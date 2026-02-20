# start_backend.ps1
Write-Host "Initializing Truth X Backend..." -ForegroundColor Cyan

# Delete old broken venv
if (Test-Path "venv") {
    Write-Host "Removing old virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "venv"
}

# Create fresh venv
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Activate
Write-Host "Activating..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Install (all deps from requirements.txt)
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --quiet -r backend/requirements.txt

# Start
Write-Host ""
Write-Host "Starting server on http://localhost:8000 ..." -ForegroundColor Green
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8001 --reload
# start_backend.ps1
Write-Host "Initializing Truth X Backend..." -ForegroundColor Cyan

# Create venv if not exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}
else {
    Write-Host "Using existing virtual environment." -ForegroundColor Green
}

# Activate
Write-Host "Activating..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Install (all deps from requirements.txt)
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --quiet -r backend/requirements.txt

# Start
Write-Host ""
Write-Host "Starting server on http://localhost:8000 ..." -ForegroundColor Green
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8001 --reload
