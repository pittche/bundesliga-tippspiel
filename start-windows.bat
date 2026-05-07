@echo off
REM Bundesliga Tippspiel - Windows Batch Starter

echo.
echo ============================================
echo    BUNDESLIGA TIPPSPIEL
echo ============================================
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    
    echo Installing dependencies...
    venv\Scripts\pip.exe install -r requirements.txt
)

echo Starting Tippspiel Web-App...
echo Browser will open at http://127.0.0.1:5000
echo.
echo To stop: Ctrl+C or close this window
echo.

venv\Scripts\python.exe webapp.py
pause
