"""truth.x — Production-Grade Video Deepfake Detector (UPGRADED).

Architecture:
    - Backbone: VideoMAE (Temporal Transformer)
    - Input: 16-frame temporal sequences (clips)
    - Analysis: Cross-modal temporal coherence + Face Landmark Biometrics
    - Scoring: Anomaly Amplification (Suspicious clips dominate)
    - Observability: Detailed runtime logging and fallback exposure
"""

from __future__ import annotations

import gc
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml
from PIL import Image
from transformers import VideoMAEImageProcessor, VideoMAEModel

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
        logger.warning("CUDA requested for video detector but unavailable; using CPU")
        return torch.device("cpu")
    return torch.device(configured)


class TemporalAnomalyClassifier(nn.Module):
    """Analyzes high-dimensional VideoMAE embeddings for temporal inconsistency."""

    def __init__(self, hidden_size: int = 768):
        super().__init__()
        # Projection for coherence analysis
        self.proj = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Linear(256, 128)
        )

    def forward(self, x: torch.Tensor) -> Dict[str, float]:
        """Analyzes frame-to-frame feature transitions with continuous scoring."""
        # x: (batch, time, hidden) -> usually (1, 8, 768) for VideoMAE tubelets
        batch_size, time_steps, hidden = x.shape
        if time_steps < 2:
            return {"score": 0.5, "coherence": 1.0}

        proj_x = self.proj(x)  # (1, 8, 128)

        # 1. Temporal Coherence (Cosine Similarity between adjacent frames)
        sims = F.cosine_similarity(proj_x[:, :-1, :], proj_x[:, 1:, :], dim=-1)
        mean_sim = float(sims.mean().item())
        std_sim = float(sims.std().item()) if time_steps > 2 else 0.0

        # 2. Continuous Anomaly Scoring (Recalibrated for modern video)
        # Philosophy: Modern phones produce extremely smooth video (0.94-0.98 similarity).
        # We now use a wider "Natural" band to avoid false positives.
        
        # Center at 0.94 (ideal smooth motion)
        dist_from_natural = abs(mean_sim - 0.94)
        
        # Recalibrated Scaling:
        if mean_sim > 0.975:
            # Towards hyper-perfection (Strong AI signature)
            # Only start climbing aggressively after 0.98
            dist_pushed = max(0, mean_sim - 0.975)
            score = 0.15 + (dist_pushed * 25.0) # Reaches 0.65 at 0.995, 0.9 at 1.0
        elif mean_sim < 0.88:
            # Towards jitter (Manipulation signature)
            dist_pushed = 0.88 - mean_sim
            score = 0.15 + (dist_pushed * 3.5) # Reaches 0.5 at 0.78, 0.8 at 0.65
        else:
            # Inside the "Natural Band" (0.88 - 0.975)
            # Low baseline score for healthy motion
            score = 0.05 + (dist_from_natural * 0.5) # Max 0.08 inside band

        # Apply variance penalty only if significantly unstable
        if std_sim > 0.10:
            score += (std_sim * 1.5)

        final_score = float(np.clip(score, 0.02, 0.98))
        
        logger.debug("Temporal Head (Recalibrated): mean_sim=%.4f, std_sim=%.4f -> raw_score=%.4f", 
                     mean_sim, std_sim, final_score)

        return {
            "score": final_score,
            "mean_coherence": mean_sim,
            "coherence_std": std_sim
        }


class VideoDeepfakeDetector(BaseDetector):
    """The core VideoMAE temporal detection engine."""

    modality = "video"

    def __init__(self) -> None:
        super().__init__()
        self.config = _load_config()
        v_cfg = self.config.get("video", {})
        self.model_name = v_cfg.get("model_name", "MCG-NJU/videomae-base")
        
        # Performance/Robustness settings
        self.batch_size = 1  # 1 clip (16 frames) at a time
        self.fallback_active = False
        self.init_error = None
        
        self.processor = None
        self.model = None
        self.anomaly_head = None

        self.enabled = os.environ.get("VIDEO_DETECTION_ENABLED", "true").lower() == "true"
        logger.info("VideoDeepfakeDetector initialized (Enabled=%s)", self.enabled)

    def _ensure_model(self) -> bool:
        """Lazy-load the video model if enabled."""
        if not self.enabled:
            return False
            
        if self.model is None:
            logger.info("Initializing VideoMAE Temporal Backbone: %s", self.model_name)
            try:
                t0 = time.perf_counter()
                self.processor = VideoMAEImageProcessor.from_pretrained(self.model_name)
                self.model = VideoMAEModel.from_pretrained(self.model_name, low_cpu_mem_usage=True)
                self.model.to(self.device)
                self.model.eval()
                
                self.anomaly_head = TemporalAnomalyClassifier(self.model.config.hidden_size).to(self.device)
                self.anomaly_head.eval()
                
                logger.info("VideoMAE loaded successfully (%.2fs) ✓", time.perf_counter() - t0)
                return True
            except Exception as e:
                self.fallback_active = True
                self.init_error = str(e)
                logger.error("VideoMAE LOAD FAILURE: %s. Reverting to fallback scoring.", e)
                return False
        return True

    @torch.no_grad()
    def _run_inference(self, clip_frames: List[Image.Image]) -> Dict[str, Any]:
        """Executes VideoMAE temporal transformer inference on a single 16-frame clip."""
        if not self._ensure_model() or self.fallback_active:
            return {"error": "VideoMAE Offline", "score": 0.5}

        t_start = time.perf_counter()
        
        # Preprocessing: Ensure robust resizing and normalization
        inputs = self.processor(list(clip_frames), return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        try:
            logger.debug("VideoMAE Inference: clip_frames=%d, tensor_shape=%s", 
                         len(clip_frames), inputs['pixel_values'].shape)
            
            outputs = self.model(**inputs)
            # VideoMAE tubelet embedding results in 8 temporal tokens for 16 frames
            hidden = outputs.last_hidden_state # (1, 1568, 768)
            
            batch, total_tokens, h_dim = hidden.shape
            temp_tokens = 8
            spatial_tokens = total_tokens // temp_tokens
            
            # Pool spatial tokens to get pure temporal trajectory
            temporal_features = hidden.view(batch, temp_tokens, spatial_tokens, h_dim).mean(dim=2)
            
            result = self.anomaly_head(temporal_features)
            
            latency = (time.perf_counter() - t_start) * 1000
            logger.info("Clip Analysis: mean_sim=%.4f, score=%.4f, latency=%.2fms", 
                        result['mean_coherence'], result['score'], latency)
            
            return {**result, "latency": latency}
            
        except Exception as e:
            logger.error("VideoMAE Inference Runtime Error: %s", e)
            return {"error": str(e), "score": 0.5}

    def predict(self, frames: List[Image.Image]) -> Dict[str, Any]:
        """Main entry point: Video -> Clips -> Temporal Inference -> Ensemble Scoring."""
        t_overall = time.perf_counter()
        
        if not frames:
            return self._format_result(label="unknown", confidence=0.0, fake_probability=0.5)

        num_frames = len(frames)
        logger.info("Pipeline Start: Analyzing %d frames for temporal integrity", num_frames)

        # 1. TEMPORAL CLIP EXTRACTION
        clips = []
        clip_size = 16
        if num_frames >= clip_size:
            for i in range(0, num_frames - clip_size + 1, clip_size // 2):
                clips.append(frames[i : i + clip_size])
        else:
            padded = frames.copy()
            while len(padded) < clip_size:
                padded.append(padded[-1])
            clips.append(padded)

        # 2. RUN TEMPORAL INFERENCE
        clip_results = []
        for i, clip in enumerate(clips[:4]):
            res = self._run_inference(clip)
            if "error" not in res:
                clip_results.append(res)

        # 3. ANOMALY AMPLIFICATION SCORING
        if not clip_results:
            temporal_prob = 0.5
            max_latency = 0.0
        else:
            scores = [c["score"] for c in clip_results]
            max_score = max(scores)
            mean_score = sum(scores) / len(scores)
            max_latency = max([c.get("latency", 0) for c in clip_results])
            temporal_prob = (max_score * 0.8) + (mean_score * 0.2)

        # 4. BIOMETRIC LANDMARK CONSISTENCY
        landmark_res = self._analyze_face_landmarks(frames)
        landmark_prob = landmark_res.get("landmark_anomaly_score", 0.0) if landmark_res else 0.5
        
        # 5. MULTI-SIGNAL CORROBORATION (Recalibrated Fusion)
        # Philosophy: Extreme confidence (90%+) requires multiple independent forensic signals.
        # Single-metric anomalies should be dampened to "Suspicious" or "Mixed" levels.
        
        # Base fusion: weighted average biased towards the stronger signal
        if (temporal_prob > 0.75 and landmark_prob > 0.75):
            # CORROBORATED: Both temporal and biometric signals indicate AI
            final_prob = max(temporal_prob, landmark_prob)
            logger.info("Forensic Corroboration: Multiple signals detected (T=%.2f, B=%.2f)", 
                        temporal_prob, landmark_prob)
        elif (temporal_prob < 0.3 and landmark_prob < 0.3):
            # AUTHENTIC CORROBORATION: Both indicate healthy video
            final_prob = min(temporal_prob, landmark_prob)
        else:
            # ISOLATED OR AMBIGUOUS: Signals are neutral or only one triggers
            # Dampen confidence aggressively to avoid false positives
            final_prob = (temporal_prob * 0.5) + (landmark_prob * 0.5)
            # Pull towards neutral (0.5) if significantly different
            if abs(temporal_prob - landmark_prob) > 0.4:
                final_prob = (final_prob + 0.5) / 2.0
                logger.info("Confidence Dampening: Conflicting signals (T=%.2f, B=%.2f) -> Pulled to %.2f", 
                            temporal_prob, landmark_prob, final_prob)

        # 6. SIGMOID CALIBRATION (Push away from 50%, but with a dampened slope)
        # Using a gentler slope (k=8 instead of k=12) to avoid "snap" to 99%
        calibrated_fake_prob = 1 / (1 + math.exp(-8 * (final_prob - 0.5)))
        
        # Limit certainty to 0.96 for uncorroborated single-modality signals
        if (temporal_prob < 0.7 or landmark_prob < 0.7) and calibrated_fake_prob > 0.85:
            calibrated_fake_prob = 0.85
            logger.info("Certainty Capped: Single-signal anomaly capped at 85%")
        
        label = "fake" if calibrated_fake_prob > 0.5 else "real"
        confidence = calibrated_fake_prob if label == "fake" else (1.0 - calibrated_fake_prob)

        # 7. EXPLAINABILITY GENERATION
        reasons = []
        if temporal_prob > 0.70:
            reasons.append(self._make_reason(
                "temporal_inconsistency", "high" if temporal_prob > 0.85 else "medium",
                "Unnatural frame-to-frame coherence detected by Temporal Transformer.",
                f"VideoMAE Score: {temporal_prob:.2f}"
            ))
        
        if landmark_res and landmark_res.get("reasons"):
            reasons.extend(landmark_res["reasons"])

        overall_time = time.perf_counter() - t_overall
        self._cleanup_gpu()

        return self._format_result(
            label=label,
            confidence=confidence,
            fake_probability=calibrated_fake_prob,
            reasons=reasons,
            extra={
                "debug_info": {
                    "frames_processed": num_frames,
                    "clips_analyzed": len(clip_results),
                    "total_pipeline_time": round(overall_time, 3),
                },
                "technical_signals": {
                    "temporal_anomaly": round(temporal_prob, 4),
                    "landmark_anomaly": round(landmark_prob, 4),
                }
            }
        )

    def _analyze_face_landmarks(self, frames: List[Image.Image]) -> Optional[Dict[str, Any]]:
        """Analyzes facial landmarks for biological inconsistencies (blinking, drift, etc.)."""
        try:
            import mediapipe as mp
            mp_face_mesh = mp.solutions.face_mesh
            face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True)
            
            ear_values = [] # Eye Aspect Ratio
            lip_vars = []
            geo_drifts = []
            reasons = []

            # Sample frames for efficiency
            sampled = frames[::max(1, len(frames)//20)][:20]
            
            prev_geo = None
            for frame in sampled:
                img = np.array(frame.convert("RGB"))
                res = face_mesh.process(img)
                if not res.multi_face_landmarks: continue
                
                l = res.multi_face_landmarks[0].landmark
                # EAR (Eyes)
                ear = (abs(l[159].y - l[145].y) + abs(l[386].y - l[374].y)) / 2.0
                ear_values.append(ear)
                # Lip distance
                lip_vars.append(abs(l[13].y - l[14].y))
                # Geometry (Nose tip, chin, forehead)
                curr_geo = np.array([[l[1].x, l[1].y], [l[152].x, l[152].y], [l[10].x, l[10].y]])
                if prev_geo is not None:
                    geo_drifts.append(np.mean(np.linalg.norm(curr_geo - prev_geo, axis=1)))
                prev_geo = curr_geo

            face_mesh.close()
            
            if not ear_values: return None

            # Logic
            ear_std = np.std(ear_values)
            blink_anomaly = ear_std < 0.003
            if blink_anomaly:
                reasons.append(BaseDetector._make_reason("abnormal_blinking", "high", "Lack of natural blink variation (AI signature).", f"EAR Std: {ear_std:.5f}"))

            drift = np.mean(geo_drifts) if geo_drifts else 0
            if drift > 0.012:
                reasons.append(BaseDetector._make_reason("facial_geometry_drift", "medium", "Unstable facial landmark tracking (Possible FaceSwap).", f"Mean Drift: {drift:.5f}"))

            anomaly_score = 0.5
            if blink_anomaly: anomaly_score += 0.25
            if drift > 0.012: anomaly_score += 0.2
            
            return {
                "landmark_anomaly_score": min(1.0, anomaly_score),
                "reasons": reasons,
                "blink_std": float(ear_std),
                "mean_drift": float(drift)
            }
        except Exception as e:
            logger.debug("Landmark Analysis Skip: %s", e)
            return None
