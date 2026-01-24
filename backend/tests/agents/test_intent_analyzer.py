"""
Nova (Intent Analyzer) Agent - Comprehensive Test Suite

Run with:
    # Unit tests (mocked, fast)
    pytest backend/tests/agents/test_intent_analyzer.py -v

    # Integration tests (real API, slow)
    pytest backend/tests/agents/test_intent_analyzer.py -v -m integration

    # Manual interactive testing
    python backend/tests/agents/test_intent_analyzer.py --interactive

    # Run all test scenarios and save results
    python backend/tests/agents/test_intent_analyzer.py --run-all --output results.json
"""
import pytest
import asyncio
import json
import sys
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.intent_analyzer import (
    IntentAnalyzer,
    Intent,
    analyze_intent,
    MAX_RETRIES,
    CONFIDENCE_THRESHOLD_FOR_CLARIFICATION,
)
from app.agents.intent_schema import (
    IntentOutput,
    ExtractedEntities,
    TaskType,
    Scope,
    Priority,
    LARAVEL_DOMAINS,
)
from app.agents.conversation_summary import (
    ConversationSummary,
    RecentMessage,
    format_recent_messages,
)


# =============================================================================
# Test Fixtures and Sample Data
# =============================================================================

SAMPLE_PROJECT_CONTEXT = """### Technology Stack
- **Backend:** Laravel 11.x (PHP 8.3)
- **Database:** mysql
- **Auth:** sanctum + spatie/laravel-permission

### Database Models
Available models: User, Order, Product, Category, Payment

### Codebase Statistics
- **Total Files:** 150
- **Controllers:** UserController, OrderController, ProductController, Api/V1/OrderController
- **Models:** User, Order, Product, Category, Payment

### Architecture Patterns
- Service Layer pattern
- Repository pattern for complex queries
"""

SAMPLE_CONVERSATION_SUMMARY = ConversationSummary(
    project_name="E-commerce API",
    project_id="test-123",
    decisions=["Use service pattern for business logic", "Add soft deletes to Order model"],
    completed_tasks=["Created Order model", "Added order migration"],
    pending_tasks=["Add order export feature"],
    known_files=["app/Models/Order.php", "app/Http/Controllers/OrderController.php"],
    known_classes=["Order", "OrderController", "OrderService"],
    known_tables=["orders", "order_items"],
)

SAMPLE_RECENT_MESSAGES = [
    RecentMessage(role="user", content="Let's work on the order system"),
    RecentMessage(role="assistant", content="I'll help you with the order system. What would you like to do?"),
    RecentMessage(role="user", content="First, let's create the export feature"),
]


# =============================================================================
# Test Scenarios - Comprehensive Coverage
# =============================================================================

TEST_SCENARIOS = [
    # === FEATURE REQUESTS ===
    {
        "name": "feature_simple",
        "description": "Simple feature request",
        "input": "Add a user profile page",
        "expected": {
            "task_type": "feature",
            "priority": "medium",
            "needs_clarification": False,
            "domains_should_contain": ["controllers", "views"],
        },
    },
    {
        "name": "feature_with_entities",
        "description": "Feature request with explicit entities",
        "input": "Add an export method to the OrderController that generates PDF reports",
        "expected": {
            "task_type": "feature",
            "priority": "medium",
            "needs_clarification": False,
            "entities_should_contain": {
                "classes": ["OrderController"],
                "methods": ["export"],
            },
        },
    },
    {
        "name": "feature_database",
        "description": "Feature requiring migration",
        "input": "Add a new 'notes' field to the users table",
        "expected": {
            "task_type": "feature",
            "requires_migration": True,
            "domains_should_contain": ["database", "models"],
        },
    },
    {
        "name": "feature_api",
        "description": "API endpoint feature",
        "input": "Create a REST API endpoint for /api/products with full CRUD operations",
        "expected": {
            "task_type": "feature",
            "domains_should_contain": ["api", "controllers", "routing"],
            "entities_should_contain": {
                "routes": ["/api/products"],
            },
        },
    },

    # === BUGFIX REQUESTS ===
    {
        "name": "bugfix_auth",
        "description": "Authentication bug",
        "input": "The login form shows 'invalid credentials' even when I enter the correct password",
        "expected": {
            "task_type": "bugfix",
            "priority": "high",
            "needs_clarification": False,
            "domains_should_contain": ["auth"],
        },
    },
    {
        "name": "bugfix_critical",
        "description": "Critical production bug",
        "input": "URGENT: Stripe webhooks are failing and payments aren't being processed",
        "expected": {
            "task_type": "bugfix",
            "priority": "critical",
            "needs_clarification": False,
        },
    },
    {
        "name": "bugfix_validation",
        "description": "Validation bug",
        "input": "The email validation is not working - users can submit invalid emails",
        "expected": {
            "task_type": "bugfix",
            "domains_should_contain": ["validation"],
        },
    },

    # === REFACTOR REQUESTS ===
    {
        "name": "refactor_performance",
        "description": "Performance optimization",
        "input": "Optimize the product listing query - it's too slow with 10k products",
        "expected": {
            "task_type": "refactor",
            "domains_should_contain": ["database", "models"],
        },
    },
    {
        "name": "refactor_code_quality",
        "description": "Code quality improvement",
        "input": "Refactor the UserController to use the service pattern",
        "expected": {
            "task_type": "refactor",
            "entities_should_contain": {
                "classes": ["UserController"],
            },
        },
    },

    # === QUESTION REQUESTS ===
    {
        "name": "question_how",
        "description": "How-to question",
        "input": "How does Laravel handle database transactions?",
        "expected": {
            "task_type": "question",
            "priority": "low",
            "needs_clarification": False,
        },
    },
    {
        "name": "question_explain",
        "description": "Explanation request",
        "input": "Explain how the Order model relationships work",
        "expected": {
            "task_type": "question",
            "entities_should_contain": {
                "classes": ["Order"],
            },
        },
    },

    # === CLARIFICATION NEEDED ===
    {
        "name": "ambiguous_endpoint",
        "description": "Ambiguous API request",
        "input": "Add the API endpoint",
        "expected": {
            "needs_clarification": True,
            "min_clarifying_questions": 1,
        },
    },
    {
        "name": "ambiguous_fix",
        "description": "Vague fix request",
        "input": "Fix the bug",
        "expected": {
            "needs_clarification": True,
            "min_clarifying_questions": 1,
        },
    },
    {
        "name": "ambiguous_reference",
        "description": "Reference to unknown context",
        "input": "Continue working on that feature we discussed",
        "expected": {
            "needs_clarification": True,
        },
        "use_empty_context": True,
    },

    # === EDGE CASES ===
    {
        "name": "edge_empty_input",
        "description": "Empty input handling",
        "input": "",
        "expected": {
            "needs_clarification": True,
        },
    },
    {
        "name": "edge_very_long_input",
        "description": "Very long repetitive input (may need clarification)",
        "input": "I need to create a comprehensive user management system that includes " * 20,
        "expected": {
            "task_type": "feature",
            # May or may not need clarification - repetitive input is ambiguous
        },
    },
    {
        "name": "edge_special_characters",
        "description": "Input with special characters",
        "input": "Add validation for email@domain.com format in the User model's $fillable array",
        "expected": {
            "task_type": "feature",
            "domains_should_contain": ["validation", "models"],
        },
    },

    # === CONTEXT-DEPENDENT ===
    {
        "name": "context_continuation",
        "description": "Continuation from conversation",
        "input": "Now add pagination to it",
        "expected": {
            "task_type": "feature",
        },
        "use_conversation_context": True,
    },
    {
        "name": "context_with_history",
        "description": "Request with conversation history",
        "input": "Actually, let's do both caching and pagination",
        "expected": {
            "task_type": "feature",
            "domains_should_contain": ["cache"],
        },
        "use_conversation_context": True,
        "recent_messages": [
            RecentMessage(role="user", content="The order list is loading slowly"),
            RecentMessage(role="assistant", content="I can add pagination or caching. Which would you prefer?"),
        ],
    },

    # === PRIORITY DETECTION ===
    {
        "name": "priority_critical_security",
        "description": "Security vulnerability",
        "input": "SECURITY: Found SQL injection vulnerability in the search endpoint",
        "expected": {
            "task_type": "bugfix",
            "priority": "critical",
        },
    },
    {
        "name": "priority_high_customer",
        "description": "Customer-facing issue (checkout = payments = critical)",
        "input": "Customers are complaining that checkout is failing intermittently",
        "expected": {
            "task_type": "bugfix",
            "priority_in": ["high", "critical"],  # Checkout issues can be high or critical
        },
    },
    {
        "name": "priority_low_docs",
        "description": "Documentation update",
        "input": "Update the README with the new API endpoints",
        "expected": {
            "priority": "low",
        },
    },

    # === MULTI-DOMAIN ===
    {
        "name": "multi_domain_full_feature",
        "description": "Full feature spanning multiple domains",
        "input": "Implement a complete order notification system with email, queue jobs, and database logging",
        "expected": {
            "task_type": "feature",
            "scope": "cross_domain",
            "domains_should_contain": ["mail", "queue", "database"],
        },
    },
]


# =============================================================================
# Mock Responses for Unit Tests
# =============================================================================

def create_mock_response(scenario: dict) -> str:
    """Create a mock Claude response for a test scenario."""
    expected = scenario.get("expected", {})

    response = {
        "task_type": expected.get("task_type", "feature"),
        "task_type_confidence": 0.9,
        "domains_affected": expected.get("domains_should_contain", ["controllers"]),
        "scope": expected.get("scope", "single_file"),
        "languages": ["php"],
        "requires_migration": expected.get("requires_migration", False),
        "priority": expected.get("priority", "medium"),
        "entities": {
            "files": expected.get("entities_should_contain", {}).get("files", []),
            "classes": expected.get("entities_should_contain", {}).get("classes", []),
            "methods": expected.get("entities_should_contain", {}).get("methods", []),
            "routes": expected.get("entities_should_contain", {}).get("routes", []),
            "tables": expected.get("entities_should_contain", {}).get("tables", []),
        },
        "search_queries": ["test query 1", "test query 2"],
        "reasoning": "Test reasoning for scenario",
        "overall_confidence": 0.3 if expected.get("needs_clarification") else 0.85,
        "needs_clarification": expected.get("needs_clarification", False),
        "clarifying_questions": ["What would you like to do?"] if expected.get("needs_clarification") else [],
    }

    return json.dumps(response)


# =============================================================================
# Unit Tests (Mocked)
# =============================================================================

class TestIntentAnalyzerUnit:
    """Unit tests with mocked Claude service."""

    @pytest.fixture
    def mock_claude_service(self):
        """Create a mock Claude service."""
        mock = MagicMock()
        mock.chat_async = AsyncMock(return_value='{"task_type": "feature", "task_type_confidence": 0.9, "domains_affected": ["controllers"], "scope": "single_file", "languages": ["php"], "requires_migration": false, "priority": "medium", "entities": {"files": [], "classes": [], "methods": [], "routes": [], "tables": []}, "search_queries": ["test"], "reasoning": "Test", "overall_confidence": 0.9, "needs_clarification": false, "clarifying_questions": []}')
        return mock

    @pytest.fixture
    def analyzer(self, mock_claude_service):
        """Create analyzer with mocked service."""
        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mock_claude_service):
            return IntentAnalyzer(claude_service=mock_claude_service)

    @pytest.mark.asyncio
    async def test_basic_analysis(self, analyzer, mock_claude_service):
        """Test basic intent analysis."""
        intent = await analyzer.analyze("Add a new feature")

        assert intent is not None
        assert intent.task_type == "feature"
        assert intent.analysis_time_ms >= 0
        mock_claude_service.chat_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_project_context(self, analyzer, mock_claude_service):
        """Test analysis with project context."""
        intent = await analyzer.analyze(
            "Add export feature",
            project_context=SAMPLE_PROJECT_CONTEXT,
        )

        assert intent is not None
        # Verify project context was included in the call
        call_args = mock_claude_service.chat_async.call_args
        messages = call_args.kwargs.get('messages', call_args.args[0] if call_args.args else [])
        assert any("Laravel 11.x" in str(m) for m in messages)

    @pytest.mark.asyncio
    async def test_with_conversation_summary(self, analyzer, mock_claude_service):
        """Test analysis with conversation summary."""
        intent = await analyzer.analyze(
            "Continue with the export",
            conversation_summary=SAMPLE_CONVERSATION_SUMMARY,
        )

        assert intent is not None
        call_args = mock_claude_service.chat_async.call_args
        messages = call_args.kwargs.get('messages', call_args.args[0] if call_args.args else [])
        assert any("E-commerce API" in str(m) for m in messages)

    @pytest.mark.asyncio
    async def test_with_recent_messages(self, analyzer, mock_claude_service):
        """Test analysis with recent messages."""
        intent = await analyzer.analyze(
            "Let's do that",
            recent_messages=SAMPLE_RECENT_MESSAGES,
        )

        assert intent is not None
        call_args = mock_claude_service.chat_async.call_args
        messages = call_args.kwargs.get('messages', call_args.args[0] if call_args.args else [])
        assert any("order system" in str(m).lower() for m in messages)

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_claude_service):
        """Test retry mechanism on API failure."""
        # Fail twice, succeed on third
        mock_claude_service.chat_async = AsyncMock(side_effect=[
            Exception("API Error 1"),
            Exception("API Error 2"),
            '{"task_type": "feature", "task_type_confidence": 0.9, "domains_affected": [], "scope": "single_file", "languages": ["php"], "requires_migration": false, "priority": "medium", "entities": {"files": [], "classes": [], "methods": [], "routes": [], "tables": []}, "search_queries": [], "reasoning": "Test", "overall_confidence": 0.9, "needs_clarification": false, "clarifying_questions": []}',
        ])

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mock_claude_service):
            analyzer = IntentAnalyzer(claude_service=mock_claude_service)
            intent = await analyzer.analyze("Test input")

        assert intent is not None
        assert intent.retry_count == 2
        assert mock_claude_service.chat_async.call_count == 3

    @pytest.mark.asyncio
    async def test_error_fallback(self, mock_claude_service):
        """Test error fallback when all retries fail."""
        mock_claude_service.chat_async = AsyncMock(side_effect=Exception("Persistent error"))

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mock_claude_service):
            analyzer = IntentAnalyzer(claude_service=mock_claude_service)
            intent = await analyzer.analyze("Test input")

        assert intent is not None
        assert intent.needs_clarification is True
        assert "error" in intent.reasoning.lower()
        assert intent.should_halt_pipeline() is True

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, mock_claude_service):
        """Test handling of invalid JSON response."""
        mock_claude_service.chat_async = AsyncMock(return_value="This is not JSON")

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mock_claude_service):
            analyzer = IntentAnalyzer(claude_service=mock_claude_service)
            intent = await analyzer.analyze("Test input")

        # Should fall back to error state
        assert intent.needs_clarification is True

    @pytest.mark.asyncio
    async def test_markdown_wrapped_json(self, mock_claude_service):
        """Test handling of JSON wrapped in markdown code blocks."""
        mock_claude_service.chat_async = AsyncMock(return_value='''```json
{"task_type": "feature", "task_type_confidence": 0.9, "domains_affected": ["api"], "scope": "single_file", "languages": ["php"], "requires_migration": false, "priority": "medium", "entities": {"files": [], "classes": [], "methods": [], "routes": [], "tables": []}, "search_queries": ["test"], "reasoning": "Test", "overall_confidence": 0.9, "needs_clarification": false, "clarifying_questions": []}
```''')

        with patch('app.agents.intent_analyzer.get_claude_service', return_value=mock_claude_service):
            analyzer = IntentAnalyzer(claude_service=mock_claude_service)
            intent = await analyzer.analyze("Test input")

        assert intent.task_type == "feature"
        assert "api" in intent.domains_affected


class TestIntentDataclass:
    """Test Intent dataclass methods."""

    def test_from_output(self):
        """Test creating Intent from IntentOutput."""
        output = IntentOutput(
            task_type=TaskType.FEATURE,
            task_type_confidence=0.9,
            domains_affected=["controllers", "models"],
            scope=Scope.FEATURE,
            languages=["php", "blade"],
            requires_migration=True,
            priority=Priority.HIGH,
            entities=ExtractedEntities(classes=["UserController"]),
            search_queries=["UserController", "user feature"],
            reasoning="Test reasoning",
            overall_confidence=0.85,
            needs_clarification=False,
            clarifying_questions=[],
        )

        intent = Intent.from_output(output, analysis_time_ms=100, retry_count=1)

        assert intent.task_type == "feature"
        assert intent.task_type_confidence == 0.9
        assert "controllers" in intent.domains_affected
        assert intent.requires_migration is True
        assert intent.analysis_time_ms == 100
        assert intent.retry_count == 1

    def test_clarification_required(self):
        """Test creating clarification intent."""
        intent = Intent.clarification_required(
            questions=["What feature?", "Which module?"],
            reasoning="Request is too vague",
        )

        assert intent.needs_clarification is True
        assert len(intent.clarifying_questions) == 2
        assert intent.should_halt_pipeline() is True
        assert intent.overall_confidence < CONFIDENCE_THRESHOLD_FOR_CLARIFICATION

    def test_error_fallback(self):
        """Test creating error fallback intent."""
        intent = Intent.error_fallback("Connection timeout")

        assert intent.needs_clarification is True
        assert "timeout" in intent.reasoning.lower()
        assert intent.should_halt_pipeline() is True

    def test_should_halt_pipeline(self):
        """Test pipeline halt conditions."""
        # Should halt on clarification needed
        intent1 = Intent(task_type="feature", task_type_confidence=0.9, needs_clarification=True)
        assert intent1.should_halt_pipeline() is True

        # Should halt on low confidence
        intent2 = Intent(task_type="feature", task_type_confidence=0.9, overall_confidence=0.3)
        assert intent2.should_halt_pipeline() is True

        # Should NOT halt on good confidence and no clarification
        intent3 = Intent(task_type="feature", task_type_confidence=0.9, overall_confidence=0.8)
        assert intent3.should_halt_pipeline() is False

    def test_to_dict(self):
        """Test serialization to dictionary."""
        intent = Intent(
            task_type="bugfix",
            task_type_confidence=0.95,
            priority="critical",
            domains_affected=["auth"],
        )

        data = intent.to_dict()

        assert data["task_type"] == "bugfix"
        assert data["priority"] == "critical"
        assert isinstance(data["domains_affected"], list)


class TestConversationSummary:
    """Test ConversationSummary functionality."""

    def test_to_prompt_text(self):
        """Test converting summary to prompt text."""
        summary = SAMPLE_CONVERSATION_SUMMARY
        text = summary.to_prompt_text()

        assert "<conversation_context>" in text
        assert "E-commerce API" in text
        assert "Order model" in text
        assert "</conversation_context>" in text

    def test_update_after_execution(self):
        """Test updating summary after task completion."""
        summary = ConversationSummary(project_name="Test")

        summary.update_after_execution(
            task_completed="Added user export feature",
            files_modified=["app/Http/Controllers/UserController.php"],
            new_decisions=["Use CSV format for exports"],
            new_entities={"classes": ["ExportService"], "methods": ["export"]},
        )

        assert "Added user export feature" in summary.completed_tasks
        assert "app/Http/Controllers/UserController.php" in summary.known_files
        assert "Use CSV format for exports" in summary.decisions
        assert "ExportService" in summary.known_classes
        assert summary.update_count == 1
        assert summary.last_updated is not None

    def test_trim_old_entries(self):
        """Test that old entries are trimmed."""
        summary = ConversationSummary()

        # Add many tasks
        for i in range(20):
            summary.completed_tasks.append(f"Task {i}")

        summary._trim_old_entries(max_items=10)

        assert len(summary.completed_tasks) == 10
        assert "Task 19" in summary.completed_tasks  # Most recent kept

    def test_serialization(self):
        """Test JSON serialization/deserialization."""
        summary = SAMPLE_CONVERSATION_SUMMARY

        json_str = summary.to_json()
        restored = ConversationSummary.from_json(json_str)

        assert restored.project_name == summary.project_name
        assert restored.decisions == summary.decisions
        assert restored.known_files == summary.known_files

    def test_from_dict_ignores_unknown_fields(self):
        """Test that from_dict handles extra fields gracefully."""
        data = {
            "project_name": "Test",
            "unknown_field": "should be ignored",
            "another_unknown": 123,
        }

        summary = ConversationSummary.from_dict(data)
        assert summary.project_name == "Test"


class TestRecentMessages:
    """Test RecentMessage functionality."""

    def test_format_recent_messages(self):
        """Test formatting recent messages."""
        formatted = format_recent_messages(SAMPLE_RECENT_MESSAGES)

        assert "<recent_messages>" in formatted
        assert "[USER]:" in formatted
        assert "[ASSISTANT]:" in formatted
        assert "order system" in formatted

    def test_format_empty_messages(self):
        """Test formatting empty message list."""
        formatted = format_recent_messages([])

        assert "No recent messages" in formatted

    def test_format_max_messages(self):
        """Test that max_messages limit is respected."""
        messages = [RecentMessage(role="user", content=f"Message {i}") for i in range(10)]

        formatted = format_recent_messages(messages, max_messages=3)

        # Should only contain last 3 messages
        assert "Message 7" in formatted
        assert "Message 8" in formatted
        assert "Message 9" in formatted
        assert "Message 0" not in formatted


# =============================================================================
# Integration Tests (Real API)
# =============================================================================

@pytest.mark.integration
class TestIntentAnalyzerIntegration:
    """Integration tests with real Claude API."""

    @pytest.fixture
    def analyzer(self):
        """Create real analyzer instance."""
        return IntentAnalyzer()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", TEST_SCENARIOS, ids=[s["name"] for s in TEST_SCENARIOS])
    async def test_scenario(self, analyzer, scenario):
        """Test each scenario against real API."""
        # Build context based on scenario options
        project_context = None if scenario.get("use_empty_context") else SAMPLE_PROJECT_CONTEXT
        conversation_summary = SAMPLE_CONVERSATION_SUMMARY if scenario.get("use_conversation_context") else None
        recent_messages = scenario.get("recent_messages", SAMPLE_RECENT_MESSAGES if scenario.get("use_conversation_context") else None)

        intent = await analyzer.analyze(
            user_input=scenario["input"],
            project_context=project_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages,
        )

        # Validate expected outcomes
        expected = scenario["expected"]

        if "task_type" in expected:
            assert intent.task_type == expected["task_type"], f"Expected task_type={expected['task_type']}, got {intent.task_type}"

        if "priority" in expected:
            assert intent.priority == expected["priority"], f"Expected priority={expected['priority']}, got {intent.priority}"

        if "priority_in" in expected:
            assert intent.priority in expected["priority_in"], f"Expected priority in {expected['priority_in']}, got {intent.priority}"

        if "needs_clarification" in expected:
            assert intent.needs_clarification == expected["needs_clarification"], f"Expected needs_clarification={expected['needs_clarification']}, got {intent.needs_clarification}"

        if "requires_migration" in expected:
            assert intent.requires_migration == expected["requires_migration"]

        if "scope" in expected:
            assert intent.scope == expected["scope"]

        if "domains_should_contain" in expected:
            for domain in expected["domains_should_contain"]:
                assert domain in intent.domains_affected, f"Expected domain '{domain}' in {intent.domains_affected}"

        if "entities_should_contain" in expected:
            for entity_type, values in expected["entities_should_contain"].items():
                for value in values:
                    assert value in intent.entities.get(entity_type, []), f"Expected '{value}' in entities.{entity_type}"

        if "min_clarifying_questions" in expected:
            assert len(intent.clarifying_questions) >= expected["min_clarifying_questions"]


# =============================================================================
# Interactive CLI Testing
# =============================================================================

async def run_interactive_test():
    """Run interactive testing mode."""
    print("\n" + "=" * 60)
    print("Nova (Intent Analyzer) - Interactive Test Mode")
    print("=" * 60)
    print("\nType your requests to test Nova's intent analysis.")
    print("Commands: 'quit' to exit, 'context on/off' to toggle context\n")

    analyzer = IntentAnalyzer()
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

            print("\n[Nova]: Analyzing...")

            intent = await analyzer.analyze(
                user_input=user_input,
                project_context=SAMPLE_PROJECT_CONTEXT if use_context else None,
                conversation_summary=SAMPLE_CONVERSATION_SUMMARY if use_context else None,
            )

            # Display results
            print("\n" + "-" * 40)
            print(f"Task Type:      {intent.task_type} (confidence: {intent.task_type_confidence:.2f})")
            print(f"Priority:       {intent.priority}")
            print(f"Scope:          {intent.scope}")
            print(f"Domains:        {', '.join(intent.domains_affected)}")
            print(f"Migration:      {'Yes' if intent.requires_migration else 'No'}")
            print(f"Confidence:     {intent.overall_confidence:.2f}")
            print(f"Analysis Time:  {intent.analysis_time_ms}ms")

            if intent.entities.get("classes") or intent.entities.get("files"):
                print(f"\nEntities:")
                if intent.entities.get("files"):
                    print(f"  Files:   {', '.join(intent.entities['files'])}")
                if intent.entities.get("classes"):
                    print(f"  Classes: {', '.join(intent.entities['classes'])}")
                if intent.entities.get("methods"):
                    print(f"  Methods: {', '.join(intent.entities['methods'])}")
                if intent.entities.get("routes"):
                    print(f"  Routes:  {', '.join(intent.entities['routes'])}")
                if intent.entities.get("tables"):
                    print(f"  Tables:  {', '.join(intent.entities['tables'])}")

            print(f"\nSearch Queries: {', '.join(intent.search_queries[:3])}")
            print(f"\nReasoning: {intent.reasoning}")

            if intent.needs_clarification:
                print(f"\n⚠️  CLARIFICATION NEEDED:")
                for q in intent.clarifying_questions:
                    print(f"   • {q}")

            if intent.should_halt_pipeline():
                print(f"\n🛑 Pipeline would HALT")
            else:
                print(f"\n✅ Pipeline would PROCEED")

            print("-" * 40)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


async def run_all_scenarios(output_file: Optional[str] = None):
    """Run all test scenarios and optionally save results."""
    print("\n" + "=" * 60)
    print("Nova (Intent Analyzer) - Running All Test Scenarios")
    print("=" * 60)

    analyzer = IntentAnalyzer()
    results = []
    passed = 0
    failed = 0

    for scenario in TEST_SCENARIOS:
        print(f"\n[{scenario['name']}] {scenario['description']}...")

        try:
            # Build context
            project_context = None if scenario.get("use_empty_context") else SAMPLE_PROJECT_CONTEXT
            conversation_summary = SAMPLE_CONVERSATION_SUMMARY if scenario.get("use_conversation_context") else None
            recent_messages = scenario.get("recent_messages")

            start = time.time()
            intent = await analyzer.analyze(
                user_input=scenario["input"],
                project_context=project_context,
                conversation_summary=conversation_summary,
                recent_messages=recent_messages,
            )
            elapsed = time.time() - start

            # Check expectations
            expected = scenario["expected"]
            errors = []

            if "task_type" in expected and intent.task_type != expected["task_type"]:
                errors.append(f"task_type: expected {expected['task_type']}, got {intent.task_type}")

            if "priority" in expected and intent.priority != expected["priority"]:
                errors.append(f"priority: expected {expected['priority']}, got {intent.priority}")

            if "priority_in" in expected and intent.priority not in expected["priority_in"]:
                errors.append(f"priority: expected one of {expected['priority_in']}, got {intent.priority}")

            if "needs_clarification" in expected and intent.needs_clarification != expected["needs_clarification"]:
                errors.append(f"needs_clarification: expected {expected['needs_clarification']}, got {intent.needs_clarification}")

            if errors:
                print(f"   ❌ FAILED: {'; '.join(errors)}")
                failed += 1
            else:
                print(f"   ✅ PASSED ({elapsed:.2f}s)")
                passed += 1

            results.append({
                "scenario": scenario["name"],
                "input": scenario["input"],
                "expected": expected,
                "actual": intent.to_dict(),
                "passed": len(errors) == 0,
                "errors": errors,
                "elapsed_ms": int(elapsed * 1000),
            })

            # Rate limiting
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
            results.append({
                "scenario": scenario["name"],
                "error": str(e),
                "passed": False,
            })

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(TEST_SCENARIOS)} total")
    print("=" * 60)

    # Save results if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {"passed": passed, "failed": failed, "total": len(TEST_SCENARIOS)},
                "results": results,
            }, f, indent=2)
        print(f"\nResults saved to: {output_file}")


def main():
    """Main entry point for CLI testing."""
    parser = argparse.ArgumentParser(description="Test Nova (Intent Analyzer) Agent")
    parser.add_argument("--interactive", action="store_true", help="Run interactive testing mode")
    parser.add_argument("--run-all", action="store_true", help="Run all test scenarios")
    parser.add_argument("--output", type=str, help="Output file for results (JSON)")

    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_test())
    elif args.run_all:
        asyncio.run(run_all_scenarios(args.output))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()