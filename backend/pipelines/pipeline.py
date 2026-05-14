"""truth.x — Simplified Pipeline Entry Point (Updated).

This module provides a simplified `DeepfakeDetectionPipeline` wrapper
that delegates to the main_pipeline for full functionality.
Maintains backwards compatibility with the API layer.
"""

from __future__ import annotations

import gc
import os
import time
from typing import Any, Dict, Optional

import torch
import yaml

from backend.utils.logger import logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class DeepfakeDetectionPipeline:
    """Full detection pipeline — lazy-loads models and runs all detectors.

    This is the simplified wrapper used by api.py. It delegates to
    the main_pipeline for the full orchestration logic.
    """

    def __init__(self) -> None:
        self.cfg = _load_config()
        self.device = self.cfg.get("device", "cuda" if torch.cuda.is_available() else "cpu")
        self._inner_pipeline = None
        logger.info("Pipeline initialized (device=%s)", self.device)

    @property
    def _pipeline(self):
        """Lazy-load the inner pipeline."""
        if self._inner_pipeline is None:
            from backend.pipelines.main_pipeline import DeepfakeDetectionPipeline as MainPipeline
            self._inner_pipeline = MainPipeline()
        return self._inner_pipeline

    # ── Lazy model accessors (backwards compatible) ──────────────────────

    @property
    def video_detector(self):
        self._pipeline.load_model("video")
        return self._pipeline.models.get("video")

    @property
    def audio_detector(self):
        self._pipeline.load_model("audio")
        return self._pipeline.models.get("audio")

    @property
    def text_detector(self):
        self._pipeline.load_model("text")
        return self._pipeline.models.get("text")

    @property
    def faiss_search(self):
        self._pipeline.load_model("faiss")
        return self._pipeline.models.get("faiss")

    def preload_all(self) -> None:
        """Preload all models (call at startup for faster first request)."""
        logger.info("Preloading all models...")
        _ = self.video_detector
        _ = self.audio_detector
        _ = self.text_detector
        _ = self.faiss_search
        logger.info("All models preloaded ✓")

    # ── Main processing ───────────────────────────────────────────────────

    def process(
        self,
        video_path: Optional[str] = None,
        query: Optional[str] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Run the full detection pipeline.

        Args:
            video_path: Path to video file (optional).
            query: Text query for text detection + article search (optional).
            progress_callback: Optional callable(progress_pct: int, status: str).

        Returns:
            Complete analysis report dict.
        """
        # Convert progress_callback to status_callback format
        status_messages = {
            "starting": 5,
            "extracting metadata": 10,
            "extracting frames": 20,
            "detecting faces": 30,
            "analyzing video": 40,
            "analyzing audio": 60,
            "analyzing text": 70,
            "searching articles": 80,
            "aggregating results": 90,
            "complete": 100,
        }

        def _status_cb(msg: str) -> None:
            if progress_callback:
                # Map status message to progress percentage
                lower_msg = msg.lower()
                pct = 50
                for key, val in status_messages.items():
                    if key in lower_msg:
                        pct = val
                        break
                progress_callback(pct, lower_msg)

        # Delegate to the main pipeline
        report = self._pipeline.process(
            video_path=video_path,
            query=query,
            status_callback=_status_cb,
        )

        return report
