"""
GUARDIAN (Validator) Tests with Exhaustive Logging.

Tests code validation with issue tracking, score logging,
and fix loop iteration capture.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.agents.logging import AgentLogger
from tests.agents.logging.instrumented_claude import (
    InstrumentedClaudeService,
    MockClaudeServiceWithUsage,
)


class TestGuardianWithLogging:
    """Tests for GUARDIAN agent with comprehensive logging."""

    @pytest.mark.asyncio
    async def test_validation_pass_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """
        Passing validation should be fully logged.

        Verifies:
        - Validation score captured
        - All checks logged
        - No issues recorded
        """
        from app.agents.validator import Validator

        mock_response = json.dumps({
            "score": 92,
            "approved": True,
            "issues": [],
            "checks_passed": [
                "syntax_valid",
                "security_check",
                "laravel_conventions",
                "relationships_valid",
            ],
            "summary": "Code passes all validation checks",
        })

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate") as execution:
            agent_logger.log_agent_input("GUARDIAN", {
                "files_to_validate": [sample_execution_result.file],
                "intent_type": sample_intent.task_type,
            })

            result = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )

            agent_logger.log_agent_output("GUARDIAN", result)
            execution.final_output = result

        # Verify passed
        assert result is not None
        assert result.approved == True
        assert result.score >= 90

        # Verify logging
        report = agent_logger.generate_report()
        guardian_exec = report["agent_executions"].get("GUARDIAN_validate")
        assert guardian_exec is not None

    @pytest.mark.asyncio
    async def test_validation_issues_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """Validation issues should be fully logged."""
        from app.agents.validator import Validator

        mock_response = json.dumps({
            "score": 65,
            "approved": False,
            "issues": [
                {
                    "severity": "error",
                    "file": "app/Http/Controllers/TestController.php",
                    "line": 15,
                    "message": "Missing return type declaration",
                    "suggestion": "Add return type JsonResponse",
                },
                {
                    "severity": "warning",
                    "file": "app/Http/Controllers/TestController.php",
                    "line": 20,
                    "message": "Consider using form request for validation",
                    "suggestion": "Create TestRequest class",
                },
            ],
            "checks_passed": ["syntax_valid"],
            "checks_failed": ["type_safety", "laravel_best_practices"],
            "summary": "Code needs improvements",
        })

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_issues") as execution:
            result = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )

            # Log issues separately
            if result and hasattr(result, 'issues'):
                agent_logger.log_agent_output("GUARDIAN", {
                    "score": result.score,
                    "approved": result.approved,
                    "issue_count": len(result.issues),
                    "issues": [
                        {
                            "severity": i.severity if hasattr(i, 'severity') else "unknown",
                            "message": i.message if hasattr(i, 'message') else str(i),
                        }
                        for i in result.issues
                    ],
                })

            execution.final_output = result

        # Verify issues captured
        assert result.approved == False
        assert len(result.issues) >= 2

        # Verify logging
        report = agent_logger.generate_report()
        log_dir = agent_logger.get_log_dir()
        output_file = log_dir / "agents" / "guardian" / "output.json"
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_subscription_validation_logged(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
    ):
        """
        Full subscription scenario validation should be logged.
        """
        from app.agents.validator import Validator
        from app.agents.executor import ExecutionResult
        from app.agents.intent_analyzer import Intent
        from app.agents.context_retriever import RetrievedContext, CodeChunk

        # Create mock execution results from scenario
        execution_results = [
            ExecutionResult(
                file="database/migrations/2024_01_01_000001_create_plans_table.php",
                action="create",
                content="<?php // migration",
                diff=None,
                original_content=None,
                success=True,
            ),
            ExecutionResult(
                file="app/Models/Plan.php",
                action="create",
                content="<?php class Plan extends Model {}",
                diff=None,
                original_content=None,
                success=True,
            ),
            ExecutionResult(
                file="app/Http/Controllers/SubscriptionController.php",
                action="create",
                content="<?php class SubscriptionController extends Controller {}",
                diff=None,
                original_content=None,
                success=True,
            ),
        ]

        intent = Intent(
            task_type="feature",
            task_type_confidence=0.92,
            domains_affected=["database", "models", "controllers"],
            scope="feature",
            languages=["php"],
            requires_migration=True,
            priority="high",
            entities={},
            search_queries=[],
            reasoning="Subscription management",
            overall_confidence=0.92,
            needs_clarification=False,
            clarifying_questions=[],
        )

        context = RetrievedContext(
            chunks=[
                CodeChunk(
                    file_path="app/Models/User.php",
                    content="<?php class User extends Model {}",
                    chunk_type="class",
                    start_line=1,
                    end_line=10,
                    score=0.9,
                ),
            ],
            domain_summaries={},
        )

        mock_response = subscription_management_scenario["mock_responses"]["guardian"]["validation"]

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_subscription") as execution:
            agent_logger.log_agent_input("GUARDIAN", {
                "scenario": "subscription_management",
                "files_count": len(execution_results),
            })

            result = await validator.validate(
                user_input=subscription_management_scenario["user_input"],
                intent=intent,
                results=execution_results,
                context=context,
            )

            agent_logger.log_agent_output("GUARDIAN", result)

            # Save final context snapshot
            agent_logger.log_context_snapshot("after_guardian", {
                "score": result.score,
                "approved": result.approved,
                "issues_count": len(result.issues) if hasattr(result, 'issues') else 0,
            })

            execution.final_output = result

        # Verify scenario requirements
        expected = subscription_management_scenario["expected_flow"]["guardian"]
        assert result.score >= expected["min_score"]

        # Verify logging
        report = agent_logger.generate_report()
        assert report["context_snapshots"].get("after_guardian") is not None


class TestGuardianFixLoopLogging:
    """Tests for GUARDIAN fix loop logging."""

    @pytest.mark.asyncio
    async def test_fix_loop_iteration_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """Fix loop iterations should be tracked."""
        from app.agents.validator import Validator

        # First validation fails
        fail_response = json.dumps({
            "score": 60,
            "approved": False,
            "issues": [
                {"severity": "error", "message": "Missing validation"},
            ],
            "checks_passed": [],
        })

        # Second validation passes
        pass_response = json.dumps({
            "score": 88,
            "approved": True,
            "issues": [],
            "checks_passed": ["all_checks"],
        })

        # Mock service returns fail then pass
        mock_service = MagicMock()
        mock_service.chat_async = AsyncMock(side_effect=[fail_response, pass_response])
        mock_service._last_usage = {}

        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_fix_loop") as execution:
            # First validation
            agent_logger.log_agent_input("GUARDIAN", {"iteration": 1})
            result1 = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )

            if not result1.approved:
                agent_logger.log_retry(
                    agent="GUARDIAN",
                    operation="validation",
                    retry_count=1,
                    reason="Issues found, fixing",
                )

            # Second validation (after fix)
            agent_logger.log_agent_input("GUARDIAN", {"iteration": 2})
            result2 = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )

            agent_logger.log_agent_output("GUARDIAN", {
                "iterations": 2,
                "final_score": result2.score,
                "final_approved": result2.approved,
            })

            execution.final_output = result2

        # Verify fix loop tracked
        report = agent_logger.generate_report()
        assert report["summary"]["errors"]["total_retries"] >= 1

    @pytest.mark.asyncio
    async def test_score_progression_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """Score progression across iterations should be logged."""
        from app.agents.validator import Validator

        scores = [55, 68, 75, 85]
        responses = [
            json.dumps({
                "score": score,
                "approved": score >= 80,
                "issues": [] if score >= 80 else [{"message": "Issues"}],
            })
            for score in scores
        ]

        mock_service = MagicMock()
        mock_service.chat_async = AsyncMock(side_effect=responses)
        mock_service._last_usage = {}

        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)
        score_history = []

        with agent_logger.agent_execution("GUARDIAN", "validate_progression") as execution:
            for i, _ in enumerate(scores):
                result = await validator.validate(
                    user_input="Test feature implementation",
                    intent=sample_intent,
                    results=[sample_execution_result],
                    context=sample_context,
                )
                score_history.append(result.score)

                if result.approved:
                    break

                agent_logger.log_retry(
                    agent="GUARDIAN",
                    operation="validation",
                    retry_count=i + 1,
                    reason=f"Score {result.score} < 80",
                )

            agent_logger.log_agent_output("GUARDIAN", {
                "score_history": score_history,
                "iterations": len(score_history),
                "final_approved": result.approved,
            })

            execution.final_output = result

        # Verify progression
        assert score_history == [55, 68, 75, 85]

        # Verify logging
        report = agent_logger.generate_report()
        log_dir = agent_logger.get_log_dir()
        output_file = log_dir / "agents" / "guardian" / "output.json"
        assert output_file.exists()


class TestGuardianSeverityLogging:
    """Tests for GUARDIAN issue severity logging."""

    @pytest.mark.asyncio
    async def test_error_severity_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """Error-level issues should be prominently logged."""
        from app.agents.validator import Validator

        mock_response = json.dumps({
            "score": 40,
            "approved": False,
            "issues": [
                {
                    "severity": "error",
                    "file": "test.php",
                    "line": 10,
                    "message": "SQL injection vulnerability",
                },
                {
                    "severity": "error",
                    "file": "test.php",
                    "line": 25,
                    "message": "Hardcoded credentials",
                },
            ],
        })

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_errors") as execution:
            result = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )

            # Log errors as actual errors
            for issue in result.issues:
                if hasattr(issue, 'severity') and issue.severity == "error":
                    agent_logger.log_error(
                        agent="GUARDIAN",
                        error=Exception(issue.message),
                        operation="validation",
                        recoverable=True,
                    )

            execution.final_output = result

        # Verify errors logged
        report = agent_logger.generate_report()
        assert report["summary"]["errors"]["total"] >= 2

    @pytest.mark.asyncio
    async def test_warning_severity_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """Warning-level issues should be logged appropriately."""
        from app.agents.validator import Validator

        mock_response = json.dumps({
            "score": 75,
            "approved": False,
            "issues": [
                {
                    "severity": "warning",
                    "message": "Consider adding rate limiting",
                },
                {
                    "severity": "info",
                    "message": "Could use dependency injection",
                },
            ],
        })

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_warnings") as execution:
            result = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )

            agent_logger.log_agent_output("GUARDIAN", {
                "warnings": len([i for i in result.issues if hasattr(i, 'severity') and i.severity == "warning"]),
                "info": len([i for i in result.issues if hasattr(i, 'severity') and i.severity == "info"]),
            })

            execution.final_output = result

        # Verify logging captured severity levels
        report = agent_logger.generate_report()
        assert report is not None


class TestGuardianMetricsLogging:
    """Tests for GUARDIAN metrics and reporting."""

    @pytest.mark.asyncio
    async def test_validation_duration_logged(
        self,
        agent_logger: AgentLogger,
        sample_execution_result,
        sample_intent,
        sample_context,
    ):
        """Validation duration should be tracked."""
        from app.agents.validator import Validator

        mock_response = json.dumps({
            "score": 90,
            "approved": True,
            "issues": [],
        })

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_timing") as execution:
            result = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=[sample_execution_result],
                context=sample_context,
            )
            execution.final_output = result

        # Verify timing logged
        report = agent_logger.generate_report()
        guardian_exec = report["agent_executions"].get("GUARDIAN_validate_timing")
        assert guardian_exec["timing"]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_multi_file_validation_logged(
        self,
        agent_logger: AgentLogger,
        sample_intent,
        sample_context,
    ):
        """Multi-file validation should track all files."""
        from app.agents.validator import Validator
        from app.agents.executor import ExecutionResult

        execution_results = [
            ExecutionResult(
                file=f"app/Test/File{i}.php",
                action="create",
                content=f"<?php class File{i} {{}}",
                diff=None,
                original_content=None,
                success=True,
            )
            for i in range(5)
        ]

        mock_response = json.dumps({
            "score": 85,
            "approved": True,
            "issues": [],
        })

        mock_service = MockClaudeServiceWithUsage(
            responses={"validation": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="GUARDIAN",
        )

        validator = Validator(claude_service=instrumented)

        with agent_logger.agent_execution("GUARDIAN", "validate_multi") as execution:
            agent_logger.log_agent_input("GUARDIAN", {
                "files_count": len(execution_results),
                "files": [r.file for r in execution_results],
            })

            result = await validator.validate(
                user_input="Test feature implementation",
                intent=sample_intent,
                results=execution_results,
                context=sample_context,
            )

            agent_logger.log_agent_output("GUARDIAN", {
                "files_validated": len(execution_results),
                "score": result.score,
            })

            execution.final_output = result

        # Verify all files tracked
        report = agent_logger.generate_report()
        guardian_exec = report["agent_executions"].get("GUARDIAN_validate_multi")
        assert guardian_exec is not None
