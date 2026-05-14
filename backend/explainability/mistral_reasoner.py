"""truth.x — Mistral Reasoner for Explainability.

Uses Mistral LLM to synthesize multimodal signals into a cohesive,
human-readable intelligence report.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from backend.utils.logger import logger
from backend.services.mistral_client import run_mistral_chat


class MistralReasoner:
    """Synthesizes raw detection signals into a human-readable intelligence report."""

    def generate_report(self, signals: Dict[str, Any]) -> str:
        """Generate a cohesive explanation based on cross-modal signals.
        
        Args:
            signals: A dictionary containing reasons from text, video, audio, image, and RAG.
        Returns:
            A well-structured paragraph explaining the authenticity or manipulation of the media.
        """
        # If no significant signals, return generic safe response
        has_signals = any(len(s) > 0 for s in signals.values() if isinstance(s, list))
        if not has_signals:
            return "No suspicious manipulation indicators were detected across analyzed modalities. The content appears consistent with natural media."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Lead Intelligence Analyst for Truth_X, an advanced multimodal deepfake and misinformation detection system. "
                    "Your task is to synthesize raw detection signals (from video, audio, text, image, and news verification) into a single, highly professional, cohesive paragraph. "
                    "Do NOT list bullet points. Do NOT say 'The system detected' or 'I found'. Speak directly about the media. "
                    "Example: 'This content exhibits severe temporal inconsistencies and lip-sync anomalies typical of deepfakes, alongside manipulative, hyperbolic text that contradicts verified news sources from Reuters.' "
                    "Focus on the most severe signals. Keep it under 60 words."
                )
            },
            {
                "role": "user",
                "content": f"RAW SIGNALS TO SYNTHESIZE:\n{json.dumps(signals, indent=2)}"
            }
        ]

        try:
            report = run_mistral_chat(messages, temperature=0.3)
            if report:
                return report.strip()
        except Exception as e:
            logger.warning("Mistral report generation failed: %s", e)

        return ""
