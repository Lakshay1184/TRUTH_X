"""truth.x — Content Type Classifier for Adaptive Verification.

Classifies user input to determine verification strategy:
- Scientific/Educational
- News/Current Events
- Opinion/Commentary
- Social Media Claim
- Factual Explanation
- Political Statement
- Other

Informs retrieval and analysis strategy.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend.utils.logger import logger
from backend.services.mistral_client import run_mistral_chat


class ContentClassifier:
    """Classifies content type to inform verification strategy."""

    # Keywords mapping to content types
    _TYPE_INDICATORS = {
        "scientific": [
            "study", "research", "peer-reviewed", "hypothesis", "experiment",
            "methodology", "findings", "academic", "journal", "scientist",
            "species", "biology", "psychology", "neuroscience", "behavior",
            "sleep", "cognition", "dopamine", "cortex", "synapse"
        ],
        "news": [
            "breaking", "reported", "announced", "confirmed", "statement",
            "said", "according to", "spokesman", "spokesperson", "official",
            "incident", "event", "occur", "happened", "date", "time"
        ],
        "opinion": [
            "believe", "think", "opinion", "view", "perspective", "argument",
            "claim", "assert", "suggest", "imply", "controversial", "debate"
        ],
        "political": [
            "politician", "party", "election", "vote", "congress", "senate",
            "bill", "legislation", "campaign", "government", "president"
        ],
        "social_media": [
            "tweet", "tiktok", "instagram", "facebook", "viral", "share",
            "trend", "hashtag", "viral", "meme", "screenshot"
        ],
    }

    def classify(self, text: str) -> Dict[str, Any]:
        """Classify content type using LLM reasoning.

        Args:
            text: The input content to classify

        Returns:
            {
                "type": str,  # scientific, news, opinion, political, social_media, other, factual_explanation
                "confidence": float,  # 0-1
                "reasoning": str,  # why this classification
                "sub_types": list[str],  # additional relevant categories
                "suggested_sources": list[str],  # source type recommendations
            }
        """
        try:
            # Use LLM to classify
            return self._llm_classify(text)
        except Exception as e:
            logger.warning("LLM classification failed, falling back to heuristic: %s", e)
            return self._heuristic_classify(text)

    def _llm_classify(self, text: str) -> Dict[str, Any]:
        """Classify using Chat Mistral."""
        messages = [
            {
                "role": "system",
                "content": """You are a content classification system for an OSINT verification platform.
Classify the user's input into ONE primary type. Return a JSON object with:
- type (string): One of: scientific, news, opinion, political, social_media, factual_explanation, other
- confidence (float): 0-1 confidence in classification
- reasoning (string): Brief explanation of classification
- sub_types (array): Any secondary categories (max 2)
- suggested_sources (array): Recommended source types to retrieve (e.g., ["academic", "news", "scientific_journals"])

Be precise. For scientific claims, suggest academic sources. For news, suggest journalistic sources."""
            },
            {
                "role": "user",
                "content": f"Classify this content:\n\n{text[:2000]}"  # First 2000 chars
            }
        ]

        response = run_mistral_chat(messages, response_format={"type": "json_object"})
        
        if response:
            try:
                result = json.loads(response)
                return {
                    "type": result.get("type", "other"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", ""),
                    "sub_types": result.get("sub_types", []),
                    "suggested_sources": result.get("suggested_sources", []),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return self._heuristic_classify(text)

    def _heuristic_classify(self, text: str) -> Dict[str, Any]:
        """Fallback rule-based classification."""
        text_lower = text.lower()
        text_words = set(text_lower.split())

        # Count keyword matches
        scores = {}
        for content_type, keywords in self._TYPE_INDICATORS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            scores[content_type] = matches

        # Determine primary type
        if not scores or all(v == 0 for v in scores.values()):
            return {
                "type": "factual_explanation",
                "confidence": 0.4,
                "reasoning": "No strong indicators; treating as factual explanation",
                "sub_types": [],
                "suggested_sources": ["general", "educational"],
            }

        primary_type = max(scores, key=scores.get)
        confidence = min(1.0, scores[primary_type] / 5.0)  # Normalize

        # Map to source suggestions
        source_map = {
            "scientific": ["academic_journals", "scientific_databases", "peer_reviewed"],
            "news": ["news_outlets", "journalistic_sources", "wire_services"],
            "opinion": ["analysis", "editorial", "commentary"],
            "political": ["political_databases", "government_records", "policy_sources"],
            "social_media": ["social_platforms", "misinformation_databases"],
            "other": ["general"],
        }

        return {
            "type": primary_type,
            "confidence": confidence,
            "reasoning": f"Content matches {scores[primary_type]} indicators for {primary_type}",
            "sub_types": [t for t, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)[1:3] if s > 0],
            "suggested_sources": source_map.get(primary_type, ["general"]),
        }
