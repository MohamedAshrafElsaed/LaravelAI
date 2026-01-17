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

INTENT_ANALYSIS_PROMPT = """<role>
You are an expert Laravel architect specializing in understanding developer requests and translating them into actionable technical specifications. Your analysis directly determines which code changes will be made, so accuracy is critical.
</role>

<context>
Accurate intent analysis ensures the correct files are modified and the right approach is taken. Misclassifying a bugfix as a feature could lead to unnecessary new code. Missing an affected domain could leave changes incomplete. Poor search queries mean relevant existing code won't be found for context.
</context>

<project_info>
{project_context}
</project_info>

<user_request>
{user_input}
</user_request>

<instructions>
Analyze the user's request and extract structured information. Think through:
1. What is the user trying to accomplish? (task_type)
2. Which parts of the Laravel application are involved? (domains_affected)
3. How extensive are the changes? (scope)
4. What file types will be modified? (languages)
5. Does this require database schema changes? (requires_migration)
6. What search terms would find relevant existing code? (search_queries)

Handle ambiguous requests by inferring the most likely intent based on context clues:
- Mentions of "broken", "not working", "error", "fix" → likely bugfix
- Mentions of "add", "create", "new", "implement" → likely feature
- Mentions of "clean up", "improve", "refactor", "optimize" → likely refactor
- Ends with "?" or asks "how", "why", "what" → likely question
</instructions>

<output_format>
Respond with a JSON object containing:

- "task_type": "feature" | "bugfix" | "refactor" | "question"
- "domains_affected": Array of affected domains from: auth, payment, api, database, queue, mail, storage, cache, routing, middleware, validation, events, models, controllers, services, views
- "scope": "single_file" | "feature" | "cross_domain"
- "languages": Array from: php, blade, vue, js, ts, css, json, yaml
- "requires_migration": boolean
- "search_queries": Array of 2-5 specific search terms (class names, method names, Laravel concepts)
</output_format>

<examples>
<example>
<input>The login form shows "invalid credentials" even when I enter the correct password</input>
<output>
{{
  "task_type": "bugfix",
  "domains_affected": ["auth", "validation"],
  "scope": "single_file",
  "languages": ["php"],
  "requires_migration": false,
  "search_queries": ["LoginController", "AuthenticatesUsers", "attempt", "credentials", "validateLogin"]
}}
</output>
</example>

<example>
<input>Add a feature to export user orders as PDF with filtering by date range</input>
<output>
{{
  "task_type": "feature",
  "domains_affected": ["controllers", "services", "views", "routing"],
  "scope": "feature",
  "languages": ["php", "blade"],
  "requires_migration": false,
  "search_queries": ["OrderController", "Order", "export", "PDF", "dompdf", "OrderService"]
}}
</output>
</example>

<example>
<input>Create a notifications system where users get emails when their order ships, with a database to track notification history</input>
<output>
{{
  "task_type": "feature",
  "domains_affected": ["database", "mail", "events", "queue", "models", "controllers"],
  "scope": "cross_domain",
  "languages": ["php", "blade"],
  "requires_migration": true,
  "search_queries": ["Notification", "OrderShipped", "Mailable", "notifications table", "NotificationController", "event listener"]
}}
</output>
</example>

<example>
<input>How does the payment processing work in this app?</input>
<output>
{{
  "task_type": "question",
  "domains_affected": ["payment", "services"],
  "scope": "single_file",
  "languages": ["php"],
  "requires_migration": false,
  "search_queries": ["PaymentService", "PaymentController", "stripe", "charge", "processPayment"]
}}
</output>
</example>
</examples>

<verification>
Before responding, verify:
1. task_type matches the user's actual intent (action vs question)
2. All potentially affected domains are listed
3. scope accurately reflects the extent of changes
4. search_queries are specific enough to find relevant code
5. Your JSON is valid and all fields are populated
</verification>

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
        # Defensive check - ensure data is a dict
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return cls(task_type="question", search_queries=[data[:50]])

        if not isinstance(data, dict):
            return cls(task_type="question", search_queries=[str(data)[:50]])

        return cls(
            task_type=data.get("task_type", "question"),
            domains_affected=data.get("domains_affected", []) if isinstance(data.get("domains_affected"), list) else [],
            scope=data.get("scope", "single_file"),
            languages=data.get("languages", ["php"]) if isinstance(data.get("languages"), list) else ["php"],
            requires_migration=data.get("requires_migration", False),
            search_queries=data.get("search_queries", []) if isinstance(data.get("search_queries"), list) else [],
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
