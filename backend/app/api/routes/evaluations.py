"""Evaluations API routes: inspect model benchmark scores and per-unit error metrics."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EvaluationOut
from app.db.models import EvaluationRun
from app.db.session import get_db_session

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("", response_model=list[EvaluationOut])
def list_evaluations(db: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    stmt = select(EvaluationRun).order_by(EvaluationRun.created_at.desc())
    runs = db.scalars(stmt).all()

    results = []
    for r in runs:
        mv = r.model_version
        results.append(
            {
                "id": r.id,
                "model_version_id": r.model_version_id,
                "model_version": mv.version if mv else "unknown",
                "evaluation_role": r.evaluation_role,
                "metrics": r.metrics,
                "created_at": r.created_at,
            }
        )
    return results
