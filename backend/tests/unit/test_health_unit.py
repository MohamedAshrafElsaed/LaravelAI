"""
Unit Tests for Health API

Isolated unit tests for health check functionality.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestHealthCheckUnit:
    """Unit tests for health check endpoint logic."""

    @pytest.mark.asyncio
    async def test_health_check_function_returns_dict(self):
        """Health check function should return a dictionary."""
        from app.api.health import health_check

        result = await health_check()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_health_check_function_has_status(self):
        """Health check function should include status key."""
        from app.api.health import health_check

        result = await health_check()

        assert "status" in result
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_function_has_service(self):
        """Health check function should include service key."""
        from app.api.health import health_check

        result = await health_check()

        assert "service" in result
        assert result["service"] == "laravel-ai"


class TestHealthRouterConfiguration:
    """Unit tests for health router configuration."""

    def test_health_router_exists(self):
        """Health router should be properly defined."""
        from app.api.health import router

        assert router is not None

    def test_health_router_has_routes(self):
        """Health router should have registered routes."""
        from app.api.health import router

        routes = [route.path for route in router.routes]
        assert "/health" in routes

    def test_health_route_method(self):
        """Health route should use GET method."""
        from app.api.health import router

        for route in router.routes:
            if route.path == "/health":
                assert "GET" in route.methods
