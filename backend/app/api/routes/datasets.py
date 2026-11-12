"""Datasets API routes: listing, file import, sample loading, and engine runs."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import DatasetDetailOut, DatasetVersionOut, EngineRunSummary
from app.db.models import DatasetVersion, EngineRun, RulPrediction
from app.db.session import get_db_session
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetVersionOut])
def list_datasets(db: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return DatasetService.list_datasets(db)


@router.post("/sample", response_model=dict[str, Any])
def load_sample_dataset(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    """Loads and validates the committed synthetic C-MAPSS FD001 fixtures."""
    try:
        return DatasetService.load_samples(db)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@router.post("/imports", response_model=dict[str, Any])
async def import_dataset_file(
    file: UploadFile = File(...),
    dataset_code: Annotated[str, Form()] = "FD001",
    file_role: Annotated[str, Form()] = "train",  # train, test, test_rul
    dataset_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Uploads and ingests a C-MAPSS raw file (train, test, or test_rul)."""
    if file_role not in ("train", "test", "test_rul"):
        raise HTTPException(status_code=400, detail=f"Invalid file_role: {file_role}")

    if dataset_id:
        ds = db.get(DatasetVersion, uuid.UUID(dataset_id))
        if not ds:
            raise HTTPException(status_code=404, detail="DatasetVersion not found")
    else:
        ds = DatasetService.get_or_create_dataset_version(db, dataset_code=dataset_code)

    content = await file.read()
    try:
        result = DatasetService.ingest_file_content(
            db=db,
            dataset_id=ds.id,
            file_role=file_role,
            filename=file.filename or f"{dataset_code}_{file_role}.txt",
            content=content,
        )
        return {"dataset_id": ds.id, **result}
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.get("/{dataset_id}", response_model=DatasetDetailOut)
def get_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    ds = DatasetService.get_dataset(db, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@router.get("/{dataset_id}/engines", response_model=list[EngineRunSummary])
def list_dataset_engines(
    dataset_id: uuid.UUID,
    role: str | None = None,
    db: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(EngineRun)
        .where(EngineRun.dataset_version_id == dataset_id)
        .order_by(EngineRun.unit_number.asc())
    )
    if role:
        stmt = stmt.where(EngineRun.file_role == role)

    runs = db.scalars(stmt).all()
    results = []
    for r in runs:
        pred = db.scalars(
            select(RulPrediction)
            .where(RulPrediction.engine_run_id == r.id)
            .order_by(RulPrediction.created_at.desc())
        ).first()

        results.append(
            {
                "id": r.id,
                "dataset_version_id": r.dataset_version_id,
                "file_role": r.file_role,
                "unit_number": r.unit_number,
                "max_cycle": r.max_cycle,
                "ground_truth_rul": r.ground_truth_rul,
                "predicted_rul": round(pred.predicted_rul, 1) if pred else None,
                "risk_level": pred.risk_level if pred else None,
                "created_at": r.created_at,
            }
        )
    return results
