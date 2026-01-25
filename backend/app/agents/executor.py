"""
Forge (Executor) Agent v2 - Enhanced Code Generation Engine.

Executes plan steps by generating production-ready Laravel code.
Uses pattern extraction, chain-of-thought reasoning, and precision modification.

ENHANCEMENTS:
- Group A: Context-aware pattern extraction for style matching
- Group B: Chain-of-thought reasoning before code generation
- Group D: Precision modification with smart insertion points
"""
import difflib
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple

from app.agents.config import AgentConfig, agent_config
from app.agents.context_retriever import RetrievedContext
from app.agents.planner import PlanStep
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

# Import Laravel intelligence (Phase 2)
try:
    from app.agents.forge_laravel import get_laravel_enhancement, LaravelFileDetector

    LARAVEL_INTELLIGENCE_AVAILABLE = True
except ImportError:
    LARAVEL_INTELLIGENCE_AVAILABLE = False
    get_laravel_enhancement = None
    LaravelFileDetector = None

logger = logging.getLogger(__name__)


def safe_format(template: str, **kwargs) -> str:
    """Safely format template with values that may contain curly braces."""
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    return result


# =============================================================================
# DATA CLASSES - Pattern Extraction & Reasoning
# =============================================================================

@dataclass
class CodePatterns:
    """Extracted coding patterns from codebase context (Group A)."""

    # Indentation & Formatting
    indent_style: str = "spaces"  # spaces or tabs
    indent_size: int = 4
    line_ending: str = "lf"

    # PHP/Laravel Specific
    declare_strict_types: bool = True
    use_statement_style: str = "grouped"  # grouped, alphabetical, or by_type
    docblock_style: str = "full"  # full, minimal, or none

    # Naming Conventions (detected from context)
    method_naming: str = "camelCase"
    property_naming: str = "camelCase"
    constant_naming: str = "UPPER_SNAKE"

    # Patterns Found
    uses_repository_pattern: bool = False
    uses_service_pattern: bool = False
    uses_dto_pattern: bool = False
    uses_action_pattern: bool = False

    # Base Classes & Traits
    base_controller: str = "Controller"
    base_model: str = "Model"
    common_traits: List[str] = field(default_factory=list)

    # Example Snippets (for style matching)
    sample_docblock: str = ""
    sample_method: str = ""
    sample_constructor: str = ""

    def to_prompt_string(self) -> str:
        """Convert patterns to prompt-friendly format."""
        lines = [
            "<detected_patterns>",
            f"  <formatting indent='{self.indent_size} {self.indent_style}' strict_types='{self.declare_strict_types}'/>",
            f"  <naming methods='{self.method_naming}' properties='{self.property_naming}'/>",
            f"  <docblocks style='{self.docblock_style}'/>",
        ]

        if self.uses_repository_pattern:
            lines.append("  <pattern>Repository Pattern in use</pattern>")
        if self.uses_service_pattern:
            lines.append("  <pattern>Service Layer Pattern in use</pattern>")
        if self.common_traits:
            lines.append(f"  <common_traits>{', '.join(self.common_traits)}</common_traits>")

        if self.sample_docblock:
            lines.append(f"  <sample_docblock>\n{self.sample_docblock}\n  </sample_docblock>")

        lines.append("</detected_patterns>")
        return "\n".join(lines)


@dataclass
class ExecutionReasoning:
    """Chain-of-thought reasoning before code generation (Group B)."""

    # Understanding
    task_understanding: str = ""
    file_purpose: str = ""

    # Analysis
    required_imports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # For MODIFY actions
    insertion_point: str = ""  # Where to add new code
    preservation_notes: str = ""  # What must NOT be changed

    # Plan
    implementation_steps: List[str] = field(default_factory=list)

    # Risks
    potential_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InsertionPoint:
    """Smart insertion point for modifications (Group D)."""

    line_number: int
    anchor_text: str  # Text to search for as anchor
    position: str  # "before", "after", "replace"
    context_lines: int = 3  # Lines of context for matching
    confidence: float = 1.0


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
    warnings: List[str] = field(default_factory=list)
    reasoning: Optional[ExecutionReasoning] = None  # NEW: Include reasoning
    patterns_used: Optional[CodePatterns] = None  # NEW: Include patterns

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = asdict(self)
        # Handle nested dataclasses
        if self.reasoning:
            result['reasoning'] = self.reasoning.to_dict()
        if self.patterns_used:
            result['patterns_used'] = asdict(self.patterns_used)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionResult":
        """Create from dictionary."""
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


# =============================================================================
# SYSTEM PROMPTS - Enhanced with CoT and Pattern Awareness
# =============================================================================

REASONING_SYSTEM_PROMPT = """<role>
You are an expert Laravel architect analyzing a code generation task.
Your job is to THINK through the implementation before any code is written.
</role>

<task>
Analyze the task and produce a structured reasoning that will guide code generation.
Focus on: understanding, dependencies, implementation approach, and risks.
</task>

<output_requirements>
Respond ONLY with a JSON object. Be concise but thorough.
</output_requirements>"""

REASONING_USER_PROMPT = """<task>
<action>{action}</action>
<file>{file_path}</file>
<description>{description}</description>
</task>

<current_file_content>
{current_content}
</current_file_content>

<codebase_patterns>
{patterns}
</codebase_patterns>

<codebase_context>
{context}
</codebase_context>

Think through this task step by step. Output JSON:
{{
  "task_understanding": "One sentence: what are we trying to accomplish?",
  "file_purpose": "One sentence: what is/will be this file's responsibility?",
  "required_imports": ["List of use statements needed"],
  "dependencies": ["Classes/services this will depend on"],
  "insertion_point": "For MODIFY: describe WHERE to add code (e.g., 'after the constructor', 'inside the boot method')",
  "preservation_notes": "For MODIFY: what existing code MUST be preserved",
  "implementation_steps": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ..."
  ],
  "potential_issues": ["Any risks or edge cases to handle"]
}}"""

EXECUTION_SYSTEM_CREATE = """<role>
You are Forge, an expert Laravel developer creating production-ready code.
Your code will be directly added to the codebase - it must be complete and correct.
</role>

<chain_of_thought>
You have been provided with:
1. A reasoning analysis of the task
2. Detected code patterns from the codebase
3. Relevant code context

USE this information to generate code that:
- Matches the existing codebase style exactly
- Follows the detected patterns and conventions
- Implements the complete functionality without placeholders
</chain_of_thought>

<code_requirements>
**Structure:**
- Correct namespace based on file path
- All necessary use statements (check reasoning.required_imports)
- Class docblock matching detected style
- Method docblocks with @param, @return, @throws

**Style Matching:**
- Match indentation from detected_patterns
- Match docblock style from sample_docblock
- Match naming conventions from detected_patterns
- Use same patterns (Repository, Service, etc.) if detected

**Quality:**
- PSR-12 formatting
- Strict type declarations if pattern shows it
- Complete error handling
- No TODOs or placeholders
</code_requirements>

<verification>
Before responding, verify:
1. Namespace matches file path exactly
2. All imports from reasoning.required_imports included
3. Style matches detected_patterns
4. No placeholder code remains
5. JSON is valid with properly escaped content
</verification>

Respond ONLY with the JSON object."""

EXECUTION_SYSTEM_MODIFY = """<role>
You are Forge, an expert Laravel developer making precise code modifications.
Your changes will appear in a code review diff - make targeted, reviewable changes.
</role>

<critical_rule>
**PRESERVE ALL EXISTING CODE**
- You are ADDING to or MODIFYING existing code, NOT replacing the file
- The output must contain the ENTIRE file with your changes integrated
- If original has 100 lines and you add 10, result should have ~110 lines
- NEVER delete functionality unless explicitly requested
</critical_rule>

<chain_of_thought>
You have been provided with:
1. A reasoning analysis including WHERE to insert code (insertion_point)
2. Notes on what to preserve (preservation_notes)
3. The current file content
4. Detected code patterns

USE the insertion_point to determine exactly where your changes go.
USE preservation_notes to ensure you don't break existing functionality.
</chain_of_thought>

<modification_strategy>
**For Adding Methods:**
1. Find the insertion_point location
2. Match existing method style (docblocks, spacing, type hints)
3. Add the new method with proper spacing before/after

**For Adding Properties:**
1. Group with related properties
2. Match visibility and type hint style

**For Adding Routes:**
1. Find the appropriate route group
2. ADD the new route - never replace existing routes
3. Match naming and middleware patterns

**For Adding Imports:**
1. Add in alphabetical order with existing imports
2. Group by type if that's the pattern
</modification_strategy>

<diff_awareness>
Your changes should produce a clean diff:
- Mostly '+' lines (additions), minimal '-' lines
- Changes grouped logically
- No reformatting of unchanged code
- If diff shows entire file replaced, you're doing it WRONG
</diff_awareness>

<verification>
Before responding:
1. Count: Does output have >= original line count (unless deleting)?
2. Check: Are all original functions/routes/classes still present?
3. Verify: Does new code match existing style?
4. Confirm: Is insertion at the correct location?
</verification>

IMPORTANT: Output the COMPLETE file content, not just changes.
Respond ONLY with the JSON object."""

EXECUTION_SYSTEM_DELETE = """<role>
You are Forge, confirming a safe file deletion.
Deletions are destructive - verify safety before proceeding.
</role>

<safety_checks>
Before confirming deletion:
1. No active references to this file elsewhere?
2. No route references to this controller/middleware?
3. No config references to this class?
4. Is replacement ready if this is part of refactor?
5. Could the task be done without deletion?

If ANY check fails, set safe_to_delete to false.
</safety_checks>

Respond ONLY with the JSON object."""

EXECUTION_USER_CREATE = """<reasoning_analysis>
{reasoning}
</reasoning_analysis>

<detected_patterns>
{patterns}
</detected_patterns>

<task>
<action>create</action>
<file_path>{file_path}</file_path>
<description>{description}</description>
</task>

<codebase_context>
{context}
</codebase_context>

<previous_steps>
{previous_results}
</previous_steps>

Generate the complete file following the reasoning and matching detected patterns.

<output_format>
{{
  "file": "{file_path}",
  "action": "create",
  "content": "complete file content as properly escaped string"
}}
</output_format>"""

EXECUTION_USER_MODIFY = """<reasoning_analysis>
{reasoning}
</reasoning_analysis>

<detected_patterns>
{patterns}
</detected_patterns>

<task>
<action>modify</action>
<file_path>{file_path}</file_path>
<description>{description}</description>
</task>

<current_file_content>
```php
{current_content}
```
</current_file_content>

<codebase_context>
{context}
</codebase_context>

<previous_steps>
{previous_results}
</previous_steps>

Modify the file following the reasoning. Insert at the specified insertion_point.
Preserve ALL existing code as noted in preservation_notes.

<output_format>
{{
  "file": "{file_path}",
  "action": "modify",
  "content": "COMPLETE file content after modifications - entire file, not just changes"
}}
</output_format>"""

EXECUTION_USER_DELETE = """<task>
<action>delete</action>
<file_path>{file_path}</file_path>
<description>{description}</description>
</task>

<current_file_content>
```php
{current_content}
```
</current_file_content>

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

SELF_VERIFICATION_SYSTEM = """<role>
You are a code reviewer performing verification on generated Laravel code.
</role>

<checks>
1. **Syntax**: Valid PHP syntax? Proper brackets, semicolons?
2. **Imports**: All used classes imported with 'use' statements?
3. **Namespace**: Matches file path? (app/Services/X.php → App\\Services)
4. **Class name**: Matches filename?
5. **PHP tags**: Starts with <?php?
6. **Completeness**: No TODO, FIXME, or placeholders?
7. **For MODIFY**: Original functionality preserved?
</checks>

Respond ONLY with JSON. Be quick and focused."""

SELF_VERIFICATION_USER = """<file_info>
<file_path>{file_path}</file_path>
<action>{action}</action>
</file_info>

<generated_code>
```{language}
{content}
```
</generated_code>

<original_content>
{original_content}
</original_content>

<output_format>
{{
  "passes_verification": true | false,
  "issues": ["List of critical issues found, empty if none"],
  "content_preserved": true | false,
  "confidence": "high" | "medium" | "low"
}}
</output_format>"""

FIX_SYSTEM_PROMPT = """<role>
You are Forge fixing specific code issues. Focus ONLY on the identified issues.
</role>

<critical_rules>
- Keep ALL existing functionality intact
- Make minimal changes to fix identified issues
- Output the ENTIRE file, not just fixes
- For "content lost" errors: restore from original_file_content
</critical_rules>

Respond ONLY with the JSON object."""


# =============================================================================
# EXECUTOR CLASS - Enhanced Implementation
# =============================================================================

class Executor:
    """
    Forge - The Code Generation Engine.

    Enhanced with:
    - Pattern extraction from codebase context (Group A)
    - Chain-of-thought reasoning before generation (Group B)
    - Precision modification with smart insertion (Group D)
    """

    def __init__(
            self,
            claude_service: Optional[ClaudeService] = None,
            config: Optional[AgentConfig] = None,
    ):
        """Initialize the executor."""
        self.claude = claude_service or get_claude_service()
        self.config = config or agent_config
        logger.info("[FORGE] Initialized with enhanced execution pipeline")

    # =========================================================================
    # MAIN EXECUTION METHODS
    # =========================================================================

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
        Execute a plan step with enhanced pipeline.

        Pipeline:
        1. Extract patterns from context (Group A)
        2. Generate reasoning for the task (Group B)
        3. Execute with precision (Group D)
        4. Verify and fix if needed
        """
        logger.info(f"[FORGE] Executing step {step.order}: [{step.action}] {step.file}")

        # Validate file exists for modify actions
        if step.action == "modify" and self.config.REQUIRE_FILE_EXISTS_FOR_MODIFY:
            if not current_file_content:
                logger.error(f"[FORGE] Cannot modify non-existent file: {step.file}")
                return ExecutionResult(
                    file=step.file,
                    action=step.action,
                    content="",
                    success=False,
                    error=f"File '{step.file}' not found. Use 'create' for new files.",
                    warnings=["File not found for modify action"]
                )

        warnings = []
        if context.confidence_level in ("low", "insufficient"):
            warnings.append(f"Low context confidence ({context.confidence_level})")

        try:
            # STEP 1: Extract patterns from context (Group A)
            patterns = self._extract_code_patterns(context, step.file)
            logger.info(
                f"[FORGE] Extracted patterns: strict_types={patterns.declare_strict_types}, docblock={patterns.docblock_style}")

            # STEP 2: Generate reasoning (Group B)
            reasoning = await self._generate_reasoning(
                step=step,
                patterns=patterns,
                context=context,
                current_content=current_file_content or "",
            )
            logger.info(f"[FORGE] Reasoning complete: {len(reasoning.implementation_steps)} steps planned")

            # STEP 3: Execute with precision (Group D)
            prev_results_str = self._format_previous_results(previous_results)

            if step.action == "create":
                result = await self._execute_create(
                    step, context, prev_results_str, patterns, reasoning
                )
            elif step.action == "modify":
                result = await self._execute_modify(
                    step, context, prev_results_str, current_file_content or "",
                    patterns, reasoning
                )
            elif step.action == "delete":
                result = await self._execute_delete(
                    step, context, current_file_content or ""
                )
            else:
                return ExecutionResult(
                    file=step.file, action=step.action, content="",
                    success=False, error=f"Unknown action: {step.action}"
                )

            # Attach metadata to result
            result.warnings.extend(warnings)
            result.reasoning = reasoning
            result.patterns_used = patterns

            # STEP 4: Verify and fix if needed
            if enable_self_verification and result.content:
                passes, issues = await self._verify_result(result, current_file_content)
                if not passes and issues:
                    logger.info(f"[FORGE] Fixing {len(issues)} verification issues")
                    result = await self._fix_execution(result, issues, context, patterns)

            logger.info(f"[FORGE] Step {step.order} completed successfully")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"[FORGE] JSON parse error: {e}")
            return await self._recover_from_error(step, "json_parse", str(e), "")

        except Exception as e:
            logger.error(f"[FORGE] Step {step.order} failed: {e}")
            return ExecutionResult(
                file=step.file, action=step.action, content="",
                success=False, error=str(e), warnings=warnings
            )

    # =========================================================================
    # LARAVEL INTELLIGENCE INTEGRATION (Phase 2)
    # =========================================================================

    def _get_laravel_context(
            self,
            file_path: str,
            description: str,
            current_content: str,
            context: RetrievedContext,
    ) -> str:
        """
        Get Laravel-specific context enhancement.

        Integrates with forge_laravel.py to provide:
        - File type detection
        - Laravel conventions
        - Code snippets and suggestions
        """
        if not LARAVEL_INTELLIGENCE_AVAILABLE or not get_laravel_enhancement:
            return ""

        try:
            enhancement = get_laravel_enhancement(
                file_path=file_path,
                description=description,
                current_content=current_content,
                context_chunks=context.chunks,
            )

            # Format for prompt inclusion
            parts = ["\n<laravel_intelligence>"]

            # File type info
            parts.append(f"  <file_type>{enhancement.get('file_type', 'unknown')}</file_type>")

            # Conventions
            conventions = enhancement.get("conventions", {})
            if conventions:
                parts.append("  <conventions>")
                for key, value in conventions.items():
                    parts.append(f"    <{key}>{value}</{key}>")
                parts.append("  </conventions>")

            # Suggestions
            suggestions = enhancement.get("suggestions", [])
            if suggestions:
                parts.append("  <suggestions>")
                for suggestion in suggestions:
                    parts.append(f"    <suggestion>{suggestion}</suggestion>")
                parts.append("  </suggestions>")

            # Code snippets (samples)
            snippets = enhancement.get("code_snippets", {})
            if snippets:
                parts.append("  <code_samples>")
                for name, code in snippets.items():
                    parts.append(f"    <sample name='{name}'>{code}</sample>")
                parts.append("  </code_samples>")

            parts.append("</laravel_intelligence>")

            return "\n".join(parts)

        except Exception as e:
            logger.warning(f"[FORGE] Laravel intelligence failed: {e}")
            return ""

    # =========================================================================
    # GROUP A: PATTERN EXTRACTION
    # =========================================================================

    def _extract_code_patterns(
            self,
            context: RetrievedContext,
            target_file: str,
    ) -> CodePatterns:
        """
        Extract coding patterns from codebase context.

        Analyzes context chunks to detect:
        - Indentation style and size
        - Docblock format
        - Naming conventions
        - Architectural patterns (Repository, Service, etc.)
        - Common base classes and traits
        """
        patterns = CodePatterns()

        if not context.chunks:
            return patterns

        # Collect code samples for analysis
        php_samples = []
        for chunk in context.chunks:
            if chunk.file_path.endswith('.php'):
                php_samples.append(chunk.content)

        if not php_samples:
            return patterns

        # Analyze first few samples
        combined = "\n".join(php_samples[:5])

        # Detect strict types
        patterns.declare_strict_types = "declare(strict_types=1)" in combined

        # Detect indentation
        indent_match = re.search(r'\n(\s+)(public|private|protected|function)', combined)
        if indent_match:
            indent = indent_match.group(1)
            patterns.indent_style = "tabs" if "\t" in indent else "spaces"
            patterns.indent_size = len(indent.replace("\t", "    "))

        # Detect docblock style
        if "/**\n" in combined and "@param" in combined:
            patterns.docblock_style = "full"
        elif "/**" in combined:
            patterns.docblock_style = "minimal"
        else:
            patterns.docblock_style = "none"

        # Extract sample docblock
        docblock_match = re.search(r'(/\*\*[\s\S]*?\*/)\s*\n\s*(public|private|protected)', combined)
        if docblock_match:
            patterns.sample_docblock = docblock_match.group(1)

        # Detect architectural patterns
        patterns.uses_repository_pattern = "Repository" in combined and "interface" in combined.lower()
        patterns.uses_service_pattern = "Service" in combined and "app/Services" in str(
            [c.file_path for c in context.chunks])
        patterns.uses_dto_pattern = "DTO" in combined or "DataTransferObject" in combined
        patterns.uses_action_pattern = "Action" in combined and "handle(" in combined

        # Detect common traits
        trait_matches = re.findall(r'use\s+([\w\\]+Trait|HasFactory|SoftDeletes|Notifiable)', combined)
        patterns.common_traits = list(set(trait_matches))

        # Detect base classes
        controller_match = re.search(r'extends\s+([\w\\]*Controller)', combined)
        if controller_match:
            patterns.base_controller = controller_match.group(1)

        return patterns

    # =========================================================================
    # GROUP B: CHAIN-OF-THOUGHT REASONING
    # =========================================================================

    async def _generate_reasoning(
            self,
            step: PlanStep,
            patterns: CodePatterns,
            context: RetrievedContext,
            current_content: str,
    ) -> ExecutionReasoning:
        """
        Generate chain-of-thought reasoning before code generation.

        This helps Claude:
        1. Understand the task completely
        2. Identify required imports/dependencies
        3. Plan the implementation steps
        4. For MODIFY: identify exact insertion point
        """
        user_prompt = safe_format(
            REASONING_USER_PROMPT,
            action=step.action,
            file_path=step.file,
            description=step.description,
            current_content=current_content[:5000] if current_content else "N/A - new file",
            patterns=patterns.to_prompt_string(),
            context=context.to_prompt_string()[:8000],
        )

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=[{"role": "user", "content": user_prompt}],
                system=REASONING_SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=2048,
                request_type="reasoning",
            )

            data = self._parse_response(response)

            return ExecutionReasoning(
                task_understanding=data.get("task_understanding", ""),
                file_purpose=data.get("file_purpose", ""),
                required_imports=data.get("required_imports", []),
                dependencies=data.get("dependencies", []),
                insertion_point=data.get("insertion_point", ""),
                preservation_notes=data.get("preservation_notes", ""),
                implementation_steps=data.get("implementation_steps", []),
                potential_issues=data.get("potential_issues", []),
            )

        except Exception as e:
            logger.warning(f"[FORGE] Reasoning generation failed: {e}, using defaults")
            return ExecutionReasoning(
                task_understanding=step.description,
                implementation_steps=["Implement as described"],
            )

    # =========================================================================
    # GROUP D: PRECISION EXECUTION
    # =========================================================================

    async def _execute_create(
            self,
            step: PlanStep,
            context: RetrievedContext,
            previous_results: str,
            patterns: CodePatterns,
            reasoning: ExecutionReasoning,
    ) -> ExecutionResult:
        """Execute CREATE action with pattern awareness and reasoning."""

        # Format reasoning for prompt
        reasoning_str = json.dumps(reasoning.to_dict(), indent=2)

        # Get Laravel-specific enhancement (Phase 2)
        laravel_context = self._get_laravel_context(
            step.file, step.description, "", context
        )

        user_prompt = safe_format(
            EXECUTION_USER_CREATE,
            reasoning=reasoning_str,
            patterns=patterns.to_prompt_string(),
            file_path=step.file,
            description=step.description,
            context=context.to_prompt_string() + laravel_context,
            previous_results=previous_results,
        )

        response = await self._call_claude(user_prompt, EXECUTION_SYSTEM_CREATE)
        data = self._parse_response(response)
        content = data.get("content", "")

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
            patterns: CodePatterns,
            reasoning: ExecutionReasoning,
    ) -> ExecutionResult:
        """Execute MODIFY action with precision insertion."""

        # Format reasoning for prompt
        reasoning_str = json.dumps(reasoning.to_dict(), indent=2)

        # Get Laravel-specific enhancement (Phase 2)
        laravel_context = self._get_laravel_context(
            step.file, step.description, current_content, context
        )

        user_prompt = safe_format(
            EXECUTION_USER_MODIFY,
            reasoning=reasoning_str,
            patterns=patterns.to_prompt_string(),
            file_path=step.file,
            description=step.description,
            current_content=current_content,
            context=context.to_prompt_string() + laravel_context,
            previous_results=previous_results,
        )

        response = await self._call_claude(user_prompt, EXECUTION_SYSTEM_MODIFY)
        data = self._parse_response(response)
        content = data.get("content", "")

        diff = self._generate_diff(current_content, content, step.file)

        # Validate content preservation
        warnings = []
        preservation_check = self._check_content_preservation(current_content, content)
        if not preservation_check["preserved"]:
            logger.warning(f"[FORGE] Content may have been lost: {preservation_check['issues']}")
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
        """Execute DELETE action with safety verification."""
        user_prompt = safe_format(
            EXECUTION_USER_DELETE,
            file_path=step.file,
            description=step.description,
            current_content=current_content,
        )

        response = await self._call_claude(user_prompt, EXECUTION_SYSTEM_DELETE)
        data = self._parse_response(response)
        diff = self._generate_diff(current_content, "", step.file)

        return ExecutionResult(
            file=step.file,
            action="delete",
            content="",
            diff=diff,
            original_content=current_content,
        )

    # =========================================================================
    # VERIFICATION & FIXING
    # =========================================================================

    async def _verify_result(
            self,
            result: ExecutionResult,
            original_content: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify generated code passes quality checks."""
        if result.action == "delete" or not result.content:
            return True, []

        logger.info(f"[FORGE] Verifying {result.file}")

        ext = result.file.split(".")[-1] if "." in result.file else "php"
        language = "php" if ext == "php" else ext

        user_prompt = safe_format(
            SELF_VERIFICATION_USER,
            file_path=result.file,
            action=result.action,
            language=language,
            content=result.content[:8000],
            original_content=original_content[:3000] if original_content else "N/A",
        )

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=[{"role": "user", "content": user_prompt}],
                system=SELF_VERIFICATION_SYSTEM,
                temperature=0.1,
                max_tokens=512,
                request_type="verification",
            )

            data = self._parse_response(response)
            passes = data.get("passes_verification", True)
            issues = data.get("issues", [])
            content_preserved = data.get("content_preserved", True)

            # Add content preservation as critical issue if failed
            if result.action == "modify" and not content_preserved:
                issues.insert(0, "CRITICAL: Original file content was not preserved")

            if not passes:
                logger.warning(f"[FORGE] Verification found issues: {issues}")

            return passes, issues

        except Exception as e:
            logger.error(f"[FORGE] Verification failed: {e}")
            return True, []  # Assume pass on verification failure

    async def _fix_execution(
            self,
            result: ExecutionResult,
            issues: List[str],
            context: RetrievedContext,
            patterns: CodePatterns,
    ) -> ExecutionResult:
        """Fix identified issues in generated code."""
        logger.info(f"[FORGE] Fixing execution for {result.file}")

        original_section = ""
        if result.action == "modify" and result.original_content:
            original_section = f"""
<original_file_content>
CRITICAL: This is the ORIGINAL content that MUST be preserved:
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

<detected_patterns>
{patterns.to_prompt_string()}
</detected_patterns>

<output_format>
{{
  "file": "{result.file}",
  "action": "{result.action}",
  "content": "complete fixed file content",
  "fixes_applied": ["Brief description of each fix"]
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
                reasoning=result.reasoning,
                patterns_used=result.patterns_used,
            )

        except Exception as e:
            logger.error(f"[FORGE] Fix failed: {e}")
            return result

    async def _recover_from_error(
            self,
            step: PlanStep,
            error_type: str,
            error_message: str,
            partial_output: str,
    ) -> ExecutionResult:
        """Attempt recovery from code generation error."""
        logger.info(f"[FORGE] Attempting error recovery for {step.file}")

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
  "recovery_notes": "What was fixed"
}}
</output_format>"""

        try:
            response = await self._call_claude(user_prompt, FIX_SYSTEM_PROMPT)
            data = self._parse_response(response)
            content = data.get("content", "")

            if not content:
                raise ValueError("Recovery produced empty content")

            diff = self._generate_diff("", content, step.file)
            logger.info(f"[FORGE] Error recovery successful for {step.file}")

            return ExecutionResult(
                file=step.file,
                action=step.action,
                content=content,
                diff=diff,
                original_content="",
            )

        except Exception as e:
            logger.error(f"[FORGE] Error recovery failed: {e}")
            return ExecutionResult(
                file=step.file,
                action=step.action,
                content="",
                success=False,
                error=f"Error recovery failed: {str(e)}",
            )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def _call_claude(
            self,
            user_prompt: str,
            system_prompt: Optional[str] = None,
    ) -> str:
        """Call Claude with caching-optimized system prompt."""
        messages = [{"role": "user", "content": user_prompt}]

        return await self.claude.chat_async(
            model=ClaudeModel.SONNET,
            messages=messages,
            system=system_prompt,
            temperature=0.3,
            max_tokens=8192,
            request_type="execution",
        )

    def _parse_response(self, response: str) -> dict:
        """Parse JSON response from Claude."""
        response_text = response.strip()

        # Remove markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"[FORGE] Failed to parse response: {e}")
            logger.debug(f"[FORGE] Raw response: {response_text[:500]}...")
            return {"content": "", "error": "Failed to parse response"}

    def _generate_diff(self, original: str, modified: str, filename: str) -> str:
        """Generate unified diff between original and modified content."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

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

    def _format_previous_results(self, results: List[ExecutionResult]) -> str:
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

    def _check_content_preservation(self, original: str, modified: str) -> dict:
        """Check if original content was preserved in modification."""
        issues = []

        if not original or not modified:
            return {"preserved": True, "issues": []}

        original_lines = set(original.strip().split('\n'))
        modified_lines = set(modified.strip().split('\n'))

        # Find significant removals (non-empty, non-comment)
        removed = original_lines - modified_lines
        significant_removals = [
            l for l in removed
            if l.strip() and not l.strip().startswith('//')
        ]

        if len(significant_removals) > len(original_lines) * 0.3:
            issues.append(f"Significant content removal: {len(significant_removals)} lines")

        # Check for key Laravel patterns
        patterns_to_check = [
            (r'Route::', 'Route definitions'),
            (r'use\s+[\w\\]+;', 'Use statements'),
            (r'(public|private|protected)\s+function\s+\w+', 'Method definitions'),
            (r'class\s+\w+', 'Class definitions'),
        ]

        for pattern, description in patterns_to_check:
            original_count = len(re.findall(pattern, original))
            modified_count = len(re.findall(pattern, modified))
            if modified_count < original_count:
                issues.append(f"{description} may have been removed ({original_count} → {modified_count})")

        return {"preserved": len(issues) == 0, "issues": issues}

    # =========================================================================
    # LEGACY COMPATIBILITY METHODS
    # =========================================================================

    async def self_verify(self, result: ExecutionResult) -> Tuple[bool, List[str]]:
        """Legacy method - wraps _verify_result."""
        return await self._verify_result(result, result.original_content)

    async def fix_execution(
            self,
            result: ExecutionResult,
            issues: List[str],
            context: RetrievedContext,
    ) -> ExecutionResult:
        """Legacy method - wraps _fix_execution with default patterns."""
        patterns = CodePatterns()
        return await self._fix_execution(result, issues, context, patterns)

    async def recover_from_error(
            self,
            step: PlanStep,
            error_type: str,
            error_message: str,
            partial_output: str = "",
    ) -> ExecutionResult:
        """Legacy method - wraps _recover_from_error."""
        return await self._recover_from_error(step, error_type, error_message, partial_output)
