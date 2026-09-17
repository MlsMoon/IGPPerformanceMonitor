@echo off
:: Timed PresentMon capture-debug session; output redirected to temp\ so
:: debug artifacts don't pollute the project root.
:: Usage: capture_debug.bat [--process-name NAME | --all-processes] [--timed N]

:: Self-elevate to administrator if not already elevated
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0\.."
if not exist temp mkdir temp
python -m src.main --headless %* > temp\capture_debug.txt 2>&1
echo Output written to temp\capture_debug.txt
type temp\capture_debug.txt
pause
