from db.database import SessionLocal
from db import models

session = SessionLocal()
try:
    print('=== Upstox Connections ===')
    upstox = session.query(models.BrokerConnection).filter(
        models.BrokerConnection.broker_name == 'upstox'
    ).all()
    for c in upstox:
        tokens = 'YES' if c.encrypted_tokens else 'NO'
        print(f'  id={c.id}, user_id={c.user_id}, broker_user_id={c.broker_user_id}, tokens={tokens}')
    
    print()
    print('=== Zerodha Connections ===')
    zerodha = session.query(models.BrokerConnection).filter(
        models.BrokerConnection.broker_name == 'zerodha'
    ).all()
    for c in zerodha:
        tokens = 'YES' if c.encrypted_tokens else 'NO'
        print(f'  id={c.id}, user_id={c.user_id}, broker_user_id={c.broker_user_id}, tokens={tokens}')
finally:
    session.close()
