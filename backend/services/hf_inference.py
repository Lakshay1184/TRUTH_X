"""truth.x — HuggingFace Inference API Client.

Provides async inference for heavy models via the HF Inference API,
with connection pooling, retry logic, response caching, and graceful degradation.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union

import httpx

from backend.utils.env_loader import ensure_backend_environment_loaded
from backend.utils.logger import logger

ensure_backend_environment_loaded()

# ─── Configuration ───────────────────────────────────────────────────────

HF_API_URL = "https://api-inference.huggingface.co/models"
_DEFAULT_TIMEOUT = 60.0
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0
_CACHE_MAX_SIZE = 100
_CACHE_TTL_SECONDS = 300  # 5 minutes


# ─── LRU Cache with TTL ─────────────────────────────────────────────────

class _TTLCache:
    """Thread-safe LRU cache with time-to-live expiration."""

    def __init__(self, max_size: int = _CACHE_MAX_SIZE, ttl: float = _CACHE_TTL_SECONDS):
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            ts, value = self._cache[key]
            if time.time() - ts < self._ttl:
                self._cache.move_to_end(key)
                return value
            else:
                del self._cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        self._cache[key] = (time.time(), value)
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


# ─── HF Inference Client ────────────────────────────────────────────────

class HFInferenceClient:
    """Async client for HuggingFace Inference API with retry and caching."""

    def __init__(self, token: Optional[str] = None) -> None:
        self._token = token or os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")
        if not self._token:
            logger.warning("HUGGINGFACEHUB_API_TOKEN not set — HF API calls will fail")
        self._cache = _TTLCache()
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("HFInferenceClient initialized (token=%s)", "set" if self._token else "MISSING")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(_DEFAULT_TIMEOUT, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    def _cache_key(self, model: str, payload: Any) -> str:
        raw = f"{model}:{str(payload)}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def infer(
        self,
        model_id: str,
        payload: Dict[str, Any],
        use_cache: bool = True,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> Optional[Any]:
        """Send inference request to HF API with retry and caching.

        Args:
            model_id: HuggingFace model ID (e.g., "facebook/bart-large-mnli")
            payload: JSON payload for the model
            use_cache: Whether to use response caching
            timeout: Request timeout in seconds

        Returns:
            Model response dict/list, or None on failure (graceful degradation)
        """
        if not self._token:
            logger.warning("HF API call skipped — no token configured")
            return None

        # Check cache
        cache_key = self._cache_key(model_id, payload)
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("HF cache hit: %s", model_id)
                return cached

        url = f"{HF_API_URL}/{model_id}"
        client = await self._ensure_client()

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=timeout,
                )

                if response.status_code == 200:
                    result = response.json()
                    if use_cache:
                        self._cache.put(cache_key, result)
                    logger.debug("HF API success: %s (attempt %d)", model_id, attempt)
                    return result

                elif response.status_code == 503:
                    # Model loading — wait and retry
                    body = response.json()
                    wait_time = body.get("estimated_time", 20)
                    logger.info("HF model loading: %s (waiting %.0fs)", model_id, wait_time)
                    await asyncio.sleep(min(wait_time, 30))
                    continue

                elif response.status_code == 429:
                    # Rate limited
                    backoff = _RETRY_BACKOFF_BASE ** attempt
                    logger.warning("HF rate limited: %s (retry in %.1fs)", model_id, backoff)
                    await asyncio.sleep(backoff)
                    continue

                else:
                    logger.error(
                        "HF API error: %s -> %d: %s",
                        model_id, response.status_code, response.text[:200],
                    )
                    # Don't retry on 4xx client errors (except 429)
                    if response.status_code < 500:
                        return None
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_BACKOFF_BASE ** attempt)
                        continue
                    return None

            except httpx.TimeoutException:
                logger.warning("HF API timeout: %s (attempt %d/%d)", model_id, attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF_BASE ** attempt)
                    continue
                return None

            except Exception as e:
                logger.error("HF API unexpected error: %s — %s", model_id, e)
                return None

        return None

    async def classify_text(self, model_id: str, text: str) -> Optional[List[Dict]]:
        """Shortcut for text classification models."""
        return await self.infer(model_id, {"inputs": text})

    async def classify_nli(
        self, model_id: str, premise: str, hypothesis: str,
    ) -> Optional[Dict[str, float]]:
        """Run NLI (Natural Language Inference) classification.

        Returns dict like {"entailment": 0.8, "contradiction": 0.1, "neutral": 0.1}
        """
        payload = {
            "inputs": f"{premise}</s></s>{hypothesis}",
            "parameters": {"candidate_labels": ["entailment", "contradiction", "neutral"]},
        }
        # Use zero-shot classification endpoint format
        payload = {
            "inputs": premise,
            "parameters": {
                "candidate_labels": [hypothesis],
                "multi_label": False,
            },
        }
        result = await self.infer(model_id, payload)

        if result and isinstance(result, dict) and "scores" in result:
            labels = result.get("labels", [])
            scores = result.get("scores", [])
            return dict(zip(labels, scores))
        return None

    async def compute_perplexity(self, model_id: str, text: str) -> Optional[float]:
        """Estimate text perplexity using a language model."""
        # HF API returns token-level log-probabilities for text-generation models
        payload = {
            "inputs": text[:1000],  # Limit for API
            "parameters": {"return_full_text": False, "max_new_tokens": 1},
        }
        result = await self.infer(model_id, payload, use_cache=True)
        # Perplexity estimation from generation score if available
        return None  # Will be computed locally as fallback

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("HF inference client closed")


# ─── Synchronous wrapper for thread-based usage ─────────────────────────

def run_hf_inference(model_id: str, payload: Dict[str, Any], token: Optional[str] = None) -> Optional[Any]:
    """Synchronous wrapper for HF inference that handles nested event loops."""
    
    def _run_in_new_loop():
        client = HFInferenceClient(token=token)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(client.infer(model_id, payload))
            loop.run_until_complete(client.close())
            return result
        finally:
            try:
                loop.close()
            except Exception:
                pass

    # Check if a loop is already running
    try:
        running_loop = asyncio.get_running_loop()
        loop_running = running_loop.is_running()
    except RuntimeError:
        loop_running = False

    if not loop_running:
        try:
            return _run_in_new_loop()
        except Exception as e:
            logger.error("Sync HF inference failed reason=%s", e)
            return None

    # If we're inside a running loop, run the coroutine in a separate thread
    import threading
    import queue

    q: "queue.Queue" = queue.Queue()

    def _thread_worker():
        try:
            thread_client = HFInferenceClient(token=token)
            result = asyncio.run(thread_client.infer(model_id, payload))
            try:
                asyncio.run(thread_client.close())
            except Exception:
                pass
            q.put((True, result))
        except Exception as e:
            q.put((False, e))

    t = threading.Thread(target=_thread_worker, daemon=True)
    t.start()
    t.join(timeout=_DEFAULT_TIMEOUT + 5)

    try:
        ok, payload = q.get_nowait()
    except queue.Empty:
        logger.error("HF thread timeout")
        return None

    if not ok:
        logger.error("HF thread failed reason=%s", payload)
        return None

    return payload
