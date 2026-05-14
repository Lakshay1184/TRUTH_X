# start_backend.ps1 — truth.x Backend Launcher
Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  truth.x Backend Server" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan

# Activate venv if present
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "`n→ Activating virtual environment..." -ForegroundColor Yellow
    .\venv\Scripts\Activate.ps1
} elseif (Test-Path "venv_new\Scripts\Activate.ps1") {
    Write-Host "`n→ Activating virtual environment (venv_new)..." -ForegroundColor Yellow
    .\venv_new\Scripts\Activate.ps1
} else {
    Write-Host "`n⚠ No venv found — using system Python" -ForegroundColor Yellow
}

# Install core deps if missing
Write-Host "→ Checking dependencies..." -ForegroundColor Yellow
pip install --quiet fastapi uvicorn python-multipart pyyaml python-dotenv httpx 2>$null

# Create data directories
New-Item -ItemType Directory -Force -Path "data\processed" | Out-Null

# Start server
Write-Host ""
Write-Host "→ Starting server on http://localhost:8000" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
