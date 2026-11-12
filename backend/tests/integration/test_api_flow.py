"""Integration test for the full end-to-end TelemetryX workflow via REST API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_full_telemetryx_api_workflow(client: TestClient) -> None:
    # 1. Health check
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    # 2. Load committed synthetic C-MAPSS sample fixtures
    res = client.post("/api/v1/datasets/sample")
    assert res.status_code == 200
    data_sample = res.json()
    assert "dataset_id" in data_sample
    dataset_id = data_sample["dataset_id"]

    # 3. Inspect dataset details
    res = client.get(f"/api/v1/datasets/{dataset_id}")
    assert res.status_code == 200
    ds_detail = res.json()
    assert ds_detail["dataset_code"] == "FD001"
    assert ds_detail["status"] == "prepared"
    assert ds_detail["train_count"] > 0
    assert ds_detail["test_count"] > 0

    # 4. List engines
    res = client.get(f"/api/v1/datasets/{dataset_id}/engines?role=test")
    assert res.status_code == 200
    engines = res.json()
    assert len(engines) > 0
    first_engine_id = engines[0]["id"]

    # 5. Inspect engine cycles telemetry
    res = client.get(f"/api/v1/engines/{first_engine_id}/cycles?start_cycle=1&end_cycle=10")
    assert res.status_code == 200
    cycles = res.json()
    assert len(cycles) > 0
    assert "sensor_values" in cycles[0]
    assert "operational_settings" in cycles[0]

    # 6. Train Gradient Boosting Model
    exp_payload = {
        "name": "test-gbr-baseline",
        "dataset_version_id": dataset_id,
        "algorithm": "gradient_boosting",
        "hyperparameters": {"learning_rate": 0.1, "max_iter": 30, "max_depth": 5},
        "rul_cap": 125,
        "validation_fraction": 0.2,
        "random_seed": 42,
    }
    res = client.post("/api/v1/experiments", json=exp_payload)
    assert res.status_code == 200
    exp_data = res.json()
    assert "model_version_id" in exp_data
    model_id = exp_data["model_version_id"]

    # 7. Verify model registered
    res = client.get("/api/v1/models")
    assert res.status_code == 200
    models = res.json()
    assert any(m["id"] == model_id for m in models)

    # 8. Run batch predictions on test engines
    res = client.post(f"/api/v1/models/{model_id}/predictions?dataset_id={dataset_id}&role=test")
    assert res.status_code == 200
    preds = res.json()
    assert len(preds) > 0
    assert "predicted_rul" in preds[0]
    assert "lower_bound" in preds[0]
    assert "upper_bound" in preds[0]
    assert "risk_level" in preds[0]

    # 9. List predictions & inspect details with SHAP and recommendations
    res = client.get("/api/v1/predictions")
    assert res.status_code == 200
    all_preds = res.json()
    assert len(all_preds) > 0
    first_pred_id = all_preds[0]["id"]

    res = client.get(f"/api/v1/predictions/{first_pred_id}")
    assert res.status_code == 200
    p_detail = res.json()
    assert p_detail["explanation"] is not None
    assert "top_contributors" in p_detail["explanation"]
    assert p_detail["recommendation"] is not None
    assert "Simulated C-MAPSS benchmark" in p_detail["recommendation"]["rationale"]

    # 10. Check Evaluation runs
    res = client.get("/api/v1/evaluations")
    assert res.status_code == 200
    evals = res.json()
    assert len(evals) >= 1
    # Check that NASA score and RMSE are computed
    metrics = evals[0]["metrics"]
    assert "nasa_score" in metrics
    assert "rmse" in metrics
    assert "mae" in metrics

    # 11. Fleet Dashboard Summary
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["fleet_size"] > 0
    assert "healthy" in summary["risk_distribution"]
    assert summary["active_model"] is not None
