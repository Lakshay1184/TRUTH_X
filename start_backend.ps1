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

# Install (no C++ needed now)
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --quiet fastapi uvicorn python-multipart pyyaml python-dotenv httpx

# Start
Write-Host ""
Write-Host "Starting server on http://localhost:8000 ..." -ForegroundColor Green
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
