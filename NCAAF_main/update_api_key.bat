@echo off
echo ==========================================
echo UPDATE YOUR SPORTSDATA API KEY
echo ==========================================
echo.
echo Your old API key was exposed and needs to be rotated!
echo.
echo Steps:
echo 1. Go to https://sportsdata.io/developers/
echo 2. Login to your account
echo 3. Rotate/regenerate your API key
echo 4. Copy the new key
echo.
set /p NEW_KEY=Paste your NEW API key here:

if "%NEW_KEY%"=="" (
    echo ERROR: No key provided!
    pause
    exit /b 1
)

echo.
echo Updating .env file with new key...

REM Create temporary file with updated key
powershell -Command "(Get-Content .env) -replace 'SPORTSDATA_API_KEY=.*', 'SPORTSDATA_API_KEY=%NEW_KEY%' | Set-Content .env"

echo.
echo API key updated successfully!
echo.
echo You can now run: run_backtest.bat
pause