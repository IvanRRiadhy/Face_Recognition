@echo off
setlocal enabledelayedexpansion

:: Check for administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo =======================================================
    echo Administrator privileges required. Requesting elevation...
    echo =======================================================
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"

set "SERVICE_NAME=FaceDetectionService"
set "NSSM_PATH=%BASE_DIR%\nssm.exe"

echo =======================================================
echo     Uninstalling %SERVICE_NAME%
echo =======================================================

if not exist "%NSSM_PATH%" (
    echo [ERROR] nssm.exe not found in %BASE_DIR%!
    pause
    exit /b 1
)

echo Stopping service if running...
"%NSSM_PATH%" stop "%SERVICE_NAME%" >nul 2>&1

echo Removing service...
"%NSSM_PATH%" remove "%SERVICE_NAME%" confirm

echo.
echo =======================================================
echo Service uninstalled successfully!
echo =======================================================
echo.
pause
