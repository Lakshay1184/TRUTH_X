"""
Truth_X — FastAPI server main entrypoint.
Modularized architecture.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.utils.env_loader import ensure_backend_environment_loaded, log_runtime_env_status
from backend.utils.logger import logger
from . import shared
from backend.pipelines.main_pipeline import DeepfakeDetectionPipeline

@asynccontextmanager
async def lifespan(application: FastAPI):
    shared.ensure_backend_environment_loaded()
    log_runtime_env_status("api_startup")

    # Pre-initialize pipeline (models lazy-load on first request)
    shared._pipeline = DeepfakeDetectionPipeline()
    
    # Pre-initialize Intel Adapter and its models in background thread
    def _init_intel():
        try:
            from backend.intel.truthguard_adapter import get_adapter
            get_adapter()
            logger.info("Intel system pre-initialized in background")
        except Exception as e:
            logger.error("Failed to pre-initialize Intel system: %s", e)

    threading.Thread(target=_init_intel, daemon=True).start()
    
    logger.info("API initialized (models will lazy-load in background) ✓")
    yield
    shared._pipeline = None

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
from backend.api.health_routes import router as health_router
from backend.api.analyze_routes import router as analyze_router
from backend.api.intel_routes import router as intel_router
from backend.api.history_routes import router as history_router
from backend.api.live_routes import router as live_router
from backend.api.social_routes import router as social_router
from backend.api.explain_routes import router as explain_router
from backend.api.cache_routes import router as cache_router

app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(intel_router)
app.include_router(history_router)
app.include_router(live_router)
app.include_router(social_router)
app.include_router(explain_router)
app.include_router(cache_router)
