@echo off
echo Starting WorkFlow AI...
echo.

REM Check if PowerContext is running
echo Checking PowerContext service...
curl -s http://localhost:18080/health/ready >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: PowerContext service is not running at http://localhost:18080
    echo Please start PowerContext first:
    echo   powercontext server run --env-file .env
    echo.
    echo The app will still work but semantic search will use local fallback.
    echo.
)

REM Start the backend
echo Starting backend server...
cd /d "%~dp0"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
