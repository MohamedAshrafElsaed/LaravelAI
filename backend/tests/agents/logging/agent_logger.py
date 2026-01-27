"""
AgentLogger - Core logging class for exhaustive agent operation tracking.

Provides comprehensive logging capabilities for capturing every operation,
prompt, response, file access, and data transfer during multi-agent execution.
"""

import json
import os
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
import uuid

from .log_schemas import (
    AgentExecutionLog,
    ClaudeCallLog,
    ContextRetrievalLog,
    CostBreakdown,
    ErrorLog,
    FileAccessLog,
    LogEntry,
    LogLevel,
    LogPhase,
    MetricsSummary,
    TokenUsage,
)


# Claude pricing (per million tokens) as of 2024
CLAUDE_PRICING = {
    "claude-3-opus-20240229": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.5},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
    "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
    "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25, "cache_write": 0.3125, "cache_read": 0.025},
    "claude-3-5-haiku-20241022": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.1},
}


class AgentLogger:
    """
    Comprehensive logger for multi-agent test execution.

    Captures ALL operations including:
    - Claude API calls with full prompts/responses
    - Context retrieval operations
    - File accesses
    - Agent inputs/outputs
    - Errors and retries
    - Timing and token metrics
    """

    def __init__(
        self,
        log_dir: Path,
        test_name: str = "test_run",
        save_prompts: bool = True,
        save_responses: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize the agent logger.

        Args:
            log_dir: Directory to save log files
            test_name: Name of the test run
            save_prompts: Whether to save full prompts to separate files
            save_responses: Whether to save full responses to separate files
            verbose: Whether to print log entries to console
        """
        self.run_id = str(uuid.uuid4())
        self.log_dir = Path(log_dir) / self.run_id
        self.test_name = test_name
        self.save_prompts = save_prompts
        self.save_responses = save_responses
        self.verbose = verbose

        # Create directory structure
        self._create_directories()

        # Initialize tracking
        self.metrics = MetricsSummary(run_id=self.run_id, test_name=test_name)
        self.agent_executions: Dict[str, AgentExecutionLog] = {}
        self.current_execution: Optional[AgentExecutionLog] = None
        self.master_log: List[Dict[str, Any]] = []

        # Context tracking for accumulation between agents
        self.context_snapshots: Dict[str, Dict[str, Any]] = {}
        self.call_counter = 0

    def _create_directories(self) -> None:
        """Create the log directory structure."""
        dirs = [
            self.log_dir,
            self.log_dir / "prompts",
            self.log_dir / "responses",
            self.log_dir / "context",
            self.log_dir / "agents",
            self.log_dir / "metrics",
            self.log_dir / "errors",
        ]
        for agent in ["nova", "scout", "blueprint", "forge", "guardian", "palette", "conductor"]:
            dirs.append(self.log_dir / "agents" / agent)

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def agent_execution(
        self, agent: str, operation: str
    ) -> Generator[AgentExecutionLog, None, None]:
        """
        Context manager for tracking an agent's execution.

        Usage:
            with agent_logger.agent_execution("NOVA", "analyze") as execution:
                # Execute agent operations
                result = await agent.analyze(...)
                execution.final_output = result

        Args:
            agent: Agent name (NOVA, SCOUT, BLUEPRINT, FORGE, GUARDIAN, PALETTE)
            operation: Operation being performed

        Yields:
            AgentExecutionLog for tracking
        """
        execution = AgentExecutionLog(agent=agent, operation=operation)
        self.current_execution = execution

        # Log start
        self._log_entry(
            LogLevel.INFO,
            agent,
            operation,
            LogPhase.INPUT,
            f"Starting {agent} execution: {operation}",
        )

        try:
            yield execution
            execution.success = True
        except Exception as e:
            execution.success = False
            self.log_error(agent, e, operation=operation)
            raise
        finally:
            execution.complete()
            self.agent_executions[f"{agent}_{operation}"] = execution
            self.metrics.add_agent_execution(execution)
            self.current_execution = None

            # Log completion
            self._log_entry(
                LogLevel.INFO,
                agent,
                operation,
                LogPhase.OUTPUT,
                f"Completed {agent} execution: {operation} (success={execution.success}, "
                f"duration={execution.duration_ms}ms, tokens={execution.total_tokens})",
            )

            # Save agent-specific logs
            self._save_agent_logs(execution)

    def log_claude_call(
        self,
        agent: str,
        operation: str,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        response_content: str,
        usage: Optional[Dict[str, int]] = None,
        latency_ms: int = 0,
        stop_reason: Optional[str] = None,
        error: Optional[str] = None,
    ) -> ClaudeCallLog:
        """
        Log a Claude API call with full details.

        Args:
            agent: Agent making the call
            operation: Operation type
            model: Claude model used
            system_prompt: Full system prompt
            messages: Full message history
            response_content: Complete response text
            usage: Token usage dict (input_tokens, output_tokens, etc.)
            latency_ms: API call latency
            stop_reason: Reason the model stopped generating
            error: Error message if call failed

        Returns:
            ClaudeCallLog with all details
        """
        self.call_counter += 1

        # Calculate costs
        usage = usage or {}
        token_usage = TokenUsage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
        )

        cost = self._calculate_cost(model, token_usage)

        # Create log entry
        call_log = ClaudeCallLog(
            agent=agent,
            operation=operation,
            model=model,
            system_prompt=system_prompt,
            system_prompt_length=len(system_prompt),
            messages=messages,
            messages_count=len(messages),
            total_message_chars=sum(len(str(m.get("content", ""))) for m in messages),
            response_content=response_content,
            response_length=len(response_content),
            stop_reason=stop_reason,
            token_usage=token_usage,
            cost=cost,
            latency_ms=latency_ms,
            error=error,
        )

        # Add to current execution
        if self.current_execution:
            self.current_execution.add_claude_call(call_log)

        # Log to master log
        self._add_to_master_log("claude_call", call_log.to_dict())

        # Save prompt and response to files
        if self.save_prompts:
            self._save_prompt(agent, self.call_counter, system_prompt, messages)
        if self.save_responses:
            self._save_response(agent, self.call_counter, response_content, call_log.to_dict())

        # Verbose output
        if self.verbose:
            print(f"[{agent}] Claude call: model={model}, tokens={token_usage.total_tokens}, "
                  f"cost=${cost.total_cost:.4f}, latency={latency_ms}ms")

        return call_log

    def log_context_retrieval(
        self,
        agent: str,
        search_queries: List[str],
        chunks_found: int,
        chunks_used: int,
        total_tokens: int,
        file_paths: List[str],
        scores: List[float],
        embedding_latency_ms: int = 0,
        search_latency_ms: int = 0,
    ) -> ContextRetrievalLog:
        """
        Log a context retrieval operation.

        Args:
            agent: Agent performing retrieval (usually SCOUT)
            search_queries: Search queries used
            chunks_found: Total chunks found
            chunks_used: Chunks selected for use
            total_tokens: Total tokens in retrieved context
            file_paths: File paths accessed
            scores: Relevance scores
            embedding_latency_ms: Time to generate embeddings
            search_latency_ms: Time to search vector store

        Returns:
            ContextRetrievalLog with all details
        """
        retrieval_log = ContextRetrievalLog(
            agent=agent,
            search_queries=search_queries,
            query_embeddings_generated=len(search_queries),
            chunks_found=chunks_found,
            chunks_used=chunks_used,
            total_chunk_tokens=total_tokens,
            file_paths=file_paths,
            unique_files=len(set(file_paths)),
            scores=scores,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            max_score=max(scores) if scores else 0.0,
            min_score=min(scores) if scores else 0.0,
            embedding_latency_ms=embedding_latency_ms,
            search_latency_ms=search_latency_ms,
            total_latency_ms=embedding_latency_ms + search_latency_ms,
        )

        # Add to current execution
        if self.current_execution:
            self.current_execution.add_context_retrieval(retrieval_log)

        # Log to master log
        self._add_to_master_log("context_retrieval", retrieval_log.to_dict())

        # Save search queries
        self._save_json(
            self.log_dir / "agents" / agent.lower() / "search_queries.json",
            {"queries": search_queries, "chunks_used": chunks_used},
        )

        if self.verbose:
            print(f"[{agent}] Context retrieval: {len(search_queries)} queries, "
                  f"{chunks_used}/{chunks_found} chunks used")

        return retrieval_log

    def log_file_access(
        self,
        agent: str,
        operation: str,
        file_path: str,
        content: Optional[str] = None,
        search_pattern: Optional[str] = None,
        matches_found: int = 0,
        latency_ms: int = 0,
        error: Optional[str] = None,
    ) -> FileAccessLog:
        """
        Log a file access operation.

        Args:
            agent: Agent accessing the file
            operation: Type of access (read, write, search, list)
            file_path: Path to the file
            content: File content (for read/write)
            search_pattern: Search pattern (for search operations)
            matches_found: Number of matches (for search)
            latency_ms: Operation latency
            error: Error message if failed

        Returns:
            FileAccessLog with details
        """
        # Determine file type from extension
        file_type = Path(file_path).suffix.lstrip(".") if file_path else "unknown"

        access_log = FileAccessLog(
            agent=agent,
            operation=operation,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=len(content.encode()) if content else 0,
            content_preview=content[:500] if content else "",
            content_length=len(content) if content else 0,
            line_count=content.count("\n") + 1 if content else 0,
            search_pattern=search_pattern,
            matches_found=matches_found,
            latency_ms=latency_ms,
            error=error,
        )

        # Add to current execution
        if self.current_execution:
            self.current_execution.add_file_access(access_log)

        # Log to master log
        self._add_to_master_log("file_access", access_log.to_dict())

        if self.verbose:
            print(f"[{agent}] File {operation}: {file_path}")

        return access_log

    def log_agent_input(
        self, agent: str, input_data: Dict[str, Any], operation: str = ""
    ) -> None:
        """
        Log the input to an agent.

        Args:
            agent: Agent name
            input_data: Input data dictionary
            operation: Operation type
        """
        self._log_entry(
            LogLevel.INFO,
            agent,
            operation,
            LogPhase.INPUT,
            f"Agent input received",
            input_data=input_data,
        )

        # Save to agent directory
        self._save_json(
            self.log_dir / "agents" / agent.lower() / "input.json",
            input_data,
        )

    def log_agent_output(
        self, agent: str, output_data: Any, operation: str = ""
    ) -> None:
        """
        Log the output from an agent.

        Args:
            agent: Agent name
            output_data: Output data (will be serialized)
            operation: Operation type
        """
        # Serialize output if needed
        if hasattr(output_data, "to_dict"):
            serialized = output_data.to_dict()
        elif hasattr(output_data, "__dict__"):
            serialized = {k: str(v) for k, v in output_data.__dict__.items() if not k.startswith("_")}
        else:
            serialized = str(output_data)

        self._log_entry(
            LogLevel.INFO,
            agent,
            operation,
            LogPhase.OUTPUT,
            f"Agent output generated",
            output_data=serialized if isinstance(serialized, dict) else {"value": serialized},
        )

        # Save to agent directory
        self._save_json(
            self.log_dir / "agents" / agent.lower() / "output.json",
            serialized if isinstance(serialized, dict) else {"value": serialized},
        )

    def log_context_snapshot(
        self, snapshot_name: str, context_data: Dict[str, Any]
    ) -> None:
        """
        Save a snapshot of the context at a specific point.

        Args:
            snapshot_name: Name for the snapshot (e.g., "after_nova", "after_scout")
            context_data: Context data to snapshot
        """
        self.context_snapshots[snapshot_name] = {
            "timestamp": datetime.utcnow().isoformat(),
            "data": context_data,
        }

        # Save to context directory
        self._save_json(
            self.log_dir / "context" / f"{snapshot_name}.json",
            self.context_snapshots[snapshot_name],
        )

    def log_error(
        self,
        agent: str,
        error: Exception,
        operation: str = "",
        phase: str = "processing",
        retry_count: int = 0,
        max_retries: int = 3,
        recoverable: bool = True,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> ErrorLog:
        """
        Log an error with full stack trace.

        Args:
            agent: Agent where error occurred
            error: The exception
            operation: Operation being performed
            phase: Phase where error occurred
            retry_count: Current retry count
            max_retries: Maximum retries allowed
            recoverable: Whether error is recoverable
            input_data: Input data at time of error

        Returns:
            ErrorLog with details
        """
        error_log = ErrorLog(
            agent=agent,
            operation=operation,
            phase=phase,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            input_data=input_data,
            retry_count=retry_count,
            max_retries=max_retries,
            recoverable=recoverable,
        )

        # Add to current execution
        if self.current_execution:
            self.current_execution.add_error(error_log)

        # Log to master log
        self._add_to_master_log("error", error_log.to_dict())

        # Save to errors directory
        self._save_json(
            self.log_dir / "errors" / f"error_{error_log.error_id}.json",
            error_log.to_dict(),
        )

        if self.verbose:
            print(f"[{agent}] ERROR: {type(error).__name__}: {str(error)}")

        return error_log

    def log_retry(
        self,
        agent: str,
        operation: str,
        retry_count: int,
        reason: str,
        wait_time_ms: int = 0,
    ) -> None:
        """
        Log a retry attempt.

        Args:
            agent: Agent retrying
            operation: Operation being retried
            retry_count: Current retry number
            reason: Reason for retry
            wait_time_ms: Wait time before retry
        """
        self._log_entry(
            LogLevel.WARNING,
            agent,
            operation,
            LogPhase.RETRY,
            f"Retry #{retry_count}: {reason} (waiting {wait_time_ms}ms)",
        )
        self.metrics.total_retries += 1

    def _log_entry(
        self,
        level: LogLevel,
        agent: str,
        operation: str,
        phase: LogPhase,
        message: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> LogEntry:
        """Create and record a log entry."""
        entry = LogEntry(
            level=level,
            agent=agent,
            operation=operation,
            phase=phase,
            message=message,
            input_data=input_data,
            output_data=output_data,
        )

        if self.current_execution:
            self.current_execution.add_entry(entry)

        self._add_to_master_log("entry", entry.to_dict())

        return entry

    def _calculate_cost(self, model: str, usage: TokenUsage) -> CostBreakdown:
        """Calculate cost breakdown for a Claude call."""
        pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-3-5-sonnet-20241022"])

        return CostBreakdown(
            input_cost=(usage.input_tokens / 1_000_000) * pricing["input"],
            output_cost=(usage.output_tokens / 1_000_000) * pricing["output"],
            cache_write_cost=(usage.cache_creation_input_tokens / 1_000_000) * pricing["cache_write"],
            cache_read_cost=(usage.cache_read_input_tokens / 1_000_000) * pricing["cache_read"],
        )

    def _add_to_master_log(self, event_type: str, data: Dict[str, Any]) -> None:
        """Add an entry to the master log."""
        self.master_log.append({
            "sequence": len(self.master_log) + 1,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data,
        })

    def _save_prompt(
        self,
        agent: str,
        call_number: int,
        system_prompt: str,
        messages: List[Dict[str, Any]],
    ) -> None:
        """Save prompt to file."""
        # Save as text for human readability
        prompt_path = self.log_dir / "prompts" / f"{agent.lower()}_call_{call_number}_prompt.txt"
        with open(prompt_path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("SYSTEM PROMPT\n")
            f.write("=" * 80 + "\n")
            f.write(system_prompt)
            f.write("\n\n")
            f.write("=" * 80 + "\n")
            f.write("MESSAGES\n")
            f.write("=" * 80 + "\n")
            for i, msg in enumerate(messages):
                f.write(f"\n--- Message {i + 1} (role: {msg.get('role', 'unknown')}) ---\n")
                content = msg.get("content", "")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            f.write(f"[{item.get('type', 'unknown')}]\n")
                            if item.get("type") == "text":
                                f.write(item.get("text", ""))
                        else:
                            f.write(str(item))
                        f.write("\n")
                else:
                    f.write(str(content))
                f.write("\n")

        # Also save as JSON for programmatic access
        json_path = self.log_dir / "prompts" / f"{agent.lower()}_call_{call_number}_prompt.json"
        self._save_json(json_path, {
            "system_prompt": system_prompt,
            "messages": messages,
        })

    def _save_response(
        self,
        agent: str,
        call_number: int,
        response_content: str,
        call_log: Dict[str, Any],
    ) -> None:
        """Save response to file."""
        # Save response text
        response_path = self.log_dir / "responses" / f"{agent.lower()}_call_{call_number}_response.txt"
        with open(response_path, "w") as f:
            f.write(response_content)

        # Save full call log as JSON
        json_path = self.log_dir / "responses" / f"{agent.lower()}_call_{call_number}_response.json"
        self._save_json(json_path, call_log)

    def _save_agent_logs(self, execution: AgentExecutionLog) -> None:
        """Save agent-specific logs."""
        agent_dir = self.log_dir / "agents" / execution.agent.lower()

        # Save execution summary
        self._save_json(agent_dir / "execution.json", execution.to_dict())

        # Save metrics
        self._save_json(agent_dir / "metrics.json", {
            "api_calls": execution.total_api_calls,
            "input_tokens": execution.total_input_tokens,
            "output_tokens": execution.total_output_tokens,
            "total_tokens": execution.total_tokens,
            "total_cost": execution.total_cost,
            "duration_ms": execution.duration_ms,
            "success": execution.success,
        })

    def _save_json(self, path: Path, data: Any) -> None:
        """Save data as JSON."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive report and save all logs.

        Returns:
            Report data dictionary
        """
        self.metrics.complete()

        # Build report
        report = {
            "run_id": self.run_id,
            "test_name": self.test_name,
            "summary": self.metrics.to_dict(),
            "agent_executions": {
                k: v.to_dict() for k, v in self.agent_executions.items()
            },
            "context_snapshots": self.context_snapshots,
        }

        # Save master log
        self._save_json(self.log_dir / "master_log.json", self.master_log)

        # Save metrics summary
        self._save_json(self.log_dir / "metrics" / "summary.json", self.metrics.to_dict())

        # Save tokens breakdown
        tokens_data = {
            "by_agent": {
                agent: {
                    "input_tokens": exec_log.total_input_tokens,
                    "output_tokens": exec_log.total_output_tokens,
                    "cache_read_tokens": exec_log.total_cache_read_tokens,
                    "total_tokens": exec_log.total_tokens,
                }
                for agent, exec_log in self.agent_executions.items()
            },
            "totals": {
                "input_tokens": self.metrics.total_input_tokens,
                "output_tokens": self.metrics.total_output_tokens,
                "cache_read_tokens": self.metrics.total_cache_read_tokens,
                "total_tokens": self.metrics.total_tokens,
            },
        }
        self._save_json(self.log_dir / "metrics" / "tokens.json", tokens_data)

        # Save timing breakdown
        timing_data = {
            "by_agent": {
                agent: exec_log.duration_ms
                for agent, exec_log in self.agent_executions.items()
            },
            "total_duration_ms": self.metrics.total_duration_ms,
        }
        self._save_json(self.log_dir / "metrics" / "timing.json", timing_data)

        # Save all errors summary
        all_errors = []
        for exec_log in self.agent_executions.values():
            all_errors.extend([e.to_dict() for e in exec_log.errors])
        self._save_json(self.log_dir / "errors" / "errors.json", all_errors)

        # Save retries summary
        self._save_json(self.log_dir / "errors" / "retries.json", {
            "total_retries": self.metrics.total_retries,
        })

        return report

    def get_log_dir(self) -> Path:
        """Get the log directory path."""
        return self.log_dir

    def get_run_id(self) -> str:
        """Get the current run ID."""
        return self.run_id
