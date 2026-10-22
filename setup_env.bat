@echo off
setlocal enabledelayedexpansion
title Setup Face Detection Environment

echo =====================================================================
echo  Setting up Python Virtual Environment (.venv)
echo =====================================================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and make sure 'Add to PATH' is checked.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/2] Creating virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [1/2] Existing .venv detected.
)

echo [2/2] Installing required dependencies...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo =====================================================================
echo  Setup Completed Successfully!
echo =====================================================================
echo You can now run:
echo   - run_service.bat        (to run manually in a console)
echo   - install_service.bat    (as Administrator to run in background)
echo.
pause
