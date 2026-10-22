@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo Starting Face Detection AI Engine...
"%~dp0.venv\Scripts\python.exe" "%~dp0run_server.py"
