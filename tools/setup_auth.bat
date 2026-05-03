@echo off
echo Fixing auth setup...

cd /D "%~dp0\.."

echo 1. Removing existing database...
if exist data\tradecraftx.db del /F data\tradecraftx.db
if exist data\tradecraftx.db-shm del /F data\tradecraftx.db-shm
if exist data\tradecraftx.db-wal del /F data\tradecraftx.db-wal

echo 2. Running migrations...
python -m alembic upgrade head

echo.
echo Setup complete! Now restart the backend server.
echo Run: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
