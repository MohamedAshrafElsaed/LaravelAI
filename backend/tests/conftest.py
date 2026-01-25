"""
Pytest Configuration and Shared Fixtures for Agent Tests

This conftest.py provides:
- Shared fixtures for all agent tests
- Mock factories for services
- Sample data generators
- Test markers configuration

Place this file in: backend/tests/agents/conftest.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Pytest Markers Configuration
# =============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires real API)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (mocked, fast)"
    )


# =============================================================================
# Sample PHP Code Fixtures
# =============================================================================

@pytest.fixture
def sample_controller_content() -> str:
    """Sample Laravel controller content."""
    return r'''<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class UserController extends Controller
{
    public function index(): JsonResponse
    {
        return response()->json(User::paginate(15));
    }

    public function store(Request $request): JsonResponse
    {
        $user = User::create($request->validated());
        return response()->json($user, 201);
    }

    public function show(User $user): JsonResponse
    {
        return response()->json($user);
    }
}
'''


@pytest.fixture
def sample_model_content() -> str:
    """Sample Laravel model content."""
    return r'''<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Order extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'user_id',
        'total',
        'status',
    ];

    protected $casts = [
        'total' => 'decimal:2',
    ];

    public function user()
    {
        return $this->belongsTo(User::class);
    }

    public function items()
    {
        return $this->hasMany(OrderItem::class);
    }
}
'''


@pytest.fixture
def sample_migration_content() -> str:
    """Sample Laravel migration content."""
    return r'''<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('orders', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained();
            $table->decimal('total', 10, 2);
            $table->string('status')->default('pending');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('orders');
    }
};
'''


@pytest.fixture
def sample_routes_content() -> str:
    """Sample Laravel routes content."""
    return r'''<?php

use App\Http\Controllers\UserController;
use App\Http\Controllers\OrderController;
use Illuminate\Support\Facades\Route;

Route::middleware(['auth:sanctum'])->group(function () {
    Route::apiResource('users', UserController::class);
    Route::apiResource('orders', OrderController::class);
});
'''


@pytest.fixture
def sample_project_context() -> str:
    """Sample project context string."""
    return """### Technology Stack
- **Backend:** Laravel 11.x (PHP 8.3)
- **Database:** mysql
- **Auth:** sanctum + spatie/laravel-permission

### Database Models
Available models: User, Order, Product, Category, Payment

### Architecture Patterns
- Service Layer pattern
- Form Requests for validation
- API Resources for responses
"""


# =============================================================================
# Mock Service Fixtures
# =============================================================================

@pytest.fixture
def mock_claude_service():
    """Create a mock Claude service."""
    mock = MagicMock()
    mock.chat_async = AsyncMock(return_value='{}')
    mock.stream_cached = AsyncMock()
    return mock


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    from app.services.vector_store import VectorStore

    mock = MagicMock(spec=VectorStore)
    mock.search = MagicMock(return_value=[])
    mock.collection_exists = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    from app.services.embeddings import EmbeddingService

    mock = MagicMock(spec=EmbeddingService)
    mock.embed_query = AsyncMock(return_value=[0.1] * 1536)
    return mock


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    mock = MagicMock()
    mock.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    return mock


# =============================================================================
# Agent Fixtures
# =============================================================================

@pytest.fixture
def mock_nova(mock_claude_service):
    """Create a mocked Nova (IntentAnalyzer) agent."""
    from app.agents.intent_analyzer import IntentAnalyzer
    return IntentAnalyzer(claude_service=mock_claude_service)


@pytest.fixture
def mock_scout(mock_db_session, mock_vector_store, mock_embedding_service):
    """Create a mocked Scout (ContextRetriever) agent."""
    from app.agents.context_retriever import ContextRetriever
    return ContextRetriever(
        db=mock_db_session,
        vector_store=mock_vector_store,
        embedding_service=mock_embedding_service,
    )


@pytest.fixture
def mock_blueprint(mock_claude_service):
    """Create a mocked Blueprint (Planner) agent."""
    from app.agents.planner import Planner
    return Planner(claude_service=mock_claude_service)


@pytest.fixture
def mock_forge(mock_claude_service):
    """Create a mocked Forge (Executor) agent."""
    from app.agents.executor import Executor
    return Executor(claude_service=mock_claude_service)


# =============================================================================
# Data Class Fixtures
# =============================================================================

@pytest.fixture
def sample_intent():
    """Create a sample Intent object."""
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
            "methods": [],
            "routes": [],
            "tables": [],
        },
        search_queries=["UserController", "user management"],
        reasoning="Add new feature to UserController",
        overall_confidence=0.85,
        needs_clarification=False,
        clarifying_questions=[],
    )


@pytest.fixture
def sample_context():
    """Create a sample RetrievedContext object."""
    from app.agents.context_retriever import RetrievedContext, CodeChunk

    return RetrievedContext(
        chunks=[
            CodeChunk(
                file_path="app/Http/Controllers/UserController.php",
                content="<?php class UserController {}",
                chunk_type="class",
                start_line=1,
                end_line=10,
                score=0.9,
            ),
        ],
        domain_summaries={"controllers": "User controller found"},
    )


@pytest.fixture
def sample_plan():
    """Create a sample Plan object."""
    from app.agents.planner import Plan, PlanStep

    return Plan(
        summary="Add export feature",
        reasoning={
            "understanding": "Add CSV export to controller",
            "approach": "Standard Laravel implementation",
        },
        steps=[
            PlanStep(
                order=1,
                action="modify",
                file="app/Http/Controllers/UserController.php",
                category="controller",
                description="Add export method",
                depends_on=[],
                estimated_lines=20,
            ),
        ],
        overall_confidence=0.85,
        risk_level="low",
        estimated_complexity=2,
        needs_clarification=False,
        clarifying_questions=[],
        warnings=[],
    )


@pytest.fixture
def sample_plan_step():
    """Create a sample PlanStep object."""
    from app.agents.planner import PlanStep

    return PlanStep(
        order=1,
        action="modify",
        file="app/Http/Controllers/UserController.php",
        category="controller",
        description="Add export method to generate CSV",
        depends_on=[],
        estimated_lines=30,
    )


@pytest.fixture
def sample_execution_result():
    """Create a sample ExecutionResult object."""
    from app.agents.executor import ExecutionResult

    return ExecutionResult(
        file="app/Http/Controllers/UserController.php",
        action="modify",
        content="<?php class UserController { public function export() {} }",
        diff="+ public function export() {}",
        original_content="<?php class UserController {}",
        success=True,
    )


@pytest.fixture
def sample_conversation_summary():
    """Create a sample ConversationSummary object."""
    from app.agents.conversation_summary import ConversationSummary

    return ConversationSummary(
        project_name="Test Project",
        project_id="test-123",
        decisions=["Use service pattern"],
        completed_tasks=["Created User model"],
        pending_tasks=["Add export feature"],
        known_files=["app/Models/User.php"],
        known_classes=["User", "UserController"],
    )


# =============================================================================
# Search Results Fixtures
# =============================================================================

@pytest.fixture
def sample_search_results():
    """Create sample search results."""
    from app.services.vector_store import SearchResult

    return [
        SearchResult(
            chunk_id="chunk-1",
            file_path="app/Http/Controllers/UserController.php",
            content="<?php class UserController extends Controller {}",
            chunk_type="class",
            score=0.95,
            metadata={"laravel_type": "controller"},
        ),
        SearchResult(
            chunk_id="chunk-2",
            file_path="app/Models/User.php",
            content="<?php class User extends Model {}",
            chunk_type="class",
            score=0.88,
            metadata={"laravel_type": "model"},
        ),
    ]


# =============================================================================
# Response Factory Fixtures
# =============================================================================

@pytest.fixture
def nova_response_factory():
    """Factory for creating Nova responses."""
    def create_response(
        task_type: str = "feature",
        needs_clarification: bool = False,
        requires_migration: bool = False,
        domains: List[str] = None,
        entities: Dict = None,
    ) -> str:
        return json.dumps({
            "task_type": task_type,
            "task_type_confidence": 0.9,
            "domains_affected": domains or ["controllers"],
            "scope": "feature",
            "languages": ["php"],
            "requires_migration": requires_migration,
            "priority": "medium",
            "entities": entities or {"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
            "search_queries": ["query1", "query2"],
            "reasoning": "Test reasoning",
            "overall_confidence": 0.3 if needs_clarification else 0.85,
            "needs_clarification": needs_clarification,
            "clarifying_questions": ["What?"] if needs_clarification else [],
        })
    return create_response


@pytest.fixture
def blueprint_response_factory():
    """Factory for creating Blueprint responses."""
    def create_response(
        steps: List[Dict] = None,
        needs_clarification: bool = False,
        confidence: float = 0.85,
    ) -> str:
        if needs_clarification:
            return json.dumps({
                "summary": "Need clarification",
                "reasoning": {},
                "steps": [],
                "overall_confidence": 0.2,
                "risk_level": "medium",
                "estimated_complexity": 1,
                "needs_clarification": True,
                "clarifying_questions": ["What feature?"],
                "warnings": [],
            })

        default_steps = steps or [
            {
                "order": 1,
                "action": "modify",
                "file": "app/Http/Controllers/TestController.php",
                "category": "controller",
                "description": "Modify controller",
                "depends_on": [],
                "estimated_lines": 20,
            }
        ]

        return json.dumps({
            "summary": "Implementation plan",
            "reasoning": {
                "understanding": "Test understanding",
                "approach": "Standard approach",
            },
            "steps": default_steps,
            "overall_confidence": confidence,
            "risk_level": "low",
            "estimated_complexity": len(default_steps),
            "needs_clarification": False,
            "clarifying_questions": [],
            "warnings": [],
        })
    return create_response


@pytest.fixture
def forge_response_factory():
    """Factory for creating Forge responses."""
    def create_response(
        file: str = "test.php",
        action: str = "create",
        content: str = "<?php class Test {}",
    ) -> str:
        return json.dumps({
            "file": file,
            "action": action,
            "content": content,
        })
    return create_response


@pytest.fixture
def reasoning_response_factory():
    """Factory for creating reasoning responses."""
    def create_response(
        task: str = "Implement feature",
        imports: List[str] = None,
        steps: List[str] = None,
    ) -> str:
        return json.dumps({
            "task_understanding": task,
            "file_purpose": "Laravel file",
            "required_imports": imports or [],
            "dependencies": [],
            "insertion_point": "After existing methods",
            "preservation_notes": "Keep all existing code",
            "implementation_steps": steps or ["Step 1", "Step 2"],
            "potential_issues": [],
        })
    return create_response


@pytest.fixture
def verification_response_factory():
    """Factory for creating verification responses."""
    def create_response(
        passes: bool = True,
        issues: List[str] = None,
    ) -> str:
        return json.dumps({
            "passes_verification": passes,
            "issues": issues or [],
            "content_preserved": True,
            "confidence": "high" if passes else "low",
        })
    return create_response


# =============================================================================
# Helper Functions
# =============================================================================

def create_mock_claude_with_responses(responses: List[str]):
    """Create a mock Claude service with predefined responses."""
    mock = MagicMock()
    mock.chat_async = AsyncMock(side_effect=responses)
    return mock


def create_mock_streaming_claude(content: str):
    """Create a mock Claude service for streaming."""
    mock = MagicMock()

    async def mock_stream(*args, **kwargs):
        yield json.dumps({"content": content})

    mock.stream_cached = mock_stream
    mock.chat_async = AsyncMock(return_value='{}')
    return mock


# =============================================================================
# Test Data Generators
# =============================================================================

@pytest.fixture
def generate_plan_steps():
    """Generator for creating multiple plan steps."""
    def generate(count: int = 3, start_order: int = 1) -> List[Dict]:
        steps = []
        for i in range(count):
            order = start_order + i
            steps.append({
                "order": order,
                "action": "create" if i == 0 else "modify",
                "file": f"app/Test/File{order}.php",
                "category": "service",
                "description": f"Step {order} description",
                "depends_on": list(range(start_order, order)) if order > start_order else [],
                "estimated_lines": 20 + (i * 10),
            })
        return steps
    return generate


@pytest.fixture
def generate_code_chunks():
    """Generator for creating multiple code chunks."""
    from app.agents.context_retriever import CodeChunk

    def generate(count: int = 3) -> List:
        chunks = []
        for i in range(count):
            chunks.append(
                CodeChunk(
                    chunk_id=f"chunk-{i}",
                    file_path=f"app/Test/File{i}.php",
                    content=f"<?php class Test{i} {{}}",
                    chunk_type="class",
                    relevance_score=0.9 - (i * 0.1),
                )
            )
        return chunks
    return generate