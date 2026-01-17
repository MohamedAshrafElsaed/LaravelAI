"""
Vector store service using Qdrant.
Handles storage and retrieval of code embeddings.
"""
import uuid
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException

from app.core.config import settings
from app.services.embeddings import get_embedding_dimension

logger = logging.getLogger(__name__)


# Default embedding dimension (text-embedding-3-small)
DEFAULT_DIMENSION = 1536

# Collection name prefix
COLLECTION_PREFIX = "laravel_project_"


class VectorStoreError(Exception):
    """Custom exception for vector store errors."""
    pass


@dataclass
class SearchResult:
    """Result of a vector search."""
    chunk_id: str
    file_path: str
    content: str
    chunk_type: str
    score: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "content": self.content,
            "chunk_type": self.chunk_type,
            "score": self.score,
            "metadata": self.metadata,
        }


class VectorStore:
    """Qdrant vector store for code embeddings."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the vector store.

        Args:
            url: Qdrant URL (defaults to config)
            api_key: Qdrant API key (defaults to config)
        """
        logger.info(f"[VECTOR_STORE] Initializing VectorStore")
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key

        if not self.url:
            logger.error(f"[VECTOR_STORE] No Qdrant URL configured")
            raise VectorStoreError(
                "No Qdrant URL configured. Set QDRANT_URL in your environment."
            )

        logger.info(f"[VECTOR_STORE] Connecting to Qdrant at {self.url}")
        # Initialize client
        try:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key if self.api_key else None,
                timeout=60.0,
            )
            logger.info(f"[VECTOR_STORE] Connected to Qdrant successfully")
        except Exception as e:
            logger.error(f"[VECTOR_STORE] Failed to connect to Qdrant: {str(e)}")
            raise VectorStoreError(f"Failed to connect to Qdrant: {str(e)}")

    def _get_collection_name(self, project_id: str) -> str:
        """Get the collection name for a project."""
        # Qdrant collection names must be alphanumeric with underscores
        safe_id = project_id.replace("-", "_")
        return f"{COLLECTION_PREFIX}{safe_id}"

    def collection_exists(self, project_id: str) -> bool:
        """Check if a collection exists for a project."""
        try:
            collection_name = self._get_collection_name(project_id)
            collections = self.client.get_collections()
            return any(c.name == collection_name for c in collections.collections)
        except Exception:
            return False

    def create_collection(
        self,
        project_id: str,
        dimension: int = DEFAULT_DIMENSION,
        recreate: bool = False,
    ) -> bool:
        """
        Create a Qdrant collection for a project.

        Args:
            project_id: The project's UUID
            dimension: Embedding dimension
            recreate: If True, delete existing collection first

        Returns:
            True if collection was created/exists
        """
        collection_name = self._get_collection_name(project_id)
        logger.info(f"[VECTOR_STORE] Creating collection {collection_name}, dimension={dimension}, recreate={recreate}")

        try:
            # Check if collection exists
            if self.collection_exists(project_id):
                if recreate:
                    logger.info(f"[VECTOR_STORE] Collection exists, recreating")
                    self.delete_collection(project_id)
                else:
                    logger.info(f"[VECTOR_STORE] Collection already exists")
                    return True

            # Create collection with optimized settings for code search
            logger.info(f"[VECTOR_STORE] Creating new collection {collection_name}")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                    on_disk=True,  # Store vectors on disk for larger collections
                ),
                # Optimize for filtered searches
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    on_disk=True,
                ),
                # Payload indexes for filtering
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=10000,
                ),
            )

            # Create payload indexes for common filters
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="file_path",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="chunk_type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="laravel_type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

            logger.info(f"[VECTOR_STORE] Collection {collection_name} created successfully")
            return True

        except Exception as e:
            logger.error(f"[VECTOR_STORE] Failed to create collection: {str(e)}")
            raise VectorStoreError(f"Failed to create collection: {str(e)}")

    def delete_collection(self, project_id: str) -> bool:
        """
        Delete a project's collection.

        Args:
            project_id: The project's UUID

        Returns:
            True if deleted, False if didn't exist
        """
        collection_name = self._get_collection_name(project_id)

        try:
            if not self.collection_exists(project_id):
                return False

            self.client.delete_collection(collection_name=collection_name)
            return True

        except Exception as e:
            raise VectorStoreError(f"Failed to delete collection: {str(e)}")

    def store_chunks(
        self,
        project_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        laravel_type: str = "unknown",
    ) -> int:
        """
        Store chunks with their embeddings in Qdrant.

        Args:
            project_id: The project's UUID
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors
            laravel_type: Laravel type for the file

        Returns:
            Number of points stored
        """
        logger.info(f"[VECTOR_STORE] store_chunks called: {len(chunks)} chunks, laravel_type={laravel_type}")

        if not chunks or not embeddings:
            logger.warning(f"[VECTOR_STORE] No chunks or embeddings to store")
            return 0

        if len(chunks) != len(embeddings):
            logger.error(f"[VECTOR_STORE] Chunks/embeddings count mismatch: {len(chunks)} vs {len(embeddings)}")
            raise VectorStoreError(
                f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) count mismatch"
            )

        collection_name = self._get_collection_name(project_id)

        # Ensure collection exists
        if not self.collection_exists(project_id):
            dimension = len(embeddings[0])
            logger.info(f"[VECTOR_STORE] Collection doesn't exist, creating with dimension={dimension}")
            self.create_collection(project_id, dimension=dimension)

        try:
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                # Generate point ID
                point_id = str(uuid.uuid4())

                # Prepare payload
                payload = {
                    "chunk_id": chunk.get("id", point_id),
                    "file_path": chunk.get("file_path", ""),
                    "content": chunk.get("content", ""),
                    "chunk_type": chunk.get("chunk_type", "unknown"),
                    "name": chunk.get("name"),
                    "parent_name": chunk.get("parent_name"),
                    "line_start": chunk.get("line_start", 0),
                    "line_end": chunk.get("line_end", 0),
                    "token_count": chunk.get("token_count", 0),
                    "laravel_type": laravel_type,
                }

                # Add any additional metadata
                if chunk.get("metadata"):
                    payload["metadata"] = chunk["metadata"]

                points.append(models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                ))

            # Upsert in batches
            batch_size = 100
            total_batches = (len(points) + batch_size - 1) // batch_size
            logger.info(f"[VECTOR_STORE] Upserting {len(points)} points in {total_batches} batches")

            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                batch_num = i // batch_size + 1
                logger.debug(f"[VECTOR_STORE] Upserting batch {batch_num}/{total_batches} ({len(batch)} points)")
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch,
                    wait=True,
                )

            logger.info(f"[VECTOR_STORE] Successfully stored {len(points)} points in {collection_name}")
            return len(points)

        except Exception as e:
            logger.error(f"[VECTOR_STORE] Failed to store chunks: {str(e)}")
            raise VectorStoreError(f"Failed to store chunks: {str(e)}")

    def search(
        self,
        project_id: str,
        query_embedding: List[float],
        limit: int = 10,
        file_path_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
        laravel_type_filter: Optional[str] = None,
        score_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search for similar chunks.

        Args:
            project_id: The project's UUID
            query_embedding: Query embedding vector
            limit: Maximum number of results
            file_path_filter: Filter by file path (partial match)
            chunk_type_filter: Filter by chunk type
            laravel_type_filter: Filter by Laravel type
            score_threshold: Minimum similarity score

        Returns:
            List of SearchResult objects
        """
        collection_name = self._get_collection_name(project_id)

        if not self.collection_exists(project_id):
            return []

        try:
            # Build filter conditions
            filter_conditions = []

            if file_path_filter:
                filter_conditions.append(
                    models.FieldCondition(
                        key="file_path",
                        match=models.MatchText(text=file_path_filter),
                    )
                )

            if chunk_type_filter:
                filter_conditions.append(
                    models.FieldCondition(
                        key="chunk_type",
                        match=models.MatchValue(value=chunk_type_filter),
                    )
                )

            if laravel_type_filter:
                filter_conditions.append(
                    models.FieldCondition(
                        key="laravel_type",
                        match=models.MatchValue(value=laravel_type_filter),
                    )
                )

            # Create filter if we have conditions
            query_filter = None
            if filter_conditions:
                query_filter = models.Filter(
                    must=filter_conditions,
                )

            # Perform search
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
                with_payload=True,
            )

            # Convert to SearchResult objects
            search_results = []
            for result in results:
                payload = result.payload or {}
                search_results.append(SearchResult(
                    chunk_id=payload.get("chunk_id", str(result.id)),
                    file_path=payload.get("file_path", ""),
                    content=payload.get("content", ""),
                    chunk_type=payload.get("chunk_type", "unknown"),
                    score=result.score,
                    metadata={
                        "name": payload.get("name"),
                        "parent_name": payload.get("parent_name"),
                        "line_start": payload.get("line_start", 0),
                        "line_end": payload.get("line_end", 0),
                        "laravel_type": payload.get("laravel_type"),
                        "token_count": payload.get("token_count", 0),
                        **(payload.get("metadata", {})),
                    },
                ))

            return search_results

        except Exception as e:
            raise VectorStoreError(f"Search failed: {str(e)}")

    def delete_by_file_path(
        self,
        project_id: str,
        file_path: str,
    ) -> int:
        """
        Delete all chunks for a specific file.

        Args:
            project_id: The project's UUID
            file_path: Path of the file to delete chunks for

        Returns:
            Number of points deleted
        """
        collection_name = self._get_collection_name(project_id)

        if not self.collection_exists(project_id):
            return 0

        try:
            # Delete points matching the file path
            result = self.client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="file_path",
                                match=models.MatchValue(value=file_path),
                            )
                        ]
                    )
                ),
                wait=True,
            )

            return result.status if hasattr(result, 'status') else 0

        except Exception as e:
            raise VectorStoreError(f"Failed to delete chunks: {str(e)}")

    def get_collection_info(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a project's collection.

        Args:
            project_id: The project's UUID

        Returns:
            Collection info dictionary or None
        """
        collection_name = self._get_collection_name(project_id)

        if not self.collection_exists(project_id):
            return None

        try:
            info = self.client.get_collection(collection_name=collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value if info.status else "unknown",
                "dimension": info.config.params.vectors.size if info.config else 0,
            }

        except Exception as e:
            raise VectorStoreError(f"Failed to get collection info: {str(e)}")

    def count_chunks(self, project_id: str) -> int:
        """
        Count total chunks in a project's collection.

        Args:
            project_id: The project's UUID

        Returns:
            Number of chunks stored
        """
        info = self.get_collection_info(project_id)
        return info.get("points_count", 0) if info else 0


# Convenience functions

def create_collection(
    project_id: str,
    dimension: int = DEFAULT_DIMENSION,
    recreate: bool = False,
) -> bool:
    """Create a Qdrant collection for a project."""
    store = VectorStore()
    return store.create_collection(project_id, dimension, recreate)


def store_chunks(
    project_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    laravel_type: str = "unknown",
) -> int:
    """Store chunks with embeddings in Qdrant."""
    store = VectorStore()
    return store.store_chunks(project_id, chunks, embeddings, laravel_type)


def search(
    project_id: str,
    query_embedding: List[float],
    limit: int = 10,
    **filters,
) -> List[Dict[str, Any]]:
    """Search for similar chunks."""
    store = VectorStore()
    results = store.search(project_id, query_embedding, limit, **filters)
    return [r.to_dict() for r in results]


def delete_collection(project_id: str) -> bool:
    """Delete a project's collection."""
    store = VectorStore()
    return store.delete_collection(project_id)
