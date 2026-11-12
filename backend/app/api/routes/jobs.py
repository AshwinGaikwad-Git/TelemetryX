import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import JobRun
from app.db.session import get_db_session
from app.services.job_service import dispatch, job_dict

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    job = db.get(JobRun, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job_dict(job)


@router.post("/{job_id}/retry", status_code=202)
def retry_job(job_id: uuid.UUID, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    job = db.get(JobRun, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried")
    db.execute(
        update(JobRun)
        .where(JobRun.id == job_id, JobRun.status == "failed")
        .values(
            status="queued",
            error=None,
            result=None,
            attempt_count=0,
        )
    )
    db.commit()
    try:
        dispatch(job_id)
    except Exception as error:
        job.status = "failed"
        job.error = str(error)[:2000]
        db.commit()
    db.refresh(job)
    return job_dict(job)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db_session)) -> dict[str, Any]:
    result = db.execute(
        update(JobRun)
        .where(
            JobRun.id == job_id,
            JobRun.status == "queued",
        )
        .values(status="cancelled")
    )
    db.commit()
    if result.rowcount != 1:  # type: ignore[attr-defined]
        raise HTTPException(409, "Only queued jobs can be cancelled")
    job = db.get(JobRun, job_id)
    assert job is not None
    return job_dict(job)
