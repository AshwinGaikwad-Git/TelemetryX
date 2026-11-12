"""Unit tests for ML models, NASA evaluation score, SHAP explainability, and risk logic."""

import numpy as np
import pytest

from app.ml.evaluator import calculate_nasa_score, evaluate_predictions
from app.ml.explainability import PredictionExplainer
from app.ml.models import GradientBoostingRULModel
from app.ml.risk import generate_recommendation, map_rul_to_risk


def test_nasa_score_asymmetric_penalties() -> None:
    # 1. Underestimating RUL by 10 cycles (y_pred = 40, d = -10)
    score_under, _ = calculate_nasa_score(np.array([50.0]), np.array([40.0]))

    # 2. Overestimating RUL by 10 cycles (y_pred = 60, d = +10)
    score_over, _ = calculate_nasa_score(np.array([50.0]), np.array([60.0]))

    # NASA formula penalizes late failure prediction (overestimation) more than early:
    # d = -10 => exp(10/13) - 1 ≈ 1.158
    # d = +10 => exp(10/10) - 1 = e - 1 ≈ 1.718
    assert score_over > score_under
    assert score_under == pytest.approx(np.exp(10.0 / 13.0) - 1.0, rel=1e-3)
    assert score_over == pytest.approx(np.exp(1.0) - 1.0, rel=1e-3)


def test_evaluate_predictions_produces_band_metrics() -> None:
    y_true = np.array([5.0, 20.0, 60.0])
    y_pred = np.array([6.0, 18.0, 55.0])

    report = evaluate_predictions(y_true, y_pred, unit_ids=[1, 2, 3])

    assert report.sample_size == 3
    assert report.rmse > 0
    assert report.mae > 0
    assert "urgent_under_15" in report.band_metrics
    assert report.band_metrics["urgent_under_15"]["count"] == 1
    assert len(report.per_unit_results) == 3


def test_gradient_boosting_model_predicts_with_intervals() -> None:
    rng = np.random.default_rng(42)
    # Generate synthetic features
    X = rng.normal(size=(60, 5))
    # Synthetic target with linear relation + noise
    y = np.maximum(0.0, 100.0 - 15.0 * X[:, 0] + rng.normal(0, 2.0, size=60))

    model = GradientBoostingRULModel(max_iter=30, random_state=42)
    model.fit(X, y)

    preds, lower, upper = model.predict(X[:10])

    assert len(preds) == 10
    assert np.all(preds >= 0.0)
    assert np.all(lower <= preds + 1e-5)
    assert np.all(preds <= upper + 1e-5)


def test_risk_mapping_thresholds() -> None:
    assert map_rul_to_risk(45.0) == "healthy"
    assert map_rul_to_risk(30.1) == "healthy"
    assert map_rul_to_risk(30.0) == "planning"
    assert map_rul_to_risk(15.0) == "planning"
    assert map_rul_to_risk(14.9) == "attention"
    assert map_rul_to_risk(5.0) == "attention"
    assert map_rul_to_risk(4.9) == "urgent"
    assert map_rul_to_risk(0.0) == "urgent"


def test_recommendation_generation() -> None:
    rec_urgent = generate_recommendation(
        predicted_rul=3.2,
        lower_bound=1.0,
        upper_bound=6.5,
        top_contributors=[
            {
                "feature": "sensor_11_slope_15",
                "description": "Ps30 - Static pressure",
                "direction": "decreases_rul",
            }
        ],
    )
    assert rec_urgent.priority == "urgent"
    assert "URGENT" in rec_urgent.rationale
    assert "Ps30" in rec_urgent.rationale
    assert "Simulated C-MAPSS benchmark" in rec_urgent.rationale

    rec_healthy = generate_recommendation(predicted_rul=45.0, lower_bound=38.0, upper_bound=52.0)
    assert rec_healthy.priority == "healthy"
    assert "HEALTHY" in rec_healthy.rationale


def test_explainability_attribution() -> None:
    rng = np.random.default_rng(42)
    X = rng.normal(size=(50, 4))
    y = np.maximum(0.0, 80.0 + 20.0 * X[:, 0] - 30.0 * X[:, 1])

    model = GradientBoostingRULModel(max_iter=25, random_state=42)
    model.fit(X, y)

    explainer = PredictionExplainer(
        point_model=model.point_model,
        feature_names=["sensor_2", "sensor_3", "sensor_4", "cycle_norm"],
        background_data=X[:10],
    )

    explanation = explainer.explain_instance(X[0], top_k=2)
    assert "top_contributors" in explanation
    assert len(explanation["top_contributors"]) <= 2
    assert "summary" in explanation
    top_c = explanation["top_contributors"]
    assert top_c[0]["magnitude"] >= top_c[1]["magnitude"]


def test_interval_metrics_measure_coverage_and_width() -> None:
    report = evaluate_predictions(
        np.array([10.0, 20.0]),
        np.array([12.0, 18.0]),
        lower_bounds=np.array([9.0, 15.0]),
        upper_bounds=np.array([15.0, 19.0]),
    )
    assert report.interval_metrics == {
        "nominal_coverage": 0.9,
        "empirical_coverage": 0.5,
        "mean_width": 5.0,
    }


def test_explanation_fallback_is_labelled_as_sensitivity() -> None:
    class Estimator:
        def predict(self, values):
            return values.sum(axis=1)

    explainer = PredictionExplainer(Estimator(), ["sensor_2", "sensor_3"])
    explainer.explainer = None
    result = explainer.explain_instance(np.array([1.0, 2.0]))
    assert result["method"] == "local_perturbation"
    assert "not SHAP" in result["summary"]
