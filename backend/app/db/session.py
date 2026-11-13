import logging
import sqlite3
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection: Any, connection_record: Any) -> None:
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


db_url = get_settings().database_url
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
# Schema changes are applied with Alembic, including on SQLite. Never silently switch stores.

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
