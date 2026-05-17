"""
Truth_X Media Pipeline Orchestrator.
Coordinates downloading, processing, and transcription.
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, List
from backend.utils.logger import logger
from backend.services.media_downloader import MediaDownloader
from backend.services.audio_processor import AudioProcessor
from backend.services.transcript_service import TranscriptService

class MediaPipeline:
    """Orchestrates the media ingestion pipeline."""

    def __init__(self):
        self.downloader = MediaDownloader()
        self.audio_processor = AudioProcessor()
        self.transcriber = TranscriptService()

    def ingest_url(self, url: str, status_callback: Optional[callable] = None) -> Optional[str]:
        """
        Ingest a URL (YouTube, Twitter, etc.). 
        In this version, remote media downloading is disabled for stability.
        Returns a context string based on metadata.
        """
        try:
            if status_callback:
                status_callback("Extracting source intelligence...")
            
            info = self.downloader.get_info(url)
            if info:
                title = info.get("title", "Unknown Source")
                description = info.get("description", "")
                logger.info(f"FORENSIC SUCCESS: Source metadata extracted: {title}")
                
                context = f"SOURCE TITLE: {title}\nSOURCE URL: {url}\nDESCRIPTION: {description}\n\n"
                context += "NOTE: Full transcript unavailable for remote sources in cloud deployment. Analysis based on metadata and technical signals."
                
                if status_callback:
                    status_callback("Intelligence metadata extracted ✓")
                return context

            # Fallback for generic URLs
            from backend.utils.web import fetch_url_text
            text = fetch_url_text(url)
            if text:
                return text
            
            return f"Source URL: {url} (Detailed analysis unavailable)"

        except Exception as e:
            logger.error(f"FORENSIC CRITICAL: Media pipeline crash for {url}: {e}")
            return None

    def ingest_file(self, file_path: str, status_callback: Optional[callable] = None) -> Optional[str]:
        """
        Process a local file and return the transcript.
        """
        temp_files = []
        try:
            # 1. Normalize
            if status_callback:
                status_callback("Extracting audio forensics...")
            normalized_path = self.audio_processor.normalize(file_path, status_callback)
            if not normalized_path:
                logger.error(f"Media normalization failed for {file_path}")
                return None
            temp_files.append(normalized_path)

            # 2. Chunk
            if status_callback:
                status_callback("Segmenting signal for AI processing...")
            chunks = self.audio_processor.chunk(normalized_path, chunk_minutes=10, status_callback=status_callback)
            if chunks and chunks[0] != normalized_path:
                temp_files.extend(chunks)

            # 3. Transcribe
            if not self.transcriber.enabled:
                logger.info(f"Transcription disabled (Lightweight mode) for local file: {file_path}")
                if status_callback:
                    status_callback("Transcription skipped: Lightweight deployment mode active")
                return "NOTE: Full transcript unavailable in lightweight cloud mode."

            if status_callback:
                status_callback("Generating AI transcript (Whisper)...")
            transcript = self.transcriber.transcribe_chunks(chunks, status_callback)
            
            if not transcript or not transcript.strip():
                logger.error(f"Whisper produced empty transcript for local file {file_path}")
                if status_callback:
                    status_callback("Transcription failed: No speech detected")
                return None

            return transcript.strip()

        except Exception as e:
            logger.error(f"Media pipeline failed for file {file_path}: {e}")
            return None
        finally:
            # 4. Cleanup
            self.audio_processor.cleanup(temp_files)
