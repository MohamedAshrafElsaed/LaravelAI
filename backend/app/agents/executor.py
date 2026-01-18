"""
Executor Agent.

Executes individual plan steps by generating code changes.
Uses Claude Sonnet for high-quality code generation.

UPDATED: Includes file existence checks and better error handling.
"""
import difflib
import json
import logging
import re
from typing import Optional, List, Tuple
from dataclasses import dataclass, field, asdict

from app.agents.planner import PlanStep
from app.agents.context_retriever import RetrievedContext
from app.agents.config import AgentConfig, agent_config
from app.agents.exceptions import FileNotFoundForModifyError
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)


def safe_format(template: str, **kwargs) -> str:
    """
    Safely format a string template with values that may contain curly braces.

    Uses manual placeholder replacement to avoid Python's format() issues
    with curly braces in values (common in code).
    """
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    return result


# =============================================================================
# SYSTEM PROMPTS - Static, cacheable for 90% cost reduction
# =============================================================================

EXECUTION_SYSTEM_CREATE = """<role>
You are an expert Laravel developer creating production-ready code. Your code will be directly added to the codebase, so it must be complete, correct, and follow all project conventions.
</role>

<default_to_action>
Generate complete, working code. Go beyond the basics to create a fully-featured implementation including proper error handling, validation, and edge cases. Don't generate placeholder code or TODOs.
</default_to_action>

<code_guidelines>
Generate a complete, production-ready file following these standards:

**Structure Requirements:**
- Correct namespace based on file path (app/Services/PaymentService.php → App\\Services)
- All necessary use statements at the top
- Class docblock with description, @package, and @author if project uses them
- Method docblocks with @param, @return, @throws

**Code Quality:**
- PSR-12 formatting (4-space indentation, proper spacing)
- Strict type declarations where appropriate
- Type hints on all method parameters and returns
- Defensive coding with proper error handling

**Laravel Conventions:**
- Use dependency injection in constructors
- Use Laravel facades appropriately (avoid when DI is better)
- Follow existing patterns from codebase context
- Use Eloquent relationships properly
- Implement interfaces if the pattern exists in codebase

**What Makes Excellent Laravel Code:**
- Single responsibility principle - each class does one thing well
- Proper exception handling with custom exceptions when appropriate
- Validation at boundaries (controller inputs, external API responses)
- Clear, descriptive naming that explains intent
</code_guidelines>

<example>
For a file at app/Services/PaymentService.php with description "Create payment processing service":
```php
<?php

declare(strict_types=1);

namespace App\\Services;

use App\\Models\\Order;
use App\\Models\\Payment;
use App\\Exceptions\\PaymentFailedException;
use Illuminate\\Support\\Facades\\Log;

/**
 * Handles payment processing for orders.
 */
class PaymentService
{
    /**
     * Process a payment for an order.
     *
     * @param Order $order
     * @param array $paymentDetails
     * @return Payment
     * @throws PaymentFailedException
     */
    public function processPayment(Order $order, array $paymentDetails): Payment
    {
        // Implementation...
    }
}
```
</example>

<verification>
Before responding, verify:
1. Namespace matches the file path exactly
2. All use statements are included (no undefined classes)
3. All methods have complete docblocks
4. Type hints are present on all parameters and returns
5. Code follows patterns from codebase context
6. No placeholder code or TODOs remain
7. JSON is valid and content is properly escaped
</verification>

Respond ONLY with the JSON object."""

EXECUTION_SYSTEM_MODIFY = """<role>
You are an expert Laravel developer making precise modifications to existing code. Your changes will appear in a code review diff, so make targeted changes that are easy to review and understand.
</role>

<default_to_action>
Make targeted, minimal changes while ensuring the modification is complete and production-ready. Do not over-engineer or add unnecessary abstractions. Do not refactor unrelated code.
</default_to_action>

<modification_guidelines>
**CRITICAL: Preserve Existing Code**
- You MUST keep ALL existing code in the file
- Your task is to ADD to or MODIFY existing code, NOT to replace the entire file
- If the current file has 100 lines and you add 10 lines, the result should have ~110 lines
- NEVER delete existing functionality unless explicitly asked to

**Minimal Change Principle:**
- Only modify what's necessary for the task
- Preserve ALL existing code that isn't directly related
- Match the exact coding style of the existing file
- Don't "improve" or refactor code that isn't part of the task

**When Adding Code:**
- Add new methods at logical locations (e.g., after related methods)
- Add new use statements in alphabetical order with existing ones
- Add new properties near related properties
- Match docblock style exactly with existing methods
- For route files: ADD new routes, don't replace existing routes

**When Changing Code:**
- Preserve indentation and formatting style
- Keep variable naming consistent with file
- Don't change function signatures if not required
- Maintain backwards compatibility

**Diff Awareness:**
Think about how your changes will appear in a diff:
- Minimize lines changed
- The diff should show mostly ADDITIONS ('+' lines), not removals
- Keep additions grouped logically
- Avoid reformatting unchanged code
- If the diff shows the entire file being replaced, you're doing it WRONG
</modification_guidelines>

<example>
Task: Add a method to check if user has active subscription

If the existing User model uses this docblock style:
```php
/**
 * Get the user's full name.
 */
public function getFullName(): string
```

Then add your method with the SAME style:
```php
/**
 * Check if the user has an active subscription.
 */
public function hasActiveSubscription(): bool
{
    return $this->subscription_ends_at !== null
        && $this->subscription_ends_at->isFuture()
        && $this->subscription_status === 'active';
}
```
</example>

<verification>
Before responding, verify:
1. All existing functionality is preserved
2. Only task-related code was changed
3. New code matches existing style exactly
4. All imports/use statements are still valid
5. No unintended whitespace or formatting changes
6. JSON is valid and content is properly escaped
</verification>

IMPORTANT: Content must include the ENTIRE file, not just the changes.

Respond ONLY with the JSON object."""

EXECUTION_SYSTEM_DELETE = """<role>
You are an expert Laravel developer confirming a safe file deletion. Deletions are destructive and irreversible, so careful verification is critical.
</role>

<deletion_safety_checks>
Before confirming deletion, verify:
1. **No active references**: Is this file imported/used elsewhere?
2. **No route references**: Is this controller/middleware referenced in routes?
3. **No config references**: Is this class referenced in config files?
4. **Replacement exists**: If this is being replaced, is the replacement ready?
5. **Not a false positive**: Could the task be accomplished without deletion?

If ANY safety check fails, set "safe_to_delete" to false.
</deletion_safety_checks>

Respond ONLY with the JSON object."""

SELF_VERIFICATION_SYSTEM = """<role>
You are a code reviewer performing a quick verification check on generated code.
</role>

<quick_checks>
Perform these checks (respond quickly - this is a fast verification):

1. **Syntax**: Does the code have valid syntax? (proper brackets, semicolons, etc.)
2. **Imports**: Are all used classes/functions imported with use statements?
3. **Namespace**: Does the namespace match the file path?
4. **Class name**: Does the class name match the filename?
5. **PHP tags**: Does PHP file start with <?php?
6. **No placeholders**: Are there any TODO, FIXME, or placeholder comments?
7. **Complete**: Does the code look complete (no truncation)?
</quick_checks>

Respond ONLY with the JSON object. Be quick and focused."""

FIX_SYSTEM_PROMPT = """<role>
You are an expert Laravel developer fixing specific code issues. Focus ONLY on the identified issues - do not refactor or change anything else.
</role>

<fix_guidelines>
**CRITICAL: Preserve All Existing Code**
- Keep ALL existing functionality intact
- Only make the minimal changes needed to fix the identified issues
- The output should contain the ENTIRE file, not just the fixes
- NEVER delete or replace an entire file when asked to modify styles/content

**For each issue:**
1. Identify the exact location of the problem
2. Determine the minimal fix needed
3. Apply the fix without changing surrounding code
4. Verify the fix doesn't break anything else

**Common Laravel Fixes:**
- Missing use statement → Add at top with other imports (keep existing imports!)
- Missing return type → Add type hint to method signature
- Missing docblock → Add matching existing style
- Syntax error → Fix the specific syntax issue
- Missing validation → Add to Form Request or inline
- File content replaced instead of modified → Restore missing content and ADD the new code

**For "Route completely replaces existing content" errors:**
- The fix is to KEEP all existing routes AND add the new route
- Look at the original routes/api.php content and ensure all existing routes are preserved

**For "Entire file deleted" / Critical Errors (score=0):**
- This is a CRITICAL error that must be fixed immediately
- You MUST regenerate the COMPLETE file from the original content provided
- Look at <original_file_content> and use that as the BASE
- Apply the requested changes (e.g., style updates) while keeping ALL functionality
- The fix MUST include ALL of the original components, sections, and logic
- For style changes: Update CSS/classes but preserve the full template structure

**Do NOT:**
- Refactor code that wasn't mentioned in issues
- Change code style or formatting beyond what's requested
- Add features not requested
- Remove functionality that works
- Delete existing code unless explicitly requested
- NEVER output an empty or minimal file when the original was substantial
</fix_guidelines>

Respond ONLY with the JSON object."""

ERROR_RECOVERY_SYSTEM = """<role>
You are recovering from a code generation error. Analyze what went wrong and generate corrected code.
</role>

<recovery_strategy>
Based on the error type, apply the appropriate fix:

**For JSON parse errors:**
- Ensure all strings are properly escaped (newlines as \\n, quotes as \\")
- Ensure no control characters in strings
- Validate JSON structure before responding

**For syntax errors in generated code:**
- Check for unclosed brackets, parentheses, or braces
- Ensure all statements end with semicolons (PHP)
- Verify proper string quoting

**For incomplete output:**
- Generate complete file content
- Don't truncate large files - include everything
- Ensure closing tags and braces are present

**For validation failures:**
- Add missing imports/use statements
- Add missing type hints
- Fix namespace to match file path
</recovery_strategy>

Generate the COMPLETE corrected code. Respond ONLY with the JSON object."""

# =============================================================================
# USER PROMPTS - Dynamic, contains the actual request and context
# =============================================================================

EXECUTION_USER_CREATE = """<task>
<description>{description}</description>
<file_path>{file_path}</file_path>
</task>

<project_info>
{project_context}
</project_info>

<codebase_context>
{context}
</codebase_context>

<previous_steps>
{previous_results}
</previous_steps>

<output_format>
{{
  "file": "{file_path}",
  "action": "create",
  "content": "complete file content as a properly escaped string"
}}
</output_format>"""

EXECUTION_USER_MODIFY = """<task>
<description>{description}</description>
<file_path>{file_path}</file_path>
</task>

<current_code>
```php
{current_content}
```
</current_code>

<project_info>
{project_context}
</project_info>

<codebase_context>
{context}
</codebase_context>

<previous_steps>
{previous_results}
</previous_steps>

<output_format>
{{
  "file": "{file_path}",
  "action": "modify",
  "content": "COMPLETE file content after modifications"
}}
</output_format>"""

EXECUTION_USER_DELETE = """<task>
<description>{description}</description>
<file_path>{file_path}</file_path>
</task>

<current_code>
```php
{current_content}
```
</current_code>

<output_format>
{{
  "file": "{file_path}",
  "action": "delete",
  "content": "",
  "safe_to_delete": true | false,
  "reason": "Explanation of why this file should/shouldn't be deleted",
  "potential_issues": ["List any files that might reference this one"]
}}
</output_format>"""

SELF_VERIFICATION_USER = """<task>
Verify the following generated code for common issues before it gets applied.
</task>

<file_info>
<file_path>{file_path}</file_path>
<action>{action}</action>
</file_info>

<generated_code>
```{language}
{content}
```
</generated_code>

<output_format>
{{
  "passes_verification": true | false,
  "issues": ["List of critical issues found, empty if none"],
  "confidence": "high" | "medium" | "low"
}}
</output_format>"""


@dataclass
class ExecutionResult:
    """Result of executing a plan step."""

    file: str
    action: str  # create, modify, delete
    content: str
    diff: str = ""
    original_content: str = ""
    success: bool = True
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)  # Track warnings

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionResult":
        """Create from dictionary."""
        # Defensive check - ensure data is a dict
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return cls(file="", action="modify", content="", success=False, error=data)

        if not isinstance(data, dict):
            return cls(file="", action="modify", content="", success=False, error=str(data))

        return cls(
            file=data.get("file", ""),
            action=data.get("action", "modify"),
            content=data.get("content", ""),
            diff=data.get("diff", ""),
            original_content=data.get("original_content", ""),
            success=data.get("success", True),
            error=data.get("error"),
        )


class Executor:
    """
    Executes plan steps by generating code.

    Uses Claude Sonnet for high-quality code generation.

    UPDATED: Includes file existence validation and better context handling.
    """

    def __init__(
        self,
        claude_service: Optional[ClaudeService] = None,
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize the executor.

        Args:
            claude_service: Optional Claude service instance.
            config: Optional agent configuration.
        """
        self.claude = claude_service or get_claude_service()
        self.config = config or agent_config
        logger.info("[EXECUTOR] Initialized with safety checks")

    async def execute_step(
        self,
        step: PlanStep,
        context: RetrievedContext,
        previous_results: List[ExecutionResult],
        current_file_content: Optional[str] = None,
        project_context: str = "",
        enable_self_verification: bool = True,
    ) -> ExecutionResult:
        """
        Execute a single plan step with safety checks.

        Args:
            step: The plan step to execute
            context: Retrieved codebase context
            previous_results: Results from previous steps
            current_file_content: Current content of the file (for modify/delete)
            project_context: Rich project context (stack, conventions, etc.)
            enable_self_verification: Whether to run self-verification on generated code

        Returns:
            ExecutionResult with generated code
        """
        logger.info(f"[EXECUTOR] Executing step {step.order}: [{step.action}] {step.file}")

        # Validate file exists for modify actions
        if step.action == "modify":
            if self.config.REQUIRE_FILE_EXISTS_FOR_MODIFY:
                if not current_file_content:
                    logger.error(f"[EXECUTOR] Cannot modify non-existent file: {step.file}")

                    # Check if this should be a create instead
                    return ExecutionResult(
                        file=step.file,
                        action=step.action,
                        content="",
                        success=False,
                        error=f"File '{step.file}' not found in codebase. "
                              f"Did you mean to use 'create' action? "
                              f"If modifying an existing file, ensure it's indexed.",
                        warnings=[
                            "File not found for modify action",
                            "Consider using 'create' action for new files"
                        ]
                    )

        # Add context quality warning to results
        warnings = []
        if context.confidence_level in ("low", "insufficient"):
            warnings.append(
                f"Low context confidence ({context.confidence_level}). "
                "Generated code may need manual review."
            )

        # Format previous results for context
        prev_results_str = self._format_previous_results(previous_results)

        try:
            if step.action == "create":
                result = await self._execute_create(
                    step, context, prev_results_str, project_context
                )
            elif step.action == "modify":
                result = await self._execute_modify(
                    step, context, prev_results_str, current_file_content or "", project_context
                )
            elif step.action == "delete":
                result = await self._execute_delete(
                    step, context, current_file_content or ""
                )
            else:
                logger.error(f"[EXECUTOR] Unknown action: {step.action}")
                return ExecutionResult(
                    file=step.file,
                    action=step.action,
                    content="",
                    success=False,
                    error=f"Unknown action: {step.action}",
                )

            # Add context warnings to result
            result.warnings.extend(warnings)

            # Run self-verification if enabled and code was generated
            if enable_self_verification and result.content:
                passes, issues = await self.self_verify(result)
                if not passes and issues:
                    # Try to fix the issues automatically
                    logger.info(f"[EXECUTOR] Auto-fixing {len(issues)} verification issues")
                    result = await self.fix_execution(result, issues, context)

            logger.info(f"[EXECUTOR] Step {step.order} completed successfully")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"[EXECUTOR] JSON parse error in step {step.order}: {e}")
            # Attempt error recovery
            return await self.recover_from_error(
                step=step,
                error_type="json_parse",
                error_message=str(e),
                partial_output="",
            )

        except Exception as e:
            logger.error(f"[EXECUTOR] Step {step.order} failed: {e}")
            return ExecutionResult(
                file=step.file,
                action=step.action,
                content="",
                success=False,
                error=str(e),
                warnings=warnings,
            )

    async def _execute_create(
        self,
        step: PlanStep,
        context: RetrievedContext,
        previous_results: str,
        project_context: str = "",
    ) -> ExecutionResult:
        """Execute a create action."""
        user_prompt = safe_format(
            EXECUTION_USER_CREATE,
            description=step.description,
            file_path=step.file,
            project_context=project_context,
            context=context.to_prompt_string(),
            previous_results=previous_results,
        )

        response = await self._call_claude(user_prompt, EXECUTION_SYSTEM_CREATE)
        data = self._parse_response(response)

        content = data.get("content", "")

        # Generate diff (entire file is new)
        diff = self._generate_diff("", content, step.file)

        return ExecutionResult(
            file=step.file,
            action="create",
            content=content,
            diff=diff,
            original_content="",
        )

    async def _execute_modify(
        self,
        step: PlanStep,
        context: RetrievedContext,
        previous_results: str,
        current_content: str,
        project_context: str = "",
    ) -> ExecutionResult:
        """Execute a modify action with original content preservation."""
        user_prompt = safe_format(
            EXECUTION_USER_MODIFY,
            description=step.description,
            file_path=step.file,
            current_content=current_content,
            project_context=project_context,
            context=context.to_prompt_string(),
            previous_results=previous_results,
        )

        response = await self._call_claude(user_prompt, EXECUTION_SYSTEM_MODIFY)
        data = self._parse_response(response)

        content = data.get("content", "")

        # Generate unified diff
        diff = self._generate_diff(current_content, content, step.file)

        # Validate that original content is preserved
        warnings = []
        if current_content and content:
            preservation_check = self._check_content_preservation(current_content, content)
            if not preservation_check["preserved"]:
                logger.warning(f"[EXECUTOR] Content may have been lost: {preservation_check['issues']}")
                warnings.extend(preservation_check["issues"])

        return ExecutionResult(
            file=step.file,
            action="modify",
            content=content,
            diff=diff,
            original_content=current_content,
            warnings=warnings,
        )

    async def _execute_delete(
        self,
        step: PlanStep,
        context: RetrievedContext,
        current_content: str,
    ) -> ExecutionResult:
        """Execute a delete action."""
        user_prompt = safe_format(
            EXECUTION_USER_DELETE,
            description=step.description,
            file_path=step.file,
            current_content=current_content,
        )

        response = await self._call_claude(user_prompt, EXECUTION_SYSTEM_DELETE)
        data = self._parse_response(response)

        # Generate diff showing full deletion
        diff = self._generate_diff(current_content, "", step.file)

        return ExecutionResult(
            file=step.file,
            action="delete",
            content="",
            diff=diff,
            original_content=current_content,
        )

    async def _call_claude(self, user_prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call Claude with the prompt, using system parameter for caching."""
        messages = [{"role": "user", "content": user_prompt}]

        return await self.claude.chat_async(
            model=ClaudeModel.SONNET,
            messages=messages,
            system=system_prompt,  # Static prompt - gets cached!
            temperature=0.3,  # Lower temperature for more consistent code
            max_tokens=8192,  # Allow for larger files
            request_type="execution",
        )

    def _parse_response(self, response: str) -> dict:
        """Parse JSON response from Claude."""
        response_text = response.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"[EXECUTOR] Failed to parse response: {e}")
            logger.debug(f"[EXECUTOR] Raw response: {response_text[:500]}...")
            return {"content": "", "error": "Failed to parse response"}

    def _generate_diff(
        self,
        original: str,
        modified: str,
        filename: str,
    ) -> str:
        """Generate a unified diff between original and modified content."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        # Add newline to last line if missing
        if original_lines and not original_lines[-1].endswith("\n"):
            original_lines[-1] += "\n"
        if modified_lines and not modified_lines[-1].endswith("\n"):
            modified_lines[-1] += "\n"

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )

        return "".join(diff)

    def _format_previous_results(
        self,
        results: List[ExecutionResult],
    ) -> str:
        """Format previous results for context."""
        if not results:
            return "No previous steps executed yet."

        parts = []
        for result in results:
            status = "✓ Success" if result.success else "✗ Failed"
            parts.append(f"Step: [{result.action}] {result.file} - {status}")
            if result.error:
                parts.append(f"  Error: {result.error}")

        return "\n".join(parts)

    def _check_content_preservation(
        self,
        original: str,
        modified: str,
    ) -> dict:
        """Check if original content was preserved in modification."""
        issues = []

        # Check for significant content loss
        original_lines = set(original.strip().split('\n'))
        modified_lines = set(modified.strip().split('\n'))

        # Find lines that were removed (excluding empty lines)
        removed_lines = original_lines - modified_lines
        significant_removals = [l for l in removed_lines if l.strip() and not l.strip().startswith('//')]

        if len(significant_removals) > len(original_lines) * 0.3:  # More than 30% removed
            issues.append(f"Significant content removal detected: {len(significant_removals)} lines")

        # Check for key Laravel patterns that should be preserved
        patterns_to_preserve = [
            (r'Route::', 'Route definitions'),
            (r'use\s+[\w\\]+;', 'Use statements'),
            (r'function\s+\w+\s*\(', 'Function definitions'),
        ]

        for pattern, description in patterns_to_preserve:
            original_matches = len(re.findall(pattern, original))
            modified_matches = len(re.findall(pattern, modified))
            if modified_matches < original_matches:
                issues.append(f"{description} may have been removed")

        return {
            "preserved": len(issues) == 0,
            "issues": issues,
        }

    async def fix_execution(
        self,
        result: ExecutionResult,
        issues: list[str],
        context: RetrievedContext,
    ) -> ExecutionResult:
        """
        Fix a failed or problematic execution.

        Args:
            result: The problematic result
            issues: List of issues to fix
            context: Codebase context

        Returns:
            Fixed ExecutionResult
        """
        logger.info(f"[EXECUTOR] Fixing execution for {result.file}")

        # Include original content if this was a modify action
        original_section = ""
        if result.action == "modify" and result.original_content:
            original_section = f"""
<original_file_content>
This is the ORIGINAL content of the file that should be PRESERVED and ADDED TO:
```php
{result.original_content}
```
</original_file_content>
"""

        user_prompt = f"""<context>
<file>{result.file}</file>
<action>{result.action}</action>
</context>
{original_section}
<generated_code_with_issues>
```php
{result.content}
```
</generated_code_with_issues>

<issues_to_fix>
{chr(10).join(f"- {issue}" for issue in issues)}
</issues_to_fix>

<codebase_reference>
{context.to_prompt_string()}
</codebase_reference>

<output_format>
{{
  "file": "{result.file}",
  "action": "{result.action}",
  "content": "complete fixed file content",
  "fixes_applied": ["Brief description of each fix made"]
}}
</output_format>"""

        try:
            response = await self._call_claude(user_prompt, FIX_SYSTEM_PROMPT)
            data = self._parse_response(response)

            content = data.get("content", "")
            diff = self._generate_diff(result.original_content, content, result.file)

            return ExecutionResult(
                file=result.file,
                action=result.action,
                content=content,
                diff=diff,
                original_content=result.original_content,
            )

        except Exception as e:
            logger.error(f"[EXECUTOR] Fix failed: {e}")
            return result  # Return original on failure

    async def self_verify(
        self,
        result: ExecutionResult,
    ) -> tuple[bool, list[str]]:
        """
        Perform quick self-verification on generated code.

        Args:
            result: The execution result to verify

        Returns:
            Tuple of (passes_verification, list of issues)
        """
        if result.action == "delete" or not result.content:
            return True, []

        logger.info(f"[EXECUTOR] Self-verifying {result.file}")

        # Determine language from file extension
        ext = result.file.split(".")[-1] if "." in result.file else "php"
        language = "php" if ext == "php" else ext

        user_prompt = safe_format(
            SELF_VERIFICATION_USER,
            file_path=result.file,
            action=result.action,
            language=language,
            content=result.content[:8000],  # Limit content for quick check
        )

        try:
            # Use a smaller model for quick verification (could be Haiku)
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=[{"role": "user", "content": user_prompt}],
                system=SELF_VERIFICATION_SYSTEM,  # Static prompt - gets cached!
                temperature=0.1,
                max_tokens=512,
                request_type="verification",
            )

            data = self._parse_response(response)
            passes = data.get("passes_verification", True)
            issues = data.get("issues", [])

            if not passes:
                logger.warning(f"[EXECUTOR] Self-verification found issues: {issues}")

            return passes, issues

        except Exception as e:
            logger.error(f"[EXECUTOR] Self-verification failed: {e}")
            # On verification failure, assume it passes to not block
            return True, []

    async def recover_from_error(
        self,
        step: PlanStep,
        error_type: str,
        error_message: str,
        partial_output: str = "",
    ) -> ExecutionResult:
        """
        Attempt to recover from a code generation error.

        Args:
            step: The plan step that failed
            error_type: Type of error (json_parse, syntax, incomplete, validation)
            error_message: The error message
            partial_output: Any partial output from the failed attempt

        Returns:
            ExecutionResult with recovered code, or failed result
        """
        logger.info(f"[EXECUTOR] Attempting error recovery for {step.file}")

        user_prompt = f"""<original_task>
<description>{step.description}</description>
<file_path>{step.file}</file_path>
</original_task>

<failed_attempt>
<error_type>{error_type}</error_type>
<error_message>{error_message}</error_message>
<partial_output>
{partial_output[:4000] if partial_output else "No output captured"}
</partial_output>
</failed_attempt>

<output_format>
{{
  "file": "{step.file}",
  "action": "{step.action}",
  "content": "complete corrected file content",
  "recovery_notes": "Brief description of what was fixed"
}}
</output_format>"""

        try:
            response = await self._call_claude(user_prompt, ERROR_RECOVERY_SYSTEM)
            data = self._parse_response(response)

            content = data.get("content", "")
            if not content:
                raise ValueError("Recovery produced empty content")

            diff = self._generate_diff("", content, step.file)

            logger.info(f"[EXECUTOR] Error recovery successful for {step.file}")

            return ExecutionResult(
                file=step.file,
                action=step.action,
                content=content,
                diff=diff,
                original_content="",
            )

        except Exception as e:
            logger.error(f"[EXECUTOR] Error recovery failed: {e}")
            return ExecutionResult(
                file=step.file,
                action=step.action,
                content="",
                success=False,
                error=f"Error recovery failed: {str(e)}",
            )
