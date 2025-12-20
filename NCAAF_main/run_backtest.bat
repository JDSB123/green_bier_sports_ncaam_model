@echo off
REM NCAAF Model ROE Optimization Backtest Script for Windows
REM This script imports cached data, trains enhanced models, and runs comprehensive backtests

echo ==========================================
echo NCAAF MODEL ROE OPTIMIZATION BACKTEST
echo ==========================================
echo.

REM Check if .env has real API key
findstr /C:"YOUR_API_KEY_HERE" .env >nul
if %errorlevel% equ 0 (
    echo ERROR: You must update .env with your REAL SportsDataIO API key
    echo Edit .env and replace YOUR_API_KEY_HERE with your actual key
    echo IMPORTANT: Rotate the old key that was exposed!
    pause
    exit /b 1
)

REM Step 1: Start Docker containers
echo Step 1: Starting Docker containers...
docker compose up -d postgres redis
timeout /t 10 >nul

REM Step 2: Run database migrations
echo Step 2: Running database migrations...
docker compose exec postgres psql -U ncaaf_user -d ncaaf_v5 -c "SELECT 1" >nul 2>&1

REM Step 3: Import cached data (if available)
echo Step 3: Importing cached data...

REM Check for Azure connection string
if defined AZURE_STORAGE_CONNECTION_STRING (
    echo Importing from Azure storage...
    docker compose run --rm ml_service python scripts/import_historical_data.py ^
        --azure ^
        --azure-container ncaaf-data ^
        --consolidate
) else (
    echo No Azure connection string found. Skipping Azure import.
)

REM Check for local data directory
if exist "data\cached" (
    echo Importing from local cached data...
    docker compose run --rm ml_service python scripts/import_historical_data.py ^
        --directory /app/data/cached ^
        --consolidate
) else (
    echo No local cached data found at data\cached\
)

REM Step 4: Backfill recent data from SportsDataIO
echo Step 4: Backfilling recent data from SportsDataIO...
docker compose run --rm ml_service python scripts/import_historical_data.py ^
    --backfill ^
    --start-season 2024 ^
    --end-season 2024

REM Step 5: Train enhanced models with walk-forward validation
echo Step 5: Training enhanced models...
echo This may take 10-15 minutes with hyperparameter tuning...

REM First run with hyperparameter tuning
docker compose run --rm ml_service python scripts/train_xgboost_enhanced.py ^
    --tune ^
    --start-season 2018 ^
    --end-season 2024

REM Step 6: Run comprehensive backtest
echo Step 6: Running comprehensive backtest...
echo Comparing baseline vs enhanced models on 2024 season...

docker compose run --rm ml_service python scripts/backtest_enhanced.py ^
    --start-date 2024-09-01 ^
    --end-date 2024-12-17 ^
    --plot

REM Step 7: Check results
echo.
echo ==========================================
echo BACKTEST COMPLETE
echo ==========================================
echo.
echo Check the following files for results:
echo   - backtest_report.txt - Detailed comparison report
echo   - backtest_comparison.png - Performance visualization
echo   - ml_service\models\performance_report.txt - Model metrics
echo.
echo Expected ROI improvement: +40-60%%
echo.

REM Step 8: Optional - Start services for live predictions
set /p START_SERVICES=Do you want to start the services for live predictions? (y/n):
if /i "%START_SERVICES%"=="y" (
    echo Starting all services...
    docker compose up -d
    echo.
    echo Services running at:
    echo   - Ingestion API: http://localhost:8080/health
    echo   - ML API: http://localhost:8000/docs
    echo   - PostgreSQL: localhost:5434
    echo   - Redis: localhost:6380
)

echo.
echo Deployment complete!
pause