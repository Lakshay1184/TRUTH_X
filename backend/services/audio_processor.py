"""
Truth_X Audio Processor Service.
Handles normalization (mono, 16kHz) and intelligent chunking using pydub.
"""

from __future__ import annotations

import os
from typing import List, Optional
from pydub import AudioSegment
from backend.utils.logger import logger

class AudioProcessor:
    """Handles audio format conversion, normalization, and chunking."""

    def __init__(self, processing_dir: str = "data/processed"):
        self.processing_dir = processing_dir
        os.makedirs(self.processing_dir, exist_ok=True)

    def normalize(self, input_path: str, status_callback: Optional[callable] = None) -> Optional[str]:
        """Convert any audio/video file to normalized WAV (mono, 16kHz)."""
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return None

        if status_callback:
            status_callback("Normalizing audio (16kHz, Mono)...")

        try:
            # Generate output path
            base_name = os.path.basename(input_path)
            output_name = f"normalized_{os.path.splitext(base_name)[0]}.wav"
            output_path = os.path.join(self.processing_dir, output_name)

            # Load and process
            audio = AudioSegment.from_file(input_path)
            audio = audio.set_channels(1).set_frame_rate(16000)
            
            # Export
            audio.export(output_path, format="wav")
            logger.info(f"Normalized audio saved: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Normalization failed for {input_path}: {e}")
            return None

    def chunk(self, wav_path: str, chunk_minutes: int = 10, status_callback: Optional[callable] = None) -> List[str]:
        """
        Split a long WAV file into smaller chunks to avoid memory spikes 
        during transcription and handle long-form content.
        """
        if not os.path.exists(wav_path):
            logger.error(f"WAV file not found: {wav_path}")
            return []

        if status_callback:
            status_callback(f"Chunking long audio ({chunk_minutes}m segments)...")

        try:
            audio = AudioSegment.from_wav(wav_path)
            chunk_ms = chunk_minutes * 60 * 1000
            
            # If shorter than chunk size, return as single item
            if len(audio) <= chunk_ms:
                return [wav_path]

            chunks = []
            base_name = os.path.splitext(os.path.basename(wav_path))[0]

            for i, start in enumerate(range(0, len(audio), chunk_ms)):
                chunk = audio[start : start + chunk_ms]
                chunk_name = f"{base_name}_chunk_{i}.wav"
                chunk_path = os.path.join(self.processing_dir, chunk_name)
                
                chunk.export(chunk_path, format="wav")
                chunks.append(chunk_path)

            logger.info(f"Created {len(chunks)} chunks from {wav_path}")
            return chunks

        except Exception as e:
            logger.error(f"Chunking failed for {wav_path}: {e}")
            return [wav_path] # Return original as fallback if chunking fails

    def cleanup(self, file_paths: List[str]):
        """Clean up temporary processing files."""
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.unlink(path)
                    logger.debug(f"Cleaned up: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {path}: {e}")
