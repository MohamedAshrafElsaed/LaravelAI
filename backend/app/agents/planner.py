"""
Planner Agent.

Creates execution plans for implementing features, fixes, and refactors.
Uses Claude Sonnet for complex reasoning about implementation steps.
"""
import json
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

from app.agents.intent_analyzer import Intent
from app.agents.context_retriever import RetrievedContext
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)

PLANNING_PROMPT = """You are an expert Laravel developer creating an implementation plan.

## User Request
{user_input}

## Intent Analysis
- Task Type: {task_type}
- Scope: {scope}
- Domains Affected: {domains}
- Requires Migration: {requires_migration}

{project_context}

## Relevant Codebase Context
{context}

## Instructions
Create a detailed step-by-step plan to implement this request. Consider:

1. Laravel best practices and conventions
2. Existing code patterns in the codebase
3. Proper file organization (Controllers, Models, Services, etc.)
4. Database migrations if needed
5. Testing requirements
6. Security considerations

For each step, specify:
- order: Sequential step number (1, 2, 3...)
- action: One of "create", "modify", "delete"
- file: Full file path (e.g., "app/Services/PaymentGateway.php")
- description: Clear description of what to do

Respond with a JSON object:
{{
  "summary": "Brief 1-sentence summary of the plan",
  "steps": [
    {{
      "order": 1,
      "action": "create",
      "file": "app/Services/Example.php",
      "description": "Create service class to handle..."
    }},
    ...
  ]
}}

Important:
- Order steps logically (migrations before models, models before controllers, etc.)
- Include all necessary files (don't forget routes, configs, etc.)
- Be specific about what changes are needed in each file

Respond ONLY with the JSON object."""


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    order: int
    action: str  # create, modify, delete
    file: str
    description: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlanStep":
        """Create from dictionary."""
        return cls(
            order=data.get("order", 0),
            action=data.get("action", "modify"),
            file=data.get("file", ""),
            description=data.get("description", ""),
        )


@dataclass
class Plan:
    """An execution plan for implementing a request."""

    summary: str
    steps: list[PlanStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "summary": self.summary,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        """Create from dictionary."""
        steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            summary=data.get("summary", ""),
            steps=sorted(steps, key=lambda s: s.order),
        )


class Planner:
    """
    Creates execution plans for code changes.

    Uses Claude Sonnet for complex reasoning about implementation.
    """

    def __init__(self, claude_service: Optional[ClaudeService] = None):
        """
        Initialize the planner.

        Args:
            claude_service: Optional Claude service instance.
        """
        self.claude = claude_service or get_claude_service()
        logger.info("[PLANNER] Initialized")

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
            intent: Analyzed intent
            context: Retrieved codebase context
            project_context: Rich project context (stack, conventions, etc.)

        Returns:
            Plan with ordered steps
        """
        logger.info(f"[PLANNER] Creating plan for: {user_input[:100]}...")

        # Build the prompt
        prompt = PLANNING_PROMPT.format(
            user_input=user_input,
            task_type=intent.task_type,
            scope=intent.scope,
            domains=", ".join(intent.domains_affected) or "general",
            requires_migration="Yes" if intent.requires_migration else "No",
            project_context=project_context,
            context=context.to_prompt_string(),
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=messages,
                temperature=0.5,
                max_tokens=4096,
            )

            # Parse JSON response
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            plan_data = json.loads(response_text)
            plan = Plan.from_dict(plan_data)

            logger.info(f"[PLANNER] Plan created: {plan.summary}")
            logger.info(f"[PLANNER] Steps: {len(plan.steps)}")
            for step in plan.steps:
                logger.debug(f"[PLANNER]   {step.order}. [{step.action}] {step.file}")

            return plan

        except json.JSONDecodeError as e:
            logger.error(f"[PLANNER] Failed to parse plan JSON: {e}")
            logger.debug(f"[PLANNER] Raw response: {response}")
            # Return empty plan
            return Plan(
                summary="Failed to create plan - invalid response format",
                steps=[],
            )

        except Exception as e:
            logger.error(f"[PLANNER] Planning failed: {e}")
            raise

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
        logger.info(f"[PLANNER] Refining plan based on feedback")

        prompt = f"""You are an expert Laravel developer refining an implementation plan.

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

Respond with the complete updated plan as a JSON object:
{{
  "summary": "Updated summary",
  "steps": [...]
}}

Respond ONLY with the JSON object."""

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=messages,
                temperature=0.5,
                max_tokens=4096,
            )

            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            plan_data = json.loads(response_text)
            refined_plan = Plan.from_dict(plan_data)

            logger.info(f"[PLANNER] Plan refined: {refined_plan.summary}")
            return refined_plan

        except Exception as e:
            logger.error(f"[PLANNER] Plan refinement failed: {e}")
            return plan  # Return original plan on failure
