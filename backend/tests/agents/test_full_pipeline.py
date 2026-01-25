"""
Full Agent Pipeline Integration Tests

Tests the complete flow: Nova → Scout → Blueprint → Forge
Verifies end-to-end code generation from user input to executable code.

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_full_pipeline.py -v

    # Integration tests (real API, slow)
    pytest backend/tests/agents/test_full_pipeline.py -v -m integration

    # Run all scenarios
    python backend/tests/agents/test_full_pipeline.py --run-all
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

from app.agents.intent_analyzer import IntentAnalyzer, Intent
from app.agents.context_retriever import ContextRetriever, RetrievedContext, CodeChunk
from app.agents.planner import Planner, PlanStep, Plan
from app.agents.executor import Executor, ExecutionResult, CodePatterns
from app.agents.conversation_summary import ConversationSummary
from app.agents.exceptions import InsufficientContextError
from app.agents.config import AgentConfig
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
Available models: User, Order, Product, Category, Payment, Review

### Architecture Patterns
- Service Layer pattern for business logic
- Form Requests for validation
- API Resources for response transformation
- Repository pattern for data access

### Codebase Statistics
- **Total Files:** 200
- **Controllers:** UserController, OrderController, ProductController, PaymentController
- **Models:** User, Order, Product, Category, Payment
"""

SAMPLE_CONVERSATION_SUMMARY = ConversationSummary(
    project_name="E-commerce API",
    project_id="test-project-123",
    decisions=["Use service pattern", "API versioning with v1 prefix"],
    completed_tasks=["Created Order model", "Added payment integration"],
    pending_tasks=["Add product reviews feature"],
    known_files=["app/Models/Order.php", "app/Http/Controllers/OrderController.php"],
    known_classes=["Order", "OrderController", "User", "Product"],
)

# Sample file contents for context
SAMPLE_USER_CONTROLLER = r'''<?php

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

SAMPLE_PRODUCT_MODEL = r'''<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Product extends Model
{
    use HasFactory;

    protected $fillable = ['name', 'price', 'description', 'category_id'];

    protected $casts = [
        'price' => 'decimal:2',
    ];

    public function category()
    {
        return $this->belongsTo(Category::class);
    }
}
'''

SAMPLE_ORDER_MODEL = r'''<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Order extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = ['user_id', 'total', 'status'];

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

SAMPLE_ROUTES = r'''<?php

use App\Http\Controllers\UserController;
use App\Http\Controllers\OrderController;
use App\Http\Controllers\ProductController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')->middleware(['auth:sanctum'])->group(function () {
    Route::apiResource('users', UserController::class);
    Route::apiResource('orders', OrderController::class);
    Route::apiResource('products', ProductController::class);
});
'''


# =============================================================================
# Search Results for Different Scenarios
# =============================================================================

def get_search_results(scenario_type: str) -> List[SearchResult]:
    """Get appropriate search results for scenario type."""
    results_map = {
        "user": [
            SearchResult(
                chunk_id="user-ctrl-1",
                file_path="app/Http/Controllers/UserController.php",
                content=SAMPLE_USER_CONTROLLER,
                chunk_type="class",
                score=0.95,
                metadata={"laravel_type": "controller"},
            ),
        ],
        "product": [
            SearchResult(
                chunk_id="product-model-1",
                file_path="app/Models/Product.php",
                content=SAMPLE_PRODUCT_MODEL,
                chunk_type="class",
                score=0.92,
                metadata={"laravel_type": "model"},
            ),
        ],
        "order": [
            SearchResult(
                chunk_id="order-model-1",
                file_path="app/Models/Order.php",
                content=SAMPLE_ORDER_MODEL,
                chunk_type="class",
                score=0.90,
                metadata={"laravel_type": "model"},
            ),
        ],
        "routes": [
            SearchResult(
                chunk_id="routes-1",
                file_path="routes/api.php",
                content=SAMPLE_ROUTES,
                chunk_type="routes",
                score=0.88,
                metadata={"laravel_type": "routes"},
            ),
        ],
        "mixed": [
            SearchResult(
                chunk_id="user-ctrl-1",
                file_path="app/Http/Controllers/UserController.php",
                content=SAMPLE_USER_CONTROLLER,
                chunk_type="class",
                score=0.95,
                metadata={"laravel_type": "controller"},
            ),
            SearchResult(
                chunk_id="product-model-1",
                file_path="app/Models/Product.php",
                content=SAMPLE_PRODUCT_MODEL,
                chunk_type="class",
                score=0.90,
                metadata={"laravel_type": "model"},
            ),
            SearchResult(
                chunk_id="routes-1",
                file_path="routes/api.php",
                content=SAMPLE_ROUTES,
                chunk_type="routes",
                score=0.85,
                metadata={"laravel_type": "routes"},
            ),
        ],
        "empty": [],
    }
    return results_map.get(scenario_type, results_map["mixed"])


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
        "entities": expected.get("entities", {
            "files": [], "classes": [], "methods": [], "routes": [], "tables": []
        }),
        "search_queries": expected.get("search_queries", ["query1", "query2"]),
        "reasoning": f"Analysis for {scenario['name']}",
        "overall_confidence": 0.3 if expected.get("needs_clarification") else 0.85,
        "needs_clarification": expected.get("needs_clarification", False),
        "clarifying_questions": ["What specifically?"] if expected.get("needs_clarification") else [],
    })


def create_blueprint_response(scenario: dict) -> str:
    """Create mock Blueprint response."""
    expected = scenario.get("blueprint_expected", {})

    if expected.get("needs_clarification"):
        return json.dumps({
            "summary": "Need more information",
            "reasoning": {"understanding": "Unclear", "approach": "Need clarification"},
            "steps": [],
            "overall_confidence": 0.2,
            "risk_level": "medium",
            "estimated_complexity": 1,
            "needs_clarification": True,
            "clarifying_questions": ["What feature?"],
            "warnings": [],
        })

    steps = expected.get("steps", [])
    if not steps:
        steps = [
            {
                "order": 1,
                "action": "create",
                "file": "app/Services/TestService.php",
                "category": "service",
                "description": "Create service class",
                "depends_on": [],
                "estimated_lines": 50,
            }
        ]

    return json.dumps({
        "summary": f"Plan for {scenario['name']}",
        "reasoning": {
            "understanding": scenario.get("user_input", "")[:100],
            "approach": "Standard Laravel implementation",
            "dependency_analysis": "Proper ordering",
            "risks_considered": "Low risk",
        },
        "steps": steps,
        "overall_confidence": expected.get("confidence", 0.85),
        "risk_level": expected.get("risk_level", "low"),
        "estimated_complexity": expected.get("complexity", 3),
        "needs_clarification": False,
        "clarifying_questions": [],
        "warnings": expected.get("warnings", []),
    })


def create_reasoning_response(step: dict) -> str:
    """Create mock reasoning response for Forge."""
    return json.dumps({
        "task_understanding": f"Implement {step.get('description', 'feature')}",
        "file_purpose": f"Laravel {step.get('category', 'file')}",
        "required_imports": ["App\\Models\\User"],
        "dependencies": [],
        "insertion_point": "After existing methods",
        "preservation_notes": "Keep all existing code",
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "potential_issues": [],
    })


def create_execution_response(step: dict, content: str) -> str:
    """Create mock execution response for Forge."""
    return json.dumps({
        "file": step.get("file", "test.php"),
        "action": step.get("action", "create"),
        "content": content,
    })


def create_verification_response(passes: bool = True) -> str:
    """Create mock verification response."""
    return json.dumps({
        "passes_verification": passes,
        "issues": [] if passes else ["Minor issue"],
        "content_preserved": True,
        "confidence": "high",
    })


# =============================================================================
# Full Pipeline Scenarios
# =============================================================================

FULL_PIPELINE_SCENARIOS = [
    {
        "name": "complete_feature_flow",
        "description": "Full feature implementation flows through all four agents",
        "user_input": "Add a reviews feature where users can rate products 1-5 stars",
        "search_type": "product",
        "nova_expected": {
            "task_type": "feature",
            "requires_migration": True,
            "domains": ["models", "controllers", "database"],
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "create", "file": "database/migrations/2024_01_15_create_reviews_table.php", "category": "migration", "description": "Create reviews table", "depends_on": [], "estimated_lines": 30},
                {"order": 2, "action": "create", "file": "app/Models/Review.php", "category": "model", "description": "Create Review model", "depends_on": [1], "estimated_lines": 40},
                {"order": 3, "action": "create", "file": "app/Http/Controllers/ReviewController.php", "category": "controller", "description": "Create ReviewController", "depends_on": [2], "estimated_lines": 80},
                {"order": 4, "action": "modify", "file": "routes/api.php", "category": "route", "description": "Add review routes", "depends_on": [3], "estimated_lines": 5},
            ],
            "confidence": 0.9,
        },
        "forge_expected": {
            "total_files": 4,
            "all_success": True,
        },
    },
    {
        "name": "bugfix_single_file",
        "description": "Bugfix touches single file, minimal plan",
        "user_input": "Fix the user controller index method - it's not returning proper pagination",
        "search_type": "user",
        "nova_expected": {
            "task_type": "bugfix",
            "domains": ["controllers"],
            "entities": {"classes": ["UserController"]},
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "modify", "file": "app/Http/Controllers/UserController.php", "category": "controller", "description": "Fix pagination in index method", "depends_on": [], "estimated_lines": 10},
            ],
            "confidence": 0.85,
            "risk_level": "low",
        },
        "forge_expected": {
            "total_files": 1,
            "all_success": True,
        },
        "file_contents": {
            "app/Http/Controllers/UserController.php": SAMPLE_USER_CONTROLLER,
        },
    },
    {
        "name": "ambiguous_halts_early",
        "description": "Ambiguous request halts at Nova",
        "user_input": "Fix it",
        "search_type": "mixed",
        "nova_expected": {
            "task_type": "question",
            "needs_clarification": True,
        },
        "pipeline_halts_at": "nova",
    },
    {
        "name": "refactor_multi_file",
        "description": "Refactoring touches multiple files",
        "user_input": "Refactor OrderController to use the repository pattern",
        "search_type": "order",
        "nova_expected": {
            "task_type": "refactor",
            "domains": ["controllers", "services"],
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "create", "file": "app/Repositories/OrderRepositoryInterface.php", "category": "other", "description": "Create repository interface", "depends_on": [], "estimated_lines": 20},
                {"order": 2, "action": "create", "file": "app/Repositories/OrderRepository.php", "category": "repository", "description": "Create repository implementation", "depends_on": [1], "estimated_lines": 60},
                {"order": 3, "action": "modify", "file": "app/Http/Controllers/OrderController.php", "category": "controller", "description": "Inject repository", "depends_on": [2], "estimated_lines": 30},
                {"order": 4, "action": "modify", "file": "app/Providers/AppServiceProvider.php", "category": "config", "description": "Bind repository", "depends_on": [1, 2], "estimated_lines": 5},
            ],
        },
        "forge_expected": {
            "total_files": 4,
            "all_success": True,
        },
        "file_contents": {
            "app/Http/Controllers/OrderController.php": "<?php\nclass OrderController {}",
            "app/Providers/AppServiceProvider.php": "<?php\nclass AppServiceProvider { public function register() {} }",
        },
    },
    {
        "name": "simple_method_addition",
        "description": "Simple addition to existing class",
        "user_input": "Add a getFullName() method to the User model",
        "search_type": "user",
        "nova_expected": {
            "task_type": "feature",
            "scope": "single_file",
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "modify", "file": "app/Models/User.php", "category": "model", "description": "Add getFullName method", "depends_on": [], "estimated_lines": 10},
            ],
            "complexity": 1,
        },
        "forge_expected": {
            "total_files": 1,
        },
        "file_contents": {
            "app/Models/User.php": "<?php\nclass User extends Model { protected $fillable = ['name', 'email']; }",
        },
    },
    {
        "name": "api_endpoint_creation",
        "description": "Create new API endpoint with full stack",
        "user_input": "Create an API endpoint for product search with filters",
        "search_type": "product",
        "nova_expected": {
            "task_type": "feature",
            "domains": ["controllers", "routes"],
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "create", "file": "app/Http/Requests/SearchProductRequest.php", "category": "request", "description": "Create search request validation", "depends_on": [], "estimated_lines": 25},
                {"order": 2, "action": "modify", "file": "app/Http/Controllers/ProductController.php", "category": "controller", "description": "Add search method", "depends_on": [1], "estimated_lines": 30},
                {"order": 3, "action": "modify", "file": "routes/api.php", "category": "route", "description": "Add search route", "depends_on": [2], "estimated_lines": 3},
            ],
        },
        "forge_expected": {
            "total_files": 3,
        },
        "file_contents": {
            "app/Http/Controllers/ProductController.php": "<?php\nclass ProductController { public function index() {} }",
            "routes/api.php": SAMPLE_ROUTES,
        },
    },
    {
        "name": "low_context_continues",
        "description": "Low context doesn't halt but affects confidence",
        "user_input": "Add analytics tracking to all controllers",
        "search_type": "empty",
        "nova_expected": {
            "task_type": "feature",
        },
        "blueprint_expected": {
            "confidence": 0.6,
            "warnings": ["Limited context available"],
            "steps": [
                {"order": 1, "action": "create", "file": "app/Traits/TracksAnalytics.php", "category": "trait", "description": "Create analytics trait", "depends_on": [], "estimated_lines": 30},
            ],
        },
        "forge_expected": {
            "total_files": 1,
            "has_warnings": True,
        },
    },
    {
        "name": "question_retrieves_context_only",
        "description": "Question retrieves context but doesn't execute",
        "user_input": "How does the Order model calculate totals?",
        "search_type": "order",
        "nova_expected": {
            "task_type": "question",
        },
        "pipeline_halts_at": "scout",
        "returns_context": True,
    },
    {
        "name": "database_migration_flow",
        "description": "Database change creates proper migration",
        "user_input": "Add a 'discount_code' column to the orders table",
        "search_type": "order",
        "nova_expected": {
            "task_type": "feature",
            "requires_migration": True,
            "domains": ["database", "models"],
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "create", "file": "database/migrations/2024_01_15_add_discount_code_to_orders.php", "category": "migration", "description": "Add discount_code column", "depends_on": [], "estimated_lines": 25},
                {"order": 2, "action": "modify", "file": "app/Models/Order.php", "category": "model", "description": "Add discount_code to fillable", "depends_on": [1], "estimated_lines": 5},
            ],
        },
        "forge_expected": {
            "total_files": 2,
        },
        "file_contents": {
            "app/Models/Order.php": SAMPLE_ORDER_MODEL,
        },
    },
    {
        "name": "forge_verification_triggers_fix",
        "description": "Forge verification catches issues and fixes them",
        "user_input": "Add an export method to ProductController",
        "search_type": "product",
        "nova_expected": {
            "task_type": "feature",
        },
        "blueprint_expected": {
            "steps": [
                {"order": 1, "action": "modify", "file": "app/Http/Controllers/ProductController.php", "category": "controller", "description": "Add export method", "depends_on": [], "estimated_lines": 20},
            ],
        },
        "forge_expected": {
            "total_files": 1,
            "triggers_fix": True,
        },
        "file_contents": {
            "app/Http/Controllers/ProductController.php": "<?php\nclass ProductController {}",
        },
    },
]


# =============================================================================
# Pipeline Runner
# =============================================================================

class FullAgentPipeline:
    """
    Full agent pipeline: Nova → Scout → Blueprint → Forge
    """

    def __init__(
        self,
        nova: IntentAnalyzer,
        scout: ContextRetriever,
        blueprint: Planner,
        forge: Executor,
    ):
        self.nova = nova
        self.scout = scout
        self.blueprint = blueprint
        self.forge = forge

    async def run(
        self,
        user_input: str,
        project_id: str,
        project_context: Optional[str] = None,
        conversation_summary: Optional[ConversationSummary] = None,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete pipeline.

        Returns dict with: intent, context, plan, results, halted, halt_stage
        """
        result = {
            "intent": None,
            "context": None,
            "plan": None,
            "execution_results": [],
            "halted": False,
            "halt_stage": None,
            "halt_reason": None,
            "warnings": [],
        }

        file_contents = file_contents or {}

        # ========== Stage 1: Nova - Intent Analysis ==========
        intent = await self.nova.analyze(
            user_input=user_input,
            project_context=project_context,
            conversation_summary=conversation_summary,
        )
        result["intent"] = intent

        if intent.should_halt_pipeline():
            result["halted"] = True
            result["halt_stage"] = "nova"
            result["halt_reason"] = "clarification_needed" if intent.needs_clarification else "low_confidence"
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
            context = RetrievedContext(chunks=[], warnings=[str(e)])
            result["context"] = context
            result["warnings"].append(str(e))

        # Question type halts after context retrieval
        if intent.task_type == "question":
            result["halted"] = True
            result["halt_stage"] = "scout"
            result["halt_reason"] = "question_type"
            return result

        # ========== Stage 3: Blueprint - Planning ==========
        plan = await self.blueprint.plan(
            user_input=user_input,
            intent=intent,
            context=context,
            project_context=project_context or "",
        )
        result["plan"] = plan

        if plan.should_halt_pipeline():
            result["halted"] = True
            result["halt_stage"] = "blueprint"
            result["halt_reason"] = "plan_clarification_needed" if plan.needs_clarification else "low_confidence"
            return result

        # ========== Stage 4: Forge - Execution ==========
        execution_results = []
        previous_results = []

        for step in plan.steps:
            current_content = file_contents.get(step.file)

            exec_result = await self.forge.execute_step(
                step=step,
                context=context,
                previous_results=previous_results,
                current_file_content=current_content,
                project_context=project_context or "",
                enable_self_verification=True,
            )

            execution_results.append(exec_result)
            previous_results.append(exec_result)

            # Update file contents for subsequent steps
            if exec_result.success and exec_result.content:
                file_contents[step.file] = exec_result.content

        result["execution_results"] = execution_results
        return result


# =============================================================================
# Mock Service Factory
# =============================================================================

def create_mock_services(scenario: dict) -> dict:
    """Create all mock services for a pipeline scenario."""

    # Get search results based on scenario
    search_type = scenario.get("search_type", "mixed")
    search_results = [] if search_type == "empty" else get_search_results(search_type)

    # Mock Claude for Nova
    mock_nova_claude = MagicMock()
    mock_nova_claude.chat_async = AsyncMock(return_value=create_nova_response(scenario))

    # Mock Claude for Blueprint
    mock_blueprint_claude = MagicMock()
    mock_blueprint_claude.chat_async = AsyncMock(return_value=create_blueprint_response(scenario))

    # Mock Claude for Forge (needs multiple responses per step)
    forge_expected = scenario.get("forge_expected", {})
    blueprint_expected = scenario.get("blueprint_expected", {})
    steps = blueprint_expected.get("steps", [{"order": 1, "action": "create", "file": "test.php", "category": "service", "description": "Test"}])

    forge_responses = []
    for step in steps:
        # Reasoning response
        forge_responses.append(create_reasoning_response(step))

        # Execution response
        content = f"<?php\n// Generated for {step.get('file', 'test.php')}\nclass Test {{}}"
        forge_responses.append(create_execution_response(step, content))

        # Verification response (if needed)
        if forge_expected.get("triggers_fix"):
            forge_responses.append(create_verification_response(False))
            forge_responses.append(create_execution_response(step, content + "\n// Fixed"))
        else:
            forge_responses.append(create_verification_response(True))

    mock_forge_claude = MagicMock()
    mock_forge_claude.chat_async = AsyncMock(side_effect=forge_responses)

    # Mock vector store for Scout
    mock_vector_store = MagicMock(spec=VectorStore)
    mock_vector_store.search = MagicMock(return_value=search_results)
    mock_vector_store.collection_exists = MagicMock(return_value=True)

    # Mock embedding service
    mock_embedding = MagicMock(spec=EmbeddingService)
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)

    # Mock database session
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    return {
        "nova_claude": mock_nova_claude,
        "blueprint_claude": mock_blueprint_claude,
        "forge_claude": mock_forge_claude,
        "vector_store": mock_vector_store,
        "embedding": mock_embedding,
        "db": mock_db,
    }


# =============================================================================
# Unit Tests - Full Pipeline Flow
# =============================================================================

class TestFullPipelineFlow:
    """Test the complete agent pipeline flow."""

    @pytest.mark.asyncio
    async def test_complete_feature_flow(self):
        """Test feature request flows through all four agents."""
        scenario = FULL_PIPELINE_SCENARIOS[0]  # complete_feature_flow
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
            )

        # All four agents should have run
        assert result["intent"] is not None
        assert result["context"] is not None
        assert result["plan"] is not None
        assert len(result["execution_results"]) > 0
        assert not result["halted"]

        # Verify expected file count
        forge_expected = scenario.get("forge_expected", {})
        if "total_files" in forge_expected:
            assert len(result["execution_results"]) == forge_expected["total_files"]

    @pytest.mark.asyncio
    async def test_pipeline_halts_at_nova(self):
        """Test ambiguous request halts at Nova."""
        scenario = FULL_PIPELINE_SCENARIOS[2]  # ambiguous_halts_early
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        assert result["halted"] is True
        assert result["halt_stage"] == "nova"
        assert result["context"] is None
        assert result["plan"] is None
        assert len(result["execution_results"]) == 0

    @pytest.mark.asyncio
    async def test_question_halts_at_scout(self):
        """Test question request halts after Scout."""
        scenario = FULL_PIPELINE_SCENARIOS[7]  # question_retrieves_context_only
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        assert result["halted"] is True
        assert result["halt_stage"] == "scout"
        assert result["intent"] is not None
        assert result["context"] is not None
        assert result["plan"] is None

    @pytest.mark.asyncio
    async def test_bugfix_single_file_modification(self):
        """Test bugfix modifies single existing file."""
        scenario = FULL_PIPELINE_SCENARIOS[1]  # bugfix_single_file
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                file_contents=scenario.get("file_contents", {}),
            )

        assert result["intent"].task_type == "bugfix"
        assert len(result["execution_results"]) == 1
        assert result["execution_results"][0].action == "modify"

    @pytest.mark.asyncio
    async def test_refactor_multi_file(self):
        """Test refactoring creates and modifies multiple files."""
        scenario = FULL_PIPELINE_SCENARIOS[3]  # refactor_multi_file
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                file_contents=scenario.get("file_contents", {}),
            )

        assert result["intent"].task_type == "refactor"
        assert len(result["execution_results"]) == 4

        # Check mix of create and modify
        actions = [r.action for r in result["execution_results"]]
        assert "create" in actions
        assert "modify" in actions

    @pytest.mark.asyncio
    async def test_migration_requirement_flows_through(self):
        """Test migration requirement flows from Nova to Forge."""
        scenario = FULL_PIPELINE_SCENARIOS[8]  # database_migration_flow
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                file_contents=scenario.get("file_contents", {}),
            )

        assert result["intent"].requires_migration is True

        # First step should be migration
        migration_steps = [s for s in result["plan"].steps if s.category == "migration"]
        assert len(migration_steps) > 0

    @pytest.mark.asyncio
    async def test_execution_order_respects_dependencies(self):
        """Test that execution follows dependency order."""
        scenario = FULL_PIPELINE_SCENARIOS[0]  # complete_feature_flow
        mocks = create_mock_services(scenario)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Results should be in order
        assert len(result["execution_results"]) == len(result["plan"].steps)

        # Migration should come before model
        files = [r.file for r in result["execution_results"]]
        migration_idx = next((i for i, f in enumerate(files) if "migration" in f), -1)
        model_idx = next((i for i, f in enumerate(files) if "Models" in f), -1)

        if migration_idx >= 0 and model_idx >= 0:
            assert migration_idx < model_idx


# =============================================================================
# Unit Tests - Error Handling
# =============================================================================

class TestPipelineErrorHandling:
    """Test error handling in the full pipeline."""

    @pytest.mark.asyncio
    async def test_nova_error_halts_pipeline(self):
        """Test that Nova error halts the pipeline gracefully."""
        mocks = create_mock_services(FULL_PIPELINE_SCENARIOS[0])
        mocks["nova_claude"].chat_async = AsyncMock(side_effect=Exception("API Error"))

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input="test input",
                project_id="test-123",
            )

        # Should halt with clarification (fallback behavior)
        assert result["halted"] is True
        assert result["intent"].needs_clarification is True

    @pytest.mark.asyncio
    async def test_forge_error_continues_other_steps(self):
        """Test that Forge error on one step doesn't stop others."""
        scenario = FULL_PIPELINE_SCENARIOS[0]
        mocks = create_mock_services(scenario)

        # Make first execution fail, others succeed
        original_responses = list(mocks["forge_claude"].chat_async.side_effect)
        original_responses[1] = '{"error": "Generation failed"}'
        mocks["forge_claude"].chat_async = AsyncMock(side_effect=original_responses)

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mocks["nova_claude"]):
            nova = IntentAnalyzer(claude_service=mocks["nova_claude"])
            scout = ContextRetriever(
                db=mocks["db"],
                vector_store=mocks["vector_store"],
                embedding_service=mocks["embedding"],
            )
            blueprint = Planner(claude_service=mocks["blueprint_claude"])
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
            )

        # Pipeline should complete
        assert len(result["execution_results"]) > 0


# =============================================================================
# Parametrized Scenario Tests
# =============================================================================

class TestAllPipelineScenarios:
    """Run all pipeline scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", FULL_PIPELINE_SCENARIOS, ids=[s["name"] for s in FULL_PIPELINE_SCENARIOS])
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
            forge = Executor(claude_service=mocks["forge_claude"])

            pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
            result = await pipeline.run(
                user_input=scenario["user_input"],
                project_id="test-123",
                project_context=SAMPLE_PROJECT_CONTEXT,
                file_contents=scenario.get("file_contents", {}),
            )

        # Validate based on scenario expectations
        if "pipeline_halts_at" in scenario:
            assert result["halted"] is True
            assert result["halt_stage"] == scenario["pipeline_halts_at"]
        else:
            # Nova expectations
            nova_expected = scenario.get("nova_expected", {})
            if "task_type" in nova_expected:
                assert result["intent"].task_type == nova_expected["task_type"]
            if "requires_migration" in nova_expected:
                assert result["intent"].requires_migration == nova_expected["requires_migration"]

            # Forge expectations
            if not result["halted"]:
                forge_expected = scenario.get("forge_expected", {})
                if "total_files" in forge_expected:
                    assert len(result["execution_results"]) == forge_expected["total_files"]


# =============================================================================
# Integration Tests (Real API)
# =============================================================================

@pytest.mark.integration
class TestFullPipelineIntegration:
    """Integration tests with real Claude API."""

    @pytest.mark.asyncio
    async def test_real_simple_feature(self):
        """Test real simple feature through pipeline."""
        nova = IntentAnalyzer()
        # Note: Would need real Scout, Blueprint, Forge for full test

        intent = await nova.analyze(
            user_input="Add a getDisplayName method to the User model",
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert intent.task_type == "feature"
        assert not intent.needs_clarification


# =============================================================================
# CLI Runner
# =============================================================================

async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all full pipeline scenarios."""
    print("\n" + "=" * 70)
    print("Full Agent Pipeline - Running All Scenarios")
    print("Nova → Scout → Blueprint → Forge")
    print("=" * 70)

    results = []
    passed = 0
    failed = 0

    for scenario in FULL_PIPELINE_SCENARIOS:
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
                forge = Executor(claude_service=mocks["forge_claude"])

                pipeline = FullAgentPipeline(nova, scout, blueprint, forge)
                result = await pipeline.run(
                    user_input=scenario["user_input"],
                    project_id="test-123",
                    project_context=SAMPLE_PROJECT_CONTEXT,
                    file_contents=scenario.get("file_contents", {}),
                )

            # Validate
            errors = []

            if "pipeline_halts_at" in scenario:
                if not result["halted"]:
                    errors.append(f"Expected halt at {scenario['pipeline_halts_at']}")
                elif result["halt_stage"] != scenario["pipeline_halts_at"]:
                    errors.append(f"Wrong halt stage: {result['halt_stage']}")
            else:
                if result["halted"]:
                    errors.append(f"Unexpected halt at {result['halt_stage']}")

                forge_expected = scenario.get("forge_expected", {})
                if "total_files" in forge_expected:
                    if len(result["execution_results"]) != forge_expected["total_files"]:
                        errors.append(f"File count: expected {forge_expected['total_files']}, got {len(result['execution_results'])}")

            if errors:
                print(f"   ❌ FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                status = result["halt_stage"] or "COMPLETE"
                exec_count = len(result["execution_results"])
                print(f"   ✅ PASSED (status={status}, executed={exec_count})")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "passed": len(errors) == 0,
                "halted": result["halted"],
                "halt_stage": result["halt_stage"],
                "intent_type": result["intent"].task_type if result["intent"] else None,
                "plan_steps": len(result["plan"].steps) if result["plan"] else 0,
                "execution_results": len(result["execution_results"]),
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
    print(f"Results: {passed} passed, {failed} failed, {len(FULL_PIPELINE_SCENARIOS)} total")
    print("=" * 70)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline": "Nova → Scout → Blueprint → Forge",
                "summary": {"passed": passed, "failed": failed},
                "results": results,
            }, f, indent=2)
        print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test Full Agent Pipeline")
    parser.add_argument("--run-all", action="store_true", help="Run all scenarios")
    parser.add_argument("--output", type=str, help="Output file for results")

    args = parser.parse_args()

    if args.run_all:
        asyncio.run(run_all_scenarios(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()