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

    # App
    app_name: str = "Laravel AI"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

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
    openai_embedding_model: str = "text-embedding-3-small"

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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()