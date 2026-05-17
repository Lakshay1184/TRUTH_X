"""
Social media intelligence routes for Truth_X.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.utils.logger import logger

router = APIRouter(prefix="/social", tags=["social"])

class SocialScanRequest(BaseModel):
    url: str

@router.post("/scan")
async def scan_social_media(request: SocialScanRequest) -> Dict[str, Any]:
    """Scrapes a social media URL and extracts content."""
    from backend.workers.social_scanner import scan_social_url
    try:
        result = scan_social_url(request.url)
        status = result.get("status", "success") if isinstance(result, dict) else "success"
        return {"status": status, "result": result}
    except Exception as e:
        logger.error("Social scan failed: %s", e)
        raise HTTPException(500, f"Social scan failed: {e}")

@router.get("/graph/{content_id}")
async def get_propagation_graph(content_id: str, url: str) -> Dict[str, Any]:
    """Build and return the misinformation propagation graph for a given content."""
    from backend.workers.social_scanner import build_propagation_graph
    try:
        graph = build_propagation_graph(url, content_id)
        return {"status": "success", "graph": graph}
    except Exception as e:
        logger.error("Graph generation failed: %s", e)
        raise HTTPException(500, f"Graph generation failed: {e}")
