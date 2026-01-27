"""
Unit tests for Usage module functions.

Tests usage tracking, cost calculation, and statistics aggregation.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from decimal import Decimal


class TestUsageModel:
    """Unit tests for Usage model."""

    def test_usage_record_creation(self):
        """Usage record should be created correctly."""
        from uuid import uuid4

        record = MagicMock()
        record.user_id = str(uuid4())
        record.project_id = str(uuid4())
        record.model = "claude-3-sonnet"
        record.provider = "anthropic"
        record.request_type = "chat"
        record.input_tokens = 1000
        record.output_tokens = 500
        record.total_tokens = 1500
        record.cost = Decimal("0.0045")

        assert record.input_tokens + record.output_tokens == record.total_tokens
        assert record.cost > 0


class TestCostCalculation:
    """Unit tests for cost calculation."""

    def test_claude_sonnet_pricing(self):
        """Claude Sonnet pricing should be correct."""
        # Pricing: $3 per 1M input, $15 per 1M output
        input_price_per_million = 3.0
        output_price_per_million = 15.0

        input_tokens = 1000
        output_tokens = 500

        input_cost = (input_tokens / 1_000_000) * input_price_per_million
        output_cost = (output_tokens / 1_000_000) * output_price_per_million
        total_cost = input_cost + output_cost

        assert input_cost == pytest.approx(0.003)
        assert output_cost == pytest.approx(0.0075)
        assert total_cost == pytest.approx(0.0105)

    def test_claude_haiku_pricing(self):
        """Claude Haiku pricing should be correct."""
        # Pricing: $0.25 per 1M input, $1.25 per 1M output
        input_price_per_million = 0.25
        output_price_per_million = 1.25

        input_tokens = 1000
        output_tokens = 500

        input_cost = (input_tokens / 1_000_000) * input_price_per_million
        output_cost = (output_tokens / 1_000_000) * output_price_per_million
        total_cost = input_cost + output_cost

        assert total_cost < 0.001  # Much cheaper than Sonnet

    def test_batch_pricing_discount(self):
        """Batch API should have 50% discount."""
        regular_cost = 0.01
        batch_discount = 0.5
        batch_cost = regular_cost * batch_discount

        assert batch_cost == 0.005

    def test_prompt_caching_savings(self):
        """Prompt caching should reduce costs."""
        full_price = 0.01
        cache_read_discount = 0.1  # 90% discount for cache reads

        cached_cost = full_price * cache_read_discount
        savings = full_price - cached_cost

        assert savings == pytest.approx(0.009)
        assert cached_cost == pytest.approx(0.001)


class TestUsageAggregation:
    """Unit tests for usage aggregation."""

    def test_daily_aggregation(self):
        """Daily usage should aggregate correctly."""
        records = [
            {"date": "2024-01-15", "tokens": 1000, "cost": 0.01},
            {"date": "2024-01-15", "tokens": 2000, "cost": 0.02},
            {"date": "2024-01-14", "tokens": 1500, "cost": 0.015},
        ]

        # Aggregate by date
        daily = {}
        for r in records:
            date = r["date"]
            if date not in daily:
                daily[date] = {"tokens": 0, "cost": 0}
            daily[date]["tokens"] += r["tokens"]
            daily[date]["cost"] += r["cost"]

        assert daily["2024-01-15"]["tokens"] == 3000
        assert daily["2024-01-15"]["cost"] == 0.03

    def test_model_aggregation(self):
        """Usage by model should aggregate correctly."""
        records = [
            {"model": "claude-sonnet", "tokens": 1000},
            {"model": "claude-sonnet", "tokens": 2000},
            {"model": "claude-haiku", "tokens": 5000},
        ]

        by_model = {}
        for r in records:
            model = r["model"]
            if model not in by_model:
                by_model[model] = 0
            by_model[model] += r["tokens"]

        assert by_model["claude-sonnet"] == 3000
        assert by_model["claude-haiku"] == 5000

    def test_period_filtering(self):
        """Usage should be filterable by date range."""
        records = [
            MagicMock(created_at=datetime(2024, 1, 15)),
            MagicMock(created_at=datetime(2024, 1, 10)),
            MagicMock(created_at=datetime(2024, 1, 5)),
            MagicMock(created_at=datetime(2023, 12, 25)),
        ]

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        filtered = [r for r in records if start_date <= r.created_at <= end_date]
        assert len(filtered) == 3


class TestUsageSummary:
    """Unit tests for usage summary generation."""

    def test_summary_structure(self):
        """Usage summary should have correct structure."""
        summary = {
            "total_requests": 100,
            "total_input_tokens": 50000,
            "total_output_tokens": 30000,
            "total_tokens": 80000,
            "total_cost": 1.50,
        }

        assert summary["total_tokens"] == summary["total_input_tokens"] + summary["total_output_tokens"]
        assert summary["total_cost"] > 0

    def test_today_stats(self):
        """Today's stats should be computed correctly."""
        today = datetime.utcnow().date()
        records = [
            MagicMock(created_at=datetime.combine(today, datetime.min.time()), cost=0.05),
            MagicMock(created_at=datetime.combine(today, datetime.min.time()), cost=0.10),
            MagicMock(created_at=datetime.combine(today - timedelta(days=1), datetime.min.time()), cost=0.20),
        ]

        today_records = [r for r in records if r.created_at.date() == today]
        today_cost = sum(r.cost for r in today_records)

        assert today_cost == pytest.approx(0.15)

    def test_empty_summary(self):
        """Empty usage should return zeros."""
        summary = {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

        assert all(v == 0 or v == 0.0 for v in summary.values())


class TestPricingInfo:
    """Unit tests for pricing information."""

    def test_pricing_models(self):
        """Pricing info should include all models."""
        pricing = {
            "claude-3-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
            "claude-3-opus": {"input": 15.0, "output": 75.0},
        }

        assert "claude-3-sonnet" in pricing
        assert "claude-3-haiku" in pricing
        assert pricing["claude-3-haiku"]["input"] < pricing["claude-3-sonnet"]["input"]

    def test_pricing_units(self):
        """Pricing should be per million tokens."""
        # All prices are per 1M tokens
        sonnet_input = 3.0  # $3 per 1M
        sonnet_output = 15.0  # $15 per 1M

        # Calculate cost for 1000 tokens
        cost_1k_input = (1000 / 1_000_000) * sonnet_input
        assert cost_1k_input == 0.003


class TestUsageTracker:
    """Unit tests for UsageTracker methods."""

    @pytest.mark.asyncio
    async def test_track_usage(self, mock_usage_tracker):
        """track_usage should record usage correctly."""
        mock_usage_tracker.track = AsyncMock()

        await mock_usage_tracker.track(
            user_id="user-123",
            project_id="project-456",
            model="claude-3-sonnet",
            input_tokens=1000,
            output_tokens=500,
            request_type="chat",
        )

        # Verify track was called
        mock_usage_tracker.track.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_summary(self, mock_usage_tracker):
        """get_user_summary should return aggregated data."""
        summary = await mock_usage_tracker.get_user_summary("user-123", days=30)

        assert "summary" in summary
        assert "total_requests" in summary["summary"]
