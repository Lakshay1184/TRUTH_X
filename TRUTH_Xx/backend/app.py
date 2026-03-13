"""truth.x — FastAPI server wrapping the detection pipeline.

Start with:
    python -m uvicorn TRUTH_Xx.backend.app:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# ── Ensure truth.x root is importable ────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)            # TRUTH_Xx/
_ML_ROOT = os.path.dirname(_PROJECT_ROOT)                 # truth.x/
if _ML_ROOT not in sys.path:
    sys.path.insert(0, _ML_ROOT)

# ── Logger ──────────────────────────────────────────────────────────────
from utils.logger import logger

# ── Global state ────────────────────────────────────────────────────────
_pipeline: Any = None
_sb_url: str | None = None
_sb_key: str | None = None

# ── Async Job Queue ──────────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


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


# ── Metadata Extraction Helper ──────────────────────────────────────────
try:
    from main_pipeline import extract_video_metadata, _find_ffprobe
except ImportError:
    sys.path.append(_ML_ROOT)
    from main_pipeline import extract_video_metadata, _find_ffprobe

_FFPROBE_PATH = _find_ffprobe()


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
        # Cleanup temp file
        if video_path and os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except OSError:
                pass
        # Auto-cleanup job after 10 minutes
        def _cleanup():
            time.sleep(600)
            with _jobs_lock:
                _jobs.pop(job_id, None)
        threading.Thread(target=_cleanup, daemon=True).start()


# ── Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    global _pipeline
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
    load_dotenv(os.path.join(_ML_ROOT, ".env"))
    _init_supabase()

    try:
        from main_pipeline import DeepfakeDetectionPipeline
        _pipeline = DeepfakeDetectionPipeline()
        _pipeline.load_model("video")
        _pipeline.load_model("audio")
        _pipeline.load_model("text")
        logger.info("Pipeline initialized and models loaded")
    except ImportError as e:
        logger.error("Failed to import DeepfakeDetectionPipeline: %s", e)
    except Exception as e:
        logger.error("Failed to initialize pipeline: %s", e)

    yield
    _pipeline = None


# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(title="truth.x", version="1.1.0", lifespan=lifespan)

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
    document: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """
    Submit an analysis job. Returns immediately with a job_id.
    Poll /analyze/result/{job_id} for the result.
    """
    if _pipeline is None:
        raise HTTPException(500, "ML Pipeline not initialized")

    # ── Document upload → extract text ──────────────────────────────────
    if document is not None:
        try:
            from utils.document_reader import detect_format, read_document
            fmt = detect_format(document.filename or "")
            if fmt is None:
                raise HTTPException(400, "Unsupported document format.")
            temp_os_dir = os.path.join(_ML_ROOT, "data", "processed")
            os.makedirs(temp_os_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=fmt, dir=temp_os_dir) as tmp_doc:
                tmp_doc.write(await document.read())
                doc_path = tmp_doc.name
            try:
                doc_text = read_document(doc_path)
                if doc_text.strip():
                    query = doc_text
                else:
                    raise HTTPException(400, "Uploaded document is empty.")
            finally:
                try: os.unlink(doc_path)
                except OSError: pass
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Document reading error: {e}")

    if video is None and query is None:
        raise HTTPException(400, "Provide a video file, text query, or document.")

    # ── Save uploaded video ──────────────────────────────────────────────
    video_path = None
    original_filename = None
    if video is not None:
        original_filename = video.filename
        temp_os_dir = os.path.join(_ML_ROOT, "data", "processed")
        os.makedirs(temp_os_dir, exist_ok=True)
        suffix = os.path.splitext(video.filename or ".mp4")[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_os_dir) as tmp:
            tmp.write(await video.read())
            video_path = tmp.name

    # ── Create job and start background thread ───────────────────────────
    job_id = str(uuid.uuid4())[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending",
            "status_message": "Queued for analysis...",
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

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
    running = [j for j in _jobs.values() if j["status"] in ("pending", "running")]
    if running:
        return {"status": running[0].get("status_message", "Processing...")}
    return {"status": "Idle"}


@app.post("/extract-metadata")
async def extract_metadata(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    video_path = None
    try:
        suffix = os.path.splitext(file.filename or ".mp4")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            video_path = tmp.name
        meta = extract_video_metadata(video_path, _FFPROBE_PATH)
        tags = meta.get("tags", {})
        video_info = meta.get("video", {})
        file_info = meta.get("file_info", {})

        def get_val(data, key, default="Not available"):
            val = data.get(key)
            return val if val else default

        device_make = tags.get("manufacturer", "")
        device_model = tags.get("camera_device", "")
        device_info = f"{device_make} {device_model}".strip()

        return {
            "creation_time": get_val(tags, "creation_time"),
            "gps_coordinates": get_val(tags, "gps_location"),
            "device": device_info if device_info else "Not available",
            "format": get_val(file_info, "container_format"),
            "resolution": get_val(video_info, "resolution"),
            "duration": get_val(file_info, "duration_human"),
            "codec": get_val(video_info, "codec_short"),
            "file_size": f"{file_info.get('file_size_mb', 0)} MB",
        }
    except Exception as e:
        logger.error("Metadata extraction failed: %s", e)
        raise HTTPException(500, f"Metadata extraction failed: {e}")
    finally:
        if video_path and os.path.exists(video_path):
            try: os.unlink(video_path)
            except OSError: pass


@app.get("/health")
async def health() -> Dict[str, Any]:
    ready = _pipeline is not None
    return {
        "status": "ok" if ready else "error",
        "pipeline": "ready" if ready else "not_initialized",
        "ffprobe": "available" if ready and _pipeline.ffprobe_path else "fallback",
        "models": {k: (v is not None) for k, v in _pipeline.models.items()} if ready else {}
    }
