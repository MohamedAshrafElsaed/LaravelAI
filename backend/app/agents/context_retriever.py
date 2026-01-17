"""
Context Retriever Agent.

Retrieves relevant code context from the vector database based on intent.
Expands related files and manages token budget.
"""
import logging
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.intent_analyzer import Intent
from app.services.vector_store import VectorStore
from app.services.embeddings import EmbeddingService, EmbeddingProvider
from app.models.models import Project, IndexedFile
from app.core.config import settings

logger = logging.getLogger(__name__)

# Token budget for context (leaving room for system prompt and response)
DEFAULT_TOKEN_BUDGET = 50000
CHARS_PER_TOKEN = 4  # Rough estimate


@dataclass
class CodeChunk:
    """A chunk of code with metadata."""

    file_path: str
    content: str
    chunk_type: str  # class, function, method, etc.
    start_line: int
    end_line: int
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def estimated_tokens(self) -> int:
        """Estimate token count for this chunk."""
        return len(self.content) // CHARS_PER_TOKEN


@dataclass
class RetrievedContext:
    """Context retrieved for a request."""

    chunks: list[CodeChunk] = field(default_factory=list)
    domain_summaries: dict[str, str] = field(default_factory=dict)
    related_files: list[str] = field(default_factory=list)
    total_tokens: int = 0

    def to_prompt_string(self) -> str:
        """Convert context to a string for the LLM prompt."""
        parts = []

        # Add domain summaries
        if self.domain_summaries:
            parts.append("## Domain Summaries\n")
            for domain, summary in self.domain_summaries.items():
                parts.append(f"### {domain}\n{summary}\n")

        # Add code chunks grouped by file
        if self.chunks:
            parts.append("\n## Relevant Code\n")
            current_file = None
            for chunk in self.chunks:
                if chunk.file_path != current_file:
                    current_file = chunk.file_path
                    parts.append(f"\n### File: {chunk.file_path}\n")
                parts.append(f"```php\n// Lines {chunk.start_line}-{chunk.end_line} ({chunk.chunk_type})\n{chunk.content}\n```\n")

        return "\n".join(parts)


# Laravel file relationship mappings
LARAVEL_RELATIONSHIPS = {
    "Controller": {
        "patterns": ["app/Http/Controllers/{name}.php"],
        "related": [
            "resources/views/{name_snake}/**/*.blade.php",
            "app/Http/Requests/{name}Request.php",
            "app/Models/{model}.php",
            "routes/web.php",
            "routes/api.php",
        ],
    },
    "Model": {
        "patterns": ["app/Models/{name}.php"],
        "related": [
            "database/migrations/*_create_{name_snake_plural}_table.php",
            "app/Http/Controllers/{name}Controller.php",
            "app/Policies/{name}Policy.php",
        ],
    },
    "Migration": {
        "patterns": ["database/migrations/*.php"],
        "related": [
            "app/Models/{model}.php",
        ],
    },
}


class ContextRetriever:
    """
    Retrieves relevant context from the codebase.

    Uses vector search to find relevant code chunks, then expands
    to include related files based on Laravel conventions.
    """

    def __init__(
        self,
        db: AsyncSession,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """
        Initialize the context retriever.

        Args:
            db: Database session
            vector_store: Optional vector store instance
            embedding_service: Optional embedding service
        """
        self.db = db
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        logger.info("[CONTEXT_RETRIEVER] Initialized")

    async def _ensure_services(self, project_id: str) -> None:
        """Ensure vector store and embedding services are initialized."""
        if self.vector_store is None:
            self.vector_store = VectorStore()

        if self.embedding_service is None:
            provider = (
                EmbeddingProvider.VOYAGE
                if settings.embedding_provider == "voyage"
                else EmbeddingProvider.OPENAI
            )
            self.embedding_service = EmbeddingService(provider=provider)

    async def retrieve(
        self,
        project_id: str,
        intent: Intent,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ) -> RetrievedContext:
        """
        Retrieve relevant context based on intent.

        Args:
            project_id: The project UUID
            intent: Analyzed user intent
            token_budget: Maximum tokens for context

        Returns:
            RetrievedContext with relevant code chunks
        """
        logger.info(f"[CONTEXT_RETRIEVER] Retrieving context for project={project_id}")
        logger.info(f"[CONTEXT_RETRIEVER] Search queries: {intent.search_queries}")

        await self._ensure_services(project_id)

        context = RetrievedContext()
        used_tokens = 0
        seen_files = set()

        # 1. Search vector DB with each query
        if not intent.search_queries:
            logger.warning("[CONTEXT_RETRIEVER] No search queries provided in intent")

        for query in intent.search_queries:
            if used_tokens >= token_budget:
                break

            try:
                logger.info(f"[CONTEXT_RETRIEVER] Generating embedding for query: '{query}'")
                # Generate embedding for query
                query_embedding = await self.embedding_service.embed_text(query)

                if not query_embedding:
                    logger.error(f"[CONTEXT_RETRIEVER] Failed to generate embedding for query '{query}'")
                    continue

                logger.info(f"[CONTEXT_RETRIEVER] Searching vector store with embedding ({len(query_embedding)} dims)")

                # Search vector store with lower threshold first
                # Note: VectorStore.search is synchronous, uses query_embedding parameter
                results = self.vector_store.search(
                    project_id=project_id,
                    query_embedding=query_embedding,  # Correct parameter name
                    limit=10,
                    score_threshold=0.3,  # Lower threshold to get more results
                )

                logger.info(f"[CONTEXT_RETRIEVER] Query '{query}' returned {len(results)} results")

                # If no results, try with even lower threshold
                if not results:
                    logger.info(f"[CONTEXT_RETRIEVER] Retrying with lower threshold (0.1)")
                    results = self.vector_store.search(
                        project_id=project_id,
                        query_embedding=query_embedding,
                        limit=10,
                        score_threshold=0.1,
                    )
                    logger.info(f"[CONTEXT_RETRIEVER] Retry returned {len(results)} results")

                for result in results:
                    # Handle SearchResult objects (convert to dict if needed)
                    if hasattr(result, 'to_dict'):
                        result_data = result.to_dict()
                    elif isinstance(result, dict):
                        result_data = result
                    else:
                        logger.warning(f"[CONTEXT_RETRIEVER] Skipping unknown result type: {type(result)}")
                        continue

                    # Extract metadata - handle nested structure
                    metadata = result_data.get("metadata", {})
                    if not isinstance(metadata, dict):
                        metadata = {}

                    chunk = CodeChunk(
                        file_path=result_data.get("file_path", "unknown"),
                        content=result_data.get("content", ""),
                        chunk_type=result_data.get("chunk_type", "code"),
                        start_line=metadata.get("line_start", 0),
                        end_line=metadata.get("line_end", 0),
                        score=result_data.get("score", 0.0),
                        metadata=metadata,
                    )

                    # Check token budget
                    if used_tokens + chunk.estimated_tokens > token_budget:
                        logger.info(f"[CONTEXT_RETRIEVER] Token budget reached ({used_tokens}/{token_budget})")
                        break

                    context.chunks.append(chunk)
                    seen_files.add(chunk.file_path)
                    used_tokens += chunk.estimated_tokens

            except Exception as e:
                logger.error(f"[CONTEXT_RETRIEVER] Search error for query '{query}': {e}")
                continue

        # 2. Expand related files based on Laravel conventions
        related = await self._expand_related_files(project_id, list(seen_files))
        remaining_budget = token_budget - used_tokens

        for file_path in related:
            if file_path in seen_files:
                continue
            if remaining_budget <= 0:
                break

            try:
                # Fetch file content from database
                file_content = await self._get_file_content(project_id, file_path)
                if file_content:
                    estimated = len(file_content) // CHARS_PER_TOKEN
                    if estimated <= remaining_budget:
                        context.related_files.append(file_path)
                        context.chunks.append(CodeChunk(
                            file_path=file_path,
                            content=file_content,
                            chunk_type="related_file",
                            start_line=1,
                            end_line=file_content.count("\n") + 1,
                            score=0.5,  # Lower score for related files
                        ))
                        remaining_budget -= estimated
                        seen_files.add(file_path)
            except Exception as e:
                logger.debug(f"[CONTEXT_RETRIEVER] Could not fetch related file {file_path}: {e}")

        # 3. Add domain summaries
        context.domain_summaries = await self._get_domain_summaries(
            project_id, intent.domains_affected
        )

        context.total_tokens = used_tokens
        logger.info(f"[CONTEXT_RETRIEVER] Retrieved {len(context.chunks)} chunks, {context.total_tokens} estimated tokens")

        # Fallback: If no chunks found, try to get basic project structure
        if not context.chunks:
            logger.warning("[CONTEXT_RETRIEVER] No chunks retrieved, attempting fallback")
            await self._add_fallback_context(project_id, context, token_budget)

        return context

    async def _add_fallback_context(
        self,
        project_id: str,
        context: RetrievedContext,
        token_budget: int,
    ) -> None:
        """Add fallback context when vector search returns nothing."""
        # Try to get some basic files from the database
        fallback_files = [
            "routes/web.php",
            "routes/api.php",
            "app/Models/User.php",
            "app/Http/Controllers/Controller.php",
            "config/app.php",
        ]

        used_tokens = 0
        for file_path in fallback_files:
            if used_tokens >= token_budget // 4:  # Use max 25% of budget for fallback
                break

            try:
                content = await self._get_file_content(project_id, file_path)
                if content:
                    estimated = len(content) // CHARS_PER_TOKEN
                    if used_tokens + estimated <= token_budget // 4:
                        context.chunks.append(CodeChunk(
                            file_path=file_path,
                            content=content[:5000],  # Truncate long files
                            chunk_type="fallback",
                            start_line=1,
                            end_line=content.count("\n") + 1,
                            score=0.3,
                        ))
                        used_tokens += estimated
                        logger.info(f"[CONTEXT_RETRIEVER] Added fallback file: {file_path}")
            except Exception as e:
                logger.debug(f"[CONTEXT_RETRIEVER] Fallback file not found: {file_path}")

    async def _expand_related_files(
        self,
        project_id: str,
        file_paths: list[str],
    ) -> list[str]:
        """
        Find related files based on Laravel conventions.

        Args:
            project_id: The project UUID
            file_paths: List of file paths to expand from

        Returns:
            List of related file paths
        """
        related = []

        for path in file_paths:
            # Check if it's a controller
            if "Controller" in path and "Controllers/" in path:
                # Extract controller name
                name = path.split("/")[-1].replace("Controller.php", "")
                name_snake = self._to_snake_case(name)

                # Add potential related files
                related.extend([
                    f"resources/views/{name_snake}/index.blade.php",
                    f"resources/views/{name_snake}/show.blade.php",
                    f"resources/views/{name_snake}/create.blade.php",
                    f"resources/views/{name_snake}/edit.blade.php",
                    f"app/Models/{name}.php",
                    f"app/Http/Requests/{name}Request.php",
                ])

            # Check if it's a model
            elif "Models/" in path:
                name = path.split("/")[-1].replace(".php", "")
                name_snake = self._to_snake_case(name)
                related.extend([
                    f"app/Http/Controllers/{name}Controller.php",
                    f"app/Policies/{name}Policy.php",
                ])

        return related

    async def _get_file_content(
        self,
        project_id: str,
        file_path: str,
    ) -> Optional[str]:
        """Get file content from the database."""
        try:
            stmt = select(IndexedFile).where(
                IndexedFile.project_id == project_id,
                IndexedFile.file_path == file_path,
            )
            result = await self.db.execute(stmt)
            indexed_file = result.scalar_one_or_none()

            if indexed_file and indexed_file.content:
                return indexed_file.content
        except Exception as e:
            logger.debug(f"[CONTEXT_RETRIEVER] Error fetching file content: {e}")

        return None

    async def _get_domain_summaries(
        self,
        project_id: str,
        domains: list[str],
    ) -> dict[str, str]:
        """
        Get summaries for affected domains.

        This could be enhanced to use pre-computed summaries or
        generate them dynamically.
        """
        summaries = {}

        domain_descriptions = {
            "auth": "Authentication and authorization - Users, roles, permissions, guards, policies",
            "payment": "Payment processing - Gateways, transactions, subscriptions, invoices",
            "api": "API endpoints - REST resources, API routes, API authentication",
            "database": "Database layer - Models, migrations, seeders, factories",
            "queue": "Background jobs - Queues, workers, failed jobs, job batching",
            "mail": "Email - Mailables, notifications, email templates",
            "storage": "File storage - Disks, uploads, file management",
            "cache": "Caching - Cache drivers, cache tags, rate limiting",
            "routing": "Routing - Web routes, API routes, route groups, middleware",
            "middleware": "HTTP middleware - Request/response processing, guards",
            "validation": "Validation - Form requests, validation rules, custom validators",
            "events": "Events - Event classes, listeners, subscribers, broadcasting",
        }

        for domain in domains:
            if domain in domain_descriptions:
                summaries[domain] = domain_descriptions[domain]

        return summaries

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert PascalCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
