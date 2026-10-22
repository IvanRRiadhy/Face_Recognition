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

:: Get directory where this batch script is located (no trailing backslash)
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"

set "SERVICE_NAME=FaceDetectionService"
set "DISPLAY_NAME=Face Detection Engine Service"
set "DESCRIPTION=Face Detection Engine background service powered by NSSM"
set "EXE_PATH=%BASE_DIR%\FaceDetectionEngine.exe"
set "NSSM_PATH=%BASE_DIR%\nssm.exe"
set "LOG_OUT=%BASE_DIR%\service_output.log"
set "LOG_ERR=%BASE_DIR%\service_error.log"

echo =======================================================
echo     Installing %SERVICE_NAME%
echo =======================================================
echo Directory: %BASE_DIR%
echo Executable: %EXE_PATH%
echo NSSM Path : %NSSM_PATH%
echo.

if not exist "%NSSM_PATH%" (
    echo [ERROR] nssm.exe not found in %BASE_DIR%!
    pause
    exit /b 1
)

if not exist "%EXE_PATH%" (
    echo [ERROR] FaceDetectionEngine.exe not found in %BASE_DIR%!
    pause
    exit /b 1
)

:: Check if service already exists; stop it if running
"%NSSM_PATH%" status "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo Service %SERVICE_NAME% already exists. Stopping and reinstalling...
    "%NSSM_PATH%" stop "%SERVICE_NAME%" >nul 2>&1
    "%NSSM_PATH%" remove "%SERVICE_NAME%" confirm >nul 2>&1
)

echo Registering service with NSSM...
"%NSSM_PATH%" install "%SERVICE_NAME%" "%EXE_PATH%"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install service.
    pause
    exit /b 1
)

echo Configuring service parameters...
"%NSSM_PATH%" set "%SERVICE_NAME%" AppDirectory "%BASE_DIR%"
"%NSSM_PATH%" set "%SERVICE_NAME%" DisplayName "%DISPLAY_NAME%"
"%NSSM_PATH%" set "%SERVICE_NAME%" Description "%DESCRIPTION%"
"%NSSM_PATH%" set "%SERVICE_NAME%" Start SERVICE_AUTO_START

:: Configure log files and rotation
"%NSSM_PATH%" set "%SERVICE_NAME%" AppStdout "%LOG_OUT%"
"%NSSM_PATH%" set "%SERVICE_NAME%" AppStderr "%LOG_ERR%"
"%NSSM_PATH%" set "%SERVICE_NAME%" AppRotateFiles 1
"%NSSM_PATH%" set "%SERVICE_NAME%" AppRotateOnline 1
"%NSSM_PATH%" set "%SERVICE_NAME%" AppRotateSeconds 86400
"%NSSM_PATH%" set "%SERVICE_NAME%" AppRotateBytes 10485760

echo Starting service...
"%NSSM_PATH%" start "%SERVICE_NAME%"

echo.
echo =======================================================
echo Service installation complete!
echo Status:
"%NSSM_PATH%" status "%SERVICE_NAME%"
echo.
echo Log files:
echo   - Standard Output: %LOG_OUT%
echo   - Standard Error : %LOG_ERR%
echo =======================================================
echo.
pause
