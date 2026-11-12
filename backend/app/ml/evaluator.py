"""Evaluation metrics for RUL prediction including the official NASA C-MAPSS scoring function."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def calculate_nasa_score(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, np.ndarray]:
    """Calculates the official asymmetric NASA scoring function for RUL.

    Formula:
      d = y_pred - y_true (error in cycles)
      s_i = exp(-d / 13) - 1   if d < 0  (underestimation / conservative)
      s_i = exp(d / 10) - 1    if d >= 0 (overestimation / dangerous)
      Score = sum(s_i)

    Returns:
      (total_score, per_unit_scores)
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    diff = y_p - y_t

    penalties = np.where(
        diff < 0,
        np.exp(-diff / 13.0) - 1.0,
        np.exp(diff / 10.0) - 1.0,
    )
    total_score = float(np.sum(penalties))
    return total_score, penalties


@dataclass
class EvaluationReport:
    rmse: float
    mae: float
    r2: float
    nasa_score: float
    per_unit_results: list[dict[str, Any]]
    band_metrics: dict[str, dict[str, float]]
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rmse": round(self.rmse, 3),
            "mae": round(self.mae, 3),
            "r2": round(self.r2, 4),
            "nasa_score": round(self.nasa_score, 2),
            "sample_size": self.sample_size,
            "band_metrics": self.band_metrics,
            "per_unit_results": self.per_unit_results,
        }


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    unit_ids: list[int] | None = None,
) -> EvaluationReport:
    """Computes comprehensive evaluation metrics comparing predicted RUL to ground truth."""
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)

    if len(y_t) != len(y_p):
        raise ValueError(f"Length mismatch: {len(y_t)} true vs {len(y_p)} predictions")

    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    mae = float(mean_absolute_error(y_t, y_p))
    r2 = float(r2_score(y_t, y_p)) if len(y_t) > 1 else 1.0
    nasa_score, penalties = calculate_nasa_score(y_t, y_p)

    errors = y_p - y_t
    units = unit_ids if unit_ids is not None else list(range(1, len(y_t) + 1))

    per_unit = []
    for i in range(len(y_t)):
        per_unit.append(
            {
                "unit_number": int(units[i]),
                "actual_rul": round(float(y_t[i]), 1),
                "predicted_rul": round(float(y_p[i]), 1),
                "error": round(float(errors[i]), 1),
                "abs_error": round(float(abs(errors[i])), 1),
                "nasa_penalty": round(float(penalties[i]), 2),
            }
        )

    # Error statistics across true-RUL bands
    band_defs = {
        "urgent_under_15": y_t < 15,
        "planning_15_to_30": (y_t >= 15) & (y_t <= 30),
        "healthy_over_30": y_t > 30,
    }
    band_metrics = {}
    for band_name, mask in band_defs.items():
        if np.any(mask):
            band_metrics[band_name] = {
                "count": int(np.sum(mask)),
                "mae": round(float(mean_absolute_error(y_t[mask], y_p[mask])), 2),
                "rmse": round(float(np.sqrt(mean_squared_error(y_t[mask], y_p[mask]))), 2),
            }
        else:
            band_metrics[band_name] = {"count": 0, "mae": 0.0, "rmse": 0.0}

    return EvaluationReport(
        rmse=rmse,
        mae=mae,
        r2=r2,
        nasa_score=nasa_score,
        per_unit_results=per_unit,
        band_metrics=band_metrics,
        sample_size=len(y_t),
    )
