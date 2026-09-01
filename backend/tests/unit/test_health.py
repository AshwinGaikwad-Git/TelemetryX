from fastapi.testclient import TestClient

from app.main import app


def test_liveness_returns_ok_and_request_id() -> None:
    response = TestClient(app).get("/api/v1/health/live", headers={"X-Request-ID": "smoke-test-id"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "smoke-test-id"


def test_openapi_is_available() -> None:
    response = TestClient(app).get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health/live" in response.json()["paths"]
