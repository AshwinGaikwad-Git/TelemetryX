"""Predictions API routes: query, filter, and inspect prediction details."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import PredictionOut
from app.db.session import get_db_session
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    model_version_id: uuid.UUID | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    return PredictionService.list_predictions(
        db=db,
        model_version_id=model_version_id,
        risk_level=risk_level,
        limit=limit,
    )


@router.get("/{prediction_id}", response_model=PredictionOut)
def get_prediction(
    prediction_id: uuid.UUID, db: Session = Depends(get_db_session)
) -> dict[str, Any]:
    pred = PredictionService.get_prediction(db, prediction_id)
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return pred
