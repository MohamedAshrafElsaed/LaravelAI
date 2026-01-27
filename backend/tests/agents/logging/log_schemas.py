"""
Log schemas for exhaustive agent logging.

Defines dataclasses for structured logging of all operations
during multi-agent test execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AgentName(str, Enum):
    """Agent identifiers."""
    NOVA = "NOVA"
    SCOUT = "SCOUT"
    BLUEPRINT = "BLUEPRINT"
    FORGE = "FORGE"
    GUARDIAN = "GUARDIAN"
    PALETTE = "PALETTE"
    CONDUCTOR = "CONDUCTOR"


class LogPhase(str, Enum):
    """Execution phases within an operation."""
    INPUT = "input"
    PROCESSING = "processing"
    OUTPUT = "output"
    ERROR = "error"
    RETRY = "retry"


@dataclass
class TokenUsage:
    """Token usage metrics from Claude API call."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def total_input_with_cache(self) -> int:
        """Total input tokens including cache."""
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "total_tokens": self.total_tokens,
            "total_input_with_cache": self.total_input_with_cache,
        }


@dataclass
class CostBreakdown:
    """Cost breakdown for API calls."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_write_cost: float = 0.0
    cache_read_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        """Total cost."""
        return self.input_cost + self.output_cost + self.cache_write_cost + self.cache_read_cost

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "cache_write_cost": self.cache_write_cost,
            "cache_read_cost": self.cache_read_cost,
            "total_cost": self.total_cost,
        }


@dataclass
class ClaudeCallLog:
    """Complete log of a Claude API call."""
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent: str = ""
    operation: str = ""
    model: str = ""

    # Request details
    system_prompt: str = ""
    system_prompt_length: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    messages_count: int = 0
    total_message_chars: int = 0

    # Response details
    response_content: str = ""
    response_length: int = 0
    stop_reason: Optional[str] = None

    # Metrics
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    latency_ms: int = 0

    # Error handling
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "operation": self.operation,
            "model": self.model,
            "request": {
                "system_prompt": self.system_prompt,
                "system_prompt_length": self.system_prompt_length,
                "messages": self.messages,
                "messages_count": self.messages_count,
                "total_message_chars": self.total_message_chars,
            },
            "response": {
                "content": self.response_content,
                "length": self.response_length,
                "stop_reason": self.stop_reason,
            },
            "metrics": {
                "token_usage": self.token_usage.to_dict(),
                "cost": self.cost.to_dict(),
                "latency_ms": self.latency_ms,
            },
            "error": self.error,
            "retry_count": self.retry_count,
        }


@dataclass
class ContextRetrievalLog:
    """Log of context retrieval operations."""
    retrieval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent: str = "SCOUT"

    # Search details
    search_queries: List[str] = field(default_factory=list)
    query_embeddings_generated: int = 0

    # Results
    chunks_found: int = 0
    chunks_used: int = 0
    total_chunk_tokens: int = 0

    # File paths accessed
    file_paths: List[str] = field(default_factory=list)
    unique_files: int = 0

    # Relevance scores
    scores: List[float] = field(default_factory=list)
    avg_score: float = 0.0
    max_score: float = 0.0
    min_score: float = 0.0

    # Timing
    embedding_latency_ms: int = 0
    search_latency_ms: int = 0
    total_latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "retrieval_id": self.retrieval_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "search": {
                "queries": self.search_queries,
                "query_embeddings_generated": self.query_embeddings_generated,
            },
            "results": {
                "chunks_found": self.chunks_found,
                "chunks_used": self.chunks_used,
                "total_chunk_tokens": self.total_chunk_tokens,
            },
            "files": {
                "paths": self.file_paths,
                "unique_count": self.unique_files,
            },
            "scores": {
                "values": self.scores,
                "avg": self.avg_score,
                "max": self.max_score,
                "min": self.min_score,
            },
            "timing": {
                "embedding_latency_ms": self.embedding_latency_ms,
                "search_latency_ms": self.search_latency_ms,
                "total_latency_ms": self.total_latency_ms,
            },
        }


@dataclass
class FileAccessLog:
    """Log of file access operations."""
    access_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent: str = ""
    operation: str = ""  # read, write, search, list

    # File details
    file_path: str = ""
    file_type: str = ""
    file_size_bytes: int = 0

    # Content (for reads/writes)
    content_preview: str = ""  # First N chars
    content_length: int = 0
    line_count: int = 0

    # Search details (for search operations)
    search_pattern: Optional[str] = None
    matches_found: int = 0

    # Timing
    latency_ms: int = 0

    # Error
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_id": self.access_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "operation": self.operation,
            "file": {
                "path": self.file_path,
                "type": self.file_type,
                "size_bytes": self.file_size_bytes,
            },
            "content": {
                "preview": self.content_preview,
                "length": self.content_length,
                "line_count": self.line_count,
            },
            "search": {
                "pattern": self.search_pattern,
                "matches_found": self.matches_found,
            } if self.search_pattern else None,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


@dataclass
class ErrorLog:
    """Log of errors and exceptions."""
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent: str = ""
    operation: str = ""
    phase: str = ""

    # Error details
    error_type: str = ""
    error_message: str = ""
    stack_trace: Optional[str] = None

    # Context
    input_data: Optional[Dict[str, Any]] = None

    # Recovery
    retry_count: int = 0
    max_retries: int = 0
    recoverable: bool = False
    recovered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "operation": self.operation,
            "phase": self.phase,
            "error": {
                "type": self.error_type,
                "message": self.error_message,
                "stack_trace": self.stack_trace,
            },
            "context": {
                "input_data": self.input_data,
            },
            "recovery": {
                "retry_count": self.retry_count,
                "max_retries": self.max_retries,
                "recoverable": self.recoverable,
                "recovered": self.recovered,
            },
        }


@dataclass
class LogEntry:
    """Generic log entry for any operation."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: LogLevel = LogLevel.INFO
    agent: str = ""
    operation: str = ""
    phase: LogPhase = LogPhase.PROCESSING

    # Optional model info (for Claude calls)
    model: Optional[str] = None

    # Token metrics (if applicable)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost: float = 0.0

    # Timing
    latency_ms: int = 0

    # Data
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None

    # Error info (if applicable)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None

    # Request tracking
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Message for human-readable logs
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "agent": self.agent,
            "operation": self.operation,
            "phase": self.phase.value,
            "model": self.model,
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "cache_read": self.cache_read_tokens,
            },
            "cost": self.total_cost,
            "latency_ms": self.latency_ms,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": {
                "type": self.error_type,
                "message": self.error_message,
                "stack_trace": self.stack_trace,
            } if self.error_type else None,
            "request_id": self.request_id,
            "message": self.message,
        }


@dataclass
class AgentExecutionLog:
    """Complete execution log for a single agent."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent: str = ""
    operation: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # All log entries
    entries: List[LogEntry] = field(default_factory=list)

    # Claude API calls
    claude_calls: List[ClaudeCallLog] = field(default_factory=list)

    # Context retrievals (mainly for SCOUT)
    context_retrievals: List[ContextRetrievalLog] = field(default_factory=list)

    # File accesses
    file_accesses: List[FileAccessLog] = field(default_factory=list)

    # Errors
    errors: List[ErrorLog] = field(default_factory=list)

    # Aggregated metrics
    total_api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: int = 0

    # Status
    success: bool = True
    final_output: Optional[Any] = None

    @property
    def duration_ms(self) -> int:
        """Get execution duration in milliseconds."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return 0

    def add_entry(self, entry: LogEntry) -> None:
        """Add a log entry."""
        self.entries.append(entry)

    def add_claude_call(self, call: ClaudeCallLog) -> None:
        """Add a Claude API call log and update metrics."""
        self.claude_calls.append(call)
        self.total_api_calls += 1
        self.total_input_tokens += call.token_usage.input_tokens
        self.total_output_tokens += call.token_usage.output_tokens
        self.total_cache_read_tokens += call.token_usage.cache_read_input_tokens
        self.total_tokens += call.token_usage.total_tokens
        self.total_cost += call.cost.total_cost
        self.total_latency_ms += call.latency_ms

    def add_context_retrieval(self, retrieval: ContextRetrievalLog) -> None:
        """Add a context retrieval log."""
        self.context_retrievals.append(retrieval)

    def add_file_access(self, access: FileAccessLog) -> None:
        """Add a file access log."""
        self.file_accesses.append(access)

    def add_error(self, error: ErrorLog) -> None:
        """Add an error log."""
        self.errors.append(error)
        if not error.recovered:
            self.success = False

    def complete(self, output: Any = None) -> None:
        """Mark execution as complete."""
        self.completed_at = datetime.utcnow()
        self.final_output = output

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "agent": self.agent,
            "operation": self.operation,
            "timing": {
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "duration_ms": self.duration_ms,
            },
            "metrics": {
                "total_api_calls": self.total_api_calls,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cache_read_tokens": self.total_cache_read_tokens,
                "total_tokens": self.total_tokens,
                "total_cost": self.total_cost,
                "total_latency_ms": self.total_latency_ms,
            },
            "success": self.success,
            "entries_count": len(self.entries),
            "claude_calls_count": len(self.claude_calls),
            "context_retrievals_count": len(self.context_retrievals),
            "file_accesses_count": len(self.file_accesses),
            "errors_count": len(self.errors),
            "entries": [e.to_dict() for e in self.entries],
            "claude_calls": [c.to_dict() for c in self.claude_calls],
            "context_retrievals": [r.to_dict() for r in self.context_retrievals],
            "file_accesses": [f.to_dict() for f in self.file_accesses],
            "errors": [e.to_dict() for e in self.errors],
            "final_output": self._serialize_output(self.final_output),
        }

    def _serialize_output(self, output: Any) -> Any:
        """Serialize output for JSON."""
        if output is None:
            return None
        if hasattr(output, "to_dict"):
            return output.to_dict()
        if hasattr(output, "__dict__"):
            return {k: str(v) for k, v in output.__dict__.items() if not k.startswith("_")}
        return str(output)


@dataclass
class MetricsSummary:
    """Summary metrics for a complete test run."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    test_name: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Per-agent metrics
    agent_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Totals
    total_agents_executed: int = 0
    total_api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_duration_ms: int = 0

    # Success tracking
    agents_succeeded: int = 0
    agents_failed: int = 0
    total_errors: int = 0
    total_retries: int = 0

    # Context tracking
    total_chunks_retrieved: int = 0
    total_files_accessed: int = 0

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_agents_executed == 0:
            return 0.0
        return (self.agents_succeeded / self.total_agents_executed) * 100

    def add_agent_execution(self, execution: AgentExecutionLog) -> None:
        """Add metrics from an agent execution."""
        self.total_agents_executed += 1
        self.total_api_calls += execution.total_api_calls
        self.total_input_tokens += execution.total_input_tokens
        self.total_output_tokens += execution.total_output_tokens
        self.total_cache_read_tokens += execution.total_cache_read_tokens
        self.total_tokens += execution.total_tokens
        self.total_cost += execution.total_cost
        self.total_duration_ms += execution.duration_ms

        if execution.success:
            self.agents_succeeded += 1
        else:
            self.agents_failed += 1

        self.total_errors += len(execution.errors)
        self.total_chunks_retrieved += sum(
            r.chunks_used for r in execution.context_retrievals
        )
        self.total_files_accessed += len(execution.file_accesses)

        # Store per-agent metrics
        self.agent_metrics[execution.agent] = {
            "operation": execution.operation,
            "duration_ms": execution.duration_ms,
            "api_calls": execution.total_api_calls,
            "input_tokens": execution.total_input_tokens,
            "output_tokens": execution.total_output_tokens,
            "cost": execution.total_cost,
            "success": execution.success,
            "errors": len(execution.errors),
        }

    def complete(self) -> None:
        """Mark the run as complete."""
        self.completed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "test_name": self.test_name,
            "timing": {
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "total_duration_ms": self.total_duration_ms,
            },
            "agents": {
                "total_executed": self.total_agents_executed,
                "succeeded": self.agents_succeeded,
                "failed": self.agents_failed,
                "success_rate": self.success_rate,
                "per_agent": self.agent_metrics,
            },
            "tokens": {
                "total_input": self.total_input_tokens,
                "total_output": self.total_output_tokens,
                "total_cache_read": self.total_cache_read_tokens,
                "total": self.total_tokens,
            },
            "cost": {
                "total": self.total_cost,
            },
            "api_calls": {
                "total": self.total_api_calls,
            },
            "errors": {
                "total": self.total_errors,
                "total_retries": self.total_retries,
            },
            "context": {
                "total_chunks_retrieved": self.total_chunks_retrieved,
                "total_files_accessed": self.total_files_accessed,
            },
        }
