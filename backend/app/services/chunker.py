"""
Code chunker service.
Splits parsed code files into logical chunks for embedding.
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import tiktoken

logger = logging.getLogger(__name__)

# Default maximum tokens per chunk
DEFAULT_MAX_TOKENS = 500

# Overlap tokens between chunks for context continuity
OVERLAP_TOKENS = 50


@dataclass
class CodeChunk:
    """Represents a chunk of code for embedding."""
    id: str  # Unique identifier for the chunk
    file_path: str
    content: str
    chunk_type: str  # class, method, function, property, section, etc.
    name: Optional[str] = None  # Name of the class/method/function
    parent_name: Optional[str] = None  # Parent class name for methods
    line_start: int = 0
    line_end: int = 0
    token_count: int = 0
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        return result


class Chunker:
    """Service for chunking code into embeddable pieces."""

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS):
        """
        Initialize the chunker.

        Args:
            max_tokens: Maximum tokens per chunk
        """
        self.max_tokens = max_tokens
        # Use cl100k_base encoding (used by text-embedding-3-small)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback encoding
            self.encoding = tiktoken.get_encoding("gpt2")

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self.encoding.encode(text))

    def _generate_chunk_id(self, file_path: str, chunk_type: str,
                           name: Optional[str], index: int) -> str:
        """Generate a unique chunk ID."""
        base = f"{file_path}::{chunk_type}"
        if name:
            base += f"::{name}"
        base += f"::{index}"
        return base

    def _split_text_into_chunks(
        self,
        text: str,
        file_path: str,
        chunk_type: str,
        name: Optional[str] = None,
        parent_name: Optional[str] = None,
        line_start: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[CodeChunk]:
        """
        Split a large text into multiple chunks with overlap.

        Args:
            text: The text to split
            file_path: Path to the source file
            chunk_type: Type of chunk
            name: Name of the code element
            parent_name: Parent class name
            line_start: Starting line number
            metadata: Additional metadata

        Returns:
            List of CodeChunk objects
        """
        chunks = []
        tokens = self.encoding.encode(text)

        if len(tokens) <= self.max_tokens:
            # Text fits in a single chunk
            chunks.append(CodeChunk(
                id=self._generate_chunk_id(file_path, chunk_type, name, 0),
                file_path=file_path,
                content=text,
                chunk_type=chunk_type,
                name=name,
                parent_name=parent_name,
                line_start=line_start,
                line_end=line_start + text.count("\n"),
                token_count=len(tokens),
                metadata=metadata,
            ))
        else:
            # Split into multiple chunks with overlap
            start = 0
            chunk_index = 0

            while start < len(tokens):
                end = min(start + self.max_tokens, len(tokens))
                chunk_tokens = tokens[start:end]
                chunk_text = self.encoding.decode(chunk_tokens)

                # Calculate approximate line numbers
                lines_before = self.encoding.decode(tokens[:start]).count("\n")
                lines_in_chunk = chunk_text.count("\n")

                chunks.append(CodeChunk(
                    id=self._generate_chunk_id(file_path, chunk_type, name, chunk_index),
                    file_path=file_path,
                    content=chunk_text,
                    chunk_type=f"{chunk_type}_part",
                    name=f"{name}_part{chunk_index}" if name else None,
                    parent_name=parent_name,
                    line_start=line_start + lines_before,
                    line_end=line_start + lines_before + lines_in_chunk,
                    token_count=len(chunk_tokens),
                    metadata={
                        **(metadata or {}),
                        "part": chunk_index,
                        "total_parts": -1,  # Will be updated after
                    },
                ))

                # Move start with overlap
                start = end - OVERLAP_TOKENS if end < len(tokens) else end
                chunk_index += 1

            # Update total parts
            for chunk in chunks:
                if chunk.metadata and "part" in chunk.metadata:
                    chunk.metadata["total_parts"] = len(chunks)

        return chunks

    def chunk_php_file(
        self,
        file_path: str,
        parsed_data: Dict[str, Any],
        source_code: str,
    ) -> List[CodeChunk]:
        """
        Chunk a parsed PHP file.

        Args:
            file_path: Path to the PHP file
            parsed_data: Parsed PHP structure from PHPParser
            source_code: Original source code

        Returns:
            List of CodeChunk objects
        """
        logger.info(f"[CHUNKER] Chunking PHP file: {file_path}")
        chunks = []
        source_lines = source_code.split("\n")

        # Add namespace and imports as context chunk
        context_parts = []
        if parsed_data.get("namespace"):
            context_parts.append(f"namespace {parsed_data['namespace']};")

        for use_stmt in parsed_data.get("use_statements", []):
            alias = f" as {use_stmt['alias']}" if use_stmt.get("alias") else ""
            context_parts.append(f"use {use_stmt['name']}{alias};")

        if context_parts:
            context_text = "\n".join(context_parts)
            chunks.extend(self._split_text_into_chunks(
                text=context_text,
                file_path=file_path,
                chunk_type="imports",
                name="imports",
                metadata={
                    "namespace": parsed_data.get("namespace"),
                    "import_count": len(parsed_data.get("use_statements", [])),
                },
            ))

        # Process classes
        for cls in parsed_data.get("classes", []):
            class_name = cls["name"]

            # Create class signature chunk
            class_sig_parts = []
            if cls.get("docblock"):
                class_sig_parts.append(cls["docblock"])

            sig = ""
            if cls.get("is_abstract"):
                sig += "abstract "
            if cls.get("is_final"):
                sig += "final "
            sig += f"{cls['type']} {class_name}"
            if cls.get("extends"):
                sig += f" extends {cls['extends']}"
            if cls.get("implements"):
                sig += f" implements {', '.join(cls['implements'])}"

            class_sig_parts.append(sig)

            # Add class constants
            for const in cls.get("constants", []):
                class_sig_parts.append(f"    const {const['name']} = {const['value']};")

            # Add properties
            for prop in cls.get("properties", []):
                prop_line = f"    {prop['visibility']}"
                if prop.get("is_static"):
                    prop_line += " static"
                if prop.get("type_hint"):
                    prop_line += f" {prop['type_hint']}"
                prop_line += f" ${prop['name']}"
                if prop.get("default_value"):
                    prop_line += f" = {prop['default_value']}"
                prop_line += ";"
                class_sig_parts.append(prop_line)

            class_sig_text = "\n".join(class_sig_parts)
            chunks.extend(self._split_text_into_chunks(
                text=class_sig_text,
                file_path=file_path,
                chunk_type="class",
                name=class_name,
                line_start=cls.get("line_start", 0),
                metadata={
                    "class_type": cls["type"],
                    "extends": cls.get("extends"),
                    "implements": cls.get("implements", []),
                    "traits": cls.get("traits", []),
                    "property_count": len(cls.get("properties", [])),
                    "method_count": len(cls.get("methods", [])),
                },
            ))

            # Process methods
            for method in cls.get("methods", []):
                method_text_parts = []

                if method.get("docblock"):
                    method_text_parts.append(method["docblock"])

                # Build method signature
                method_sig = f"{method['visibility']}"
                if method.get("is_static"):
                    method_sig += " static"
                if method.get("is_abstract"):
                    method_sig += " abstract"
                if method.get("is_final"):
                    method_sig += " final"

                method_sig += f" function {method['name']}("

                # Add parameters
                params = []
                for param in method.get("parameters", []):
                    param_str = ""
                    if param.get("type_hint"):
                        param_str += f"{param['type_hint']} "
                    if param.get("is_reference"):
                        param_str += "&"
                    if param.get("is_variadic"):
                        param_str += "..."
                    param_str += f"${param['name']}"
                    if param.get("default_value"):
                        param_str += f" = {param['default_value']}"
                    params.append(param_str)

                method_sig += ", ".join(params) + ")"

                if method.get("return_type"):
                    method_sig += f": {method['return_type']}"

                method_text_parts.append(method_sig)

                # Add body if available
                if method.get("body"):
                    method_text_parts.append(method["body"])

                method_text = "\n".join(method_text_parts)
                chunks.extend(self._split_text_into_chunks(
                    text=method_text,
                    file_path=file_path,
                    chunk_type="method",
                    name=method["name"],
                    parent_name=class_name,
                    line_start=method.get("line_start", 0),
                    metadata={
                        "visibility": method["visibility"],
                        "is_static": method.get("is_static", False),
                        "return_type": method.get("return_type"),
                        "parameter_count": len(method.get("parameters", [])),
                    },
                ))

        # Process standalone functions
        for func in parsed_data.get("functions", []):
            func_text_parts = []

            if func.get("docblock"):
                func_text_parts.append(func["docblock"])

            func_sig = f"function {func['name']}("

            params = []
            for param in func.get("parameters", []):
                param_str = ""
                if param.get("type_hint"):
                    param_str += f"{param['type_hint']} "
                if param.get("is_reference"):
                    param_str += "&"
                if param.get("is_variadic"):
                    param_str += "..."
                param_str += f"${param['name']}"
                if param.get("default_value"):
                    param_str += f" = {param['default_value']}"
                params.append(param_str)

            func_sig += ", ".join(params) + ")"

            if func.get("return_type"):
                func_sig += f": {func['return_type']}"

            func_text_parts.append(func_sig)

            if func.get("body"):
                func_text_parts.append(func["body"])

            func_text = "\n".join(func_text_parts)
            chunks.extend(self._split_text_into_chunks(
                text=func_text,
                file_path=file_path,
                chunk_type="function",
                name=func["name"],
                line_start=func.get("line_start", 0),
                metadata={
                    "return_type": func.get("return_type"),
                    "parameter_count": len(func.get("parameters", [])),
                },
            ))

        # If no classes or functions, chunk the entire file
        if not chunks:
            chunks.extend(self._split_text_into_chunks(
                text=source_code,
                file_path=file_path,
                chunk_type="file",
                name=file_path.split("/")[-1],
                metadata={"file_type": "php"},
            ))

        logger.info(f"[CHUNKER] PHP file chunked: {len(chunks)} chunks created")
        return chunks

    def chunk_blade_file(
        self,
        file_path: str,
        parsed_data: Dict[str, Any],
        source_code: str,
    ) -> List[CodeChunk]:
        """
        Chunk a parsed Blade template file.

        Args:
            file_path: Path to the Blade file
            parsed_data: Parsed Blade structure from BladeParser
            source_code: Original source code

        Returns:
            List of CodeChunk objects
        """
        logger.info(f"[CHUNKER] Chunking Blade file: {file_path}")
        chunks = []

        # Create a summary chunk with template metadata
        summary_parts = [f"Blade Template: {file_path.split('/')[-1]}"]

        if parsed_data.get("extends"):
            summary_parts.append(f"@extends('{parsed_data['extends']}')")

        if parsed_data.get("yields"):
            summary_parts.append(f"Yields: {', '.join(parsed_data['yields'])}")

        if parsed_data.get("includes"):
            include_names = [inc["name"] for inc in parsed_data["includes"][:5]]
            summary_parts.append(f"Includes: {', '.join(include_names)}")

        if parsed_data.get("components"):
            comp_names = [c["name"] for c in parsed_data["components"][:5]]
            summary_parts.append(f"Components: {', '.join(comp_names)}")

        if parsed_data.get("livewire"):
            lw_names = [l["name"] for l in parsed_data["livewire"][:5]]
            summary_parts.append(f"Livewire: {', '.join(lw_names)}")

        if parsed_data.get("variables"):
            var_names = [v["name"] for v in parsed_data["variables"][:10]]
            summary_parts.append(f"Variables: {', '.join(set(var_names))}")

        summary_text = "\n".join(summary_parts)
        chunks.extend(self._split_text_into_chunks(
            text=summary_text,
            file_path=file_path,
            chunk_type="blade_summary",
            name="summary",
            metadata={
                "extends": parsed_data.get("extends"),
                "section_count": len(parsed_data.get("sections", [])),
                "include_count": len(parsed_data.get("includes", [])),
                "component_count": len(parsed_data.get("components", [])),
                "livewire_count": len(parsed_data.get("livewire", [])),
            },
        ))

        # Chunk each section
        for section in parsed_data.get("sections", []):
            if section.get("content"):
                section_text = f"@section('{section['name']}')\n{section['content']}\n@endsection"
                chunks.extend(self._split_text_into_chunks(
                    text=section_text,
                    file_path=file_path,
                    chunk_type="blade_section",
                    name=section["name"],
                    line_start=section.get("line_start", 0),
                    metadata={"section_name": section["name"]},
                ))

        # If the template is small enough or has no sections, chunk the whole file
        if not parsed_data.get("sections") or self.count_tokens(source_code) <= self.max_tokens:
            chunks.extend(self._split_text_into_chunks(
                text=source_code,
                file_path=file_path,
                chunk_type="blade_template",
                name=file_path.split("/")[-1].replace(".blade.php", ""),
                metadata={
                    "extends": parsed_data.get("extends"),
                    "is_full_template": True,
                },
            ))

        logger.info(f"[CHUNKER] Blade file chunked: {len(chunks)} chunks created")
        return chunks

    def chunk_generic_file(
        self,
        file_path: str,
        source_code: str,
        file_type: str = "generic",
    ) -> List[CodeChunk]:
        """
        Chunk a generic file (config, routes, etc.).

        Args:
            file_path: Path to the file
            source_code: File content
            file_type: Type of file

        Returns:
            List of CodeChunk objects
        """
        return self._split_text_into_chunks(
            text=source_code,
            file_path=file_path,
            chunk_type=file_type,
            name=file_path.split("/")[-1],
            metadata={"file_type": file_type},
        )


def chunk_file(
    file_path: str,
    parsed_data: Optional[Dict[str, Any]],
    source_code: str,
    file_type: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Chunk a file into embeddable pieces.

    Args:
        file_path: Path to the source file
        parsed_data: Parsed file data (from PHP or Blade parser)
        source_code: Original source code
        file_type: Type of file (php, blade, etc.)
        max_tokens: Maximum tokens per chunk

    Returns:
        List of chunk dictionaries
    """
    logger.info(f"[CHUNKER] chunk_file called for {file_path}, type={file_type}")
    chunker = Chunker(max_tokens=max_tokens)

    if file_type == "php" and parsed_data:
        chunks = chunker.chunk_php_file(file_path, parsed_data, source_code)
    elif file_type == "blade" and parsed_data:
        chunks = chunker.chunk_blade_file(file_path, parsed_data, source_code)
    else:
        chunks = chunker.chunk_generic_file(file_path, source_code, file_type)

    logger.info(f"[CHUNKER] chunk_file completed for {file_path}: {len(chunks)} chunks")
    return [chunk.to_dict() for chunk in chunks]
