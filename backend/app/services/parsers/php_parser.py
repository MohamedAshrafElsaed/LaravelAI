"""
PHP parser using tree-sitter.
Extracts classes, methods, properties, use statements, and namespaces.
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
import tree_sitter_php as tsphp
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

# Initialize tree-sitter PHP language
PHP_LANGUAGE = Language(tsphp.language_php())


@dataclass
class PHPProperty:
    """Represents a PHP class property."""
    name: str
    visibility: str  # public, protected, private
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_static: bool = False
    line_start: int = 0
    line_end: int = 0
    docblock: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PHPParameter:
    """Represents a method/function parameter."""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_variadic: bool = False
    is_reference: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PHPMethod:
    """Represents a PHP method or function."""
    name: str
    visibility: str  # public, protected, private
    parameters: List[PHPParameter] = field(default_factory=list)
    return_type: Optional[str] = None
    is_static: bool = False
    is_abstract: bool = False
    is_final: bool = False
    line_start: int = 0
    line_end: int = 0
    docblock: Optional[str] = None
    body: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["parameters"] = [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.parameters]
        return result


@dataclass
class PHPClass:
    """Represents a PHP class, interface, or trait."""
    name: str
    type: str  # class, interface, trait, enum
    extends: Optional[str] = None
    implements: List[str] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    methods: List[PHPMethod] = field(default_factory=list)
    properties: List[PHPProperty] = field(default_factory=list)
    constants: List[Dict[str, Any]] = field(default_factory=list)
    is_abstract: bool = False
    is_final: bool = False
    line_start: int = 0
    line_end: int = 0
    docblock: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["methods"] = [m.to_dict() if hasattr(m, 'to_dict') else m for m in self.methods]
        result["properties"] = [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.properties]
        return result


@dataclass
class PHPFunction:
    """Represents a standalone PHP function."""
    name: str
    parameters: List[PHPParameter] = field(default_factory=list)
    return_type: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    docblock: Optional[str] = None
    body: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["parameters"] = [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.parameters]
        return result


@dataclass
class PHPUseStatement:
    """Represents a use/import statement."""
    name: str
    alias: Optional[str] = None
    type: str = "class"  # class, function, const

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PHPParseResult:
    """Result of parsing a PHP file."""
    namespace: Optional[str] = None
    use_statements: List[PHPUseStatement] = field(default_factory=list)
    classes: List[PHPClass] = field(default_factory=list)
    functions: List[PHPFunction] = field(default_factory=list)
    constants: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "use_statements": [u.to_dict() for u in self.use_statements],
            "classes": [c.to_dict() for c in self.classes],
            "functions": [f.to_dict() for f in self.functions],
            "constants": self.constants,
            "errors": self.errors,
        }


class PHPParser:
    """Parser for PHP files using tree-sitter."""

    def __init__(self):
        """Initialize the PHP parser."""
        self.parser = Parser(PHP_LANGUAGE)

    def _get_node_text(self, node, source_code: bytes) -> str:
        """Extract text content from a tree-sitter node."""
        return source_code[node.start_byte:node.end_byte].decode("utf-8")

    def _find_docblock(self, node, source_code: bytes) -> Optional[str]:
        """Find the docblock comment preceding a node."""
        prev_sibling = node.prev_named_sibling

        while prev_sibling:
            if prev_sibling.type == "comment":
                text = self._get_node_text(prev_sibling, source_code)
                if text.startswith("/**"):
                    return text
            elif prev_sibling.type not in {"comment"}:
                break
            prev_sibling = prev_sibling.prev_named_sibling

        return None

    def _parse_visibility(self, modifiers: List[str]) -> str:
        """Determine visibility from modifiers."""
        if "private" in modifiers:
            return "private"
        if "protected" in modifiers:
            return "protected"
        return "public"

    def _get_modifiers(self, node, source_code: bytes) -> List[str]:
        """Extract modifiers from a declaration."""
        modifiers = []
        for child in node.children:
            if child.type in {"visibility_modifier", "static_modifier",
                             "abstract_modifier", "final_modifier", "readonly_modifier"}:
                modifiers.append(self._get_node_text(child, source_code).lower())
            elif child.type == "modifier":
                modifiers.append(self._get_node_text(child, source_code).lower())
        return modifiers

    def _parse_type(self, type_node, source_code: bytes) -> Optional[str]:
        """Parse a type declaration node."""
        if type_node is None:
            return None

        if type_node.type == "type_list":
            types = []
            for child in type_node.children:
                if child.type not in {"|", "&"}:
                    types.append(self._get_node_text(child, source_code))
            return "|".join(types)

        return self._get_node_text(type_node, source_code)

    def _parse_parameter(self, param_node, source_code: bytes) -> PHPParameter:
        """Parse a function/method parameter."""
        name = ""
        type_hint = None
        default_value = None
        is_variadic = False
        is_reference = False

        for child in param_node.children:
            if child.type == "variable_name":
                name = self._get_node_text(child, source_code).lstrip("$")
            elif child.type in {"type_list", "named_type", "primitive_type",
                               "optional_type", "union_type", "intersection_type"}:
                type_hint = self._parse_type(child, source_code)
            elif child.type == "property_promotion_parameter":
                # Handle constructor promotion
                for subchild in child.children:
                    if subchild.type == "variable_name":
                        name = self._get_node_text(subchild, source_code).lstrip("$")
                    elif subchild.type in {"type_list", "named_type", "primitive_type"}:
                        type_hint = self._parse_type(subchild, source_code)
            elif child.type == "variadic_parameter":
                is_variadic = True
            elif child.type == "reference_modifier":
                is_reference = True

        # Check for default value
        for child in param_node.children:
            if child.type == "=":
                # Next sibling is the default value
                idx = list(param_node.children).index(child)
                if idx + 1 < len(param_node.children):
                    default_value = self._get_node_text(
                        param_node.children[idx + 1], source_code
                    )

        return PHPParameter(
            name=name,
            type_hint=type_hint,
            default_value=default_value,
            is_variadic=is_variadic,
            is_reference=is_reference,
        )

    def _parse_method(self, method_node, source_code: bytes) -> PHPMethod:
        """Parse a class method declaration."""
        name = ""
        parameters = []
        return_type = None
        body = None
        modifiers = self._get_modifiers(method_node, source_code)

        for child in method_node.children:
            if child.type == "name":
                name = self._get_node_text(child, source_code)
            elif child.type == "formal_parameters":
                for param in child.children:
                    if param.type == "simple_parameter":
                        parameters.append(self._parse_parameter(param, source_code))
                    elif param.type == "property_promotion_parameter":
                        parameters.append(self._parse_parameter(param, source_code))
                    elif param.type == "variadic_parameter":
                        parameters.append(self._parse_parameter(param, source_code))
            elif child.type in {"type_list", "named_type", "primitive_type",
                               "optional_type", "union_type"}:
                return_type = self._parse_type(child, source_code)
            elif child.type == "compound_statement":
                body = self._get_node_text(child, source_code)

        docblock = self._find_docblock(method_node, source_code)

        return PHPMethod(
            name=name,
            visibility=self._parse_visibility(modifiers),
            parameters=parameters,
            return_type=return_type,
            is_static="static" in modifiers,
            is_abstract="abstract" in modifiers,
            is_final="final" in modifiers,
            line_start=method_node.start_point[0] + 1,
            line_end=method_node.end_point[0] + 1,
            docblock=docblock,
            body=body,
        )

    def _parse_property(self, prop_node, source_code: bytes) -> List[PHPProperty]:
        """Parse a property declaration (may contain multiple properties)."""
        properties = []
        modifiers = self._get_modifiers(prop_node, source_code)
        type_hint = None
        docblock = self._find_docblock(prop_node, source_code)

        # Find type hint
        for child in prop_node.children:
            if child.type in {"type_list", "named_type", "primitive_type",
                             "optional_type", "union_type"}:
                type_hint = self._parse_type(child, source_code)
                break

        # Find property names and values
        for child in prop_node.children:
            if child.type == "property_element":
                name = ""
                default_value = None

                for subchild in child.children:
                    if subchild.type == "variable_name":
                        name = self._get_node_text(subchild, source_code).lstrip("$")
                    elif subchild.type == "property_initializer":
                        for init_child in subchild.children:
                            if init_child.type != "=":
                                default_value = self._get_node_text(init_child, source_code)
                                break

                if name:
                    properties.append(PHPProperty(
                        name=name,
                        visibility=self._parse_visibility(modifiers),
                        type_hint=type_hint,
                        default_value=default_value,
                        is_static="static" in modifiers,
                        line_start=prop_node.start_point[0] + 1,
                        line_end=prop_node.end_point[0] + 1,
                        docblock=docblock,
                    ))

        return properties

    def _parse_class(self, class_node, source_code: bytes) -> PHPClass:
        """Parse a class, interface, trait, or enum declaration."""
        name = ""
        class_type = "class"
        extends = None
        implements = []
        traits = []
        methods = []
        properties = []
        constants = []
        modifiers = []

        # Determine class type from node type
        if class_node.type == "interface_declaration":
            class_type = "interface"
        elif class_node.type == "trait_declaration":
            class_type = "trait"
        elif class_node.type == "enum_declaration":
            class_type = "enum"

        for child in class_node.children:
            if child.type == "name":
                name = self._get_node_text(child, source_code)
            elif child.type in {"abstract_modifier", "final_modifier"}:
                modifiers.append(self._get_node_text(child, source_code).lower())
            elif child.type == "base_clause":
                # extends
                for subchild in child.children:
                    if subchild.type == "name" or subchild.type == "qualified_name":
                        extends = self._get_node_text(subchild, source_code)
            elif child.type == "class_interface_clause":
                # implements
                for subchild in child.children:
                    if subchild.type in {"name", "qualified_name"}:
                        implements.append(self._get_node_text(subchild, source_code))
            elif child.type == "declaration_list":
                # Class body - methods, properties, constants
                for member in child.children:
                    if member.type == "method_declaration":
                        methods.append(self._parse_method(member, source_code))
                    elif member.type == "property_declaration":
                        properties.extend(self._parse_property(member, source_code))
                    elif member.type == "use_declaration":
                        # Trait use
                        for trait_child in member.children:
                            if trait_child.type in {"name", "qualified_name"}:
                                traits.append(self._get_node_text(trait_child, source_code))
                    elif member.type == "const_declaration":
                        # Class constants
                        for const_child in member.children:
                            if const_child.type == "const_element":
                                const_name = ""
                                const_value = ""
                                for elem in const_child.children:
                                    if elem.type == "name":
                                        const_name = self._get_node_text(elem, source_code)
                                    elif elem.type != "=":
                                        const_value = self._get_node_text(elem, source_code)
                                if const_name:
                                    constants.append({
                                        "name": const_name,
                                        "value": const_value,
                                    })

        docblock = self._find_docblock(class_node, source_code)

        return PHPClass(
            name=name,
            type=class_type,
            extends=extends,
            implements=implements,
            traits=traits,
            methods=methods,
            properties=properties,
            constants=constants,
            is_abstract="abstract" in modifiers,
            is_final="final" in modifiers,
            line_start=class_node.start_point[0] + 1,
            line_end=class_node.end_point[0] + 1,
            docblock=docblock,
        )

    def _parse_function(self, func_node, source_code: bytes) -> PHPFunction:
        """Parse a standalone function declaration."""
        name = ""
        parameters = []
        return_type = None
        body = None

        for child in func_node.children:
            if child.type == "name":
                name = self._get_node_text(child, source_code)
            elif child.type == "formal_parameters":
                for param in child.children:
                    if param.type in {"simple_parameter", "variadic_parameter"}:
                        parameters.append(self._parse_parameter(param, source_code))
            elif child.type in {"type_list", "named_type", "primitive_type",
                               "optional_type", "union_type"}:
                return_type = self._parse_type(child, source_code)
            elif child.type == "compound_statement":
                body = self._get_node_text(child, source_code)

        docblock = self._find_docblock(func_node, source_code)

        return PHPFunction(
            name=name,
            parameters=parameters,
            return_type=return_type,
            line_start=func_node.start_point[0] + 1,
            line_end=func_node.end_point[0] + 1,
            docblock=docblock,
            body=body,
        )

    def _parse_use_statement(self, use_node, source_code: bytes) -> List[PHPUseStatement]:
        """Parse a use/import statement."""
        statements = []
        use_type = "class"

        for child in use_node.children:
            if child.type == "function":
                use_type = "function"
            elif child.type == "const":
                use_type = "const"
            elif child.type == "use_clause":
                name = ""
                alias = None

                for subchild in child.children:
                    if subchild.type in {"name", "qualified_name"}:
                        name = self._get_node_text(subchild, source_code)
                    elif subchild.type == "namespace_aliasing_clause":
                        for alias_child in subchild.children:
                            if alias_child.type == "name":
                                alias = self._get_node_text(alias_child, source_code)

                if name:
                    statements.append(PHPUseStatement(
                        name=name,
                        alias=alias,
                        type=use_type,
                    ))

        return statements

    def parse(self, source_code: str) -> PHPParseResult:
        """
        Parse PHP source code and extract structural information.

        Args:
            source_code: The PHP source code as a string

        Returns:
            PHPParseResult containing parsed information
        """
        logger.debug(f"[PHP_PARSER] Parsing PHP source code ({len(source_code)} bytes)")
        result = PHPParseResult()
        source_bytes = source_code.encode("utf-8")

        try:
            tree = self.parser.parse(source_bytes)
            root = tree.root_node

            # Check for parse errors
            if root.has_error:
                logger.warning(f"[PHP_PARSER] Source code contains syntax errors")
                result.errors.append("Source code contains syntax errors")

            # Walk the tree
            def walk(node):
                if node.type == "namespace_definition":
                    # Extract namespace
                    for child in node.children:
                        if child.type == "namespace_name":
                            result.namespace = self._get_node_text(child, source_bytes)
                    # Continue walking children for classes inside namespace
                    for child in node.children:
                        walk(child)

                elif node.type == "namespace_use_declaration":
                    result.use_statements.extend(
                        self._parse_use_statement(node, source_bytes)
                    )

                elif node.type in {"class_declaration", "interface_declaration",
                                  "trait_declaration", "enum_declaration"}:
                    result.classes.append(self._parse_class(node, source_bytes))

                elif node.type == "function_definition":
                    result.functions.append(self._parse_function(node, source_bytes))

                elif node.type == "const_declaration":
                    # Global constants
                    for child in node.children:
                        if child.type == "const_element":
                            const_name = ""
                            const_value = ""
                            for elem in child.children:
                                if elem.type == "name":
                                    const_name = self._get_node_text(elem, source_bytes)
                                elif elem.type != "=":
                                    const_value = self._get_node_text(elem, source_bytes)
                            if const_name:
                                result.constants.append({
                                    "name": const_name,
                                    "value": const_value,
                                })

                else:
                    # Recursively walk children
                    for child in node.children:
                        walk(child)

            walk(root)

            logger.debug(f"[PHP_PARSER] Parse completed: {len(result.classes)} classes, {len(result.functions)} functions, {len(result.use_statements)} use statements")

        except Exception as e:
            logger.error(f"[PHP_PARSER] Parse error: {str(e)}")
            result.errors.append(f"Parse error: {str(e)}")

        return result

    def parse_file(self, file_path: str) -> PHPParseResult:
        """
        Parse a PHP file and extract structural information.

        Args:
            file_path: Path to the PHP file

        Returns:
            PHPParseResult containing parsed information
        """
        logger.info(f"[PHP_PARSER] Parsing file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                source_code = f.read()
            result = self.parse(source_code)
            logger.info(f"[PHP_PARSER] File parsed successfully: {file_path}")
            return result
        except Exception as e:
            logger.error(f"[PHP_PARSER] Failed to read file {file_path}: {str(e)}")
            result = PHPParseResult()
            result.errors.append(f"Failed to read file: {str(e)}")
            return result


def parse_php_file(file_path: str) -> Dict[str, Any]:
    """
    Parse a PHP file and return structured information.

    Args:
        file_path: Path to the PHP file

    Returns:
        Dictionary containing parsed PHP structure
    """
    logger.info(f"[PHP_PARSER] parse_php_file called for {file_path}")
    parser = PHPParser()
    result = parser.parse_file(file_path)
    return result.to_dict()


def parse_php_content(source_code: str) -> Dict[str, Any]:
    """
    Parse PHP source code and return structured information.

    Args:
        source_code: PHP source code as string

    Returns:
        Dictionary containing parsed PHP structure
    """
    logger.debug(f"[PHP_PARSER] parse_php_content called ({len(source_code)} bytes)")
    parser = PHPParser()
    result = parser.parse(source_code)
    return result.to_dict()
