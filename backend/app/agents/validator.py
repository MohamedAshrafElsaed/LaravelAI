"""
Validator Agent.

Validates execution results against coding standards, conventions,
and the original intent to ensure quality and completeness.
"""
import json
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

from app.agents.intent_analyzer import Intent
from app.agents.context_retriever import RetrievedContext
from app.agents.executor import ExecutionResult
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are an expert Laravel code reviewer validating generated code changes.

## Original User Request
{user_input}

## Intent Analysis
- Task Type: {task_type}
- Scope: {scope}
- Domains Affected: {domains}

## Generated Changes
{changes}

## Codebase Context (for reference)
{context}

## Validation Criteria
Review the generated code against these criteria:

1. **Completeness**: Does it fully implement the user's request?
2. **Laravel Conventions**: Follows Laravel naming, structure, and patterns?
3. **Code Quality**: PSR-12 compliant, proper type hints, docblocks?
4. **Security**: No SQL injection, XSS, mass assignment vulnerabilities?
5. **Breaking Changes**: Does it break existing functionality?
6. **Dependencies**: Are all required imports/uses present?
7. **Database**: If migrations added, are they correct?
8. **Testing**: Could this code be easily tested?

## Instructions
Provide a thorough validation review.

Respond with a JSON object:
{{
  "approved": true/false,
  "score": 0-100,
  "issues": [
    {{
      "severity": "error|warning|info",
      "file": "path/to/file.php",
      "line": 42,
      "message": "Description of the issue"
    }}
  ],
  "suggestions": [
    "Optional improvement suggestion 1",
    "Optional improvement suggestion 2"
  ],
  "summary": "Brief summary of the validation result"
}}

Rules:
- Set approved=true only if there are no "error" severity issues
- Score 80+ means good quality, 90+ excellent
- Be specific about issues (include file and line if possible)
- Issues with severity "error" must be fixed before approval

Respond ONLY with the JSON object."""


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
        issues = [ValidationIssue.from_dict(i) for i in data.get("issues", [])]
        return cls(
            approved=data.get("approved", False),
            score=data.get("score", 0),
            issues=issues,
            suggestions=data.get("suggestions", []),
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
    """

    def __init__(self, claude_service: Optional[ClaudeService] = None):
        """
        Initialize the validator.

        Args:
            claude_service: Optional Claude service instance.
        """
        self.claude = claude_service or get_claude_service()
        logger.info("[VALIDATOR] Initialized")

    async def validate(
        self,
        user_input: str,
        intent: Intent,
        results: list[ExecutionResult],
        context: RetrievedContext,
    ) -> ValidationResult:
        """
        Validate execution results.

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

        prompt = VALIDATION_PROMPT.format(
            user_input=user_input,
            task_type=intent.task_type,
            scope=intent.scope,
            domains=", ".join(intent.domains_affected) or "general",
            changes=changes_str,
            context=context.to_prompt_string()[:10000],  # Limit context size
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
            )

            # Parse JSON response
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            validation_data = json.loads(response_text)
            result = ValidationResult.from_dict(validation_data)

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
