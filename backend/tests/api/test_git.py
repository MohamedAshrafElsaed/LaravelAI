"""
Integration tests for Git API endpoints.

Tests git operations, branch management, and change tracking.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestGitAPI:
    """Test suite for /api/v1/projects/{project_id}/git endpoints."""

    # =========================================================================
    # List Branches
    # =========================================================================

    def test_list_branches_requires_auth(self, client):
        """GET /api/v1/projects/{project_id}/branches without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/branches")
        assert response.status_code == 401

    @patch("app.api.git.get_valid_git_service")
    def test_list_branches(
        self, mock_get_git_service, client_with_mocked_db, mock_db_async, test_project
    ):
        """GET /api/v1/projects/{project_id}/branches should return branches."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project
        mock_db_async.execute.return_value = mock_result

        mock_git = MagicMock()
        mock_git.list_branches.return_value = [
            {"name": "main", "is_current": True, "commit": "abc123", "message": "Initial commit", "author": "testuser", "date": "2024-01-15"},
            {"name": "develop", "is_current": False, "commit": "def456", "message": "Add feature", "author": "testuser", "date": "2024-01-14"},
        ]
        mock_get_git_service.return_value = mock_git

        response = client_with_mocked_db.get(f"/api/v1/projects/{test_project.id}/branches")
        assert response.status_code == 200
        data = response.json()
        assert "branches" in data or isinstance(data, list)

    @patch("app.api.git.get_valid_git_service")
    def test_list_branches_project_not_found(
        self, mock_get_git_service, client_with_mocked_db, mock_db_async
    ):
        """GET /api/v1/projects/{project_id}/branches with invalid project should return 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get(f"/api/v1/projects/{uuid4()}/branches")
        assert response.status_code == 404

    # =========================================================================
    # Apply Changes
    # =========================================================================

    def test_apply_changes_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/apply without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/apply", json={"changes": []})
        assert response.status_code == 401

    # =========================================================================
    # Create PR
    # =========================================================================

    def test_create_pr_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/pr without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/pr", json={})
        assert response.status_code == 401

    # =========================================================================
    # Sync Repository
    # =========================================================================

    def test_sync_repo_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/sync without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/sync")
        assert response.status_code == 401

    # =========================================================================
    # Reset Repository
    # =========================================================================

    def test_reset_repo_requires_auth(self, client):
        """POST /api/v1/projects/{project_id}/reset without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/reset")
        assert response.status_code == 401

    # =========================================================================
    # Get Diff
    # =========================================================================

    def test_get_diff_requires_auth(self, client):
        """GET /api/v1/projects/{project_id}/diff without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/diff")
        assert response.status_code == 401

    # =========================================================================
    # Git Changes
    # =========================================================================

    def test_list_changes_requires_auth(self, client):
        """GET /api/v1/projects/{project_id}/changes without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/changes")
        assert response.status_code == 401

    def test_list_changes(self, client_with_mocked_db, mock_db_async, test_project, test_git_change):
        """GET /api/v1/projects/{project_id}/changes should return changes."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project
        mock_result.scalars.return_value.all.return_value = [test_git_change]
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get(f"/api/v1/projects/{test_project.id}/changes")
        assert response.status_code == 200

    def test_get_change(self, client_with_mocked_db, mock_db_async, test_project, test_git_change):
        """GET /api/v1/projects/{project_id}/changes/{id} should return change."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_git_change
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get(
            f"/api/v1/projects/{test_project.id}/changes/{test_git_change.id}"
        )
        assert response.status_code == 200

    def test_delete_change(self, client_with_mocked_db, mock_db_async, test_project, test_git_change):
        """DELETE /api/v1/projects/{project_id}/changes/{id} should delete change."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_git_change
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.delete(
            f"/api/v1/projects/{test_project.id}/changes/{test_git_change.id}"
        )
        assert response.status_code in [200, 204]


class TestGitAPIEdgeCases:
    """Test edge cases for Git API."""

    @patch("app.api.git.get_valid_git_service")
    def test_branches_empty_repo(
        self, mock_get_git_service, client_with_mocked_db, mock_db_async, test_project
    ):
        """Branches endpoint should handle empty repo gracefully."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_project
        mock_db_async.execute.return_value = mock_result

        mock_git = MagicMock()
        mock_git.list_branches.return_value = []
        mock_get_git_service.return_value = mock_git

        response = client_with_mocked_db.get(f"/api/v1/projects/{test_project.id}/branches")
        assert response.status_code == 200
        data = response.json()
        assert "branches" in data or isinstance(data, list)
