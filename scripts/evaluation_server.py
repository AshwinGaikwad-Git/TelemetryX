"""Start a disposable migrated API for browser tests; never uses the development DB."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="telemetryx-browser-") as directory:
    storage = Path(directory)
    os.environ.update(
        DATABASE_URL=f"sqlite:///{(storage / 'evaluation.db').as_posix()}",
        RAW_STORAGE_PATH=str(storage / "raw"),
        PROCESSED_STORAGE_PATH=str(storage / "processed"),
        MODEL_STORAGE_PATH=str(storage / "models"),
        JOB_BACKEND="local",
        API_CORS_ORIGINS="http://127.0.0.1:3001,http://localhost:3001",
        OMP_NUM_THREADS="1",
    )
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", check=True)
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"], cwd=ROOT / "backend", check=True)
