@echo off
echo Fixing auth setup...

echo 1. Recreating database...
del /F storage\dev.db 2>nul

echo 2. Running migrations...
python -m alembic stamp base
python -m alembic upgrade head

echo 3. Creating DEFAULT tenant...
python -c "from db.database import SessionLocal; from db import models; s = SessionLocal(); s.add(models.Tenant(name='DEFAULT')); s.commit(); print('Done')"

echo.
echo Setup complete! Now restart the backend server.
echo Run: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
