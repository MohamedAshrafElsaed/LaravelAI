"""
Forge (Executor) Agent Unit Tests

Tests for the code generation engine including:
- Pattern extraction (Group A)
- Chain-of-thought reasoning (Group B)
- Precision modification (Group D)
- Self-verification and fixing
- Error recovery

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_executor.py -v

    # Integration tests (real API, slow)
    pytest backend/tests/agents/test_executor.py -v -m integration

    # Run all scenarios
    python backend/tests/agents/test_executor.py --run-all
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

from app.agents.executor import (
    Executor,
    ExecutionResult,
    CodePatterns,
    ExecutionReasoning,
    InsertionPoint,
    safe_format,
)
from app.agents.planner import PlanStep
from app.agents.context_retriever import RetrievedContext, CodeChunk
from app.agents.config import AgentConfig


# =============================================================================
# Sample Data - Using raw strings to avoid unicode escape issues
# =============================================================================

SAMPLE_PHP_CONTROLLER = r'''<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * User Controller
 *
 * Handles user-related HTTP requests.
 */
class UserController extends Controller
{
    /**
     * Display a listing of users.
     *
     * @return JsonResponse
     */
    public function index(): JsonResponse
    {
        $users = User::paginate(15);
        return response()->json($users);
    }

    /**
     * Store a newly created user.
     *
     * @param Request $request
     * @return JsonResponse
     */
    public function store(Request $request): JsonResponse
    {
        $user = User::create($request->validated());
        return response()->json($user, 201);
    }
}
'''

SAMPLE_PHP_MODEL = r'''<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

/**
 * Order Model
 *
 * @property int $id
 * @property int $user_id
 * @property float $total
 */
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
        'created_at' => 'datetime',
    ];

    public function user()
    {
        return $this->belongsTo(User::class);
    }
}
'''

SAMPLE_ROUTES_FILE = r'''<?php

use App\Http\Controllers\UserController;
use App\Http\Controllers\OrderController;
use Illuminate\Support\Facades\Route;

Route::middleware(['auth:sanctum'])->group(function () {
    Route::apiResource('users', UserController::class);
    Route::apiResource('orders', OrderController::class);
});
'''


def create_sample_context(chunks: List[Dict] = None) -> RetrievedContext:
    """Create sample retrieved context."""
    if chunks is None:
        chunks = [
            {
                "file_path": "app/Http/Controllers/UserController.php",
                "content": SAMPLE_PHP_CONTROLLER,
                "chunk_type": "class",
            },
            {
                "file_path": "app/Models/Order.php",
                "content": SAMPLE_PHP_MODEL,
                "chunk_type": "class",
            },
        ]

    code_chunks = [
        CodeChunk(
            chunk_id=f"chunk-{i}",
            file_path=c["file_path"],
            content=c["content"],
            chunk_type=c.get("chunk_type", "class"),
            relevance_score=0.9 - (i * 0.1),
        )
        for i, c in enumerate(chunks)
    ]

    return RetrievedContext(
        chunks=code_chunks,
        confidence_level="high",
        domain_summaries={"controllers": "User and Order controllers"},
    )


def create_plan_step(
    order: int = 1,
    action: str = "modify",
    file: str = "app/Http/Controllers/UserController.php",
    description: str = "Add export method",
    category: str = "controller",
) -> PlanStep:
    """Create a sample plan step."""
    return PlanStep(
        order=order,
        action=action,
        file=file,
        category=category,
        description=description,
        depends_on=[],
        estimated_lines=50,
    )


# =============================================================================
# Mock Response Factories
# =============================================================================

def create_reasoning_response(step: PlanStep) -> str:
    """Create mock reasoning response."""
    return json.dumps({
        "task_understanding": f"Add functionality to {step.file}",
        "file_purpose": "Controller for handling HTTP requests",
        "required_imports": ["App\\Models\\User", "Illuminate\\Http\\Response"],
        "dependencies": ["User model"],
        "insertion_point": "After the store method, before the closing brace",
        "preservation_notes": "Keep all existing methods intact",
        "implementation_steps": [
            "Add use statement if needed",
            "Create new method with proper docblock",
            "Implement business logic",
        ],
        "potential_issues": ["May need to handle large datasets"],
    })


def create_execution_response(step: PlanStep, content: str) -> str:
    """Create mock execution response."""
    return json.dumps({
        "file": step.file,
        "action": step.action,
        "content": content,
    })


def create_verification_response(passes: bool = True, issues: List[str] = None) -> str:
    """Create mock verification response."""
    return json.dumps({
        "passes_verification": passes,
        "issues": issues or [],
        "content_preserved": True,
        "confidence": "high",
    })


def create_fix_response(step: PlanStep, content: str) -> str:
    """Create mock fix response."""
    return json.dumps({
        "file": step.file,
        "action": step.action,
        "content": content,
        "fixes_applied": ["Fixed syntax error", "Added missing import"],
    })


# =============================================================================
# Executor Test Scenarios
# =============================================================================

EXECUTOR_SCENARIOS = [
    {
        "name": "create_new_controller",
        "description": "Create a new controller file",
        "step": {
            "order": 1,
            "action": "create",
            "file": "app/Http/Controllers/ProductController.php",
            "category": "controller",
            "description": "Create ProductController with index and store methods",
        },
        "current_content": None,
        "expected": {
            "success": True,
            "has_content": True,
            "action": "create",
        },
    },
    {
        "name": "modify_add_method",
        "description": "Add a new method to existing controller",
        "step": {
            "order": 1,
            "action": "modify",
            "file": "app/Http/Controllers/UserController.php",
            "category": "controller",
            "description": "Add export method to generate CSV",
        },
        "current_content": SAMPLE_PHP_CONTROLLER,
        "expected": {
            "success": True,
            "has_content": True,
            "action": "modify",
            "preserves_content": True,
        },
    },
    {
        "name": "modify_add_relationship",
        "description": "Add relationship to model",
        "step": {
            "order": 1,
            "action": "modify",
            "file": "app/Models/Order.php",
            "category": "model",
            "description": "Add items() hasMany relationship",
        },
        "current_content": SAMPLE_PHP_MODEL,
        "expected": {
            "success": True,
            "has_content": True,
            "preserves_content": True,
        },
    },
    {
        "name": "modify_add_route",
        "description": "Add new route to routes file",
        "step": {
            "order": 1,
            "action": "modify",
            "file": "routes/api.php",
            "category": "route",
            "description": "Add product export route",
        },
        "current_content": SAMPLE_ROUTES_FILE,
        "expected": {
            "success": True,
            "preserves_content": True,
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file safely",
        "step": {
            "order": 1,
            "action": "delete",
            "file": "app/Http/Controllers/LegacyController.php",
            "category": "controller",
            "description": "Remove deprecated controller",
        },
        "current_content": "<?php\nclass LegacyController {}",
        "expected": {
            "success": True,
            "action": "delete",
            "empty_content": True,
        },
    },
    {
        "name": "modify_nonexistent_file",
        "description": "Attempt to modify non-existent file",
        "step": {
            "order": 1,
            "action": "modify",
            "file": "app/Http/Controllers/NonExistent.php",
            "category": "controller",
            "description": "Modify non-existent file",
        },
        "current_content": None,
        "expected": {
            "success": False,
            "has_error": True,
        },
    },
    {
        "name": "create_migration",
        "description": "Create a new migration file",
        "step": {
            "order": 1,
            "action": "create",
            "file": "database/migrations/2024_01_15_create_reviews_table.php",
            "category": "migration",
            "description": "Create reviews table with rating and comment columns",
        },
        "current_content": None,
        "expected": {
            "success": True,
            "has_content": True,
        },
    },
    {
        "name": "create_form_request",
        "description": "Create a form request class",
        "step": {
            "order": 1,
            "action": "create",
            "file": "app/Http/Requests/StoreProductRequest.php",
            "category": "request",
            "description": "Create validation request for storing products",
        },
        "current_content": None,
        "expected": {
            "success": True,
            "has_content": True,
        },
    },
]


# =============================================================================
# Unit Tests - CodePatterns
# =============================================================================

class TestCodePatterns:
    """Tests for CodePatterns data class."""

    def test_default_patterns(self):
        """Test default pattern values."""
        patterns = CodePatterns()

        assert patterns.indent_style == "spaces"
        assert patterns.indent_size == 4
        assert patterns.declare_strict_types is True
        assert patterns.docblock_style == "full"
        assert patterns.method_naming == "camelCase"

    def test_to_prompt_string(self):
        """Test prompt string generation."""
        patterns = CodePatterns(
            indent_size=4,
            declare_strict_types=True,
            uses_repository_pattern=True,
            common_traits=["HasFactory", "SoftDeletes"],
        )

        prompt_str = patterns.to_prompt_string()

        assert "<detected_patterns>" in prompt_str
        assert "strict_types='True'" in prompt_str
        assert "Repository Pattern" in prompt_str
        assert "HasFactory" in prompt_str

    def test_pattern_with_sample_docblock(self):
        """Test pattern with sample docblock."""
        sample = "/** @param string $name */"
        patterns = CodePatterns(sample_docblock=sample)

        prompt_str = patterns.to_prompt_string()

        assert "<sample_docblock>" in prompt_str
        assert "@param string" in prompt_str


# =============================================================================
# Unit Tests - ExecutionReasoning
# =============================================================================

class TestExecutionReasoning:
    """Tests for ExecutionReasoning data class."""

    def test_default_reasoning(self):
        """Test default reasoning values."""
        reasoning = ExecutionReasoning()

        assert reasoning.task_understanding == ""
        assert reasoning.required_imports == []
        assert reasoning.implementation_steps == []

    def test_to_dict(self):
        """Test dictionary conversion."""
        reasoning = ExecutionReasoning(
            task_understanding="Add export feature",
            required_imports=["App\\Models\\User"],
            implementation_steps=["Step 1", "Step 2"],
        )

        data = reasoning.to_dict()

        assert data["task_understanding"] == "Add export feature"
        assert len(data["required_imports"]) == 1
        assert len(data["implementation_steps"]) == 2


# =============================================================================
# Unit Tests - ExecutionResult
# =============================================================================

class TestExecutionResult:
    """Tests for ExecutionResult data class."""

    def test_successful_result(self):
        """Test successful execution result."""
        result = ExecutionResult(
            file="test.php",
            action="create",
            content="<?php echo 'test';",
        )

        assert result.success is True
        assert result.error is None
        assert result.warnings == []

    def test_failed_result(self):
        """Test failed execution result."""
        result = ExecutionResult(
            file="test.php",
            action="modify",
            content="",
            success=False,
            error="File not found",
        )

        assert result.success is False
        assert result.error == "File not found"

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = ExecutionResult(
            file="test.php",
            action="create",
            content="<?php",
            diff="+ <?php",
        )

        data = result.to_dict()

        assert data["file"] == "test.php"
        assert data["action"] == "create"
        assert data["diff"] == "+ <?php"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "file": "test.php",
            "action": "modify",
            "content": "<?php",
            "success": True,
        }

        result = ExecutionResult.from_dict(data)

        assert result.file == "test.php"
        assert result.action == "modify"
        assert result.success is True

    def test_from_dict_with_string(self):
        """Test creation from JSON string."""
        json_str = '{"file": "test.php", "action": "create", "content": "<?php"}'

        result = ExecutionResult.from_dict(json_str)

        assert result.file == "test.php"

    def test_from_dict_with_invalid_data(self):
        """Test creation with invalid data."""
        result = ExecutionResult.from_dict("not valid json {")

        assert result.success is False
        assert result.error is not None


# =============================================================================
# Unit Tests - Pattern Extraction (Group A)
# =============================================================================

class TestPatternExtraction:
    """Tests for pattern extraction from codebase context."""

    @pytest.fixture
    def executor(self):
        """Create executor with mocked Claude service."""
        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(return_value="{}")
        return Executor(claude_service=mock_claude)

    def test_extract_strict_types(self, executor):
        """Test detection of strict_types declaration."""
        context = create_sample_context([
            {"file_path": "test.php", "content": "<?php\ndeclare(strict_types=1);"}
        ])

        patterns = executor._extract_code_patterns(context, "test.php")

        assert patterns.declare_strict_types is True

    def test_extract_indentation(self, executor):
        """Test detection of indentation style."""
        context = create_sample_context([
            {"file_path": "test.php", "content": "<?php\nclass Test {\n    public function test() {}\n}"}
        ])

        patterns = executor._extract_code_patterns(context, "test.php")

        assert patterns.indent_style == "spaces"
        assert patterns.indent_size == 4

    def test_extract_docblock_style(self, executor):
        """Test detection of docblock style."""
        context = create_sample_context([
            {"file_path": "test.php", "content": SAMPLE_PHP_CONTROLLER}
        ])

        patterns = executor._extract_code_patterns(context, "test.php")

        assert patterns.docblock_style == "full"

    def test_extract_repository_pattern(self, executor):
        """Test detection of repository pattern."""
        context = create_sample_context([
            {"file_path": "app/Repositories/UserRepository.php",
             "content": "interface UserRepositoryInterface {}"}
        ])

        patterns = executor._extract_code_patterns(context, "test.php")

        assert patterns.uses_repository_pattern is True

    def test_extract_common_traits(self, executor):
        """Test detection of common traits."""
        context = create_sample_context([
            {"file_path": "test.php", "content": SAMPLE_PHP_MODEL}
        ])

        patterns = executor._extract_code_patterns(context, "test.php")

        assert "HasFactory" in patterns.common_traits or "SoftDeletes" in patterns.common_traits

    def test_empty_context_returns_defaults(self, executor):
        """Test that empty context returns default patterns."""
        context = RetrievedContext(chunks=[], confidence_level="low")

        patterns = executor._extract_code_patterns(context, "test.php")

        assert patterns.indent_size == 4
        assert patterns.indent_style == "spaces"


# =============================================================================
# Unit Tests - Content Preservation
# =============================================================================

class TestContentPreservation:
    """Tests for content preservation validation."""

    @pytest.fixture
    def executor(self):
        mock_claude = MagicMock()
        return Executor(claude_service=mock_claude)

    def test_preservation_check_passes(self, executor):
        """Test preservation check with valid modification."""
        original = SAMPLE_PHP_CONTROLLER
        modified = original.replace(
            "}\n}",
            """    public function export(): JsonResponse
    {
        return response()->json(['data' => 'export']);
    }
}
}"""
        )

        result = executor._check_content_preservation(original, modified)

        assert result["preserved"] is True
        assert len(result["issues"]) == 0

    def test_preservation_check_fails_on_removal(self, executor):
        """Test preservation check detects content removal."""
        original = SAMPLE_PHP_CONTROLLER
        modified = "<?php\nclass UserController {}"  # Lost all methods

        result = executor._check_content_preservation(original, modified)

        assert result["preserved"] is False
        assert len(result["issues"]) > 0

    def test_preservation_check_with_empty_original(self, executor):
        """Test preservation check with empty original (create action)."""
        result = executor._check_content_preservation("", "<?php\nclass Test {}")

        assert result["preserved"] is True

    def test_preservation_detects_route_removal(self, executor):
        """Test that route removal is detected."""
        original = SAMPLE_ROUTES_FILE
        modified = "<?php\nRoute::get('/test', fn() => 'test');"

        result = executor._check_content_preservation(original, modified)

        assert result["preserved"] is False
        assert any("Route" in issue for issue in result["issues"])


# =============================================================================
# Unit Tests - Diff Generation
# =============================================================================

class TestDiffGeneration:
    """Tests for diff generation."""

    @pytest.fixture
    def executor(self):
        mock_claude = MagicMock()
        return Executor(claude_service=mock_claude)

    def test_generate_diff_for_new_file(self, executor):
        """Test diff generation for new file."""
        diff = executor._generate_diff("", "<?php\necho 'test';", "test.php")

        assert "+<?php" in diff
        assert "a/test.php" in diff
        assert "b/test.php" in diff

    def test_generate_diff_for_modification(self, executor):
        """Test diff generation for modification."""
        original = "<?php\nclass Test {}"
        modified = "<?php\nclass Test {\n    public function test() {}\n}"

        diff = executor._generate_diff(original, modified, "test.php")

        assert "+" in diff
        assert "public function test" in diff

    def test_generate_diff_for_deletion(self, executor):
        """Test diff generation for deletion."""
        original = "<?php\nclass Test {}"

        diff = executor._generate_diff(original, "", "test.php")

        assert "-<?php" in diff


# =============================================================================
# Unit Tests - Executor Execute Step
# =============================================================================

class TestExecutorExecuteStep:
    """Tests for the main execute_step method."""

    def create_mock_executor(self, reasoning_response: str = None, execution_response: str = None):
        """Create executor with configured mock responses."""
        mock_claude = MagicMock()

        responses = []
        if reasoning_response:
            responses.append(reasoning_response)
        if execution_response:
            responses.append(execution_response)

        if responses:
            mock_claude.chat_async = AsyncMock(side_effect=responses)
        else:
            mock_claude.chat_async = AsyncMock(return_value="{}")

        return Executor(claude_service=mock_claude)

    @pytest.mark.asyncio
    async def test_execute_create_step(self):
        """Test executing a create step."""
        step = create_plan_step(action="create", file="app/Services/TestService.php")
        context = create_sample_context()

        new_content = "<?php\nnamespace App\\Services;\nclass TestService {}"

        executor = self.create_mock_executor(
            reasoning_response=create_reasoning_response(step),
            execution_response=create_execution_response(step, new_content),
        )

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=None,
            enable_self_verification=False,
        )

        assert result.success is True
        assert result.action == "create"
        assert result.file == step.file

    @pytest.mark.asyncio
    async def test_execute_modify_step(self):
        """Test executing a modify step."""
        step = create_plan_step(action="modify")
        context = create_sample_context()

        modified_content = SAMPLE_PHP_CONTROLLER + "\n    public function export() {}"

        executor = self.create_mock_executor(
            reasoning_response=create_reasoning_response(step),
            execution_response=create_execution_response(step, modified_content),
        )

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=SAMPLE_PHP_CONTROLLER,
            enable_self_verification=False,
        )

        assert result.success is True
        assert result.action == "modify"
        assert result.original_content == SAMPLE_PHP_CONTROLLER

    @pytest.mark.asyncio
    async def test_execute_modify_nonexistent_file_fails(self):
        """Test that modifying non-existent file fails."""
        step = create_plan_step(action="modify")
        context = create_sample_context()

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock()

        config = AgentConfig()
        config.REQUIRE_FILE_EXISTS_FOR_MODIFY = True

        executor = Executor(claude_service=mock_claude, config=config)

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=None,  # File doesn't exist
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_delete_step(self):
        """Test executing a delete step."""
        step = create_plan_step(action="delete")
        context = create_sample_context()

        delete_response = json.dumps({
            "file": step.file,
            "action": "delete",
            "content": "",
            "safe_to_delete": True,
            "reason": "No longer needed",
        })

        executor = self.create_mock_executor(execution_response=delete_response)

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content="<?php class Old {}",
            enable_self_verification=False,
        )

        assert result.action == "delete"
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_execute_with_low_context_confidence(self):
        """Test execution continues with low context confidence but adds warning."""
        step = create_plan_step(action="create")
        context = RetrievedContext(chunks=[], confidence_level="low")

        new_content = "<?php class Test {}"

        executor = self.create_mock_executor(
            reasoning_response=create_reasoning_response(step),
            execution_response=create_execution_response(step, new_content),
        )

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=None,
            enable_self_verification=False,
        )

        assert result.success is True
        assert any("confidence" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_execute_with_previous_results(self):
        """Test that previous results are included in context."""
        step = create_plan_step(order=2, action="modify")
        context = create_sample_context()

        previous = [
            ExecutionResult(
                file="app/Models/User.php",
                action="create",
                content="<?php class User {}",
                success=True,
            )
        ]

        modified_content = SAMPLE_PHP_CONTROLLER

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(side_effect=[
            create_reasoning_response(step),
            create_execution_response(step, modified_content),
        ])

        executor = Executor(claude_service=mock_claude)

        await executor.execute_step(
            step=step,
            context=context,
            previous_results=previous,
            current_file_content=SAMPLE_PHP_CONTROLLER,
            enable_self_verification=False,
        )

        # Verify previous results were passed to Claude
        calls = mock_claude.chat_async.call_args_list
        assert len(calls) >= 1


# =============================================================================
# Unit Tests - Self Verification
# =============================================================================

class TestSelfVerification:
    """Tests for self-verification functionality."""

    @pytest.mark.asyncio
    async def test_verification_passes(self):
        """Test verification passes for valid code."""
        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(return_value=create_verification_response(True))

        executor = Executor(claude_service=mock_claude)

        result = ExecutionResult(
            file="test.php",
            action="create",
            content="<?php\nnamespace App;\nclass Test {}",
        )

        passes, issues = await executor._verify_result(result, None)

        assert passes is True
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_verification_fails_with_issues(self):
        """Test verification fails and returns issues."""
        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=create_verification_response(False, ["Missing namespace", "Invalid syntax"])
        )

        executor = Executor(claude_service=mock_claude)

        result = ExecutionResult(
            file="test.php",
            action="create",
            content="<?php class Test {}",  # Missing namespace
        )

        passes, issues = await executor._verify_result(result, None)

        assert passes is False
        assert "Missing namespace" in issues

    @pytest.mark.asyncio
    async def test_verification_skipped_for_delete(self):
        """Test verification is skipped for delete action."""
        mock_claude = MagicMock()
        executor = Executor(claude_service=mock_claude)

        result = ExecutionResult(
            file="test.php",
            action="delete",
            content="",
        )

        passes, issues = await executor._verify_result(result, None)

        assert passes is True
        mock_claude.chat_async.assert_not_called()


# =============================================================================
# Unit Tests - Fix Execution
# =============================================================================

class TestFixExecution:
    """Tests for fix execution functionality."""

    @pytest.mark.asyncio
    async def test_fix_execution_corrects_issues(self):
        """Test that fix execution corrects identified issues."""
        step = create_plan_step()
        original_content = "<?php class Test {"  # Missing closing brace
        fixed_content = "<?php class Test {}"

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=create_fix_response(step, fixed_content)
        )

        executor = Executor(claude_service=mock_claude)

        result = ExecutionResult(
            file=step.file,
            action="create",
            content=original_content,
        )

        context = create_sample_context()
        patterns = CodePatterns()

        fixed_result = await executor._fix_execution(
            result, ["Missing closing brace"], context, patterns
        )

        assert fixed_result.content == fixed_content

    @pytest.mark.asyncio
    async def test_fix_preserves_original_on_modify(self):
        """Test that fix preserves original content for modify action."""
        original = SAMPLE_PHP_CONTROLLER

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=json.dumps({
                "file": "test.php",
                "action": "modify",
                "content": original + "\n// Fixed",
            })
        )

        executor = Executor(claude_service=mock_claude)

        result = ExecutionResult(
            file="test.php",
            action="modify",
            content=original,
            original_content=original,
        )

        context = create_sample_context()
        patterns = CodePatterns()

        fixed_result = await executor._fix_execution(
            result, ["Minor issue"], context, patterns
        )

        # Original content should be in the prompt
        call_args = mock_claude.chat_async.call_args
        prompt = str(call_args)
        assert "ORIGINAL" in prompt.upper() or "original" in prompt


# =============================================================================
# Unit Tests - Error Recovery
# =============================================================================

class TestErrorRecovery:
    """Tests for error recovery functionality."""

    @pytest.mark.asyncio
    async def test_recover_from_json_error(self):
        """Test recovery from JSON parse error."""
        step = create_plan_step()
        recovered_content = "<?php class Recovered {}"

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=json.dumps({
                "file": step.file,
                "action": step.action,
                "content": recovered_content,
            })
        )

        executor = Executor(claude_service=mock_claude)

        result = await executor._recover_from_error(
            step=step,
            error_type="json_parse",
            error_message="Invalid JSON",
            partial_output="<?php class Partial {",
        )

        assert result.success is True
        assert result.content == recovered_content

    @pytest.mark.asyncio
    async def test_recover_failure_returns_error(self):
        """Test that recovery failure returns error result."""
        step = create_plan_step()

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=json.dumps({"content": ""})  # Empty content
        )

        executor = Executor(claude_service=mock_claude)

        result = await executor._recover_from_error(
            step=step,
            error_type="unknown",
            error_message="Fatal error",
            partial_output="",
        )

        assert result.success is False


# =============================================================================
# Unit Tests - Reasoning Generation (Group B)
# =============================================================================

class TestReasoningGeneration:
    """Tests for chain-of-thought reasoning generation."""

    @pytest.mark.asyncio
    async def test_reasoning_generated_for_create(self):
        """Test reasoning is generated for create action."""
        step = create_plan_step(action="create")
        context = create_sample_context()
        patterns = CodePatterns()

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=create_reasoning_response(step)
        )

        executor = Executor(claude_service=mock_claude)

        reasoning = await executor._generate_reasoning(
            step=step,
            patterns=patterns,
            context=context,
            current_content="",
        )

        assert reasoning.task_understanding != ""
        assert len(reasoning.implementation_steps) > 0

    @pytest.mark.asyncio
    async def test_reasoning_includes_insertion_point_for_modify(self):
        """Test reasoning includes insertion point for modify action."""
        step = create_plan_step(action="modify")
        context = create_sample_context()
        patterns = CodePatterns()

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(
            return_value=create_reasoning_response(step)
        )

        executor = Executor(claude_service=mock_claude)

        reasoning = await executor._generate_reasoning(
            step=step,
            patterns=patterns,
            context=context,
            current_content=SAMPLE_PHP_CONTROLLER,
        )

        assert reasoning.insertion_point != ""

    @pytest.mark.asyncio
    async def test_reasoning_fallback_on_error(self):
        """Test reasoning falls back gracefully on error."""
        step = create_plan_step()
        context = create_sample_context()
        patterns = CodePatterns()

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(side_effect=Exception("API Error"))

        executor = Executor(claude_service=mock_claude)

        reasoning = await executor._generate_reasoning(
            step=step,
            patterns=patterns,
            context=context,
            current_content="",
        )

        # Should return default reasoning, not crash
        assert reasoning.task_understanding == step.description


# =============================================================================
# Parametrized Scenario Tests
# =============================================================================

class TestAllExecutorScenarios:
    """Run all executor scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", EXECUTOR_SCENARIOS, ids=[s["name"] for s in EXECUTOR_SCENARIOS])
    async def test_scenario(self, scenario):
        """Test each executor scenario."""
        step_data = scenario["step"]
        step = PlanStep(
            order=step_data["order"],
            action=step_data["action"],
            file=step_data["file"],
            category=step_data["category"],
            description=step_data["description"],
            depends_on=[],
            estimated_lines=50,
        )

        context = create_sample_context()
        expected = scenario["expected"]

        # Create mock responses based on action
        if step.action == "delete":
            execution_response = json.dumps({
                "file": step.file,
                "action": "delete",
                "content": "",
                "safe_to_delete": True,
            })
            mock_responses = [execution_response]
        else:
            content = scenario.get("current_content") or "<?php\nclass Test {}"
            if step.action == "modify" and scenario.get("current_content"):
                content = scenario["current_content"] + "\n// Modified"

            mock_responses = [
                create_reasoning_response(step),
                create_execution_response(step, content),
            ]

        mock_claude = MagicMock()
        mock_claude.chat_async = AsyncMock(side_effect=mock_responses)

        config = AgentConfig()
        config.REQUIRE_FILE_EXISTS_FOR_MODIFY = True

        executor = Executor(claude_service=mock_claude, config=config)

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=scenario.get("current_content"),
            enable_self_verification=False,
        )

        # Validate expectations
        if "success" in expected:
            assert result.success == expected["success"]

        if "action" in expected:
            assert result.action == expected["action"]

        if expected.get("has_error"):
            assert result.error is not None

        if expected.get("has_content"):
            assert result.content != ""

        if expected.get("empty_content"):
            assert result.content == ""


# =============================================================================
# Integration Tests (Real API)
# =============================================================================

@pytest.mark.integration
class TestExecutorIntegration:
    """Integration tests with real Claude API."""

    @pytest.mark.asyncio
    async def test_real_create_execution(self):
        """Test real create execution with Claude API."""
        executor = Executor()

        step = create_plan_step(
            action="create",
            file="app/Services/TestService.php",
            description="Create a simple service class with a single method",
        )

        context = create_sample_context()

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=None,
            enable_self_verification=True,
        )

        assert result.success is True
        assert "<?php" in result.content
        assert "namespace" in result.content
        assert "class" in result.content

    @pytest.mark.asyncio
    async def test_real_modify_execution(self):
        """Test real modify execution with Claude API."""
        executor = Executor()

        step = create_plan_step(
            action="modify",
            description="Add a simple getter method called getName()",
        )

        context = create_sample_context()

        result = await executor.execute_step(
            step=step,
            context=context,
            previous_results=[],
            current_file_content=SAMPLE_PHP_CONTROLLER,
            enable_self_verification=True,
        )

        assert result.success is True
        # Original content should be preserved
        assert "index" in result.content
        assert "store" in result.content


# =============================================================================
# CLI Runner
# =============================================================================

async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all executor scenarios and report results."""
    print("\n" + "=" * 70)
    print("Forge (Executor) Agent - Running All Scenarios")
    print("=" * 70)

    results = []
    passed = 0
    failed = 0

    for scenario in EXECUTOR_SCENARIOS:
        print(f"\n[{scenario['name']}] {scenario['description']}...")

        try:
            step_data = scenario["step"]
            step = PlanStep(
                order=step_data["order"],
                action=step_data["action"],
                file=step_data["file"],
                category=step_data["category"],
                description=step_data["description"],
                depends_on=[],
                estimated_lines=50,
            )

            context = create_sample_context()
            expected = scenario["expected"]

            # Create mock
            if step.action == "delete":
                mock_response = json.dumps({
                    "file": step.file, "action": "delete", "content": "", "safe_to_delete": True
                })
                mock_responses = [mock_response]
            else:
                content = scenario.get("current_content") or "<?php class Test {}"
                if step.action == "modify" and scenario.get("current_content"):
                    content = scenario["current_content"] + "\n// Modified"
                mock_responses = [
                    create_reasoning_response(step),
                    create_execution_response(step, content),
                ]

            mock_claude = MagicMock()
            mock_claude.chat_async = AsyncMock(side_effect=mock_responses)

            config = AgentConfig()
            config.REQUIRE_FILE_EXISTS_FOR_MODIFY = True

            executor = Executor(claude_service=mock_claude, config=config)

            result = await executor.execute_step(
                step=step,
                context=context,
                previous_results=[],
                current_file_content=scenario.get("current_content"),
                enable_self_verification=False,
            )

            # Validate
            errors = []
            if "success" in expected and result.success != expected["success"]:
                errors.append(f"success: expected {expected['success']}, got {result.success}")
            if expected.get("has_error") and not result.error:
                errors.append("Expected error but none found")

            if errors:
                print(f"   FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                print(f"   PASSED (action={result.action}, success={result.success})")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "passed": len(errors) == 0,
                "action": result.action,
                "success": result.success,
                "errors": errors,
            })

        except Exception as e:
            print(f"   ERROR: {e}")
            failed += 1
            results.append({
                "scenario": scenario["name"],
                "passed": False,
                "error": str(e),
            })

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {len(EXECUTOR_SCENARIOS)} total")
    print("=" * 70)

    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "Forge (Executor)",
                "summary": {"passed": passed, "failed": failed},
                "results": results,
            }, f, indent=2)
        print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test Forge (Executor) Agent")
    parser.add_argument("--run-all", action="store_true", help="Run all scenarios")
    parser.add_argument("--output", type=str, help="Output file for results")

    args = parser.parse_args()

    if args.run_all:
        asyncio.run(run_all_scenarios(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()