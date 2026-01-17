"""
Prompt Caching Service for Claude API.

Provides intelligent caching of system prompts and context to reduce costs
and improve response latency. Uses Anthropic's cache_control feature for
1-hour cache duration.
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheType(str, Enum):
    """Types of cacheable content."""
    SYSTEM_PROMPT = "system_prompt"
    PROJECT_CONTEXT = "project_context"
    CODE_CONTEXT = "code_context"
    CONVERSATION_HISTORY = "conversation_history"


@dataclass
class CacheStats:
    """Statistics for cache usage."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    tokens_saved: int = 0
    estimated_cost_saved: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "tokens_saved": self.tokens_saved,
            "estimated_cost_saved": self.estimated_cost_saved,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class CachedContent:
    """Represents cached content with metadata."""
    content_hash: str
    content: str
    cache_type: CacheType
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    access_count: int = 0
    tokens_estimate: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "content_hash": self.content_hash,
            "cache_type": self.cache_type.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
            "access_count": self.access_count,
            "tokens_estimate": self.tokens_estimate,
            "metadata": self.metadata,
        }


@dataclass
class CachedPromptResponse:
    """Response with cache information."""
    content: str
    cache_hit: bool = False
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_savings_estimate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "cache_hit": self.cache_hit,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "cost_savings_estimate": self.cost_savings_estimate,
        }


class PromptCacheService:
    """
    Service for caching prompts and context with Claude API.

    Uses Anthropic's cache_control feature for automatic caching of
    system prompts and large context blocks. Provides 90% cost reduction
    on cache hits.
    """

    # Cache pricing (90% discount on cache reads)
    CACHE_WRITE_MULTIPLIER = 1.25  # 25% extra for cache writes
    CACHE_READ_MULTIPLIER = 0.1   # 90% discount on cache reads

    # Minimum content length for caching (1024 tokens minimum required by API)
    MIN_CACHE_TOKENS = 1024

    # Cache TTL (Anthropic default is 5 minutes, but can extend with activity)
    CACHE_TTL_MINUTES = 5

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the prompt cache service.

        Args:
            api_key: Anthropic API key. Uses settings if not provided.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        # Local cache tracking (for statistics)
        self._content_cache: dict[str, CachedContent] = {}
        self._stats: dict[str, CacheStats] = {}

        logger.info("[PROMPT_CACHE] Service initialized with cache support")

    def _hash_content(self, content: str) -> str:
        """Generate hash for content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _estimate_tokens(self, content: str) -> int:
        """Estimate token count (rough approximation)."""
        # Rough estimate: 1 token per 4 characters
        return len(content) // 4

    def _should_cache(self, content: str) -> bool:
        """Determine if content should be cached."""
        tokens = self._estimate_tokens(content)
        return tokens >= self.MIN_CACHE_TOKENS

    def _get_stats(self, cache_type: CacheType) -> CacheStats:
        """Get or create stats for cache type."""
        if cache_type.value not in self._stats:
            self._stats[cache_type.value] = CacheStats()
        return self._stats[cache_type.value]

    def _update_stats(
        self,
        cache_type: CacheType,
        cache_hit: bool,
        tokens_saved: int = 0,
        cost_saved: float = 0.0,
    ) -> None:
        """Update cache statistics."""
        stats = self._get_stats(cache_type)
        stats.total_requests += 1
        if cache_hit:
            stats.cache_hits += 1
            stats.tokens_saved += tokens_saved
            stats.estimated_cost_saved += cost_saved
        else:
            stats.cache_misses += 1
        stats.last_updated = datetime.utcnow()

    def build_cached_system(
        self,
        base_prompt: str,
        project_context: Optional[str] = None,
        code_context: Optional[str] = None,
    ) -> list[dict]:
        """
        Build a system prompt with cache_control markers.

        Args:
            base_prompt: Base system prompt
            project_context: Optional project context (cached if large enough)
            code_context: Optional code context (cached if large enough)

        Returns:
            List of content blocks with cache_control
        """
        system_blocks = []

        # Base prompt (always included, may be cached)
        if self._should_cache(base_prompt):
            system_blocks.append({
                "type": "text",
                "text": base_prompt,
                "cache_control": {"type": "ephemeral"}
            })
            logger.info(f"[PROMPT_CACHE] Base prompt marked for caching ({self._estimate_tokens(base_prompt)} tokens)")
        else:
            system_blocks.append({
                "type": "text",
                "text": base_prompt,
            })

        # Project context (cached if large enough)
        if project_context and self._should_cache(project_context):
            system_blocks.append({
                "type": "text",
                "text": f"\n\n## Project Context\n{project_context}",
                "cache_control": {"type": "ephemeral"}
            })
            logger.info(f"[PROMPT_CACHE] Project context marked for caching ({self._estimate_tokens(project_context)} tokens)")
        elif project_context:
            system_blocks.append({
                "type": "text",
                "text": f"\n\n## Project Context\n{project_context}",
            })

        # Code context (cached if large enough)
        if code_context and self._should_cache(code_context):
            system_blocks.append({
                "type": "text",
                "text": f"\n\n## Code Context\n{code_context}",
                "cache_control": {"type": "ephemeral"}
            })
            logger.info(f"[PROMPT_CACHE] Code context marked for caching ({self._estimate_tokens(code_context)} tokens)")
        elif code_context:
            system_blocks.append({
                "type": "text",
                "text": f"\n\n## Code Context\n{code_context}",
            })

        return system_blocks

    async def chat_with_cache(
        self,
        messages: list[dict],
        system_prompt: str,
        project_context: Optional[str] = None,
        code_context: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> CachedPromptResponse:
        """
        Send a chat request with automatic prompt caching.

        Args:
            messages: Conversation messages
            system_prompt: Base system prompt
            project_context: Optional project context
            code_context: Optional code context
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            CachedPromptResponse with cache metrics
        """
        logger.info(f"[PROMPT_CACHE] Chat request with caching, model={model}")
        start_time = time.time()

        # Build cached system prompt
        system_blocks = self.build_cached_system(
            base_prompt=system_prompt,
            project_context=project_context,
            code_context=code_context,
        )

        try:
            response = await self.async_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_blocks,
                messages=messages,
            )

            content = response.content[0].text
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract cache metrics from usage
            usage = response.usage
            cache_creation = getattr(usage, 'cache_creation_input_tokens', 0) or 0
            cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens

            # Determine if this was a cache hit
            cache_hit = cache_read > 0

            # Calculate cost savings
            # Cache reads are 90% cheaper than regular input tokens
            if cache_hit:
                regular_cost = (cache_read / 1_000_000) * 3  # $3/MTok for Sonnet input
                cached_cost = (cache_read / 1_000_000) * 3 * self.CACHE_READ_MULTIPLIER
                cost_savings = regular_cost - cached_cost
            else:
                cost_savings = 0.0

            # Update statistics
            cache_type = CacheType.PROJECT_CONTEXT if project_context else CacheType.SYSTEM_PROMPT
            self._update_stats(
                cache_type=cache_type,
                cache_hit=cache_hit,
                tokens_saved=cache_read if cache_hit else 0,
                cost_saved=cost_savings,
            )

            logger.info(
                f"[PROMPT_CACHE] Response received - cache_hit={cache_hit}, "
                f"cache_creation={cache_creation}, cache_read={cache_read}, "
                f"latency={latency_ms}ms, cost_saved=${cost_savings:.6f}"
            )

            return CachedPromptResponse(
                content=content,
                cache_hit=cache_hit,
                cache_creation_input_tokens=cache_creation,
                cache_read_input_tokens=cache_read,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_savings_estimate=cost_savings,
            )

        except Exception as e:
            logger.error(f"[PROMPT_CACHE] Chat error: {e}")
            raise

    async def stream_with_cache(
        self,
        messages: list[dict],
        system_prompt: str,
        project_context: Optional[str] = None,
        code_context: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """
        Stream a chat response with automatic prompt caching.

        Args:
            messages: Conversation messages
            system_prompt: Base system prompt
            project_context: Optional project context
            code_context: Optional code context
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Yields:
            Response text chunks, then final CachedPromptResponse
        """
        logger.info(f"[PROMPT_CACHE] Stream request with caching, model={model}")
        start_time = time.time()

        # Build cached system prompt
        system_blocks = self.build_cached_system(
            base_prompt=system_prompt,
            project_context=project_context,
            code_context=code_context,
        )

        full_response = []
        cache_creation = 0
        cache_read = 0
        input_tokens = 0
        output_tokens = 0

        try:
            async with self.async_client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_blocks,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_response.append(text)
                    yield text

                # Get final message with usage stats
                final_message = await stream.get_final_message()
                usage = final_message.usage
                cache_creation = getattr(usage, 'cache_creation_input_tokens', 0) or 0
                cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens

        except Exception as e:
            logger.error(f"[PROMPT_CACHE] Stream error: {e}")
            raise

        latency_ms = int((time.time() - start_time) * 1000)
        cache_hit = cache_read > 0

        # Calculate cost savings
        if cache_hit:
            regular_cost = (cache_read / 1_000_000) * 3
            cached_cost = (cache_read / 1_000_000) * 3 * self.CACHE_READ_MULTIPLIER
            cost_savings = regular_cost - cached_cost
        else:
            cost_savings = 0.0

        # Update statistics
        cache_type = CacheType.PROJECT_CONTEXT if project_context else CacheType.SYSTEM_PROMPT
        self._update_stats(
            cache_type=cache_type,
            cache_hit=cache_hit,
            tokens_saved=cache_read if cache_hit else 0,
            cost_saved=cost_savings,
        )

        logger.info(
            f"[PROMPT_CACHE] Stream completed - cache_hit={cache_hit}, "
            f"cache_read={cache_read}, latency={latency_ms}ms"
        )

        # Yield final response object
        yield CachedPromptResponse(
            content="".join(full_response),
            cache_hit=cache_hit,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_savings_estimate=cost_savings,
        )

    def get_stats(self, cache_type: Optional[CacheType] = None) -> dict:
        """
        Get cache statistics.

        Args:
            cache_type: Optional specific cache type

        Returns:
            Dict of statistics
        """
        if cache_type:
            return self._get_stats(cache_type).to_dict()

        return {
            cache_type: stats.to_dict()
            for cache_type, stats in self._stats.items()
        }

    def get_total_savings(self) -> dict:
        """Get total cost savings across all cache types."""
        total_tokens = 0
        total_cost = 0.0
        total_requests = 0
        total_hits = 0

        for stats in self._stats.values():
            total_tokens += stats.tokens_saved
            total_cost += stats.estimated_cost_saved
            total_requests += stats.total_requests
            total_hits += stats.cache_hits

        return {
            "total_requests": total_requests,
            "total_cache_hits": total_hits,
            "overall_hit_rate": total_hits / total_requests if total_requests > 0 else 0.0,
            "total_tokens_saved": total_tokens,
            "total_cost_saved": total_cost,
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._stats.clear()
        logger.info("[PROMPT_CACHE] Statistics reset")


# Factory function
def get_prompt_cache_service() -> PromptCacheService:
    """Get a prompt cache service instance."""
    return PromptCacheService()
