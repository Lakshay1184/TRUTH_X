"""truth.x Intel LangGraph engine.

This module upgrades Intel mode into a claim-level verification pipeline with:
- content classification
- claim extraction and normalization
- query rewriting
- retrieval routing
- Tavily + semantic retrieval
- evidence aggregation and contradiction analysis
- source ranking and verdict generation
- Mistral summaries
- grounded RAG QA
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, TypedDict

import numpy as np
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, StateGraph

from backend.utils.env_loader import ensure_backend_environment_loaded
from backend.rag.claim_extractor import ClaimExtractor
from backend.rag.content_classifier import ContentClassifier
from backend.rag.contradiction_detector import ContradictionDetector
from backend.services.faiss_service import FAISSSearch
from backend.services.mistral_client import run_mistral_chat
from backend.services.tavily_client import TavilyClient, run_tavily_search
from backend.utils.logger import logger
from backend.utils.pipeline_audit import PipelineAuditTrail

ensure_backend_environment_loaded()

IntelMode = Literal["analysis", "qa"]


_STOPWORDS = {
    "the", "and", "or", "but", "not", "for", "with", "that", "this", "there",
    "from", "into", "about", "like", "than", "then", "when", "where", "what",
    "which", "because", "exactly", "really", "very", "just", "like", "between",
    "their", "they", "them", "were", "been", "into", "through", "using", "used",
    "does", "did", "doing", "have", "has", "had", "will", "would", "could",
    "should", "might", "may", "can", "must", "also", "more", "most", "less",
}

_CLAIM_TOPIC_RULES: List[tuple[Sequence[str], List[str]]] = [
    (("dolphin", "dolphins"), ["dolphin unihemispheric sleep study", "cetacean sleep neuroscience", "marine mammal sleep behavior"]),
    (("octopus", "octopuses", "cephalopod"), ["octopus sleep behavior research", "cephalopod REM sleep study", "octopus cognition research"]),
    (("animal", "animals", "cognition", "intelligence", "think", "consciousness"), ["animal cognition research", "comparative animal intelligence", "animal consciousness studies"]),
    (("sleep", "dream", "dream-like", "rem"), ["sleep neuroscience research", "REM sleep study", "sleep behavior research"]),
    (("politics", "election", "vote", "congress", "senate", "president"), ["government record", "official statement", "policy analysis"]),
    (("vaccine", "medical", "health", "disease", "cancer"), ["medical research study", "peer-reviewed medical evidence", "nih pubmed search"]),
]


class IntelGraphState(TypedDict, total=False):
    mode: IntelMode
    trace_id: str
    audit: PipelineAuditTrail
    content: str
    question: str
    content_type: Dict[str, Any]
    claims: List[Dict[str, Any]]
    normalized_claims: List[Dict[str, Any]]
    query_plan: List[Dict[str, Any]]
    retrieval_plan: Dict[str, Any]
    tavily_results: List[Dict[str, Any]]
    scientific_results: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    evidence_graph: List[Dict[str, Any]]
    claim_evidence_map: Dict[str, List[Dict[str, Any]]]
    contradiction_result: Dict[str, Any]
    ranked_sources: List[Dict[str, Any]]
    verdict: Dict[str, Any]
    summary: str
    rag_context: str
    qa_documents: List[Document]
    qa_answer: Dict[str, Any]
    qa_context: str
    retrieval_errors: List[Dict[str, str]]
    retrieval_diagnostics: Dict[str, Any]
    progress_callback: Any
    pipeline_trace: Dict[str, Any]
    error: str
    is_fallback: bool
    original_url: str
    transcript: str


def _now_ms() -> float:
    return round(time.perf_counter() * 1000, 2)


def _dedupe_preserve_order(items: Iterable[Dict[str, Any]], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    results: List[Dict[str, Any]] = []
    for item in items:
        digest_source = "|".join(str(item.get(field, "")).strip().lower() for field in key_fields)
        digest = hashlib.sha1(digest_source.encode("utf-8", errors="ignore")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        results.append(item)
    return results


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _claim_terms(claim_text: str) -> List[str]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{2,}\b", claim_text.lower())
    return [token for token in tokens if token not in _STOPWORDS][:12]


class IntelEngine:
    """LangGraph-powered claim-level intelligence pipeline."""

    _MIN_EVIDENCE_SCORE = 0.42
    _MIN_QA_SCORE = 0.33

    def __init__(self) -> None:
        self._stage_progress: Dict[str, int] = {
            "content_classification": 8,
            "claim_extraction": 18,
            "claim_normalization": 28,
            "query_rewriting": 38,
            "retrieval_routing": 44,
            "tavily_search": 58,
            "scientific_retrieval": 68,
            "evidence_aggregation": 76,
            "no_evidence_response": 82,
            "contradiction_analysis": 86,
            "source_ranking": 90,
            "verdict_generation": 94,
            "mistral_summary": 97,
            "conversational_qa": 100,
        }
        self._stage_labels: Dict[str, str] = {
            "content_classification": "Analyzing claims",
            "claim_extraction": "Analyzing claims",
            "claim_normalization": "Analyzing claims",
            "query_rewriting": "Searching sources",
            "retrieval_routing": "Searching sources",
            "tavily_search": "Searching sources",
            "scientific_retrieval": "Searching sources",
            "evidence_aggregation": "Verifying evidence",
            "no_evidence_response": "Preparing report",
            "contradiction_analysis": "Verifying evidence",
            "source_ranking": "Verifying evidence",
            "verdict_generation": "Building report",
            "mistral_summary": "Preparing intelligence",
            "conversational_qa": "Preparing intelligence",
        }
        self._stage_requirements: Dict[str, Dict[str, Any]] = {
            "content_classification": {"required": ["content"]},
            "claim_extraction": {"required": ["content", "audit"]},
            "claim_normalization": {"required": ["claims", "audit"]},
            "query_rewriting": {"required": ["normalized_claims", "content_type", "audit"]},
            "retrieval_routing": {"required": ["content_type", "audit"]},
            "tavily_search": {"required": ["query_plan", "retrieval_plan", "audit"]},
            "scientific_retrieval": {"required": ["query_plan", "retrieval_plan", "content_type", "audit"]},
            "evidence_aggregation": {"required": ["query_plan", "retrieval_plan", "audit"]},
            "no_evidence_response": {"required": ["claims", "query_plan", "retrieval_plan", "audit"]},
            "contradiction_analysis": {"required": ["claims", "evidence_items", "audit"]},
            "source_ranking": {"required": ["evidence_items", "contradiction_result", "audit"]},
            "verdict_generation": {"required": ["contradiction_result", "ranked_sources", "audit"]},
            "mistral_summary": {"required": ["content_type", "normalized_claims", "audit"]},
            "conversational_qa": {"required": ["question", "audit"]},
        }
        self.classifier = ContentClassifier()
        self.claim_extractor = ClaimExtractor()
        self.contradiction_detector = ContradictionDetector()
        self.faiss = FAISSSearch()
        self.tavily = TavilyClient()
        self._embedder = None
        self._text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=80)
        self._graph = self._build_graph()

    @property
    def embedder(self):
        return self._load_embedder()

    def _state_snapshot(self, state: IntelGraphState) -> Dict[str, Any]:
        return {
            "state_keys": sorted(state.keys()),
            "claim_count": len(state.get("claims", [])),
            "normalized_claim_count": len(state.get("normalized_claims", [])),
            "query_count": len(state.get("query_plan", [])),
            "tavily_count": len(state.get("tavily_results", [])),
            "scientific_count": len(state.get("scientific_results", [])),
            "evidence_count": len(state.get("evidence_items", [])),
            "ranked_count": len(state.get("ranked_sources", [])),
            "contradiction_count": len(state.get("contradiction_result", {}).get("contradictions", [])),
        }

    def _validate_stage_state(self, stage_name: str, state: IntelGraphState) -> None:
        requirements = self._stage_requirements.get(stage_name, {})
        required_keys = requirements.get("required", [])
        missing = [key for key in required_keys if key not in state or state.get(key) is None]
        if missing:
            raise RuntimeError(f"{stage_name} missing required state keys: {', '.join(missing)}")

    def _has_grounded_evidence(self, state: IntelGraphState) -> bool:
        ranked_sources = state.get("ranked_sources", [])
        evidence_items = state.get("evidence_items", [])
        return bool(ranked_sources or evidence_items)

    def _build_failure_summary(self, state: IntelGraphState, reason: str) -> str:
        claims = [claim.get("normalized_text") or claim.get("original_text") or "" for claim in state.get("normalized_claims", [])[:5]]
        queries = [claim.get("rewritten_queries", [])[:3] for claim in state.get("query_plan", [])[:5]]
        flat_queries = [query for group in queries for query in group][:8]
        domains = list(state.get("retrieval_plan", {}).get("priority_domains", []))
        retrieval_errors = [f"{item.get('stage')}: {item.get('reason')}" for item in state.get("retrieval_errors", [])[:6]]
        parts = [
            "Intel analysis could not produce a grounded Mistral summary.",
            f"Reason: {reason}",
            f"Claims extracted: {len(state.get('claims', []))}",
        ]
        if claims:
            parts.append("Claims: " + " | ".join(claims))
        if flat_queries:
            parts.append("Rewritten queries: " + " | ".join(flat_queries))
        if domains:
            parts.append("Searched domains: " + ", ".join(domains))
        if retrieval_errors:
            parts.append("Retrieval issues: " + " | ".join(retrieval_errors))
        if self._has_grounded_evidence(state):
            parts.append(f"Retrieved evidence sources: {len(state.get('ranked_sources', [])) or len(state.get('evidence_items', []))}")
        else:
            parts.append("Evidence was insufficient after retrieval attempts.")
        return "\n".join(parts)

    def _load_embedder(self):
        if self._embedder is not None:
            return self._embedder
        from sentence_transformers import SentenceTransformer
        try:
            import yaml
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.yaml")
            with open(config_path, "r", encoding="utf-8") as handle:
                cfg = yaml.safe_load(handle)
            model_name = cfg.get("retrieval", {}).get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
        except Exception:
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info("Loading Intel embedder: %s (forcing CPU)", model_name)
        self._embedder = SentenceTransformer(model_name, device="cpu")
        return self._embedder

    def _topic_overlap(self, claim_text: str, candidate_text: str) -> float:
        claim_terms = set(_claim_terms(claim_text))
        if not claim_terms:
            return 0.0
        candidate_terms = set(re.findall(r"\b[a-zA-Z][a-zA-Z\-]{2,}\b", candidate_text.lower()))
        overlap = len(claim_terms & candidate_terms)
        return overlap / max(len(claim_terms), 1)

    def _score_claim_source(self, claim_text: str, item: Dict[str, Any]) -> float:
        combined_text = " ".join([
            claim_text,
            item.get("title", ""),
            item.get("content", ""),
            item.get("publisher", ""),
            item.get("url", ""),
        ])
        semantic = float(item.get("semantic_score", item.get("similarity_score", 0.0)) or 0.0)
        overlap = self._topic_overlap(claim_text, combined_text)
        publisher = str(item.get("publisher", "")).lower()
        trust_bonus = 0.06 if any(domain in publisher for domain in ["nih", "pubmed", "nature", "science", "reuters", "ap", "bbc", "gov", "thehindu", "indianexpress"]) else 0.0
        query = str(item.get("retrieval_query", "")).lower()
        query_bonus = 0.04 if any(term in query for term in _claim_terms(claim_text)[:4]) else 0.0
        score = (semantic * 0.62) + (overlap * 0.28) + trust_bonus + query_bonus
        if overlap == 0 and semantic < 0.5:
            score -= 0.1
        return round(_clamp(score), 4)

    def _filter_candidate_evidence(self, claim: Dict[str, Any], candidates: List[Dict[str, Any]], *, min_score: Optional[float] = None) -> List[Dict[str, Any]]:
        threshold = self._MIN_EVIDENCE_SCORE if min_score is None else min_score
        filtered: List[Dict[str, Any]] = []
        for candidate in candidates:
            claim_text = claim.get("normalized_text", "")
            combined_text = " ".join([
                claim_text,
                candidate.get("title", ""),
                candidate.get("content", ""),
                candidate.get("publisher", ""),
                candidate.get("url", ""),
            ])
            overlap = self._topic_overlap(claim_text, combined_text)
            if overlap <= 0:
                continue
            score = self._score_claim_source(claim_text, candidate)
            if score < threshold:
                continue
            filtered.append({**candidate, "claim_relevance_score": score})
        filtered.sort(key=lambda item: item.get("claim_relevance_score", 0.0), reverse=True)
        return filtered

    def _build_graph(self):
        graph = StateGraph(IntelGraphState)
        graph.add_node("content_classification", self._node_content_classification)
        graph.add_node("claim_extraction", self._node_claim_extraction)
        graph.add_node("claim_normalization", self._node_claim_normalization)
        graph.add_node("query_rewriting", self._node_query_rewriting)
        graph.add_node("retrieval_routing", self._node_retrieval_routing)
        graph.add_node("tavily_search", self._node_tavily_search)
        graph.add_node("scientific_retrieval", self._node_scientific_retrieval)
        graph.add_node("evidence_aggregation", self._node_evidence_aggregation)
        graph.add_node("no_evidence_response", self._node_no_evidence_response)
        graph.add_node("contradiction_analysis", self._node_contradiction_analysis)
        graph.add_node("source_ranking", self._node_source_ranking)
        graph.add_node("verdict_generation", self._node_verdict_generation)
        graph.add_node("mistral_summary", self._node_mistral_summary)
        graph.add_node("conversational_qa", self._node_conversational_qa)

        graph.set_entry_point("content_classification")
        graph.add_edge("content_classification", "claim_extraction")
        graph.add_edge("claim_extraction", "claim_normalization")
        graph.add_edge("claim_normalization", "query_rewriting")
        graph.add_edge("query_rewriting", "retrieval_routing")
        graph.add_edge("retrieval_routing", "tavily_search")
        graph.add_edge("tavily_search", "scientific_retrieval")
        graph.add_edge("scientific_retrieval", "evidence_aggregation")

        def _after_evidence(state: IntelGraphState) -> str:
            if state.get("evidence_items"):
                return "contradiction_analysis"
            return "no_evidence_response"

        graph.add_conditional_edges(
            "evidence_aggregation",
            _after_evidence,
            {
                "contradiction_analysis": "contradiction_analysis",
                "no_evidence_response": "no_evidence_response",
            },
        )
        
        def _after_summary(state: IntelGraphState) -> str:
            return "conversational_qa" if state.get("mode") == "qa" else END

        graph.add_edge("contradiction_analysis", "source_ranking")
        graph.add_edge("source_ranking", "verdict_generation")
        graph.add_edge("verdict_generation", "mistral_summary")
        graph.add_conditional_edges("mistral_summary", _after_summary, {"conversational_qa": "conversational_qa", END: END})
        
        graph.add_conditional_edges("no_evidence_response", _after_summary, {"conversational_qa": "conversational_qa", END: END})
        
        graph.add_edge("conversational_qa", END)
        return graph.compile()

    def _run_with_retries(self, state: IntelGraphState, stage_name: str, fn, retries: int = 2) -> IntelGraphState:
        audit = state["audit"]
        last_error: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                self._validate_stage_state(stage_name, state)
                audit.log_event(stage_name, "stage input validated", attempt=attempt, **self._state_snapshot(state))
                progress_callback = state.get("progress_callback")
                if callable(progress_callback):
                    progress_callback(self._stage_progress.get(stage_name, 0), self._stage_labels.get(stage_name, stage_name.replace("_", " ")))
                with audit.stage(stage_name) as stage_record:
                    stage_record["attempt"] = attempt
                    started = _now_ms()
                    result = fn(state)
                    stage_record["returned_keys"] = sorted(result.keys())
                    stage_record["status"] = "success"
                    stage_record["duration_ms"] = round(_now_ms() - started, 2)
                    if callable(progress_callback):
                        progress_callback(self._stage_progress.get(stage_name, 0), self._stage_labels.get(stage_name, stage_name.replace("_", " ")))
                    return {**state, **result}
            except Exception as exc:
                last_error = exc
                audit.record_failure(stage_name, str(exc), attempt=attempt)
                logger.warning("Intel stage failed stage=%s attempt=%d/%d reason=%s", stage_name, attempt, retries, exc)
                progress_callback = state.get("progress_callback")
                if callable(progress_callback):
                    progress_callback(self._stage_progress.get(stage_name, 0), f"{self._stage_labels.get(stage_name, stage_name.replace('_', ' '))} failed")
                if attempt < retries:
                    audit.log_event(stage_name, "retrying", attempt=attempt + 1)
                    time.sleep(0.2 * attempt)
        raise RuntimeError(f"{stage_name} failed after {retries} attempts: {last_error}") from last_error

    def analyze(self, content: str, *, content_type_override: Optional[str] = None, progress_callback: Optional[Any] = None, file_path: Optional[str] = None) -> Dict[str, Any]:
        audit = PipelineAuditTrail()
        
        def _update_status(msg: str):
            if progress_callback:
                progress_callback(5, msg)
            logger.info(f"Media Ingestion: {msg}")

        original_content = content
        transcript = None
        is_url = content.strip().startswith(("http://", "https://"))
        is_fallback = False
        
        from backend.services.media_pipeline import MediaPipeline
        media_pipeline = MediaPipeline()

        if file_path:
            # ── LOCAL FILE FLOW ─────────────────────────────────────────────
            _update_status("Processing local video forensics...")
            transcript = media_pipeline.ingest_file(file_path, _update_status)
            if transcript:
                content = transcript
                audit.log_event("media_ingestion", "Local media transcribed", transcript_chars=len(transcript))
            else:
                logger.error("Local media ingestion failed")
                raise ValueError("Could not extract transcript from the uploaded video file.")
        
        elif is_url:
            from backend.utils.web import is_video_platform_url, fetch_url_text
            
            if is_video_platform_url(content):
                # ── VIDEO URL FLOW ─────────────────────────────────────────────
                _update_status("Downloading video media...")
                transcript = media_pipeline.ingest_url(content, _update_status)
                
                if transcript:
                    if self._is_boilerplate_content(transcript):
                        logger.warning("Ingested transcript contains only boilerplate, using metadata fallback")
                        is_fallback = True
                        content = self._extract_url_metadata_context(content)
                    else:
                        content = transcript
                        audit.log_event("media_ingestion", "Remote media transcribed", transcript_chars=len(transcript))
                else:
                    logger.warning("Media ingestion failed, using metadata fallback")
                    is_fallback = True
                    content = self._extract_url_metadata_context(content)
            else:
                # ── ARTICLE URL FLOW ───────────────────────────────────────────
                _update_status("Extracting article text...")
                fetched_text = fetch_url_text(content)
                if fetched_text:
                    if self._is_boilerplate_content(fetched_text):
                        logger.warning("Article text is boilerplate, using title fallback")
                        content = self._extract_url_metadata_context(content)
                        is_fallback = True
                    else:
                        content = fetched_text
                        audit.log_event("content_extraction", "Article text extracted", text_chars=len(fetched_text))
                else:
                    content = self._extract_url_metadata_context(content)
                    is_fallback = True

        state: IntelGraphState = {
            "mode": "analysis",
            "trace_id": audit.trace_id,
            "audit": audit,
            "content": content,
            "question": "",
            "retrieval_errors": [],
            "progress_callback": progress_callback,
            "is_fallback": is_fallback,
            "original_url": original_content if is_url else "",
        }
        
        if transcript:
            state["transcript"] = transcript

        logger.info("Intel analysis started trace_id=%s chars=%d fallback=%s", audit.trace_id, len(content), is_fallback)
        if content_type_override:
            state["content_type"] = {"type": content_type_override, "confidence": 1.0, "reasoning": "override"}
        
        final_state = self._graph.invoke(state)
        final_state["pipeline_trace"] = audit.finish()
        
        if is_url:
            final_state["originalContent"] = original_content
            
        return self._format_analysis_response(final_state)

    def _extract_url_metadata_context(self, url: str) -> str:
        """Extract title and available metadata from a URL as fallback context."""
        from backend.services.media_downloader import MediaDownloader
        downloader = MediaDownloader()
        
        logger.info("Extracting metadata context for: %s", url)
        info = downloader.get_info(url)
        
        if info:
            title = info.get("title", "")
            description = info.get("description", "")
            uploader = info.get("uploader", "")
            
            context_parts = []
            if title: context_parts.append(f"Title: {title}")
            if uploader: context_parts.append(f"Source/Uploader: {uploader}")
            if description: 
                # Clean description of links/noise
                clean_desc = re.sub(r'https?://\S+', '', description).strip()
                context_parts.append(f"Context: {clean_desc[:500]}")
            
            return " | ".join(context_parts)
            
        # Hard fallback: semantic components of the URL itself
        clean_url = url.replace("https://", "").replace("http://", "").replace("www.", "")
        url_context = " ".join(re.split(r'[/.\-_]', clean_url))
        return f"URL Intelligence: {url_context}"

    def _is_boilerplate_content(self, text: str) -> bool:
        """Check if the extracted text is just platform boilerplate."""
        if not text or len(text.strip()) < 50:
            return True
        
        boilerplate_indicators = [
            "About Press Copyright", "Contact us Creator", "Advertise Developers", 
            "Terms Privacy Policy", "Safety How YouTube works", "Test new features",
            "© 2024 Google LLC", "Cookies & Privacy", "All rights reserved"
        ]
        
        # If too many indicators are found, it's boilerplate
        matches = sum(1 for indicator in boilerplate_indicators if indicator in text)
        return matches >= 2

    def answer(self, content: str, question: str, evidence: Optional[List[Dict[str, Any]]] = None, verification_result: Optional[Dict[str, Any]] = None, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
        audit = PipelineAuditTrail()
        state: IntelGraphState = {
            "mode": "qa",
            "trace_id": audit.trace_id,
            "audit": audit,
            "content": content,
            "question": question,
            "retrieval_errors": [],
            "progress_callback": progress_callback,
        }
        if evidence:
            state["evidence_items"] = evidence
            state["ranked_sources"] = evidence
        
        if verification_result:
            state["summary"] = verification_result.get("summary", "")
            
            # Handle both nested and flat verdict formats
            verdict_data = verification_result.get("verdict")
            if isinstance(verdict_data, dict):
                state["verdict"] = verdict_data
            else:
                state["verdict"] = {
                    "label": verification_result.get("verdict_label"), 
                    "confidence": verification_result.get("verdict_score", 0.5) / 100.0
                }
            
            state["contradiction_result"] = verification_result.get("contradiction_result", {})

        logger.info("Intel QA started trace_id=%s question_chars=%d", audit.trace_id, len(question))
        final_state = self._graph.invoke(state)
        final_state["pipeline_trace"] = audit.finish()
        return self._format_qa_response(final_state)

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    def _node_content_classification(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            existing = local_state.get("content_type", {})
            if existing.get("type"):
                return {"content_type": existing}
            classification = self.classifier.classify(local_state["content"])
            logger.info("Intel classification type=%s confidence=%.2f", classification.get("type"), classification.get("confidence", 0.0))
            local_state["audit"].log_event("content_classification", "classification complete", classification=classification)
            return {"content_type": classification}
        return self._run_with_retries(state, "content_classification", _impl)

    def _node_claim_extraction(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("claims"):
                return {"claims": local_state["claims"]}
            claim_result = self.claim_extractor.extract(local_state["content"], audit=local_state["audit"])
            claims = claim_result.get("claims", [])
            logger.info("Intel claim extraction produced %d claims", len(claims))
            if not claims:
                local_state["retrieval_errors"].append({"stage": "claim_extraction", "reason": "No atomic claims extracted"})
            return {
                "claims": claims,
                "retrieval_errors": local_state.get("retrieval_errors", []),
                "claims_meta": claim_result,
            }
        return self._run_with_retries(state, "claim_extraction", _impl)

    def _node_claim_normalization(self, state: IntelGraphState) -> Dict[str, Any]:
        def _normalize_claim(claim: Dict[str, Any], idx: int) -> Dict[str, Any]:
            text = re.sub(r"\s+", " ", claim.get("text", "")).strip()
            lower = text.lower()
            claim_kind = claim.get("type", "factual")
            if any(token in lower for token in ["might", "may", "could", "possibly", "suggests", "appears", "seems"]):
                claim_kind = "speculative"
            elif any(token in lower for token in ["i think", "i believe", "opinion", "in my view", "seems to me"]):
                claim_kind = "opinion"
            elif any(token in lower for token in ["study", "research", "peer-reviewed", "journal", "neuroscience", "biology", "behavior"]):
                claim_kind = "scientific"

            keywords = [token for token in re.findall(r"\b[a-zA-Z][a-zA-Z\-]{2,}\b", lower) if token not in _STOPWORDS]
            return {
                "claim_id": f"claim-{idx + 1}",
                "original_text": text,
                "normalized_text": text,
                "claim_kind": claim_kind,
                "keywords": keywords[:10],
                "claim_type": claim.get("type", "factual"),
                "confidence": claim.get("confidence", 0.6),
            }

        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("normalized_claims"):
                return {"normalized_claims": local_state["normalized_claims"]}
            claims = local_state.get("claims", [])
            normalized = [_normalize_claim(claim, idx) for idx, claim in enumerate(claims)]
            local_state["audit"].log_event("claim_normalization", "claims normalized", normalized_claims=normalized)
            logger.info("Intel claim normalization completed count=%d", len(normalized))
            return {"normalized_claims": normalized}

        return self._run_with_retries(state, "claim_normalization", _impl)

    def _rewrite_claim(self, claim: Dict[str, Any], content_type: Dict[str, Any]) -> List[str]:
        text = claim.get("normalized_text", claim.get("original_text", ""))
        lower = text.lower()
        keywords = claim.get("keywords", [])
        content_kind = (content_type.get("type") or "other").lower()

        for patterns, queries in _CLAIM_TOPIC_RULES:
            if any(token in lower for token in patterns):
                return queries[:3]

        joined = " ".join(keywords[:5]) if keywords else text
        base = re.sub(r"\s+", " ", joined).strip()
        if content_kind in {"scientific", "educational"}:
            return [
                f"{base} research",
                f"{base} study",
                f"{base} peer reviewed evidence",
            ]
        if content_kind in {"breaking news", "misinformation", "political claim", "social post", "conspiracy"}:
            return [
                f"{base} source",
                f"{base} official statement",
                f"{base} fact check",
            ]
        return [f"{base} evidence", f"{base} research"]

    def _node_query_rewriting(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("query_plan"):
                return {"query_plan": local_state["query_plan"]}
            content_type = local_state.get("content_type", {})
            normalized_claims = local_state.get("normalized_claims", [])
            query_plan: List[Dict[str, Any]] = []
            for claim in normalized_claims:
                rewritten = self._rewrite_claim(claim, content_type)
                query_plan.append({
                    **claim,
                    "rewritten_queries": rewritten,
                    "primary_query": rewritten[0],
                })
            logger.info("Intel query rewriting produced %d claim plans", len(query_plan))
            local_state["audit"].log_event(
                "query_rewriting",
                "queries rewritten",
                original_claims=[claim.get("normalized_text", "") for claim in normalized_claims],
                query_plan=query_plan,
            )
            return {"query_plan": query_plan}

        return self._run_with_retries(state, "query_rewriting", _impl)

    def _domain_targets(self, content_type: Dict[str, Any]) -> Dict[str, Any]:
        kind = (content_type.get("type") or "other").lower()
        if kind in {"scientific", "educational"}:
            return {
                "mode": "scientific",
                "priority_domains": [
                    "nih.gov", "pubmed.ncbi.nlm.nih.gov", "nature.com", "science.org", 
                    "sciencedirect.com", "scientificamerican.com", "newscientist.com"
                ],
                "fact_check": False,
            }
        if kind in {"breaking news", "misinformation"}:
            return {
                "mode": "news",
                "priority_domains": ["reuters.com", "apnews.com", "bbc.com", "thehindu.com", "indianexpress.com", "aljazeera.com"],
                "fact_check": True,
            }
        if kind in {"political claim"}:
            return {
                "mode": "political",
                "priority_domains": ["reuters.com", "apnews.com", "bbc.com", "gov", "whitehouse.gov", "tribuneindia.com"],
                "fact_check": True,
            }
        if kind in {"social post", "conspiracy"}:
            return {
                "mode": "social", 
                "priority_domains": ["snopes.com", "politifact.com", "factcheck.org", "reuters.com", "apnews.com"],
                "fact_check": True,
            }
        return {
            "mode": "general",
            "priority_domains": ["reuters.com", "apnews.com", "bbc.com", "npr.org"],
            "fact_check": True,
        }

    def _node_retrieval_routing(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("retrieval_plan"):
                return {"retrieval_plan": local_state["retrieval_plan"]}
            content_type = local_state.get("content_type", {})
            retrieval_plan = self._domain_targets(content_type)
            local_state["audit"].log_event("retrieval_routing", "retrieval routed", retrieval_plan=retrieval_plan)
            logger.info("Intel retrieval routing mode=%s domains=%s", retrieval_plan["mode"], retrieval_plan["priority_domains"])
            return {"retrieval_plan": retrieval_plan}

        return self._run_with_retries(state, "retrieval_routing", _impl)

    def _search_tavily_for_claim(self, claim: Dict[str, Any], retrieval_plan: Dict[str, Any], audit: PipelineAuditTrail, existing_queries: set[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        domains = retrieval_plan.get("priority_domains", [])
        
        search_depth = "basic"
        content_kind = retrieval_plan.get("mode", "general")
        if content_kind in ["social", "political"]:
            search_depth = "advanced"

        for query in claim.get("rewritten_queries", [])[:2]: 
            query_hash = hashlib.sha1(query.lower().strip().encode()).hexdigest()
            if query_hash in existing_queries:
                continue
            existing_queries.add(query_hash)

            try:
                audit.log_event("tavily_search", "Tavily query dispatched", query=query, domains=domains)
                started = time.perf_counter()
                
                raw = run_tavily_search(
                    query, 
                    max_results=2, 
                    audit=audit, 
                    include_domains=domains
                )
                raw = raw or []
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                
                logger.info("Tavily query=%r results=%d latency=%.2fms", query, len(raw), latency_ms)
                
                for item in raw:
                    results.append({
                        "claim_id": claim["claim_id"],
                        "claim_text": claim["normalized_text"],
                        "retrieval_query": query,
                        "source": "tavily",
                        "publisher": item.get("url", "").split("/")[2] if item.get("url") and "/" in item.get("url", "") else item.get("source", "Web"),
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "url": item.get("url", ""),
                        "similarity_score": item.get("score", 0.5),
                    })
                
                trusted_count = sum(1 for r in results if any(td in r.get("publisher", "").lower() for td in ["reuters.com", "apnews.com", "bbc.com", "tribuneindia.com", "thehindu.com"]))
                if trusted_count >= 2:
                    break

            except Exception as exc:
                audit.record_failure("tavily_search", f"Tavily query failed: {exc}", query=query)
        
        return results

    def _node_tavily_search(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("tavily_results") or local_state.get("evidence_items"):
                return {"tavily_results": local_state.get("tavily_results", [])}
            
            retrieval_plan = local_state.get("retrieval_plan", {})
            query_plan = local_state.get("query_plan", [])
            tavily_results: List[Dict[str, Any]] = []
            processed_queries: set[str] = set()
            domain_counts: Dict[str, int] = {}
            
            for claim in query_plan[:3]:
                claim_results = self._search_tavily_for_claim(claim, retrieval_plan, local_state["audit"], processed_queries)
                claim_results = self._filter_candidate_evidence(claim, claim_results)
                
                for res in claim_results:
                    domain = res.get("publisher", "").lower()
                    if domain_counts.get(domain, 0) < 2:
                        tavily_results.append(res)
                        domain_counts[domain] = domain_counts.get(domain, 0) + 1
                
                if len(tavily_results) >= 5:
                    break

            tavily_results = _dedupe_preserve_order(tavily_results, key_fields=("url", "title", "content"))
            return {"tavily_results": tavily_results}

        return self._run_with_retries(state, "tavily_search", _impl)

    def _search_scientific_sources(self, claim: Dict[str, Any], retrieval_plan: Dict[str, Any], audit: PipelineAuditTrail) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        query = claim.get("primary_query") or claim.get("rewritten_queries", [claim.get("normalized_text", "")])[0]
        try:
            local_hits = self.faiss.search(query, k=5)
            for hit in local_hits:
                results.append({
                    "claim_id": claim["claim_id"],
                    "claim_text": claim["normalized_text"],
                    "retrieval_query": query,
                    "source": "vector_local",
                    "publisher": hit.get("source", "Local Corpus"),
                    "title": hit.get("title", ""),
                    "content": hit.get("claim", hit.get("content", "")),
                    "url": hit.get("url", ""),
                    "similarity_score": hit.get("similarity_score", 0.0),
                })
        except Exception as exc:
            logger.warning("Scientific vector retrieval failed query=%r reason=%s", query, exc)

        if retrieval_plan.get("mode") == "scientific":
            try:
                scientific_domains = retrieval_plan.get("priority_domains", [])
                raw = run_tavily_search(query, max_results=2, include_domains=scientific_domains)
                for item in raw or []:
                    results.append({
                        "claim_id": claim["claim_id"],
                        "claim_text": claim["normalized_text"],
                        "retrieval_query": query,
                        "source": "tavily_scientific",
                        "publisher": item.get("url", "").split("/")[2] if item.get("url") and "/" in item.get("url", "") else item.get("source", "Scientific Web"),
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "url": item.get("url", ""),
                        "similarity_score": item.get("score", 0.5),
                    })
            except Exception as exc:
                logger.warning("Scientific Tavily retrieval failed query=%r reason=%s", query, exc)

        return results

    def _node_scientific_retrieval(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("scientific_results") or local_state.get("evidence_items"):
                return {"scientific_results": local_state.get("scientific_results", [])}
            content_type = local_state.get("content_type", {})
            retrieval_plan = local_state.get("retrieval_plan", {})
            query_plan = local_state.get("query_plan", [])
            scientific_results: List[Dict[str, Any]] = []
            if (content_type.get("type") or "").lower() in {"scientific", "educational"}:
                for claim in query_plan:
                    claim_results = self._search_scientific_sources(claim, retrieval_plan, local_state["audit"])
                    claim_results = self._filter_candidate_evidence(claim, claim_results)
                    scientific_results.extend(claim_results)
            
            scientific_results = _dedupe_preserve_order(scientific_results, key_fields=("url", "title", "content"))
            return {"scientific_results": scientific_results}

        return self._run_with_retries(state, "scientific_retrieval", _impl)

    def _node_evidence_aggregation(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("claim_evidence_map") and local_state.get("evidence_items"):
                return {
                    "evidence_items": local_state["evidence_items"],
                    "evidence_graph": local_state.get("evidence_graph", []),
                    "claim_evidence_map": local_state["claim_evidence_map"]
                }
            candidates = local_state.get("tavily_results", []) + local_state.get("scientific_results", [])
            if not candidates and local_state.get("evidence_items"):
                candidates = list(local_state.get("evidence_items", []))
            
            aggregated: List[Dict[str, Any]] = []
            edges: List[Dict[str, Any]] = []
            for item in candidates:
                aggregated.append({
                    **item,
                    "evidence_id": hashlib.sha1(f"{item.get('url','')}|{item.get('title','')}".encode("utf-8", errors="ignore")).hexdigest()[:16],
                    "relation": item.get("relation", "uncertain"),
                    "evidence_type": item.get("source", "unknown"),
                })
                edges.append({
                    "claim_id": item.get("claim_id"),
                    "evidence_id": aggregated[-1]["evidence_id"],
                    "relation": aggregated[-1]["relation"],
                })
            aggregated = _dedupe_preserve_order(aggregated, key_fields=("evidence_id", "url", "title"))
            claim_evidence_map: Dict[str, List[Dict[str, Any]]] = {}
            for item in aggregated:
                claim_id = item.get("claim_id", "")
                claim_evidence_map.setdefault(claim_id, []).append(item)
            
            return {"evidence_items": aggregated, "evidence_graph": edges, "claim_evidence_map": claim_evidence_map}

        return self._run_with_retries(state, "evidence_aggregation", _impl)

    def _node_no_evidence_response(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("verdict"):
                return {"verdict": local_state["verdict"]}
            
            has_transcript = bool(local_state.get("transcript"))
            reason = "No corroborated external OSINT evidence found. Analysis proceeding based on internal signals."
            
            verdict = {
                "label": "unverified",
                "credibility_score": 30.0 if has_transcript else 0.0,
                "authenticity_score": 30.0 if has_transcript else 0.0,
                "confidence": 0.1,
                "reason": reason,
                "verdict": "Insufficient Evidence",
                "supporting_count": 0,
                "contradicting_count": 0,
                "neutral_count": 0,
            }
            return {
                "verdict": verdict,
                "analysis": {"evidence_summary": reason, "no_evidence": True},
                "contradiction_result": {
                    "supporting_count": 0, "contradicting_count": 0, "neutral_count": 0,
                    "credibility_score": 30.0 if has_transcript else 0.0,
                    "evidence_summary": reason, "contradictions": [],
                },
                "ranked_sources": [],
            }

        return self._run_with_retries(state, "no_evidence_response", _impl)

    def _node_contradiction_analysis(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("contradiction_result"):
                return {"contradiction_result": local_state["contradiction_result"]}
            claims = local_state.get("claims", [])
            evidence_payload = {"evidence_pieces": local_state.get("evidence_items", [])}
            result = self.contradiction_detector.analyze(claims, evidence_payload, audit=local_state["audit"])
            return {"contradiction_result": result}

        return self._run_with_retries(state, "contradiction_analysis", _impl)

    def _node_source_ranking(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("ranked_sources"):
                return {"ranked_sources": local_state["ranked_sources"]}
            evidence = list(local_state.get("evidence_items", []))
            contradiction_result = local_state.get("contradiction_result", {})
            contradictions = {
                (item.get("claim_id"), item.get("evidence_id"), item.get("url")): item for item in contradiction_result.get("contradictions", [])
            }

            ranked: List[Dict[str, Any]] = []
            for item in evidence:
                key = (item.get("claim_id"), item.get("evidence_id"), item.get("url"))
                relation = contradictions.get(key, {}).get("relation", item.get("relation", "uncertain"))
                source_cred = contradictions.get(key, {}).get("source_credibility", 0.35)
                similarity = float(item.get("semantic_score", item.get("similarity_score", 0.0)))
                relation_bonus = 0.18 if relation == "entailment" else -0.22 if relation == "contradiction" else 0.0
                credibility_bonus = (source_cred - 0.5) * 0.35
                final_score = _clamp(0.45 + similarity * 0.4 + relation_bonus + credibility_bonus)
                ranked.append({
                    **item,
                    "relation": relation,
                    "source_credibility": source_cred,
                    "ranking_score": round(final_score, 4),
                })
            ranked.sort(key=lambda x: x.get("ranking_score", 0.0), reverse=True)
            return {"ranked_sources": ranked}

        return self._run_with_retries(state, "source_ranking", _impl)

    def _node_verdict_generation(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("verdict"):
                return {"verdict": local_state["verdict"]}
            contradiction_result = local_state.get("contradiction_result", {})
            ranked = local_state.get("ranked_sources", [])
            supporting = contradiction_result.get("supporting_count", 0)
            contradicting = contradiction_result.get("contradicting_count", 0)
            neutral = contradiction_result.get("neutral_count", 0)

            if not ranked:
                score = 30.0 if bool(local_state.get("transcript")) else 0.0
                verdict = {
                    "label": "unverified", "credibility_score": score, "authenticity_score": score,
                    "verdict": "Insufficient Evidence", "confidence": 0.0,
                    "reason": "No external OSINT evidence retrieved."
                }
            else:
                score = float(contradiction_result.get("credibility_score", 50.0))
                if score <= 20: label = "fake_news"
                elif score <= 40: label = "misleading"
                elif score <= 60: label = "mixed_evidence"
                elif score <= 80: label = "likely_true"
                else: label = "verified"

                from backend.detectors.base import BaseDetector
                verdict_text = BaseDetector.interpret_credibility(score)
                verdict = {
                    "label": label, "credibility_score": score, "authenticity_score": score,
                    "verdict": verdict_text, "confidence": round(abs(score - 50) / 50, 3),
                    "reason": contradiction_result.get("evidence_summary", ""),
                    "supporting_count": supporting, "contradicting_count": contradicting, "neutral_count": neutral,
                }
            return {"verdict": verdict}

        return self._run_with_retries(state, "verdict_generation", _impl)

    def _node_mistral_summary(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            if local_state.get("summary"):
                return {"summary": local_state["summary"]}
            
            evidence = local_state.get("ranked_sources", [])[:5]
            has_transcript = bool(local_state.get("transcript"))
            
            if not evidence and not has_transcript:
                return {"summary": self._build_failure_summary(local_state, "No evidence and no transcript found.")}

            contradiction = local_state.get("contradiction_result", {})
            content_type = local_state.get("content_type", {}).get("type", "other")
            claim_lines = [f"- {claim.get('normalized_text')}" for claim in local_state.get("normalized_claims", [])[:8]]
            evidence_lines = [f"- [{item.get('relation', 'uncertain')}] {item.get('publisher', 'Unknown')}: {item.get('title', '')[:120]}" for item in evidence]
            
            source_type = "video investigation" if has_transcript else f"{content_type} article"
            is_fallback = state.get("is_fallback", False)
            
            prompt = f"""You are a senior forensic OSINT analyst at TRUTH X. Provide a cinematic, structured intelligence summary of the {source_type}.

{'NOTE: Full transcript unavailable. Analysis based on metadata/signals.' if is_fallback else ''}
{'NOTE: No external OSINT verified. Based on internal forensic reasoning.' if not evidence else ''}

STRUCTURE:
**🧠 EXECUTIVE SUMMARY**
**🔍 KEY FINDINGS**
**⚠ CONTRADICTIONS & DISCREPANCIES**
**📚 SUPPORTING EVIDENCE**
**✅ FINAL VERDICT**

CONTEXT:
{"Transcript: " + local_state.get('transcript', '')[:2500] if has_transcript else "Type: " + content_type}
Claims: {chr(10).join(claim_lines) or '- none'}
Intelligence: {chr(10).join(evidence_lines) or '- none'}
Discrepancies: {contradiction.get('evidence_summary', '')}
"""
            messages = [{"role": "system", "content": "You write structured intelligence reports."}, {"role": "user", "content": prompt}]
            summary = run_mistral_chat(messages, audit=local_state["audit"], stage="mistral_summary")
            return {"summary": summary.strip() if summary else "Inconclusive analysis."}

        return self._run_with_retries(state, "mistral_summary", _impl)

    def _node_conversational_qa(self, state: IntelGraphState) -> Dict[str, Any]:
        def _impl(local_state: IntelGraphState) -> Dict[str, Any]:
            question = local_state.get("question", "").strip()
            if not question: return {"qa_answer": {"answer": "No question provided.", "sources_cited": [], "confidence": 0.0}}
            summary = local_state.get("summary", "")
            verdict = local_state.get("verdict", {})
            evidence = local_state.get("ranked_sources", []) or local_state.get("evidence_items", [])
            evidence_blocks = [f"SOURCE [{i+1}]: {item.get('publisher')}\nTITLE: {item.get('title')}\nCONTENT: {str(item.get('content'))[:300]}" for i, item in enumerate(evidence[:10])]
            
            evidence_str = "---\n".join(evidence_blocks)
            prompt = f"""Answer based ONLY on context: {question}

Summary: {summary}
Verdict: {verdict.get('label')}

Evidence:
{evidence_str}"""
            messages = [{"role": "system", "content": "Concise investigative assistant."}, {"role": "user", "content": prompt}]
            response = run_mistral_chat(messages, temperature=0.3, audit=local_state["audit"], stage="contextual_qa")
            return {"qa_answer": {"answer": response.strip() if response else "No answer available.", "sources_cited": [e.get("publisher") for e in evidence[:3]], "confidence": 0.8}}

        return self._run_with_retries(state, "conversational_qa", _impl)

    def _format_evidence(self, ranked_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{
            "title": item.get("title", ""), "source": item.get("publisher", "Unknown"),
            "url": item.get("url", ""), "snippet": (item.get("content", "") or "")[:240],
            "relation": item.get("relation", "uncertain"), "credibility": item.get("source_credibility"),
            "ranking_score": item.get("ranking_score", 0.0), "claim_id": item.get("claim_id"),
        } for item in ranked_sources[:12]]

    def _format_analysis_response(self, state: IntelGraphState) -> Dict[str, Any]:
        ranked = state.get("ranked_sources", [])
        contradiction = state.get("contradiction_result", {})
        return {
            "status": "success", "content_type": state.get("content_type", {}),
            "claims": state.get("normalized_claims", []), "sources_analyzed": len(ranked),
            "evidence": self._format_evidence(ranked), "analysis": contradiction,
            "summary": state.get("summary", ""), "verdict": state.get("verdict", {}),
            "pipeline_trace": state.get("pipeline_trace", {}), "is_fallback": state.get("is_fallback", False),
            "originalContent": state.get("original_url", "") if state.get("is_fallback") else state.get("content", ""),
        }

    def _format_qa_response(self, state: IntelGraphState) -> Dict[str, Any]:
        qa_answer = state.get("qa_answer", {})
        return {
            "status": "success", "question": state.get("question", ""), "answer": qa_answer.get("answer", ""),
            "sources": qa_answer.get("sources_cited", []), "confidence": qa_answer.get("confidence", 0.0),
        }
