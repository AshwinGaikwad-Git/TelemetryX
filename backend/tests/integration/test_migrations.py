import uuid

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import get_settings


def test_upgrade_preserves_existing_job_rows(tmp_path, monkeypatch) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20260902_0002")
    engine = create_engine(url)
    identity = uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO job_runs (id, job_type, idempotency_key) "
                "VALUES (:id, 'smoke', 'old-job')"
            ),
            {"id": identity},
        )
    command.upgrade(config, "head")
    assert {"payload", "result"} <= {c["name"] for c in inspect(engine).get_columns("job_runs")}
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT payload, status FROM job_runs WHERE id = :id"), {"id": identity}
        ).one()
        assert row[0] == "{}"
        assert row[1] == "queued"
    command.downgrade(config, "20260902_0002")
    assert "payload" not in {c["name"] for c in inspect(engine).get_columns("job_runs")}
    command.upgrade(config, "head")
    engine.dispose()
