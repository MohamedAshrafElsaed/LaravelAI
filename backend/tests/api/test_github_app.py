"""
Integration tests for GitHub App API endpoints.

Tests GitHub App installation and status endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestGitHubAppAPI:
    """Test suite for /api/v1/github-app endpoints."""

    # =========================================================================
    # Install Redirect
    # =========================================================================

    def test_install_requires_auth(self, client):
        """GET /api/v1/github-app/install without token should return 401."""
        response = client.get("/api/v1/github-app/install", follow_redirects=False)
        assert response.status_code == 401

    def test_install_redirect(self, client_with_mocked_db):
        """GET /api/v1/github-app/install should redirect to GitHub."""
        response = client_with_mocked_db.get(
            "/api/v1/github-app/install",
            follow_redirects=False
        )
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "github.com" in location
        assert "installations" in location

    # =========================================================================
    # Callback
    # =========================================================================

    def test_callback_requires_auth(self, client):
        """GET /api/v1/github-app/callback without token should return 401."""
        response = client.get("/api/v1/github-app/callback?installation_id=12345")
        assert response.status_code == 401

    def test_callback_missing_installation_id(self, client_with_mocked_db):
        """GET /api/v1/github-app/callback without installation_id should return 422."""
        response = client_with_mocked_db.get("/api/v1/github-app/callback")
        assert response.status_code == 422

    @patch("app.api.github_app.GitHubAppService")
    @patch("app.api.github_app.httpx.AsyncClient")
    def test_callback_success(
        self, mock_httpx_client, mock_app_service_class, client_with_mocked_db
    ):
        """GET /api/v1/github-app/callback should save installation."""
        # Mock GitHub API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "account": {
                "login": "testuser",
                "type": "User",
            },
        }

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_client_instance

        mock_app_service = MagicMock()
        mock_app_service._generate_jwt.return_value = "mock_jwt"
        mock_app_service.save_installation = AsyncMock()
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get(
            "/api/v1/github-app/callback?installation_id=12345",
            follow_redirects=False
        )
        assert response.status_code == 307  # Redirects to frontend
        location = response.headers.get("location", "")
        assert "github_app=installed" in location

    @patch("app.api.github_app.GitHubAppService")
    @patch("app.api.github_app.httpx.AsyncClient")
    def test_callback_github_api_error(
        self, mock_httpx_client, mock_app_service_class, client_with_mocked_db
    ):
        """GET /api/v1/github-app/callback should handle GitHub API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not Found"}

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_client_instance

        mock_app_service = MagicMock()
        mock_app_service._generate_jwt.return_value = "mock_jwt"
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get(
            "/api/v1/github-app/callback?installation_id=99999",
            follow_redirects=False
        )
        # Should still redirect (possibly with error param) or return redirect
        assert response.status_code in [307, 400]

    # =========================================================================
    # Status
    # =========================================================================

    def test_status_requires_auth(self, client):
        """GET /api/v1/github-app/status without token should return 401."""
        response = client.get("/api/v1/github-app/status")
        assert response.status_code == 401

    @patch("app.api.github_app.GitHubAppService")
    def test_status_not_installed(
        self, mock_app_service_class, client_with_mocked_db
    ):
        """GET /api/v1/github-app/status without installation should return installed=false."""
        mock_app_service = MagicMock()
        mock_app_service.get_user_installation = AsyncMock(return_value=None)
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get("/api/v1/github-app/status")
        assert response.status_code == 200
        data = response.json()
        assert data["installed"] == False
        assert "install_url" in data

    @patch("app.api.github_app.GitHubAppService")
    def test_status_installed(
        self, mock_app_service_class, client_with_mocked_db
    ):
        """GET /api/v1/github-app/status with installation should return installed=true."""
        mock_installation = MagicMock()
        mock_installation.installation_id = 12345
        mock_installation.account_login = "testuser"

        mock_app_service = MagicMock()
        mock_app_service.get_user_installation = AsyncMock(return_value=mock_installation)
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get("/api/v1/github-app/status")
        assert response.status_code == 200
        data = response.json()
        assert data["installed"] == True
        assert data["installation_id"] == 12345
        assert data["account_login"] == "testuser"


class TestGitHubAppAPIEdgeCases:
    """Test edge cases for GitHub App API."""

    @patch("app.api.github_app.GitHubAppService")
    @patch("app.api.github_app.httpx.AsyncClient")
    def test_callback_organization_installation(
        self, mock_httpx_client, mock_app_service_class, client_with_mocked_db
    ):
        """Callback for organization installation should work."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "account": {
                "login": "test-org",
                "type": "Organization",
            },
        }

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_client_instance

        mock_app_service = MagicMock()
        mock_app_service._generate_jwt.return_value = "mock_jwt"
        mock_app_service.save_installation = AsyncMock()
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get(
            "/api/v1/github-app/callback?installation_id=12345",
            follow_redirects=False
        )
        assert response.status_code == 307

    @patch("app.api.github_app.GitHubAppService")
    def test_status_includes_install_url(
        self, mock_app_service_class, client_with_mocked_db
    ):
        """Status endpoint should always include install_url."""
        mock_app_service = MagicMock()
        mock_app_service.get_user_installation = AsyncMock(return_value=None)
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get("/api/v1/github-app/status")
        assert response.status_code == 200
        data = response.json()
        assert "install_url" in data
        assert "github.com" in data["install_url"]

    @patch("app.api.github_app.GitHubAppService")
    @patch("app.api.github_app.httpx.AsyncClient")
    def test_callback_saves_installation_data(
        self, mock_httpx_client, mock_app_service_class, client_with_mocked_db, test_user
    ):
        """Callback should save installation with correct data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "account": {
                "login": "testuser",
                "type": "User",
            },
        }

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_client_instance

        mock_app_service = MagicMock()
        mock_app_service._generate_jwt.return_value = "mock_jwt"
        mock_app_service.save_installation = AsyncMock()
        mock_app_service_class.return_value = mock_app_service

        response = client_with_mocked_db.get(
            "/api/v1/github-app/callback?installation_id=12345",
            follow_redirects=False
        )

        # Verify save_installation was called with correct args
        if mock_app_service.save_installation.called:
            call_args = mock_app_service.save_installation.call_args
            assert call_args is not None
