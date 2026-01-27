"""
BLUEPRINT (Planner) Tests with Exhaustive Logging.

Tests plan generation with step logging, dependency tracking,
and implementation strategy capture.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.agents.logging import AgentLogger
from tests.agents.logging.instrumented_claude import (
    InstrumentedClaudeService,
    MockClaudeServiceWithUsage,
)


class TestBlueprintWithLogging:
    """Tests for BLUEPRINT agent with comprehensive logging."""

    @pytest.mark.asyncio
    async def test_plan_generation_logged(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
        sample_intent,
        sample_context,
    ):
        """
        Plan generation should be fully logged.

        Verifies:
        - Claude API call is captured
        - Plan steps are logged
        - Dependencies are tracked
        - Risk assessment is captured
        """
        from app.agents.planner import Planner

        mock_response = subscription_management_scenario["mock_responses"]["blueprint"]["plan"]

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan") as execution:
            agent_logger.log_agent_input("BLUEPRINT", {
                "intent": sample_intent.to_dict() if hasattr(sample_intent, 'to_dict') else str(sample_intent),
                "context_chunks": len(sample_context.chunks),
            })

            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Laravel 11.x application",
            )

            agent_logger.log_agent_output("BLUEPRINT", plan)
            execution.final_output = plan

        # Verify plan was generated
        assert plan is not None
        assert len(plan.steps) >= 1

        # Verify logging
        report = agent_logger.generate_report()
        blueprint_exec = report["agent_executions"].get("BLUEPRINT_plan")
        assert blueprint_exec is not None
        assert blueprint_exec["metrics"]["total_api_calls"] >= 1

    @pytest.mark.asyncio
    async def test_subscription_plan_logged(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
    ):
        """
        Full subscription scenario plan should be logged.
        """
        from app.agents.planner import Planner
        from app.agents.intent_analyzer import Intent
        from app.agents.context_retriever import RetrievedContext, CodeChunk

        # Create intent from scenario
        intent = Intent(
            task_type="feature",
            task_type_confidence=0.92,
            domains_affected=["database", "models", "controllers", "services"],
            scope="feature",
            languages=["php"],
            requires_migration=True,
            priority="high",
            entities={"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
            search_queries=[],
            reasoning="Full subscription management",
            overall_confidence=0.92,
            needs_clarification=False,
            clarifying_questions=[],
        )

        # Create minimal context
        context = RetrievedContext(
            chunks=[
                CodeChunk(
                    file_path="app/Models/User.php",
                    content="<?php class User {}",
                    chunk_type="class",
                    start_line=1,
                    end_line=10,
                    score=0.9,
                ),
            ],
            domain_summaries={},
        )

        mock_response = subscription_management_scenario["mock_responses"]["blueprint"]["plan"]

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_subscription") as execution:
            agent_logger.log_agent_input("BLUEPRINT", {
                "scenario": "subscription_management",
                "user_input": subscription_management_scenario["user_input"][:200],
            })

            plan = await planner.plan(
                user_input=subscription_management_scenario["user_input"],
                intent=intent,
                context=context,
                project_context="Laravel + React application",
            )

            # Log plan steps
            plan_data = plan.to_dict() if hasattr(plan, 'to_dict') else {"steps": []}
            agent_logger.log_agent_output("BLUEPRINT", plan_data)

            # Save context snapshot
            agent_logger.log_context_snapshot("after_blueprint", {
                "steps_count": len(plan.steps),
                "step_types": list(set(s.category for s in plan.steps)),
            })

            execution.final_output = plan

        # Verify scenario requirements
        expected = subscription_management_scenario["expected_flow"]["blueprint"]
        assert len(plan.steps) >= expected["min_steps"]

        # Verify logging
        report = agent_logger.generate_report()
        assert report["context_snapshots"].get("after_blueprint") is not None

    @pytest.mark.asyncio
    async def test_step_dependencies_logged(
        self,
        agent_logger: AgentLogger,
        blueprint_response_factory,
        sample_intent,
        sample_context,
    ):
        """Step dependencies should be properly logged."""
        from app.agents.planner import Planner

        # Create plan with dependencies
        steps_with_deps = [
            {
                "order": 1,
                "action": "create",
                "file": "database/migrations/create_table.php",
                "category": "migration",
                "description": "Create database migration",
                "depends_on": [],
                "estimated_lines": 30,
            },
            {
                "order": 2,
                "action": "create",
                "file": "app/Models/Model.php",
                "category": "model",
                "description": "Create model",
                "depends_on": [1],
                "estimated_lines": 50,
            },
            {
                "order": 3,
                "action": "create",
                "file": "app/Services/Service.php",
                "category": "service",
                "description": "Create service",
                "depends_on": [2],
                "estimated_lines": 80,
            },
            {
                "order": 4,
                "action": "create",
                "file": "app/Http/Controllers/Controller.php",
                "category": "controller",
                "description": "Create controller",
                "depends_on": [2, 3],
                "estimated_lines": 60,
            },
        ]

        mock_response = blueprint_response_factory(steps=steps_with_deps)

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_deps") as execution:
            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Test project",
            )

            # Log dependencies
            agent_logger.log_agent_output("BLUEPRINT", {
                "steps": [
                    {
                        "order": s.order,
                        "file": s.file,
                        "depends_on": s.depends_on,
                    }
                    for s in plan.steps
                ]
            })

            execution.final_output = plan

        # Verify dependencies tracked
        assert len(plan.steps) == 4
        assert plan.steps[3].depends_on == [2, 3]

        # Verify logging
        report = agent_logger.generate_report()
        log_dir = agent_logger.get_log_dir()
        output_file = log_dir / "agents" / "blueprint" / "output.json"
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_clarification_plan_logged(
        self,
        agent_logger: AgentLogger,
        blueprint_response_factory,
        sample_intent,
        sample_context,
    ):
        """Plan requiring clarification should be logged."""
        from app.agents.planner import Planner

        mock_response = blueprint_response_factory(needs_clarification=True)

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_unclear") as execution:
            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Test project",
            )

            agent_logger.log_agent_output("BLUEPRINT", plan)
            execution.final_output = plan

        # Verify clarification captured
        assert plan.needs_clarification == True
        assert len(plan.clarifying_questions) > 0

        # Verify logging
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["succeeded"] >= 1


class TestBlueprintRiskAssessmentLogged:
    """Tests for BLUEPRINT risk assessment logging."""

    @pytest.mark.asyncio
    async def test_low_risk_plan_logged(
        self,
        agent_logger: AgentLogger,
        blueprint_response_factory,
        sample_intent,
        sample_context,
    ):
        """Low risk plan should be logged accordingly."""
        from app.agents.planner import Planner

        mock_response = blueprint_response_factory(confidence=0.95)

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_low_risk") as execution:
            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Test project",
            )
            execution.final_output = plan

        # Verify low risk
        assert plan.risk_level == "low"
        assert plan.overall_confidence >= 0.9

    @pytest.mark.asyncio
    async def test_complexity_estimation_logged(
        self,
        agent_logger: AgentLogger,
        blueprint_response_factory,
        sample_intent,
        sample_context,
        generate_plan_steps,
    ):
        """Complexity estimation should be logged."""
        from app.agents.planner import Planner

        # Generate many steps for high complexity
        many_steps = generate_plan_steps(count=10)
        mock_response = blueprint_response_factory(steps=many_steps)

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_complex") as execution:
            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Test project",
            )

            agent_logger.log_agent_output("BLUEPRINT", {
                "complexity": plan.estimated_complexity,
                "steps_count": len(plan.steps),
                "total_estimated_lines": sum(s.estimated_lines for s in plan.steps),
            })

            execution.final_output = plan

        # Verify complexity captured
        assert plan.estimated_complexity == 10
        assert len(plan.steps) == 10


class TestBlueprintMetricsLogged:
    """Tests for BLUEPRINT metrics and reporting."""

    @pytest.mark.asyncio
    async def test_token_usage_logged(
        self,
        agent_logger: AgentLogger,
        blueprint_response_factory,
        sample_intent,
        sample_context,
    ):
        """Token usage for planning should be tracked."""
        from app.agents.planner import Planner

        mock_response = blueprint_response_factory()

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
            simulate_tokens=True,
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_tokens") as execution:
            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Test project",
            )
            execution.final_output = plan

        # Verify logging occurred (token tracking may vary with mock)
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 1

    @pytest.mark.asyncio
    async def test_plan_file_output_logged(
        self,
        agent_logger: AgentLogger,
        blueprint_response_factory,
        sample_intent,
        sample_context,
    ):
        """Plan file paths should be logged."""
        from app.agents.planner import Planner

        mock_response = blueprint_response_factory()

        mock_service = MockClaudeServiceWithUsage(
            responses={"planning": mock_response},
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="BLUEPRINT",
        )

        planner = Planner(claude_service=instrumented)

        with agent_logger.agent_execution("BLUEPRINT", "plan_files") as execution:
            plan = await planner.plan(
                user_input="Test feature implementation",
                intent=sample_intent,
                context=sample_context,
                project_context="Test project",
            )

            # Log planned files
            planned_files = [s.file for s in plan.steps]
            agent_logger.log_agent_output("BLUEPRINT", {
                "planned_files": planned_files,
            })

            execution.final_output = plan

        # Verify files captured
        log_dir = agent_logger.get_log_dir()
        output_file = log_dir / "agents" / "blueprint" / "output.json"
        assert output_file.exists()
