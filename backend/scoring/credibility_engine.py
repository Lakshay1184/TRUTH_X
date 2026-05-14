"""truth.x — Credibility Scoring Engine (UPGRADED).

Computes a unified credibility score (0–100) using Anomaly Amplification
and Confidence Calibration to prevent "neutral score collapse" (clustering at 50%).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from backend.utils.logger import logger


class CredibilityEngine:
    """Computes cross-modal credibility score with Anomaly Amplification."""

    # Default weights per modality
    DEFAULT_WEIGHTS = {
        "video": 0.40,
        "audio": 0.15,
        "image": 0.15,
        "text": 0.10,
        "news": 0.20,
    }

    def __init__(self) -> None:
        try:
            from backend.detectors.video_detector import _load_config
            self.config = _load_config()
            self.weights = self.config.get("credibility", {}).get("weights", self.DEFAULT_WEIGHTS)
        except Exception:
            self.weights = self.DEFAULT_WEIGHTS

    def compute(
        self,
        video_result: Optional[Dict[str, Any]] = None,
        audio_result: Optional[Dict[str, Any]] = None,
        text_result: Optional[Dict[str, Any]] = None,
        image_result: Optional[Dict[str, Any]] = None,
        news_verification: Optional[Dict[str, Any]] = None,
        manipulation_signals: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provenance_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute unified credibility score using Anomaly Amplification.

        Philosophy: High-confidence suspicious signals dominate the final score
        instead of being diluted by averaging.
        """
        scores: Dict[str, float] = {}
        factors: List[Dict[str, Any]] = []
        flags: List[Dict[str, str]] = []

        # 1. Collect per-modality authenticity (0=Fake, 100=Real)
        if video_result and video_result.get("label") != "unknown":
            video_auth = self._result_to_authenticity(video_result)
            scores["video"] = video_auth
            factors.append({"modality": "video", "authenticity": round(video_auth, 1), "label": video_result.get("label", "")})
            if video_auth < 45:
                flags.append({
                    "label": "Video Deepfake Anomaly",
                    "detail": f"Confidence: {video_result.get('confidence', 0):.0%} (Temporal Anomaly: {video_result.get('temporal_anomaly_score', 0):.2f})",
                    "severity": "critical" if video_auth < 20 else "high",
                })

        if audio_result and not audio_result.get("error"):
            audio_auth = self._result_to_authenticity(audio_result)
            scores["audio"] = audio_auth
            factors.append({"modality": "audio", "authenticity": round(audio_auth, 1), "label": audio_result.get("label", "")})
            if audio_auth < 45:
                flags.append({
                    "label": "Synthetic Audio Patterns",
                    "detail": f"Confidence: {audio_result.get('confidence', 0):.0%}",
                    "severity": "high",
                })

        if text_result:
            text_auth = self._text_to_authenticity(text_result)
            scores["text"] = text_auth
            factors.append({"modality": "text", "authenticity": round(text_auth, 1), "label": text_result.get("label", "")})
            if text_auth < 35:
                flags.append({
                    "label": "AI Text Signature",
                    "detail": f"Probability: {text_result.get('ai_probability', 0):.0%}",
                    "severity": "high",
                })

        if image_result:
            image_auth = self._result_to_authenticity(image_result)
            scores["image"] = image_auth
            factors.append({"modality": "image", "authenticity": round(image_auth, 1), "label": image_result.get("label", "")})
            if image_auth < 45:
                flags.append({
                    "label": "AI Image Artifacts",
                    "detail": f"Confidence: {image_result.get('confidence', 0):.0%}",
                    "severity": "high",
                })

        if news_verification:
            news_score = news_verification.get("credibility_score", 50)
            scores["news"] = float(news_score)
            verdict = news_verification.get("verdict", "Unverified")
            factors.append({"modality": "news", "authenticity": news_score, "label": verdict})
            if news_score < 40:
                flags.append({
                    "label": f"Factual Contradiction: {verdict}",
                    "detail": news_verification.get("evidence_summary", "")[:100],
                    "severity": "critical" if news_score < 25 else "high",
                })

        # 2. Base Metadata Penalties
        meta_penalty = self._compute_metadata_penalty(metadata, flags) if metadata else 0

        # 3. Final Scoring with ANOMALY AMPLIFICATION
        if not scores:
            final_score = 50.0 - meta_penalty
        else:
            # ANOMALY AMPLIFICATION LOGIC:
            # If any modality is highly suspicious (< 40 auth), it drags the whole score down.
            
            min_auth = min(scores.values())
            avg_auth = sum(scores.values()) / len(scores)
            
            if min_auth < 40:
                # Suspension mode: Minimum score dominates (70% weight to anomaly)
                final_score = (min_auth * 0.7) + (avg_auth * 0.3)
                logger.info("Anomaly Amplification Active: min=%0.1f, avg=%0.1f -> final=%0.1f", min_auth, avg_auth, final_score)
            else:
                # Normal mode: Weighted average using configured weights
                active_weights = {k: self.weights.get(k, 0.1) for k in scores}
                total_w = sum(active_weights.values())
                normalized = {k: v / total_w for k, v in active_weights.items()}
                final_score = sum(scores[k] * normalized[k] for k in scores)

            # Apply metadata penalty
            final_score -= meta_penalty

        # 4. CONFIDENCE CALIBRATION (Push away from 50%)
        calibrated_score = self._calibrate(final_score)

        # 5. Manipulation signals & Provenance
        if manipulation_signals:
            for sig in manipulation_signals:
                calibrated_score -= 5
                flags.append({"label": f"Manipulation Signal: {sig.get('type')}", "detail": sig.get("detail", ""), "severity": "medium"})

        if provenance_result and provenance_result.get("confidence", 0) > 0.4:
            prov_penalty = provenance_result.get("confidence", 0) * 35
            calibrated_score -= prov_penalty
            flags.append({
                "label": "AI Generation Fingerprint",
                "detail": f"Origin: {provenance_result.get('likely_origin')} ({provenance_result.get('confidence'):.0%})",
                "severity": "critical",
            })

        final_score_int = max(0, min(100, int(round(calibrated_score))))
        risk_level = self._risk_level(final_score_int)
        verdict = self._verdict(final_score_int)

        logger.info("Scoring Finalized: raw=%0.1f, calibrated=%d, risk=%s", final_score, final_score_int, risk_level)

        return {
            "score": final_score_int,
            "risk_level": risk_level,
            "verdict": verdict,
            "per_modality_scores": {k: round(v, 1) for k, v in scores.items()},
            "contributing_factors": factors,
            "flags": flags,
            "flag_count": len(flags),
            "provenance": provenance_result or {},
        }

    @staticmethod
    def _calibrate(s: float) -> float:
        """Push scores away from the 50% neutral zone using a non-linear scaling."""
        x = (s - 50.0) / 50.0
        sign = 1 if x >= 0 else -1
        calibrated_x = sign * (abs(x) ** 0.85) 
        return (calibrated_x * 50.0) + 50.0

    @staticmethod
    def _result_to_authenticity(result: Dict) -> float:
        """Convert detector result to authenticity score (0=Fake, 100=Real)."""
        fake_prob = result.get("fake_probability")
        if fake_prob is not None:
            return (1.0 - float(fake_prob)) * 100.0

        label = str(result.get("label", "")).lower()
        confidence = float(result.get("confidence", 0.5))
        if label in ("fake", "deepfake", "ai-generated", "spoof", "manipulated"):
            return (1.0 - confidence) * 100.0
        elif label in ("real", "authentic", "human-written", "bonafide"):
            return confidence * 100.0
        return 50.0

    @staticmethod
    def _text_to_authenticity(result: Dict) -> float:
        ai_prob = float(result.get("ai_probability", 0))
        return (1.0 - ai_prob) * 100.0

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 75: return "low"
        if score >= 45: return "medium"
        return "high"

    @staticmethod
    def _verdict(score: int) -> str:
        if score >= 85: return "Authentic"
        if score >= 65: return "Likely Authentic"
        if score >= 45: return "Suspicious"
        if score >= 25: return "Likely Manipulated"
        return "Highly Suspicious / Deepfake"

    @staticmethod
    def _compute_metadata_penalty(metadata: Dict, flags: List) -> int:
        penalty = 0
        tags = metadata.get("tags", {})
        encoder = str(tags.get("encoder", "")).lower()
        if any(x in encoder for x in ["lavf", "handbrake", "obs"]):
            penalty += 10
            flags.append({"label": "Re-encoded / Transcoded", "detail": f"Encoder: {encoder}", "severity": "medium"})
        if not tags:
            penalty += 5
            flags.append({"label": "Metadata Stripped", "detail": "No file metadata found", "severity": "medium"})
        return penalty
