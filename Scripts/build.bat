@echo off
setlocal
echo ============================================
echo  IGP Performance Monitor - Build
echo ============================================

cd /d "%~dp0\.."

:: Read semantic version from VERSION file (single source of truth)
set /p APP_VERSION=<VERSION
for /f "tokens=* delims= " %%I in ("%APP_VERSION%") do set "APP_VERSION=%%~I"
if not defined APP_VERSION (echo [build] ERROR: VERSION file empty or missing & exit /b 1)

:: Build metadata: timestamp + git short sha
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd-HHmmss\")"') do set "BUILD_TS=%%I"
for /f %%I in ('git rev-parse --short HEAD 2^>nul') do set "GIT_SHA=%%I"
if not defined GIT_SHA set "GIT_SHA=nogit"
set "APP_BUILD=%BUILD_TS%-%GIT_SHA%"
echo [build] Version: %APP_VERSION% (build %APP_BUILD%)

:: Write build metadata (NOT the version — version comes from VERSION file)
if not exist "build\generated" mkdir "build\generated"
powershell -NoProfile -Command ^
    "[System.IO.File]::WriteAllText('build\\generated\\build_info.txt', '%APP_BUILD%', (New-Object System.Text.UTF8Encoding($false)))"

:: Clean
if exist "dist" rmdir /s /q "dist"
if exist "build\IGPPerformanceMonitor" rmdir /s /q "build\IGPPerformanceMonitor"
if exist "build\auto_updater" rmdir /s /q "build\auto_updater"

:: Build main EXE
echo.
echo [build] Building IGPPerformanceMonitor.exe...
python -m PyInstaller --noconfirm --onefile --windowed --uac-admin ^
    --name "IGPPerformanceMonitor" ^
    --icon "assets\icon.ico" ^
    --add-data "third-party\PresentMon-2.4.1-x64.exe;third-party" ^
    --add-data "build\generated\build_info.txt;build\generated" ^
    --add-data "VERSION;." ^
    --add-data "CHANGELOG.md;." ^
    --add-data "CHANGELOG.zh-CN.md;." ^
    --add-data "docs;docs" ^
    --add-data "src\i18n\locales;src/i18n/locales" ^
    --add-data "assets\icon.png;assets" ^
    --add-data "assets\icon.ico;assets" ^
    --hidden-import psutil ^
    --hidden-import pynvml ^
    --hidden-import win32api ^
    --hidden-import win32con ^
    --hidden-import win32pdh ^
    --clean ^
    src\main.py
if %ERRORLEVEL% NEQ 0 goto :fail

if not exist "dist\IGPPerformanceMonitor.exe" goto :fail
echo [build] IGPPerformanceMonitor.exe OK

:: Build auto_updater EXE
echo.
echo [build] Building auto_updater.exe...
python -m PyInstaller --noconfirm --onefile --noconsole ^
    --name "auto_updater" ^
    --icon "assets\icon.ico" ^
    --clean ^
    src\auto_updater\main.py
if %ERRORLEVEL% NEQ 0 goto :fail

if not exist "dist\auto_updater.exe" goto :fail
echo [build] auto_updater.exe OK

echo.
echo ============================================
echo  Build succeeded!
echo  dist\IGPPerformanceMonitor.exe
echo  dist\auto_updater.exe
echo ============================================
if /I "%CI%"=="true" exit /b 0
if /I "%1"=="--no-pause" exit /b 0
pause
exit /b 0

:fail
echo.
echo ============================================
echo  Build FAILED!
echo ============================================
if /I not "%CI%"=="true" if /I not "%1"=="--no-pause" pause
exit /b 1
