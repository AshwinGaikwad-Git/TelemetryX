"""Datasets API routes: listing, file import, sample loading, and engine runs."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import DatasetDetailOut, DatasetVersionOut, EngineRunSummary
from app.core.config import get_settings
from app.db.models import DatasetVersion, EngineRun, RulPrediction
from app.db.session import get_db_session
from app.pipelines.parser import calculate_sha256
from app.services.dataset_service import DatasetService
from app.services.job_service import enqueue, job_dict

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetVersionOut])
def list_datasets(db: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return DatasetService.list_datasets(db)


@router.post("/sample", status_code=202)
def load_sample_dataset(
    db: Session = Depends(get_db_session),
    idempotency_key: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return job_dict(enqueue(db, "sample", {}, idempotency_key))
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.post("", status_code=201)
def create_dataset(db: Session = Depends(get_db_session)) -> dict[str, str]:
    ds = DatasetService.get_or_create_dataset_version(db)
    return {"dataset_id": str(ds.id)}


@router.post("/{dataset_id}/prepare", status_code=202)
def prepare_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    if not db.get(DatasetVersion, dataset_id):
        raise HTTPException(404, "Dataset not found")
    return job_dict(enqueue(db, "prepare", {"dataset_id": str(dataset_id)}))


@router.post("/imports", status_code=202)
async def import_dataset_file(
    file: UploadFile = File(...),
    dataset_code: Annotated[str, Form()] = "FD001",
    file_role: Annotated[str, Form()] = "train",
    dataset_id: Annotated[uuid.UUID | None, Form()] = None,
    db: Session = Depends(get_db_session),
    idempotency_key: str | None = Header(default=None),
) -> dict[str, Any]:
    if file_role not in ("train", "test", "test_rul") or dataset_code != "FD001":
        raise HTTPException(400, "Supported roles: train/test/test_rul; subset: FD001")
    # Bound memory while reading, including uploads without a Content-Length header.
    limit = get_settings().max_upload_size_mb * 1024 * 1024
    content = bytearray()
    while chunk := await file.read(min(1024 * 1024, limit + 1 - len(content))):
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "Upload exceeds MAX_UPLOAD_SIZE_MB")
    if dataset_id:
        ds = db.get(DatasetVersion, dataset_id)
        if not ds:
            raise HTTPException(404, "Dataset version not found")
    else:
        ds = DatasetService.get_or_create_dataset_version(db, dataset_code=dataset_code)
    checksum = calculate_sha256(bytes(content))
    directory = get_settings().raw_storage_path / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{checksum}.txt"
    if not path.exists():
        path.write_bytes(bytes(content))
    payload = {
        "dataset_id": str(ds.id),
        "file_role": file_role,
        "filename": file.filename or f"{file_role}.txt",
        "storage_uri": str(path),
    }
    try:
        job = enqueue(db, "import", payload, idempotency_key)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {**job_dict(job), "dataset_id": str(ds.id)}


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
    model_version_id: uuid.UUID | None = None,
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
        query = select(RulPrediction).where(RulPrediction.engine_run_id == r.id)
        if model_version_id:
            query = query.where(RulPrediction.model_version_id == model_version_id)
        pred = db.scalars(query.order_by(RulPrediction.created_at.desc())).first()

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
