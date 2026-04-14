"""Local LLM API integration with OpenAI-compatible format."""

import httpx
from typing import List, Optional
from dataclasses import dataclass

from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger(__name__)


@dataclass
class LocalChatResponse:
    """Represents a chat completion response from local LLM."""

    content: str
    model: str
    usage: Optional[dict] = None


class LocalLLMClient:
    """Client for local LLM API with OpenAI-compatible format."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        # Load from config if not provided
        config = get_config()
        llm_config = config.get("local_llm", {})

        self.base_url = base_url or llm_config.get("base_url", "http://localhost:8000/v1")
        self.model_name = model_name or llm_config.get("model_name", "local-model")
        self.api_key = api_key or llm_config.get("api_key", "")
        self.timeout = timeout or llm_config.get("timeout", 300)

        # Ensure minimum timeout of 300s for cold-start models
        if self.timeout < 300:
            logger.warning(
                "Local LLM timeout {0}s below minimum 300s, setting to 300s".format(self.timeout)
            )
            self.timeout = 300

    def is_configured(self) -> bool:
        """Check if local LLM is configured and enabled."""
        config = get_config()
        llm_config = config.get("local_llm", {})
        return llm_config.get("enabled", False) and bool(llm_config.get("base_url"))

    def _build_headers(self) -> dict:
        """Build request headers."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LocalChatResponse:
        """Send a chat completion request to local LLM.

        Uses OpenAI-compatible /v1/chat/completions format.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (optional, uses default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LocalChatResponse with content, model, and usage
        """
        if not self.is_configured():
            raise ValueError("Local LLM not configured or disabled")

        payload = {
            "model": model or self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()

                return LocalChatResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", model or self.model_name),
                    usage=data.get("usage"),
                )

            except httpx.HTTPStatusError as e:
                logger.error("Local LLM API error", status=e.response.status_code, error=str(e))
                raise ValueError(f"Local LLM API error: {e.response.status_code}")
            except Exception as e:
                logger.error("Local LLM request failed", error=str(e))
                raise ValueError(f"Local LLM request failed: {str(e)}")

    def chat_sync(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LocalChatResponse:
        """Synchronous version of chat."""
        import asyncio

        return asyncio.run(self.chat(messages, model, temperature, max_tokens))
