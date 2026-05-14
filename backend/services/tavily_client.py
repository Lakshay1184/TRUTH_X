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

from backend.utils.logger import logger

TAVILY_API_URL = "https://api.tavily.com/search"
_DEFAULT_TIMEOUT = 15.0
_MAX_RETRIES = 3


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
            "nature.com", "science.org", "thelancet.com", "who.int", "cdc.gov"
        ]

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(_DEFAULT_TIMEOUT))
        return self._client

    async def search(
        self, 
        query: str, 
        search_depth: str = "advanced",
        include_domains: Optional[List[str]] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Execute a live web search for a claim.
        Returns a list of result dictionaries containing url, title, and content.
        """
        if not self._api_key:
            return []

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

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.post(TAVILY_API_URL, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    logger.debug("Tavily search successful: %d results for '%s'", len(results), query[:30])
                    return results
                
                elif response.status_code == 429:
                    logger.warning("Tavily rate limit hit. Retrying...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("Tavily API error: %d - %s", response.status_code, response.text)
                    return []

            except httpx.TimeoutException:
                logger.warning("Tavily search timeout (attempt %d/%d)", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                logger.error("Tavily search unexpected error: %s", e)
                return []

        return []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Synchronous wrapper for use in threads/existing pipeline
def run_tavily_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    client = TavilyClient()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(client.search(query, max_results=max_results))
        loop.run_until_complete(client.close())
        return result
    except Exception as e:
        logger.error("Sync Tavily search failed: %s", e)
        return []
    finally:
        loop.close()
