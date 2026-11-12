"""Experiments API routes: creating and monitoring training runs."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ExperimentCreate, ExperimentOut
from app.db.models import Experiment
from app.db.session import get_db_session
from app.services.experiment_service import ExperimentService
from app.services.job_service import enqueue, job_dict

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentOut])
def list_experiments(db: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return ExperimentService.list_experiments(db)


@router.post("", status_code=202)
def run_experiment(
    req: ExperimentCreate,
    db: Session = Depends(get_db_session),
    idempotency_key: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return job_dict(enqueue(db, "train", req.model_dump(mode="json"), idempotency_key))
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/{experiment_id}", response_model=dict[str, Any])
def get_experiment(
    experiment_id: uuid.UUID, db: Session = Depends(get_db_session)
) -> dict[str, Any]:
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mv = exp.models[0] if exp.models else None
    return {
        "id": exp.id,
        "name": exp.name,
        "dataset_version_id": exp.dataset_version_id,
        "algorithm": exp.algorithm,
        "hyperparameters": exp.hyperparameters,
        "split_definition": exp.split_definition,
        "random_seed": exp.random_seed,
        "status": exp.status,
        "created_at": exp.created_at,
        "model_version": {
            "id": str(mv.id),
            "version": mv.version,
            "artifact_uri": mv.artifact_uri,
            "metrics": mv.metrics,
            "feature_manifest": mv.feature_manifest,
        }
        if mv
        else None,
    }
