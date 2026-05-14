"""truth.x — Image AI Detection with Ensemble Analysis.

Architecture:
    1. Existing ViT classifier (LOCAL) — primary deepfake/real classification
    2. CLIP Embedding Analysis (HF API) — synthetic image detection
    3. Metadata + Artifact Analysis (LOCAL) — EXIF and artifact inspection

Detects: Stable Diffusion, Midjourney, Flux, DALL-E, GAN-generated, manipulated photos.
"""

from __future__ import annotations

import gc
import math
import os
import struct
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import yaml
from PIL import Image
from PIL.ExifTags import TAGS

from backend.detectors.base import BaseDetector
from backend.utils.logger import logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    (1024, 576), (576, 1024), (1152, 896), (896, 1152),
}


class ImageAIDetector(BaseDetector):
    """Detects AI-generated images using ensemble of ViT + CLIP + metadata analysis."""

    modality = "image"

    def __init__(self) -> None:
        super().__init__()
        cfg = _load_config()
        video_cfg = cfg.get("video", {})
        image_cfg = cfg.get("image", {})

        # Reuse the existing ViT model for frame-level classification
        self.model_name: str = video_cfg.get("model_name", "dima806/deepfake_vs_real_image_detection")
        self.batch_size: int = video_cfg.get("batch_size", 8)

        # CLIP model for embedding analysis (via HF API)
        self.clip_model: str = image_cfg.get(
            "clip_model", "openai/clip-vit-base-patch32"
        )

        # Ensemble weights
        self.weight_vit: float = image_cfg.get("weight_vit", 0.45)
        self.weight_clip: float = image_cfg.get("weight_clip", 0.25)
        self.weight_artifact: float = image_cfg.get("weight_artifact", 0.30)

        # Load ViT model (reuse video model)
        self._vit_model = None
        self._vit_extractor = None

        logger.info("ImageAIDetector initialized (ViT=%s)", self.model_name)

    def _ensure_vit(self) -> None:
        """Lazy-load the ViT model."""
        if self._vit_model is not None:
            return
        from transformers import AutoImageProcessor, AutoModelForImageClassification
        logger.info("Loading ViT model for image detection: %s", self.model_name)
        self._vit_extractor = AutoImageProcessor.from_pretrained(self.model_name)
        self._vit_model = AutoModelForImageClassification.from_pretrained(self.model_name)
        self._vit_model.to(self.device)
        self._vit_model.eval()
        logger.info("ViT model loaded for image detection ✓")

    # ── Main predict ──────────────────────────────────────────────────────

    def predict(self, image: Image.Image, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Analyze a single image for AI generation.

        Args:
            image: PIL Image to analyze
            image_path: Optional path to the original file (for metadata)

        Returns:
            Detection result with explainability
        """
        reasons: List[Dict[str, Any]] = []

        # ── 1. ViT Classification (LOCAL) ──
        vit_score = self._run_vit_analysis(image, reasons)

        # ── 2. Metadata & Artifact Analysis (LOCAL) ──
        artifact_score = self._run_artifact_analysis(image, image_path, reasons)

        # ── 3. CLIP Analysis (HF API — optional) ──
        clip_score = self._run_clip_analysis(image, reasons)

        # ── Ensemble ──
        if clip_score is not None:
            fake_prob = (
                self.weight_vit * vit_score
                + self.weight_clip * clip_score
                + self.weight_artifact * artifact_score
            )
        else:
            # Fallback: redistribute CLIP weight
            total = self.weight_vit + self.weight_artifact
            fake_prob = (
                (self.weight_vit / total) * vit_score
                + (self.weight_artifact / total) * artifact_score
            )

        fake_prob = max(0.0, min(1.0, fake_prob))
        label = "ai-generated" if fake_prob >= 0.5 else "authentic"
        confidence = fake_prob if label == "ai-generated" else 1.0 - fake_prob

        self._cleanup_gpu()

        logger.info("Image result: label=%s, confidence=%.4f, fake_prob=%.4f",
                     label, confidence, fake_prob)

        return self._format_result(
            label=label,
            confidence=confidence,
            fake_probability=fake_prob,
            reasons=reasons,
            extra={
                "ensemble_scores": {
                    "vit_score": round(vit_score, 4),
                    "clip_score": round(clip_score, 4) if clip_score is not None else None,
                    "artifact_score": round(artifact_score, 4),
                },
            },
        )

    # ── ViT Analysis ──────────────────────────────────────────────────────

    @torch.no_grad()
    def _run_vit_analysis(self, image: Image.Image, reasons: List) -> float:
        """Run ViT classifier on the image."""
        self._ensure_vit()
        try:
            inputs = self._vit_extractor(images=[image], return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self._vit_model(**inputs)
            probs = torch.softmax(outputs.logits / 1.5, dim=-1).cpu().tolist()[0]

            id2label = self._vit_model.config.id2label
            fake_prob = 0.0
            for i, p in enumerate(probs):
                lbl = str(id2label.get(i, "")).lower()
                if any(kw in lbl for kw in ("fake", "deepfake", "spoof", "generated")):
                    fake_prob = p

            if fake_prob > 0.6:
                reasons.append(self._make_reason(
                    "vit_classification",
                    "high" if fake_prob > 0.8 else "medium",
                    f"ViT classifier detected synthetic patterns ({fake_prob:.0%} confidence)",
                    f"Model: {self.model_name}",
                ))
            return fake_prob

        except Exception as e:
            logger.error("ViT image analysis failed: %s", e)
            return 0.5

    # ── Artifact Analysis ─────────────────────────────────────────────────

    def _run_artifact_analysis(
        self, image: Image.Image, image_path: Optional[str], reasons: List,
    ) -> float:
        """Analyze image metadata and artifacts for AI generation signatures."""
        score = 0.0
        checks_run = 0

        # 1. EXIF metadata check
        exif_score = self._check_exif(image, reasons)
        score += exif_score
        checks_run += 1

        # 2. Resolution check (common AI resolutions)
        res_score = self._check_resolution(image, reasons)
        score += res_score
        checks_run += 1

        # 3. Frequency domain analysis
        freq_score = self._check_frequency_artifacts(image, reasons)
        score += freq_score
        checks_run += 1

        # 4. Color distribution analysis
        color_score = self._check_color_distribution(image, reasons)
        score += color_score
        checks_run += 1

        return score / max(checks_run, 1)

    def _check_exif(self, image: Image.Image, reasons: List) -> float:
        """Check EXIF metadata for AI tool signatures or missing data."""
        try:
            exif_data = image._getexif()
        except (AttributeError, Exception):
            exif_data = None

        if exif_data is None or len(exif_data) == 0:
            reasons.append(self._make_reason(
                "missing_exif",
                "medium",
                "No EXIF metadata found — AI-generated images typically lack camera metadata",
                "EXIF data: None",
            ))
            return 0.6

        # Check for AI software signatures
        parsed = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            parsed[str(tag_name).lower()] = str(value).lower()

        software = parsed.get("software", "")
        make = parsed.get("make", "")
        model = parsed.get("model", "")

        for sig in _AI_SOFTWARE_SIGNATURES:
            for field_val in (software, make, model):
                if sig in field_val:
                    reasons.append(self._make_reason(
                        "ai_tool_signature",
                        "critical",
                        f"AI generation software detected in metadata: '{sig}'",
                        f"Field value: '{field_val}'",
                    ))
                    return 0.95

        # Has real camera metadata
        if make or model:
            return 0.1  # Likely real photo

        return 0.3

    def _check_resolution(self, image: Image.Image, reasons: List) -> float:
        """Check if resolution matches common AI generation sizes."""
        w, h = image.size
        if (w, h) in _COMMON_AI_RESOLUTIONS:
            reasons.append(self._make_reason(
                "ai_resolution_match",
                "low",
                f"Resolution {w}×{h} matches common AI generation sizes",
                f"Common AI resolutions: 512², 768², 1024², etc.",
            ))
            return 0.5
        return 0.1

    def _check_frequency_artifacts(self, image: Image.Image, reasons: List) -> float:
        """Analyze frequency domain for GAN/diffusion artifacts."""
        try:
            import cv2
            arr = np.array(image.convert("L").resize((256, 256)))
            # FFT analysis
            f_transform = np.fft.fft2(arr.astype(np.float32))
            f_shift = np.fft.fftshift(f_transform)
            magnitude = np.log1p(np.abs(f_shift))

            # Check for unusual frequency patterns
            center = magnitude.shape[0] // 2
            # High-frequency energy ratio
            inner = magnitude[center - 32:center + 32, center - 32:center + 32]
            outer_mask = np.ones_like(magnitude, dtype=bool)
            outer_mask[center - 32:center + 32, center - 32:center + 32] = False
            outer = magnitude[outer_mask]

            inner_energy = float(np.mean(inner))
            outer_energy = float(np.mean(outer))

            if outer_energy > 0 and inner_energy / outer_energy < 1.5:
                reasons.append(self._make_reason(
                    "frequency_anomaly",
                    "medium",
                    "Unusual frequency distribution — possible synthetic generation artifacts",
                    f"Inner/outer energy ratio: {inner_energy / outer_energy:.2f} (natural photos typically >2.0)",
                ))
                return 0.55

            return 0.2

        except Exception as e:
            logger.debug("Frequency analysis failed: %s", e)
            return 0.3

    def _check_color_distribution(self, image: Image.Image, reasons: List) -> float:
        """Analyze color distribution for AI generation patterns."""
        try:
            arr = np.array(image.convert("RGB")).astype(np.float32)
            # Channel-wise statistics
            means = arr.mean(axis=(0, 1))
            stds = arr.std(axis=(0, 1))

            # AI images often have unusually uniform color distributions
            std_variance = float(np.std(stds))
            if std_variance < 5.0:
                reasons.append(self._make_reason(
                    "uniform_color_distribution",
                    "low",
                    "Unusually uniform color distribution across channels",
                    f"Channel std variance: {std_variance:.2f} (natural: >8.0)",
                ))
                return 0.45

            return 0.15

        except Exception as e:
            logger.debug("Color analysis failed: %s", e)
            return 0.3

    # ── CLIP Analysis ─────────────────────────────────────────────────────

    def _run_clip_analysis(self, image: Image.Image, reasons: List) -> Optional[float]:
        """Run CLIP embedding analysis via HF API (optional)."""
        try:
            from backend.services.hf_inference import run_hf_inference

            # Convert image to base64
            import base64
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Use zero-shot classification with image
            result = run_hf_inference(
                self.clip_model,
                {
                    "inputs": {
                        "image": img_b64,
                    },
                    "parameters": {
                        "candidate_labels": [
                            "a real photograph taken by a camera",
                            "an AI generated image, digital art, synthetic",
                        ],
                    },
                },
            )

            if result and isinstance(result, dict) and "scores" in result:
                labels = result.get("labels", [])
                scores = result.get("scores", [])
                label_scores = dict(zip(labels, scores))
                ai_score = 0.0
                for lbl, sc in label_scores.items():
                    if "ai" in lbl.lower() or "synthetic" in lbl.lower() or "generated" in lbl.lower():
                        ai_score = sc

                if ai_score > 0.5:
                    reasons.append(self._make_reason(
                        "clip_synthetic_detection",
                        "high" if ai_score > 0.7 else "medium",
                        f"CLIP embedding analysis detects synthetic patterns ({ai_score:.0%})",
                        f"Model: {self.clip_model}",
                    ))

                return ai_score

        except Exception as e:
            logger.debug("CLIP analysis unavailable: %s", e)

        return None
