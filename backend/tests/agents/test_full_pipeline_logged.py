"""
Full Pipeline Tests with Exhaustive Logging.

Tests the complete agent pipeline (NOVA → SCOUT → BLUEPRINT → FORGE → GUARDIAN)
with comprehensive logging of every operation, prompt, response, and data transfer.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from tests.agents.logging import AgentLogger, ReportGenerator
from tests.agents.logging.instrumented_claude import (
    InstrumentedClaudeService,
    MockClaudeServiceWithUsage,
)


class TestFullPipelineWithLogging:
    """
    Full pipeline tests with exhaustive logging.

    Pipeline Flow:
    User Input → NOVA → SCOUT → BLUEPRINT → [APPROVAL] → FORGE → GUARDIAN → [FIX LOOP]
    """

    @pytest.mark.asyncio
    async def test_subscription_pipeline_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        subscription_management_scenario,
        mock_search_results_subscription,
    ):
        """
        Complete subscription management pipeline with full logging.

        This is the main comprehensive test that exercises all agents
        and logs everything for analysis.
        """
        from app.agents.intent_analyzer import IntentAnalyzer
        from app.agents.context_retriever import ContextRetriever
        from app.agents.planner import Planner
        from app.agents.executor import Executor
        from app.agents.validator import Validator

        scenario = subscription_management_scenario

        # Setup mock responses for each agent
        mock_responses = {
            "nova": scenario["mock_responses"]["nova"]["intent"],
            "blueprint": scenario["mock_responses"]["blueprint"]["plan"],
            "forge": json.dumps({
                "file": "test.php",
                "action": "create",
                "content": "<?php class Test {}",
            }),
            "guardian": scenario["mock_responses"]["guardian"]["validation"],
        }

        # Create instrumented services for each agent
        def create_instrumented_claude(agent_name: str, responses: dict):
            mock_service = MockClaudeServiceWithUsage(responses=responses)
            return InstrumentedClaudeService(
                claude_service=mock_service,
                agent_logger=agent_logger,
                default_agent=agent_name,
            )

        # Initialize agents
        nova_claude = create_instrumented_claude("NOVA", {"intent": mock_responses["nova"]})
        blueprint_claude = create_instrumented_claude("BLUEPRINT", {"planning": mock_responses["blueprint"]})
        forge_claude = create_instrumented_claude("FORGE", {
            "reasoning": "{}",
            "execution": mock_responses["forge"],
            "verification": json.dumps({"passes_verification": True, "issues": []}),
        })
        guardian_claude = create_instrumented_claude("GUARDIAN", {"validation": mock_responses["guardian"]})

        nova = IntentAnalyzer(claude_service=nova_claude)
        scout = ContextRetriever(
            db=mock_db_session,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service,
        )
        blueprint = Planner(claude_service=blueprint_claude)
        forge = Executor(claude_service=forge_claude)
        guardian = Validator(claude_service=guardian_claude)

        # Setup scout mock
        mock_vector_store.search = MagicMock(return_value=mock_search_results_subscription)

        results = {}

        # =====================================================================
        # Stage 1: NOVA - Intent Analysis
        # =====================================================================
        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            agent_logger.log_agent_input("NOVA", {
                "user_input": scenario["user_input"][:500],
                "project_context": scenario["project_context"],
            })

            nova_claude.set_context("NOVA", "analyze")
            intent = await nova.analyze(
                user_input=scenario["user_input"],
                project_context=json.dumps(scenario["project_context"]),
                conversation_summary=None,
            )

            agent_logger.log_agent_output("NOVA", intent)
            agent_logger.log_context_snapshot("after_nova", {
                "task_type": intent.task_type,
                "domains": intent.domains_affected,
                "requires_migration": intent.requires_migration,
                "confidence": intent.overall_confidence,
            })
            execution.final_output = intent
            results["intent"] = intent

        # =====================================================================
        # Stage 2: SCOUT - Context Retrieval
        # =====================================================================
        with agent_logger.agent_execution("SCOUT", "retrieve") as execution:
            agent_logger.log_agent_input("SCOUT", {
                "intent": intent.to_dict() if hasattr(intent, 'to_dict') else str(intent),
                "search_queries": intent.search_queries,
            })

            context = await scout.retrieve(
                project_id="test-project-123",
                intent=intent,
                require_minimum=False,  # Don't fail on insufficient context in tests
            )

            agent_logger.log_context_retrieval(
                agent="SCOUT",
                search_queries=intent.search_queries,
                chunks_found=len(mock_search_results_subscription),
                chunks_used=len(context.chunks) if context else 0,
                total_tokens=sum(len(c.content) // 4 for c in context.chunks) if context else 0,
                file_paths=[r.file_path for r in mock_search_results_subscription],
                scores=[r.score for r in mock_search_results_subscription],
            )

            agent_logger.log_agent_output("SCOUT", context)
            agent_logger.log_context_snapshot("after_scout", {
                "chunks_count": len(context.chunks) if context else 0,
                "unique_files": len(set(c.file_path for c in context.chunks)) if context else 0,
            })
            execution.final_output = context
            results["context"] = context

        # =====================================================================
        # Stage 3: BLUEPRINT - Planning
        # =====================================================================
        with agent_logger.agent_execution("BLUEPRINT", "plan") as execution:
            agent_logger.log_agent_input("BLUEPRINT", {
                "intent_type": intent.task_type,
                "context_chunks": len(context.chunks) if context else 0,
            })

            blueprint_claude.set_context("BLUEPRINT", "plan")
            plan = await blueprint.plan(
                user_input=scenario["user_input"],
                intent=intent,
                context=context,
                project_context=json.dumps(scenario["project_context"]),
            )

            agent_logger.log_agent_output("BLUEPRINT", plan)
            agent_logger.log_context_snapshot("after_blueprint", {
                "steps_count": len(plan.steps),
                "step_types": list(set(s.category for s in plan.steps)),
                "estimated_complexity": plan.estimated_complexity,
            })
            execution.final_output = plan
            results["plan"] = plan

        # =====================================================================
        # Stage 4: FORGE - Execution
        # =====================================================================
        execution_results = []
        with agent_logger.agent_execution("FORGE", "execute") as execution:
            agent_logger.log_agent_input("FORGE", {
                "steps_count": len(plan.steps),
                "steps": [{"order": s.order, "file": s.file, "action": s.action} for s in plan.steps[:5]],
            })

            forge_claude.set_context("FORGE", "execute")

            # Execute first 3 steps for test
            for step in plan.steps[:3]:
                result = await forge.execute_step(
                    step=step,
                    context=context,
                    previous_results=execution_results,
                    current_file_content=None,
                    project_context=json.dumps(scenario["project_context"]),
                )

                if result:
                    agent_logger.log_file_access(
                        agent="FORGE",
                        operation="write",
                        file_path=result.file,
                        content=result.content,
                    )
                    execution_results.append(result)

            agent_logger.log_agent_output("FORGE", {
                "files_generated": len(execution_results),
                "success_count": sum(1 for r in execution_results if r.success),
            })
            agent_logger.log_context_snapshot("after_forge", {
                "files": [r.file for r in execution_results],
                "total_lines": sum(len(r.content.split('\n')) for r in execution_results),
            })
            execution.final_output = execution_results
            results["execution_results"] = execution_results

        # =====================================================================
        # Stage 5: GUARDIAN - Validation
        # =====================================================================
        with agent_logger.agent_execution("GUARDIAN", "validate") as execution:
            agent_logger.log_agent_input("GUARDIAN", {
                "files_to_validate": [r.file for r in execution_results],
                "intent_type": intent.task_type,
            })

            guardian_claude.set_context("GUARDIAN", "validate")
            validation = await guardian.validate(
                user_input=scenario["user_input"],
                intent=intent,
                results=execution_results,
                context=context,
            )

            agent_logger.log_agent_output("GUARDIAN", validation)
            agent_logger.log_context_snapshot("final_validation", {
                "score": validation.score,
                "approved": validation.approved,
                "issues_count": len(validation.issues) if hasattr(validation, 'issues') else 0,
            })
            execution.final_output = validation
            results["validation"] = validation

        # =====================================================================
        # Generate Report
        # =====================================================================
        report = agent_logger.generate_report()

        # =====================================================================
        # Assertions - Verify Pipeline Success
        # =====================================================================

        # Verify each stage completed
        assert results["intent"] is not None
        assert results["context"] is not None
        assert results["plan"] is not None
        assert len(results["execution_results"]) >= 1
        assert results["validation"] is not None

        # Verify scenario expectations
        expected = scenario["expected_flow"]
        assert results["intent"].task_type == expected["nova"]["task_type"]
        assert results["intent"].requires_migration == expected["nova"]["requires_migration"]
        assert len(results["plan"].steps) >= expected["blueprint"]["min_steps"]
        assert results["validation"].score >= expected["guardian"]["min_score"]

        # Verify comprehensive logging
        assert report["summary"]["agents"]["total_executed"] == 5
        assert report["summary"]["agents"]["succeeded"] >= 4

        # Verify context snapshots captured
        assert "after_nova" in report["context_snapshots"]
        assert "after_scout" in report["context_snapshots"]
        assert "after_blueprint" in report["context_snapshots"]
        assert "after_forge" in report["context_snapshots"]
        assert "final_validation" in report["context_snapshots"]

        # Verify log files created
        log_dir = agent_logger.get_log_dir()
        assert (log_dir / "master_log.json").exists()
        assert (log_dir / "metrics" / "summary.json").exists()

    @pytest.mark.asyncio
    async def test_simple_crud_pipeline_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        simple_crud_scenario,
    ):
        """
        Simple CRUD pipeline test with logging.
        """
        from app.agents.intent_analyzer import IntentAnalyzer
        from app.agents.context_retriever import ContextRetriever
        from app.agents.planner import Planner
        from app.agents.executor import Executor
        from app.agents.validator import Validator

        scenario = simple_crud_scenario

        # Create mock services
        nova_mock = MockClaudeServiceWithUsage(
            responses={"intent": scenario["mock_responses"]["nova"]["intent"]},
        )
        blueprint_mock = MockClaudeServiceWithUsage(
            responses={"planning": scenario["mock_responses"]["blueprint"]["plan"]},
        )
        forge_mock = MockClaudeServiceWithUsage(
            responses={
                "reasoning": "{}",
                "execution": json.dumps({"file": "test.php", "action": "create", "content": "<?php"}),
                "verification": json.dumps({"passes_verification": True}),
            },
        )
        guardian_mock = MockClaudeServiceWithUsage(
            responses={"validation": scenario["mock_responses"]["guardian"]["validation"]},
        )

        # Setup vector store
        mock_vector_store.search = MagicMock(return_value=[])

        # Run pipeline
        results = await self._run_pipeline(
            agent_logger=agent_logger,
            scenario=scenario,
            nova_service=InstrumentedClaudeService(nova_mock, agent_logger, "NOVA"),
            scout_db=mock_db_session,
            scout_vector_store=mock_vector_store,
            scout_embedding_service=mock_embedding_service,
            blueprint_service=InstrumentedClaudeService(blueprint_mock, agent_logger, "BLUEPRINT"),
            forge_service=InstrumentedClaudeService(forge_mock, agent_logger, "FORGE"),
            guardian_service=InstrumentedClaudeService(guardian_mock, agent_logger, "GUARDIAN"),
        )

        # Verify pipeline completed
        assert results["validation"].score >= scenario["expected_flow"]["guardian"]["min_score"]

        # Verify logging
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 4

    @pytest.mark.asyncio
    async def test_bug_fix_pipeline_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
        bug_fix_scenario,
    ):
        """
        Bug fix pipeline test with logging.
        """
        from app.agents.intent_analyzer import IntentAnalyzer

        scenario = bug_fix_scenario

        nova_mock = MockClaudeServiceWithUsage(
            responses={"intent": scenario["mock_responses"]["nova"]["intent"]},
        )
        instrumented = InstrumentedClaudeService(nova_mock, agent_logger, "NOVA")

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_bugfix") as execution:
            intent = await nova.analyze(
                user_input=scenario["user_input"],
                project_context=json.dumps(scenario["project_context"]),
            )
            execution.final_output = intent

        # Verify bugfix identified
        assert intent.task_type == "bugfix"

        # Verify logging
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["succeeded"] >= 1

    async def _run_pipeline(
        self,
        agent_logger: AgentLogger,
        scenario: dict,
        nova_service,
        scout_db,
        scout_vector_store,
        scout_embedding_service,
        blueprint_service,
        forge_service,
        guardian_service,
    ) -> dict:
        """Helper to run the full pipeline with given services."""
        from app.agents.intent_analyzer import IntentAnalyzer
        from app.agents.context_retriever import ContextRetriever
        from app.agents.planner import Planner
        from app.agents.executor import Executor
        from app.agents.validator import Validator

        nova = IntentAnalyzer(claude_service=nova_service)
        scout = ContextRetriever(
            db=scout_db,
            vector_store=scout_vector_store,
            embedding_service=scout_embedding_service,
        )
        blueprint = Planner(claude_service=blueprint_service)
        forge = Executor(claude_service=forge_service)
        guardian = Validator(claude_service=guardian_service)

        results = {}

        # NOVA
        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            intent = await nova.analyze(
                user_input=scenario["user_input"],
                project_context=json.dumps(scenario.get("project_context", {})),
            )
            execution.final_output = intent
            results["intent"] = intent

        # SCOUT
        with agent_logger.agent_execution("SCOUT", "retrieve") as execution:
            context = await scout.retrieve(
                project_id="test-project",
                intent=intent,
                require_minimum=False,  # Don't fail on insufficient context in tests
            )
            execution.final_output = context
            results["context"] = context

        # BLUEPRINT
        with agent_logger.agent_execution("BLUEPRINT", "plan") as execution:
            plan = await blueprint.plan(
                user_input=scenario["user_input"],
                intent=intent,
                context=context,
                project_context=json.dumps(scenario.get("project_context", {})),
            )
            execution.final_output = plan
            results["plan"] = plan

        # FORGE
        execution_results = []
        with agent_logger.agent_execution("FORGE", "execute") as execution:
            for step in plan.steps[:2]:
                result = await forge.execute_step(
                    step=step,
                    context=context,
                    previous_results=execution_results,
                    current_file_content=None,
                    project_context=json.dumps(scenario.get("project_context", {})),
                )
                if result:
                    execution_results.append(result)
            execution.final_output = execution_results
            results["execution_results"] = execution_results

        # GUARDIAN
        with agent_logger.agent_execution("GUARDIAN", "validate") as execution:
            validation = await guardian.validate(
                user_input=scenario["user_input"],
                intent=intent,
                results=execution_results,
                context=context,
            )
            execution.final_output = validation
            results["validation"] = validation

        return results


class TestPipelineReporting:
    """Tests for pipeline report generation."""

    @pytest.mark.asyncio
    async def test_markdown_report_generated(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
    ):
        """Markdown report should be generated correctly."""
        from app.agents.intent_analyzer import IntentAnalyzer

        scenario = subscription_management_scenario

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": scenario["mock_responses"]["nova"]["intent"]},
        )
        instrumented = InstrumentedClaudeService(mock_service, agent_logger, "NOVA")

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            intent = await nova.analyze(
                user_input=scenario["user_input"],
                project_context="{}",
            )
            execution.final_output = intent

        # Generate report
        agent_logger.generate_report()

        # Generate markdown report
        log_dir = agent_logger.get_log_dir()
        report_gen = ReportGenerator(log_dir)
        md_report = report_gen.generate_markdown_report(log_dir / "summary_report.md")

        # Verify markdown generated
        assert "# Agent Pipeline Test Report" in md_report
        assert "NOVA" in md_report
        assert (log_dir / "summary_report.md").exists()

    @pytest.mark.asyncio
    async def test_html_report_generated(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
    ):
        """HTML report should be generated correctly."""
        from app.agents.intent_analyzer import IntentAnalyzer

        scenario = subscription_management_scenario

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": scenario["mock_responses"]["nova"]["intent"]},
        )
        instrumented = InstrumentedClaudeService(mock_service, agent_logger, "NOVA")

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            intent = await nova.analyze(
                user_input=scenario["user_input"],
                project_context="{}",
            )
            execution.final_output = intent

        # Generate report
        agent_logger.generate_report()

        # Generate HTML report
        log_dir = agent_logger.get_log_dir()
        report_gen = ReportGenerator(log_dir)
        html_report = report_gen.generate_html_report(log_dir / "report.html")

        # Verify HTML generated
        assert "<!DOCTYPE html>" in html_report
        assert "Agent Pipeline Test Report" in html_report
        assert (log_dir / "report.html").exists()

    @pytest.mark.asyncio
    async def test_json_report_generated(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
    ):
        """JSON report should be generated with all data."""
        from app.agents.intent_analyzer import IntentAnalyzer

        scenario = subscription_management_scenario

        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": scenario["mock_responses"]["nova"]["intent"]},
        )
        instrumented = InstrumentedClaudeService(mock_service, agent_logger, "NOVA")

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            intent = await nova.analyze(
                user_input=scenario["user_input"],
                project_context="{}",
            )
            execution.final_output = intent

        # Generate report
        report = agent_logger.generate_report()

        # Verify JSON structure
        log_dir = agent_logger.get_log_dir()
        report_gen = ReportGenerator(log_dir)
        json_report = report_gen.generate_json_report(log_dir / "report.json")

        # Verify JSON fields
        assert "summary" in json_report
        assert "agents" in json_report
        assert (log_dir / "report.json").exists()


class TestPipelineErrorHandling:
    """Tests for pipeline error handling with logging."""

    @pytest.mark.asyncio
    async def test_agent_failure_logged(
        self,
        agent_logger: AgentLogger,
    ):
        """Agent failure should be logged with full context and return fallback intent."""
        from app.agents.intent_analyzer import IntentAnalyzer

        mock_service = MockClaudeServiceWithUsage(
            default_response="Invalid JSON response",
        )
        instrumented = InstrumentedClaudeService(mock_service, agent_logger, "NOVA")

        nova = IntentAnalyzer(claude_service=instrumented)

        with agent_logger.agent_execution("NOVA", "analyze_fail") as execution:
            # IntentAnalyzer returns fallback intent instead of raising
            intent = await nova.analyze(
                user_input="Test request",
                project_context="{}",
            )
            execution.final_output = intent

        # Verify fallback intent was returned (needs_clarification should be True)
        assert intent.needs_clarification == True
        assert intent.task_type == "question"
        assert intent.retry_count > 0  # Should have retried

        # Verify error was logged
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 1

    @pytest.mark.asyncio
    async def test_partial_pipeline_logged(
        self,
        agent_logger: AgentLogger,
        mock_db_session,
        mock_vector_store,
        mock_embedding_service,
    ):
        """Partial pipeline completion should still generate reports."""
        from app.agents.intent_analyzer import IntentAnalyzer, Intent

        # Successful NOVA
        mock_service = MockClaudeServiceWithUsage(
            responses={"intent": json.dumps({
                "task_type": "feature",
                "task_type_confidence": 0.9,
                "domains_affected": ["controllers"],
                "scope": "feature",
                "languages": ["php"],
                "requires_migration": False,
                "priority": "medium",
                "entities": {"files": [], "classes": [], "methods": [], "routes": [], "tables": []},
                "search_queries": [],
                "reasoning": "Test",
                "overall_confidence": 0.9,
                "needs_clarification": False,
                "clarifying_questions": [],
            })},
        )
        instrumented = InstrumentedClaudeService(mock_service, agent_logger, "NOVA")

        nova = IntentAnalyzer(claude_service=instrumented)

        # Only run NOVA
        with agent_logger.agent_execution("NOVA", "analyze") as execution:
            intent = await nova.analyze(
                user_input="Test request",
                project_context="{}",
            )
            execution.final_output = intent

        # Generate partial report
        report = agent_logger.generate_report()

        # Verify partial data captured
        assert report["summary"]["agents"]["total_executed"] >= 1
        assert "NOVA_analyze" in report["agent_executions"]
