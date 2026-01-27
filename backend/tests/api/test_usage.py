"""
Integration tests for Usage API endpoints.

Tests usage tracking, statistics, and pricing endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestUsageAPI:
    """Test suite for /api/v1/usage endpoints."""

    # =========================================================================
    # Usage Summary
    # =========================================================================

    def test_summary_requires_auth(self, client):
        """GET /api/v1/usage/summary without token should return 401."""
        response = client.get("/api/v1/usage/summary")
        assert response.status_code == 401

    # =========================================================================
    # Daily Breakdown
    # =========================================================================

    def test_daily_requires_auth(self, client):
        """GET /api/v1/usage/daily without token should return 401."""
        response = client.get("/api/v1/usage/daily")
        assert response.status_code == 401

    # =========================================================================
    # History
    # =========================================================================

    def test_history_requires_auth(self, client):
        """GET /api/v1/usage/history without token should return 401."""
        response = client.get("/api/v1/usage/history")
        assert response.status_code == 401

    # =========================================================================
    # Project Usage
    # =========================================================================

    def test_project_usage_requires_auth(self, client):
        """GET /api/v1/usage/project/{id} without token should return 401."""
        response = client.get(f"/api/v1/usage/project/{uuid4()}")
        assert response.status_code == 401

    # =========================================================================
    # Pricing
    # =========================================================================

    def test_pricing_requires_auth(self, client):
        """GET /api/v1/usage/pricing without token should return 401."""
        response = client.get("/api/v1/usage/pricing")
        assert response.status_code == 401

    # =========================================================================
    # Stats
    # =========================================================================

    def test_stats_requires_auth(self, client):
        """GET /api/v1/usage/stats without token should return 401."""
        response = client.get("/api/v1/usage/stats")
        assert response.status_code == 401
