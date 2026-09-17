@echo off
:: Run the self-check areas and tee the report into temp\ so an agent can read
:: it afterwards. Self-elevates because the capture area needs PresentMon,
:: which needs admin.
::
:: Usage: selfcheck.bat [AREA ...] [-a App.exe] [-s SECONDS]
::        selfcheck.bat all
::        selfcheck.bat capture -a Unity.exe -s 8
::
:: The ui and update areas do not need admin; for those just run
::   python -m src.main -t ui
:: directly and read stdout.

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%* --elevated' -Verb RunAs"
    echo Elevated run started in a separate console.
    echo Its report appears at temp\selfcheck\report.txt when it finishes - poll for that file.
    exit /b 0
)

:: Only the console UAC just spawned should wait for a keypress. An already
:: elevated caller - an agent, or CI - would hang on it forever.
:: (shift does not affect %*, so the marker is stripped by substitution.)
set ARGS=%*
set PAUSE_WHEN_DONE=0
if not "%ARGS%"=="%ARGS:--elevated=%" set PAUSE_WHEN_DONE=1
set ARGS=%ARGS:--elevated=%

cd /d "%~dp0\.."
if not exist temp\selfcheck mkdir temp\selfcheck
if "%ARGS%"=="" set ARGS=all
python -m src.main -t %ARGS% > temp\selfcheck\report.txt 2>&1
set RC=%errorlevel%
type temp\selfcheck\report.txt
echo.
echo Report written to temp\selfcheck\report.txt (exit %RC%)
if "%PAUSE_WHEN_DONE%"=="1" pause
exit /b %RC%
