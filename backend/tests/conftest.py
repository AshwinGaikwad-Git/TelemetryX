"""Tests never connect to the user's database or write into their data/model folders."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_storage = tempfile.TemporaryDirectory(prefix="telemetryx-tests-")
_root = Path(_storage.name)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["RAW_STORAGE_PATH"] = str(_root / "raw")
os.environ["PROCESSED_STORAGE_PATH"] = str(_root / "processed")
os.environ["MODEL_STORAGE_PATH"] = str(_root / "models")
os.environ["JOB_BACKEND"] = "local"
os.environ["OMP_NUM_THREADS"] = "1"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.industrial.auth import _attempts  # noqa: E402
from app.main import app  # noqa: E402
from app.services import job_service  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    _attempts.clear()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def session() -> Iterator[object]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = session
    monkeypatch.setattr(job_service, "SessionLocal", factory)
    # Execute explicitly in tests; a separate test verifies real executor dispatch.
    monkeypatch.setattr(job_service, "dispatch", lambda job_id: None)
    yield
    app.dependency_overrides.clear()
    engine.dispose()
