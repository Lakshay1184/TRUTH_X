"""truth.x — Unified Explainability Engine.

Aggregates explainability signals from all modalities into a
professional, trustworthy report format.

Generates:
    - Overall credibility reasons
    - Per-modality breakdowns
    - Suspicious indicator summaries
    - Human-readable explanations
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.utils.logger import logger
from backend.explainability.mistral_reasoner import MistralReasoner


# ─── Severity ordering ───────────────────────────────────────────────────

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class ExplainabilityEngine:
    """Cross-modal explainability aggregator."""

    def explain(
        self,
        video_result: Optional[Dict[str, Any]] = None,
        audio_result: Optional[Dict[str, Any]] = None,
        text_result: Optional[Dict[str, Any]] = None,
        image_result: Optional[Dict[str, Any]] = None,
        news_verification: Optional[Dict[str, Any]] = None,
        manipulation_signals: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate unified explainability report.

        Returns:
            {
                "overall_reasons": [sorted list of most important reasons],
                "per_modality": {
                    "video": {...},
                    "audio": {...},
                    "text": {...},
                    "image": {...},
                    "news": {...},
                },
                "suspicious_indicators": [list of high/critical indicators],
                "credibility_factors": {
                    "positive": [...],
                    "negative": [...],
                },
                "intelligence_report": str,
            }
        """
        all_reasons: List[Dict[str, Any]] = []
        per_modality: Dict[str, Any] = {}
        positive_factors: List[str] = []
        negative_factors: List[str] = []

        # ── Video explainability ──
        if video_result:
            video_reasons = self._extract_video_reasons(video_result)
            all_reasons.extend(video_reasons)
            per_modality["video"] = {
                "analyzed": True,
                "label": video_result.get("label", "unknown"),
                "confidence": video_result.get("confidence", 0),
                "reasons": video_reasons,
            }
            self._classify_factor(video_result, "video", positive_factors, negative_factors)

        # ── Audio explainability ──
        if audio_result and not audio_result.get("error"):
            audio_reasons = self._extract_audio_reasons(audio_result)
            all_reasons.extend(audio_reasons)
            per_modality["audio"] = {
                "analyzed": True,
                "label": audio_result.get("label", "unknown"),
                "confidence": audio_result.get("confidence", 0),
                "reasons": audio_reasons,
            }
            self._classify_factor(audio_result, "audio", positive_factors, negative_factors)

        # ── Text explainability ──
        if text_result:
            text_reasons = self._extract_text_reasons(text_result)
            all_reasons.extend(text_reasons)
            per_modality["text"] = {
                "analyzed": True,
                "label": text_result.get("label", "unknown"),
                "confidence": text_result.get("confidence", 0),
                "reasons": text_reasons,
            }
            self._classify_factor(text_result, "text", positive_factors, negative_factors)

        # ── Image explainability ──
        if image_result:
            image_reasons = self._extract_reasons_from_result(image_result, "image")
            all_reasons.extend(image_reasons)
            per_modality["image"] = {
                "analyzed": True,
                "label": image_result.get("label", "unknown"),
                "confidence": image_result.get("confidence", 0),
                "reasons": image_reasons,
            }
            self._classify_factor(image_result, "image", positive_factors, negative_factors)

        # ── News verification explainability ──
        if news_verification:
            news_reasons = self._extract_news_reasons(news_verification)
            all_reasons.extend(news_reasons)
            per_modality["news"] = {
                "analyzed": True,
                "verdict": news_verification.get("verdict", "Unverified"),
                "credibility_score": news_verification.get("credibility_score", 50),
                "reasons": news_reasons,
            }

        # ── Manipulation signals ──
        if manipulation_signals:
            for sig in manipulation_signals:
                all_reasons.append({
                    "indicator": sig.get("type", "manipulation_signal"),
                    "severity": "medium",
                    "detail": sig.get("detail", ""),
                    "evidence": "",
                    "modality": "text",
                })
                negative_factors.append(sig.get("detail", "Manipulation pattern detected"))

        # Sort reasons by severity
        all_reasons.sort(key=lambda r: _SEVERITY_ORDER.get(r.get("severity", "low"), 3))

        # Extract high/critical indicators
        suspicious = [
            r["indicator"] for r in all_reasons
            if r.get("severity") in ("high", "critical")
        ]

        logger.info("Explainability: %d reasons, %d suspicious indicators",
                     len(all_reasons), len(suspicious))

        intelligence_report = ""
        if os.environ.get("MISTRAL_REASONING_ENABLED", "").lower() in ("1", "true", "yes"):
            reasoner = MistralReasoner()
            intelligence_report = reasoner.generate_report({
                "overall_reasons": all_reasons[:10],
                "suspicious_indicators": list(set(suspicious)),
                "per_modality_labels": {k: v.get("label") for k, v in per_modality.items()},
            })
        else:
            logger.info("Mistral explainability reasoning skipped (MISTRAL_REASONING_ENABLED is not enabled)")

        return {
            "overall_reasons": all_reasons[:10],  # Top 10 most important
            "per_modality": per_modality,
            "suspicious_indicators": list(set(suspicious)),
            "credibility_factors": {
                "positive": positive_factors,
                "negative": negative_factors,
            },
            "intelligence_report": intelligence_report,
        }

    # ── Video reasons ─────────────────────────────────────────────────────

    def _extract_video_reasons(self, result: Dict) -> List[Dict]:
        reasons = []

        # 1. From explicit explainability field (new detector style)
        reasons.extend(self._extract_reasons_from_result(result, "video"))

        # 2. Temporal Transformer Signals (VideoMAE)
        temporal_score = result.get("temporal_anomaly_score")
        if temporal_score is not None:
            if temporal_score > 0.8:
                reasons.append({
                    "indicator": "temporal_transformer_anomaly",
                    "severity": "critical",
                    "detail": "Critical temporal inconsistency detected by VideoMAE Transformer.",
                    "evidence": f"Anomaly Score: {temporal_score:.4f}",
                    "modality": "video",
                })
            elif temporal_score > 0.6:
                reasons.append({
                    "indicator": "temporal_instability",
                    "severity": "high",
                    "detail": "Significant frame-to-frame coherence deviation detected.",
                    "evidence": f"Anomaly Score: {temporal_score:.4f}",
                    "modality": "video",
                })

        # 3. Biometric Landmark Anomalies
        landmark_score = result.get("landmark_anomaly_score")
        if landmark_score is not None and landmark_score > 0.6:
            reasons.append({
                "indicator": "biometric_inconsistency",
                "severity": "high",
                "detail": "Abnormal facial landmark geometry or blinking patterns detected.",
                "evidence": f"Biometric Score: {landmark_score:.4f}",
                "modality": "video",
            })

        # 4. Fallback Observability
        if result.get("fallback_active"):
            reasons.append({
                "indicator": "detector_fallback",
                "severity": "low",
                "detail": "VideoMAE inference offline, using secondary heuristic detection.",
                "evidence": result.get("debug_info", {}).get("fallback_reason", "Unknown error"),
                "modality": "video",
            })

        return reasons

    # ── Audio reasons ─────────────────────────────────────────────────────

    def _extract_audio_reasons(self, result: Dict) -> List[Dict]:
        reasons = self._extract_reasons_from_result(result, "audio")

        spectral = result.get("spectral_features", {})
        if spectral:
            flatness = spectral.get("spectral_flatness", 0)
            if flatness > 0.01:
                reasons.append({
                    "indicator": "high_spectral_flatness",
                    "severity": "medium",
                    "detail": "High spectral flatness indicates possible synthetic audio",
                    "evidence": f"Spectral flatness: {flatness:.6f} (threshold: 0.01)",
                    "modality": "audio",
                })

            mfcc_std = spectral.get("mfcc_std", 10)
            if mfcc_std < 5:
                reasons.append({
                    "indicator": "uniform_mfcc",
                    "severity": "medium",
                    "detail": "Unusually consistent MFCC features — typical of synthetic audio",
                    "evidence": f"MFCC std: {mfcc_std:.4f} (natural speech: >5.0)",
                    "modality": "audio",
                })

        # Segment inconsistency
        segments = result.get("segments", [])
        if len(segments) > 2:
            seg_probs = [s.get("fake_probability", 0.5) for s in segments]
            import numpy as np
            seg_std = float(np.std(seg_probs))
            if seg_std > 0.2:
                reasons.append({
                    "indicator": "segment_inconsistency",
                    "severity": "high",
                    "detail": "High variance in audio segment analysis — possible splicing",
                    "evidence": f"Segment std: {seg_std:.4f}",
                    "modality": "audio",
                })

        return reasons

    # ── Text reasons ──────────────────────────────────────────────────────

    def _extract_text_reasons(self, result: Dict) -> List[Dict]:
        reasons = self._extract_reasons_from_result(result, "text")

        ai_prob = result.get("ai_probability", 0)
        if ai_prob > 0.7:
            reasons.append({
                "indicator": "high_ai_probability",
                "severity": "high" if ai_prob > 0.85 else "medium",
                "detail": f"Text analysis indicates {ai_prob:.0%} probability of AI generation",
                "evidence": f"Model: RoBERTa-based Neural Classifier (ChatGPT Detection)",
                "modality": "text",
            })

        # Enhanced analysis signals
        enhanced = result.get("enhanced_analysis", {})
        if enhanced:
            perplexity = enhanced.get("perplexity_score", 0)
            if perplexity > 0.6:
                reasons.append({
                    "indicator": "low_perplexity",
                    "severity": "medium",
                    "detail": "Low text perplexity — AI-generated text is more predictable",
                    "evidence": f"Perplexity score: {perplexity:.3f}",
                    "modality": "text",
                })

            burstiness = enhanced.get("burstiness_score", 0)
            if burstiness > 0.6:
                reasons.append({
                    "indicator": "low_burstiness",
                    "severity": "medium",
                    "detail": "Low burstiness — text lacks natural variation in sentence structure",
                    "evidence": f"Burstiness score: {burstiness:.3f}",
                    "modality": "text",
                })

            stylometric = enhanced.get("stylometric_score", 0)
            if stylometric > 0.6:
                reasons.append({
                    "indicator": "uniform_style",
                    "severity": "low",
                    "detail": "Uniform linguistic patterns suggest machine-generated text",
                    "evidence": f"Stylometric score: {stylometric:.3f}",
                    "modality": "text",
                })

        return reasons

    # ── News reasons ──────────────────────────────────────────────────────

    def _extract_news_reasons(self, verification: Dict) -> List[Dict]:
        reasons = []
        contradictions = verification.get("contradictions", [])

        for c in contradictions:
            if c.get("relation") == "contradiction":
                reasons.append({
                    "indicator": "contradicts_trusted_source",
                    "severity": "high" if c.get("confidence", 0) > 0.7 else "medium",
                    "detail": c.get("explanation", "Contradicts trusted source reporting"),
                    "evidence": f"Source: {c.get('source', 'Unknown')} | {c.get('evidence', '')[:100]}",
                    "modality": "news",
                })

        verdict = verification.get("verdict", "")
        if verdict in ("Likely False", "Misleading"):
            reasons.append({
                "indicator": "low_credibility_verdict",
                "severity": "critical" if verdict == "Likely False" else "high",
                "detail": f"Fact-check verdict: {verdict}",
                "evidence": verification.get("evidence_summary", ""),
                "modality": "news",
            })

        return reasons

    # ── Generic reason extraction ─────────────────────────────────────────

    @staticmethod
    def _extract_reasons_from_result(result: Dict, modality: str) -> List[Dict]:
        """Extract reasons from the explainability field of a result."""
        explainability = result.get("explainability", {})
        reasons = explainability.get("reasons", [])
        for r in reasons:
            r.setdefault("modality", modality)
        return reasons

    @staticmethod
    def _classify_factor(
        result: Dict, modality: str,
        positive: List[str], negative: List[str],
    ) -> None:
        label = result.get("label", "").lower()
        confidence = result.get("confidence", 0)
        name_map = {
            "video": "Video Analysis",
            "audio": "Audio Analysis",
            "text": "Text Analysis",
            "image": "Image Analysis",
        }
        name = name_map.get(modality, modality.capitalize())

        if label in ("real", "authentic", "human-written") and confidence > 0.6:
            positive.append(f"{name}: {label} ({confidence:.0%} confidence)")
        elif label in ("fake", "ai-generated", "deepfake") and confidence > 0.5:
            negative.append(f"{name}: {label} ({confidence:.0%} confidence)")
