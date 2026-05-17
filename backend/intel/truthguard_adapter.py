"""TruthGuard Integration Adapter

Bridges TruthGuard analysis engine to Truth_X Intel backend.
Converts TruthGuard outputs to Truth_X frontend API contract.

This implementation wraps the internal IntelEngine.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from backend.utils.logger import logger
from backend.intel.engine import IntelEngine


class TruthGuardAdapter:
    """
    Adapter that integrates the internal IntelEngine as the TruthGuard backend.
    """
    
    def __init__(self):
        self.logger = logger
        self.engine = IntelEngine()
        self.truthguard_available = True
    
    async def analyze_content(
        self,
        content: str,
        content_type: str,
        trace_id: str,
        progress_callback: Optional[callable] = None,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run Intel analysis on content.
        
        Args:
            content: The text/URL/media to analyze
            content_type: Type of content (text, url, youtube, etc.)
            trace_id: Unique trace ID for this analysis
            progress_callback: Optional callback(progress_pct, status_msg)
            file_path: Optional path to local media file
        
        Returns:
            Analysis result in Truth_X frontend format
        """
        start_time = time.perf_counter()
        
        try:
            self.logger.info(
                f"Intel analysis start | trace_id={trace_id} | content_type={content_type} | file={bool(file_path)}"
            )
            
            # Map Truth_X content types to engine override if needed
            input_type = self._map_content_type_to_input_type(content_type)
            
            # Run the synchronous IntelEngine directly in the current background thread.
            engine_result = self.engine.analyze(
                content=content,
                content_type_override=input_type,
                progress_callback=progress_callback,
                file_path=file_path
            )
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            # Add metadata for backend tracking
            engine_result["processing_time_ms"] = elapsed_ms
            engine_result["originalContent"] = content
            
            return engine_result
        
        except Exception as e:
            self.logger.error(
                f"Intel analysis error | trace_id={trace_id} | error={str(e)}"
            )
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def answer_question(
        self,
        question: str,
        context: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
        verification_result: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        conversation_history: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a question about a completed analysis using RAG.
        
        Args:
            question: The question to answer
            context: The original content/context
            evidence: Previously retrieved evidence items
            verification_result: Full previous analysis result
            job_id: ID of completed analysis job
            conversation_history: Previous Q&A turns
        
        Returns:
            Answer in frontend format
        """
        try:
            # Run the synchronous IntelEngine in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.engine.answer(
                    content=context,
                    question=question,
                    evidence=evidence,
                    verification_result=verification_result
                )
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Failed to answer question: {e}")
            return {
                "status": "error",
                "message": str(e),
            }

    def _map_content_type_to_input_type(self, content_type: str) -> str:
        """Map Truth_X content types to IntelEngine input types."""
        mapping = {
            "text": "raw_text",
            "headline": "raw_text",
            "url": "news_article",
            "news_url": "news_article",
            "news_article": "news_article",
            "youtube": "video_content",
            "youtube_url": "video_content",
            "video_content": "video_content",
            "twitter": "social_media",
            "twitter_url": "social_media",
            "instagram": "social_media",
            "instagram_url": "social_media",
            "social_media": "social_media",
            "video": "video_content",
            "video_file": "video_content",
            "image": "raw_text",
            "screenshot": "raw_text",
            "social_post": "social_media",
        }
        return mapping.get(content_type.lower(), "raw_text")


# Global adapter instance
_adapter: Optional[TruthGuardAdapter] = None


def get_adapter() -> TruthGuardAdapter:
    """Get or create the global TruthGuard adapter."""
    global _adapter
    if _adapter is None:
        _adapter = TruthGuardAdapter()
    return _adapter
