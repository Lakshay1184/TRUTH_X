"""
Health check routes for Truth_X.
"""

from typing import Dict
from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Return empty response or a small transparent pixel to satisfy the browser
    return FileResponse(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "favicon.ico")) if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "favicon.ico")) else {"status": "not found"}
