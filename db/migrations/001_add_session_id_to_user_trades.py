"""Add session_id to user_trades table if not exists."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal, engine
from sqlalchemy import text


def upgrade():
    """Add session_id column to user_trades table."""
    db = SessionLocal()
    try:
        # Check if table exists
        result = db.execute(text("SHOW TABLES LIKE 'user_trades'"))
        if not result.fetchone():
            print("user_trades table does not exist yet - will be created automatically")
            return
        
        # Check if column exists
        result = db.execute(text("SHOW COLUMNS FROM user_trades LIKE 'session_id'"))
        if result.fetchone():
            print("session_id column already exists in user_trades")
            return
        
        # Add session_id column
        db.execute(text("ALTER TABLE user_trades ADD COLUMN session_id VARCHAR(36) NULL, ADD INDEX ix_trades_session_symbol (session_id, symbol)"))
        db.commit()
        print("Successfully added session_id column to user_trades")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


def downgrade():
    """Remove session_id column from user_trades table."""
    db = SessionLocal()
    try:
        # Check if column exists
        result = db.execute(text("SHOW COLUMNS FROM user_trades LIKE 'session_id'"))
        if not result.fetchone():
            print("session_id column does not exist in user_trades")
            return
        
        # Remove column
        db.execute(text("ALTER TABLE user_trades DROP COLUMN session_id"))
        db.commit()
        print("Successfully removed session_id column from user_trades")
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
