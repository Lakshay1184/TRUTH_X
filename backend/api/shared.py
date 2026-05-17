"""
Shared state and utilities for Truth_X API.
"""

from __future__ import annotations

import os
import re
import httpx
from typing import Optional, Literal
from backend.utils.logger import logger
from backend.utils.env_loader import ensure_backend_environment_loaded, log_runtime_env_status
from backend.workers.job_manager import JobManager
from backend.pipelines.main_pipeline import DeepfakeDetectionPipeline

AnalysisModality = Literal["text", "image", "audio", "video"]

# Global State
_pipeline: Optional[DeepfakeDetectionPipeline] = None
_job_manager = JobManager()

async def _log_to_supabase(table: str, data: dict) -> None:
    """
    Log analysis data to Supabase using history_service.
    Maintains compatibility with existing code while fixing the underlying issue.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        user_id = data.get("user_id")
        if not user_id:
            logger.warning("No user_id provided for history log, skipping.")
            return

        # Map 'analysis_history' fields from data dict
        await save_history_entry(
            user_id=user_id,
            task_type=data.get("task_type", "AI Detection"),
            input_summary=data.get("input_summary", "Media Analysis"),
            verdict_label=data.get("verdict_label"),
            verdict_score=data.get("verdict_score"),
            processing_time_ms=data.get("processing_time_ms", 0),
            evidence_count=data.get("evidence_count", 0),
            source_count=data.get("source_count", 0),
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
        )
        logger.info("Intelligence history logged via history_service")
    except Exception as e:
        logger.error("Failed to log to history_service: %s", e)
