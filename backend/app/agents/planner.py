"""
Blueprint - Planner Agent (v2 Enhanced)

Creates execution plans for implementing features, fixes, and refactors.
Uses Claude Sonnet with Structured Outputs for guaranteed schema compliance.

Key Features:
- Pydantic-based structured outputs for plan validation
- Chain-of-thought reasoning captured in plan
- Dependency graph validation (no circular deps)
- Confidence and risk scoring
- No-guessing policy with clarification support
- Retry with exponential backoff (max 2 retries)
- Integration with Nova's intent and Scout's context
- Laravel-specific conventions enforcement
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from pydantic import ValidationError

from app.agents.agent_identity import AgentType, get_agent
from app.agents.intent_analyzer import Intent
from app.agents.context_retriever import RetrievedContext
from app.agents.plan_schema import (
    PlanOutput,
    PlanStepOutput,
    PlanReasoningOutput,
    ActionType,
    StepCategory,
    RiskLevel,
    get_plan_json_schema,
    validate_dependency_order,
    CATEGORY_ORDER,
)
from app.agents.blueprint_system_prompt import (
    BLUEPRINT_SYSTEM_PROMPT,
    BLUEPRINT_USER_PROMPT_TEMPLATE,
)
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 2
INITIAL_RETRY_DELAY = 1.0  # seconds
CONFIDENCE_THRESHOLD_FOR_CLARIFICATION = 0.5

MODEL_MAP = {
    "haiku": ClaudeModel.HAIKU,
    "sonnet": ClaudeModel.SONNET,
    "opus": ClaudeModel.OPUS,
}


def extract_json(text: str) -> Optional[dict]:
    """
    Extract JSON object from text that may contain markdown or other content.

    Handles various formats:
    - Pure JSON
    - JSON in ```json code blocks
    - JSON in ``` code blocks
    - JSON surrounded by text
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code block
    code_block_patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'```json(.*?)```',
        r'```(.*?)```',
    ]

    for pattern in code_block_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # Try to find JSON object by looking for { ... }
    first_brace = text.find('{')
    last_brace = text.rfind('}')

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            pass

    return None


def safe_format(template: str, **kwargs) -> str:
    """
    Safely format a string template with values that may contain curly braces.
    """
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    return result


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    order: int
    action: str  # create, modify, delete
    file: str
    description: str
    category: str = "other"
    depends_on: list[int] = field(default_factory=list)
    estimated_lines: int = 50

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlanStep":
        """Create from dictionary."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return cls(order=0, action="modify", file="", description=data)

        if not isinstance(data, dict):
            return cls(order=0, action="modify", file="", description=str(data))

        return cls(
            order=data.get("order", 0),
            action=data.get("action", "modify"),
            file=data.get("file", ""),
            description=data.get("description", ""),
            category=data.get("category", "other"),
            depends_on=data.get("depends_on", []),
            estimated_lines=data.get("estimated_lines", 50),
        )

    @classmethod
    def from_output(cls, output: PlanStepOutput) -> "PlanStep":
        """Create from validated PlanStepOutput."""
        return cls(
            order=output.order,
            action=output.action,
            file=output.file,
            description=output.description,
            category=output.category,
            depends_on=output.depends_on,
            estimated_lines=output.estimated_lines,
        )


@dataclass
class PlanReasoning:
    """Chain-of-thought reasoning for the plan."""

    understanding: str = ""
    approach: str = ""
    dependency_analysis: str = ""
    risks_considered: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_output(cls, output: PlanReasoningOutput) -> "PlanReasoning":
        return cls(
            understanding=output.understanding,
            approach=output.approach,
            dependency_analysis=output.dependency_analysis,
            risks_considered=output.risks_considered,
        )


@dataclass
class Plan:
    """An execution plan for implementing a request."""

    summary: str
    steps: list[PlanStep] = field(default_factory=list)

    # Reasoning (chain-of-thought)
    reasoning: Optional[PlanReasoning] = None

    # Quality metrics
    overall_confidence: float = 0.0
    risk_level: str = "medium"
    estimated_complexity: int = 5

    # Clarification handling
    needs_clarification: bool = False
    clarifying_questions: list[str] = field(default_factory=list)

    # Warnings
    warnings: list[str] = field(default_factory=list)

    # Metadata
    planning_time_ms: int = 0
    retry_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "summary": self.summary,
            "steps": [step.to_dict() for step in self.steps],
            "reasoning": self.reasoning.to_dict() if self.reasoning else None,
            "overall_confidence": self.overall_confidence,
            "risk_level": self.risk_level,
            "estimated_complexity": self.estimated_complexity,
            "needs_clarification": self.needs_clarification,
            "clarifying_questions": self.clarifying_questions,
            "warnings": self.warnings,
            "planning_time_ms": self.planning_time_ms,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        """Create from dictionary (for backwards compatibility)."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return cls(summary=data, steps=[])

        if not isinstance(data, dict):
            return cls(summary=str(data), steps=[])

        steps_data = data.get("steps", [])
        if not isinstance(steps_data, list):
            steps_data = []

        steps = [PlanStep.from_dict(s) for s in steps_data]

        reasoning_data = data.get("reasoning")
        reasoning = None
        if reasoning_data and isinstance(reasoning_data, dict):
            reasoning = PlanReasoning(
                understanding=reasoning_data.get("understanding", ""),
                approach=reasoning_data.get("approach", ""),
                dependency_analysis=reasoning_data.get("dependency_analysis", ""),
                risks_considered=reasoning_data.get("risks_considered", ""),
            )

        return cls(
            summary=data.get("summary", ""),
            steps=sorted(steps, key=lambda s: s.order),
            reasoning=reasoning,
            overall_confidence=data.get("overall_confidence", 0.0),
            risk_level=data.get("risk_level", "medium"),
            estimated_complexity=data.get("estimated_complexity", 5),
            needs_clarification=data.get("needs_clarification", False),
            clarifying_questions=data.get("clarifying_questions", []),
            warnings=data.get("warnings", []),
        )

    @classmethod
    def from_output(
        cls,
        output: PlanOutput,
        planning_time_ms: int = 0,
        retry_count: int = 0,
    ) -> "Plan":
        """Create Plan from validated PlanOutput."""
        return cls(
            summary=output.summary,
            steps=[PlanStep.from_output(s) for s in output.steps],
            reasoning=PlanReasoning.from_output(output.reasoning),
            overall_confidence=output.overall_confidence,
            risk_level=output.risk_level,
            estimated_complexity=output.estimated_complexity,
            needs_clarification=output.needs_clarification,
            clarifying_questions=output.clarifying_questions,
            warnings=output.warnings,
            planning_time_ms=planning_time_ms,
            retry_count=retry_count,
        )

    @classmethod
    def clarification_required(
        cls,
        questions: list[str],
        reasoning: str = "Insufficient information to create plan",
    ) -> "Plan":
        """Create a Plan that requires clarification (pipeline should prompt user)."""
        return cls(
            summary="Cannot create plan - clarification needed",
            steps=[],
            reasoning=PlanReasoning(
                understanding="Request requires clarification",
                approach=reasoning,
                dependency_analysis="N/A",
                risks_considered="Risk of incorrect implementation without clarity",
            ),
            overall_confidence=0.2,
            risk_level="medium",
            estimated_complexity=1,
            needs_clarification=True,
            clarifying_questions=questions,
        )

    @classmethod
    def error_fallback(cls, error_message: str) -> "Plan":
        """Create a fallback Plan on unrecoverable error."""
        return cls(
            summary=f"Planning failed: {error_message}",
            steps=[],
            reasoning=PlanReasoning(
                understanding="Error occurred during planning",
                approach=f"Error: {error_message}",
                dependency_analysis="N/A",
                risks_considered="Cannot assess risks due to error",
            ),
            overall_confidence=0.0,
            risk_level="high",
            estimated_complexity=1,
            needs_clarification=True,
            clarifying_questions=[
                "I encountered an error creating the plan. Could you rephrase your request?",
                "What specific outcome are you trying to achieve?",
            ],
        )

    def should_halt_pipeline(self) -> bool:
        """Check if pipeline should halt for clarification."""
        return (
            self.needs_clarification or
            self.overall_confidence < CONFIDENCE_THRESHOLD_FOR_CLARIFICATION or
            len(self.steps) == 0
        )

    def get_files_to_create(self) -> list[str]:
        """Get list of files that will be created."""
        return [s.file for s in self.steps if s.action == "create"]

    def get_files_to_modify(self) -> list[str]:
        """Get list of files that will be modified."""
        return [s.file for s in self.steps if s.action == "modify"]

    def total_estimated_lines(self) -> int:
        """Get total estimated lines of code."""
        return sum(s.estimated_lines for s in self.steps)


class Planner:
    """
    Blueprint - Creates execution plans for code changes.

    Uses Claude Sonnet with Structured Outputs for guaranteed schema compliance.
    Implements chain-of-thought reasoning for better plan quality.
    """

    def __init__(self, claude_service: Optional[ClaudeService] = None):
        """
        Initialize the planner.

        Args:
            claude_service: Optional Claude service instance.
        """
        self.claude = claude_service or get_claude_service()
        self.identity = get_agent(AgentType.BLUEPRINT)
        self._schema = get_plan_json_schema()

        logger.info(f"[{self.identity.name.upper()}] Initialized with Sonnet + Structured Outputs")

    def _build_user_prompt(
        self,
        user_input: str,
        intent: Intent,
        context: RetrievedContext,
        project_context: str = "",
    ) -> str:
        """
        Build the user prompt with all context.

        Args:
            user_input: Original user request
            intent: Analyzed intent from Nova
            context: Retrieved codebase context from Scout
            project_context: Rich project context

        Returns:
            Formatted user prompt
        """
        # Extract entities from intent
        entities = intent.entities if isinstance(intent.entities, dict) else {}

        return safe_format(
            BLUEPRINT_USER_PROMPT_TEMPLATE,
            user_input=user_input,
            task_type=intent.task_type,
            scope=intent.scope,
            domains=", ".join(intent.domains_affected) or "general",
            priority=intent.priority,
            requires_migration="Yes" if intent.requires_migration else "No",
            intent_confidence=f"{intent.overall_confidence:.2f}",
            entity_files=", ".join(entities.get("files", [])) or "None specified",
            entity_classes=", ".join(entities.get("classes", [])) or "None specified",
            entity_methods=", ".join(entities.get("methods", [])) or "None specified",
            entity_routes=", ".join(entities.get("routes", [])) or "None specified",
            entity_tables=", ".join(entities.get("tables", [])) or "None specified",
            project_context=project_context or "No project context available",
            retrieved_context=context.to_prompt_string(),
        )

    async def plan(
        self,
        user_input: str,
        intent: Intent,
        context: RetrievedContext,
        project_context: str = "",
    ) -> Plan:
        """
        Create an execution plan.

        Args:
            user_input: Original user request
            intent: Analyzed intent from Nova
            context: Retrieved codebase context from Scout
            project_context: Rich project context (stack, conventions, etc.)

        Returns:
            Plan with ordered steps

        Note:
            If needs_clarification=True, the pipeline should prompt the user.
            Check plan.should_halt_pipeline() before proceeding to execution.
        """
        start_time = time.time()

        logger.info(f"[{self.identity.name.upper()}] {self.identity.get_random_greeting()}")
        logger.info(f"[{self.identity.name.upper()}] Creating plan for: {user_input[:100]}...")

        # Build the user prompt
        user_prompt = self._build_user_prompt(
            user_input=user_input,
            intent=intent,
            context=context,
            project_context=project_context,
        )

        # Attempt planning with retries
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                plan = await self._call_claude_structured(
                    user_prompt=user_prompt,
                    attempt=attempt,
                )

                # Calculate timing
                planning_time_ms = int((time.time() - start_time) * 1000)
                plan.planning_time_ms = planning_time_ms
                plan.retry_count = attempt

                # Validate dependency order and add warnings
                if plan.steps:
                    step_outputs = [
                        PlanStepOutput(
                            order=s.order,
                            action=ActionType(s.action),
                            file=s.file,
                            category=StepCategory(s.category) if s.category in [e.value for e in StepCategory] else StepCategory.OTHER,
                            description=s.description,
                            depends_on=s.depends_on,
                            estimated_lines=s.estimated_lines,
                        )
                        for s in plan.steps
                    ]
                    order_warnings = validate_dependency_order(step_outputs)
                    plan.warnings.extend(order_warnings)

                # Log result
                self._log_plan_result(plan)

                return plan

            except Exception as e:
                last_error = e
                logger.warning(
                    f"[{self.identity.name.upper()}] Attempt {attempt + 1}/{MAX_RETRIES + 1} failed: {e}"
                )

                if attempt < MAX_RETRIES:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    logger.info(f"[{self.identity.name.upper()}] Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        # All retries failed
        logger.error(f"[{self.identity.name.upper()}] All retries exhausted. Error: {last_error}")

        planning_time_ms = int((time.time() - start_time) * 1000)
        fallback = Plan.error_fallback(str(last_error))
        fallback.planning_time_ms = planning_time_ms
        fallback.retry_count = MAX_RETRIES

        return fallback

    async def _call_claude_structured(self, user_prompt: str, attempt: int) -> Plan:
        """
        Call Claude with structured output expectations.

        Args:
            user_prompt: The formatted user prompt
            attempt: Current attempt number (for logging)

        Returns:
            Validated Plan object
        """
        logger.debug(f"[{self.identity.name.upper()}] {self.identity.get_random_thinking()}")

        messages = [{"role": "user", "content": user_prompt}]

        # Use Claude service with caching for system prompt
        response = await self.claude.chat_async(
            model=MODEL_MAP.get(settings.blueprint_model, ClaudeModel.SONNET),
            messages=messages,
            system=BLUEPRINT_SYSTEM_PROMPT,
            temperature=0.5,  # Slightly higher for creative planning
            max_tokens=4096,
            request_type="planning",
            use_cache=True,  # Cache the static system prompt
        )

        # Parse and validate response
        plan_output = self._parse_and_validate(response)
        return Plan.from_output(plan_output)

    def _parse_and_validate(self, response: str) -> PlanOutput:
        """
        Parse Claude's response and validate against schema.

        Args:
            response: Raw response from Claude

        Returns:
            Validated PlanOutput

        Raises:
            ValueError: If response cannot be parsed or validated
        """
        if not response:
            raise ValueError("Empty response from Claude")

        # Extract JSON from response
        plan_data = extract_json(response)

        if not plan_data:
            logger.error(f"[{self.identity.name.upper()}] Could not extract JSON")
            logger.error(f"[{self.identity.name.upper()}] Raw (first 500): {response[:500]}")
            raise ValueError("Could not extract JSON from response")

        # Validate with Pydantic
        try:
            plan_output = PlanOutput.model_validate(plan_data)
            logger.info(f"[{self.identity.name.upper()}] Schema validation passed")
            return plan_output

        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            logger.error(f"[{self.identity.name.upper()}] Validation failed: {errors}")

            # Try to create a partial plan from what we have
            partial_plan = self._create_partial_plan(plan_data, errors)
            if partial_plan:
                return partial_plan

            raise ValueError(f"Schema validation failed: {errors}")

    def _create_partial_plan(
        self,
        data: dict,
        errors: list[str],
    ) -> Optional[PlanOutput]:
        """
        Attempt to create a partial plan from invalid data.

        Used when validation fails but we have usable data.
        """
        try:
            # Try to fix common issues
            steps = data.get("steps", [])
            if steps:
                # Ensure steps have required fields
                fixed_steps = []
                for i, step in enumerate(steps):
                    if isinstance(step, dict):
                        fixed_step = {
                            "order": step.get("order", i + 1),
                            "action": step.get("action", "modify"),
                            "file": step.get("file", "unknown"),
                            "category": step.get("category", "other"),
                            "description": step.get("description", "No description"),
                            "depends_on": step.get("depends_on", []),
                            "estimated_lines": step.get("estimated_lines", 50),
                        }
                        fixed_steps.append(fixed_step)

                data["steps"] = fixed_steps

            # Ensure reasoning exists
            if "reasoning" not in data or not data["reasoning"]:
                data["reasoning"] = {
                    "understanding": "Recovered from partial data",
                    "approach": "Plan may be incomplete",
                    "dependency_analysis": "Unable to fully analyze",
                    "risks_considered": "Validation errors occurred",
                }

            # Set defaults for missing fields
            data.setdefault("summary", "Plan recovered from partial data")
            data.setdefault("overall_confidence", 0.5)
            data.setdefault("risk_level", "medium")
            data.setdefault("estimated_complexity", 5)
            data.setdefault("needs_clarification", False)
            data.setdefault("clarifying_questions", [])
            data.setdefault("warnings", [f"Plan recovered with validation issues: {errors[:2]}"])

            return PlanOutput.model_validate(data)

        except Exception as e:
            logger.warning(f"[{self.identity.name.upper()}] Could not create partial plan: {e}")
            return None

    def _log_plan_result(self, plan: Plan) -> None:
        """Log the planning result."""
        logger.info(f"[{self.identity.name.upper()}] {self.identity.get_random_completion()}")
        logger.info(f"[{self.identity.name.upper()}] Summary: {plan.summary}")
        logger.info(f"[{self.identity.name.upper()}] Steps: {len(plan.steps)}")
        logger.info(f"[{self.identity.name.upper()}] Confidence: {plan.overall_confidence:.2f}")
        logger.info(f"[{self.identity.name.upper()}] Risk: {plan.risk_level}")
        logger.info(f"[{self.identity.name.upper()}] Complexity: {plan.estimated_complexity}/10")

        if plan.needs_clarification:
            logger.info(f"[{self.identity.name.upper()}] ⚠️ CLARIFICATION NEEDED")
            for q in plan.clarifying_questions:
                logger.info(f"[{self.identity.name.upper()}]   - {q}")

        for step in plan.steps:
            logger.info(
                f"[{self.identity.name.upper()}]   {step.order}. [{step.action}] "
                f"[{step.category}] {step.file}"
            )

        if plan.warnings:
            for warning in plan.warnings:
                logger.warning(f"[{self.identity.name.upper()}] ⚠️ {warning}")

        logger.info(f"[{self.identity.name.upper()}] Planning time: {plan.planning_time_ms}ms")

    async def refine_plan(
        self,
        plan: Plan,
        feedback: str,
        context: RetrievedContext,
    ) -> Plan:
        """
        Refine an existing plan based on feedback.

        Args:
            plan: Current plan
            feedback: Feedback or issues to address
            context: Retrieved codebase context

        Returns:
            Refined plan
        """
        logger.info(f"[{self.identity.name.upper()}] Refining plan based on feedback")

        prompt = f"""You are Blueprint, refining an implementation plan based on feedback.

## Current Plan
{json.dumps(plan.to_dict(), indent=2)}

## Feedback/Issues
{feedback}

## Codebase Context
{context.to_prompt_string()}

## Instructions
Refine the plan to address the feedback. You can:
- Add new steps
- Modify existing steps
- Remove unnecessary steps
- Reorder steps
- Update descriptions for clarity

Maintain proper dependency ordering and ensure the plan remains complete.

Respond with the complete updated plan as a JSON object matching the schema."""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.claude.chat_async(
                model=MODEL_MAP.get(settings.blueprint_model, ClaudeModel.SONNET),
                messages=messages,
                system=BLUEPRINT_SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=4096,
                request_type="planning",
            )

            if not response:
                logger.error(f"[{self.identity.name.upper()}] Empty response when refining")
                return plan

            plan_data = extract_json(response)

            if not plan_data:
                logger.error(f"[{self.identity.name.upper()}] Could not extract JSON when refining")
                return plan

            try:
                plan_output = PlanOutput.model_validate(plan_data)
                refined_plan = Plan.from_output(plan_output)
                logger.info(f"[{self.identity.name.upper()}] Plan refined: {refined_plan.summary}")
                return refined_plan

            except ValidationError as e:
                logger.warning(f"[{self.identity.name.upper()}] Refined plan validation failed: {e}")
                # Fall back to dict parsing
                return Plan.from_dict(plan_data)

        except Exception as e:
            logger.error(f"[{self.identity.name.upper()}] Plan refinement failed: {e}")
            return plan  # Return original plan on failure

    async def validate_plan_against_context(
        self,
        plan: Plan,
        context: RetrievedContext,
    ) -> list[str]:
        """
        Validate that plan files exist in context where expected.

        Args:
            plan: The plan to validate
            context: Retrieved codebase context

        Returns:
            List of validation warnings
        """
        warnings = []
        context_files = {chunk.file_path for chunk in context.chunks}

        for step in plan.steps:
            if step.action == "modify":
                # Check if file exists in context
                if step.file not in context_files:
                    # Check partial matches
                    matching = [f for f in context_files if step.file in f or f in step.file]
                    if not matching:
                        warnings.append(
                            f"Step {step.order}: File '{step.file}' marked for modify "
                            f"but not found in codebase context"
                        )

        return warnings