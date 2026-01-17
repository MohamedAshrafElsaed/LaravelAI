"""
Intent Analyzer Agent.

Analyzes user input to understand what they want to accomplish,
extracting task type, affected domains, scope, and search queries.
"""
import json
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)

INTENT_ANALYSIS_PROMPT = """You are an expert Laravel developer assistant. Analyze the user's request and extract structured information about their intent.

PROJECT CONTEXT:
{project_context}

USER REQUEST:
{user_input}

Analyze this request and respond with a JSON object containing:

1. "task_type": One of:
   - "feature" - Adding new functionality
   - "bugfix" - Fixing a bug or error
   - "refactor" - Improving code without changing behavior
   - "question" - User is asking a question, not requesting changes

2. "domains_affected": Array of Laravel domains that will be affected. Examples:
   - "auth" - Authentication/authorization
   - "payment" - Payment processing
   - "api" - API endpoints
   - "database" - Database/migrations
   - "queue" - Jobs/queues
   - "mail" - Email functionality
   - "storage" - File storage
   - "cache" - Caching
   - "routing" - Routes
   - "middleware" - Middleware
   - "validation" - Form validation
   - "events" - Events/listeners

3. "scope": One of:
   - "single_file" - Changes to one file only
   - "feature" - Multiple related files in one feature
   - "cross_domain" - Changes spanning multiple domains

4. "languages": Array of languages/file types involved. Examples:
   - "php" - PHP code
   - "blade" - Blade templates
   - "vue" - Vue.js components
   - "js" - JavaScript
   - "css" - Stylesheets
   - "json" - JSON config files

5. "requires_migration": Boolean - Does this need a database migration?

6. "search_queries": Array of 2-5 search terms to find relevant code in the codebase.
   Be specific and include:
   - Class names that might exist
   - Method names
   - Key terms from the request
   - Related Laravel concepts

Respond ONLY with the JSON object, no additional text."""


@dataclass
class Intent:
    """Represents the analyzed intent from user input."""

    task_type: str  # feature, bugfix, refactor, question
    domains_affected: list[str] = field(default_factory=list)
    scope: str = "single_file"  # single_file, feature, cross_domain
    languages: list[str] = field(default_factory=lambda: ["php"])
    requires_migration: bool = False
    search_queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Intent":
        """Create from dictionary."""
        return cls(
            task_type=data.get("task_type", "question"),
            domains_affected=data.get("domains_affected", []),
            scope=data.get("scope", "single_file"),
            languages=data.get("languages", ["php"]),
            requires_migration=data.get("requires_migration", False),
            search_queries=data.get("search_queries", []),
        )


class IntentAnalyzer:
    """
    Analyzes user input to understand their intent.

    Uses Claude Haiku for fast, cost-effective analysis.
    """

    def __init__(self, claude_service: Optional[ClaudeService] = None):
        """
        Initialize the intent analyzer.

        Args:
            claude_service: Optional Claude service instance.
        """
        self.claude = claude_service or get_claude_service()
        logger.info("[INTENT_ANALYZER] Initialized")

    async def analyze(
        self,
        user_input: str,
        project_context: Optional[str] = None,
    ) -> Intent:
        """
        Analyze user input to extract intent.

        Args:
            user_input: The user's request text
            project_context: Optional context about the project

        Returns:
            Intent object with extracted information
        """
        logger.info(f"[INTENT_ANALYZER] Analyzing input: {user_input[:100]}...")

        # Build the prompt
        context = project_context or "Laravel project (no additional context provided)"
        prompt = INTENT_ANALYSIS_PROMPT.format(
            project_context=context,
            user_input=user_input,
        )

        # Call Claude Haiku for fast analysis
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.HAIKU,
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=1024,
                request_type="intent",
            )

            # Parse JSON response
            # Clean up response - remove markdown code blocks if present
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first and last lines (```json and ```)
                response_text = "\n".join(lines[1:-1])

            intent_data = json.loads(response_text)
            intent = Intent.from_dict(intent_data)

            logger.info(f"[INTENT_ANALYZER] Analysis complete: task_type={intent.task_type}, scope={intent.scope}")
            logger.debug(f"[INTENT_ANALYZER] Search queries: {intent.search_queries}")

            return intent

        except json.JSONDecodeError as e:
            logger.error(f"[INTENT_ANALYZER] Failed to parse response as JSON: {e}")
            logger.debug(f"[INTENT_ANALYZER] Raw response: {response}")
            # Return a default intent for questions
            return Intent(
                task_type="question",
                search_queries=[user_input[:50]],
            )

        except Exception as e:
            logger.error(f"[INTENT_ANALYZER] Analysis failed: {e}")
            raise
