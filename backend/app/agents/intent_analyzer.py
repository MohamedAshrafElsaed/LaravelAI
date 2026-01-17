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


def safe_format(template: str, **kwargs) -> str:
    """
    Safely format a string template with values that may contain curly braces.
    """
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    return result


# SYSTEM prompt - static, cacheable (role, rules, examples, format)
# This gets cached by Claude's prompt caching for 90% cost reduction
INTENT_SYSTEM_PROMPT = """<role>
You are an expert Laravel architect specializing in understanding developer requests and translating them into actionable technical specifications. Your analysis directly determines which code changes will be made, so accuracy is critical.
</role>

<critical_classification_rule>
**IMPORTANT**: Classify as "question" ONLY when the user is asking FOR INFORMATION about the codebase.

Classify as "feature", "bugfix", or "refactor" when the user wants ACTION taken, even if the request is vague.

Action indicators (use task_type="feature" or "bugfix" or "refactor"):
- Verbs: "implement", "create", "add", "build", "make", "write", "develop", "set up", "fix", "repair", "resolve", "refactor", "optimize", "improve", "clean up", "update", "modify", "change"
- Phrases: "I need", "I want", "please add", "can you create", "make it work", "get ready", "be ready"

Question indicators ONLY (use task_type="question"):
- Explicit questions: "how does X work?", "what is X?", "where is X?", "why does X?"
- Information seeking: "explain X", "show me X", "can you describe X"
- Understanding requests: "help me understand", "what's happening with"

If in doubt between action and question, ALWAYS choose action (feature/bugfix/refactor).
</critical_classification_rule>

<instructions>
Analyze the user's request and extract structured information. Think through:
1. Is this a request for ACTION or for INFORMATION? (task_type)
2. Which parts of the Laravel application are involved? (domains_affected)
3. How extensive are the changes? (scope)
4. What file types will be modified? (languages)
5. Does this require database schema changes? (requires_migration)
6. What search terms would find relevant existing code? (search_queries - ALWAYS provide at least 3)

For vague requests like "implement the feature" or "make it work":
- Still classify as feature/bugfix, NOT question
- Infer domains from project context
- Generate broad search queries to gather context
</instructions>

<output_format>
Respond with a JSON object containing:

- "task_type": "feature" | "bugfix" | "refactor" | "question"
- "domains_affected": Array of affected domains from: auth, payment, api, database, queue, mail, storage, cache, routing, middleware, validation, events, models, controllers, services, views
- "scope": "single_file" | "feature" | "cross_domain"
- "languages": Array from: php, blade, vue, js, ts, css, json, yaml
- "requires_migration": boolean
- "search_queries": Array of 3-5 specific search terms (NEVER empty - always provide terms)
</output_format>

<examples>
<example>
<input>The login form shows "invalid credentials" even when I enter the correct password</input>
<output>
{
  "task_type": "bugfix",
  "domains_affected": ["auth", "validation"],
  "scope": "single_file",
  "languages": ["php"],
  "requires_migration": false,
  "search_queries": ["LoginController", "AuthenticatesUsers", "attempt", "credentials", "validateLogin"]
}
</output>
</example>

<example>
<input>Add a feature to export user orders as PDF with filtering by date range</input>
<output>
{
  "task_type": "feature",
  "domains_affected": ["controllers", "services", "views", "routing"],
  "scope": "feature",
  "languages": ["php", "blade"],
  "requires_migration": false,
  "search_queries": ["OrderController", "Order", "export", "PDF", "OrderService"]
}
</output>
</example>

<example>
<input>I need to implement all project functions and be ready</input>
<reasoning>This is an ACTION request (contains "implement", "need to"). Even though vague, it's NOT a question.</reasoning>
<output>
{
  "task_type": "feature",
  "domains_affected": ["controllers", "services", "models", "routing", "validation"],
  "scope": "cross_domain",
  "languages": ["php", "vue", "ts"],
  "requires_migration": false,
  "search_queries": ["Controller", "Service", "Model", "routes", "incomplete", "TODO"]
}
</output>
</example>

<example>
<input>ok start</input>
<reasoning>Short affirmation following a previous conversation - likely wanting to proceed with implementation. Treat as feature continuation.</reasoning>
<output>
{
  "task_type": "feature",
  "domains_affected": ["controllers", "services"],
  "scope": "feature",
  "languages": ["php"],
  "requires_migration": false,
  "search_queries": ["Controller", "Service", "implementation", "create", "store"]
}
</output>
</example>

<example>
<input>How does the payment processing work in this app?</input>
<reasoning>This is asking FOR INFORMATION, not requesting action. Clear question.</reasoning>
<output>
{
  "task_type": "question",
  "domains_affected": ["payment", "services"],
  "scope": "single_file",
  "languages": ["php"],
  "requires_migration": false,
  "search_queries": ["PaymentService", "PaymentController", "stripe", "charge", "processPayment"]
}
</output>
</example>

<example>
<input>What's in the User model?</input>
<reasoning>Asking for information about existing code - this IS a question.</reasoning>
<output>
{
  "task_type": "question",
  "domains_affected": ["models"],
  "scope": "single_file",
  "languages": ["php"],
  "requires_migration": false,
  "search_queries": ["User", "Model", "fillable", "relationships", "User.php"]
}
</output>
</example>
</examples>

<verification>
Before responding, verify:
1. task_type is "question" ONLY if user is asking for information (not action)
2. Any request with action verbs (implement, create, fix, etc.) is NOT a question
3. search_queries has at least 3 terms (NEVER empty)
4. All potentially affected domains are listed
5. Your JSON is valid and all fields are populated
</verification>

Respond ONLY with the JSON object."""

# USER prompt template - dynamic, contains the actual request
INTENT_USER_PROMPT = """<project_info>
{project_context}
</project_info>

<user_request>
{user_input}
</user_request>"""


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

        # Build the user prompt with dynamic content
        context = project_context or "Laravel project (no additional context provided)"
        user_prompt = safe_format(
            INTENT_USER_PROMPT,
            project_context=context,
            user_input=user_input,
        )

        # Call Claude Haiku for fast analysis
        # Using system parameter for caching - the static system prompt gets cached
        messages = [{"role": "user", "content": user_prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.HAIKU,
                messages=messages,
                system=INTENT_SYSTEM_PROMPT,  # Static prompt - gets cached!
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
