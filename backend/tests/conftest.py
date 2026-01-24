"""
Pytest configuration and shared fixtures for agent tests.

Place this file at: backend/tests/conftest.py

Supports:
- Nova (Intent Analyzer) tests
- Scout (Context Retriever) tests
- Nova → Scout integration tests
"""
import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import List, Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Async Event Loop Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Mock Claude Service (for Nova)
# =============================================================================

@pytest.fixture
def mock_claude_service():
    """
    Mock Claude service for unit tests.
    Returns a MagicMock with async chat_async method.
    Default response is a valid feature intent.
    """
    mock = MagicMock()
    mock.chat_async = AsyncMock(return_value='''{
        "task_type": "feature",
        "task_type_confidence": 0.9,
        "domains_affected": ["controllers"],
        "scope": "single_file",
        "languages": ["php"],
        "requires_migration": false,
        "priority": "medium",
        "entities": {
            "files": [],
            "classes": [],
            "methods": [],
            "routes": [],
            "tables": []
        },
        "search_queries": ["test query"],
        "reasoning": "Test reasoning",
        "overall_confidence": 0.9,
        "needs_clarification": false,
        "clarifying_questions": []
    }''')
    return mock


@pytest.fixture
def mock_claude_clarification():
    """Mock Claude service that returns a clarification-needed response."""
    mock = MagicMock()
    mock.chat_async = AsyncMock(return_value='''{
        "task_type": "feature",
        "task_type_confidence": 0.4,
        "domains_affected": ["controllers"],
        "scope": "single_file",
        "languages": ["php"],
        "requires_migration": false,
        "priority": "medium",
        "entities": {
            "files": [],
            "classes": [],
            "methods": [],
            "routes": [],
            "tables": []
        },
        "search_queries": ["generic search"],
        "reasoning": "Request is ambiguous",
        "overall_confidence": 0.3,
        "needs_clarification": true,
        "clarifying_questions": ["What specific feature would you like?", "Which module should this be in?"]
    }''')
    return mock


@pytest.fixture
def mock_claude_error():
    """Mock Claude service that raises an error."""
    mock = MagicMock()
    mock.chat_async = AsyncMock(side_effect=Exception("API Error"))
    return mock


# =============================================================================
# Mock Vector Store (for Scout)
# =============================================================================

@pytest.fixture
def mock_vector_store():
    """
    Mock VectorStore for unit tests.
    Returns sample search results by default.
    """
    from app.services.vector_store import VectorStore, SearchResult

    sample_results = [
        SearchResult(
            chunk_id="chunk-1",
            file_path="app/Http/Controllers/UserController.php",
            content="class UserController extends Controller { public function store() {} }",
            chunk_type="class",
            score=0.92,
            metadata={"laravel_type": "controller", "line_start": 1, "line_end": 10},
        ),
        SearchResult(
            chunk_id="chunk-2",
            file_path="app/Models/User.php",
            content="class User extends Model { protected $fillable = ['name', 'email']; }",
            chunk_type="class",
            score=0.88,
            metadata={"laravel_type": "model", "line_start": 1, "line_end": 5},
        ),
    ]

    mock = MagicMock(spec=VectorStore)
    mock.search = MagicMock(return_value=sample_results)
    mock.collection_exists = MagicMock(return_value=True)
    mock.create_collection = MagicMock(return_value=True)
    mock.store_chunks = MagicMock(return_value=2)
    return mock


@pytest.fixture
def mock_vector_store_empty():
    """Mock VectorStore that returns no results."""
    from app.services.vector_store import VectorStore

    mock = MagicMock(spec=VectorStore)
    mock.search = MagicMock(return_value=[])
    mock.collection_exists = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_vector_store_error():
    """Mock VectorStore that raises errors."""
    from app.services.vector_store import VectorStore

    mock = MagicMock(spec=VectorStore)
    mock.search = MagicMock(side_effect=Exception("Search failed"))
    mock.collection_exists = MagicMock(return_value=True)
    return mock


# =============================================================================
# Mock Embedding Service (for Scout)
# =============================================================================

@pytest.fixture
def mock_embedding_service():
    """
    Mock EmbeddingService for unit tests.
    Returns valid embedding vectors.
    """
    from app.services.embeddings import EmbeddingService

    mock = MagicMock(spec=EmbeddingService)
    # Return 1536-dim vector (OpenAI default)
    mock.embed_query = AsyncMock(return_value=[0.1] * 1536)
    mock.embed_chunks = AsyncMock(return_value=[[0.1] * 1536])
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_embedding_service_error():
    """Mock EmbeddingService that returns None (failure)."""
    from app.services.embeddings import EmbeddingService

    mock = MagicMock(spec=EmbeddingService)
    mock.embed_query = AsyncMock(return_value=None)
    mock.embed_chunks = AsyncMock(return_value=[])
    return mock


# =============================================================================
# Mock Database Session
# =============================================================================

@pytest.fixture
def mock_db_session():
    """
    Mock SQLAlchemy async session.
    Returns None for file content queries by default.
    """
    mock = MagicMock()

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        return result

    mock.execute = AsyncMock(side_effect=mock_execute)
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_db_with_files():
    """Mock database session with indexed files."""
    mock = MagicMock()

    # Simulate file content in database
    mock_file = MagicMock()
    mock_file.content = "<?php\n\nclass User extends Model { }"
    mock_file.file_path = "app/Models/User.php"

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_file)
        return result

    mock.execute = AsyncMock(side_effect=mock_execute)
    return mock


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_project_context():
    """Sample project context for testing."""
    return """### Technology Stack
- **Backend:** Laravel 11.x (PHP 8.3)
- **Database:** mysql
- **Auth:** sanctum + spatie/laravel-permission

### Database Models
Available models: User, Order, Product, Category, Payment

### Codebase Statistics
- **Total Files:** 150
- **Controllers:** UserController, OrderController, ProductController

### Architecture Patterns
- Service Layer pattern
- Repository pattern
"""


@pytest.fixture
def sample_conversation_summary():
    """Sample conversation summary for testing."""
    from app.agents.conversation_summary import ConversationSummary

    return ConversationSummary(
        project_name="Test Project",
        project_id="test-123",
        decisions=["Use service pattern"],
        completed_tasks=["Created User model"],
        pending_tasks=["Add authentication"],
        known_files=["app/Models/User.php"],
        known_classes=["User", "UserController"],
        known_tables=["users"],
    )


@pytest.fixture
def sample_recent_messages():
    """Sample recent messages for testing."""
    from app.agents.conversation_summary import RecentMessage

    return [
        RecentMessage(role="user", content="Let's work on the user system"),
        RecentMessage(role="assistant", content="Sure, I'll help with that."),
    ]


@pytest.fixture
def sample_intent_feature():
    """Sample feature intent for testing Scout."""
    from app.agents.intent_analyzer import Intent

    return Intent(
        task_type="feature",
        task_type_confidence=0.9,
        domains_affected=["controllers", "models"],
        scope="feature",
        languages=["php"],
        requires_migration=False,
        priority="medium",
        entities={
            "files": [],
            "classes": ["UserController"],
            "methods": ["store"],
            "routes": [],
            "tables": [],
        },
        search_queries=["UserController store", "User model", "user validation"],
        reasoning="Feature request for user management",
        overall_confidence=0.85,
        needs_clarification=False,
    )


@pytest.fixture
def sample_intent_bugfix():
    """Sample bugfix intent for testing Scout."""
    from app.agents.intent_analyzer import Intent

    return Intent(
        task_type="bugfix",
        task_type_confidence=0.95,
        domains_affected=["auth", "controllers"],
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
        search_queries=["AuthController login", "authentication", "sanctum"],
        reasoning="Authentication bug",
        overall_confidence=0.9,
        needs_clarification=False,
    )


@pytest.fixture
def sample_intent_clarification():
    """Sample intent that needs clarification."""
    from app.agents.intent_analyzer import Intent

    return Intent(
        task_type="feature",
        task_type_confidence=0.4,
        domains_affected=[],
        scope="single_file",
        languages=["php"],
        requires_migration=False,
        priority="medium",
        entities={"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
        search_queries=[],
        reasoning="Request is too vague",
        overall_confidence=0.3,
        needs_clarification=True,
        clarifying_questions=["What feature would you like?"],
    )


# =============================================================================
# Agent Fixtures
# =============================================================================

@pytest.fixture
def intent_analyzer(mock_claude_service):
    """Create IntentAnalyzer with mocked Claude service."""
    from unittest.mock import patch
    from app.agents.intent_analyzer import IntentAnalyzer

    with patch('app.agents.intent_analyzer.get_claude_service', return_value=mock_claude_service):
        analyzer = IntentAnalyzer(claude_service=mock_claude_service)
        yield analyzer


@pytest.fixture
def context_retriever(mock_db_session, mock_vector_store, mock_embedding_service):
    """Create ContextRetriever with mocked services."""
    from app.agents.context_retriever import ContextRetriever

    return ContextRetriever(
        db=mock_db_session,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
    )


@pytest.fixture
def context_retriever_empty(mock_db_session, mock_vector_store_empty, mock_embedding_service):
    """Create ContextRetriever that returns no results."""
    from app.agents.context_retriever import ContextRetriever

    return ContextRetriever(
        db=mock_db_session,
        vector_store=mock_vector_store_empty,
        embedding_service=mock_embedding_service,
    )


@pytest.fixture
def real_intent_analyzer():
    """Create IntentAnalyzer with real Claude service (for integration tests)."""
    from app.agents.intent_analyzer import IntentAnalyzer
    return IntentAnalyzer()


# =============================================================================
# Agent Config Fixtures
# =============================================================================

@pytest.fixture
def strict_agent_config():
    """Agent config that aborts on insufficient context."""
    from app.agents.config import AgentConfig

    return AgentConfig(
        MIN_CONTEXT_CHUNKS=3,
        WARN_CONTEXT_CHUNKS=5,
        ABORT_ON_NO_CONTEXT=True,
        CONTEXT_SCORE_THRESHOLD=0.3,
        CONTEXT_RETRY_THRESHOLD=0.15,
    )


@pytest.fixture
def lenient_agent_config():
    """Agent config that doesn't abort on insufficient context."""
    from app.agents.config import AgentConfig

    return AgentConfig(
        MIN_CONTEXT_CHUNKS=1,
        WARN_CONTEXT_CHUNKS=2,
        ABORT_ON_NO_CONTEXT=False,
        CONTEXT_SCORE_THRESHOLD=0.1,
        CONTEXT_RETRY_THRESHOLD=0.05,
    )


# =============================================================================
# Search Result Fixtures
# =============================================================================

@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    from app.services.vector_store import SearchResult

    return [
        SearchResult(
            chunk_id="c1",
            file_path="app/Http/Controllers/UserController.php",
            content="class UserController { public function store() {} }",
            chunk_type="class",
            score=0.92,
            metadata={"laravel_type": "controller"},
        ),
        SearchResult(
            chunk_id="c2",
            file_path="app/Models/User.php",
            content="class User extends Model { }",
            chunk_type="class",
            score=0.88,
            metadata={"laravel_type": "model"},
        ),
        SearchResult(
            chunk_id="c3",
            file_path="routes/api.php",
            content="Route::apiResource('users', UserController::class);",
            chunk_type="route",
            score=0.75,
            metadata={"laravel_type": "route"},
        ),
    ]


@pytest.fixture
def low_score_search_results():
    """Search results with scores below typical thresholds."""
    from app.services.vector_store import SearchResult

    return [
        SearchResult(
            chunk_id="c1",
            file_path="app/Providers/AppServiceProvider.php",
            content="class AppServiceProvider { }",
            chunk_type="class",
            score=0.15,
            metadata={"laravel_type": "provider"},
        ),
    ]


# =============================================================================
# Pytest Hooks
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require real API)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "scout: marks tests for Scout (Context Retriever) agent"
    )
    config.addinivalue_line(
        "markers", "nova: marks tests for Nova (Intent Analyzer) agent"
    )
    config.addinivalue_line(
        "markers", "pipeline: marks tests for multi-agent pipeline"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests by default unless explicitly requested."""
    if config.getoption("-m") and "integration" in config.getoption("-m"):
        # Integration tests explicitly requested
        return

    skip_integration = pytest.mark.skip(
        reason="Integration tests skipped by default. Use -m integration to run."
    )

    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


# =============================================================================
# Utility Functions for Tests
# =============================================================================

def create_mock_search_results(
    count: int = 3,
    base_score: float = 0.9,
    file_pattern: str = "app/File{}.php"
) -> List:
    """Helper to create multiple mock search results."""
    from app.services.vector_store import SearchResult

    results = []
    for i in range(count):
        results.append(SearchResult(
            chunk_id=f"chunk-{i}",
            file_path=file_pattern.format(i),
            content=f"class File{i} {{ }}",
            chunk_type="class",
            score=base_score - (i * 0.05),
            metadata={"index": i},
        ))
    return results


def create_intent_with_queries(queries: List[str], task_type: str = "feature"):
    """Helper to create an intent with specific search queries."""
    from app.agents.intent_analyzer import Intent

    return Intent(
        task_type=task_type,
        task_type_confidence=0.9,
        search_queries=queries,
        overall_confidence=0.85,
        needs_clarification=False,
    )