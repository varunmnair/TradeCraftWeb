from db.database import SessionLocal
from db import models

session = SessionLocal()
try:
    conns = session.query(models.BrokerConnection).filter(
        models.BrokerConnection.broker_name == 'zerodha'
    ).all()
    print(f'Zerodha connections: {len(conns)}')
    for c in conns:
        has_tokens = 'YES' if c.encrypted_tokens else 'NO'
        updated = c.token_updated_at.strftime('%Y-%m-%d %H:%M:%S') if c.token_updated_at else 'None'
        print(f'  id={c.id}, user_id={c.user_id}, broker_user_id={c.broker_user_id}, tokens={has_tokens}, updated={updated}')
finally:
    session.close()
