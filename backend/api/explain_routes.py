"""
Explainability routes for Truth_X.
"""

from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/explainability", tags=["explainability"])

class KeyFindingsRequest(BaseModel):
    analysis: Dict[str, Any]

@router.post("/key-findings")
async def explainability_key_findings(request: KeyFindingsRequest) -> Dict[str, Any]:
    analysis = request.analysis or {}
    explainability = analysis.get("explainability", {}) if isinstance(analysis, dict) else {}
    news_verification = analysis.get("news_verification", {}) if isinstance(analysis, dict) else {}

    existing = explainability.get("key_findings") if isinstance(explainability, dict) else None
    if isinstance(existing, list) and existing:
        return {"findings": existing[:6], "source": "report"}

    contradictions = news_verification.get("contradictions", []) if isinstance(news_verification, dict) else []
    trimmed_contradictions = [
        {
            "claim": c.get("claim", ""),
            "relation": c.get("relation", ""),
            "confidence": c.get("confidence", 0.0),
            "source": c.get("source", ""),
        }
        for c in contradictions[:6]
        if isinstance(c, dict)
    ]

    signals = {
        "video_result": analysis.get("video_result"),
        "audio_result": analysis.get("audio_result"),
        "text_result": analysis.get("text_result"),
        "image_result": analysis.get("image_result"),
        "news_verification": {
            "verdict": news_verification.get("verdict"),
            "credibility_score": news_verification.get("credibility_score"),
            "evidence_summary": news_verification.get("evidence_summary"),
        },
        "contradictions": trimmed_contradictions,
        "overall_reasons": explainability.get("overall_reasons", []),
        "provenance": analysis.get("credibility", {}).get("provenance", {}),
    }

    from backend.explainability.mistral_reasoner import MistralReasoner
    reasoner = MistralReasoner()
    findings = reasoner.generate_key_findings(signals)

    if findings:
        return {"findings": findings, "source": "mistral"}

    fallback = []
    reasons = explainability.get("overall_reasons", []) if isinstance(explainability, dict) else []
    for reason in reasons:
        if not isinstance(reason, dict): continue
        detail = reason.get("detail") or reason.get("indicator")
        if isinstance(detail, str) and detail.strip():
            fallback.append(detail.strip())
        if len(fallback) >= 6: break

    return {"findings": fallback, "source": "fallback"}
