import re
import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

Role = Literal["admin", "manager", "engineer", "technician", "viewer"]
Priority = Literal["low", "medium", "high", "critical"]
State = Literal["running", "idle", "stopped", "maintenance"]


class InputModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def trim_text(cls, value: object, info: ValidationInfo) -> object:
        # Password whitespace is significant; descriptive input is normalized before length checks.
        return value.strip() if isinstance(value, str) and info.field_name != "password" else value


class Credentials(InputModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def email_format(cls, value: str) -> str:
        value = value.strip().lower()
        if (
            not re.fullmatch(
                r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}",
                value,
            )
            or value.split("@", 1)[0].startswith(".")
            or value.split("@", 1)[0].endswith(".")
            or ".." in value
        ):
            raise ValueError("Enter a valid email address")
        return value


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=100)
    company_name: str = Field(min_length=1, max_length=120)


class CompanyCreate(InputModel):
    name: str = Field(min_length=1, max_length=120)


class InvitationAccept(InputModel):
    token: str = Field(min_length=20, max_length=100)


class MemberCreate(InputModel):
    email: str = Field(min_length=3, max_length=254)
    role: Role

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return Credentials.email_format(value)


class RoleUpdate(InputModel):
    role: Role


class SiteCreate(InputModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=200)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Use an IANA timezone such as Asia/Kolkata") from error
        return value


class MachineCreate(InputModel):
    site_id: uuid.UUID
    asset_tag: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    equipment_type: str = Field(min_length=1, max_length=80)
    manufacturer: str = Field(default="", max_length=100)
    model: str = Field(default="", max_length=100)
    area: str = Field(default="", max_length=100)
    criticality: Priority = "medium"
    operating_state: State = "stopped"
    notes: str = Field(default="", max_length=5000)


class MachineUpdate(InputModel):
    operating_state: State


class SensorCreate(InputModel):
    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=30)
    expected_interval_seconds: int = Field(default=60, ge=1, le=86400)
    valid_min: float | None = Field(default=None, allow_inf_nan=False)
    valid_max: float | None = Field(default=None, allow_inf_nan=False)
    warning_low: float | None = Field(default=None, allow_inf_nan=False)
    warning_high: float | None = Field(default=None, allow_inf_nan=False)
    persistence_samples: int = Field(default=3, ge=1, le=100)

    @model_validator(mode="after")
    def ordered_limits(self) -> "SensorCreate":
        bounds = [
            v
            for v in (self.valid_min, self.warning_low, self.warning_high, self.valid_max)
            if v is not None
        ]
        if bounds != sorted(bounds) or (
            self.valid_min is not None and self.valid_min == self.valid_max
        ):
            raise ValueError("Limits must be ordered from valid_min through warnings to valid_max")
        return self


class TelemetryPoint(InputModel):
    machine_id: uuid.UUID
    sensor_key: str = Field(max_length=60)
    timestamp: AwareDatetime
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(max_length=30)


class TelemetryBatch(InputModel):
    readings: list[TelemetryPoint] = Field(min_length=1, max_length=10000)


class WorkCreate(InputModel):
    machine_id: uuid.UUID
    alert_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=5000)
    priority: Priority = "medium"
    assigned_to: uuid.UUID | None = None
    due_at: AwareDatetime | None = None


class WorkUpdate(InputModel):
    status: Literal["open", "assigned", "in_progress", "completed", "verified", "cancelled"]
    assigned_to: uuid.UUID | None = None
    findings: str | None = Field(default=None, max_length=5000)
    component: str | None = Field(default=None, max_length=120)
    downtime_minutes: int | None = Field(default=None, ge=0, le=10000000)


def utc(value: datetime) -> datetime:
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
