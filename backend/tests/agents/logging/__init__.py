"""
Agent logging infrastructure for exhaustive test logging.

This module provides comprehensive logging capabilities for tracking
every operation, prompt, response, file access, and data transfer
during multi-agent test execution.
"""

from .log_schemas import (
    LogEntry,
    AgentExecutionLog,
    ClaudeCallLog,
    ContextRetrievalLog,
    FileAccessLog,
    ErrorLog,
    MetricsSummary,
)
from .agent_logger import AgentLogger
from .instrumented_claude import InstrumentedClaudeService
from .report_generator import ReportGenerator

__all__ = [
    "LogEntry",
    "AgentExecutionLog",
    "ClaudeCallLog",
    "ContextRetrievalLog",
    "FileAccessLog",
    "ErrorLog",
    "MetricsSummary",
    "AgentLogger",
    "InstrumentedClaudeService",
    "ReportGenerator",
]
