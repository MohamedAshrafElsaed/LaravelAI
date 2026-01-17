"""
Blade template parser using regex patterns.
Extracts directives, variables, components, and structure.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class BladeSection:
    """Represents a Blade section."""
    name: str
    content: Optional[str] = None
    line_start: int = 0
    line_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BladeInclude:
    """Represents a Blade include or component."""
    type: str  # include, component, livewire, slot
    name: str
    parameters: Optional[str] = None
    line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BladeControlBlock:
    """Represents a Blade control structure (if, foreach, etc.)."""
    type: str  # if, elseif, else, foreach, for, while, forelse, switch
    condition: Optional[str] = None
    line_start: int = 0
    line_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BladeVariable:
    """Represents a variable used in the template."""
    name: str
    escaped: bool = True  # {{ }} vs {!! !!}
    line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BladeParseResult:
    """Result of parsing a Blade template."""
    extends: Optional[str] = None
    sections: List[BladeSection] = field(default_factory=list)
    yields: List[str] = field(default_factory=list)
    stacks: List[str] = field(default_factory=list)
    pushes: List[Dict[str, str]] = field(default_factory=list)
    includes: List[BladeInclude] = field(default_factory=list)
    components: List[BladeInclude] = field(default_factory=list)
    livewire: List[BladeInclude] = field(default_factory=list)
    slots: List[str] = field(default_factory=list)
    variables: List[BladeVariable] = field(default_factory=list)
    control_blocks: List[BladeControlBlock] = field(default_factory=list)
    php_blocks: List[Dict[str, Any]] = field(default_factory=list)
    props: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extends": self.extends,
            "sections": [s.to_dict() for s in self.sections],
            "yields": self.yields,
            "stacks": self.stacks,
            "pushes": self.pushes,
            "includes": [i.to_dict() for i in self.includes],
            "components": [c.to_dict() for c in self.components],
            "livewire": [l.to_dict() for l in self.livewire],
            "slots": self.slots,
            "variables": [v.to_dict() for v in self.variables],
            "control_blocks": [c.to_dict() for c in self.control_blocks],
            "php_blocks": self.php_blocks,
            "props": self.props,
            "errors": self.errors,
        }


class BladeParser:
    """Parser for Laravel Blade templates."""

    # Regex patterns for Blade directives
    PATTERNS = {
        # Layout directives
        "extends": re.compile(r"@extends\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
        "section_inline": re.compile(
            r"@section\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^)]+)\)", re.MULTILINE
        ),
        "section_block": re.compile(
            r"@section\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE
        ),
        "endsection": re.compile(r"@endsection", re.MULTILINE),
        "yield": re.compile(
            r"@yield\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*([^)]+))?\)", re.MULTILINE
        ),
        "parent": re.compile(r"@parent", re.MULTILINE),

        # Stacks
        "stack": re.compile(r"@stack\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
        "push": re.compile(r"@push\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
        "endpush": re.compile(r"@endpush", re.MULTILINE),
        "prepend": re.compile(r"@prepend\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
        "endprepend": re.compile(r"@endprepend", re.MULTILINE),

        # Includes
        "include": re.compile(
            r"@include\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "include_if": re.compile(
            r"@includeIf\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "include_when": re.compile(
            r"@includeWhen\s*\([^,]+,\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "include_unless": re.compile(
            r"@includeUnless\s*\([^,]+,\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "include_first": re.compile(
            r"@includeFirst\s*\(\s*\[([^\]]+)\](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "each": re.compile(
            r"@each\s*\(\s*['\"]([^'\"]+)['\"]\s*,", re.MULTILINE
        ),

        # Components
        "component": re.compile(
            r"@component\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "endcomponent": re.compile(r"@endcomponent", re.MULTILINE),
        "slot": re.compile(
            r"@slot\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "endslot": re.compile(r"@endslot", re.MULTILINE),

        # Anonymous components (x-component syntax)
        "x_component": re.compile(
            r"<x-([a-zA-Z0-9\-_.]+)(?:\s+[^>]*)?>", re.MULTILINE
        ),
        "x_component_self_closing": re.compile(
            r"<x-([a-zA-Z0-9\-_.]+)(?:\s+[^>]*)?\s*/>", re.MULTILINE
        ),

        # Livewire
        "livewire": re.compile(
            r"@livewire\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*(\[[^\]]*\]|[^)]+))?\s*\)",
            re.MULTILINE
        ),
        "livewire_tag": re.compile(
            r"<livewire:([a-zA-Z0-9\-_.]+)(?:\s+[^>]*)?\s*/?>", re.MULTILINE
        ),

        # Control structures
        "if": re.compile(r"@if\s*\(([^)]+)\)", re.MULTILINE),
        "elseif": re.compile(r"@elseif\s*\(([^)]+)\)", re.MULTILINE),
        "else": re.compile(r"@else(?!\w)", re.MULTILINE),
        "endif": re.compile(r"@endif", re.MULTILINE),
        "unless": re.compile(r"@unless\s*\(([^)]+)\)", re.MULTILINE),
        "endunless": re.compile(r"@endunless", re.MULTILINE),

        # Loops
        "foreach": re.compile(r"@foreach\s*\(([^)]+)\)", re.MULTILINE),
        "endforeach": re.compile(r"@endforeach", re.MULTILINE),
        "forelse": re.compile(r"@forelse\s*\(([^)]+)\)", re.MULTILINE),
        "empty": re.compile(r"@empty(?!\w)", re.MULTILINE),
        "endforelse": re.compile(r"@endforelse", re.MULTILINE),
        "for": re.compile(r"@for\s*\(([^)]+)\)", re.MULTILINE),
        "endfor": re.compile(r"@endfor", re.MULTILINE),
        "while": re.compile(r"@while\s*\(([^)]+)\)", re.MULTILINE),
        "endwhile": re.compile(r"@endwhile", re.MULTILINE),

        # Switch
        "switch": re.compile(r"@switch\s*\(([^)]+)\)", re.MULTILINE),
        "case": re.compile(r"@case\s*\(([^)]+)\)", re.MULTILINE),
        "default": re.compile(r"@default(?!\w)", re.MULTILINE),
        "break": re.compile(r"@break(?:\s*\(([^)]+)\))?", re.MULTILINE),
        "endswitch": re.compile(r"@endswitch", re.MULTILINE),

        # Authentication
        "auth": re.compile(r"@auth(?:\s*\(\s*['\"]?([^'\")\s]+)['\"]?\s*\))?", re.MULTILINE),
        "endauth": re.compile(r"@endauth", re.MULTILINE),
        "guest": re.compile(r"@guest(?:\s*\(\s*['\"]?([^'\")\s]+)['\"]?\s*\))?", re.MULTILINE),
        "endguest": re.compile(r"@endguest", re.MULTILINE),

        # Environment
        "env": re.compile(r"@env\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
        "endenv": re.compile(r"@endenv", re.MULTILINE),
        "production": re.compile(r"@production", re.MULTILINE),
        "endproduction": re.compile(r"@endproduction", re.MULTILINE),

        # Other directives
        "isset": re.compile(r"@isset\s*\(([^)]+)\)", re.MULTILINE),
        "endisset": re.compile(r"@endisset", re.MULTILINE),
        "empty_check": re.compile(r"@empty\s*\(([^)]+)\)", re.MULTILINE),
        "endempty": re.compile(r"@endempty", re.MULTILINE),

        # Props and attributes (for components)
        "props": re.compile(r"@props\s*\(\s*\[([^\]]+)\]\s*\)", re.MULTILINE),
        "aware": re.compile(r"@aware\s*\(\s*\[([^\]]+)\]\s*\)", re.MULTILINE),

        # PHP blocks
        "php_block": re.compile(r"@php(.*?)@endphp", re.DOTALL),
        "php_inline": re.compile(r"@php\s*\(([^)]+)\)", re.MULTILINE),

        # Variables
        "escaped_var": re.compile(r"\{\{\s*([^}]+)\s*\}\}", re.MULTILINE),
        "unescaped_var": re.compile(r"\{!!\s*([^}]+)\s*!!\}", re.MULTILINE),
        "raw_php": re.compile(r"\<\?php(.+?)\?\>", re.DOTALL),

        # JSON
        "json": re.compile(r"@json\s*\(([^)]+)\)", re.MULTILINE),

        # CSRF and Method
        "csrf": re.compile(r"@csrf", re.MULTILINE),
        "method": re.compile(r"@method\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),

        # Error handling
        "error": re.compile(r"@error\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
        "enderror": re.compile(r"@enderror", re.MULTILINE),

        # Once
        "once": re.compile(r"@once", re.MULTILINE),
        "endonce": re.compile(r"@endonce", re.MULTILINE),

        # Class and style (Alpine.js integration)
        "class": re.compile(r"@class\s*\(\s*\[([^\]]+)\]\s*\)", re.MULTILINE),
        "style": re.compile(r"@style\s*\(\s*\[([^\]]+)\]\s*\)", re.MULTILINE),

        # Selected, checked, disabled
        "selected": re.compile(r"@selected\s*\(([^)]+)\)", re.MULTILINE),
        "checked": re.compile(r"@checked\s*\(([^)]+)\)", re.MULTILINE),
        "disabled": re.compile(r"@disabled\s*\(([^)]+)\)", re.MULTILINE),
        "readonly": re.compile(r"@readonly\s*\(([^)]+)\)", re.MULTILINE),
        "required": re.compile(r"@required\s*\(([^)]+)\)", re.MULTILINE),
    }

    def __init__(self):
        """Initialize the Blade parser."""
        pass

    def _get_line_number(self, content: str, pos: int) -> int:
        """Get line number for a position in the content."""
        return content[:pos].count("\n") + 1

    def _extract_variable_name(self, expr: str) -> Set[str]:
        """Extract variable names from an expression."""
        variables = set()
        # Match $variable patterns
        var_pattern = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")
        for match in var_pattern.finditer(expr):
            variables.add(match.group(1))
        return variables

    def parse(self, content: str) -> BladeParseResult:
        """
        Parse Blade template content.

        Args:
            content: The Blade template content as a string

        Returns:
            BladeParseResult containing parsed information
        """
        logger.debug(f"[BLADE_PARSER] Parsing Blade content ({len(content)} bytes)")
        result = BladeParseResult()

        try:
            # Parse @extends
            extends_match = self.PATTERNS["extends"].search(content)
            if extends_match:
                result.extends = extends_match.group(1)

            # Parse sections
            section_stack = []
            for match in self.PATTERNS["section_block"].finditer(content):
                section_name = match.group(1)
                line_start = self._get_line_number(content, match.start())
                section_stack.append({
                    "name": section_name,
                    "line_start": line_start,
                    "start_pos": match.end(),
                })

            # Find endsection positions
            endsection_positions = [
                m.start() for m in self.PATTERNS["endsection"].finditer(content)
            ]

            # Match sections with their end positions
            for i, section in enumerate(section_stack):
                if i < len(endsection_positions):
                    end_pos = endsection_positions[i]
                    section_content = content[section["start_pos"]:end_pos].strip()
                    result.sections.append(BladeSection(
                        name=section["name"],
                        content=section_content[:500] if len(section_content) > 500 else section_content,
                        line_start=section["line_start"],
                        line_end=self._get_line_number(content, end_pos),
                    ))

            # Inline sections
            for match in self.PATTERNS["section_inline"].finditer(content):
                result.sections.append(BladeSection(
                    name=match.group(1),
                    content=match.group(2).strip(),
                    line_start=self._get_line_number(content, match.start()),
                    line_end=self._get_line_number(content, match.end()),
                ))

            # Parse @yield
            for match in self.PATTERNS["yield"].finditer(content):
                result.yields.append(match.group(1))

            # Parse @stack
            for match in self.PATTERNS["stack"].finditer(content):
                result.stacks.append(match.group(1))

            # Parse @push
            for match in self.PATTERNS["push"].finditer(content):
                result.pushes.append({
                    "name": match.group(1),
                    "line": self._get_line_number(content, match.start()),
                })

            # Parse @include variants
            for pattern_name in ["include", "include_if", "include_when",
                                "include_unless", "each"]:
                for match in self.PATTERNS[pattern_name].finditer(content):
                    result.includes.append(BladeInclude(
                        type=pattern_name.replace("_", "-"),
                        name=match.group(1),
                        parameters=match.group(2) if len(match.groups()) > 1 else None,
                        line=self._get_line_number(content, match.start()),
                    ))

            # Parse @component
            for match in self.PATTERNS["component"].finditer(content):
                result.components.append(BladeInclude(
                    type="component",
                    name=match.group(1),
                    parameters=match.group(2) if len(match.groups()) > 1 else None,
                    line=self._get_line_number(content, match.start()),
                ))

            # Parse x-component syntax
            for pattern_name in ["x_component", "x_component_self_closing"]:
                for match in self.PATTERNS[pattern_name].finditer(content):
                    result.components.append(BladeInclude(
                        type="x-component",
                        name=match.group(1),
                        parameters=None,
                        line=self._get_line_number(content, match.start()),
                    ))

            # Parse @slot
            for match in self.PATTERNS["slot"].finditer(content):
                result.slots.append(match.group(1))

            # Parse @livewire
            for match in self.PATTERNS["livewire"].finditer(content):
                result.livewire.append(BladeInclude(
                    type="livewire-directive",
                    name=match.group(1),
                    parameters=match.group(2) if len(match.groups()) > 1 else None,
                    line=self._get_line_number(content, match.start()),
                ))

            # Parse <livewire:component> tags
            for match in self.PATTERNS["livewire_tag"].finditer(content):
                result.livewire.append(BladeInclude(
                    type="livewire-tag",
                    name=match.group(1),
                    parameters=None,
                    line=self._get_line_number(content, match.start()),
                ))

            # Parse control structures
            control_patterns = [
                ("if", "if"), ("elseif", "elseif"), ("foreach", "foreach"),
                ("forelse", "forelse"), ("for", "for"), ("while", "while"),
                ("switch", "switch"), ("unless", "unless"),
            ]

            for pattern_name, block_type in control_patterns:
                for match in self.PATTERNS[pattern_name].finditer(content):
                    result.control_blocks.append(BladeControlBlock(
                        type=block_type,
                        condition=match.group(1) if match.groups() else None,
                        line_start=self._get_line_number(content, match.start()),
                    ))

            # Parse variables - escaped {{ $var }}
            seen_vars = set()
            for match in self.PATTERNS["escaped_var"].finditer(content):
                expr = match.group(1).strip()
                var_names = self._extract_variable_name(expr)
                for var_name in var_names:
                    if var_name not in seen_vars:
                        seen_vars.add(var_name)
                        result.variables.append(BladeVariable(
                            name=var_name,
                            escaped=True,
                            line=self._get_line_number(content, match.start()),
                        ))

            # Parse variables - unescaped {!! $var !!}
            for match in self.PATTERNS["unescaped_var"].finditer(content):
                expr = match.group(1).strip()
                var_names = self._extract_variable_name(expr)
                for var_name in var_names:
                    if var_name not in seen_vars:
                        seen_vars.add(var_name)
                        result.variables.append(BladeVariable(
                            name=var_name,
                            escaped=False,
                            line=self._get_line_number(content, match.start()),
                        ))

            # Parse @php blocks
            for match in self.PATTERNS["php_block"].finditer(content):
                result.php_blocks.append({
                    "content": match.group(1).strip()[:500],
                    "line_start": self._get_line_number(content, match.start()),
                    "line_end": self._get_line_number(content, match.end()),
                })

            # Parse @props
            for match in self.PATTERNS["props"].finditer(content):
                props_content = match.group(1)
                # Extract prop names
                prop_pattern = re.compile(r"['\"]([^'\"]+)['\"]")
                for prop_match in prop_pattern.finditer(props_content):
                    result.props.append(prop_match.group(1))

        except Exception as e:
            logger.error(f"[BLADE_PARSER] Parse error: {str(e)}")
            result.errors.append(f"Parse error: {str(e)}")

        logger.debug(f"[BLADE_PARSER] Parse completed: {len(result.sections)} sections, {len(result.includes)} includes, {len(result.components)} components, {len(result.variables)} variables")
        return result

    def parse_file(self, file_path: str) -> BladeParseResult:
        """
        Parse a Blade template file.

        Args:
            file_path: Path to the Blade template file

        Returns:
            BladeParseResult containing parsed information
        """
        logger.info(f"[BLADE_PARSER] Parsing file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            result = self.parse(content)
            logger.info(f"[BLADE_PARSER] File parsed successfully: {file_path}")
            return result
        except Exception as e:
            logger.error(f"[BLADE_PARSER] Failed to read file {file_path}: {str(e)}")
            result = BladeParseResult()
            result.errors.append(f"Failed to read file: {str(e)}")
            return result


def parse_blade_file(file_path: str) -> Dict[str, Any]:
    """
    Parse a Blade template file and return structured information.

    Args:
        file_path: Path to the Blade template file

    Returns:
        Dictionary containing parsed Blade structure
    """
    logger.info(f"[BLADE_PARSER] parse_blade_file called for {file_path}")
    parser = BladeParser()
    result = parser.parse_file(file_path)
    return result.to_dict()


def parse_blade_content(content: str) -> Dict[str, Any]:
    """
    Parse Blade template content and return structured information.

    Args:
        content: Blade template content as string

    Returns:
        Dictionary containing parsed Blade structure
    """
    logger.debug(f"[BLADE_PARSER] parse_blade_content called ({len(content)} bytes)")
    parser = BladeParser()
    result = parser.parse(content)
    return result.to_dict()
