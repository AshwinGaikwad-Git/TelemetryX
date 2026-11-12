"""ML package: models, evaluation, explainability, and risk scoring."""

from app.ml.evaluator import EvaluationReport, calculate_nasa_score, evaluate_predictions
from app.ml.explainability import PredictionExplainer
from app.ml.models import GradientBoostingRULModel, NaiveBaselineModel
from app.ml.risk import (
    MaintenanceRecommendationResult,
    generate_recommendation,
    map_rul_to_risk,
)

__all__ = [
    "calculate_nasa_score",
    "evaluate_predictions",
    "EvaluationReport",
    "NaiveBaselineModel",
    "GradientBoostingRULModel",
    "PredictionExplainer",
    "map_rul_to_risk",
    "generate_recommendation",
    "MaintenanceRecommendationResult",
]
