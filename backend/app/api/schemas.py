"""Pydantic schemas and request/response models for TelemetryX REST API."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# Datasets
class DatasetVersionOut(BaseModel):
    id: uuid.UUID
    dataset_code: str
    source_name: str
    source_uri: str | None = None
    checksum_sha256: str | None = None
    parser_version: str
    preprocessing_version: str
    status: str
    engine_count: int = 0
    train_count: int = 0
    test_count: int = 0
    has_test_rul: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetDetailOut(DatasetVersionOut):
    files: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] | None = None


# Engine Runs and Telemetry
class EngineRunSummary(BaseModel):
    id: uuid.UUID
    dataset_version_id: uuid.UUID
    file_role: str
    unit_number: int
    max_cycle: int
    ground_truth_rul: float | None = None
    predicted_rul: float | None = None
    risk_level: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineRunDetail(EngineRunSummary):
    prediction: dict[str, Any] | None = None
    explanation: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None


class EngineCycleTelemetry(BaseModel):
    cycle: int
    operational_settings: list[float]
    sensor_values: dict[str, float]
    features: dict[str, float] | None = None


# Experiments and Models
class ExperimentCreate(BaseModel):
    name: str = "fd001-gradient-boosting-v1"
    dataset_version_id: uuid.UUID
    algorithm: Literal["gradient_boosting", "naive"] = "gradient_boosting"
    hyperparameters: dict[str, Any] = Field(
        default_factory=lambda: {"learning_rate": 0.08, "max_iter": 120, "max_depth": 6}
    )
    rul_cap: int = Field(default=125, ge=1, le=10000)
    validation_fraction: float = Field(default=0.2, gt=0, lt=1)
    random_seed: int = 42


class ExperimentOut(BaseModel):
    id: uuid.UUID
    name: str
    dataset_version_id: uuid.UUID
    algorithm: str
    status: str
    random_seed: int
    created_at: datetime
    model_version_id: uuid.UUID | None = None
    metrics: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class ModelVersionOut(BaseModel):
    dataset_version_id: uuid.UUID
    id: uuid.UUID
    experiment_id: uuid.UUID
    version: str
    artifact_uri: str
    metrics: dict[str, Any]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Predictions & Explanations
class PredictionOut(BaseModel):
    id: uuid.UUID
    model_version_id: uuid.UUID
    engine_run_id: uuid.UUID
    unit_number: int
    file_role: str
    cycle: int
    predicted_rul: float
    lower_bound: float
    upper_bound: float
    risk_level: str
    ground_truth_rul: float | None = None
    created_at: datetime
    explanation: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


# Evaluation
class EvaluationOut(BaseModel):
    dataset_version_id: uuid.UUID
    id: uuid.UUID
    model_version_id: uuid.UUID
    model_version: str
    evaluation_role: str
    metrics: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Dashboard Summary
class FleetSummaryOut(BaseModel):
    fleet_size: int
    mean_predicted_rul: float
    risk_distribution: dict[str, int]
    attention_required_count: int
    active_model: dict[str, Any] | None = None
    critical_engines: list[dict[str, Any]]
    latest_recommendations: list[dict[str, Any]]
