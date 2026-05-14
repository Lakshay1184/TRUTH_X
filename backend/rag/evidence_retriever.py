"""truth.x — Evidence Retriever for RAG Fake News Pipeline.

Retrieves relevant evidence from:
    1. Local article corpus (FAISS / cosine similarity)
    2. Google Fact Check API (if API key configured)

Returns ranked evidence passages for contradiction analysis.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import yaml

from backend.utils.logger import logger
from backend.services.tavily_client import run_tavily_search

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class EvidenceRetriever:
    """Retrieves evidence from multiple sources for claim verification."""

    def __init__(self, faiss_service=None) -> None:
        cfg = _load_config()
        self._faiss = faiss_service
        self._fact_check_api_key = os.environ.get("FACT_CHECK_API_KEY", "")
        self._fact_check_api_url = os.environ.get(
            "FACT_CHECK_API_URL",
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
        )
        self.top_k = cfg.get("retrieval", {}).get("top_k", 5)
        self._tavily_enabled = bool(os.environ.get("TAVILY_API_KEY", ""))
        logger.info("EvidenceRetriever initialized (FAISS=%s, FactCheckAPI=%s, Tavily=%s)",
                     self._faiss is not None, bool(self._fact_check_api_key), self._tavily_enabled)

    def retrieve(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Retrieve evidence for a list of claims.

        Args:
            claims: List of claim dicts from ClaimExtractor

        Returns:
            {
                "evidence_pieces": [{
                    "claim_text": str,
                    "source": str,  # "local_corpus" | "fact_check_api"
                    "title": str,
                    "content": str,
                    "similarity_score": float,
                    "publisher": str,
                    "url": str,
                }],
                "sources_searched": [str],
                "total_evidence": int,
            }
        """
        all_evidence: List[Dict[str, Any]] = []
        sources_searched = []

        for claim in claims:
            claim_text = claim.get("text", "")
            if not claim_text:
                continue

            # 1. Local corpus search
            local_results = self._search_local(claim_text)
            if local_results:
                for r in local_results:
                    r["claim_text"] = claim_text
                    r["source"] = "local_corpus"
                all_evidence.extend(local_results)
                if "local_corpus" not in sources_searched:
                    sources_searched.append("local_corpus")

            # 2. Google Fact Check API
            api_results = self._search_fact_check_api(claim_text)
            if api_results:
                for r in api_results:
                    r["claim_text"] = claim_text
                    r["source"] = "fact_check_api"
                all_evidence.extend(api_results)
                if "fact_check_api" not in sources_searched:
                    sources_searched.append("fact_check_api")

            # 3. Tavily Live Web Intelligence
            tavily_results = self._search_tavily_api(claim_text)
            if tavily_results:
                for r in tavily_results:
                    r["claim_text"] = claim_text
                    r["source"] = "tavily_live_search"
                all_evidence.extend(tavily_results)
                if "tavily_live_search" not in sources_searched:
                    sources_searched.append("tavily_live_search")

        # Deduplicate and rank by relevance
        all_evidence = self._deduplicate(all_evidence)
        all_evidence.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

        logger.info("Evidence retrieval: %d pieces from %d sources",
                     len(all_evidence), len(sources_searched))

        return {
            "evidence_pieces": all_evidence[:self.top_k * 2],  # Cap at reasonable size
            "sources_searched": sources_searched,
            "total_evidence": len(all_evidence),
        }

    # ── Local corpus search ───────────────────────────────────────────────

    def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """Search the local article corpus via FAISS service."""
        if self._faiss is None:
            return []
        try:
            results = self._faiss.search(query, k=self.top_k)
            return [
                {
                    "title": r.get("title", ""),
                    "content": r.get("claim", r.get("content", ""))[:500],
                    "similarity_score": r.get("similarity_score", 0),
                    "publisher": r.get("source", r.get("publisher", "Local Corpus")),
                    "url": r.get("url", ""),
                    "verdict": r.get("verdict", ""),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("Local search failed: %s", e)
            return []

    # ── Google Fact Check API ─────────────────────────────────────────────

    def _search_fact_check_api(self, query: str) -> List[Dict[str, Any]]:
        """Search Google Fact Check Tools API."""
        if not self._fact_check_api_key:
            return []

        try:
            import httpx
            response = httpx.get(
                self._fact_check_api_url,
                params={
                    "query": query[:200],
                    "key": self._fact_check_api_key,
                    "languageCode": "en",
                },
                timeout=10,
            )

            if response.status_code != 200:
                logger.warning("Fact Check API returned %d", response.status_code)
                return []

            data = response.json()
            results = []

            for claim_obj in data.get("claims", [])[:5]:
                claim_review = claim_obj.get("claimReview", [{}])[0] if claim_obj.get("claimReview") else {}
                results.append({
                    "title": claim_obj.get("text", ""),
                    "content": claim_obj.get("text", ""),
                    "similarity_score": 0.7,  # API doesn't return similarity
                    "publisher": claim_review.get("publisher", {}).get("name", "Fact Checker"),
                    "url": claim_review.get("url", ""),
                    "verdict": claim_review.get("textualRating", ""),
                })

            return results

        except Exception as e:
            logger.warning("Fact Check API error: %s", e)
            return []

    # ── Tavily Live Search ────────────────────────────────────────────────

    def _search_tavily_api(self, query: str) -> List[Dict[str, Any]]:
        """Search for live web evidence using Tavily."""
        if not self._tavily_enabled:
            return []
            
        try:
            raw_results = run_tavily_search(query, max_results=self.top_k)
            results = []
            
            for item in raw_results:
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("content", "")[:1000],
                    "similarity_score": item.get("score", 0.8),  # Default high since Tavily ranks well
                    "publisher": item.get("url", "").split("/")[2] if "url" in item else "Web Source",
                    "url": item.get("url", ""),
                    "verdict": "",  # To be reasoned by Mistral later
                })
            
            return results
        except Exception as e:
            logger.warning("Tavily API error: %s", e)
            return []

    # ── Deduplication ─────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate evidence based on title similarity."""
        seen_titles = set()
        deduped = []
        for e in evidence:
            title_key = e.get("title", "").lower().strip()[:50]
            if title_key and title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            deduped.append(e)
        return deduped
