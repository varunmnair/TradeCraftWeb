"""
Cleanup script to remove stale broker connections (connections with no tokens).
"""
import sys

def cleanup_stale_connections():
    from db.database import SessionLocal
    from db import models
    
    session = SessionLocal()
    try:
        print("Finding stale connections (no tokens)...")
        
        # Find connections with no tokens
        stale = session.query(models.BrokerConnection).filter(
            models.BrokerConnection.encrypted_tokens.is_(None)
        ).all()
        
        print(f"Found {len(stale)} stale connections to remove")
        
        for conn in stale:
            print(f"  Deleting: id={conn.id}, broker={conn.broker_name}, user_id={conn.user_id}")
            session.delete(conn)
        
        session.commit()
        print("Cleanup complete!")
        
        # Print remaining connections
        print("\nRemaining connections:")
        remaining = session.query(models.BrokerConnection).all()
        for conn in remaining:
            tokens = 'YES' if conn.encrypted_tokens else 'NO'
            print(f"  id={conn.id}, broker={conn.broker_name}, user_id={conn.user_id}, broker_user_id={conn.broker_user_id}, tokens={tokens}")
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    cleanup_stale_connections()
