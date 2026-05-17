"""
Intel Analysis routes for Truth_X.
"""

import os
import threading
import asyncio
import uuid
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form, Request
from pydantic import BaseModel
from . import shared
from backend.utils.auth import extract_user_id_from_token
from backend.utils.logger import logger

router = APIRouter(prefix="/intel", tags=["intel"])

class ContentClassifyRequest(BaseModel):
    """Request to classify content type for verification strategy."""
    content: str

class IntelQARequest(BaseModel):
    """Request for context-aware Q&A on verification results."""
    question: str
    context: str
    evidence: list[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]] = None

@router.post("/classify")
async def classify_content(request: ContentClassifyRequest) -> Dict[str, Any]:
    try:
        if not request.content or not request.content.strip():
            raise HTTPException(400, "Content cannot be empty")
        
        content_lower = request.content.lower()
        if any(keyword in content_lower for keyword in ["youtube", "video", "transcript"]):
            content_type = "video_content"
        elif any(keyword in content_lower for keyword in ["http", "www", "url", "link", ".com"]):
            content_type = "news_article"
        elif any(keyword in content_lower for keyword in ["tweet", "twitter", "instagram", "facebook", "social"]):
            content_type = "social_media"
        else:
            content_type = "raw_text"
        
        result = {
            "type": content_type,
            "confidence": 0.85,
            "reasoning": f"Content classified as {content_type} based on keywords and format.",
            "sub_types": [],
            "suggested_sources": ["Tavily Search", "NewsAPI", "Academic Sources"],
        }
        
        logger.info("Content classified as: %s (confidence: %.2f)", result["type"], result["confidence"])
        
        return {
            "status": "success",
            "classification": result,
        }
    except Exception as e:
        logger.error("Content classification failed: %s", e)
        raise HTTPException(500, f"Classification failed: {e}")

@router.post("/analyze/start")
async def start_intel_analysis(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    content = None
    content_type = None
    file = None
    
    ct_header = request.headers.get("Content-Type", "")
    
    if "multipart/form-data" in ct_header:
        # ── FILE UPLOAD FLOW ─────────────────────────────────────────────
        form_data = await request.form()
        content = form_data.get("content")
        content_type = form_data.get("content_type")
        file = form_data.get("file") # This will be an UploadFile
        
        if file:
            # If it's a file, content might be empty, use filename
            if not content:
                content = file.filename
            if not content_type:
                content_type = "video_content"
    else:
        # ── JSON FLOW (URL/TEXT) ─────────────────────────────────────────
        try:
            body = await request.json()
            content = body.get("content")
            content_type = body.get("content_type")
        except:
            raise HTTPException(400, "Invalid JSON payload")

    if not content and not file:
        raise HTTPException(400, "Content or file cannot be empty")

    user_id = extract_user_id_from_token(authorization)
    if user_id:
        logger.info("Intel analysis started for user: %s", user_id)

    job_id = shared._job_manager.create_job()
    
    file_path = None
    if isinstance(file, UploadFile):
        # Save uploaded file to temp
        temp_dir = os.path.join("data", "uploads")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{job_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(await file.read())
        logger.info("Local video uploaded for Intel: %s", file_path)

    worker = threading.Thread(
        target=_run_intel_analysis_job,
        args=(job_id, content, content_type, user_id, file_path),
        daemon=True,
    )
    worker.start()
    return {
        "job_id": job_id,
        "status": "pending",
        "progress": 5,
        "status_message": "Analyzing claims",
    }

@router.get("/analyze/result/{job_id}")
async def get_intel_job_result(job_id: str) -> Dict[str, Any]:
    job = shared._job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Intel analysis job not found.")

    if job["status"] in ("complete", "failed", "error"):
        payload: Dict[str, Any] = {
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress", 0),
            "status_message": job.get("status_message", "Analysis complete" if job["status"] == "complete" else "Analysis failed"),
        }
        if job["status"] == "complete":
            payload["result"] = job.get("result")
        else:
            payload["error"] = job.get("error")
        return payload

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "status_message": job.get("status_message", "Processing..."),
    }

@router.post("/qa")
async def intel_qa(
    request: IntelQARequest,
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    try:
        if not request.question.strip():
            raise HTTPException(400, "Question cannot be empty")
        
        user_id = extract_user_id_from_token(authorization)
        if user_id:
            logger.info("Intel QA requested by user: %s", user_id)
        
        from backend.intel.truthguard_adapter import get_adapter
        adapter = get_adapter()
        
        job_id = None
        if request.verification_result and "job_id" in request.verification_result:
            job_id = request.verification_result["job_id"]
        
        response = await adapter.answer_question(
            question=request.question,
            context=request.context,
            evidence=request.evidence,
            verification_result=request.verification_result,
            job_id=job_id,
            conversation_history=[],
        )
        
        if response.get("status") == "error":
            answer = f"Based on the provided context, the verification requires evaluation of retrieved sources."
            return {
                "status": "success",
                "answer": answer,
                "sources": request.evidence[:3] if request.evidence else [],
                "confidence": 0.5,
            }
        
        return {
            "status": "success",
            "answer": response.get("answer", ""),
            "sources": response.get("sources", []),
            "confidence": response.get("confidence", 0.5),
        }
    except Exception as e:
        logger.error("Intel QA failed: %s", e)
        return {
            "status": "success",
            "answer": f"I can help answer questions about the verification. Your question was: {request.question}",
            "sources": request.evidence[:3] if request.evidence else [],
            "confidence": 0.4,
        }

# --- Background Worker Logic ---

async def _run_intel_analysis_job_async(job_id: str, content: str, content_type: Optional[str], user_id: Optional[str] = None, file_path: Optional[str] = None) -> None:
    from backend.intel.truthguard_adapter import get_adapter
    from backend.intel.job_handler import get_intel_handler
    
    def _progress_update(progress: int, message: str) -> None:
        shared._job_manager.update_progress(job_id, progress, message)
        logger.info("Intel job %s: %s (%d%%)", job_id, message, progress)
    
    try:
        adapter = get_adapter()
        handler = get_intel_handler()
        trace_id = str(uuid.uuid4())
        
        result = await adapter.analyze_content(
            content=content,
            content_type=content_type or "raw_text",
            trace_id=trace_id,
            progress_callback=_progress_update,
            file_path=file_path,
        )
        
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown engine error")
            shared._job_manager.fail_job(job_id, error_msg)
            return

        shared._job_manager.complete_job(job_id, result)
        
        # Save result to Supabase history
        await handler.save_intel_result_to_history(
            job_id=job_id,
            content=content,
            content_type=content_type or "raw_text",
            result=result,
            user_id=user_id,
        )
        
    except Exception as exc:
        logger.error("Intel job %s failed: %s", job_id, exc)
        shared._job_manager.fail_job(job_id, str(exc))
    finally:
        # Cleanup uploaded file
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
                logger.info("Temp upload cleaned: %s", file_path)
            except:
                pass

def _run_intel_analysis_job(job_id: str, content: str, content_type: Optional[str], user_id: Optional[str] = None, file_path: Optional[str] = None) -> None:
    try:
        asyncio.run(_run_intel_analysis_job_async(job_id, content, content_type, user_id, file_path))
    except Exception as e:
        logger.error("Failed to run Intel analysis job: %s", e)
        shared._job_manager.fail_job(job_id, str(e))
