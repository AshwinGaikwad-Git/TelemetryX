from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy.exc import OperationalError

from app.api.routes import health
from app.main import app


def test_readiness_returns_service_unavailable_when_database_is_down(
    monkeypatch: MonkeyPatch,
) -> None:
    def raise_operational_error() -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(health.engine, "connect", raise_operational_error)
    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database is unavailable"
