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

# Import operations logger (lazy to avoid circular imports)
_ops_logger = None

def _get_ops_logger():
    """Lazy load operations logger."""
    global _ops_logger
    if _ops_logger is None:
        try:
            from app.services.ai_operations_logger import get_operations_logger
            _ops_logger = get_operations_logger()
        except ImportError:
            pass
    return _ops_logger


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

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of an API call based on model and tokens."""
        # Pricing per million tokens (as of 2024)
        pricing = {
            "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
            "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
        }

        model_pricing = pricing.get(model, {"input": 3.0, "output": 15.0})
        input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
        return input_cost + output_cost

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
        """Track API usage to UsageTracker database (not ops_logger - that's done in chat_async)."""
        # Note: ops_logger logging is now done directly in chat_async/stream methods
        # with detailed cache info. This method only handles UsageTracker database logging.

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
        input_tokens = 0
        output_tokens = 0
        content = ""
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

            response = self.client.messages.create(**kwargs)

            content = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(f"[CLAUDE] Response received - tokens: input={input_tokens}, output={output_tokens}, latency={latency_ms}ms")

            # Log to operations logger
            ops_logger = _get_ops_logger()
            if ops_logger:
                cost = self._calculate_cost(model_id, input_tokens, output_tokens)
                ops_logger.log_api_call(
                    model=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    duration_ms=latency_ms,
                    request_type=request_type,
                    user_id=self.user_id,
                    project_id=self.project_id,
                )

            return content

        except Exception as e:
            error_message = str(e)
            logger.error(f"[CLAUDE] Chat error: {error_message}")

            # Log error to operations logger
            ops_logger = _get_ops_logger()
            if ops_logger:
                from app.services.ai_operations_logger import OperationType
                ops_logger.log(
                    operation_type=OperationType.API_ERROR,
                    message=f"Sync chat error: {error_message}",
                    model=model_id,
                    user_id=self.user_id,
                    project_id=self.project_id,
                    success=False,
                    error=error_message,
                )
            raise

    async def chat_async(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        use_cache: bool = True,
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
            use_cache: Enable prompt caching for system prompt (default: True)

        Returns:
            The assistant's response text
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Async chat request - model={model_id}, messages={len(messages)}, type={request_type}, cache={use_cache}")

        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 0
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

            # Use cache_control for system prompt when caching is enabled
            if system:
                if use_cache:
                    kwargs["system"] = [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                else:
                    kwargs["system"] = system

            response = await self.async_client.messages.create(**kwargs)

            content = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Get cache stats from response
            cache_creation_input_tokens = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0
            cache_read_input_tokens = getattr(response.usage, 'cache_read_input_tokens', 0) or 0

            logger.info(f"[CLAUDE] Response received - tokens: input={input_tokens}, output={output_tokens}, cache_read={cache_read_input_tokens}, cache_write={cache_creation_input_tokens}")

            return content

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[CLAUDE] Async chat error: {error_message}")
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            # Calculate cache savings
            cache_hit = cache_read_input_tokens > 0
            tokens_saved = cache_read_input_tokens if cache_hit else 0

            # Cache pricing is 90% cheaper for cached tokens
            model_pricing = {
                "claude-sonnet-4-5-20250929": {"input": 3.0, "cached": 0.30},
                "claude-haiku-4-5-20251001": {"input": 0.80, "cached": 0.08},
            }.get(model_id, {"input": 3.0, "cached": 0.30})

            # Calculate cost saved
            cost_saved = (tokens_saved / 1_000_000) * (model_pricing["input"] - model_pricing["cached"])

            # Log to operations logger with cache info
            ops_logger = _get_ops_logger()
            if ops_logger:
                cost = self._calculate_cost(model_id, input_tokens, output_tokens)

                if cache_hit:
                    ops_logger.log_cache_hit(
                        tokens_saved=tokens_saved,
                        cost_saved=cost_saved,
                        user_id=self.user_id,
                        project_id=self.project_id,
                    )
                elif cache_creation_input_tokens > 0:
                    ops_logger.log_cache_miss(
                        user_id=self.user_id,
                        project_id=self.project_id,
                    )

                ops_logger.log_api_call(
                    model=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    duration_ms=latency_ms,
                    request_type=request_type,
                    cache_hit=cache_hit,
                    cache_tokens_saved=tokens_saved,
                    cache_cost_saved=cost_saved,
                    user_id=self.user_id,
                    project_id=self.project_id,
                )

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

    async def chat_async_cached(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
    ) -> str:
        """
        Send an async chat request with prompt caching enabled.

        Uses cache_control markers on system prompt for up to 90% cost reduction
        on repeated calls with the same system prompt.

        Args:
            model: Claude model to use (HAIKU or SONNET)
            messages: List of message dicts with 'role' and 'content'
            system: System prompt (will be cached)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            request_type: Type of request for tracking

        Returns:
            The assistant's response text
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Cached async request - model={model_id}, messages={len(messages)}, type={request_type}")

        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 0
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

            # Build system with cache_control marker for caching
            if system:
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]

            response = await self.async_client.messages.create(**kwargs)

            content = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Get cache stats from response
            cache_creation_input_tokens = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0
            cache_read_input_tokens = getattr(response.usage, 'cache_read_input_tokens', 0) or 0

            logger.info(f"[CLAUDE] Cached response - tokens: input={input_tokens}, output={output_tokens}, cache_read={cache_read_input_tokens}, cache_write={cache_creation_input_tokens}")

            return content

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[CLAUDE] Cached async chat error: {error_message}")
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            # Calculate cache savings
            cache_hit = cache_read_input_tokens > 0
            tokens_saved = cache_read_input_tokens if cache_hit else 0

            # Cache pricing is 90% cheaper for cached tokens
            model_pricing = {
                "claude-sonnet-4-5-20250929": {"input": 3.0, "cached": 0.30},
                "claude-haiku-4-5-20251001": {"input": 0.80, "cached": 0.08},
            }.get(model_id, {"input": 3.0, "cached": 0.30})

            # Calculate cost saved (difference between regular and cached price)
            cost_saved = (tokens_saved / 1_000_000) * (model_pricing["input"] - model_pricing["cached"])

            # Log to operations logger with cache info
            ops_logger = _get_ops_logger()
            if ops_logger:
                cost = self._calculate_cost(model_id, input_tokens, output_tokens)

                if cache_hit:
                    ops_logger.log_cache_hit(
                        tokens_saved=tokens_saved,
                        cost_saved=cost_saved,
                        user_id=self.user_id,
                        project_id=self.project_id,
                    )
                elif cache_creation_input_tokens > 0:
                    ops_logger.log_cache_miss(
                        user_id=self.user_id,
                        project_id=self.project_id,
                    )

                ops_logger.log_api_call(
                    model=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    duration_ms=latency_ms,
                    request_type=request_type,
                    cache_hit=cache_hit,
                    cache_tokens_saved=tokens_saved,
                    cache_cost_saved=cost_saved,
                    user_id=self.user_id,
                    project_id=self.project_id,
                )

            # Track usage
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

    async def stream_cached(
        self,
        model: ClaudeModel | str,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response with prompt caching enabled.

        Args:
            model: Claude model to use
            messages: List of message dicts
            system: System prompt (will be cached)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            request_type: Type of request for tracking

        Yields:
            Response text chunks as they arrive
        """
        model_id = model.value if isinstance(model, ClaudeModel) else model
        logger.info(f"[CLAUDE] Cached stream request - model={model_id}, messages={len(messages)}, type={request_type}")

        start_time = time.time()
        full_response = []
        input_tokens = 0
        output_tokens = 0
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 0
        status = "success"
        error_message = None

        try:
            kwargs = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

            # Build system with cache_control marker
            if system:
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]

            async with self.async_client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    full_response.append(text)
                    yield text

                # Get final message with usage stats
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens
                cache_creation_input_tokens = getattr(final_message.usage, 'cache_creation_input_tokens', 0) or 0
                cache_read_input_tokens = getattr(final_message.usage, 'cache_read_input_tokens', 0) or 0

            logger.info(f"[CLAUDE] Cached stream completed - tokens: input={input_tokens}, output={output_tokens}, cache_read={cache_read_input_tokens}")

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[CLAUDE] Cached stream error: {error_message}")
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            response_content = "".join(full_response)

            # Calculate cache savings
            cache_hit = cache_read_input_tokens > 0
            tokens_saved = cache_read_input_tokens if cache_hit else 0

            model_pricing = {
                "claude-sonnet-4-5-20250929": {"input": 3.0, "cached": 0.30},
                "claude-haiku-4-5-20251001": {"input": 0.80, "cached": 0.08},
            }.get(model_id, {"input": 3.0, "cached": 0.30})

            cost_saved = (tokens_saved / 1_000_000) * (model_pricing["input"] - model_pricing["cached"])

            # Log to operations logger with cache info
            ops_logger = _get_ops_logger()
            if ops_logger:
                cost = self._calculate_cost(model_id, input_tokens, output_tokens)

                if cache_hit:
                    ops_logger.log_cache_hit(
                        tokens_saved=tokens_saved,
                        cost_saved=cost_saved,
                        user_id=self.user_id,
                        project_id=self.project_id,
                    )
                elif cache_creation_input_tokens > 0:
                    ops_logger.log_cache_miss(
                        user_id=self.user_id,
                        project_id=self.project_id,
                    )

                ops_logger.log_api_call(
                    model=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    duration_ms=latency_ms,
                    request_type=request_type,
                    cache_hit=cache_hit,
                    cache_tokens_saved=tokens_saved,
                    cache_cost_saved=cost_saved,
                    user_id=self.user_id,
                    project_id=self.project_id,
                )

            # Track usage
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
