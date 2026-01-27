"""
Scout Schema - Strict Pydantic models for Context Retriever output.

Scout retrieves code context from the indexed codebase.
Output is strictly validated to ensure grounded, verifiable results.
"""
from enum import Enum
from typing import List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class ConfidenceLevel(str, Enum):
    """Confidence level of retrieved context."""
    HIGH = "high"  # 6+ relevant chunks, high scores
    MEDIUM = "medium"  # 3-5 relevant chunks
    LOW = "low"  # 1-2 chunks or low scores
    INSUFFICIENT = "insufficient"  # 0 chunks or no relevant results


class RetrievalStrategy(str, Enum):
    """Strategies used during retrieval."""
    DIRECT_ENTITY = "direct_entity"  # Exact file/class lookup
    INDEX_SEARCH = "index_search"  # Database IndexedFile search
    VECTOR_SEARCH = "vector_search"  # Qdrant semantic search
    KEYWORD_SEARCH = "keyword_search"  # Grep/keyword in files
    CONVENTION_EXPAND = "convention_expand"  # Laravel convention expansion
    FALLBACK = "fallback"  # Basic project files


class CodeChunk(BaseModel):
    """A retrieved code chunk with metadata."""

    model_config = ConfigDict(strict=True)

    file_path: str = Field(
        description="Relative path to the file (e.g., 'app/Http/Controllers/UserController.php')"
    )
    start_line: int = Field(
        ge=1,
        description="Starting line number (1-indexed)"
    )
    end_line: int = Field(
        ge=1,
        description="Ending line number (1-indexed)"
    )
    content: str = Field(
        description="Actual code content from the file"
    )
    chunk_type: str = Field(
        default="code",
        description="Type: class, method, function, config, route, migration, etc."
    )
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0-1.0) from search or manual assignment"
    )
    reason: str = Field(
        description="Short explanation of why this chunk is relevant to the request"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (class_name, method_name, laravel_type, etc.)"
    )

    @property
    def estimated_tokens(self) -> int:
        """Estimate token count (4 chars per token approximation)."""
        return len(self.content) // 4


class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval process."""

    model_config = ConfigDict(strict=True)

    queries_used: List[str] = Field(
        default_factory=list,
        description="Search queries that were executed"
    )
    strategies_used: List[RetrievalStrategy] = Field(
        default_factory=list,
        description="Retrieval strategies that were applied"
    )
    files_scanned_count: int = Field(
        default=0,
        ge=0,
        description="Number of files examined during retrieval"
    )
    token_estimate: int = Field(
        default=0,
        ge=0,
        description="Estimated total tokens in retrieved context"
    )
    vector_search_count: int = Field(
        default=0,
        ge=0,
        description="Number of vector search queries executed"
    )
    index_hits: int = Field(
        default=0,
        ge=0,
        description="Number of direct index/database hits"
    )
    retrieval_time_ms: int = Field(
        default=0,
        ge=0,
        description="Total retrieval time in milliseconds"
    )


class RetrievedContext(BaseModel):
    """
    Complete context retrieved by Scout.

    All fields must be grounded in actual search results.
    No assumptions or hallucinations allowed.
    """

    model_config = ConfigDict(strict=True)

    chunks: List[CodeChunk] = Field(
        default_factory=list,
        description="Retrieved code chunks, ordered by relevance"
    )
    related_files: List[str] = Field(
        default_factory=list,
        description="File paths discovered via search (not assumed)"
    )
    domain_summaries: Dict[str, str] = Field(
        default_factory=dict,
        description="Domain summaries derived ONLY from retrieved code"
    )
    confidence_level: ConfidenceLevel = Field(
        default=ConfidenceLevel.INSUFFICIENT,
        description="Overall confidence in retrieved context"
    )
    retrieval_metadata: RetrievalMetadata = Field(
        default_factory=RetrievalMetadata,
        description="Metadata about the retrieval process"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings about retrieval quality"
    )

    @property
    def is_sufficient(self) -> bool:
        """Check if context is sufficient to proceed."""
        return self.confidence_level != ConfidenceLevel.INSUFFICIENT

    @property
    def total_tokens(self) -> int:
        """Calculate total estimated tokens."""
        return sum(chunk.estimated_tokens for chunk in self.chunks)

    def to_prompt_string(self) -> str:
        """Convert context to a string for downstream prompts."""
        parts = []

        # Confidence warning
        if self.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT):
            parts.append(f"⚠️ WARNING: Limited context (confidence: {self.confidence_level.value})")
            parts.append("Generated code may need manual verification.\n")

        # Warnings
        if self.warnings:
            parts.append("## Retrieval Warnings")
            for warning in self.warnings:
                parts.append(f"- {warning}")
            parts.append("")

        # Domain summaries (only if derived from code)
        if self.domain_summaries:
            parts.append("## Domain Context")
            for domain, summary in self.domain_summaries.items():
                parts.append(f"### {domain}\n{summary}")

        # Code chunks grouped by file
        if self.chunks:
            parts.append("\n## Retrieved Code")
            current_file = None
            for chunk in self.chunks:
                if chunk.file_path != current_file:
                    current_file = chunk.file_path
                    parts.append(f"\n### {chunk.file_path}")
                    parts.append(f"Relevance: {chunk.relevance_score:.2f} | Reason: {chunk.reason}")

                # Detect language for syntax highlighting
                lang = "php"
                if chunk.file_path.endswith(".blade.php"):
                    lang = "blade"
                elif chunk.file_path.endswith((".js", ".ts", ".vue")):
                    lang = "javascript"
                elif chunk.file_path.endswith(".json"):
                    lang = "json"

                parts.append(f"```{lang}\n// Lines {chunk.start_line}-{chunk.end_line} ({chunk.chunk_type})")
                parts.append(chunk.content)
                parts.append("```")
        else:
            parts.append("\n## ⚠️ No Relevant Code Found")
            parts.append("No matching code chunks were found.")
            if self.retrieval_metadata.queries_used:
                parts.append(f"Queries tried: {', '.join(self.retrieval_metadata.queries_used)}")

        return "\n".join(parts)


# Schema for validation
def get_retrieved_context_schema() -> dict:
    """Get JSON schema for RetrievedContext."""
    return RetrievedContext.model_json_schema()
