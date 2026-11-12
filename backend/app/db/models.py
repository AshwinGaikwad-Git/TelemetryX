"""SQLAlchemy 2.0 ORM models for TelemetryX domain entities."""

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SystemMetadata(Base):
    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(sa.String(100), primary_key=True)
    value: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    dataset_code: Mapped[str] = mapped_column(sa.String(50), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    parser_version: Mapped[str] = mapped_column(sa.String(50), default="1.0.0", nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(
        sa.String(50), default="1.0.0", nullable=False
    )
    parameters: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(50), default="imported", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    files: Mapped[list["DatasetFile"]] = relationship(
        "DatasetFile", back_populates="dataset_version", cascade="all, delete-orphan"
    )
    engine_runs: Mapped[list["EngineRun"]] = relationship(
        "EngineRun", back_populates="dataset_version", cascade="all, delete-orphan"
    )
    feature_sets: Mapped[list["FeatureSet"]] = relationship(
        "FeatureSet", back_populates="dataset_version", cascade="all, delete-orphan"
    )


class DatasetFile(Base):
    __tablename__ = "dataset_files"
    __table_args__ = (
        sa.UniqueConstraint(
            "dataset_version_id", "file_role", "checksum_sha256", name="uq_dataset_file_checksum"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_role: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # train, test, test_rul
    original_filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    storage_uri: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    engine_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(50), default="validated", nullable=False)
    report: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    dataset_version: Mapped["DatasetVersion"] = relationship(
        "DatasetVersion", back_populates="files"
    )


class EngineRun(Base):
    __tablename__ = "engine_runs"
    __table_args__ = (
        sa.UniqueConstraint(
            "dataset_version_id", "file_role", "unit_number", name="uq_engine_run_unit"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_role: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # train, test
    unit_number: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    max_cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    ground_truth_rul: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    dataset_version: Mapped["DatasetVersion"] = relationship(
        "DatasetVersion", back_populates="engine_runs"
    )
    cycles: Mapped[list["EngineCycle"]] = relationship(
        "EngineCycle", back_populates="engine_run", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["RulPrediction"]] = relationship(
        "RulPrediction", back_populates="engine_run", cascade="all, delete-orphan"
    )


class EngineCycle(Base):
    __tablename__ = "engine_cycles"
    __table_args__ = (
        sa.UniqueConstraint("engine_run_id", "cycle", name="uq_engine_cycle"),
        sa.Index("idx_engine_cycle_run_cycle", "engine_run_id", "cycle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    engine_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("engine_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    operational_settings: Mapped[list[float]] = mapped_column(sa.JSON, nullable=False)
    sensor_values: Mapped[dict[str, float]] = mapped_column(sa.JSON, nullable=False)
    quality_flag: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    engine_run: Mapped["EngineRun"] = relationship("EngineRun", back_populates="cycles")


class FeatureSet(Base):
    __tablename__ = "feature_sets"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    feature_version: Mapped[str] = mapped_column(sa.String(50), default="1.0.0", nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    feature_manifest_uri: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    dataset_version: Mapped["DatasetVersion"] = relationship(
        "DatasetVersion", back_populates="feature_sets"
    )
    features: Mapped[list["CycleFeature"]] = relationship(
        "CycleFeature", back_populates="feature_set", cascade="all, delete-orphan"
    )


class CycleFeature(Base):
    __tablename__ = "cycle_features"
    __table_args__ = (
        sa.UniqueConstraint("feature_set_id", "engine_run_id", "cycle", name="uq_cycle_features"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    feature_set_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("feature_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engine_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("engine_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    features: Mapped[dict[str, float]] = mapped_column(sa.JSON, nullable=False)
    rul_target: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    sequence_eligible: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    feature_set: Mapped["FeatureSet"] = relationship("FeatureSet", back_populates="features")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_set_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("feature_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    algorithm: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    split_definition: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    random_seed: Mapped[int] = mapped_column(sa.Integer, default=42, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(50), default="queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    models: Mapped[list["ModelVersion"]] = relationship(
        "ModelVersion", back_populates="experiment", cascade="all, delete-orphan"
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    feature_manifest: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    training_data_range: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="models")
    predictions: Mapped[list["RulPrediction"]] = relationship(
        "RulPrediction", back_populates="model_version", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun", back_populates="model_version", cascade="all, delete-orphan"
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_role: Mapped[str] = mapped_column(sa.String(50), default="test", nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    per_unit_results_uri: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    model_version: Mapped["ModelVersion"] = relationship(
        "ModelVersion", back_populates="evaluations"
    )


class RulPrediction(Base):
    __tablename__ = "rul_predictions"
    __table_args__ = (
        sa.UniqueConstraint(
            "model_version_id", "engine_run_id", "cycle", name="uq_rul_prediction_cycle"
        ),
        sa.Index("idx_predictions_run_cycle", "engine_run_id", "cycle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engine_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("engine_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    predicted_rul: Mapped[float] = mapped_column(sa.Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(sa.Float, nullable=False)
    upper_bound: Mapped[float] = mapped_column(sa.Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        sa.String(50), nullable=False, index=True
    )  # healthy, planning, attention, urgent
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    model_version: Mapped["ModelVersion"] = relationship(
        "ModelVersion", back_populates="predictions"
    )
    engine_run: Mapped["EngineRun"] = relationship("EngineRun", back_populates="predictions")
    explanation: Mapped["PredictionExplanation | None"] = relationship(
        "PredictionExplanation",
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )
    recommendation: Mapped["MaintenanceRecommendation | None"] = relationship(
        "MaintenanceRecommendation",
        back_populates="prediction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PredictionExplanation(Base):
    __tablename__ = "prediction_explanations"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("rul_predictions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    method: Mapped[str] = mapped_column(sa.String(50), default="shap_tree", nullable=False)
    baseline: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON, nullable=True)
    top_contributors: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON, nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    prediction: Mapped["RulPrediction"] = relationship(
        "RulPrediction", back_populates="explanation"
    )


class MaintenanceRecommendation(Base):
    __tablename__ = "maintenance_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("rul_predictions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    recommendation_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    priority: Mapped[str] = mapped_column(
        sa.String(50), nullable=False
    )  # healthy, planning, attention, urgent
    rationale: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    prediction: Mapped["RulPrediction"] = relationship(
        "RulPrediction", back_populates="recommendation"
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(50), default="queued", nullable=False, index=True
    )  # queued, running, succeeded, failed, cancelled
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(sa.String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
