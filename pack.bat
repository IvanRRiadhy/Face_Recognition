@echo off
setlocal enabledelayedexpansion
title Face Detection Engine - Packaging Standalone Server

echo =====================================================================
echo  Face Detection Engine - Standalone Package Builder
echo =====================================================================
echo.

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"

set "ZIP_NAME=FaceDetectionEngine_Server_Standalone.zip"
set "ZIP_PATH=%ROOT_DIR%\%ZIP_NAME%"
set "DIST_DIR=%ROOT_DIR%\dist\FaceDetectionEngine"
set "SPEC_FILE=%ROOT_DIR%\FaceDetectionEngine.spec"

:: ---------------------------------------------------------------------
:: 1. Check whether to run PyInstaller build
:: ---------------------------------------------------------------------
if /i "%~1"=="--build" goto do_build
if /i "%~1"=="--rebuild" goto do_build
if /i "%~1"=="-b" goto do_build
if /i "%~1"=="--no-build" goto skip_build

if not exist "%DIST_DIR%\FaceDetectionEngine.exe" (
    echo [INFO] Executable not found in dist. PyInstaller build required.
    goto do_build
)

if not exist "%DIST_DIR%\_internal" (
    echo [INFO] _internal directory not found in dist. PyInstaller build required.
    goto do_build
)

echo Existing build found at: %DIST_DIR%
choice /C YN /N /T 5 /D N /M "Recompile executable with PyInstaller first? [Y/N, default in 5s: N]: "
if errorlevel 2 goto skip_build

:do_build
echo.
echo [1/4] Compiling project with PyInstaller...
python -m PyInstaller "%SPEC_FILE%" --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)
echo       PyInstaller build finished successfully.
goto check_build

:skip_build
echo [1/4] Using existing PyInstaller build.

:check_build
:: ---------------------------------------------------------------------
:: 2. Verify build output exists
:: ---------------------------------------------------------------------
if not exist "%DIST_DIR%\FaceDetectionEngine.exe" (
    echo [ERROR] %DIST_DIR%\FaceDetectionEngine.exe does not exist!
    pause
    exit /b 1
)

if not exist "%DIST_DIR%\_internal" (
    echo [ERROR] %DIST_DIR%\_internal directory does not exist!
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------
:: 3. Copy companion files into dist folder
:: ---------------------------------------------------------------------
echo.
echo [2/4] Copying required companion and instruction files to dist...

if not exist "%ROOT_DIR%\InstallAsService.bat" (
    echo [ERROR] Missing InstallAsService.bat in %ROOT_DIR%!
    pause
    exit /b 1
)
copy /y "%ROOT_DIR%\InstallAsService.bat" "%DIST_DIR%\" >nul
echo       Copied InstallAsService.bat

if not exist "%ROOT_DIR%\UninstallService.bat" (
    echo [ERROR] Missing UninstallService.bat in %ROOT_DIR%!
    pause
    exit /b 1
)
copy /y "%ROOT_DIR%\UninstallService.bat" "%DIST_DIR%\" >nul
echo       Copied UninstallService.bat

if not exist "%ROOT_DIR%\nssm.exe" (
    echo [ERROR] Missing nssm.exe in %ROOT_DIR%!
    pause
    exit /b 1
)
copy /y "%ROOT_DIR%\nssm.exe" "%DIST_DIR%\" >nul
echo       Copied nssm.exe

if not exist "%ROOT_DIR%\config.json" (
    echo [ERROR] Missing config.json in %ROOT_DIR%!
    pause
    exit /b 1
)
copy /y "%ROOT_DIR%\config.json" "%DIST_DIR%\" >nul
echo       Copied config.json

if exist "%ROOT_DIR%\HOW_TO_INSTALL_AND_USE.md" (
    copy /y "%ROOT_DIR%\HOW_TO_INSTALL_AND_USE.md" "%DIST_DIR%\" >nul
    echo       Copied HOW_TO_INSTALL_AND_USE.md
)

if exist "%ROOT_DIR%\README.md" (
    copy /y "%ROOT_DIR%\README.md" "%DIST_DIR%\" >nul
    echo       Copied README.md
)

:: ---------------------------------------------------------------------
:: 4. Create the standalone ZIP archive
:: ---------------------------------------------------------------------
echo.
echo [3/4] Creating %ZIP_NAME%...

if exist "%ZIP_PATH%" (
    echo       Removing existing archive...
    del /f /q "%ZIP_PATH%"
)

cd /d "%DIST_DIR%"

where tar.exe >nul 2>&1
if %errorlevel% equ 0 (
    tar.exe -a -c -f "%ZIP_PATH%" *
) else (
    powershell -NoProfile -Command "Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"
)

if %errorlevel% neq 0 (
    echo [ERROR] Failed to create ZIP archive!
    cd /d "%ROOT_DIR%"
    pause
    exit /b 1
)

cd /d "%ROOT_DIR%"

:: ---------------------------------------------------------------------
:: 5. Validate archive and display details
:: ---------------------------------------------------------------------
echo.
echo [4/4] Verifying archive contents...

if not exist "%ZIP_PATH%" (
    echo [ERROR] ZIP archive was not found at %ZIP_PATH%!
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
    "$item = Get-Item '%ZIP_PATH%';" ^
    "$mb = [math]::Round($item.Length / 1MB, 2);" ^
    "Write-Host ('      Archive Size: ' + $mb + ' MB') -ForegroundColor Green;" ^
    "Write-Host '';" ^
    "Write-Host '      Files in Archive Root:' -ForegroundColor Cyan;" ^
    "Add-Type -AssemblyName System.IO.Compression.FileSystem;" ^
    "$zip = [System.IO.Compression.ZipFile]::OpenRead($item.FullName);" ^
    "$rootEntries = $zip.Entries | Where-Object { $_.FullName -notmatch '/' -or $_.FullName -match '^[^/]+/$' };" ^
    "foreach ($e in $rootEntries) { Write-Host ('        [+] ' + $e.FullName) -ForegroundColor Gray };" ^
    "$zip.Dispose();"

echo.
echo =====================================================================
echo  STANDALONE ZIP PACKAGE CREATED SUCCESSFULLY!
echo =====================================================================
echo  Output Location: %ZIP_PATH%
echo =====================================================================
echo.
pause
