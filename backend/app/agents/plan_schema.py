"""
Plan Schema - Strict Pydantic models for Blueprint's structured output.

Uses Claude's Structured Outputs feature for guaranteed schema compliance.
Optimized for Laravel implementation planning with dependency ordering.
"""
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class ActionType(str, Enum):
    """Type of action for a plan step."""
    CREATE = "create"  # New file that doesn't exist
    MODIFY = "modify"  # Change existing file
    DELETE = "delete"  # Remove file (rare)


class StepCategory(str, Enum):
    """Category of step for dependency ordering."""
    CONFIG = "config"  # Config files, .env changes
    MIGRATION = "migration"  # Database migrations
    MODEL = "model"  # Eloquent models
    TRAIT = "trait"  # Traits, interfaces, base classes
    SERVICE = "service"  # Service classes
    REPOSITORY = "repository"  # Repository classes
    EVENT = "event"  # Events and listeners
    JOB = "job"  # Queue jobs
    POLICY = "policy"  # Authorization policies
    REQUEST = "request"  # Form requests
    RESOURCE = "resource"  # API resources
    CONTROLLER = "controller"  # HTTP controllers
    MIDDLEWARE = "middleware"  # HTTP middleware
    ROUTE = "route"  # Route definitions
    VIEW = "view"  # Blade views
    TEST = "test"  # Tests
    OTHER = "other"  # Anything else


class RiskLevel(str, Enum):
    """Risk level for the plan."""
    LOW = "low"  # Simple changes, low impact
    MEDIUM = "medium"  # Moderate complexity, some risk
    HIGH = "high"  # Complex changes, significant risk
    CRITICAL = "critical"  # Breaking changes, requires review


class PlanStepOutput(BaseModel):
    """
    A single step in the implementation plan.

    Each step represents one file change with clear description
    of what needs to be done.
    """
    model_config = ConfigDict(use_enum_values=True)

    order: int = Field(
        ge=1,
        description="Execution order (1-based). Dependencies must have lower order numbers."
    )
    action: ActionType = Field(
        description="Action type: create (new file), modify (existing), delete (remove)"
    )
    file: str = Field(
        min_length=1,
        description="Full file path relative to project root (e.g., 'app/Models/User.php')"
    )
    category: StepCategory = Field(
        description="Category for dependency ordering (migration, model, controller, etc.)"
    )
    description: str = Field(
        min_length=10,
        description="Detailed description of what to create/change. Be specific about methods, properties, relationships."
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="List of step order numbers this step depends on. Empty if no dependencies."
    )
    estimated_lines: int = Field(
        default=50,
        ge=1,
        description="Estimated lines of code to generate/modify"
    )

    @field_validator('file')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Ensure file path is valid."""
        v = v.strip()
        # Remove leading slash if present
        if v.startswith('/'):
            v = v[1:]
        # Basic path validation
        if '..' in v:
            raise ValueError("File path cannot contain '..'")
        return v

    @field_validator('depends_on')
    @classmethod
    def validate_dependencies(cls, v: list[int], info) -> list[int]:
        """Ensure dependencies reference valid step numbers."""
        order = info.data.get('order', 0)
        for dep in v:
            if dep >= order:
                raise ValueError(f"Step {order} cannot depend on step {dep} (must be earlier)")
        return v


class PlanReasoningOutput(BaseModel):
    """
    Chain-of-thought reasoning for the plan.

    Captures Blueprint's thinking process to ensure quality plans.
    """
    model_config = ConfigDict(use_enum_values=True)

    understanding: str = Field(
        description="1-2 sentences: What is the user trying to accomplish?"
    )
    approach: str = Field(
        description="2-3 sentences: What approach will we take and why?"
    )
    dependency_analysis: str = Field(
        description="1-2 sentences: Key dependencies identified and how they affect ordering"
    )
    risks_considered: str = Field(
        description="1-2 sentences: What risks or edge cases were considered?"
    )


class PlanOutput(BaseModel):
    """
    Structured output schema for Blueprint's implementation plan.

    This schema is used with Claude's Structured Outputs feature
    to guarantee valid, parseable responses.
    """
    model_config = ConfigDict(use_enum_values=True)

    # Plan Summary
    summary: str = Field(
        min_length=10,
        max_length=200,
        description="One sentence describing what this plan accomplishes"
    )

    # Chain-of-thought reasoning (captured but concise)
    reasoning: PlanReasoningOutput = Field(
        description="Brief chain-of-thought reasoning for the plan"
    )

    # The actual steps
    steps: list[PlanStepOutput] = Field(
        min_length=1,
        description="Ordered list of implementation steps"
    )

    # Quality metrics
    overall_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in plan feasibility (0.0 to 1.0)"
    )
    risk_level: RiskLevel = Field(
        description="Overall risk level of the plan"
    )
    estimated_complexity: int = Field(
        ge=1, le=10,
        description="Complexity score 1-10 (1=trivial, 10=major refactor)"
    )

    # Clarification handling (consistent with Nova)
    needs_clarification: bool = Field(
        default=False,
        description="True if plan cannot be created without more information"
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask if needs_clarification=true (1-3 questions)"
    )

    # Warnings and notes
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings about the plan (breaking changes, manual steps needed, etc.)"
    )

    @model_validator(mode='after')
    def validate_plan_consistency(self) -> 'PlanOutput':
        """Validate overall plan consistency."""
        # Check step order numbers are sequential
        orders = [s.order for s in self.steps]
        expected = list(range(1, len(self.steps) + 1))
        if sorted(orders) != expected:
            raise ValueError(f"Step orders must be sequential 1 to {len(self.steps)}")

        # Check dependency graph for cycles
        self._check_circular_dependencies()

        # If needs clarification, must have questions
        if self.needs_clarification and not self.clarifying_questions:
            raise ValueError("Must provide clarifying_questions when needs_clarification=true")

        return self

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies in the plan."""
        # Build adjacency list
        graph: dict[int, list[int]] = {s.order: s.depends_on for s in self.steps}

        # DFS to detect cycles
        visited: set[int] = set()
        rec_stack: set[int] = set()

        def has_cycle(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for step_order in graph:
            if step_order not in visited:
                if has_cycle(step_order):
                    raise ValueError("Circular dependency detected in plan steps")


def get_plan_json_schema() -> dict:
    """
    Get the JSON schema for PlanOutput.

    Used with Claude's Structured Outputs API.
    Adds additionalProperties: false for strict validation.
    """
    schema = PlanOutput.model_json_schema()

    # Ensure additionalProperties is false for all objects
    def add_additional_properties_false(obj: dict) -> dict:
        if isinstance(obj, dict):
            if obj.get("type") == "object":
                obj["additionalProperties"] = False
            for value in obj.values():
                if isinstance(value, dict):
                    add_additional_properties_false(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            add_additional_properties_false(item)
        return obj

    schema = add_additional_properties_false(schema)

    # Handle $defs references
    if "$defs" in schema:
        for def_schema in schema["$defs"].values():
            add_additional_properties_false(def_schema)

    return schema


# Dependency order map for validation
CATEGORY_ORDER = {
    StepCategory.CONFIG: 1,
    StepCategory.MIGRATION: 2,
    StepCategory.TRAIT: 3,
    StepCategory.MODEL: 4,
    StepCategory.REPOSITORY: 5,
    StepCategory.SERVICE: 6,
    StepCategory.EVENT: 7,
    StepCategory.JOB: 8,
    StepCategory.POLICY: 9,
    StepCategory.REQUEST: 10,
    StepCategory.RESOURCE: 11,
    StepCategory.CONTROLLER: 12,
    StepCategory.MIDDLEWARE: 13,
    StepCategory.ROUTE: 14,
    StepCategory.VIEW: 15,
    StepCategory.TEST: 16,
    StepCategory.OTHER: 99,
}


def validate_dependency_order(steps: list[PlanStepOutput]) -> list[str]:
    """
    Validate that steps follow proper Laravel dependency order.

    Returns list of warnings if order is suboptimal.
    """
    warnings = []

    for step in steps:
        category_order = CATEGORY_ORDER.get(StepCategory(step.category), 99)

        for dep_order in step.depends_on:
            dep_step = next((s for s in steps if s.order == dep_order), None)
            if dep_step:
                dep_category_order = CATEGORY_ORDER.get(StepCategory(dep_step.category), 99)

                # Check if dependency is in wrong order
                if dep_category_order > category_order:
                    warnings.append(
                        f"Step {step.order} ({step.category}) depends on step {dep_order} "
                        f"({dep_step.category}) which typically comes later"
                    )

    return warnings
