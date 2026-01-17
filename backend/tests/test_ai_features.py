"""
Unit tests for AI Features.

Run with: pytest tests/test_ai_features.py -v
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch


# =============================================================================
# Hooks Tests
# =============================================================================

class TestHooks:
    """Tests for Hooks service."""

    @pytest.fixture
    def hooks_manager(self):
        from app.services.hooks import HooksManager
        return HooksManager(enable_audit_log=True)

    @pytest.mark.asyncio
    async def test_dangerous_file_blocked(self, hooks_manager):
        """Test that dangerous file operations are blocked."""
        from app.services.hooks import HookEvent, HookDecision

        result = await hooks_manager.execute(
            event=HookEvent.FILE_WRITE,
            user_id="test_user",
            data={"file_path": ".env.production"}
        )

        assert result.decision == HookDecision.DENY
        assert "sensitive" in result.reason.lower() or "blocked" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_safe_file_allowed(self, hooks_manager):
        """Test that safe file operations are allowed."""
        from app.services.hooks import HookEvent, HookDecision

        result = await hooks_manager.execute(
            event=HookEvent.FILE_WRITE,
            user_id="test_user",
            data={"file_path": "app/Models/User.php"}
        )

        assert result.decision == HookDecision.ALLOW

    @pytest.mark.asyncio
    async def test_critical_file_delete_blocked(self, hooks_manager):
        """Test that deletion of critical files is blocked."""
        from app.services.hooks import HookEvent, HookDecision

        result = await hooks_manager.execute(
            event=HookEvent.FILE_DELETE,
            user_id="test_user",
            data={"file_path": "composer.json"}
        )

        assert result.decision == HookDecision.DENY

    def test_budget_management(self, hooks_manager):
        """Test user budget management."""
        hooks_manager.set_user_budget("user1", daily_budget=10.0, spent_today=0.0)

        status = hooks_manager.get_user_budget_status("user1")
        assert status["daily_budget"] == 10.0
        assert status["remaining"] == 10.0

        hooks_manager.record_user_spending("user1", 3.5)
        status = hooks_manager.get_user_budget_status("user1")
        assert status["spent_today"] == 3.5
        assert status["remaining"] == 6.5

    @pytest.mark.asyncio
    async def test_custom_hook_registration(self, hooks_manager):
        """Test registering and executing custom hooks."""
        from app.services.hooks import Hook, HookEvent, HookDecision, HookResult

        call_count = 0

        async def custom_handler(context):
            nonlocal call_count
            call_count += 1
            return HookResult(decision=HookDecision.ALLOW)

        hooks_manager.register(Hook(
            name="test_hook",
            event=HookEvent.REQUEST_START,
            handler=custom_handler,
        ))

        await hooks_manager.execute(
            event=HookEvent.REQUEST_START,
            user_id="test_user",
        )

        assert call_count == 1

    def test_audit_log(self, hooks_manager):
        """Test audit log retrieval."""
        audit = hooks_manager.get_audit_log(limit=10)
        assert isinstance(audit, list)


# =============================================================================
# Session Management Tests
# =============================================================================

class TestSessionManagement:
    """Tests for Session Management service."""

    @pytest.fixture
    def session_manager(self):
        from app.services.session_manager import SessionManager, MemorySessionStore
        return SessionManager(store=MemorySessionStore())

    @pytest.mark.asyncio
    async def test_session_creation(self, session_manager):
        """Test creating a new session."""
        session = await session_manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )

        assert session.id is not None
        assert session.user_id == "test_user"
        assert session.project_id == "test_project"
        assert session.state.value == "active"

    @pytest.mark.asyncio
    async def test_session_message_handling(self, session_manager):
        """Test adding messages to session."""
        session = await session_manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )

        success = await session_manager.add_message(
            session_id=session.id,
            role="user",
            content="Test message",
        )

        assert success is True

        retrieved = await session_manager.get_session(session.id)
        assert retrieved.message_count == 1
        assert retrieved.messages[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_session_context_update(self, session_manager):
        """Test updating session context."""
        session = await session_manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )

        success = await session_manager.update_context(
            session_id=session.id,
            project_context="Test context",
            custom_data={"key": "value"},
        )

        assert success is True

        retrieved = await session_manager.get_session(session.id)
        assert retrieved.context.project_context == "Test context"
        assert retrieved.context.custom_data["key"] == "value"

    @pytest.mark.asyncio
    async def test_session_fork(self, session_manager):
        """Test forking a session."""
        session = await session_manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )

        await session_manager.add_message(
            session_id=session.id,
            role="user",
            content="Message 1",
        )

        await session_manager.add_message(
            session_id=session.id,
            role="assistant",
            content="Response 1",
        )

        forked = await session_manager.fork_session(session.id, fork_point=1)

        assert forked is not None
        assert forked.id != session.id
        assert forked.parent_session_id == session.id
        assert forked.message_count == 1

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, session_manager):
        """Test session pause, resume, complete lifecycle."""
        session = await session_manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )

        # Pause
        paused = await session_manager.pause_session(session.id)
        assert paused is True

        retrieved = await session_manager.get_session(session.id)
        assert retrieved.state.value == "paused"

        # Resume
        resumed = await session_manager.resume_session(session.id)
        assert resumed is not None
        assert resumed.state.value == "active"

        # Complete
        completed = await session_manager.complete_session(session.id)
        assert completed is True

        retrieved = await session_manager.get_session(session.id)
        assert retrieved.state.value == "completed"

    @pytest.mark.asyncio
    async def test_session_usage_tracking(self, session_manager):
        """Test recording token usage."""
        session = await session_manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )

        await session_manager.record_usage(session.id, tokens=500, cost=0.005)
        await session_manager.record_usage(session.id, tokens=300, cost=0.003)

        retrieved = await session_manager.get_session(session.id)
        assert retrieved.total_tokens_used == 800
        assert retrieved.total_cost == 0.008


# =============================================================================
# Structured Outputs Tests
# =============================================================================

class TestStructuredOutputs:
    """Tests for Structured Outputs service."""

    def test_schemas_loaded(self):
        """Test that all schemas are loaded."""
        from app.services.structured_outputs import SCHEMAS, OutputFormat

        for fmt in OutputFormat:
            assert fmt in SCHEMAS, f"Schema missing for {fmt}"

    def test_schema_structure(self):
        """Test schema structure validity."""
        from app.services.structured_outputs import SCHEMAS, OutputFormat

        for fmt, schema in SCHEMAS.items():
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema


# =============================================================================
# Batch Processor Tests
# =============================================================================

class TestBatchProcessor:
    """Tests for Batch Processor service."""

    def test_batch_request_creation(self):
        """Test creating batch requests."""
        from app.services.batch_processor import BatchRequest, BatchRequestType

        request = BatchRequest(
            custom_id="test_1",
            file_path="test.php",
            content="<?php echo 'test'; ?>",
            request_type=BatchRequestType.SECURITY_SCAN,
        )

        assert request.custom_id == "test_1"
        assert request.file_path == "test.php"
        assert request.request_type == BatchRequestType.SECURITY_SCAN

    def test_batch_job_serialization(self):
        """Test batch job serialization."""
        from app.services.batch_processor import BatchJob, BatchStatus

        job = BatchJob(
            id="test-job-123",
            status=BatchStatus.PROCESSING,
            total_requests=10,
            completed_requests=5,
        )

        data = job.to_dict()
        assert data["id"] == "test-job-123"
        assert data["status"] == "processing"
        assert data["total_requests"] == 10


# =============================================================================
# Prompt Cache Tests
# =============================================================================

class TestPromptCache:
    """Tests for Prompt Cache service."""

    def test_cache_block_building(self):
        """Test building cache blocks."""
        from app.services.prompt_cache import PromptCacheService

        # Mock API key for testing
        with patch.object(PromptCacheService, '__init__', lambda self, **kwargs: None):
            service = PromptCacheService.__new__(PromptCacheService)
            service.api_key = "test"
            service._content_cache = {}
            service._stats = {}

            # Large enough to cache (>1024 tokens estimated)
            large_context = "A" * 5000

            blocks = service.build_cached_system(
                base_prompt="Test prompt",
                project_context=large_context,
            )

            # Should have cache_control on large content
            has_cache = any(
                block.get("cache_control") for block in blocks
            )
            assert has_cache is True


# =============================================================================
# Subagents Tests
# =============================================================================

class TestSubagents:
    """Tests for Subagents service."""

    def test_subagent_configs_complete(self):
        """Test all subagent types have configs."""
        from app.services.subagents import SubagentType, SUBAGENT_CONFIGS

        for agent_type in SubagentType:
            assert agent_type in SUBAGENT_CONFIGS, f"Config missing for {agent_type}"

    def test_subagent_config_structure(self):
        """Test subagent config structure."""
        from app.services.subagents import SUBAGENT_CONFIGS

        for agent_type, config in SUBAGENT_CONFIGS.items():
            assert config.agent_type == agent_type
            assert config.description
            assert config.system_prompt
            assert config.model


# =============================================================================
# Multilingual Tests
# =============================================================================

class TestMultilingual:
    """Tests for Multilingual service."""

    def test_supported_languages(self):
        """Test supported languages list."""
        from app.services.multilingual import SupportedLanguage, LANGUAGE_NAMES

        assert len(SupportedLanguage) >= 15

        for lang in SupportedLanguage:
            assert lang in LANGUAGE_NAMES

    def test_rtl_languages(self):
        """Test RTL language identification."""
        from app.services.multilingual import SupportedLanguage, RTL_LANGUAGES

        assert SupportedLanguage.ARABIC in RTL_LANGUAGES

    def test_localized_prompt_generation(self):
        """Test generating localized prompts."""
        from app.services.multilingual import MultilingualService, SupportedLanguage

        # Mock API key for testing
        with patch.object(MultilingualService, '__init__', lambda self, **kwargs: None):
            service = MultilingualService.__new__(MultilingualService)
            service.default_language = SupportedLanguage.ENGLISH

            prompt = service.get_localized_system_prompt(
                language=SupportedLanguage.SPANISH,
                base_prompt="You are a Laravel expert.",
            )

            assert "Language Instructions" in prompt


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests between services."""

    @pytest.mark.asyncio
    async def test_hooks_with_sessions(self):
        """Test hooks and sessions working together."""
        from app.services.hooks import HooksManager, HookEvent, HookDecision
        from app.services.session_manager import SessionManager, MemorySessionStore

        hooks = HooksManager()
        sessions = SessionManager(store=MemorySessionStore())

        # Create session
        session = await sessions.create_session(
            user_id="integration_user",
            project_id="test_project",
        )

        # Check hook before operation
        result = await hooks.execute(
            event=HookEvent.FILE_WRITE,
            user_id="integration_user",
            request_id=session.id,
            data={"file_path": "safe_file.php"},
        )

        # If allowed, record in session
        if result.decision == HookDecision.ALLOW:
            await sessions.add_message(
                session_id=session.id,
                role="system",
                content="File operation approved",
            )

        retrieved = await sessions.get_session(session.id)
        assert retrieved.message_count == 1
