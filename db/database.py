"""
SQLAlchemy database utilities.

Database Configuration:
-----------------------
The database URL is determined in the following order:
1. DATABASE_URL environment variable (for production deployments)
2. Default: sqlite:///./data/tradecraftx.db (for development)

Production Usage:
-----------------
Set the DATABASE_URL environment variable to override the default:
- PostgreSQL: postgresql://user:pass@host:5432/tradecraftx
- MySQL: mysql://user:pass@host:3306/tradecraftx
- SQLite (different path): sqlite:///var/data/tradecraftx.db

Development Notes:
-----------------
- The ./data/ directory is gitignored to prevent accidental commits of database files
- SQLite uses WAL mode for better concurrency
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


# Default database path - ./data/tradecraftx.db
DATA_DIR = Path("data")
DEFAULT_SQLITE_PATH = DATA_DIR / "tradecraftx.db"


def _build_database_url() -> str:
    """Build database URL from environment or default."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use relative path with ./: sqlite:///./data/tradecraftx.db
    return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


# Determine database URL
# Priority: 1. Environment variable, 2. Default (./data/tradecraftx.db)
DATABASE_URL = _build_database_url()

# Connection args for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Create engine with appropriate settings
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configure SQLite pragmas for better behavior."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
