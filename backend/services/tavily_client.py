"""truth.x — Tavily API Client.

Provides real-time web intelligence and OSINT retrieval for the RAG pipeline.
Filters for trusted domains and deduplicates results.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.utils.env_loader import ensure_backend_environment_loaded
from backend.utils.logger import logger

ensure_backend_environment_loaded()

TAVILY_API_URL = "https://api.tavily.com/search"
_DEFAULT_TIMEOUT = float(os.environ.get("TAVILY_TIMEOUT_SECONDS", "6"))
_MAX_RETRIES = int(os.environ.get("TAVILY_MAX_RETRIES", "1"))

# --- Query Cache (1 Hour TTL) ---
_tavily_cache: Dict[str, Any] = {}
_cache_ttl = 3600 # 1 hour

def _get_cache_key(query: str, include_domains: Optional[List[str]]) -> str:
    import hashlib
    domain_str = ",".join(sorted(include_domains)) if include_domains else "default"
    return hashlib.sha1(f"{query.lower()}|{domain_str}".encode()).hexdigest()

class TavilyClient:
    """Async client for Tavily Search API with retry logic and trusted source filtering."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if not self._api_key:
            logger.warning("TAVILY_API_KEY not set — live web search will be disabled")
        self._client: Optional[httpx.AsyncClient] = None
        
        # OSINT filtering for reliable sources
        self.trusted_domains = [
            "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org", 
            "snopes.com", "politifact.com", "factcheck.org", "afp.com",
            "nytimes.com", "washingtonpost.com", "wsj.com", "bloomberg.com",
            "nature.com", "science.org", "thelancet.com", "who.int", "cdc.gov",
            "tribuneindia.com", "thehindu.com", "indianexpress.com", "aljazeera.com",
            "scientificamerican.com", "newscientist.com", "economist.com"
        ]

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(_DEFAULT_TIMEOUT))
        return self._client

    async def search(
        self, 
        query: str, 
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        max_results: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Execute a live web search for a claim with caching.
        Returns a list of result dictionaries containing url, title, and content.
        """
        if not self._api_key:
            logger.warning("Tavily request skipped: API key not configured")
            return []

        # --- Cache Check ---
        cache_key = _get_cache_key(query, include_domains)
        if cache_key in _tavily_cache:
            entry = _tavily_cache[cache_key]
            if time.time() - entry["timestamp"] < _cache_ttl:
                logger.info("Tavily cache hit for query: %r", query[:100])
                return entry["results"]

        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": search_depth,
            "include_domains": include_domains or self.trusted_domains,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }

        client = await self._ensure_client()
        logger.info(
            "Tavily request dispatched | query=%r | depth=%s | results=%d",
            query[:150],
            search_depth,
            max_results,
        )

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                request_started = time.perf_counter()
                response = await client.post(TAVILY_API_URL, json=payload)
                latency_ms = round((time.perf_counter() - request_started) * 1000, 2)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    
                    # Store in cache
                    _tavily_cache[cache_key] = {
                        "results": results,
                        "timestamp": time.time()
                    }
                    
                    logger.info(
                        "Tavily success | query=%r | latency=%.2fms | results=%d",
                        query[:100],
                        latency_ms,
                        len(results),
                    )
                    return results
                
                elif response.status_code == 429:
                    logger.warning("Tavily rate limit hit. Sleeping...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("Tavily error %d: %s", response.status_code, response.text)
                    return []

            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                logger.error("Tavily unexpected error: %s", e)
                return []

        return []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Synchronous wrapper for use in threads/existing pipeline
def run_tavily_search(
    query: str,
    max_results: int = 5,
    audit=None,
    stage: str = "tavily_search",
    include_domains: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Synchronous wrapper around TavilyClient.search that handles nested event loops."""
    
    def _run_in_new_loop():
        client = TavilyClient()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            started = time.perf_counter()
            result = loop.run_until_complete(client.search(query, include_domains=include_domains, max_results=max_results))
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            if audit is not None:
                audit.log_event(stage, "Tavily response received", latency_ms=elapsed_ms, result_count=len(result))
            loop.run_until_complete(client.close())
            return result
        finally:
            try:
                loop.close()
            except Exception:
                pass

    # Check if a loop is already running
    try:
        running_loop = asyncio.get_running_loop()
        loop_running = running_loop.is_running()
    except RuntimeError:
        loop_running = False

    if not loop_running:
        try:
            return _run_in_new_loop()
        except Exception as e:
            logger.error("Sync Tavily search failed stage=%s reason=%s", stage, e)
            if audit is not None:
                audit.record_failure(stage, f"Tavily failed: {e}", query=query[:200])
            return []

    # If we're inside a running loop, run the coroutine in a separate thread
    import threading
    import queue

    q: "queue.Queue" = queue.Queue()

    def _thread_worker():
        try:
            thread_client = TavilyClient()
            started = time.perf_counter()
            result = asyncio.run(thread_client.search(query, include_domains=include_domains, max_results=max_results))
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            try:
                asyncio.run(thread_client.close())
            except Exception:
                pass
            if audit is not None:
                audit.log_event(stage, "Tavily response received (thread)", latency_ms=elapsed_ms, result_count=len(result))
            q.put((True, result))
        except Exception as e:
            q.put((False, e))

    t = threading.Thread(target=_thread_worker, daemon=True)
    t.start()
    t.join(timeout=_DEFAULT_TIMEOUT + 5)

    try:
        ok, payload = q.get_nowait()
    except queue.Empty:
        logger.error("Tavily thread timeout stage=%s", stage)
        return []

    if not ok:
        logger.error("Tavily thread failed stage=%s reason=%s", stage, payload)
        return []

    return payload
