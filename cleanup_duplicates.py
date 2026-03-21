from db.database import SessionLocal
from db import models

session = SessionLocal()
try:
    conns = session.query(models.BrokerConnection).filter(
        models.BrokerConnection.broker_user_id.isnot(None)
    ).all()
    
    print(f'Total connections with broker_user_id: {len(conns)}')
    
    seen = {}
    to_delete = []
    for c in conns:
        key = (c.user_id, c.broker_name, c.broker_user_id)
        if key in seen:
            print(f'Duplicate: id={c.id}, user={c.user_id}, broker={c.broker_name}, buid={c.broker_user_id}')
            to_delete.append(c.id)
        else:
            seen[key] = c.id
    
    if to_delete:
        print(f'Deleting {len(to_delete)} duplicates...')
        session.query(models.BrokerConnection).filter(
            models.BrokerConnection.id.in_(to_delete)
        ).delete(synchronize_session=False)
        session.commit()
        print('Done!')
    else:
        print('No duplicates found.')
except Exception as e:
    session.rollback()
    print(f'Error: {e}')
finally:
    session.close()
