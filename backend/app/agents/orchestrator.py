"""
Orchestrator Agent.

Coordinates all agents to process user requests from start to finish.
Manages the workflow: analyze → retrieve → plan → execute → validate.

UPDATED: Includes safety checks and circuit breakers.
"""
import json
import logging
from typing import Optional, Callable, Any, List
from dataclasses import dataclass, field
from enum import Enum
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
from app.models.models import Project, IndexedFile
from app.services.claude import ClaudeService, get_claude_service
from app.services.conversation_logger import ConversationLogger

logger = logging.getLogger(__name__)


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


@dataclass
class ProcessEvent:
    """Event emitted during processing for real-time UI updates."""

    phase: ProcessPhase
    message: str
    progress: float  # 0.0 to 1.0
    data: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "phase": self.phase.value,
            "message": self.message,
            "progress": self.progress,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ProcessResult:
    """Final result of processing a request."""

    success: bool
    intent: Optional[Intent] = None
    plan: Optional[Plan] = None
    execution_results: list[ExecutionResult] = field(default_factory=list)
    validation: Optional[ValidationResult] = None
    error: Optional[str] = None
    events: list[ProcessEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "intent": self.intent.to_dict() if self.intent else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "execution_results": [r.to_dict() for r in self.execution_results],
            "validation": self.validation.to_dict() if self.validation else None,
            "error": self.error,
            "events": [e.to_dict() for e in self.events],
        }


class Orchestrator:
    """
    Orchestrates the full request processing workflow.

    Coordinates all agents and manages retries on validation failures.

    UPDATED: Includes safety checks and circuit breakers.
    """

    def __init__(
        self,
        db: AsyncSession,
        event_callback: Optional[Callable[[ProcessEvent], Any]] = None,
        claude_service: Optional[ClaudeService] = None,
        conversation_logger: Optional[ConversationLogger] = None,
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            db: Database session
            event_callback: Optional callback for real-time events
            claude_service: Optional ClaudeService instance (with or without tracking).
                           If not provided, uses the default singleton.
            conversation_logger: Optional ConversationLogger for detailed conversation logging
            config: Optional agent configuration
        """
        self.db = db
        self.event_callback = event_callback
        self.conversation_logger = conversation_logger
        self.config = config or agent_config

        # Initialize agents with the Claude service and config
        claude = claude_service or get_claude_service()
        self.intent_analyzer = IntentAnalyzer(claude)
        self.context_retriever = ContextRetriever(db, config=self.config)
        self.planner = Planner(claude)
        self.executor = Executor(claude, config=self.config)
        self.validator = Validator(claude, config=self.config)

        tracking_info = "with tracking" if (claude_service and claude_service.tracker) else "without tracking"
        logging_info = "with conversation logging" if conversation_logger else "without conversation logging"
        logger.info(f"[ORCHESTRATOR] Initialized with all agents and safety features ({tracking_info}, {logging_info})")

    async def _emit_event(
        self,
        phase: ProcessPhase,
        message: str,
        progress: float,
        data: Optional[dict] = None,
    ) -> ProcessEvent:
        """Emit a processing event."""
        event = ProcessEvent(
            phase=phase,
            message=message,
            progress=progress,
            data=data,
        )

        logger.info(f"[ORCHESTRATOR] {phase.value}: {message} ({progress*100:.0f}%)")

        if self.event_callback:
            try:
                result = self.event_callback(event)
                # Handle async callbacks
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Event callback error: {e}")

        return event

    async def process_request(
        self,
        project_id: str,
        user_input: str,
    ) -> ProcessResult:
        """
        Process a user request through the full pipeline with safety checks.

        Args:
            project_id: The project UUID
            user_input: User's request text

        Returns:
            ProcessResult with all outputs
        """
        logger.info(f"[ORCHESTRATOR] Processing request for project={project_id}")
        logger.info(f"[ORCHESTRATOR] User input: {user_input[:200]}...")

        result = ProcessResult(success=False, events=[])

        # Clear validator history for new request
        self.validator.clear_history()

        try:
            # 1. Fetch project and build rich context
            project = await self._get_project(project_id)
            if not project:
                result.error = "Project not found"
                return result

            # Build rich context from scan data (stack, health, ai_context)
            project_context = self.build_project_context(project)
            logger.info(f"[ORCHESTRATOR] Built project context ({len(project_context)} chars)")

            # 2. Analyze intent
            event = await self._emit_event(
                ProcessPhase.ANALYZING,
                "Analyzing your request...",
                0.1,
            )
            result.events.append(event)

            intent = await self.intent_analyzer.analyze(user_input, project_context)
            result.intent = intent

            # Log intent analysis
            if self.conversation_logger:
                self.conversation_logger.log_intent_analysis(intent.to_dict())

            event = await self._emit_event(
                ProcessPhase.ANALYZING,
                f"Identified task type: {intent.task_type}",
                0.15,
                {"intent": intent.to_dict()},
            )
            result.events.append(event)

            # 3. Retrieve context (with safety check)
            event = await self._emit_event(
                ProcessPhase.RETRIEVING,
                "Searching codebase for relevant context...",
                0.2,
            )
            result.events.append(event)

            try:
                context = await self.context_retriever.retrieve(
                    project_id, intent,
                    require_minimum=self.config.ABORT_ON_NO_CONTEXT
                )
            except InsufficientContextError as e:
                # Handle insufficient context gracefully
                await self._emit_event(
                    ProcessPhase.FAILED,
                    f"Insufficient codebase context: {e.message}",
                    0.25
                )
                result.error = (
                    f"Unable to find relevant code in the project. "
                    f"Found {e.details['chunks_found']} code chunks. "
                    f"Please ensure the project is indexed and try a more specific request."
                )
                return result

            # Warn about low confidence
            if context.confidence_level == "low":
                event = await self._emit_event(
                    ProcessPhase.RETRIEVING,
                    f"⚠️ Limited context found ({len(context.chunks)} chunks). Proceeding with caution.",
                    0.25
                )
                result.events.append(event)

            # Log context retrieval
            if self.conversation_logger:
                chunks_data = [
                    {
                        "file_path": chunk.file_path,
                        "content": chunk.content[:500] if chunk.content else "",
                        "score": getattr(chunk, 'score', None),
                    }
                    for chunk in context.chunks[:20]  # Limit to 20 chunks
                ]
                self.conversation_logger.log_context_retrieval(
                    chunks_count=len(context.chunks),
                    chunks=chunks_data,
                    related_files=context.related_files if hasattr(context, 'related_files') else None,
                    domain_summaries=context.domain_summaries if hasattr(context, 'domain_summaries') else None,
                )

            event = await self._emit_event(
                ProcessPhase.RETRIEVING,
                f"Found {len(context.chunks)} relevant code sections",
                0.3,
                {"chunks_count": len(context.chunks)},
            )
            result.events.append(event)

            # 4. Handle questions differently
            if intent.task_type == "question":
                # For questions, we just return the context
                # The chat endpoint will handle generating the response
                event = await self._emit_event(
                    ProcessPhase.COMPLETED,
                    "Context retrieved for question",
                    1.0,
                )
                result.events.append(event)
                result.success = True
                return result

            # 5. Create plan
            event = await self._emit_event(
                ProcessPhase.PLANNING,
                "Creating implementation plan...",
                0.35,
            )
            result.events.append(event)

            plan = await self.planner.plan(user_input, intent, context, project_context)
            result.plan = plan

            # Log plan creation
            if self.conversation_logger:
                self.conversation_logger.log_plan(plan.to_dict())

            event = await self._emit_event(
                ProcessPhase.PLANNING,
                f"Plan created with {len(plan.steps)} steps",
                0.4,
                {"plan": plan.to_dict()},
            )
            result.events.append(event)

            if not plan.steps:
                result.error = "Could not create a valid plan"
                event = await self._emit_event(
                    ProcessPhase.FAILED,
                    "Planning failed - no steps generated",
                    0.4,
                )
                result.events.append(event)
                return result

            # 6. Execute steps
            execution_results = []
            total_steps = len(plan.steps)

            for i, step in enumerate(plan.steps):
                step_progress_start = 0.4 + (0.4 * (i / total_steps))
                step_progress_end = 0.4 + (0.4 * ((i + 1) / total_steps))

                # Emit step_started event
                event = await self._emit_event(
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

                # Get current file content for modify/delete
                current_content = None
                if step.action in ["modify", "delete"]:
                    current_content = await self._get_file_content(project_id, step.file)

                exec_result = await self.executor.execute_step(
                    step=step,
                    context=context,
                    previous_results=execution_results,
                    current_file_content=current_content,
                    project_context=project_context,
                )

                execution_results.append(exec_result)

                # Log execution step
                if self.conversation_logger:
                    self.conversation_logger.log_execution_step(
                        step_number=i + 1,
                        total_steps=total_steps,
                        step_data=step.to_dict(),
                        result_data=exec_result.to_dict(),
                        generated_code=exec_result.content,
                        diff=exec_result.diff,
                    )

                # Emit step_completed event with result data
                event = await self._emit_event(
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
                    logger.warning(f"[ORCHESTRATOR] Step {step.order} failed: {exec_result.error}")

            result.execution_results = execution_results

            event = await self._emit_event(
                ProcessPhase.EXECUTING,
                f"Executed {len(execution_results)} steps",
                0.8,
            )
            result.events.append(event)

            # 7. Validate results
            event = await self._emit_event(
                ProcessPhase.VALIDATING,
                "Validating generated code...",
                0.85,
            )
            result.events.append(event)

            validation = await self.validator.validate(
                user_input=user_input,
                intent=intent,
                results=execution_results,
                context=context,
            )
            result.validation = validation

            # Log validation
            if self.conversation_logger:
                self.conversation_logger.log_validation(validation.to_dict())

            # 8. Retry if validation failed (with circuit breaker)
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
                        logger.error(
                            f"[ORCHESTRATOR] Score degraded: {previous_score} -> {validation.score}. Aborting."
                        )
                        event = await self._emit_event(
                            ProcessPhase.FAILED,
                            f"Fix attempts are making code worse (score: {previous_score} → {validation.score})",
                            0.9
                        )
                        result.events.append(event)
                        break

                    # Only apply MIN_VALIDATION_SCORE check after first attempt
                    if validation.score < self.config.MIN_VALIDATION_SCORE and not is_critical_failure:
                        logger.error(f"[ORCHESTRATOR] Score too low: {validation.score}. Aborting.")
                        event = await self._emit_event(
                            ProcessPhase.FAILED,
                            f"Validation score too low ({validation.score}). Manual review required.",
                            0.9
                        )
                        result.events.append(event)
                        break

                # Log critical failure recovery attempt
                if is_critical_failure and retry_count == 1:
                    logger.warning(f"[ORCHESTRATOR] Critical failure detected (score={initial_score}). Attempting recovery...")

                previous_score = validation.score

                event = await self._emit_event(
                    ProcessPhase.FIXING,
                    f"Fixing issues (attempt {retry_count}/{self.config.MAX_FIX_ATTEMPTS})...",
                    0.85 + (0.05 * retry_count),
                    {"issues": [i.to_dict() for i in validation.errors]},
                )
                result.events.append(event)

                # Get all error messages for context
                all_issues = [i.message for i in validation.errors]

                # Normalize file paths for comparison (handle different formats)
                def normalize_path(path: str) -> str:
                    """Normalize file path for comparison."""
                    if not path:
                        return ""
                    # Remove leading/trailing whitespace
                    path = path.strip()
                    # Normalize slashes
                    path = path.replace("\\", "/")
                    # Remove leading ./
                    if path.startswith("./"):
                        path = path[2:]
                    # Lowercase for comparison
                    return path.lower()

                # Create a map of normalized paths to original paths
                exec_result_paths = {
                    normalize_path(r.file): i
                    for i, r in enumerate(execution_results)
                }

                # Track which files need fixing
                files_to_fix = set()

                # Try to fix each problematic result
                for issue in validation.errors:
                    issue_file_norm = normalize_path(issue.file)

                    # Find matching execution result
                    if issue_file_norm in exec_result_paths:
                        files_to_fix.add(exec_result_paths[issue_file_norm])
                    elif issue.file:
                        # Try partial matching (e.g., "api.php" matches "routes/api.php")
                        for norm_path, idx in exec_result_paths.items():
                            if issue_file_norm in norm_path or norm_path.endswith(issue_file_norm):
                                files_to_fix.add(idx)
                                break

                # If no files matched but we have errors, try to fix all execution results
                if not files_to_fix and validation.errors:
                    logger.warning("[ORCHESTRATOR] No specific files matched errors, attempting to fix all")
                    files_to_fix = set(range(len(execution_results)))

                # Fix each identified file
                for idx in files_to_fix:
                    exec_result = execution_results[idx]
                    if not exec_result.success:
                        continue

                    # Get file-specific issues plus general issues (without a file)
                    exec_file_norm = normalize_path(exec_result.file)
                    file_issues = [
                        issue.message
                        for issue in validation.errors
                        if normalize_path(issue.file) == exec_file_norm
                        or not issue.file  # Include issues without a specific file
                        or normalize_path(issue.file) in exec_file_norm
                        or exec_file_norm.endswith(normalize_path(issue.file))
                    ]

                    # If no specific issues, provide all error messages as context
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
                            logger.warning(f"[ORCHESTRATOR] File {exec_result.file} was incorrectly deleted. Regenerating...")
                            # Regenerate the file with critical context
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
                            logger.info(f"[ORCHESTRATOR] Fixing {exec_result.file} with {len(file_issues)} issues")
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

                logger.info(f"[ORCHESTRATOR] Retry {retry_count}: approved={validation.approved}, score={validation.score}")

            # 9. Final status
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
                event = await self._emit_event(
                    ProcessPhase.COMPLETED,
                    f"Completed with warnings. Score: {validation.score}/100",
                    1.0,
                    {"validation": validation.to_dict()},
                )
                result.events.append(event)
                # Still mark as success if only warnings remain
                result.success = len(validation.errors) == 0

            return result

        except Exception as e:
            logger.exception(f"[ORCHESTRATOR] Processing failed: {e}")
            result.error = str(e)

            event = await self._emit_event(
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
        """
        Build rich project context from scan data for AI prompts.

        This provides the AI with accurate information about the project's
        technology stack, structure, patterns, and conventions to avoid
        hallucinations and generate code that matches the codebase.

        Args:
            project: Project model with scan data

        Returns:
            Formatted string with project context
        """
        parts = []

        # Helper to safely get dict values
        def safe_get(obj, key, default=None):
            """Safely get a value from dict, handling str/None cases."""
            if obj is None:
                return default
            if isinstance(obj, str):
                # Try to parse as JSON if it's a string
                try:
                    obj = json.loads(obj)
                except (json.JSONDecodeError, TypeError):
                    return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return default

        # Basic info
        parts.append(f"## Project: {project.repo_full_name}")
        parts.append("")

        # Technology Stack
        stack = project.stack
        if stack:
            # Handle if stack is a string (JSON)
            if isinstance(stack, str):
                try:
                    stack = json.loads(stack)
                except (json.JSONDecodeError, TypeError):
                    stack = {}

            if isinstance(stack, dict):
                parts.append("### Technology Stack")

                # Backend
                backend = safe_get(stack, "backend", {})
                if isinstance(backend, dict) and backend:
                    framework = safe_get(backend, "framework", "unknown")
                    version = safe_get(backend, "version", "")
                    php_version = safe_get(backend, "php_version", "")
                    parts.append(f"- **Backend Framework:** {framework} {version}".strip())
                    if php_version:
                        parts.append(f"- **PHP Version:** {php_version}")

                # Frontend
                frontend = safe_get(stack, "frontend", {})
                if isinstance(frontend, dict) and frontend:
                    frontend_framework = safe_get(frontend, "framework", "")
                    frontend_version = safe_get(frontend, "version", "")
                    if frontend_framework:
                        parts.append(f"- **Frontend Framework:** {frontend_framework} {frontend_version}".strip())

                # Database
                database = safe_get(stack, "database", {})
                if isinstance(database, dict) and database:
                    db_type = safe_get(database, "type", "")
                    if db_type:
                        parts.append(f"- **Database:** {db_type}")

                # Key packages
                packages = safe_get(stack, "packages", [])
                if isinstance(packages, list) and packages:
                    parts.append(f"- **Key Packages:** {', '.join(str(p) for p in packages[:10])}")

                parts.append("")

        # File Statistics
        file_stats = project.file_stats
        if file_stats:
            if isinstance(file_stats, str):
                try:
                    file_stats = json.loads(file_stats)
                except (json.JSONDecodeError, TypeError):
                    file_stats = {}

            if isinstance(file_stats, dict):
                parts.append("### Codebase Statistics")
                total_files = safe_get(file_stats, 'total_files', 0)
                total_lines = safe_get(file_stats, 'total_lines', 0)
                parts.append(f"- **Total Files:** {total_files}")
                parts.append(f"- **Total Lines:** {total_lines:,}" if isinstance(total_lines, int) else f"- **Total Lines:** {total_lines}")

                by_type = safe_get(file_stats, "by_type", {})
                if isinstance(by_type, dict) and by_type:
                    type_summary = ", ".join([f"{k}: {v}" for k, v in list(by_type.items())[:5]])
                    parts.append(f"- **By Type:** {type_summary}")

                parts.append("")

        # Project Structure
        structure = project.structure
        if structure:
            if isinstance(structure, str):
                try:
                    structure = json.loads(structure)
                except (json.JSONDecodeError, TypeError):
                    structure = {}

            if isinstance(structure, dict):
                parts.append("### Project Structure")

                # Key directories
                directories = safe_get(structure, "directories", [])
                if isinstance(directories, list) and directories:
                    parts.append(f"- **Key Directories:** {', '.join(str(d) for d in directories[:10])}")

                # Patterns detected
                patterns = safe_get(structure, "patterns_detected", [])
                if isinstance(patterns, list) and patterns:
                    parts.append(f"- **Patterns Detected:** {', '.join(str(p) for p in patterns)}")

                parts.append("")

        # Health Score
        if project.health_score is not None:
            try:
                parts.append(f"### Health Score: {float(project.health_score):.0f}/100")
            except (ValueError, TypeError):
                parts.append(f"### Health Score: {project.health_score}/100")

            health_check = project.health_check
            if health_check:
                if isinstance(health_check, str):
                    try:
                        health_check = json.loads(health_check)
                    except (json.JSONDecodeError, TypeError):
                        health_check = {}

                if isinstance(health_check, dict):
                    categories = safe_get(health_check, "categories", {})
                    if isinstance(categories, dict) and categories:
                        parts.append("Category Scores:")
                        for cat, data in list(categories.items())[:6]:
                            score = safe_get(data, "score", 0) if isinstance(data, dict) else data
                            parts.append(f"  - {cat}: {score}/100")

                    # Critical issues
                    critical = safe_get(health_check, "critical_issues", 0)
                    warnings = safe_get(health_check, "warnings", 0)
                    if critical or warnings:
                        parts.append(f"- **Issues:** {critical} critical, {warnings} warnings")

            parts.append("")

        # AI Context (conventions, patterns)
        ai_context = project.ai_context
        if ai_context:
            if isinstance(ai_context, str):
                try:
                    ai_context = json.loads(ai_context)
                except (json.JSONDecodeError, TypeError):
                    ai_context = {}

            if isinstance(ai_context, dict):
                # CLAUDE.md content (summary rules for AI)
                claude_md = safe_get(ai_context, "claude_md_content", "")
                if claude_md and isinstance(claude_md, str):
                    parts.append("### Project Conventions (CLAUDE.md)")
                    # Include first ~1500 chars of CLAUDE.md
                    if len(claude_md) > 1500:
                        parts.append(claude_md[:1500] + "...")
                    else:
                        parts.append(claude_md)
                    parts.append("")

                # Coding conventions
                conventions = safe_get(ai_context, "conventions", {})
                if isinstance(conventions, dict) and conventions:
                    php_conv = safe_get(conventions, "php", {})
                    vue_conv = safe_get(conventions, "vue", {})

                    if (isinstance(php_conv, dict) and php_conv) or (isinstance(vue_conv, dict) and vue_conv):
                        parts.append("### Coding Conventions")

                        if isinstance(php_conv, dict) and php_conv:
                            naming = safe_get(php_conv, "naming_style", "")
                            if naming:
                                parts.append(f"- **PHP Naming:** {naming}")
                            uses_traits = safe_get(php_conv, "uses_traits", False)
                            if uses_traits:
                                parts.append("- **Uses Traits:** Yes")

                        if isinstance(vue_conv, dict) and vue_conv:
                            vue_version = safe_get(vue_conv, "version", "")
                            api_style = safe_get(vue_conv, "api_style", "")
                            if vue_version:
                                parts.append(f"- **Vue Version:** {vue_version}")
                            if api_style:
                                parts.append(f"- **Vue API Style:** {api_style}")

                        parts.append("")

                # Key patterns
                patterns = safe_get(ai_context, "key_patterns", [])
                if isinstance(patterns, list) and patterns:
                    parts.append("### Architecture Patterns")
                    for pattern in patterns[:5]:
                        parts.append(f"- {pattern}")
                    parts.append("")

                # Domain knowledge (models, routes)
                domain = safe_get(ai_context, "domain_knowledge", {})
                if isinstance(domain, dict) and domain:
                    models = safe_get(domain, "models", [])
                    if isinstance(models, list) and models:
                        parts.append(f"### Database Models")
                        parts.append(f"Available models: {', '.join(str(m) for m in models[:15])}")
                        parts.append("")

        return "\n".join(parts)

    async def process_question(
        self,
        project_id: str,
        question: str,
    ) -> tuple[Intent, RetrievedContext, str]:
        """
        Process a question (without code generation).

        Returns intent, context, and project context for the chat endpoint to use.

        Args:
            project_id: The project UUID
            question: User's question

        Returns:
            Tuple of (Intent, RetrievedContext, project_context_string)
        """
        logger.info(f"[ORCHESTRATOR] Processing question for project={project_id}")

        # Get project and build rich context
        project = await self._get_project(project_id)
        project_context = ""
        if project:
            project_context = self.build_project_context(project)
            logger.info(f"[ORCHESTRATOR] Built question context ({len(project_context)} chars)")

        # Analyze intent
        intent = await self.intent_analyzer.analyze(question, project_context)

        # Retrieve context
        context = await self.context_retriever.retrieve(project_id, intent)

        return intent, context, project_context
