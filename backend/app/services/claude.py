"""
Claude API wrapper for Anthropic's Claude models.
Provides simple chat and streaming interfaces.
"""
import logging
from typing import Optional, AsyncGenerator
from enum import Enum

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class ClaudeModel(str, Enum):
    """Available Claude models."""
    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-5-20250929"


class ClaudeService:
    """
    Wrapper for Anthropic's Claude API.

    Provides both synchronous and asynchronous chat interfaces,
    with support for streaming responses.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Claude service.

        Args:
            api_key: Anthropic API key. Uses settings if not provided.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        logger.info("[CLAUDE] Service initialized")

    def chat(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat request and get a response.

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            The assistant's response text
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Chat request - model={model_id}, messages={len(messages)}")

        try:
            kwargs = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = self.client.messages.create(**kwargs)

            content = response.content[0].text
            logger.info(f"[CLAUDE] Response received - tokens: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
            return content

        except Exception as e:
            logger.error(f"[CLAUDE] Chat error: {str(e)}")
            raise

    async def chat_async(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Send an async chat request and get a response.

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Returns:
            The assistant's response text
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Async chat request - model={model_id}, messages={len(messages)}")

        try:
            kwargs = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            response = await self.async_client.messages.create(**kwargs)

            content = response.content[0].text
            logger.info(f"[CLAUDE] Response received - tokens: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
            return content

        except Exception as e:
            logger.error(f"[CLAUDE] Async chat error: {str(e)}")
            raise

    async def stream(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response token by token.

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Yields:
            Response text chunks as they arrive
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Stream request - model={model_id}, messages={len(messages)}")

        try:
            kwargs = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system

            async with self.async_client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

            logger.info("[CLAUDE] Stream completed")

        except Exception as e:
            logger.error(f"[CLAUDE] Stream error: {str(e)}")
            raise


# Singleton instance
_claude_service: Optional[ClaudeService] = None


def get_claude_service() -> ClaudeService:
    """Get or create the Claude service singleton."""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service
