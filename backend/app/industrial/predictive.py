"""Machine-specific supervised RUL; research turbofan artifacts are never reused."""

import hashlib
import io
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from sklearn.model_selection import GroupShuffleSplit
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.industrial.auth import Database, Member, audit, require
from app.industrial.models import EquipmentModel, EquipmentPrediction, Machine, Sensor
from app.industrial.schemas import utc
from app.industrial.service import machine_for, machine_snapshot, record
from app.ml.models import GradientBoostingRULModel, load_rul_model

router = APIRouter(
    prefix="/industrial/companies/{company_id}/machines/{machine_id}",
    tags=["equipment predictions"],
)


def public_model(model: EquipmentModel) -> dict[str, Any]:
    return {key: value for key, value in record(model).items() if key != "artifact_uri"}


def train(db: Session, machine: Machine, content: bytes) -> EquipmentModel:
    try:
        frame = pd.read_csv(io.BytesIO(content), dtype={"run_id": str})
    except (ValueError, UnicodeError) as error:
        raise HTTPException(
            422, "Upload a UTF-8 CSV with run_id, remaining_hours and sensor columns"
        ) from error
    sensors = {
        s.key: s
        for s in db.scalars(
            select(Sensor).where(
                Sensor.company_id == machine.company_id,
                Sensor.machine_id == machine.id,
            )
        ).all()
    }
    keys = sorted(set(frame.columns) - {"run_id", "remaining_hours"})
    if not keys or len(keys) > 30 or not set(keys) <= set(sensors):
        raise HTTPException(
            422, "Include 1–30 registered sensor keys; no unknown columns are allowed"
        )
    if not {"run_id", "remaining_hours"} <= set(frame.columns):
        raise HTTPException(422, "CSV requires run_id and remaining_hours labels")
    if not 100 <= len(frame) <= 10000 or frame.run_id.nunique() < 5:
        raise HTTPException(
            422, "Provide 100–10,000 labeled snapshots from at least 5 independent failure runs"
        )
    if frame.isna().any().any() or frame.run_id.str.strip().eq("").any():
        raise HTTPException(422, "Missing values and empty run IDs are not allowed")
    try:
        numeric = frame[keys + ["remaining_hours"]].astype(float)
    except ValueError as error:
        raise HTTPException(422, "Sensor values and remaining_hours must be numeric") from error
    if not np.isfinite(numeric.to_numpy()).all() or (numeric.remaining_hours < 0).any():
        raise HTTPException(422, "Values must be finite and remaining_hours nonnegative")
    if numeric.remaining_hours.max() > 1e6 or numeric.remaining_hours.nunique() < 10:
        raise HTTPException(
            422, "Provide varied remaining-life labels in hours, no greater than 1,000,000"
        )
    for key in keys:
        sensor = sensors[key]
        if (sensor.valid_min is not None and (numeric[key] < sensor.valid_min).any()) or (
            sensor.valid_max is not None and (numeric[key] > sensor.valid_max).any()
        ):
            raise HTTPException(422, f"Training values for {key} exceed the sensor's valid range")
    # Entire runs stay together; no preprocessing or fitting sees held-out runs.
    train_idx, valid_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(
            numeric,
            groups=frame.run_id,
        )
    )
    x = numeric[keys].to_numpy()
    y = numeric.remaining_hours.to_numpy()
    model = GradientBoostingRULModel(max_iter=60, max_depth=4)
    model.fit(x[train_idx], y[train_idx])
    pred, low, high = model.predict(x[valid_idx])
    metrics = {
        "mae_hours": float(np.mean(np.abs(pred - y[valid_idx]))),
        "rmse_hours": float(np.sqrt(np.mean((pred - y[valid_idx]) ** 2))),
        "interval_coverage": float(np.mean((y[valid_idx] >= low) & (y[valid_idx] <= high))),
        "baseline_mae_hours": float(np.mean(np.abs(np.median(y[train_idx]) - y[valid_idx]))),
        "training_rows": len(train_idx),
        "validation_rows": len(valid_idx),
        "training_runs": int(frame.iloc[train_idx].run_id.nunique()),
        "validation_runs": int(frame.iloc[valid_idx].run_id.nunique()),
        "split": "held-out failure runs",
        "status": "experimental",
    }
    identity = uuid.uuid4()
    path = (
        get_settings().model_storage_path
        / "industrial"
        / str(machine.company_id)
        / f"{identity}.joblib"
    )
    schema = {
        key: {
            "unit": sensors[key].unit,
            "min": float(x[train_idx, i].min()),
            "max": float(x[train_idx, i].max()),
            "median": float(np.median(x[train_idx, i])),
        }
        for i, key in enumerate(keys)
    }
    model.save(path)
    result = EquipmentModel(
        id=identity,
        company_id=machine.company_id,
        machine_id=machine.id,
        artifact_uri=str(path),
        checksum=hashlib.sha256(content).hexdigest(),
        feature_schema=schema,
        metrics=metrics,
        created_at=datetime.now(UTC),
    )
    db.add(result)
    db.flush()
    return result


def latest_model(db: Session, machine: Machine) -> EquipmentModel | None:
    return db.scalar(
        select(EquipmentModel)
        .where(
            EquipmentModel.company_id == machine.company_id,
            EquipmentModel.machine_id == machine.id,
        )
        .order_by(EquipmentModel.created_at.desc(), EquipmentModel.id.desc())
        .limit(1)
    )


def readiness(
    db: Session, machine: Machine, model: EquipmentModel | None
) -> tuple[str | None, dict[str, Any]]:
    if not model:
        return "Train an equipment-specific model from labeled failure history first.", {}
    sensors = {s["key"]: s for s in machine_snapshot(db, machine)["sensors"]}
    values = {}
    for key, feature in model.feature_schema.items():
        sensor = sensors.get(key)
        if not sensor or sensor["unit"] != feature["unit"]:
            return f"Sensor {key} is missing or its unit differs from training.", {}
        if sensor["freshness"] != "fresh":
            return f"Fresh readings required for {key}.", {}
        point = sensor["latest"]
        if point["value"] < feature["min"] or point["value"] > feature["max"]:
            return f"{key} is outside the model's training range; review model applicability.", {}
        values[key] = {
            "value": point["value"],
            "timestamp": utc(point["timestamp"]).isoformat(),
            "unit": sensor["unit"],
        }
    times = [datetime.fromisoformat(v["timestamp"]) for v in values.values()]
    tolerance = min(sensors[key]["expected_interval_seconds"] for key in values)
    if (max(times) - min(times)).total_seconds() > tolerance:
        return "Sensor readings must be aligned within one sampling interval.", {}
    return None, values


@router.get("/predictive")
def status(
    company_id: uuid.UUID, machine_id: uuid.UUID, member: Member, db: Database
) -> dict[str, Any]:
    machine = machine_for(db, company_id, machine_id)
    model = latest_model(db, machine)
    reason, _ = readiness(db, machine, model)
    history = db.scalars(
        select(EquipmentPrediction)
        .where(
            EquipmentPrediction.company_id == company_id,
            EquipmentPrediction.machine_id == machine_id,
        )
        .order_by(EquipmentPrediction.created_at.desc(), EquipmentPrediction.id.desc())
        .limit(50)
    ).all()
    return {
        "model": public_model(model) if model else None,
        "ready": reason is None,
        "reason": reason,
        "history": [record(p) for p in history],
    }


@router.post("/predictive/train", status_code=201)
def train_model(
    company_id: uuid.UUID,
    machine_id: uuid.UUID,
    member: Member,
    db: Database,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    require(member, "admin", "engineer")
    machine = machine_for(db, company_id, machine_id)
    content = file.file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Training CSV must be at most 2 MB")
    model = train(db, machine, content)
    audit(
        db,
        company_id,
        str(member.user_id),
        "equipment_model.trained",
        model.id,
        {"machine_id": str(machine_id), "checksum": model.checksum, "metrics": model.metrics},
    )
    db.commit()
    return public_model(model)


@router.post("/predictive/predict", status_code=201)
def predict(
    company_id: uuid.UUID, machine_id: uuid.UUID, member: Member, db: Database
) -> dict[str, Any]:
    require(member, "admin", "manager", "engineer")
    machine = machine_for(db, company_id, machine_id)
    model = latest_model(db, machine)
    reason, values = readiness(db, machine, model)
    if reason or model is None:
        raise HTTPException(409, reason)
    keys = sorted(model.feature_schema)
    x = np.array([[values[key]["value"] for key in keys]])
    try:
        estimator = load_rul_model(model.artifact_uri)
    except (OSError, ValueError) as error:
        raise HTTPException(409, "Model artifact unavailable; train a new model") from error
    point, lower, upper = estimator.predict(x)
    # Replacing one feature at a time is sensitivity evidence, not causal attribution.
    evidence = []
    for i, key in enumerate(keys):
        altered = x.copy()
        altered[0, i] = model.feature_schema[key]["median"]
        substituted = estimator.predict(altered)[0][0]
        evidence.append({"sensor": key, "delta_hours": float(point[0] - substituted)})
    result = EquipmentPrediction(
        company_id=company_id,
        machine_id=machine_id,
        model_id=model.id,
        remaining_hours=float(point[0]),
        lower_hours=float(lower[0]),
        upper_hours=float(upper[0]),
        created_at=datetime.now(UTC),
        observed_at=max(datetime.fromisoformat(v["timestamp"]) for v in values.values()),
        evidence={
            "inputs": values,
            "method": "training-median substitution sensitivity",
            "contributors": sorted(evidence, key=lambda v: abs(v["delta_hours"]), reverse=True),
            "model_checksum": model.checksum,
            "validation": model.metrics,
        },
    )
    db.add(result)
    db.flush()
    audit(
        db,
        company_id,
        str(member.user_id),
        "equipment_prediction.created",
        result.id,
        {"machine_id": str(machine_id), "model_id": str(model.id)},
    )
    db.commit()
    return record(result)
