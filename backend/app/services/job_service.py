"""Persistent job state shared by the local executor and Redis workers."""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import JobRun
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="telemetryx-job")


def job_dict(job: JobRun) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "error": job.error,
        "result": job.result,
    }


def dispatch(job_id: uuid.UUID) -> None:
    if get_settings().job_backend == "redis":
        from app.workers.tasks import execute_job

        execute_job.send(str(job_id))
    else:
        executor.submit(run_job, str(job_id))


def enqueue(db: Session, kind: str, payload: dict[str, Any], key: str | None = None) -> JobRun:
    key = key or str(uuid.uuid4())
    existing = db.scalars(select(JobRun).where(JobRun.idempotency_key == key)).first()
    if existing:
        if existing.job_type != kind or existing.payload != payload:
            raise ValueError("Idempotency key was already used for a different request")
        return existing
    job = JobRun(job_type=kind, payload=payload, idempotency_key=key, status="queued")
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return enqueue(db, kind, payload, key)
    try:
        dispatch(job.id)
    except Exception as error:
        job.status = "failed"
        job.error = f"Could not submit job: {error}. Retry after restoring the worker/broker."
        db.commit()
    return job


def perform(db: Session, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path

    from app.api.schemas import ExperimentCreate
    from app.services.dataset_service import DatasetService
    from app.services.experiment_service import ExperimentService
    from app.services.prediction_service import PredictionService

    if kind == "sample":
        return DatasetService.load_samples(db)
    if kind == "import":
        return DatasetService.ingest_file_content(
            db,
            uuid.UUID(payload["dataset_id"]),
            payload["file_role"],
            payload["filename"],
            Path(payload["storage_uri"]).read_bytes(),
        )
    if kind == "prepare":
        fs = DatasetService.prepare_feature_set(db, uuid.UUID(payload["dataset_id"]))
        return {"feature_set_id": str(fs.id)}
    if kind == "train":
        return ExperimentService.run_training_experiment(
            db, ExperimentCreate.model_validate(payload)
        )
    if kind == "predict":
        predictions = PredictionService.run_predictions_for_dataset(
            db,
            uuid.UUID(payload["model_id"]),
            uuid.UUID(payload["dataset_id"]),
            payload["role"],
        )
        return {"predictions": predictions}
    raise ValueError(f"Unknown job type: {kind}")


def run_job(job_id: str) -> None:
    """Claim once, retry only transient failures, and persist a pollable result."""
    identity = uuid.UUID(job_id)
    with SessionLocal() as db:
        claimed = db.execute(
            update(JobRun)
            .where(
                JobRun.id == identity,
                JobRun.status == "queued",
            )
            .values(status="running")
        )
        db.commit()
        if claimed.rowcount != 1:  # type: ignore[attr-defined]
            return
        job = db.get(JobRun, identity)
        assert job is not None
        for attempt in range(1, get_settings().job_max_attempts + 1):
            job.attempt_count = attempt
            db.commit()
            try:
                result = perform(db, job.job_type, job.payload)
                if result.get("status") == "failed":
                    job.status = "failed"
                    job.result = jsonable_encoder(result)
                    job.error = "File validation failed. Inspect result.report.errors."
                else:
                    job.result = jsonable_encoder(result)
                    job.status = "succeeded"
                    job.error = None
                db.commit()
                return
            except Exception as error:
                db.rollback()
                logger.exception("job_attempt_failed", extra={"job_id": job_id, "attempt": attempt})
                job = db.get(JobRun, identity)
                assert job is not None
                if (
                    isinstance(error, (OperationalError, OSError))
                    and attempt < get_settings().job_max_attempts
                ):
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                job.status = "failed"
                job.error = str(error)[:2000]
                db.commit()
                return


def recover_local_jobs() -> None:
    """The development executor supports a single API process, including reloads."""
    if get_settings().job_backend != "local":
        return
    with SessionLocal() as db:
        interrupted = db.scalars(select(JobRun).where(JobRun.status == "running")).all()
        for job in interrupted:
            job.status = "failed"
            job.error = "API process stopped during execution. Retry this job explicitly."
        db.commit()
        pending = db.scalars(select(JobRun).where(JobRun.status == "queued")).all()
        for job in pending:
            dispatch(job.id)
