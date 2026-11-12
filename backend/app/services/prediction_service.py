"""Service for generating RUL predictions, SHAP explanations, and maintenance guidance."""

import uuid
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EngineRun,
    EvaluationRun,
    MaintenanceRecommendation,
    ModelVersion,
    PredictionExplanation,
    RulPrediction,
)
from app.ml.evaluator import evaluate_predictions
from app.ml.explainability import PredictionExplainer
from app.ml.models import GradientBoostingRULModel
from app.ml.risk import generate_recommendation, map_rul_to_risk
from app.pipelines.constants import SETTINGS_COLUMNS
from app.pipelines.features import FeatureManifest, LeakFreePreprocessor


class PredictionService:
    @staticmethod
    def list_predictions(
        db: Session,
        model_version_id: uuid.UUID | None = None,
        risk_level: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = select(RulPrediction).order_by(RulPrediction.created_at.desc())
        if model_version_id:
            stmt = stmt.where(RulPrediction.model_version_id == model_version_id)
        if risk_level:
            stmt = stmt.where(RulPrediction.risk_level == risk_level)
        stmt = stmt.limit(limit)

        predictions = db.scalars(stmt).all()
        results = []
        for p in predictions:
            run = p.engine_run
            results.append(
                {
                    "id": p.id,
                    "model_version_id": p.model_version_id,
                    "engine_run_id": p.engine_run_id,
                    "unit_number": run.unit_number if run else 0,
                    "file_role": run.file_role if run else "test",
                    "cycle": p.cycle,
                    "predicted_rul": round(p.predicted_rul, 1),
                    "lower_bound": round(p.lower_bound, 1),
                    "upper_bound": round(p.upper_bound, 1),
                    "risk_level": p.risk_level,
                    "ground_truth_rul": round(run.ground_truth_rul, 1)
                    if run and run.ground_truth_rul is not None
                    else None,
                    "created_at": p.created_at,
                    "explanation": {
                        "method": p.explanation.method,
                        "top_contributors": p.explanation.top_contributors,
                        "summary": p.explanation.summary,
                    }
                    if p.explanation
                    else None,
                    "recommendation": {
                        "recommendation_type": p.recommendation.recommendation_type,
                        "priority": p.recommendation.priority,
                        "rationale": p.recommendation.rationale,
                    }
                    if p.recommendation
                    else None,
                }
            )
        return results

    @staticmethod
    def get_prediction(db: Session, prediction_id: uuid.UUID) -> dict[str, Any] | None:
        p = db.get(RulPrediction, prediction_id)
        if not p:
            return None

        run = p.engine_run
        return {
            "id": p.id,
            "model_version_id": p.model_version_id,
            "engine_run_id": p.engine_run_id,
            "unit_number": run.unit_number if run else 0,
            "file_role": run.file_role if run else "test",
            "cycle": p.cycle,
            "predicted_rul": round(p.predicted_rul, 1),
            "lower_bound": round(p.lower_bound, 1),
            "upper_bound": round(p.upper_bound, 1),
            "risk_level": p.risk_level,
            "ground_truth_rul": round(run.ground_truth_rul, 1)
            if run and run.ground_truth_rul is not None
            else None,
            "created_at": p.created_at,
            "explanation": {
                "method": p.explanation.method,
                "top_contributors": p.explanation.top_contributors,
                "summary": p.explanation.summary,
            }
            if p.explanation
            else None,
            "recommendation": {
                "recommendation_type": p.recommendation.recommendation_type,
                "priority": p.recommendation.priority,
                "rationale": p.recommendation.rationale,
            }
            if p.recommendation
            else None,
        }

    @staticmethod
    def run_predictions_for_dataset(
        db: Session,
        model_version_id: uuid.UUID,
        dataset_id: uuid.UUID,
        role: str = "test",
    ) -> list[dict[str, Any]]:
        """Generates RUL estimates, 90% intervals, SHAP explanations, and recommendations."""
        mv = db.get(ModelVersion, model_version_id)
        if not mv:
            raise ValueError(f"ModelVersion {model_version_id} not found")

        # 1. Load model bundle
        model = GradientBoostingRULModel.load(mv.artifact_uri)
        manifest = FeatureManifest.from_dict(mv.feature_manifest)

        # 2. Load engine runs for target role
        runs = db.scalars(
            select(EngineRun)
            .where(
                EngineRun.dataset_version_id == dataset_id,
                EngineRun.file_role == role,
            )
            .order_by(EngineRun.unit_number.asc())
        ).all()
        if not runs:
            raise ValueError(f"No {role} engine runs found for dataset {dataset_id}")

        rows = []
        for r in runs:
            for c in r.cycles:
                row_dict: dict[str, Any] = {
                    "unit_number": r.unit_number,
                    "cycle": c.cycle,
                }
                for i, setting in enumerate(SETTINGS_COLUMNS):
                    row_dict[setting] = c.operational_settings[i]
                for s, val in c.sensor_values.items():
                    row_dict[s] = val
                rows.append(row_dict)

        df = pd.DataFrame(rows)

        # 3. Transform features without leakage
        preprocessor = LeakFreePreprocessor()
        X_df = preprocessor.transform(df, manifest=manifest)
        feature_cols = manifest.feature_names

        # Explainer for feature attribution
        explainer = PredictionExplainer(
            point_model=model.point_model,
            feature_names=feature_cols,
            background_data=X_df[feature_cols].to_numpy()[:20],
        )

        # Delete prior predictions for this model and dataset
        existing_preds = db.scalars(
            select(RulPrediction)
            .join(EngineRun)
            .where(
                RulPrediction.model_version_id == model_version_id,
                EngineRun.dataset_version_id == dataset_id,
            )
        ).all()
        for ep in existing_preds:
            db.delete(ep)
        db.flush()

        results = []
        true_ruls = []
        pred_ruls = []
        unit_ids = []

        # Predict for the final cycle of each unit
        for r in runs:
            unit_df = X_df[X_df["unit_number"] == r.unit_number]
            if unit_df.empty:
                continue

            final_cycle_row = unit_df.sort_values("cycle").iloc[-1]
            final_cycle = int(final_cycle_row["cycle"])
            x_vec = final_cycle_row[feature_cols].to_numpy().reshape(1, -1)

            p_rul, p_lower, p_upper = model.predict(x_vec)
            pred_val = float(p_rul[0])
            lower_val = float(p_lower[0])
            upper_val = float(p_upper[0])
            risk = map_rul_to_risk(pred_val)

            # Explain instance
            explanation_data = explainer.explain_instance(x_vec[0], top_k=5)

            # Generate recommendation
            rec = generate_recommendation(
                predicted_rul=pred_val,
                lower_bound=lower_val,
                upper_bound=upper_val,
                top_contributors=explanation_data.get("top_contributors"),
            )

            # Persist Prediction
            rul_pred = RulPrediction(
                model_version_id=mv.id,
                engine_run_id=r.id,
                cycle=final_cycle,
                predicted_rul=pred_val,
                lower_bound=lower_val,
                upper_bound=upper_val,
                risk_level=risk,
            )
            db.add(rul_pred)
            db.flush()

            # Persist Explanation
            pred_expl = PredictionExplanation(
                prediction_id=rul_pred.id,
                method=explanation_data["method"],
                baseline=explanation_data.get("baseline"),
                top_contributors=explanation_data["top_contributors"],
                summary=explanation_data.get("summary"),
            )
            db.add(pred_expl)

            # Persist Recommendation
            maint_rec = MaintenanceRecommendation(
                prediction_id=rul_pred.id,
                recommendation_type=rec.recommendation_type,
                priority=rec.priority,
                rationale=rec.rationale,
            )
            db.add(maint_rec)

            if r.ground_truth_rul is not None:
                true_ruls.append(float(r.ground_truth_rul))
                pred_ruls.append(pred_val)
                unit_ids.append(r.unit_number)

            results.append(
                {
                    "unit_number": r.unit_number,
                    "cycle": final_cycle,
                    "predicted_rul": round(pred_val, 1),
                    "lower_bound": round(lower_val, 1),
                    "upper_bound": round(upper_val, 1),
                    "risk_level": risk,
                    "ground_truth_rul": round(r.ground_truth_rul, 1)
                    if r.ground_truth_rul is not None
                    else None,
                    "summary": explanation_data.get("summary"),
                }
            )

        # 4. If ground truth RUL was available for test units, compute official test evaluation
        if true_ruls:
            test_report = evaluate_predictions(
                np.array(true_ruls), np.array(pred_ruls), unit_ids=unit_ids
            )
            eval_run = EvaluationRun(
                model_version_id=mv.id,
                dataset_version_id=dataset_id,
                evaluation_role="test",
                metrics=test_report.to_dict(),
            )
            db.add(eval_run)

        db.commit()
        return results
