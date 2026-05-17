"""truth.x — Social Media Intelligence Scanner.

Asynchronously scrapes content from shared URLs, performs OCR on images,
and extracts network graphs for propagation analysis.
"""

import re
import httpx
from bs4 import BeautifulSoup
import os
from backend.workers.celery_app import celery_app
from backend.utils.logger import logger

# For simple OCR if needed, would import pytesseract
# import pytesseract

@celery_app.task(bind=True, max_retries=3)
def scan_social_url(self, url: str) -> dict:
    """Scrape and analyze a social media URL."""
    logger.info(f"Scanning social URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # Note: True production systems use Playwright/Puppeteer for social sites due to heavy JS.
        # This is an httpx fallback approach for standard pages.
        with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract basic metadata
            title = soup.find("title")
            title_text = title.text if title else ""
            
            meta_desc = soup.find("meta", {"name": "description"})
            desc_text = meta_desc["content"] if meta_desc and "content" in meta_desc.attrs else ""
            
            # Extract main text content (rudimentary)
            paragraphs = soup.find_all("p")
            main_text = "\n".join([p.text for p in paragraphs])
            
            # Try to identify platform
            platform = "unknown"
            if "twitter.com" in url or "x.com" in url:
                platform = "twitter"
            elif "facebook.com" in url:
                platform = "facebook"
            elif "instagram.com" in url:
                platform = "instagram"
            elif "reddit.com" in url:
                platform = "reddit"
            elif "youtube.com" in url or "youtu.be" in url:
                platform = "youtube"
                
            return {
                "url": url,
                "platform": platform,
                "title": title_text,
                "description": desc_text,
                "scraped_text": main_text[:2000],  # Limit length
                "status": "success",
            }
            
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error scanning {url}: {e.response.status_code}")
        if e.response.status_code in [403, 429]:
            self.retry(countdown=60)
        return {"url": url, "error": f"HTTP {e.response.status_code}", "status": "failed"}
    except Exception as e:
        logger.error(f"Error scanning {url}: {e}")
        return {"url": url, "error": str(e), "status": "failed"}


@celery_app.task
def build_propagation_graph(url: str, content_id: str) -> dict:
    """Build a propagation graph for a URL/content ID.

    The previous implementation returned a hardcoded mock graph which caused
    demo data to appear in production UIs. We now gate the mock output behind
    the `ENABLE_SOCIAL_MOCK` environment variable. When not enabled, return an
    empty graph and log the skip so the caller can handle an honest 'no data'.
    """
    logger.info(f"Building propagation graph for {content_id} / {url}")
    enable_mock = os.environ.get("ENABLE_SOCIAL_MOCK", "false").lower() in ("1", "true", "yes")
    if not enable_mock:
        logger.info("Propagation graph mock disabled (ENABLE_SOCIAL_MOCK=false); returning empty graph")
        return {"nodes": [], "edges": []}

    # Returns dummy graph data for UI rendering when explicitly enabled
    return {
        "nodes": [
            {"id": "source", "type": "origin", "url": url},
            {"id": "node_1", "type": "share", "platform": "twitter", "engagement": 1500},
            {"id": "node_2", "type": "share", "platform": "facebook", "engagement": 300},
        ],
        "edges": [
            {"source": "source", "target": "node_1", "time_delta_mins": 15},
            {"source": "source", "target": "node_2", "time_delta_mins": 45},
            {"source": "node_1", "target": "node_2", "time_delta_mins": 30}, # cross-pollination
        ]
    }
