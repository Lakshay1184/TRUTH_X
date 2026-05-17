"""
Live Detection API for Truth_X.
Handles real-time audio analysis via WebSockets.
"""

import asyncio
import json
import time
import base64
import numpy as np
import io
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List, Optional

from backend.utils.logger import logger

router = APIRouter(prefix="/live", tags=["live"])

# Shared detector instance
_live_audio_detector = None

def get_live_audio_detector():
    global _live_audio_detector
    if _live_audio_detector is None:
        try:
            from backend.detectors.audio_detector import AudioDeepfakeDetector
            _live_audio_detector = AudioDeepfakeDetector()
        except Exception as e:
            logger.error(f"Failed to initialize live audio detector: {e}")
    return _live_audio_detector

class RollingAggregator:
    """Aggregates rolling inference results for stable live updates with temporal smoothing."""
    def __init__(self, window_size: int = 8):
        self.window_size = window_size
        self.history = []
        self.labels = []

    def add(self, prob: float, label: str):
        self.history.append(prob)
        self.labels.append(label)
        if len(self.history) > self.window_size:
            self.history.pop(0)
            self.labels.pop(0)

    def get_stable_metrics(self) -> Dict[str, Any]:
        if not self.history:
            return {"fake_prob": 0.5, "label": "suspicious", "confidence": 0.5}
        
        # Weighted average: more recent results have higher impact
        weights = np.linspace(0.5, 1.0, len(self.history))
        avg_prob = np.average(self.history, weights=weights)
        
        # Most frequent label in recent history
        from collections import Counter
        stable_label = Counter(self.labels).most_common(1)[0][0]
        
        # Confidence based on consistency of recent labels
        consistency = Counter(self.labels).most_common(1)[0][1] / len(self.labels)
        
        return {
            "fake_prob": float(avg_prob),
            "label": stable_label,
            "confidence": float(consistency)
        }

@router.websocket("/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Production-grade Live Audio WebSocket established")
    
    detector = get_live_audio_detector()
    if detector is None or detector.model is None:
        await websocket.send_json({"type": "ERROR", "message": "Neural detection engine offline"})
        await websocket.close()
        return

    # Configuration for MelodyMachine V2 (optimized for 3s chunks)
    SAMPLE_RATE = 16000
    CHUNK_DURATION_SEC = 3.0
    REQUIRED_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_SEC)
    
    chunk_buffer = []
    total_samples = 0
    aggregator = RollingAggregator(window_size=6)
    
    try:
        while True:
            # Receive base64 PCM data
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
            except (WebSocketDisconnect, json.JSONDecodeError):
                break
            
            if data.get("type") == "AUDIO_CHUNK":
                payload = data.get("data")
                if not payload:
                    continue
                    
                # Decode and convert to float32 normalized
                try:
                    audio_bytes = base64.b64decode(payload)
                    audio_chunk = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    chunk_buffer.append(audio_chunk)
                    total_samples += len(audio_chunk)
                except Exception as e:
                    logger.warning(f"Audio decode error: {e}")
                    continue
                
                # Perform analysis when we have enough for a valid MelodyMachine V2 segment
                if total_samples >= REQUIRED_SAMPLES:
                    full_audio = np.concatenate(chunk_buffer)
                    # Take exactly the required samples for the detector
                    analysis_segment = full_audio[:REQUIRED_SAMPLES]
                    
                    # 1. Neural Inference (MelodyMachine V2)
                    start_time = time.perf_counter()
                    result = detector._predict_segment(analysis_segment, SAMPLE_RATE)
                    latency = (time.perf_counter() - start_time) * 1000
                    
                    # 2. Forensic Signal Extraction
                    spectral = detector._extract_spectral_features(analysis_segment, SAMPLE_RATE)
                    anomaly_score = detector._spectral_anomaly_score(spectral)
                    
                    # 3. Decision Logic
                    base_fake_prob = result.get("fake_probability", 0.5)
                    # Boost detection if spectral anomalies match model suspicion
                    final_instant_prob = np.clip(base_fake_prob + (anomaly_score * 0.2), 0.0, 1.0)
                    
                    label = "real"
                    if final_instant_prob > 0.75: label = "fake"
                    elif final_instant_prob > 0.45: label = "suspicious"
                    
                    # 4. Temporal Smoothing
                    aggregator.add(final_instant_prob, label)
                    metrics = aggregator.get_stable_metrics()
                    
                    # 5. Live UI Telemetry Update
                    await websocket.send_json({
                        "type": "ANALYSIS_RESULT",
                        "fake_probability": round(metrics["fake_prob"], 4),
                        "label": metrics["label"],
                        "confidence": round(metrics["confidence"] * 100, 1),
                        "latency_ms": round(latency, 2),
                        "forensics": {
                            "spectral_anomaly": anomaly_score > 0.15,
                            "cadence_inconsistency": base_fake_prob > 0.6 and spectral.get("mfcc_std", 10) < 6.0,
                            "resonance_check": spectral.get("spectral_flatness", 0) > 0.008,
                            "cloning_signal": base_fake_prob > 0.8
                        }
                    })
                    
                    # Slide window: keep last 1 second for overlap smoothing
                    overlap_samples = SAMPLE_RATE
                    chunk_buffer = [full_audio[-(total_samples - REQUIRED_SAMPLES + overlap_samples):]]
                    total_samples = len(chunk_buffer[0])

            elif data.get("type") == "END_SESSION":
                break

    except Exception as e:
        logger.error(f"Live pipeline error: {e}")
    finally:
        logger.info("Live audio session terminated")
