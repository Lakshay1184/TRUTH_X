"""truth.x — Contradiction Detector for RAG Fake News Pipeline.

Uses NLI (Natural Language Inference) to detect whether evidence
supports, contradicts, or is neutral toward a claim.

Primary: HF Inference API (facebook/bart-large-mnli)
Fallback: Local keyword-based heuristic
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import json
import os
import re
from typing import Any, Dict, List, Optional

from backend.utils.logger import logger
from backend.services.mistral_client import run_mistral_chat


# ─── Trusted source credibility weights ──────────────────────────────────

_SOURCE_CREDIBILITY = {
    "reuters": 0.95,
    "associated press": 0.95,
    "ap news": 0.95,
    "bbc": 0.90,
    "bbc news": 0.90,
    "the guardian": 0.85,
    "new york times": 0.85,
    "washington post": 0.85,
    "snopes": 0.90,
    "factcheck.org": 0.90,
    "politifact": 0.90,
    "afp fact check": 0.90,
    "full fact": 0.88,
    "alt news": 0.85,
    "boom live": 0.85,
    "the quint": 0.80,
    "who": 0.92,
    "cdc": 0.90,
    "nih": 0.90,
}


class ContradictionDetector:
    """Detects contradictions between claims and evidence using NLI."""

    def __init__(self, nli_model: str = "facebook/bart-large-mnli") -> None:
        self.nli_model = nli_model
        logger.info("ContradictionDetector initialized (NLI=%s)", nli_model)

    def analyze(
        self,
        claims: List[Dict[str, Any]],
        evidence: Dict[str, Any],
        audit=None,
    ) -> Dict[str, Any]:
        """Analyze claims against evidence for contradictions.

        Args:
            claims: List of claim dicts from ClaimExtractor
            evidence: Evidence dict from EvidenceRetriever

        Returns:
            {
                "contradictions": [{
                    "claim": str,
                    "evidence": str,
                    "relation": "contradiction" | "entailment" | "neutral",
                    "confidence": float,
                    "source": str,
                    "explanation": str,
                }],
                "verdict": str,
                "credibility_score": int (0-100),
                "evidence_summary": str,
                "supporting_count": int,
                "contradicting_count": int,
                "neutral_count": int,
            }
        """
        evidence_pieces = evidence.get("evidence_pieces", [])
        if not claims or not evidence_pieces:
            logger.info(
                "Contradiction analysis skipped claims=%d evidence=%d",
                len(claims),
                len(evidence_pieces),
            )
            if audit is not None:
                audit.log_event(
                    "contradiction_analysis",
                    "Skipped due to insufficient claims or evidence",
                    claim_count=len(claims),
                    evidence_count=len(evidence_pieces),
                )
            return self._no_evidence_result(claims)

        analyses = []
        supporting = 0
        contradicting = 0
        neutral = 0
        started = time.perf_counter()
        if audit is not None:
            audit.log_event(
                "contradiction_analysis",
                "Contradiction analysis started",
                claim_count=len(claims),
                evidence_count=len(evidence_pieces),
            )

        for claim in claims:
            claim_text = claim.get("text", "")
            if not claim_text:
                continue

            # Check each evidence piece against this claim
            for ev in evidence_pieces:
                if ev.get("claim_text", "") != claim_text:
                    continue

                ev_content = ev.get("content", ev.get("title", ""))
                if not ev_content:
                    continue

                # 1. Try Mistral LLM reasoning first
                relation, confidence = None, 0.0
                if os.environ.get("MISTRAL_API_KEY"):
                    logger.info("Contradiction analysis attempting Mistral reasoning claim=%r evidence_source=%s", claim_text[:120], ev.get("publisher", "Unknown"))
                    relation, confidence = self._llm_classify(claim_text, ev_content)
                
                # 2. Try NLI via HF API if LLM didn't work
                if relation is None:
                    logger.info("Contradiction analysis using HF NLI fallback claim=%r evidence_source=%s", claim_text[:120], ev.get("publisher", "Unknown"))
                    relation, confidence = self._nli_classify(claim_text, ev_content)

                # 3. Fallback to heuristic if APIs unavailable
                if relation is None:
                    logger.warning("Contradiction analysis fallback to heuristic source=%s", ev.get("publisher", "Unknown"))
                    relation, confidence = self._heuristic_classify(claim_text, ev_content, ev)

                # Weight by source credibility
                source_name = ev.get("publisher", "").lower()
                source_cred = _SOURCE_CREDIBILITY.get(source_name, 0.35)

                explanation = self._generate_explanation(
                    relation, confidence, claim_text, ev_content,
                    ev.get("publisher", "Unknown Source"),
                )

                analyses.append({
                    "claim_id": ev.get("claim_id", ""),
                    "claim": claim_text[:200],
                    "evidence": ev_content[:300],
                    "relation": relation,
                    "confidence": round(confidence, 3),
                    "source": ev.get("publisher", "Unknown"),
                    "source_credibility": source_cred,
                    "url": ev.get("url", ""),
                    "evidence_id": ev.get("evidence_id", ""),
                    "explanation": explanation,
                })

                if relation == "entailment":
                    supporting += 1
                elif relation == "contradiction":
                    contradicting += 1
                else:
                    neutral += 1

                if audit is not None:
                    audit.log_event(
                        "contradiction_analysis",
                        "Claim-evidence relation classified",
                        claim=claim_text[:200],
                        source=ev.get("publisher", "Unknown"),
                        relation=relation,
                        confidence=round(confidence, 3),
                    )

        # Compute credibility score
        credibility = self._compute_credibility(
            supporting, contradicting, neutral, claims, analyses,
        )

        # Determine verdict
        verdict = self._determine_verdict(credibility, supporting, contradicting, neutral)

        # Generate evidence summary
        summary = self._generate_summary(analyses, verdict, credibility)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        logger.info("Contradiction analysis: verdict=%s, credibility=%d, S=%d/C=%d/N=%d",
                     verdict, credibility, supporting, contradicting, neutral)
        logger.info("Contradiction analysis complete latency_ms=%.2f analyses=%d", elapsed_ms, len(analyses))
        if audit is not None:
            audit.log_event(
                "contradiction_analysis",
                "Contradiction analysis complete",
                verdict=verdict,
                credibility_score=credibility,
                supporting_count=supporting,
                contradicting_count=contradicting,
                neutral_count=neutral,
                latency_ms=elapsed_ms,
            )

        return {
            "contradictions": analyses,
            "verdict": verdict,
            "credibility_score": credibility,
            "evidence_summary": summary,
            "supporting_count": supporting,
            "contradicting_count": contradicting,
            "neutral_count": neutral,
        }

    # ── LLM Classification (Mistral API) ──────────────────────────────────
    
    def _llm_classify(self, premise: str, hypothesis: str) -> tuple[Optional[str], float]:
        """Classify claim-evidence relation using LLM reasoning."""
        messages = [
            {
                "role": "system",
                "content": "You are a fact-checking intelligence system. Compare the CLAIM against the EVIDENCE. Does the evidence support, contradict, or is it neutral/insufficient regarding the claim? Return ONLY a JSON object with keys 'relation' (strictly one of: 'entailment', 'contradiction', 'neutral') and 'confidence' (float 0-1)."
            },
            {
                "role": "user",
                "content": f"CLAIM: {premise}\nEVIDENCE: {hypothesis}"
            }
        ]
        
        try:
            response = run_mistral_chat(messages, response_format={"type": "json_object"})
            if response:
                try:
                    data = json.loads(response)
                    rel = data.get("relation", "").lower()
                    conf = float(data.get("confidence", 0.0))
                    if rel in ("entailment", "contradiction", "neutral"):
                        return rel, conf
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
        except Exception as e:
            logger.debug("LLM relation classification failed: %s", e)
            
        return None, 0.0

    # ── NLI Classification (HF API) ──────────────────────────────────────

    def _nli_classify(self, premise: str, hypothesis: str) -> tuple[Optional[str], float]:
        """Classify claim-evidence relation using NLI model via HF API."""
        try:
            from backend.services.hf_inference import run_hf_inference

            result = run_hf_inference(
                self.nli_model,
                {
                    "inputs": premise[:500],
                    "parameters": {
                        "candidate_labels": [
                            "This claim is supported by evidence",
                            "This claim is contradicted by evidence",
                            "There is not enough evidence",
                        ],
                    },
                },
            )

            if result and isinstance(result, dict) and "labels" in result:
                labels = result["labels"]
                scores = result["scores"]
                label_scores = dict(zip(labels, scores))

                best_label = labels[0]  # Highest score
                best_score = scores[0]

                if "supported" in best_label.lower():
                    return "entailment", best_score
                elif "contradicted" in best_label.lower():
                    return "contradiction", best_score
                else:
                    return "neutral", best_score

        except Exception as e:
            logger.debug("NLI API call failed: %s", e)

        return None, 0.0

    # ── Heuristic Fallback ────────────────────────────────────────────────

    def _heuristic_classify(
        self, claim: str, evidence: str, ev_meta: Dict,
    ) -> tuple[str, float]:
        """Rule-based contradiction detection when NLI API is unavailable."""
        claim_lower = claim.lower()
        ev_lower = evidence.lower()

        # Check if evidence has a verdict
        verdict = ev_meta.get("verdict", "").lower()
        if verdict:
            if any(w in verdict for w in ("false", "fake", "misleading", "incorrect", "wrong", "pants on fire")):
                return "contradiction", 0.80
            elif any(w in verdict for w in ("true", "correct", "accurate", "verified")):
                return "entailment", 0.75
            elif any(w in verdict for w in ("mixed", "partly", "partial", "half")):
                return "neutral", 0.60

        # Negation detection
        negation_words = {"not", "no", "never", "neither", "nobody", "nothing", "nowhere",
                          "don't", "doesn't", "didn't", "won't", "isn't", "aren't", "wasn't"}

        claim_has_neg = any(w in claim_lower.split() for w in negation_words)
        ev_has_neg = any(w in ev_lower.split() for w in negation_words)

        # If one has negation and the other doesn't → likely contradiction
        if claim_has_neg != ev_has_neg:
            # Check if they're about the same topic (word overlap)
            claim_words = set(claim_lower.split())
            ev_words = set(ev_lower.split())
            overlap = len(claim_words & ev_words) / max(len(claim_words), 1)
            if overlap > 0.3:
                return "contradiction", 0.65

        # High word overlap → likely entailment
        claim_words = set(re.findall(r'\b\w{4,}\b', claim_lower))
        ev_words = set(re.findall(r'\b\w{4,}\b', ev_lower))
        if claim_words:
            overlap = len(claim_words & ev_words) / len(claim_words)
            if overlap > 0.5:
                return "entailment", 0.55

        return "neutral", 0.4

    # ── Credibility Scoring ───────────────────────────────────────────────

    def _compute_credibility(
        self,
        supporting: int,
        contradicting: int,
        neutral: int,
        claims: List[Dict],
        analyses: List[Dict],
    ) -> int:
        """Compute credibility score (0–100)."""
        credibility = 100.0

        # Contradiction penalty (weighted by source credibility)
        for a in analyses:
            if a["relation"] == "contradiction":
                source_cred = a.get("source_credibility", 0.35)
                penalty = 30 * source_cred * a["confidence"]
                credibility -= penalty

        # No evidence penalty
        if not analyses:
            credibility -= 30

        # Supporting evidence bonus
        for a in analyses:
            if a["relation"] == "entailment":
                source_cred = a.get("source_credibility", 0.35)
                bonus = 10 * source_cred * a["confidence"]
                credibility = min(100, credibility + bonus)

        # Emotional manipulation penalty (from claims metadata)
        for claim in claims:
            if claim.get("type") == "absolute":
                credibility -= 5

        return max(0, min(100, int(credibility)))

    # ── Verdict Determination ─────────────────────────────────────────────

    @staticmethod
    def _determine_verdict(
        credibility: int, supporting: int, contradicting: int, neutral: int,
    ) -> str:
        """Map credibility score to verdict category."""
        total = supporting + contradicting + neutral
        if total == 0:
            return "unverified"
        # Use label-first categories: supported / partially_supported / limited_evidence / contradicted
        if credibility >= 75:
            return "supported"
        elif credibility >= 55:
            return "partially_supported"
        elif credibility >= 40:
            return "limited_evidence"
        else:
            return "contradicted"

    # ── Explanation Generation ────────────────────────────────────────────

    @staticmethod
    def _generate_explanation(
        relation: str, confidence: float,
        claim: str, evidence: str, source: str,
    ) -> str:
        """Generate human-readable explanation for a claim-evidence pair."""
        if relation == "contradiction":
            return f"Contradicts reporting from {source} — evidence suggests the claim is inaccurate ({confidence:.0%} confidence)"
        elif relation == "entailment":
            return f"Supported by {source} — evidence corroborates this claim ({confidence:.0%} confidence)"
        else:
            return f"Insufficient evidence from {source} to verify this claim"

    @staticmethod
    def _generate_summary(analyses: List[Dict], verdict: str, credibility: int) -> str:
        """Generate overall evidence summary."""
        if not analyses:
            return "No relevant evidence found in trusted sources. This claim could not be verified."

        contradictions = [a for a in analyses if a["relation"] == "contradiction"]
        supports = [a for a in analyses if a["relation"] == "entailment"]

        parts = []
        if contradictions:
            sources = list(set(a["source"] for a in contradictions))
            parts.append(f"Contradicted by {', '.join(sources[:3])}")
        if supports:
            sources = list(set(a["source"] for a in supports))
            parts.append(f"Supported by {', '.join(sources[:3])}")

        summary = ". ".join(parts) + "." if parts else ""
        summary += f" Overall credibility: {credibility}/100 ({verdict})."

        return summary

    # ── No evidence result ────────────────────────────────────────────────

    @staticmethod
    def _no_evidence_result(claims: List[Dict]) -> Dict[str, Any]:
        return {
            "contradictions": [],
            "verdict": "unverified",
            "credibility_score": 0,
            "evidence_summary": "No grounded evidence was retrieved for this claim. Retrieval diagnostics should be consulted.",
            "supporting_count": 0,
            "contradicting_count": 0,
            "neutral_count": 0,
        }
