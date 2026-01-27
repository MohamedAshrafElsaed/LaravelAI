"""
Custom exceptions for the agent system.
"""
from typing import Optional, List, Dict, Any


class AgentException(Exception):
    """Base exception for all agent errors."""

    def __init__(
            self,
            message: str,
            agent: str,
            recoverable: bool = False,
            details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.agent = agent
        self.recoverable = recoverable
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.message,
            "agent": self.agent,
            "recoverable": self.recoverable,
            "details": self.details
        }


class InsufficientContextError(AgentException):
    """Raised when context retrieval returns insufficient results."""

    def __init__(
            self,
            message: str = "Insufficient codebase context to proceed safely",
            chunks_found: int = 0,
            queries_tried: Optional[List[str]] = None
    ):
        super().__init__(
            message=message,
            agent="context_retriever",
            recoverable=True,
            details={
                "chunks_found": chunks_found,
                "queries_tried": queries_tried or [],
                "suggestion": "Ensure the project is indexed and try more specific queries"
            }
        )


class FileNotFoundForModifyError(AgentException):
    """Raised when trying to modify a file that doesn't exist."""

    def __init__(self, file_path: str):
        super().__init__(
            message=f"Cannot modify file '{file_path}' - not found in codebase index",
            agent="executor",
            recoverable=True,
            details={
                "file_path": file_path,
                "suggestion": "Use 'create' action instead, or ensure the file is indexed"
            }
        )


class ValidationDegradationError(AgentException):
    """Raised when fix attempts make the code worse."""

    def __init__(self, initial_score: int, current_score: int, attempts: int):
        super().__init__(
            message=f"Validation score degraded from {initial_score} to {current_score} after {attempts} fix attempts",
            agent="orchestrator",
            recoverable=False,
            details={
                "initial_score": initial_score,
                "current_score": current_score,
                "attempts": attempts,
                "suggestion": "Manual review required - automated fixes are not improving the code"
            }
        )


class ContradictoryValidationError(AgentException):
    """Raised when validator gives contradictory feedback."""

    def __init__(self, contradictions: List[Dict[str, str]]):
        super().__init__(
            message="Validator provided contradictory feedback across iterations",
            agent="validator",
            recoverable=True,
            details={
                "contradictions": contradictions,
                "suggestion": "Review validation criteria for consistency"
            }
        )
