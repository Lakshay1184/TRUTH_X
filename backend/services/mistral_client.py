"""truth.x — Mistral AI Inference Client.

Provides an LLM reasoning layer for explainability, claim extraction, 
and contradiction analysis.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.utils.env_loader import ensure_backend_environment_loaded
from backend.utils.logger import logger

ensure_backend_environment_loaded()

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
_DEFAULT_TIMEOUT = float(os.environ.get("MISTRAL_TIMEOUT_SECONDS", "20"))
_MAX_RETRIES = int(os.environ.get("MISTRAL_MAX_RETRIES", "2"))


class MistralClient:
    """Async client for Mistral API with retry logic and JSON schema adherence."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self._api_key:
            logger.warning("MISTRAL_API_KEY not set — LLM reasoning will degrade to heuristics")
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(_DEFAULT_TIMEOUT))
        return self._client

    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "mistral-small-latest",
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Execute a chat completion request to Mistral.
        """
        if not self._api_key:
            logger.warning("Mistral request skipped: API key not configured")
            return None

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if response_format:
            payload["response_format"] = response_format

        client = await self._ensure_client()
        prompt_chars = sum(len(message.get("content", "")) for message in messages)
        estimated_tokens = max(1, prompt_chars // 4)
        logger.info(
            "Mistral request sent model=%s temperature=%.2f messages=%d prompt_chars=%d est_tokens=%d",
            model,
            temperature,
            len(messages),
            prompt_chars,
            estimated_tokens,
        )

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                request_started = time.perf_counter()
                response = await client.post(
                    MISTRAL_API_URL, 
                    headers=self._get_headers(),
                    json=payload
                )
                latency_ms = round((time.perf_counter() - request_started) * 1000, 2)
                if response.status_code == 200:
                    data = response.json()
                    content = (data["choices"][0]["message"].get("content") or "").strip()
                    logger.info(f"Mistral RAW response: {content[:200]}...")
                    if not content:
                        logger.warning(
                            "Mistral returned empty content latency_ms=%.2f attempt=%d",
                            latency_ms,
                            attempt,
                        )
                        return None
                    logger.info(
                        "Mistral response received latency_ms=%.2f content_chars=%d attempt=%d",
                        latency_ms,
                        len(content or ""),
                        attempt,
                    )
                    return content
                
                elif response.status_code == 429:
                    logger.warning(
                        "Mistral rate limit hit latency_ms=%.2f attempt=%d/%d",
                        latency_ms,
                        attempt,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error(
                        "Mistral API error status=%d latency_ms=%.2f body=%s",
                        response.status_code,
                        latency_ms,
                        response.text,
                    )
                    return None

            except httpx.TimeoutException:
                logger.warning("Mistral timeout attempt=%d/%d", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                logger.error("Mistral unexpected error attempt=%d/%d reason=%s", attempt, _MAX_RETRIES, e)
                return None

        return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Synchronous wrapper for use in threads/existing pipeline
def run_mistral_chat(messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
    """Synchronous wrapper for the async Mistral client.

    This handles two execution environments:
    - No running event loop: create a fresh asyncio loop and run the coroutine.
    - Running event loop (e.g., inside an async server): run the coroutine in a
      separate thread using `asyncio.run` to avoid "event loop already running".
    """
    audit = kwargs.pop("audit", None)
    stage = kwargs.pop("stage", "mistral")

    if audit is not None:
        audit.log_event(stage, "Mistral request dispatched", message_count=len(messages))

    # Helper to run in current-thread (no running loop)
    def _run_in_new_loop():
        client = MistralClient()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            started = time.perf_counter()
            result = loop.run_until_complete(client.chat(messages, **kwargs))
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            if audit is not None:
                audit.log_event(stage, "Mistral response received", latency_ms=elapsed_ms, has_content=bool(result))
            loop.run_until_complete(client.close())
            return result
        finally:
            try:
                loop.close()
            except Exception:
                pass

    # If there's no running loop, run normally in this thread
    try:
        running_loop = asyncio.get_running_loop()
        loop_running = running_loop.is_running()
    except RuntimeError:
        loop_running = False

    if not loop_running:
        try:
            return _run_in_new_loop()
        except Exception as e:
            logger.error("Sync Mistral chat failed stage=%s reason=%s", stage, e)
            if audit is not None:
                audit.record_failure(stage, f"Mistral failed: {e}")
            return None

    # If we're inside a running loop, run the coroutine in a separate thread
    import threading
    import queue

    q: "queue.Queue" = queue.Queue()

    def _thread_worker():
        try:
            thread_client = MistralClient()
            # Use asyncio.run inside the new thread
            started = time.perf_counter()
            result = asyncio.run(thread_client.chat(messages, **kwargs))
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            try:
                asyncio.run(thread_client.close())
            except Exception:
                pass
            if audit is not None:
                audit.log_event(stage, "Mistral response received (thread)", latency_ms=elapsed_ms, has_content=bool(result))
            q.put((True, result))
        except Exception as e:
            q.put((False, e))

    t = threading.Thread(target=_thread_worker, daemon=True)
    t.start()
    # Wait for the thread to finish, but bound by timeout to avoid hanging
    t.join(timeout=_DEFAULT_TIMEOUT + 5)

    try:
        ok, payload = q.get_nowait()
    except queue.Empty:
        logger.error("Mistral thread timeout stage=%s", stage)
        if audit is not None:
            audit.record_failure(stage, "Mistral thread timeout")
        return None

    if not ok:
        logger.error("Mistral thread failed stage=%s reason=%s", stage, payload)
        if audit is not None:
            audit.record_failure(stage, f"Mistral failed: {payload}")
        return None

    return payload
