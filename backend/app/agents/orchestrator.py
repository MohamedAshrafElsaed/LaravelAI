"""
Conductor - Orchestrator Agent (Enhanced).

Coordinates all agents to process user requests from start to finish.
Manages the workflow: analyze → retrieve → plan → execute → validate.

ENHANCEMENTS:
- Group A: Enhanced error handling with graceful degradation
- Group B: Smart retry logic with exponential backoff
- Group C: Observability metrics and performance tracking
- Group D: Progressive context accumulation
"""
import json
import logging
import asyncio
import time
from typing import Optional, Callable, Any, List, Dict, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.intent_analyzer import IntentAnalyzer, Intent
from app.agents.context_retriever import ContextRetriever, RetrievedContext
from app.agents.planner import Planner, Plan, PlanStep
from app.agents.executor import Executor, ExecutionResult
from app.agents.validator import Validator, ValidationResult, ValidationIssue
from app.agents.config import AgentConfig, agent_config
from app.agents.exceptions import (
    InsufficientContextError,
    AgentException,
    ValidationDegradationError,
)
from app.models.models import Project, IndexedFile
from app.services.claude import ClaudeService, get_claude_service
from app.services.conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ProcessPhase(str, Enum):
    """Phases of request processing."""
    ANALYZING = "analyzing"
    RETRIEVING = "retrieving"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentName(str, Enum):
    """Names of agents in the pipeline."""
    NOVA = "nova"
    SCOUT = "scout"
    BLUEPRINT = "blueprint"
    FORGE = "forge"
    GUARDIAN = "guardian"
    CONDUCTOR = "conductor"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    RECOVERABLE = "recoverable"
    DEGRADED = "degraded"
    FATAL = "fatal"


# =============================================================================
# METRICS AND OBSERVABILITY (Group C)
# =============================================================================

@dataclass
class AgentMetrics:
    """Metrics for a single agent execution."""
    agent: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None
    retries: int = 0
    tokens_used: int = 0

    def complete(self, success: bool = True, error: str = None):
        """Mark agent execution as complete."""
        self.completed_at = datetime.utcnow()
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        self.success = success
        self.error = error

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "retries": self.retries,
            "tokens_used": self.tokens_used,
        }


@dataclass
class PipelineMetrics:
    """Metrics for the entire pipeline execution."""
    request_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0
    agents: Dict[str, AgentMetrics] = field(default_factory=dict)
    phases_completed: List[str] = field(default_factory=list)
    total_retries: int = 0
    total_tokens: int = 0
    final_score: int = 0
    success: bool = False

    def start_agent(self, agent: str) -> AgentMetrics:
        """Start tracking an agent."""
        metrics = AgentMetrics(agent=agent)
        self.agents[agent] = metrics
        return metrics

    def complete_agent(self, agent: str, success: bool = True, error: str = None):
        """Complete tracking an agent."""
        if agent in self.agents:
            self.agents[agent].complete(success, error)

    def complete_phase(self, phase: str):
        """Mark a phase as completed."""
        if phase not in self.phases_completed:
            self.phases_completed.append(phase)

    def finalize(self, success: bool, score: int = 0):
        """Finalize pipeline metrics."""
        self.completed_at = datetime.utcnow()
        self.total_duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
        self.success = success
        self.final_score = score
        self.total_tokens = sum(m.tokens_used for m in self.agents.values())
        self.total_retries = sum(m.retries for m in self.agents.values())

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_ms": self.total_duration_ms,
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "phases_completed": self.phases_completed,
            "total_retries": self.total_retries,
            "total_tokens": self.total_tokens,
            "final_score": self.final_score,
            "success": self.success,
        }


# =============================================================================
# CONTEXT ACCUMULATOR (Group D)
# =============================================================================

@dataclass
class AccumulatedContext:
    """Progressive context accumulated across the pipeline."""

    # From project
    project_context: str = ""
    project_id: str = ""

    # From Nova
    intent: Optional[Intent] = None
    task_summary: str = ""

    # From Scout
    retrieved_context: Optional[RetrievedContext] = None
    key_files: List[str] = field(default_factory=list)
    detected_patterns: Dict[str, Any] = field(default_factory=dict)

    # From Blueprint
    plan: Optional[Plan] = None
    planned_files: List[str] = field(default_factory=list)

    # From Forge
    execution_results: List[ExecutionResult] = field(default_factory=list)
    generated_content: Dict[str, str] = field(default_factory=dict)

    # From Guardian
    validation_history: List[ValidationResult] = field(default_factory=list)
    recurring_issues: Set[str] = field(default_factory=set)

    def add_intent(self, intent: Intent):
        """Add intent analysis results."""
        self.intent = intent
        self.task_summary = f"{intent.task_type}: {', '.join(intent.domains_affected[:3])}"

    def add_context(self, context: RetrievedContext):
        """Add retrieved context."""
        self.retrieved_context = context
        self.key_files = [c.file_path for c in context.chunks[:10]]
        # Extract patterns for later validation
        for chunk in context.chunks:
            if "strict_types" in chunk.content:
                self.detected_patterns["strict_types"] = True
            if "declare(" in chunk.content:
                self.detected_patterns["declare_block"] = True

    def add_plan(self, plan: Plan):
        """Add planning results."""
        self.plan = plan
        self.planned_files = [s.file for s in plan.steps]

    def add_execution(self, result: ExecutionResult):
        """Add execution result."""
        self.execution_results.append(result)
        if result.success and result.content:
            self.generated_content[result.file] = result.content

    def add_validation(self, validation: ValidationResult):
        """Add validation result and track recurring issues."""
        self.validation_history.append(validation)
        # Track issue signatures for deduplication
        for issue in validation.issues:
            if hasattr(issue, 'signature') and issue.signature:
                self.recurring_issues.add(issue.signature)

    def get_fix_context(self) -> str:
        """Get context specifically for fix attempts."""
        parts = [f"Task: {self.task_summary}"]

        if self.detected_patterns:
            parts.append(f"Codebase patterns: {json.dumps(self.detected_patterns)}")

        if self.validation_history:
            last = self.validation_history[-1]
            parts.append(f"Last validation: score={last.score}, errors={len(last.errors)}")

            # Include recurring issues as warnings
            if len(self.validation_history) > 1:
                recurring = self._find_recurring_issues()
                if recurring:
                    parts.append(f"RECURRING ISSUES (fix carefully): {recurring}")

        return "\n".join(parts)

    def _find_recurring_issues(self) -> List[str]:
        """Find issues that appeared in multiple validations."""
        if len(self.validation_history) < 2:
            return []

        # Count issue occurrences by signature
        signature_counts: Dict[str, int] = {}
        for validation in self.validation_history:
            for issue in validation.issues:
                sig = getattr(issue, 'signature', None) or issue.message[:50]
                signature_counts[sig] = signature_counts.get(sig, 0) + 1

        # Return issues that appeared more than once
        return [sig for sig, count in signature_counts.items() if count > 1]


# =============================================================================
# RETRY STRATEGY (Group B)
# =============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 5.0
    exponential_base: float = 2.0
    jitter: float = 0.1


@dataclass
class RetryState:
    """Tracks retry state across fix attempts."""
    attempt: int = 0
    total_attempts: int = 0
    last_score: int = 0
    best_score: int = 0
    best_results: List[ExecutionResult] = field(default_factory=list)
    fixed_issues: Set[str] = field(default_factory=set)
    unfixable_issues: Set[str] = field(default_factory=set)

    def record_attempt(self, score: int, results: List[ExecutionResult]):
        """Record a fix attempt."""
        self.attempt += 1
        self.total_attempts += 1
        self.last_score = score

        if score > self.best_score:
            self.best_score = score
            self.best_results = results.copy()

    def mark_fixed(self, issue_signature: str):
        """Mark an issue as fixed."""
        self.fixed_issues.add(issue_signature)

    def mark_unfixable(self, issue_signature: str):
        """Mark an issue as unfixable (appeared 3+ times)."""
        self.unfixable_issues.add(issue_signature)

    def should_retry(self, config: AgentConfig) -> Tuple[bool, str]:
        """Determine if another retry should be attempted."""
        if self.attempt >= config.MAX_FIX_ATTEMPTS:
            return False, f"Max attempts ({config.MAX_FIX_ATTEMPTS}) reached"

        if self.last_score < self.best_score - config.SCORE_DEGRADATION_THRESHOLD:
            return False, f"Score degrading ({self.best_score} -> {self.last_score})"

        return True, ""

    def get_backoff_delay(self, config: RetryConfig) -> float:
        """Calculate exponential backoff delay."""
        import random
        delay = min(
            config.base_delay * (config.exponential_base ** self.attempt),
            config.max_delay
        )
        # Add jitter
        jitter = delay * config.jitter * (random.random() * 2 - 1)
        return delay + jitter


# =============================================================================
# ERROR HANDLING (Group A)
# =============================================================================

@dataclass
class AgentError:
    """Structured error from an agent."""
    agent: AgentName
    phase: ProcessPhase
    message: str
    severity: ErrorSeverity
    recoverable: bool
    details: Dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "agent": self.agent.value,
            "phase": self.phase.value,
            "message": self.message,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "details": self.details,
            "suggestion": self.suggestion,
        }


class ErrorRecoveryStrategy:
    """Strategies for recovering from agent errors."""

    @staticmethod
    def for_intent_error(error: Exception, context: AccumulatedContext) -> Tuple[bool, str]:
        """Recovery strategy for Nova (intent analysis) errors."""
        # Intent analysis is critical - can't proceed without it
        return False, "Intent analysis failed. Please rephrase your request."

    @staticmethod
    def for_context_error(error: Exception, context: AccumulatedContext) -> Tuple[bool, str]:
        """Recovery strategy for Scout (context retrieval) errors."""
        if isinstance(error, InsufficientContextError):
            # Can proceed with warning if some context found
            if hasattr(error, 'details') and error.details.get('chunks_found', 0) > 0:
                return True, "Limited context found. Proceeding with caution."
            return False, "No relevant code found. Ensure project is indexed."
        return False, f"Context retrieval failed: {str(error)}"

    @staticmethod
    def for_planning_error(error: Exception, context: AccumulatedContext) -> Tuple[bool, str]:
        """Recovery strategy for Blueprint (planning) errors."""
        # If we have context, we can try a simpler plan
        if context.retrieved_context and len(context.retrieved_context.chunks) > 0:
            return True, "Planning failed. Attempting simplified approach."
        return False, "Could not create a plan for this request."

    @staticmethod
    def for_execution_error(error: Exception, context: AccumulatedContext) -> Tuple[bool, str]:
        """Recovery strategy for Forge (execution) errors."""
        # Partial execution might still be useful
        successful = [r for r in context.execution_results if r.success]
        if successful:
            return True, f"Partial execution: {len(successful)} steps succeeded."
        return False, "Code generation failed. Please try a simpler request."

    @staticmethod
    def for_validation_error(error: Exception, context: AccumulatedContext) -> Tuple[bool, str]:
        """Recovery strategy for Guardian (validation) errors."""
        # Validation errors are usually recoverable - we have the code
        if context.execution_results:
            return True, "Validation encountered issues. Returning unvalidated results."
        return False, "Validation failed with no results to return."


# =============================================================================
# PROCESS EVENT AND RESULT
# =============================================================================

@dataclass
class ProcessEvent:
    """Event emitted during processing for real-time UI updates."""
    phase: ProcessPhase
    message: str
    progress: float
    data: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent: Optional[str] = None
    metrics: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "message": self.message,
            "progress": self.progress,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "metrics": self.metrics,
        }


@dataclass
class ProcessResult:
    """Final result of processing a request."""
    success: bool
    intent: Optional[Intent] = None
    plan: Optional[Plan] = None
    execution_results: List[ExecutionResult] = field(default_factory=list)
    validation: Optional[ValidationResult] = None
    error: Optional[str] = None
    events: List[ProcessEvent] = field(default_factory=list)
    metrics: Optional[PipelineMetrics] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "intent": self.intent.to_dict() if self.intent else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "execution_results": [r.to_dict() for r in self.execution_results],
            "validation": self.validation.to_dict() if self.validation else None,
            "error": self.error,
            "events": [e.to_dict() for e in self.events],
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "warnings": self.warnings,
        }


# =============================================================================
# MAIN ORCHESTRATOR CLASS
# =============================================================================

class Orchestrator:
    """
    Conductor - Orchestrates the full request processing workflow.

    Enhanced with:
    - Graceful error handling and recovery
    - Smart retry logic with exponential backoff
    - Comprehensive metrics and observability
    - Progressive context accumulation
    """

    def __init__(
        self,
        db: AsyncSession,
        event_callback: Optional[Callable[[ProcessEvent], Any]] = None,
        claude_service: Optional[ClaudeService] = None,
        conversation_logger: Optional[ConversationLogger] = None,
        config: Optional[AgentConfig] = None,
    ):
        """Initialize the orchestrator."""
        self.db = db
        self.event_callback = event_callback
        self.conversation_logger = conversation_logger
        self.config = config or agent_config
        self.retry_config = RetryConfig(max_attempts=self.config.MAX_FIX_ATTEMPTS)

        # Initialize agents
        claude = claude_service or get_claude_service()
        self.intent_analyzer = IntentAnalyzer(claude)
        self.context_retriever = ContextRetriever(db, config=self.config)
        self.planner = Planner(claude)
        self.executor = Executor(claude, config=self.config)
        self.validator = Validator(claude, config=self.config)

        # Request counter for metrics
        self._request_counter = 0

        tracking_info = "with tracking" if (claude_service and claude_service.tracker) else "without tracking"
        logging_info = "with conversation logging" if conversation_logger else "without conversation logging"
        logger.info(f"[CONDUCTOR] Initialized with enhanced orchestration ({tracking_info}, {logging_info})")

    # =========================================================================
    # EVENT EMISSION
    # =========================================================================

    async def _emit_event(
        self,
        phase: ProcessPhase,
        message: str,
        progress: float,
        data: Optional[dict] = None,
        agent: Optional[str] = None,
        metrics: Optional[dict] = None,
    ) -> ProcessEvent:
        """Emit a processing event."""
        event = ProcessEvent(
            phase=phase,
            message=message,
            progress=progress,
            data=data,
            agent=agent,
            metrics=metrics,
        )

        logger.info(f"[CONDUCTOR] {phase.value}: {message} ({progress*100:.0f}%)")

        if self.event_callback:
            try:
                result = self.event_callback(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"[CONDUCTOR] Event callback error: {e}")

        return event

    # =========================================================================
    # AGENT EXECUTION WITH METRICS
    # =========================================================================

    @asynccontextmanager
    async def _track_agent(self, agent: AgentName, metrics: PipelineMetrics):
        """Context manager to track agent execution."""
        agent_metrics = metrics.start_agent(agent.value)
        try:
            yield agent_metrics
            agent_metrics.complete(success=True)
        except Exception as e:
            agent_metrics.complete(success=False, error=str(e))
            raise

    async def _execute_with_retry(
        self,
        agent: AgentName,
        operation: Callable,
        metrics: PipelineMetrics,
        max_retries: int = 2,
    ) -> Any:
        """Execute an agent operation with retry logic."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                async with self._track_agent(agent, metrics) as agent_metrics:
                    agent_metrics.retries = attempt
                    result = await operation()
                    return result
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = self.retry_config.base_delay * (2 ** attempt)
                    logger.warning(f"[CONDUCTOR] {agent.value} failed (attempt {attempt+1}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[CONDUCTOR] {agent.value} failed after {max_retries+1} attempts: {e}")

        raise last_error

    # =========================================================================
    # MAIN PROCESSING PIPELINE
    # =========================================================================

    async def process_request(
        self,
        project_id: str,
        user_input: str,
    ) -> ProcessResult:
        """
        Process a user request through the full pipeline.

        Enhanced with:
        - Graceful error handling per agent
        - Progressive context accumulation
        - Smart retry with backoff
        - Comprehensive metrics
        """
        self._request_counter += 1
        request_id = f"req_{self._request_counter}_{int(time.time())}"

        logger.info(f"[CONDUCTOR] Processing request {request_id} for project={project_id}")
        logger.info(f"[CONDUCTOR] User input: {user_input[:200]}...")

        # Initialize tracking
        result = ProcessResult(success=False, events=[], warnings=[])
        metrics = PipelineMetrics(request_id=request_id)
        context = AccumulatedContext(project_id=project_id)
        retry_state = RetryState()

        # Clear validator history
        self.validator.clear_history()

        try:
            # ==================================================================
            # PHASE 0: PROJECT SETUP
            # ==================================================================
            project = await self._get_project(project_id)
            if not project:
                result.error = "Project not found"
                metrics.finalize(success=False)
                result.metrics = metrics
                return result

            context.project_context = self.build_project_context(project)
            logger.info(f"[CONDUCTOR] Built project context ({len(context.project_context)} chars)")

            # ==================================================================
            # PHASE 1: NOVA - INTENT ANALYSIS
            # ==================================================================
            event = await self._emit_event(
                ProcessPhase.ANALYZING,
                "Analyzing your request...",
                0.1,
                agent=AgentName.NOVA.value,
            )
            result.events.append(event)

            try:
                intent = await self._execute_with_retry(
                    AgentName.NOVA,
                    lambda: self.intent_analyzer.analyze(user_input, context.project_context),
                    metrics,
                )
                result.intent = intent
                context.add_intent(intent)
                metrics.complete_phase(ProcessPhase.ANALYZING.value)

                if self.conversation_logger:
                    self.conversation_logger.log_intent_analysis(intent.to_dict())

                event = await self._emit_event(
                    ProcessPhase.ANALYZING,
                    f"Identified task type: {intent.task_type}",
                    0.15,
                    {"intent": intent.to_dict()},
                    agent=AgentName.NOVA.value,
                )
                result.events.append(event)

            except Exception as e:
                recoverable, message = ErrorRecoveryStrategy.for_intent_error(e, context)
                if not recoverable:
                    result.error = message
                    metrics.finalize(success=False)
                    result.metrics = metrics
                    return result
                result.warnings.append(message)

            # ==================================================================
            # PHASE 2: SCOUT - CONTEXT RETRIEVAL
            # ==================================================================
            event = await self._emit_event(
                ProcessPhase.RETRIEVING,
                "Searching codebase for relevant context...",
                0.2,
                agent=AgentName.SCOUT.value,
            )
            result.events.append(event)

            try:
                retrieved = await self._execute_with_retry(
                    AgentName.SCOUT,
                    lambda: self.context_retriever.retrieve(
                        project_id, intent,
                        require_minimum=self.config.ABORT_ON_NO_CONTEXT
                    ),
                    metrics,
                )
                context.add_context(retrieved)
                metrics.complete_phase(ProcessPhase.RETRIEVING.value)

                # Warn on low confidence
                if retrieved.confidence_level == "low":
                    result.warnings.append(f"Limited context: {len(retrieved.chunks)} chunks found")
                    event = await self._emit_event(
                        ProcessPhase.RETRIEVING,
                        f"⚠️ Limited context found ({len(retrieved.chunks)} chunks)",
                        0.25,
                        agent=AgentName.SCOUT.value,
                    )
                    result.events.append(event)

                if self.conversation_logger:
                    self.conversation_logger.log_context_retrieval(
                        chunks_count=len(retrieved.chunks),
                        chunks=[{
                            "file_path": c.file_path,
                            "content": c.content[:500] if c.content else "",
                            "score": getattr(c, 'score', None),
                        } for c in retrieved.chunks[:20]],
                    )

                event = await self._emit_event(
                    ProcessPhase.RETRIEVING,
                    f"Found {len(retrieved.chunks)} relevant code sections",
                    0.3,
                    {"chunks_count": len(retrieved.chunks)},
                    agent=AgentName.SCOUT.value,
                )
                result.events.append(event)

            except InsufficientContextError as e:
                recoverable, message = ErrorRecoveryStrategy.for_context_error(e, context)
                if not recoverable:
                    result.error = message
                    await self._emit_event(ProcessPhase.FAILED, message, 0.25)
                    metrics.finalize(success=False)
                    result.metrics = metrics
                    return result
                result.warnings.append(message)

            # ==================================================================
            # PHASE 2.5: HANDLE QUESTIONS
            # ==================================================================
            if intent.task_type == "question":
                event = await self._emit_event(
                    ProcessPhase.COMPLETED,
                    "Context retrieved for question",
                    1.0,
                )
                result.events.append(event)
                result.success = True
                metrics.finalize(success=True)
                result.metrics = metrics
                return result

            # ==================================================================
            # PHASE 3: BLUEPRINT - PLANNING
            # ==================================================================
            event = await self._emit_event(
                ProcessPhase.PLANNING,
                "Creating implementation plan...",
                0.35,
                agent=AgentName.BLUEPRINT.value,
            )
            result.events.append(event)

            try:
                plan = await self._execute_with_retry(
                    AgentName.BLUEPRINT,
                    lambda: self.planner.plan(
                        user_input, intent, context.retrieved_context, context.project_context
                    ),
                    metrics,
                )
                result.plan = plan
                context.add_plan(plan)
                metrics.complete_phase(ProcessPhase.PLANNING.value)

                if self.conversation_logger:
                    self.conversation_logger.log_plan(plan.to_dict())

                event = await self._emit_event(
                    ProcessPhase.PLANNING,
                    f"Plan created with {len(plan.steps)} steps",
                    0.4,
                    {"plan": plan.to_dict()},
                    agent=AgentName.BLUEPRINT.value,
                )
                result.events.append(event)

                if not plan.steps:
                    result.error = "Could not create a valid plan"
                    metrics.finalize(success=False)
                    result.metrics = metrics
                    return result

            except Exception as e:
                recoverable, message = ErrorRecoveryStrategy.for_planning_error(e, context)
                if not recoverable:
                    result.error = message
                    metrics.finalize(success=False)
                    result.metrics = metrics
                    return result
                result.warnings.append(message)

            # ==================================================================
            # PHASE 4: FORGE - EXECUTION
            # ==================================================================
            execution_results = []
            total_steps = len(plan.steps)

            for i, step in enumerate(plan.steps):
                step_progress_start = 0.4 + (0.4 * (i / total_steps))
                step_progress_end = 0.4 + (0.4 * ((i + 1) / total_steps))

                event = await self._emit_event(
                    ProcessPhase.EXECUTING,
                    f"Executing step {step.order}/{total_steps}: {step.description[:50]}...",
                    step_progress_start,
                    {"step": step.to_dict(), "step_index": i},
                    agent=AgentName.FORGE.value,
                )
                result.events.append(event)

                # Get current content for modify/delete
                current_content = None
                if step.action in ["modify", "delete"]:
                    current_content = await self._get_file_content(project_id, step.file)

                try:
                    exec_result = await self.executor.execute_step(
                        step=step,
                        context=context.retrieved_context,
                        previous_results=execution_results,
                        current_file_content=current_content,
                        project_context=context.project_context,
                    )
                    execution_results.append(exec_result)
                    context.add_execution(exec_result)

                    if self.conversation_logger:
                        self.conversation_logger.log_execution_step(
                            step_number=i + 1,
                            total_steps=total_steps,
                            step_data=step.to_dict(),
                            result_data=exec_result.to_dict(),
                            generated_code=exec_result.content,
                            diff=exec_result.diff,
                        )

                    event = await self._emit_event(
                        ProcessPhase.EXECUTING,
                        f"Step {step.order}/{total_steps} {'completed' if exec_result.success else 'failed'}",
                        step_progress_end,
                        {"step": step.to_dict(), "result": exec_result.to_dict()},
                        agent=AgentName.FORGE.value,
                    )
                    result.events.append(event)

                except Exception as e:
                    logger.error(f"[CONDUCTOR] Step {step.order} failed: {e}")
                    exec_result = ExecutionResult(
                        file=step.file,
                        action=step.action,
                        content="",
                        success=False,
                        error=str(e),
                    )
                    execution_results.append(exec_result)

            result.execution_results = execution_results
            metrics.complete_phase(ProcessPhase.EXECUTING.value)

            event = await self._emit_event(
                ProcessPhase.EXECUTING,
                f"Executed {len(execution_results)} steps",
                0.8,
                agent=AgentName.FORGE.value,
            )
            result.events.append(event)

            # ==================================================================
            # PHASE 5: GUARDIAN - VALIDATION + FIX LOOP
            # ==================================================================
            event = await self._emit_event(
                ProcessPhase.VALIDATING,
                "Validating generated code...",
                0.85,
                agent=AgentName.GUARDIAN.value,
            )
            result.events.append(event)

            validation = await self.validator.validate(
                user_input=user_input,
                intent=intent,
                results=execution_results,
                context=context.retrieved_context,
            )
            result.validation = validation
            context.add_validation(validation)
            retry_state.record_attempt(validation.score, execution_results)

            if self.conversation_logger:
                self.conversation_logger.log_validation(validation.to_dict())

            # ==================================================================
            # FIX LOOP WITH SMART RETRY
            # ==================================================================
            while not validation.approved:
                should_retry, reason = retry_state.should_retry(self.config)

                if not should_retry:
                    logger.warning(f"[CONDUCTOR] Stopping retry: {reason}")
                    event = await self._emit_event(
                        ProcessPhase.FIXING,
                        f"Fix attempts stopped: {reason}",
                        0.9,
                        agent=AgentName.GUARDIAN.value,
                    )
                    result.events.append(event)
                    break

                # Exponential backoff
                delay = retry_state.get_backoff_delay(self.retry_config)
                logger.info(f"[CONDUCTOR] Retry {retry_state.attempt + 1} after {delay:.2f}s delay")
                await asyncio.sleep(delay)

                event = await self._emit_event(
                    ProcessPhase.FIXING,
                    f"Fixing issues (attempt {retry_state.attempt + 1}/{self.config.MAX_FIX_ATTEMPTS})...",
                    0.85 + (0.03 * retry_state.attempt),
                    {"issues": [i.to_dict() for i in validation.errors]},
                    agent=AgentName.FORGE.value,
                )
                result.events.append(event)

                # Smart fix: prioritize unfixed issues, skip recurring ones
                execution_results = await self._smart_fix(
                    execution_results, validation, context, retry_state
                )
                result.execution_results = execution_results

                # Re-validate
                validation = await self.validator.validate(
                    user_input=user_input,
                    intent=intent,
                    results=execution_results,
                    context=context.retrieved_context,
                )
                result.validation = validation
                context.add_validation(validation)
                retry_state.record_attempt(validation.score, execution_results)

                if self.conversation_logger:
                    self.conversation_logger.log_validation(validation.to_dict())

                logger.info(f"[CONDUCTOR] Retry {retry_state.attempt}: score={validation.score}, approved={validation.approved}")

            metrics.complete_phase(ProcessPhase.VALIDATING.value)

            # ==================================================================
            # FINAL RESULT
            # ==================================================================
            if validation.approved:
                event = await self._emit_event(
                    ProcessPhase.COMPLETED,
                    f"Completed successfully! Score: {validation.score}/100",
                    1.0,
                    {"validation": validation.to_dict()},
                )
                result.events.append(event)
                result.success = True
            else:
                # Use best results if current is worse
                if retry_state.best_score > validation.score:
                    result.execution_results = retry_state.best_results
                    result.warnings.append(f"Using best attempt (score: {retry_state.best_score})")

                event = await self._emit_event(
                    ProcessPhase.COMPLETED,
                    f"Completed with warnings. Score: {validation.score}/100",
                    1.0,
                    {"validation": validation.to_dict()},
                )
                result.events.append(event)
                result.success = len(validation.errors) == 0

            metrics.finalize(success=result.success, score=validation.score)
            result.metrics = metrics

            # Log final metrics
            logger.info(f"[CONDUCTOR] Pipeline complete: {metrics.to_dict()}")

            return result

        except Exception as e:
            logger.exception(f"[CONDUCTOR] Processing failed: {e}")
            result.error = str(e)
            metrics.finalize(success=False)
            result.metrics = metrics

            event = await self._emit_event(
                ProcessPhase.FAILED,
                f"Processing failed: {str(e)}",
                0.0,
            )
            result.events.append(event)

            return result

    # =========================================================================
    # SMART FIX LOGIC (Group B)
    # =========================================================================

    async def _smart_fix(
        self,
        execution_results: List[ExecutionResult],
        validation: ValidationResult,
        context: AccumulatedContext,
        retry_state: RetryState,
    ) -> List[ExecutionResult]:
        """
        Intelligent fix strategy that:
        - Prioritizes issues by severity and fixability
        - Skips recurring unfixable issues
        - Deduplicates similar issues
        - Provides accumulated context to fixes
        """
        # Group issues by file
        issues_by_file: Dict[str, List[ValidationIssue]] = {}
        for issue in validation.errors:
            file_key = self._normalize_path(issue.file)
            if file_key not in issues_by_file:
                issues_by_file[file_key] = []
            issues_by_file[file_key].append(issue)

        # Map execution results by file
        results_by_file = {
            self._normalize_path(r.file): i
            for i, r in enumerate(execution_results)
        }

        # Fix each file with issues
        for file_key, issues in issues_by_file.items():
            # Skip if no matching result
            if file_key not in results_by_file:
                # Try partial match
                matched = False
                for result_key, idx in results_by_file.items():
                    if file_key in result_key or result_key.endswith(file_key):
                        file_key = result_key
                        matched = True
                        break
                if not matched:
                    continue

            idx = results_by_file[file_key]
            exec_result = execution_results[idx]

            if not exec_result.success:
                continue

            # Filter issues: skip unfixable ones
            fixable_issues = []
            for issue in issues:
                sig = getattr(issue, 'signature', None) or issue.message[:50]

                # Check if this issue has appeared 3+ times
                occurrences = sum(
                    1 for v in context.validation_history
                    for vi in v.issues
                    if (getattr(vi, 'signature', None) or vi.message[:50]) == sig
                )

                if occurrences >= 3:
                    retry_state.mark_unfixable(sig)
                    logger.warning(f"[CONDUCTOR] Marking issue as unfixable (3+ occurrences): {sig}")
                    continue

                fixable_issues.append(issue)

            if not fixable_issues:
                continue

            # Build issue messages with context
            issue_messages = [i.message for i in fixable_issues]

            # Add accumulated context hints
            fix_context = context.get_fix_context()
            if fix_context:
                issue_messages.append(f"CONTEXT: {fix_context}")

            # Execute fix
            logger.info(f"[CONDUCTOR] Fixing {exec_result.file} with {len(fixable_issues)} issues")
            fixed = await self.executor.fix_execution(
                result=exec_result,
                issues=issue_messages,
                context=context.retrieved_context,
            )
            execution_results[idx] = fixed

            # Mark issues as fixed if score improves
            for issue in fixable_issues:
                sig = getattr(issue, 'signature', None) or issue.message[:50]
                retry_state.mark_fixed(sig)

        return execution_results

    def _normalize_path(self, path: str) -> str:
        """Normalize file path for comparison."""
        if not path:
            return ""
        path = path.strip().replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        return path.lower()

    # =========================================================================
    # DATABASE HELPERS
    # =========================================================================

    async def _get_project(self, project_id: str) -> Optional[Project]:
        """Fetch project from database."""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_file_content(self, project_id: str, file_path: str) -> Optional[str]:
        """Get file content from indexed files."""
        stmt = select(IndexedFile).where(
            IndexedFile.project_id == project_id,
            IndexedFile.file_path == file_path,
        )
        result = await self.db.execute(stmt)
        indexed_file = result.scalar_one_or_none()
        return indexed_file.content if indexed_file else None

    # =========================================================================
    # PROJECT CONTEXT BUILDER
    # =========================================================================

    def build_project_context(self, project: Project) -> str:
        """Build rich project context from scan data."""
        parts = []

        def safe_get(obj, key, default=None):
            if obj is None:
                return default
            if isinstance(obj, str):
                try:
                    obj = json.loads(obj)
                except (json.JSONDecodeError, TypeError):
                    return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return default

        parts.append(f"## Project: {project.repo_full_name}")
        parts.append("")

        # Technology Stack
        stack = project.stack
        if stack:
            if isinstance(stack, str):
                try:
                    stack = json.loads(stack)
                except:
                    stack = {}

            if isinstance(stack, dict):
                parts.append("### Technology Stack")
                backend = safe_get(stack, "backend", {})
                if isinstance(backend, dict) and backend:
                    framework = safe_get(backend, "framework", "unknown")
                    version = safe_get(backend, "version", "")
                    php_version = safe_get(backend, "php_version", "")
                    parts.append(f"- **Backend:** {framework} {version}".strip())
                    if php_version:
                        parts.append(f"- **PHP:** {php_version}")

                frontend = safe_get(stack, "frontend", {})
                if isinstance(frontend, dict) and frontend:
                    parts.append(f"- **Frontend:** {safe_get(frontend, 'framework', '')} {safe_get(frontend, 'version', '')}".strip())

                database = safe_get(stack, "database", {})
                if isinstance(database, dict):
                    db_type = safe_get(database, "type", "")
                    if db_type:
                        parts.append(f"- **Database:** {db_type}")

                packages = safe_get(stack, "packages", [])
                if isinstance(packages, list) and packages:
                    parts.append(f"- **Packages:** {', '.join(str(p) for p in packages[:10])}")

                parts.append("")

        # Health Score
        if project.health_score is not None:
            try:
                parts.append(f"### Health: {float(project.health_score):.0f}/100")
            except:
                parts.append(f"### Health: {project.health_score}/100")
            parts.append("")

        # AI Context
        ai_context = project.ai_context
        if ai_context:
            if isinstance(ai_context, str):
                try:
                    ai_context = json.loads(ai_context)
                except:
                    ai_context = {}

            if isinstance(ai_context, dict):
                claude_md = safe_get(ai_context, "claude_md_content", "")
                if claude_md:
                    parts.append("### Conventions (CLAUDE.md)")
                    parts.append(claude_md[:1500] + "..." if len(claude_md) > 1500 else claude_md)
                    parts.append("")

                patterns = safe_get(ai_context, "key_patterns", [])
                if isinstance(patterns, list) and patterns:
                    parts.append("### Patterns")
                    for p in patterns[:5]:
                        parts.append(f"- {p}")
                    parts.append("")

        return "\n".join(parts)

    # =========================================================================
    # QUESTION PROCESSING
    # =========================================================================

    async def process_question(
        self,
        project_id: str,
        question: str,
    ) -> Tuple[Intent, RetrievedContext, str]:
        """Process a question without code generation."""
        logger.info(f"[CONDUCTOR] Processing question for project={project_id}")

        project = await self._get_project(project_id)
        project_context = self.build_project_context(project) if project else ""

        intent = await self.intent_analyzer.analyze(question, project_context)
        context = await self.context_retriever.retrieve(project_id, intent)

        return intent, context, project_context