# Bundesliga Tippspiel - Windows Native Starter
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   BUNDESLIGA TIPPSPIEL" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check if venv exists
if (-not (Test-Path "$projectDir\venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv "$projectDir\venv"
    
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & "$projectDir\venv\Scripts\pip.exe" install -r "$projectDir\requirements.txt"
}

# Activate venv and start app
Write-Host "Starting Tippspiel Web-App..." -ForegroundColor Yellow
Write-Host "Browser will open at http://127.0.0.1:5000" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop: Ctrl+C or close this window" -ForegroundColor Gray
Write-Host ""

& "$projectDir\venv\Scripts\python.exe" "$projectDir\webapp.py"
