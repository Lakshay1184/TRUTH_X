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
        Ingest a URL (YouTube, Twitter, etc.), process it, and return the transcript.
        """
        temp_files = []
        try:
            # 1. Download
            if status_callback:
                status_callback("Connecting to media stream...")
            
            downloaded_path = self.downloader.download(url, status_callback)
            if not downloaded_path:
                logger.error(f"FORENSIC FAILURE: Media download failed for {url}")
                return None
            
            logger.info(f"FORENSIC SUCCESS: Media internalized at {downloaded_path}")
            temp_files.append(downloaded_path)

            # 2. Normalize
            if status_callback:
                status_callback("Extracting audio forensics...")
            
            normalized_path = self.audio_processor.normalize(downloaded_path, status_callback)
            if normalized_path:
                logger.info(f"FORENSIC SUCCESS: Audio normalized to WAV at {normalized_path}")
                temp_files.append(normalized_path)
            else:
                logger.warning(f"FORENSIC WARNING: Audio normalization failed, attempting raw fallback")
                normalized_path = downloaded_path # Fallback

            # 3. Chunk
            if status_callback:
                status_callback("Segmenting signal for AI processing...")
            
            chunks = self.audio_processor.chunk(normalized_path, chunk_minutes=10, status_callback=status_callback)
            if chunks:
                logger.info(f"FORENSIC SUCCESS: Generated {len(chunks)} signal segments for processing")
                if chunks[0] != normalized_path:
                    temp_files.extend(chunks)
            else:
                logger.error("FORENSIC FAILURE: Signal segmentation produced zero chunks")
                return None

            # 4. Transcribe
            if status_callback:
                status_callback("Generating AI transcript (Whisper)...")
            
            transcript = self.transcriber.transcribe_chunks(chunks, status_callback)
            
            if not transcript or not transcript.strip():
                logger.error(f"FORENSIC FAILURE: Whisper produced empty transcript for {url}")
                if status_callback:
                    status_callback("Transcription failed: No speech detected in signal")
                return None

            logger.info(f"FORENSIC SUCCESS: Intelligence transcript generated (chars={len(transcript)})")
            return transcript.strip()

        except Exception as e:
            logger.error(f"FORENSIC CRITICAL: Media pipeline crash for {url}: {e}")
            return None
        finally:
            # 5. Cleanup
            self.audio_processor.cleanup(temp_files)
            logger.info("FORENSIC CLEANUP: Temporary ingestion artifacts removed")

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
