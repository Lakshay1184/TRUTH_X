"""truth.x — Main Detection Pipeline Orchestrator (UPGRADED).

Coordinates all detection modules with full explainability:
    1. Video deepfake detection (ViT + temporal + face landmarks)
    2. Audio synthetic voice detection (model + spectral)
    3. Text AI detection (DeBERTa + perplexity + burstiness + stylometric)
    4. Image AI detection (ViT + CLIP + artifacts) [NEW]
    5. Fake news RAG verification (claims + evidence + NLI) [NEW]
    6. Unified explainability [NEW]
    7. Credibility scoring [NEW]

Usage (CLI):
    python -m backend.pipelines.main_pipeline --video path/to/video.mp4
    python -m backend.pipelines.main_pipeline --query "Some suspicious claim"
    python -m backend.pipelines.main_pipeline --text-file path/to/document.pdf
    python -m backend.pipelines.main_pipeline --video clip.mp4 --query "Is this real?"
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import yaml
from dotenv import load_dotenv

from backend.utils.logger import logger
from backend.utils.media import extract_video_metadata, find_ffprobe
from backend.pipelines.preprocessing import (
    extract_frames_adaptive,
    detect_and_crop_faces,
    align_faces,
    extract_audio,
)
from backend.pipelines.postprocessing import (
    aggregate_results,
    compute_risk_score,
    generate_drift_data,
)

# ─── Config ──────────────────────────────────────────────────────────────

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        logger.warning("Config file not found at %s, using defaults", CONFIG_PATH)
        return {
            "device": "cpu",
            "video": {"frame_sample_rate": 1, "max_frames": 32},
            "temp_dir": "data/processed",
        }
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── Pipeline ────────────────────────────────────────────────────────────

class DeepfakeDetectionPipeline:
    """Orchestrates all detection, preprocessing, and postprocessing stages.

    Models are loaded lazily on first use to minimize startup time
    and memory consumption when only a subset of detectors is needed.
    """

    def __init__(self, models: Optional[Dict[str, Any]] = None) -> None:
        self.config = _load_config()
        self.models: Dict[str, Any] = models if models else {}
        self.ffprobe_path = find_ffprobe()

        # New components (lazy-loaded)
        self._explainer = None
        self._credibility_engine = None
        self._claim_extractor = None
        self._evidence_retriever = None
        self._contradiction_detector = None
        self._provenance_engine = None

        if self.ffprobe_path:
            logger.info("FFprobe found: %s", self.ffprobe_path)
        else:
            logger.warning("FFprobe NOT found — using FFmpeg fallback")

    # ── Lazy Model Loading ───────────────────────────────────────────────

    def load_model(self, model_name: str) -> None:
        """Load a detector/service on demand if not already loaded."""
        if model_name in self.models and self.models[model_name] is not None:
            return

        try:
            if model_name == "video":
                logger.info("Loading Video Deepfake Detector...")
                from backend.detectors.video_detector import VideoDeepfakeDetector
                self.models["video"] = VideoDeepfakeDetector()

            elif model_name == "audio":
                logger.info("Loading Audio Deepfake Detector...")
                from backend.detectors.audio_detector import AudioDeepfakeDetector
                self.models["audio"] = AudioDeepfakeDetector()

            elif model_name == "text":
                logger.info("Loading Text AI Detector...")
                from backend.detectors.text_detector import TextAIDetector
                self.models["text"] = TextAIDetector()

            elif model_name == "image":
                logger.info("Loading Image AI Detector...")
                from backend.detectors.image_detector import ImageAIDetector
                self.models["image"] = ImageAIDetector()

            elif model_name == "faiss":
                logger.info("Loading FAISS Search Service...")
                from backend.services.faiss_service import FAISSSearch
                self.models["faiss"] = FAISSSearch()

        except Exception as e:
            logger.error("Failed to load model '%s': %s", model_name, e)
            self.models[model_name] = None

    # ── Lazy component loading ───────────────────────────────────────────

    @property
    def explainer(self):
        if self._explainer is None:
            from backend.explainability.explainer import ExplainabilityEngine
            self._explainer = ExplainabilityEngine()
        return self._explainer

    @property
    def credibility_engine(self):
        if self._credibility_engine is None:
            from backend.scoring.credibility_engine import CredibilityEngine
            self._credibility_engine = CredibilityEngine()
        return self._credibility_engine

    @property
    def claim_extractor(self):
        if self._claim_extractor is None:
            from backend.rag.claim_extractor import ClaimExtractor
            self._claim_extractor = ClaimExtractor()
        return self._claim_extractor

    @property
    def evidence_retriever(self):
        if self._evidence_retriever is None:
            from backend.rag.evidence_retriever import EvidenceRetriever
            self.load_model("faiss")
            self._evidence_retriever = EvidenceRetriever(
                faiss_service=self.models.get("faiss"),
            )
        return self._evidence_retriever

    @property
    def contradiction_detector(self):
        if self._contradiction_detector is None:
            from backend.rag.contradiction_detector import ContradictionDetector
            self._contradiction_detector = ContradictionDetector()
        return self._contradiction_detector

    @property
    def provenance_engine(self):
        if self._provenance_engine is None:
            from backend.scoring.provenance_engine import ProvenanceEngine
            self._provenance_engine = ProvenanceEngine()
        return self._provenance_engine

    # ── Main Process ─────────────────────────────────────────────────────

    def process(
        self,
        video_path: Optional[str] = None,
        query: Optional[str] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Run the full analysis pipeline.

        Args:
            video_path: Path to a video file for deepfake analysis.
            query: Text string for AI-text detection + fact-check search.
            status_callback: Optional function called with status messages.

        Returns:
            Complete analysis report dict matching the frontend API contract.
        """
        def _set_status(msg: str) -> None:
            if status_callback:
                status_callback(msg)
            logger.info(msg)

        t_start = time.perf_counter()
        _set_status("Initializing analysis...")

        metadata: Dict[str, Any] = {}
        video_result: Optional[Dict[str, Any]] = None
        audio_result: Optional[Dict[str, Any]] = None
        text_result: Optional[Dict[str, Any]] = None
        image_result: Optional[Dict[str, Any]] = None
        fact_check: List[Dict[str, Any]] = []
        news_verification: Optional[Dict[str, Any]] = None
        drift_data: List[Dict[str, Any]] = []
        ai_models: List[Dict[str, Any]] = []
        manipulation_signals: List[Dict[str, str]] = []

        # ── Video Processing ─────────────────────────────────────────────
        if video_path and os.path.exists(video_path):
            video_result, audio_result, metadata, drift_data, ai_models = (
                self._process_video(video_path, _set_status, ai_models)
            )

        # ── Text Processing ──────────────────────────────────────────────
        if query and query.strip():
            text_result, fact_check, ai_models = self._process_text(
                query, _set_status, ai_models,
            )

        # ── Fake News RAG Verification (NEW) ─────────────────────────────
        if query and query.strip():
            _set_status("Running fake news verification pipeline...")
            news_verification, manipulation_signals = self._run_news_verification(
                query, _set_status,
            )

        # ── Aggregation & Postprocessing ─────────────────────────────────
        _set_status("Computing final risk assessment...")

        # Legacy risk scoring (backwards compatible)
        risk_assessment = compute_risk_score(metadata, video_result, text_result)

        # Drift data (if not already generated from video processing)
        if not drift_data:
            duration = metadata.get("file_info", {}).get("duration_seconds", 0)
            if duration > 0:
                drift_data = generate_drift_data(duration, video_result)

        # Combined label aggregation (legacy)
        base_report = aggregate_results(
            video_result=video_result,
            audio_result=audio_result,
            text_result=text_result,
            articles=fact_check,
            weights={
                "video": self.config.get("aggregation", {}).get("video_weight", 0.45),
                "audio": self.config.get("aggregation", {}).get("audio_weight", 0.30),
                "text": self.config.get("aggregation", {}).get("text_weight", 0.25),
            },
        )

        # ── NEW: Provenance Analysis ─────────────────────────────────────
        _set_status("Analyzing manipulation provenance...")
        provenance_result = self.provenance_engine.analyze_provenance(
            video_result=video_result,
            audio_result=audio_result,
            text_result=text_result,
            image_result=image_result,
        )

        # ── NEW: Unified Credibility Scoring ─────────────────────────────
        _set_status("Computing credibility score...")
        credibility = self.credibility_engine.compute(
            video_result=video_result,
            audio_result=audio_result,
            text_result=text_result,
            image_result=image_result,
            news_verification=news_verification,
            manipulation_signals=manipulation_signals,
            metadata=metadata,
            provenance_result=provenance_result,
        )

        # ── NEW: Unified Explainability ──────────────────────────────────
        _set_status("Generating explainability report...")
        explainability = self.explainer.explain(
            video_result=video_result,
            audio_result=audio_result,
            text_result=text_result,
            image_result=image_result,
            news_verification=news_verification,
            manipulation_signals=manipulation_signals,
        )

        processing_time = round(time.perf_counter() - t_start, 2)

        # ── Construct frontend-compatible report ─────────────────────────
        full_report: Dict[str, Any] = {
            # Basic info
            "summary": "Analysis complete",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "processing_time_seconds": processing_time,

            # NEW: Credibility score (primary scoring)
            "score": credibility["score"],
            "risk_level": credibility["risk_level"],
            "verdict": credibility.get("verdict", "Unknown"),

            # Legacy risk assessment (backwards compatible)
            "risk_assessment": {
                **risk_assessment,
                "authenticity_score": credibility["score"],
                "flags": credibility.get("flags", risk_assessment.get("flags", [])),
            },

            # Data for UI
            "metadata": metadata,
            "drift_data": drift_data,
            "ai_models": ai_models,

            # Detailed ML results
            "video_result": base_report.get("video"),
            "audio_result": base_report.get("audio"),
            "text_result": base_report.get("text"),
            "image_result": image_result,
            "related_articles": base_report.get("related_articles"),
            "combined_fake_probability": base_report.get("combined_fake_probability", 0.5),
            "overall_label": base_report.get("overall_label", "uncertain"),

            # NEW: Fake news verification
            "news_verification": news_verification,

            # NEW: Unified explainability
            "explainability": explainability,

            # NEW: Per-modality credibility breakdown
            "credibility": credibility,
        }

        _set_status(f"Analysis complete ({processing_time}s)")
        logger.info(
            "Pipeline complete: score=%d, risk=%s, verdict=%s, label=%s (%.2fs)",
            full_report["score"], full_report["risk_level"],
            full_report.get("verdict", ""),
            full_report["overall_label"], processing_time,
        )

        # Free GPU memory
        if _has_torch_cuda():
            import torch
            torch.cuda.empty_cache()
        gc.collect()

        return full_report

    # ── Video Sub-pipeline ───────────────────────────────────────────────

    def _process_video(
        self,
        video_path: str,
        status_cb: Callable[[str], None],
        ai_models: List[Dict[str, Any]],
    ) -> tuple:
        """Run video analysis: metadata → frames → deepfake → audio."""
        metadata: Dict[str, Any] = {}
        video_result: Optional[Dict[str, Any]] = None
        audio_result: Optional[Dict[str, Any]] = None
        drift_data: List[Dict[str, Any]] = []

        try:
            # 1. Extract metadata
            status_cb("Extracting metadata fingerprints...")
            t0 = time.perf_counter()
            metadata = extract_video_metadata(video_path, self.ffprobe_path)
            logger.info("Metadata extraction: %.2fs", time.perf_counter() - t0)

            # 2. Deepfake detection (video frames)
            status_cb("Running deepfake detection model...")
            self.load_model("video")
            if self.models.get("video"):
                video_result = self._run_video_detector(video_path, ai_models)

            # 3. Audio detection
            status_cb("Analyzing audio frequency anomalies...")
            self.load_model("audio")
            if self.models.get("audio"):
                audio_result = self._run_audio_detector(video_path)

            # 4. Generate drift data
            duration = metadata.get("file_info", {}).get("duration_seconds", 0)
            if duration > 0:
                drift_data = generate_drift_data(duration, video_result)

        except Exception as exc:
            logger.error("Video analysis error: %s", exc)
            metadata = metadata or {"error": str(exc)}

        return video_result, audio_result, metadata, drift_data, ai_models

    def _run_video_detector(
        self, video_path: str, ai_models: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Extract frames → preprocess → run video detector."""
        try:
            video_cfg = self.config.get("video", {})
            t0 = time.perf_counter()

            # Adaptive frame extraction
            frames = extract_frames_adaptive(
                video_path,
                target_fps=video_cfg.get("frame_sample_rate", 1),
                max_frames=video_cfg.get("max_frames", 32),
                min_frames=video_cfg.get("min_frames", 8),
                scene_change_threshold=video_cfg.get("scene_change_threshold", 30.0),
            )

            if not frames:
                logger.error("No frames extracted from video — skipping vision model")
                return None

            # Face detection & quality filtering
            if video_cfg.get("face_detection", True):
                frames = detect_and_crop_faces(
                    frames,
                    quality_threshold=video_cfg.get("face_quality_threshold", 100.0),
                )
                frames = align_faces(frames)

            # Run detector
            video_result = self.models["video"].predict(frames)
            elapsed = time.perf_counter() - t0

            label = video_result.get("label", "unknown")
            confidence = video_result.get("confidence", 0)
            logger.info("VideoMAE Deepfake Detection: %s @ %.2f%% (%.2fs)", label, confidence * 100, elapsed)

            ai_models.append({
                "name": "VideoMAE (Temporal Transformer)",
                "score": int(video_result.get("fake_probability", 0) * 100),
                "label": label.capitalize(),
                "details": f"Temporal Anomaly: {video_result.get('temporal_anomaly_score', 0):.2f}"
            })

            return video_result

        except Exception as e:
            logger.error("Deepfake detection failed: %s", e)
            return None

    def _run_audio_detector(self, video_path: str) -> Optional[Dict[str, Any]]:
        """Extract audio → run audio detector."""
        try:
            project_root = os.path.dirname(_BACKEND_DIR)
            temp_dir = os.path.join(
                project_root,
                self.config.get("temp_dir", "data/processed"),
            )
            os.makedirs(temp_dir, exist_ok=True)

            audio_path = extract_audio(video_path, temp_dir)
            if not os.path.exists(audio_path):
                logger.warning("Audio extraction produced no file")
                return None

            t0 = time.perf_counter()
            audio_result = self.models["audio"].predict(audio_path)
            logger.info("Audio detection: %.2fs", time.perf_counter() - t0)

            # Cleanup temp audio file
            try:
                os.unlink(audio_path)
            except OSError:
                pass

            return audio_result

        except Exception as e:
            logger.error("Audio detection failed: %s", e)
            return None

    # ── Text Sub-pipeline ────────────────────────────────────────────────

    def _process_text(
        self,
        query: str,
        status_cb: Callable[[str], None],
        ai_models: List[Dict[str, Any]],
    ) -> tuple:
        """Run text detection and fact-check search."""
        text_result: Optional[Dict[str, Any]] = None
        fact_check: List[Dict[str, Any]] = []

        # Text AI Detection
        status_cb("Analyzing text patterns...")
        self.load_model("text")
        if self.models.get("text"):
            try:
                t0 = time.perf_counter()
                text_result = self.models["text"].predict(query)
                elapsed = time.perf_counter() - t0
                logger.info("Text detection: %s (%.2fs)", text_result.get("label"), elapsed)

                ai_prob = text_result.get("ai_probability", 0)
                ai_models.append({
                    "name": "TextAIDetector (DeBERTa-v3 + Ensemble)",
                    "score": int(ai_prob * 100),
                })
            except Exception as e:
                logger.error("Text detection failed: %s", e)

        # Fact-check search (FAISS)
        status_cb("Cross-referencing content database...")
        self.load_model("faiss")
        if self.models.get("faiss"):
            try:
                t0 = time.perf_counter()
                fact_check = self.models["faiss"].search(query)
                elapsed = time.perf_counter() - t0
                if fact_check:
                    best_score = fact_check[0].get("similarity_score", 0)
                    ai_models.append({
                        "name": "FactCheck (Semantic Search)",
                        "score": int(best_score * 100),
                    })
                logger.info("FAISS search: %d results (%.2fs)", len(fact_check), elapsed)
            except Exception as e:
                logger.error("FAISS search failed: %s", e)

        return text_result, fact_check, ai_models

    # ── Fake News RAG Pipeline (NEW) ─────────────────────────────────────

    def _run_news_verification(
        self, query: str, status_cb: Callable[[str], None],
    ) -> tuple[Optional[Dict[str, Any]], List[Dict[str, str]]]:
        """Run the full RAG fake news verification pipeline."""
        try:
            # 1. Extract claims
            status_cb("Extracting factual claims...")
            claim_result = self.claim_extractor.extract(query)
            claims = claim_result.get("claims", [])
            manipulation_signals = claim_result.get("manipulation_signals", [])

            if not claims:
                logger.info("No actionable claims extracted — skipping verification")
                return {
                    "verdict": "Unverified",
                    "credibility_score": 50,
                    "evidence_summary": "No specific factual claims detected in the text.",
                    "claims_analyzed": 0,
                    "contradictions_found": 0,
                    "emotional_score": claim_result.get("emotional_score", 0),
                    "contradictions": [],
                }, manipulation_signals

            # 2. Retrieve evidence
            status_cb("Searching trusted sources...")
            evidence = self.evidence_retriever.retrieve(claims)

            # 3. Contradiction analysis
            status_cb("Analyzing contradictions...")
            contradiction_result = self.contradiction_detector.analyze(claims, evidence)

            # Combine into news verification report
            news_verification = {
                "verdict": contradiction_result.get("verdict", "Unverified"),
                "credibility_score": contradiction_result.get("credibility_score", 50),
                "evidence_summary": contradiction_result.get("evidence_summary", ""),
                "claims_analyzed": len(claims),
                "contradictions_found": contradiction_result.get("contradicting_count", 0),
                "supporting_found": contradiction_result.get("supporting_count", 0),
                "emotional_score": claim_result.get("emotional_score", 0),
                "contradictions": contradiction_result.get("contradictions", []),
                "sources": evidence.get("sources_searched", []),
            }

            logger.info("News verification: verdict=%s, credibility=%d",
                         news_verification["verdict"],
                         news_verification["credibility_score"])

            return news_verification, manipulation_signals

        except Exception as e:
            logger.error("News verification pipeline failed: %s", e)
            return None, []


# ─── Utilities ───────────────────────────────────────────────────────────

def _has_torch_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


# ─── CLI Entry Point ─────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="truth.x — Detection Pipeline")
    p.add_argument("--video", type=str, default=None, help="Video file for deepfake analysis")
    p.add_argument("--query", type=str, default=None, help="Text for AI-text detection + article search")
    p.add_argument("--text-file", type=str, default=None, help="Document (.pdf .docx .txt) for AI-text detection")
    return p.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    # Handle document input → query
    text_file = getattr(args, "text_file", None)
    if text_file:
        from backend.utils.document_reader import read_document
        logger.info("Reading document: %s", text_file)
        file_text = read_document(text_file)
        if not file_text.strip():
            print("ERROR: Document is empty.")
            sys.exit(1)
        args.query = file_text

    if not args.video and not args.query:
        print("ERROR: Provide --video, --query, or --text-file.")
        sys.exit(1)

    print("Initializing Pipeline...", end="", flush=True)
    pipeline = DeepfakeDetectionPipeline()
    print(" done.")

    print("\nStarting analysis...")
    report = pipeline.process(video_path=args.video, query=args.query)

    # ── CLI Output ───────────────────────────────────────────────────────
    sep = "=" * 60
    print(f"\n{sep}")
    print("  truth.x  —  Detection Report")
    print(sep)

    v = report.get("video_result")
    if v and v.get("label") != "unknown":
        print(f"\n  [Video]  {v['label'].upper()}  (confidence: {v.get('confidence', 0):.2%})")
        if v.get("temporal_consistency"):
            tc = v["temporal_consistency"]
            print(f"           Temporal consistency: {tc.get('score', 0):.2%}  "
                  f"(switches: {tc.get('label_switches', 0)})")
        if v.get("trust_score") is not None:
            print(f"           Trust score: {v['trust_score']:.2%}")

    a = report.get("audio_result")
    if a and not a.get("error"):
        print(f"\n  [Audio]  {a.get('label', 'N/A').upper()}  (confidence: {a.get('confidence', 0):.2%})")
        if a.get("num_segments_analyzed"):
            print(f"           Segments analyzed: {a['num_segments_analyzed']}")

    t = report.get("text_result")
    if t:
        print(f"\n  [Text]   {t.get('label', 'N/A').upper()}  (confidence: {t.get('confidence', 0):.2%})")
        enhanced = t.get("enhanced_analysis", {})
        if enhanced:
            print(f"           Burstiness: {enhanced.get('burstiness_score', 0):.2%}  "
                  f"Stylometric: {enhanced.get('stylometric_score', 0):.2%}")

    # NEW: News verification
    nv = report.get("news_verification")
    if nv:
        print(f"\n  [News]   {nv.get('verdict', 'N/A').upper()}  "
              f"(credibility: {nv.get('credibility_score', 0)}/100)")
        if nv.get("claims_analyzed"):
            print(f"           Claims analyzed: {nv['claims_analyzed']}, "
                  f"Contradictions: {nv.get('contradictions_found', 0)}")

    print(f"\n{'-' * 60}")
    print(f"  CREDIBILITY SCORE  : {report['score']} / 100")
    print(f"  VERDICT            : {report.get('verdict', 'Unknown').upper()}")
    print(f"  RISK LEVEL         : {report['risk_level'].upper()}")
    print(f"  OVERALL LABEL      : {report['overall_label'].upper()}")

    # Explainability
    explainability = report.get("explainability", {})
    reasons = explainability.get("overall_reasons", [])
    if reasons:
        print(f"\n  [Reasons]")
        for r in reasons[:5]:
            severity = r.get("severity", "").upper()
            print(f"   ‣ [{severity}] {r.get('indicator', '')}: {r.get('detail', '')}")

    flags = report.get("risk_assessment", {}).get("flags", [])
    if flags:
        print(f"\n  [Flags]")
        for flag in flags[:5]:
            print(f"   ‣ [{flag['severity'].upper()}] {flag['label']}: {flag['detail']}")

    print(f"\n  Processing time: {report['processing_time_seconds']}s")
    print(f"{sep}\n")


if __name__ == "__main__":
    main()
