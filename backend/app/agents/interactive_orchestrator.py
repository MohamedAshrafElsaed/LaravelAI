"""
Interactive Orchestrator Agent.

Enhanced orchestrator that provides a fully interactive, dynamic multi-agent
experience with named agents, thinking animations, and plan approval gateway.

Coordinates all agents with real-time visibility: analyze → retrieve → plan →
(approval gateway) → execute → validate.
"""
import json
import logging
import asyncio
import random
from typing import Optional, Callable, Any, List, Dict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.intent_analyzer import IntentAnalyzer, Intent
from app.agents.context_retriever import ContextRetriever, RetrievedContext
from app.agents.planner import Planner, Plan, PlanStep
from app.agents.executor import Executor, ExecutionResult
from app.agents.validator import Validator, ValidationResult
from app.agents.config import AgentConfig, agent_config
from app.agents.exceptions import InsufficientContextError
from app.agents.orchestrator import ProcessPhase, ProcessEvent, ProcessResult
from app.agents.agent_identity import (
    AgentType,
    AgentIdentity,
    get_agent,
    NOVA,
    SCOUT,
    BLUEPRINT,
    FORGE,
    GUARDIAN,
    CONDUCTOR,
    get_thinking_messages,
    get_random_thinking_message,
)
from app.agents.events import (
    EventType,
    AgentTimelineTracker,
    create_sse_event,
    agent_thinking,
    agent_message,
    agent_handoff,
    agent_state_change,
    intent_started,
    intent_thinking,
    intent_analyzed,
    context_started,
    context_thinking,
    context_chunk_found,
    context_retrieved,
    planning_started,
    planning_thinking,
    plan_step_added,
    plan_ready,
    plan_approved,
    plan_created,
    execution_started,
    step_started,
    step_thinking,
    step_code_chunk,
    step_progress,
    step_completed,
    execution_completed,
    validation_started,
    validation_thinking,
    validation_issue_found,
    validation_fix_started,
    validation_fix_completed,
    validation_result,
    progress_update,
    connected,
    complete,
    error,
)
from app.models.models import Project, IndexedFile
from app.services.claude import ClaudeService, get_claude_service
from app.services.conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


@dataclass
class PlanApprovalState:
    """Tracks the state of plan approval."""
    plan: Optional[Plan] = None
    approved: bool = False
    modified: bool = False
    rejected: bool = False
    rejection_reason: Optional[str] = None
    user_instructions: Optional[str] = None


class InteractiveOrchestrator:
    """
    Enhanced orchestrator with interactive multi-agent experience.

    Features:
    - Named AI agents with distinct personalities
    - Real-time thinking animations for each phase
    - Plan approval gateway with user modification support
    - Detailed event streaming for frontend visualization
    - Agent timeline tracking
    """

    def __init__(
        self,
        db: AsyncSession,
        event_callback: Optional[Callable[[str], Any]] = None,
        claude_service: Optional[ClaudeService] = None,
        conversation_logger: Optional[ConversationLogger] = None,
        config: Optional[AgentConfig] = None,
        require_plan_approval: bool = True,
        step_by_step_mode: bool = False,
    ):
        """
        Initialize the interactive orchestrator.

        Args:
            db: Database session
            event_callback: Callback for SSE events (receives formatted event strings)
            claude_service: Optional ClaudeService instance
            conversation_logger: Optional ConversationLogger for detailed logging
            config: Optional agent configuration
            require_plan_approval: If True, pauses for user plan approval
            step_by_step_mode: If True, pauses between execution steps
        """
        self.db = db
        self.event_callback = event_callback
        self.conversation_logger = conversation_logger
        self.config = config or agent_config
        self.require_plan_approval = require_plan_approval
        self.step_by_step_mode = step_by_step_mode

        # Plan approval state
        self.plan_approval = PlanApprovalState()
        self._plan_approval_event = asyncio.Event()

        # Initialize agents with the Claude service and config
        claude = claude_service or get_claude_service()
        self.intent_analyzer = IntentAnalyzer(claude)
        self.context_retriever = ContextRetriever(db, config=self.config)
        self.planner = Planner(claude)
        self.executor = Executor(claude, config=self.config)
        self.validator = Validator(claude, config=self.config)

        # Timeline tracker
        self.timeline = AgentTimelineTracker()

        # Current active agent
        self.active_agent: Optional[AgentIdentity] = None

        tracking_info = "with tracking" if (claude_service and claude_service.tracker) else "without tracking"
        logging_info = "with conversation logging" if conversation_logger else "without conversation logging"
        logger.info(f"[INTERACTIVE_ORCHESTRATOR] Initialized ({tracking_info}, {logging_info})")

    async def _emit_event(self, event_str: str) -> None:
        """Emit an SSE event string."""
        if self.event_callback:
            try:
                result = self.event_callback(event_str)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"[INTERACTIVE_ORCHESTRATOR] Event callback error: {e}")

    async def _emit_legacy_event(
        self,
        phase: ProcessPhase,
        message: str,
        progress: float,
        data: Optional[dict] = None,
    ) -> ProcessEvent:
        """Emit a legacy ProcessEvent for backwards compatibility."""
        event = ProcessEvent(
            phase=phase,
            message=message,
            progress=progress,
            data=data,
        )
        logger.info(f"[INTERACTIVE_ORCHESTRATOR] {phase.value}: {message} ({progress*100:.0f}%)")
        return event

    async def _set_active_agent(self, agent: AgentIdentity) -> None:
        """Set the currently active agent and emit state change."""
        if self.active_agent and self.active_agent != agent:
            # Deactivate previous agent
            await self._emit_event(agent_state_change(
                self.active_agent.agent_type.value,
                self.active_agent.name,
                "idle",
            ))
            self.timeline.complete_current()

        self.active_agent = agent
        self.timeline.start_agent(agent.agent_type.value, agent.name)

        await self._emit_event(agent_state_change(
            agent.agent_type.value,
            agent.name,
            "active",
        ))

    async def _emit_thinking_sequence(
        self,
        agent: AgentIdentity,
        action_type: str,
        count: int = 3,
        delay: float = 0.8,
        file_path: Optional[str] = None,
        step_index: Optional[int] = None,
    ) -> None:
        """Emit a sequence of thinking messages for an agent."""
        messages = get_thinking_messages(action_type)
        if not messages:
            messages = agent.thinking_phrases

        # Sample random messages
        selected = random.sample(messages, min(count, len(messages)))

        for i, thought in enumerate(selected):
            progress = (i + 1) / count
            await self._emit_event(agent_thinking(
                agent.agent_type.value,
                agent.name,
                thought,
                action_type,
                file_path,
                step_index,
                progress,
            ))
            self.timeline.add_thought(thought)
            await asyncio.sleep(delay)

    async def _handoff(
        self,
        from_agent: AgentIdentity,
        to_agent: AgentIdentity,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit an agent handoff event."""
        message = from_agent.get_random_handoff(to_agent.name)

        await self._emit_event(agent_handoff(
            from_agent.agent_type.value,
            from_agent.name,
            to_agent.agent_type.value,
            to_agent.name,
            message,
            context,
        ))

        # Also emit as agent message for conversation thread
        await self._emit_event(agent_message(
            from_agent.agent_type.value,
            from_agent.name,
            message,
            "handoff",
            to_agent.agent_type.value,
            to_agent.name,
        ))

        await self._set_active_agent(to_agent)

    async def approve_plan(self, approved: bool = True, modified_plan: Optional[Dict] = None, rejection_reason: Optional[str] = None) -> None:
        """
        Approve, modify, or reject the current plan.

        Called by the frontend when user makes a decision on the plan.
        """
        self.plan_approval.approved = approved
        self.plan_approval.rejected = not approved and rejection_reason is not None
        self.plan_approval.rejection_reason = rejection_reason

        if modified_plan:
            self.plan_approval.modified = True
            # Convert dict back to Plan object
            steps = [
                PlanStep(
                    order=s.get("order", i + 1),
                    action=s.get("action", "modify"),
                    file=s.get("file", ""),
                    description=s.get("description", ""),
                )
                for i, s in enumerate(modified_plan.get("steps", []))
            ]
            self.plan_approval.plan = Plan(
                summary=modified_plan.get("summary", ""),
                steps=steps,
            )

        # Signal that plan decision has been made
        self._plan_approval_event.set()

    async def process_request(
        self,
        project_id: str,
        user_input: str,
    ) -> ProcessResult:
        """
        Process a user request with full interactive experience.

        Args:
            project_id: The project UUID
            user_input: User's request text

        Returns:
            ProcessResult with all outputs
        """
        logger.info(f"[INTERACTIVE_ORCHESTRATOR] Processing request for project={project_id}")
        logger.info(f"[INTERACTIVE_ORCHESTRATOR] User input: {user_input[:200]}...")

        result = ProcessResult(success=False, events=[])
        self.validator.clear_history()
        self.plan_approval = PlanApprovalState()
        self._plan_approval_event.clear()

        try:
            # ============== CONDUCTOR INTRO ==============
            await self._set_active_agent(CONDUCTOR)
            await self._emit_event(agent_message(
                CONDUCTOR.agent_type.value,
                CONDUCTOR.name,
                CONDUCTOR.get_random_greeting(),
                "greeting",
            ))
            await asyncio.sleep(0.3)

            # ============== FETCH PROJECT ==============
            project = await self._get_project(project_id)
            if not project:
                result.error = "Project not found"
                await self._emit_event(error("Project not found"))
                return result

            project_context = self.build_project_context(project)

            # ============== PHASE 1: NOVA - INTENT ANALYSIS ==============
            await self._handoff(CONDUCTOR, NOVA, {"task": "analyze_intent"})

            await self._emit_event(agent_message(
                NOVA.agent_type.value,
                NOVA.name,
                NOVA.get_random_greeting(),
                "greeting",
            ))

            await self._emit_event(intent_started("Analyzing your request..."))

            # Emit thinking sequence
            await self._emit_thinking_sequence(NOVA, "intent", count=3)

            event = await self._emit_legacy_event(
                ProcessPhase.ANALYZING,
                "Analyzing your request...",
                0.1,
            )
            result.events.append(event)

            # Actual intent analysis
            intent = await self.intent_analyzer.analyze(user_input, project_context)
            result.intent = intent

            # Log intent
            if self.conversation_logger:
                self.conversation_logger.log_intent_analysis(intent.to_dict())

            # Emit analyzed result
            await self._emit_event(intent_analyzed(
                intent.to_dict(),
                f"Identified: {intent.task_type} affecting {', '.join(intent.domains_affected[:3])}",
                0.15,
            ))

            await self._emit_event(agent_message(
                NOVA.agent_type.value,
                NOVA.name,
                f"I understand you want to {intent.task_type}. This affects: {', '.join(intent.domains_affected[:3])}.",
                "completion",
            ))

            event = await self._emit_legacy_event(
                ProcessPhase.ANALYZING,
                f"Identified task type: {intent.task_type}",
                0.15,
                {"intent": intent.to_dict()},
            )
            result.events.append(event)

            # ============== PHASE 2: SCOUT - CONTEXT RETRIEVAL ==============
            await self._handoff(NOVA, SCOUT, {"intent": intent.to_dict()})

            await self._emit_event(agent_message(
                SCOUT.agent_type.value,
                SCOUT.name,
                SCOUT.get_random_greeting(),
                "greeting",
            ))

            await self._emit_event(context_started("Searching the codebase..."))

            # Emit thinking sequence
            await self._emit_thinking_sequence(SCOUT, "context", count=4)

            event = await self._emit_legacy_event(
                ProcessPhase.RETRIEVING,
                "Searching codebase for relevant context...",
                0.2,
            )
            result.events.append(event)

            # Actual context retrieval
            try:
                context = await self.context_retriever.retrieve(
                    project_id, intent,
                    require_minimum=self.config.ABORT_ON_NO_CONTEXT
                )
            except InsufficientContextError as e:
                await self._emit_event(agent_message(
                    SCOUT.agent_type.value,
                    SCOUT.name,
                    f"I couldn't find relevant code in the codebase. {e.message}",
                    "error",
                ))
                result.error = (
                    f"Unable to find relevant code in the project. "
                    f"Found {e.details['chunks_found']} code chunks. "
                    f"Please ensure the project is indexed and try a more specific request."
                )
                await self._emit_event(error(result.error))
                return result

            # Emit found chunks (show a few key ones)
            for i, chunk in enumerate(context.chunks[:3]):
                await self._emit_event(context_chunk_found(
                    chunk.file_path,
                    chunk.chunk_type,
                    chunk.score,
                    chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content,
                ))
                await asyncio.sleep(0.2)

            # Log context retrieval
            if self.conversation_logger:
                chunks_data = [
                    {
                        "file_path": chunk.file_path,
                        "content": chunk.content[:500] if chunk.content else "",
                        "score": getattr(chunk, 'score', None),
                    }
                    for chunk in context.chunks[:20]
                ]
                self.conversation_logger.log_context_retrieval(
                    chunks_count=len(context.chunks),
                    chunks=chunks_data,
                    related_files=context.related_files if hasattr(context, 'related_files') else None,
                    domain_summaries=context.domain_summaries if hasattr(context, 'domain_summaries') else None,
                )

            await self._emit_event(context_retrieved(
                len(context.chunks),
                context.confidence_level,
                f"Found {len(context.chunks)} relevant code sections",
                0.3,
            ))

            await self._emit_event(agent_message(
                SCOUT.agent_type.value,
                SCOUT.name,
                f"Found {len(context.chunks)} relevant code sections with {context.confidence_level} confidence.",
                "completion",
            ))

            event = await self._emit_legacy_event(
                ProcessPhase.RETRIEVING,
                f"Found {len(context.chunks)} relevant code sections",
                0.3,
                {"chunks_count": len(context.chunks)},
            )
            result.events.append(event)

            # ============== HANDLE QUESTIONS ==============
            if intent.task_type == "question":
                event = await self._emit_legacy_event(
                    ProcessPhase.COMPLETED,
                    "Context retrieved for question",
                    1.0,
                )
                result.events.append(event)
                result.success = True

                # Complete timeline
                self.timeline.complete_current()

                return result

            # ============== PHASE 3: BLUEPRINT - PLANNING ==============
            await self._handoff(SCOUT, BLUEPRINT, {
                "context_chunks": len(context.chunks),
                "confidence": context.confidence_level,
            })

            await self._emit_event(agent_message(
                BLUEPRINT.agent_type.value,
                BLUEPRINT.name,
                BLUEPRINT.get_random_greeting(),
                "greeting",
            ))

            await self._emit_event(planning_started("Creating implementation plan..."))

            # Emit thinking sequence
            await self._emit_thinking_sequence(BLUEPRINT, "planning", count=4)

            event = await self._emit_legacy_event(
                ProcessPhase.PLANNING,
                "Creating implementation plan...",
                0.35,
            )
            result.events.append(event)

            # Actual planning
            plan = await self.planner.plan(user_input, intent, context, project_context)
            result.plan = plan

            # Emit steps one by one (for animation)
            for i, step in enumerate(plan.steps):
                await self._emit_event(plan_step_added(
                    i,
                    step.to_dict(),
                    len(plan.steps),
                ))
                await asyncio.sleep(0.3)

            # Log plan
            if self.conversation_logger:
                self.conversation_logger.log_plan(plan.to_dict())

            await self._emit_event(agent_message(
                BLUEPRINT.agent_type.value,
                BLUEPRINT.name,
                f"I've designed a {len(plan.steps)}-step implementation plan: {plan.summary[:100]}",
                "completion",
            ))

            event = await self._emit_legacy_event(
                ProcessPhase.PLANNING,
                f"Plan created with {len(plan.steps)} steps",
                0.4,
                {"plan": plan.to_dict()},
            )
            result.events.append(event)

            if not plan.steps:
                result.error = "Could not create a valid plan"
                await self._emit_event(error("Planning failed - no steps generated"))
                return result

            # ============== PLAN APPROVAL GATEWAY ==============
            if self.require_plan_approval:
                await self._emit_event(plan_ready(
                    plan.to_dict(),
                    "Plan ready for review. Please approve to continue.",
                    True,
                ))

                # Wait for user approval (with timeout)
                try:
                    await asyncio.wait_for(
                        self._plan_approval_event.wait(),
                        timeout=300.0,  # 5 minute timeout
                    )
                except asyncio.TimeoutError:
                    result.error = "Plan approval timed out"
                    await self._emit_event(error("Plan approval timed out"))
                    return result

                # Handle rejection
                if self.plan_approval.rejected:
                    await self._emit_event(agent_message(
                        BLUEPRINT.agent_type.value,
                        BLUEPRINT.name,
                        f"Plan rejected: {self.plan_approval.rejection_reason}. Let me try again...",
                        "error",
                    ))
                    # Could implement regeneration here
                    result.error = f"Plan rejected: {self.plan_approval.rejection_reason}"
                    return result

                # Handle modification
                if self.plan_approval.modified and self.plan_approval.plan:
                    plan = self.plan_approval.plan
                    result.plan = plan
                    await self._emit_event(agent_message(
                        BLUEPRINT.agent_type.value,
                        BLUEPRINT.name,
                        "Plan modified by user. Proceeding with updated plan.",
                        "custom",
                    ))

                await self._emit_event(plan_approved(plan.to_dict()))
            else:
                # Auto-approve
                await self._emit_event(plan_created(plan.to_dict(), "Plan created", 0.4))

            # ============== PHASE 4: FORGE - EXECUTION ==============
            await self._handoff(BLUEPRINT, FORGE, {
                "plan_steps": len(plan.steps),
            })

            await self._emit_event(agent_message(
                FORGE.agent_type.value,
                FORGE.name,
                FORGE.get_random_greeting(),
                "greeting",
            ))

            await self._emit_event(execution_started(len(plan.steps), "Starting code execution..."))

            execution_results = []
            total_steps = len(plan.steps)

            for i, step in enumerate(plan.steps):
                step_progress_start = 0.4 + (0.4 * (i / total_steps))
                step_progress_end = 0.4 + (0.4 * ((i + 1) / total_steps))

                # Determine action type for thinking messages
                action_type = step.action
                if "route" in step.file.lower():
                    action_type = "route"
                elif "migration" in step.file.lower():
                    action_type = "migration"
                elif "model" in step.file.lower():
                    action_type = "model"
                elif "controller" in step.file.lower():
                    action_type = "controller"

                # Emit step started
                await self._emit_event(step_started(
                    i,
                    step.to_dict(),
                    f"Working on step {step.order}: {step.description[:50]}...",
                    False,
                ))

                event = await self._emit_legacy_event(
                    ProcessPhase.EXECUTING,
                    f"Executing step {step.order}/{total_steps}: {step.description[:50]}...",
                    step_progress_start,
                    {
                        "step": step.to_dict(),
                        "step_status": "started",
                        "step_index": i,
                        "total_steps": total_steps,
                    },
                )
                result.events.append(event)

                # Emit thinking sequence for this step
                await self._emit_thinking_sequence(
                    FORGE,
                    action_type,
                    count=4,
                    delay=0.6,
                    file_path=step.file,
                    step_index=i,
                )

                # Get current file content for modify/delete
                current_content = None
                if step.action in ["modify", "delete"]:
                    current_content = await self._get_file_content(project_id, step.file)

                # Execute the step
                exec_result = await self.executor.execute_step(
                    step=step,
                    context=context,
                    previous_results=execution_results,
                    current_file_content=current_content,
                    project_context=project_context,
                )

                execution_results.append(exec_result)

                # Log execution
                if self.conversation_logger:
                    self.conversation_logger.log_execution_step(
                        step_number=i + 1,
                        total_steps=total_steps,
                        step_data=step.to_dict(),
                        result_data=exec_result.to_dict(),
                        generated_code=exec_result.content,
                        diff=exec_result.diff,
                    )

                # Emit step completed
                await self._emit_event(step_completed(
                    i,
                    step.to_dict(),
                    exec_result.to_dict(),
                    f"Step {step.order} {'completed' if exec_result.success else 'failed'}",
                    step_progress_end,
                ))

                event = await self._emit_legacy_event(
                    ProcessPhase.EXECUTING,
                    f"Step {step.order}/{total_steps} {'completed' if exec_result.success else 'failed'}: {step.file}",
                    step_progress_end,
                    {
                        "step": step.to_dict(),
                        "step_status": "completed",
                        "step_index": i,
                        "total_steps": total_steps,
                        "result": exec_result.to_dict(),
                    },
                )
                result.events.append(event)

                if not exec_result.success:
                    logger.warning(f"[INTERACTIVE_ORCHESTRATOR] Step {step.order} failed: {exec_result.error}")

            result.execution_results = execution_results

            await self._emit_event(execution_completed(
                total_steps,
                sum(1 for r in execution_results if r.success),
            ))

            await self._emit_event(agent_message(
                FORGE.agent_type.value,
                FORGE.name,
                FORGE.get_random_completion(),
                "completion",
            ))

            event = await self._emit_legacy_event(
                ProcessPhase.EXECUTING,
                f"Executed {len(execution_results)} steps",
                0.8,
            )
            result.events.append(event)

            # ============== PHASE 5: GUARDIAN - VALIDATION ==============
            await self._handoff(FORGE, GUARDIAN, {
                "files_changed": len(execution_results),
            })

            await self._emit_event(agent_message(
                GUARDIAN.agent_type.value,
                GUARDIAN.name,
                GUARDIAN.get_random_greeting(),
                "greeting",
            ))

            await self._emit_event(validation_started("Validating generated code..."))

            # Emit thinking sequence
            await self._emit_thinking_sequence(GUARDIAN, "validation", count=4)

            event = await self._emit_legacy_event(
                ProcessPhase.VALIDATING,
                "Validating generated code...",
                0.85,
            )
            result.events.append(event)

            # Actual validation
            validation = await self.validator.validate(
                user_input=user_input,
                intent=intent,
                results=execution_results,
                context=context,
            )
            result.validation = validation

            # Emit found issues one by one
            for issue in validation.issues:
                await self._emit_event(validation_issue_found(
                    issue.severity,
                    issue.file,
                    issue.message,
                    issue.line,
                    None,  # suggestion
                ))
                await asyncio.sleep(0.2)

            # Log validation
            if self.conversation_logger:
                self.conversation_logger.log_validation(validation.to_dict())

            # ============== FIX LOOP ==============
            initial_score = validation.score
            previous_score = initial_score
            retry_count = 0

            # Detect critical failure (e.g., file deleted entirely)
            is_critical_failure = initial_score <= self.config.CRITICAL_FAILURE_THRESHOLD

            while not validation.approved and retry_count < self.config.MAX_FIX_ATTEMPTS:
                retry_count += 1

                # Circuit breaker - but allow at least one fix attempt for critical failures
                if self.config.ABORT_ON_SCORE_DEGRADATION and retry_count > 1:
                    if validation.score < previous_score - self.config.SCORE_DEGRADATION_THRESHOLD:
                        await self._emit_event(agent_message(
                            GUARDIAN.agent_type.value,
                            GUARDIAN.name,
                            f"Fix attempts are making the code worse (score: {previous_score} -> {validation.score}). Stopping.",
                            "error",
                        ))
                        break

                    # Only apply MIN_VALIDATION_SCORE check after first attempt
                    # This ensures we always try at least once to fix, even critical failures
                    if validation.score < self.config.MIN_VALIDATION_SCORE and not is_critical_failure:
                        await self._emit_event(agent_message(
                            GUARDIAN.agent_type.value,
                            GUARDIAN.name,
                            f"Validation score too low ({validation.score}). Manual review required.",
                            "error",
                        ))
                        break

                # For critical failures on first attempt, emit a recovery message
                if is_critical_failure and retry_count == 1:
                    await self._emit_event(agent_message(
                        GUARDIAN.agent_type.value,
                        GUARDIAN.name,
                        f"Critical issue detected (score: {initial_score}). Attempting automatic recovery...",
                        "warning",
                    ))

                previous_score = validation.score

                # Emit fix started
                await self._emit_event(validation_fix_started(
                    len(validation.errors),
                    f"Starting fix attempt {retry_count}/{self.config.MAX_FIX_ATTEMPTS}...",
                ))

                # Handoff to Forge for fixes
                await self._handoff(GUARDIAN, FORGE, {
                    "issues": [i.to_dict() for i in validation.errors],
                    "fix_attempt": retry_count,
                })

                await self._emit_event(agent_message(
                    FORGE.agent_type.value,
                    FORGE.name,
                    f"On it! Fixing {len(validation.errors)} issues...",
                    "custom",
                ))

                event = await self._emit_legacy_event(
                    ProcessPhase.FIXING,
                    f"Fixing issues (attempt {retry_count}/{self.config.MAX_FIX_ATTEMPTS})...",
                    0.85 + (0.05 * retry_count),
                    {"issues": [i.to_dict() for i in validation.errors]},
                )
                result.events.append(event)

                # Fix logic (same as original orchestrator)
                all_issues = [i.message for i in validation.errors]

                def normalize_path(path: str) -> str:
                    if not path:
                        return ""
                    path = path.strip().replace("\\", "/")
                    if path.startswith("./"):
                        path = path[2:]
                    return path.lower()

                exec_result_paths = {
                    normalize_path(r.file): i
                    for i, r in enumerate(execution_results)
                }

                files_to_fix = set()

                for issue in validation.errors:
                    issue_file_norm = normalize_path(issue.file)
                    if issue_file_norm in exec_result_paths:
                        files_to_fix.add(exec_result_paths[issue_file_norm])
                    elif issue.file:
                        for norm_path, idx in exec_result_paths.items():
                            if issue_file_norm in norm_path or norm_path.endswith(issue_file_norm):
                                files_to_fix.add(idx)
                                break

                if not files_to_fix and validation.errors:
                    files_to_fix = set(range(len(execution_results)))

                for idx in files_to_fix:
                    exec_result = execution_results[idx]
                    if not exec_result.success:
                        continue

                    exec_file_norm = normalize_path(exec_result.file)
                    file_issues = [
                        issue.message
                        for issue in validation.errors
                        if normalize_path(issue.file) == exec_file_norm
                        or not issue.file
                        or normalize_path(issue.file) in exec_file_norm
                        or exec_file_norm.endswith(normalize_path(issue.file))
                    ]

                    if not file_issues:
                        file_issues = all_issues

                    if file_issues:
                        # Detect if file was completely deleted (critical failure)
                        file_was_deleted = (
                            is_critical_failure
                            and self.config.REGENERATE_ON_DELETION
                            and retry_count == 1
                            and any("deleted" in issue.lower() or "entire file" in issue.lower() for issue in file_issues)
                        )

                        if file_was_deleted:
                            # File was deleted - need to regenerate entirely
                            await self._emit_event(agent_message(
                                FORGE.agent_type.value,
                                FORGE.name,
                                f"File was incorrectly deleted. Regenerating {exec_result.file}...",
                                "warning",
                            ))

                            # Emit thinking for regeneration
                            await self._emit_thinking_sequence(
                                FORGE,
                                "create",
                                count=3,
                                delay=0.8,
                                file_path=exec_result.file,
                            )

                            # Regenerate the file using the executor with original intent
                            regeneration_issues = file_issues + [
                                "CRITICAL: The previous attempt deleted the entire file instead of modifying it.",
                                "You MUST preserve all existing functionality while making the requested changes.",
                                "Regenerate the complete file with proper styling changes as requested.",
                            ]

                            fixed = await self.executor.fix_execution(
                                result=exec_result,
                                issues=regeneration_issues,
                                context=context,
                            )
                        else:
                            # Normal fix attempt
                            await self._emit_thinking_sequence(
                                FORGE,
                                "modify",
                                count=2,
                                delay=0.5,
                                file_path=exec_result.file,
                            )

                            fixed = await self.executor.fix_execution(
                                result=exec_result,
                                issues=file_issues,
                                context=context,
                            )
                        execution_results[idx] = fixed

                result.execution_results = execution_results

                # Log fix attempt
                if self.conversation_logger:
                    fixed_files = [execution_results[idx].file for idx in files_to_fix if execution_results[idx].success]
                    self.conversation_logger.log_fix_attempt(
                        attempt_number=retry_count,
                        max_attempts=self.config.MAX_FIX_ATTEMPTS,
                        issues=all_issues,
                        fixed_files=fixed_files,
                    )

                await self._emit_event(validation_fix_completed(
                    len(files_to_fix),
                    len(validation.errors),
                ))

                # Handoff back to Guardian for re-validation
                await self._handoff(FORGE, GUARDIAN, {"fixed_files": len(files_to_fix)})

                await self._emit_event(agent_message(
                    GUARDIAN.agent_type.value,
                    GUARDIAN.name,
                    "Re-validating the fixes...",
                    "custom",
                ))

                # Re-validate
                validation = await self.validator.validate(
                    user_input=user_input,
                    intent=intent,
                    results=execution_results,
                    context=context,
                )
                result.validation = validation

                # Log re-validation
                if self.conversation_logger:
                    self.conversation_logger.log_validation(validation.to_dict())

            # ============== FINAL RESULT ==============
            await self._emit_event(validation_result(
                validation.to_dict(),
                "Validation complete",
                0.95,
            ))

            if validation.approved:
                await self._emit_event(agent_message(
                    GUARDIAN.agent_type.value,
                    GUARDIAN.name,
                    f"All checks passed! Score: {validation.score}/100",
                    "completion",
                ))

                event = await self._emit_legacy_event(
                    ProcessPhase.COMPLETED,
                    f"Completed successfully! Score: {validation.score}/100",
                    1.0,
                    {"validation": validation.to_dict()},
                )
                result.events.append(event)
                result.success = True
            else:
                await self._emit_event(agent_message(
                    GUARDIAN.agent_type.value,
                    GUARDIAN.name,
                    f"Completed with {len(validation.issues)} issues. Score: {validation.score}/100",
                    "completion",
                ))

                event = await self._emit_legacy_event(
                    ProcessPhase.COMPLETED,
                    f"Completed with warnings. Score: {validation.score}/100",
                    1.0,
                    {"validation": validation.to_dict()},
                )
                result.events.append(event)
                result.success = len(validation.errors) == 0

            # ============== CONDUCTOR WRAP-UP ==============
            await self._set_active_agent(CONDUCTOR)
            self.timeline.complete_current()

            await self._emit_event(agent_message(
                CONDUCTOR.agent_type.value,
                CONDUCTOR.name,
                CONDUCTOR.get_random_completion(),
                "completion",
            ))

            return result

        except Exception as e:
            logger.exception(f"[INTERACTIVE_ORCHESTRATOR] Processing failed: {e}")
            result.error = str(e)

            await self._emit_event(agent_message(
                CONDUCTOR.agent_type.value,
                CONDUCTOR.name,
                CONDUCTOR.get_random_error(),
                "error",
            ))

            await self._emit_event(error(str(e)))

            event = await self._emit_legacy_event(
                ProcessPhase.FAILED,
                f"Processing failed: {str(e)}",
                0.0,
            )
            result.events.append(event)

            return result

    async def _get_project(self, project_id: str) -> Optional[Project]:
        """Fetch project from database."""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_file_content(
        self,
        project_id: str,
        file_path: str,
    ) -> Optional[str]:
        """Get file content from indexed files."""
        stmt = select(IndexedFile).where(
            IndexedFile.project_id == project_id,
            IndexedFile.file_path == file_path,
        )
        result = await self.db.execute(stmt)
        indexed_file = result.scalar_one_or_none()

        if indexed_file and indexed_file.content:
            return indexed_file.content

        return None

    def build_project_context(self, project: Project) -> str:
        """Build rich project context from scan data."""
        # Use the same implementation from the base Orchestrator
        from app.agents.orchestrator import Orchestrator

        # Create a temporary orchestrator just to use the method
        temp = Orchestrator.__new__(Orchestrator)
        return Orchestrator.build_project_context(temp, project)

    async def process_question(
        self,
        project_id: str,
        question: str,
    ) -> tuple[Intent, RetrievedContext, str]:
        """
        Process a question (without code generation).

        Returns intent, context, and project context for the chat endpoint.
        """
        logger.info(f"[INTERACTIVE_ORCHESTRATOR] Processing question for project={project_id}")

        project = await self._get_project(project_id)
        project_context = ""
        if project:
            project_context = self.build_project_context(project)

        intent = await self.intent_analyzer.analyze(question, project_context)
        context = await self.context_retriever.retrieve(project_id, intent)

        return intent, context, project_context

    def get_timeline_summary(self) -> Dict[str, Any]:
        """Get the agent timeline summary."""
        return self.timeline.get_summary()
