import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

db_url = get_settings().database_url
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

try:
    engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    # Test connection if not sqlite
    if not db_url.startswith("sqlite"):
        with engine.connect():
            pass
except Exception as ex:
    logger.warning("Configured database unavailable (%s). Falling back to local SQLite.", ex)
    db_url = "sqlite:///telemetryx_dev.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    from app.db.base import Base

    Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
