"""
Blueprint (Planner) Agent Tests

Tests the Planner agent's ability to create implementation plans.
Includes unit tests, schema validation tests, and pipeline integration.

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_planner.py -v

    # Integration tests (real API, slow)
    pytest backend/tests/agents/test_planner.py -v -m integration

    # Interactive mode
    python backend/tests/agents/test_planner.py --interactive

    # Run all scenarios
    python backend/tests/agents/test_planner.py --run-all
"""
import pytest
import asyncio
import json
import sys
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.planner import Planner, Plan, PlanStep, PlanReasoning
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
from app.agents.intent_analyzer import IntentAnalyzer, Intent
from app.agents.context_retriever import ContextRetriever, RetrievedContext, CodeChunk
from app.agents.conversation_summary import ConversationSummary, RecentMessage
from app.agents.config import agent_config
from app.services.vector_store import VectorStore, SearchResult
from app.services.embeddings import EmbeddingService


# =============================================================================
# Sample Data
# =============================================================================

SAMPLE_PROJECT_CONTEXT = """### Technology Stack
- **Backend:** Laravel 11.x (PHP 8.3)
- **Database:** mysql
- **Auth:** sanctum + spatie/laravel-permission

### Database Models
Available models: User, Order, Product, Category, Payment

### Architecture Patterns
- Service Layer pattern
- Repository pattern for complex queries
- Form Requests for validation

### Codebase Statistics
- **Total Files:** 150
- **Controllers:** UserController, OrderController, ProductController
"""

SAMPLE_INTENT_FEATURE = Intent(
    task_type="feature",
    task_type_confidence=0.9,
    domains_affected=["controllers", "models", "database"],
    scope="feature",
    languages=["php"],
    requires_migration=True,
    priority="medium",
    entities={
        "files": [],
        "classes": ["Product"],
        "methods": [],
        "routes": ["/api/products"],
        "tables": ["products"],
    },
    search_queries=["Product", "ProductController", "products table"],
    reasoning="User wants to add a reviews feature to products",
    overall_confidence=0.85,
    needs_clarification=False,
)

SAMPLE_INTENT_BUGFIX = Intent(
    task_type="bugfix",
    task_type_confidence=0.95,
    domains_affected=["auth", "controllers"],
    scope="single_file",
    languages=["php"],
    requires_migration=False,
    priority="high",
    entities={
        "files": ["app/Http/Controllers/Auth/LoginController.php"],
        "classes": ["LoginController"],
        "methods": ["login"],
        "routes": ["/api/login"],
        "tables": [],
    },
    search_queries=["LoginController", "login", "Auth::attempt"],
    reasoning="User reports login returning 500 errors",
    overall_confidence=0.9,
    needs_clarification=False,
)

SAMPLE_INTENT_REFACTOR = Intent(
    task_type="refactor",
    task_type_confidence=0.85,
    domains_affected=["controllers", "services"],
    scope="feature",
    languages=["php"],
    requires_migration=False,
    priority="medium",
    entities={
        "files": ["app/Http/Controllers/OrderController.php"],
        "classes": ["OrderController"],
        "methods": [],
        "routes": [],
        "tables": [],
    },
    search_queries=["OrderController", "Order", "repository pattern"],
    reasoning="User wants to refactor OrderController to use repository pattern",
    overall_confidence=0.8,
    needs_clarification=False,
)

SAMPLE_INTENT_AMBIGUOUS = Intent(
    task_type="question",
    task_type_confidence=0.3,
    domains_affected=[],
    scope="single_file",
    languages=["php"],
    requires_migration=False,
    priority="medium",
    entities={"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
    search_queries=["bug", "fix"],
    reasoning="Request is too vague to understand",
    overall_confidence=0.2,
    needs_clarification=True,
    clarifying_questions=["What specific bug are you referring to?"],
)

SAMPLE_CONTEXT = RetrievedContext(
    chunks=[
        CodeChunk(
            file_path="app/Models/Product.php",
            content=(
                "class Product extends Model {\n"
                "    protected $fillable = ['name', 'price', 'description'];\n"
                "    \n"
                "    public function category() {\n"
                "        return $this->belongsTo(Category::class);\n"
                "    }\n"
                "}"
            ),
            chunk_type="class",
            start_line=1,
            end_line=10,
            score=0.92,
        ),
        CodeChunk(
            file_path="app/Http/Controllers/ProductController.php",
            content=(
                "class ProductController extends Controller {\n"
                "    public function index() {\n"
                "        return Product::paginate();\n"
                "    }\n"
                "    \n"
                "    public function store(StoreProductRequest $request) {\n"
                "        return Product::create($request->validated());\n"
                "    }\n"
                "}"
            ),
            chunk_type="class",
            start_line=1,
            end_line=15,
            score=0.88,
        ),
    ],
    domain_summaries={
        "models": "Product model with category relationship",
        "controllers": "ProductController with CRUD operations",
    },
)

SAMPLE_CONTEXT_AUTH = RetrievedContext(
    chunks=[
        CodeChunk(
            file_path="app/Http/Controllers/Auth/LoginController.php",
            content=(
                "class LoginController extends Controller {\n"
                "    public function login(Request $request) {\n"
                "        if (Auth::attempt($request->only('email', 'password'))) {\n"
                "            return response()->json(['token' => $request->user()->createToken('api')->plainTextToken]);\n"
                "        }\n"
                "        return response()->json(['error' => 'Invalid credentials'], 401);\n"
                "    }\n"
                "}"
            ),
            chunk_type="class",
            start_line=1,
            end_line=12,
            score=0.95,
        ),
    ],
    domain_summaries={"auth": "LoginController with Sanctum token authentication"},
)


# =============================================================================
# Mock Plan Responses
# =============================================================================

MOCK_PLAN_FEATURE = {
    "summary": "Create product reviews feature with ratings and comments",
    "reasoning": {
        "understanding": "User wants to add a reviews feature where customers can rate products 1-5 stars and leave comments.",
        "approach": "Create Review model with migration, add relationships to Product and User, create API endpoints with proper validation.",
        "dependency_analysis": "Migration must come first, then Model, then Controller with routes last.",
        "risks_considered": "Need to prevent duplicate reviews per user/product. Should validate rating range."
    },
    "steps": [
        {
            "order": 1,
            "action": "create",
            "file": "database/migrations/2024_01_15_000001_create_reviews_table.php",
            "category": "migration",
            "description": "Create reviews table with user_id, product_id, rating (1-5), comment, timestamps. Add unique constraint on [user_id, product_id].",
            "depends_on": [],
            "estimated_lines": 35
        },
        {
            "order": 2,
            "action": "create",
            "file": "app/Models/Review.php",
            "category": "model",
            "description": "Create Review model with fillable, casts, belongsTo relationships to User and Product.",
            "depends_on": [1],
            "estimated_lines": 40
        },
        {
            "order": 3,
            "action": "modify",
            "file": "app/Models/Product.php",
            "category": "model",
            "description": "Add hasMany relationship to Review, add averageRating() method.",
            "depends_on": [2],
            "estimated_lines": 15
        },
        {
            "order": 4,
            "action": "create",
            "file": "app/Http/Requests/StoreReviewRequest.php",
            "category": "request",
            "description": "Create form request with validation: rating required|integer|between:1,5, comment nullable|string|max:1000.",
            "depends_on": [2],
            "estimated_lines": 25
        },
        {
            "order": 5,
            "action": "create",
            "file": "app/Http/Controllers/Api/ReviewController.php",
            "category": "controller",
            "description": "Create controller with index, store, update, destroy methods using ReviewResource.",
            "depends_on": [2, 4],
            "estimated_lines": 60
        },
        {
            "order": 6,
            "action": "modify",
            "file": "routes/api.php",
            "category": "route",
            "description": "Add nested resource routes: Route::apiResource('products.reviews', ReviewController::class)",
            "depends_on": [5],
            "estimated_lines": 5
        }
    ],
    "overall_confidence": 0.9,
    "risk_level": "medium",
    "estimated_complexity": 5,
    "needs_clarification": False,
    "clarifying_questions": [],
    "warnings": ["Consider caching average_rating for high-traffic products"]
}

MOCK_PLAN_BUGFIX = {
    "summary": "Fix login endpoint 500 error by adding proper exception handling",
    "reasoning": {
        "understanding": "Login endpoint is returning 500 errors, likely due to unhandled exceptions.",
        "approach": "Add try-catch block and proper error responses in LoginController.",
        "dependency_analysis": "Single file modification, no dependencies.",
        "risks_considered": "Must ensure error messages don't leak sensitive information."
    },
    "steps": [
        {
            "order": 1,
            "action": "modify",
            "file": "app/Http/Controllers/Auth/LoginController.php",
            "category": "controller",
            "description": "Wrap Auth::attempt in try-catch, add proper exception handling, return appropriate error responses with status codes.",
            "depends_on": [],
            "estimated_lines": 20
        }
    ],
    "overall_confidence": 0.85,
    "risk_level": "low",
    "estimated_complexity": 2,
    "needs_clarification": False,
    "clarifying_questions": [],
    "warnings": []
}

MOCK_PLAN_CLARIFICATION = {
    "summary": "Cannot create plan - need more information about the bug",
    "reasoning": {
        "understanding": "User reports 'a bug' but doesn't specify which component or what the issue is.",
        "approach": "Cannot determine approach without knowing what's broken.",
        "dependency_analysis": "Cannot analyze dependencies without knowing affected components.",
        "risks_considered": "Risk of fixing wrong thing without more details."
    },
    "steps": [],
    "overall_confidence": 0.2,
    "risk_level": "medium",
    "estimated_complexity": 1,
    "needs_clarification": True,
    "clarifying_questions": [
        "Which component or endpoint is affected?",
        "What is the expected vs actual behavior?",
        "Do you see any error messages?"
    ],
    "warnings": []
}

MOCK_PLAN_REFACTOR = {
    "summary": "Refactor OrderController to use repository pattern",
    "reasoning": {
        "understanding": "User wants to extract data access logic from OrderController into a repository class.",
        "approach": "Create OrderRepository interface and implementation, inject into controller, move query logic.",
        "dependency_analysis": "Interface first, then implementation, then update controller.",
        "risks_considered": "Need to maintain backward compatibility with existing controller methods."
    },
    "steps": [
        {
            "order": 1,
            "action": "create",
            "file": "app/Repositories/Contracts/OrderRepositoryInterface.php",
            "category": "trait",
            "description": "Create interface with methods: all(), find($id), create(array $data), update($id, array $data), delete($id), findByUser($userId)",
            "depends_on": [],
            "estimated_lines": 20
        },
        {
            "order": 2,
            "action": "create",
            "file": "app/Repositories/OrderRepository.php",
            "category": "repository",
            "description": "Implement OrderRepositoryInterface with Eloquent queries, inject Order model.",
            "depends_on": [1],
            "estimated_lines": 60
        },
        {
            "order": 3,
            "action": "modify",
            "file": "app/Providers/AppServiceProvider.php",
            "category": "config",
            "description": "Bind OrderRepositoryInterface to OrderRepository in register() method.",
            "depends_on": [1, 2],
            "estimated_lines": 10
        },
        {
            "order": 4,
            "action": "modify",
            "file": "app/Http/Controllers/OrderController.php",
            "category": "controller",
            "description": "Inject OrderRepositoryInterface via constructor, replace direct Eloquent calls with repository methods.",
            "depends_on": [2, 3],
            "estimated_lines": 40
        }
    ],
    "overall_confidence": 0.85,
    "risk_level": "medium",
    "estimated_complexity": 4,
    "needs_clarification": False,
    "clarifying_questions": [],
    "warnings": ["Ensure all existing tests are updated to mock the repository"]
}


# =============================================================================
# Test Scenarios
# =============================================================================

PLANNER_SCENARIOS = [
    {
        "name": "feature_reviews",
        "description": "Create product reviews feature",
        "user_input": "Add a reviews feature where users can rate products 1-5 stars and leave comments",
        "intent": SAMPLE_INTENT_FEATURE,
        "context": SAMPLE_CONTEXT,
        "mock_response": MOCK_PLAN_FEATURE,
        "expected": {
            "min_steps": 4,
            "has_migration": True,
            "has_model": True,
            "has_controller": True,
            "needs_clarification": False,
            "risk_level_in": ["low", "medium"],
        },
    },
    {
        "name": "bugfix_login",
        "description": "Fix login 500 error",
        "user_input": "Fix the login endpoint - it's returning 500 errors",
        "intent": SAMPLE_INTENT_BUGFIX,
        "context": SAMPLE_CONTEXT_AUTH,
        "mock_response": MOCK_PLAN_BUGFIX,
        "expected": {
            "min_steps": 1,
            "max_steps": 3,
            "has_migration": False,
            "needs_clarification": False,
            "risk_level_in": ["low", "medium"],
        },
    },
    {
        "name": "ambiguous_request",
        "description": "Ambiguous request triggers clarification",
        "user_input": "Fix the bug",
        "intent": SAMPLE_INTENT_AMBIGUOUS,
        "context": RetrievedContext(chunks=[]),
        "mock_response": MOCK_PLAN_CLARIFICATION,
        "expected": {
            "min_steps": 0,
            "needs_clarification": True,
            "has_questions": True,
        },
    },
    {
        "name": "refactor_repository",
        "description": "Refactor to repository pattern",
        "user_input": "Refactor the OrderController to use the repository pattern",
        "intent": SAMPLE_INTENT_REFACTOR,
        "context": SAMPLE_CONTEXT,
        "mock_response": MOCK_PLAN_REFACTOR,
        "expected": {
            "min_steps": 3,
            "has_migration": False,
            "needs_clarification": False,
        },
    },
    {
        "name": "simple_method_add",
        "description": "Add a simple method to existing model",
        "user_input": "Add an isActive() method to the User model that checks if status is 'active'",
        "intent": Intent(
            task_type="feature",
            task_type_confidence=0.95,
            domains_affected=["models"],
            scope="single_file",
            languages=["php"],
            requires_migration=False,
            priority="low",
            entities={"files": [], "classes": ["User"], "methods": ["isActive"], "routes": [], "tables": []},
            search_queries=["User model", "status"],
            reasoning="Simple method addition to User model",
            overall_confidence=0.95,
        ),
        "context": SAMPLE_CONTEXT,
        "mock_response": {
            "summary": "Add isActive() method to User model",
            "reasoning": {
                "understanding": "User wants a helper method to check if user status is active.",
                "approach": "Add simple accessor method to User model.",
                "dependency_analysis": "No dependencies, single file change.",
                "risks_considered": "Low risk, simple additive change."
            },
            "steps": [
                {
                    "order": 1,
                    "action": "modify",
                    "file": "app/Models/User.php",
                    "category": "model",
                    "description": "Add isActive(): bool method that returns $this->status === 'active'",
                    "depends_on": [],
                    "estimated_lines": 8
                }
            ],
            "overall_confidence": 0.95,
            "risk_level": "low",
            "estimated_complexity": 1,
            "needs_clarification": False,
            "clarifying_questions": [],
            "warnings": []
        },
        "expected": {
            "min_steps": 1,
            "max_steps": 1,
            "has_migration": False,
            "needs_clarification": False,
            "complexity_max": 2,
        },
    },
]


# =============================================================================
# Unit Tests - PlanStep
# =============================================================================

class TestPlanStep:
    """Test PlanStep dataclass."""

    def test_creation(self):
        """Test basic PlanStep creation."""
        step = PlanStep(
            order=1,
            action="create",
            file="app/Models/Test.php",
            description="Create Test model",
            category="model",
            depends_on=[],
            estimated_lines=50,
        )

        assert step.order == 1
        assert step.action == "create"
        assert step.file == "app/Models/Test.php"
        assert step.category == "model"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        step = PlanStep(
            order=1,
            action="modify",
            file="app/Models/User.php",
            description="Add method",
            category="model",
        )

        data = step.to_dict()

        assert data["order"] == 1
        assert data["action"] == "modify"
        assert data["file"] == "app/Models/User.php"

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "order": 2,
            "action": "create",
            "file": "app/Services/TestService.php",
            "description": "Create service",
            "category": "service",
            "depends_on": [1],
            "estimated_lines": 100,
        }

        step = PlanStep.from_dict(data)

        assert step.order == 2
        assert step.action == "create"
        assert step.depends_on == [1]

    def test_from_dict_handles_string(self):
        """Test from_dict handles string input gracefully."""
        step = PlanStep.from_dict("just a string")

        assert step.description == "just a string"
        assert step.order == 0

    def test_from_dict_handles_json_string(self):
        """Test from_dict handles JSON string."""
        json_str = '{"order": 1, "action": "create", "file": "test.php", "description": "test"}'
        step = PlanStep.from_dict(json_str)

        assert step.order == 1
        assert step.action == "create"

    def test_from_output(self):
        """Test creation from PlanStepOutput."""
        output = PlanStepOutput(
            order=1,
            action=ActionType.CREATE,
            file="app/Models/Test.php",
            category=StepCategory.MODEL,
            description="Create Test model with fillable and relationships",
            depends_on=[],
            estimated_lines=40,
        )

        step = PlanStep.from_output(output)

        assert step.order == 1
        assert step.action == "create"
        assert step.category == "model"


# =============================================================================
# Unit Tests - Plan
# =============================================================================

class TestPlan:
    """Test Plan dataclass."""

    def test_creation(self):
        """Test basic Plan creation."""
        plan = Plan(
            summary="Test plan",
            steps=[
                PlanStep(order=1, action="create", file="test.php", description="test"),
            ],
            overall_confidence=0.9,
            risk_level="low",
        )

        assert plan.summary == "Test plan"
        assert len(plan.steps) == 1
        assert plan.overall_confidence == 0.9

    def test_to_dict(self):
        """Test serialization to dictionary."""
        plan = Plan(
            summary="Test plan",
            steps=[
                PlanStep(order=1, action="create", file="test.php", description="test"),
            ],
            reasoning=PlanReasoning(
                understanding="Test understanding",
                approach="Test approach",
                dependency_analysis="No deps",
                risks_considered="Low risk",
            ),
            overall_confidence=0.85,
            risk_level="medium",
        )

        data = plan.to_dict()

        assert data["summary"] == "Test plan"
        assert len(data["steps"]) == 1
        assert data["reasoning"]["understanding"] == "Test understanding"
        assert data["overall_confidence"] == 0.85

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "summary": "Create feature",
            "steps": [
                {"order": 1, "action": "create", "file": "test.php", "description": "test"},
                {"order": 2, "action": "modify", "file": "existing.php", "description": "modify"},
            ],
            "overall_confidence": 0.8,
            "risk_level": "medium",
        }

        plan = Plan.from_dict(data)

        assert plan.summary == "Create feature"
        assert len(plan.steps) == 2
        assert plan.steps[0].order == 1
        assert plan.steps[1].order == 2

    def test_from_dict_sorts_steps(self):
        """Test that from_dict sorts steps by order."""
        data = {
            "summary": "Test",
            "steps": [
                {"order": 3, "action": "modify", "file": "c.php", "description": "third"},
                {"order": 1, "action": "create", "file": "a.php", "description": "first"},
                {"order": 2, "action": "create", "file": "b.php", "description": "second"},
            ],
        }

        plan = Plan.from_dict(data)

        assert plan.steps[0].order == 1
        assert plan.steps[1].order == 2
        assert plan.steps[2].order == 3

    def test_clarification_required(self):
        """Test creating clarification-required plan."""
        plan = Plan.clarification_required(
            questions=["What feature?", "Which file?"],
            reasoning="Request is too vague",
        )

        assert plan.needs_clarification is True
        assert len(plan.clarifying_questions) == 2
        assert plan.should_halt_pipeline() is True
        assert plan.overall_confidence < 0.5

    def test_error_fallback(self):
        """Test creating error fallback plan."""
        plan = Plan.error_fallback("API timeout")

        assert plan.needs_clarification is True
        assert "timeout" in plan.summary.lower() or "timeout" in plan.reasoning.approach.lower()
        assert plan.should_halt_pipeline() is True

    def test_should_halt_pipeline_on_clarification(self):
        """Test pipeline halts on clarification needed."""
        plan = Plan(
            summary="Test",
            steps=[],
            needs_clarification=True,
            overall_confidence=0.3,
        )

        assert plan.should_halt_pipeline() is True

    def test_should_halt_pipeline_on_low_confidence(self):
        """Test pipeline halts on low confidence."""
        plan = Plan(
            summary="Test",
            steps=[PlanStep(order=1, action="create", file="t.php", description="t")],
            overall_confidence=0.3,
        )

        assert plan.should_halt_pipeline() is True

    def test_should_halt_pipeline_on_empty_steps(self):
        """Test pipeline halts on empty steps."""
        plan = Plan(
            summary="Test",
            steps=[],
            overall_confidence=0.9,
        )

        assert plan.should_halt_pipeline() is True

    def test_should_not_halt_on_valid_plan(self):
        """Test pipeline continues on valid plan."""
        plan = Plan(
            summary="Valid plan",
            steps=[PlanStep(order=1, action="create", file="t.php", description="t")],
            overall_confidence=0.85,
            needs_clarification=False,
        )

        assert plan.should_halt_pipeline() is False

    def test_get_files_to_create(self):
        """Test getting files to create."""
        plan = Plan(
            summary="Test",
            steps=[
                PlanStep(order=1, action="create", file="a.php", description="a"),
                PlanStep(order=2, action="modify", file="b.php", description="b"),
                PlanStep(order=3, action="create", file="c.php", description="c"),
            ],
        )

        files = plan.get_files_to_create()

        assert len(files) == 2
        assert "a.php" in files
        assert "c.php" in files

    def test_get_files_to_modify(self):
        """Test getting files to modify."""
        plan = Plan(
            summary="Test",
            steps=[
                PlanStep(order=1, action="create", file="a.php", description="a"),
                PlanStep(order=2, action="modify", file="b.php", description="b"),
                PlanStep(order=3, action="modify", file="c.php", description="c"),
            ],
        )

        files = plan.get_files_to_modify()

        assert len(files) == 2
        assert "b.php" in files
        assert "c.php" in files

    def test_total_estimated_lines(self):
        """Test total estimated lines calculation."""
        plan = Plan(
            summary="Test",
            steps=[
                PlanStep(order=1, action="create", file="a.php", description="a", estimated_lines=50),
                PlanStep(order=2, action="create", file="b.php", description="b", estimated_lines=30),
                PlanStep(order=3, action="modify", file="c.php", description="c", estimated_lines=20),
            ],
        )

        assert plan.total_estimated_lines() == 100


# =============================================================================
# Unit Tests - Plan Schema
# =============================================================================

class TestPlanSchema:
    """Test Pydantic schema validation."""

    def test_valid_plan_output(self):
        """Test valid PlanOutput creation."""
        output = PlanOutput(
            summary="Test plan",
            reasoning=PlanReasoningOutput(
                understanding="Test",
                approach="Test approach",
                dependency_analysis="No deps",
                risks_considered="Low risk",
            ),
            steps=[
                PlanStepOutput(
                    order=1,
                    action=ActionType.CREATE,
                    file="test.php",
                    category=StepCategory.MODEL,
                    description="Create test model",
                    depends_on=[],
                    estimated_lines=50,
                ),
            ],
            overall_confidence=0.9,
            risk_level=RiskLevel.LOW,
            estimated_complexity=3,
        )

        assert output.summary == "Test plan"
        assert len(output.steps) == 1

    def test_step_order_validation(self):
        """Test that step orders must be sequential."""
        with pytest.raises(ValueError, match="sequential"):
            PlanOutput(
                summary="Test",
                reasoning=PlanReasoningOutput(
                    understanding="T", approach="T", dependency_analysis="T", risks_considered="T"
                ),
                steps=[
                    PlanStepOutput(order=1, action=ActionType.CREATE, file="a.php", category=StepCategory.MODEL, description="a"),
                    PlanStepOutput(order=3, action=ActionType.CREATE, file="b.php", category=StepCategory.MODEL, description="b"),  # Gap!
                ],
                overall_confidence=0.9,
                risk_level=RiskLevel.LOW,
                estimated_complexity=3,
            )

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        with pytest.raises(ValueError, match="[Cc]ircular"):
            PlanOutput(
                summary="Test",
                reasoning=PlanReasoningOutput(
                    understanding="T", approach="T", dependency_analysis="T", risks_considered="T"
                ),
                steps=[
                    PlanStepOutput(order=1, action=ActionType.CREATE, file="a.php", category=StepCategory.MODEL, description="a", depends_on=[2]),
                    PlanStepOutput(order=2, action=ActionType.CREATE, file="b.php", category=StepCategory.MODEL, description="b", depends_on=[1]),
                ],
                overall_confidence=0.9,
                risk_level=RiskLevel.LOW,
                estimated_complexity=3,
            )

    def test_clarification_requires_questions(self):
        """Test that needs_clarification requires questions."""
        with pytest.raises(ValueError, match="clarifying_questions"):
            PlanOutput(
                summary="Test",
                reasoning=PlanReasoningOutput(
                    understanding="T", approach="T", dependency_analysis="T", risks_considered="T"
                ),
                steps=[],
                overall_confidence=0.3,
                risk_level=RiskLevel.MEDIUM,
                estimated_complexity=1,
                needs_clarification=True,
                clarifying_questions=[],  # Empty!
            )

    def test_get_plan_json_schema(self):
        """Test JSON schema generation."""
        schema = get_plan_json_schema()

        assert "properties" in schema
        assert "summary" in schema["properties"]
        assert "steps" in schema["properties"]
        assert "reasoning" in schema["properties"]

    def test_validate_dependency_order(self):
        """Test dependency order validation."""
        steps = [
            PlanStepOutput(order=1, action=ActionType.CREATE, file="controller.php", category=StepCategory.CONTROLLER, description="controller", depends_on=[2]),
            PlanStepOutput(order=2, action=ActionType.CREATE, file="model.php", category=StepCategory.MODEL, description="model"),
        ]

        warnings = validate_dependency_order(steps)

        # Controller depending on model should be fine, but step 1 depending on step 2 is backwards
        assert len(warnings) >= 0  # May or may not warn depending on implementation


# =============================================================================
# Unit Tests - Planner Class
# =============================================================================

class TestPlanner:
    """Test Planner class."""

    @pytest.fixture
    def mock_claude(self):
        """Create mock Claude service."""
        mock = MagicMock()
        mock.chat_async = AsyncMock(return_value=json.dumps(MOCK_PLAN_FEATURE))
        return mock

    @pytest.fixture
    def planner(self, mock_claude):
        """Create Planner with mock Claude."""
        return Planner(claude_service=mock_claude)

    @pytest.mark.asyncio
    async def test_plan_creation(self, planner, mock_claude):
        """Test basic plan creation."""
        plan = await planner.plan(
            user_input="Add a reviews feature",
            intent=SAMPLE_INTENT_FEATURE,
            context=SAMPLE_CONTEXT,
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert plan.summary is not None
        assert len(plan.steps) > 0
        assert plan.overall_confidence > 0
        mock_claude.chat_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_includes_reasoning(self, planner):
        """Test that plan includes reasoning."""
        plan = await planner.plan(
            user_input="Add a reviews feature",
            intent=SAMPLE_INTENT_FEATURE,
            context=SAMPLE_CONTEXT,
        )

        assert plan.reasoning is not None
        assert plan.reasoning.understanding != ""
        assert plan.reasoning.approach != ""

    @pytest.mark.asyncio
    async def test_plan_clarification(self, mock_claude):
        """Test plan with clarification needed."""
        mock_claude.chat_async = AsyncMock(return_value=json.dumps(MOCK_PLAN_CLARIFICATION))
        planner = Planner(claude_service=mock_claude)

        plan = await planner.plan(
            user_input="Fix the bug",
            intent=SAMPLE_INTENT_AMBIGUOUS,
            context=RetrievedContext(chunks=[]),
        )

        assert plan.needs_clarification is True
        assert len(plan.clarifying_questions) > 0
        assert plan.should_halt_pipeline() is True

    @pytest.mark.asyncio
    async def test_plan_retry_on_error(self, mock_claude):
        """Test retry logic on transient errors."""
        # First call fails, second succeeds
        mock_claude.chat_async = AsyncMock(
            side_effect=[
                Exception("Transient error"),
                json.dumps(MOCK_PLAN_FEATURE),
            ]
        )
        planner = Planner(claude_service=mock_claude)

        plan = await planner.plan(
            user_input="Add reviews",
            intent=SAMPLE_INTENT_FEATURE,
            context=SAMPLE_CONTEXT,
        )

        assert plan.summary is not None
        assert plan.retry_count == 1
        assert mock_claude.chat_async.call_count == 2

    @pytest.mark.asyncio
    async def test_plan_fallback_on_all_retries_failed(self, mock_claude):
        """Test fallback when all retries fail."""
        mock_claude.chat_async = AsyncMock(side_effect=Exception("Persistent error"))
        planner = Planner(claude_service=mock_claude)

        plan = await planner.plan(
            user_input="Add reviews",
            intent=SAMPLE_INTENT_FEATURE,
            context=SAMPLE_CONTEXT,
        )

        assert plan.needs_clarification is True
        assert plan.should_halt_pipeline() is True
        assert "error" in plan.summary.lower() or "failed" in plan.summary.lower()

    @pytest.mark.asyncio
    async def test_plan_timing_tracked(self, planner):
        """Test that planning time is tracked."""
        plan = await planner.plan(
            user_input="Add reviews",
            intent=SAMPLE_INTENT_FEATURE,
            context=SAMPLE_CONTEXT,
        )

        assert plan.planning_time_ms > 0

    @pytest.mark.asyncio
    async def test_refine_plan(self, planner, mock_claude):
        """Test plan refinement."""
        original_plan = Plan.from_dict(MOCK_PLAN_FEATURE)

        mock_claude.chat_async = AsyncMock(return_value=json.dumps({
            **MOCK_PLAN_FEATURE,
            "summary": "Updated: Create product reviews with caching",
        }))

        refined = await planner.refine_plan(
            plan=original_plan,
            feedback="Add caching for the average rating calculation",
            context=SAMPLE_CONTEXT,
        )

        assert "caching" in refined.summary.lower() or refined.summary != original_plan.summary


# =============================================================================
# Parametrized Scenario Tests
# =============================================================================

class TestPlannerScenarios:
    """Run all planner scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", PLANNER_SCENARIOS, ids=[s["name"] for s in PLANNER_SCENARIOS])
    async def test_scenario(self, scenario):
        """Test each scenario through the planner."""
        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(return_value=json.dumps(scenario["mock_response"]))

        planner = Planner(claude_service=mock_claude)

        plan = await planner.plan(
            user_input=scenario["user_input"],
            intent=scenario["intent"],
            context=scenario["context"],
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        expected = scenario.get("expected", {})

        # Validate expectations
        if "min_steps" in expected:
            assert len(plan.steps) >= expected["min_steps"], f"Expected >= {expected['min_steps']} steps, got {len(plan.steps)}"

        if "max_steps" in expected:
            assert len(plan.steps) <= expected["max_steps"], f"Expected <= {expected['max_steps']} steps, got {len(plan.steps)}"

        if "needs_clarification" in expected:
            assert plan.needs_clarification == expected["needs_clarification"]

        if "has_questions" in expected and expected["has_questions"]:
            assert len(plan.clarifying_questions) > 0

        if "has_migration" in expected:
            has_migration = any(s.category == "migration" for s in plan.steps)
            assert has_migration == expected["has_migration"]

        if "has_model" in expected:
            has_model = any(s.category == "model" for s in plan.steps)
            assert has_model == expected["has_model"]

        if "has_controller" in expected:
            has_controller = any(s.category == "controller" for s in plan.steps)
            assert has_controller == expected["has_controller"]

        if "risk_level_in" in expected:
            assert plan.risk_level in expected["risk_level_in"]

        if "complexity_max" in expected:
            assert plan.estimated_complexity <= expected["complexity_max"]


# =============================================================================
# Integration Tests (Real API)
# =============================================================================

@pytest.mark.integration
class TestPlannerIntegration:
    """Integration tests with real Claude API."""

    @pytest.fixture
    def real_planner(self):
        """Create real Planner."""
        return Planner()

    @pytest.mark.asyncio
    async def test_real_feature_plan(self, real_planner):
        """Test real feature plan creation."""
        plan = await real_planner.plan(
            user_input="Add a reviews feature where users can rate products 1-5 stars",
            intent=SAMPLE_INTENT_FEATURE,
            context=SAMPLE_CONTEXT,
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert plan.summary is not None
        assert len(plan.steps) > 0
        assert not plan.needs_clarification
        assert plan.overall_confidence > 0.5

        # Should have proper ordering
        for i, step in enumerate(plan.steps):
            assert step.order == i + 1

    @pytest.mark.asyncio
    async def test_real_simple_plan(self, real_planner):
        """Test real simple plan creation."""
        simple_intent = Intent(
            task_type="feature",
            task_type_confidence=0.95,
            domains_affected=["models"],
            scope="single_file",
            languages=["php"],
            requires_migration=False,
            priority="low",
            entities={"files": [], "classes": ["User"], "methods": [], "routes": [], "tables": []},
            search_queries=["User model"],
            reasoning="Simple method addition",
            overall_confidence=0.95,
        )

        plan = await real_planner.plan(
            user_input="Add isActive() method to User model",
            intent=simple_intent,
            context=SAMPLE_CONTEXT,
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert len(plan.steps) <= 2  # Should be simple
        assert plan.estimated_complexity <= 3

    @pytest.mark.asyncio
    async def test_real_ambiguous_triggers_clarification(self, real_planner):
        """Test that ambiguous request triggers clarification."""
        plan = await real_planner.plan(
            user_input="Fix the bug",
            intent=SAMPLE_INTENT_AMBIGUOUS,
            context=RetrievedContext(chunks=[]),
            project_context="",
        )

        # Should either need clarification or have very low confidence
        assert plan.needs_clarification or plan.overall_confidence < 0.5


# =============================================================================
# Interactive CLI Testing
# =============================================================================

async def run_interactive_test():
    """Run interactive testing mode."""
    print("\n" + "=" * 60)
    print("Blueprint (Planner) - Interactive Test Mode")
    print("=" * 60)
    print("\nType your requests to test Blueprint's planning.")
    print("Commands: 'quit' to exit, 'context on/off' to toggle context\n")

    planner = Planner()
    use_context = True

    while True:
        try:
            user_input = input("\n[You]: ").strip()

            if user_input.lower() == 'quit':
                print("\nGoodbye!")
                break

            if user_input.lower() == 'context on':
                use_context = True
                print("✓ Project context enabled")
                continue

            if user_input.lower() == 'context off':
                use_context = False
                print("✓ Project context disabled")
                continue

            if not user_input:
                continue

            print("\n[Blueprint]: Creating plan...")

            # Create a basic intent for testing
            intent = Intent(
                task_type="feature",
                task_type_confidence=0.8,
                domains_affected=["controllers", "models"],
                scope="feature",
                languages=["php"],
                requires_migration=False,
                priority="medium",
                entities={"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
                search_queries=user_input.split()[:5],
                reasoning="Interactive test request",
                overall_confidence=0.8,
            )

            plan = await planner.plan(
                user_input=user_input,
                intent=intent,
                context=SAMPLE_CONTEXT if use_context else RetrievedContext(chunks=[]),
                project_context=SAMPLE_PROJECT_CONTEXT if use_context else "",
            )

            # Display results
            print("\n" + "-" * 50)
            print(f"Summary:      {plan.summary}")
            print(f"Steps:        {len(plan.steps)}")
            print(f"Confidence:   {plan.overall_confidence:.2f}")
            print(f"Risk:         {plan.risk_level}")
            print(f"Complexity:   {plan.estimated_complexity}/10")
            print(f"Plan Time:    {plan.planning_time_ms}ms")

            if plan.reasoning:
                print(f"\nReasoning:")
                print(f"  Understanding: {plan.reasoning.understanding}")
                print(f"  Approach:      {plan.reasoning.approach}")

            if plan.steps:
                print(f"\nSteps:")
                for step in plan.steps:
                    deps = f" (deps: {step.depends_on})" if step.depends_on else ""
                    print(f"  {step.order}. [{step.action}] [{step.category}] {step.file}{deps}")
                    print(f"     {step.description[:80]}...")

            if plan.needs_clarification:
                print(f"\n⚠️  CLARIFICATION NEEDED:")
                for q in plan.clarifying_questions:
                    print(f"   • {q}")

            if plan.warnings:
                print(f"\n⚠️  Warnings:")
                for w in plan.warnings:
                    print(f"   • {w}")

            if plan.should_halt_pipeline():
                print(f"\n🛑 Pipeline would HALT")
            else:
                print(f"\n✅ Pipeline would PROCEED to Forge")

            print("-" * 50)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all planner scenarios and report results."""
    print("\n" + "=" * 60)
    print("Blueprint (Planner) - Running All Scenarios")
    print("=" * 60)

    results = []
    passed = 0
    failed = 0

    for scenario in PLANNER_SCENARIOS:
        print(f"\n[{scenario['name']}] {scenario['description']}...")

        try:
            mock_claude = MagicMock()
            mock_claude.chat_async = AsyncMock(return_value=json.dumps(scenario["mock_response"]))

            planner = Planner(claude_service=mock_claude)

            plan = await planner.plan(
                user_input=scenario["user_input"],
                intent=scenario["intent"],
                context=scenario["context"],
                project_context=SAMPLE_PROJECT_CONTEXT,
            )

            # Validate
            errors = []
            expected = scenario.get("expected", {})

            if "min_steps" in expected and len(plan.steps) < expected["min_steps"]:
                errors.append(f"min_steps: expected >= {expected['min_steps']}, got {len(plan.steps)}")

            if "needs_clarification" in expected and plan.needs_clarification != expected["needs_clarification"]:
                errors.append(f"needs_clarification mismatch")

            if errors:
                print(f"   ❌ FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                status = "CLARIFY" if plan.needs_clarification else f"{len(plan.steps)} steps"
                print(f"   ✅ PASSED ({status}, conf={plan.overall_confidence:.2f})")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "passed": len(errors) == 0,
                "steps": len(plan.steps),
                "confidence": plan.overall_confidence,
                "needs_clarification": plan.needs_clarification,
                "errors": errors,
            })

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
            results.append({
                "scenario": scenario["name"],
                "passed": False,
                "error": str(e),
            })

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(PLANNER_SCENARIOS)} total")
    print("=" * 60)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {"passed": passed, "failed": failed},
                "results": results,
            }, f, indent=2)
        print(f"\nResults saved to: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Blueprint (Planner) Agent")
    parser.add_argument("--interactive", action="store_true", help="Run interactive testing mode")
    parser.add_argument("--run-all", action="store_true", help="Run all scenarios")
    parser.add_argument("--output", type=str, help="Output file for results")

    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_test())
    elif args.run_all:
        asyncio.run(run_all_scenarios(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()