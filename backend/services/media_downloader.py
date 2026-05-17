"""
Truth_X Media Downloader Service.
Wraps yt-dlp to handle various social media and video URLs.
"""

from __future__ import annotations

import os
import yt_dlp
from typing import Optional, Dict, Any
from backend.utils.logger import logger

class MediaDownloader:
    """Handles downloading of video/audio from various online sources."""

    def __init__(self, download_dir: str = "data/downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

    def download(self, url: str, status_callback: Optional[callable] = None) -> Optional[str]:
        """
        Download media from URL and return the path to the downloaded file.
        Prefer best audio for Intel processing.
        """
        if status_callback:
            status_callback("Connecting to media source...")

        # Output template: downloads/video_id.ext
        output_tmpl = os.path.join(self.download_dir, "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_tmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "nocheckcertificate": True,
            # --- Advanced Hardening against 403 Forbidden ---
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "retries": 15,
            "fragment_retries": 15,
            "http_chunk_size": 10485760, # 10MB
            "concurrent_fragment_downloads": 8,
            "geo_bypass": True,
            "ignoreerrors": False, # Stop immediately on error to report it
            "no_color": True,
            # youtube-specific hardening
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web", "mweb"],
                    "player_skip": ["webpage", "configs"],
                }
            },
            # Allow some extra time for extraction
            "socket_timeout": 60,
        }

        try:
            logger.info(f"Initiating forensic extraction for: {url}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if status_callback:
                    status_callback("Downloading media stream...")
                
                # Perform extraction and download
                info = ydl.extract_info(url, download=True)
                if not info:
                    logger.error(f"yt-dlp failed to extract info for {url}")
                    return None

                # Diagnostics
                extractor = info.get("extractor_key", "unknown")
                logger.info(f"Forensic extraction successful. Extractor: {extractor}")
                
                # The postprocessor changes the extension to .wav
                filename = ydl.prepare_filename(info)
                base_path = os.path.splitext(filename)[0]
                final_path = f"{base_path}.wav"
                
                if os.path.exists(final_path):
                    logger.info(f"Media internalized at: {final_path}")
                    return final_path
                
                logger.error(f"Expected Internal file not found: {final_path}")
                return None

        except yt_dlp.utils.DownloadError as de:
            err_msg = str(de)
            logger.error(f"yt-dlp Download Error: {err_msg}")
            
            if "403" in err_msg or "Forbidden" in err_msg:
                if status_callback:
                    status_callback("Error: Video download blocked by platform.")
            elif "Sign in to confirm your age" in err_msg:
                if status_callback:
                    status_callback("Error: Source unavailable (age restricted).")
            else:
                if status_callback:
                    status_callback("Error: YouTube extraction failed. Source rejected connection.")
            return None
        except Exception as e:
            logger.error(f"MediaDownloader critical failure: {e}")
            if status_callback:
                status_callback(f"Ingestion failed: Service timeout or rejection.")
            return None

    def get_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get metadata about the media without downloading."""
        ydl_opts = {"quiet": True, "no_warnings": True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception:
            return None
