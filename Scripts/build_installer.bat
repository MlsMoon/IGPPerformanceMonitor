@echo off
setlocal
echo ============================================
echo  IGP Performance Monitor - Installer
echo ============================================

cd /d "%~dp0\.."

set /p APP_VERSION=<VERSION
for /f "tokens=* delims= " %%I in ("%APP_VERSION%") do set "APP_VERSION=%%~I"
if not defined APP_VERSION (echo [installer] ERROR: VERSION file empty or missing & exit /b 1)

if not exist "dist\IGPPerformanceMonitor.exe" (
    echo [installer] ERROR: dist\IGPPerformanceMonitor.exe missing. Run Scripts\build.bat first.
    exit /b 1
)
if not exist "LICENSE" (
    echo [installer] ERROR: LICENSE missing.
    exit /b 1
)
if not exist "assets\icon.ico" (
    echo [installer] ERROR: assets\icon.ico missing.
    exit /b 1
)

set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
where iscc >nul 2>nul
if %ERRORLEVEL% EQU 0 if not defined ISCC for /f "delims=" %%I in ('where iscc') do set "ISCC=%%I"

if not defined ISCC (
    echo [installer] ERROR: Inno Setup 6 compiler ^(ISCC.exe^) not found.
    echo Install from https://jrsoftware.org/isinfo.php or: choco install innosetup
    exit /b 1
)

echo [installer] Version: %APP_VERSION%
echo [installer] Compiler: %ISCC%
"%ISCC%" /DMyAppVersion=%APP_VERSION% "Scripts\installer.iss"
if %ERRORLEVEL% NEQ 0 (
    echo [installer] ERROR: Inno Setup compile failed.
    exit /b 1
)

if not exist "dist\IGPPerformanceMonitor-Setup-%APP_VERSION%.exe" (
    echo [installer] ERROR: installer output missing.
    exit /b 1
)

echo [installer] dist\IGPPerformanceMonitor-Setup-%APP_VERSION%.exe OK
exit /b 0
