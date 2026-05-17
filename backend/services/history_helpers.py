"""
Helper utilities for automatically saving analysis history.
Integrates with IntelEngine and other analysis pipelines.
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


async def save_intel_analysis_history(
    user_id: str,
    input_content: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save Intel analysis to history after IntelEngine.analyze() completes.
    
    Args:
        user_id: Authenticated user UUID
        input_content: Original content analyzed
        analysis_result: Dict returned from IntelEngine.analyze()
        processing_time_ms: Total processing time in milliseconds
    
    Returns:
        True if successfully saved
    """
    try:
        from backend.services.history_service import save_history_entry
        
        # Extract metadata from analysis result
        verdict = analysis_result.get("verdict", {})
        verdict_label = verdict.get("label")
        verdict_score = verdict.get("confidence")
        
        evidence = analysis_result.get("evidence", [])
        evidence_count = len(evidence)
        
        sources_analyzed = analysis_result.get("sources_analyzed", 0)
        
        summary = analysis_result.get("summary", "")
        
        # Truncate input summary
        input_summary = input_content[:100] if len(input_content) > 100 else input_content
        
        # Create metadata object
        metadata = {
            "claims_found": analysis_result.get("claims_found", 0),
            "pipeline_stage": analysis_result.get("pipeline_stage"),
            "model_used": "Intel Pipeline v1",
        }
        
        # Save to history
        entry = await save_history_entry(
            user_id=user_id,
            task_type="Intel Verification",
            input_summary=input_summary,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            evidence_count=evidence_count,
            source_count=sources_analyzed,
            summary=summary,
            metadata=metadata,
        )
        
        logger.info(f"Saved Intel analysis history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving Intel analysis history: {str(e)}")
        return False


async def save_video_analysis_history(
    user_id: str,
    video_filename: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save video analysis to history.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        verdict_label = analysis_result.get("classification")
        verdict_score = analysis_result.get("confidence")
        
        metadata = {
            "video_duration_seconds": analysis_result.get("duration"),
            "frames_analyzed": analysis_result.get("frames_analyzed"),
            "model_used": analysis_result.get("model"),
        }
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type="Video Analysis",
            input_summary=video_filename,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            metadata=metadata,
        )
        
        logger.info(f"Saved video analysis history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving video analysis history: {str(e)}")
        return False


async def save_image_analysis_history(
    user_id: str,
    image_filename: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save image analysis to history.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        verdict_label = analysis_result.get("classification")
        verdict_score = analysis_result.get("confidence")
        
        metadata = {
            "image_resolution": analysis_result.get("resolution"),
            "manipulations_detected": analysis_result.get("manipulations"),
            "model_used": analysis_result.get("model"),
        }
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type="Image Analysis",
            input_summary=image_filename,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            metadata=metadata,
        )
        
        logger.info(f"Saved image analysis history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving image analysis history: {str(e)}")
        return False


async def save_text_analysis_history(
    user_id: str,
    text_content: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save text analysis to history.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        verdict_label = analysis_result.get("classification")
        verdict_score = analysis_result.get("confidence")
        
        # Truncate summary
        text_summary = text_content[:100] if len(text_content) > 100 else text_content
        
        metadata = {
            "text_length": len(text_content),
            "sentences_analyzed": analysis_result.get("sentences_analyzed"),
            "model_used": analysis_result.get("model"),
        }
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type="Text Analysis",
            input_summary=text_summary,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            metadata=metadata,
        )
        
        logger.info(f"Saved text analysis history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving text analysis history: {str(e)}")
        return False


async def save_ai_detection_history(
    user_id: str,
    content_filename: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save AI detection analysis to history.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        verdict_label = analysis_result.get("ai_detection_label")
        verdict_score = analysis_result.get("ai_score")
        
        metadata = {
            "detection_type": analysis_result.get("type"),
            "model_used": analysis_result.get("model"),
            "artifacts_found": analysis_result.get("artifacts_found"),
        }
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type="AI Detection",
            input_summary=content_filename,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            metadata=metadata,
        )
        
        logger.info(f"Saved AI detection history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving AI detection history: {str(e)}")
        return False


async def save_fake_news_check_history(
    user_id: str,
    article_title: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save fake news check analysis to history.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        verdict_label = analysis_result.get("misinformation_label")
        verdict_score = analysis_result.get("misinformation_confidence")
        
        metadata = {
            "fact_checks_found": analysis_result.get("fact_checks"),
            "source_credibility": analysis_result.get("source_credibility"),
            "model_used": "Fake News Pipeline v1",
        }
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type="Fake News Check",
            input_summary=article_title[:100],
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            summary=analysis_result.get("analysis_summary"),
            metadata=metadata,
        )
        
        logger.info(f"Saved fake news check history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving fake news check history: {str(e)}")
        return False


async def save_url_verification_history(
    user_id: str,
    url: str,
    analysis_result: Dict[str, Any],
    processing_time_ms: int,
) -> bool:
    """
    Save URL verification analysis to history.
    """
    try:
        from backend.services.history_service import save_history_entry
        
        verdict_label = analysis_result.get("url_verdict")
        verdict_score = analysis_result.get("safety_score")
        
        metadata = {
            "url_domain": analysis_result.get("domain"),
            "phishing_detected": analysis_result.get("phishing_detected"),
            "malware_detected": analysis_result.get("malware_detected"),
            "model_used": "URL Safety Pipeline v1",
        }
        
        entry = await save_history_entry(
            user_id=user_id,
            task_type="URL Verification",
            input_summary=url,
            verdict_label=verdict_label,
            verdict_score=verdict_score,
            processing_time_ms=processing_time_ms,
            metadata=metadata,
        )
        
        logger.info(f"Saved URL verification history for user {user_id}: {entry.get('id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving URL verification history: {str(e)}")
        return False
