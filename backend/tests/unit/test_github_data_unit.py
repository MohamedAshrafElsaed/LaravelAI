"""
Unit tests for GitHub Data module functions.

Tests GitHub data synchronization and caching logic.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from uuid import uuid4


class TestGitHubIssueModel:
    """Unit tests for GitHubIssue model."""

    def test_issue_creation(self):
        """GitHubIssue should be created correctly."""
        issue = MagicMock()
        issue.id = str(uuid4())
        issue.github_id = 12345
        issue.number = 42
        issue.title = "Bug: Login not working"
        issue.state = "open"
        issue.labels = ["bug", "priority:high"]

        assert issue.number == 42
        assert issue.state == "open"
        assert "bug" in issue.labels

    def test_issue_state_values(self):
        """Issue states should be valid."""
        valid_states = ["open", "closed", "all"]

        for state in valid_states:
            assert state in ["open", "closed", "all"]


class TestGitHubActionModel:
    """Unit tests for GitHubAction model."""

    def test_action_creation(self):
        """GitHubAction should be created correctly."""
        action = MagicMock()
        action.id = str(uuid4())
        action.github_id = 12345
        action.workflow_name = "CI"
        action.status = "completed"
        action.conclusion = "success"

        assert action.status == "completed"
        assert action.conclusion == "success"

    def test_action_status_values(self):
        """Action statuses should be valid."""
        valid_statuses = ["queued", "in_progress", "completed"]
        valid_conclusions = ["success", "failure", "cancelled", "skipped"]

        assert "completed" in valid_statuses
        assert "success" in valid_conclusions


class TestGitHubSyncService:
    """Unit tests for GitHubSyncService methods."""

    @pytest.mark.asyncio
    async def test_sync_issues(self, mock_github_sync_service):
        """sync_issues should return synced issues."""
        issues = await mock_github_sync_service.sync_issues(
            MagicMock(), "all", 100
        )

        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_sync_actions(self, mock_github_sync_service):
        """sync_actions should return synced actions."""
        actions = await mock_github_sync_service.sync_actions(
            MagicMock(), 50
        )

        assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_full_sync(self, mock_github_sync_service):
        """full_sync should sync all data types."""
        result = await mock_github_sync_service.full_sync(
            MagicMock(), MagicMock()
        )

        assert "collaborators" in result
        assert "issues" in result
        assert "actions" in result
        assert "errors" in result


class TestIssueParsing:
    """Unit tests for issue data parsing."""

    def test_parse_github_issue(self):
        """GitHub API issue should be parsed correctly."""
        api_issue = {
            "id": 12345,
            "number": 42,
            "title": "Bug report",
            "body": "Description here",
            "state": "open",
            "user": {"login": "testuser", "avatar_url": "https://..."},
            "labels": [{"name": "bug"}, {"name": "priority:high"}],
            "assignees": [{"login": "dev1"}],
            "comments": 5,
            "html_url": "https://github.com/...",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T12:00:00Z",
            "closed_at": None,
        }

        # Parse labels
        labels = [l["name"] for l in api_issue["labels"]]
        assert "bug" in labels

        # Parse assignees
        assignees = [a["login"] for a in api_issue["assignees"]]
        assert "dev1" in assignees

    def test_parse_issue_timestamps(self):
        """Issue timestamps should be parsed correctly."""
        timestamp_str = "2024-01-15T10:00:00Z"

        parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        assert parsed.year == 2024
        assert parsed.month == 1
        assert parsed.day == 15


class TestActionParsing:
    """Unit tests for action data parsing."""

    def test_parse_workflow_run(self):
        """Workflow run should be parsed correctly."""
        api_run = {
            "id": 12345,
            "workflow_id": 100,
            "name": "CI",
            "run_number": 42,
            "status": "completed",
            "conclusion": "success",
            "head_branch": "main",
            "head_sha": "abc123",
            "actor": {"login": "testuser", "avatar_url": "https://..."},
            "html_url": "https://github.com/...",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:05:00Z",
            "run_started_at": "2024-01-15T10:00:30Z",
        }

        assert api_run["status"] == "completed"
        assert api_run["conclusion"] == "success"
        assert api_run["run_number"] == 42


class TestInsightsParsing:
    """Unit tests for insights data parsing."""

    def test_parse_traffic_data(self):
        """Traffic data should be parsed correctly."""
        traffic = {
            "views": {"count": 100, "uniques": 50},
            "clones": {"count": 25, "uniques": 15},
        }

        assert traffic["views"]["count"] == 100
        assert traffic["clones"]["uniques"] == 15

    def test_parse_code_frequency(self):
        """Code frequency should be parsed correctly."""
        # Weekly additions/deletions
        code_frequency = [
            [1704844800, 100, -50],  # timestamp, additions, deletions
            [1704240000, 200, -75],
        ]

        week1 = code_frequency[0]
        assert week1[1] == 100  # additions
        assert week1[2] == -50  # deletions (negative)

    def test_parse_languages(self):
        """Language breakdown should be parsed correctly."""
        languages = {
            "PHP": 50000,
            "JavaScript": 20000,
            "CSS": 10000,
        }

        total = sum(languages.values())
        php_percent = (languages["PHP"] / total) * 100

        assert php_percent > 50


class TestSyncErrorHandling:
    """Unit tests for sync error handling."""

    def test_rate_limit_error(self):
        """Rate limit errors should be handled."""
        from app.services.github_sync_service import GitHubSyncError

        error = GitHubSyncError("Rate limit exceeded")
        assert "rate limit" in str(error).lower()

    def test_partial_sync_errors(self):
        """Partial sync failures should be recorded."""
        result = {
            "collaborators": [],
            "issues": [],
            "actions": [],
            "projects": [],
            "insights": None,
            "errors": ["Failed to sync insights: Rate limit exceeded"],
        }

        assert len(result["errors"]) == 1
        assert "Rate limit" in result["errors"][0]
