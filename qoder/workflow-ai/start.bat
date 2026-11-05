@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please run: python bootstrap.py
    exit /b 1
)
".venv\Scripts\python.exe" run.py
