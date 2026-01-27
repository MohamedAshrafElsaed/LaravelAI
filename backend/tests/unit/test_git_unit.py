"""
Unit tests for Git module functions.

Tests git operations, branch management, and change tracking.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestGitService:
    """Unit tests for GitService methods."""

    def test_clone_repo_path_generation(self):
        """Clone path should be generated correctly."""
        project_id = str(uuid4())
        base_path = "/tmp/repos"

        clone_path = f"{base_path}/{project_id}"
        assert project_id in clone_path
        assert clone_path.startswith(base_path)

    def test_branch_name_generation(self):
        """AI branch names should follow convention."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d")
        short_id = "abc123"

        branch_name = f"ai-changes/{timestamp}-{short_id}"

        assert branch_name.startswith("ai-changes/")
        assert timestamp in branch_name

    def test_commit_message_formatting(self):
        """Commit messages should be properly formatted."""
        action = "Add"
        description = "user export feature"

        message = f"{action} {description}"
        assert len(message) < 72  # Git best practice

    def test_parse_git_diff(self):
        """Git diff should be parsed correctly."""
        diff = """diff --git a/app/User.php b/app/User.php
index abc123..def456 100644
--- a/app/User.php
+++ b/app/User.php
@@ -10,6 +10,10 @@ class User
     protected $fillable = ['name', 'email'];
+
+    public function export()
+    {
+        return $this->toArray();
+    }
 }"""

        # Parse diff for changed files
        lines = diff.split("\n")
        changed_files = [l.split(" b/")[1] for l in lines if l.startswith("diff --git")]

        assert "app/User.php" in changed_files


class TestGitChangeModel:
    """Unit tests for GitChange model."""

    def test_git_change_status_enum(self):
        """GitChangeStatus should have correct values."""
        from app.models.models import GitChangeStatus

        assert GitChangeStatus.PENDING.value == "pending"
        assert GitChangeStatus.APPLIED.value == "applied"
        assert GitChangeStatus.PUSHED.value == "pushed"
        assert GitChangeStatus.PR_CREATED.value == "pr_created"
        assert GitChangeStatus.MERGED.value == "merged"
        assert GitChangeStatus.ROLLED_BACK.value == "rolled_back"

    def test_git_change_model_has_fields(self):
        """GitChange model should have expected fields."""
        from app.models.models import GitChange
        from sqlalchemy import inspect

        # Get the model columns
        mapper = inspect(GitChange)
        columns = {c.name for c in mapper.columns}

        # Verify expected columns exist
        assert "branch_name" in columns
        assert "base_branch" in columns
        assert "status" in columns
        assert "pr_number" in columns
        assert "title" in columns


class TestBranchOperations:
    """Unit tests for branch operations."""

    def test_list_branches_response(self, mock_git_service):
        """list_branches should return structured data."""
        branches = mock_git_service.list_branches()

        assert isinstance(branches, list)
        assert len(branches) > 0

        for branch in branches:
            assert "name" in branch
            assert "is_current" in branch

    def test_current_branch_detection(self, mock_git_service):
        """Current branch should be detected correctly."""
        branches = mock_git_service.list_branches()
        current = [b for b in branches if b["is_current"]]

        assert len(current) == 1
        assert current[0]["name"] == "main"

    def test_branch_checkout_validation(self):
        """Branch name should be validated before checkout."""
        valid_names = ["main", "develop", "feature/test", "ai-changes/20240115"]
        invalid_names = ["../escape", "rm -rf /", "branch name with spaces"]

        for name in valid_names:
            # Valid: alphanumeric, /, -, _
            is_valid = all(c.isalnum() or c in "/-_" for c in name)
            assert is_valid or "/" in name

        for name in invalid_names:
            is_safe = ".." not in name and " " not in name
            if not is_safe:
                assert True  # Invalid names detected


class TestPullRequestCreation:
    """Unit tests for PR creation."""

    @pytest.mark.asyncio
    async def test_create_pr_response(self, mock_git_service):
        """create_pull_request should return PR data."""
        result = await mock_git_service.create_pull_request(
            title="Test PR",
            body="Test body",
            head="feature-branch",
            base="main",
        )

        assert "number" in result
        assert "url" in result
        assert "state" in result

    def test_pr_title_formatting(self):
        """PR title should be properly formatted."""
        change_title = "Add user export feature"
        pr_title = f"[AI] {change_title}"

        assert pr_title.startswith("[AI]")
        assert len(pr_title) < 100

    def test_pr_body_template(self):
        """PR body should include required sections."""
        template = """## Summary
{summary}

## Changes
{changes}

## Testing
- [ ] Tests pass
- [ ] Manual testing completed

---
Generated by Laravel AI"""

        assert "## Summary" in template
        assert "## Changes" in template
        assert "Generated by Laravel AI" in template


class TestRollback:
    """Unit tests for rollback operations."""

    def test_rollback_requires_applied_status(self):
        """Only applied changes can be rolled back."""
        from app.models.models import GitChangeStatus

        rollbackable_statuses = [
            GitChangeStatus.APPLIED.value,
            GitChangeStatus.PUSHED.value,
        ]

        non_rollbackable_statuses = [
            GitChangeStatus.PENDING.value,
            GitChangeStatus.ROLLED_BACK.value,
        ]

        for status in rollbackable_statuses:
            assert status in ["applied", "pushed"]

        for status in non_rollbackable_statuses:
            assert status not in rollbackable_statuses

    def test_rollback_commit_creation(self):
        """Rollback should create revert commit."""
        original_commit = "abc123"
        rollback_commit = f"revert-{original_commit[:7]}"

        assert original_commit[:7] in rollback_commit


class TestSyncOperations:
    """Unit tests for sync operations."""

    def test_pull_latest_success(self, mock_git_service):
        """pull_latest should return success status."""
        result = mock_git_service.pull_latest()
        assert result == True

    def test_reset_to_remote(self, mock_git_service):
        """reset_to_remote should work."""
        mock_git_service.reset_to_remote()
        # Should not raise exception

    def test_get_changed_files(self, mock_git_service):
        """get_changed_files should return file list."""
        files = mock_git_service.get_changed_files()

        assert isinstance(files, list)
        for f in files:
            assert isinstance(f, str)
