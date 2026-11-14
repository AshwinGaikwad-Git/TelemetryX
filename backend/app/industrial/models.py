import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def identity() -> Any:
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)


def created() -> Any:
    return mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())


class User(Base):
    __tablename__ = "industrial_users"
    id: Mapped[uuid.UUID] = identity()
    email: Mapped[str] = mapped_column(sa.String(254), unique=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    password_hash: Mapped[str] = mapped_column(sa.String(300))
    created_at: Mapped[datetime] = created()


class Company(Base):
    __tablename__ = "industrial_companies"
    id: Mapped[uuid.UUID] = identity()
    name: Mapped[str] = mapped_column(sa.String(120))
    created_at: Mapped[datetime] = created()


class Membership(Base):
    __tablename__ = "industrial_memberships"
    __table_args__ = (sa.UniqueConstraint("company_id", "user_id"),)
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(User.id), index=True)
    role: Mapped[str] = mapped_column(sa.String(20))


class LoginSession(Base):
    __tablename__ = "industrial_sessions"
    token_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(User.id), index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))


class Invitation(Base):
    __tablename__ = "industrial_invitations"
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    email: Mapped[str] = mapped_column(sa.String(254))
    role: Mapped[str] = mapped_column(sa.String(20))
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(sa.Boolean, default=False)


class Site(Base):
    __tablename__ = "industrial_sites"
    __table_args__ = (sa.UniqueConstraint("id", "company_id"),)
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    name: Mapped[str] = mapped_column(sa.String(120))
    timezone: Mapped[str] = mapped_column(sa.String(80), default="UTC")
    location: Mapped[str] = mapped_column(sa.String(200), default="")


class Machine(Base):
    __tablename__ = "industrial_machines"
    __table_args__ = (
        sa.UniqueConstraint("id", "company_id"),
        sa.UniqueConstraint("company_id", "asset_tag"),
        sa.ForeignKeyConstraint(["site_id", "company_id"], [Site.id, Site.company_id]),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    site_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, index=True)
    asset_tag: Mapped[str] = mapped_column(sa.String(60))
    name: Mapped[str] = mapped_column(sa.String(120))
    equipment_type: Mapped[str] = mapped_column(sa.String(80))
    manufacturer: Mapped[str] = mapped_column(sa.String(100), default="")
    model: Mapped[str] = mapped_column(sa.String(100), default="")
    area: Mapped[str] = mapped_column(sa.String(100), default="")
    criticality: Mapped[str] = mapped_column(sa.String(20), default="medium")
    operating_state: Mapped[str] = mapped_column(sa.String(20), default="stopped")
    notes: Mapped[str] = mapped_column(sa.Text, default="")
    created_at: Mapped[datetime] = created()


class Sensor(Base):
    __tablename__ = "industrial_sensors"
    __table_args__ = (
        sa.UniqueConstraint("id", "company_id"),
        sa.UniqueConstraint("machine_id", "key"),
        sa.ForeignKeyConstraint(["machine_id", "company_id"], [Machine.id, Machine.company_id]),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, index=True)
    key: Mapped[str] = mapped_column(sa.String(60))
    name: Mapped[str] = mapped_column(sa.String(100))
    unit: Mapped[str] = mapped_column(sa.String(30))
    expected_interval_seconds: Mapped[int] = mapped_column(sa.Integer, default=60)
    valid_min: Mapped[float | None] = mapped_column(sa.Float)
    valid_max: Mapped[float | None] = mapped_column(sa.Float)
    warning_low: Mapped[float | None] = mapped_column(sa.Float)
    warning_high: Mapped[float | None] = mapped_column(sa.Float)
    persistence_samples: Mapped[int] = mapped_column(sa.Integer, default=3)


class Reading(Base):
    __tablename__ = "industrial_readings"
    __table_args__ = (
        sa.UniqueConstraint("sensor_id", "timestamp"),
        sa.ForeignKeyConstraint(["sensor_id", "company_id"], [Sensor.id, Sensor.company_id]),
        sa.Index("ix_industrial_reading_time", "company_id", "sensor_id", "timestamp"),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    sensor_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    value: Mapped[float] = mapped_column(sa.Float)
    source: Mapped[str] = mapped_column(sa.String(30), default="api")


class Alert(Base):
    __tablename__ = "industrial_alerts"
    __table_args__ = (
        sa.ForeignKeyConstraint(["machine_id", "company_id"], [Machine.id, Machine.company_id]),
        sa.ForeignKeyConstraint(["sensor_id", "company_id"], [Sensor.id, Sensor.company_id]),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)
    sensor_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)
    title: Mapped[str] = mapped_column(sa.String(250))
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    severity: Mapped[str] = mapped_column(sa.String(20), default="attention")
    evidence: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey(User.id))
    created_at: Mapped[datetime] = created()
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class WorkOrder(Base):
    __tablename__ = "industrial_work_orders"
    __table_args__ = (
        sa.ForeignKeyConstraint(["machine_id", "company_id"], [Machine.id, Machine.company_id]),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)
    alert_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey(Alert.id))
    title: Mapped[str] = mapped_column(sa.String(180))
    description: Mapped[str] = mapped_column(sa.Text, default="")
    priority: Mapped[str] = mapped_column(sa.String(20), default="medium")
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey(User.id))
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    findings: Mapped[str] = mapped_column(sa.Text, default="")
    component: Mapped[str] = mapped_column(sa.String(120), default="")
    downtime_minutes: Mapped[int] = mapped_column(sa.Integer, default=0)
    created_at: Mapped[datetime] = created()
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class IngestionKey(Base):
    __tablename__ = "industrial_ingestion_keys"
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[datetime] = created()


class AuditEvent(Base):
    __tablename__ = "industrial_audit_events"
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    actor: Mapped[str] = mapped_column(sa.String(100))
    action: Mapped[str] = mapped_column(sa.String(100))
    entity_id: Mapped[str] = mapped_column(sa.String(100))
    details: Mapped[dict[str, Any]] = mapped_column(sa.JSON, default=dict)
    created_at: Mapped[datetime] = created()


class EquipmentModel(Base):
    __tablename__ = "industrial_equipment_models"
    __table_args__ = (
        sa.UniqueConstraint("id", "company_id", "machine_id"),
        sa.ForeignKeyConstraint(["machine_id", "company_id"], [Machine.id, Machine.company_id]),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, index=True)
    artifact_uri: Mapped[str] = mapped_column(sa.Text)
    checksum: Mapped[str] = mapped_column(sa.String(64))
    feature_schema: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = created()


class EquipmentPrediction(Base):
    __tablename__ = "industrial_equipment_predictions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["model_id", "company_id", "machine_id"],
            [EquipmentModel.id, EquipmentModel.company_id, EquipmentModel.machine_id],
        ),
    )
    id: Mapped[uuid.UUID] = identity()
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey(Company.id), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)
    remaining_hours: Mapped[float] = mapped_column(sa.Float)
    lower_hours: Mapped[float] = mapped_column(sa.Float)
    upper_hours: Mapped[float] = mapped_column(sa.Float)
    evidence: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    observed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = created()
