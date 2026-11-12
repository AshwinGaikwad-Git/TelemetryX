"""Operator recovery after stopping all workers: python -m app.workers.recover."""

from sqlalchemy import select

from app.db.models import JobRun
from app.db.session import SessionLocal


def recover() -> int:
    with SessionLocal() as db:
        jobs = db.scalars(select(JobRun).where(JobRun.status == "running")).all()
        for job in jobs:
            job.status = "failed"
            job.error = (
                "Worker execution was interrupted. Retry explicitly after inspecting outputs."
            )
        db.commit()
        return len(jobs)


if __name__ == "__main__":
    print(
        f"Marked {recover()} interrupted jobs as failed. Restart workers, then retry through /jobs."
    )
