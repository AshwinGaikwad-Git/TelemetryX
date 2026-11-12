"""Service for aggregating fleet overview KPIs, risk distributions, and alerts."""

from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelVersion, RulPrediction


class DashboardService:
    @staticmethod
    def get_fleet_summary(db: Session) -> dict[str, Any]:
        # 1. Fetch latest predictions
        stmt_preds = select(RulPrediction).order_by(RulPrediction.created_at.desc())
        preds = db.scalars(stmt_preds).all()

        risk_dist = {"healthy": 0, "planning": 0, "attention": 0, "urgent": 0}
        critical_engines = []
        recommendations = []
        ruls = []

        # Deduplicate to latest prediction per engine run
        seen_runs = set()
        for p in preds:
            if p.engine_run_id in seen_runs:
                continue
            seen_runs.add(p.engine_run_id)

            run = p.engine_run
            ruls.append(p.predicted_rul)
            risk = p.risk_level.lower()
            if risk in risk_dist:
                risk_dist[risk] += 1

            if risk in ("urgent", "attention"):
                critical_engines.append(
                    {
                        "engine_run_id": str(p.engine_run_id),
                        "unit_number": run.unit_number if run else 0,
                        "cycle": p.cycle,
                        "predicted_rul": round(p.predicted_rul, 1),
                        "lower_bound": round(p.lower_bound, 1),
                        "upper_bound": round(p.upper_bound, 1),
                        "risk_level": p.risk_level,
                        "recommendation": p.recommendation.rationale if p.recommendation else None,
                    }
                )

            if p.recommendation:
                recommendations.append(
                    {
                        "unit_number": run.unit_number if run else 0,
                        "priority": p.recommendation.priority,
                        "type": p.recommendation.recommendation_type,
                        "rationale": p.recommendation.rationale,
                    }
                )

        # Sort critical engines by predicted RUL ascending
        critical_engines.sort(key=lambda x: float(str(x["predicted_rul"])))

        total_count = len(seen_runs) if seen_runs else 0

        # Latest active model
        stmt_m = select(ModelVersion).order_by(ModelVersion.created_at.desc())
        latest_model = db.scalars(stmt_m).first()

        active_model_dict = None
        if latest_model:
            active_model_dict = {
                "id": str(latest_model.id),
                "version": latest_model.version,
                "metrics": latest_model.metrics,
                "status": latest_model.status,
            }

        mean_rul = float(np.mean(ruls)) if ruls else 0.0

        return {
            "fleet_size": total_count,
            "mean_predicted_rul": round(mean_rul, 1),
            "risk_distribution": risk_dist,
            "attention_required_count": risk_dist["urgent"] + risk_dist["attention"],
            "active_model": active_model_dict,
            "critical_engines": critical_engines[:10],
            "latest_recommendations": recommendations[:10],
        }
