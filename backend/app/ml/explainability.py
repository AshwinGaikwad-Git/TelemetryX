"""Prediction explainability using SHAP and feature attribution."""

from typing import Any

import numpy as np
import shap

from app.pipelines.constants import SENSOR_DESCRIPTIONS


class PredictionExplainer:
    """Computes per-prediction feature contributions to explain individual engine RUL estimates."""

    def __init__(
        self, point_model: Any, feature_names: list[str], background_data: np.ndarray | None = None
    ) -> None:
        self.point_model = point_model
        self.feature_names = feature_names

        # Use background sample if provided, otherwise standard TreeExplainer
        try:
            if background_data is not None and len(background_data) > 0:
                bg = background_data[: min(50, len(background_data))]
                self.explainer = shap.Explainer(self.point_model.predict, bg)
            else:
                self.explainer = shap.TreeExplainer(self.point_model)
        except Exception:
            # Fallback to general explainer
            self.explainer = shap.Explainer(self.point_model)

    def explain_instance(
        self,
        features: np.ndarray,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Explains a single prediction given its feature row vector.

        Returns:
            dict containing baseline_value, top_contributors, and summary text.
        """
        x_2d = np.asarray(features, dtype=float).reshape(1, -1)

        try:
            shap_values = self.explainer(x_2d)
            if hasattr(shap_values, "values"):
                vals = np.asarray(shap_values.values[0], dtype=float)
                base_val = (
                    float(shap_values.base_values[0])
                    if hasattr(shap_values, "base_values")
                    else 0.0
                )
            else:
                vals = np.asarray(shap_values[0], dtype=float)
                base_val = 0.0
        except Exception:
            # Safe numerical perturbation fallback if TreeExplainer structure fails
            pred_base = float(self.point_model.predict(x_2d)[0])
            base_val = pred_base
            vals = np.zeros(len(self.feature_names))
            for i in range(len(self.feature_names)):
                x_perturbed = x_2d.copy()
                x_perturbed[0, i] += 0.05
                pred_perturbed = float(self.point_model.predict(x_perturbed)[0])
                vals[i] = pred_perturbed - pred_base

        contributors: list[dict[str, Any]] = []
        for i, val in enumerate(vals):
            feat = self.feature_names[i]
            direction = "increases_rul" if val >= 0 else "decreases_rul"
            # Extract plain readable sensor label if available
            root_sensor = (
                feat.split("_")[0] + "_" + feat.split("_")[1]
                if feat.startswith("sensor_")
                else feat
            )
            desc = SENSOR_DESCRIPTIONS.get(root_sensor, feat)

            contributors.append(
                {
                    "feature": feat,
                    "description": desc,
                    "attribution": round(float(val), 3),
                    "magnitude": round(float(abs(val)), 3),
                    "direction": direction,
                }
            )

        # Sort contributors by absolute magnitude
        contributors.sort(key=lambda c: float(c["magnitude"]), reverse=True)
        top_contributors = contributors[:top_k]

        # Plain language summary
        neg_drivers = [
            str(c["description"]).split(" - ")[0]
            for c in top_contributors
            if c["direction"] == "decreases_rul"
        ]
        pos_drivers = [
            str(c["description"]).split(" - ")[0]
            for c in top_contributors
            if c["direction"] == "increases_rul"
        ]

        summary_parts = []
        if neg_drivers:
            summary_parts.append(
                f"Degradation indicators driving RUL reduction: {', '.join(neg_drivers[:3])}."
            )
        if pos_drivers:
            summary_parts.append(
                f"Telemetry features supporting remaining life: {', '.join(pos_drivers[:2])}."
            )
        if not summary_parts:
            summary_parts.append("Prediction aligns with nominal operational baseline telemetry.")

        summary = " ".join(summary_parts)

        return {
            "method": "shap_attribution",
            "baseline": {"expected_value": round(base_val, 2)},
            "top_contributors": top_contributors,
            "summary": summary,
        }
