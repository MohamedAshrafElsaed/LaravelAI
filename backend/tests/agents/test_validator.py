"""
Tests for Guardian - Enhanced Validator Agent.

Covers:
- Quick validation checks
- Pattern extraction
- Contradiction detection
- Full validation flow
- Issue categorization
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass

from app.agents.validator import (
    Validator,
    ValidationResult,
    ValidationIssue,
    QuickValidator,
    ContradictionTracker,
    ContradictionInfo,
    ExtractedPatterns,
    IssueCategory,
    categorize_issue,
    generate_issue_signature,
    extract_patterns_from_context,
)
from app.agents.executor import ExecutionResult
from app.agents.context_retriever import RetrievedContext, CodeChunk
from app.agents.intent_analyzer import Intent


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_claude():
    """Create a mock Claude service."""
    mock = MagicMock()
    mock.chat_async = AsyncMock()
    return mock


@pytest.fixture
def validator(mock_claude):
    """Create a validator with mocked Claude service."""
    return Validator(claude_service=mock_claude)


@pytest.fixture
def sample_context():
    """Create a sample RetrievedContext."""
    return RetrievedContext(
        chunks=[
            CodeChunk(
                file_path="app/Services/BaseService.php",
                content="""<?php
declare(strict_types=1);

namespace App\\Services;

use Illuminate\\Support\\Facades\\Log;

abstract class BaseService
{
    protected function logAction(string $action): void
    {
        Log::info($action);
    }
}
""",
                chunk_type="code",
                start_line=1,
                end_line=15,
                score=0.9,
            ),
            CodeChunk(
                file_path="app/Http/Controllers/BaseController.php",
                content="""<?php

namespace App\\Http\\Controllers;

use Illuminate\\Foundation\\Auth\\Access\\AuthorizesRequests;
use Illuminate\\Foundation\\Validation\\ValidatesRequests;
use Illuminate\\Routing\\Controller;

class BaseController extends Controller
{
    use AuthorizesRequests, ValidatesRequests;
}
""",
                chunk_type="code",
                start_line=1,
                end_line=12,
                score=0.85,
            ),
        ],
        confidence_level="high",
    )


@pytest.fixture
def sample_intent():
    """Create a sample Intent."""
    return Intent(
        task_type="feature",
        scope="single_file",
        domains_affected=["users"],
        search_queries=["UserService"],
    )


def create_execution_result(
        file: str = "app/Services/UserService.php",
        action: str = "create",
        content: str = "<?php\nnamespace App\\Services;\n\nclass UserService {}",
        success: bool = True,
        error: str = None,
) -> ExecutionResult:
    """Helper to create ExecutionResult."""
    return ExecutionResult(
        file=file,
        action=action,
        content=content,
        success=success,
        error=error,
    )


def create_validation_response(
        approved: bool = True,
        score: int = 95,
        issues: list = None,
        suggestions: list = None,
        summary: str = "Validation complete",
) -> str:
    """Helper to create mock validation response."""
    return json.dumps({
        "approved": approved,
        "score": score,
        "issues": issues or [],
        "suggestions": suggestions or [],
        "summary": summary,
    })


# =============================================================================
# UNIT TESTS - Issue Categorization
# =============================================================================

class TestIssueCategorization:
    """Tests for issue categorization."""

    def test_categorize_missing_import(self):
        """Test categorization of missing import issues."""
        msg = "Missing use statement: App\\Services\\UserService is not imported"
        assert categorize_issue(msg) == IssueCategory.IMPORT_MISSING

    def test_categorize_unused_import(self):
        """Test categorization of unused import issues."""
        msg = "Unused import: App\\Models\\User is imported but never used"
        assert categorize_issue(msg) == IssueCategory.IMPORT_UNUSED

    def test_categorize_security(self):
        """Test categorization of security issues."""
        msg = "CRITICAL: SQL injection vulnerability detected"
        assert categorize_issue(msg) == IssueCategory.SECURITY

    def test_categorize_type_hint(self):
        """Test categorization of type hint issues."""
        msg = "Missing return type hint on public method"
        assert categorize_issue(msg) == IssueCategory.TYPE_HINT

    def test_categorize_namespace(self):
        """Test categorization of namespace issues."""
        msg = "Wrong namespace: expected App\\Services, got App\\Service"
        assert categorize_issue(msg) == IssueCategory.NAMESPACE

    def test_categorize_other(self):
        """Test categorization of uncategorized issues."""
        msg = "Some random issue that doesn't match patterns"
        assert categorize_issue(msg) == IssueCategory.OTHER


class TestIssueSignature:
    """Tests for issue signature generation."""

    def test_generate_signature_basic(self):
        """Test basic signature generation."""
        sig = generate_issue_signature("app/Services/UserService.php", 10, "import_missing")
        assert len(sig) == 12  # MD5 hash truncated to 12 chars

    def test_same_location_same_signature(self):
        """Test that nearby lines produce same signature."""
        sig1 = generate_issue_signature("app/Services/UserService.php", 10, "import_missing")
        sig2 = generate_issue_signature("app/Services/UserService.php", 12, "import_missing")
        assert sig1 == sig2  # Lines within 5-line bucket

    def test_different_location_different_signature(self):
        """Test that distant lines produce different signatures."""
        sig1 = generate_issue_signature("app/Services/UserService.php", 10, "import_missing")
        sig2 = generate_issue_signature("app/Services/UserService.php", 50, "import_missing")
        assert sig1 != sig2

    def test_path_normalization(self):
        """Test that paths are normalized."""
        sig1 = generate_issue_signature("app/Services/UserService.php", 10, "import_missing")
        sig2 = generate_issue_signature("App\\Services\\UserService.php", 10, "import_missing")
        assert sig1 == sig2


# =============================================================================
# UNIT TESTS - Quick Validator
# =============================================================================

class TestQuickValidator:
    """Tests for QuickValidator."""

    def test_validate_php_valid(self):
        """Test validation of valid PHP content."""
        content = """<?php

namespace App\\Services;

class UserService
{
    public function getUser(): array
    {
        return [];
    }
}
"""
        issues = QuickValidator.validate_php(content, "app/Services/UserService.php")
        assert len(issues) == 0

    def test_validate_php_missing_opening_tag(self):
        """Test detection of missing PHP opening tag."""
        content = "namespace App\\Services;\n\nclass UserService {}"
        issues = QuickValidator.validate_php(content, "app/Services/UserService.php")
        assert any("<?php" in i for i in issues)

    def test_validate_php_missing_namespace(self):
        """Test detection of missing namespace in app files."""
        content = "<?php\n\nclass UserService {}"
        issues = QuickValidator.validate_php(content, "app/Services/UserService.php")
        assert any("namespace" in i for i in issues)

    def test_validate_php_missing_class(self):
        """Test detection of missing class in controller file."""
        content = "<?php\n\nnamespace App\\Http\\Controllers;"
        issues = QuickValidator.validate_php(content, "app/Http/Controllers/UserController.php")
        assert any("class" in i.lower() for i in issues)

    def test_validate_php_unbalanced_braces(self):
        """Test detection of unbalanced braces."""
        content = "<?php\nnamespace App\\Services;\n\nclass UserService {\n    public function test() {"
        issues = QuickValidator.validate_php(content, "app/Services/UserService.php")
        assert any("Unbalanced braces" in i for i in issues)

    def test_validate_blade_valid(self):
        """Test validation of valid Blade template."""
        content = """@extends('layouts.app')

@section('content')
    <div>{{ $user->name }}</div>
@endsection
"""
        issues = QuickValidator.validate_blade(content, "resources/views/user.blade.php")
        assert len(issues) == 0

    def test_validate_blade_unclosed_directive(self):
        """Test detection of unclosed Blade directive."""
        content = """@if($user)
    <div>{{ $user->name }}</div>
"""
        issues = QuickValidator.validate_blade(content, "resources/views/user.blade.php")
        assert any("@if" in i for i in issues)

    def test_validate_blade_unescaped_request(self):
        """Test detection of unescaped request data."""
        content = """{!! $request->input('name') !!}"""
        issues = QuickValidator.validate_blade(content, "resources/views/user.blade.php")
        assert any("Unescaped" in i for i in issues)

    def test_validate_migration_valid(self):
        """Test validation of valid migration."""
        content = """<?php

use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

class CreateUsersTable extends Migration
{
    public function up()
    {
        Schema::create('users', function (Blueprint $table) {
            $table->id();
        });
    }

    public function down()
    {
        Schema::dropIfExists('users');
    }
}
"""
        issues = QuickValidator.validate_migration(content, "database/migrations/create_users.php")
        assert len(issues) == 0

    def test_validate_migration_empty_down(self):
        """Test detection of empty down method."""
        content = """<?php
class CreateUsersTable extends Migration
{
    public function up()
    {
        Schema::create('users', fn($t) => $t->id());
    }

    public function down()
    {
        //
    }
}
"""
        issues = QuickValidator.validate_migration(content, "database/migrations/create_users.php")
        assert any("down()" in i and "empty" in i for i in issues)

    def test_quick_check_execution_result(self):
        """Test quick_check on ExecutionResult."""
        result = create_execution_result(
            content="<?php\nnamespace App\\Services;\n\nclass UserService {}"
        )
        issues = QuickValidator.quick_check(result)
        assert len(issues) == 0

    def test_quick_check_failed_result(self):
        """Test quick_check on failed ExecutionResult."""
        result = create_execution_result(success=False, error="Generation failed")
        issues = QuickValidator.quick_check(result)
        assert any("failed" in i.lower() for i in issues)

    def test_quick_check_empty_content(self):
        """Test quick_check on empty content."""
        result = create_execution_result(content="")
        issues = QuickValidator.quick_check(result)
        assert any("No content" in i for i in issues)


# =============================================================================
# UNIT TESTS - Pattern Extraction
# =============================================================================

class TestPatternExtraction:
    """Tests for pattern extraction from context."""

    def test_extract_strict_types(self, sample_context):
        """Test detection of strict_types declaration."""
        patterns = extract_patterns_from_context(sample_context)
        assert patterns.uses_strict_types is True

    def test_extract_indentation(self, sample_context):
        """Test detection of indentation style."""
        patterns = extract_patterns_from_context(sample_context)
        assert patterns.indentation == "4 spaces"

    def test_extract_common_imports(self, sample_context):
        """Test extraction of common imports."""
        patterns = extract_patterns_from_context(sample_context)
        assert "Illuminate\\Support\\Facades\\Log" in patterns.common_imports

    def test_extract_base_classes(self, sample_context):
        """Test extraction of base classes."""
        patterns = extract_patterns_from_context(sample_context)
        assert "Controller" in patterns.base_classes

    def test_extract_traits(self, sample_context):
        """Test extraction of traits."""
        patterns = extract_patterns_from_context(sample_context)
        assert any("Requests" in t for t in patterns.traits_used)

    def test_to_prompt_string(self, sample_context):
        """Test conversion to prompt string."""
        patterns = extract_patterns_from_context(sample_context)
        prompt_str = patterns.to_prompt_string()
        assert "<detected_codebase_patterns>" in prompt_str
        assert "Strict types: Yes" in prompt_str


# =============================================================================
# UNIT TESTS - Contradiction Tracker
# =============================================================================

class TestContradictionTracker:
    """Tests for contradiction detection."""

    def test_add_result(self):
        """Test adding validation result to tracker."""
        tracker = ContradictionTracker()
        result = ValidationResult(
            approved=False,
            score=60,
            issues=[ValidationIssue(
                severity="error",
                file="test.php",
                message="Missing import",
                line=10,
            )],
        )
        tracker.add_result(result)
        assert len(tracker.history) == 1

    def test_detect_flip_flop(self):
        """Test detection of flip-flopping issues."""
        tracker = ContradictionTracker()

        # First validation - issue present
        result1 = ValidationResult(
            approved=False,
            score=60,
            issues=[ValidationIssue(
                severity="error",
                file="test.php",
                message="Missing import: UserService",
                line=10,
            )],
        )
        tracker.add_result(result1)

        # Second validation - issue fixed (empty)
        result2 = ValidationResult(approved=True, score=95, issues=[])
        tracker.add_result(result2)

        # Third validation - issue back
        result3 = ValidationResult(
            approved=False,
            score=60,
            issues=[ValidationIssue(
                severity="error",
                file="test.php",
                message="Missing import: UserService",
                line=10,
            )],
        )

        contradictions = tracker.detect_contradictions(result3)
        assert len(contradictions) >= 1
        assert contradictions[0].contradiction_type == "flip_flop"

    def test_detect_conflicting_advice(self):
        """Test detection of conflicting advice."""
        tracker = ContradictionTracker()

        # First validation - says to remove something
        result1 = ValidationResult(
            approved=False,
            score=70,
            issues=[ValidationIssue(
                severity="warning",
                file="test.php",
                message="Remove redundant import",
                line=5,
            )],
        )
        tracker.add_result(result1)

        # Second validation - says to add the same thing
        result2 = ValidationResult(
            approved=False,
            score=70,
            issues=[ValidationIssue(
                severity="error",
                file="test.php",
                message="Add missing import",
                line=5,
            )],
        )

        contradictions = tracker.detect_contradictions(result2)
        assert len(contradictions) >= 1
        assert contradictions[0].contradiction_type == "conflicting_advice"

    def test_detect_severity_change(self):
        """Test detection of severity changes on same issue."""
        tracker = ContradictionTracker()

        issue1 = ValidationIssue(
            severity="warning",
            file="test.php",
            message="Missing docblock",
            line=10,
        )
        result1 = ValidationResult(approved=True, score=85, issues=[issue1])
        tracker.add_result(result1)

        # Same issue, different severity
        issue2 = ValidationIssue(
            severity="error",
            file="test.php",
            message="Missing docblock",
            line=10,
        )
        result2 = ValidationResult(approved=False, score=60, issues=[issue2])

        contradictions = tracker.detect_contradictions(result2)
        severity_changes = [c for c in contradictions if c.contradiction_type == "severity_change"]
        assert len(severity_changes) >= 1

    def test_clear_history(self):
        """Test clearing tracker history."""
        tracker = ContradictionTracker()
        result = ValidationResult(approved=True, score=95, issues=[])
        tracker.add_result(result)

        tracker.clear()
        assert len(tracker.history) == 0
        assert len(tracker.issue_occurrences) == 0


# =============================================================================
# UNIT TESTS - ValidationIssue
# =============================================================================

class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_create_with_auto_category(self):
        """Test automatic category assignment."""
        issue = ValidationIssue(
            severity="error",
            file="test.php",
            message="Missing use statement: App\\Services\\UserService",
            line=10,
        )
        assert issue.category == IssueCategory.IMPORT_MISSING.value

    def test_create_with_auto_signature(self):
        """Test automatic signature generation."""
        issue = ValidationIssue(
            severity="error",
            file="test.php",
            message="Missing import",
            line=10,
        )
        assert issue.signature is not None
        assert len(issue.signature) == 12

    def test_to_dict(self):
        """Test conversion to dictionary."""
        issue = ValidationIssue(
            severity="error",
            file="test.php",
            message="Test message",
            line=10,
        )
        d = issue.to_dict()
        assert d["severity"] == "error"
        assert d["file"] == "test.php"
        assert d["line"] == 10
        # Category and signature not included in dict (internal use)
        assert "category" not in d

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "severity": "warning",
            "file": "app/test.php",
            "message": "Test warning",
            "line": 25,
        }
        issue = ValidationIssue.from_dict(data)
        assert issue.severity == "warning"
        assert issue.file == "app/test.php"
        assert issue.line == 25

    def test_from_dict_invalid(self):
        """Test creation from invalid data."""
        issue = ValidationIssue.from_dict("just a string")
        assert issue.severity == "info"
        assert issue.message == "just a string"


# =============================================================================
# UNIT TESTS - ValidationResult
# =============================================================================

class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_errors_property(self):
        """Test errors property filters correctly."""
        result = ValidationResult(
            approved=False,
            score=50,
            issues=[
                ValidationIssue(severity="error", file="a.php", message="Error 1"),
                ValidationIssue(severity="warning", file="b.php", message="Warning 1"),
                ValidationIssue(severity="error", file="c.php", message="Error 2"),
            ],
        )
        assert len(result.errors) == 2
        assert all(e.severity == "error" for e in result.errors)

    def test_warnings_property(self):
        """Test warnings property filters correctly."""
        result = ValidationResult(
            approved=True,
            score=85,
            issues=[
                ValidationIssue(severity="warning", file="a.php", message="Warning 1"),
                ValidationIssue(severity="info", file="b.php", message="Info 1"),
            ],
        )
        assert len(result.warnings) == 1

    def test_get_issue_signatures(self):
        """Test getting all issue signatures."""
        result = ValidationResult(
            approved=False,
            score=60,
            issues=[
                ValidationIssue(severity="error", file="a.php", message="Error 1", line=10),
                ValidationIssue(severity="error", file="b.php", message="Error 2", line=20),
            ],
        )
        sigs = result.get_issue_signatures()
        assert len(sigs) == 2

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ValidationResult(
            approved=True,
            score=95,
            issues=[],
            suggestions=["Consider adding tests"],
            summary="All good",
        )
        d = result.to_dict()
        assert d["approved"] is True
        assert d["score"] == 95
        assert "Consider adding tests" in d["suggestions"]

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "approved": False,
            "score": 70,
            "issues": [
                {"severity": "error", "file": "test.php", "message": "Error", "line": 1}
            ],
            "suggestions": [],
            "summary": "Has issues",
        }
        result = ValidationResult.from_dict(data)
        assert result.approved is False
        assert result.score == 70
        assert len(result.issues) == 1


# =============================================================================
# INTEGRATION TESTS - Validator
# =============================================================================

class TestValidatorIntegration:
    """Integration tests for the full Validator."""

    @pytest.mark.asyncio
    async def test_validate_success(self, validator, mock_claude, sample_context, sample_intent):
        """Test successful validation flow."""
        mock_claude.chat_async.return_value = create_validation_response(
            approved=True,
            score=95,
            issues=[],
            summary="Excellent code quality",
        )

        result = create_execution_result(
            content="<?php\nnamespace App\\Services;\n\nclass UserService {\n    public function getUser(): array\n    {\n        return [];\n    }\n}"
        )

        validation = await validator.validate(
            user_input="Create a UserService",
            intent=sample_intent,
            results=[result],
            context=sample_context,
        )

        assert validation.approved is True
        assert validation.score == 95
        assert len(validation.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_with_errors(self, validator, mock_claude, sample_context, sample_intent):
        """Test validation with errors."""
        mock_claude.chat_async.return_value = create_validation_response(
            approved=False,
            score=55,
            issues=[
                {
                    "severity": "error",
                    "file": "app/Services/UserService.php",
                    "line": 5,
                    "message": "Missing use statement: App\\Models\\User",
                }
            ],
            summary="Has errors",
        )

        result = create_execution_result()

        validation = await validator.validate(
            user_input="Create a UserService",
            intent=sample_intent,
            results=[result],
            context=sample_context,
        )

        assert validation.approved is False
        assert validation.score == 55
        assert len(validation.errors) == 1

    @pytest.mark.asyncio
    async def test_quick_check_blocks_validation(self, validator, sample_context, sample_intent):
        """Test that quick check failures block full validation."""
        # Create result with unbalanced braces (quick check will fail)
        result = create_execution_result(
            content="<?php\nnamespace App\\Services;\n\nclass UserService {\n    public function test() {"
        )

        validation = await validator.validate(
            user_input="Create a UserService",
            intent=sample_intent,
            results=[result],
            context=sample_context,
        )

        assert validation.approved is False
        assert validation.score <= 30
        assert any("Unbalanced" in i.message for i in validation.issues)

    @pytest.mark.asyncio
    async def test_validate_single(self, validator, mock_claude, sample_context):
        """Test single file validation."""
        mock_claude.chat_async.return_value = create_validation_response(
            approved=True,
            score=90,
        )

        result = create_execution_result(
            content="<?php\nnamespace App\\Services;\n\nclass TestService {}"
        )

        validation = await validator.validate_single(result, sample_context)
        assert validation is not None

    @pytest.mark.asyncio
    async def test_clear_history(self, validator, mock_claude, sample_context, sample_intent):
        """Test clearing validation history."""
        mock_claude.chat_async.return_value = create_validation_response()

        result = create_execution_result()
        await validator.validate("test", sample_intent, [result], sample_context)

        assert len(validator.validation_history) == 1

        validator.clear_history()
        assert len(validator.validation_history) == 0

    @pytest.mark.asyncio
    async def test_response_with_reasoning(self, validator, mock_claude, sample_context, sample_intent):
        """Test parsing response with reasoning tags."""
        response_with_reasoning = """<reasoning>
Step 1: The code implements a UserService.
Step 2: All imports are present.
Step 3: No security issues found.
</reasoning>

{
    "approved": true,
    "score": 92,
    "issues": [],
    "suggestions": ["Consider adding unit tests"],
    "summary": "Good implementation"
}"""

        mock_claude.chat_async.return_value = response_with_reasoning

        result = create_execution_result()

        validation = await validator.validate(
            user_input="Create a UserService",
            intent=sample_intent,
            results=[result],
            context=sample_context,
        )

        assert validation.approved is True
        assert validation.reasoning != ""
        assert "Step 1" in validation.reasoning

    @pytest.mark.asyncio
    async def test_json_parse_error_handling(self, validator, mock_claude, sample_context, sample_intent):
        """Test handling of JSON parse errors."""
        mock_claude.chat_async.return_value = "not valid json {{{{"

        result = create_execution_result()

        validation = await validator.validate(
            user_input="Create a UserService",
            intent=sample_intent,
            results=[result],
            context=sample_context,
        )

        assert validation.approved is False
        assert validation.score == 0
        assert any("parse" in i.message.lower() for i in validation.issues)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_context_pattern_extraction(self):
        """Test pattern extraction with empty context."""
        context = RetrievedContext(chunks=[], confidence_level="low")
        patterns = extract_patterns_from_context(context)
        assert patterns.uses_strict_types is False
        assert patterns.common_imports == []

    def test_validation_issue_from_string(self):
        """Test ValidationIssue creation from plain string."""
        issue = ValidationIssue.from_dict("Plain error message")
        assert issue.message == "Plain error message"
        assert issue.severity == "info"

    def test_validation_result_from_string(self):
        """Test ValidationResult creation from plain string."""
        result = ValidationResult.from_dict("Error occurred")
        assert result.summary == "Error occurred"
        assert result.approved is False

    def test_quick_validator_delete_action(self):
        """Test quick validator skips delete actions."""
        result = ExecutionResult(file="test.php", action="delete", content="")
        issues = QuickValidator.quick_check(result)
        assert len(issues) == 0

    def test_contradiction_tracker_empty_history(self):
        """Test contradiction detection with empty history."""
        tracker = ContradictionTracker()
        result = ValidationResult(approved=True, score=95, issues=[])
        contradictions = tracker.detect_contradictions(result)
        assert len(contradictions) == 0


# =============================================================================
# PARAMETRIZED TESTS
# =============================================================================

class TestParametrized:
    """Parametrized tests for comprehensive coverage."""

    @pytest.mark.parametrize("message,expected_category", [
        ("Missing use statement for UserService", IssueCategory.IMPORT_MISSING),
        ("Unused import detected", IssueCategory.IMPORT_UNUSED),
        ("SQL injection vulnerability", IssueCategory.SECURITY),
        ("Missing return type hint", IssueCategory.TYPE_HINT),
        ("Wrong namespace declaration", IssueCategory.NAMESPACE),
        ("Random unmatched message", IssueCategory.OTHER),
    ])
    def test_categorize_various_messages(self, message, expected_category):
        """Test categorization of various issue messages."""
        assert categorize_issue(message) == expected_category

    @pytest.mark.parametrize("file,expected_validator", [
        ("app/Services/UserService.php", "php"),
        ("resources/views/user.blade.php", "blade"),
        ("database/migrations/2024_create_users.php", "migration"),
        ("routes/web.php", "route"),
    ])
    def test_quick_check_selects_correct_validator(self, file, expected_validator):
        """Test that quick_check selects the appropriate validator."""
        # This is more of a smoke test - the actual content would determine issues
        result = ExecutionResult(
            file=file,
            action="create",
            content="<?php\nnamespace App;\nclass Test {}",
            success=True,
        )
        # Should not raise
        QuickValidator.quick_check(result)