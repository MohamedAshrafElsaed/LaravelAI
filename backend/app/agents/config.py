"""
Agent Configuration - Centralized settings for all agents.
"""
import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for the agent system."""

    # Context Retrieval Thresholds
    MIN_CONTEXT_CHUNKS: int = 1  # Minimum chunks required to proceed
    WARN_CONTEXT_CHUNKS: int = 3  # Warn if below this threshold
    CONTEXT_SCORE_THRESHOLD: float = 0.2  # Lower threshold for vector search
    CONTEXT_RETRY_THRESHOLD: float = 0.1  # Even lower for retry
    MAX_CONTEXT_RETRIES: int = 2

    # Validation Thresholds
    MIN_VALIDATION_SCORE: int = 50  # Abort if score below this
    SCORE_DEGRADATION_THRESHOLD: int = 5  # Abort if score drops by this much
    MAX_FIX_ATTEMPTS: int = 3

    # Critical Failure Auto-Fix
    ENABLE_AUTO_FIX_CRITICAL: bool = True  # Auto-fix even on critical failures (score=0)
    CRITICAL_FAILURE_THRESHOLD: int = 10  # Score at or below this is considered critical
    REGENERATE_ON_DELETION: bool = True  # Regenerate file if entirely deleted

    # Execution Settings
    REQUIRE_FILE_EXISTS_FOR_MODIFY: bool = True
    ENABLE_SELF_VERIFICATION: bool = True
    ENABLE_CONTRADICTION_DETECTION: bool = True

    # Safety Settings
    ABORT_ON_NO_CONTEXT: bool = True  # Critical: prevents hallucination
    ABORT_ON_SCORE_DEGRADATION: bool = True
    REQUIRE_EXPLICIT_CONFIRMATION_FOR_DESTRUCTIVE: bool = True

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            MIN_CONTEXT_CHUNKS=int(os.getenv("AGENT_MIN_CONTEXT_CHUNKS", "1")),
            WARN_CONTEXT_CHUNKS=int(os.getenv("AGENT_WARN_CONTEXT_CHUNKS", "3")),
            ABORT_ON_NO_CONTEXT=os.getenv("AGENT_ABORT_ON_NO_CONTEXT", "true").lower() == "true",
            MAX_FIX_ATTEMPTS=int(os.getenv("AGENT_MAX_FIX_ATTEMPTS", "3")),
            MIN_VALIDATION_SCORE=int(os.getenv("AGENT_MIN_VALIDATION_SCORE", "50")),
            SCORE_DEGRADATION_THRESHOLD=int(os.getenv("AGENT_SCORE_DEGRADATION_THRESHOLD", "5")),
            ABORT_ON_SCORE_DEGRADATION=os.getenv("AGENT_ABORT_ON_SCORE_DEGRADATION", "true").lower() == "true",
            REQUIRE_FILE_EXISTS_FOR_MODIFY=os.getenv("AGENT_REQUIRE_FILE_EXISTS_FOR_MODIFY", "true").lower() == "true",
            ENABLE_SELF_VERIFICATION=os.getenv("AGENT_ENABLE_SELF_VERIFICATION", "true").lower() == "true",
            ENABLE_CONTRADICTION_DETECTION=os.getenv("AGENT_ENABLE_CONTRADICTION_DETECTION", "true").lower() == "true",
            ENABLE_AUTO_FIX_CRITICAL=os.getenv("AGENT_ENABLE_AUTO_FIX_CRITICAL", "true").lower() == "true",
            CRITICAL_FAILURE_THRESHOLD=int(os.getenv("AGENT_CRITICAL_FAILURE_THRESHOLD", "10")),
            REGENERATE_ON_DELETION=os.getenv("AGENT_REGENERATE_ON_DELETION", "true").lower() == "true",
        )


# Global config instance
agent_config = AgentConfig.from_env()
