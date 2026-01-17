@echo off
REM NCAAM Model - Environment Checker
REM Run this anytime things feel "off" to diagnose issues

echo ========================================
echo NCAAM Model - Environment Check
echo ========================================
echo.

echo [1/7] Checking Current Directory...
cd
if exist predict.bat (
    echo   ✓ In correct directory
) else (
    echo   ✗ WRONG DIRECTORY! Need to be in green_bier_sports_ncaam_model/
    echo   Run: cd green_bier_sports_ncaam_model
    goto :end
)
echo.

echo [2/7] Checking Python...
python --version 2>nul
if errorlevel 1 (
    echo   ✗ Python not found!
) else (
    echo   ✓ Python found
    for /f "tokens=*" %%i in ('where python') do echo   Location: %%i
)
echo.

echo [3/7] Checking Virtual Environment...
if exist .venv\Scripts\python.exe (
    echo   ✓ Virtual environment exists
    .venv\Scripts\python.exe --version
    if defined VIRTUAL_ENV (
        echo   ✓ Virtual environment is ACTIVE
    ) else (
        echo   ⚠ Virtual environment exists but NOT activated
        echo   Run: .\.venv\Scripts\Activate.ps1
    )
) else (
    echo   ✗ Virtual environment NOT found!
    echo   Create it: python -m venv .venv
)
echo.

echo [4/7] Checking Docker...
docker --version 2>nul
if errorlevel 1 (
    echo   ✗ Docker not found!
) else (
    echo   ✓ Docker found
)
docker compose version 2>nul
if errorlevel 1 (
    echo   ✗ Docker Compose not found!
) else (
    echo   ✓ Docker Compose found
)
echo.

echo [5/7] Checking Running Containers...
docker ps --format "table {{.Names}}\t{{.Status}}" 2>nul
if errorlevel 1 (
    echo   ⚠ Could not check containers (Docker not running?)
) else (
    echo   ✓ Listed above
)
echo.

echo [6/7] Checking Secrets...
if exist secrets\db_password.txt (
    echo   ✓ db_password.txt exists
) else (
    echo   ✗ db_password.txt missing
)
if exist secrets\redis_password.txt (
    echo   ✓ redis_password.txt exists
) else (
    echo   ✗ redis_password.txt missing
)
if exist secrets\odds_api_key.txt (
    echo   ✓ odds_api_key.txt exists
) else (
    echo   ✗ odds_api_key.txt missing
)
if exist secrets\teams_webhook_secret.txt (
    echo   ✓ teams_webhook_secret.txt exists
) else (
    echo   ⚠ teams_webhook_secret.txt missing (optional)
)
echo.

echo [7/7] Checking Docker Compose File...
if exist docker-compose.yml (
    echo   ✓ docker-compose.yml found
) else (
    echo   ✗ docker-compose.yml NOT found!
)
echo.

echo ========================================
echo Summary
echo ========================================
if exist predict.bat (
    if exist .venv\Scripts\python.exe (
        if exist docker-compose.yml (
            if exist secrets\odds_api_key.txt (
                echo ✓ Environment looks GOOD!
                echo.
                echo Ready to run: .\predict.bat
            ) else (
                echo ⚠ Secrets need setup
                echo Run: python ensure_secrets.py
            )
        ) else (
            echo ✗ Missing core files
        )
    ) else (
        echo ⚠ Virtual environment needs setup
        echo Run: python -m venv .venv
    )
) else (
    echo ✗ You are in the WRONG directory!
    echo Navigate to: green_bier_sports_ncaam_model
)
echo ========================================

:end
pause
