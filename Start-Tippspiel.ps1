# Bundesliga Tippspiel - Windows Starter
# Dieses Script startet die Web-App und oeffnet den Browser

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   BUNDESLIGA TIPPSPIEL" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# WSL-Pfad
$wslPath = "/home/pittche/claude/Claude-Projects/Tipp-Spiel"

# Pruefen ob WSL verfuegbar
try {
    $wslCheck = wsl -e echo "ok" 2>&1
    if ($wslCheck -ne "ok") {
        throw "WSL nicht verfuegbar"
    }
} catch {
    Write-Host "FEHLER: WSL ist nicht installiert oder nicht gestartet." -ForegroundColor Red
    Write-Host "Bitte starte WSL zuerst." -ForegroundColor Yellow
    Read-Host "Druecke Enter zum Beenden"
    exit 1
}

Write-Host "Starte Tippspiel Web-App..." -ForegroundColor Yellow
Write-Host "Browser oeffnet sich automatisch auf http://127.0.0.1:5000" -ForegroundColor Gray
Write-Host ""
Write-Host "Zum Beenden: Ctrl+C oder dieses Fenster schliessen" -ForegroundColor Gray
Write-Host ""

# Web-App starten
wsl -e bash -c "cd $wslPath && python3 webapp.py"
