import sys
sys.stdout.write('Checking tradecraftx.db...\n')
sys.stdout.flush()

from db.database import SessionLocal, DATABASE_URL
from db import models

sys.stdout.write(f'Database URL: {DATABASE_URL}\n')
sys.stdout.flush()

session = SessionLocal()
try:
    zerodha = session.query(models.BrokerConnection).filter(
        models.BrokerConnection.broker_name == 'zerodha'
    ).all()
    sys.stdout.write(f'Zerodha connections: {len(zerodha)}\n')
    sys.stdout.flush()
    for c in zerodha:
        tokens = 'YES' if c.encrypted_tokens else 'NO'
        sys.stdout.write(f'  id={c.id}, user_id={c.user_id}, broker_user_id={c.broker_user_id}, tokens={tokens}\n')
        sys.stdout.flush()
finally:
    session.close()
    sys.stdout.write('Done\n')
    sys.stdout.flush()
