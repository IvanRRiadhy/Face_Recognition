# =====================================================================
#  Face Detection AI Engine - 1-Click Auto Installer
# =====================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " Face Detection AI Engine - 1-Click Auto Installer" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Administrator privileges required." -ForegroundColor Red
    Write-Host "Please right-click 'install.bat' and select 'Run as administrator'." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$zipFile = Join-Path $scriptDir "package.zip"
$targetDir = "C:\Face_Detection"

if (-not (Test-Path $zipFile)) {
    Write-Host "[ERROR] 'package.zip' was not found in: $scriptDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 2. Extract Package
Write-Host "[1/5] Extracting package to $targetDir..." -ForegroundColor Green
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}
Expand-Archive -Path $zipFile -DestinationPath $targetDir -Force
Write-Host "      Files extracted successfully." -ForegroundColor Gray

# 3. Detect Python
Write-Host "[2/5] Detecting Python installation..." -ForegroundColor Green
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
$pythonExe = $null

if ($pyCmd) {
    $pythonExe = $pyCmd.Source
} else {
    $candidates = Get-ChildItem -Path "C:\Users" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidates) {
        $pythonExe = $candidates.FullName
    }
}

if (-not $pythonExe) {
    Write-Host "[ERROR] Python 3.10+ was not found on this computer!" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/ (make sure 'Add to PATH' is checked)." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "      Found Python at: $pythonExe" -ForegroundColor Gray

# 4. Setup .venv and Dependencies
Write-Host "[3/5] Setting up virtual environment and AI dependencies..." -ForegroundColor Green
Set-Location $targetDir
$venvPython = Join-Path $targetDir ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "      Creating Python virtual environment (.venv)..." -ForegroundColor Gray
    & $pythonExe -m venv (Join-Path $targetDir ".venv")
}

Write-Host "      Installing/updating required packages (FastAPI, OpenCV, YuNet)..." -ForegroundColor Gray
& $venvPython -m pip install -r (Join-Path $targetDir "requirements.txt") | Out-Null

$modelFile = Join-Path $targetDir "assets\models\face_detection_yunet_2023mar.onnx"
if (-not (Test-Path $modelFile)) {
    Write-Host "      Downloading YuNet AI model..." -ForegroundColor Gray
    New-Item -ItemType Directory -Path (Split-Path -Parent $modelFile) -Force | Out-Null
    Invoke-WebRequest -Uri "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" -OutFile $modelFile
}

# 5. Register Task Scheduler
Write-Host "[4/5] Registering Background Auto-Start Task..." -ForegroundColor Green
$serverScript = Join-Path $targetDir "run_server.py"
$action = New-ScheduledTaskAction -Execute $venvPython -Argument $serverScript -WorkingDirectory $targetDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

Register-ScheduledTask -TaskName "FaceDetectionEngine" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "      Task registered successfully." -ForegroundColor Gray

# 6. Configure Firewall
Write-Host "[5/5] Configuring Firewall for Port 9001 (LAN / Wi-Fi Access)..." -ForegroundColor Green
netsh advfirewall firewall delete rule name="Face Detection Engine (Port 9001)" >$null 2>&1
netsh advfirewall firewall add rule name="Face Detection Engine (Port 9001)" dir=in action=allow protocol=TCP localport=9001 profile=private,public >$null
Write-Host "      Firewall rule configured for Port 9001." -ForegroundColor Gray

# 7. Start the Service
Write-Host ""
Write-Host "Starting Face Detection Engine service in the background..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName "FaceDetectionEngine"
Start-Sleep -Seconds 3

# 8. Summary Display
Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " INSTALLATION COMPLETED & SERVICE IS RUNNING!" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installed Location: $targetDir"
Write-Host ""
Write-Host "Access URLs:"
Write-Host "  - Local Swagger Docs: http://localhost:9001/docs" -ForegroundColor Yellow
Write-Host "  - Local Health Check: http://localhost:9001/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "LAN / Wi-Fi Access for other devices:" -ForegroundColor White
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.254*' }
foreach ($ip in $ips) {
    Write-Host "  - $($ip.InterfaceAlias): http://$($ip.IPAddress):9001/docs" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Controls (inside $targetDir):" -ForegroundColor White
Write-Host "  - Stop:      stop_service.bat"
Write-Host "  - Uninstall: uninstall_service.bat"
Write-Host ""

Read-Host "Press Enter to exit installer"
