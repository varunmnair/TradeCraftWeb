@echo off
setlocal enabledelayedexpansion

title TradeCraftX - Starting Application

echo ========================================
echo   TradeCraftX - Starting Application
echo ========================================
echo.

:: Step 0: Check .env exists
if not exist ".env" (
    echo [ERROR] .env file not found. Copy .env.example to .env and fill in required values.
    echo.
    echo   Required: UPSTOX_API_KEY, UPSTOX_API_SECRET
    echo   Optional but recommended: UPSTOX_ANALYTICS_TOKEN ^(for CMP/OHLCV^)
    echo.
    pause
    exit /b 1
)

:: Check critical env vars are set (not default placeholder)
for /f "tokens=1,* delims==" %%A in ('findstr /b "UPSTOX_ANALYTICS_TOKEN=" .env ^| findstr /v "your_analytics_long_lived_token"') do set "HAS_TOKEN=1"
if not defined HAS_TOKEN (
    echo [WARNING] UPSTOX_ANALYTICS_TOKEN is not set or still has placeholder value.
    echo   CMP and OHLCV features will fail.
    echo   Create an Analytics app in Upstox developer portal and add the token to .env
    echo.
    choice /c CN /n /m "[C]ontinue anyway or [N]o to abort? "
    if errorlevel 2 exit /b 1
)

:: Step 1: Check Docker
echo [1/4] Checking Docker...
docker info 1>nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop first.
    echo.
    pause
    exit /b 1
)
echo   Docker is running.
echo.

:: Step 2: Build and start
echo [2/4] Building and starting containers...
docker compose up --build -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start containers.
    echo.
    pause
    exit /b 1
)
echo   Containers started.
echo.

:: Step 3: Wait for health
echo [3/4] Waiting for application to be ready...
set RETRIES=0
:health_check
ping -n 3 127.0.0.1 1>nul 2>nul
C:\Windows\System32\curl.exe -s -o nul -f http://localhost:8000/health
if !errorlevel! neq 0 (
    set /a RETRIES+=1
    if !RETRIES! lss 30 (
        goto health_check
    )
    echo [ERROR] Application failed to start within 60 seconds.
    echo.
    echo Recent logs:
    docker compose logs --tail=20
    echo.
    pause
    exit /b 1
)
echo   Application is ready.
echo.

:: Step 4: Open browser
echo [4/4] Opening application in browser...
start http://localhost:8000
echo   Browser opened to http://localhost:8000
echo.

echo ========================================
echo   Application is running at:
echo   http://localhost:8000
echo.
echo   To stop:  docker compose down
echo   To view logs:  docker compose logs -f
echo ========================================
echo.
ping -n 3 127.0.0.1 1>nul 2>nul
