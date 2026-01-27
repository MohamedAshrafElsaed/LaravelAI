"""
InstrumentedClaudeService - Wrapper around ClaudeService for exhaustive logging.

Intercepts all Claude API calls to capture full prompts, responses,
timing, and token metrics for test logging.
"""

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from unittest.mock import MagicMock, AsyncMock

from .agent_logger import AgentLogger


class InstrumentedClaudeService:
    """
    Wrapper around ClaudeService that intercepts all calls for logging.

    Can wrap either a real ClaudeService or a mock for testing.
    Captures full prompts, responses, timing, and metrics.
    """

    def __init__(
        self,
        claude_service: Any,
        agent_logger: AgentLogger,
        default_agent: str = "UNKNOWN",
    ):
        """
        Initialize the instrumented service.

        Args:
            claude_service: The underlying ClaudeService or mock
            agent_logger: AgentLogger instance for logging
            default_agent: Default agent name for logging (can be overridden per-call)
        """
        self._service = claude_service
        self._logger = agent_logger
        self._default_agent = default_agent
        self._current_agent = default_agent
        self._current_operation = "chat"

    def set_context(self, agent: str, operation: str = "chat") -> None:
        """
        Set the current agent context for logging.

        Args:
            agent: Agent name (NOVA, SCOUT, BLUEPRINT, etc.)
            operation: Operation type (analyze, retrieve, plan, execute, validate)
        """
        self._current_agent = agent
        self._current_operation = operation

    async def chat_async(
        self,
        model: Any,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        use_cache: bool = True,
        **kwargs,
    ) -> str:
        """
        Instrumented async chat call with full logging.

        Captures the complete prompt, response, timing, and token usage.
        """
        model_id = model.value if hasattr(model, "value") else str(model)
        start_time = time.time()
        error = None
        response_content = ""
        usage = {}

        try:
            # Check if service is a mock
            if isinstance(self._service.chat_async, (MagicMock, AsyncMock)):
                # For mocks, call directly and extract response
                result = await self._service.chat_async(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    use_cache=use_cache,
                    **kwargs,
                )
                response_content = result if isinstance(result, str) else str(result)
                # Try to get usage from mock if available
                if hasattr(self._service, "_last_usage"):
                    usage = self._service._last_usage
            else:
                # Real service call
                response_content = await self._service.chat_async(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    use_cache=use_cache,
                    **kwargs,
                )

            return response_content

        except Exception as e:
            error = str(e)
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            # Log the call
            self._logger.log_claude_call(
                agent=self._current_agent,
                operation=self._current_operation,
                model=model_id,
                system_prompt=system or "",
                messages=messages,
                response_content=response_content,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason="end_turn" if not error else "error",
                error=error,
            )

    async def chat_async_cached(
        self,
        model: Any,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> str:
        """
        Instrumented cached async chat call with full logging.
        """
        model_id = model.value if hasattr(model, "value") else str(model)
        start_time = time.time()
        error = None
        response_content = ""
        usage = {}

        try:
            if isinstance(self._service.chat_async_cached, (MagicMock, AsyncMock)):
                result = await self._service.chat_async_cached(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                )
                response_content = result if isinstance(result, str) else str(result)
                if hasattr(self._service, "_last_usage"):
                    usage = self._service._last_usage
            else:
                response_content = await self._service.chat_async_cached(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                )

            return response_content

        except Exception as e:
            error = str(e)
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.log_claude_call(
                agent=self._current_agent,
                operation=self._current_operation,
                model=model_id,
                system_prompt=system or "",
                messages=messages,
                response_content=response_content,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason="end_turn" if not error else "error",
                error=error,
            )

    async def stream(
        self,
        model: Any,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Instrumented streaming call with full logging.

        Collects all chunks for logging while yielding them.
        """
        model_id = model.value if hasattr(model, "value") else str(model)
        start_time = time.time()
        error = None
        full_response: List[str] = []
        usage = {}

        try:
            if isinstance(self._service.stream, (MagicMock, AsyncMock)):
                # Handle mock - might return list or async generator
                stream_result = self._service.stream(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                )

                if hasattr(stream_result, "__aiter__"):
                    async for chunk in stream_result:
                        full_response.append(chunk)
                        yield chunk
                else:
                    # Mock returned a coroutine or list
                    result = await stream_result if hasattr(stream_result, "__await__") else stream_result
                    if isinstance(result, list):
                        for chunk in result:
                            full_response.append(chunk)
                            yield chunk
                    else:
                        full_response.append(str(result))
                        yield str(result)

                if hasattr(self._service, "_last_usage"):
                    usage = self._service._last_usage
            else:
                async for chunk in self._service.stream(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                ):
                    full_response.append(chunk)
                    yield chunk

        except Exception as e:
            error = str(e)
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            response_content = "".join(full_response)

            self._logger.log_claude_call(
                agent=self._current_agent,
                operation=self._current_operation,
                model=model_id,
                system_prompt=system or "",
                messages=messages,
                response_content=response_content,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason="end_turn" if not error else "error",
                error=error,
            )

    async def stream_cached(
        self,
        model: Any,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Instrumented cached streaming call with full logging.
        """
        model_id = model.value if hasattr(model, "value") else str(model)
        start_time = time.time()
        error = None
        full_response: List[str] = []
        usage = {}

        try:
            if isinstance(self._service.stream_cached, (MagicMock, AsyncMock)):
                stream_result = self._service.stream_cached(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                )

                if hasattr(stream_result, "__aiter__"):
                    async for chunk in stream_result:
                        full_response.append(chunk)
                        yield chunk
                else:
                    result = await stream_result if hasattr(stream_result, "__await__") else stream_result
                    if isinstance(result, list):
                        for chunk in result:
                            full_response.append(chunk)
                            yield chunk
                    else:
                        full_response.append(str(result))
                        yield str(result)

                if hasattr(self._service, "_last_usage"):
                    usage = self._service._last_usage
            else:
                async for chunk in self._service.stream_cached(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                ):
                    full_response.append(chunk)
                    yield chunk

        except Exception as e:
            error = str(e)
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            response_content = "".join(full_response)

            self._logger.log_claude_call(
                agent=self._current_agent,
                operation=self._current_operation,
                model=model_id,
                system_prompt=system or "",
                messages=messages,
                response_content=response_content,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason="end_turn" if not error else "error",
                error=error,
            )

    def chat(
        self,
        model: Any,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> str:
        """
        Instrumented synchronous chat call with full logging.
        """
        model_id = model.value if hasattr(model, "value") else str(model)
        start_time = time.time()
        error = None
        response_content = ""
        usage = {}

        try:
            if isinstance(self._service.chat, MagicMock):
                result = self._service.chat(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                )
                response_content = result if isinstance(result, str) else str(result)
                if hasattr(self._service, "_last_usage"):
                    usage = self._service._last_usage
            else:
                response_content = self._service.chat(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    request_type=request_type,
                    **kwargs,
                )

            return response_content

        except Exception as e:
            error = str(e)
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.log_claude_call(
                agent=self._current_agent,
                operation=self._current_operation,
                model=model_id,
                system_prompt=system or "",
                messages=messages,
                response_content=response_content,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason="end_turn" if not error else "error",
                error=error,
            )

    def __getattr__(self, name: str) -> Any:
        """
        Forward any other attribute access to the underlying service.

        This allows the instrumented service to be used as a drop-in
        replacement for ClaudeService.
        """
        return getattr(self._service, name)


class MockClaudeServiceWithUsage:
    """
    Mock ClaudeService that tracks usage for testing.

    Provides configurable responses and tracks all calls
    with simulated token usage.
    """

    def __init__(
        self,
        default_response: str = "Mock response",
        responses: Optional[Dict[str, str]] = None,
        simulate_tokens: bool = True,
    ):
        """
        Initialize the mock service.

        Args:
            default_response: Default response for all calls
            responses: Dict mapping operation types to specific responses
            simulate_tokens: Whether to simulate token usage
        """
        self.default_response = default_response
        self.responses = responses or {}
        self.simulate_tokens = simulate_tokens
        self.calls: List[Dict[str, Any]] = []
        self._last_usage: Dict[str, int] = {}

    def _get_response(self, request_type: str, messages: List[Dict]) -> str:
        """Get response for the given request type."""
        if request_type in self.responses:
            return self.responses[request_type]

        # Check for keyword matches in messages
        last_message = messages[-1].get("content", "") if messages else ""
        if isinstance(last_message, str):
            for key, response in self.responses.items():
                if key.lower() in last_message.lower():
                    return response

        return self.default_response

    def _simulate_usage(self, system: Optional[str], messages: List[Dict], response: str) -> Dict[str, int]:
        """Simulate token usage."""
        if not self.simulate_tokens:
            return {}

        # Rough estimation: 1 token ≈ 4 chars
        system_tokens = len(system or "") // 4
        message_tokens = sum(len(str(m.get("content", ""))) // 4 for m in messages)
        response_tokens = len(response) // 4

        self._last_usage = {
            "input_tokens": system_tokens + message_tokens,
            "output_tokens": response_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        return self._last_usage

    def _record_call(
        self,
        method: str,
        model: Any,
        messages: List[Dict],
        system: Optional[str],
        request_type: str,
        **kwargs,
    ) -> None:
        """Record a call for inspection."""
        self.calls.append({
            "method": method,
            "model": str(model),
            "messages": messages,
            "system": system,
            "request_type": request_type,
            "kwargs": kwargs,
        })

    async def chat_async(
        self,
        model: Any,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        use_cache: bool = True,
        **kwargs,
    ) -> str:
        """Mock async chat."""
        self._record_call("chat_async", model, messages, system, request_type, **kwargs)
        response = self._get_response(request_type, messages)
        self._simulate_usage(system, messages, response)
        return response

    async def chat_async_cached(
        self,
        model: Any,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> str:
        """Mock cached async chat."""
        self._record_call("chat_async_cached", model, messages, system, request_type, **kwargs)
        response = self._get_response(request_type, messages)
        usage = self._simulate_usage(system, messages, response)
        # Simulate cache hit
        usage["cache_read_input_tokens"] = usage.get("input_tokens", 0) // 2
        return response

    async def stream(
        self,
        model: Any,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Mock streaming."""
        self._record_call("stream", model, messages, system, request_type, **kwargs)
        response = self._get_response(request_type, messages)
        self._simulate_usage(system, messages, response)

        # Yield in chunks
        words = response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    async def stream_cached(
        self,
        model: Any,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Mock cached streaming."""
        self._record_call("stream_cached", model, messages, system, request_type, **kwargs)
        response = self._get_response(request_type, messages)
        usage = self._simulate_usage(system, messages, response)
        usage["cache_read_input_tokens"] = usage.get("input_tokens", 0) // 2

        words = response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    def chat(
        self,
        model: Any,
        messages: List[Dict],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        request_type: str = "chat",
        **kwargs,
    ) -> str:
        """Mock sync chat."""
        self._record_call("chat", model, messages, system, request_type, **kwargs)
        response = self._get_response(request_type, messages)
        self._simulate_usage(system, messages, response)
        return response

    def get_calls(self) -> List[Dict[str, Any]]:
        """Get all recorded calls."""
        return self.calls

    def clear_calls(self) -> None:
        """Clear recorded calls."""
        self.calls = []


def create_instrumented_mock(
    agent_logger: AgentLogger,
    responses: Optional[Dict[str, str]] = None,
    default_agent: str = "TEST",
) -> InstrumentedClaudeService:
    """
    Create an instrumented mock Claude service for testing.

    Args:
        agent_logger: AgentLogger for logging
        responses: Optional dict of request_type -> response
        default_agent: Default agent name

    Returns:
        InstrumentedClaudeService wrapping a mock
    """
    mock_service = MockClaudeServiceWithUsage(responses=responses)
    return InstrumentedClaudeService(
        claude_service=mock_service,
        agent_logger=agent_logger,
        default_agent=default_agent,
    )
