"""
Orchestrator Agent.

Coordinates all agents to process user requests from start to finish.
Manages the workflow: analyze → retrieve → plan → execute → validate.
"""
import json
import logging
from typing import Optional, Callable, Any
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
from app.models.models import Project, IndexedFile
from app.services.claude import get_claude_service

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3


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
    """

    def __init__(
        self,
        db: AsyncSession,
        event_callback: Optional[Callable[[ProcessEvent], Any]] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            db: Database session
            event_callback: Optional callback for real-time events
        """
        self.db = db
        self.event_callback = event_callback

        # Initialize agents
        claude = get_claude_service()
        self.intent_analyzer = IntentAnalyzer(claude)
        self.context_retriever = ContextRetriever(db)
        self.planner = Planner(claude)
        self.executor = Executor(claude)
        self.validator = Validator(claude)

        logger.info("[ORCHESTRATOR] Initialized with all agents")

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
        Process a user request through the full pipeline.

        Args:
            project_id: The project UUID
            user_input: User's request text

        Returns:
            ProcessResult with all outputs
        """
        logger.info(f"[ORCHESTRATOR] Processing request for project={project_id}")
        logger.info(f"[ORCHESTRATOR] User input: {user_input[:200]}...")

        result = ProcessResult(success=False, events=[])

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

            event = await self._emit_event(
                ProcessPhase.ANALYZING,
                f"Identified task type: {intent.task_type}",
                0.15,
                {"intent": intent.to_dict()},
            )
            result.events.append(event)

            # 3. Retrieve context
            event = await self._emit_event(
                ProcessPhase.RETRIEVING,
                "Searching codebase for relevant context...",
                0.2,
            )
            result.events.append(event)

            context = await self.context_retriever.retrieve(project_id, intent)

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

            # 8. Retry if validation failed
            retry_count = 0
            while not validation.approved and retry_count < MAX_RETRY_ATTEMPTS:
                retry_count += 1

                event = await self._emit_event(
                    ProcessPhase.FIXING,
                    f"Fixing issues (attempt {retry_count}/{MAX_RETRY_ATTEMPTS})...",
                    0.85 + (0.05 * retry_count),
                    {"issues": [i.to_dict() for i in validation.errors]},
                )
                result.events.append(event)

                # Get error messages
                issues = [i.message for i in validation.errors]

                # Try to fix each problematic result
                for i, exec_result in enumerate(execution_results):
                    if not exec_result.success:
                        continue

                    # Check if this file has issues
                    file_issues = [
                        issue.message
                        for issue in validation.errors
                        if issue.file == exec_result.file
                    ]

                    if file_issues:
                        fixed = await self.executor.fix_execution(
                            result=exec_result,
                            issues=file_issues,
                            context=context,
                        )
                        execution_results[i] = fixed

                result.execution_results = execution_results

                # Re-validate
                validation = await self.validator.validate(
                    user_input=user_input,
                    intent=intent,
                    results=execution_results,
                    context=context,
                )
                result.validation = validation

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

        # Basic info
        parts.append(f"## Project: {project.repo_full_name}")
        parts.append("")

        # Technology Stack
        if project.stack:
            parts.append("### Technology Stack")
            stack = project.stack

            # Backend
            backend = stack.get("backend", {})
            if backend:
                framework = backend.get("framework", "unknown")
                version = backend.get("version", "")
                php_version = backend.get("php_version", "")
                parts.append(f"- **Backend Framework:** {framework} {version}".strip())
                if php_version:
                    parts.append(f"- **PHP Version:** {php_version}")

            # Frontend
            frontend = stack.get("frontend", {})
            if frontend:
                frontend_framework = frontend.get("framework", "")
                frontend_version = frontend.get("version", "")
                if frontend_framework:
                    parts.append(f"- **Frontend Framework:** {frontend_framework} {frontend_version}".strip())

            # Database
            database = stack.get("database", {})
            if database:
                db_type = database.get("type", "")
                if db_type:
                    parts.append(f"- **Database:** {db_type}")

            # Key packages
            packages = stack.get("packages", [])
            if packages:
                parts.append(f"- **Key Packages:** {', '.join(packages[:10])}")

            parts.append("")

        # File Statistics
        if project.file_stats:
            parts.append("### Codebase Statistics")
            stats = project.file_stats
            parts.append(f"- **Total Files:** {stats.get('total_files', 0)}")
            parts.append(f"- **Total Lines:** {stats.get('total_lines', 0):,}")

            by_type = stats.get("by_type", {})
            if by_type:
                type_summary = ", ".join([f"{k}: {v}" for k, v in list(by_type.items())[:5]])
                parts.append(f"- **By Type:** {type_summary}")

            parts.append("")

        # Project Structure
        if project.structure:
            parts.append("### Project Structure")
            structure = project.structure

            # Key directories
            directories = structure.get("directories", [])
            if directories:
                parts.append(f"- **Key Directories:** {', '.join(directories[:10])}")

            # Patterns detected
            patterns = structure.get("patterns_detected", [])
            if patterns:
                parts.append(f"- **Patterns Detected:** {', '.join(patterns)}")

            parts.append("")

        # Health Score
        if project.health_score is not None:
            parts.append(f"### Health Score: {project.health_score:.0f}/100")

            if project.health_check:
                health = project.health_check
                categories = health.get("categories", {})
                if categories:
                    parts.append("Category Scores:")
                    for cat, data in list(categories.items())[:6]:
                        score = data.get("score", 0) if isinstance(data, dict) else data
                        parts.append(f"  - {cat}: {score}/100")

                # Critical issues
                critical = health.get("critical_issues", 0)
                warnings = health.get("warnings", 0)
                if critical or warnings:
                    parts.append(f"- **Issues:** {critical} critical, {warnings} warnings")

            parts.append("")

        # AI Context (conventions, patterns)
        if project.ai_context:
            ai_ctx = project.ai_context

            # CLAUDE.md content (summary rules for AI)
            claude_md = ai_ctx.get("claude_md_content", "")
            if claude_md:
                parts.append("### Project Conventions (CLAUDE.md)")
                # Include first ~1500 chars of CLAUDE.md
                if len(claude_md) > 1500:
                    parts.append(claude_md[:1500] + "...")
                else:
                    parts.append(claude_md)
                parts.append("")

            # Coding conventions
            conventions = ai_ctx.get("conventions", {})
            if conventions:
                php_conv = conventions.get("php", {})
                vue_conv = conventions.get("vue", {})

                if php_conv or vue_conv:
                    parts.append("### Coding Conventions")

                    if php_conv:
                        naming = php_conv.get("naming_style", "")
                        if naming:
                            parts.append(f"- **PHP Naming:** {naming}")
                        uses_traits = php_conv.get("uses_traits", False)
                        if uses_traits:
                            parts.append("- **Uses Traits:** Yes")

                    if vue_conv:
                        vue_version = vue_conv.get("version", "")
                        api_style = vue_conv.get("api_style", "")
                        if vue_version:
                            parts.append(f"- **Vue Version:** {vue_version}")
                        if api_style:
                            parts.append(f"- **Vue API Style:** {api_style}")

                    parts.append("")

            # Key patterns
            patterns = ai_ctx.get("key_patterns", [])
            if patterns:
                parts.append("### Architecture Patterns")
                for pattern in patterns[:5]:
                    parts.append(f"- {pattern}")
                parts.append("")

            # Domain knowledge (models, routes)
            domain = ai_ctx.get("domain_knowledge", {})
            if domain:
                models = domain.get("models", [])
                if models:
                    parts.append(f"### Database Models")
                    parts.append(f"Available models: {', '.join(models[:15])}")
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
