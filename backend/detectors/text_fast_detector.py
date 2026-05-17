"""Fast local text detector for low-latency text-only analysis."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List

from backend.utils.logger import logger


from backend.detectors.base import BaseDetector

class FastTextAIDetector(BaseDetector):
    """Deterministic stylometric text detector with no network or model download."""

    modality = "text"

    def predict(self, text: str) -> Dict[str, Any]:
        if not text or not text.strip():
            return self._format_result(
                label="unknown", confidence=0.0, fake_probability=0.0,
                extra={"ai_probability": 0.0, "human_probability": 0.0},
            )

        reasons: List[Dict[str, str]] = []
        burstiness = self._burstiness(text, reasons)
        stylometric = self._stylometrics(text, reasons)
        entropy_score = self._entropy_score(text)
        primary = self._primary_score(text, reasons)

        ai_probability = max(0.0, min(1.0, (primary * 0.45) + (burstiness * 0.25) + (stylometric * 0.20) + (entropy_score * 0.10)))
        human_probability = 1.0 - ai_probability
        
        label = "ai-generated" if ai_probability >= 0.5 else "human-written"
        confidence = ai_probability if label == "ai-generated" else human_probability

        logger.info("Fast text detection: label=%s confidence=%.3f ai_probability=%.3f", label, confidence, ai_probability)
        
        return self._format_result(
            label=label,
            confidence=confidence,
            fake_probability=ai_probability,
            reasons=reasons,
            extra={
                "ai_probability": round(ai_probability, 4),
                "human_probability": round(human_probability, 4),
                "enhanced_analysis": {
                    "detector_backend": "local",
                    "local_stylometric_score": round(primary, 4),
                    "burstiness_score": round(burstiness, 4),
                    "stylometric_score": round(stylometric, 4),
                    "entropy_score": round(entropy_score, 4),
                },
            }
        )

    def _primary_score(self, text: str, reasons: List[Dict[str, str]]) -> float:
        words = re.findall(r"\b\w+\b", text.lower())
        sentences = [s.strip() for s in re.split(r"[.!?]+\s+", text) if len(s.strip()) > 3]
        if len(words) < 8:
            return 0.35

        unique_ratio = len(set(words)) / max(len(words), 1)
        avg_sentence_len = len(words) / max(len(sentences), 1)
        transition_terms = {"however", "moreover", "furthermore", "additionally", "therefore", "consequently", "overall", "notably"}
        transition_ratio = sum(1 for word in words if word in transition_terms) / len(words)
        punctuation_density = len(re.findall(r"[,;:]", text)) / max(len(sentences), 1)

        score = 0.25
        if 0.35 <= unique_ratio <= 0.62:
            score += 0.20
        if 12 <= avg_sentence_len <= 28:
            score += 0.20
        if transition_ratio > 0.015:
            score += 0.15
        if punctuation_density <= 1.8:
            score += 0.10

        if score >= 0.65:
            reasons.append(self._reason(
                "local_stylometric_signal",
                "medium",
                "Local stylometric analysis found uniform structure associated with generated text.",
                f"Vocabulary ratio: {unique_ratio:.3f}, average sentence length: {avg_sentence_len:.1f}",
            ))
        return max(0.05, min(0.95, score))

    def _burstiness(self, text: str, reasons: List[Dict[str, str]]) -> float:
        sentences = [s.strip() for s in re.split(r"[.!?]+\s+", text) if len(s.strip()) > 5]
        if len(sentences) < 3:
            return 0.3
        lengths = [len(sentence.split()) for sentence in sentences]
        mean = sum(lengths) / len(lengths)
        variance = sum((length - mean) ** 2 for length in lengths) / len(lengths)
        cv = math.sqrt(variance) / max(mean, 1)
        uniformity = 1.0 - min(1.0, cv)
        if uniformity > 0.75:
            reasons.append(self._reason("low_burstiness", "medium", "Sentence lengths are unusually uniform.", f"Coefficient of variation: {cv:.3f}"))
        return uniformity

    def _stylometrics(self, text: str, reasons: List[Dict[str, str]]) -> float:
        words = re.findall(r"\b\w+\b", text.lower())
        if len(words) < 20:
            return 0.3
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
        repeat_ratio = 0.0
        if bigrams:
            repeat_ratio = Counter(bigrams).most_common(1)[0][1] / len(bigrams)
        function_words = {"the", "a", "an", "is", "are", "was", "were", "be", "of", "in", "to", "for", "with", "and", "but", "or", "that", "this"}
        function_ratio = sum(1 for word in words if word in function_words) / len(words)
        score = 0.0
        if 0.30 < function_ratio < 0.50:
            score += 0.35
        if repeat_ratio > 0.03:
            score += 0.30
            reasons.append(self._reason("repetitive_patterns", "low", "Repeated phrase patterns were detected.", f"Repeat ratio: {repeat_ratio:.3f}"))
        return min(1.0, score)

    @staticmethod
    def _entropy_score(text: str) -> float:
        freq = Counter(text.lower())
        total = len(text)
        entropy = -sum((count / total) * math.log2(count / total) for count in freq.values())
        if entropy < 3.8:
            return 0.65
        if entropy < 4.1:
            return 0.45
        return 0.3

    @staticmethod
    def _reason(indicator: str, severity: str, detail: str, evidence: str = "") -> Dict[str, str]:
        return {
            "indicator": indicator,
            "severity": severity,
            "detail": detail,
            "evidence": evidence,
        }
