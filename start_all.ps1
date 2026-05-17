# start_all.ps1 — Truth_X Orchestration Script

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Truth_X Unified Service Launcher" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

$backendPort = 8000
$frontendPort = 4040

$pythonExe = "python"
if (Test-Path ".venv\Scripts\python.exe") {
	$pythonExe = ".venv\Scripts\python.exe"
} elseif (Test-Path "venv\Scripts\python.exe") {
	$pythonExe = "venv\Scripts\python.exe"
}

# 1. Start Backend API
Write-Host "Step 1: Launching FastAPI Backend..." -ForegroundColor Yellow
Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList "-NoExit", "-Command", "`"$pythonExe`" -m uvicorn backend.api:app --reload --port $backendPort"

# 2. Start Celery Worker
Write-Host "Step 2: Launching Celery Worker..." -ForegroundColor Yellow
Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList "-NoExit", "-Command", "`"$pythonExe`" -m celery -A backend.workers.celery_app worker --loglevel=info -P solo"

# 3. Start Frontend
Write-Host "Step 3: Launching Next.js Frontend..." -ForegroundColor Yellow
if (Test-Path ".next") {
	Write-Host "-> Clearing stale Next.js build cache..." -ForegroundColor Yellow
	Remove-Item -Recurse -Force ".next"
}
Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList "-NoExit", "-Command", "npm run dev -- -p $frontendPort"

Write-Host "All services are starting." -ForegroundColor Green
Write-Host "Backend: http://localhost:$backendPort"
Write-Host "Frontend: http://localhost:$frontendPort"
