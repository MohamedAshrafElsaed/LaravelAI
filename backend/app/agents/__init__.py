"""
AI Agents for Laravel code assistance.

This package contains specialized agents that work together to analyze,
plan, and execute code modifications for Laravel projects.

UPDATED: Includes configuration and exception classes.
"""
from app.agents.config import AgentConfig, agent_config
from app.agents.context_retriever import ContextRetriever, RetrievedContext, CodeChunk
from app.agents.exceptions import (
    AgentException,
    InsufficientContextError,
    FileNotFoundForModifyError,
    ValidationDegradationError,
    ContradictoryValidationError,
)
from app.agents.executor import Executor, ExecutionResult
from app.agents.intent_analyzer import IntentAnalyzer, Intent
from app.agents.orchestrator import Orchestrator, ProcessResult, ProcessPhase, ProcessEvent
from app.agents.planner import Planner, Plan, PlanStep
from app.agents.validator import Validator, ValidationResult, ValidationIssue

__all__ = [
    # Configuration
    "AgentConfig",
    "agent_config",
    # Exceptions
    "AgentException",
    "InsufficientContextError",
    "FileNotFoundForModifyError",
    "ValidationDegradationError",
    "ContradictoryValidationError",
    # Intent Analysis
    "IntentAnalyzer",
    "Intent",
    # Context Retrieval
    "ContextRetriever",
    "RetrievedContext",
    "CodeChunk",
    # Planning
    "Planner",
    "Plan",
    "PlanStep",
    # Execution
    "Executor",
    "ExecutionResult",
    # Validation
    "Validator",
    "ValidationResult",
    "ValidationIssue",
    # Orchestration
    "Orchestrator",
    "ProcessResult",
    "ProcessPhase",
    "ProcessEvent",
]
