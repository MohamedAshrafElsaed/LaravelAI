"""
Scout (Context Retriever) Agent - Comprehensive Test Suite

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_context_retriever.py -v

    # Integration tests (real services, slow)
    pytest backend/tests/agents/test_context_retriever.py -v -m integration

    # Manual interactive testing
    python backend/tests/agents/test_context_retriever.py --interactive

    # Run all test scenarios and save results
    python backend/tests/agents/test_context_retriever.py --run-all --output results.json
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
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.context_retriever import (
    ContextRetriever,
    CodeChunk,
    RetrievedContext,
    LARAVEL_RELATIONSHIPS,
    DEFAULT_TOKEN_BUDGET,
    CHARS_PER_TOKEN,
)
from app.agents.intent_analyzer import Intent
from app.agents.config import AgentConfig, agent_config
from app.agents.exceptions import InsufficientContextError
from app.services.vector_store import VectorStore, SearchResult
from app.services.embeddings import EmbeddingService, EmbeddingProvider


# =============================================================================
# Test Fixtures and Sample Data
# =============================================================================

SAMPLE_PROJECT_ID = "test-project-123"

SAMPLE_INTENT_FEATURE = Intent(
    task_type="feature",
    task_type_confidence=0.9,
    domains_affected=["controllers", "models", "routing"],
    scope="feature",
    languages=["php"],
    requires_migration=False,
    priority="medium",
    entities={
        "files": ["app/Http/Controllers/UserController.php"],
        "classes": ["UserController", "User"],
        "methods": ["store", "update"],
        "routes": ["/api/users"],
        "tables": ["users"],
    },
    search_queries=[
        "UserController store method",
        "User model",
        "api users route",
    ],
    reasoning="Feature request for user management",
    overall_confidence=0.85,
    needs_clarification=False,
)

SAMPLE_INTENT_BUGFIX = Intent(
    task_type="bugfix",
    task_type_confidence=0.95,
    domains_affected=["auth", "middleware"],
    scope="single_file",
    languages=["php"],
    requires_migration=False,
    priority="high",
    entities={
        "files": [],
        "classes": ["AuthController"],
        "methods": ["login"],
        "routes": [],
        "tables": [],
    },
    search_queries=[
        "AuthController login",
        "authentication middleware",
        "sanctum guard",
    ],
    reasoning="Authentication bug fix",
    overall_confidence=0.9,
    needs_clarification=False,
)

SAMPLE_INTENT_EMPTY_QUERIES = Intent(
    task_type="question",
    task_type_confidence=0.7,
    domains_affected=[],
    scope="single_file",
    languages=["php"],
    requires_migration=False,
    priority="low",
    entities={"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
    search_queries=[],  # Empty queries
    reasoning="General question",
    overall_confidence=0.6,
    needs_clarification=False,
)

SAMPLE_SEARCH_RESULTS = [
    SearchResult(
        chunk_id="chunk-1",
        file_path="app/Http/Controllers/UserController.php",
        content=(
            "<?php\n\n"
            "namespace App\\Http\\Controllers;\n\n"
            "use App\\Models\\User;\n"
            "use Illuminate\\Http\\Request;\n\n"
            "class UserController extends Controller\n"
            "{\n"
            "    public function store(Request $request)\n"
            "    {\n"
            "        $validated = $request->validate([\n"
            "            'name' => 'required|string|max:255',\n"
            "            'email' => 'required|email|unique:users',\n"
            "        ]);\n"
            "        \n"
            "        return User::create($validated);\n"
            "    }\n"
            "}"
        ),
        chunk_type="class",
        score=0.92,
        metadata={
            "name": "UserController",
            "line_start": 1,
            "line_end": 20,
            "laravel_type": "controller",
        },
    ),
    SearchResult(
        chunk_id="chunk-2",
        file_path="app/Models/User.php",
        content=(
            "<?php\n\n"
            "namespace App\\Models;\n\n"
            "use Illuminate\\Foundation\\Auth\\User as Authenticatable;\n\n"
            "class User extends Authenticatable\n"
            "{\n"
            "    protected $fillable = ['name', 'email', 'password'];\n"
            "    \n"
            "    protected $hidden = ['password', 'remember_token'];\n"
            "}"
        ),
        chunk_type="class",
        score=0.88,
        metadata={
            "name": "User",
            "line_start": 1,
            "line_end": 12,
            "laravel_type": "model",
        },
    ),
    SearchResult(
        chunk_id="chunk-3",
        file_path="routes/api.php",
        content=(
            "<?php\n\n"
            "use App\\Http\\Controllers\\UserController;\n\n"
            "Route::apiResource('users', UserController::class);"
        ),
        chunk_type="route",
        score=0.75,
        metadata={
            "line_start": 1,
            "line_end": 5,
            "laravel_type": "route",
        },
    ),
]

SAMPLE_LOW_SCORE_RESULTS = [
    SearchResult(
        chunk_id="chunk-low-1",
        file_path="app/Providers/AppServiceProvider.php",
        content="<?php\n\nnamespace App\\Providers;\n\nclass AppServiceProvider {}",
        chunk_type="class",
        score=0.15,  # Below threshold
        metadata={"laravel_type": "provider"},
    ),
]


# =============================================================================
# Mock Factories
# =============================================================================

def create_mock_vector_store(search_results: List[SearchResult] = None):
    """Create a mock VectorStore with configurable results."""
    mock = MagicMock(spec=VectorStore)
    mock.search = MagicMock(return_value=search_results or SAMPLE_SEARCH_RESULTS)
    mock.collection_exists = MagicMock(return_value=True)
    return mock


def create_mock_embedding_service():
    """Create a mock EmbeddingService."""
    mock = MagicMock(spec=EmbeddingService)
    mock.embed_query = AsyncMock(return_value=[0.1] * 1536)  # Return valid embedding
    return mock


def create_mock_db_session(indexed_files: Dict[str, str] = None):
    """Create a mock database session with IndexedFile results."""
    mock = MagicMock()

    async def mock_execute(stmt):
        result = MagicMock()
        # Return None by default, or content if file exists
        if indexed_files:
            # Extract file path from query if possible
            file_content = list(indexed_files.values())[0] if indexed_files else None
            mock_file = MagicMock()
            mock_file.content = file_content
            result.scalar_one_or_none = MagicMock(return_value=mock_file)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    mock.execute = AsyncMock(side_effect=mock_execute)
    return mock


# =============================================================================
# Unit Tests - CodeChunk
# =============================================================================

class TestCodeChunk:
    """Test CodeChunk dataclass."""

    def test_estimated_tokens(self):
        """Test token estimation."""
        chunk = CodeChunk(
            file_path="test.php",
            content="x" * 400,  # 400 chars
            chunk_type="code",
            start_line=1,
            end_line=10,
            score=0.9,
        )

        # 400 chars / 4 chars per token = 100 tokens
        assert chunk.estimated_tokens == 100

    def test_empty_content_tokens(self):
        """Test token estimation for empty content."""
        chunk = CodeChunk(
            file_path="test.php",
            content="",
            chunk_type="code",
            start_line=1,
            end_line=1,
            score=0.5,
        )

        assert chunk.estimated_tokens == 0

    def test_metadata_default(self):
        """Test default metadata is empty dict."""
        chunk = CodeChunk(
            file_path="test.php",
            content="test",
            chunk_type="code",
            start_line=1,
            end_line=1,
        )

        assert chunk.metadata == {}
        assert chunk.score == 0.0


# =============================================================================
# Unit Tests - RetrievedContext
# =============================================================================

class TestRetrievedContext:
    """Test RetrievedContext dataclass."""

    def test_is_sufficient_with_enough_chunks(self):
        """Test sufficiency check with enough chunks."""
        context = RetrievedContext(
            chunks=[
                CodeChunk("f1.php", "content1", "class", 1, 10, 0.9),
                CodeChunk("f2.php", "content2", "class", 1, 10, 0.8),
            ]
        )

        # Default MIN_CONTEXT_CHUNKS is 1
        assert context.is_sufficient is True

    def test_is_sufficient_empty(self):
        """Test sufficiency check with no chunks."""
        context = RetrievedContext(chunks=[])

        assert context.is_sufficient is False

    def test_confidence_level_high(self):
        """Test high confidence level."""
        # Need >= WARN_CONTEXT_CHUNKS * 2 = 6 chunks for high
        chunks = [
            CodeChunk(f"f{i}.php", f"content{i}", "class", 1, 10, 0.9)
            for i in range(7)
        ]
        context = RetrievedContext(chunks=chunks)

        assert context.confidence_level == "high"

    def test_confidence_level_medium(self):
        """Test medium confidence level."""
        # Need >= WARN_CONTEXT_CHUNKS = 3 for medium
        chunks = [
            CodeChunk(f"f{i}.php", f"content{i}", "class", 1, 10, 0.9)
            for i in range(4)
        ]
        context = RetrievedContext(chunks=chunks)

        assert context.confidence_level == "medium"

    def test_confidence_level_low(self):
        """Test low confidence level."""
        # Need >= MIN_CONTEXT_CHUNKS = 1 for low
        chunks = [CodeChunk("f1.php", "content", "class", 1, 10, 0.9)]
        context = RetrievedContext(chunks=chunks)

        assert context.confidence_level == "low"

    def test_confidence_level_insufficient(self):
        """Test insufficient confidence level."""
        context = RetrievedContext(chunks=[])

        assert context.confidence_level == "insufficient"

    def test_to_prompt_string_with_chunks(self):
        """Test prompt string generation with chunks."""
        context = RetrievedContext(
            chunks=[
                CodeChunk(
                    file_path="app/Models/User.php",
                    content="class User { }",
                    chunk_type="class",
                    start_line=1,
                    end_line=5,
                    score=0.9,
                )
            ],
            domain_summaries={"models": "Eloquent models"},
            warnings=["Limited context available"],
        )

        prompt = context.to_prompt_string()

        assert "app/Models/User.php" in prompt
        assert "class User" in prompt
        assert "Eloquent models" in prompt
        assert "Limited context" in prompt
        assert "score: 0.90" in prompt

    def test_to_prompt_string_empty(self):
        """Test prompt string generation with no chunks."""
        context = RetrievedContext(chunks=[])

        prompt = context.to_prompt_string()

        assert "No Relevant Code Found" in prompt
        assert "re-indexed" in prompt.lower() or "no matching" in prompt.lower()

    def test_to_prompt_string_with_warning(self):
        """Test prompt string includes confidence warning for low confidence."""
        context = RetrievedContext(
            chunks=[CodeChunk("f.php", "x", "code", 1, 1, 0.5)]
        )

        prompt = context.to_prompt_string()

        assert "WARNING" in prompt
        assert "low" in prompt.lower()


# =============================================================================
# Unit Tests - ContextRetriever
# =============================================================================

class TestContextRetrieverUnit:
    """Unit tests for ContextRetriever with mocked dependencies."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return create_mock_db_session()

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        return create_mock_vector_store()

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        return create_mock_embedding_service()

    @pytest.fixture
    def retriever(self, mock_db, mock_vector_store, mock_embedding_service):
        """Create ContextRetriever with mocked services."""
        return ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

    @pytest.mark.asyncio
    async def test_basic_retrieval(self, retriever, mock_vector_store, mock_embedding_service):
        """Test basic context retrieval."""
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
        )

        assert context is not None
        assert len(context.chunks) > 0
        assert context.is_sufficient
        mock_embedding_service.embed_query.assert_called()
        mock_vector_store.search.assert_called()

    @pytest.mark.asyncio
    async def test_retrieval_with_empty_queries(self, retriever):
        """Test retrieval handles empty search queries."""
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_EMPTY_QUERIES,
            require_minimum=False,
        )

        assert context is not None
        # Should have warning about no queries
        assert len(context.chunks) == 0 or context.confidence_level in ["low", "insufficient"]

    @pytest.mark.asyncio
    async def test_retrieval_tracks_metadata(self, retriever):
        """Test that retrieval metadata is tracked."""
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
        )

        assert "project_id" in context.retrieval_metadata
        assert "queries_tried" in context.retrieval_metadata
        assert "strategies_used" in context.retrieval_metadata
        assert context.retrieval_metadata["project_id"] == SAMPLE_PROJECT_ID

    @pytest.mark.asyncio
    async def test_retrieval_deduplicates_files(self, mock_db, mock_embedding_service):
        """Test that duplicate files are not included."""
        # Create vector store that returns duplicates
        duplicate_results = [
            SearchResult("c1", "app/Models/User.php", "content1", "class", 0.9, {}),
            SearchResult("c2", "app/Models/User.php", "content2", "class", 0.85, {}),  # Same file
            SearchResult("c3", "app/Controllers/UserController.php", "content3", "class", 0.8, {}),
        ]
        mock_vector_store = create_mock_vector_store(duplicate_results)

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
        )

        file_paths = [c.file_path for c in context.chunks]
        # Should not have duplicate User.php
        assert file_paths.count("app/Models/User.php") <= 1

    @pytest.mark.asyncio
    async def test_retrieval_respects_token_budget(self, mock_db, mock_embedding_service):
        """Test that token budget is respected."""
        # Create results with large content
        large_results = [
            SearchResult(
                f"c{i}",
                f"app/File{i}.php",
                "x" * 10000,  # Large content
                "class",
                0.9 - (i * 0.01),
                {}
            )
            for i in range(20)
        ]
        mock_vector_store = create_mock_vector_store(large_results)

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        small_budget = 5000  # ~20,000 chars
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
            token_budget=small_budget,
        )

        # Should not exceed budget
        assert context.total_tokens <= small_budget

    @pytest.mark.asyncio
    async def test_retrieval_retries_with_lower_threshold(self, mock_db, mock_embedding_service):
        """Test that retrieval retries with lower threshold if insufficient."""
        # First search returns nothing, second returns results
        call_count = [0]

        def mock_search(*args, **kwargs):
            call_count[0] += 1
            threshold = kwargs.get("score_threshold", 0.5)
            if threshold > 0.15:  # Normal threshold
                return []  # No results
            else:  # Retry threshold
                return SAMPLE_SEARCH_RESULTS

        mock_vector_store = MagicMock(spec=VectorStore)
        mock_vector_store.search = MagicMock(side_effect=mock_search)

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
        )

        # Should have tried multiple thresholds
        assert "vector_search_low_threshold" in context.retrieval_metadata.get("strategies_used", [])

    @pytest.mark.asyncio
    async def test_insufficient_context_error(self, mock_db, mock_embedding_service):
        """Test InsufficientContextError is raised when configured."""
        # Vector store returns no results
        mock_vector_store = create_mock_vector_store([])

        # Create config that aborts on no context
        config = AgentConfig(ABORT_ON_NO_CONTEXT=True, MIN_CONTEXT_CHUNKS=1)

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=config,
        )

        with pytest.raises(InsufficientContextError) as exc_info:
            await retriever.retrieve(
                project_id=SAMPLE_PROJECT_ID,
                intent=SAMPLE_INTENT_FEATURE,
                require_minimum=True,
            )

        assert exc_info.value.details["chunks_found"] == 0

    @pytest.mark.asyncio
    async def test_insufficient_context_warning(self, mock_db, mock_embedding_service):
        """Test warning is added when context is insufficient but not aborting."""
        mock_vector_store = create_mock_vector_store([])

        config = AgentConfig(ABORT_ON_NO_CONTEXT=False, MIN_CONTEXT_CHUNKS=1)

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
            config=config,
        )

        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
            require_minimum=True,
        )

        assert len(context.warnings) > 0
        assert any("chunk" in w.lower() for w in context.warnings)

    @pytest.mark.asyncio
    async def test_domain_summaries_included(self, retriever):
        """Test that domain summaries are included."""
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
        )

        # Intent has domains: controllers, models, routing
        assert "controllers" in context.domain_summaries or len(context.domain_summaries) > 0

    @pytest.mark.asyncio
    async def test_embedding_error_handled(self, mock_db, mock_vector_store):
        """Test that embedding errors are handled gracefully."""
        mock_embedding = MagicMock(spec=EmbeddingService)
        mock_embedding.embed_query = AsyncMock(return_value=None)  # Failed embedding

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
        )

        # Should not raise, just log and continue
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
            require_minimum=False,
        )

        assert context is not None

    @pytest.mark.asyncio
    async def test_search_error_handled(self, mock_db, mock_embedding_service):
        """Test that search errors are handled gracefully."""
        mock_vector_store = MagicMock(spec=VectorStore)
        mock_vector_store.search = MagicMock(side_effect=Exception("Search failed"))

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        # Should not raise, just log and continue
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
            require_minimum=False,
        )

        assert context is not None


# =============================================================================
# Unit Tests - Laravel Conventions Expansion
# =============================================================================

class TestLaravelConventionsExpansion:
    """Test Laravel file relationship expansion."""

    @pytest.fixture
    def retriever(self):
        """Create retriever for testing helper methods."""
        mock_db = create_mock_db_session()
        return ContextRetriever(db=mock_db)

    @pytest.mark.asyncio
    async def test_expand_controller_relationships(self, retriever):
        """Test expanding related files for a controller."""
        file_paths = ["app/Http/Controllers/UserController.php"]

        related = await retriever._expand_related_files(SAMPLE_PROJECT_ID, file_paths)

        # Should suggest related model, request, service, views, routes
        assert "app/Models/User.php" in related
        assert "app/Http/Requests/UserRequest.php" in related
        assert "routes/api.php" in related or "routes/web.php" in related

    @pytest.mark.asyncio
    async def test_expand_model_relationships(self, retriever):
        """Test expanding related files for a model."""
        file_paths = ["app/Models/Order.php"]

        related = await retriever._expand_related_files(SAMPLE_PROJECT_ID, file_paths)

        # Should suggest related controller, policy
        assert "app/Http/Controllers/OrderController.php" in related
        assert "app/Policies/OrderPolicy.php" in related

    @pytest.mark.asyncio
    async def test_expand_no_duplicates(self, retriever):
        """Test that expansion doesn't create duplicates."""
        file_paths = [
            "app/Http/Controllers/UserController.php",
            "app/Models/User.php",
        ]

        related = await retriever._expand_related_files(SAMPLE_PROJECT_ID, file_paths)

        # No duplicates
        assert len(related) == len(set(related))

    def test_to_snake_case(self, retriever):
        """Test snake_case conversion."""
        assert retriever._to_snake_case("UserController") == "user_controller"
        assert retriever._to_snake_case("OrderItem") == "order_item"
        assert retriever._to_snake_case("API") == "a_p_i"
        assert retriever._to_snake_case("user") == "user"


# =============================================================================
# Unit Tests - Edge Cases
# =============================================================================

class TestContextRetrieverEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def mock_db(self):
        return create_mock_db_session()

    @pytest.fixture
    def mock_embedding_service(self):
        return create_mock_embedding_service()

    @pytest.mark.asyncio
    async def test_very_long_query(self, mock_db, mock_embedding_service):
        """Test handling of very long search queries."""
        mock_vector_store = create_mock_vector_store()

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        long_query_intent = Intent(
            task_type="feature",
            task_type_confidence=0.9,
            search_queries=["x" * 10000],  # Very long query
            overall_confidence=0.85,
            needs_clarification=False,
        )

        # Should handle without error
        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=long_query_intent,
            require_minimum=False,
        )

        assert context is not None

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, mock_db, mock_embedding_service):
        """Test handling of special characters in queries."""
        mock_vector_store = create_mock_vector_store()

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        special_intent = Intent(
            task_type="feature",
            task_type_confidence=0.9,
            search_queries=[
                "$request->validate(['email' => 'required'])",
                "Route::get('/api/{id}', [Controller::class, 'show'])",
            ],
        )

        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=special_intent,
            require_minimum=False,
        )

        assert context is not None

    @pytest.mark.asyncio
    async def test_unicode_in_content(self, mock_db, mock_embedding_service):
        """Test handling of unicode in search results."""
        unicode_results = [
            SearchResult(
                chunk_id="c1",
                file_path="app/Services/TranslationService.php",
                content=u"// 日本語コメント\nclass TranslationService { }",
                chunk_type="class",
                score=0.9,
                metadata={},
            ),
        ]
        mock_vector_store = create_mock_vector_store(unicode_results)

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
            require_minimum=False,
        )

        assert context is not None
        if context.chunks:
            assert "日本語" in context.chunks[0].content

    @pytest.mark.asyncio
    async def test_zero_token_budget(self, mock_db, mock_embedding_service):
        """Test handling of zero token budget."""
        mock_vector_store = create_mock_vector_store()

        retriever = ContextRetriever(
            db=mock_db,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )

        context = await retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=SAMPLE_INTENT_FEATURE,
            token_budget=0,
            require_minimum=False,
        )

        # Should return empty or minimal context
        assert context.total_tokens == 0


# =============================================================================
# Test Scenarios for Integration Testing
# =============================================================================

RETRIEVAL_TEST_SCENARIOS = [
    {
        "name": "feature_with_entities",
        "description": "Feature request with explicit entities",
        "intent": SAMPLE_INTENT_FEATURE,
        "expected": {
            "min_chunks": 1,
            "should_find_files": ["UserController", "User"],
        },
    },
    {
        "name": "bugfix_auth",
        "description": "Authentication bugfix",
        "intent": SAMPLE_INTENT_BUGFIX,
        "expected": {
            "min_chunks": 1,
            "domains_in_summary": ["auth"],
        },
    },
    {
        "name": "empty_queries",
        "description": "Intent with no search queries",
        "intent": SAMPLE_INTENT_EMPTY_QUERIES,
        "expected": {
            "confidence_level_in": ["low", "insufficient"],
        },
    },
]


# =============================================================================
# Integration Tests (Real Services)
# =============================================================================

@pytest.mark.integration
class TestContextRetrieverIntegration:
    """Integration tests with real services."""

    @pytest.fixture
    def real_retriever(self):
        """Create retriever with real services (requires running Qdrant, etc.)."""
        # This would need actual database and vector store connections
        # For now, skip if services not available
        pytest.skip("Integration tests require running services")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", RETRIEVAL_TEST_SCENARIOS, ids=[s["name"] for s in RETRIEVAL_TEST_SCENARIOS])
    async def test_scenario(self, real_retriever, scenario):
        """Test each retrieval scenario."""
        context = await real_retriever.retrieve(
            project_id=SAMPLE_PROJECT_ID,
            intent=scenario["intent"],
        )

        expected = scenario["expected"]

        if "min_chunks" in expected:
            assert len(context.chunks) >= expected["min_chunks"]

        if "confidence_level_in" in expected:
            assert context.confidence_level in expected["confidence_level_in"]


# =============================================================================
# Interactive CLI Testing
# =============================================================================

async def run_interactive_test():
    """Run interactive testing mode."""
    print("\n" + "=" * 60)
    print("Scout (Context Retriever) - Interactive Test Mode")
    print("=" * 60)
    print("\nThis mode tests Scout's context retrieval capabilities.")
    print("Enter search queries to see what context is retrieved.\n")

    # Note: Would need real services for interactive testing
    print("Note: Interactive mode requires running Qdrant and database.")
    print("For unit tests, use: pytest test_context_retriever.py -v")


async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all test scenarios."""
    print("\n" + "=" * 60)
    print("Scout (Context Retriever) - Running All Test Scenarios")
    print("=" * 60)

    results = []
    passed = 0
    failed = 0

    # Run unit tests with mocks
    for scenario in RETRIEVAL_TEST_SCENARIOS:
        print(f"\n[{scenario['name']}] {scenario['description']}...")

        try:
            mock_db = create_mock_db_session()
            mock_vector_store = create_mock_vector_store()
            mock_embedding = create_mock_embedding_service()

            retriever = ContextRetriever(
                db=mock_db,
                vector_store=mock_vector_store,
                embedding_service=mock_embedding,
            )

            context = await retriever.retrieve(
                project_id=SAMPLE_PROJECT_ID,
                intent=scenario["intent"],
                require_minimum=False,
            )

            # Validate
            expected = scenario["expected"]
            errors = []

            if "min_chunks" in expected and len(context.chunks) < expected["min_chunks"]:
                errors.append(f"Expected min {expected['min_chunks']} chunks, got {len(context.chunks)}")

            if "confidence_level_in" in expected and context.confidence_level not in expected["confidence_level_in"]:
                errors.append(f"Expected confidence in {expected['confidence_level_in']}, got {context.confidence_level}")

            if errors:
                print(f"   ❌ FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                print(f"   ✅ PASSED (chunks={len(context.chunks)}, confidence={context.confidence_level})")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "passed": len(errors) == 0,
                "chunks_found": len(context.chunks),
                "confidence": context.confidence_level,
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
    print(f"Results: {passed} passed, {failed} failed, {len(RETRIEVAL_TEST_SCENARIOS)} total")
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
    parser = argparse.ArgumentParser(description="Test Scout (Context Retriever) Agent")
    parser.add_argument("--interactive", action="store_true", help="Run interactive testing")
    parser.add_argument("--run-all", action="store_true", help="Run all test scenarios")
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