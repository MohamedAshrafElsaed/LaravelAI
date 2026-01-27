"""
Integration tests for Projects API endpoints.

Tests project CRUD, indexing, scanning, and file operations.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestProjectsAPI:
    """Test suite for /api/v1/projects endpoints."""

    # =========================================================================
    # List Projects
    # =========================================================================

    def test_list_projects_requires_auth(self, client):
        """GET /api/v1/projects without token should return 401."""
        response = client.get("/api/v1/projects")
        assert response.status_code in [401, 307]

    def test_list_projects_empty(self, client_with_mocked_db, mock_db_async):
        """GET /api/v1/projects should return empty list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data or isinstance(data, list)

    # =========================================================================
    # Create Project
    # =========================================================================

    def test_create_project_requires_auth(self, client):
        """POST /api/v1/projects without token should return 401."""
        response = client.post("/api/v1/projects", json={
            "github_repo_id": 123456,
            "repo_full_name": "testuser/test-repo",
            "repo_url": "https://github.com/testuser/test-repo"
        })
        assert response.status_code in [401, 307]

    def test_create_project_missing_fields(self, client_with_mocked_db):
        """POST /api/v1/projects with missing fields should return 422."""
        response = client_with_mocked_db.post("/api/v1/projects", json={})
        assert response.status_code == 422

    # =========================================================================
    # Get Project
    # =========================================================================

    def test_get_project_requires_auth(self, client):
        """GET /api/v1/projects/{id} without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}")
        assert response.status_code == 401

    def test_get_project_not_found(self, client_with_mocked_db, mock_db_async):
        """GET /api/v1/projects/{id} with invalid ID should return 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_async.execute.return_value = mock_result

        response = client_with_mocked_db.get(f"/api/v1/projects/{uuid4()}")
        assert response.status_code == 404

    # =========================================================================
    # Delete Project
    # =========================================================================

    def test_delete_project_requires_auth(self, client):
        """DELETE /api/v1/projects/{id} without token should return 401."""
        response = client.delete(f"/api/v1/projects/{uuid4()}")
        assert response.status_code == 401

    # =========================================================================
    # Index Project
    # =========================================================================

    def test_index_project_requires_auth(self, client):
        """POST /api/v1/projects/{id}/index without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/index")
        assert response.status_code == 401

    # =========================================================================
    # Clone Project
    # =========================================================================

    def test_clone_project_requires_auth(self, client):
        """POST /api/v1/projects/{id}/clone without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/clone")
        assert response.status_code == 401

    # =========================================================================
    # Scan Project
    # =========================================================================

    def test_scan_project_requires_auth(self, client):
        """POST /api/v1/projects/{id}/scan without token should return 401."""
        response = client.post(f"/api/v1/projects/{uuid4()}/scan")
        assert response.status_code == 401

    # =========================================================================
    # Get Files
    # =========================================================================

    def test_get_files_requires_auth(self, client):
        """GET /api/v1/projects/{id}/files without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/files")
        assert response.status_code == 401

    # =========================================================================
    # Health Check
    # =========================================================================

    def test_health_check_requires_auth(self, client):
        """GET /api/v1/projects/{id}/health without token should return 401."""
        response = client.get(f"/api/v1/projects/{uuid4()}/health")
        assert response.status_code == 401
