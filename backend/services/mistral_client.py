"""truth.x — Mistral AI Inference Client.

Provides an LLM reasoning layer for explainability, claim extraction, 
and contradiction analysis.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.utils.logger import logger

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3


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
            return None

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if response_format:
            payload["response_format"] = response_format

        client = await self._ensure_client()

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.post(
                    MISTRAL_API_URL, 
                    headers=self._get_headers(),
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    return content
                
                elif response.status_code == 429:
                    logger.warning("Mistral rate limit hit. Retrying...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("Mistral API error: %d - %s", response.status_code, response.text)
                    return None

            except httpx.TimeoutException:
                logger.warning("Mistral timeout (attempt %d/%d)", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                logger.error("Mistral unexpected error: %s", e)
                return None

        return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Synchronous wrapper for use in threads/existing pipeline
def run_mistral_chat(messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
    client = MistralClient()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(client.chat(messages, **kwargs))
        loop.run_until_complete(client.close())
        return result
    except Exception as e:
        logger.error("Sync Mistral chat failed: %s", e)
        return None
    finally:
        loop.close()
