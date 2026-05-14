"""truth.x — FastAPI server wrapping the detection pipeline.

Start with:
    python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import os
import tempfile
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.utils.logger import logger
from backend.workers.job_manager import JobManager
from backend.pipelines.main_pipeline import DeepfakeDetectionPipeline

# ─── Supabase Logging ───────────────────────────────────────────────────

_sb_url: Optional[str] = None
_sb_key: Optional[str] = None


def _init_supabase() -> None:
    global _sb_url, _sb_key
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if url and key and "your-project" not in url:
        _sb_url = url.rstrip("/")
        _sb_key = key
        logger.info("Supabase REST configured (%s)", _sb_url)
    else:
        logger.warning("SUPABASE_URL / SUPABASE_KEY not set — DB logging disabled.")


async def _log_to_supabase(table: str, data: dict) -> None:
    if not _sb_url or not _sb_key:
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_sb_url}/rest/v1/{table}",
                json=data,
                headers={
                    "apikey": _sb_key,
                    "Authorization": f"Bearer {_sb_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                timeout=10,
            )
            if resp.status_code < 300:
                logger.info("Logged to Supabase → %s", table)
            else:
                logger.error("Supabase insert failed (%s): %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("Supabase request error: %s", e)


# ─── Pipeline & Job Manager ─────────────────────────────────────────────

_pipeline: Optional[DeepfakeDetectionPipeline] = None
_job_manager = JobManager()


def _run_analysis_job(
    job_id: str,
    video_path: Optional[str],
    query: Optional[str],
    original_filename: Optional[str],
) -> None:
    """Run in a background thread. Updates job status when done."""
    _job_manager.update_progress(job_id, 5, "processing")

    try:
        if not _pipeline:
            raise RuntimeError("Pipeline not initialized.")

        def _update_status(msg: str) -> None:
            _job_manager.update_progress(job_id, -1, msg)
            logger.info("Job %s: %s", job_id, msg)

        report = _pipeline.process(
            video_path=video_path,
            query=query,
            status_callback=_update_status,
        )

        if original_filename and "metadata" in report:
            report["metadata"]["original_filename"] = original_filename

        _job_manager.complete_job(job_id, report)
        
        # Log to Supabase
        try:
            import asyncio
            # Ensure safe extraction of values that might be None
            overall_label = report.get("overall_label", "unknown")
            if overall_label is None:
                overall_label = "unknown"
                
            combined_fake_prob = report.get("combined_fake_probability", 0.0)
            if combined_fake_prob is None:
                combined_fake_prob = 0.0
                
            combined_conf = report.get("combined_confidence", 0.0)
            if combined_conf is None:
                combined_conf = 0.0
                
            log_data = {
                "job_id": job_id,
                "filename": str(original_filename) if original_filename else "text_query",
                "overall_label": str(overall_label),
                "combined_fake_probability": float(combined_fake_prob),
                "combined_confidence": float(combined_conf),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            # Try to get existing event loop, otherwise create one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(_log_to_supabase("analysis_results", log_data))
        except Exception as e:
            logger.error("Failed to log to Supabase: %s", e)

    except Exception as exc:
        import traceback
        logger.error("Job %s failed:\n%s", job_id, traceback.format_exc())
        _job_manager.fail_job(job_id, str(exc))

    finally:
        # Clean up temp video file
        if video_path and os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except OSError:
                pass


# ─── Lifespan ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    global _pipeline
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    _init_supabase()

    # Pre-initialize pipeline (models lazy-load on first request)
    _pipeline = DeepfakeDetectionPipeline()
    logger.info("API initialized (models will lazy-load on first request) ✓")
    yield
    _pipeline = None


# ─── App ─────────────────────────────────────────────────────────────────

app = FastAPI(title="truth.x", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routes ──────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(
    video: Optional[UploadFile] = File(None),
    query: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Submit an analysis job. Returns immediately with a job_id.
    Poll /analyze/result/{job_id} for the result.
    """
    if video is None and query is None:
        raise HTTPException(400, "Provide video or text.")

    if not _pipeline:
        raise HTTPException(500, "Pipeline not initialized.")

    # Save uploaded video to temp file
    video_path = None
    original_filename = None
    if video is not None:
        original_filename = video.filename
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        processed_dir = os.path.join(project_root, "data", "processed")
        os.makedirs(processed_dir, exist_ok=True)
        suffix = os.path.splitext(video.filename or ".mp4")[1] or ".mp4"
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix, dir=processed_dir,
        ) as tmp:
            tmp.write(await video.read())
            video_path = tmp.name

    # Create job
    job_id = _job_manager.create_job()

    # Launch background thread (ML models are CPU/GPU-bound, not async)
    thread = threading.Thread(
        target=_run_analysis_job,
        args=(job_id, video_path, query, original_filename),
        daemon=True,
    )
    thread.start()

    logger.info("Submitted job %s (file=%s)", job_id, original_filename or "text-only")
    return {"job_id": job_id, "status": "pending"}


@app.get("/analyze/result/{job_id}")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    """Poll for the result of an analysis job."""
    job = _job_manager.get_job(job_id)

    if job is None:
        raise HTTPException(404, "Job not found or expired.")

    status = job["status"]

    if status == "complete":
        return {"status": "done", "result": job["result"]}
    elif status == "error":
        raise HTTPException(500, f"Analysis failed: {job['error']}")
    else:
        return {
            "status": status,
            "status_message": job.get("status", "Processing..."),
            "progress": job.get("progress", 0),
        }


@app.get("/analyze/status")
async def get_analyze_status() -> Dict[str, Any]:
    """Returns overview of active jobs (backwards-compatible)."""
    return {
        "status": "Idle" if _job_manager.active_count == 0 else "Processing...",
        "active_jobs": _job_manager.active_count,
        "total_jobs": _job_manager.total_count,
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


# ─── Result Caching (for PWA Share Target) ───────────────────────────────

_recent_results: Dict[str, Any] = {}


@app.post("/cache-result")
async def cache_result(result: Dict[str, Any]) -> Dict[str, str]:
    """Cache an analysis result and return its ID for later retrieval."""
    import uuid
    result_id = str(uuid.uuid4())[:8]
    _recent_results[result_id] = result

    # Evict oldest if over limit
    if len(_recent_results) > 50:
        oldest_key = next(iter(_recent_results))
        del _recent_results[oldest_key]

    logger.info("Cached result %s (total cached: %d)", result_id, len(_recent_results))
    return {"id": result_id}


@app.get("/result/{result_id}")
async def get_result(result_id: str) -> Dict[str, Any]:
    """Retrieve a cached analysis result by ID."""
    if result_id not in _recent_results:
        raise HTTPException(404, "Result not found or expired.")
    return _recent_results[result_id]


# ─── Social Media & Graph Intelligence ───────────────────────────────────

class SocialScanRequest(BaseModel):
    url: str

@app.post("/social/scan")
async def scan_social_media(request: SocialScanRequest) -> Dict[str, Any]:
    """Scrapes a social media URL and extracts content."""
    from backend.workers.social_scanner import scan_social_url
    
    # Run synchronously for simplicity unless Celery worker is active
    try:
        # In a real environment, you'd use scan_social_url.delay(request.url)
        # Here we run it directly so we don't strictly require Redis running locally
        result = scan_social_url(request.url)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error("Social scan failed: %s", e)
        raise HTTPException(500, f"Social scan failed: {e}")

@app.get("/social/graph/{content_id}")
async def get_propagation_graph(content_id: str, url: str) -> Dict[str, Any]:
    """Build and return the misinformation propagation graph for a given content."""
    from backend.workers.social_scanner import build_propagation_graph
    
    try:
        graph = build_propagation_graph(url, content_id)
        return {"status": "success", "graph": graph}
    except Exception as e:
        logger.error("Graph generation failed: %s", e)
        raise HTTPException(500, f"Graph generation failed: {e}")

# ─── Community Verification Layer ────────────────────────────────────────

class CommunityVoteRequest(BaseModel):
    content_id: str
    vote: str  # 'fake' or 'real'
    evidence_url: Optional[str] = None
    user_id: str

@app.post("/community/vote")
async def submit_community_vote(request: CommunityVoteRequest) -> Dict[str, Any]:
    """Submit a community vote on content authenticity.
    
    In a full production environment, this applies a reputation-weighted
    consensus algorithm to update the global credibility score.
    """
    try:
        # Mocking the Supabase write since we might not have the table yet
        vote_data = {
            "content_id": request.content_id,
            "user_id": request.user_id,
            "vote": request.vote,
            "evidence_url": request.evidence_url,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Async fire-and-forget log
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.create_task(_log_to_supabase("community_votes", vote_data))
        
        return {
            "status": "success",
            "message": "Vote submitted successfully",
            "vote_recorded": vote_data
        }
    except Exception as e:
        logger.error("Vote submission failed: %s", e)
        raise HTTPException(500, f"Vote submission failed: {e}")
