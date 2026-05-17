"""
Core Analysis routes for Truth_X.
"""

import os
import tempfile
import threading
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Header
from . import shared
from backend.utils.logger import logger
from backend.utils.document_reader import detect_format, read_document
from datetime import datetime, timezone

from backend.utils.auth import extract_user_id_from_token

router = APIRouter(tags=["analyze"])

@router.post("/analyze")
async def analyze(
    video: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    text_file: Optional[UploadFile] = File(None),
    query: Optional[str] = Form(None),
    verify_news: bool = Form(False),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    if video is None and audio is None and image is None and text_file is None and query is None:
        raise HTTPException(400, "Provide a media file, text file, or query text.")

    user_id = extract_user_id_from_token(authorization)
    if user_id:
        logger.info("Analysis started for user: %s", user_id)

    pipeline = shared.get_pipeline()

    supplied_files = {
        "video": video,
        "audio": audio,
        "image": image,
        "text": text_file,
    }
    file_modalities = [name for name, upload in supplied_files.items() if upload is not None]
    if len(file_modalities) > 1:
        raise HTTPException(400, "Provide only one primary input file per analysis request.")

    modality: shared.AnalysisModality
    if video is not None:
        modality = "video"
    elif audio is not None:
        modality = "audio"
    elif image is not None:
        modality = "image"
    else:
        modality = "text"

    # Save uploaded media to temp files
    video_path = None
    audio_path = None
    image_path = None
    text_path = None
    original_filename = None
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    processed_dir = os.path.join(project_root, "data", "processed")
    os.makedirs(processed_dir, exist_ok=True)

    if video is not None:
        original_filename = video.filename
        suffix = os.path.splitext(video.filename or ".mp4")[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=processed_dir) as tmp:
            tmp.write(await video.read())
            video_path = tmp.name

    if audio is not None:
        original_filename = original_filename or audio.filename
        suffix = os.path.splitext(audio.filename or ".wav")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=processed_dir) as tmp:
            tmp.write(await audio.read())
            audio_path = tmp.name

    if image is not None:
        original_filename = original_filename or image.filename
        suffix = os.path.splitext(image.filename or ".jpg")[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=processed_dir) as tmp:
            tmp.write(await image.read())
            image_path = tmp.name

    if text_file is not None:
        original_filename = original_filename or text_file.filename
        ext = detect_format(text_file.filename or "")
        if ext is None:
            raise HTTPException(400, "Unsupported text file format. Use .txt, .pdf, or .docx.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=processed_dir) as tmp:
            tmp.write(await text_file.read())
            text_path = tmp.name

        if not query:
            try:
                query = read_document(text_path)
            except Exception as exc:
                raise HTTPException(400, f"Failed to read text file: {exc}")
        if text_path and os.path.exists(text_path):
            try:
                os.unlink(text_path)
            except OSError:
                pass

    if modality != "text":
        query = None
        verify_news = False

    if modality == "text" and (not query or not query.strip()):
        raise HTTPException(400, "Text analysis requires non-empty text or a supported text file.")

    job_id = shared._job_manager.create_job()

    thread = threading.Thread(
        target=_run_analysis_job,
        args=(job_id, modality, video_path, audio_path, image_path, query, verify_news, original_filename, user_id),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "pending", "modality": modality}

@router.get("/analyze/result/{job_id}")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    job = shared._job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found or expired.")

    status = job["status"]
    if status == "complete":
        return {"status": "done", "result": job["result"]}
    elif status in ("error", "failed", "cancelled"):
        return {
            "status": "failed" if status in ("error", "failed") else "cancelled",
            "error": job.get("error") or "Analysis did not complete.",
            "status_message": job.get("status_message", "Analysis failed"),
            "progress": job.get("progress", 0),
        }
    else:
        return {
            "status": "running" if status == "processing" else status,
            "status_message": job.get("status_message", "Processing..."),
            "progress": job.get("progress", 0),
        }

@router.get("/analyze/status")
async def get_analyze_status() -> Dict[str, Any]:
    return {
        "status": "Idle" if shared._job_manager.active_count == 0 else "Processing...",
        "active_jobs": shared._job_manager.active_count,
        "total_jobs": shared._job_manager.total_count,
    }

def _run_analysis_job(
    job_id: str,
    modality: shared.AnalysisModality,
    video_path: Optional[str],
    audio_path: Optional[str],
    image_path: Optional[str],
    query: Optional[str],
    verify_news: bool,
    original_filename: Optional[str],
    user_id: Optional[str] = None,
) -> None:
    shared._job_manager.update_progress(job_id, 5, "processing")
    
    try:
        pipeline = shared.get_pipeline()

        def _progress_from_status(msg: str) -> int:
            text = msg.lower()
            if "initializing" in text: return 5
            if "complete" in text: return 100
            return 50 # Simplified mapping

        def _update_status(msg: str) -> None:
            shared._job_manager.update_progress(job_id, _progress_from_status(msg), msg)

        report = pipeline.process(
            modality=modality,
            video_path=video_path,
            audio_path=audio_path,
            image_path=image_path,
            query=query,
            verify_news=verify_news,
            status_callback=_update_status,
        )

        if original_filename and "metadata" in report:
            report["metadata"]["original_filename"] = original_filename

        shared._job_manager.complete_job(job_id, report)
        
        # Log to Supabase logic preserved...
        try:
            import asyncio
            overall_label = report.get("overall_label", "unknown") or "unknown"
            combined_fake_prob = report.get("combined_fake_probability", 0.0) or 0.0
            combined_conf = report.get("combined_confidence", 0.0) or 0.0
            score = report.get("score", 50)
            risk_level = report.get("risk_level", "MEDIUM")
            
            # Common metadata for all history
            metadata = {
                "job_id": job_id,
                "content_type": modality,
                "confidence": float(combined_conf),
                "original_filename": original_filename,
                "overall_label": str(overall_label),
                "risk_level": str(risk_level),
                "evidence_count": len(report.get("related_articles", [])),
                "source_count": len(report.get("related_articles", [])),
            }

            if verify_news:
                task_type = "URL Verification" if modality == "text" and query and query.startswith("http") else "Fake News Check"
                verification_data = {
                    "job_id": job_id,
                    "user_id": user_id,
                    "task_type": task_type,
                    "input_summary": str(query)[:200] if query else "screenshot",
                    "verdict_label": report.get("verdict", "Unverified"),
                    "verdict_score": int(score),
                    "metadata": metadata,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                asyncio.run(shared._log_to_supabase("analysis_history", verification_data))
            else:
                # Map modality to valid task_type enum
                task_type_map = {
                    "video": "Video Analysis",
                    "image": "Image Analysis",
                    "text": "Text Analysis",
                    "audio": "AI Detection" 
                }
                task_type = task_type_map.get(modality, "AI Detection")
                
                detection_data = {
                    "job_id": job_id,
                    "user_id": user_id,
                    "task_type": task_type,
                    "input_summary": str(original_filename) if original_filename else str(query)[:200] if query else "Media Upload",
                    "verdict_label": str(overall_label),
                    "verdict_score": int(score),
                    "evidence_count": 0,
                    "source_count": 0,
                    "metadata": metadata,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                asyncio.run(shared._log_to_supabase("analysis_history", detection_data))
        except Exception as e:
            logger.error("Failed to log to Supabase: %s", e)

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc)
        shared._job_manager.fail_job(job_id, str(exc))
    finally:
        for tmp_path in (video_path, audio_path, image_path):
            if tmp_path and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except: pass
