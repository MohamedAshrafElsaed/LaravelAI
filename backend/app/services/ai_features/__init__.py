"""
AI Features Package.

Production-ready AI features for the Laravel AI Assistant:
- Batch Processing: Bulk file analysis with 50% cost savings
- Structured Outputs: Guaranteed JSON response formats
- Prompt Caching: 90% cost reduction on repeated context
- Subagents: Specialized agents for security, performance, testing
- Hooks: Control and audit logging for AI operations
- Session Management: Conversation continuity and forking
- Multilingual Support: 15+ language support

Usage:
    from app.services.ai_features import (
        BatchProcessor,
        StructuredOutputService,
        PromptCacheService,
        SubagentManager,
        HooksManager,
        SessionManager,
        MultilingualService,
    )
"""

# Batch Processing
from app.services.batch_processor import (
    BatchProcessor,
    BatchJob,
    BatchRequest,
    BatchResult,
    BatchStatus,
    BatchRequestType,
    get_batch_processor,
)

# Structured Outputs
from app.services.structured_outputs import (
    StructuredOutputService,
    StructuredResponse,
    OutputFormat,
    SCHEMAS,
    get_structured_output_service,
)

# Prompt Caching
from app.services.prompt_cache import (
    PromptCacheService,
    CachedPromptResponse,
    CachedContent,
    CacheStats,
    CacheType,
    get_prompt_cache_service,
)

# Subagents
from app.services.subagents import (
    SubagentManager,
    Subagent,
    SubagentConfig,
    SubagentResult,
    SubagentType,
    SubagentModel,
    SUBAGENT_CONFIGS,
    get_subagent_manager,
)

# Hooks
from app.services.hooks import (
    HooksManager,
    Hook,
    HookEvent,
    HookDecision,
    HookContext,
    HookResult,
    AuditLogEntry,
    with_hooks,
    get_hooks_manager,
)

# Session Management
from app.services.session_manager import (
    SessionManager,
    Session,
    SessionState,
    SessionMessage,
    SessionContext,
    SessionStore,
    FileSessionStore,
    MemorySessionStore,
    get_session_manager,
)

# Multilingual Support
from app.services.multilingual import (
    MultilingualService,
    LanguageDetectionResult,
    TranslationResult,
    LocalizedResponse,
    SupportedLanguage,
    LANGUAGE_NAMES,
    RTL_LANGUAGES,
    get_multilingual_service,
)

__all__ = [
    # Batch Processing
    "BatchProcessor",
    "BatchJob",
    "BatchRequest",
    "BatchResult",
    "BatchStatus",
    "BatchRequestType",
    "get_batch_processor",

    # Structured Outputs
    "StructuredOutputService",
    "StructuredResponse",
    "OutputFormat",
    "SCHEMAS",
    "get_structured_output_service",

    # Prompt Caching
    "PromptCacheService",
    "CachedPromptResponse",
    "CachedContent",
    "CacheStats",
    "CacheType",
    "get_prompt_cache_service",

    # Subagents
    "SubagentManager",
    "Subagent",
    "SubagentConfig",
    "SubagentResult",
    "SubagentType",
    "SubagentModel",
    "SUBAGENT_CONFIGS",
    "get_subagent_manager",

    # Hooks
    "HooksManager",
    "Hook",
    "HookEvent",
    "HookDecision",
    "HookContext",
    "HookResult",
    "AuditLogEntry",
    "with_hooks",
    "get_hooks_manager",

    # Session Management
    "SessionManager",
    "Session",
    "SessionState",
    "SessionMessage",
    "SessionContext",
    "SessionStore",
    "FileSessionStore",
    "MemorySessionStore",
    "get_session_manager",

    # Multilingual Support
    "MultilingualService",
    "LanguageDetectionResult",
    "TranslationResult",
    "LocalizedResponse",
    "SupportedLanguage",
    "LANGUAGE_NAMES",
    "RTL_LANGUAGES",
    "get_multilingual_service",
]
