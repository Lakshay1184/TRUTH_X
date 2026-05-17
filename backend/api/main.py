"""
Truth_X — FastAPI server main entrypoint.
Modularized architecture.
"""

print(">>> BACKEND STARTUP: main.py execution started")

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

print(">>> BACKEND STARTUP: Imports progressing...")

from backend.utils.env_loader import ensure_backend_environment_loaded, log_runtime_env_status
from backend.utils.logger import logger
from . import shared

print(">>> BACKEND STARTUP: Shared state imported")

@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("LIFESPAN START: Initializing environment...")
    shared.ensure_backend_environment_loaded()
    log_runtime_env_status("api_startup")

    # HEAVY SYSTEM OPTIMIZATION:
    # All components (Pipeline, Detectors, Intel) will now lazy-load on demand.
    # This ensures uvicorn binds to the port IMMEDIATELY without blocking on ML setup.
    
    logger.info("LIFESPAN COMPLETE: API ready for port binding ✓")
    yield
    logger.info("LIFESPAN SHUTDOWN: Cleaning up...")

app = FastAPI(
    title="truth.x",
    description="Multi-modal AI content verification system",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
print(">>> BACKEND STARTUP: Registering routers...")

try:
    print(">>> BACKEND STARTUP: Importing health_routes...")
    from backend.api.health_routes import router as health_router
    app.include_router(health_router)
    
    print(">>> BACKEND STARTUP: Importing analyze_routes...")
    from backend.api.analyze_routes import router as analyze_router
    app.include_router(analyze_router)
    
    print(">>> BACKEND STARTUP: Importing intel_routes...")
    from backend.api.intel_routes import router as intel_router
    app.include_router(intel_router)
    
    print(">>> BACKEND STARTUP: Importing history_routes...")
    from backend.api.history_routes import router as history_router
    app.include_router(history_router)
    
    print(">>> BACKEND STARTUP: Importing live_routes...")
    from backend.api.live_routes import router as live_router
    app.include_router(live_router)
    
    print(">>> BACKEND STARTUP: Importing social_routes...")
    from backend.api.social_routes import router as social_router
    app.include_router(social_router)
    
    print(">>> BACKEND STARTUP: Importing explain_routes...")
    from backend.api.explain_routes import router as explain_router
    app.include_router(explain_router)
    
    print(">>> BACKEND STARTUP: Importing cache_routes...")
    from backend.api.cache_routes import router as cache_router
    app.include_router(cache_router)
    
except Exception as e:
    print(f">>> BACKEND STARTUP ERROR: {e}")
    import traceback
    traceback.print_exc()

print(">>> BACKEND STARTUP: Routers registered. Startup sequence finished.")
