"""SQLAlchemy database utilities."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DEFAULT_SQLITE_PATH = Path("storage/dev.db")


def _build_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


DATABASE_URL = _build_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
