"""
Token Counter Service.

Provides token counting capabilities for pre-request estimation
and budget checking.
"""
import logging
from typing import Optional, List, Dict, Any

from anthropic import Anthropic

from app.core.config import settings
from app.core.pricing import calculate_cost, estimate_cost

logger = logging.getLogger(__name__)


class TokenCounter:
    """
    Service for counting tokens before making API calls.

    Uses Anthropic's token counting API to get accurate token counts
    for budget estimation and rate limiting.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the token counter.

        Args:
            api_key: Anthropic API key. Uses settings if not provided.
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = Anthropic(api_key=self.api_key)
        logger.info("[TOKEN_COUNTER] Service initialized")

    def count_claude_tokens(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Count tokens for a Claude API request before sending.

        Uses Anthropic's token counting API to get exact input token count.

        Args:
            model: Claude model identifier
            messages: List of message dicts with 'role' and 'content'
            system: Optional system prompt
            tools: Optional list of tool definitions

        Returns:
            Number of input tokens
        """
        logger.debug(f"[TOKEN_COUNTER] Counting tokens for model={model}")

        try:
            params: Dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            if system:
                params["system"] = system
            if tools:
                params["tools"] = tools

            response = self.client.messages.count_tokens(**params)
            token_count = response.input_tokens

            logger.info(f"[TOKEN_COUNTER] Token count: {token_count}")
            return token_count

        except Exception as e:
            logger.error(f"[TOKEN_COUNTER] Error counting tokens: {str(e)}")
            # Return estimate based on character count as fallback
            return self._estimate_tokens_from_text(messages, system)

    def _estimate_tokens_from_text(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
    ) -> int:
        """
        Estimate tokens from text length when API is unavailable.

        Uses approximate ratio of 4 characters per token.

        Args:
            messages: List of message dicts
            system: Optional system prompt

        Returns:
            Estimated token count
        """
        total_chars = 0

        if system:
            total_chars += len(system)

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                # Handle multi-part content
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total_chars += len(part.get("text", ""))

        # Rough estimate: ~4 characters per token
        estimated = total_chars // 4
        logger.debug(f"[TOKEN_COUNTER] Estimated {estimated} tokens from {total_chars} chars")
        return estimated

    def estimate_request_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        estimated_output_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """
        Estimate the cost of an API request before making it.

        Args:
            provider: AI provider (claude, openai, voyage)
            model: Model identifier
            input_tokens: Known input token count
            estimated_output_tokens: Estimated output tokens (default 1000)

        Returns:
            Dict with input_cost, output_cost, total_cost estimates
        """
        logger.debug(
            f"[TOKEN_COUNTER] Estimating cost - provider={provider}, model={model}, "
            f"input={input_tokens}, output_est={estimated_output_tokens}"
        )

        costs = estimate_cost(provider, model, input_tokens, estimated_output_tokens)

        logger.info(f"[TOKEN_COUNTER] Estimated cost: ${costs['total_cost']:.6f}")
        return costs

    def check_budget(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        estimated_output_tokens: int,
        budget_limit: float,
    ) -> Dict[str, Any]:
        """
        Check if a request would exceed a budget limit.

        Args:
            provider: AI provider
            model: Model identifier
            input_tokens: Known input token count
            estimated_output_tokens: Estimated output tokens
            budget_limit: Maximum allowed cost

        Returns:
            Dict with within_budget, estimated_cost, and budget_remaining
        """
        costs = self.estimate_request_cost(
            provider, model, input_tokens, estimated_output_tokens
        )

        within_budget = costs["total_cost"] <= budget_limit
        budget_remaining = budget_limit - costs["total_cost"]

        result = {
            "within_budget": within_budget,
            "estimated_cost": costs["total_cost"],
            "budget_limit": budget_limit,
            "budget_remaining": max(0, budget_remaining),
        }

        if not within_budget:
            logger.warning(
                f"[TOKEN_COUNTER] Budget exceeded - estimated=${costs['total_cost']:.6f}, "
                f"limit=${budget_limit:.6f}"
            )

        return result


# Singleton instance
_counter_instance: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """Get or create the token counter singleton."""
    global _counter_instance
    if _counter_instance is None:
        _counter_instance = TokenCounter()
    return _counter_instance
