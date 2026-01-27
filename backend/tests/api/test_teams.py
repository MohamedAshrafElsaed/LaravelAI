"""
Integration tests for Teams API endpoints.

Tests team management, member operations, and project assignments.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestTeamsAPI:
    """Test suite for /api/v1/teams endpoints."""

    # =========================================================================
    # Create Team
    # =========================================================================

    def test_create_team_requires_auth(self, client):
        """POST /api/v1/teams without token should return 401."""
        response = client.post("/api/v1/teams", json={"name": "Test Team"})
        assert response.status_code == 401

    def test_create_team_missing_name(self, client_with_mocked_db):
        """POST /api/v1/teams without name should return 422."""
        response = client_with_mocked_db.post("/api/v1/teams", json={})
        assert response.status_code == 422

    # =========================================================================
    # List Teams
    # =========================================================================

    def test_list_teams_requires_auth(self, client):
        """GET /api/v1/teams without token should return 401."""
        response = client.get("/api/v1/teams")
        assert response.status_code == 401

    def test_list_teams(self, client_with_mocked_db, mock_db_async):
        """GET /api/v1/teams should return user's teams."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get("/api/v1/teams")
        assert response.status_code == 200

    # =========================================================================
    # Get Team
    # =========================================================================

    def test_get_team_requires_auth(self, client):
        """GET /api/v1/teams/{id} without token should return 401."""
        response = client.get(f"/api/v1/teams/{uuid4()}")
        assert response.status_code == 401

    # =========================================================================
    # Update Team
    # =========================================================================

    def test_update_team_requires_auth(self, client):
        """PATCH /api/v1/teams/{id} without token should return 401."""
        response = client.patch(f"/api/v1/teams/{uuid4()}", json={"name": "New Name"})
        assert response.status_code == 401

    # =========================================================================
    # Delete Team
    # =========================================================================

    def test_delete_team_requires_auth(self, client):
        """DELETE /api/v1/teams/{id} without token should return 401."""
        response = client.delete(f"/api/v1/teams/{uuid4()}")
        assert response.status_code == 401

    # =========================================================================
    # Team Members
    # =========================================================================

    def test_list_members_requires_auth(self, client):
        """GET /api/v1/teams/{id}/members without token should return 401."""
        response = client.get(f"/api/v1/teams/{uuid4()}/members")
        assert response.status_code == 401

    def test_invite_member_requires_auth(self, client):
        """POST /api/v1/teams/{id}/members without token should return 401."""
        response = client.post(f"/api/v1/teams/{uuid4()}/members", json={})
        assert response.status_code == 401

    def test_remove_member_requires_auth(self, client):
        """DELETE /api/v1/teams/{id}/members/{mid} without token should return 401."""
        response = client.delete(f"/api/v1/teams/{uuid4()}/members/{uuid4()}")
        assert response.status_code == 401

    # =========================================================================
    # Team Projects
    # =========================================================================

    def test_list_team_projects_requires_auth(self, client):
        """GET /api/v1/teams/{id}/projects without token should return 401."""
        response = client.get(f"/api/v1/teams/{uuid4()}/projects")
        assert response.status_code == 401
