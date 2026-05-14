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

    def _format_result(
        self,
        label: str,
        confidence: float,
        fake_probability: float,
        reasons: Optional[List[Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Standard result format with explainability."""
        result: Dict[str, Any] = {
            "label": label,
            "confidence": round(confidence, 4),
            "fake_probability": round(fake_probability, 4),
            "real_probability": round(1.0 - fake_probability, 4),
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
