"""
Integration tests for GitHub Data API endpoints.

Tests GitHub data synchronization for issues, actions, projects, and insights.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestGitHubDataAPI:
    """Test suite for /api/v1/projects/{project_id}/... GitHub data endpoints."""

    # =========================================================================
    # List Issues
    # =========================================================================

    def test_list_issues_requires_auth(self, client):
        """GET /api/v1/projects/{project_id}/issues without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/issues")
        assert response.status_code == 401

    def test_list_issues(
        self, client_with_mocked_db, mock_db_async, test_project
    ):
        """GET /api/v1/projects/{project_id}/issues should return issues."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project
        mock_result.scalars.return_value.all.return_value = []
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get(f"/api/v1/projects/{test_project.id}/issues")
        assert response.status_code == 200

    # =========================================================================
    # Sync Issues
    # =========================================================================

    def test_sync_issues_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/sync/issues without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/sync/issues")
        assert response.status_code == 401

    # =========================================================================
    # List Actions
    # =========================================================================

    def test_list_actions_requires_auth(self, client):
        """GET /api/v1/projects/{project_id}/actions without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/actions")
        assert response.status_code == 401

    # =========================================================================
    # Sync Actions
    # =========================================================================

    def test_sync_actions_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/sync/actions without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/sync/actions")
        assert response.status_code == 401

    # =========================================================================
    # Full Sync
    # =========================================================================

    def test_full_sync_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/sync/all without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/sync/all")
        assert response.status_code == 401

    # =========================================================================
    # Insights
    # =========================================================================

    def test_get_insights_requires_auth(self, client):
        """GET /api/v1/projects/{project_id}/insights without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/insights")
        assert response.status_code == 401
