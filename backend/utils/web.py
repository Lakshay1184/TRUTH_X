"""
Truth_X Web Scraping and Text Extraction Utilities.
"""

from __future__ import annotations

import re
import httpx
from typing import Optional
from backend.utils.logger import logger

def extract_text_from_html(html: str) -> str:
    """Naively extract readable text from HTML."""
    # Remove script/style blocks
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    # Strip all tags
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url_text(url: str) -> Optional[str]:
    """Fetch a URL and extract visible text."""
    try:
        # Use common browser headers to avoid blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = httpx.get(url, timeout=15, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        text = extract_text_from_html(resp.text)
        return text if text else None
    except Exception as exc:
        logger.warning("URL fetch failed: %s", exc)
        return None

def is_video_platform_url(url: str) -> bool:
    """Identify if a URL points to a major video platform or direct video file."""
    url = url.lower()
    video_indicators = [
        "youtube.com", "youtu.be",
        "tiktok.com",
        "instagram.com/reels", "instagram.com/reel", "instagram.com/p/",
        "twitter.com/", "x.com/", "/status/",
        "facebook.com/watch", "facebook.com/reel",
        ".mp4", ".mkv", ".mov", ".avi", ".webm"
    ]
    return any(indicator in url for indicator in video_indicators)
