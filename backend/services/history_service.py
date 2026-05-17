"""
History service for storing and retrieving analysis history entries.
Integrates with Supabase for user-specific data persistence.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
from pydantic import BaseModel

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or "your-project" in SUPABASE_URL:
    print("Warning: Supabase environment variables not configured. History service disabled.")
    supabase = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        supabase = None


class HistoryEntry(BaseModel):
    """Schema for history entry storage."""
    task_type: str
    input_summary: str
    verdict_label: Optional[str] = None
    verdict_score: Optional[int] = None
    processing_time_ms: int
    processing_time_formatted: str
    evidence_count: int = 0
    source_count: int = 0
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def format_processing_time(milliseconds: int) -> str:
    """Format milliseconds into human-readable time string."""
    if milliseconds < 1000:
        return f"{milliseconds}ms"
    elif milliseconds < 60000:
        seconds = milliseconds / 1000
        return f"{seconds:.1f}s"
    else:
        minutes = milliseconds // 60000
        seconds = (milliseconds % 60000) / 1000
        return f"{minutes}m {seconds:.0f}s"


async def save_history_entry(
    user_id: str,
    task_type: str,
    input_summary: str,
    verdict_label: Optional[str] = None,
    verdict_score: Optional[int] = None,
    processing_time_ms: int = 0,
    evidence_count: int = 0,
    source_count: int = 0,
    summary: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Save an analysis history entry to Supabase.
    
    Args:
        user_id: Authenticated user UUID
        task_type: Type of analysis (Intel Verification, Video Analysis, etc.)
        input_summary: Brief summary of input (URL, filename, text preview)
        verdict_label: Result label (Supported, Contradicted, AI Generated, etc.)
        verdict_score: Credibility score (0-100)
        processing_time_ms: Processing time in milliseconds
        evidence_count: Number of evidence sources found
        source_count: Number of sources analyzed
        summary: Brief intelligence summary
        metadata: Additional metadata as dict
    
    Returns:
        The created history entry object
    """
    try:
        processing_time_formatted = format_processing_time(processing_time_ms)
        
        entry = {
            "user_id": user_id,
            "task_type": task_type,
            "input_summary": input_summary,
            "verdict_label": verdict_label,
            "verdict_score": verdict_score,
            "processing_time_ms": processing_time_ms,
            "processing_time_formatted": processing_time_formatted,
            "evidence_count": evidence_count,
            "source_count": source_count,
            "summary": summary,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if supabase is None:
            return entry

        response = supabase.table("analysis_history").insert(entry).execute()
        return response.data[0] if response.data else entry
    
    except Exception as e:
        print(f"Error saving history entry: {str(e)}")
        raise


async def get_user_history(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Fetch user's analysis history with pagination.
    
    Args:
        user_id: Authenticated user UUID
        limit: Number of entries to fetch (default 20)
        offset: Pagination offset (default 0)
    
    Returns:
        Dict with entries and total count
    """
    try:
        if supabase is None:
            return {"entries": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}

        # Get total count
        count_response = supabase.table("analysis_history").select(
            "count()", count="exact"
        ).eq("user_id", user_id).execute()
        
        total_count = count_response.count if hasattr(count_response, 'count') else 0
        
        # Get paginated entries (newest first)
        response = supabase.table("analysis_history").select(
            "*"
        ).eq("user_id", user_id).order(
            "created_at", desc=True
        ).range(offset, offset + limit - 1).execute()
        
        return {
            "entries": response.data or [],
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
        }
    
    except Exception as e:
        print(f"Error fetching history: {str(e)}")
        raise


async def get_history_by_type(
    user_id: str,
    task_type: str,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Fetch user's history filtered by task type.
    
    Args:
        user_id: Authenticated user UUID
        task_type: Task type to filter by
        limit: Number of entries to fetch
        offset: Pagination offset
    
    Returns:
        Dict with filtered entries and total count
    """
    try:
        if supabase is None:
            return {"entries": [], "total": 0, "limit": limit, "offset": offset, "has_more": False, "task_type": task_type}

        count_response = supabase.table("analysis_history").select(
            "count()", count="exact"
        ).eq("user_id", user_id).eq("task_type", task_type).execute()
        
        total_count = count_response.count if hasattr(count_response, 'count') else 0
        
        response = supabase.table("analysis_history").select(
            "*"
        ).eq("user_id", user_id).eq(
            "task_type", task_type
        ).order(
            "created_at", desc=True
        ).range(offset, offset + limit - 1).execute()
        
        return {
            "entries": response.data or [],
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
            "task_type": task_type,
        }
    
    except Exception as e:
        print(f"Error fetching history by type: {str(e)}")
        raise


async def delete_history_entry(user_id: str, entry_id: str) -> bool:
    """
    Delete a specific history entry (user-specific).
    
    Args:
        user_id: Authenticated user UUID
        entry_id: History entry UUID to delete
    
    Returns:
        True if successful
    """
    try:
        if supabase is None:
            return False

        response = supabase.table("analysis_history").delete().eq(
            "id", entry_id
        ).eq("user_id", user_id).execute()
        return True
    
    except Exception as e:
        print(f"Error deleting history entry: {str(e)}")
        return False


async def clear_user_history(user_id: str) -> bool:
    """
    Clear all history for a user (destructive).
    
    Args:
        user_id: Authenticated user UUID
    
    Returns:
        True if successful
    """
    try:
        if supabase is None:
            return False

        response = supabase.table("analysis_history").delete().eq(
            "user_id", user_id
        ).execute()
        return True
    
    except Exception as e:
        print(f"Error clearing user history: {str(e)}")
        return False


async def get_history_stats(user_id: str) -> Dict[str, Any]:
    """
    Get aggregated statistics about user's analysis history.
    
    Args:
        user_id: Authenticated user UUID
    
    Returns:
        Dict with statistics
    """
    try:
        if supabase is None:
            return {"total_analyses": 0, "task_type_distribution": {}, "top_task_type": None}

        # Total entries
        total_response = supabase.table("analysis_history").select(
            "count()", count="exact"
        ).eq("user_id", user_id).execute()
        
        total_count = total_response.count if hasattr(total_response, 'count') else 0
        
        # Get task type distribution (fetch small sample and count locally)
        response = supabase.table("analysis_history").select(
            "task_type"
        ).eq("user_id", user_id).limit(1000).execute()
        
        task_type_counts = {}
        for entry in response.data or []:
            task = entry.get("task_type", "Unknown")
            task_type_counts[task] = task_type_counts.get(task, 0) + 1
        
        return {
            "total_analyses": total_count,
            "task_type_distribution": task_type_counts,
            "top_task_type": max(task_type_counts.items(), key=lambda x: x[1])[0] if task_type_counts else None,
        }
    
    except Exception as e:
        print(f"Error fetching history stats: {str(e)}")
        return {
            "total_analyses": 0,
            "task_type_distribution": {},
            "top_task_type": None,
        }
