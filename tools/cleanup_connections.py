"""
Cleanup script to remove duplicate broker connections.
Keeps only the most recent connection for each user+broker combination.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def cleanup_connections():
    from db.database import SessionLocal
    from db import models

    session = SessionLocal()
    try:
        print("Finding duplicate connections...")

        # Get all connections grouped by user_id and broker_name
        from sqlalchemy import func

        # Find max id per user+broker
        subq = session.query(
            models.BrokerConnection.user_id,
            models.BrokerConnection.broker_name,
            func.max(models.BrokerConnection.id).label("max_id"),
        ).group_by(
            models.BrokerConnection.user_id,
            models.BrokerConnection.broker_name,
        ).subquery()

        # Get connections to keep (one per user+broker with highest id)
        keep_ids = session.query(
            func.max(models.BrokerConnection.id),
        ).join(
            subq,
            (models.BrokerConnection.user_id == subq.c.user_id)
            & (models.BrokerConnection.broker_name == subq.c.broker_name),
        ).group_by(
            models.BrokerConnection.user_id,
            models.BrokerConnection.broker_name,
        ).all()

        keep_ids = [row[0] for row in keep_ids]

        # Find duplicates to delete
        duplicates = session.query(models.BrokerConnection).filter(
            ~models.BrokerConnection.id.in_(keep_ids)
        ).all()

        print(f"Found {len(duplicates)} duplicate connections to remove")

        for conn in duplicates:
            print(
                f"  Deleting: id={conn.id}, broker={conn.broker_name}, user_id={conn.user_id}, broker_user_id={conn.broker_user_id}"
            )
            session.delete(conn)

        session.commit()
        print("Cleanup complete!")

        # Print remaining connections
        print("\nRemaining connections:")
        remaining = session.query(models.BrokerConnection).all()
        for conn in remaining:
            tokens = "YES" if conn.encrypted_tokens else "NO"
            print(
                f"  id={conn.id}, broker={conn.broker_name}, user_id={conn.user_id}, broker_user_id={conn.broker_user_id}, tokens={tokens}"
            )

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    cleanup_connections()
