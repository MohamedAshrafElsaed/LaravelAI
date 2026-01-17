"""
Validator Agent.

Validates execution results against coding standards, conventions,
and the original intent to ensure quality and completeness.

UPDATED: Includes contradiction detection.
"""
import json
import logging
from typing import Optional, List
from dataclasses import dataclass, field, asdict

from app.agents.intent_analyzer import Intent
from app.agents.context_retriever import RetrievedContext
from app.agents.executor import ExecutionResult
from app.agents.config import AgentConfig, agent_config
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


# SYSTEM prompt - static, cacheable for 90% cost reduction
VALIDATION_SYSTEM_PROMPT = """<role>
You are a senior Laravel code reviewer and quality assurance expert. Your validation directly determines whether code ships to production, so thoroughness and accuracy are critical. You have deep expertise in Laravel conventions, PHP best practices, security vulnerabilities, and code quality standards.
</role>

<validation_criteria>
Review the code against each criterion. Mark PASS, FAIL, or N/A for each.

**1. COMPLETENESS** (Required - blocks approval if FAIL)
- [ ] All requirements from user request are implemented
- [ ] No placeholder code (TODO, FIXME, "implement later")
- [ ] Edge cases are handled appropriately
- FAIL if: Any requirement is missing or incomplete

**2. LARAVEL CONVENTIONS** (Required - blocks approval if FAIL)
- [ ] Correct namespace based on file location
- [ ] Proper naming: singular Model, plural Controller, PascalCase classes
- [ ] Relationships defined correctly (hasMany, belongsTo, etc.)
- [ ] Facades used appropriately (prefer DI in services)
- FAIL if: Namespace wrong, naming conventions violated, or Laravel patterns ignored

**3. CODE QUALITY** (Required - blocks approval if FAIL)
- [ ] PSR-12 formatting (4-space indentation, proper bracing)
- [ ] Type hints on all parameters and return types
- [ ] Methods have docblocks with @param, @return, @throws
- [ ] No code duplication (DRY principle followed)
- FAIL if: Missing type hints on public methods, no docblocks, or severe formatting issues

**4. SECURITY** (Required - CRITICAL, blocks approval if FAIL)
- [ ] No raw SQL with user input (use parameterized queries/Eloquent)
- [ ] No unescaped output in views (use {{ }} not {!! !!} for user data)
- [ ] Mass assignment protection ($fillable or $guarded properly set)
- [ ] Authentication/authorization checks where needed
- [ ] No hardcoded secrets or credentials
- FAIL if: ANY security vulnerability detected

**5. DEPENDENCIES & IMPORTS** (Required - blocks approval if FAIL)
- [ ] All use statements present (no undefined classes)
- [ ] No unused imports
- [ ] Correct class references (not misspelled)
- FAIL if: Missing imports would cause runtime errors

**6. DATABASE/MIGRATIONS** (If applicable)
- [ ] Migrations are reversible (down() method works)
- [ ] Proper column types and constraints
- [ ] Indexes on foreign keys and frequently queried columns
- [ ] Foreign key relationships defined correctly
- FAIL if: Migration would fail or cause data issues

**7. BACKWARDS COMPATIBILITY** (Warning level)
- [ ] Existing method signatures not changed (unless intended)
- [ ] Existing functionality not broken
- [ ] Config changes are additive, not breaking
- WARNING if: Potential breaking changes detected

**8. TESTABILITY** (Info level)
- [ ] Dependencies are injectable (for mocking)
- [ ] Methods have single responsibility
- [ ] No static method abuse
- INFO if: Code would be difficult to test
</validation_criteria>

<severity_guide>
Use these severity levels precisely:

**ERROR** (Blocks approval - MUST be fixed):
- Security vulnerabilities
- Missing type hints on public interfaces
- Missing use statements that would cause errors
- Code that doesn't fulfill the user's request
- Namespace or class name errors
- Syntax errors

**WARNING** (Doesn't block, but should be addressed):
- Potential breaking changes
- Missing docblocks on private methods
- Suboptimal patterns that still work
- Minor convention violations

**INFO** (Suggestions for improvement):
- Testability concerns
- Performance suggestions
- Alternative approaches
- Style preferences
</severity_guide>

<scoring_calibration>
Score based on the criteria results:

**95-100 (Excellent)**:
- All criteria PASS
- Code is production-ready
- Follows all best practices
- Example: Clean controller with proper validation, service layer, type hints, full docblocks

**85-94 (Good)**:
- All required criteria PASS
- Minor warnings present
- Code is shippable with small improvements
- Example: Working code with 1-2 missing docblocks on private methods

**70-84 (Acceptable)**:
- Most required criteria PASS
- Some warnings, no errors
- Code works but has room for improvement
- Example: Working code that could use better error handling

**50-69 (Needs Work)**:
- One or more required criteria FAIL
- Code has errors that must be fixed
- Example: Missing use statement, incomplete implementation

**0-49 (Rejected)**:
- Multiple critical failures
- Security issues present
- Fundamentally broken or incomplete
- Example: Security vulnerability, major missing functionality
</scoring_calibration>

<examples>
<example_excellent>
<scenario>Controller with proper validation, service injection, type hints</scenario>
<result>
{
  "approved": true,
  "score": 96,
  "issues": [
    {
      "severity": "info",
      "file": "app/Http/Controllers/OrderController.php",
      "line": 45,
      "message": "Consider adding rate limiting to this endpoint"
    }
  ],
  "suggestions": ["Consider adding API resource for response formatting"],
  "summary": "Excellent implementation following Laravel conventions. All criteria pass with minor suggestions."
}
</result>
</example_excellent>

<example_needs_fix>
<scenario>Controller missing use statement and validation</scenario>
<result>
{
  "approved": false,
  "score": 58,
  "issues": [
    {
      "severity": "error",
      "file": "app/Http/Controllers/UserController.php",
      "line": 12,
      "message": "Missing use statement: App\\Services\\UserService is referenced but not imported"
    },
    {
      "severity": "error",
      "file": "app/Http/Controllers/UserController.php",
      "line": 28,
      "message": "No input validation - user data used directly without validation"
    },
    {
      "severity": "warning",
      "file": "app/Http/Controllers/UserController.php",
      "line": 35,
      "message": "Method lacks return type hint"
    }
  ],
  "suggestions": ["Create a StoreUserRequest form request for validation"],
  "summary": "Code has 2 errors blocking approval: missing import and no input validation. Fix these issues before deployment."
}
</result>
</example_needs_fix>

<example_security_fail>
<scenario>Code with SQL injection vulnerability</scenario>
<result>
{
  "approved": false,
  "score": 25,
  "issues": [
    {
      "severity": "error",
      "file": "app/Services/SearchService.php",
      "line": 42,
      "message": "CRITICAL SECURITY: SQL injection vulnerability - user input concatenated into raw query. Use parameterized queries: DB::select('SELECT * FROM users WHERE name = ?', [$name])"
    }
  ],
  "suggestions": ["Use Eloquent query builder or parameterized queries for all database operations"],
  "summary": "REJECTED: Critical SQL injection vulnerability detected. This code MUST NOT be deployed."
}
</result>
</example_security_fail>
</examples>

<output_format>
{
  "approved": boolean,
  "score": number (0-100),
  "issues": [
    {
      "severity": "error" | "warning" | "info",
      "file": "path/to/file.php",
      "line": number | null,
      "message": "Clear description of the issue and how to fix it"
    }
  ],
  "suggestions": ["Improvement suggestions not tied to specific issues"],
  "summary": "One paragraph summarizing validation result and key findings"
}

RULES:
- approved=true ONLY if zero "error" severity issues
- Always include the file and line number when possible
- Messages should explain WHAT is wrong and HOW to fix it
- Summary should mention if code is production-ready
</output_format>

<verification>
Before responding, verify:
1. You checked ALL 8 validation criteria
2. Severity levels match the guide (security = error, testability = info)
3. Score matches the calibration examples
4. approved matches whether any errors exist
5. Issues include actionable fix suggestions
6. JSON is valid
</verification>

Respond ONLY with the JSON object."""

# USER prompt template - dynamic, contains the actual request and context
VALIDATION_USER_PROMPT = """<validation_context>
<user_request>{user_input}</user_request>
<intent>
- Task Type: {task_type}
- Scope: {scope}
- Domains: {domains}
</intent>
</validation_context>

<generated_changes>
{changes}
</generated_changes>

<codebase_reference>
{context}
</codebase_reference>"""


@dataclass
class ValidationIssue:
    """A validation issue found in the code."""

    severity: str  # error, warning, info
    file: str
    message: str
    line: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationIssue":
        """Create from dictionary."""
        # Defensive check - ensure data is a dict
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return cls(severity="info", file="", message=data)

        if not isinstance(data, dict):
            return cls(severity="info", file="", message=str(data))

        return cls(
            severity=data.get("severity", "info"),
            file=data.get("file", ""),
            message=data.get("message", ""),
            line=data.get("line"),
        )


@dataclass
class ValidationResult:
    """Result of validating execution results."""

    approved: bool
    score: int
    issues: list[ValidationIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "approved": self.approved,
            "score": self.score,
            "issues": [issue.to_dict() for issue in self.issues],
            "suggestions": self.suggestions,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationResult":
        """Create from dictionary."""
        # Defensive check - ensure data is a dict
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return cls(approved=False, score=0, summary=data)

        if not isinstance(data, dict):
            return cls(approved=False, score=0, summary=str(data))

        issues_data = data.get("issues", [])
        if not isinstance(issues_data, list):
            issues_data = []

        issues = [ValidationIssue.from_dict(i) for i in issues_data]

        suggestions = data.get("suggestions", [])
        if not isinstance(suggestions, list):
            suggestions = []

        return cls(
            approved=data.get("approved", False),
            score=data.get("score", 0),
            issues=issues,
            suggestions=suggestions,
            summary=data.get("summary", ""),
        )

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get only error-severity issues."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get only warning-severity issues."""
        return [i for i in self.issues if i.severity == "warning"]


class Validator:
    """
    Validates execution results for quality and correctness.

    Uses Claude Sonnet for thorough code review.

    UPDATED: Includes contradiction detection.
    """

    def __init__(
        self,
        claude_service: Optional[ClaudeService] = None,
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize the validator.

        Args:
            claude_service: Optional Claude service instance.
            config: Optional agent configuration.
        """
        self.claude = claude_service or get_claude_service()
        self.config = config or agent_config
        self.validation_history: List[ValidationResult] = []  # Track history
        logger.info("[VALIDATOR] Initialized with contradiction detection")

    async def validate(
        self,
        user_input: str,
        intent: Intent,
        results: List[ExecutionResult],
        context: RetrievedContext,
    ) -> ValidationResult:
        """
        Validate execution results with contradiction detection.

        Args:
            user_input: Original user request
            intent: Analyzed intent
            results: Execution results to validate
            context: Codebase context for reference

        Returns:
            ValidationResult with approval status and issues
        """
        logger.info(f"[VALIDATOR] Validating {len(results)} execution results")

        # Format changes for review
        changes_str = self._format_changes(results)

        # Build user prompt with dynamic content
        user_prompt = safe_format(
            VALIDATION_USER_PROMPT,
            user_input=user_input,
            task_type=intent.task_type,
            scope=intent.scope,
            domains=", ".join(intent.domains_affected) or "general",
            changes=changes_str,
            context=context.to_prompt_string()[:10000],  # Limit context size
        )

        # Using system parameter for caching - the static system prompt gets cached
        messages = [{"role": "user", "content": user_prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=messages,
                system=VALIDATION_SYSTEM_PROMPT,  # Static prompt - gets cached!
                temperature=0.3,
                max_tokens=4096,
                request_type="validation",
            )

            # Parse JSON response
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            validation_data = json.loads(response_text)
            result = ValidationResult.from_dict(validation_data)

            # Check for contradictions with previous validations
            if self.config.ENABLE_CONTRADICTION_DETECTION and self.validation_history:
                contradictions = self._detect_contradictions(result)
                if contradictions:
                    logger.warning(f"[VALIDATOR] Detected {len(contradictions)} contradictions")
                    # Add warning to suggestions
                    result.suggestions = result.suggestions or []
                    result.suggestions.append(
                        f"Validation may be inconsistent: {len(contradictions)} potential contradictions detected"
                    )

            # Store in history
            self.validation_history.append(result)

            logger.info(f"[VALIDATOR] Validation complete: approved={result.approved}, score={result.score}")
            logger.info(f"[VALIDATOR] Issues: {len(result.errors)} errors, {len(result.warnings)} warnings")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"[VALIDATOR] Failed to parse validation response: {e}")
            # Return failed validation on parse error
            return ValidationResult(
                approved=False,
                score=0,
                summary="Failed to parse validation response",
                issues=[ValidationIssue(
                    severity="error",
                    file="",
                    message="Validation process failed - could not parse response",
                )],
            )

        except Exception as e:
            logger.error(f"[VALIDATOR] Validation failed: {e}")
            raise

    def _detect_contradictions(self, current: ValidationResult) -> List[dict]:
        """Detect contradictory feedback across validation iterations."""
        contradictions = []

        # Patterns that are often contradictory
        contradiction_patterns = [
            ("redundant", "missing"),
            ("remove", "add"),
            ("unnecessary", "required"),
            ("should not", "should"),
        ]

        if not self.validation_history:
            return contradictions

        previous = self.validation_history[-1]

        for curr_issue in current.issues:
            curr_msg = curr_issue.message.lower()
            for prev_issue in previous.issues:
                prev_msg = prev_issue.message.lower()

                # Check if same file
                if curr_issue.file != prev_issue.file:
                    continue

                # Check for contradictory language
                for pattern_a, pattern_b in contradiction_patterns:
                    if (pattern_a in curr_msg and pattern_b in prev_msg) or \
                       (pattern_b in curr_msg and pattern_a in prev_msg):
                        contradictions.append({
                            "file": curr_issue.file,
                            "previous": prev_issue.message,
                            "current": curr_issue.message,
                            "pattern": f"{pattern_a} vs {pattern_b}"
                        })

        return contradictions

    def clear_history(self):
        """Clear validation history (call at start of new request)."""
        self.validation_history = []

    def _format_changes(self, results: list[ExecutionResult]) -> str:
        """Format execution results for validation prompt."""
        parts = []

        for result in results:
            status = "✓" if result.success else "✗"
            parts.append(f"\n### {status} [{result.action.upper()}] {result.file}\n")

            if result.action == "delete":
                parts.append("*File marked for deletion*\n")
            elif result.diff:
                parts.append(f"```diff\n{result.diff}\n```\n")
            elif result.content:
                # Show full content if no diff (for creates)
                parts.append(f"```php\n{result.content}\n```\n")

            if result.error:
                parts.append(f"\n**Error:** {result.error}\n")

        return "\n".join(parts)

    async def quick_check(
        self,
        result: ExecutionResult,
    ) -> list[str]:
        """
        Quick syntax and basic validation check.

        Args:
            result: Single execution result

        Returns:
            List of quick-check issues (empty if OK)
        """
        issues = []

        if not result.success:
            issues.append(f"Execution failed: {result.error}")
            return issues

        if result.action != "delete" and not result.content:
            issues.append("No content generated")
            return issues

        content = result.content

        # PHP-specific checks
        if result.file.endswith(".php"):
            if not content.strip().startswith("<?php"):
                issues.append("PHP file should start with <?php")

            # Check for basic syntax issues
            if "function (" in content and "function(" not in content:
                # This is actually OK in PHP for anonymous functions
                pass

            # Check for namespace
            if "namespace " not in content and "app/" in result.file.lower():
                issues.append("App files should have a namespace declaration")

            # Check for class declaration in class files
            if any(x in result.file for x in ["Controller", "Model", "Service", "Repository"]):
                if "class " not in content:
                    issues.append(f"Expected class declaration in {result.file}")

        # Blade-specific checks
        elif result.file.endswith(".blade.php"):
            # Basic blade checks
            if "@extends" not in content and "@section" not in content:
                if "<html" not in content.lower() and "<!doctype" not in content.lower():
                    # Might be a partial/component, which is OK
                    pass

        return issues

    async def validate_single(
        self,
        result: ExecutionResult,
        context: RetrievedContext,
    ) -> ValidationResult:
        """
        Validate a single execution result.

        Args:
            result: Execution result to validate
            context: Codebase context

        Returns:
            ValidationResult for this single file
        """
        # First do quick checks
        quick_issues = await self.quick_check(result)

        if quick_issues:
            return ValidationResult(
                approved=False,
                score=30,
                issues=[ValidationIssue(
                    severity="error",
                    file=result.file,
                    message=issue,
                ) for issue in quick_issues],
                summary="Quick validation failed",
            )

        # For more thorough validation, use the full validate method
        # with a dummy intent
        dummy_intent = Intent(task_type="feature", search_queries=[])
        return await self.validate(
            user_input=f"Validate changes to {result.file}",
            intent=dummy_intent,
            results=[result],
            context=context,
        )
