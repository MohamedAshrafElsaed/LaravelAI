"""
Tracked Claude Client.

Wraps the Claude API with automatic usage tracking for cost monitoring.
"""
import logging
import time
from typing import Optional, List, Dict, Any, AsyncGenerator

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings
from app.services.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class TrackedClaudeClient:
    """
    Claude API client with automatic usage tracking.

    Wraps Anthropic's Claude API and automatically tracks:
    - Token usage (input/output)
    - Costs based on pricing
    - Latency
    - Request/response payloads
    - Error states
    """

    def __init__(
        self,
        tracker: UsageTracker,
        user_id: str,
        project_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the tracked Claude client.

        Args:
            tracker: UsageTracker instance for recording usage
            user_id: User ID for attribution
            project_id: Optional project ID for attribution
            api_key: Anthropic API key (uses settings if not provided)
        """
        self.tracker = tracker
        self.user_id = user_id
        self.project_id = project_id

        api_key = api_key or settings.anthropic_api_key
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=api_key)
        self.async_client = AsyncAnthropic(api_key=api_key)

        logger.info(f"[TRACKED_CLAUDE] Client initialized for user={user_id}")

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        request_type: str = "chat",
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        store_payload: bool = True,
    ) -> Any:
        """
        Send an async chat request with automatic usage tracking.

        Args:
            model: Claude model identifier
            messages: List of message dicts with 'role' and 'content'
            request_type: Type of request for categorization
            system: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            tools: Optional tool definitions
            store_payload: Whether to store request/response in usage record

        Returns:
            Claude API response object
        """
        logger.info(f"[TRACKED_CLAUDE] Chat request - model={model}, type={request_type}")

        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        status = "success"
        error_message = None
        response = None
        response_content = None

        try:
            # Build request params
            kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system
            if tools:
                kwargs["tools"] = tools

            # Make the API call
            response = await self.async_client.messages.create(**kwargs)

            # Extract usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Extract response content
            if response.content:
                if response.content[0].type == "text":
                    response_content = response.content[0].text
                else:
                    response_content = str(response.content)

            logger.info(
                f"[TRACKED_CLAUDE] Response received - tokens: "
                f"input={input_tokens}, output={output_tokens}"
            )

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[TRACKED_CLAUDE] Chat error: {error_message}")

        finally:
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Build payloads for storage
            request_payload = None
            response_payload = None

            if store_payload:
                request_payload = {
                    "model": model,
                    "messages": self._truncate_messages(messages),
                    "system": system[:500] if system else None,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if response_content:
                    response_payload = {
                        "content": response_content[:2000] if response_content else None,
                        "stop_reason": getattr(response, "stop_reason", None) if response else None,
                    }

            # Track usage
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

        if status == "error":
            raise Exception(error_message)

        return response

    def chat_sync(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        request_type: str = "chat",
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """
        Send a synchronous chat request.

        Note: Usage tracking is done synchronously, which may block.
        Prefer async version when possible.

        Args:
            model: Claude model identifier
            messages: List of message dicts
            request_type: Type of request
            system: Optional system prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            tools: Optional tool definitions

        Returns:
            Claude API response object
        """
        logger.info(f"[TRACKED_CLAUDE] Sync chat request - model={model}")

        start_time = time.time()

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                kwargs["system"] = system
            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"[TRACKED_CLAUDE] Sync response - tokens: "
                f"input={response.usage.input_tokens}, output={response.usage.output_tokens}"
            )

            # Note: Can't await in sync method, usage tracking should be done separately
            # This is a limitation - consider using async version

            return response

        except Exception as e:
            logger.error(f"[TRACKED_CLAUDE] Sync chat error: {str(e)}")
            raise

    async def stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        request_type: str = "chat",
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        store_payload: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response with usage tracking.

        Usage is tracked after streaming completes.

        Args:
            model: Claude model identifier
            messages: List of message dicts
            request_type: Type of request
            system: Optional system prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            store_payload: Whether to store payloads

        Yields:
            Response text chunks as they arrive
        """
        logger.info(f"[TRACKED_CLAUDE] Stream request - model={model}")

        start_time = time.time()
        full_response = []
        input_tokens = 0
        output_tokens = 0
        status = "success"
        error_message = None

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
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

                # Get final message with usage
                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

            logger.info(
                f"[TRACKED_CLAUDE] Stream complete - tokens: "
                f"input={input_tokens}, output={output_tokens}"
            )

        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"[TRACKED_CLAUDE] Stream error: {error_message}")
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            request_payload = None
            response_payload = None

            if store_payload:
                request_payload = {
                    "model": model,
                    "messages": self._truncate_messages(messages),
                    "system": system[:500] if system else None,
                }
                response_text = "".join(full_response)
                response_payload = {
                    "content": response_text[:2000] if response_text else None,
                }

            # Track usage
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

    def _truncate_messages(
        self,
        messages: List[Dict[str, Any]],
        max_content_length: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Truncate message contents for storage.

        Keeps message structure but limits content length to reduce storage.

        Args:
            messages: Original messages
            max_content_length: Max characters per message content

        Returns:
            Truncated messages
        """
        truncated = []
        for msg in messages:
            truncated_msg = {"role": msg.get("role")}
            content = msg.get("content", "")

            if isinstance(content, str):
                truncated_msg["content"] = (
                    content[:max_content_length] + "..."
                    if len(content) > max_content_length
                    else content
                )
            elif isinstance(content, list):
                # Handle multi-part content
                truncated_msg["content"] = f"[{len(content)} parts]"
            else:
                truncated_msg["content"] = str(content)[:max_content_length]

            truncated.append(truncated_msg)

        return truncated
