"""
Integration tests for GitHub API endpoints.

Tests GitHub repository listing and access.
"""
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4


class TestGitHubAPI:
    """Test suite for /api/v1/github endpoints."""

    # =========================================================================
    # List Repositories
    # =========================================================================

    def test_repos_requires_auth(self, client):
        """GET /api/v1/github/repos without token should return 401."""
        response = client.get("/api/v1/github/repos")
        assert response.status_code == 401

    def test_repos_invalid_token(self, client):
        """GET /api/v1/github/repos with invalid token should return 401."""
        response = client.get(
            "/api/v1/github/repos",
            headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401

    # =========================================================================
    # Get Single Repository
    # =========================================================================

    def test_repo_by_id_requires_auth(self, client):
        """GET /api/v1/github/repos/{id} without token should return 401."""
        response = client.get("/api/v1/github/repos/12345")
        assert response.status_code == 401
