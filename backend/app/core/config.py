"""
Application configuration using Pydantic Settings.
Loads from environment variables with validation.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Agent Model Selection
    nova_model: str = "opus"          # Intent Analyzer model
    blueprint_model: str = "opus"   # Planner model (NEW)
    scout_model: str = "opus"        # Context Retriever model (for future use)
    forge_model: str = "opus"       # Executor model (for future use)
    guardian_model: str = "opus"     # Validator model (for future use)

    # App
    app_name: str = "Laravel AI"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    cors_origins: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]
    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/laravelai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/auth/github/callback"

    # Anthropic
    anthropic_api_key: str = ""
    claude_intent_model: str = "claude-haiku-4-5-20251001"
    claude_execution_model: str = "claude-sonnet-4-5-20250929"

    # Qdrant
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "laravel_code"

    # OpenAI (for embeddings)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-large"

    # Voyage AI (alternative embeddings provider)
    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-code-3"

    # Embedding provider selection: "openai" or "voyage"
    embedding_provider: str = "openai"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # Logging
    log_level: str = "INFO"
    log_dir: str = ""  # Empty means console only, set to path for file logging
    log_json: bool = False  # Use JSON format for logs (recommended for production)

    # Batch Processing
    batch_processing_enabled: bool = True
    batch_max_size: int = 100
    batch_poll_interval_seconds: int = 5

    # Prompt Caching
    prompt_caching_enabled: bool = True
    prompt_cache_min_tokens: int = 1024  # Minimum tokens to cache

    # Subagents
    subagents_enabled: bool = True
    subagents_enable_caching: bool = True

    # Hooks
    hooks_enabled: bool = True
    hooks_audit_log_enabled: bool = True
    hooks_max_audit_entries: int = 10000
    hooks_default_user_daily_budget: float = 10.0  # Default $10/day per user

    # Session Management
    sessions_enabled: bool = True
    sessions_storage_dir: str = "/tmp/laravelai_sessions"
    sessions_default_ttl_hours: int = 24
    sessions_max_messages: int = 100

    # Multilingual Support
    multilingual_enabled: bool = True
    multilingual_default_language: str = "en"
    multilingual_auto_detect: bool = True
    multilingual_translate_responses: bool = False  # Set to True to auto-translate

    # Structured Outputs
    structured_outputs_enabled: bool = True
    structured_outputs_strict_validation: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()