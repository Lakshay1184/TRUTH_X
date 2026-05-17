"""truth.x — Evidence Retriever for RAG Fake News Pipeline.

Retrieves relevant evidence from:
    1. Local article corpus (FAISS / cosine similarity)
    2. Google Fact Check API (if API key configured)

Returns ranked evidence passages for contradiction analysis.
"""

from __future__ import annotations

import json
import os
import time
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
        # Minimum similarity threshold for retrieval (rag.min_similarity)
        self.min_similarity = cfg.get("rag", {}).get("min_similarity", 0.3)
        # Control whether to use the local seeded corpus (data/articles.json)
        self._use_local_corpus = bool(cfg.get("retrieval", {}).get("use_local_corpus", False))
        self._tavily_enabled = bool(os.environ.get("TAVILY_API_KEY", ""))
        logger.info("EvidenceRetriever initialized (FAISS=%s, FactCheckAPI=%s, Tavily=%s)",
                     self._faiss is not None, bool(self._fact_check_api_key), self._tavily_enabled)

    def _rewrite_query(self, claim_text: str, claim_type: str = "", content_type: str = "") -> str:
        query = claim_text.strip()
        hints: List[str] = []
        normalized_type = (content_type or claim_type or "").lower()
        if normalized_type in {"scientific", "factual_explanation"}:
            hints.extend(["peer-reviewed", "research", "study", "academic"])
        elif normalized_type == "news":
            hints.extend(["report", "official statement", "wire service"])
        elif normalized_type == "political":
            hints.extend(["government record", "policy", "vote", "statement"])
        elif normalized_type == "social_media":
            hints.extend(["post", "platform", "fact check", "screenshot"])
        elif normalized_type == "opinion":
            hints.extend(["analysis", "editorial", "commentary"])

        if hints:
            query = f"{query} {' '.join(hints[:3])}"
        return query[:400]

    def retrieve(self, claims: List[Dict[str, Any]], content_type: str = "", audit=None) -> Dict[str, Any]:
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
        retrieval_errors: List[Dict[str, str]] = []
        started = time.perf_counter()

        logger.info(
            "Evidence retrieval started claims=%d content_type=%s faiss=%s fact_check=%s tavily=%s",
            len(claims),
            content_type or "unknown",
            self._faiss is not None,
            bool(self._fact_check_api_key),
            self._tavily_enabled,
        )
        if audit is not None:
            audit.log_event("evidence_retrieval", "Evidence retrieval started", claim_count=len(claims), content_type=content_type)

        for claim in claims:
            claim_text = claim.get("text", "")
            if not claim_text:
                continue

            claim_type = claim.get("type", "")
            rewritten_query = self._rewrite_query(claim_text, claim_type, content_type)
            logger.info(
                "Evidence retrieval claim query original=%r rewritten=%r type=%s",
                claim_text[:180],
                rewritten_query[:220],
                claim_type or "factual",
            )
            if audit is not None:
                audit.log_event(
                    "evidence_retrieval",
                    "Claim query rewritten",
                    original_query=claim_text[:220],
                    rewritten_query=rewritten_query[:220],
                    claim_type=claim_type or "factual",
                )

            # 1. Local corpus search
            local_results = []
            if self._use_local_corpus:
                local_results = self._search_local(rewritten_query)
                # filter by min similarity to avoid returning low-quality/demo matches
                local_results = [r for r in local_results if (r.get("similarity_score", 0) or 0) >= self.min_similarity]
                if local_results:
                    for r in local_results:
                        r["claim_text"] = claim_text
                        r["source"] = "local_corpus"
                        r["retrieval_query"] = rewritten_query
                    all_evidence.extend(local_results)
                    if "local_corpus" not in sources_searched:
                        sources_searched.append("local_corpus")
                    logger.info("Local semantic retrieval matched %d documents (post-filter)", len(local_results))
                else:
                    logger.warning("Local semantic retrieval returned no matches (or none above min_similarity) for query=%r", rewritten_query[:200])
                    retrieval_errors.append({
                        "stage": "local_semantic_retrieval",
                        "reason": f"No local semantic matches above threshold for query: {rewritten_query[:120]}",
                    })
            else:
                logger.info("Local corpus search skipped per configuration (use_local_corpus=false)")

            # 2. Google Fact Check API
            api_results = self._search_fact_check_api(rewritten_query)
            if api_results:
                for r in api_results:
                    r["claim_text"] = claim_text
                    r["source"] = "fact_check_api"
                    r["retrieval_query"] = rewritten_query
                all_evidence.extend(api_results)
                if "fact_check_api" not in sources_searched:
                    sources_searched.append("fact_check_api")
                logger.info("Fact Check API returned %d results", len(api_results))
            else:
                logger.info("Fact Check API returned no results or is disabled for query=%r", rewritten_query[:200])
                retrieval_errors.append({
                    "stage": "fact_check_api",
                    "reason": f"No fact-check matches for query: {rewritten_query[:120]} or API disabled",
                })

            # 3. Tavily Live Web Intelligence
            tavily_results = self._search_tavily_api(rewritten_query, audit=audit)
            if tavily_results:
                for r in tavily_results:
                    r["claim_text"] = claim_text
                    r["source"] = "tavily_live_search"
                    r["retrieval_query"] = rewritten_query
                all_evidence.extend(tavily_results)
                if "tavily_live_search" not in sources_searched:
                    sources_searched.append("tavily_live_search")
                logger.info("Tavily search returned %d results for claim", len(tavily_results))
            else:
                logger.warning("Tavily search returned no results for query=%r", rewritten_query[:200])
                retrieval_errors.append({
                    "stage": "tavily_search",
                    "reason": f"No Tavily results for query: {rewritten_query[:120]}",
                })

        # Apply final filtering: drop any evidence below similarity threshold
        filtered_evidence = [e for e in all_evidence if (e.get("similarity_score", 0) or 0) >= self.min_similarity]
        if not filtered_evidence and all_evidence:
            # If everything was filtered out, keep the top-k items but flag in retrieval_errors
            logger.warning("All retrieved evidence fell below min_similarity=%.2f; returning top candidates for debugging", self.min_similarity)
            retrieval_errors.append({
                "stage": "final_filtering",
                "reason": f"All candidates below min_similarity={self.min_similarity}. Returning top candidates for inspection.",
            })
            filtered_evidence = sorted(all_evidence, key=lambda x: x.get("similarity_score", 0), reverse=True)[: self.top_k]

        # Deduplicate and rank by relevance
        all_evidence = self._deduplicate(filtered_evidence)
        all_evidence.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Evidence retrieval complete evidence_count=%d sources=%d latency_ms=%.2f",
            len(all_evidence),
            len(sources_searched),
            elapsed_ms,
        )
        if audit is not None:
            audit.log_event(
                "evidence_retrieval",
                "Evidence retrieval complete",
                evidence_count=len(all_evidence),
                sources_searched=sources_searched,
                latency_ms=elapsed_ms,
                retrieval_errors=retrieval_errors,
            )

        return {
            "evidence_pieces": all_evidence[:self.top_k * 2],  # Cap at reasonable size
            "sources_searched": sources_searched,
            "total_evidence": len(all_evidence),
            "retrieval_errors": retrieval_errors,
        }

    # ── Local corpus search ───────────────────────────────────────────────

    def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """Search the local article corpus via FAISS service."""
        if self._faiss is None:
            return []
        try:
            started = time.perf_counter()
            results = self._faiss.search(query, k=self.top_k)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info("FAISS semantic retrieval query=%r result_count=%d latency_ms=%.2f", query[:200], len(results), elapsed_ms)
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
            logger.error("Local search failed query=%r reason=%s", query[:200], e)
            return []

    # ── Google Fact Check API ─────────────────────────────────────────────

    def _search_fact_check_api(self, query: str) -> List[Dict[str, Any]]:
        """Search Google Fact Check Tools API."""
        if not self._fact_check_api_key:
            return []

        try:
            import httpx
            started = time.perf_counter()
            logger.info("Fact Check API request sent query=%r", query[:200])
            response = httpx.get(
                self._fact_check_api_url,
                params={
                    "query": query[:200],
                    "key": self._fact_check_api_key,
                    "languageCode": "en",
                },
                timeout=10,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)

            if response.status_code != 200:
                logger.warning("Fact Check API returned status=%d latency_ms=%.2f", response.status_code, latency_ms)
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
            logger.warning("Fact Check API error query=%r reason=%s", query[:200], e)
            return []

    # ── Tavily Live Search ────────────────────────────────────────────────

    def _search_tavily_api(self, query: str, audit=None) -> List[Dict[str, Any]]:
        """Search for live web evidence using Tavily."""
        if not self._tavily_enabled:
            logger.warning("Tavily search skipped: API key not configured")
            if audit is not None:
                audit.log_event("tavily_search", "Tavily skipped; API key missing")
            return []
            
        try:
            raw_results = run_tavily_search(query, max_results=self.top_k, audit=audit, stage="tavily_search")
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
            logger.warning("Tavily API error query=%r reason=%s", query[:200], e)
            if audit is not None:
                audit.record_failure("tavily_search", f"Tavily API error: {e}", query=query[:200])
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
