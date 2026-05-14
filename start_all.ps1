# start_all.ps1 — Truth_X Orchestration Script

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Truth_X Unified Service Launcher" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# 1. Start Backend API
Write-Host "Step 1: Launching FastAPI Backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python -m uvicorn backend.api:app --reload --port 8000"

# 2. Start Celery Worker
Write-Host "Step 2: Launching Celery Worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\celery -A backend.workers.celery_app worker --loglevel=info -P solo"

# 3. Start Frontend
Write-Host "Step 3: Launching Next.js Frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "All services are starting." -ForegroundColor Green
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"
