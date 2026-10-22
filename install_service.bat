@echo off
setlocal enabledelayedexpansion
title Face Detection AI Engine - Auto-Start Setup

echo =====================================================================
echo  Face Detection Engine - Windows Auto-Start & Firewall Setup
echo =====================================================================
echo.

:: 1. Check for Administrator Privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This installer requires Administrator privileges.
    echo Please right-click 'install_service.bat' and select 'Run as administrator'.
    echo.
    pause
    exit /b 1
)

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

:: Check if .venv exists, if not create and install dependencies automatically
if not exist "%APP_DIR%\.venv\Scripts\python.exe" (
    echo [Setup] Virtual environment not found. Setting up .venv...
    python -m venv "%APP_DIR%\.venv"
    "%APP_DIR%\.venv\Scripts\python.exe" -m pip install -r "%APP_DIR%\requirements.txt"
)

:: 2. Clean up any previous broken NSSM service
echo [1/4] Cleaning up previous service state...
assets\tools\nssm.exe stop FaceDetectionEngine >nul 2>&1
assets\tools\nssm.exe remove FaceDetectionEngine confirm >nul 2>&1
sc stop FaceDetectionEngine >nul 2>&1
sc delete FaceDetectionEngine >nul 2>&1

:: 3. Clear old logs
if exist "%APP_DIR%\service_error.log" del /f /q "%APP_DIR%\service_error.log"
if exist "%APP_DIR%\service.log" del /f /q "%APP_DIR%\service.log"

:: 4. Register Task in Windows Task Scheduler via PowerShell cmdlet
echo [2/4] Registering Windows Auto-Start Task 'FaceDetectionEngine'...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$action = New-ScheduledTaskAction -Execute '%APP_DIR%\.venv\Scripts\python.exe' -Argument '%APP_DIR%\run_server.py' -WorkingDirectory '%APP_DIR%';" ^
    "$trigger = New-ScheduledTaskTrigger -AtLogOn;" ^
    "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest;" ^
    "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0;" ^
    "Register-ScheduledTask -TaskName 'FaceDetectionEngine' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null;"

if %errorLevel% equ 0 (
    echo       Auto-Start Task successfully registered in Task Scheduler!
) else (
    echo       [WARNING] Task Scheduler registration had an issue.
)

:: 5. Configure Firewall for LAN / WLAN access
echo [3/4] Configuring Windows Firewall rule for Port 9001...
netsh advfirewall firewall show rule name="Face Detection Engine (Port 9001)" >nul 2>&1
if %errorLevel% equ 0 (
    netsh advfirewall firewall delete rule name="Face Detection Engine (Port 9001)" >nul 2>&1
)

netsh advfirewall firewall add rule ^
    name="Face Detection Engine (Port 9001)" ^
    dir=in ^
    action=allow ^
    protocol=TCP ^
    localport=9001 ^
    profile=private,public >nul

echo       Firewall rule active (Port 9001 TCP Allowed)

:: 6. Start the background service right now
echo [4/4] Starting Face Detection Engine in the background...
powershell -NoProfile -Command "Start-ScheduledTask -TaskName 'FaceDetectionEngine'"
timeout /t 3 /nobreak >nul

:: 7. Display IP Address & Access URLs
echo.
echo =====================================================================
echo  AUTO-START SERVICE INSTALLED AND STARTED SUCCESSFULLY!
echo =====================================================================
echo.
echo Local machine access:
echo   - Swagger Docs: http://localhost:9001/docs
echo   - Health Check: http://localhost:9001/health
echo.
echo Other devices on your WLAN / Router can access:
powershell -NoProfile -Command ^
    "$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.254*' };" ^
    "foreach ($ip in $ips) { Write-Host ('  - ' + $ip.InterfaceAlias + ': http://' + $ip.IPAddress + ':9001/docs') }"

echo.
echo Control Commands:
echo   - Start:   powershell Start-ScheduledTask -TaskName FaceDetectionEngine
echo   - Stop:    stop_service.bat
echo   - Remove:  uninstall_service.bat
echo.
pause
