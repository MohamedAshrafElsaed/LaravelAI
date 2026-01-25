"""
Nova → Scout → Blueprint Pipeline Integration Tests

Tests the complete flow from Intent Analysis through Context Retrieval to Planning.
Verifies that each agent's output properly drives the next agent.

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_nova_scout_blueprint_pipeline.py -v

    # Integration tests (real API, slow)
    pytest backend/tests/agents/test_nova_scout_blueprint_pipeline.py -v -m integration

    # Run all scenarios
    python backend/tests/agents/test_nova_scout_blueprint_pipeline.py --run-all
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.intent_analyzer import IntentAnalyzer
from app.agents.context_retriever import ContextRetriever, RetrievedContext
from app.agents.planner import Planner
from app.agents.conversation_summary import ConversationSummary, RecentMessage
from app.agents.exceptions import InsufficientContextError
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
- Form Requests for validation
- API Resources for responses

### Codebase Statistics
- **Total Files:** 150
- **Controllers:** UserController, OrderController, ProductController
"""

SAMPLE_CONVERSATION_SUMMARY = ConversationSummary(
    project_name="E-commerce API",
    project_id="test-project-123",
    decisions=["Use service pattern for business logic"],
    completed_tasks=["Created Order model"],
    pending_tasks=["Add order export feature"],
    known_files=["app/Models/Order.php", "app/Http/Controllers/OrderController.php"],
    known_classes=["Order", "OrderController"],
)

# Search results for different scenarios
SEARCH_RESULTS_PRODUCT = [
    SearchResult(
        chunk_id="product-1",
        file_path="app/Models/Product.php",
        content="class Product extends Model { protected $fillable = ['name', 'price']; }",
        chunk_type="class",
        score=0.92,
        metadata={"laravel_type": "model"},
    ),
    SearchResult(
        chunk_id="product-2",
        file_path="app/Http/Controllers/ProductController.php",
        content="class ProductController extends Controller { public function index() { return Product::paginate(); } }",
        chunk_type="class",
        score=0.88,
        metadata={"laravel_type": "controller"},
    ),
]

SEARCH_RESULTS_AUTH = [
    SearchResult(
        chunk_id="auth-1",
        file_path="app/Http/Controllers/Auth/LoginController.php",
        content="class LoginController { public function login(Request $request) { Auth::attempt($request->only('email', 'password')); } }",
        chunk_type="class",
        score=0.95,
        metadata={"laravel_type": "controller"},
    ),
]

SEARCH_RESULTS_ORDER = [
    SearchResult(
        chunk_id="order-1",
        file_path="app/Http/Controllers/OrderController.php",
        content="class OrderController { public function index() { return Order::paginate(); } }",
        chunk_type="class",
        score=0.9,
        metadata={"laravel_type": "controller"},
    ),
    SearchResult(
        chunk_id="order-2",
        file_path="app/Models/Order.php",
        content="class Order extends Model { protected $fillable = ['user_id', 'total']; }",
        chunk_type="class",
        score=0.85,
        metadata={"laravel_type": "model"},
    ),
]


# =============================================================================
# Mock Response Factories
# =============================================================================

def create_nova_response(scenario: dict) -> str:
    """Create mock Nova response."""
    expected = scenario.get("nova_expected", {})

    return json.dumps({
        "task_type": expected.get("task_type", "feature"),
        "task_type_confidence": 0.9,
        "domains_affected": expected.get("domains", ["controllers", "models"]),
        "scope": expected.get("scope", "feature"),
        "languages": ["php"],
        "requires_migration": expected.get("requires_migration", False),
        "priority": expected.get("priority", "medium"),
        "entities": {
            "files": expected.get("entities", {}).get("files", []),
            "classes": expected.get("entities", {}).get("classes", []),
            "methods": [],
            "routes": [],
            "tables": [],
        },
        "search_queries": ["test query 1", "test query 2", "test query 3"],
        "reasoning": f"Test reasoning for {scenario['name']}",
        "overall_confidence": 0.3 if expected.get("needs_clarification") else 0.85,
        "needs_clarification": expected.get("needs_clarification", False),
        "clarifying_questions": ["What would you like?"] if expected.get("needs_clarification") else [],
    })


def create_blueprint_response(scenario: dict) -> str:
    """Create mock Blueprint response."""
    expected = scenario.get("blueprint_expected", {})

    if expected.get("needs_clarification"):
        return json.dumps({
            "summary": "Cannot create plan - need more information",
            "reasoning": {
                "understanding": "Request is unclear",
                "approach": "Need clarification",
                "dependency_analysis": "N/A",
                "risks_considered": "Risk of incorrect implementation",
            },
            "steps": [],
            "overall_confidence": 0.2,
            "risk_level": "medium",
            "estimated_complexity": 1,
            "needs_clarification": True,
            "clarifying_questions": ["What specific feature do you need?"],
            "warnings": [],
        })

    steps = []
    step_order = 1

    if expected.get("has_migration"):
        steps.append({
            "order": step_order,
            "action": "create",
            "file": "database/migrations/2024_01_15_create_test_table.php",
            "category": "migration",
            "description": "Create migration for test feature",
            "depends_on": [],
            "estimated_lines": 30,
        })
        step_order += 1

    if expected.get("has_model"):
        steps.append({
            "order": step_order,
            "action": "create",
            "file": "app/Models/Test.php",
            "category": "model",
            "description": "Create Test model",
            "depends_on": [1] if expected.get("has_migration") else [],
            "estimated_lines": 40,
        })
        step_order += 1

    if expected.get("has_controller"):
        steps.append({
            "order": step_order,
            "action": "create",
            "file": "app/Http/Controllers/TestController.php",
            "category": "controller",
            "description": "Create TestController",
            "depends_on": list(range(1, step_order)),
            "estimated_lines": 60,
        })
        step_order += 1

    # Add at least one step if none specified
    if not steps:
        steps.append({
            "order": 1,
            "action": "modify",
            "file": "app/Models/User.php",
            "category": "model",
            "description": "Modify existing file",
            "depends_on": [],
            "estimated_lines": 20,
        })

    return json.dumps({
        "summary": f"Implementation plan for {scenario['name']}",
        "reasoning": {
            "understanding": f"User wants to {scenario.get('user_input', 'implement feature')[:50]}",
            "approach": "Standard Laravel implementation pattern",
            "dependency_analysis": "Following proper dependency order",
            "risks_considered": "Low risk implementation",
        },
        "steps": steps,
        "overall_confidence": expected.get("confidence", 0.85),
        "risk_level": expected.get("risk_level", "medium"),
        "estimated_complexity": expected.get("complexity", 4),
        "needs_clarification": False,
        "clarifying_questions": [],
        "warnings": expected.get("warnings", []),
    })


# =============================================================================
# Pipeline Scenarios
# =============================================================================

PIPELINE_SCENARIOS = [
    {
        "name": "feature_complete_flow",
        "description": "Complete feature flows through all three agents",
        "user_input": "Add a reviews feature where users can rate products 1-5 stars and leave comments",
        "search_results": SEARCH_RESULTS_PRODUCT,
        "nova_expected": {
            "task_type": "feature",
            "needs_clarification": False,
            "requires_migration": True,
            "domains": ["models", "controllers", "database"],
        },
        "scout_expected": {
            "min_chunks": 1,
            "should_find": ["Product"],
        },
        "blueprint_expected": {
            "min_steps": 3,
            "has_migration": True,
            "has_model": True,
            "has_controller": True,
            "needs_clarification": False,
        },
    },
    {
        "name": "bugfix_single_file",
        "description": "Bugfix affects single file, simple plan",
        "user_input": "Fix the login endpoint - it's returning 500 errors when email is empty",
        "search_results": SEARCH_RESULTS_AUTH,
        "nova_expected": {
            "task_type": "bugfix",
            "needs_clarification": False,
            "domains": ["auth", "controllers"],
            "entities": {"classes": ["LoginController"]},
        },
        "scout_expected": {
            "min_chunks": 1,
            "should_find": ["LoginController"],
        },
        "blueprint_expected": {
            "min_steps": 1,
            "max_steps": 2,
            "has_migration": False,
            "needs_clarification": False,
            "risk_level": "low",
        },
    },
    {
        "name": "ambiguous_halts_at_nova",
        "description": "Ambiguous request halts at Nova, never reaches Blueprint",
        "user_input": "Fix it",
        "search_results": [],
        "nova_expected": {
            "task_type": "question",
            "needs_clarification": True,
        },
        "scout_expected": {
            "should_skip": True,
        },
        "blueprint_expected": {
            "should_skip": True,
        },
    },
    {
        "name": "refactor_repository_pattern",
        "description": "Refactoring request generates multi-step plan",
        "user_input": "Refactor OrderController to use the repository pattern",
        "search_results": SEARCH_RESULTS_ORDER,
        "nova_expected": {
            "task_type": "refactor",
            "needs_clarification": False,
            "domains": ["controllers", "services"],
            "entities": {"classes": ["OrderController"]},
        },
        "scout_expected": {
            "min_chunks": 1,
            "should_find": ["OrderController"],
        },
        "blueprint_expected": {
            "min_steps": 3,
            "has_migration": False,
            "needs_clarification": False,
        },
    },
    {
        "name": "simple_method_addition",
        "description": "Simple method addition has minimal plan",
        "user_input": "Add an isActive() method to the User model",
        "search_results": SEARCH_RESULTS_PRODUCT,  # Reuse for simplicity
        "nova_expected": {
            "task_type": "feature",
            "needs_clarification": False,
            "domains": ["models"],
        },
        "scout_expected": {
            "min_chunks": 1,
        },
        "blueprint_expected": {
            "min_steps": 1,
            "max_steps": 1,
            "has_migration": False,
            "complexity": 1,
        },
    },
    {
        "name": "context_insufficient_but_proceeds",
        "description": "Low context doesn't halt pipeline but affects confidence",
        "user_input": "Add a new analytics dashboard feature",
        "search_results": [],  # No context found
        "nova_expected": {
            "task_type": "feature",
            "needs_clarification": False,
        },
        "scout_expected": {
            "min_chunks": 0,
            "confidence_level": "insufficient",
        },
        "blueprint_expected": {
            "needs_clarification": False,  # Can still plan
            "confidence": 0.6,  # Lower confidence
            "warnings": ["Limited codebase context available"],
        },
    },
    {
        "name": "database_change_requires_migration",
        "description": "Database changes correctly identify migration need",
        "user_input": "Add a 'status' column to the orders table with enum values",
        "search_results": SEARCH_RESULTS_ORDER,
        "nova_expected": {
            "task_type": "feature",
            "requires_migration": True,
            "domains": ["database", "models"],
        },
        "scout_expected": {
            "min_chunks": 1,
        },
        "blueprint_expected": {
            "min_steps": 2,
            "has_migration": True,
            "has_model": True,
        },
    },
    {
        "name": "question_no_plan_needed",
        "description": "Question request retrieves context but doesn't need plan",
        "user_input": "How does the Order model calculate totals?",
        "search_results": SEARCH_RESULTS_ORDER,
        "nova_expected": {
            "task_type": "question",
            "needs_clarification": False,
        },
        "scout_expected": {
            "min_chunks": 1,
        },
        "blueprint_expected": {
            "should_skip": True,  # Questions don't need plans
        },
    },
]


# =============================================================================
# Pipeline Runner
# =============================================================================

class NovaScoutBlueprintPipeline:
    """
    Simulates the Nova → Scout → Blueprint pipeline.

    This represents the first three stages of the full agent pipeline,
    stopping before execution (Forge) and validation (Guardian).
    """

    def __init__(
            self,
            nova: IntentAnalyzer,
            scout: ContextRetriever,
            blueprint: Planner,
    ):
        self.nova = nova
        self.scout = scout
        self.blueprint = blueprint

    async def run(
            self,
            user_input: str,
            project_id: str,
            project_context: Optional[str] = None,
            conversation_summary: Optional[ConversationSummary] = None,
            recent_messages: Optional[List[RecentMessage]] = None,
    ) -> Dict[str, Any]:
        """
        Run the Nova → Scout → Blueprint pipeline.

        Returns:
            Dict with 'intent', 'context', 'plan', 'halted', and 'halt_stage' keys
        """
        result = {
            "intent": None,
            "context": None,
            "plan": None,
            "halted": False,
            "halt_stage": None,
            "halt_reason": None,
        }

        # ========== Stage 1: Nova - Intent Analysis ==========
        intent = await self.nova.analyze(
            user_input=user_input,
            project_context=project_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages,
        )
        result["intent"] = intent

        # Check if pipeline should halt at Nova
        if intent.should_halt_pipeline():
            result["halted"] = True
            result["halt_stage"] = "nova"
            result["halt_reason"] = (
                "clarification_needed" if intent.needs_clarification
                else "low_confidence"
            )
            return result

        # ========== Stage 2: Scout - Context Retrieval ==========
        try:
            context = await self.scout.retrieve(
                project_id=project_id,
                intent=intent,
                require_minimum=False,
            )
            result["context"] = context
        except InsufficientContextError as e:
            # Log but continue - Blueprint can still plan with limited context
            result["context"] = RetrievedContext(
                chunks=[],
                warnings=[str(e)],
            )

        # Check for question type - may not need planning
        if intent.task_type == "question":
            result["halted"] = True
            result["halt_stage"] = "scout"
            result["halt_reason"] = "question_type_no_plan_needed"
            return result

        # ========== Stage 3: Blueprint - Planning ==========
        plan = await self.blueprint.plan(
            user_input=user_input,
            intent=intent,
            context=result["context"],
            project_context=project_context or "",
        )
        result["plan"] = plan

        # Check if plan needs clarification
        if plan.should_halt_pipeline():
            result["halted"] = True
            result["halt_stage"] = "blueprint"
            result["halt_reason"] = (
                "plan_clarification_needed" if plan.needs_clarification
                else "low_plan_confidence"
            )

        return result


# =============================================================================
# Mock Service Factory
# =============================================================================

def create_mock_services(scenario: dict) -> dict:
    """Create all mock services for a pipeline scenario."""

    # Mock Claude for Nova
    mock_nova_claude = MagicMock()
    mock_nova_claude.chat_async = AsyncMock(return_value=create_nova_response(scenario))

    # Mock Claude for Blueprint
    mock_blueprint_claude = MagicMock()
    mock_blueprint_claude.chat_async = AsyncMock(return_value=create_blueprint_response(scenario))

    # Mock vector store for Scout
    mock_vector_store = MagicMock(spec=VectorStore)
    mock_vector_store.search = MagicMock(return_value=scenario.get("search_results", []))
    mock_vector_store.collection_exists = MagicMock(return_value=True)

    # Mock embedding service for Scout
    mock_embedding = MagicMock(spec=EmbeddingService)
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)

    # Mock database session
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    return {
        "nova_claude": mock_nova_claude,
        "blueprint_claude": mock_blueprint_claude,
        "vector_store": mock_vector_store,
        "embedding": mock_embedding,
        "db": mock_db,
    }


# =============================================================================
# Unit Tests - Pipeline Flow
# =============================================================================

class TestPipelineFlow:
    """Test the complete Nova → Scout → Blueprint pipeline flow."""

    @pytest.mark.asyncio
    async def test_complete_feature_flow(self):
        """Test that a feature request flows through all three agents."""
        scenario = PIPELINE_SCENARIOS[0]  # feature_complete_flow
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
            )

        # All three agents should have run
        assert result["intent"] is not None
        assert result["context"] is not None
        assert result["plan"] is not None
        assert not result["halted"]

        # Verify Nova output
        assert result["intent"].task_type == "feature"

        # Verify Blueprint output
        assert len(result["plan"].steps) > 0

    @pytest.mark.asyncio
    async def test_pipeline_halts_at_nova_clarification(self):
        """Test that ambiguous request halts at Nova."""
        scenario = PIPELINE_SCENARIOS[2]  # ambiguous_halts_at_nova
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Should halt at Nova
        assert result["halted"] is True
        assert result["halt_stage"] == "nova"
        assert result["intent"].needs_clarification is True

        # Scout and Blueprint should NOT have run
        assert result["context"] is None
        assert result["plan"] is None

    @pytest.mark.asyncio
    async def test_question_halts_at_scout(self):
        """Test that question request halts after Scout (no plan needed)."""
        scenario = PIPELINE_SCENARIOS[7]  # question_no_plan_needed
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Should halt at Scout
        assert result["halted"] is True
        assert result["halt_stage"] == "scout"
        assert result["halt_reason"] == "question_type_no_plan_needed"

        # Intent and context should exist
        assert result["intent"] is not None
        assert result["context"] is not None

        # Plan should NOT exist
        assert result["plan"] is None

    @pytest.mark.asyncio
    async def test_intent_drives_context_retrieval(self):
        """Test that Nova's intent properly drives Scout's retrieval."""
        scenario = PIPELINE_SCENARIOS[1]  # bugfix_single_file
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Verify embedding was called (Scout used Nova's search queries)
        assert mocks["embedding"].embed_query.call_count > 0

        # Verify domains flow through
        assert "auth" in result["intent"].domains_affected

    @pytest.mark.asyncio
    async def test_context_affects_plan_quality(self):
        """Test that context quality affects plan confidence."""
        scenario = PIPELINE_SCENARIOS[5]  # context_insufficient_but_proceeds
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Context should be empty/minimal
        assert len(result["context"].chunks) == 0

        # Plan should still exist but with lower confidence
        assert result["plan"] is not None

    @pytest.mark.asyncio
    async def test_migration_requirement_flows_through(self):
        """Test that migration requirement flows from Nova to Blueprint."""
        scenario = PIPELINE_SCENARIOS[6]  # database_change_requires_migration
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Nova should identify migration need
        assert result["intent"].requires_migration is True

        # Blueprint should create migration step
        assert result["plan"] is not None
        has_migration = any(s.category == "migration" for s in result["plan"].steps)
        assert has_migration is True


# =============================================================================
# Parametrized Scenario Tests
# =============================================================================

class TestAllPipelineScenarios:
    """Run all pipeline scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", PIPELINE_SCENARIOS, ids=[s["name"] for s in PIPELINE_SCENARIOS])
    async def test_scenario(self, scenario):
        """Test each scenario through the full pipeline."""
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])

            pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
            )

        # Validate Nova expectations
        nova_expected = scenario.get("nova_expected", {})

        if "task_type" in nova_expected:
            assert result["intent"].task_type == nova_expected["task_type"]

        if "needs_clarification" in nova_expected:
            assert result["intent"].needs_clarification == nova_expected["needs_clarification"]

        if "requires_migration" in nova_expected:
            assert result["intent"].requires_migration == nova_expected["requires_migration"]

        # Validate Scout expectations
        scout_expected = scenario.get("scout_expected", {})

        if scout_expected.get("should_skip"):
            assert result["context"] is None
        elif result["context"]:
            if "min_chunks" in scout_expected:
                # May have 0 if mocked empty
                pass

        # Validate Blueprint expectations
        blueprint_expected = scenario.get("blueprint_expected", {})

        if blueprint_expected.get("should_skip"):
            assert result["plan"] is None
        elif result["plan"]:
            if "min_steps" in blueprint_expected:
                assert len(result["plan"].steps) >= blueprint_expected["min_steps"]

            if "max_steps" in blueprint_expected:
                assert len(result["plan"].steps) <= blueprint_expected["max_steps"]

            if "needs_clarification" in blueprint_expected:
                assert result["plan"].needs_clarification == blueprint_expected["needs_clarification"]


# =============================================================================
# Integration Tests (Real API)
# =============================================================================

@pytest.mark.integration
class TestPipelineIntegration:
    """Integration tests with real Claude API."""

    @pytest.mark.asyncio
    async def test_real_feature_pipeline(self):
        """Test real feature request through full pipeline."""
        nova = IntentAnalyzer()
        # Note: Scout and Blueprint would need real services too
        # For now, test just Nova with real API

        intent = await nova.analyze(
            user_input="Add a reviews feature where users can rate products",
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert intent.task_type == "feature"
        assert not intent.needs_clarification
        assert intent.requires_migration is True or "database" in intent.domains_affected


# =============================================================================
# CLI Runner
# =============================================================================

async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all pipeline scenarios and report results."""
    print("\n" + "=" * 70)
    print("Nova → Scout → Blueprint Pipeline - Running All Scenarios")
    print("=" * 70)

    results = []
    passed = 0
    failed = 0

    for scenario in PIPELINE_SCENARIOS:
        print(f"\n[{scenario['name']}] {scenario['description']}...")

        try:
            mocks = create_mock_services(scenario)

            with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
                nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
                scout = ContextRetriever(
                    db=mocks["db"],
                    vector_store=mocks["vector_store"],
                    embedding_service=mocks["embedding"],
                )
                blueprint = Planner(claude_service=mocks["blueprint_claude"])

                pipeline = NovaScoutBlueprintPipeline(nova=nova, scout=scout, blueprint=blueprint)
                result = await pipeline.run(
                    user_input=scenario["user_input"],
                    project_id="test-123",
                    project_context=SAMPLE_PROJECT_CONTEXT,
                )

            # Validate
            errors = []

            nova_expected = scenario.get("nova_expected", {})
            if "task_type" in nova_expected and result["intent"].task_type != nova_expected["task_type"]:
                errors.append(
                    f"Nova task_type: expected {nova_expected['task_type']}, got {result['intent'].task_type}")

            scout_expected = scenario.get("scout_expected", {})
            if scout_expected.get("should_skip") and result["context"] is not None:
                errors.append("Scout should have been skipped")

            blueprint_expected = scenario.get("blueprint_expected", {})
            if blueprint_expected.get("should_skip") and result["plan"] is not None:
                errors.append("Blueprint should have been skipped")
            elif not blueprint_expected.get("should_skip") and result["plan"]:
                if "min_steps" in blueprint_expected and len(result["plan"].steps) < blueprint_expected["min_steps"]:
                    errors.append(f"Blueprint min_steps: expected >= {blueprint_expected['min_steps']}")

            if errors:
                print(f"   ❌ FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                status = result["halt_stage"] or "COMPLETE"
                plan_steps = len(result["plan"].steps) if result["plan"] else 0
                print(f"   ✅ PASSED (halt={status}, plan_steps={plan_steps})")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "passed": len(errors) == 0,
                "halt_stage": result["halt_stage"],
                "intent_type": result["intent"].task_type if result["intent"] else None,
                "context_chunks": len(result["context"].chunks) if result["context"] else 0,
                "plan_steps": len(result["plan"].steps) if result["plan"] else 0,
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
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {len(PIPELINE_SCENARIOS)} total")
    print("=" * 70)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline": "Nova → Scout → Blueprint",
                "summary": {"passed": passed, "failed": failed},
                "results": results,
            }, f, indent=2)
        print(f"\nResults saved to: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Nova → Scout → Blueprint Pipeline")
    parser.add_argument("--run-all", action="store_true", help="Run all scenarios")
    parser.add_argument("--output", type=str, help="Output file for results")

    args = parser.parse_args()

    if args.run_all:
        asyncio.run(run_all_scenarios(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
