from __future__ import annotations

import os
from typing import Any, Dict, List

import torch
import yaml
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

from utils.logger import logger

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml",
)


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class VideoDeepfakeDetector:
    """Classifies individual frames as fake or real using a HuggingFace
    image-classification model and returns aggregated scores."""

    def __init__(self) -> None:
        cfg = _load_config()
        video_cfg = cfg["video"]
        self.model_name: str = video_cfg["model_name"]
        self.batch_size: int = video_cfg.get("batch_size", 8)
        self.device = torch.device(
            cfg.get("device", "cuda") if torch.cuda.is_available() else "cpu"
        )

        logger.info("Loading video model '%s' on %s", self.model_name, self.device)
        self.extractor = AutoImageProcessor.from_pretrained(self.model_name)
        self.model = AutoModelForImageClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        logger.info("Video model loaded successfully")

    @torch.no_grad()
    def _predict_batch(self, frames: List[Image.Image]) -> List[Dict[str, float]]:
        inputs = self.extractor(images=frames, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).cpu().tolist()

        id2label = self.model.config.id2label
        results = []
        for prob_row in probs:
            results.append({id2label[i]: round(p, 4) for i, p in enumerate(prob_row)})
        return results

    def predict(self, frames: List[Image.Image]) -> Dict[str, Any]:
        """Run inference on a list of PIL Images.

        Returns a dict with:
            - per_frame : list of per-frame label probability dicts
            - average   : averaged probabilities across all frames
            - label     : "fake" or "real" based on the dominant average class
            - confidence: the probability of the predicted label
        """
        if not frames:
            logger.warning("No frames provided for video prediction")
            return {"per_frame": [], "average": {}, "label": "unknown", "confidence": 0.0}

        logger.info("Running video inference on %d frames (batch_size=%d)", len(frames), self.batch_size)

        per_frame: List[Dict[str, float]] = []
        for start in range(0, len(frames), self.batch_size):
            batch = frames[start : start + self.batch_size]
            logger.debug("Processing frame batch %d–%d", start, start + len(batch) - 1)
            per_frame.extend(self._predict_batch(batch))

        if not per_frame:
             return {"per_frame": [], "average": {}, "label": "unknown", "confidence": 0.0}

        label_keys = per_frame[0].keys()
        average = {k: round(sum(f[k] for f in per_frame) / len(per_frame), 4) for k in label_keys}

        predicted_label = max(average, key=average.get)  # type: ignore[arg-type]
        confidence = average[predicted_label]

        # Robust label mapping
        fake_keywords = {"fake", "deepfake", "spoof"}
        real_keywords = {"real", "original", "natural"}
        
        fake_prob = sum(v for k, v in average.items() if any(kw in k.lower() for kw in fake_keywords))
        real_prob = sum(v for k, v in average.items() if any(kw in k.lower() for kw in real_keywords))
        
        if fake_prob == 0 and real_prob == 0:
            # Fallback
            fake_prob = 0.0
            real_prob = 1.0
            
        if fake_prob > real_prob:
            canonical_label = "fake"
            confidence = fake_prob
        else:
            canonical_label = "real"
            confidence = real_prob

        result: Dict[str, Any] = {
            "per_frame": per_frame,
            "average": average,
            "label": canonical_label,
            "confidence": confidence,
        }

        logger.info("Video result: label=%s, confidence=%.4f", canonical_label, confidence)
        return result
