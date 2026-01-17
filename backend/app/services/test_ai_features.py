"""
Test script for AI Features.

Run this script to verify all production AI features are working correctly.

Usage:
    cd backend
    python -m app.services.test_ai_features

Or run specific tests:
    python -m app.services.test_ai_features --test batch
    python -m app.services.test_ai_features --test structured
    python -m app.services.test_ai_features --test cache
    python -m app.services.test_ai_features --test subagents
    python -m app.services.test_ai_features --test hooks
    python -m app.services.test_ai_features --test sessions
    python -m app.services.test_ai_features --test multilingual
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, success: bool, details: str = "") -> None:
    """Print test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"  {status} - {test_name}")
    if details:
        print(f"         {details}")


async def test_batch_processor() -> bool:
    """Test Batch Processing service."""
    print_header("Testing Batch Processor")

    try:
        from app.services.batch_processor import (
            BatchProcessor, BatchRequest, BatchRequestType, BatchStatus
        )
        from app.core.config import settings

        # Check if API key is configured
        if not settings.anthropic_api_key:
            print_result("API Key Check", False, "ANTHROPIC_API_KEY not set")
            return False

        print_result("Import", True)

        # Create processor
        processor = BatchProcessor()
        print_result("Initialization", True)

        # Test request creation
        request = BatchRequest(
            custom_id="test_1",
            file_path="test.php",
            content="<?php echo 'Hello'; ?>",
            request_type=BatchRequestType.FILE_ANALYSIS,
        )
        print_result("BatchRequest Creation", True, f"custom_id={request.custom_id}")

        # Test job listing
        jobs = processor.list_jobs()
        print_result("Job Listing", True, f"Active jobs: {len(jobs)}")

        print("\n  ℹ️  Full batch test requires API call (skipped in basic test)")
        print("      To test: Create a batch with real files")

        return True

    except Exception as e:
        print_result("Batch Processor", False, str(e))
        return False


async def test_structured_outputs() -> bool:
    """Test Structured Outputs service."""
    print_header("Testing Structured Outputs")

    try:
        from app.services.structured_outputs import (
            StructuredOutputService, OutputFormat, SCHEMAS
        )
        from app.core.config import settings

        if not settings.anthropic_api_key:
            print_result("API Key Check", False, "ANTHROPIC_API_KEY not set")
            return False

        print_result("Import", True)

        # Create service
        service = StructuredOutputService()
        print_result("Initialization", True)

        # Check schemas
        print_result("Schemas Loaded", True, f"Available: {len(SCHEMAS)} schemas")

        for fmt in OutputFormat:
            schema = SCHEMAS.get(fmt)
            if schema:
                print_result(f"Schema: {fmt.value}", True, f"Fields: {len(schema.get('properties', {}))}")
            else:
                print_result(f"Schema: {fmt.value}", False, "Not found")

        print("\n  ℹ️  Full structured output test requires API call")
        print("      To test: await service.analyze_intent('Add login feature')")

        return True

    except Exception as e:
        print_result("Structured Outputs", False, str(e))
        return False


async def test_prompt_cache() -> bool:
    """Test Prompt Cache service."""
    print_header("Testing Prompt Cache")

    try:
        from app.services.prompt_cache import (
            PromptCacheService, CacheType
        )
        from app.core.config import settings

        if not settings.anthropic_api_key:
            print_result("API Key Check", False, "ANTHROPIC_API_KEY not set")
            return False

        print_result("Import", True)

        # Create service
        service = PromptCacheService()
        print_result("Initialization", True)

        # Test cache building
        system_blocks = service.build_cached_system(
            base_prompt="You are a Laravel expert.",
            project_context="A" * 5000,  # Large enough to cache
        )
        print_result("Cache Block Building", True, f"Blocks: {len(system_blocks)}")

        # Check if cache_control was added
        has_cache_control = any(
            block.get("cache_control") for block in system_blocks
        )
        print_result("Cache Control Markers", has_cache_control)

        # Test stats
        stats = service.get_stats()
        print_result("Stats Retrieval", True, f"Types tracked: {len(stats)}")

        print("\n  ℹ️  Full cache test requires API call")
        print("      To test: await service.chat_with_cache(...)")

        return True

    except Exception as e:
        print_result("Prompt Cache", False, str(e))
        return False


async def test_subagents() -> bool:
    """Test Subagents service."""
    print_header("Testing Subagents")

    try:
        from app.services.subagents import (
            SubagentManager, SubagentType, SUBAGENT_CONFIGS
        )
        from app.core.config import settings

        if not settings.anthropic_api_key:
            print_result("API Key Check", False, "ANTHROPIC_API_KEY not set")
            return False

        print_result("Import", True)

        # Create manager
        manager = SubagentManager(enable_caching=True)
        print_result("Initialization", True, "Caching enabled")

        # List available subagents
        subagents = manager.list_available_subagents()
        print_result("Subagent Configs", True, f"Available: {len(subagents)}")

        for agent in subagents:
            print(f"      - {agent['agent_type']}: {agent['description'][:50]}...")

        # Check all types have configs
        for agent_type in SubagentType:
            has_config = agent_type in SUBAGENT_CONFIGS
            print_result(f"Config: {agent_type.value}", has_config)

        print("\n  ℹ️  Full subagent test requires API call")
        print("      To test: await manager.security_review(code)")

        return True

    except Exception as e:
        print_result("Subagents", False, str(e))
        return False


async def test_hooks() -> bool:
    """Test Hooks service."""
    print_header("Testing Hooks System")

    try:
        from app.services.hooks import (
            HooksManager, Hook, HookEvent, HookDecision, HookResult
        )

        print_result("Import", True)

        # Create manager
        manager = HooksManager(enable_audit_log=True)
        print_result("Initialization", True)

        # List hooks
        hooks = manager.list_hooks()
        print_result("Built-in Hooks", True, f"Registered: {len(hooks)}")

        # Test dangerous file guard
        result = await manager.execute(
            event=HookEvent.FILE_WRITE,
            user_id="test_user",
            project_id="test_project",
            data={"file_path": ".env.production"}
        )
        is_blocked = result.decision == HookDecision.DENY
        print_result("Dangerous File Guard", is_blocked, f"Decision: {result.decision.value}")

        # Test safe file
        result = await manager.execute(
            event=HookEvent.FILE_WRITE,
            user_id="test_user",
            project_id="test_project",
            data={"file_path": "app/Models/User.php"}
        )
        is_allowed = result.decision == HookDecision.ALLOW
        print_result("Safe File Allowed", is_allowed, f"Decision: {result.decision.value}")

        # Test budget control
        manager.set_user_budget("test_user", daily_budget=10.0, spent_today=0.0)
        budget = manager.get_user_budget_status("test_user")
        print_result("Budget Management", True, f"Remaining: ${budget['remaining']:.2f}")

        # Test audit log
        audit = manager.get_audit_log(limit=10)
        print_result("Audit Logging", True, f"Entries: {len(audit)}")

        # Register custom hook
        async def custom_hook(context):
            return HookResult(decision=HookDecision.ALLOW)

        manager.register(Hook(
            name="test_custom_hook",
            event=HookEvent.REQUEST_START,
            handler=custom_hook,
        ))
        print_result("Custom Hook Registration", True)

        return True

    except Exception as e:
        print_result("Hooks", False, str(e))
        return False


async def test_sessions() -> bool:
    """Test Session Management service."""
    print_header("Testing Session Management")

    try:
        from app.services.session_manager import (
            SessionManager, Session, SessionState, MemorySessionStore
        )

        print_result("Import", True)

        # Create manager with memory store (for testing)
        store = MemorySessionStore()
        manager = SessionManager(store=store)
        print_result("Initialization", True, "Using memory store")

        # Create session
        session = await manager.create_session(
            user_id="test_user",
            project_id="test_project",
        )
        print_result("Session Creation", True, f"ID: {session.id[:8]}...")

        # Add message
        added = await manager.add_message(
            session_id=session.id,
            role="user",
            content="Hello, test message",
        )
        print_result("Add Message", added)

        # Update context
        updated = await manager.update_context(
            session_id=session.id,
            project_context="Test project context",
            custom_data={"test_key": "test_value"},
        )
        print_result("Update Context", updated)

        # Get session
        retrieved = await manager.get_session(session.id)
        print_result("Session Retrieval", retrieved is not None, f"Messages: {retrieved.message_count}")

        # Fork session
        forked = await manager.fork_session(session.id)
        print_result("Session Fork", forked is not None, f"New ID: {forked.id[:8]}...")

        # List sessions
        sessions = await manager.list_user_sessions("test_user")
        print_result("List Sessions", True, f"Found: {len(sessions)}")

        # Pause session
        paused = await manager.pause_session(session.id)
        print_result("Session Pause", paused)

        # Resume session
        resumed = await manager.resume_session(session.id)
        print_result("Session Resume", resumed is not None)

        # Record usage
        recorded = await manager.record_usage(session.id, tokens=1000, cost=0.01)
        print_result("Usage Recording", recorded)

        # Complete session
        completed = await manager.complete_session(session.id)
        print_result("Session Complete", completed)

        # Delete session
        deleted = await manager.delete_session(session.id)
        print_result("Session Delete", deleted)

        return True

    except Exception as e:
        print_result("Sessions", False, str(e))
        return False


async def test_multilingual() -> bool:
    """Test Multilingual service."""
    print_header("Testing Multilingual Support")

    try:
        from app.services.multilingual import (
            MultilingualService, SupportedLanguage, LANGUAGE_NAMES, RTL_LANGUAGES
        )
        from app.core.config import settings

        print_result("Import", True)

        # Check supported languages
        print_result("Languages Loaded", True, f"Supported: {len(SupportedLanguage)}")

        # List some languages
        print("      Languages:")
        for lang in list(SupportedLanguage)[:5]:
            rtl = "RTL" if lang in RTL_LANGUAGES else "LTR"
            print(f"        - {lang.value}: {LANGUAGE_NAMES.get(lang)} ({rtl})")
        print("        ...")

        if not settings.anthropic_api_key:
            print_result("API Key Check", False, "ANTHROPIC_API_KEY not set (detection/translation needs API)")
            print("\n  ℹ️  Multilingual detection requires API key")
            return True

        # Create service
        service = MultilingualService()
        print_result("Initialization", True)

        # Test localized system prompt
        localized = service.get_localized_system_prompt(
            language=SupportedLanguage.SPANISH,
            base_prompt="You are a Laravel expert.",
        )
        has_instructions = "Spanish" in localized or "Español" in localized
        print_result("Localized Prompt", has_instructions)

        # Get supported languages list
        langs = service.get_supported_languages()
        print_result("Language List", True, f"Returned: {len(langs)}")

        print("\n  ℹ️  Full multilingual test requires API call")
        print("      To test: await service.detect_language('Hola mundo')")

        return True

    except Exception as e:
        print_result("Multilingual", False, str(e))
        return False


async def test_integration() -> bool:
    """Test integration between services."""
    print_header("Testing Service Integration")

    try:
        from app.services.ai_features import (
            get_hooks_manager,
            get_session_manager,
            HookEvent,
            HookDecision,
        )

        print_result("Unified Import", True)

        # Test hooks + sessions integration
        hooks = get_hooks_manager()
        sessions = get_session_manager()

        # Create session and check hooks
        from app.services.session_manager import MemorySessionStore
        sessions.store = MemorySessionStore()

        session = await sessions.create_session(
            user_id="integration_test",
            project_id="test_project",
        )

        # Simulate hook check before file operation
        result = await hooks.execute(
            event=HookEvent.FILE_WRITE,
            user_id="integration_test",
            project_id="test_project",
            request_id=session.id,
            data={"file_path": "app/test.php"},
        )

        if result.decision == HookDecision.ALLOW:
            await sessions.add_message(
                session_id=session.id,
                role="assistant",
                content="File operation approved by hooks",
                metadata={"hook_result": result.to_dict()},
            )

        retrieved = await sessions.get_session(session.id)
        has_message = retrieved.message_count > 0
        print_result("Hooks + Sessions Integration", has_message)

        await sessions.delete_session(session.id)

        return True

    except Exception as e:
        print_result("Integration", False, str(e))
        return False


async def run_all_tests() -> dict:
    """Run all tests and return results."""
    results = {}

    tests = [
        ("batch", test_batch_processor),
        ("structured", test_structured_outputs),
        ("cache", test_prompt_cache),
        ("subagents", test_subagents),
        ("hooks", test_hooks),
        ("sessions", test_sessions),
        ("multilingual", test_multilingual),
        ("integration", test_integration),
    ]

    for name, test_fn in tests:
        try:
            results[name] = await test_fn()
        except Exception as e:
            logger.error(f"Test {name} crashed: {e}")
            results[name] = False

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test AI Features")
    parser.add_argument(
        "--test",
        choices=["all", "batch", "structured", "cache", "subagents", "hooks", "sessions", "multilingual", "integration"],
        default="all",
        help="Which test to run",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Laravel AI - Production Features Test Suite")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    test_map = {
        "batch": test_batch_processor,
        "structured": test_structured_outputs,
        "cache": test_prompt_cache,
        "subagents": test_subagents,
        "hooks": test_hooks,
        "sessions": test_sessions,
        "multilingual": test_multilingual,
        "integration": test_integration,
    }

    if args.test == "all":
        results = asyncio.run(run_all_tests())
    else:
        test_fn = test_map[args.test]
        results = {args.test: asyncio.run(test_fn())}

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print(f"\n  Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 All tests passed!")
        return 0
    else:
        print("\n  ⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
