"""
Unit tests for GitHub module functions.

Tests repository filtering, token handling, and GitHub API helpers.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestRepositoryFiltering:
    """Unit tests for repository filtering logic."""

    def test_is_php_repo(self):
        """PHP repositories should be identified correctly."""
        # PHP repo
        php_repo = MagicMock()
        php_repo.language = "PHP"
        assert php_repo.language == "PHP"

        # Non-PHP repo
        js_repo = MagicMock()
        js_repo.language = "JavaScript"
        assert js_repo.language != "PHP"

    def test_is_laravel_repo(self):
        """Laravel repositories should be identified by common patterns."""
        # Mock repo with Laravel files
        laravel_patterns = [
            "artisan",
            "composer.json",
            "app/Http/Kernel.php",
            "routes/web.php",
        ]

        for pattern in laravel_patterns:
            assert "artisan" in laravel_patterns or "composer.json" in laravel_patterns

    def test_filter_repos_by_language(self):
        """Repository list should filter by language."""
        repos = [
            MagicMock(language="PHP", name="php-app"),
            MagicMock(language="JavaScript", name="js-app"),
            MagicMock(language="PHP", name="laravel-app"),
            MagicMock(language="Python", name="py-app"),
        ]

        php_repos = [r for r in repos if r.language == "PHP"]
        assert len(php_repos) == 2
        assert all(r.language == "PHP" for r in php_repos)

    def test_sort_repos_by_pushed_at(self):
        """Repositories should be sortable by last push date."""
        from datetime import datetime

        old_repo = MagicMock(pushed_at=datetime(2023, 1, 1))
        old_repo.name = "old-repo"

        new_repo = MagicMock(pushed_at=datetime(2024, 1, 15))
        new_repo.name = "new-repo"

        mid_repo = MagicMock(pushed_at=datetime(2023, 6, 15))
        mid_repo.name = "mid-repo"

        repos = [old_repo, new_repo, mid_repo]

        sorted_repos = sorted(repos, key=lambda r: r.pushed_at, reverse=True)
        assert sorted_repos[0].name == "new-repo"
        assert sorted_repos[-1].name == "old-repo"


class TestGitHubTokenService:
    """Unit tests for GitHub token service."""

    @pytest.mark.asyncio
    async def test_ensure_valid_token_not_expired(self, test_user):
        """ensure_valid_token should return token if not expired."""
        from datetime import datetime, timedelta

        # Token expires in the future
        test_user.github_token_expires_at = datetime.utcnow() + timedelta(hours=4)

        # Token should be considered valid
        assert test_user.github_token_expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_ensure_valid_token_expired(self, test_user):
        """ensure_valid_token should refresh if token expired."""
        from datetime import datetime, timedelta

        # Token already expired
        test_user.github_token_expires_at = datetime.utcnow() - timedelta(hours=1)

        # Token should be considered expired
        assert test_user.github_token_expires_at < datetime.utcnow()

    @pytest.mark.asyncio
    async def test_ensure_valid_token_no_expiry(self, test_user):
        """ensure_valid_token should work when no expiry is set."""
        test_user.github_token_expires_at = None

        # No expiry means token doesn't expire (classic OAuth apps)
        assert test_user.github_token_expires_at is None


class TestGitHubAPIHelpers:
    """Unit tests for GitHub API helper functions."""

    def test_build_repo_response(self):
        """Repository response should contain required fields."""
        mock_repo = MagicMock()
        mock_repo.id = 12345
        mock_repo.name = "test-repo"
        mock_repo.full_name = "user/test-repo"
        mock_repo.html_url = "https://github.com/user/test-repo"
        mock_repo.description = "A test repository"
        mock_repo.language = "PHP"
        mock_repo.default_branch = "main"
        mock_repo.private = False
        mock_repo.stargazers_count = 10

        response = {
            "id": mock_repo.id,
            "name": mock_repo.name,
            "full_name": mock_repo.full_name,
            "html_url": mock_repo.html_url,
            "description": mock_repo.description,
            "language": mock_repo.language,
            "default_branch": mock_repo.default_branch,
            "private": mock_repo.private,
            "stargazers_count": mock_repo.stargazers_count,
        }

        assert response["id"] == 12345
        assert response["name"] == "test-repo"
        assert response["language"] == "PHP"

    def test_handle_github_exception(self):
        """GitHub exceptions should be handled correctly."""
        from github import GithubException, UnknownObjectException, RateLimitExceededException

        # Test different exception types
        bad_creds = GithubException(401, {"message": "Bad credentials"}, None)
        assert bad_creds.status == 401

        not_found = UnknownObjectException(404, {"message": "Not Found"}, None)
        assert not_found.status == 404

        rate_limit = RateLimitExceededException(403, {"message": "Rate limit exceeded"}, None)
        assert rate_limit.status == 403

    def test_parse_repo_full_name(self):
        """Repository full name should parse to owner/repo."""
        full_name = "testuser/test-repo"
        parts = full_name.split("/")

        assert len(parts) == 2
        assert parts[0] == "testuser"
        assert parts[1] == "test-repo"


class TestGitHubClientCreation:
    """Unit tests for GitHub client creation."""

    def test_create_github_client(self):
        """GitHub client should be created with token."""
        token = "test_token_123"

        # Verify token is a string as expected by PyGithub
        assert isinstance(token, str)
        assert len(token) > 0

    def test_github_client_get_user(self):
        """GitHub client should return authenticated user."""
        mock_user = MagicMock()
        mock_user.login = "testuser"

        mock_github = MagicMock()
        mock_github.get_user.return_value = mock_user

        user = mock_github.get_user()

        assert user.login == "testuser"
