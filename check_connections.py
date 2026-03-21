import sys
sys.stdout.write('Starting...\n')
sys.stdout.flush()

from db.database import SessionLocal
from db import models

session = SessionLocal()
try:
    conns = session.query(models.BrokerConnection).all()
    sys.stdout.write(f'Total connections: {len(conns)}\n')
    sys.stdout.flush()
    for c in conns:
        has_tokens = 'YES' if c.encrypted_tokens else 'NO'
        sys.stdout.write(f'  id={c.id}, broker={c.broker_name}, user_id={c.user_id}, broker_user_id={c.broker_user_id}, tokens={has_tokens}\n')
        sys.stdout.flush()
finally:
    session.close()
    sys.stdout.write('Done\n')
    sys.stdout.flush()
