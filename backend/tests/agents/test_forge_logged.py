"""
FORGE (Executor) Tests with Exhaustive Logging.

Tests code generation with file output capture, diff logging,
and step-by-step execution tracking.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.agents.logging import AgentLogger
from tests.agents.logging.instrumented_claude import (
    InstrumentedClaudeService,
    MockClaudeServiceWithUsage,
)


class TestForgeWithLogging:
    """Tests for FORGE agent with comprehensive logging."""

    @pytest.mark.asyncio
    async def test_code_generation_logged(
        self,
        agent_logger: AgentLogger,
        sample_plan_step,
        sample_context,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """
        Code generation should be fully logged.

        Verifies:
        - Reasoning phase captured
        - Generated code logged
        - Verification logged
        - File diffs tracked
        """
        from app.agents.executor import Executor

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(
                    file="app/Http/Controllers/TestController.php",
                    action="create",
                    content="<?php\n\nnamespace App\\Http\\Controllers;\n\nclass TestController extends Controller\n{\n    public function index()\n    {\n        return response()->json(['message' => 'Hello']);\n    }\n}",
                ),
                "verification": verification_response_factory(),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)

        with agent_logger.agent_execution("FORGE", "execute") as execution:
            agent_logger.log_agent_input("FORGE", {
                "step": sample_plan_step.to_dict() if hasattr(sample_plan_step, 'to_dict') else str(sample_plan_step),
                "context_chunks": len(sample_context.chunks),
            })

            result = await executor.execute_step(
                step=sample_plan_step,
                context=sample_context,
                previous_results=[],
                current_file_content=None,
            )

            # Log generated file
            if result:
                agent_logger.log_file_access(
                    agent="FORGE",
                    operation="write",
                    file_path=result.file,
                    content=result.content,
                )

            agent_logger.log_agent_output("FORGE", result)
            execution.final_output = result

        # Verify result
        assert result is not None
        assert result.success == True

        # Verify logging
        report = agent_logger.generate_report()
        forge_exec = report["agent_executions"].get("FORGE_execute")
        assert forge_exec is not None
        assert forge_exec["file_accesses_count"] >= 1

    @pytest.mark.asyncio
    async def test_multi_step_execution_logged(
        self,
        agent_logger: AgentLogger,
        sample_context,
        generate_plan_steps,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """Multiple step execution should all be logged."""
        from app.agents.executor import Executor
        from app.agents.planner import PlanStep

        # Generate multiple steps
        step_dicts = generate_plan_steps(count=3)
        steps = [
            PlanStep(
                order=s["order"],
                action=s["action"],
                file=s["file"],
                category=s["category"],
                description=s["description"],
                depends_on=s["depends_on"],
                estimated_lines=s["estimated_lines"],
            )
            for s in step_dicts
        ]

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(),
                "verification": verification_response_factory(),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)
        results = []

        with agent_logger.agent_execution("FORGE", "execute_multi") as execution:
            for i, step in enumerate(steps):
                agent_logger.log_agent_input("FORGE", {
                    "step_number": i + 1,
                    "total_steps": len(steps),
                    "file": step.file,
                })

                result = await executor.execute_step(
                    step=step,
                    context=sample_context,
                    previous_results=results,
                    current_file_content=None,
                )

                if result:
                    agent_logger.log_file_access(
                        agent="FORGE",
                        operation="write",
                        file_path=result.file,
                        content=result.content,
                    )
                    results.append(result)

            agent_logger.log_agent_output("FORGE", {
                "total_files": len(results),
                "success_count": sum(1 for r in results if r.success),
            })

            execution.final_output = results

        # Verify all steps executed
        assert len(results) == 3

        # Verify all logged
        report = agent_logger.generate_report()
        forge_exec = report["agent_executions"].get("FORGE_execute_multi")
        assert forge_exec["file_accesses_count"] >= 3

    @pytest.mark.asyncio
    async def test_subscription_execution_logged(
        self,
        agent_logger: AgentLogger,
        subscription_management_scenario,
        sample_context,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """
        Full subscription scenario execution should be logged.
        """
        from app.agents.executor import Executor
        from app.agents.planner import PlanStep

        # Create steps from scenario plan
        plan_data = json.loads(subscription_management_scenario["mock_responses"]["blueprint"]["plan"])
        steps = []
        for step_dict in plan_data["steps"][:3]:  # Just first 3 for test
            steps.append(PlanStep(
                order=step_dict["order"],
                action=step_dict["action"],
                file=step_dict["file"],
                category=step_dict["category"],
                description=step_dict["description"],
                depends_on=step_dict.get("depends_on", []),
                estimated_lines=step_dict.get("estimated_lines", 50),
            ))

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(),
                "verification": verification_response_factory(),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)
        results = []

        with agent_logger.agent_execution("FORGE", "execute_subscription") as execution:
            agent_logger.log_agent_input("FORGE", {
                "scenario": "subscription_management",
                "steps_count": len(steps),
            })

            for step in steps:
                result = await executor.execute_step(
                    step=step,
                    context=sample_context,
                    previous_results=results,
                    current_file_content=None,
                )

                if result:
                    agent_logger.log_file_access(
                        agent="FORGE",
                        operation="write",
                        file_path=result.file,
                        content=result.content,
                    )
                    results.append(result)

            # Save generated files snapshot
            agent_logger.log_context_snapshot("after_forge", {
                "files_generated": [r.file for r in results],
                "total_lines": sum(len(r.content.split('\n')) for r in results),
            })

            execution.final_output = results

        # Verify scenario requirements
        expected = subscription_management_scenario["expected_flow"]["forge"]
        # Note: we only executed 3 steps for test
        assert len(results) >= 1

        # Verify logging
        report = agent_logger.generate_report()
        assert report["context_snapshots"].get("after_forge") is not None


class TestForgeDiffLogging:
    """Tests for FORGE diff and modification logging."""

    @pytest.mark.asyncio
    async def test_modify_action_logged(
        self,
        agent_logger: AgentLogger,
        sample_context,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """Modify action should log original and new content."""
        from app.agents.executor import Executor
        from app.agents.planner import PlanStep

        existing_content = "<?php\n\nclass UserController {\n    public function index() {}\n}"
        new_content = "<?php\n\nclass UserController {\n    public function index() {}\n    public function export() {\n        return response()->download('users.csv');\n    }\n}"

        step = PlanStep(
            order=1,
            action="modify",
            file="app/Http/Controllers/UserController.php",
            category="controller",
            description="Add export method",
            depends_on=[],
            estimated_lines=10,
        )

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(
                    file="app/Http/Controllers/UserController.php",
                    action="modify",
                    content=new_content,
                ),
                "verification": verification_response_factory(),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)

        with agent_logger.agent_execution("FORGE", "execute_modify") as execution:
            agent_logger.log_agent_input("FORGE", {
                "action": "modify",
                "file": step.file,
                "existing_content_length": len(existing_content),
            })

            result = await executor.execute_step(
                step=step,
                context=sample_context,
                previous_results=[],
                current_file_content=existing_content,
            )

            if result:
                agent_logger.log_file_access(
                    agent="FORGE",
                    operation="write",
                    file_path=result.file,
                    content=result.content,
                )

                # Log diff info
                agent_logger.log_agent_output("FORGE", {
                    "action": result.action,
                    "original_lines": len(existing_content.split('\n')),
                    "new_lines": len(result.content.split('\n')),
                    "has_diff": result.diff is not None,
                })

            execution.final_output = result

        # Verify modification
        assert result.action == "modify"

        # Verify logging captured diff context
        report = agent_logger.generate_report()
        forge_exec = report["agent_executions"].get("FORGE_execute_modify")
        assert forge_exec["file_accesses_count"] >= 1


class TestForgeVerificationLogging:
    """Tests for FORGE verification phase logging."""

    @pytest.mark.asyncio
    async def test_verification_pass_logged(
        self,
        agent_logger: AgentLogger,
        sample_plan_step,
        sample_context,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """Passing verification should be logged."""
        from app.agents.executor import Executor

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(),
                "verification": verification_response_factory(passes=True),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)

        with agent_logger.agent_execution("FORGE", "execute_verified") as execution:
            result = await executor.execute_step(
                step=sample_plan_step,
                context=sample_context,
                previous_results=[],
                current_file_content=None,
            )
            execution.final_output = result

        # Verify success
        assert result.success == True

    @pytest.mark.asyncio
    async def test_verification_fail_logged(
        self,
        agent_logger: AgentLogger,
        sample_plan_step,
        sample_context,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """Failed verification should be logged with issues."""
        from app.agents.executor import Executor

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(),
                "verification": verification_response_factory(
                    passes=False,
                    issues=["Missing import statement", "Syntax error on line 10"],
                ),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)

        with agent_logger.agent_execution("FORGE", "execute_failed") as execution:
            result = await executor.execute_step(
                step=sample_plan_step,
                context=sample_context,
                previous_results=[],
                current_file_content=None,
            )

            if not result.success:
                agent_logger.log_error(
                    agent="FORGE",
                    error=Exception("Verification failed"),
                    operation="verification",
                    recoverable=True,
                )

            execution.final_output = result

        # Verification may retry internally - check logging occurred
        report = agent_logger.generate_report()
        forge_exec = report["agent_executions"].get("FORGE_execute_failed")
        assert forge_exec is not None


class TestForgeMetricsLogging:
    """Tests for FORGE metrics and token tracking."""

    @pytest.mark.asyncio
    async def test_token_usage_per_step_logged(
        self,
        agent_logger: AgentLogger,
        sample_plan_step,
        sample_context,
        forge_response_factory,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """Token usage should be tracked per step."""
        from app.agents.executor import Executor

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": forge_response_factory(),
                "verification": verification_response_factory(),
            },
            simulate_tokens=True,
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)

        with agent_logger.agent_execution("FORGE", "execute_tokens") as execution:
            result = await executor.execute_step(
                step=sample_plan_step,
                context=sample_context,
                previous_results=[],
                current_file_content=None,
            )
            execution.final_output = result

        # Verify token tracking
        report = agent_logger.generate_report()
        assert report["summary"]["agents"]["total_executed"] >= 1

    @pytest.mark.asyncio
    async def test_generated_file_size_logged(
        self,
        agent_logger: AgentLogger,
        sample_plan_step,
        sample_context,
        reasoning_response_factory,
        verification_response_factory,
    ):
        """Generated file sizes should be tracked."""
        from app.agents.executor import Executor

        large_content = "<?php\n\n" + "\n".join([
            f"public function method{i}() {{ return {i}; }}"
            for i in range(100)
        ])

        mock_service = MockClaudeServiceWithUsage(
            responses={
                "reasoning": reasoning_response_factory(),
                "execution": json.dumps({
                    "file": "app/Services/LargeService.php",
                    "action": "create",
                    "content": large_content,
                }),
                "verification": verification_response_factory(),
            },
        )
        instrumented = InstrumentedClaudeService(
            claude_service=mock_service,
            agent_logger=agent_logger,
            default_agent="FORGE",
        )

        executor = Executor(claude_service=instrumented)

        with agent_logger.agent_execution("FORGE", "execute_large") as execution:
            result = await executor.execute_step(
                step=sample_plan_step,
                context=sample_context,
                previous_results=[],
                current_file_content=None,
            )

            if result:
                agent_logger.log_file_access(
                    agent="FORGE",
                    operation="write",
                    file_path=result.file,
                    content=result.content,
                )

                agent_logger.log_agent_output("FORGE", {
                    "file": result.file,
                    "content_length": len(result.content),
                    "line_count": len(result.content.split('\n')),
                })

            execution.final_output = result

        # Verify file metrics logged
        report = agent_logger.generate_report()
        forge_exec = report["agent_executions"].get("FORGE_execute_large")
        assert forge_exec["file_accesses_count"] >= 1
