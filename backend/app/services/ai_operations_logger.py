"""
AI Operations Logger.

Centralized logging service that tracks ALL AI operations in real-time:
- API calls (Claude, embeddings)
- Prompt cache hits/misses
- Batch processing jobs
- Subagent executions
- Hook decisions
- Session operations
- Token usage and costs

Provides a complete audit trail of what happened during each chat session.
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """Types of AI operations that can be logged."""
    # API Calls
    API_CALL = "api_call"
    API_CALL_START = "api_call_start"
    API_CALL_END = "api_call_end"
    API_ERROR = "api_error"

    # Prompt Cache
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_WRITE = "cache_write"

    # Batch Processing
    BATCH_CREATED = "batch_created"
    BATCH_SUBMITTED = "batch_submitted"
    BATCH_PROGRESS = "batch_progress"
    BATCH_COMPLETED = "batch_completed"
    BATCH_FAILED = "batch_failed"

    # Subagents
    SUBAGENT_START = "subagent_start"
    SUBAGENT_END = "subagent_end"
    SUBAGENT_ERROR = "subagent_error"

    # Hooks
    HOOK_TRIGGERED = "hook_triggered"
    HOOK_ALLOWED = "hook_allowed"
    HOOK_DENIED = "hook_denied"
    HOOK_WARNING = "hook_warning"

    # Sessions
    SESSION_CREATED = "session_created"
    SESSION_RESUMED = "session_resumed"
    SESSION_FORKED = "session_forked"
    SESSION_COMPLETED = "session_completed"

    # Orchestrator
    INTENT_ANALYSIS = "intent_analysis"
    CONTEXT_RETRIEVAL = "context_retrieval"
    PLAN_CREATED = "plan_created"
    EXECUTION_STEP = "execution_step"
    VALIDATION = "validation"

    # Multilingual
    LANGUAGE_DETECTED = "language_detected"
    TRANSLATION = "translation"

    # General
    CHAT_START = "chat_start"
    CHAT_END = "chat_end"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class OperationLog:
    """A single logged operation."""
    id: str
    timestamp: datetime
    operation_type: OperationType
    duration_ms: Optional[int] = None
    success: bool = True

    # Context
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    conversation_id: Optional[str] = None
    request_id: Optional[str] = None

    # Operation details
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0

    # Cache info
    cache_hit: bool = False
    cache_tokens_saved: int = 0
    cache_cost_saved: float = 0.0

    # Details
    message: str = ""
    details: dict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "operation_type": self.operation_type.value,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "conversation_id": self.conversation_id,
            "request_id": self.request_id,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "cache_hit": self.cache_hit,
            "cache_tokens_saved": self.cache_tokens_saved,
            "cache_cost_saved": self.cache_cost_saved,
            "message": self.message,
            "details": self.details,
            "error": self.error,
        }

    def to_log_line(self) -> str:
        """Format as a single log line."""
        parts = [
            f"[{self.timestamp.strftime('%H:%M:%S.%f')[:-3]}]",
            f"[{self.operation_type.value.upper()}]",
        ]

        if self.model:
            parts.append(f"[{self.model}]")

        if self.cache_hit:
            parts.append("[CACHE HIT]")

        parts.append(self.message)

        if self.duration_ms:
            parts.append(f"({self.duration_ms}ms)")

        if self.total_tokens:
            parts.append(f"[{self.total_tokens} tokens]")

        if self.cost > 0:
            parts.append(f"[${self.cost:.6f}]")

        if self.cache_cost_saved > 0:
            parts.append(f"[saved ${self.cache_cost_saved:.6f}]")

        if self.error:
            parts.append(f"ERROR: {self.error}")

        return " ".join(parts)


@dataclass
class ChatSession:
    """Tracks a complete chat session with all operations."""
    id: str
    user_id: str
    project_id: str
    conversation_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    operations: list[OperationLog] = field(default_factory=list)

    # Aggregated stats
    total_api_calls: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_cache_hits: int = 0
    total_cache_misses: int = 0
    total_tokens_saved: int = 0
    total_cost_saved: float = 0.0

    def add_operation(self, op: OperationLog) -> None:
        """Add an operation and update stats."""
        self.operations.append(op)

        if op.operation_type in [OperationType.API_CALL, OperationType.API_CALL_END]:
            self.total_api_calls += 1
            self.total_tokens += op.total_tokens
            self.total_cost += op.cost

        if op.cache_hit:
            self.total_cache_hits += 1
            self.total_tokens_saved += op.cache_tokens_saved
            self.total_cost_saved += op.cache_cost_saved
        elif op.operation_type == OperationType.CACHE_MISS:
            self.total_cache_misses += 1

    def get_summary(self) -> dict:
        """Get session summary."""
        duration = None
        if self.ended_at:
            duration = int((self.ended_at - self.started_at).total_seconds() * 1000)

        return {
            "session_id": self.id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "conversation_id": self.conversation_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": duration,
            "total_operations": len(self.operations),
            "total_api_calls": self.total_api_calls,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "cache_stats": {
                "hits": self.total_cache_hits,
                "misses": self.total_cache_misses,
                "hit_rate": self.total_cache_hits / (self.total_cache_hits + self.total_cache_misses)
                if (self.total_cache_hits + self.total_cache_misses) > 0 else 0,
                "tokens_saved": self.total_tokens_saved,
                "cost_saved": self.total_cost_saved,
            },
            "operations_by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict:
        """Count operations by type."""
        counts = defaultdict(int)
        for op in self.operations:
            counts[op.operation_type.value] += 1
        return dict(counts)

    def to_dict(self) -> dict:
        """Full session data."""
        return {
            **self.get_summary(),
            "operations": [op.to_dict() for op in self.operations],
        }


class AIOperationsLogger:
    """
    Centralized logger for all AI operations.

    Tracks every operation across all AI services and provides:
    - Real-time logging to console/file
    - Session-based aggregation
    - Cost and token tracking
    - Cache hit/miss statistics
    """

    def __init__(
        self,
        log_to_console: bool = True,
        log_to_file: bool = True,
        log_dir: Optional[str] = None,
        log_level: str = "INFO",
        callbacks: Optional[list[Callable[[OperationLog], Any]]] = None,
    ):
        """
        Initialize the operations logger.

        Args:
            log_to_console: Print logs to console
            log_to_file: Write logs to file
            log_dir: Directory for log files
            log_level: Minimum log level
            callbacks: Optional callbacks for each operation
        """
        self.log_to_console = log_to_console
        self.log_to_file = log_to_file
        self.log_dir = Path(log_dir) if log_dir else Path("/tmp/laravelai_ops_logs")
        self.log_level = log_level
        self.callbacks = callbacks or []

        # Active sessions
        self._sessions: dict[str, ChatSession] = {}
        self._current_session_id: Optional[str] = None

        # Global stats
        self._global_stats = {
            "total_operations": 0,
            "total_api_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_cache_hits": 0,
            "total_cost_saved": 0.0,
        }

        # Ensure log directory exists
        if self.log_to_file:
            self.log_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[AI_OPS_LOGGER] Initialized - console={log_to_console}, file={log_to_file}")

    def start_chat_session(
        self,
        user_id: str,
        project_id: str,
        conversation_id: Optional[str] = None,
    ) -> str:
        """
        Start a new chat session for logging.

        Args:
            user_id: User identifier
            project_id: Project identifier
            conversation_id: Optional conversation ID

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        session = ChatSession(
            id=session_id,
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
        )

        self._sessions[session_id] = session
        self._current_session_id = session_id

        self.log(
            operation_type=OperationType.CHAT_START,
            message=f"Chat session started",
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            details={
                "session_id": session_id,
            },
        )

        return session_id

    def end_chat_session(self, session_id: Optional[str] = None) -> Optional[dict]:
        """
        End a chat session and get summary.

        Args:
            session_id: Session to end (uses current if not specified)

        Returns:
            Session summary
        """
        sid = session_id or self._current_session_id
        if not sid or sid not in self._sessions:
            return None

        session = self._sessions[sid]
        session.ended_at = datetime.utcnow()

        self.log(
            operation_type=OperationType.CHAT_END,
            message=f"Chat session ended",
            user_id=session.user_id,
            project_id=session.project_id,
            details=session.get_summary(),
        )

        # Save session log to file
        if self.log_to_file:
            self._save_session_log(session)

        summary = session.get_summary()

        if sid == self._current_session_id:
            self._current_session_id = None

        return summary

    def log(
        self,
        operation_type: OperationType,
        message: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        model: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        cache_hit: bool = False,
        cache_tokens_saved: int = 0,
        cache_cost_saved: float = 0.0,
        duration_ms: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> OperationLog:
        """
        Log an AI operation.

        Args:
            operation_type: Type of operation
            message: Human-readable message
            user_id: User identifier
            project_id: Project identifier
            conversation_id: Conversation identifier
            request_id: Request identifier
            model: AI model used
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            cost: Cost in USD
            cache_hit: Whether cache was hit
            cache_tokens_saved: Tokens saved by cache
            cache_cost_saved: Cost saved by cache
            duration_ms: Operation duration
            success: Whether operation succeeded
            error: Error message if failed
            details: Additional details

        Returns:
            OperationLog entry
        """
        total_tokens = input_tokens + output_tokens

        op = OperationLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            operation_type=operation_type,
            duration_ms=duration_ms,
            success=success,
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            request_id=request_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            cache_hit=cache_hit,
            cache_tokens_saved=cache_tokens_saved,
            cache_cost_saved=cache_cost_saved,
            message=message,
            details=details or {},
            error=error,
        )

        # Add to current session
        if self._current_session_id and self._current_session_id in self._sessions:
            self._sessions[self._current_session_id].add_operation(op)

        # Update global stats
        self._global_stats["total_operations"] += 1
        if operation_type in [OperationType.API_CALL, OperationType.API_CALL_END]:
            self._global_stats["total_api_calls"] += 1
            self._global_stats["total_tokens"] += total_tokens
            self._global_stats["total_cost"] += cost
        if cache_hit:
            self._global_stats["total_cache_hits"] += 1
            self._global_stats["total_cost_saved"] += cache_cost_saved

        # Output log
        if self.log_to_console:
            self._log_to_console(op)

        # Execute callbacks
        for callback in self.callbacks:
            try:
                result = callback(op)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"[AI_OPS_LOGGER] Callback error: {e}")

        return op

    def _log_to_console(self, op: OperationLog) -> None:
        """Output operation to console with formatting."""
        log_line = op.to_log_line()

        # Color coding based on operation type
        colors = {
            OperationType.CACHE_HIT: "\033[92m",      # Green
            OperationType.CACHE_MISS: "\033[93m",    # Yellow
            OperationType.API_CALL_END: "\033[94m",  # Blue
            OperationType.ERROR: "\033[91m",         # Red
            OperationType.HOOK_DENIED: "\033[91m",   # Red
            OperationType.HOOK_WARNING: "\033[93m",  # Yellow
            OperationType.SUBAGENT_END: "\033[95m",  # Magenta
            OperationType.BATCH_COMPLETED: "\033[96m", # Cyan
        }

        reset = "\033[0m"
        color = colors.get(op.operation_type, "")

        print(f"{color}{log_line}{reset}")

    def _save_session_log(self, session: ChatSession) -> None:
        """Save session log to file."""
        try:
            # Create dated directory
            date_dir = self.log_dir / session.started_at.strftime("%Y-%m-%d")
            date_dir.mkdir(parents=True, exist_ok=True)

            # Save JSON log
            log_file = date_dir / f"session_{session.id}.json"
            with open(log_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)

            # Save human-readable log
            txt_file = date_dir / f"session_{session.id}.log"
            with open(txt_file, "w") as f:
                f.write(f"=" * 60 + "\n")
                f.write(f"Chat Session: {session.id}\n")
                f.write(f"User: {session.user_id}\n")
                f.write(f"Project: {session.project_id}\n")
                f.write(f"Started: {session.started_at.isoformat()}\n")
                f.write(f"Ended: {session.ended_at.isoformat() if session.ended_at else 'ongoing'}\n")
                f.write(f"=" * 60 + "\n\n")

                for op in session.operations:
                    f.write(op.to_log_line() + "\n")

                f.write(f"\n" + "=" * 60 + "\n")
                f.write("SUMMARY\n")
                f.write(f"=" * 60 + "\n")
                summary = session.get_summary()
                f.write(f"Total Operations: {summary['total_operations']}\n")
                f.write(f"Total API Calls: {summary['total_api_calls']}\n")
                f.write(f"Total Tokens: {summary['total_tokens']}\n")
                f.write(f"Total Cost: ${summary['total_cost']:.6f}\n")
                f.write(f"Cache Hits: {summary['cache_stats']['hits']}\n")
                f.write(f"Cache Hit Rate: {summary['cache_stats']['hit_rate']:.1%}\n")
                f.write(f"Cost Saved: ${summary['cache_stats']['cost_saved']:.6f}\n")

            logger.info(f"[AI_OPS_LOGGER] Session log saved: {log_file}")

        except Exception as e:
            logger.error(f"[AI_OPS_LOGGER] Failed to save session log: {e}")

    # Convenience methods for common operations

    def log_api_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        duration_ms: int,
        cache_hit: bool = False,
        cache_tokens_saved: int = 0,
        cache_cost_saved: float = 0.0,
        request_type: str = "chat",
        **kwargs,
    ) -> OperationLog:
        """Log an API call to Claude."""
        return self.log(
            operation_type=OperationType.API_CALL_END,
            message=f"API call to {model} ({request_type})",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            duration_ms=duration_ms,
            cache_hit=cache_hit,
            cache_tokens_saved=cache_tokens_saved,
            cache_cost_saved=cache_cost_saved,
            details={"request_type": request_type},
            **kwargs,
        )

    def log_cache_hit(
        self,
        tokens_saved: int,
        cost_saved: float,
        **kwargs,
    ) -> OperationLog:
        """Log a prompt cache hit."""
        return self.log(
            operation_type=OperationType.CACHE_HIT,
            message=f"Prompt cache HIT - saved {tokens_saved} tokens (${cost_saved:.6f})",
            cache_hit=True,
            cache_tokens_saved=tokens_saved,
            cache_cost_saved=cost_saved,
            **kwargs,
        )

    def log_cache_miss(self, **kwargs) -> OperationLog:
        """Log a prompt cache miss."""
        return self.log(
            operation_type=OperationType.CACHE_MISS,
            message="Prompt cache MISS - building new cache",
            cache_hit=False,
            **kwargs,
        )

    def log_batch_operation(
        self,
        operation: str,
        batch_id: str,
        total_requests: int,
        completed: int = 0,
        failed: int = 0,
        **kwargs,
    ) -> OperationLog:
        """Log batch processing operation."""
        op_type_map = {
            "created": OperationType.BATCH_CREATED,
            "submitted": OperationType.BATCH_SUBMITTED,
            "progress": OperationType.BATCH_PROGRESS,
            "completed": OperationType.BATCH_COMPLETED,
            "failed": OperationType.BATCH_FAILED,
        }

        return self.log(
            operation_type=op_type_map.get(operation, OperationType.BATCH_PROGRESS),
            message=f"Batch {operation}: {batch_id[:8]}... ({completed}/{total_requests} done, {failed} failed)",
            details={
                "batch_id": batch_id,
                "total_requests": total_requests,
                "completed": completed,
                "failed": failed,
            },
            **kwargs,
        )

    def log_subagent(
        self,
        agent_type: str,
        action: str,  # "start" or "end"
        tokens: int = 0,
        cost: float = 0.0,
        duration_ms: int = 0,
        cache_hit: bool = False,
        **kwargs,
    ) -> OperationLog:
        """Log subagent execution."""
        op_type = OperationType.SUBAGENT_START if action == "start" else OperationType.SUBAGENT_END

        return self.log(
            operation_type=op_type,
            message=f"Subagent {agent_type} {action}",
            total_tokens=tokens,
            cost=cost,
            duration_ms=duration_ms if action == "end" else None,
            cache_hit=cache_hit,
            details={"agent_type": agent_type},
            **kwargs,
        )

    def log_hook_decision(
        self,
        hook_name: str,
        event: str,
        decision: str,
        reason: Optional[str] = None,
        **kwargs,
    ) -> OperationLog:
        """Log hook decision."""
        op_type_map = {
            "allow": OperationType.HOOK_ALLOWED,
            "deny": OperationType.HOOK_DENIED,
            "warn": OperationType.HOOK_WARNING,
        }

        return self.log(
            operation_type=op_type_map.get(decision, OperationType.HOOK_TRIGGERED),
            message=f"Hook '{hook_name}' on {event}: {decision}" + (f" - {reason}" if reason else ""),
            success=decision != "deny",
            details={
                "hook_name": hook_name,
                "event": event,
                "decision": decision,
                "reason": reason,
            },
            **kwargs,
        )

    def log_intent_analysis(
        self,
        task_type: str,
        confidence: float,
        domains: list[str],
        tokens: int = 0,
        duration_ms: int = 0,
        **kwargs,
    ) -> OperationLog:
        """Log intent analysis result."""
        return self.log(
            operation_type=OperationType.INTENT_ANALYSIS,
            message=f"Intent: {task_type} (confidence: {confidence:.0%}) - domains: {', '.join(domains)}",
            total_tokens=tokens,
            duration_ms=duration_ms,
            details={
                "task_type": task_type,
                "confidence": confidence,
                "domains": domains,
            },
            **kwargs,
        )

    def log_plan_created(
        self,
        steps_count: int,
        complexity: str,
        tokens: int = 0,
        duration_ms: int = 0,
        **kwargs,
    ) -> OperationLog:
        """Log plan creation."""
        return self.log(
            operation_type=OperationType.PLAN_CREATED,
            message=f"Plan created: {steps_count} steps ({complexity} complexity)",
            total_tokens=tokens,
            duration_ms=duration_ms,
            details={
                "steps_count": steps_count,
                "complexity": complexity,
            },
            **kwargs,
        )

    def log_execution_step(
        self,
        step_number: int,
        total_steps: int,
        file_path: str,
        action: str,
        tokens: int = 0,
        duration_ms: int = 0,
        **kwargs,
    ) -> OperationLog:
        """Log execution step."""
        return self.log(
            operation_type=OperationType.EXECUTION_STEP,
            message=f"Step {step_number}/{total_steps}: {action} {file_path}",
            total_tokens=tokens,
            duration_ms=duration_ms,
            details={
                "step_number": step_number,
                "total_steps": total_steps,
                "file_path": file_path,
                "action": action,
            },
            **kwargs,
        )

    def log_validation(
        self,
        approved: bool,
        score: int,
        errors_count: int,
        tokens: int = 0,
        duration_ms: int = 0,
        **kwargs,
    ) -> OperationLog:
        """Log validation result."""
        status = "APPROVED" if approved else f"NEEDS FIXES ({errors_count} issues)"

        return self.log(
            operation_type=OperationType.VALIDATION,
            message=f"Validation: {status} - Score: {score}/100",
            success=approved,
            total_tokens=tokens,
            duration_ms=duration_ms,
            details={
                "approved": approved,
                "score": score,
                "errors_count": errors_count,
            },
            **kwargs,
        )

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_current_session(self) -> Optional[ChatSession]:
        """Get the current active session."""
        if self._current_session_id:
            return self._sessions.get(self._current_session_id)
        return None

    def get_global_stats(self) -> dict:
        """Get global statistics."""
        return {
            **self._global_stats,
            "active_sessions": len([s for s in self._sessions.values() if s.ended_at is None]),
            "total_sessions": len(self._sessions),
        }

    def get_recent_operations(self, limit: int = 50) -> list[dict]:
        """Get recent operations across all sessions."""
        all_ops = []
        for session in self._sessions.values():
            all_ops.extend(session.operations)

        # Sort by timestamp descending
        all_ops.sort(key=lambda x: x.timestamp, reverse=True)

        return [op.to_dict() for op in all_ops[:limit]]


# Global instance
_operations_logger: Optional[AIOperationsLogger] = None


def get_operations_logger() -> AIOperationsLogger:
    """Get the global operations logger instance."""
    global _operations_logger
    if _operations_logger is None:
        _operations_logger = AIOperationsLogger()
    return _operations_logger


def init_operations_logger(
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_dir: Optional[str] = None,
) -> AIOperationsLogger:
    """Initialize the global operations logger with custom settings."""
    global _operations_logger
    _operations_logger = AIOperationsLogger(
        log_to_console=log_to_console,
        log_to_file=log_to_file,
        log_dir=log_dir,
    )
    return _operations_logger
