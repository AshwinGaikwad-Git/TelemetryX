from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "TelemetryX API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://telemetryx:telemetryx_local_only@db:5432/telemetryx"
    redis_url: str = "redis://redis:6379/0"
    api_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
