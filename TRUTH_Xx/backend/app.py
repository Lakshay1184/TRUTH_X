"""truth.x — FastAPI server wrapping the detection pipeline.

Start with:
    python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# ── Ensure truth.x root is importable ────────────────────────────────────
# Backend lives in TRUTH_Xx/backend/app.py
# ML models live in truth.x/ (parent of TRUTH_Xx)
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)            # TRUTH_Xx/
_ML_ROOT = os.path.dirname(_PROJECT_ROOT)                 # truth.x/
if _ML_ROOT not in sys.path:
    sys.path.insert(0, _ML_ROOT)

# ── Logger ──────────────────────────────────────────────────────────────
from utils.logger import logger

# ── Paths & globals ────────────────────────────────────────────────────
_pipeline: Any = None

# ── Supabase (lightweight REST) ────────────────────────────────────────
_sb_url: str | None = None
_sb_key: str | None = None


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


# ── Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    global _pipeline
    # Load .env from both TRUTH_Xx root and truth.x root
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
    load_dotenv(os.path.join(_ML_ROOT, ".env"))
    _init_supabase()

    try:
        from main_pipeline import DeepfakeDetectionPipeline
        # We can pass pre-loaded models here if we wanted to manage them in app.py,
        # but the pipeline can handle loading them.
        _pipeline = DeepfakeDetectionPipeline()
        
        # Pre-load core models to avoid latency on first request
        _pipeline.load_model("video")
        _pipeline.load_model("audio")
        _pipeline.load_model("text")
        
        logger.info("Pipeline initialized and models loaded")
    except ImportError as e:
        logger.error("Failed to import DeepfakeDetectionPipeline: %s", e)
        # Fallback or exit? For now, we continue but requests will fail
    except Exception as e:
        logger.error("Failed to initialize pipeline: %s", e)

    yield
    # Cleanup if needed
    _pipeline = None


# ── Metadata Extraction Helper ──────────────────────────────────────────
# We import these here to avoid circular imports if main_pipeline imports app
try:
    from main_pipeline import extract_video_metadata, _find_ffprobe
except ImportError:
    # Fallback if running from a different context
    sys.path.append(_ML_ROOT)
    from main_pipeline import extract_video_metadata, _find_ffprobe

_FFPROBE_PATH = _find_ffprobe()



# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(title="truth.x", version="1.0.0", lifespan=lifespan)

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
    global _pipeline
    if _pipeline is None:
        raise HTTPException(500, "ML Pipeline not initialized")

    # ── Document upload → extract text ──────────────────────────────────
    if document is not None:
        try:
            from utils.document_reader import detect_format, read_document
            fmt = detect_format(document.filename or "")
            if fmt is None:
                raise HTTPException(400, "Unsupported document format. Upload .pdf, .docx, or .txt.")
            
            # Use temp dir from pipeline config if available, else default
            temp_dir = getattr(_pipeline, "config", {}).get("temp_dir", "data/processed")
            temp_os_dir = os.path.join(_ML_ROOT, temp_dir)
            os.makedirs(temp_os_dir, exist_ok=True)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=fmt, dir=temp_os_dir) as tmp_doc:
                tmp_doc.write(await document.read())
                doc_path = tmp_doc.name
            try:
                doc_text = read_document(doc_path)
                logger.info("Extracted %d chars from document '%s'", len(doc_text), document.filename)
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
            logger.error("Document reading failed: %s", e)
            raise HTTPException(500, f"Document reading error: {e}")

    if video is None and query is None:
        raise HTTPException(400, "Provide a video file, text query, or document.")

    # ── Video Processing Setup ──────────────────────────────────────────
    video_path = None
    if video is not None:
        try:
            temp_dir = getattr(_pipeline, "config", {}).get("temp_dir", "data/processed")
            temp_os_dir = os.path.join(_ML_ROOT, temp_dir)
            os.makedirs(temp_os_dir, exist_ok=True)
            suffix = os.path.splitext(video.filename or ".mp4")[1]

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_os_dir) as tmp:
                tmp.write(await video.read())
                video_path = tmp.name
        except Exception as e:
            logger.error("Video upload failed: %s", e)
            raise HTTPException(500, f"Video upload error: {e}")

    # ── Run Pipeline ────────────────────────────────────────────────────
    try:
        report = _pipeline.process(video_path=video_path, query=query)
        
        # Inject original filename if available (pipeline doesn't know about UploadFile)
        if video and "metadata" in report:
            report["metadata"]["original_filename"] = video.filename

        # Log to Supabase
        await _log_to_supabase("analysis_logs", {
            "file_name": video.filename if video else "text_query",
            "file_type": "video" if video else "text",
            "score": report.get("score"),
            "risk_level": report.get("risk_level"),
            "summary": report.get("summary"),
            "metadata": json.dumps(report.get("metadata")) if report.get("metadata") else None,
        })

        return report

    except Exception as e:
        logger.error("Pipeline processing error: %s", e)
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        # Cleanup video file
        if video_path and os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except OSError:
                pass


@app.post("/extract-metadata")
async def extract_metadata(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Extract metadata from a video file using ffprobe/ffmpeg.
    Returns creation_time, gps, device, format, resolution, etc.
    """
    video_path = None
    try:
        # Save uploaded file
        suffix = os.path.splitext(file.filename or ".mp4")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            video_path = tmp.name

        # Extract metadata
        meta = extract_video_metadata(video_path, _FFPROBE_PATH)
        
        # Parse into desired schema
        tags = meta.get("tags", {})
        video_info = meta.get("video", {})
        file_info = meta.get("file_info", {})

        # Helper to get value or "Not available"
        def get_val(data, key, default="Not available"):
            val = data.get(key)
            return val if val else default

        device_make = tags.get("manufacturer", "")
        device_model = tags.get("camera_device", "")
        device_info = f"{device_make} {device_model}".strip()

        response = {
            "creation_time": get_val(tags, "creation_time"),
            "gps_coordinates": get_val(tags, "gps_location"),
            "device": device_info if device_info else "Not available",
            "format": get_val(file_info, "container_format"),
            "resolution": get_val(video_info, "resolution"),
            "duration": get_val(file_info, "duration_human"),
            "codec": get_val(video_info, "codec_short"),
            "file_size": f"{file_info.get('file_size_mb', 0)} MB",
        }
        
        return response

    except Exception as e:
        logger.error("Metadata extraction failed: %s", e)
        raise HTTPException(500, f"Metadata extraction failed: {e}")
    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.unlink(video_path)
            except OSError:
                pass


@app.get("/health")
async def health() -> Dict[str, Any]:
    global _pipeline
    ready = _pipeline is not None
    return {
        "status": "ok" if ready else "error",
        "pipeline": "ready" if ready else "not_initialized",
        "ffprobe": "available" if ready and _pipeline.ffprobe_path else "fallback",
        "models": {k: (v is not None) for k, v in _pipeline.models.items()} if ready else {}
    }
