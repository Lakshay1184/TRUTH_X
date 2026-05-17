"""
History API endpoints for Truth_X backend.
Handles CRUD operations for analysis history with Supabase integration.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
import uuid
import json
from datetime import datetime

# Initialize router
router = APIRouter(prefix="/api/history", tags=["history"])


# Dependency to get current user (you'll need to implement this based on your auth)
async def get_current_user() -> str:
    """
    Extract user ID from auth context.
    In production, use JWT token validation.
    """
    # TODO: Implement your auth dependency
    # For now, returning placeholder - integrate with your actual auth
    return None


@router.post("/save")
async def save_history(
    task_type: str,
    input_summary: str,
    verdict_label: Optional[str] = None,
    verdict_score: Optional[int] = None,
    processing_time_ms: int = 0,
    evidence_count: int = 0,
    source_count: int = 0,
    summary: Optional[str] = None,
    metadata: Optional[dict] = None,
    user_id: Optional[str] = Query(None),
):
    """
    Save a new analysis history entry.
    
    Called automatically after analysis completes.
    """
    try:
        # Get authenticated user ID from request
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Import history service here to avoid circular imports
        from backend.services.history_service import save_history_entry
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type=task_type,
            input_summary=input_summary,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            evidence_count=evidence_count,
            source_count=source_count,
            summary=summary,
            metadata=metadata,
        )
        
        return {
            "success": True,
            "entry": entry,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    task_type: Optional[str] = None,
    user_id: Optional[str] = Query(None),
):
    """
    Get user's analysis history with optional filtering and pagination.
    """
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        from backend.services.history_service import get_user_history, get_history_by_type
        
        if task_type:
            result = await get_history_by_type(
                user_id=user_id,
                task_type=task_type,
                limit=limit,
                offset=offset,
            )
        else:
            result = await get_user_history(
                user_id=user_id,
                limit=limit,
                offset=offset,
            )
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_history_stats(user_id: Optional[str] = Query(None)):
    """
    Get aggregated statistics about user's analysis history.
    """
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        from backend.services.history_service import get_history_stats
        
        stats = await get_history_stats(user_id=user_id)
        
        return {
            "success": True,
            "stats": stats,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{entry_id}")
async def delete_history_entry(
    entry_id: str,
    user_id: Optional[str] = Query(None),
):
    """
    Delete a specific history entry.
    """
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        from backend.services.history_service import delete_history_entry
        
        success = await delete_history_entry(user_id=user_id, entry_id=entry_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found or unauthorized")
        
        return {
            "success": True,
            "message": "Entry deleted",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/")
async def clear_all_history(user_id: Optional[str] = Query(None)):
    """
    Clear all history for current user (destructive).
    """
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        from backend.services.history_service import clear_user_history
        
        success = await clear_user_history(user_id=user_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to clear history")
        
        return {
            "success": True,
            "message": "All history cleared",
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
