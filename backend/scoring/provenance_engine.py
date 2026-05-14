"""truth.x — Provenance Engine.

Moves beyond simple fake/real classification to attribute the likely
generation source, manipulation type, and editing pipeline characteristics.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.utils.logger import logger


class ProvenanceEngine:
    """Analyzes detection signals to determine deepfake provenance."""

    def analyze_provenance(
        self,
        video_result: Optional[Dict[str, Any]] = None,
        audio_result: Optional[Dict[str, Any]] = None,
        text_result: Optional[Dict[str, Any]] = None,
        image_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Determine likely origin and manipulation category.
        
        Returns:
            {
                "likely_origin": str,
                "manipulation_type": str,
                "confidence": float,
                "signals": List[str],
            }
        """
        signals: List[str] = []
        origin_scores: Dict[str, float] = {
            "Stable Diffusion XL family": 0.0,
            "Midjourney v5/v6": 0.0,
            "Runway/Kling (Temporal)": 0.0,
            "ElevenLabs/VoiceClone": 0.0,
            "GPT-4/Claude (Text)": 0.0,
            "Faceswap/Roop": 0.0,
            "Wav2Lip/Sync": 0.0,
        }
        
        manipulation_types: List[str] = []

        # ── Image Provenance ──
        if image_result and image_result.get("label") == "fake":
            # Heuristics based on artifact frequency
            explain = image_result.get("explainability", {}).get("reasons", [])
            for r in explain:
                indicator = r.get("indicator", "")
                if indicator == "diffusion_noise":
                    origin_scores["Stable Diffusion XL family"] += 0.4
                    signals.append("Diffusion denoising artifacts detected")
                    manipulation_types.append("Text-to-Image Synthesis")
                elif indicator == "texture_repetition":
                    origin_scores["Midjourney v5/v6"] += 0.4
                    signals.append("High-frequency texture synthesis artifacts")
                    manipulation_types.append("Generative Upscaling")

        # ── Video Provenance ──
        if video_result and video_result.get("label") in ("fake", "ai-generated"):
            temporal = video_result.get("temporal_consistency", {})
            explain = video_result.get("explainability", {}).get("reasons", [])
            
            # Check for generative video models
            if temporal.get("score", 1.0) < 0.4:
                origin_scores["Runway/Kling (Temporal)"] += 0.5
                signals.append("Severe temporal incoherence across frames")
                manipulation_types.append("Text-to-Video Generation")
                
            # Check for face swapping or lip sync
            for r in explain:
                if "lip" in r.get("indicator", "") or "sync" in r.get("indicator", ""):
                    origin_scores["Wav2Lip/Sync"] += 0.6
                    signals.append("Lip-sync boundary mismatch")
                    manipulation_types.append("Audio-Driven Lip Sync")
                elif "blink" in r.get("indicator", "") or "geometry" in r.get("indicator", ""):
                    origin_scores["Faceswap/Roop"] += 0.5
                    signals.append("Facial geometry drift and unnatural blinking")
                    manipulation_types.append("Targeted Face Swap")

        # ── Audio Provenance ──
        if audio_result and audio_result.get("label") == "fake":
            spectral = audio_result.get("spectral_features", {})
            if spectral.get("spectral_flatness", 0) > 0.01 and spectral.get("mfcc_std", 10) < 5:
                origin_scores["ElevenLabs/VoiceClone"] += 0.6
                signals.append("Uniform MFCCs and synthetic spectral flatness")
                manipulation_types.append("Zero-shot Voice Cloning")

        # ── Text Provenance ──
        if text_result and text_result.get("label") == "ai-generated":
            enhanced = text_result.get("enhanced_analysis", {})
            if enhanced.get("perplexity_score", 0) > 0.7:
                origin_scores["GPT-4/Claude (Text)"] += 0.5
                signals.append("Low perplexity indicating highly predictable LLM generation")
                manipulation_types.append("LLM Text Generation")

        # ── Aggregation ──
        best_origin = "Unknown"
        best_score = 0.0
        for origin, score in origin_scores.items():
            if score > best_score:
                best_origin = origin
                best_score = score
                
        # Normalization
        confidence = min(0.95, best_score)
        
        if confidence < 0.3:
            return {
                "likely_origin": "Unknown / Natural",
                "manipulation_type": "None detected",
                "confidence": 0.0,
                "signals": [],
            }

        return {
            "likely_origin": best_origin,
            "manipulation_type": " / ".join(list(set(manipulation_types))) or "Unknown Generation",
            "confidence": round(confidence, 2),
            "signals": list(set(signals)),
        }
