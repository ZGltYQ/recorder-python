"""OpenRouter API integration for AI features."""

import asyncio
import threading
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

import httpx

from ..utils.config import get_config
from ..utils.logger import get_logger
from .local_llm import LocalLLMClient

logger = get_logger(__name__)


@dataclass
class ModelInfo:
    """Represents an OpenRouter model."""

    id: str
    name: str
    provider: str
    context_length: int | None = None
    pricing: dict[str, str] | None = None


@dataclass
class Message:
    """Represents a chat message."""

    role: str  # 'system', 'user', 'assistant'
    content: str


@dataclass
class ChatResponse:
    """Represents a chat completion response."""

    content: str
    model: str
    usage: dict[str, int] | None = None


class OpenRouterClient:
    """Client for OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key
        self.model = model or "anthropic/claude-3.5-sonnet"
        self.temperature = 0.7
        self.max_tokens = 1000

        # Load from config if not provided
        if not self.api_key:
            config = get_config()
            self.api_key = config.get("openrouter.api_key", "")
            self.model = config.get("openrouter.model", self.model)
            self.temperature = config.get("openrouter.temperature", 0.7)
            self.max_tokens = config.get("openrouter.max_tokens", 1000)

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/audio-recorder-stt/recorder-python",
            "X-Title": "Audio Recorder STT Python",
            "Content-Type": "application/json",
        }

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    async def get_available_models(self, force_refresh: bool = False) -> list[ModelInfo]:
        """Fetch available models from OpenRouter API.

        Args:
            force_refresh: If True, bypass cache and fetch fresh list.

        Returns:
            List of ModelInfo objects.
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        # Cache models in class for 5 minutes
        if not force_refresh and hasattr(self, "_cached_models") and self._cached_models:
            cache_age = getattr(self, "_models_cache_time", None)
            if cache_age:
                import time

                if time.time() - cache_age < 300:  # 5 minutes
                    return self._cached_models

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/models",
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()

                data = response.json()
                models = []

                for item in data.get("data", []):
                    model_id = item.get("id", "")
                    name = item.get("name", model_id)

                    # Extract provider from ID (e.g., "anthropic/claude-3.5-sonnet")
                    provider = model_id.split("/")[0] if "/" in model_id else "unknown"

                    # Get context length and pricing if available
                    context_length = item.get("context_length")
                    pricing = item.get("pricing", {})

                    models.append(
                        ModelInfo(
                            id=model_id,
                            name=name,
                            provider=provider,
                            context_length=context_length,
                            pricing=pricing if pricing else None,
                        )
                    )

                # Sort by provider then name
                models.sort(key=lambda x: (x.provider, x.name))

                # Cache the results
                import time

                self._cached_models = models
                self._models_cache_time = time.time()

                return models

            except httpx.HTTPStatusError as e:
                logger.error("OpenRouter API error", status=e.response.status_code, error=str(e))
                raise ValueError(f"Failed to fetch models: {e.response.status_code}")
            except Exception as e:
                logger.error("Failed to fetch models", error=str(e))
                raise ValueError(f"Failed to fetch models: {str(e)}")

    def get_available_models_sync(self, force_refresh: bool = False) -> list[ModelInfo]:
        """Synchronous version of get_available_models."""

        return asyncio.run(self.get_available_models(force_refresh))

    def filter_models(
        self, models: list[ModelInfo], query: str = "", provider: str = ""
    ) -> list[ModelInfo]:
        """Filter models by search query and/or provider.

        Args:
            models: List of ModelInfo to filter.
            query: Search query (matches model ID or name).
            provider: Filter by provider name (e.g., "anthropic", "openai").

        Returns:
            Filtered list of models.
        """
        query_lower = query.lower().strip()
        provider_lower = provider.lower().strip() if provider else ""

        filtered = []
        for model in models:
            # Filter by provider
            if provider_lower and model.provider.lower() != provider_lower:
                continue

            # Filter by query
            if query_lower:
                if query_lower not in model.id.lower() and query_lower not in model.name.lower():
                    continue

            filtered.append(model)

        return filtered

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Send a chat completion request."""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        payload = {
            "model": model or self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()

                data = response.json()

                return ChatResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", model or self.model),
                    usage=data.get("usage"),
                )

            except httpx.HTTPStatusError as e:
                logger.error("OpenRouter API error", status=e.response.status_code, error=str(e))
                raise ValueError(f"API error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                logger.error("OpenRouter request failed", error=str(e))
                raise ValueError(f"Request failed: {str(e)}")

    def chat_sync(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Synchronous version of chat."""

        return asyncio.run(self.chat(messages, model, temperature, max_tokens))


class QuestionDetector:
    """Detects if text is a question."""

    QUESTION_WORDS = [
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "can",
        "could",
        "would",
        "should",
        "is",
        "are",
        "do",
        "does",
        "did",
        "will",
        "shall",
        "may",
        "might",
        "am",
    ]

    def __init__(self):
        pass

    def is_question(self, text: str) -> bool:
        """Check if text is a question."""
        text_lower = text.lower().strip()

        # Check for question mark
        if text.endswith("?"):
            return True

        # Check for question words at start
        words = text_lower.split()
        if words and words[0] in self.QUESTION_WORDS:
            return True

        return False


class NotConfiguredError(Exception):
    """Raised when the LLM provider is not configured."""


class AISuggestionGenerator:
    """Generates AI suggestions for questions."""

    def __init__(self, client: OpenRouterClient | None = None, provider: str = "openrouter"):
        self.provider = provider
        if client:
            self.client = client
        elif provider == "local":
            self.client = LocalLLMClient()
        else:
            self.client = client or OpenRouterClient()
        self.question_detector = QuestionDetector()
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()

    def _run_worker(self) -> None:
        """Persistent worker thread with one event loop for warm httpx connection pools."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._idle_loop())

    async def _idle_loop(self) -> None:
        """Wait for work until stop is requested."""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.5)

    def _stop_worker(self) -> None:
        """Signal the worker thread to stop."""
        self._stop_event.set()
        with self._loop_lock:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._loop.stop)
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def _run_sync(self, coro: Coroutine[Any, None, Any]) -> Any:
        """Run a coroutine on the persistent worker thread and return the result."""
        with self._loop_lock:
            loop = self._loop
        if loop is None or not loop.is_running():
            raise RuntimeError("Worker loop not available")
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=120)

    def set_provider(self, provider: str) -> None:
        """Switch LLM provider.

        Args:
            provider: "openrouter" or "local"
        """
        if provider not in ("openrouter", "local"):
            raise ValueError(f"Invalid provider: {provider}")

        if self.provider != provider:
            self.provider = provider
            if provider == "local":
                self.client = LocalLLMClient()
            else:
                self.client = OpenRouterClient()
            logger.info("Switched LLM provider", provider=provider)

    def is_question(self, text: str) -> bool:
        """Check if text is a question."""
        return self.question_detector.is_question(text)

    async def generate_response(
        self, question: str, context: list[dict[str, str]] | None = None
    ) -> str | None:
        """Generate AI response for a question."""
        if not self.client.is_configured():
            logger.warning("OpenRouter not configured, skipping AI response")
            return None

        # Build messages in OpenAI-compatible format (dicts)
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Provide concise, accurate answers to questions. "
                "Keep responses brief and to the point (2-3 sentences max).",
            }
        ]

        # Add context if provided
        if context:
            for msg in context[-5:]:  # Last 5 messages for context
                messages.append({"role": "user", "content": msg.get("text", "")})

        # Add the question
        messages.append({"role": "user", "content": question})

        try:
            if self.provider == "local":
                response = await self.client.chat(messages)
            else:
                # Convert to Message dataclass for OpenRouterClient
                openrouter_messages = [
                    Message(role=m["role"], content=m["content"]) for m in messages
                ]
                response = await self.client.chat(openrouter_messages)
            return response.content
        except Exception as e:
            logger.error("Failed to generate AI response", error=str(e), provider=self.provider)
            return None

    def generate_response_sync(
        self, question: str, context: list[dict[str, str]] | None = None
    ) -> str | None:
        """Synchronous version of generate_response."""

        return asyncio.run(self.generate_response(question, context))

    async def summarize_conversation(self, messages: list[dict[str, str]]) -> str | None:
        """Generate a summary of the conversation."""
        if not self.client.is_configured():
            return None

        if not messages:
            return "No messages to summarize."

        # Build conversation text
        conversation_text = "\n".join(
            [f"{msg.get('speaker', 'Unknown')}: {msg.get('text', '')}" for msg in messages]
        )

        # Build messages in OpenAI-compatible format (dicts)
        messages_list = [
            {
                "role": "system",
                "content": "Summarize the following conversation concisely. "
                "Highlight key points and decisions made.",
            },
            {"role": "user", "content": conversation_text},
        ]

        try:
            if self.provider == "local":
                response = await self.client.chat(messages_list)
            else:
                # Convert to Message dataclass for OpenRouterClient
                openrouter_messages = [
                    Message(role=m["role"], content=m["content"]) for m in messages_list
                ]
                response = await self.client.chat(openrouter_messages)
            return response.content
        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            return None

    def summarize_conversation_sync(self, messages: list[dict[str, str]]) -> str | None:
        """Synchronous version of summarize_conversation. Uses the persistent worker
        thread to keep the httpx connection pool warm for fast repeated calls."""
        return self._run_sync(self.summarize_conversation(messages))
