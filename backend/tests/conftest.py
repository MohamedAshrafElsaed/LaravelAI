"""
Pytest Configuration and Shared Fixtures for All Tests

This conftest.py provides:
- Shared fixtures for all agent tests
- TestClient and mock database fixtures for API tests
- Authentication fixtures (test users, auth headers)
- Mock factories for services
- Sample data generators
- Test markers configuration
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

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
# API Test Fixtures - TestClient & Database
# =============================================================================

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from main import app
    return TestClient(app)


@pytest.fixture
def client_with_mocked_db(mock_db_async, test_user):
    """TestClient with mocked database and authenticated user."""
    from main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    async def mock_get_db():
        yield mock_db_async

    async def mock_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    yield TestClient(app)

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_async():
    """Create a mock async database session with common query patterns."""
    mock = MagicMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.refresh = AsyncMock()
    mock.delete = AsyncMock()
    mock.add = MagicMock()
    mock.rollback = AsyncMock()

    # Default execute returns empty result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    mock_result.fetchall = MagicMock(return_value=[])
    mock.execute.return_value = mock_result

    return mock


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture
def test_user():
    """Create a sample User model instance for testing."""
    from app.models.models import User

    user = MagicMock(spec=User)
    user.id = str(uuid4())
    user.github_id = 12345678
    user.username = "testuser"
    user.email = "testuser@example.com"
    user.avatar_url = "https://avatars.githubusercontent.com/u/12345678"
    user.github_access_token = "encrypted_test_token"
    user.github_refresh_token = None
    user.github_token_expires_at = datetime.utcnow() + timedelta(hours=8)
    user.is_active = True
    user.monthly_requests = 0
    user.request_limit = 100
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


@pytest.fixture
def test_user_second():
    """Create a second test user for access control tests."""
    from app.models.models import User

    user = MagicMock(spec=User)
    user.id = str(uuid4())
    user.github_id = 87654321
    user.username = "otheruser"
    user.email = "other@example.com"
    user.avatar_url = "https://avatars.githubusercontent.com/u/87654321"
    user.github_access_token = "encrypted_other_token"
    user.is_active = True
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate JWT auth headers for authenticated requests."""
    from app.core.security import create_access_token

    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_current_user(test_user):
    """Override get_current_user dependency to return test user."""
    from main import app
    from app.core.security import get_current_user

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield test_user
    app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# Project Fixtures
# =============================================================================

@pytest.fixture
def test_project(test_user):
    """Create a sample Project model instance."""
    from app.models.models import Project, ProjectStatus

    project = MagicMock(spec=Project)
    project.id = str(uuid4())
    project.user_id = test_user.id
    project.github_repo_id = 123456789
    project.name = "test-laravel-app"
    project.repo_full_name = "testuser/test-laravel-app"
    project.repo_url = "https://github.com/testuser/test-laravel-app"
    project.default_branch = "main"
    project.clone_path = "/tmp/repos/test-project"
    project.status = ProjectStatus.READY.value
    project.last_indexed_at = datetime.utcnow()
    project.indexed_files_count = 150
    project.error_message = None
    project.laravel_version = "11.0"
    project.php_version = "8.3"
    project.stack = {"backend": {"framework": "laravel", "version": "11.0"}}
    project.file_stats = {"total_files": 150, "total_lines": 15000}
    project.health_score = 85.0
    project.health_check = {"score": 85.0, "production_ready": True}
    project.scan_progress = 100
    project.scanned_at = datetime.utcnow()
    project.created_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()
    project.team_id = None
    return project


@pytest.fixture
def test_project_not_ready(test_user):
    """Create a project in CLONING status."""
    from app.models.models import Project, ProjectStatus

    project = MagicMock(spec=Project)
    project.id = str(uuid4())
    project.user_id = test_user.id
    project.github_repo_id = 987654321
    project.name = "cloning-project"
    project.repo_full_name = "testuser/cloning-project"
    project.repo_url = "https://github.com/testuser/cloning-project"
    project.default_branch = "main"
    project.clone_path = None
    project.status = ProjectStatus.CLONING.value
    project.last_indexed_at = None
    project.indexed_files_count = 0
    project.error_message = None
    project.created_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()
    return project


# =============================================================================
# Team Fixtures
# =============================================================================

@pytest.fixture
def test_team(test_user):
    """Create a sample Team model instance."""
    from app.models.team_models import Team

    team = MagicMock(spec=Team)
    team.id = str(uuid4())
    team.name = "Test Team"
    team.slug = "test-team"
    team.description = "A test team"
    team.avatar_url = None
    team.owner_id = test_user.id
    team.is_personal = False
    team.github_org_name = None
    team.settings = {}
    team.created_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    return team


@pytest.fixture
def test_personal_team(test_user):
    """Create a personal team for the test user."""
    from app.models.team_models import Team

    team = MagicMock(spec=Team)
    team.id = str(uuid4())
    team.name = f"{test_user.username}'s Personal Team"
    team.slug = f"{test_user.username}-personal"
    team.description = None
    team.avatar_url = test_user.avatar_url
    team.owner_id = test_user.id
    team.is_personal = True
    team.github_org_name = None
    team.settings = {}
    team.created_at = datetime.utcnow()
    team.updated_at = datetime.utcnow()
    return team


@pytest.fixture
def test_team_member(test_team, test_user):
    """Create a sample TeamMember instance."""
    from app.models.team_models import TeamMember, TeamRole, TeamMemberStatus

    member = MagicMock(spec=TeamMember)
    member.id = str(uuid4())
    member.team_id = test_team.id
    member.user_id = test_user.id
    member.github_id = test_user.github_id
    member.github_username = test_user.username
    member.github_avatar_url = test_user.avatar_url
    member.invited_email = None
    member.role = TeamRole.OWNER.value
    member.status = TeamMemberStatus.ACTIVE.value
    member.joined_at = datetime.utcnow()
    member.invited_at = datetime.utcnow()
    member.last_active_at = datetime.utcnow()
    return member


# =============================================================================
# Conversation Fixtures
# =============================================================================

@pytest.fixture
def test_conversation(test_user, test_project):
    """Create a sample Conversation instance."""
    from app.models.models import Conversation

    conv = MagicMock(spec=Conversation)
    conv.id = str(uuid4())
    conv.user_id = test_user.id
    conv.project_id = test_project.id
    conv.title = "Test conversation"
    conv.created_at = datetime.utcnow()
    conv.updated_at = datetime.utcnow()
    conv.messages = []
    return conv


@pytest.fixture
def test_message(test_conversation):
    """Create a sample Message instance."""
    from app.models.models import Message

    msg = MagicMock(spec=Message)
    msg.id = str(uuid4())
    msg.conversation_id = test_conversation.id
    msg.role = "user"
    msg.content = "Test message content"
    msg.code_changes = None
    msg.tokens_used = 100
    msg.processing_data = None
    msg.created_at = datetime.utcnow()
    return msg


# =============================================================================
# Git Change Fixtures
# =============================================================================

@pytest.fixture
def test_git_change(test_project, test_conversation):
    """Create a sample GitChange instance."""
    from app.models.models import GitChange, GitChangeStatus

    change = MagicMock(spec=GitChange)
    change.id = str(uuid4())
    change.conversation_id = test_conversation.id
    change.project_id = test_project.id
    change.message_id = None
    change.branch_name = "ai-changes/20240115-abc123"
    change.base_branch = "main"
    change.commit_hash = "abc123def456"
    change.status = GitChangeStatus.PENDING.value
    change.pr_number = None
    change.pr_url = None
    change.pr_state = None
    change.title = "Add user export feature"
    change.description = "Implements CSV export for users"
    change.files_changed = [
        {"file": "app/Http/Controllers/UserController.php", "action": "modify"}
    ]
    change.change_summary = "Added export method to UserController"
    change.rollback_commit = None
    change.rolled_back_at = None
    change.rolled_back_from_status = None
    change.created_at = datetime.utcnow()
    change.updated_at = datetime.utcnow()
    change.applied_at = None
    change.pushed_at = None
    change.pr_created_at = None
    change.merged_at = None
    return change


# =============================================================================
# Service Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_github_service():
    """Create a mocked GitHub service with PyGithub."""
    mock = MagicMock()
    mock.get_user = MagicMock()
    mock.get_repo = MagicMock()
    return mock


@pytest.fixture
def mock_github_token_service():
    """Mock the github_token_service functions."""
    with patch('app.services.github_token_service.ensure_valid_token') as mock_ensure, \
         patch('app.services.github_token_service.handle_auth_failure') as mock_handle:
        mock_ensure.return_value = AsyncMock(return_value="valid_github_token")
        mock_handle.return_value = AsyncMock(return_value="refreshed_token")
        yield {
            "ensure_valid_token": mock_ensure,
            "handle_auth_failure": mock_handle,
        }


@pytest.fixture
def mock_team_service():
    """Create a mocked TeamService."""
    mock = MagicMock()
    mock.get_team = AsyncMock(return_value=None)
    mock.get_user_teams = AsyncMock(return_value=[])
    mock.get_user_personal_team = AsyncMock(return_value=None)
    mock.get_team_members = AsyncMock(return_value=[])
    mock.get_team_projects = AsyncMock(return_value=[])
    mock.create_team = AsyncMock()
    mock.create_personal_team = AsyncMock()
    mock.add_member = AsyncMock()
    mock.remove_member = AsyncMock()
    mock.update_member_role = AsyncMock()
    mock.check_team_access = AsyncMock(return_value=True)
    mock.check_project_access = AsyncMock(return_value=True)
    mock.assign_project_to_team = AsyncMock()
    return mock


@pytest.fixture
def mock_git_service():
    """Create a mocked GitService."""
    mock = MagicMock()
    mock.clone_repo = MagicMock(return_value="/tmp/repos/test-project")
    mock.list_branches = MagicMock(return_value=[
        {"name": "main", "is_current": True, "commit": "abc123", "message": "Initial commit", "author": "testuser", "date": "2024-01-15"},
        {"name": "feature/test", "is_current": False, "commit": "def456", "message": "Add feature", "author": "testuser", "date": "2024-01-14"},
    ])
    mock.create_branch = MagicMock()
    mock.checkout_branch = MagicMock()
    mock.apply_changes = MagicMock(return_value="abc123def456")
    mock.push_branch = MagicMock()
    mock.create_pull_request = AsyncMock(return_value={
        "number": 1,
        "url": "https://github.com/testuser/test-repo/pull/1",
        "title": "Test PR",
        "state": "open",
        "created_at": datetime.utcnow().isoformat(),
    })
    mock.pull_latest = MagicMock(return_value=True)
    mock.reset_to_remote = MagicMock()
    mock.get_diff = MagicMock(return_value="diff content")
    mock.get_changed_files = MagicMock(return_value=["file1.php", "file2.php"])
    mock.get_current_branch = MagicMock(return_value="main")
    return mock


@pytest.fixture
def mock_orchestrator():
    """Create a mocked Orchestrator for chat tests."""
    from app.agents.orchestrator import ProcessResult

    mock = MagicMock()
    mock.process_request = AsyncMock(return_value=ProcessResult(
        success=True,
        intent=None,
        plan=None,
        execution_results=[],
        validation=None,
        events=[],
        error=None,
    ))
    mock.process_question = AsyncMock()
    return mock


@pytest.fixture
def mock_usage_tracker():
    """Create a mocked UsageTracker."""
    mock = MagicMock()
    mock.get_user_summary = AsyncMock(return_value={
        "summary": {
            "total_requests": 100,
            "total_input_tokens": 50000,
            "total_output_tokens": 30000,
            "total_tokens": 80000,
            "total_cost": 1.50,
        },
        "by_provider": {"claude": {"requests": 100, "tokens": 80000, "cost": 1.50}},
        "by_model": {"claude-sonnet": {"provider": "claude", "requests": 100, "tokens": 80000, "cost": 1.50}},
        "today": {"requests": 10, "cost": 0.15},
        "period": {"start": "2024-01-01", "end": "2024-01-15"},
    })
    mock.get_daily_breakdown = AsyncMock(return_value=[])
    mock.get_usage_history = AsyncMock(return_value={
        "items": [],
        "total": 0,
        "page": 1,
        "limit": 50,
        "pages": 0,
    })
    mock.get_project_summary = AsyncMock(return_value={
        "project_id": "test-id",
        "total_requests": 50,
        "total_input_tokens": 25000,
        "total_output_tokens": 15000,
        "total_cost": 0.75,
        "by_request_type": {},
        "period": {"start": "2024-01-01", "end": "2024-01-15"},
    })
    mock.update_summary = AsyncMock()
    return mock


@pytest.fixture
def mock_github_sync_service():
    """Create a mocked GitHubSyncService."""
    mock = MagicMock()
    mock.sync_issues = AsyncMock(return_value=[])
    mock.sync_actions = AsyncMock(return_value=[])
    mock.sync_projects = AsyncMock(return_value=[])
    mock.sync_insights = AsyncMock()
    mock.sync_collaborators = AsyncMock(return_value=[])
    mock.full_sync = AsyncMock(return_value={
        "collaborators": [],
        "issues": [],
        "actions": [],
        "projects": [],
        "insights": None,
        "errors": [],
    })
    return mock


@pytest.fixture
def mock_github_app_service():
    """Create a mocked GitHubAppService."""
    mock = MagicMock()
    mock.get_user_installation = AsyncMock(return_value=None)
    mock.save_installation = AsyncMock()
    mock._generate_jwt = MagicMock(return_value="mock_jwt_token")
    return mock


@pytest.fixture
def mock_ui_designer():
    """Create a mocked UIDesigner agent."""
    mock = MagicMock()
    mock.design = AsyncMock()
    mock.design_streaming = MagicMock()
    return mock


@pytest.fixture
def mock_frontend_detector():
    """Create a mocked FrontendDetector service."""
    mock = MagicMock()
    mock.detect = AsyncMock()
    return mock


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
        action="create",
        file="app/Http/Controllers/UserController.php",
        category="controller",
        description="Create UserController with export method",
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
                "reasoning": {
                    "understanding": "Request unclear",
                    "approach": "Need more information",
                    "dependency_analysis": "Cannot determine dependencies without clarity",
                    "risks_considered": "High risk due to ambiguity",
                },
                "steps": [
                    {"order": 1, "action": "modify", "file": "unknown.php", "category": "other", "description": "Placeholder until clarified", "depends_on": [], "estimated_lines": 1}
                ],
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
                "dependency_analysis": "Steps ordered by dependency",
                "risks_considered": "Low risk - standard implementation",
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


# =============================================================================
# Agent Logging Fixtures
# =============================================================================

@pytest.fixture
def test_log_dir(tmp_path):
    """
    Temporary directory for test logs.

    Creates a unique directory for each test run that persists
    during the test for inspection.
    """
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


@pytest.fixture
def agent_logger(test_log_dir, request):
    """
    Create AgentLogger for current test with auto-report save.

    Automatically generates reports at the end of the test.
    The test name is used to identify the log run.
    """
    from tests.agents.logging import AgentLogger

    test_name = request.node.name
    logger = AgentLogger(
        log_dir=test_log_dir,
        test_name=test_name,
        save_prompts=True,
        save_responses=True,
        verbose=False,
    )

    yield logger

    # Auto-generate reports after test
    try:
        logger.generate_report()
    except Exception:
        pass  # Don't fail test if report generation fails


@pytest.fixture
def agent_logger_verbose(test_log_dir, request):
    """
    Create AgentLogger with verbose output enabled.

    Useful for debugging test failures.
    """
    from tests.agents.logging import AgentLogger

    test_name = request.node.name
    logger = AgentLogger(
        log_dir=test_log_dir,
        test_name=test_name,
        save_prompts=True,
        save_responses=True,
        verbose=True,
    )

    yield logger

    try:
        logger.generate_report()
    except Exception:
        pass


@pytest.fixture
def instrumented_claude(mock_claude_service, agent_logger):
    """
    ClaudeService wrapped with full logging instrumentation.

    Intercepts all Claude API calls and logs prompts, responses,
    timing, and token metrics.
    """
    from tests.agents.logging import InstrumentedClaudeService

    return InstrumentedClaudeService(
        claude_service=mock_claude_service,
        agent_logger=agent_logger,
        default_agent="TEST",
    )


@pytest.fixture
def instrumented_mock_claude(agent_logger):
    """
    Create an instrumented mock Claude service with response tracking.

    Provides a mock service that simulates Claude responses while
    capturing all calls for logging.
    """
    from tests.agents.logging.instrumented_claude import (
        MockClaudeServiceWithUsage,
        InstrumentedClaudeService,
    )

    mock_service = MockClaudeServiceWithUsage(
        default_response="Mock response from Claude",
        simulate_tokens=True,
    )

    return InstrumentedClaudeService(
        claude_service=mock_service,
        agent_logger=agent_logger,
        default_agent="TEST",
    )


@pytest.fixture
def subscription_management_scenario():
    """
    The main test scenario with full Stripe integration.

    Returns the complete subscription management scenario
    including user input, expected flow, and mock responses.
    """
    from tests.agents.fixtures.scenarios import SUBSCRIPTION_SCENARIO
    return SUBSCRIPTION_SCENARIO


@pytest.fixture
def simple_crud_scenario():
    """Simple CRUD test scenario for basic feature tests."""
    from tests.agents.fixtures.scenarios import SIMPLE_CRUD_SCENARIO
    return SIMPLE_CRUD_SCENARIO


@pytest.fixture
def bug_fix_scenario():
    """Bug fix test scenario."""
    from tests.agents.fixtures.scenarios import BUG_FIX_SCENARIO
    return BUG_FIX_SCENARIO


@pytest.fixture
def refactor_scenario():
    """Refactoring test scenario."""
    from tests.agents.fixtures.scenarios import REFACTOR_SCENARIO
    return REFACTOR_SCENARIO


@pytest.fixture
def mock_search_results_subscription():
    """
    Mock vector search results for subscription scenario.

    Returns search results that match the subscription management
    scenario's expected context.
    """
    from app.services.vector_store import SearchResult

    return [
        SearchResult(
            chunk_id="user-model-1",
            file_path="app/Models/User.php",
            content=r"""<?php

namespace App\Models;

use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Database\Eloquent\Factories\HasFactory;

class User extends Authenticatable
{
    use HasFactory;

    protected $fillable = [
        'name',
        'email',
        'password',
    ];

    public function team()
    {
        return $this->belongsTo(Team::class);
    }

    public function projects()
    {
        return $this->hasMany(Project::class);
    }
}""",
            chunk_type="class",
            score=0.92,
            metadata={"laravel_type": "model", "lines": "1-28"},
        ),
        SearchResult(
            chunk_id="api-routes-1",
            file_path="routes/api.php",
            content=r"""<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\ProjectController;
use App\Http\Controllers\TeamController;

Route::middleware(['auth:sanctum'])->group(function () {
    Route::get('/user', [AuthController::class, 'user']);
    Route::apiResource('projects', ProjectController::class);
    Route::apiResource('teams', TeamController::class);
});""",
            chunk_type="routes",
            score=0.88,
            metadata={"laravel_type": "routes", "lines": "1-14"},
        ),
        SearchResult(
            chunk_id="base-controller-1",
            file_path="app/Http/Controllers/Controller.php",
            content=r"""<?php

namespace App\Http\Controllers;

use Illuminate\Foundation\Auth\Access\AuthorizesRequests;
use Illuminate\Foundation\Validation\ValidatesRequests;
use Illuminate\Routing\Controller as BaseController;

class Controller extends BaseController
{
    use AuthorizesRequests, ValidatesRequests;

    protected function success($data = null, string $message = 'Success', int $status = 200)
    {
        return response()->json([
            'success' => true,
            'message' => $message,
            'data' => $data,
        ], $status);
    }

    protected function error(string $message, int $status = 400)
    {
        return response()->json([
            'success' => false,
            'message' => $message,
        ], $status);
    }
}""",
            chunk_type="class",
            score=0.85,
            metadata={"laravel_type": "controller", "lines": "1-30"},
        ),
    ]


@pytest.fixture
def logged_nova(agent_logger, nova_response_factory):
    """
    Create a Nova agent with instrumented logging.

    Uses mock responses but logs all interactions.
    """
    from tests.agents.logging.instrumented_claude import (
        MockClaudeServiceWithUsage,
        InstrumentedClaudeService,
    )
    from app.agents.intent_analyzer import IntentAnalyzer

    mock_service = MockClaudeServiceWithUsage(
        responses={
            "intent": nova_response_factory(
                task_type="feature",
                domains=["controllers", "models", "services"],
            ),
        },
    )

    instrumented = InstrumentedClaudeService(
        claude_service=mock_service,
        agent_logger=agent_logger,
        default_agent="NOVA",
    )

    return IntentAnalyzer(claude_service=instrumented)


@pytest.fixture
def logged_blueprint(agent_logger, blueprint_response_factory):
    """
    Create a Blueprint agent with instrumented logging.
    """
    from tests.agents.logging.instrumented_claude import (
        MockClaudeServiceWithUsage,
        InstrumentedClaudeService,
    )
    from app.agents.planner import Planner

    mock_service = MockClaudeServiceWithUsage(
        responses={
            "planning": blueprint_response_factory(),
        },
    )

    instrumented = InstrumentedClaudeService(
        claude_service=mock_service,
        agent_logger=agent_logger,
        default_agent="BLUEPRINT",
    )

    return Planner(claude_service=instrumented)


@pytest.fixture
def logged_forge(agent_logger, forge_response_factory, reasoning_response_factory, verification_response_factory):
    """
    Create a Forge agent with instrumented logging.
    """
    from tests.agents.logging.instrumented_claude import (
        MockClaudeServiceWithUsage,
        InstrumentedClaudeService,
    )
    from app.agents.executor import Executor

    mock_service = MockClaudeServiceWithUsage(
        responses={
            "reasoning": reasoning_response_factory(),
            "code": forge_response_factory(),
            "verification": verification_response_factory(),
        },
    )

    instrumented = InstrumentedClaudeService(
        claude_service=mock_service,
        agent_logger=agent_logger,
        default_agent="FORGE",
    )

    return Executor(claude_service=instrumented)