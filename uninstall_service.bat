@echo off
setlocal enabledelayedexpansion
title Uninstall Face Detection Engine

echo Cleaning up Face Detection Engine...
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName 'FaceDetectionEngine' -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName 'FaceDetectionEngine' -Confirm:$false -ErrorAction SilentlyContinue"

powershell -NoProfile -Command ^
    "$conns = Get-NetTCPConnection -LocalPort 9001 -ErrorAction SilentlyContinue;" ^
    "if ($conns) { foreach ($c in $conns) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } }"

netsh advfirewall firewall delete rule name="Face Detection Engine (Port 9001)" >nul 2>&1

echo Service and firewall rule uninstalled successfully.
pause
