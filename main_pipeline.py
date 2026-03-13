"""truth.x  -  Deepfake & Misinformation Detection Pipeline

Usage:
    python main_pipeline.py --video path/to/video.mp4
    python main_pipeline.py --query "Some suspicious claim"
    python main_pipeline.py --text-file path/to/document.pdf
    python main_pipeline.py --video clip.mp4 --query "Is this real?"
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import json
import math
import re
import subprocess
import gc
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import torch
import yaml
from dotenv import load_dotenv

from utils.logger import logger
from utils.postprocessing import aggregate_results

# ------------------------------------------------------------------
# Constants & Config
# ------------------------------------------------------------------

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.yaml")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {"device": "cpu", "video": {"frame_sample_rate": 1}, "temp_dir": "temp"}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ------------------------------------------------------------------
# Helpers (moved from app.py)
# ------------------------------------------------------------------

def _find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"

def _find_ffprobe() -> str | None:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        probe = ffmpeg_exe.replace("ffmpeg.exe", "ffprobe.exe") if "ffmpeg.exe" in ffmpeg_exe else ffmpeg_exe.replace("ffmpeg", "ffprobe")
        if os.path.isfile(probe):
            subprocess.run([probe, "-version"], capture_output=True, check=True)
            return probe
    except Exception:
        pass
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        return "ffprobe"
    except Exception:
        pass
    return None

def _parse_fps(fps_str: str) -> float:
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            return round(int(num) / int(den), 2)
        return round(float(fps_str), 2)
    except (ValueError, ZeroDivisionError):
        return 0.0

def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = round(seconds % 60, 1)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def _extract_metadata_ffmpeg_fallback(video_path: str) -> dict:
    if not os.path.exists(video_path):
        return {}
    ffmpeg_exe = _find_ffmpeg()
    try:
        res = subprocess.run([ffmpeg_exe, "-i", video_path, "-hide_banner"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        content = res.stderr
        duration_sec = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", content)
        if dur_match:
            h, m, s = map(float, dur_match.groups())
            duration_sec = h*3600 + m*60 + s
        video = {}
        vid_match = re.search(r"Stream.*Video:\s*(?P<codec>[^,]+),.*?(?P<width>\d+)x(?P<height>\d+)", content)
        if vid_match:
            video["codec"] = vid_match.group("codec").strip()
            video["width"] = int(vid_match.group("width"))
            video["height"] = int(vid_match.group("height"))
            video["resolution"] = f"{video['width']}×{video['height']}"
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", content)
        if fps_match:
            video["fps"] = float(fps_match.group(1))
        bit_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", content)
        total_bitrate = int(bit_match.group(1)) if bit_match else 0
        audio = {}
        aud_match = re.search(r"Stream.*Audio:\s*(?P<codec>[^,]+),\s*(?P<rate>\d+)\s*Hz", content)
        if aud_match:
            audio["codec"] = aud_match.group("codec").strip()
            audio["sample_rate_hz"] = int(aud_match.group("rate"))
        tags = {}
        for key in ["creation_time", "encoder", "location", "major_brand", "minor_version", "compatible_brands", "make", "model", "date", "title", "comment", "artist", "album"]:
            m = re.search(rf"\b{key}\s*:\s*(.+)", content, re.IGNORECASE)
            if m:
                tags[key.lower()] = m.group(1).strip()
        if "location" in tags:
            tags["gps_location"] = tags.pop("location")
        if "model" in tags:
            tags["camera_device"] = tags.pop("model")
        nb_streams = len(re.findall(r"Stream #\d+:\d+", content))
        return {
            "file_info": {
                "duration_seconds": round(duration_sec, 2),
                "duration_human": _format_duration(duration_sec),
                "total_bitrate_kbps": total_bitrate,
                "file_size_mb": round(os.path.getsize(video_path)/(1024*1024), 2),
                "nb_streams": nb_streams,
                "container_format": os.path.splitext(video_path)[1].lstrip(".").upper()
            },
            "video": video,
            "audio": audio,
            "tags": tags,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Fallback extraction failed: {e}")
        return {}

def extract_video_metadata(video_path: str, ffprobe_path: str | None = None) -> dict:
    if ffprobe_path:
        cmd = [
            ffprobe_path, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
            if result.returncode == 0:
                probe = json.loads(result.stdout)
                streams = probe.get("streams", [])
                fmt = probe.get("format", {})
                fmt_tags = fmt.get("tags", {})
                video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
                audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
                subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
                file_size_bytes = int(fmt.get("size", 0))
                duration = float(fmt.get("duration", 0))
                container = fmt.get("format_long_name", fmt.get("format_name", "unknown"))
                total_bitrate = int(fmt.get("bit_rate", 0))
                metadata: Dict[str, Any] = {
                    "file_info": {
                        "file_name": os.path.basename(video_path),
                        "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
                        "file_size_bytes": file_size_bytes,
                        "container_format": container,
                        "duration_seconds": round(duration, 2),
                        "duration_human": _format_duration(duration),
                        "total_bitrate_kbps": round(total_bitrate / 1000) if total_bitrate else 0,
                        "nb_streams": int(fmt.get("nb_streams", 0)),
                    },
                }
                if video_stream:
                    vtags = video_stream.get("tags", {})
                    width = int(video_stream.get("width", 0))
                    height = int(video_stream.get("height", 0))
                    fps = _parse_fps(video_stream.get("r_frame_rate", "0/1"))
                    avg_fps = _parse_fps(video_stream.get("avg_frame_rate", "0/1"))
                    vbitrate = int(video_stream.get("bit_rate", 0) or 0)
                    metadata["video"] = {
                        "codec": video_stream.get("codec_long_name", video_stream.get("codec_name", "unknown")),
                        "codec_short": video_stream.get("codec_name", "unknown"),
                        "profile": video_stream.get("profile", "unknown"),
                        "level": video_stream.get("level", ""),
                        "width": width, "height": height,
                        "resolution": f"{width}×{height}" if width and height else "N/A",
                        "display_aspect_ratio": video_stream.get("display_aspect_ratio", "N/A"),
                        "fps": fps, "avg_fps": avg_fps,
                        "bitrate_kbps": round(vbitrate / 1000) if vbitrate else "N/A",
                        "pixel_format": video_stream.get("pix_fmt", "unknown"),
                        "bit_depth": video_stream.get("bits_per_raw_sample", "8"),
                        "color_space": video_stream.get("color_space", "unknown"),
                        "total_frames": int(video_stream.get("nb_frames", 0) or 0),
                        "rotation": vtags.get("rotate", "0"),
                    }
                if audio_stream:
                    abitrate = int(audio_stream.get("bit_rate", 0) or 0)
                    metadata["audio"] = {
                        "codec": audio_stream.get("codec_long_name", audio_stream.get("codec_name", "unknown")),
                        "codec_short": audio_stream.get("codec_name", "unknown"),
                        "profile": audio_stream.get("profile", ""),
                        "sample_rate_hz": int(audio_stream.get("sample_rate", 0) or 0),
                        "channels": audio_stream.get("channels", 0),
                        "channel_layout": audio_stream.get("channel_layout", "unknown"),
                        "bitrate_kbps": round(abitrate / 1000) if abitrate else "N/A",
                        "language": audio_stream.get("tags", {}).get("language", "unknown"),
                    }
                all_tags = {**fmt_tags}
                if video_stream: all_tags.update(video_stream.get("tags", {}))
                tag_info: Dict[str, Any] = {}
                mapping = {
                    "creation_time": ["creation_time", "date", "DATE"],
                    "encoder": ["encoder", "Encoder", "writing_library", "handler_name"],
                    "camera_device": ["com.apple.quicktime.model", "model", "camera", "com.android.model"],
                    "manufacturer": ["com.apple.quicktime.make", "make", "manufacturer"],
                    "gps_location": ["com.apple.quicktime.location.ISO6709", "location"],
                    "title": ["title"],
                    "comment": ["comment"],
                    "major_brand": ["major_brand"],
                    "software_version": ["com.apple.quicktime.software", "software"]
                }
                for out_key, candidates in mapping.items():
                    val = next((all_tags.get(c) for c in candidates if all_tags.get(c)), None)
                    if val: tag_info[out_key] = val
                if tag_info: metadata["tags"] = tag_info
                if subtitle_streams: metadata["subtitle_streams"] = len(subtitle_streams)
                metadata["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                return metadata
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.warning(f"FFprobe extraction error: {e}")

    logger.info("Using FFmpeg fallback for metadata extraction")
    return _extract_metadata_ffmpeg_fallback(video_path)

def _generate_drift_data(duration: float, deepfake_result: dict | None) -> list[dict]:
    """Generate per-segment drift data from actual model output if available."""
    if duration <= 0:
        return []

    num_segments = min(20, max(8, int(duration / 5)))
    segment_duration = duration / num_segments
    drift_points = []

    # Use real per-frame data if we have it
    per_frame = deepfake_result.get("per_frame", []) if deepfake_result else []
    if per_frame:
        frames_per_seg = max(1, len(per_frame) // num_segments)
        for i in range(num_segments):
            start_idx = i * frames_per_seg
            end_idx = min(start_idx + frames_per_seg, len(per_frame))
            seg_frames = per_frame[start_idx:end_idx]
            if seg_frames:
                # Average "Real" probability across frames in this segment
                avg_real = sum(f.get("Real", f.get("real", 0.5)) for f in seg_frames) / len(seg_frames)
                val = max(0, min(100, int(avg_real * 100)))
            else:
                val = 50
            t_start = i * segment_duration
            drift_points.append({"t": f"{int(t_start)}s", "v": val, "type": "model"})
    else:
        # Fallback: synthetic drift based on overall score
        base_score = 50
        if deepfake_result:
            avg = deepfake_result.get("average", {})
            base_score = int(avg.get("Real", avg.get("real", 0.5)) * 100)

        import random
        for i in range(num_segments):
            t_start = i * segment_duration
            param = (i / num_segments) * math.pi * 2
            variation = math.sin(param) * 5 + random.randint(-3, 3)
            val = max(0, min(100, int(base_score + variation)))
            drift_points.append({"t": f"{int(t_start)}s", "v": val, "type": "estimated"})

    return drift_points

def _compute_risk_score(metadata: dict, video_result: dict | None = None, text_result: dict | None = None) -> dict:
    """Analyze metadata + ML results for suspicious indicators."""
    flags = []
    ml_driven = False  # True if an ML model provided a strong signal

    video = metadata.get("video", {})
    tags = metadata.get("tags", {})
    file_info = metadata.get("file_info", {})

    # ── Collect metadata penalties (applied to metadata-only base) ──
    meta_penalty = 0

    encoder = str(tags.get("encoder", "")).lower()
    if any(x in encoder for x in ["lavf", "handbrake", "obs", "x264", "x265"]):
        flags.append({"label": "Re-encoded", "detail": f"Encoder: {tags.get('encoder', 'unknown')}", "severity": "medium"})
        meta_penalty += 10

    codec = str(video.get("codec_short", "")).lower()
    if codec and codec not in ("h264", "hevc", "h265", "vp9", "vp8", "av1", "mpeg4"):
        flags.append({"label": "Unusual codec", "detail": video.get("codec", codec), "severity": "low"})
        meta_penalty += 5

    for field_val in [encoder, str(tags.get("comment", "")).lower()]:
        for sus in ["deepfake", "faceswap", "synthesia", "d-id", "heygen"]:
            if sus in field_val:
                flags.append({"label": "AI Tool Detected", "detail": f"Metadata: '{sus}'", "severity": "critical"})
                meta_penalty += 40
                break

    if not tags:
        flags.append({"label": "Stripped metadata", "detail": "No tags found", "severity": "medium"})
        meta_penalty += 10

    if video.get("width", 0) >= 1920 and 0 < file_info.get("total_bitrate_kbps", 0) < 2000:
        flags.append({"label": "Low bitrate", "detail": "Possible re-encode", "severity": "medium"})
        meta_penalty += 10

    # ── ML model results — these DRIVE the score when present ──
    ml_score = None  # Will be set if an ML model has a strong opinion

    if video_result and video_result.get("label"):
        label = video_result["label"].lower()
        confidence = video_result.get("confidence", 0)
        if label == "fake":
            # Authenticity = 1 - fake_confidence (e.g., 95% fake → 5% authentic)
            ml_score = int((1.0 - confidence) * 100)
            ml_driven = True
            flags.append({
                "label": "Deepfake Detected",
                "detail": f"Video frames: {confidence:.0%} fake confidence",
                "severity": "critical" if confidence > 0.75 else "high"
            })
        elif label == "real" and confidence > 0.5:
            # High real confidence boosts authenticity
            ml_score = int(confidence * 100)
            ml_driven = True

    if text_result and text_result.get("label"):
        label = text_result["label"].lower()
        ai_prob = text_result.get("ai_probability", 0)
        if "ai" in label and ai_prob > 0.5:
            text_ml_score = int((1.0 - ai_prob) * 100)
            flags.append({
                "label": "AI-Generated Text",
                "detail": f"Text: {ai_prob:.0%} AI-generated probability",
                "severity": "critical" if ai_prob > 0.75 else "high"
            })
            # Combine with video ML score if both present, otherwise use text alone
            if ml_score is not None:
                ml_score = min(ml_score, text_ml_score)  # Use the worse signal
            else:
                ml_score = text_ml_score
            ml_driven = True

    # ── Compute final score ──
    if ml_driven and ml_score is not None:
        # ML results are primary; metadata penalties are secondary adjustments
        score = max(0, ml_score - (meta_penalty // 2))
    else:
        # No ML signal — score is metadata-only
        score = max(0, 100 - meta_penalty)

    score = max(0, min(100, score))
    risk_level = "low" if score >= 70 else "medium" if score >= 40 else "high"

    return {
        "authenticity_score": score,
        "risk_level": risk_level,
        "flags": flags,
        "flag_count": len(flags),
    }

# ------------------------------------------------------------------
# Pipeline Class
# ------------------------------------------------------------------

class DeepfakeDetectionPipeline:
    def __init__(self, models: Dict[str, Any] | None = None):
        """
        Initialize the pipeline.
        If `models` is provided, reuse them (e.g. from app.py lifespan).
        Otherwise, models will be loaded lazily or on demand.
        """
        self.config = load_config()
        self.models = models if models else {}
        self.ffprobe_path = _find_ffprobe()
        if self.ffprobe_path:
            logger.info("FFprobe found: %s", self.ffprobe_path)
        else:
            logger.warning("FFprobe NOT found — using FFmpeg fallback")

    def load_model(self, model_name: str):
        """Lazily load a model if it's not already in self.models"""
        if model_name in self.models and self.models[model_name] is not None:
            return

        try:
            if model_name == "video":
                logger.info("Loading Video Model...")
                from models.video.deepfake_detector import VideoDeepfakeDetector
                self.models["video"] = VideoDeepfakeDetector()
            elif model_name == "audio":
                logger.info("Loading Audio Model...")
                from models.audio.synthetic_voice_detector import SyntheticVoiceDetector
                self.models["audio"] = SyntheticVoiceDetector()
            elif model_name == "text":
                logger.info("Loading Text Model...")
                from models.text.ai_text_detector import TextAIDetector
                self.models["text"] = TextAIDetector()
            elif model_name == "faiss":
                logger.info("Loading FAISS Service...")
                from services.faiss_service import FAISSSearch
                self.models["faiss"] = FAISSSearch()
        except Exception as e:
            logger.error("Failed to load model %s: %s", model_name, e)
            self.models[model_name] = None

    def process(self, video_path: str | None = None, query: str | None = None, status_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Main entry point for processing.
        Returns a dictionary containing the full analysis report.
        """
        def _set_status(msg: str):
            if status_callback:
                status_callback(msg)
            logger.info(msg)

        t_start_total = time.perf_counter()
        _set_status("Initializing analysis...")
        metadata = {}
        video_result = None
        audio_result = None
        text_result = None
        fact_check = []
        drift_data = []
        ai_models = []

        # ── Video Processing ────────────────────────────────────────────────
        if video_path and os.path.exists(video_path):
            try:
                # 1. Extract metadata
                _set_status("Extracting metadata fingerprints...")
                t0 = time.perf_counter()
                metadata = extract_video_metadata(video_path, self.ffprobe_path)
                logger.info("Metadata extraction %.2fs", time.perf_counter() - t0)

                # 2. Video Deepfake Detection
                _set_status("Running deepfake detection model...")
                self.load_model("video")
                if self.models.get("video"):
                    t_vid = time.perf_counter()
                    try:
                        from utils.preprocessing import extract_frames, detect_and_crop_faces
                        frame_rate = self.config.get("video", {}).get("frame_sample_rate", 1)
                        frames = extract_frames(video_path, target_fps=frame_rate)
                        
                        if frames and len(frames) > 0:
                            frames = detect_and_crop_faces(frames)
                            video_result = self.models["video"].predict(frames)
                            elapsed_vid = time.perf_counter() - t_vid
                            logger.info("Deepfake detection: %s (%.2fs)", video_result.get("label"), elapsed_vid)
                            
                            det_label = video_result.get("label", "unknown")
                            det_conf = video_result.get("confidence", 0)
                            ai_models.append({
                                "name": "DeepfakeDetector (ViT)",
                                "score": int(det_conf * 100),
                                "label": det_label.capitalize(),
                            })
                        else:
                            logger.error("No frames extracted from video - skipping vision model.")
                    except Exception as e:
                        logger.error("Deepfake detection failed: %s", e)

                # 3. Audio Detection
                _set_status("Analyzing audio frequency anomalies...")
                self.load_model("audio")
                if self.models.get("audio"):
                    try:
                        from utils.preprocessing import extract_audio
                        temp_dir = self.config.get("temp_dir", "data/processed")
                        os.makedirs(temp_dir, exist_ok=True)
                        audio_path = extract_audio(video_path, temp_dir)
                        if os.path.exists(audio_path):
                            t0 = time.perf_counter()
                            audio_result = self.models["audio"].predict(audio_path)
                            logger.info("Audio detection: %.2fs", time.perf_counter() - t0)
                            try: os.unlink(audio_path)
                            except OSError: pass
                    except Exception as e:
                        logger.error("Audio detection failed: %s", e)

            except Exception as exc:
                logger.error(f"Video analysis error: {exc}")
                metadata = metadata or {"error": str(exc)}

            # Cleanup is handled by caller (temp file deletion) or assuming input path persists

        # ── Text Processing ─────────────────────────────────────────────────
        if query and query.strip():
            # Text Detection
            _set_status("Analyzing text patterns...")
            self.load_model("text")
            if self.models.get("text"):
                t0 = time.perf_counter()
                try:
                    text_result = self.models["text"].predict(query)
                    elapsed = time.perf_counter() - t0
                    logger.info("Text detection: %s (%.2fs)", text_result.get("label"), elapsed)
                    ai_prob = text_result.get("ai_probability", 0)
                    ai_models.append({"name": "TextAIDetector (DeBERTa)", "score": int(ai_prob * 100)})
                except Exception as e:
                    logger.error("Text detection failed: %s", e)

            # Fact Check (FAISS)
            _set_status("Cross-referencing content database...")
            self.load_model("faiss")
            if self.models.get("faiss"):
                t0 = time.perf_counter()
                try:
                    fact_check = self.models["faiss"].search(query)
                    elapsed = time.perf_counter() - t0
                    if fact_check:
                        best_score = fact_check[0].get("similarity_score", 0)
                        ai_models.append({"name": "FactCheck (FAISS)", "score": int(best_score * 100)})
                except Exception as e:
                    logger.error("FAISS search failed: %s", e)

        # ── Aggregation & Post-processing ──────────────────────────────────
        
        # Risk Assessment
        risk_assessment = _compute_risk_score(metadata, video_result, text_result)

        # Drift Data
        duration = metadata.get("file_info", {}).get("duration_seconds", 0)
        if duration > 0:
            drift_data = _generate_drift_data(duration, video_result)

        # Basic report aggregation
        base_report = aggregate_results(
            video_result=video_result,
            audio_result=audio_result,
            text_result=text_result,
            articles=fact_check,
        )

        processing_time = round(time.perf_counter() - t_start_total, 2)
        
        # Construct full report matching the API structure
        full_report = {
            # Basic info
            "summary": "Analysis complete",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "processing_time_seconds": processing_time,
            
            # Scores & Risk
            "score": risk_assessment["authenticity_score"],
            "risk_level": risk_assessment["risk_level"],
            "risk_assessment": risk_assessment,
            
            # Data for UI
            "metadata": metadata,
            "drift_data": drift_data,
            "ai_models": ai_models,
            
            # Detailed ML results (merged from aggregate_results)
            "video_result": base_report.get("video"),
            "audio_result": base_report.get("audio"),
            "text_result": base_report.get("text"),
            "related_articles": base_report.get("related_articles"),
            "combined_fake_probability": base_report.get("combined_fake_probability", 0.5),
            "overall_label": base_report.get("overall_label", "uncertain"),
        }

        return full_report

def main() -> None:
    load_dotenv()
    args = parse_args()

    # Handle document input -> query
    text_file = getattr(args, "text_file", None)
    if text_file:
        from utils.document_reader import read_document
        logger.info("Reading document: %s", text_file)
        file_text = read_document(text_file)
        if not file_text.strip():
            print("ERROR: Document is empty.")
            sys.exit(1)
        args.query = file_text

    if not args.video and not args.query:
        print("ERROR: Provide --video, --query, or --text-file.")
        sys.exit(1)

    print("Initializing Pipeline...", end="", flush=True)
    pipeline = DeepfakeDetectionPipeline()
    print(" done.")

    print("\nStarting analysis...")
    report = pipeline.process(video_path=args.video, query=args.query)

    # ------------------------------------------------------------------
    # CLI Output Logic
    # ------------------------------------------------------------------
    sep = "=" * 60
    print(f"\n{sep}")
    print("  truth.x  -  Detection Report")
    print(sep)
    
    # 1. Video
    v = report.get("video_result")
    if v and v.get("label") != "unknown":
        print(f"\n  [Video]  {v['label'].upper()}  (confidence: {v.get('confidence', 0):.2%})")
    
    # 2. Audio
    a = report.get("audio_result")
    if a:
        print(f"\n  [Audio]  {a.get('label', 'N/A').upper()} (confidence: {a.get('confidence', 0):.2%})")

    # 3. Text
    t = report.get("text_result")
    if t:
        print(f"\n  [Text]   {t.get('label', 'N/A').upper()} (confidence: {t.get('confidence', 0):.2%})")

    # 4. Risk / Score
    print(f"\n{'-' * 60}")
    print(f"  AUTHENTICITY SCORE : {report['score']} / 100")
    print(f"  RISK LEVEL         : {report['risk_level'].upper()}")
    
    if report['risk_assessment']['flags']:
        print("\n  [Flags]")
        for flag in report['risk_assessment']['flags']:
            print(f"   - [{flag['severity'].upper()}] {flag['label']}: {flag['detail']}")

    print(f"{sep}\n")

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="truth.x  -  Detection Pipeline")
    p.add_argument("--video", type=str, default=None, help="Video file for deepfake analysis")
    p.add_argument("--query", type=str, default=None, help="Text for AI-text detection + article search")
    p.add_argument("--text-file", type=str, default=None, help="Document (.pdf .docx .txt) for AI-text detection")
    return p.parse_args()

if __name__ == "__main__":
    main()
