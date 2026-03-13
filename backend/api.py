"""truth.x — FastAPI server wrapping the detection pipeline.

Start with:
    python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations
import uuid as _uuid

import json
import os
import tempfile
import time
import asyncio
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# ── Logger ──────────────────────────────────────────────────────────────
try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("truth.x")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")

# ── Supabase & Caching ──────────────────────────────────────────────
_sb_url: str | None = None
_sb_key: str | None = None
_ffprobe_path: str | None = None

def _init_supabase():
    global _sb_url, _sb_key
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if url and key and "your-project" not in url:
        _sb_url = url.rstrip("/")
        _sb_key = key
        logger.info("Supabase REST configured  (%s)", _sb_url)
    else:
        logger.warning("SUPABASE_URL / SUPABASE_KEY not set — DB logging disabled.")

async def _log_to_supabase(table: str, data: dict):
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


# ── Pipeline Integration ──────────────────────────────────────────────
from main_pipeline import DeepfakeDetectionPipeline

_pipeline: DeepfakeDetectionPipeline | None = None

# ── Async Job Queue ──────────────────────────────────────────────────
# Jobs: { job_id: { status: "pending"|"running"|"done"|"error", result: ..., error: ... } }
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _run_analysis_job(job_id: str, video_path: str | None, query: str | None, original_filename: str | None):
    """Run in a background thread. Updates _jobs[job_id] when done."""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"

    try:
        if not _pipeline:
            raise RuntimeError("Pipeline not initialized.")

        def _update_status(msg: str):
            with _jobs_lock:
                _jobs[job_id]["status_message"] = msg
            logger.info("Job %s: %s", job_id, msg)

        report = _pipeline.process(
            video_path=video_path,
            query=query,
            status_callback=_update_status,
        )

        if original_filename and "metadata" in report:
            report["metadata"]["original_filename"] = original_filename

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = report

        logger.info("Job %s completed: %s", job_id, report.get("overall_label", "?"))

    except Exception as exc:
        import traceback
        error_detail = traceback.format_exc()
        logger.error("Job %s failed:\n%s", job_id, error_detail)
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)
    finally:
        # Clean up temp video file
        if video_path and os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except OSError:
                pass
        # Clean up job after 10 minutes
        def _cleanup():
            time.sleep(600)
            with _jobs_lock:
                _jobs.pop(job_id, None)
        threading.Thread(target=_cleanup, daemon=True).start()


# ── Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    global _pipeline
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    _init_supabase()

    # Pre-load the pipeline
    _pipeline = DeepfakeDetectionPipeline()
    logger.info("API initialized (models will lazy-load on first request) ✓")
    yield
    _pipeline = None


# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(title="truth.x", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(
    video: Optional[UploadFile] = File(None),
    query: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """
    Submit an analysis job. Returns immediately with a job_id.
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
        processed_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "processed"
        )
        os.makedirs(processed_dir, exist_ok=True)
        suffix = os.path.splitext(video.filename or ".mp4")[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=processed_dir) as tmp:
            tmp.write(await video.read())
            video_path = tmp.name

    # Create job
    job_id = str(_uuid.uuid4())[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending",
            "status_message": "Queued for analysis...",
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    # Launch background thread (not asyncio — ML models are CPU-bound)
    thread = threading.Thread(
        target=_run_analysis_job,
        args=(job_id, video_path, query, original_filename),
        daemon=True,
    )
    thread.start()

    logger.info("Submitted job %s (file=%s)", job_id, original_filename or "text")
    return {"job_id": job_id, "status": "pending"}


@app.get("/analyze/result/{job_id}")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    """Poll for the result of an analysis job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if job is None:
        raise HTTPException(404, "Job not found or expired.")

    status = job["status"]

    if status == "done":
        return {"status": "done", "result": job["result"]}
    elif status == "error":
        raise HTTPException(500, f"Analysis failed: {job['error']}")
    else:
        return {
            "status": status,
            "status_message": job.get("status_message", "Processing..."),
        }


@app.get("/analyze/status")
async def get_analyze_status() -> Dict[str, str]:
    """Returns the status of all active jobs (for backwards compat)."""
    running = [jid for jid, j in _jobs.items() if j["status"] in ("pending", "running")]
    if running:
        job = _jobs[running[0]]
        return {"status": job.get("status_message", "Processing...")}
    return {"status": "Idle"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "ffprobe": "available" if _ffprobe_path else "fallback (ffmpeg)"}


# ── Result Caching (for PWA Share Target) ───────────────────────────────
_recent_results: Dict[str, Any] = {}

@app.post("/cache-result")
async def cache_result(result: Dict[str, Any]) -> Dict[str, str]:
    """Cache an analysis result and return its ID for later retrieval."""
    result_id = str(_uuid.uuid4())[:8]
    _recent_results[result_id] = result
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
