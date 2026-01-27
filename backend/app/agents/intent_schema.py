"""
Intent Schema - Strict Pydantic models for Nova's structured output.

Uses Claude's Structured Outputs feature for guaranteed schema compliance.
Optimized for Laravel applications.
"""
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class TaskType(str, Enum):
    """Type of task being requested."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    QUESTION = "question"


class Scope(str, Enum):
    """Scope of changes required."""
    SINGLE_FILE = "single_file"
    FEATURE = "feature"
    CROSS_DOMAIN = "cross_domain"


class Priority(str, Enum):
    """
    Task priority level.

    - critical: production down, security, data loss, payment issues
    - high: blocking bug, customer impact, major regression
    - medium: normal feature work, improvements
    - low: minor tweaks, formatting, small refactors, general questions
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Laravel-specific domains (single source of truth)
LARAVEL_DOMAINS = [
    "auth",  # Authentication, guards, login, registration
    "models",  # Eloquent models, relationships, scopes
    "controllers",  # HTTP controllers, request handling
    "services",  # Service classes, business logic
    "middleware",  # HTTP middleware
    "validation",  # Form requests, validation rules
    "database",  # Migrations, seeders, factories
    "routing",  # Routes, route groups, resource routes
    "api",  # API routes, resources, transformers
    "queue",  # Jobs, queues, workers
    "events",  # Events, listeners, subscribers
    "mail",  # Mailables, notifications
    "cache",  # Caching logic
    "storage",  # File storage, uploads
    "views",  # Blade templates, components
    "policies",  # Authorization policies
    "providers",  # Service providers
    "commands",  # Artisan commands
    "tests",  # Feature/Unit tests
]


class ExtractedEntities(BaseModel):
    """
    Entities explicitly mentioned in user request.

    IMPORTANT: Only include entities that are EXPLICITLY mentioned
    in the user's message or confirmed in conversation context.
    Never invent or assume entities.

    For Laravel projects, these map to:
    - files: Full paths like "app/Http/Controllers/UserController.php"
    - classes: Class names like "UserController", "User", "OrderService"
    - methods: Method names like "store", "update", "handle"
    - routes: Route paths like "/api/users", "/dashboard"
    - tables: Database tables like "users", "orders" (if mentioned)
    """
    files: list[str] = Field(
        default_factory=list,
        description="File paths explicitly mentioned (e.g., 'UserController.php', 'app/Models/User.php')"
    )
    classes: list[str] = Field(
        default_factory=list,
        description="Class names explicitly mentioned (e.g., 'UserService', 'OrderController')"
    )
    methods: list[str] = Field(
        default_factory=list,
        description="Method names explicitly mentioned (e.g., 'store', 'update', 'index')"
    )
    routes: list[str] = Field(
        default_factory=list,
        description="Route paths explicitly mentioned (e.g., '/api/users', '/orders/{id}')"
    )
    tables: list[str] = Field(
        default_factory=list,
        description="Database table names explicitly mentioned (e.g., 'users', 'orders')"
    )


class IntentOutput(BaseModel):
    """
    Structured output schema for Nova's intent analysis.

    This schema is used with Claude's Structured Outputs feature
    to guarantee valid, parseable responses.
    """

    # Pydantic v2 configuration
    model_config = ConfigDict(use_enum_values=True)

    # Core Classification
    task_type: TaskType = Field(
        description="The type of task: feature, bugfix, refactor, or question"
    )
    task_type_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in task_type classification (0.0 to 1.0)"
    )

    # Scope and Affected Areas
    domains_affected: list[str] = Field(
        description=f"Laravel domains affected. Valid values: {', '.join(LARAVEL_DOMAINS)}"
    )
    scope: Scope = Field(
        description="Extent of changes: single_file, feature, or cross_domain"
    )
    languages: list[str] = Field(
        description="Languages involved: php, blade, vue, js, ts, css, json, yaml, sql"
    )
    requires_migration: bool = Field(
        description="Whether database migration is needed"
    )

    # Priority
    priority: Priority = Field(
        description="Task priority: critical (production/security), high (blocking), medium (normal), low (minor)"
    )

    # Extracted Entities
    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities,
        description="Entities EXPLICITLY mentioned in user request - never assume"
    )

    # Search Guidance
    search_queries: list[str] = Field(
        description="3-5 search terms for Scout to find relevant code. Minimal if needs_clarification=true"
    )

    # Reasoning (short and practical)
    reasoning: str = Field(
        description="Brief explanation of analysis (2-3 sentences max, practical, not verbose)"
    )

    # Overall Confidence
    overall_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in this analysis (0.0 to 1.0)"
    )

    # Clarification Handling
    needs_clarification: bool = Field(
        description="True if request is unclear and clarification is needed. Pipeline will HALT."
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="1-3 specific questions if needs_clarification=true. Use multiple-choice when possible."
    )


def get_intent_json_schema() -> dict:
    """
    Get the JSON schema for IntentOutput.

    Used with Claude's Structured Outputs API.
    Adds additionalProperties: false for strict validation.
    """
    schema = IntentOutput.model_json_schema()

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


# Convenience function to create Intent from validated output
def intent_from_output(output: IntentOutput) -> dict:
    """Convert IntentOutput to a dictionary for downstream agents."""
    return output.model_dump()
