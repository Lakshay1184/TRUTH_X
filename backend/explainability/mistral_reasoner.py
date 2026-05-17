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
        has_signals = any(len(s) > 0 for s in signals.values() if isinstance(s, list))
        if not has_signals:
            return ""

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

    def generate_key_findings(self, signals: Dict[str, Any], max_items: int = 6) -> List[str]:
        """Generate concise, evidence-grounded key findings.

        Returns a list of short, single-sentence findings grounded in signals.
        """
        has_signals = any(
            bool(value)
            for value in signals.values()
            if isinstance(value, (list, dict, str))
        )
        if not has_signals:
            return []

        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Lead Intelligence Analyst for Truth_X. "
                    "Generate concise investigative findings grounded ONLY in the provided signals. "
                    "Return JSON with key 'findings' as an array of strings. "
                    "Each finding must be a single short sentence, max 16 words, no generic filler. "
                    "If the signals are insufficient, return an empty array."
                ),
            },
            {
                "role": "user",
                "content": f"SIGNALS:\n{json.dumps(signals, indent=2)}",
            },
        ]

        try:
            response = run_mistral_chat(messages, temperature=0.2, response_format={"type": "json_object"})
            if response:
                data = json.loads(response)
                findings = data.get("findings", [])
                if isinstance(findings, list):
                    cleaned = [
                        str(item).strip()
                        for item in findings
                        if isinstance(item, str) and item.strip()
                    ]
                    return cleaned[:max_items]
        except Exception as e:
            logger.warning("Mistral key findings generation failed: %s", e)

        return []
