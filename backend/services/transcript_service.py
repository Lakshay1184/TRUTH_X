"""
Truth_X Transcription Service.
Uses OpenAI Whisper for multi-lingual speech-to-text.
"""

from __future__ import annotations

import os
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

from typing import List, Optional, Dict, Any
from backend.utils.logger import logger

class TranscriptService:
    """Handles speech-to-text transcription using the Whisper model."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
        self.enabled = WHISPER_AVAILABLE and os.environ.get("TRANSCRIPTION_ENABLED", "false").lower() == "true"

    @property
    def model(self):
        """Lazy-load the Whisper model."""
        if not self.enabled:
            return None
            
        if self._model is None:
            try:
                logger.info(f"Loading Whisper model: {self.model_size}...")
                self._model = whisper.load_model(self.model_size)
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                self.enabled = False
        return self._model

    def transcribe_chunks(self, chunk_paths: List[str], status_callback: Optional[callable] = None) -> str:
        """
        Transcribe a list of audio chunks and stitch them into a single transcript.
        """
        if not self.enabled:
            if status_callback:
                status_callback("Transcription skipped (Lightweight mode active)")
            return ""

        full_transcript = []
        total_chunks = len(chunk_paths)

        for i, chunk_path in enumerate(chunk_paths):
            if status_callback:
                status_callback(f"Transcribing segment {i+1}/{total_chunks}...")
            
            try:
                logger.info(f"Transcribing chunk: {chunk_path}")
                model = self.model
                if model:
                    result = model.transcribe(chunk_path)
                    text = result.get("text", "").strip()
                    if text:
                        full_transcript.append(text)
                else:
                    logger.warning("Whisper model unavailable, skipping chunk")
            except Exception as e:
                logger.error(f"Transcription failed for chunk {chunk_path}: {e}")

        return " ".join(full_transcript)

    def transcribe_file(self, audio_path: str, status_callback: Optional[callable] = None) -> Optional[str]:
        """Transcribe a single audio file directly."""
        if not self.enabled:
            return None
            
        if status_callback:
            status_callback("Analyzing speech patterns...")
            
        try:
            model = self.model
            if model:
                result = model.transcribe(audio_path)
                return result.get("text", "").strip()
            return None
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path}: {e}")
            return None
