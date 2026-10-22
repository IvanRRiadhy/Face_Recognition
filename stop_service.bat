@echo off
setlocal enabledelayedexpansion
title Stop Face Detection Engine

echo Stopping Face Detection Engine on port 9001...
schtasks /End /TN "FaceDetectionEngine" >nul 2>&1

powershell -NoProfile -Command ^
    "$conns = Get-NetTCPConnection -LocalPort 9001 -ErrorAction SilentlyContinue;" ^
    "if ($conns) { foreach ($c in $conns) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped process ID ' + $c.OwningProcess) } } else { Write-Host 'Port 9001 is already free.' }"

echo Done.
pause
