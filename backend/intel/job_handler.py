"""Intel Analysis Job Handler

Manages Intel-specific job lifecycle, including history logging to Supabase.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from backend.utils.logger import logger


class IntelJobHandler:
    """Handles Intel analysis jobs with central history service integration."""
    
    def __init__(self):
        pass
    
    async def save_intel_result_to_history(
        self,
        job_id: str,
        content: str,
        content_type: str,
        result: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """
        Save Intel analysis result to Supabase history using history_service.
        
        Args:
            job_id: Analysis job ID
            content: Original content analyzed
            content_type: Type of content
            result: Analysis result from TruthGuard (flattened)
            user_id: Optional user ID
        """
        if not user_id:
            logger.warning("No user_id for Intel history saving, skipping.")
            return

        try:
            from backend.services.history_service import save_history_entry
            
            # Result is now flattened
            verdict = result.get("verdict", {})
            
            # Save to history using central service
            await save_history_entry(
                user_id=user_id,
                task_type="Intel Verification",
                input_summary=content[:200] + "..." if len(content) > 200 else content,
                verdict_label=verdict.get("label", "unverified"),
                verdict_score=int(verdict.get("credibility_score", 50)) if verdict.get("credibility_score") is not None else 50,
                processing_time_ms=int(result.get("processing_time_ms", 0)),
                evidence_count=result.get("sources_analyzed", 0),
                source_count=result.get("sources_analyzed", 0),
                summary=result.get("summary", ""),
                metadata={
                    "content_type": content_type,
                    "claims_found": result.get("claims_found", 0),
                    "supporting_count": result.get("supporting_count", 0),
                    "contradicting_count": result.get("contradicting_count", 0),
                    "neutral_count": result.get("neutral_count", 0),
                    "confidence": verdict.get("confidence", 0.0),
                    "job_id": job_id
                }
            )
            logger.info("Intel result saved to history via history_service: %s", job_id)
        
        except Exception as e:
            logger.error("Failed to save Intel result to history: %s", e)
    
    def _format_time_ms(self, milliseconds: float) -> str:
        """Format milliseconds as human-readable duration."""
        seconds = milliseconds / 1000
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


# Global handler instance
_handler: Optional[IntelJobHandler] = None


def get_intel_handler() -> IntelJobHandler:
    """Get or create the global Intel job handler."""
    global _handler
    if _handler is None:
        _handler = IntelJobHandler()
    return _handler
