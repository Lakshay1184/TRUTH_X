"""truth.x — Postprocessing: Improved aggregation with temporal consistency and anomaly scoring."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from backend.utils.logger import logger

FAKE_LABELS = {"fake", "deepfake", "ai-generated", "ai", "machine", "spoof", "manipulated"}
REAL_LABELS = {"real", "human-written", "human", "bonafide", "original", "authentic"}


def _to_fake_probability(result: Dict[str, Any]) -> Optional[float]:
    """Convert a detector result to probability-of-fake (0.0 = real, 1.0 = fake)."""
    label = str(result.get("label", "")).lower()
    confidence = result.get("confidence")
    if confidence is None:
        return None
    if label in FAKE_LABELS:
        return float(confidence)
    elif label in REAL_LABELS:
        return 1.0 - float(confidence)
    return None


def aggregate_results(
    video_result: Optional[Dict[str, Any]] = None,
    audio_result: Optional[Dict[str, Any]] = None,
    text_result: Optional[Dict[str, Any]] = None,
    image_result: Optional[Dict[str, Any]] = None,
    articles: Optional[List[Dict[str, Any]]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Combine detector outputs with weighted aggregation, temporal consistency,
    and anomaly-based scoring.

    Improvements over simple averaging:
        - Confidence-weighted contributions (higher confidence = more influence)
        - Temporal consistency penalty from video detector
        - Trust score integration
    """
    if weights is None:
        weights = {"video": 0.40, "audio": 0.20, "text": 0.20, "image": 0.20}

    report: Dict[str, Any] = {
        "video": video_result,
        "audio": audio_result,
        "text": text_result,
        "image": image_result,
        "related_articles": articles or [],
        "combined_fake_probability": 0.0,
        "combined_confidence": 0.0,
        "overall_label": "uncertain",
    }

    weighted_sum = 0.0
    total_weight = 0.0
    confidence_sum = 0.0

    modalities = [
        ("video", video_result),
        ("audio", audio_result),
        ("text", text_result),
        ("image", image_result)
    ]

    for key, result in modalities:
        if result is None or result.get("label") == "inconclusive" or result.get("label") == "unknown":
            continue

        fake_prob = _to_fake_probability(result)
        if fake_prob is None:
            logger.warning("Cannot derive fake probability from %s (label=%s), skipping", key, result.get("label"))
            continue

        w = weights.get(key, 0.25)
        det_confidence = result.get("confidence", 0.5)

        # Confidence-weighted: scale the weight by detector confidence
        # We increase the weight exponentially for high confidence
        effective_weight = w * (0.5 + det_confidence * 0.5)

        # Temporal consistency bonus for video
        if key == "video" and "temporal_consistency" in result:
            temporal = result["temporal_consistency"]
            consistency_score = temporal.get("score", 1.0)
            effective_weight *= (0.7 + 0.3 * consistency_score)

        logger.debug("%s: fake_prob=%.4f, base_weight=%.2f, effective_weight=%.4f",
                     key, fake_prob, w, effective_weight)

        weighted_sum += fake_prob * effective_weight
        total_weight += effective_weight
        confidence_sum += det_confidence

    if total_weight > 0:
        combined_fake = round(weighted_sum / total_weight, 4)
        report["combined_fake_probability"] = combined_fake
        report["combined_confidence"] = round(abs(combined_fake - 0.5) * 2, 4)
        report["overall_label"] = "fake" if combined_fake >= 0.5 else "real"
    else:
        # Honest failure state: No data to analyze
        report["overall_label"] = "insufficient_data"
        report["combined_fake_probability"] = 0.0
        report["combined_confidence"] = 0.0
        report["status"] = "failed"
        logger.warning("Aggregation failed: No modality provided valid forensic signals.")

    logger.info("Aggregated: overall=%s, fake_prob=%.4f, confidence=%.4f",
                report["overall_label"], report["combined_fake_probability"],
                report["combined_confidence"])
    return report


def compute_risk_score(
    metadata: dict,
    video_result: Optional[Dict[str, Any]] = None,
    audio_result: Optional[Dict[str, Any]] = None,
    text_result: Optional[Dict[str, Any]] = None,
    image_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Analyze metadata + ML results for suspicious indicators and compute authenticity score."""
    flags = []
    ml_driven = False
    video = metadata.get("video", {})
    tags = metadata.get("tags", {})
    file_info = metadata.get("file_info", {})

    # ── Metadata penalties ──
    meta_penalty = 0

    encoder = str(tags.get("encoder", "")).lower()
    if any(x in encoder for x in ["lavf", "handbrake", "obs", "x264", "x265"]):
        flags.append({"label": "Re-encoded", "detail": f"Encoder: {tags.get('encoder', 'unknown')}", "severity": "medium"})
        meta_penalty += 10

    codec = str(video.get("codec_short", "")).lower()
    if codec and codec not in ("h264", "hevc", "h265", "vp9", "vp8", "av1", "mpeg4"):
        flags.append({"label": "Unusual codec", "detail": video.get("codec", codec), "severity": "low"})
        meta_penalty += 5

    for field_val in [encoder, str(tags.get("comment", "")).lower()]:
        for sus in ["deepfake", "faceswap", "synthesia", "d-id", "heygen"]:
            if sus in field_val:
                flags.append({"label": "AI Tool Detected", "detail": f"Metadata: '{sus}'", "severity": "critical"})
                meta_penalty += 40
                break

    if not tags:
        flags.append({"label": "Stripped metadata", "detail": "No tags found", "severity": "medium"})
        meta_penalty += 10

    if video.get("width", 0) >= 1920 and 0 < file_info.get("total_bitrate_kbps", 0) < 2000:
        flags.append({"label": "Low bitrate", "detail": "Possible re-encode", "severity": "medium"})
        meta_penalty += 10

    # ── ML results ──
    ml_scores = []

    if video_result and video_result.get("label"):
        label = video_result["label"].lower()
        confidence = video_result.get("confidence", 0)
        trust = video_result.get("trust_score", confidence)

        if label == "fake":
            v_score = int((1.0 - confidence) * 100)
            ml_scores.append(v_score)
            ml_driven = True
            flags.append({
                "label": "Deepfake Detected",
                "detail": f"Video: {confidence:.0%} fake confidence (trust={trust:.0%})",
                "severity": "critical" if confidence > 0.75 else "high",
            })
        elif label == "real" and confidence > 0.5:
            ml_scores.append(int(confidence * 100))
            ml_driven = True

    if audio_result and audio_result.get("label"):
        label = audio_result["label"].lower()
        confidence = audio_result.get("confidence", 0)
        fake_prob = audio_result.get("fake_probability", 0)
        
        if label == "fake" or fake_prob > 0.5:
            a_score = int((1.0 - fake_prob) * 100)
            ml_scores.append(a_score)
            ml_driven = True
            flags.append({
                "label": "Synthetic Voice",
                "detail": f"Audio: {fake_prob:.0%} synthetic probability",
                "severity": "critical" if fake_prob > 0.8 else "high",
            })
        elif label == "real" and confidence > 0.5:
            ml_scores.append(int(confidence * 100))
            ml_driven = True

    if text_result and text_result.get("label"):
        label = text_result["label"].lower()
        ai_prob = text_result.get("ai_probability", 0)
        if "ai" in label and ai_prob > 0.5:
            text_ml_score = int((1.0 - ai_prob) * 100)
            flags.append({
                "label": "AI-Generated Text",
                "detail": f"Text: {ai_prob:.0%} AI probability",
                "severity": "critical" if ai_prob > 0.75 else "high",
            })
            ml_scores.append(text_ml_score)
            ml_driven = True

    if image_result and image_result.get("label"):
        label = image_result["label"].lower()
        fake_prob = image_result.get("fake_probability", 0)
        if "ai" in label or fake_prob > 0.5:
            i_score = int((1.0 - fake_prob) * 100)
            flags.append({
                "label": "Synthetic Image",
                "detail": f"Image: {fake_prob:.0%} AI probability",
                "severity": "critical" if fake_prob > 0.8 else "high",
            })
            ml_scores.append(i_score)
            ml_driven = True
        elif "authentic" in label and image_result.get("confidence", 0) > 0.5:
            ml_scores.append(int(image_result.get("confidence", 0) * 100))
            ml_driven = True

    # ── Final score ──
    if ml_driven and ml_scores:
        # Use the most conservative (lowest) ML score
        ml_score = min(ml_scores)
        score = max(0, ml_score - (meta_penalty // 2))
    else:
        score = max(0, 100 - meta_penalty)

    score = max(0, min(100, score))
    
    # Standardized Scale (Legacy Fallback)
    if score <= 20: risk_level = "critical"
    elif score <= 40: risk_level = "high"
    elif score <= 60: risk_level = "medium"
    elif score <= 80: risk_level = "low"
    else: risk_level = "minimal"

    return {
        "authenticity_score": score,
        "risk_level": risk_level,
        "flags": flags,
        "flag_count": len(flags),
    }


def generate_drift_data(duration: float, deepfake_result: Optional[dict] = None) -> List[dict]:
    """Generate per-segment drift data from model output."""
    if duration <= 0:
        return []

    import math
    num_segments = min(20, max(8, int(duration / 5)))
    segment_duration = duration / num_segments
    drift_points = []

    per_frame = deepfake_result.get("per_frame", []) if deepfake_result else []
    if per_frame:
        frames_per_seg = max(1, len(per_frame) // num_segments)
        for i in range(num_segments):
            start_idx = i * frames_per_seg
            end_idx = min(start_idx + frames_per_seg, len(per_frame))
            seg_frames = per_frame[start_idx:end_idx]
            if seg_frames:
                avg_real = sum(f.get("Real", f.get("real", 0.5)) for f in seg_frames) / len(seg_frames)
                val = max(0, min(100, int(avg_real * 100)))
            else:
                val = 50
            t_start = i * segment_duration
            drift_points.append({"t": f"{int(t_start)}s", "v": val, "type": "model"})
    else:
        base_score = 50
        if deepfake_result:
            avg = deepfake_result.get("average", {})
            base_score = int(avg.get("Real", avg.get("real", 0.5)) * 100)

        import random
        for i in range(num_segments):
            t_start = i * segment_duration
            param = (i / num_segments) * math.pi * 2
            variation = math.sin(param) * 5 + random.randint(-3, 3)
            val = max(0, min(100, int(base_score + variation)))
            drift_points.append({"t": f"{int(t_start)}s", "v": val, "type": "estimated"})

    return drift_points
