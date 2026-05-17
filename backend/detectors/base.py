"""truth.x — Abstract Base Detector.

All detectors inherit from this base class to ensure consistent
interface, explainability output, and lifecycle management.
"""

from __future__ import annotations

import gc
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import torch

from backend.utils.logger import logger


class BaseDetector(ABC):
    """Abstract base for all truth.x detection modules."""

    modality: str = "unknown"  # Override in subclasses

    def __init__(self) -> None:
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self._load_time: float = 0.0

    @abstractmethod
    def predict(self, *args, **kwargs) -> Dict[str, Any]:
        """Run detection and return results with explainability."""
        ...

    @staticmethod
    def interpret_authenticity(authenticity_score: float) -> str:
        """Standard interpretation of AI authenticity percentage (0-100).
        USED FOR: Analyze / AI Detection mode.
        """
        score = max(0.0, min(100.0, authenticity_score))
        if score <= 20:
            return "Likely AI Generated / Manipulated"
        if score <= 40:
            return "Suspicious / Potentially Synthetic"
        if score <= 60:
            return "Uncertain / Mixed Signals"
        if score <= 80:
            return "Likely Authentic / Human"
        return "Strongly Authentic / Human"

    @staticmethod
    def interpret_credibility(credibility_score: float) -> str:
        """Standard interpretation of factual credibility percentage (0-100).
        USED FOR: Source Check / News Verification mode.
        """
        score = max(0.0, min(100.0, credibility_score))
        if score <= 15:
            return "Fake News"
        if score <= 30:
            return "Likely False"
        if score <= 45:
            return "Misleading"
        if score <= 60:
            return "Mixed Evidence"
        if score <= 80:
            return "Likely True"
        return "Verified"

    def _format_result(
        self,
        label: str,
        confidence: float,
        fake_probability: float,
        reasons: Optional[List[Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Standard result format with explainability and unified scoring."""
        # Calculate authenticity score (0-100)
        # Note: 1.0 - fake_probability gives authenticity as 0.0-1.0
        auth_score = (1.0 - fake_probability) * 100
        verdict = self.interpret_authenticity(auth_score)

        result: Dict[str, Any] = {
            "label": label,
            "confidence": round(confidence, 4),
            "fake_probability": round(fake_probability, 4),
            "real_probability": round(1.0 - fake_probability, 4),
            "authenticity_score": round(auth_score, 2),
            "verdict": verdict,
            "modality": self.modality,
            "explainability": {
                "reasons": reasons or [],
                "suspicious_indicators": [
                    r["indicator"] for r in (reasons or [])
                    if r.get("severity") in ("high", "critical")
                ],
            },
        }
        if extra:
            result.update(extra)
        return result

    @staticmethod
    def _make_reason(
        indicator: str,
        severity: str,
        detail: str,
        evidence: str = "",
    ) -> Dict[str, str]:
        """Create a standardized explainability reason entry."""
        return {
            "indicator": indicator,
            "severity": severity,  # "low", "medium", "high", "critical"
            "detail": detail,
            "evidence": evidence,
        }

    def _cleanup_gpu(self) -> None:
        """Free GPU memory after inference."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
