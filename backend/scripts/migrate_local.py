"""Back up and upgrade the verified legacy local SQLite database.

Run from backend: .venv/Scripts/python.exe -m scripts.migrate_local
"""

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.db.base import Base


def migrate() -> Path:
    database = Path("telemetryx_dev.db").resolve()
    if not database.is_file():
        raise RuntimeError(
            "No backend/telemetryx_dev.db found. Use alembic upgrade head for a new DB."
        )
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "alembic_version" not in tables:
        expected = {
            table.name: {c.name for c in table.columns} for table in Base.metadata.sorted_tables
        }
        expected["job_runs"] -= {"payload", "result"}
        actual = {name: {c["name"] for c in inspector.get_columns(name)} for name in tables}
        if actual != expected:
            raise RuntimeError("Schema does not match legacy revision 0002. Refusing to stamp it.")
    engine.dispose()
    directory = database.parent.parent / "data" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / f"telemetryx-before-0003-{datetime.now(UTC):%Y%m%dT%H%M%S%f}.db"
    with sqlite3.connect(database) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
        counts = {
            name: source.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            for name in tables
            if name != "alembic_version"
        }
    config = Config("alembic.ini")
    if "alembic_version" not in tables:
        command.stamp(config, "20260902_0002")
    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        for name, count in counts.items():
            if connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] != count:
                raise RuntimeError(f"Row count changed for {name}. Original backup is at {backup}")
    return backup


if __name__ == "__main__":
    print(f"Migration complete; existing row counts preserved. Backup: {migrate()}")
