from pathlib import Path

from app.core.config import Settings


def test_default_storage_paths_stay_inside_repository(monkeypatch) -> None:
    for name in ("RAW_STORAGE_PATH", "PROCESSED_STORAGE_PATH", "MODEL_STORAGE_PATH"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    root = Path(__file__).resolve().parents[3]
    assert settings.raw_storage_path == root / "data/raw"
    assert settings.processed_storage_path == root / "data/processed"
    assert settings.model_storage_path == root / "models"
