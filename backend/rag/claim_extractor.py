"""truth.x — Claim Extractor for RAG Fake News Pipeline.

Extracts assertive claims from user-submitted text for
fact-checking against trusted sources.

Approach: rule-based NLP (no model download needed).
    - Sentence splitting
    - Declarative statement detection
    - Superlative/absolute claim flagging
    - Emotional manipulation markers
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List

from backend.utils.logger import logger
from backend.services.mistral_client import run_mistral_chat

# ─── Emotional / Manipulative Markers ────────────────────────────────────

_URGENCY_WORDS = {
    "breaking", "urgent", "alert", "emergency", "warning", "shocking",
    "bombshell", "explosive", "developing", "just in", "must see",
    "you won't believe", "share before deleted",
}

_ABSOLUTE_WORDS = {
    "always", "never", "every", "all", "none", "no one", "everyone",
    "impossible", "guaranteed", "proven", "100%", "absolutely",
    "completely", "totally", "entirely", "definitely", "undeniably",
}

_SUPERLATIVE_PATTERNS = [
    r"\b(best|worst|greatest|largest|smallest|most|least|fastest|strongest)\b",
    r"\b(cure[sd]?|heal[sd]?|eliminat[ed]?|eradicat[ed]?|destroy[sd]?)\b.*\b(cancer|disease|virus|covid)\b",
    r"\b(secret|hidden|suppressed|banned|censored)\b",
]

_EMOTIONAL_PATTERNS = [
    r"\b(outrag|scandal|disgrac|horrif|terrif|devastat)\w*\b",
    r"!{2,}",  # Multiple exclamation marks
    r"\b(they don'?t want you to know|the truth about|exposed|revealed)\b",
    r"\b(wake up|open your eyes|sheep|sheeple)\b",
]

_MEDICAL_CLAIM_PATTERNS = [
    r"\b(cure[sd]?|treat[sd]?|heal[sd]?|prevent[sd]?)\b.*\b(cancer|diabetes|covid|disease|virus|illness)\b",
    r"\b(doctor[s]?|scientist[s]?|expert[s]?)\b.*\b(don'?t want|hide|suppress|refuse)\b",
    r"\b(miracle|breakthrough|revolutionary)\b.*\b(drug|treatment|cure|remedy)\b",
]


class ClaimExtractor:
    """Extracts factual claims and manipulation signals from text."""

    def extract(self, text: str, audit=None) -> Dict[str, Any]:
        """Extract claims and meta-signals from input text.

        Returns:
            {
                "claims": [{"text": ..., "type": ..., "confidence": ...}],
                "manipulation_signals": [{"type": ..., "detail": ...}],
                "emotional_score": float (0-1),
                "claim_count": int,
            }
        """
        if not text or not text.strip():
            if audit is not None:
                audit.log_event("claim_extraction", "Empty input received; no claims extracted")
            return {
                "claims": [], "manipulation_signals": [],
                "emotional_score": 0.0, "claim_count": 0,
            }

        claims = []
        signals = []
        started = time.perf_counter()
        logger.info("Claim extraction started chars=%d mistral_enabled=%s", len(text), bool(os.environ.get("MISTRAL_API_KEY")))
        
        # Increase limit to capture more transcript depth (e.g. intro noise removal)
        processed_text = text[:5000]

        # Try Mistral LLM extraction first if enabled
        if os.environ.get("MISTRAL_API_KEY"):
            llm_claims = self._extract_with_mistral(processed_text, audit=audit)
            if llm_claims:
                # Hard limit to 5 claims
                claims = llm_claims[:5]
                logger.info("Claim extraction Mistral path returned %d claims (limited to 5)", len(claims))
        
        # Fallback to rule-based extraction
        if not claims:
            sentences = self._split_sentences(processed_text)
            for sent in sentences:
                claim = self._analyze_sentence(sent)
                if claim:
                    claims.append(claim)
                if len(claims) >= 5: # Hard limit
                    break

        # --- Contextual Reasoning Fallback ---
        # If still no claims but text exists, extract broader semantic blocks
        if not claims and processed_text.strip():
            logger.info("No atomic claims found; generating contextual semantic blocks for analysis")
            # Take first 3 paragraphs or significant segments
            segments = [p.strip() for p in processed_text.split('\n\n') if len(p.strip()) > 60][:3]
            if not segments:
                # Fallback to first few sentences
                sentences = self._split_sentences(processed_text)[:3]
                segments = sentences
            
            for seg in segments:
                claims.append({
                    "text": seg[:300], # Cap segment length
                    "type": "contextual_reasoning",
                    "confidence": 0.5,
                })
            
            logger.info("Contextual fallback produced %d reasoning blocks", len(claims))

        # Detect manipulation signals
        signals.extend(self._detect_urgency(text))
        signals.extend(self._detect_absolutes(text))
        signals.extend(self._detect_emotional_manipulation(text))
        signals.extend(self._detect_medical_claims(text))

        # Emotional score
        emotional_score = min(1.0, len(signals) * 0.15)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        
        logger.info(
            "Claim extraction complete | claims=%d | signals=%d | emotional=%.2f | latency=%.2fms",
            len(claims), len(signals), emotional_score, elapsed_ms
        )
        
        return {
            "claims": claims,
            "manipulation_signals": signals,
            "emotional_score": round(emotional_score, 3),
            "claim_count": len(claims),
        }

    # ── LLM extraction ────────────────────────────────────────────────────

    def _extract_with_mistral(self, text: str, audit=None) -> List[Dict[str, Any]]:
        """Use Mistral to extract high-value assertive claims."""
        messages = [
            {
                "role": "system",
                "content": "You are a senior forensic analyst. Extract max 5 primary, testable, factual or statistical claims from the text. IGNORE filler, opinion, transitions, or emotional commentary. Return ONLY a JSON object with a 'claims' array of objects (text, type, confidence)."
            },
            {
                "role": "user",
                "content": text
            }
        ]
        
        try:
            response = run_mistral_chat(
                messages, 
                response_format={"type": "json_object"},
                audit=audit,
                stage="claim_extraction_mistral",
            )
            if response:
                try:
                    data = json.loads(response)
                    claims = data.get("claims", [])
                    if isinstance(claims, list):
                        return claims
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("Mistral claim extraction failed: %s", e)
        return []

    # ── Sentence splitting ────────────────────────────────────────────────

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences using regex."""
        # Handle common abbreviations
        text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs)\.\s', r'\1<PERIOD> ', text)
        sentences = re.split(r'[.!?]+\s+', text)
        sentences = [s.replace('<PERIOD>', '.').strip() for s in sentences if s.strip()]
        return sentences

    # ── Sentence analysis ─────────────────────────────────────────────────

    def _analyze_sentence(self, sentence: str) -> Dict[str, Any] | None:
        """Analyze a sentence and classify it as a claim if assertive."""
        s = sentence.strip()
        if len(s) < 20:  # Increased minimum length for meaningful claims
            return None

        # Skip questions
        if s.endswith("?"):
            return None

        # --- Boilerplate Filtering ---
        boilerplate_terms = [
            "Press Copyright", "Contact us", "Terms Privacy", "Safety How", 
            "YouTube works", "Test new features", "Google LLC", "Policy & Safety"
        ]
        if any(term in s for term in boilerplate_terms):
            logger.debug("Filtered out boilerplate claim candidate: %r", s[:100])
            return None

        # Detect claim type
        claim_type = "factual"
        confidence = 0.6

        # Check for statistical/numerical claims
        if re.search(r'\d+\s*(%|percent|million|billion|thousand)', s, re.I):
            claim_type = "statistical"
            confidence = 0.8

        # Check for attribution ("according to", "sources say")
        if re.search(r'\b(according to|sources?\s+say|report[s]?\s+show|stud(?:y|ies)\s+show)\b', s, re.I):
            claim_type = "attributed"
            confidence = 0.75

        # Check for causal claims ("causes", "leads to", "results in")
        if re.search(r'\b(cause[sd]?|lead[s]?\s+to|result[s]?\s+in|prevent[s]?|cure[sd]?)\b', s, re.I):
            claim_type = "causal"
            confidence = 0.85

        # Check for absolute/superlative claims
        lower = s.lower()
        if any(w in lower for w in _ABSOLUTE_WORDS):
            claim_type = "absolute"
            confidence = 0.9

        return {
            "text": s,
            "type": claim_type,
            "confidence": confidence,
        }

    # ── Signal detection ──────────────────────────────────────────────────

    @staticmethod
    def _detect_urgency(text: str) -> List[Dict[str, str]]:
        signals = []
        lower = text.lower()
        for word in _URGENCY_WORDS:
            if word in lower:
                signals.append({
                    "type": "urgency_language",
                    "detail": f"Urgency marker detected: '{word}'",
                })
        return signals

    @staticmethod
    def _detect_absolutes(text: str) -> List[Dict[str, str]]:
        signals = []
        lower = text.lower()
        found = [w for w in _ABSOLUTE_WORDS if w in lower]
        if found:
            signals.append({
                "type": "absolute_claims",
                "detail": f"Absolute language detected: {', '.join(found[:3])}",
            })
        return signals

    @staticmethod
    def _detect_emotional_manipulation(text: str) -> List[Dict[str, str]]:
        signals = []
        for pattern in _EMOTIONAL_PATTERNS:
            if re.search(pattern, text, re.I):
                signals.append({
                    "type": "emotional_manipulation",
                    "detail": f"Emotional manipulation pattern detected",
                })
                break  # One is enough
        return signals

    @staticmethod
    def _detect_medical_claims(text: str) -> List[Dict[str, str]]:
        signals = []
        for pattern in _MEDICAL_CLAIM_PATTERNS:
            if re.search(pattern, text, re.I):
                signals.append({
                    "type": "unverified_medical_claim",
                    "detail": "Unverified medical or health claim detected",
                })
                break
        return signals
