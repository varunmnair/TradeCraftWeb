"""Add OHLCV config and metadata tables."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal, engine
from sqlalchemy import text


def upgrade():
    """Create ohlcv_config and ohlcv_metadata tables."""
    db = SessionLocal()
    try:
        dialect = engine.dialect.name

        if dialect == 'sqlite':
            # SQLite: Check if tables exist
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv_config'"))
            if result.fetchone():
                print("ohlcv_config table already exists")
            else:
                db.execute(text("""
                    CREATE TABLE ohlcv_config (
                        id INTEGER PRIMARY KEY,
                        days INTEGER NOT NULL DEFAULT 200,
                        updated_at TIMESTAMP NOT NULL
                    )
                """))
                db.execute(text("INSERT INTO ohlcv_config (id, days, updated_at) VALUES (1, 200, datetime('now'))"))
                print("Created ohlcv_config table")

            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv_metadata'"))
            if result.fetchone():
                print("ohlcv_metadata table already exists")
            else:
                db.execute(text("""
                    CREATE TABLE ohlcv_metadata (
                        symbol VARCHAR(50) PRIMARY KEY,
                        last_fetched_at TIMESTAMP NOT NULL,
                        days_stored INTEGER NOT NULL
                    )
                """))
                print("Created ohlcv_metadata table")

        elif dialect == 'mysql':
            # MySQL: Check if tables exist
            result = db.execute(text("SHOW TABLES LIKE 'ohlcv_config'"))
            if not result.fetchone():
                db.execute(text("""
                    CREATE TABLE ohlcv_config (
                        id INT PRIMARY KEY,
                        days INT NOT NULL DEFAULT 200,
                        updated_at DATETIME(6) NOT NULL
                    )
                """))
                db.execute(text("INSERT INTO ohlcv_config (id, days, updated_at) VALUES (1, 200, NOW(6))"))
                print("Created ohlcv_config table")
            else:
                print("ohlcv_config table already exists")

            result = db.execute(text("SHOW TABLES LIKE 'ohlcv_metadata'"))
            if not result.fetchone():
                db.execute(text("""
                    CREATE TABLE ohlcv_metadata (
                        symbol VARCHAR(50) PRIMARY KEY,
                        last_fetched_at DATETIME(6) NOT NULL,
                        days_stored INT NOT NULL
                    )
                """))
                print("Created ohlcv_metadata table")
            else:
                print("ohlcv_metadata table already exists")

        db.commit()
        print("Migration completed successfully")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


def downgrade():
    """Drop ohlcv_config and ohlcv_metadata tables."""
    db = SessionLocal()
    try:
        dialect = engine.dialect.name

        if dialect == 'sqlite':
            db.execute(text("DROP TABLE IF EXISTS ohlcv_metadata"))
            db.execute(text("DROP TABLE IF EXISTS ohlcv_config"))
        elif dialect == 'mysql':
            db.execute(text("DROP TABLE IF EXISTS ohlcv_metadata"))
            db.execute(text("DROP TABLE IF EXISTS ohlcv_config"))

        db.commit()
        print("Successfully dropped ohlcv_config and ohlcv_metadata tables")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
