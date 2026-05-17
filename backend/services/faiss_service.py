"""truth.x — FAISS Semantic Search for related article retrieval."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

from backend.utils.logger import logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
CONFIG_PATH = os.path.join(_BACKEND_DIR, "config", "config.yaml")


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class FAISSSearch:
    """Semantic search over fact-check articles using sentence embeddings."""

    def __init__(self) -> None:
        cfg = _load_config()
        retrieval_cfg = cfg.get("retrieval", {})
        self.articles_path = os.path.join(_PROJECT_ROOT, retrieval_cfg.get("articles_path", "data/articles.json"))
        self.embedder_model = retrieval_cfg.get("embedder_model", "sentence-transformers/all-MiniLM-L6-v2")
        self.top_k = retrieval_cfg.get("top_k", 5)
        self._use_local_corpus = bool(retrieval_cfg.get("use_local_corpus", False))

        self.articles: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.embedder = None

        self._load_articles()
        self._load_embedder()
        self._build_index()

    def _load_articles(self) -> None:
        if not self._use_local_corpus:
            logger.info("Local corpus loading disabled by config (use_local_corpus=false)")
            return
        if not os.path.isfile(self.articles_path):
            logger.warning("Articles file not found: %s", self.articles_path)
            return
        with open(self.articles_path, "r", encoding="utf-8") as f:
            self.articles = json.load(f)
        logger.info("Loaded %d articles from %s", len(self.articles), self.articles_path)

    def _load_embedder(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(self.embedder_model, device="cpu")
            logger.info("Sentence embedder loaded: %s (forcing CPU)", self.embedder_model)
        except ImportError:
            logger.error("sentence-transformers not installed — FAISS search disabled")
        except Exception as e:
            logger.error("Failed to load embedder: %s", e)

    def _build_index(self) -> None:
        if not self.articles or self.embedder is None:
            return
        texts = [
            (a.get("title", "") + " " + a.get("claim", "") + " " + a.get("source", "")).strip()
            for a in self.articles
        ]
        self.embeddings = self.embedder.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # Normalize for cosine similarity
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        self.embeddings = self.embeddings / norms
        logger.info("Built embedding index: %d articles, dim=%d", len(self.articles), self.embeddings.shape[1])

    def search(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for articles related to the query.

        Returns list of articles sorted by similarity score (descending).
        """
        if k is None:
            k = self.top_k

        if self.embedder is None or self.embeddings is None or not self.articles:
            logger.warning("FAISS search unavailable (embedder=%s, articles=%d)",
                           self.embedder is not None, len(self.articles))
            return []

        # Encode query
        query_embedding = self.embedder.encode([query], show_progress_bar=False, convert_to_numpy=True)
        q_norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
        q_norm = np.where(q_norm == 0, 1, q_norm)
        query_embedding = query_embedding / q_norm

        # Cosine similarity
        scores = (self.embeddings @ query_embedding.T).flatten()
        top_indices = np.argsort(scores)[::-1][:k]

        results = []
        for idx in top_indices:
            article = self.articles[idx].copy()
            article["similarity_score"] = round(float(scores[idx]), 4)
            results.append(article)

        logger.info("FAISS search: query='%s...', found %d results (top=%.4f)",
                     query[:50], len(results), results[0]["similarity_score"] if results else 0)
        return results
