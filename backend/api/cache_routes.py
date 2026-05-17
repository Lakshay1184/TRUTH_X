"""
Result caching routes for Truth_X.
"""

import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from backend.utils.logger import logger

router = APIRouter(tags=["cache"])

_recent_results: Dict[str, Any] = {}

@router.post("/cache-result")
async def cache_result(result: Dict[str, Any]) -> Dict[str, str]:
    """Cache an analysis result and return its ID for later retrieval."""
    result_id = str(uuid.uuid4())[:8]
    _recent_results[result_id] = result

    # Evict oldest if over limit
    if len(_recent_results) > 50:
        oldest_key = next(iter(_recent_results))
        del _recent_results[oldest_key]

    logger.info("Cached result %s (total cached: %d)", result_id, len(_recent_results))
    return {"id": result_id}

@router.get("/result/{result_id}")
async def get_result(result_id: str) -> Dict[str, Any]:
    """Retrieve a cached analysis result by ID."""
    if result_id not in _recent_results:
        raise HTTPException(404, "Result not found or expired.")
    return _recent_results[result_id]
