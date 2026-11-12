"""Models API routes: list trained model versions and execute batch predictions."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import ModelVersionOut
from app.db.models import ModelVersion
from app.db.session import get_db_session
from app.services.experiment_service import ExperimentService
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelVersionOut])
def list_models(db: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return ExperimentService.list_models(db)


@router.get("/{model_id}", response_model=dict[str, Any])
def get_model(model_id: uuid.UUID, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    m = db.get(ModelVersion, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model version not found")

    return {
        "id": m.id,
        "experiment_id": m.experiment_id,
        "version": m.version,
        "artifact_uri": m.artifact_uri,
        "feature_manifest": m.feature_manifest,
        "metrics": m.metrics,
        "status": m.status,
        "created_at": m.created_at,
    }


@router.post("/{model_id}/predictions", response_model=list[dict[str, Any]])
def run_predictions(
    model_id: uuid.UUID,
    dataset_id: uuid.UUID = Query(...),
    role: str = Query(default="test"),
    db: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    try:
        return PredictionService.run_predictions_for_dataset(
            db=db,
            model_version_id=model_id,
            dataset_id=dataset_id,
            role=role,
        )
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
