"""
SSE Event System for Multi-Agent Chat Experience.

Defines all event types for real-time communication with the frontend,
including agent messages, thinking states, planning, execution, and validation.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class EventType(str, Enum):
    """SSE event type constants."""

    # Connection Events
    CONNECTED = "connected"
    COMPLETE = "complete"
    ERROR = "error"

    # Agent Communication Events
    AGENT_THINKING = "agent_thinking"  # Agent is thinking/processing
    AGENT_MESSAGE = "agent_message"  # Agent sends a message
    AGENT_HANDOFF = "agent_handoff"  # Agent hands off to another
    AGENT_STATE_CHANGE = "agent_state_change"  # Agent becomes active/inactive

    # Intent Analysis (Nova)
    INTENT_STARTED = "intent_started"  # Nova starts analyzing
    INTENT_THINKING = "intent_thinking"  # Nova's thinking process
    INTENT_ANALYZED = "intent_analyzed"  # Analysis complete

    # Context Retrieval (Scout)
    CONTEXT_STARTED = "context_started"  # Scout starts searching
    CONTEXT_THINKING = "context_thinking"  # Scout's search progress
    CONTEXT_CHUNK_FOUND = "context_chunk_found"  # Found a relevant chunk
    CONTEXT_RETRIEVED = "context_retrieved"  # Context retrieval complete

    # Planning (Blueprint)
    PLANNING_STARTED = "planning_started"  # Blueprint starts planning
    PLANNING_THINKING = "planning_thinking"  # Blueprint's thinking process
    PLAN_STEP_ADDED = "plan_step_added"  # A step was added to the plan
    PLAN_READY = "plan_ready"  # Plan complete, awaiting approval
    PLAN_APPROVED = "plan_approved"  # User approved the plan
    PLAN_MODIFIED = "plan_modified"  # User modified the plan
    PLAN_REJECTED = "plan_rejected"  # User rejected, regenerating
    PLAN_CREATED = "plan_created"  # Legacy - plan was created

    # Execution (Forge)
    EXECUTION_STARTED = "execution_started"  # Forge starts executing
    STEP_STARTED = "step_started"  # A step begins execution
    STEP_THINKING = "step_thinking"  # Forge's thinking for current step
    STEP_CODE_CHUNK = "step_code_chunk"  # Code being generated (streaming)
    STEP_PROGRESS = "step_progress"  # Step progress update
    STEP_COMPLETED = "step_completed"  # A step finished
    EXECUTION_COMPLETED = "execution_completed"  # All steps done

    # Validation (Guardian)
    VALIDATION_STARTED = "validation_started"  # Guardian starts validating
    VALIDATION_THINKING = "validation_thinking"  # Guardian's checking process
    VALIDATION_ISSUE_FOUND = "validation_issue_found"  # Found an issue
    VALIDATION_FIX_STARTED = "validation_fix_started"  # Starting auto-fix
    VALIDATION_FIX_COMPLETED = "validation_fix_completed"  # Fix completed
    VALIDATION_RESULT = "validation_result"  # Final validation result

    # Answer Streaming (for questions)
    ANSWER_CHUNK = "answer_chunk"  # Streaming text response
    ANSWER_COMPLETE = "answer_complete"  # Answer finished

    # Progress Events
    PROGRESS_UPDATE = "progress_update"  # General progress update


@dataclass
class SSEEvent:
    """Server-Sent Event structure for the frontend."""
    event: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_sse(self) -> str:
        """Format as SSE string for streaming."""
        data_with_timestamp = {
            **self.data,
            "timestamp": self.timestamp.isoformat(),
        }
        return f"event: {self.event.value}\ndata: {json.dumps(data_with_timestamp)}\n\n"


# ============== Event Builder Functions ==============

def create_sse_event(event_type: str, data: dict) -> str:
    """Create an SSE formatted event string."""
    data_with_timestamp = {
        **data,
        "timestamp": datetime.now().isoformat(),
    }
    return f"event: {event_type}\ndata: {json.dumps(data_with_timestamp)}\n\n"


# --- Agent Events ---

def agent_thinking(
        agent_type: str,
        agent_name: str,
        thought: str,
        action_type: Optional[str] = None,
        file_path: Optional[str] = None,
        step_index: Optional[int] = None,
        progress: float = 0.0,
) -> str:
    """Create agent thinking event."""
    return create_sse_event(EventType.AGENT_THINKING.value, {
        "agent": agent_type,
        "agent_name": agent_name,
        "thought": thought,
        "action_type": action_type,
        "file_path": file_path,
        "step_index": step_index,
        "progress": progress,
    })


def agent_message(
        from_agent: str,
        from_name: str,
        message: str,
        message_type: str = "custom",
        to_agent: Optional[str] = None,
        to_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Create agent message event."""
    return create_sse_event(EventType.AGENT_MESSAGE.value, {
        "from_agent": from_agent,
        "from_name": from_name,
        "message": message,
        "message_type": message_type,
        "to_agent": to_agent,
        "to_name": to_name,
        "metadata": metadata or {},
    })


def agent_handoff(
        from_agent: str,
        from_name: str,
        to_agent: str,
        to_name: str,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
) -> str:
    """Create agent handoff event."""
    return create_sse_event(EventType.AGENT_HANDOFF.value, {
        "from_agent": from_agent,
        "from_name": from_name,
        "to_agent": to_agent,
        "to_name": to_name,
        "message": message,
        "context": context or {},
    })


def agent_state_change(
        agent_type: str,
        agent_name: str,
        state: str,  # "active", "idle", "waiting"
        metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Create agent state change event."""
    return create_sse_event(EventType.AGENT_STATE_CHANGE.value, {
        "agent": agent_type,
        "agent_name": agent_name,
        "state": state,
        "metadata": metadata or {},
    })


# --- Intent Analysis Events (Nova) ---

def intent_started(message: str = "Analyzing your request...") -> str:
    """Nova starts analyzing."""
    return create_sse_event(EventType.INTENT_STARTED.value, {
        "message": message,
        "agent": "nova",
        "agent_name": "Nova",
    })


def intent_thinking(thought: str, progress: float = 0.0) -> str:
    """Nova's thinking process."""
    return create_sse_event(EventType.INTENT_THINKING.value, {
        "thought": thought,
        "progress": progress,
        "agent": "nova",
        "agent_name": "Nova",
    })


def intent_analyzed(
        intent_data: Dict[str, Any],
        message: str = "Intent analysis complete",
        progress: float = 0.2,
) -> str:
    """Intent analysis complete."""
    return create_sse_event(EventType.INTENT_ANALYZED.value, {
        "message": message,
        "intent": intent_data,
        "progress": progress,
        "agent": "nova",
        "agent_name": "Nova",
    })


# --- Context Retrieval Events (Scout) ---

def context_started(message: str = "Searching the codebase...") -> str:
    """Scout starts searching."""
    return create_sse_event(EventType.CONTEXT_STARTED.value, {
        "message": message,
        "agent": "scout",
        "agent_name": "Scout",
    })


def context_thinking(thought: str, progress: float = 0.0) -> str:
    """Scout's search progress."""
    return create_sse_event(EventType.CONTEXT_THINKING.value, {
        "thought": thought,
        "progress": progress,
        "agent": "scout",
        "agent_name": "Scout",
    })


def context_chunk_found(
        file_path: str,
        chunk_type: str,
        score: float,
        preview: Optional[str] = None,
) -> str:
    """Found a relevant chunk."""
    return create_sse_event(EventType.CONTEXT_CHUNK_FOUND.value, {
        "file_path": file_path,
        "chunk_type": chunk_type,
        "score": score,
        "preview": preview,
        "agent": "scout",
        "agent_name": "Scout",
    })


def context_retrieved(
        chunks_count: int,
        confidence_level: str,
        message: str = "Context retrieval complete",
        progress: float = 0.3,
        context_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Context retrieval complete."""
    return create_sse_event(EventType.CONTEXT_RETRIEVED.value, {
        "message": message,
        "chunks_count": chunks_count,
        "confidence_level": confidence_level,
        "progress": progress,
        "context": context_data,
        "agent": "scout",
        "agent_name": "Scout",
    })


# --- Planning Events (Blueprint) ---

def planning_started(message: str = "Creating implementation plan...") -> str:
    """Blueprint starts planning."""
    return create_sse_event(EventType.PLANNING_STARTED.value, {
        "message": message,
        "agent": "blueprint",
        "agent_name": "Blueprint",
    })


def planning_thinking(thought: str, progress: float = 0.0) -> str:
    """Blueprint's thinking process."""
    return create_sse_event(EventType.PLANNING_THINKING.value, {
        "thought": thought,
        "progress": progress,
        "agent": "blueprint",
        "agent_name": "Blueprint",
    })


def plan_step_added(
        step_index: int,
        step_data: Dict[str, Any],
        total_steps: int = 0,
) -> str:
    """A step was added to the plan."""
    return create_sse_event(EventType.PLAN_STEP_ADDED.value, {
        "step_index": step_index,
        "step": step_data,
        "total_steps": total_steps,
        "agent": "blueprint",
        "agent_name": "Blueprint",
    })


def plan_ready(
        plan_data: Dict[str, Any],
        message: str = "Plan ready for review",
        awaiting_approval: bool = True,
) -> str:
    """Plan complete, awaiting approval."""
    return create_sse_event(EventType.PLAN_READY.value, {
        "message": message,
        "plan": plan_data,
        "awaiting_approval": awaiting_approval,
        "agent": "blueprint",
        "agent_name": "Blueprint",
    })


def plan_approved(plan_data: Optional[Dict[str, Any]] = None) -> str:
    """User approved the plan."""
    return create_sse_event(EventType.PLAN_APPROVED.value, {
        "message": "Plan approved, starting execution",
        "plan": plan_data,
    })


def plan_modified(plan_data: Dict[str, Any]) -> str:
    """User modified the plan."""
    return create_sse_event(EventType.PLAN_MODIFIED.value, {
        "message": "Plan modified by user",
        "plan": plan_data,
    })


def plan_rejected(reason: Optional[str] = None) -> str:
    """User rejected, regenerating."""
    return create_sse_event(EventType.PLAN_REJECTED.value, {
        "message": "Plan rejected, regenerating",
        "reason": reason,
    })


def plan_created(
        plan_data: Dict[str, Any],
        message: str = "Plan created",
        progress: float = 0.4,
) -> str:
    """Legacy plan created event."""
    return create_sse_event(EventType.PLAN_CREATED.value, {
        "message": message,
        "plan": plan_data,
        "progress": progress,
        "agent": "blueprint",
        "agent_name": "Blueprint",
    })


# --- Execution Events (Forge) ---

def execution_started(
        total_steps: int,
        message: str = "Starting code execution...",
) -> str:
    """Forge starts executing."""
    return create_sse_event(EventType.EXECUTION_STARTED.value, {
        "message": message,
        "total_steps": total_steps,
        "agent": "forge",
        "agent_name": "Forge",
    })


def step_started(
        step_index: int,
        step_data: Dict[str, Any],
        message: str = "Starting step...",
        fixing: bool = False,
) -> str:
    """A step begins execution."""
    return create_sse_event(EventType.STEP_STARTED.value, {
        "message": message,
        "step_index": step_index,
        "step": step_data,
        "fixing": fixing,
        "agent": "forge",
        "agent_name": "Forge",
    })


def step_thinking(
        step_index: int,
        thought: str,
        action_type: Optional[str] = None,
        file_path: Optional[str] = None,
        progress: float = 0.0,
) -> str:
    """Forge's thinking for current step."""
    return create_sse_event(EventType.STEP_THINKING.value, {
        "step_index": step_index,
        "thought": thought,
        "action_type": action_type,
        "file_path": file_path,
        "progress": progress,
        "agent": "forge",
        "agent_name": "Forge",
    })


def step_code_chunk(
        step_index: int,
        file_path: str,
        chunk: str,
        accumulated_length: int,
        total_length: int,
        done: bool,
        action: str = "create",
        content: Optional[str] = None,
) -> str:
    """
    Emit a code chunk during step execution for real-time streaming.

    Args:
        step_index: Index of the current step
        file_path: Path of the file being generated
        chunk: The current chunk of code (empty if done=True)
        accumulated_length: Total characters accumulated so far
        total_length: Total expected length
        done: Whether this is the final chunk
        action: Action type (create, modify, delete)
        content: Full content (only sent when done=True)
    """
    data = {
        "step_index": step_index,
        "file": file_path,
        "chunk": chunk,
        "accumulated_length": accumulated_length,
        "total_length": total_length,
        "done": done,
        "action": action,
        "progress": accumulated_length / total_length if total_length > 0 else 1.0,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if done and content:
        data["content"] = content

    return create_sse_event(EventType.STEP_CODE_CHUNK, data)


def step_progress(
        step_index: int,
        progress: float,
        message: Optional[str] = None,
) -> str:
    """Step progress update."""
    return create_sse_event(EventType.STEP_PROGRESS.value, {
        "step_index": step_index,
        "progress": progress,
        "message": message,
        "agent": "forge",
        "agent_name": "Forge",
    })


def step_completed(
        step_index: int,
        step_data: Dict[str, Any],
        result: Dict[str, Any],
        message: str = "Step completed",
        progress: float = 0.0,
) -> str:
    """A step finished."""
    return create_sse_event(EventType.STEP_COMPLETED.value, {
        "message": message,
        "step_index": step_index,
        "step": step_data,
        "result": result,
        "progress": progress,
        "agent": "forge",
        "agent_name": "Forge",
    })


def execution_completed(
        total_steps: int,
        successful_steps: int,
        message: str = "Execution complete",
) -> str:
    """All steps done."""
    return create_sse_event(EventType.EXECUTION_COMPLETED.value, {
        "message": message,
        "total_steps": total_steps,
        "successful_steps": successful_steps,
        "agent": "forge",
        "agent_name": "Forge",
    })


# --- Validation Events (Guardian) ---

def validation_started(message: str = "Starting validation...") -> str:
    """Guardian starts validating."""
    return create_sse_event(EventType.VALIDATION_STARTED.value, {
        "message": message,
        "agent": "guardian",
        "agent_name": "Guardian",
    })


def validation_thinking(thought: str, progress: float = 0.0) -> str:
    """Guardian's checking process."""
    return create_sse_event(EventType.VALIDATION_THINKING.value, {
        "thought": thought,
        "progress": progress,
        "agent": "guardian",
        "agent_name": "Guardian",
    })


def validation_issue_found(
        severity: str,  # "error", "warning", "info"
        file: str,
        message: str,
        line: Optional[int] = None,
        suggestion: Optional[str] = None,
) -> str:
    """Found an issue."""
    return create_sse_event(EventType.VALIDATION_ISSUE_FOUND.value, {
        "issue": {
            "severity": severity,
            "file": file,
            "message": message,
            "line": line,
            "suggestion": suggestion,
        },
        "agent": "guardian",
        "agent_name": "Guardian",
    })


def validation_fix_started(
        issues_count: int,
        message: str = "Starting auto-fix...",
) -> str:
    """Starting auto-fix."""
    return create_sse_event(EventType.VALIDATION_FIX_STARTED.value, {
        "message": message,
        "issues_count": issues_count,
        "agent": "guardian",
        "agent_name": "Guardian",
    })


def validation_fix_completed(
        fixed_count: int,
        remaining_count: int,
        message: str = "Fix attempt completed",
) -> str:
    """Fix completed."""
    return create_sse_event(EventType.VALIDATION_FIX_COMPLETED.value, {
        "message": message,
        "fixed_count": fixed_count,
        "remaining_count": remaining_count,
        "agent": "guardian",
        "agent_name": "Guardian",
    })


def validation_result(
        validation_data: Dict[str, Any],
        message: str = "Validation complete",
        progress: float = 0.9,
) -> str:
    """Final validation result."""
    return create_sse_event(EventType.VALIDATION_RESULT.value, {
        "message": message,
        "validation": validation_data,
        "progress": progress,
        "agent": "guardian",
        "agent_name": "Guardian",
    })


# --- Answer Streaming Events ---

def answer_chunk(chunk: str) -> str:
    """Streaming text response chunk."""
    return create_sse_event(EventType.ANSWER_CHUNK.value, {
        "chunk": chunk,
    })


def answer_complete(full_answer: str) -> str:
    """Answer finished."""
    return create_sse_event(EventType.ANSWER_COMPLETE.value, {
        "answer": full_answer,
    })


# --- Progress Events ---

def progress_update(
        phase: str,
        progress: float,
        message: str,
        details: Optional[Dict[str, Any]] = None,
) -> str:
    """General progress update."""
    return create_sse_event(EventType.PROGRESS_UPDATE.value, {
        "phase": phase,
        "progress": progress,
        "message": message,
        "details": details or {},
    })


# --- Connection Events ---

def connected(conversation_id: str, message: str = "Connected to chat stream") -> str:
    """Connection established."""
    return create_sse_event(EventType.CONNECTED.value, {
        "conversation_id": conversation_id,
        "message": message,
    })


def complete(
        success: bool,
        answer: Optional[str] = None,
        plan: Optional[Dict[str, Any]] = None,
        execution_results: Optional[List[Dict[str, Any]]] = None,
        validation: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        agent_timeline: Optional[List[Dict[str, Any]]] = None,
        log_paths: Optional[Dict[str, str]] = None,
        ops_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """Processing complete."""
    return create_sse_event(EventType.COMPLETE.value, {
        "success": success,
        "answer": answer,
        "plan": plan,
        "execution_results": execution_results or [],
        "validation": validation,
        "error": error,
        "summary": summary,
        "agent_timeline": agent_timeline,
        "log_paths": log_paths,
        "ops_summary": ops_summary,
    })


def error(message: str, details: Optional[Dict[str, Any]] = None) -> str:
    """Error occurred."""
    return create_sse_event(EventType.ERROR.value, {
        "message": message,
        "details": details or {},
    })


# ============== Agent Timeline Tracking ==============

@dataclass
class AgentActivity:
    """Tracks an agent's activity during processing."""
    agent_type: str
    agent_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "active"  # "active", "completed", "error"
    messages: List[str] = field(default_factory=list)
    thoughts: List[str] = field(default_factory=list)

    def complete(self, status: str = "completed") -> None:
        """Mark activity as complete."""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "messages": self.messages,
            "thoughts": self.thoughts,
        }


class AgentTimelineTracker:
    """Tracks all agent activities during a processing session."""

    def __init__(self):
        self.activities: List[AgentActivity] = []
        self.current_activity: Optional[AgentActivity] = None
        self.start_time: datetime = datetime.now()

    def start_agent(self, agent_type: str, agent_name: str) -> AgentActivity:
        """Start tracking a new agent activity."""
        # Complete current activity if any
        if self.current_activity:
            self.current_activity.complete()

        activity = AgentActivity(
            agent_type=agent_type,
            agent_name=agent_name,
            start_time=datetime.now(),
        )
        self.activities.append(activity)
        self.current_activity = activity
        return activity

    def add_message(self, message: str) -> None:
        """Add a message to current activity."""
        if self.current_activity:
            self.current_activity.messages.append(message)

    def add_thought(self, thought: str) -> None:
        """Add a thought to current activity."""
        if self.current_activity:
            self.current_activity.thoughts.append(thought)

    def complete_current(self, status: str = "completed") -> None:
        """Complete the current activity."""
        if self.current_activity:
            self.current_activity.complete(status)
            self.current_activity = None

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get the full timeline."""
        return [activity.to_dict() for activity in self.activities]

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all agent activities."""
        total_duration = (datetime.now() - self.start_time).total_seconds() * 1000

        agent_durations = {}
        for activity in self.activities:
            if activity.agent_type not in agent_durations:
                agent_durations[activity.agent_type] = 0
            if activity.duration_ms:
                agent_durations[activity.agent_type] += activity.duration_ms

        return {
            "total_duration_ms": total_duration,
            "agent_count": len(self.activities),
            "agent_durations": agent_durations,
            "timeline": self.get_timeline(),
        }
