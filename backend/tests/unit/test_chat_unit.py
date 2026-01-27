"""
Unit tests for Chat module functions.

Tests orchestration, conversation management, and SSE event handling.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from uuid import uuid4
import json


class TestSSEEventFormatting:
    """Unit tests for SSE event formatting."""

    def test_create_sse_event(self):
        """SSE events should be formatted correctly."""
        from app.api.chat import create_sse_event

        event = create_sse_event("test_event", {"message": "Hello"})

        assert event.startswith("event: test_event\n")
        assert "data: " in event
        assert event.endswith("\n\n")

    def test_sse_event_json_data(self):
        """SSE event data should be valid JSON."""
        from app.api.chat import create_sse_event

        data = {"key": "value", "number": 42}
        event = create_sse_event("test", data)

        # Extract data line
        lines = event.strip().split("\n")
        data_line = [l for l in lines if l.startswith("data: ")][0]
        json_str = data_line[6:]  # Remove "data: " prefix

        parsed = json.loads(json_str)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42


class TestEventTypes:
    """Unit tests for SSE event type constants."""

    def test_event_type_values(self):
        """Event types should have correct values."""
        from app.api.chat import EventType

        assert EventType.CONNECTED == "connected"
        assert EventType.INTENT_ANALYZED == "intent_analyzed"
        assert EventType.CONTEXT_RETRIEVED == "context_retrieved"
        assert EventType.PLAN_CREATED == "plan_created"
        assert EventType.STEP_STARTED == "step_started"
        assert EventType.STEP_COMPLETED == "step_completed"
        assert EventType.COMPLETE == "complete"
        assert EventType.ERROR == "error"


class TestConversationHelpers:
    """Unit tests for conversation helper functions."""

    def test_format_conversation_history(self):
        """Conversation history should be formatted correctly."""
        from app.api.chat import format_conversation_history

        history = [
            {"role": "user", "content": "Hello", "has_code_changes": False},
            {"role": "assistant", "content": "Hi there!", "has_code_changes": False},
        ]

        formatted = format_conversation_history(history)

        assert "<previous_conversation>" in formatted
        assert "</previous_conversation>" in formatted
        assert "User:" in formatted or "**User:**" in formatted

    def test_format_empty_history(self):
        """Empty history should return empty string."""
        from app.api.chat import format_conversation_history

        formatted = format_conversation_history([])
        assert formatted == ""

    def test_format_history_truncation(self):
        """Long messages should be truncated."""
        from app.api.chat import format_conversation_history

        long_content = "x" * 2000
        history = [
            {"role": "user", "content": long_content, "has_code_changes": False},
        ]

        formatted = format_conversation_history(history)
        assert "[truncated]" in formatted


class TestConversationModel:
    """Unit tests for Conversation model."""

    def test_conversation_creation(self):
        """Conversation should be created correctly."""
        from app.models.models import Conversation

        conv = Conversation(
            id=str(uuid4()),
            user_id=str(uuid4()),
            project_id=str(uuid4()),
        )

        assert conv.title is None  # Title is set from first message

    def test_message_creation(self):
        """Message should be created correctly."""
        from app.models.models import Message

        msg = Message(
            conversation_id=str(uuid4()),
            role="user",
            content="Test message",
        )

        assert msg.role == "user"
        assert msg.code_changes is None


class TestOrchestrator:
    """Unit tests for Orchestrator class."""

    def test_process_result_structure(self):
        """ProcessResult should have correct structure."""
        from app.agents.orchestrator import ProcessResult

        result = ProcessResult(
            success=True,
            intent=None,
            plan=None,
            execution_results=[],
            validation=None,
            events=[],
            error=None,
        )

        assert result.success == True
        assert result.execution_results == []
        assert result.error is None

    def test_process_phase_enum(self):
        """ProcessPhase should have correct values."""
        from app.agents.orchestrator import ProcessPhase

        phases = [
            ProcessPhase.ANALYZING,
            ProcessPhase.RETRIEVING,
            ProcessPhase.PLANNING,
            ProcessPhase.EXECUTING,
            ProcessPhase.VALIDATING,
            ProcessPhase.COMPLETED,
            ProcessPhase.FAILED,
        ]

        assert len(phases) >= 6


class TestChatRequest:
    """Unit tests for ChatRequest model."""

    def test_chat_request_defaults(self):
        """ChatRequest should have correct defaults."""
        from app.api.chat import ChatRequest

        request = ChatRequest(message="Hello")

        assert request.message == "Hello"
        assert request.conversation_id is None
        assert request.interactive_mode == False

    def test_chat_request_with_options(self):
        """ChatRequest should accept all options."""
        from app.api.chat import ChatRequest

        request = ChatRequest(
            message="Add feature",
            conversation_id="conv-123",
            interactive_mode=True,
            require_plan_approval=True,
        )

        assert request.interactive_mode == True
        assert request.require_plan_approval == True


class TestPlanApproval:
    """Unit tests for plan approval handling."""

    def test_plan_approval_request(self):
        """PlanApprovalRequest should be structured correctly."""
        from app.api.chat import PlanApprovalRequest

        request = PlanApprovalRequest(
            conversation_id="conv-123",
            approved=True,
        )

        assert request.approved == True
        assert request.modified_plan is None

    def test_plan_rejection(self):
        """Plan rejection should include reason."""
        from app.api.chat import PlanApprovalRequest

        request = PlanApprovalRequest(
            conversation_id="conv-123",
            approved=False,
            rejection_reason="Too many changes",
        )

        assert request.approved == False
        assert request.rejection_reason == "Too many changes"


class TestBatchProcessing:
    """Unit tests for batch processing."""

    def test_batch_request_structure(self):
        """BatchAnalysisRequest should have correct structure."""
        from app.api.chat import BatchAnalysisRequest

        request = BatchAnalysisRequest(
            files=[
                {"path": "app/User.php", "content": "<?php class User {}"},
            ],
            analysis_type="file_analysis",
        )

        assert len(request.files) == 1
        assert request.analysis_type == "file_analysis"

    def test_batch_status_response(self):
        """BatchStatusResponse should have correct structure."""
        from app.api.chat import BatchStatusResponse

        response = BatchStatusResponse(
            id="batch-123",
            status="processing",
            total_requests=10,
            completed_requests=5,
            failed_requests=0,
            total_tokens=10000,
            total_cost=0.05,
        )

        assert response.completed_requests == 5
        assert response.total_cost == 0.05


class TestAgentInfo:
    """Unit tests for agent information."""

    def test_get_all_agents(self):
        """get_all_agents should return agent list."""
        from app.agents.agent_identity import get_all_agents

        agents = get_all_agents()

        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_agent_to_dict(self):
        """Agent should serialize to dict correctly."""
        from app.agents.agent_identity import get_all_agents

        agents = get_all_agents()
        agent_dict = agents[0].to_dict()

        assert "name" in agent_dict
        assert "role" in agent_dict
        assert "color" in agent_dict


class TestOperationsLogger:
    """Unit tests for AI operations logger."""

    def test_start_session(self):
        """start_chat_session should return session ID."""
        from app.services.ai_operations_logger import get_operations_logger

        logger = get_operations_logger()
        session_id = logger.start_chat_session(
            user_id="user-123",
            project_id="project-456",
            conversation_id="conv-789",
        )

        assert session_id is not None
        assert isinstance(session_id, str)

    def test_log_operation(self):
        """log operation should work."""
        from app.services.ai_operations_logger import get_operations_logger, OperationType

        logger = get_operations_logger()
        logger.log(
            operation_type=OperationType.API_CALL,
            message="Test operation",
            user_id="user-123",
            project_id="project-456",
            success=True,
        )

        # Should not raise exception

    def test_get_global_stats(self):
        """get_global_stats should return stats dict."""
        from app.services.ai_operations_logger import get_operations_logger

        logger = get_operations_logger()
        stats = logger.get_global_stats()

        assert isinstance(stats, dict)
