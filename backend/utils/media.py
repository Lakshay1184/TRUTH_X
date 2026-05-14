"""truth.x — FFmpeg / FFprobe media helpers."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict

from backend.utils.logger import logger


# ─── Locate binaries ────────────────────────────────────────────────────

def find_ffmpeg() -> str:
    """Find ffmpeg executable in local directory or system PATH."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for rel in ("ffmpeg/bin/ffmpeg.exe", "ffmpeg/ffmpeg.exe"):
        candidate = os.path.join(project_root, rel)
        if os.path.isfile(candidate):
            return candidate
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return "ffmpeg"


def find_ffprobe() -> str | None:
    """Find ffprobe executable."""
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


# ─── Helpers ─────────────────────────────────────────────────────────────

def parse_fps(fps_str: str) -> float:
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            return round(int(num) / int(den), 2)
        return round(float(fps_str), 2)
    except (ValueError, ZeroDivisionError):
        return 0.0


def format_duration(seconds: float) -> str:
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


# ─── Metadata Extraction ────────────────────────────────────────────────

def _extract_metadata_ffmpeg_fallback(video_path: str) -> dict:
    """Parse metadata from ffmpeg stderr output (fallback when ffprobe unavailable)."""
    if not os.path.exists(video_path):
        return {}
    ffmpeg_exe = find_ffmpeg()
    try:
        res = subprocess.run(
            [ffmpeg_exe, "-i", video_path, "-hide_banner"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        content = res.stderr
        duration_sec = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", content)
        if dur_match:
            h, m, s = map(float, dur_match.groups())
            duration_sec = h * 3600 + m * 60 + s

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

        tags: Dict[str, Any] = {}
        for key in ["creation_time", "encoder", "location", "major_brand", "model", "comment"]:
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
                "duration_human": format_duration(duration_sec),
                "total_bitrate_kbps": total_bitrate,
                "file_size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 2),
                "nb_streams": nb_streams,
                "container_format": os.path.splitext(video_path)[1].lstrip(".").upper(),
            },
            "video": video,
            "audio": audio,
            "tags": tags,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("Fallback metadata extraction failed: %s", e)
        return {}


def extract_video_metadata(video_path: str, ffprobe_path: str | None = None) -> dict:
    """Extract comprehensive video metadata using ffprobe (preferred) or ffmpeg fallback."""
    if ffprobe_path:
        cmd = [ffprobe_path, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path]
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
                        "duration_human": format_duration(duration),
                        "total_bitrate_kbps": round(total_bitrate / 1000) if total_bitrate else 0,
                        "nb_streams": int(fmt.get("nb_streams", 0)),
                    },
                }
                if video_stream:
                    vtags = video_stream.get("tags", {})
                    width = int(video_stream.get("width", 0))
                    height = int(video_stream.get("height", 0))
                    fps = parse_fps(video_stream.get("r_frame_rate", "0/1"))
                    avg_fps = parse_fps(video_stream.get("avg_frame_rate", "0/1"))
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
                if video_stream:
                    all_tags.update(video_stream.get("tags", {}))
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
                    "software_version": ["com.apple.quicktime.software", "software"],
                }
                for out_key, candidates in mapping.items():
                    val = next((all_tags.get(c) for c in candidates if all_tags.get(c)), None)
                    if val:
                        tag_info[out_key] = val
                if tag_info:
                    metadata["tags"] = tag_info
                if subtitle_streams:
                    metadata["subtitle_streams"] = len(subtitle_streams)
                metadata["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                return metadata
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logger.warning("FFprobe extraction error: %s", e)

    logger.info("Using FFmpeg fallback for metadata extraction")
    return _extract_metadata_ffmpeg_fallback(video_path)
