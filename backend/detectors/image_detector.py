"""truth.x — Image AI Detection with Ensemble Analysis.

Architecture:
    1. Primary: umm-maybe/AI-image-detector (Stable classification architecture)
    2. Secondary: dima806/deepfake_vs_real_image_detection (Deepfake vs Real)
    3. Metadata + Artifact Analysis (LOCAL) — EXIF and artifact inspection
"""

from __future__ import annotations

import gc
import math
import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import yaml
from PIL import Image
from PIL.ExifTags import TAGS
from transformers import AutoProcessor, AutoModelForImageClassification

from backend.detectors.base import BaseDetector
from backend.utils.logger import logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


# ─── Known AI tool signatures ───────────────────────────────────────────

_AI_SOFTWARE_SIGNATURES = {
    "stable diffusion", "midjourney", "dall-e", "dalle", "flux",
    "comfyui", "automatic1111", "invoke ai", "dream studio",
    "leonardo ai", "playground ai", "nightcafe", "artbreeder",
    "deepai", "craiyon", "bing image creator", "firefly",
    "novelai", "tensor.art", "civitai",
}

_COMMON_AI_RESOLUTIONS = {
    (512, 512), (768, 768), (1024, 1024), (1024, 768), (768, 1024),
    (1280, 720), (1920, 1080), (512, 768), (768, 512),
}


# --- Detector Health Registry ---
_MODEL_HEALTH: Dict[str, bool] = {}

class ImageAIDetector(BaseDetector):
    """Detects AI-generated images using ensemble of high-performance models."""

    modality = "image"

    def __init__(self) -> None:
        super().__init__()
        # PRIMARY MODEL (Stable classification architecture)
        self.primary_model_name = "umm-maybe/AI-image-detector"
        # SECONDARY MODEL (Deepfake vs Real)
        self.secondary_model_name = "dima806/deepfake_vs_real_image_detection"

        # Ensemble weights (Balanced Probabilistic Fusion)
        self.weight_primary = 0.55
        self.weight_secondary = 0.30
        self.weight_artifact = 0.15

        self._primary_model = None
        self._primary_processor = None
        self._secondary_model = None
        self._secondary_processor = None

        logger.info("ImageAIDetector initialized (Primary=%s, Secondary=%s)", 
                    self.primary_model_name, self.secondary_model_name)

    def _ensure_models(self) -> None:
        """Lazy-load the image detection models with health caching."""
        
        # 1. Primary Model Handling (umm-maybe/AI-image-detector)
        if self._primary_model is None and _MODEL_HEALTH.get(self.primary_model_name) is not False:
            logger.info("Loading primary image model: %s", self.primary_model_name)
            try:
                self._primary_processor = AutoProcessor.from_pretrained(self.primary_model_name)
                self._primary_model = AutoModelForImageClassification.from_pretrained(self.primary_model_name)
                self._primary_model.to(self.device)
                self._primary_model.eval()
                _MODEL_HEALTH[self.primary_model_name] = True
                logger.info("Primary image model loaded successfully ✓")
            except Exception as e:
                logger.error("Failed to load primary image model '%s': %s", self.primary_model_name, e)
                _MODEL_HEALTH[self.primary_model_name] = False

        # 2. Secondary Model Handling (dima806/deepfake_vs_real_image_detection)
        if self._secondary_model is None and _MODEL_HEALTH.get(self.secondary_model_name) is not False:
            logger.info("Loading secondary image model: %s", self.secondary_model_name)
            try:
                self._secondary_processor = AutoProcessor.from_pretrained(self.secondary_model_name)
                self._secondary_model = AutoModelForImageClassification.from_pretrained(self.secondary_model_name)
                self._secondary_model.to(self.device)
                self._secondary_model.eval()
                _MODEL_HEALTH[self.secondary_model_name] = True
                logger.info("Secondary image model loaded successfully ✓")
            except Exception as e:
                logger.error("Failed to load secondary image model '%s': %s", self.secondary_model_name, e)
                _MODEL_HEALTH[self.secondary_model_name] = False

    @torch.no_grad()
    def predict(self, image: Image.Image, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Analyze a single image for AI generation with ensemble logic."""
        self._ensure_models()
        reasons: List[Dict[str, Any]] = []

        primary_fake_prob = None
        secondary_fake_prob = None

        # 1. Primary Neural Inference
        if self._primary_model is not None and self._primary_processor is not None:
            try:
                inputs_p = self._primary_processor(images=image, return_tensors="pt").to(self.device)
                outputs_p = self._primary_model(**inputs_p)
                probs_p = torch.softmax(outputs_p.logits, dim=-1).cpu().tolist()[0]
                # umm-maybe/AI-image-detector: 0=real, 1=fake
                primary_fake_prob = float(probs_p[1])
            except Exception as e:
                logger.error("Primary image inference failed: %s", e)

        # 2. Secondary Neural Inference
        if self._secondary_model is not None and self._secondary_processor is not None:
            try:
                inputs_s = self._secondary_processor(images=image, return_tensors="pt").to(self.device)
                outputs_s = self._secondary_model(**inputs_s)
                probs_s = torch.softmax(outputs_s.logits, dim=-1).cpu().tolist()[0]
                # dima806/deepfake_vs_real_image_detection: 0=real, 1=fake
                secondary_fake_prob = float(probs_s[1])
            except Exception as e:
                logger.error("Secondary image inference failed: %s", e)

        # 3. Heuristic & Artifact Analysis
        artifact_score = self._run_artifact_analysis(image, image_path, reasons)

        # 4. Probabilistic Fusion
        weights = []
        probs = []
        
        if primary_fake_prob is not None:
            weights.append(self.weight_primary)
            probs.append(primary_fake_prob)
        if secondary_fake_prob is not None:
            weights.append(self.weight_secondary)
            probs.append(secondary_fake_prob)
            
        weights.append(self.weight_artifact)
        probs.append(artifact_score)
        
        total_w = sum(weights)
        if total_w > 0:
            fake_prob = sum(p * w for p, w in zip(probs, weights)) / total_w
        else:
            fake_prob = 0.5 # Neutral fallback

        # 5. Dynamic Calibration & Signal Agreement
        neural_certainty = 0.0
        if primary_fake_prob is not None and secondary_fake_prob is not None:
            neural_certainty = 1.0 - abs(primary_fake_prob - secondary_fake_prob)
            # Pull towards midpoint if they disagree wildly
            if abs(primary_fake_prob - secondary_fake_prob) > 0.6:
                fake_prob = (fake_prob * 0.7) + (0.5 * 0.3)
                logger.info("High neural divergence detected, dampening score.")

        fake_prob = max(0.0, min(1.0, fake_prob))
        label = "ai-generated" if fake_prob >= 0.55 else "authentic"
        confidence = fake_prob if label == "ai-generated" else 1.0 - fake_prob

        # Log findings
        if primary_fake_prob is not None:
            reasons.append(self._make_reason(
                "primary_neural_analysis",
                "high" if primary_fake_prob > 0.8 else "medium" if primary_fake_prob > 0.4 else "low",
                f"Primary vision model indicates {primary_fake_prob:.1%} probability of synthetic patterns.",
                f"Model: {self.primary_model_name}"
            ))

        if secondary_fake_prob is not None:
            reasons.append(self._make_reason(
                "secondary_verification",
                "medium",
                f"Secondary deepfake detector confirms {secondary_fake_prob:.1%} probability of manipulation.",
                f"Model: {self.secondary_model_name}"
            ))

        self._cleanup_gpu()
        logger.info("Forensic image analysis complete: label=%s, fake_prob=%.4f", label, fake_prob)

        return self._format_result(
            label=label,
            confidence=confidence,
            fake_probability=fake_prob,
            reasons=reasons,
            extra={
                "technical_signals": {
                    "primary_fake_prob": round(primary_fake_prob, 4) if primary_fake_prob is not None else None,
                    "secondary_fake_prob": round(secondary_fake_prob, 4) if secondary_fake_prob is not None else None,
                    "artifact_score": round(artifact_score, 4),
                    "neural_certainty": round(neural_certainty, 4)
                }
            }
        )

    def _run_artifact_analysis(self, image: Image.Image, image_path: Optional[str], reasons: List) -> float:
        """Handcrafted forensic checks with probabilistic contribution."""
        checks = [
            self._check_exif(image, reasons),
            self._check_resolution(image, reasons),
            self._check_frequency_artifacts(image, reasons),
        ]
        return sum(checks) / len(checks)

    def _check_exif(self, image: Image.Image, reasons: List) -> float:
        try:
            exif = image._getexif()
        except:
            exif = None
            
        if not exif:
            reasons.append(self._make_reason("missing_metadata", "low", "Camera metadata absent — common in processed media.", "EXIF: Not found"))
            return 0.35 # Mild suspicion contribution
            
        parsed = {TAGS.get(k, k): v for k, v in exif.items()}
        software = str(parsed.get("Software", "")).lower()
        for sig in _AI_SOFTWARE_SIGNATURES:
            if sig in software:
                reasons.append(self._make_reason("ai_tool_signature", "high", f"AI software marker detected: {sig}", f"Software: {software}"))
                return 0.85
        return 0.1

    def _check_resolution(self, image: Image.Image, reasons: List) -> float:
        if image.size in _COMMON_AI_RESOLUTIONS:
            reasons.append(self._make_reason("standard_resolution", "low", f"Resolution {image.size} is a common output for digital assets.", ""))
            return 0.30
        return 0.1

    def _check_frequency_artifacts(self, image: Image.Image, reasons: List) -> float:
        try:
            arr = np.array(image.convert("L").resize((256, 256)))
            f = np.fft.fftshift(np.fft.fft2(arr))
            magnitude = np.log(np.abs(f) + 1)
            center = 128
            # Measure high-frequency energy ratio
            inner = magnitude[center-32:center+32, center-32:center+32].mean()
            outer = magnitude.mean()
            ratio = inner / outer if outer > 0 else 2.0
            
            # Recalibrated ratio threshold: Natural photos usually > 1.8
            if ratio < 1.4:
                reasons.append(self._make_reason("frequency_anomaly", "medium", "Unusual spectral distribution detected in frequency domain.", f"Energy Ratio: {ratio:.2f}"))
                return 0.65
            return 0.15
        except:
            return 0.2
