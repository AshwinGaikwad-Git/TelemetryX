from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "TelemetryX API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///telemetryx_dev.db"
    redis_url: str = "redis://redis:6379/0"
    api_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    raw_storage_path: Path = Path(__file__).resolve().parents[3] / "data/raw"
    processed_storage_path: Path = Path(__file__).resolve().parents[3] / "data/processed"
    model_storage_path: Path = Path(__file__).resolve().parents[3] / "models"
    max_upload_size_mb: int = Field(default=100, ge=1)
    job_backend: Literal["local", "redis"] = "local"
    job_max_attempts: int = Field(default=3, ge=1, le=10)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
