"""
Forge Streaming Module.

Provides real-time code streaming capabilities for the Forge executor.
Integrates with the existing events infrastructure (step_code_chunk, etc.)
to provide live code generation feedback to the UI.

Usage:
    from app.agents.forge_streaming import StreamingExecutor

    executor = StreamingExecutor(claude_service, event_emitter=emit_event)
    async for event in executor.execute_step_streaming(step, context, ...):
        await send_to_client(event)
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, AsyncGenerator, Callable, Any, Dict

from app.agents.config import AgentConfig
from app.agents.context_retriever import RetrievedContext
from app.agents.executor import (
    Executor,
    ExecutionResult,
    CodePatterns,
    ExecutionReasoning,
    safe_format,
    EXECUTION_SYSTEM_CREATE,
    EXECUTION_SYSTEM_MODIFY,
    REASONING_SYSTEM_PROMPT,
    REASONING_USER_PROMPT,
)
from app.agents.planner import PlanStep
from app.services.claude import ClaudeService, ClaudeModel

logger = logging.getLogger(__name__)


# =============================================================================
# STREAMING EVENT TYPES
# =============================================================================

class StreamEventType(str, Enum):
    """Types of streaming events emitted during code generation."""

    # Execution lifecycle
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"

    # Reasoning phase
    REASONING_STARTED = "reasoning_started"
    REASONING_CHUNK = "reasoning_chunk"
    REASONING_COMPLETED = "reasoning_completed"

    # Code generation phase
    CODE_STARTED = "code_started"
    CODE_CHUNK = "code_chunk"
    CODE_COMPLETED = "code_completed"

    # Verification phase
    VERIFY_STARTED = "verify_started"
    VERIFY_COMPLETED = "verify_completed"

    # Fix phase
    FIX_STARTED = "fix_started"
    FIX_CHUNK = "fix_chunk"
    FIX_COMPLETED = "fix_completed"

    # Progress updates
    PROGRESS = "progress"
    THINKING = "thinking"


@dataclass
class StreamEvent:
    """An event emitted during streaming code generation."""

    event_type: StreamEventType
    data: Dict[str, Any] = field(default_factory=dict)

    # For code chunks
    content: str = ""
    file_path: str = ""

    # Progress tracking
    progress: float = 0.0
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.event_type.value,
            "data": self.data,
            "content": self.content,
            "file_path": self.file_path,
            "progress": self.progress,
            "message": self.message,
        }

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        return f"event: {self.event_type.value}\ndata: {json.dumps(self.to_dict())}\n\n"


# =============================================================================
# STREAMING CODE BUFFER
# =============================================================================

class CodeBuffer:
    """
    Buffers streamed code and extracts complete segments.

    Handles the challenge of streaming JSON responses where the code
    content is embedded in a JSON string.
    """

    def __init__(self):
        self.buffer = ""
        self.in_content = False
        self.content_key = '"content":'
        self.escape_next = False
        self.extracted_content = ""

    def add_chunk(self, chunk: str) -> List[str]:
        """
        Add a chunk and return any complete code segments.

        Returns list of code segments ready for streaming to UI.
        """
        self.buffer += chunk
        segments = []

        # Look for the start of content field
        if not self.in_content:
            content_start = self.buffer.find(self.content_key)
            if content_start != -1:
                # Find the opening quote after "content":
                quote_start = self.buffer.find('"', content_start + len(self.content_key))
                if quote_start != -1:
                    self.in_content = True
                    self.buffer = self.buffer[quote_start + 1:]  # Start after opening quote

        if self.in_content:
            # Process character by character to handle escapes
            new_content = ""
            i = 0
            while i < len(self.buffer):
                char = self.buffer[i]

                if self.escape_next:
                    # Handle escape sequences
                    if char == 'n':
                        new_content += '\n'
                    elif char == 't':
                        new_content += '\t'
                    elif char == 'r':
                        new_content += '\r'
                    elif char == '"':
                        new_content += '"'
                    elif char == '\\':
                        new_content += '\\'
                    else:
                        new_content += char
                    self.escape_next = False
                elif char == '\\':
                    self.escape_next = True
                elif char == '"':
                    # End of content string
                    self.in_content = False
                    self.buffer = self.buffer[i + 1:]
                    break
                else:
                    new_content += char

                i += 1

            if new_content:
                self.extracted_content += new_content
                segments.append(new_content)

            # Clear processed buffer if still in content
            if self.in_content:
                self.buffer = ""

        return segments

    def get_full_content(self) -> str:
        """Get all extracted content so far."""
        return self.extracted_content

    def reset(self):
        """Reset the buffer state."""
        self.buffer = ""
        self.in_content = False
        self.escape_next = False
        self.extracted_content = ""


# =============================================================================
# STREAMING EXECUTOR
# =============================================================================

class StreamingExecutor(Executor):
    """
    Enhanced Executor with streaming code generation.

    Extends the base Executor to provide real-time streaming of:
    - Reasoning/thinking process
    - Generated code chunks
    - Progress updates

    Integrates with the existing events infrastructure.
    """

    def __init__(
            self,
            claude_service: Optional[ClaudeService] = None,
            config: Optional[AgentConfig] = None,
            event_emitter: Optional[Callable[[StreamEvent], Any]] = None,
    ):
        """
        Initialize the streaming executor.

        Args:
            claude_service: Claude API service
            config: Agent configuration
            event_emitter: Optional callback for emitting events to UI
        """
        super().__init__(claude_service, config)
        self.event_emitter = event_emitter
        logger.info("[FORGE:STREAMING] Initialized with streaming support")

    async def _emit(self, event: StreamEvent) -> None:
        """Emit an event if emitter is configured."""
        if self.event_emitter:
            try:
                result = self.event_emitter(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"[FORGE:STREAMING] Error emitting event: {e}")

    async def execute_step_streaming(
            self,
            step: PlanStep,
            context: RetrievedContext,
            previous_results: List[ExecutionResult],
            current_file_content: Optional[str] = None,
            project_context: str = "",
            enable_self_verification: bool = True,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute a plan step with streaming output.

        Yields StreamEvents as code is generated, allowing real-time
        display in the UI.

        Usage:
            async for event in executor.execute_step_streaming(...):
                if event.event_type == StreamEventType.CODE_CHUNK:
                    display_code_chunk(event.content)
        """
        logger.info(f"[FORGE:STREAMING] Starting step {step.order}: [{step.action}] {step.file}")

        # Emit start event
        yield StreamEvent(
            event_type=StreamEventType.STEP_STARTED,
            file_path=step.file,
            message=f"Starting {step.action} on {step.file}",
            progress=0.0,
            data={"action": step.action, "file": step.file},
        )

        # Validate file exists for modify
        if step.action == "modify" and self.config.REQUIRE_FILE_EXISTS_FOR_MODIFY:
            if not current_file_content:
                yield StreamEvent(
                    event_type=StreamEventType.STEP_FAILED,
                    file_path=step.file,
                    message=f"File '{step.file}' not found",
                    data={"error": "File not found for modify action"},
                )
                return

        try:
            # Phase 1: Extract patterns
            yield StreamEvent(
                event_type=StreamEventType.THINKING,
                message="Analyzing code patterns...",
                progress=0.1,
            )
            patterns = self._extract_code_patterns(context, step.file)

            # Phase 2: Generate reasoning with streaming
            yield StreamEvent(
                event_type=StreamEventType.REASONING_STARTED,
                message="Planning implementation...",
                progress=0.15,
            )

            reasoning = None
            async for event in self._stream_reasoning(step, patterns, context, current_file_content or ""):
                yield event
                if event.event_type == StreamEventType.REASONING_COMPLETED:
                    reasoning = event.data.get("reasoning")

            if not reasoning:
                reasoning = ExecutionReasoning(task_understanding=step.description)

            # Phase 3: Generate code with streaming
            yield StreamEvent(
                event_type=StreamEventType.CODE_STARTED,
                file_path=step.file,
                message=f"Generating code for {step.file}...",
                progress=0.3,
            )

            result = None
            prev_results_str = self._format_previous_results(previous_results)

            if step.action == "create":
                async for event in self._stream_create(step, context, prev_results_str, patterns, reasoning):
                    yield event
                    if event.event_type == StreamEventType.CODE_COMPLETED:
                        result = event.data.get("result")
            elif step.action == "modify":
                async for event in self._stream_modify(
                        step, context, prev_results_str, current_file_content or "", patterns, reasoning
                ):
                    yield event
                    if event.event_type == StreamEventType.CODE_COMPLETED:
                        result = event.data.get("result")
            elif step.action == "delete":
                # Delete doesn't need streaming
                result = await self._execute_delete(step, context, current_file_content or "")
                yield StreamEvent(
                    event_type=StreamEventType.CODE_COMPLETED,
                    file_path=step.file,
                    progress=0.8,
                    data={"result": result},
                )

            if not result:
                yield StreamEvent(
                    event_type=StreamEventType.STEP_FAILED,
                    file_path=step.file,
                    message="Code generation failed",
                )
                return

            # Phase 4: Verify (optional)
            if enable_self_verification and result.content:
                yield StreamEvent(
                    event_type=StreamEventType.VERIFY_STARTED,
                    message="Verifying generated code...",
                    progress=0.85,
                )

                passes, issues = await self._verify_result(result, current_file_content)

                yield StreamEvent(
                    event_type=StreamEventType.VERIFY_COMPLETED,
                    data={"passes": passes, "issues": issues},
                    progress=0.9,
                )

                # Fix if needed
                if not passes and issues:
                    yield StreamEvent(
                        event_type=StreamEventType.FIX_STARTED,
                        message=f"Fixing {len(issues)} issues...",
                        progress=0.92,
                    )

                    async for event in self._stream_fix(result, issues, context, patterns):
                        yield event
                        if event.event_type == StreamEventType.FIX_COMPLETED:
                            result = event.data.get("result", result)

            # Emit completion
            result.reasoning = reasoning
            result.patterns_used = patterns

            yield StreamEvent(
                event_type=StreamEventType.STEP_COMPLETED,
                file_path=step.file,
                message=f"Completed {step.action} on {step.file}",
                progress=1.0,
                data={"result": result.to_dict()},
            )

        except Exception as e:
            logger.error(f"[FORGE:STREAMING] Error: {e}")
            yield StreamEvent(
                event_type=StreamEventType.STEP_FAILED,
                file_path=step.file,
                message=str(e),
                data={"error": str(e)},
            )

    async def _stream_reasoning(
            self,
            step: PlanStep,
            patterns: CodePatterns,
            context: RetrievedContext,
            current_content: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream the reasoning phase."""

        user_prompt = safe_format(
            REASONING_USER_PROMPT,
            action=step.action,
            file_path=step.file,
            description=step.description,
            current_content=current_content[:5000] if current_content else "N/A",
            patterns=patterns.to_prompt_string(),
            context=context.to_prompt_string()[:8000],
        )

        try:
            full_response = ""

            async for chunk in self.claude.stream_cached(
                    model=ClaudeModel.SONNET,
                    messages=[{"role": "user", "content": user_prompt}],
                    system=REASONING_SYSTEM_PROMPT,
                    temperature=0.2,
                    max_tokens=2048,
                    request_type="reasoning",
            ):
                full_response += chunk

                # Emit reasoning chunks for UI
                yield StreamEvent(
                    event_type=StreamEventType.REASONING_CHUNK,
                    content=chunk,
                    message="Thinking...",
                )

            # Parse the complete response
            data = self._parse_response(full_response)
            reasoning = ExecutionReasoning(
                task_understanding=data.get("task_understanding", ""),
                file_purpose=data.get("file_purpose", ""),
                required_imports=data.get("required_imports", []),
                dependencies=data.get("dependencies", []),
                insertion_point=data.get("insertion_point", ""),
                preservation_notes=data.get("preservation_notes", ""),
                implementation_steps=data.get("implementation_steps", []),
                potential_issues=data.get("potential_issues", []),
            )

            yield StreamEvent(
                event_type=StreamEventType.REASONING_COMPLETED,
                message="Planning complete",
                progress=0.25,
                data={"reasoning": reasoning},
            )

        except Exception as e:
            logger.warning(f"[FORGE:STREAMING] Reasoning failed: {e}")
            yield StreamEvent(
                event_type=StreamEventType.REASONING_COMPLETED,
                data={"reasoning": ExecutionReasoning(task_understanding=step.description)},
            )

    async def _stream_create(
            self,
            step: PlanStep,
            context: RetrievedContext,
            previous_results: str,
            patterns: CodePatterns,
            reasoning: ExecutionReasoning,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream CREATE action with real-time code output."""

        from app.agents.executor import EXECUTION_USER_CREATE

        reasoning_str = json.dumps(reasoning.to_dict(), indent=2)

        user_prompt = safe_format(
            EXECUTION_USER_CREATE,
            reasoning=reasoning_str,
            patterns=patterns.to_prompt_string(),
            file_path=step.file,
            description=step.description,
            context=context.to_prompt_string(),
            previous_results=previous_results,
        )

        buffer = CodeBuffer()
        full_response = ""

        try:
            async for chunk in self.claude.stream_cached(
                    model=ClaudeModel.SONNET,
                    messages=[{"role": "user", "content": user_prompt}],
                    system=EXECUTION_SYSTEM_CREATE,
                    temperature=0.3,
                    max_tokens=8192,
                    request_type="execution",
            ):
                full_response += chunk

                # Extract code segments from the JSON stream
                code_segments = buffer.add_chunk(chunk)
                for segment in code_segments:
                    yield StreamEvent(
                        event_type=StreamEventType.CODE_CHUNK,
                        content=segment,
                        file_path=step.file,
                    )

            # Parse final result
            data = self._parse_response(full_response)
            content = data.get("content", "") or buffer.get_full_content()
            diff = self._generate_diff("", content, step.file)

            result = ExecutionResult(
                file=step.file,
                action="create",
                content=content,
                diff=diff,
                original_content="",
            )

            yield StreamEvent(
                event_type=StreamEventType.CODE_COMPLETED,
                file_path=step.file,
                content=content,
                progress=0.8,
                data={"result": result},
            )

        except Exception as e:
            logger.error(f"[FORGE:STREAMING] Create failed: {e}")
            yield StreamEvent(
                event_type=StreamEventType.STEP_FAILED,
                file_path=step.file,
                message=str(e),
            )

    async def _stream_modify(
            self,
            step: PlanStep,
            context: RetrievedContext,
            previous_results: str,
            current_content: str,
            patterns: CodePatterns,
            reasoning: ExecutionReasoning,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream MODIFY action with real-time code output."""

        from app.agents.executor import EXECUTION_USER_MODIFY

        reasoning_str = json.dumps(reasoning.to_dict(), indent=2)

        user_prompt = safe_format(
            EXECUTION_USER_MODIFY,
            reasoning=reasoning_str,
            patterns=patterns.to_prompt_string(),
            file_path=step.file,
            description=step.description,
            current_content=current_content,
            context=context.to_prompt_string(),
            previous_results=previous_results,
        )

        buffer = CodeBuffer()
        full_response = ""

        try:
            async for chunk in self.claude.stream_cached(
                    model=ClaudeModel.SONNET,
                    messages=[{"role": "user", "content": user_prompt}],
                    system=EXECUTION_SYSTEM_MODIFY,
                    temperature=0.3,
                    max_tokens=8192,
                    request_type="execution",
            ):
                full_response += chunk

                # Extract code segments
                code_segments = buffer.add_chunk(chunk)
                for segment in code_segments:
                    yield StreamEvent(
                        event_type=StreamEventType.CODE_CHUNK,
                        content=segment,
                        file_path=step.file,
                    )

            # Parse final result
            data = self._parse_response(full_response)
            content = data.get("content", "") or buffer.get_full_content()
            diff = self._generate_diff(current_content, content, step.file)

            # Check content preservation
            warnings = []
            preservation_check = self._check_content_preservation(current_content, content)
            if not preservation_check["preserved"]:
                warnings.extend(preservation_check["issues"])

            result = ExecutionResult(
                file=step.file,
                action="modify",
                content=content,
                diff=diff,
                original_content=current_content,
                warnings=warnings,
            )

            yield StreamEvent(
                event_type=StreamEventType.CODE_COMPLETED,
                file_path=step.file,
                content=content,
                progress=0.8,
                data={"result": result},
            )

        except Exception as e:
            logger.error(f"[FORGE:STREAMING] Modify failed: {e}")
            yield StreamEvent(
                event_type=StreamEventType.STEP_FAILED,
                file_path=step.file,
                message=str(e),
            )

    async def _stream_fix(
            self,
            result: ExecutionResult,
            issues: List[str],
            context: RetrievedContext,
            patterns: CodePatterns,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream the fix phase."""

        from app.agents.executor import FIX_SYSTEM_PROMPT

        original_section = ""
        if result.action == "modify" and result.original_content:
            original_section = f"""
<original_file_content>
```php
{result.original_content}
```
</original_file_content>
"""

        user_prompt = f"""<context>
<file>{result.file}</file>
<action>{result.action}</action>
</context>
{original_section}
<generated_code_with_issues>
```php
{result.content}
```
</generated_code_with_issues>

<issues_to_fix>
{chr(10).join(f"- {issue}" for issue in issues)}
</issues_to_fix>

<detected_patterns>
{patterns.to_prompt_string()}
</detected_patterns>

<output_format>
{{
  "file": "{result.file}",
  "action": "{result.action}",
  "content": "complete fixed file content",
  "fixes_applied": ["Brief description of each fix"]
}}
</output_format>"""

        buffer = CodeBuffer()
        full_response = ""

        try:
            async for chunk in self.claude.stream_cached(
                    model=ClaudeModel.SONNET,
                    messages=[{"role": "user", "content": user_prompt}],
                    system=FIX_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=8192,
                    request_type="fix",
            ):
                full_response += chunk

                code_segments = buffer.add_chunk(chunk)
                for segment in code_segments:
                    yield StreamEvent(
                        event_type=StreamEventType.FIX_CHUNK,
                        content=segment,
                        file_path=result.file,
                    )

            # Parse result
            data = self._parse_response(full_response)
            content = data.get("content", "") or buffer.get_full_content()
            diff = self._generate_diff(result.original_content, content, result.file)

            fixed_result = ExecutionResult(
                file=result.file,
                action=result.action,
                content=content,
                diff=diff,
                original_content=result.original_content,
            )

            yield StreamEvent(
                event_type=StreamEventType.FIX_COMPLETED,
                file_path=result.file,
                progress=0.95,
                data={"result": fixed_result},
            )

        except Exception as e:
            logger.error(f"[FORGE:STREAMING] Fix failed: {e}")
            yield StreamEvent(
                event_type=StreamEventType.FIX_COMPLETED,
                data={"result": result},  # Return original on failure
            )


# =============================================================================
# INTEGRATION WITH INTERACTIVE ORCHESTRATOR
# =============================================================================

async def stream_execution_to_events(
        executor: StreamingExecutor,
        step: PlanStep,
        context: RetrievedContext,
        previous_results: List[ExecutionResult],
        current_file_content: Optional[str],
        event_callback: Callable[[Dict[str, Any]], Any],
) -> ExecutionResult:
    """
    Bridge function to integrate StreamingExecutor with InteractiveOrchestrator.

    Converts StreamEvents to the existing event format used by
    step_code_chunk, step_progress, etc.

    Usage in InteractiveOrchestrator:
        from app.agents.forge_streaming import StreamingExecutor, stream_execution_to_events

        streaming_executor = StreamingExecutor(self.claude, event_emitter=self._emit_event)

        result = await stream_execution_to_events(
            streaming_executor,
            step,
            context,
            previous_results,
            current_content,
            self._emit_event,
        )
    """
    result = None

    async for event in executor.execute_step_streaming(
            step=step,
            context=context,
            previous_results=previous_results,
            current_file_content=current_file_content,
    ):
        # Convert StreamEvent to existing event format
        if event.event_type == StreamEventType.CODE_CHUNK:
            # Use the existing step_code_chunk event
            await event_callback({
                "type": "step_code_chunk",
                "data": {
                    "step_order": step.order,
                    "file": step.file,
                    "chunk": event.content,
                },
            })

        elif event.event_type == StreamEventType.PROGRESS:
            await event_callback({
                "type": "step_progress",
                "data": {
                    "step_order": step.order,
                    "progress": event.progress,
                    "message": event.message,
                },
            })

        elif event.event_type == StreamEventType.THINKING:
            await event_callback({
                "type": "step_thinking",
                "data": {
                    "step_order": step.order,
                    "message": event.message,
                },
            })

        elif event.event_type == StreamEventType.STEP_COMPLETED:
            result = ExecutionResult.from_dict(event.data.get("result", {}))

        elif event.event_type == StreamEventType.STEP_FAILED:
            result = ExecutionResult(
                file=step.file,
                action=step.action,
                content="",
                success=False,
                error=event.message,
            )

    return result or ExecutionResult(
        file=step.file,
        action=step.action,
        content="",
        success=False,
        error="No result from streaming execution",
    )
