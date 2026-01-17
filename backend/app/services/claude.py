"""
Claude API wrapper for Anthropic's Claude models.
Provides simple chat and streaming interfaces with optional usage tracking.
"""
import logging
import time
from typing import Optional, AsyncGenerator, TYPE_CHECKING
from enum import Enum

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class ClaudeModel(str, Enum):
    """Available Claude models."""
    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-5-20250929"


class ClaudeService:
    """
    Wrapper for Anthropic's Claude API.

    Provides both synchronous and asynchronous chat interfaces,
    with support for streaming responses and optional usage tracking.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        tracker: Optional["UsageTracker"] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize the Claude service.

        Args:
            api_key: Anthropic API key. Uses settings if not provided.
            tracker: Optional UsageTracker for auto-tracking API calls.
            user_id: User ID for tracking (required if tracker is provided).
            project_id: Optional project ID for tracking.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        # Tracking configuration
        self.tracker = tracker
        self.user_id = user_id
        self.project_id = project_id

        if tracker:
            logger.info(f"[CLAUDE] Service initialized with tracking - user={user_id}, project={project_id}")
        else:
            logger.info("[CLAUDE] Service initialized (no tracking)")

    def _should_track(self) -> bool:
        """Check if usage tracking is enabled."""
        return self.tracker is not None and self.user_id is not None

    async def _track_usage(
        self,
        model: str,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        messages: list[dict],
        system: Optional[str],
        response_content: Optional[str],
        latency_ms: int,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """Track API usage if tracking is enabled."""
        if not self._should_track():
            return

        try:
            # Build request payload (truncate for storage)
            request_payload = {
                "model": model,
                "messages": self._truncate_messages(messages),
                "system": system[:2000] if system else None,
            }

            # Build response payload
            response_payload = {
                "content": response_content[:10000] if response_content else None,
            } if response_content else {}

            await self.tracker.track(
                user_id=self.user_id,
                project_id=self.project_id,
                provider="claude",
                model=model,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_payload=request_payload,
                response_payload=response_payload,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(f"[CLAUDE] Failed to track usage: {e}")

    def _truncate_messages(
        self,
        messages: list[dict],
        max_content_length: int = 2000,
    ) -> list[dict]:
        """Truncate message contents for storage."""
        truncated = []
        for msg in messages:
            truncated_msg = {"role": msg.get("role")}
            content = msg.get("content", "")

            if isinstance(content, str):
                truncated_msg["content"] = (
                    content[:max_content_length] + "...[truncated]"
                    if len(content) > max_content_length
                    else content
                )
            elif isinstance(content, list):
                truncated_msg["content"] = f"[{len(content)} parts]"
            else:
                truncated_msg["content"] = str(content)[:max_content_length]

            truncated.append(truncated_msg)
        return truncated

    def chat(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
    ) -> str:
        """
        Send a chat request and get a response (synchronous).

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            request_type: Type of request for tracking (intent, planning, execution, etc.)

        Returns:
            The assistant's response text
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Chat request - model={model_id}, messages={len(messages)}, type={request_type}")

        start_time = time.time()

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
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(f"[CLAUDE] Response received - tokens: input={input_tokens}, output={output_tokens}, latency={latency_ms}ms")

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
        request_type: str = "chat",
    ) -> str:
        """
        Send an async chat request and get a response with automatic tracking.

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            request_type: Type of request for tracking (intent, planning, execution, validation, chat)

        Returns:
            The assistant's response text
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Async chat request - model={model_id}, messages={len(messages)}, type={request_type}")

        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        content = ""
        status = "success"
        error_message = None

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
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            logger.info(f"[CLAUDE] Response received - tokens: input={input_tokens}, output={output_tokens}")

            return content

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[CLAUDE] Async chat error: {error_message}")
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            # Track usage asynchronously
            await self._track_usage(
                model=model_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                messages=messages,
                system=system,
                response_content=content,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            )

    async def stream(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response token by token with automatic tracking.

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            request_type: Type of request for tracking

        Yields:
            Response text chunks as they arrive
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Stream request - model={model_id}, messages={len(messages)}, type={request_type}")

        start_time = time.time()
        full_response = []
        input_tokens = 0
        output_tokens = 0
        status = "success"
        error_message = None

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
                    full_response.append(text)
                    yield text

                # Get final message with usage stats
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

            logger.info(f"[CLAUDE] Stream completed - tokens: input={input_tokens}, output={output_tokens}")

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[CLAUDE] Stream error: {error_message}")
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            response_content = "".join(full_response)

            # Track usage asynchronously
            await self._track_usage(
                model=model_id,
                request_type=request_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                messages=messages,
                system=system,
                response_content=response_content,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            )


# Singleton instance (without tracking - for backward compatibility)
_claude_service: Optional[ClaudeService] = None


def get_claude_service() -> ClaudeService:
    """Get or create the Claude service singleton (without tracking)."""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service


def create_tracked_claude_service(
    tracker: "UsageTracker",
    user_id: str,
    project_id: Optional[str] = None,
) -> ClaudeService:
    """
    Create a new Claude service instance with usage tracking.

    Args:
        tracker: UsageTracker instance
        user_id: User ID for attribution
        project_id: Optional project ID for attribution

    Returns:
        ClaudeService configured with tracking
    """
    return ClaudeService(
        tracker=tracker,
        user_id=user_id,
        project_id=project_id,
    )
