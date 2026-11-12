import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.schemas import ExperimentCreate
from app.core.config import get_settings
from app.db.models import EngineRun, Experiment, FeatureSet, JobRun, ModelVersion
from app.main import app
from app.ml.models import load_rul_model
from app.pipelines.parser import calculate_sha256
from app.services import job_service
from app.services.dataset_service import DatasetService, training_dataframe
from app.services.experiment_service import ExperimentService
from app.services.prediction_service import PredictionService

_dispatch = job_service.dispatch


def test_dramatiq_transport_uses_the_shared_job_runner(monkeypatch) -> None:
    from dramatiq.brokers.stub import StubBroker

    from app.workers.tasks import execute_job

    broker = StubBroker()
    broker.declare_actor(execute_job)
    monkeypatch.setattr(execute_job, "broker", broker)
    monkeypatch.setattr(get_settings(), "job_backend", "redis")
    monkeypatch.setattr(job_service, "perform", lambda db, kind, payload: {"delivered": True})
    with job_service.SessionLocal() as db:
        job = job_service.enqueue(db, "sample", {})
        identity = job.id
    _dispatch(identity)
    consumer = broker.consume("telemetryx", timeout=1000)
    message = next(consumer)
    assert message is not None
    execute_job.fn(*message.args, **message.kwargs)
    consumer.ack(message)
    consumer.close()
    with job_service.SessionLocal() as db:
        completed = db.get(JobRun, identity)
        assert completed.status == "succeeded"
        assert completed.result == {"delivered": True}
    broker.close()


def test_interrupted_worker_recovery_is_explicit(monkeypatch) -> None:
    from app.workers import recover

    monkeypatch.setattr(recover, "SessionLocal", job_service.SessionLocal)
    with job_service.SessionLocal() as db:
        job = job_service.enqueue(db, "sample", {})
        job.status = "running"
        db.commit()
        identity = job.id
    assert recover.recover() == 1
    with job_service.SessionLocal() as db:
        recovered = db.get(JobRun, identity)
        assert recovered.status == "failed"
        assert "interrupted" in recovered.error


def complete(client: TestClient, response) -> dict:
    assert response.status_code == 202, response.text
    job_service.run_job(response.json()["id"])
    return client.get(f"/api/v1/jobs/{response.json()['id']}").json()


def telemetry(units: int = 5) -> bytes:
    rows = []
    for unit in range(1, units + 1):
        for cycle in range(1, 26):
            sensors = [500.0] * 21
            sensors[1] = 640 + cycle + unit
            # Seed 42 holds unit 5 out. A validation-only sensor must stay excluded.
            sensors[2] = 9000 + cycle if unit == 5 else 1585.0
            rows.append(" ".join(map(str, [unit, cycle, 0, 0, 100, *sensors])))
    return ("\r\n".join(rows) + "\r\n").encode()


def test_holdout_statistics_and_snapshot_are_train_only() -> None:
    with job_service.SessionLocal() as db:
        ds = DatasetService.get_or_create_dataset_version(db)
        DatasetService.ingest_file_content(db, ds.id, "train", "train.txt", telemetry())
        result = ExperimentService.run_training_experiment(
            db,
            ExperimentCreate(
                dataset_version_id=ds.id,
                algorithm="naive",
                random_seed=42,
                rul_cap=12,
            ),
        )
        model = db.get(ModelVersion, result["model_version_id"])
        assert model is not None
        exp = db.get(Experiment, result["experiment_id"])
        assert exp is not None
        assert exp.split_definition["val_units"] == [5]
        assert "sensor_3" not in model.feature_manifest["selected_sensors"]
        frame = training_dataframe(db, ds.id)
        training = frame[frame.unit_number != 5]
        index = model.feature_manifest["feature_names"].index("sensor_2")
        assert model.feature_manifest["scaler_mean"][index] == pytest.approx(
            training.sensor_2.mean()
        )
        assert model.feature_manifest["rul_cap"] == 12
        fs = db.get(FeatureSet, exp.feature_set_id)
        assert fs is not None
        manifest_path = Path(fs.feature_manifest_uri)
        snapshot = manifest_path.with_name("features.csv")
        assert calculate_sha256(snapshot.read_bytes()) == fs.parameters["snapshot_sha256"]
        assert json.loads(manifest_path.read_text())["extra"]["val_units"] == [5]
        loaded = load_rul_model(model.artifact_uri)
        assert loaded.manifest.to_dict() == model.feature_manifest
        assert model.metrics["interval_metrics"]["nominal_coverage"] == 0.9


def test_import_preserves_bytes_and_reimport_preserves_run_ids() -> None:
    raw = telemetry(2)
    with job_service.SessionLocal() as db:
        ds = DatasetService.get_or_create_dataset_version(db)
        DatasetService.ingest_file_content(db, ds.id, "train", "../../train.txt", raw)
        db.refresh(ds)
        original_ids = [r.id for r in ds.engine_runs]
        file = ds.files[0]
        assert Path(file.storage_uri).read_bytes() == raw
        assert file.checksum_sha256 == calculate_sha256(raw)
        assert file.original_filename == "train.txt"
        DatasetService.prepare_feature_set(db, ds.id)
        result = DatasetService.ingest_file_content(db, ds.id, "train", "train.txt", raw)
        assert result["reused"]
        assert [r.id for r in ds.engine_runs] == original_ids
        with pytest.raises(ValueError, match="immutable"):
            DatasetService.ingest_file_content(db, ds.id, "train", "changed.txt", telemetry(3))
        ds2 = DatasetService.get_or_create_dataset_version(db)
        assert ds2.id != ds.id


def test_jobs_failure_polling_idempotency_retry_and_cancel(monkeypatch) -> None:
    client = TestClient(app)
    dataset = client.post("/api/v1/datasets").json()["dataset_id"]
    response = client.post(
        "/api/v1/datasets/imports",
        data={
            "dataset_id": dataset,
            "file_role": "train",
        },
        files={"file": ("invalid.txt", b"1 2 3")},
        headers={"Idempotency-Key": "bad-import"},
    )
    failed = complete(client, response)
    assert failed["status"] == "failed"
    assert failed["result"]["report"]["errors"]
    retry = client.post(f"/api/v1/jobs/{failed['id']}/retry")
    assert complete(client, retry)["status"] == "failed"
    assert client.get("/api/v1/datasets").json()[0]["engine_count"] == 0
    # Validation failures are not automatically retried.
    assert failed["attempt_count"] == 1
    with job_service.SessionLocal() as db:
        first = job_service.enqueue(db, "sample", {}, "same-request")
        second = job_service.enqueue(db, "sample", {}, "same-request")
        assert first.id == second.id
        with pytest.raises(ValueError, match="different request"):
            job_service.enqueue(db, "train", {}, "same-request")
        cancelled = client.post(f"/api/v1/jobs/{first.id}/cancel").json()
        assert cancelled["status"] == "cancelled"
        job_service.run_job(str(first.id))
        assert client.get(f"/api/v1/jobs/{first.id}").json()["attempt_count"] == 0


def test_upload_limit_and_request_validation(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 1)
    client = TestClient(app)
    response = client.post(
        "/api/v1/datasets/imports",
        files={
            "file": ("large.txt", b"0" * (1024 * 1024 + 1)),
        },
    )
    assert response.status_code == 413
    assert (
        client.post(
            "/api/v1/experiments",
            json={
                "dataset_version_id": str(uuid.uuid4()),
                "validation_fraction": 1,
            },
        ).status_code
        == 422
    )


def test_transient_job_retries_and_real_local_executor(monkeypatch) -> None:
    calls = []

    def work(db, kind, payload):
        calls.append(kind)
        if len(calls) == 1:
            raise OSError("temporary storage failure")
        return {"ok": True}

    monkeypatch.setattr(job_service, "perform", work)
    monkeypatch.setattr(job_service.time, "sleep", lambda seconds: None)
    futures = []

    def submit(identity):
        futures.append(job_service.executor.submit(job_service.run_job, str(identity)))

    monkeypatch.setattr(job_service, "dispatch", submit)
    with job_service.SessionLocal() as db:
        job = job_service.enqueue(db, "sample", {})
        identity = job.id
    futures[0].result(timeout=10)
    with job_service.SessionLocal() as db:
        current = db.get(JobRun, identity)
        assert current.status == "succeeded", current.error
        assert current.attempt_count == 2


def test_fleet_uses_one_dataset_and_model_and_prediction_roles_do_not_erase() -> None:
    client = TestClient(app)
    sample = complete(client, client.post("/api/v1/datasets/sample"))["result"]
    dataset = sample["dataset_id"]
    trained = complete(
        client,
        client.post(
            "/api/v1/experiments",
            json={
                "dataset_version_id": dataset,
                "algorithm": "naive",
            },
        ),
    )["result"]
    model = trained["model_version_id"]
    with job_service.SessionLocal() as db:
        PredictionService.run_predictions_for_dataset(db, uuid.UUID(model), uuid.UUID(dataset))
        PredictionService.run_predictions_for_dataset(
            db, uuid.UUID(model), uuid.UUID(dataset), "train"
        )
        runs = db.scalars(
            select(EngineRun).where(
                EngineRun.dataset_version_id == uuid.UUID(dataset),
                EngineRun.file_role == "test",
            )
        ).all()
        assert all(run.predictions for run in runs)
        other = DatasetService.get_or_create_dataset_version(db)
        other_id = str(other.id)
        # Incompatible artifacts must be rejected rather than silently transformed.
        mv = db.get(ModelVersion, uuid.UUID(model))
        mv.feature_manifest = {**mv.feature_manifest, "rul_cap": 999}
        db.commit()
        with pytest.raises(ValueError, match="incompatible"):
            PredictionService.run_predictions_for_dataset(db, uuid.UUID(model), uuid.UUID(dataset))
    summary = client.get(f"/api/v1/dashboard/summary?dataset_id={dataset}").json()
    assert summary["fleet_size"] == len(runs)
    assert summary["active_model"]["id"] == model
    empty = client.get(f"/api/v1/dashboard/summary?dataset_id={other_id}").json()
    assert empty["fleet_size"] == 0
    assert empty["active_model"] is None
