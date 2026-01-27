"""
Nova - Intent Analyzer Agent (v2 Enhanced)

Analyzes user input to understand what they want to accomplish.
Uses Claude's Structured Outputs for guaranteed schema compliance.
Implements strict no-guessing policy with clarification halts.

Key Features:
- Integrates with existing Project model (stack, file_stats, structure)
- Uses Orchestrator.build_project_context() for rich Laravel context
- Conversation summary for rolling context (decisions, completed tasks, entities)
- Recent messages for immediate context (last 4 messages)
- Strict structured output validation
- No-guessing policy with clarification questions
- Priority detection (critical/high/medium/low)
- Entity extraction (only explicit mentions)
- Retry with exponential backoff (max 2 retries)
"""
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from pydantic import ValidationError

from app.agents.agent_identity import AgentType, get_agent
from app.agents.conversation_summary import (
    ConversationSummary,
    RecentMessage,
    format_recent_messages,
)
from app.agents.intent_schema import (
    IntentOutput,
    ExtractedEntities,
    get_intent_json_schema,
)
from app.agents.nova_system_prompt import NOVA_SYSTEM_PROMPT
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 2
INITIAL_RETRY_DELAY = 1.0  # seconds
CONFIDENCE_THRESHOLD_FOR_CLARIFICATION = 0.5
NOVA_MODEL = os.getenv("NOVA_MODEL", "opus")

MODEL_MAP = {
    "haiku": ClaudeModel.HAIKU,
    "sonnet": ClaudeModel.SONNET,
    "opus": ClaudeModel.OPUS,
}


@dataclass
class Intent:
    """
    Represents the analyzed intent from user input.

    This is the output passed to downstream agents (Scout, Blueprint, etc.)
    """
    # Core classification
    task_type: str
    task_type_confidence: float

    # Scope and affected areas
    domains_affected: list[str] = field(default_factory=list)
    scope: str = "single_file"
    languages: list[str] = field(default_factory=lambda: ["php"])
    requires_migration: bool = False

    # Priority
    priority: str = "medium"

    # Extracted entities
    entities: dict = field(default_factory=lambda: {
        "files": [], "classes": [], "methods": [], "routes": [], "tables": []
    })

    # Search guidance
    search_queries: list[str] = field(default_factory=list)

    # Reasoning and confidence
    reasoning: str = ""
    overall_confidence: float = 0.0

    # Clarification handling
    needs_clarification: bool = False
    clarifying_questions: list[str] = field(default_factory=list)

    # Metadata
    analysis_time_ms: int = 0
    retry_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_output(cls, output: IntentOutput, analysis_time_ms: int = 0, retry_count: int = 0) -> "Intent":
        """Create Intent from validated IntentOutput."""
        return cls(
            task_type=output.task_type,
            task_type_confidence=output.task_type_confidence,
            domains_affected=output.domains_affected,
            scope=output.scope,
            languages=output.languages,
            requires_migration=output.requires_migration,
            priority=output.priority,
            entities=output.entities.model_dump(),
            search_queries=output.search_queries,
            reasoning=output.reasoning,
            overall_confidence=output.overall_confidence,
            needs_clarification=output.needs_clarification,
            clarifying_questions=output.clarifying_questions,
            analysis_time_ms=analysis_time_ms,
            retry_count=retry_count,
        )

    @classmethod
    def clarification_required(cls, questions: list[str], reasoning: str = "Insufficient information") -> "Intent":
        """Create an Intent that requires clarification (pipeline halt)."""
        return cls(
            task_type="question",
            task_type_confidence=0.3,
            priority="medium",
            reasoning=reasoning,
            overall_confidence=0.2,
            needs_clarification=True,
            clarifying_questions=questions,
            search_queries=[],
        )

    @classmethod
    def error_fallback(cls, error_message: str) -> "Intent":
        """Create a fallback Intent on unrecoverable error (still halts pipeline)."""
        return cls(
            task_type="question",
            task_type_confidence=0.0,
            priority="medium",
            reasoning=f"Analysis failed: {error_message}",
            overall_confidence=0.0,
            needs_clarification=True,
            clarifying_questions=[
                "I encountered an error analyzing your request. Could you please rephrase it?",
                "What specific task would you like me to help with?"
            ],
            search_queries=[],
        )

    def should_halt_pipeline(self) -> bool:
        """Check if pipeline should halt (clarification needed or error)."""
        return self.needs_clarification or self.overall_confidence < CONFIDENCE_THRESHOLD_FOR_CLARIFICATION


class IntentAnalyzer:
    """
    Nova - Analyzes user input to understand their intent.

    Uses Claude Sonnet with Structured Outputs for guaranteed schema compliance.
    Implements strict no-guessing policy - will halt and ask for clarification
    rather than make assumptions.
    """

    def __init__(self, claude_service: Optional[ClaudeService] = None):
        """
        Initialize the intent analyzer.

        Args:
            claude_service: Optional Claude service instance (uses singleton if not provided)
        """
        self.claude = claude_service or get_claude_service()
        self.identity = get_agent(AgentType.NOVA)
        self._schema = get_intent_json_schema()

        logger.info(f"[{self.identity.name.upper()}] Initialized with Sonnet + Structured Outputs")

    def _build_user_prompt(
            self,
            user_input: str,
            project_context: Optional[str] = None,
            conversation_summary: Optional[ConversationSummary] = None,
            recent_messages: Optional[list[RecentMessage]] = None,
    ) -> str:
        """
        Build the user prompt with all context layers.

        Args:
            user_input: Current user message
            project_context: Rich project context from Orchestrator.build_project_context()
                            Already includes: stack, file_stats, structure, ai_context
            conversation_summary: Rolling summary of conversation (decisions, tasks, entities)
            recent_messages: Last 4 messages for immediate context

        Returns:
            Formatted user prompt
        """
        parts = []

        # 1. Project context (from Orchestrator - includes Laravel info)
        if project_context:
            parts.append(f"<project_context>\n{project_context}\n</project_context>")
        else:
            parts.append("<project_context>Laravel project (no scan data available)</project_context>")

        # 2. Conversation summary (rolling context)
        if conversation_summary:
            parts.append(conversation_summary.to_prompt_text())
        else:
            parts.append("<conversation_context>No prior conversation context.</conversation_context>")

        # 3. Recent messages (last 4)
        if recent_messages:
            parts.append(format_recent_messages(recent_messages, max_messages=4))
        else:
            parts.append("<recent_messages>No recent messages.</recent_messages>")

        # 4. Current request
        parts.append(f"<current_request>\n{user_input}\n</current_request>")

        return "\n\n".join(parts)

    async def analyze(
            self,
            user_input: str,
            project_context: Optional[str] = None,
            conversation_summary: Optional[ConversationSummary] = None,
            recent_messages: Optional[list[RecentMessage]] = None,
    ) -> Intent:
        """
        Analyze user input to extract intent.

        Args:
            user_input: The user's request text
            project_context: Rich project context from Orchestrator.build_project_context()
                            (Already includes Laravel version, stack, file stats, etc.)
            conversation_summary: Rolling context from prior interactions
            recent_messages: Last 4 messages for immediate context

        Returns:
            Intent object with extracted information

        Note:
            If needs_clarification=True, the pipeline should HALT.
            Check intent.should_halt_pipeline() before proceeding.
        """
        start_time = time.time()

        logger.info(f"[{self.identity.name.upper()}] {self.identity.get_random_greeting()}")
        logger.info(f"[{self.identity.name.upper()}] Analyzing: {user_input[:100]}...")

        # Build prompt with all context layers
        user_prompt = self._build_user_prompt(
            user_input=user_input,
            project_context=project_context,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages,
        )

        # Attempt analysis with retries
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                intent = await self._call_claude_structured(
                    user_prompt=user_prompt,
                    attempt=attempt,
                )

                # Calculate timing
                analysis_time_ms = int((time.time() - start_time) * 1000)
                intent.analysis_time_ms = analysis_time_ms
                intent.retry_count = attempt

                # Log result
                self._log_analysis_result(intent)

                return intent

            except Exception as e:
                last_error = e
                logger.warning(
                    f"[{self.identity.name.upper()}] Attempt {attempt + 1}/{MAX_RETRIES + 1} failed: {e}"
                )

                if attempt < MAX_RETRIES:
                    delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                    logger.info(f"[{self.identity.name.upper()}] Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        # All retries failed - return error fallback (still halts pipeline)
        logger.error(f"[{self.identity.name.upper()}] All retries exhausted. Error: {last_error}")

        analysis_time_ms = int((time.time() - start_time) * 1000)
        fallback = Intent.error_fallback(str(last_error))
        fallback.analysis_time_ms = analysis_time_ms
        fallback.retry_count = MAX_RETRIES

        return fallback

    async def _call_claude_structured(self, user_prompt: str, attempt: int) -> Intent:
        """
        Call Claude with structured output expectations.

        Uses the existing Claude service with JSON output parsing.
        The system prompt instructs Claude to output valid JSON.

        Args:
            user_prompt: The formatted user prompt
            attempt: Current attempt number (for logging)

        Returns:
            Validated Intent object
        """
        logger.debug(f"[{self.identity.name.upper()}] {self.identity.get_random_thinking()}")

        messages = [{"role": "user", "content": user_prompt}]

        # Use existing Claude service
        response = await self.claude.chat_async(
            model=MODEL_MAP.get(NOVA_MODEL, ClaudeModel.OPUS),
            messages=messages,
            system=NOVA_SYSTEM_PROMPT,
            temperature=0.2,  # Low temperature for consistent classification
            max_tokens=2048,
            request_type="intent",
            use_cache=True,  # Cache the static system prompt
        )

        # Parse and validate response
        intent_output = self._parse_and_validate(response)
        return Intent.from_output(intent_output)

    def _parse_and_validate(self, response: str) -> IntentOutput:
        """
        Parse Claude's response and validate against schema.

        Args:
            response: Raw response from Claude

        Returns:
            Validated IntentOutput

        Raises:
            ValueError: If response cannot be parsed or validated
        """
        # Clean response - remove markdown code blocks if present
        response_text = response.strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Find start and end of code block
            start_idx = 1 if lines[0].startswith("```") else 0
            end_idx = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            response_text = "\n".join(lines[start_idx:end_idx])

        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.identity.name.upper()}] JSON parse error: {e}")
            logger.debug(f"[{self.identity.name.upper()}] Raw response: {response_text[:500]}")
            raise ValueError(f"Failed to parse JSON: {e}")

        # Validate with Pydantic
        try:
            # Handle entities if it's a flat dict
            if "entities" in data and isinstance(data["entities"], dict):
                # Ensure it has the expected structure
                entities = data["entities"]
                data["entities"] = ExtractedEntities(
                    files=entities.get("files", []),
                    classes=entities.get("classes", []),
                    methods=entities.get("methods", []),
                    routes=entities.get("routes", []),
                    tables=entities.get("tables", []),
                )

            return IntentOutput(**data)

        except ValidationError as e:
            logger.error(f"[{self.identity.name.upper()}] Validation error: {e}")
            raise ValueError(f"Schema validation failed: {e}")

    def _log_analysis_result(self, intent: Intent) -> None:
        """Log analysis results with key metrics."""
        status = "NEEDS_CLARIFICATION" if intent.needs_clarification else "OK"

        logger.info(
            f"[{self.identity.name.upper()}] Analysis complete | "
            f"status={status} | "
            f"task_type={intent.task_type} | "
            f"priority={intent.priority} | "
            f"scope={intent.scope} | "
            f"confidence={intent.overall_confidence:.2f} | "
            f"time={intent.analysis_time_ms}ms | "
            f"retries={intent.retry_count}"
        )

        if intent.needs_clarification:
            logger.info(
                f"[{self.identity.name.upper()}] Clarification needed: "
                f"{intent.clarifying_questions}"
            )
        else:
            logger.debug(
                f"[{self.identity.name.upper()}] Reasoning: {intent.reasoning}"
            )
            logger.debug(
                f"[{self.identity.name.upper()}] Search queries: {intent.search_queries}"
            )


# Convenience functions

async def analyze_intent(
        user_input: str,
        project_context: Optional[str] = None,
        conversation_summary: Optional[ConversationSummary] = None,
        recent_messages: Optional[list[RecentMessage]] = None,
        claude_service: Optional[ClaudeService] = None,
) -> Intent:
    """
    Convenience function to analyze intent without instantiating the class.

    Args:
        user_input: The user's request text
        project_context: Rich project context from Orchestrator.build_project_context()
        conversation_summary: Rolling context from prior interactions
        recent_messages: Last 4 messages for immediate context
        claude_service: Optional Claude service instance

    Returns:
        Intent object with extracted information
    """
    analyzer = IntentAnalyzer(claude_service=claude_service)
    return await analyzer.analyze(
        user_input=user_input,
        project_context=project_context,
        conversation_summary=conversation_summary,
        recent_messages=recent_messages,
    )
