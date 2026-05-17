"""truth.x — Audio Deepfake Detector with Segment-Level Analysis.

Improvements over original:
    - Segment-level analysis (3-second windows) instead of single pass
    - Spectral consistency checks via handcrafted features
    - Weighted segment aggregation
    - Confidence calibration
"""

from __future__ import annotations

import gc
import os
from typing import Any, Dict, List

import librosa
import numpy as np
import torch
import yaml
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

from backend.detectors.base import BaseDetector
from backend.utils.logger import logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_device(configured: str) -> torch.device:
    if configured == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if configured == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA requested for audio detector but unavailable; using CPU")
        return torch.device("cpu")
    return torch.device(configured)


class AudioDeepfakeDetector(BaseDetector):
    """Detects AI-generated / synthetic speech using Wav2Vec2
    with segment-level analysis and spectral feature fusion."""

    modality = "audio"

    def __init__(self) -> None:
        super().__init__()
        cfg = _load_config()
        audio_cfg = cfg.get("audio", {})
        self.model_name: str = audio_cfg.get("model_name", "MelodyMachine/Deepfake-audio-detection-V2")
        self.sample_rate: int = audio_cfg.get("sample_rate", 16000)
        self.segment_duration: float = audio_cfg.get("segment_duration", 3.0)
        self.max_duration: int = audio_cfg.get("max_duration", 30)

        logger.info("Loading audio model '%s' on %s", self.model_name, self.device)
        try:
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_name)
            self.model = AutoModelForAudioClassification.from_pretrained(self.model_name, low_cpu_mem_usage=False)
            self.model.to(self.device)
            self.model.eval()
            logger.info("Audio model loaded successfully ✓")
        except Exception as e:
            logger.error("Failed to load audio model: %s", e)
            self.model = None

    @torch.no_grad()
    def predict(self, audio_path: str) -> Dict[str, Any]:
        """Analyze an audio file with segment-level analysis."""
        if self.model is None:
            return {"error": "Model not loaded"}

        if not os.path.exists(audio_path):
            logger.error("Audio file not found: %s", audio_path)
            return {"error": "File not found"}

        try:
            # Load audio
            speech, sr = librosa.load(audio_path, sr=self.sample_rate)
            if len(speech) == 0:
                return {"error": "Empty audio file"}

            # Truncate to max duration
            max_samples = self.max_duration * sr
            if len(speech) > max_samples:
                speech = speech[:max_samples]

            # ── Segment-level analysis ──
            segment_samples = int(self.segment_duration * sr)
            segments = []
            segment_fake_probs = []

            for i in range(0, len(speech), segment_samples):
                segment = speech[i:i + segment_samples]
                if len(segment) < sr:
                    continue

                seg_result = self._predict_segment(segment, sr)
                segments.append(seg_result)
                segment_fake_probs.append(seg_result.get("fake_probability", 0.5))

            # ── Aggregate segments (weighted by confidence) ──
            if segment_fake_probs:
                weights = [abs(p - 0.5) + 0.5 for p in segment_fake_probs]
                total_weight = sum(weights)
                fake_prob = sum(p * w for p, w in zip(segment_fake_probs, weights)) / total_weight
            else:
                full_result = self._predict_segment(speech, sr)
                fake_prob = full_result.get("fake_probability", 0.5)

            # ── Spectral consistency features ──
            spectral = self._extract_spectral_features(speech, sr)
            spectral_anomaly = self._spectral_anomaly_score(spectral)
            
            # Anomaly Anchoring: If forensic signals are strong, they anchor the result floor
            if spectral_anomaly > 0.4:
                # Spectral anomalies are high-confidence synthetic signatures
                adjusted_fake_prob = max(fake_prob, spectral_anomaly * 0.9)
                logger.info("Audio Anomaly Anchor active: spectral_anomaly=%.2f anchoring fake_prob to %.4f", spectral_anomaly, adjusted_fake_prob)
            else:
                adjusted_fake_prob = np.clip(fake_prob + spectral_anomaly * 0.1, 0.0, 1.0)
            
            label = "fake" if adjusted_fake_prob > 0.5 else "real"
            confidence = adjusted_fake_prob if label == "fake" else 1.0 - adjusted_fake_prob

            # ── Build explainability reasons ──
            reasons = []
            if adjusted_fake_prob > 0.6:
                reasons.append(self._make_reason(
                    "synthetic_voice_detection",
                    "high" if adjusted_fake_prob > 0.8 else "medium",
                    f"Audio model detected synthetic voice patterns ({adjusted_fake_prob:.0%} confidence)",
                    f"Model: {self.model_name}",
                ))

            if spectral.get("spectral_flatness", 0) > 0.01:
                reasons.append(self._make_reason(
                    "spectral_inconsistencies", "medium",
                    "High spectral flatness indicates possible synthetic audio",
                    f"Spectral flatness: {spectral.get('spectral_flatness'):.6f}"
                ))

            self._cleanup_gpu()

            return self._format_result(
                label=label,
                confidence=confidence,
                fake_probability=adjusted_fake_prob,
                reasons=reasons,
                extra={
                    "technical_signals": {
                        "wav2vec2_fake_prob": round(float(fake_prob), 4),
                        "spectral_anomaly": round(float(spectral_anomaly), 4),
                        "num_segments": len(segments)
                    }
                }
            )

        except Exception as e:
            logger.error("Audio detection error: %s", e)
            return {"error": str(e)}

    def _predict_segment(self, audio_segment: np.ndarray, sr: int) -> Dict[str, float]:
        """Run model inference on a single audio segment."""
        inputs = self.feature_extractor(
            audio_segment, sampling_rate=sr, return_tensors="pt", padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).cpu().tolist()[0]

        id2label = self.model.config.id2label
        fake_prob, real_prob = 0.0, 0.0

        if id2label:
            for idx, lbl in id2label.items():
                lbl_str = str(lbl).lower()
                if "fake" in lbl_str or "spoof" in lbl_str:
                    fake_prob = probs[int(idx)]
                elif "real" in lbl_str or "bonafide" in lbl_str:
                    real_prob = probs[int(idx)]

        if fake_prob == 0.0 and real_prob == 0.0:
            fake_prob = probs[0]
            real_prob = probs[1] if len(probs) > 1 else 1.0 - fake_prob

        return {"fake_probability": fake_prob, "real_probability": real_prob}

    @staticmethod
    def _extract_spectral_features(audio: np.ndarray, sr: int) -> Dict[str, float]:
        """Extract handcrafted spectral features for anomaly detection."""
        try:
            zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=audio)))
            rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=audio, sr=sr)))
            centroid = float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)))
            bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=audio, sr=sr)))

            mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
            mfcc_mean = float(np.mean(mfcc))
            mfcc_std = float(np.std(mfcc))

            # Spectral flatness (synthetic audio tends to have higher flatness)
            flatness = float(np.mean(librosa.feature.spectral_flatness(y=audio)))

            return {
                "zero_crossing_rate": round(zcr, 6),
                "spectral_rolloff": round(rolloff, 2),
                "spectral_centroid": round(centroid, 2),
                "spectral_bandwidth": round(bandwidth, 2),
                "mfcc_mean": round(mfcc_mean, 4),
                "mfcc_std": round(mfcc_std, 4),
                "spectral_flatness": round(flatness, 6),
            }
        except Exception as e:
            logger.warning("Spectral feature extraction failed: %s", e)
            return {}

    @staticmethod
    def _spectral_anomaly_score(features: Dict[str, float]) -> float:
        """Score spectral anomalies (higher = more synthetic-sounding)."""
        score = 0.0
        if not features:
            return score

        # High spectral flatness often indicates synthetic audio
        flatness = features.get("spectral_flatness", 0)
        if flatness > 0.01:
            score += 0.2

        # Unusually consistent spectral properties (low MFCC variance)
        mfcc_std = features.get("mfcc_std", 10)
        if mfcc_std < 5:
            score += 0.15

        # High zero crossing rate
        zcr = features.get("zero_crossing_rate", 0)
        if zcr > 0.1:
            score += 0.1

        return min(score, 0.5)
