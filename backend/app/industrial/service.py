import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.industrial.auth import audit
from app.industrial.models import Alert, Machine, Reading, Sensor
from app.industrial.schemas import TelemetryPoint, utc


def record(entity: Any) -> dict[str, Any]:
    return {
        column.key: (
            utc(getattr(entity, column.key))
            if isinstance(getattr(entity, column.key), datetime)
            else getattr(entity, column.key)
        )
        for column in inspect(entity).mapper.column_attrs
        if column.key not in {"password_hash", "token_hash"}
    }


def machine_for(db: Session, company_id: uuid.UUID, identity: uuid.UUID) -> Machine:
    machine = db.scalars(
        select(Machine).where(
            Machine.id == identity,
            Machine.company_id == company_id,
        )
    ).first()
    if not machine:
        raise HTTPException(404, "Machine not found")
    return machine


def direction(sensor: Sensor, value: float) -> str | None:
    if sensor.warning_high is not None and value > sensor.warning_high:
        return "high"
    if sensor.warning_low is not None and value < sensor.warning_low:
        return "low"
    return None


def sensor_snapshot(db: Session, sensor: Sensor, now: datetime) -> dict[str, Any]:
    rows = db.scalars(
        select(Reading)
        .where(
            Reading.company_id == sensor.company_id,
            Reading.sensor_id == sensor.id,
        )
        .order_by(Reading.timestamp.desc())
        .limit(sensor.persistence_samples)
    ).all()
    latest = rows[0] if rows else None
    freshness = (
        "missing"
        if not latest
        else (
            "stale"
            if now - utc(latest.timestamp) > timedelta(seconds=sensor.expected_interval_seconds * 3)
            else "fresh"
        )
    )
    current_direction = direction(sensor, latest.value) if latest else None
    consecutive = (
        len(rows) == sensor.persistence_samples
        and all(direction(sensor, row.value) == current_direction for row in rows)
        and all(
            (utc(rows[i].timestamp) - utc(rows[i + 1].timestamp)).total_seconds()
            <= sensor.expected_interval_seconds * 3
            for i in range(len(rows) - 1)
        )
    )
    return {
        **record(sensor),
        "latest": record(latest) if latest else None,
        "freshness": freshness,
        "breach": current_direction,
        "persistent": consecutive,
        "sample_count": len(rows),
    }


def machine_snapshot(db: Session, machine: Machine, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sensors = db.scalars(
        select(Sensor)
        .where(
            Sensor.company_id == machine.company_id,
            Sensor.machine_id == machine.id,
        )
        .order_by(Sensor.name)
    ).all()
    points = [sensor_snapshot(db, sensor, now) for sensor in sensors]
    fresh = [point for point in points if point["freshness"] == "fresh"]
    connectivity = (
        "not_connected"
        if not points or not any(p["latest"] for p in points)
        else ("offline" if not fresh else "partial" if len(fresh) < len(points) else "online")
    )
    configured = [
        p for p in points if p["warning_low"] is not None or p["warning_high"] is not None
    ]
    if any(p["breach"] for p in fresh):
        health = "attention"
    elif connectivity != "online" or not configured:
        health = "unknown"
    elif any(p["sample_count"] < p["persistence_samples"] for p in configured):
        health = "insufficient_data"
    else:
        health = "within_limits"
    last_seen = max((utc(p["latest"]["timestamp"]) for p in points if p["latest"]), default=None)
    return {
        **record(machine),
        "health": health,
        "connectivity": connectivity,
        "last_seen": last_seen,
        "sensors": points,
        "monitoring": "Threshold monitoring; equipment-specific predictive models not enabled",
    }


def evaluate_alert(db: Session, sensor: Sensor, actor: str) -> None:
    snapshot = sensor_snapshot(db, sensor, datetime.now(UTC))
    if snapshot["freshness"] != "fresh" or not snapshot["persistent"]:
        return
    active = db.scalars(
        select(Alert).where(
            Alert.company_id == sensor.company_id,
            Alert.sensor_id == sensor.id,
            Alert.status.in_(["open", "acknowledged"]),
        )
    ).first()
    if snapshot["breach"] and not active:
        alert = Alert(
            company_id=sensor.company_id,
            machine_id=sensor.machine_id,
            sensor_id=sensor.id,
            title=f"{sensor.name} sustained {snapshot['breach']} limit breach",
            evidence={
                "value": snapshot["latest"]["value"],
                "unit": sensor.unit,
                "warning_low": sensor.warning_low,
                "warning_high": sensor.warning_high,
                "consecutive_samples": sensor.persistence_samples,
                "timestamp": utc(snapshot["latest"]["timestamp"]).isoformat(),
            },
        )
        db.add(alert)
        db.flush()
        audit(db, sensor.company_id, actor, "alert.opened", alert.id, alert.evidence)
    elif not snapshot["breach"] and active:
        active.status = "resolved"
        active.resolved_at = datetime.now(UTC)
        audit(db, sensor.company_id, actor, "alert.recovered", active.id)


def ingest(
    db: Session,
    company_id: uuid.UUID,
    actor: str,
    points: list[TelemetryPoint],
    source: str,
    checksum: str,
) -> dict[str, Any]:
    accepted = 0
    duplicates = 0
    errors: list[dict[str, Any]] = []
    touched: dict[uuid.UUID, Sensor] = {}
    now = datetime.now(UTC)
    # Lock machines in deterministic order to serialize imports for a machine in PostgreSQL.
    ids = sorted({point.machine_id for point in points})
    machines = db.scalars(
        select(Machine)
        .where(
            Machine.company_id == company_id,
            Machine.id.in_(ids),
        )
        .order_by(Machine.id)
        .with_for_update()
    ).all()
    machine_ids = {machine.id for machine in machines}
    sensors = db.scalars(
        select(Sensor).where(
            Sensor.company_id == company_id,
            Sensor.machine_id.in_(ids),
        )
    ).all()
    mapping = {(sensor.machine_id, sensor.key): sensor for sensor in sensors}
    for index, point in enumerate(points, start=1):
        sensor = mapping.get((point.machine_id, point.sensor_key))
        error = None
        timestamp = utc(point.timestamp)
        if point.machine_id not in machine_ids or not sensor:
            error = "Machine or sensor is not registered in this workspace"
        elif point.unit != sensor.unit:
            error = f"Unit must match the registered unit: {sensor.unit}"
        elif timestamp > now + timedelta(minutes=5):
            error = "Timestamp is more than five minutes in the future"
        elif (sensor.valid_min is not None and point.value < sensor.valid_min) or (
            sensor.valid_max is not None and point.value > sensor.valid_max
        ):
            error = "Value falls outside the sensor's valid measurement range"
        if error:
            errors.append({"row": index, "error": error})
            continue
        assert sensor is not None
        existing = db.scalars(
            select(Reading).where(
                Reading.company_id == company_id,
                Reading.sensor_id == sensor.id,
                Reading.timestamp == timestamp,
            )
        ).first()
        if existing:
            if existing.value == point.value:
                duplicates += 1
            else:
                errors.append(
                    {"row": index, "error": "Conflicting value for an existing timestamp"}
                )
            continue
        db.add(
            Reading(
                company_id=company_id,
                sensor_id=sensor.id,
                timestamp=timestamp,
                value=point.value,
                source=source,
            )
        )
        db.flush()
        accepted += 1
        touched[sensor.id] = sensor
    for sensor in touched.values():
        evaluate_alert(db, sensor, actor)
    report = {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": len(errors),
        "errors": errors,
        "checksum_sha256": checksum,
        "source": source,
    }
    audit(db, company_id, actor, "telemetry.ingested", checksum, report)
    db.commit()
    return report


def source_checksum(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
