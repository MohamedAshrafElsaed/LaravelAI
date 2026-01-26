"""
Tests for Conductor - Enhanced Orchestrator Agent.

Covers:
- Pipeline metrics tracking
- Context accumulation
- Retry logic with backoff
- Error recovery strategies
- Smart fix prioritization
"""
import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.agents.orchestrator import (
    Orchestrator,
    ProcessResult,
    ProcessEvent,
    ProcessPhase,
    AgentName,
    ErrorSeverity,
    PipelineMetrics,
    AgentMetrics,
    AccumulatedContext,
    RetryConfig,
    RetryState,
    AgentError,
    ErrorRecoveryStrategy,
)
from app.agents.intent_analyzer import Intent
from app.agents.context_retriever import RetrievedContext, CodeChunk
from app.agents.planner import Plan, PlanStep
from app.agents.executor import ExecutionResult
from app.agents.validator import ValidationResult, ValidationIssue
from app.agents.exceptions import InsufficientContextError


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_claude():
    """Create a mock Claude service."""
    mock = MagicMock()
    mock.chat_async = AsyncMock()
    mock.tracker = None
    return mock


@pytest.fixture
def sample_intent():
    """Create a sample intent."""
    return Intent(
        task_type="feature",
        scope="single_file",
        domains_affected=["users"],
        search_queries=["UserService"],
    )


@pytest.fixture
def sample_context():
    """Create a sample retrieved context."""
    return RetrievedContext(
        chunks=[
            CodeChunk(
                file_path="app/Services/BaseService.php",
                content="<?php\nnamespace App\\Services;\n\nclass BaseService {}",
                chunk_type="code",
                start_line=1,
                end_line=5,
                score=0.9,
            ),
        ],
        confidence_level="high",
    )


@pytest.fixture
def sample_plan():
    """Create a sample plan."""
    return Plan(
        reasoning="Create a new service",
        steps=[
            PlanStep(
                order=1,
                action="create",
                file="app/Services/UserService.php",
                description="Create UserService",
            )
        ],
    )


@pytest.fixture
def sample_execution_result():
    """Create a sample execution result."""
    return ExecutionResult(
        file="app/Services/UserService.php",
        action="create",
        content="<?php\nnamespace App\\Services;\n\nclass UserService {}",
        success=True,
    )


@pytest.fixture
def sample_validation_success():
    """Create a passing validation result."""
    return ValidationResult(
        approved=True,
        score=95,
        issues=[],
        summary="All checks passed",
    )


@pytest.fixture
def sample_validation_failure():
    """Create a failing validation result."""
    return ValidationResult(
        approved=False,
        score=60,
        issues=[
            ValidationIssue(
                severity="error",
                file="app/Services/UserService.php",
                message="Missing use statement",
                line=5,
            )
        ],
        summary="Has errors",
    )


# =============================================================================
# UNIT TESTS - Pipeline Metrics (Group C)
# =============================================================================

class TestPipelineMetrics:
    """Tests for pipeline metrics tracking."""

    def test_create_metrics(self):
        """Test creating pipeline metrics."""
        metrics = PipelineMetrics(request_id="test_123")
        assert metrics.request_id == "test_123"
        assert metrics.success is False
        assert len(metrics.agents) == 0

    def test_start_agent(self):
        """Test starting agent tracking."""
        metrics = PipelineMetrics(request_id="test_123")
        agent_metrics = metrics.start_agent("nova")

        assert "nova" in metrics.agents
        assert agent_metrics.agent == "nova"
        assert agent_metrics.started_at is not None

    def test_complete_agent(self):
        """Test completing agent tracking."""
        metrics = PipelineMetrics(request_id="test_123")
        metrics.start_agent("nova")
        metrics.complete_agent("nova", success=True)

        assert metrics.agents["nova"].success is True
        assert metrics.agents["nova"].completed_at is not None
        assert metrics.agents["nova"].duration_ms > 0

    def test_complete_phase(self):
        """Test phase completion tracking."""
        metrics = PipelineMetrics(request_id="test_123")
        metrics.complete_phase("analyzing")
        metrics.complete_phase("retrieving")

        assert "analyzing" in metrics.phases_completed
        assert "retrieving" in metrics.phases_completed
        assert len(metrics.phases_completed) == 2

    def test_finalize_metrics(self):
        """Test finalizing metrics."""
        metrics = PipelineMetrics(request_id="test_123")
        metrics.start_agent("nova")
        metrics.complete_agent("nova")
        metrics.finalize(success=True, score=95)

        assert metrics.success is True
        assert metrics.final_score == 95
        assert metrics.total_duration_ms > 0

    def test_to_dict(self):
        """Test metrics serialization."""
        metrics = PipelineMetrics(request_id="test_123")
        metrics.finalize(success=True, score=90)

        data = metrics.to_dict()
        assert data["request_id"] == "test_123"
        assert data["success"] is True
        assert data["final_score"] == 90


class TestAgentMetrics:
    """Tests for individual agent metrics."""

    def test_create_agent_metrics(self):
        """Test creating agent metrics."""
        metrics = AgentMetrics(agent="forge")
        assert metrics.agent == "forge"
        assert metrics.success is False
        assert metrics.retries == 0

    def test_complete_with_error(self):
        """Test completing with error."""
        metrics = AgentMetrics(agent="forge")
        metrics.complete(success=False, error="Generation failed")

        assert metrics.success is False
        assert metrics.error == "Generation failed"

    def test_duration_calculation(self):
        """Test duration is calculated correctly."""
        metrics = AgentMetrics(agent="forge")
        # Simulate some time passing
        metrics.started_at = datetime.utcnow() - timedelta(milliseconds=100)
        metrics.complete(success=True)

        assert metrics.duration_ms >= 100


# =============================================================================
# UNIT TESTS - Context Accumulation (Group D)
# =============================================================================

class TestAccumulatedContext:
    """Tests for progressive context accumulation."""

    def test_add_intent(self, sample_intent):
        """Test adding intent to context."""
        ctx = AccumulatedContext()
        ctx.add_intent(sample_intent)

        assert ctx.intent == sample_intent
        assert "feature" in ctx.task_summary

    def test_add_context(self, sample_context):
        """Test adding retrieved context."""
        ctx = AccumulatedContext()
        ctx.add_context(sample_context)

        assert ctx.retrieved_context == sample_context
        assert len(ctx.key_files) > 0

    def test_detect_patterns(self):
        """Test pattern detection from context."""
        context = RetrievedContext(
            chunks=[
                CodeChunk(
                    file_path="test.php",
                    content="<?php\ndeclare(strict_types=1);",
                    chunk_type="code",
                    start_line=1,
                    end_line=2,
                    score=0.9,
                )
            ],
            confidence_level="high",
        )

        ctx = AccumulatedContext()
        ctx.add_context(context)

        assert ctx.detected_patterns.get("strict_types") is True

    def test_add_plan(self, sample_plan):
        """Test adding plan."""
        ctx = AccumulatedContext()
        ctx.add_plan(sample_plan)

        assert ctx.plan == sample_plan
        assert len(ctx.planned_files) == 1

    def test_add_execution(self, sample_execution_result):
        """Test adding execution result."""
        ctx = AccumulatedContext()
        ctx.add_execution(sample_execution_result)

        assert len(ctx.execution_results) == 1
        assert sample_execution_result.file in ctx.generated_content

    def test_add_validation_tracks_issues(self, sample_validation_failure):
        """Test that validation tracks recurring issues."""
        ctx = AccumulatedContext()
        ctx.add_validation(sample_validation_failure)
        ctx.add_validation(sample_validation_failure)

        assert len(ctx.validation_history) == 2
        assert len(ctx.recurring_issues) > 0

    def test_get_fix_context(self, sample_intent, sample_validation_failure):
        """Test getting fix context string."""
        ctx = AccumulatedContext()
        ctx.add_intent(sample_intent)
        ctx.add_validation(sample_validation_failure)

        fix_ctx = ctx.get_fix_context()
        assert "feature" in fix_ctx
        assert "score=" in fix_ctx

    def test_find_recurring_issues(self):
        """Test finding issues that appear multiple times."""
        ctx = AccumulatedContext()

        # Add same issue twice
        issue = ValidationIssue(
            severity="error",
            file="test.php",
            message="Missing import",
            line=10,
        )

        validation1 = ValidationResult(approved=False, score=60, issues=[issue])
        validation2 = ValidationResult(approved=False, score=65, issues=[issue])

        ctx.add_validation(validation1)
        ctx.add_validation(validation2)

        recurring = ctx._find_recurring_issues()
        assert len(recurring) >= 1


# =============================================================================
# UNIT TESTS - Retry Logic (Group B)
# =============================================================================

class TestRetryConfig:
    """Tests for retry configuration."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 0.5
        assert config.exponential_base == 2.0


class TestRetryState:
    """Tests for retry state tracking."""

    def test_initial_state(self):
        """Test initial retry state."""
        state = RetryState()
        assert state.attempt == 0
        assert state.best_score == 0

    def test_record_attempt(self, sample_execution_result):
        """Test recording a fix attempt."""
        state = RetryState()
        state.record_attempt(70, [sample_execution_result])

        assert state.attempt == 1
        assert state.last_score == 70
        assert state.best_score == 70

    def test_best_score_tracking(self, sample_execution_result):
        """Test that best score is tracked."""
        state = RetryState()
        state.record_attempt(70, [sample_execution_result])
        state.record_attempt(80, [sample_execution_result])
        state.record_attempt(75, [sample_execution_result])

        assert state.best_score == 80

    def test_mark_fixed(self):
        """Test marking an issue as fixed."""
        state = RetryState()
        state.mark_fixed("issue_signature_123")

        assert "issue_signature_123" in state.fixed_issues

    def test_mark_unfixable(self):
        """Test marking an issue as unfixable."""
        state = RetryState()
        state.mark_unfixable("issue_signature_456")

        assert "issue_signature_456" in state.unfixable_issues

    def test_should_retry_max_attempts(self):
        """Test retry stops at max attempts."""
        from app.agents.config import AgentConfig
        config = AgentConfig(MAX_FIX_ATTEMPTS=3)

        state = RetryState()
        state.attempt = 3

        should, reason = state.should_retry(config)
        assert should is False
        assert "Max attempts" in reason

    def test_should_retry_score_degradation(self):
        """Test retry stops on score degradation."""
        from app.agents.config import AgentConfig
        config = AgentConfig(SCORE_DEGRADATION_THRESHOLD=5)

        state = RetryState()
        state.best_score = 80
        state.last_score = 70  # Degraded by 10

        should, reason = state.should_retry(config)
        assert should is False
        assert "degrading" in reason

    def test_backoff_delay_increases(self):
        """Test that backoff delay increases with attempts."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)
        state = RetryState()

        state.attempt = 0
        delay0 = state.get_backoff_delay(config)

        state.attempt = 1
        delay1 = state.get_backoff_delay(config)

        state.attempt = 2
        delay2 = state.get_backoff_delay(config)

        assert delay1 > delay0
        assert delay2 > delay1


# =============================================================================
# UNIT TESTS - Error Recovery (Group A)
# =============================================================================

class TestErrorRecoveryStrategy:
    """Tests for error recovery strategies."""

    def test_intent_error_not_recoverable(self):
        """Test that intent errors are not recoverable."""
        ctx = AccumulatedContext()
        error = Exception("Intent analysis failed")

        recoverable, message = ErrorRecoveryStrategy.for_intent_error(error, ctx)
        assert recoverable is False

    def test_context_error_with_chunks_recoverable(self):
        """Test context error with some chunks is recoverable."""
        ctx = AccumulatedContext()
        error = InsufficientContextError(
            message="Low context",
            chunks_found=2,
        )

        recoverable, message = ErrorRecoveryStrategy.for_context_error(error, ctx)
        assert recoverable is True

    def test_context_error_no_chunks_not_recoverable(self):
        """Test context error with no chunks is not recoverable."""
        ctx = AccumulatedContext()
        error = InsufficientContextError(
            message="No context",
            chunks_found=0,
        )

        recoverable, message = ErrorRecoveryStrategy.for_context_error(error, ctx)
        assert recoverable is False

    def test_planning_error_with_context_recoverable(self, sample_context):
        """Test planning error with context is recoverable."""
        ctx = AccumulatedContext()
        ctx.add_context(sample_context)
        error = Exception("Planning failed")

        recoverable, message = ErrorRecoveryStrategy.for_planning_error(error, ctx)
        assert recoverable is True

    def test_execution_error_partial_success(self, sample_execution_result):
        """Test execution error with partial success is recoverable."""
        ctx = AccumulatedContext()
        ctx.add_execution(sample_execution_result)
        error = Exception("Some steps failed")

        recoverable, message = ErrorRecoveryStrategy.for_execution_error(error, ctx)
        assert recoverable is True
        assert "succeeded" in message

    def test_validation_error_with_results_recoverable(self, sample_execution_result):
        """Test validation error with results is recoverable."""
        ctx = AccumulatedContext()
        ctx.add_execution(sample_execution_result)
        error = Exception("Validation failed")

        recoverable, message = ErrorRecoveryStrategy.for_validation_error(error, ctx)
        assert recoverable is True


class TestAgentError:
    """Tests for structured agent errors."""

    def test_create_agent_error(self):
        """Test creating an agent error."""
        error = AgentError(
            agent=AgentName.FORGE,
            phase=ProcessPhase.EXECUTING,
            message="Code generation failed",
            severity=ErrorSeverity.RECOVERABLE,
            recoverable=True,
        )

        assert error.agent == AgentName.FORGE
        assert error.recoverable is True

    def test_to_dict(self):
        """Test error serialization."""
        error = AgentError(
            agent=AgentName.GUARDIAN,
            phase=ProcessPhase.VALIDATING,
            message="Validation timeout",
            severity=ErrorSeverity.DEGRADED,
            recoverable=True,
            suggestion="Try again",
        )

        data = error.to_dict()
        assert data["agent"] == "guardian"
        assert data["phase"] == "validating"
        assert data["suggestion"] == "Try again"


# =============================================================================
# UNIT TESTS - Process Event and Result
# =============================================================================

class TestProcessEvent:
    """Tests for process events."""

    def test_create_event(self):
        """Test creating a process event."""
        event = ProcessEvent(
            phase=ProcessPhase.ANALYZING,
            message="Analyzing...",
            progress=0.1,
        )

        assert event.phase == ProcessPhase.ANALYZING
        assert event.progress == 0.1

    def test_event_with_metrics(self):
        """Test event with metrics data."""
        event = ProcessEvent(
            phase=ProcessPhase.COMPLETED,
            message="Done",
            progress=1.0,
            metrics={"duration_ms": 1500},
        )

        data = event.to_dict()
        assert data["metrics"]["duration_ms"] == 1500

    def test_event_with_agent(self):
        """Test event with agent name."""
        event = ProcessEvent(
            phase=ProcessPhase.EXECUTING,
            message="Generating code",
            progress=0.5,
            agent="forge",
        )

        data = event.to_dict()
        assert data["agent"] == "forge"


class TestProcessResult:
    """Tests for process results."""

    def test_create_result(self):
        """Test creating a process result."""
        result = ProcessResult(success=True)
        assert result.success is True
        assert result.error is None

    def test_result_with_warnings(self):
        """Test result with warnings."""
        result = ProcessResult(
            success=True,
            warnings=["Limited context", "Partial validation"],
        )

        assert len(result.warnings) == 2

    def test_result_with_metrics(self):
        """Test result with metrics."""
        metrics = PipelineMetrics(request_id="test")
        result = ProcessResult(success=True, metrics=metrics)

        data = result.to_dict()
        assert data["metrics"]["request_id"] == "test"


# =============================================================================
# INTEGRATION TESTS - Orchestrator
# =============================================================================

class TestOrchestratorIntegration:
    """Integration tests for the orchestrator."""

    @pytest.fixture
    def orchestrator(self, mock_db, mock_claude):
        """Create an orchestrator with mocked dependencies."""
        with patch('app.agents.orchestrator.IntentAnalyzer') as MockIntent, \
             patch('app.agents.orchestrator.ContextRetriever') as MockContext, \
             patch('app.agents.orchestrator.Planner') as MockPlanner, \
             patch('app.agents.orchestrator.Executor') as MockExecutor, \
             patch('app.agents.orchestrator.Validator') as MockValidator:

            orch = Orchestrator(
                db=mock_db,
                claude_service=mock_claude,
            )
            return orch

    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initializes correctly."""
        assert orchestrator is not None
        assert orchestrator.retry_config is not None

    def test_normalize_path(self, orchestrator):
        """Test path normalization."""
        assert orchestrator._normalize_path("app/Test.php") == "app/test.php"
        assert orchestrator._normalize_path("./app/Test.php") == "app/test.php"
        assert orchestrator._normalize_path("app\\Test.php") == "app/test.php"

    @pytest.mark.asyncio
    async def test_emit_event(self, orchestrator):
        """Test event emission."""
        events = []
        orchestrator.event_callback = lambda e: events.append(e)

        event = await orchestrator._emit_event(
            ProcessPhase.ANALYZING,
            "Test message",
            0.5,
        )

        assert event.phase == ProcessPhase.ANALYZING
        assert len(events) == 1


# =============================================================================
# PARAMETRIZED TESTS
# =============================================================================

class TestParametrized:
    """Parametrized tests for comprehensive coverage."""

    @pytest.mark.parametrize("phase,expected_value", [
        (ProcessPhase.ANALYZING, "analyzing"),
        (ProcessPhase.RETRIEVING, "retrieving"),
        (ProcessPhase.PLANNING, "planning"),
        (ProcessPhase.EXECUTING, "executing"),
        (ProcessPhase.VALIDATING, "validating"),
        (ProcessPhase.FIXING, "fixing"),
        (ProcessPhase.COMPLETED, "completed"),
        (ProcessPhase.FAILED, "failed"),
    ])
    def test_process_phase_values(self, phase, expected_value):
        """Test all process phases have correct values."""
        assert phase.value == expected_value

    @pytest.mark.parametrize("agent,expected_value", [
        (AgentName.NOVA, "nova"),
        (AgentName.SCOUT, "scout"),
        (AgentName.BLUEPRINT, "blueprint"),
        (AgentName.FORGE, "forge"),
        (AgentName.GUARDIAN, "guardian"),
        (AgentName.CONDUCTOR, "conductor"),
    ])
    def test_agent_name_values(self, agent, expected_value):
        """Test all agent names have correct values."""
        assert agent.value == expected_value

    @pytest.mark.parametrize("attempt,base_delay,expected_min", [
        (0, 1.0, 1.0),
        (1, 1.0, 2.0),
        (2, 1.0, 4.0),
        (3, 1.0, 5.0),  # Capped at max_delay
    ])
    def test_backoff_delay_formula(self, attempt, base_delay, expected_min):
        """Test backoff delay calculation."""
        config = RetryConfig(base_delay=base_delay, max_delay=5.0, jitter=0.0)
        state = RetryState()
        state.attempt = attempt

        delay = state.get_backoff_delay(config)
        assert delay >= expected_min * 0.9  # Allow small variance


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_validation_history(self):
        """Test finding recurring issues with no history."""
        ctx = AccumulatedContext()
        recurring = ctx._find_recurring_issues()
        assert len(recurring) == 0

    def test_retry_state_no_attempts(self):
        """Test retry state with no attempts."""
        from app.agents.config import AgentConfig
        config = AgentConfig()
        state = RetryState()

        should, _ = state.should_retry(config)
        assert should is True

    def test_metrics_finalize_twice(self):
        """Test finalizing metrics twice doesn't break."""
        metrics = PipelineMetrics(request_id="test")
        metrics.finalize(success=True, score=90)
        metrics.finalize(success=False, score=50)

        # Last finalize wins
        assert metrics.success is False
        assert metrics.final_score == 50

    def test_accumulated_context_empty(self):
        """Test accumulated context with no data."""
        ctx = AccumulatedContext()
        fix_ctx = ctx.get_fix_context()

        # Should not crash, returns minimal context
        assert isinstance(fix_ctx, str)

    def test_process_event_minimal(self):
        """Test process event with minimal data."""
        event = ProcessEvent(
            phase=ProcessPhase.COMPLETED,
            message="Done",
            progress=1.0,
        )

        data = event.to_dict()
        assert "phase" in data
        assert "timestamp" in data