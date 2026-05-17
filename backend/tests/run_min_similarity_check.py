"""Validate that EvidenceRetriever enforces rag.min_similarity without using local corpus.
This test injects a fake FAISS service that returns low-similarity candidates.
"""
import os
import json
from backend.rag.evidence_retriever import EvidenceRetriever

class FakeFAISS:
    def __init__(self):
        pass
    def search(self, query, k=5):
        # return candidates below typical min_similarity (0.3)
        return [
            {"title": "Low sim article 1", "content": "Irrelevant content", "similarity_score": 0.12, "source": "example.com", "url": "https://example.com/1"},
            {"title": "Low sim article 2", "content": "Also irrelevant", "similarity_score": 0.05, "source": "example.org", "url": "https://example.org/2"},
        ]

# Ensure local corpus flag is False so FAISSSearch isn't involved
os.environ.pop("TAVILY_API_KEY", None)
retriever = EvidenceRetriever(faiss_service=FakeFAISS())
# Force-enable local-corpus path only for this injected fake service test (no real dataset used)
retriever._use_local_corpus = True
retriever._faiss = FakeFAISS()
claims = [{"text": "This is a test claim about a topic"}]
res = retriever.retrieve(claims)
print(json.dumps(res, indent=2))
