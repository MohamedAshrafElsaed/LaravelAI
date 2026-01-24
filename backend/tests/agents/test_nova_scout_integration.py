"""
Nova → Scout Integration Tests

Tests the pipeline flow from Intent Analysis (Nova) to Context Retrieval (Scout).
Verifies that intent output properly drives context retrieval.

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_nova_scout_integration.py -v

    # Integration tests (real API, slow)
    pytest backend/tests/agents/test_nova_scout_integration.py -v -m integration

    # Run all scenarios
    python backend/tests/agents/test_nova_scout_integration.py --run-all
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

from app.agents.intent_analyzer import IntentAnalyzer, Intent, analyze_intent
from app.agents.context_retriever import ContextRetriever, RetrievedContext, CodeChunk
from app.agents.conversation_summary import ConversationSummary, RecentMessage
from app.agents.config import AgentConfig
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

# Mock search results that match different intents
SEARCH_RESULTS_USER = [
    SearchResult(
        chunk_id="user-1",
        file_path="app/Http/Controllers/UserController.php",
        content=(
            "class UserController extends Controller {\n"
            "    public function store(Request $request) {\n"
            "        return User::create($request->validated());\n"
            "    }\n"
            "}"
        ),
        chunk_type="class",
        score=0.92,
        metadata={"laravel_type": "controller"},
    ),
    SearchResult(
        chunk_id="user-2",
        file_path="app/Models/User.php",
        content="class User extends Authenticatable { protected $fillable = ['name', 'email']; }",
        chunk_type="class",
        score=0.88,
        metadata={"laravel_type": "model"},
    ),
]

SEARCH_RESULTS_AUTH = [
    SearchResult(
        chunk_id="auth-1",
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
        score=0.95,
        metadata={"laravel_type": "controller"},
    ),
    SearchResult(
        chunk_id="auth-2",
        file_path="app/Http/Middleware/Authenticate.php",
        content="class Authenticate extends Middleware { }",
        chunk_type="class",
        score=0.75,
        metadata={"laravel_type": "middleware"},
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
# Pipeline Integration Test Scenarios
# =============================================================================

PIPELINE_SCENARIOS = [
    {
        "name": "feature_user_export",
        "description": "Feature request flows through both agents",
        "user_input": "Add an export method to the UserController that generates CSV files",
        "nova_expected": {
            "task_type": "feature",
            "needs_clarification": False,
            "entities_should_contain": {"classes": ["UserController"]},
        },
        "scout_expected": {
            "min_chunks": 1,
            "should_find_patterns": ["UserController", "Controller"],
        },
        "search_results": SEARCH_RESULTS_USER,
    },
    {
        "name": "bugfix_auth_flow",
        "description": "Bugfix request properly retrieves auth context",
        "user_input": "Fix the login endpoint - it's returning 500 errors",
        "nova_expected": {
            "task_type": "bugfix",
            "priority_in": ["high", "critical"],
            "domains_should_contain": ["auth"],
        },
        "scout_expected": {
            "min_chunks": 1,
            "should_find_patterns": ["Login", "Auth"],
        },
        "search_results": SEARCH_RESULTS_AUTH,
    },
    {
        "name": "clarification_halts_pipeline",
        "description": "Ambiguous request halts at Nova",
        "user_input": "Fix the bug",
        "nova_expected": {
            "needs_clarification": True,
        },
        "scout_expected": {
            "should_skip": True,  # Scout should not run
        },
        "search_results": [],
    },
    {
        "name": "context_continuation",
        "description": "Continuation request uses conversation context",
        "user_input": "Now add pagination to it",
        "use_conversation_context": True,
        "nova_expected": {
            "task_type": "feature",
        },
        "scout_expected": {
            "min_chunks": 0,  # May or may not find context
        },
        "search_results": SEARCH_RESULTS_ORDER,
    },
    {
        "name": "database_feature",
        "description": "Database feature identifies migration need",
        "user_input": "Add a 'status' column to the orders table",
        "nova_expected": {
            "task_type": "feature",
            "requires_migration": True,
            "domains_should_contain": ["database"],
        },
        "scout_expected": {
            "min_chunks": 1,
        },
        "search_results": SEARCH_RESULTS_ORDER,
    },
    {
        "name": "refactor_request",
        "description": "Refactor request flows correctly",
        "user_input": "Refactor the OrderController to use the repository pattern",
        "nova_expected": {
            "task_type": "refactor",
            "entities_should_contain": {"classes": ["OrderController"]},
        },
        "scout_expected": {
            "min_chunks": 1,
            "should_find_patterns": ["OrderController"],
        },
        "search_results": SEARCH_RESULTS_ORDER,
    },
    {
        "name": "question_no_modification",
        "description": "Question request retrieves context but doesn't modify",
        "user_input": "How does the User model handle authentication?",
        "nova_expected": {
            "task_type": "question",
            "priority": "low",
        },
        "scout_expected": {
            "min_chunks": 1,
        },
        "search_results": SEARCH_RESULTS_USER,
    },
    {
        "name": "multi_domain_feature",
        "description": "Cross-domain feature retrieves from multiple areas",
        "user_input": "Add email notifications when orders are placed",
        "nova_expected": {
            "task_type": "feature",
            "scope": "cross_domain",
            "domains_should_contain": ["mail"],
        },
        "scout_expected": {
            "min_chunks": 1,
        },
        "search_results": SEARCH_RESULTS_ORDER,
    },
]


# =============================================================================
# Mock Factories
# =============================================================================

def create_nova_mock_response(scenario: dict) -> str:
    """Create mock Nova response based on scenario expectations."""
    expected = scenario.get("nova_expected", {})

    return json.dumps({
        "task_type": expected.get("task_type", "feature"),
        "task_type_confidence": 0.9,
        "domains_affected": expected.get("domains_should_contain", ["controllers"]),
        "scope": expected.get("scope", "single_file"),
        "languages": ["php"],
        "requires_migration": expected.get("requires_migration", False),
        "priority": expected.get("priority", expected.get("priority_in", ["medium"])[0] if "priority_in" in expected else "medium"),
        "entities": {
            "files": expected.get("entities_should_contain", {}).get("files", []),
            "classes": expected.get("entities_should_contain", {}).get("classes", []),
            "methods": expected.get("entities_should_contain", {}).get("methods", []),
            "routes": expected.get("entities_should_contain", {}).get("routes", []),
            "tables": expected.get("entities_should_contain", {}).get("tables", []),
        },
        "search_queries": ["test query 1", "test query 2", "test query 3"],
        "reasoning": f"Test reasoning for {scenario['name']}",
        "overall_confidence": 0.3 if expected.get("needs_clarification") else 0.85,
        "needs_clarification": expected.get("needs_clarification", False),
        "clarifying_questions": ["What would you like to fix?"] if expected.get("needs_clarification") else [],
    })


def create_mock_services(scenario: dict):
    """Create all mock services for a scenario."""
    # Mock Claude service for Nova
    mock_claude = MagicMock()
    mock_claude.chat_async = AsyncMock(return_value=create_nova_mock_response(scenario))

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
        "claude": mock_claude,
        "vector_store": mock_vector_store,
        "embedding": mock_embedding,
        "db": mock_db,
    }


# =============================================================================
# Pipeline Runner
# =============================================================================

class NovaSC0utPipeline:
    """Simulates the Nova → Scout pipeline for testing."""

    def __init__(
        self,
        nova: IntentAnalyzer,
        scout: ContextRetriever,
    ):
        self.nova = nova
        self.scout = scout

    async def run(
        self,
        user_input: str,
        project_id: str,
        project_context: Optional[str] = None,
        conversation_summary: Optional[ConversationSummary] = None,
        recent_messages: Optional[List[RecentMessage]] = None,
    ) -> Dict[str, Any]:
        """
        Run the Nova → Scout pipeline.

        Returns:
            Dict with 'intent', 'context', and 'halted' keys
        """
        result = {
            "intent": None,
            "context": None,
            "halted": False,
            "halt_reason": None,
        }

        # Step 1: Nova - Intent Analysis
        intent = await self.nova.analyze(
            user_input=user_input,
            project_context=project_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages,
        )
        result["intent"] = intent

        # Check if pipeline should halt
        if intent.should_halt_pipeline():
            result["halted"] = True
            result["halt_reason"] = "clarification_needed" if intent.needs_clarification else "low_confidence"
            return result

        # Step 2: Scout - Context Retrieval
        try:
            context = await self.scout.retrieve(
                project_id=project_id,
                intent=intent,
                require_minimum=False,  # Don't raise exception for tests
            )
            result["context"] = context
        except InsufficientContextError as e:
            result["halted"] = True
            result["halt_reason"] = "insufficient_context"
            result["error"] = str(e)

        return result


# =============================================================================
# Unit Tests - Pipeline Flow
# =============================================================================

class TestNovaScoutPipelineUnit:
    """Unit tests for Nova → Scout pipeline with mocked services."""

    @pytest.mark.asyncio
    async def test_basic_pipeline_flow(self):
        """Test basic pipeline flow from Nova to Scout."""
        scenario = PIPELINE_SCENARIOS[0]  # feature_user_export
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
            )

        # Verify Nova ran
        assert result["intent"] is not None
        assert result["intent"].task_type == "feature"

        # Verify Scout ran
        assert result["context"] is not None
        assert not result["halted"]

    @pytest.mark.asyncio
    async def test_pipeline_halts_on_clarification(self):
        """Test that pipeline halts when Nova needs clarification."""
        scenario = PIPELINE_SCENARIOS[2]  # clarification_halts_pipeline
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Verify pipeline halted
        assert result["halted"] is True
        assert result["halt_reason"] == "clarification_needed"

        # Verify Scout did NOT run
        assert result["context"] is None
        mocks["embedding"].embed_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_intent_search_queries_used(self):
        """Test that Nova's search queries are passed to Scout."""
        scenario = PIPELINE_SCENARIOS[0]
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Verify embedding was called for search queries
        assert mocks["embedding"].embed_query.call_count > 0

    @pytest.mark.asyncio
    async def test_conversation_context_flows_through(self):
        """Test that conversation context is used in Nova."""
        scenario = PIPELINE_SCENARIOS[3]  # context_continuation
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
                conversation_summary=SAMPLE_CONVERSATION_SUMMARY,
            )

        # Verify Claude was called with conversation context
        call_args = mocks["claude"].chat_async.call_args
        messages = call_args.kwargs.get('messages', call_args.args[0] if call_args.args else [])
        message_str = str(messages)

        assert "E-commerce API" in message_str or "Order" in message_str

    @pytest.mark.asyncio
    async def test_domains_affect_context_retrieval(self):
        """Test that intent domains influence context retrieval."""
        scenario = PIPELINE_SCENARIOS[1]  # bugfix_auth_flow
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Verify auth domain is in intent
        assert "auth" in result["intent"].domains_affected

        # Verify context has domain summaries
        if result["context"]:
            assert "auth" in result["context"].domain_summaries


# =============================================================================
# Unit Tests - Error Handling
# =============================================================================

class TestNovaScoutErrorHandling:
    """Test error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_nova_error_creates_fallback_intent(self):
        """Test that Nova errors create a fallback intent."""
        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(side_effect=Exception("API Error"))

        mocks = create_mock_services(PIPELINE_SCENARIOS[0])
        mocks["claude"] = mock_claude

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input="test input",
                project_id="test-123",
            )

        # Should halt with error fallback
        assert result["halted"] is True
        assert result["intent"].needs_clarification is True

    @pytest.mark.asyncio
    async def test_scout_error_handled_gracefully(self):
        """Test that Scout errors are handled gracefully."""
        scenario = PIPELINE_SCENARIOS[0]
        mocks = create_mock_services(scenario)

        # Make vector store raise an error
        mocks["vector_store"].search = MagicMock(side_effect=Exception("Search failed"))

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Should have intent but may have empty context
        assert result["intent"] is not None
        # Context retrieval should handle error gracefully
        assert result["context"] is not None or "error" in result

    @pytest.mark.asyncio
    async def test_embedding_error_continues_pipeline(self):
        """Test that embedding errors don't crash the pipeline."""
        scenario = PIPELINE_SCENARIOS[0]
        mocks = create_mock_services(scenario)

        # Make embedding return None (failure)
        mocks["embedding"].embed_query = AsyncMock(return_value=None)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Should complete without crashing
        assert result["intent"] is not None


# =============================================================================
# Unit Tests - Intent → Context Validation
# =============================================================================

class TestIntentContextValidation:
    """Test that intent properly drives context retrieval."""

    @pytest.mark.asyncio
    async def test_feature_intent_retrieves_relevant_context(self):
        """Test feature intent retrieves relevant code."""
        scenario = PIPELINE_SCENARIOS[0]  # feature_user_export
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Verify context contains relevant files
        if result["context"] and result["context"].chunks:
            file_paths = [c.file_path for c in result["context"].chunks]
            assert any("Controller" in p for p in file_paths)

    @pytest.mark.asyncio
    async def test_bugfix_intent_retrieves_error_related_context(self):
        """Test bugfix intent retrieves error-related code."""
        scenario = PIPELINE_SCENARIOS[1]  # bugfix_auth_flow
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        assert result["intent"].task_type == "bugfix"

        # Context should have auth-related files
        if result["context"] and result["context"].chunks:
            contents = [c.content for c in result["context"].chunks]
            assert any("Auth" in c or "Login" in c for c in contents)

    @pytest.mark.asyncio
    async def test_migration_intent_affects_domains(self):
        """Test that migration-required intent includes database domain."""
        scenario = PIPELINE_SCENARIOS[4]  # database_feature
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        assert result["intent"].requires_migration is True
        assert "database" in result["intent"].domains_affected


# =============================================================================
# Parametrized Scenario Tests
# =============================================================================

class TestAllScenarios:
    """Run all pipeline scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", PIPELINE_SCENARIOS, ids=[s["name"] for s in PIPELINE_SCENARIOS])
    async def test_scenario(self, scenario):
        """Test each scenario through the pipeline."""
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
            nova = IntentAnalyzer(claude_service=mocks["claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )

            pipeline = NovaSC0utPipeline(nova=nova, scout=scout)

            # Build context based on scenario
            conversation_summary = SAMPLE_CONVERSATION_SUMMARY if scenario.get("use_conversation_context") else None

            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
                conversation_summary=conversation_summary,
            )

        # Validate Nova expectations
        nova_expected = scenario.get("nova_expected", {})

        if "task_type" in nova_expected:
            assert result["intent"].task_type == nova_expected["task_type"]

        if "needs_clarification" in nova_expected:
            assert result["intent"].needs_clarification == nova_expected["needs_clarification"]

        if "priority_in" in nova_expected:
            assert result["intent"].priority in nova_expected["priority_in"]

        if "requires_migration" in nova_expected:
            assert result["intent"].requires_migration == nova_expected["requires_migration"]

        if "domains_should_contain" in nova_expected:
            for domain in nova_expected["domains_should_contain"]:
                assert domain in result["intent"].domains_affected

        # Validate Scout expectations (only if not halted)
        scout_expected = scenario.get("scout_expected", {})

        if scout_expected.get("should_skip"):
            assert result["halted"] is True
        elif not result["halted"]:
            if "min_chunks" in scout_expected:
                assert result["context"] is not None


# =============================================================================
# Integration Tests (Real API)
# =============================================================================

@pytest.mark.integration
class TestNovaScoutIntegration:
    """Integration tests with real Claude API."""

    @pytest.fixture
    def real_nova(self):
        """Create real Nova analyzer."""
        return IntentAnalyzer()

    @pytest.mark.asyncio
    async def test_real_feature_request(self, real_nova):
        """Test real feature request through Nova."""
        intent = await real_nova.analyze(
            user_input="Add an export method to the UserController that generates PDF files",
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert intent.task_type == "feature"
        assert not intent.needs_clarification
        assert len(intent.search_queries) > 0

        # Verify entities extracted
        assert "UserController" in intent.entities.get("classes", []) or \
               any("User" in c for c in intent.entities.get("classes", []))

    @pytest.mark.asyncio
    async def test_real_ambiguous_request(self, real_nova):
        """Test real ambiguous request triggers clarification."""
        intent = await real_nova.analyze(
            user_input="Fix it",
            project_context=None,  # No context
        )

        assert intent.needs_clarification is True
        assert len(intent.clarifying_questions) > 0


# =============================================================================
# CLI Runner
# =============================================================================

async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all pipeline scenarios and report results."""
    print("\n" + "=" * 60)
    print("Nova → Scout Pipeline - Running All Scenarios")
    print("=" * 60)

    results = []
    passed = 0
    failed = 0

    for scenario in PIPELINE_SCENARIOS:
        print(f"\n[{scenario['name']}] {scenario['description']}...")

        try:
            mocks = create_mock_services(scenario)

            with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["claude"]):
                nova = IntentAnalyzer(claude_service=mocks["claude"])
                scout = ContextRetriever(
                    db=mocks["db"],
                    vector_store=mocks["vector_store"],
                    embedding_service=mocks["embedding"],
                )

                pipeline = NovaSC0utPipeline(nova=nova, scout=scout)

                conversation_summary = SAMPLE_CONVERSATION_SUMMARY if scenario.get("use_conversation_context") else None

                result = await pipeline.run(
                    user_input=scenario["user_input"],
                    project_id="test-123",
                    project_context=SAMPLE_PROJECT_CONTEXT,
                    conversation_summary=conversation_summary,
                )

            # Validate
            errors = []
            nova_expected = scenario.get("nova_expected", {})
            scout_expected = scenario.get("scout_expected", {})

            if "task_type" in nova_expected and result["intent"].task_type != nova_expected["task_type"]:
                errors.append(f"task_type: expected {nova_expected['task_type']}, got {result['intent'].task_type}")

            if "needs_clarification" in nova_expected and result["intent"].needs_clarification != nova_expected["needs_clarification"]:
                errors.append(f"needs_clarification mismatch")

            if scout_expected.get("should_skip") and not result["halted"]:
                errors.append("Expected pipeline to halt but it continued")

            if errors:
                print(f"   ❌ FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                status = "HALTED" if result["halted"] else "COMPLETED"
                chunks = len(result["context"].chunks) if result["context"] else 0
                print(f"   ✅ PASSED ({status}, chunks={chunks})")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "passed": len(errors) == 0,
                "halted": result["halted"],
                "intent_task_type": result["intent"].task_type,
                "chunks_found": len(result["context"].chunks) if result["context"] else 0,
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
    print(f"Results: {passed} passed, {failed} failed, {len(PIPELINE_SCENARIOS)} total")
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
    parser = argparse.ArgumentParser(description="Test Nova → Scout Pipeline")
    parser.add_argument("--run-all", action="store_true", help="Run all scenarios")
    parser.add_argument("--output", type=str, help="Output file for results")

    args = parser.parse_args()

    if args.run_all:
        asyncio.run(run_all_scenarios(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()