from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "cymise.db"


def get_engine(db_path: Optional[Path | str] = None) -> Engine:
    """Create an engine for the given SQLite path (defaults to repo root)."""
    resolved = Path(db_path) if db_path else DEFAULT_DB_PATH
    return create_engine(f"sqlite+pysqlite:///{resolved}", future=True, echo=False)


def create_db(engine: Optional[Engine] = None) -> Engine:
    """Create tables if they do not exist and return the engine."""
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session(engine: Optional[Engine] = None) -> Session:
    """Return a new session bound to the given or default engine."""
    engine = engine or get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()
