"""Engines API routes: detailed run inspection and cycle-level telemetry time-series."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EngineCycleTelemetry, EngineRunDetail
from app.db.models import EngineCycle, EngineRun, RulPrediction
from app.db.session import get_db_session

router = APIRouter(prefix="/engines", tags=["engines"])


@router.get("/{engine_run_id}", response_model=EngineRunDetail)
def get_engine_detail(
    engine_run_id: uuid.UUID, db: Session = Depends(get_db_session)
) -> dict[str, Any]:
    run = db.get(EngineRun, engine_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Engine run not found")

    pred = db.scalars(
        select(RulPrediction)
        .where(RulPrediction.engine_run_id == run.id)
        .order_by(RulPrediction.created_at.desc())
    ).first()

    pred_dict = None
    expl_dict = None
    rec_dict = None

    if pred:
        pred_dict = {
            "id": str(pred.id),
            "predicted_rul": round(pred.predicted_rul, 1),
            "lower_bound": round(pred.lower_bound, 1),
            "upper_bound": round(pred.upper_bound, 1),
            "risk_level": pred.risk_level,
            "cycle": pred.cycle,
        }
        if pred.explanation:
            expl_dict = {
                "method": pred.explanation.method,
                "baseline": pred.explanation.baseline,
                "top_contributors": pred.explanation.top_contributors,
                "summary": pred.explanation.summary,
            }
        if pred.recommendation:
            rec_dict = {
                "recommendation_type": pred.recommendation.recommendation_type,
                "priority": pred.recommendation.priority,
                "rationale": pred.recommendation.rationale,
                "status": pred.recommendation.status,
            }

    return {
        "id": run.id,
        "dataset_version_id": run.dataset_version_id,
        "file_role": run.file_role,
        "unit_number": run.unit_number,
        "max_cycle": run.max_cycle,
        "ground_truth_rul": round(run.ground_truth_rul, 1)
        if run.ground_truth_rul is not None
        else None,
        "predicted_rul": pred_dict["predicted_rul"] if pred_dict else None,
        "risk_level": pred_dict["risk_level"] if pred_dict else None,
        "created_at": run.created_at,
        "prediction": pred_dict,
        "explanation": expl_dict,
        "recommendation": rec_dict,
    }


@router.get("/{engine_run_id}/cycles", response_model=list[EngineCycleTelemetry])
def get_engine_cycles(
    engine_run_id: uuid.UUID,
    start_cycle: int = Query(default=1, ge=1),
    end_cycle: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    run = db.get(EngineRun, engine_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Engine run not found")

    stmt = (
        select(EngineCycle)
        .where(
            EngineCycle.engine_run_id == engine_run_id,
            EngineCycle.cycle >= start_cycle,
        )
        .order_by(EngineCycle.cycle.asc())
    )
    if end_cycle:
        stmt = stmt.where(EngineCycle.cycle <= end_cycle)

    cycles = db.scalars(stmt).all()
    return [
        {
            "cycle": c.cycle,
            "operational_settings": c.operational_settings,
            "sensor_values": c.sensor_values,
        }
        for c in cycles
    ]
