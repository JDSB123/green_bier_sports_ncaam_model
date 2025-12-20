@echo off
REM NCAAF Model v5.0 - Windows Runner
REM Single entry point for all operations

if "%1"=="" goto usage

echo ============================================================
echo NCAAF Model v5.0 - Enhanced with ROE Optimizations
echo ============================================================
echo.

if "%1"=="pipeline" (
    echo Running complete pipeline...
    echo Note: This may take 30-60 minutes. Progress will be shown...
    docker compose exec ncaaf_v5 python main.py pipeline %2 %3 %4
    goto end
)

if "%1"=="train" (
    echo Training enhanced model...
    echo Note: This may take 10-15 minutes. Progress will be shown...
    docker compose exec ncaaf_v5 python main.py train
    goto end
)

if "%1"=="predict" (
    echo Making predictions...
    docker compose exec ncaaf_v5 python main.py predict %2 %3 %4 %5 %6
    goto end
)

if "%1"=="backtest" (
    echo Running backtest...
    echo Note: This may take several minutes depending on data size. Progress will be shown...
    docker compose exec ncaaf_v5 python main.py backtest
    goto end
)

if "%1"=="compare" (
    echo Comparing models...
    docker compose exec ncaaf_v5 python main.py compare
    goto end
)

if "%1"=="import" (
    echo Importing data...
    docker compose exec ncaaf_v5 python main.py import-data
    goto end
)

if "%1"=="stats" (
    echo Populating statistics...
    docker compose exec ncaaf_v5 python main.py populate-stats
    goto end
)

if "%1"=="start" (
    echo Starting unified NCAAF v5.0 container...
    docker compose up -d
    echo Container started successfully!
    echo All services (PostgreSQL, Redis, Ingestion, ML Service) running in one container
    goto end
)

if "%1"=="stop" (
    echo Stopping unified container...
    docker compose down
    echo Container stopped successfully!
    goto end
)

if "%1"=="logs" (
    echo Showing unified container logs...
    docker compose logs -f --tail=100 ncaaf_v5
    goto end
)

if "%1"=="status" (
    echo Checking unified container status...
    docker compose ps
    echo.
    echo Database games count:
    docker compose exec -T ncaaf_v5 psql -h localhost -U ncaaf_user -d ncaaf_v5 -c "SELECT COUNT(*) as total_games, COUNT(CASE WHEN home_score IS NOT NULL THEN 1 END) as completed_games FROM games;"
    goto end
)

:usage
echo Usage: run.bat [command] [options]
echo.
echo Commands:
echo   pipeline         - Run complete pipeline (data, train, compare)
echo   train           - Train enhanced model
echo   predict         - Make predictions (add: --week 15 --season 2025)
echo   backtest        - Run comprehensive backtest
echo   compare         - Compare baseline vs enhanced models
echo   import          - Import historical data
echo   stats           - Populate team statistics
echo   start           - Start Docker services
echo   stop            - Stop Docker services
echo   logs            - View service logs
echo   status          - Check system status
echo.
echo Examples:
echo   run.bat pipeline                    - First time setup
echo   run.bat train                       - Retrain models
echo   run.bat predict --week 15           - Predict week 15
echo   run.bat status                      - Check database
echo.
echo Expected Performance (Enhanced Model):
echo   ROI: 8.5%%  ^|  ATS: 56.5%%  ^|  Sharpe: 0.85  ^|  Drawdown: 12%%
echo.

:end