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

PLANNING_PROMPT = """<role>
You are a senior Laravel architect creating implementation plans. Your plans directly drive code generation, so they must be precise, complete, and correctly ordered. A well-structured plan prevents compilation errors and ensures dependencies are created before they're needed.
</role>

<default_to_action>
Create a complete, actionable plan. Include all files that need to be created or modified. Don't leave steps vague - be specific about what each file should contain or how it should change.
</default_to_action>

<task_context>
<user_request>{user_input}</user_request>
<intent>
- Task Type: {task_type}
- Scope: {scope}
- Domains Affected: {domains}
- Requires Migration: {requires_migration}
</intent>
</task_context>

<project_info>
{project_context}
</project_info>

<codebase_context>
{context}
</codebase_context>

<planning_guidelines>
Think through the logical order of operations before creating your plan:

1. **Dependency Order** (CRITICAL):
   - Migrations MUST come before models that use them
   - Models MUST come before controllers/services that reference them
   - Traits/Interfaces MUST come before classes that use them
   - Config files MUST come before code that reads them

2. **Laravel Conventions**:
   - Use singular names for models (User, not Users)
   - Use plural names for controllers (UsersController)
   - Place business logic in Services, not Controllers
   - Use Form Requests for validation
   - Use API Resources for response formatting

3. **Completeness Checklist**:
   - [ ] Database migrations (if schema changes needed)
   - [ ] Models with relationships and fillable
   - [ ] Form Request for validation
   - [ ] Service class for business logic
   - [ ] Controller with proper methods
   - [ ] Routes in appropriate route file
   - [ ] API Resource (for API endpoints)
   - [ ] Update any existing related files

4. **Action Types**:
   - "create": New file that doesn't exist
   - "modify": Change existing file (must exist in codebase)
   - "delete": Remove file (rare, use cautiously)
</planning_guidelines>

<output_format>
{{
  "summary": "One sentence describing what this plan accomplishes",
  "steps": [
    {{
      "order": 1,
      "action": "create" | "modify" | "delete",
      "file": "full/path/to/File.php",
      "description": "Specific description of what to create/change"
    }}
  ]
}}
</output_format>

<examples>
<example_simple>
<request>Add a method to check if a user's subscription is active</request>
<plan>
{{
  "summary": "Add isSubscriptionActive() method to User model",
  "steps": [
    {{
      "order": 1,
      "action": "modify",
      "file": "app/Models/User.php",
      "description": "Add isSubscriptionActive() method that checks if subscription_ends_at is in the future and status is 'active'"
    }}
  ]
}}
</plan>
</example_simple>

<example_complex>
<request>Create a product reviews feature where users can rate products 1-5 stars and leave comments</request>
<plan>
{{
  "summary": "Create complete product review system with ratings and comments",
  "steps": [
    {{
      "order": 1,
      "action": "create",
      "file": "database/migrations/2024_01_15_000001_create_reviews_table.php",
      "description": "Create reviews table with: id, user_id (foreign), product_id (foreign), rating (tinyint 1-5), comment (text nullable), timestamps. Add indexes on user_id, product_id, and rating"
    }},
    {{
      "order": 2,
      "action": "create",
      "file": "app/Models/Review.php",
      "description": "Create Review model with fillable [user_id, product_id, rating, comment], belongsTo relationships to User and Product, rating validation accessor"
    }},
    {{
      "order": 3,
      "action": "modify",
      "file": "app/Models/Product.php",
      "description": "Add hasMany relationship to Review, add averageRating() method that calculates mean rating, add reviewsCount() method"
    }},
    {{
      "order": 4,
      "action": "modify",
      "file": "app/Models/User.php",
      "description": "Add hasMany relationship to Review"
    }},
    {{
      "order": 5,
      "action": "create",
      "file": "app/Http/Requests/StoreReviewRequest.php",
      "description": "Create form request with validation: rating required|integer|between:1,5, comment nullable|string|max:1000. Add authorization check that user hasn't already reviewed this product"
    }},
    {{
      "order": 6,
      "action": "create",
      "file": "app/Http/Resources/ReviewResource.php",
      "description": "Create API resource exposing id, rating, comment, user (name only), created_at formatted"
    }},
    {{
      "order": 7,
      "action": "create",
      "file": "app/Http/Controllers/Api/ReviewController.php",
      "description": "Create controller with index (list product reviews with pagination), store (create review), update (edit own review), destroy (delete own review) methods"
    }},
    {{
      "order": 8,
      "action": "modify",
      "file": "routes/api.php",
      "description": "Add resource route for reviews nested under products: Route::apiResource('products.reviews', ReviewController::class)"
    }}
  ]
}}
</plan>
</example_complex>
</examples>

<verification>
Before finalizing your plan, verify:
1. Dependencies are ordered correctly (migrations → models → services → controllers → routes)
2. All necessary files are included (no missing pieces)
3. File paths follow Laravel conventions
4. Descriptions are specific enough to guide code generation
5. No circular dependencies exist
</verification>

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
                request_type="planning",
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
                request_type="planning",
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
