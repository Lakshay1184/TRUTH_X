"""
Truth_X Media Downloader Service (REFECTORED).
Eliminated yt-dlp dependency for cloud stability.
Focuses on metadata extraction and local file processing.
"""

from __future__ import annotations

import os
import re
import httpx
from typing import Optional, Dict, Any
from backend.utils.logger import logger

class MediaDownloader:
    """Handles metadata extraction from online sources without downloading heavy media streams."""

    def __init__(self, download_dir: str = "data/downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

    def download(self, url: str, status_callback: Optional[callable] = None) -> Optional[str]:
        """
        [DISABLED] Heavy media downloading is disabled in this version.
        Always returns None to trigger metadata-only fallbacks.
        """
        logger.warning(f"Media download requested for {url} but is DISABLED in this version.")
        if status_callback:
            status_callback("Media downloading disabled. Switching to metadata intelligence mode...")
        return None

    def get_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract lightweight metadata (Title, Description) from URL using standard HTTP.
        No yt-dlp required.
        """
        if "youtube.com" in url or "youtu.be" in url:
            return self._get_youtube_metadata(url)
        
        # General metadata extraction for other URLs could be added here
        return None

    def _get_youtube_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Naively extract YouTube title and metadata via HTTP/Regex."""
        try:
            logger.info(f"Extracting lightweight YouTube metadata: {url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            }
            resp = httpx.get(url, timeout=10, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text

            # Extract Title
            title_match = re.search(r"<title>(.*?)</title>", html)
            title = title_match.group(1).replace(" - YouTube", "").strip() if title_match else "Unknown YouTube Video"

            # Extract Description (simplified)
            desc_match = re.search(r'\"shortDescription\":\"(.*?)\"', html)
            description = desc_match.group(1).encode().decode('unicode_escape') if desc_match else ""

            return {
                "title": title,
                "description": description,
                "url": url,
                "extractor": "youtube_metadata_lite"
            }
        except Exception as e:
            logger.error(f"YouTube metadata extraction failed: {e}")
            return None
