"""
Embeddings service for generating vector embeddings.
Supports OpenAI and Voyage AI embedding models.
"""
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import httpx

from app.core.config import settings


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    VOYAGE = "voyage"


# Default models for each provider
DEFAULT_MODELS = {
    EmbeddingProvider.OPENAI: "text-embedding-3-small",
    EmbeddingProvider.VOYAGE: "voyage-code-3",
}

# Batch sizes for each provider
BATCH_SIZES = {
    EmbeddingProvider.OPENAI: 100,  # OpenAI max is 2048, but 100 is safer
    EmbeddingProvider.VOYAGE: 128,  # Voyage AI batch size
}

# Embedding dimensions
EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "voyage-code-3": 1024,
    "voyage-code-2": 1536,
}


class EmbeddingError(Exception):
    """Custom exception for embedding errors."""
    pass


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    embeddings: List[List[float]]
    model: str
    total_tokens: int
    dimension: int


class EmbeddingService:
    """Service for generating embeddings using OpenAI or Voyage AI."""

    def __init__(
        self,
        provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the embedding service.

        Args:
            provider: The embedding provider to use
            model: The model to use (defaults to provider's default)
            api_key: API key (defaults to config)
        """
        self.provider = provider
        self.model = model or DEFAULT_MODELS[provider]
        self.batch_size = BATCH_SIZES[provider]

        # Get API key from config if not provided
        if api_key:
            self.api_key = api_key
        elif provider == EmbeddingProvider.OPENAI:
            self.api_key = settings.openai_api_key
        else:
            self.api_key = settings.voyage_api_key

        if not self.api_key:
            raise EmbeddingError(
                f"No API key configured for {provider.value}. "
                f"Set {'OPENAI_API_KEY' if provider == EmbeddingProvider.OPENAI else 'VOYAGE_API_KEY'} "
                "in your environment."
            )

        # HTTP client for async requests
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _embed_openai(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings using OpenAI API."""
        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": self.model,
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                raise EmbeddingError(f"OpenAI API error: {error_msg}")

            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            total_tokens = data.get("usage", {}).get("total_tokens", 0)

            return EmbeddingResult(
                embeddings=embeddings,
                model=self.model,
                total_tokens=total_tokens,
                dimension=len(embeddings[0]) if embeddings else 0,
            )

        except httpx.RequestError as e:
            raise EmbeddingError(f"Network error calling OpenAI: {str(e)}")

    async def _embed_voyage(self, texts: List[str]) -> EmbeddingResult:
        """Generate embeddings using Voyage AI API."""
        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": self.model,
                    "input_type": "document",  # For code indexing
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get("detail", response.text)
                raise EmbeddingError(f"Voyage AI API error: {error_msg}")

            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            total_tokens = data.get("usage", {}).get("total_tokens", 0)

            return EmbeddingResult(
                embeddings=embeddings,
                model=self.model,
                total_tokens=total_tokens,
                dimension=len(embeddings[0]) if embeddings else 0,
            )

        except httpx.RequestError as e:
            raise EmbeddingError(f"Network error calling Voyage AI: {str(e)}")

    async def embed_batch(self, texts: List[str]) -> EmbeddingResult:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed (should be <= batch_size)

        Returns:
            EmbeddingResult containing embeddings and metadata
        """
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=self.model,
                total_tokens=0,
                dimension=EMBEDDING_DIMENSIONS.get(self.model, 1536),
            )

        if self.provider == EmbeddingProvider.OPENAI:
            return await self._embed_openai(texts)
        else:
            return await self._embed_voyage(texts)

    async def embed_chunks(
        self,
        chunks: List[Dict[str, Any]],
        content_key: str = "content",
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of chunks.
        Handles batching automatically.

        Args:
            chunks: List of chunk dictionaries
            content_key: Key in chunk dict containing the text to embed

        Returns:
            List of embeddings (one per chunk)
        """
        if not chunks:
            return []

        # Extract texts
        texts = [chunk.get(content_key, "") for chunk in chunks]

        # Filter out empty texts
        non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]
        non_empty_texts = [texts[i] for i in non_empty_indices]

        if not non_empty_texts:
            # Return zero vectors for empty inputs
            dim = EMBEDDING_DIMENSIONS.get(self.model, 1536)
            return [[0.0] * dim for _ in chunks]

        # Process in batches
        all_embeddings: List[List[float]] = []

        for i in range(0, len(non_empty_texts), self.batch_size):
            batch = non_empty_texts[i:i + self.batch_size]
            result = await self.embed_batch(batch)
            all_embeddings.extend(result.embeddings)

            # Small delay to avoid rate limiting
            if i + self.batch_size < len(non_empty_texts):
                await asyncio.sleep(0.1)

        # Map embeddings back to original indices
        dim = len(all_embeddings[0]) if all_embeddings else EMBEDDING_DIMENSIONS.get(self.model, 1536)
        final_embeddings: List[List[float]] = [[0.0] * dim for _ in chunks]

        for idx, emb in zip(non_empty_indices, all_embeddings):
            final_embeddings[idx] = emb

        return final_embeddings

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.

        Args:
            query: The search query text

        Returns:
            Embedding vector
        """
        if not query.strip():
            dim = EMBEDDING_DIMENSIONS.get(self.model, 1536)
            return [0.0] * dim

        # For Voyage AI, use query input type
        if self.provider == EmbeddingProvider.VOYAGE:
            client = await self._get_client()
            try:
                response = await client.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "input": [query],
                        "model": self.model,
                        "input_type": "query",  # Different from document embedding
                    },
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("detail", response.text)
                    raise EmbeddingError(f"Voyage AI API error: {error_msg}")

                data = response.json()
                return data["data"][0]["embedding"]

            except httpx.RequestError as e:
                raise EmbeddingError(f"Network error calling Voyage AI: {str(e)}")

        # OpenAI doesn't differentiate query vs document
        result = await self.embed_batch([query])
        return result.embeddings[0]


# Convenience functions

async def embed_chunks(
    chunks: List[Dict[str, Any]],
    provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[List[float]]:
    """
    Generate embeddings for a list of chunks.

    Args:
        chunks: List of chunk dictionaries with 'content' key
        provider: Embedding provider to use
        model: Model to use (optional)
        api_key: API key (optional, uses config default)

    Returns:
        List of embedding vectors
    """
    service = EmbeddingService(provider=provider, model=model, api_key=api_key)
    try:
        return await service.embed_chunks(chunks)
    finally:
        await service.close()


async def embed_query(
    query: str,
    provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[float]:
    """
    Generate embedding for a search query.

    Args:
        query: Search query text
        provider: Embedding provider to use
        model: Model to use (optional)
        api_key: API key (optional, uses config default)

    Returns:
        Embedding vector
    """
    service = EmbeddingService(provider=provider, model=model, api_key=api_key)
    try:
        return await service.embed_query(query)
    finally:
        await service.close()


def get_embedding_dimension(model: str) -> int:
    """Get the embedding dimension for a model."""
    return EMBEDDING_DIMENSIONS.get(model, 1536)
