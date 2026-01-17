"""
Executor Agent.

Executes individual plan steps by generating code changes.
Uses Claude Sonnet for high-quality code generation.
"""
import difflib
import json
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

from app.agents.planner import PlanStep
from app.agents.context_retriever import RetrievedContext
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)

EXECUTION_PROMPT_CREATE = """You are an expert Laravel developer creating a new file.

## Task
{description}

## File to Create
{file_path}

## Codebase Context
{context}

## Previous Steps Results
{previous_results}

## Instructions
Generate the complete content for this new file following Laravel best practices:

1. Follow PSR-12 coding standards
2. Use appropriate namespaces based on file path
3. Include proper docblocks and type hints
4. Follow the patterns you see in the existing codebase
5. Make the code production-ready

Respond with a JSON object:
{{
  "file": "{file_path}",
  "action": "create",
  "content": "<?php\\n\\nnamespace App\\\\...;\\n\\n..."
}}

The content should be the complete file content, properly escaped for JSON.
Respond ONLY with the JSON object."""

EXECUTION_PROMPT_MODIFY = """You are an expert Laravel developer modifying an existing file.

## Task
{description}

## File to Modify
{file_path}

## Current File Content
```php
{current_content}
```

## Codebase Context
{context}

## Previous Steps Results
{previous_results}

## Instructions
Modify this file according to the task. Guidelines:

1. Make minimal changes necessary to accomplish the task
2. Preserve existing code style and patterns
3. Don't remove unrelated code
4. Add proper docblocks for new methods
5. Maintain backwards compatibility where possible

Respond with a JSON object:
{{
  "file": "{file_path}",
  "action": "modify",
  "content": "complete new file content here"
}}

The content should be the COMPLETE file content after modifications.
Respond ONLY with the JSON object."""

EXECUTION_PROMPT_DELETE = """You are confirming a file deletion.

## Task
{description}

## File to Delete
{file_path}

## Current File Content
```php
{current_content}
```

## Instructions
Confirm this file should be deleted and explain why.

Respond with a JSON object:
{{
  "file": "{file_path}",
  "action": "delete",
  "content": "",
  "reason": "Brief explanation of why this file is being deleted"
}}

Respond ONLY with the JSON object."""


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

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionResult":
        """Create from dictionary."""
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
    """

    def __init__(self, claude_service: Optional[ClaudeService] = None):
        """
        Initialize the executor.

        Args:
            claude_service: Optional Claude service instance.
        """
        self.claude = claude_service or get_claude_service()
        logger.info("[EXECUTOR] Initialized")

    async def execute_step(
        self,
        step: PlanStep,
        context: RetrievedContext,
        previous_results: list[ExecutionResult],
        current_file_content: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a single plan step.

        Args:
            step: The plan step to execute
            context: Retrieved codebase context
            previous_results: Results from previous steps
            current_file_content: Current content of the file (for modify/delete)

        Returns:
            ExecutionResult with generated code
        """
        logger.info(f"[EXECUTOR] Executing step {step.order}: [{step.action}] {step.file}")

        # Format previous results for context
        prev_results_str = self._format_previous_results(previous_results)

        try:
            if step.action == "create":
                result = await self._execute_create(
                    step, context, prev_results_str
                )
            elif step.action == "modify":
                result = await self._execute_modify(
                    step, context, prev_results_str, current_file_content or ""
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

            logger.info(f"[EXECUTOR] Step {step.order} completed successfully")
            return result

        except Exception as e:
            logger.error(f"[EXECUTOR] Step {step.order} failed: {e}")
            return ExecutionResult(
                file=step.file,
                action=step.action,
                content="",
                success=False,
                error=str(e),
            )

    async def _execute_create(
        self,
        step: PlanStep,
        context: RetrievedContext,
        previous_results: str,
    ) -> ExecutionResult:
        """Execute a create action."""
        prompt = EXECUTION_PROMPT_CREATE.format(
            description=step.description,
            file_path=step.file,
            context=context.to_prompt_string(),
            previous_results=previous_results,
        )

        response = await self._call_claude(prompt)
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
    ) -> ExecutionResult:
        """Execute a modify action."""
        prompt = EXECUTION_PROMPT_MODIFY.format(
            description=step.description,
            file_path=step.file,
            current_content=current_content,
            context=context.to_prompt_string(),
            previous_results=previous_results,
        )

        response = await self._call_claude(prompt)
        data = self._parse_response(response)

        content = data.get("content", "")

        # Generate unified diff
        diff = self._generate_diff(current_content, content, step.file)

        return ExecutionResult(
            file=step.file,
            action="modify",
            content=content,
            diff=diff,
            original_content=current_content,
        )

    async def _execute_delete(
        self,
        step: PlanStep,
        context: RetrievedContext,
        current_content: str,
    ) -> ExecutionResult:
        """Execute a delete action."""
        prompt = EXECUTION_PROMPT_DELETE.format(
            description=step.description,
            file_path=step.file,
            current_content=current_content,
        )

        response = await self._call_claude(prompt)
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

    async def _call_claude(self, prompt: str) -> str:
        """Call Claude with the prompt."""
        messages = [{"role": "user", "content": prompt}]

        return await self.claude.chat_async(
            model=ClaudeModel.SONNET,
            messages=messages,
            temperature=0.3,  # Lower temperature for more consistent code
            max_tokens=8192,  # Allow for larger files
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
        results: list[ExecutionResult],
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

        prompt = f"""You are an expert Laravel developer fixing code issues.

## File
{result.file}

## Current Generated Code
```php
{result.content}
```

## Issues to Fix
{chr(10).join(f"- {issue}" for issue in issues)}

## Codebase Context
{context.to_prompt_string()}

## Instructions
Fix the issues in the code while maintaining the intended functionality.

Respond with a JSON object:
{{
  "file": "{result.file}",
  "action": "{result.action}",
  "content": "fixed complete file content"
}}

Respond ONLY with the JSON object."""

        try:
            response = await self._call_claude(prompt)
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
