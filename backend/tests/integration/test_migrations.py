import uuid

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import get_settings


def test_timestamp_repair_preserves_migrated_assets_and_allows_registration(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.db.session import get_db_session
    from app.main import app

    url = f"sqlite:///{tmp_path / 'industrial-migration.db'}"
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "20261113_0004")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    company_id, site_id, machine_id = [uuid.uuid4().hex for _ in range(3)]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO industrial_companies (id, name, created_at) "
                "VALUES (:id, 'Existing company', CURRENT_TIMESTAMP)"
            ),
            {"id": company_id},
        )
        connection.execute(
            text(
                "INSERT INTO industrial_sites (id, company_id, name, timezone, location) "
                "VALUES (:id, :company, 'Existing site', 'UTC', '')"
            ),
            {"id": site_id, "company": company_id},
        )
        connection.execute(
            text(
                "INSERT INTO industrial_machines "
                "(id, company_id, site_id, asset_tag, name, equipment_type, "
                "manufacturer, model, area, "
                "criticality, operating_state, notes, created_at) VALUES "
                "(:id, :company, :site, 'EXISTING', 'Existing machine', 'Pump', '', '', '', "
                "'medium', 'stopped', '', CURRENT_TIMESTAMP)"
            ),
            {"id": machine_id, "company": company_id, "site": site_id},
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT name FROM industrial_machines WHERE id=:id"), {"id": machine_id}
            ).scalar()
            == "Existing machine"
        )
        assert not connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    factory = sessionmaker(bind=engine)

    def session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = session
    client = TestClient(app)
    response = client.post(
        "/api/v1/industrial/auth/register",
        json={
            "email": "migrated@example.com",
            "password": "a-valid-long-password",
            "name": "Migrated user",
            "company_name": "Registered after migration",
        },
    )
    assert response.status_code == 201, response.text
    assert client.get("/api/v1/industrial/auth/me").status_code == 200
    company = response.json()["companies"][0]["id"]
    assert (
        client.post(
            f"/api/v1/industrial/companies/{company}/sites", json={"name": "New site"}
        ).status_code
        == 201
    )
    client.close()
    app.dependency_overrides.pop(get_db_session)
    engine.dispose()


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
