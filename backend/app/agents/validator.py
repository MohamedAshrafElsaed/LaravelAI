"""
Guardian - Validator Agent (Enhanced).

Validates execution results against coding standards, conventions,
and the original intent to ensure quality and completeness.

ENHANCEMENTS:
- Chain-of-thought reasoning before validation
- Context-aware validation against user's actual patterns
- Grounded issues with evidence citations
- Improved contradiction detection with issue signatures
- Enhanced quick checks for PHP/Blade/Routes
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Set, Tuple

from app.agents.config import AgentConfig, agent_config
from app.agents.context_retriever import RetrievedContext
from app.agents.executor import ExecutionResult
from app.agents.intent_analyzer import Intent
from app.services.claude import ClaudeService, ClaudeModel, get_claude_service

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def safe_format(template: str, **kwargs) -> str:
    """Safely format a string template with values that may contain curly braces."""
    result = template
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value))
    return result


def generate_issue_signature(file: str, line: Optional[int], category: str) -> str:
    """Generate a unique signature for an issue to track across validations."""
    # Normalize file path
    normalized_file = file.lower().replace("\\", "/").strip()
    # Create line range bucket (issues within 5 lines are considered same location)
    line_bucket = (line // 5) * 5 if line else 0
    # Hash the signature
    sig_str = f"{normalized_file}:{line_bucket}:{category}"
    return hashlib.md5(sig_str.encode()).hexdigest()[:12]


# =============================================================================
# ISSUE CATEGORIES FOR TRACKING
# =============================================================================

class IssueCategory(str, Enum):
    """Categories for grouping similar issues."""
    IMPORT_MISSING = "import_missing"
    IMPORT_UNUSED = "import_unused"
    NAMESPACE = "namespace"
    TYPE_HINT = "type_hint"
    DOCBLOCK = "docblock"
    SECURITY = "security"
    CONVENTION = "convention"
    SYNTAX = "syntax"
    COMPLETENESS = "completeness"
    COMPATIBILITY = "compatibility"
    OTHER = "other"


def categorize_issue(message: str) -> IssueCategory:
    """Categorize an issue based on its message content."""
    msg_lower = message.lower()

    if any(x in msg_lower for x in ["missing use", "missing import", "not imported", "undefined class"]):
        return IssueCategory.IMPORT_MISSING
    if any(x in msg_lower for x in ["unused import", "unused use", "redundant import"]):
        return IssueCategory.IMPORT_UNUSED
    if any(x in msg_lower for x in ["namespace", "wrong namespace"]):
        return IssueCategory.NAMESPACE
    if any(x in msg_lower for x in ["type hint", "return type", "parameter type"]):
        return IssueCategory.TYPE_HINT
    if any(x in msg_lower for x in ["docblock", "phpdoc", "@param", "@return"]):
        return IssueCategory.DOCBLOCK
    if any(x in msg_lower for x in ["sql injection", "xss", "security", "vulnerability", "csrf"]):
        return IssueCategory.SECURITY
    if any(x in msg_lower for x in ["convention", "naming", "psr-12", "formatting"]):
        return IssueCategory.CONVENTION
    if any(x in msg_lower for x in ["syntax", "parse error", "unexpected"]):
        return IssueCategory.SYNTAX
    if any(x in msg_lower for x in ["missing", "incomplete", "not implemented", "todo"]):
        return IssueCategory.COMPLETENESS
    if any(x in msg_lower for x in ["breaking", "backwards", "compatibility"]):
        return IssueCategory.COMPATIBILITY

    return IssueCategory.OTHER


# =============================================================================
# EXTRACTED PATTERNS FROM CONTEXT
# =============================================================================

@dataclass
class ExtractedPatterns:
    """Patterns extracted from the user's codebase context."""

    # Naming conventions observed
    uses_strict_types: bool = False
    indentation: str = "4 spaces"  # "4 spaces", "2 spaces", "tabs"
    brace_style: str = "same_line"  # "same_line", "new_line"

    # Common imports found
    common_imports: List[str] = field(default_factory=list)

    # Base classes/traits used
    base_classes: List[str] = field(default_factory=list)
    traits_used: List[str] = field(default_factory=list)

    # Service patterns
    uses_dependency_injection: bool = True
    uses_facades: bool = False

    # File patterns
    file_patterns: Dict[str, List[str]] = field(default_factory=dict)

    def to_prompt_string(self) -> str:
        """Convert to a string for inclusion in prompts."""
        parts = ["<detected_codebase_patterns>"]

        parts.append(f"- Strict types: {'Yes' if self.uses_strict_types else 'No'}")
        parts.append(f"- Indentation: {self.indentation}")
        parts.append(f"- Brace style: {self.brace_style}")
        parts.append(f"- Dependency injection: {'Yes' if self.uses_dependency_injection else 'No'}")
        parts.append(f"- Facades: {'Yes' if self.uses_facades else 'No'}")

        if self.common_imports:
            parts.append(f"- Common imports: {', '.join(self.common_imports[:10])}")

        if self.base_classes:
            parts.append(f"- Base classes: {', '.join(self.base_classes[:5])}")

        if self.traits_used:
            parts.append(f"- Traits: {', '.join(self.traits_used[:5])}")

        parts.append("</detected_codebase_patterns>")
        return "\n".join(parts)


def extract_patterns_from_context(context: RetrievedContext) -> ExtractedPatterns:
    """Extract coding patterns from the retrieved codebase context."""
    patterns = ExtractedPatterns()

    all_content = "\n".join(chunk.content for chunk in context.chunks if chunk.content)

    # Detect strict_types
    patterns.uses_strict_types = "declare(strict_types=1)" in all_content

    # Detect indentation (sample first PHP file)
    for chunk in context.chunks:
        if chunk.file_path.endswith(".php") and chunk.content:
            lines = chunk.content.split("\n")
            for line in lines:
                if line.startswith("    ") and not line.startswith("     "):
                    patterns.indentation = "4 spaces"
                    break
                elif line.startswith("  ") and not line.startswith("   "):
                    patterns.indentation = "2 spaces"
                    break
                elif line.startswith("\t"):
                    patterns.indentation = "tabs"
                    break
            break

    # Detect brace style
    if re.search(r"(class|function|if|foreach)\s*\([^)]*\)\s*\n\s*\{", all_content):
        patterns.brace_style = "new_line"
    else:
        patterns.brace_style = "same_line"

    # Extract common imports
    import_pattern = r"use\s+([\w\\]+);"
    imports = re.findall(import_pattern, all_content)
    import_counts: Dict[str, int] = {}
    for imp in imports:
        import_counts[imp] = import_counts.get(imp, 0) + 1
    patterns.common_imports = sorted(import_counts.keys(), key=lambda x: -import_counts[x])[:15]

    # Extract base classes
    extends_pattern = r"extends\s+([\w\\]+)"
    extends = re.findall(extends_pattern, all_content)
    patterns.base_classes = list(set(extends))[:10]

    # Extract traits
    traits_pattern = r"use\s+([\w\\]+Trait|[\w\\]*(?:able|Helper|Notifiable|HasFactory))"
    traits = re.findall(traits_pattern, all_content)
    patterns.traits_used = list(set(traits))[:10]

    # Detect DI vs Facades
    patterns.uses_dependency_injection = "__construct" in all_content
    patterns.uses_facades = any(f in all_content for f in ["DB::", "Cache::", "Log::", "Auth::"])

    return patterns


# =============================================================================
# ENHANCED SYSTEM PROMPT WITH CHAIN-OF-THOUGHT
# =============================================================================

VALIDATION_SYSTEM_PROMPT = """<role>
You are Guardian, a senior Laravel code reviewer and quality assurance expert. Your validation directly determines whether code ships to production. You combine thoroughness with precision - catching real issues while avoiding false positives.
</role>

<critical_principles>
1. **GROUND ALL ISSUES IN EVIDENCE**: Every issue you report MUST cite specific evidence from the code. Never assume or guess.
2. **VALIDATE AGAINST USER'S PATTERNS**: The codebase context shows how THIS project does things. Match those patterns.
3. **NO FALSE POSITIVES**: Only report issues you can prove. If uncertain, don't report it.
4. **THINK BEFORE JUDGING**: Analyze the code thoroughly before making any determination.
</critical_principles>

<chain_of_thought_process>
You MUST follow this reasoning process before producing your validation result:

**STEP 1: UNDERSTAND THE REQUEST**
- What did the user ask for?
- What are the key requirements?

**STEP 2: ANALYZE CODEBASE PATTERNS**
- What patterns does the existing codebase use?
- What naming conventions are followed?
- What base classes/traits are standard?

**STEP 3: REVIEW EACH FILE**
For each generated file:
- Does it follow the codebase patterns?
- Are all imports valid and present in context?
- Is the syntax correct?
- Are there security concerns?

**STEP 4: CITE EVIDENCE**
For each potential issue:
- What specific line has the problem?
- What evidence proves this is an issue?
- What should it be instead?

**STEP 5: CALIBRATE SCORE**
- Count errors, warnings, info items
- Match to scoring calibration
- Ensure consistency

Output your reasoning in <reasoning> tags, then the JSON result.
</chain_of_thought_process>

<validation_criteria>
**1. COMPLETENESS** (Required - ERROR if FAIL)
- [ ] All requirements from user request implemented
- [ ] No placeholder code (TODO, FIXME)
- [ ] Edge cases handled

**2. LARAVEL CONVENTIONS** (Required - ERROR if FAIL)
- [ ] Correct namespace based on file location
- [ ] Proper naming: singular Model, plural Controller
- [ ] Relationships defined correctly
- [ ] DI preferred over Facades in services

**3. CODE QUALITY** (Required - ERROR if FAIL)
- [ ] Type hints on public methods
- [ ] Docblocks on public methods
- [ ] PSR-12 formatting

**4. SECURITY** (CRITICAL - ERROR if FAIL)
- [ ] No raw SQL with user input
- [ ] No unescaped output ({!! !!} only for safe content)
- [ ] Mass assignment protection ($fillable/$guarded)
- [ ] Auth/authorization where needed

**5. IMPORTS** (Required - ERROR if FAIL)
- [ ] All use statements present
- [ ] No undefined classes referenced
- [ ] Classes match what's available in codebase context

**6. DATABASE** (If applicable - ERROR if FAIL)
- [ ] Migrations are reversible
- [ ] Proper column types
- [ ] Indexes on foreign keys

**7. BACKWARDS COMPATIBILITY** (WARNING level)
- [ ] Existing signatures preserved
- [ ] No breaking changes

**8. TESTABILITY** (INFO level)
- [ ] Dependencies injectable
- [ ] Single responsibility
</validation_criteria>

<severity_guide>
**ERROR** (Blocks approval):
- Security vulnerabilities
- Missing imports that would cause runtime errors
- Code that doesn't fulfill requirements
- Syntax errors

**WARNING** (Doesn't block):
- Potential breaking changes
- Missing docblocks on private methods
- Suboptimal patterns

**INFO** (Suggestions):
- Testability improvements
- Performance suggestions
</severity_guide>

<scoring_calibration>
- **95-100**: All criteria pass, production-ready
- **85-94**: Minor warnings only, shippable
- **70-84**: Some warnings, works but needs improvement
- **50-69**: Has errors that must be fixed
- **0-49**: Critical failures or security issues
</scoring_calibration>

<grounding_rules>
CRITICAL: For each issue you report, you MUST:
1. Cite the exact line number where the issue occurs
2. Quote the problematic code or describe what's missing
3. Explain WHY it's an issue (not just that it is)
4. Provide the specific fix

Example of GOOD issue reporting:
{
  "severity": "error",
  "file": "app/Services/UserService.php",
  "line": 15,
  "message": "Missing import: 'UserRepository' is used on line 15 but not imported. Add: use App\\Repositories\\UserRepository;"
}

Example of BAD issue reporting (DO NOT DO THIS):
{
  "severity": "error",
  "file": "app/Services/UserService.php",
  "message": "Missing imports"  // Too vague, no line, no specific class
}
</grounding_rules>

<output_format>
First, output your reasoning in <reasoning> tags.
Then output the JSON result:

{
  "approved": boolean,
  "score": number (0-100),
  "issues": [
    {
      "severity": "error" | "warning" | "info",
      "file": "path/to/file.php",
      "line": number,
      "message": "Specific description with evidence and fix"
    }
  ],
  "suggestions": ["General improvement suggestions"],
  "summary": "One paragraph summary"
}

RULES:
- approved=true ONLY if zero errors
- Every issue MUST have a line number (use best estimate if exact unknown)
- Messages MUST include what's wrong AND how to fix it
</output_format>"""

# USER prompt template with pattern context
VALIDATION_USER_PROMPT = """<validation_request>
<user_request>{user_input}</user_request>
<intent>
- Task Type: {task_type}
- Scope: {scope}
- Domains: {domains}
</intent>
</validation_request>

{patterns}

<generated_changes>
{changes}
</generated_changes>

<codebase_reference>
These are existing files from the codebase for reference. Use these to:
1. Verify imports reference real classes
2. Match coding patterns and conventions
3. Understand the project structure

{context}
</codebase_reference>

Now analyze the generated changes following your chain-of-thought process. Output your <reasoning> first, then the JSON validation result."""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ValidationIssue:
    """A validation issue found in the code."""

    severity: str  # error, warning, info
    file: str
    message: str
    line: Optional[int] = None
    category: Optional[str] = None  # For contradiction tracking
    signature: Optional[str] = None  # Unique identifier

    def __post_init__(self):
        """Generate category and signature after initialization."""
        if not self.category:
            self.category = categorize_issue(self.message).value
        if not self.signature:
            self.signature = generate_issue_signature(
                self.file, self.line, self.category
            )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "severity": self.severity,
            "file": self.file,
            "message": self.message,
            "line": self.line,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationIssue":
        """Create from dictionary."""
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
    issues: List[ValidationIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    summary: str = ""
    reasoning: str = ""  # Chain-of-thought reasoning
    patterns_matched: bool = True  # Whether code matches codebase patterns

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
    def errors(self) -> List[ValidationIssue]:
        """Get only error-severity issues."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-severity issues."""
        return [i for i in self.issues if i.severity == "warning"]

    def get_issue_signatures(self) -> Set[str]:
        """Get all issue signatures for comparison."""
        return {i.signature for i in self.issues if i.signature}


# =============================================================================
# CONTRADICTION TRACKER
# =============================================================================

@dataclass
class ContradictionInfo:
    """Information about a detected contradiction."""
    file: str
    previous_message: str
    current_message: str
    category: str
    contradiction_type: str  # "flip_flop", "conflicting_advice", "severity_change"


class ContradictionTracker:
    """Tracks validation history and detects contradictions."""

    # Patterns that indicate contradictory advice
    CONTRADICTION_PATTERNS = [
        ("redundant", "missing"),
        ("remove", "add"),
        ("unnecessary", "required"),
        ("should not", "should"),
        ("too many", "not enough"),
        ("unused", "missing"),
        ("delete", "create"),
    ]

    def __init__(self):
        self.history: List[ValidationResult] = []
        self.issue_occurrences: Dict[str, List[Tuple[int, str]]] = {}  # signature -> [(iteration, severity)]

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result to history."""
        iteration = len(self.history)
        self.history.append(result)

        # Track issue occurrences
        for issue in result.issues:
            if issue.signature:
                if issue.signature not in self.issue_occurrences:
                    self.issue_occurrences[issue.signature] = []
                self.issue_occurrences[issue.signature].append(
                    (iteration, issue.severity)
                )

    def detect_contradictions(self, current: ValidationResult) -> List[ContradictionInfo]:
        """Detect contradictions between current and previous validations."""
        contradictions = []

        if not self.history:
            return contradictions

        previous = self.history[-1]

        # 1. Detect flip-flops (issue appears, disappears, reappears)
        current_signatures = current.get_issue_signatures()
        for sig, occurrences in self.issue_occurrences.items():
            if len(occurrences) >= 2:
                # Check if issue flip-flopped
                was_present = [i for i, _ in occurrences]
                if len(was_present) >= 2:
                    # Issue appeared multiple times with gaps
                    for issue in current.issues:
                        if issue.signature == sig:
                            contradictions.append(ContradictionInfo(
                                file=issue.file,
                                previous_message="Issue was previously fixed",
                                current_message=issue.message,
                                category=issue.category or "unknown",
                                contradiction_type="flip_flop",
                            ))

        # 2. Detect conflicting advice on same location
        for curr_issue in current.issues:
            curr_msg = curr_issue.message.lower()

            for prev_issue in previous.issues:
                # Must be same file
                if curr_issue.file != prev_issue.file:
                    continue

                # Must be nearby lines (within 10 lines)
                if curr_issue.line and prev_issue.line:
                    if abs(curr_issue.line - prev_issue.line) > 10:
                        continue

                prev_msg = prev_issue.message.lower()

                # Check for contradictory language
                for pattern_a, pattern_b in self.CONTRADICTION_PATTERNS:
                    if (pattern_a in curr_msg and pattern_b in prev_msg) or \
                            (pattern_b in curr_msg and pattern_a in prev_msg):
                        contradictions.append(ContradictionInfo(
                            file=curr_issue.file,
                            previous_message=prev_issue.message,
                            current_message=curr_issue.message,
                            category=curr_issue.category or "unknown",
                            contradiction_type="conflicting_advice",
                        ))

        # 3. Detect severity changes on same issue
        for curr_issue in current.issues:
            for prev_issue in previous.issues:
                if curr_issue.signature == prev_issue.signature:
                    if curr_issue.severity != prev_issue.severity:
                        contradictions.append(ContradictionInfo(
                            file=curr_issue.file,
                            previous_message=f"Severity was: {prev_issue.severity}",
                            current_message=f"Severity now: {curr_issue.severity}",
                            category=curr_issue.category or "unknown",
                            contradiction_type="severity_change",
                        ))

        return contradictions

    def clear(self) -> None:
        """Clear all history."""
        self.history = []
        self.issue_occurrences = {}


# =============================================================================
# ENHANCED QUICK CHECKS
# =============================================================================

class QuickValidator:
    """Fast syntax and structural validation without LLM calls."""

    @staticmethod
    def validate_php(content: str, file_path: str) -> List[str]:
        """Quick PHP validation checks."""
        issues = []

        if not content.strip():
            issues.append("File is empty")
            return issues

        # Must start with <?php
        if not content.strip().startswith("<?php"):
            issues.append("PHP file must start with <?php")

        # Check for namespace in app/ files
        if "app/" in file_path.lower() and "namespace " not in content:
            issues.append("Files in app/ directory should have a namespace declaration")

        # Check for class in class-type files
        class_file_patterns = ["Controller", "Model", "Service", "Repository", "Request", "Resource", "Job", "Event",
                               "Listener", "Policy", "Rule"]
        if any(p in file_path for p in class_file_patterns):
            if "class " not in content and "interface " not in content and "trait " not in content:
                issues.append(f"Expected class/interface/trait declaration in {file_path}")

        # Check balanced braces
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces != close_braces:
            issues.append(f"Unbalanced braces: {open_braces} opening, {close_braces} closing")

        # Check balanced parentheses
        open_parens = content.count("(")
        close_parens = content.count(")")
        if open_parens != close_parens:
            issues.append(f"Unbalanced parentheses: {open_parens} opening, {close_parens} closing")

        # Check for common syntax errors
        if re.search(r"function\s+\w+\s*\([^)]*\)\s*:\s*$", content, re.MULTILINE):
            issues.append("Incomplete return type declaration detected")

        # Check for unclosed strings (basic check)
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            # Count quotes (very basic)
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')
            if single_quotes % 2 != 0:
                issues.append(f"Line {i}: Possible unclosed single quote")
            if double_quotes % 2 != 0:
                issues.append(f"Line {i}: Possible unclosed double quote")

        return issues

    @staticmethod
    def validate_blade(content: str, file_path: str) -> List[str]:
        """Quick Blade template validation checks."""
        issues = []

        if not content.strip():
            issues.append("Blade template is empty")
            return issues

        # Check for balanced Blade directives
        directive_pairs = [
            ("@if", "@endif"),
            ("@foreach", "@endforeach"),
            ("@for", "@endfor"),
            ("@while", "@endwhile"),
            ("@switch", "@endswitch"),
            ("@section", "@endsection"),
            ("@push", "@endpush"),
            ("@once", "@endonce"),
            ("@php", "@endphp"),
        ]

        for start, end in directive_pairs:
            start_count = content.count(start)
            end_count = content.count(end)
            # Account for @section with @show or @yield
            if start == "@section":
                end_count += content.count("@show")
            if start_count > end_count:
                issues.append(f"Unclosed {start} directive ({start_count} opens, {end_count} closes)")

        # Check for unescaped output with user data patterns
        dangerous_patterns = [
            (r"\{!!\s*\$request", "Unescaped request data - use {{ }} instead of {!! !!}"),
            (r"\{!!\s*\$_", "Unescaped superglobal - security risk"),
            (r"\{!!\s*request\(", "Unescaped request() output - security risk"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, content):
                issues.append(message)

        return issues

    @staticmethod
    def validate_migration(content: str, file_path: str) -> List[str]:
        """Quick migration validation checks."""
        issues = []

        if "class " not in content:
            issues.append("Migration must contain a class definition")
            return issues

        # Check for up method
        if "function up(" not in content and "public function up()" not in content:
            issues.append("Migration must have an up() method")

        # Check for down method
        if "function down(" not in content and "public function down()" not in content:
            issues.append("Migration must have a down() method for rollback")

        # Check if down method is empty (common mistake)
        down_match = re.search(r"function down\(\)[^{]*\{([^}]*)\}", content, re.DOTALL)
        if down_match:
            down_body = down_match.group(1).strip()
            if not down_body or down_body == "//":
                issues.append("down() method is empty - migration won't be reversible")

        return issues

    @staticmethod
    def validate_route(content: str, file_path: str) -> List[str]:
        """Quick route file validation checks."""
        issues = []

        # Check for route definitions
        if "Route::" not in content:
            issues.append("Route file should contain Route:: definitions")

        # Check for controller references without imports
        controller_refs = re.findall(r"Route::\w+\([^,]+,\s*\[([^,\]]+)Controller", content)
        for controller in controller_refs:
            controller_name = controller.strip() + "Controller"
            if f"use " not in content or controller_name not in content.split("Route::")[0]:
                # This is a heuristic - full validation happens in LLM
                pass

        return issues

    @classmethod
    def quick_check(cls, result: ExecutionResult) -> List[str]:
        """Run all applicable quick checks on an execution result."""
        issues = []

        if not result.success:
            issues.append(f"Execution failed: {result.error}")
            return issues

        if result.action == "delete":
            return issues  # No content to validate

        if not result.content:
            issues.append("No content generated")
            return issues

        content = result.content
        file_path = result.file.lower()

        # Route file checks
        if "routes/" in file_path:
            issues.extend(cls.validate_route(content, result.file))
        # Migration checks
        elif "migrations/" in file_path:
            issues.extend(cls.validate_migration(content, result.file))
        # Blade checks
        elif file_path.endswith(".blade.php"):
            issues.extend(cls.validate_blade(content, result.file))
        # PHP checks
        elif file_path.endswith(".php"):
            issues.extend(cls.validate_php(content, result.file))

        return issues


# =============================================================================
# MAIN VALIDATOR CLASS
# =============================================================================

class Validator:
    """
    Guardian - Validates execution results for quality and correctness.

    Enhanced with:
    - Chain-of-thought reasoning
    - Context-aware validation
    - Grounded issue detection
    - Improved contradiction tracking
    """

    def __init__(
            self,
            claude_service: Optional[ClaudeService] = None,
            config: Optional[AgentConfig] = None,
    ):
        """Initialize the validator."""
        self.claude = claude_service or get_claude_service()
        self.config = config or agent_config
        self.contradiction_tracker = ContradictionTracker()
        self.quick_validator = QuickValidator()
        logger.info("[GUARDIAN] Initialized with enhanced validation")

    async def validate(
            self,
            user_input: str,
            intent: Intent,
            results: List[ExecutionResult],
            context: RetrievedContext,
    ) -> ValidationResult:
        """
        Validate execution results with chain-of-thought reasoning.

        Args:
            user_input: Original user request
            intent: Analyzed intent
            results: Execution results to validate
            context: Codebase context for reference

        Returns:
            ValidationResult with approval status and issues
        """
        logger.info(f"[GUARDIAN] Validating {len(results)} execution results")

        # Step 1: Run quick checks first
        quick_issues = []
        for result in results:
            file_issues = self.quick_validator.quick_check(result)
            for issue_msg in file_issues:
                quick_issues.append(ValidationIssue(
                    severity="error",
                    file=result.file,
                    message=issue_msg,
                    line=1,
                ))

        # If quick checks found critical issues, return early
        critical_quick_issues = [i for i in quick_issues if "Unbalanced" in i.message or "empty" in i.message.lower()]
        if critical_quick_issues:
            logger.warning(f"[GUARDIAN] Quick check found {len(critical_quick_issues)} critical issues")
            return ValidationResult(
                approved=False,
                score=20,
                issues=critical_quick_issues,
                summary="Quick validation found critical syntax issues that must be fixed before full review.",
            )

        # Step 2: Extract patterns from context
        patterns = extract_patterns_from_context(context)

        # Step 3: Format changes for review
        changes_str = self._format_changes(results)

        # Step 4: Build prompt with patterns
        user_prompt = safe_format(
            VALIDATION_USER_PROMPT,
            user_input=user_input,
            task_type=intent.task_type,
            scope=intent.scope,
            domains=", ".join(intent.domains_affected) or "general",
            patterns=patterns.to_prompt_string(),
            changes=changes_str,
            context=context.to_prompt_string()[:12000],  # Limit context
        )

        messages = [{"role": "user", "content": user_prompt}]

        try:
            response = await self.claude.chat_async(
                model=ClaudeModel.SONNET,
                messages=messages,
                system=VALIDATION_SYSTEM_PROMPT,
                temperature=0.2,  # Lower for more consistent validation
                max_tokens=4096,
                request_type="validation",
            )

            # Parse response - extract reasoning and JSON
            result = self._parse_response(response)

            # Add any non-critical quick check issues
            for qi in quick_issues:
                if qi not in result.issues:
                    result.issues.append(qi)

            # Check for contradictions
            if self.config.ENABLE_CONTRADICTION_DETECTION:
                contradictions = self.contradiction_tracker.detect_contradictions(result)
                if contradictions:
                    logger.warning(f"[GUARDIAN] Detected {len(contradictions)} contradictions")
                    result.suggestions = result.suggestions or []

                    # Add specific contradiction warnings
                    for c in contradictions[:3]:  # Limit to top 3
                        result.suggestions.append(
                            f"Potential inconsistency in {c.file}: "
                            f"Previous: '{c.previous_message[:50]}...' vs "
                            f"Current: '{c.current_message[:50]}...'"
                        )

            # Track this result
            self.contradiction_tracker.add_result(result)

            logger.info(f"[GUARDIAN] Validation complete: approved={result.approved}, score={result.score}")
            logger.info(f"[GUARDIAN] Issues: {len(result.errors)} errors, {len(result.warnings)} warnings")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"[GUARDIAN] Failed to parse validation response: {e}")
            return ValidationResult(
                approved=False,
                score=0,
                summary="Failed to parse validation response",
                issues=[ValidationIssue(
                    severity="error",
                    file="",
                    message=f"Validation process failed - could not parse response: {e}",
                    line=None,
                )],
            )

        except Exception as e:
            logger.error(f"[GUARDIAN] Validation failed: {e}")
            raise

    def _parse_response(self, response: str) -> ValidationResult:
        """Parse LLM response, extracting reasoning and JSON."""
        response_text = response.strip()
        reasoning = ""

        # Extract reasoning if present
        reasoning_match = re.search(
            r"<reasoning>(.*?)</reasoning>",
            response_text,
            re.DOTALL
        )
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
            # Remove reasoning from response for JSON parsing
            response_text = response_text.replace(reasoning_match.group(0), "").strip()

        # Extract JSON
        # Try to find JSON object
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            response_text = json_match.group(0)

        # Handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        validation_data = json.loads(response_text)
        result = ValidationResult.from_dict(validation_data)
        result.reasoning = reasoning

        return result

    def _format_changes(self, results: List[ExecutionResult]) -> str:
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
                # Number the lines for easy reference
                lines = result.content.split("\n")
                numbered = "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))
                parts.append(f"```php\n{numbered}\n```\n")

            if result.error:
                parts.append(f"\n**Error:** {result.error}\n")

        return "\n".join(parts)

    async def quick_check(self, result: ExecutionResult) -> List[str]:
        """Quick syntax and basic validation check."""
        return self.quick_validator.quick_check(result)

    async def validate_single(
            self,
            result: ExecutionResult,
            context: RetrievedContext,
    ) -> ValidationResult:
        """Validate a single execution result."""
        quick_issues = await self.quick_check(result)

        if quick_issues:
            return ValidationResult(
                approved=False,
                score=30,
                issues=[ValidationIssue(
                    severity="error",
                    file=result.file,
                    message=issue,
                    line=1,
                ) for issue in quick_issues],
                summary="Quick validation failed",
            )

        dummy_intent = Intent(task_type="feature", search_queries=[])
        return await self.validate(
            user_input=f"Validate changes to {result.file}",
            intent=dummy_intent,
            results=[result],
            context=context,
        )

    def clear_history(self) -> None:
        """Clear validation history (call at start of new request)."""
        self.contradiction_tracker.clear()

    # Legacy compatibility
    @property
    def validation_history(self) -> List[ValidationResult]:
        """Access validation history (legacy compatibility)."""
        return self.contradiction_tracker.history
