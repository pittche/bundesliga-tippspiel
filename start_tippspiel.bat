@echo off
title Bundesliga Tippspiel
echo.
echo ============================================
echo   BUNDESLIGA TIPPSPIEL - Starte Web App
echo ============================================
echo.

REM Browser auf Windows-Seite oeffnen (nach 2 Sekunden Verzoegerung)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8080"

REM WSL mit Python starten (ohne Browser-Oeffnung)
wsl -e bash -c "cd /home/pittche/claude/Claude-Projects/Tipp-Spiel && python3 webapp.py --no-browser"

pause
