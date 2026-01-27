"""
Integration Tests for Health API

Tests the health check endpoints to verify service availability.
"""
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """Health endpoint should return correct JSON structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "service" in data

    def test_health_check_status_healthy(self, client):
        """Health endpoint should report healthy status."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_check_service_name(self, client):
        """Health endpoint should report correct service name."""
        response = client.get("/health")
        data = response.json()

        assert data["service"] == "laravel-ai"

    def test_health_check_content_type(self, client):
        """Health endpoint should return JSON content type."""
        response = client.get("/health")

        assert response.headers["content-type"] == "application/json"

    def test_health_check_no_auth_required(self, client):
        """Health endpoint should not require authentication."""
        # No auth headers provided
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_method_not_allowed_post(self, client):
        """Health endpoint should not accept POST requests."""
        response = client.post("/health")
        assert response.status_code == 405

    def test_health_check_method_not_allowed_put(self, client):
        """Health endpoint should not accept PUT requests."""
        response = client.put("/health")
        assert response.status_code == 405

    def test_health_check_method_not_allowed_delete(self, client):
        """Health endpoint should not accept DELETE requests."""
        response = client.delete("/health")
        assert response.status_code == 405


class TestRootEndpoint:
    """Test suite for / root endpoint."""

    def test_root_returns_200(self, client):
        """Root endpoint should return 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_structure(self, client):
        """Root endpoint should return correct JSON structure."""
        response = client.get("/")
        data = response.json()

        assert "service" in data
        assert "version" in data
        assert "status" in data

    def test_root_service_name(self, client):
        """Root endpoint should report correct service name."""
        response = client.get("/")
        data = response.json()

        assert data["service"] == "Laravel AI Backend"

    def test_root_version(self, client):
        """Root endpoint should report version."""
        response = client.get("/")
        data = response.json()

        assert data["version"] == "1.0.0"

    def test_root_status_running(self, client):
        """Root endpoint should report running status."""
        response = client.get("/")
        data = response.json()

        assert data["status"] == "running"

    def test_root_content_type(self, client):
        """Root endpoint should return JSON content type."""
        response = client.get("/")

        assert response.headers["content-type"] == "application/json"
