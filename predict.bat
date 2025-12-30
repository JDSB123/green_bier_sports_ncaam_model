@echo off
REM NCAA Basketball Prediction System v33.6.5
REM
REM SINGLE ENTRY POINT: This is the ONLY way to run predictions
REM Everything runs inside the container via run_today.py
REM
REM USAGE:
REM   predict.bat                    - Full slate today
REM   predict.bat --no-sync          - Skip data sync
REM   predict.bat --game "Duke" "UNC"  - Specific game
REM   predict.bat --date 2025-12-20     - Specific date

REM Ensure containers are running
docker compose up -d postgres
if errorlevel 1 (
    echo.
    echo ❌ Failed to start postgres container
    exit /b 1
)

REM Wait for postgres to be healthy
powershell -NoProfile -Command "Start-Sleep -Seconds 5" >nul

REM Start prediction service if not running (force recreate to pick up secrets)
docker compose up -d --force-recreate prediction-service
if errorlevel 1 (
    echo.
    echo ❌ Failed to start prediction-service container
    exit /b 1
)

REM Wait for service to be ready
powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul

REM Execute inside container - ONE source of truth
docker compose exec -T prediction-service python /app/run_today.py %*
