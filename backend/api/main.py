from __future__ import annotations

"""
Truth_X — FastAPI server main entrypoint.
Optimized for immediate port binding on Render.
"""

import os
import time

# PRE-IMPORT MILESTONE
start_time = time.time()
print(f">>> BACKEND STARTUP: main.py execution started at {start_time}")
print(f">>> RENDER PORT DETECTED: {os.environ.get('PORT', 'NOT_FOUND (Defaulting to 10000)')}")

import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# CORE IMPORTS COMPLETE
print(">>> BACKEND STARTUP: FastAPI and Core imports complete")

import asyncio
from . import shared

async def warmup_task():
    """Background task to warm up stable detectors after startup."""
    # Wait a few seconds to ensure uvicorn has bound the port and is serving requests
    await asyncio.sleep(5)
    print(">>> BACKGROUND WARMUP: Starting stable detector preloading...")
    try:
        pipeline = shared.get_pipeline()
        # Preload ONLY lightweight/stable detectors to stay within memory limits
        pipeline.warmup_models(["image", "text"])
        print(">>> BACKGROUND WARMUP: Image and Text detectors are now warm ✓")
    except Exception as e:
        print(f">>> BACKGROUND WARMUP ERROR: {e}")

@asynccontextmanager
async def lifespan(application: FastAPI):
    print(">>> LIFESPAN START: Initializing lightweight environment...")
    try:
        from backend.utils.env_loader import ensure_backend_environment_loaded, log_runtime_env_status
        ensure_backend_environment_loaded()
        log_runtime_env_status("api_startup")
    except Exception as e:
        print(f">>> LIFESPAN ERROR during env load: {e}")

    # Start background warmup WITHOUT blocking the lifespan yield
    # This allows uvicorn to bind the port IMMEDIATELY
    asyncio.create_task(warmup_task())

    print(">>> LIFESPAN COMPLETE: API reached ready state ✓ (Warmup running in background)")
    yield
    print(">>> LIFESPAN SHUTDOWN: Cleaning up...")

app = FastAPI(
    title="truth.x",
    description="Multi-modal AI content verification system",
    version="2.0.0",
    lifespan=lifespan,
)

# FASTAPI CREATED
print(">>> BACKEND STARTUP: FastAPI instance created")

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
    # We use local imports inside the try block to catch any import-time stalls
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
    print(f">>> BACKEND STARTUP ERROR during router registration: {e}")
    import traceback
    traceback.print_exc()

# ROUTES REGISTERED
print(">>> BACKEND STARTUP: Routers registered. Auditing active endpoints...")
for route in app.routes:
    methods = getattr(route, "methods", None)
    path = getattr(route, "path", None)
    if path:
        print(f"    ‣ [ROUTE] {list(methods) if methods else 'N/A'} {path}")

print(f">>> BACKEND STARTUP: Total startup sequence duration: {time.time() - start_time:.4f}s")
print(">>> BACKEND STARTUP: Application ready for Uvicorn.")
print(">>> BACKEND STARTUP: Uvicorn should now bind the port and start listening...")
