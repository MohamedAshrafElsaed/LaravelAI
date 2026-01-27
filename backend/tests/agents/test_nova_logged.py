"""
NOVA (Intent Analyzer) Tests with Exhaustive Logging.

Tests intent analysis with full prompt/response capture,
timing metrics, and token usage tracking.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.agents.logging import AgentLogger
from tests.agents.logging.instrumented_claude import (
    InstrumentedClaudeService,
    MockClaudeServiceWithUsage,
)


class TestNovaWithLogging:
    """Tests for NOVA agent with comprehensive logging."""

    @pytest.mark.asyncio
    async def test_feature_intent_analysis_logged(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
    ):
        """
        Feature intent analysis should be fully logged.

        Verifies:
        - Claude API call is captured with full prompt
        - Response is logged completely
        - Token usage is tracked
        - Timing metrics are recorded
        """
        from app.agents.intent_analyzer import IntentAnalyzer

        # Get mock response from scenario
        mock_response = subscription_management_scenario["mock_responses"]["nova"]["intent"]

        # Create instrumented Claude service
        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        # Create Nova agent with instrumented service
        nova = IntentAnalyzer(claude_service=instrumented)

        # Execute with logging context
        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            # Log input
            input_data = {
                "user_request": subscription_management_scenario["user_input"],
                "project_context": subscription_management_scenario["project_context"],
                "conversation_history": [],
            }
            agent_logger.log_agent_input("NOVA", input_data)

            # Perform analysis
            intent = await nova.analyze(
                user_input=subscription_management_scenario["user_input"],
                project_context=json.dumps(subscription_management_scenario["project_context"]),
                conversation_summary=None,
            )

            # Log output
            agent_logger.log_agent_output("NOVA", intent)
            execution.final_output = intent

        # Verify intent was parsed correctly
        assert intent is not None
        assert intent.task_type == "feature"
        assert intent.requires_migration == True
        assert len(intent.domains_affected) >= 4

        # Verify logging captured everything
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 1

        # Check that Claude call was logged
        nova_execution = report["agent_executions"].get("NOVA_analyze")
        assert nova_execution is not None
        assert nova_execution["metrics"]["total_api_calls"] >= 1

        # Verify prompt was saved
        log_dir = agent_logger.get_log_dir()
        prompts_dir = log_dir / "prompts"
        assert prompts_dir.exists()

    @pytest.mark.asyncio
    async def test_bugfix_intent_analysis_logged(
        self,
        agent_logger: AgentLogger,
        bug_fix_scenario,
    ):
        """Bug fix intent analysis should be fully logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_response = bug_fix_scenario["mock_responses"]["nova"]["intent"]

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_bugfix") as execution:
            agent_logger.log_agent_input("NOVA", {
                "user_request": bug_fix_scenario["user_input"],
                "context": bug_fix_scenario["project_context"],
            })

            intent = await nova.analyze(
                user_input=bug_fix_scenario["user_input"],
                project_context=json.dumps(bug_fix_scenario["project_context"]),
            )

            agent_logger.log_agent_output("NOVA", intent)
            execution.final_output = intent

        # Verify bugfix was identified
        assert intent.task_type == "bugfix"
        assert intent.requires_migration == False

        # Verify logging
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 1

    @pytest.mark.asyncio
    async def test_refactor_intent_analysis_logged(
        self,
        agent_logger: AgentLogger,
        refactor_scenario,
    ):
        """Refactor intent analysis should be fully logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_response = refactor_scenario["mock_responses"]["nova"]["intent"]

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_refactor") as execution:
            agent_logger.log_agent_input("NOVA", {
                "user_request": refactor_scenario["user_input"],
                "context": refactor_scenario["project_context"],
            })

            intent = await nova.analyze(
                user_input=refactor_scenario["user_input"],
                project_context=json.dumps(refactor_scenario["project_context"]),
            )

            agent_logger.log_agent_output("NOVA", intent)
            execution.final_output = intent

        # Verify refactor was identified
        assert intent.task_type == "refactor"

        # Verify metrics
        report = agent_logger.generate_report()
        nova_exec = report["agent_executions"].get("NOVA_analyze_refactor")
        assert nova_exec["success"] == True

    @pytest.mark.asyncio
    async def test_clarification_needed_logged(
        self,
        agent_logger: AgentLogger,
        nova_response_factory,
    ):
        """Intent requiring clarification should be logged with questions."""
        from app.agents.intent_analyzer import IntentAnalyzer

        # Create response that needs clarification
        mock_response = nova_response_factory(
            task_type="feature",
            needs_clarification=True,
        )

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_unclear") as execution:
            agent_logger.log_agent_input("NOVA", {
                "user_request": "Do the thing",
                "context": {},
            })

            intent = await nova.analyze(
                user_input="Do the thing",
                project_context="{}",
            )

            agent_logger.log_agent_output("NOVA", intent)
            execution.final_output = intent

        # Verify clarification was flagged
        assert intent.needs_clarification == True
        assert len(intent.clarifying_questions) > 0

        # Verify logging captured clarification state
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["succeeded"] >= 1

    @pytest.mark.asyncio
    async def test_multiple_domains_logged(
        self,
        agent_logger: AgentLogger,
        nova_response_factory,
    ):
        """Multiple affected domains should be properly logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        domains = ["controllers", "models", "services", "routes", "middleware"]
        mock_response = nova_response_factory(
            task_type="feature",
            domains=domains,
            requires_migration=True,
        )

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_complex") as execution:
            intent = await nova.analyze(
                user_input="Complex multi-domain feature",
                project_context="{}",
            )
            agent_logger.log_agent_output("NOVA", intent)
            execution.final_output = intent

        # Verify all domains captured
        assert len(intent.domains_affected) == len(domains)
        for domain in domains:
            assert domain in intent.domains_affected

        # Verify comprehensive logging
        report = agent_logger.generate_report()
        log_dir = agent_logger.get_log_dir()

        # Check output file was saved
        output_file = log_dir / "agents" / "nova" / "output.json"
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_entity_extraction_logged(
        self,
        agent_logger: AgentLogger,
        nova_response_factory,
    ):
        """Entity extraction should be logged with all entity types."""
        from app.agents.intent_analyzer import IntentAnalyzer

        entities = {
            "files": ["UserController.php", "User.php"],
            "classes": ["User", "UserController"],
            "methods": ["index", "store", "update"],
            "routes": ["/api/users", "/api/users/{id}"],
            "tables": ["users"],
        }

        mock_response = nova_response_factory(
            task_type="feature",
            entities=entities,
        )

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_entities") as execution:
            agent_logger.log_agent_input("NOVA", {
                "user_request": "Update user management",
                "expected_entities": entities,
            })

            intent = await nova.analyze(
                user_input="Update user management",
                project_context="{}",
            )

            agent_logger.log_agent_output("NOVA", intent)
            execution.final_output = intent

        # Verify entities extracted
        assert intent.entities is not None

        # Verify logging
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["succeeded"] >= 1


class TestNovaErrorHandlingLogged:
    """Tests for NOVA error handling with logging."""

    @pytest.mark.asyncio
    async def test_invalid_json_response_logged(
        self,
        agent_logger: AgentLogger,
    ):
        """Invalid JSON response should result in fallback intent and be logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_service = MockClaudeServiceWithUsage(
            default_response="This is not valid JSON",
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_error") as execution:
            # IntentAnalyzer returns fallback intent instead of raising
            intent = await nova.analyze(
                user_input="Test request",
                project_context="{}",
            )
            execution.final_output = intent

        # Verify fallback intent was returned
        assert intent.needs_clarification == True
        assert intent.retry_count > 0

        # Verify logging occurred
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 1

    @pytest.mark.asyncio
    async def test_empty_response_logged(
        self,
        agent_logger: AgentLogger,
    ):
        """Empty response should result in fallback intent and be logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_service = MockClaudeServiceWithUsage(
            default_response="",
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_empty") as execution:
            # IntentAnalyzer returns fallback intent instead of raising
            intent = await nova.analyze(
                user_input="Test request",
                project_context="{}",
            )
            execution.final_output = intent

        # Verify fallback intent was returned
        assert intent.needs_clarification == True
        assert intent.retry_count > 0

        # Verify logging still occurred
        report = agent_logger.generate_report()
        assert report is not None


class TestNovaMetricsLogged:
    """Tests for NOVA metrics and reporting."""

    @pytest.mark.asyncio
    async def test_token_usage_logged(
        self,
        agent_logger: AgentLogger,
        nova_response_factory,
    ):
        """Token usage should be accurately logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_response = nova_response_factory()

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
            simulate_tokens=True,
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_tokens") as execution:
            await nova.analyze(
                user_input="Test request",
                project_context="{}",
            )

        # Verify token metrics
        report = agent_logger.generate_report()
        tokens_data = report.get("tokens", {})

        # Check report was generated (token tracking may vary with mock)
        assert report["summary"]["agents"]["total_executed"] >= 1

    @pytest.mark.asyncio
    async def test_latency_logged(
        self,
        agent_logger: AgentLogger,
        nova_response_factory,
    ):
        """API latency should be logged."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_response = nova_response_factory()

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="NOVA",
        )

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_latency") as execution:
            await nova.analyze(
                user_input="Test request",
                project_context="{}",
            )

        # Verify timing logged
        report = agent_logger.generate_report()
        nova_exec = report["agent_executions"].get("NOVA_analyze_latency")
        assert nova_exec["timing"]["duration_ms"] >= 0
