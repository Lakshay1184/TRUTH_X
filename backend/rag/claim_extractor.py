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

    def extract(self, text: str) -> Dict[str, Any]:
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
            return {
                "claims": [], "manipulation_signals": [],
                "emotional_score": 0.0, "claim_count": 0,
            }

        claims = []
        signals = []

        # Try Mistral LLM extraction first if enabled
        if os.environ.get("MISTRAL_API_KEY"):
            llm_claims = self._extract_with_mistral(text)
            if llm_claims:
                claims = llm_claims

        # Fallback to rule-based extraction
        if not claims:
            sentences = self._split_sentences(text)
            for sent in sentences:
                claim = self._analyze_sentence(sent)
                if claim:
                    claims.append(claim)

        # Detect manipulation signals
        signals.extend(self._detect_urgency(text))
        signals.extend(self._detect_absolutes(text))
        signals.extend(self._detect_emotional_manipulation(text))
        signals.extend(self._detect_medical_claims(text))

        # Emotional score (0 = neutral, 1 = highly emotional/manipulative)
        emotional_score = min(1.0, len(signals) * 0.15)

        logger.info("Claim extraction: %d claims, %d signals, emotional=%.2f",
                     len(claims), len(signals), emotional_score)

        return {
            "claims": claims,
            "manipulation_signals": signals,
            "emotional_score": round(emotional_score, 3),
            "claim_count": len(claims),
        }

    # ── LLM extraction ────────────────────────────────────────────────────

    def _extract_with_mistral(self, text: str) -> List[Dict[str, Any]]:
        """Use Mistral to extract complex assertive claims."""
        messages = [
            {
                "role": "system",
                "content": "You are a factual claim extraction system. Extract 1 to 5 assertive, testable claims from the provided text. Return ONLY a JSON array of objects with keys: 'text' (the claim), 'type' (e.g., 'statistical', 'medical', 'political', 'causal'), and 'confidence' (float 0-1)."
            },
            {
                "role": "user",
                "content": text[:1000]
            }
        ]
        
        try:
            response = run_mistral_chat(
                messages, 
                response_format={"type": "json_object"}
            )
            if response:
                # The response_format json_object requires the output to be a JSON object,
                # so we expect {"claims": [...]} or we parse what we get.
                try:
                    data = json.loads(response)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("claims", data.get("result", []))
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
        if len(s) < 15:  # Too short to be meaningful
            return None

        # Skip questions
        if s.endswith("?"):
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
