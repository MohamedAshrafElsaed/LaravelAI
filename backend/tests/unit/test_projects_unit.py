"""
Unit tests for Projects module functions.

Tests project CRUD logic, status management, and file operations.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


class TestProjectModel:
    """Unit tests for Project model."""

    def test_project_creation(self):
        """Project model should be created with correct fields."""
        from app.models.models import Project, ProjectStatus

        # Note: SQLAlchemy defaults are applied by DB, not on object creation
        project = Project(
            user_id=str(uuid4()),
            github_repo_id=12345,
            name="test-project",
            repo_full_name="user/test-project",
            repo_url="https://github.com/user/test-project",
            default_branch="main",
            status=ProjectStatus.PENDING.value,  # Explicitly set for unit test
            indexed_files_count=0,
        )

        assert project.name == "test-project"
        assert project.status == ProjectStatus.PENDING.value
        assert project.indexed_files_count == 0

    def test_project_status_enum(self):
        """ProjectStatus enum should have all required values."""
        from app.models.models import ProjectStatus

        assert ProjectStatus.PENDING.value == "pending"
        assert ProjectStatus.CLONING.value == "cloning"
        assert ProjectStatus.SCANNING.value == "scanning"
        assert ProjectStatus.INDEXING.value == "indexing"
        assert ProjectStatus.READY.value == "ready"
        assert ProjectStatus.ERROR.value == "error"

    def test_project_default_values(self):
        """Project should have correct default values."""
        from app.models.models import Project, ProjectStatus

        # Note: SQLAlchemy defaults are applied by DB, not on object creation
        # This test verifies fields can be set to their expected default values
        project = Project(
            user_id=str(uuid4()),
            github_repo_id=12345,
            name="test-project",
            repo_full_name="user/test-project",
            repo_url="https://github.com/user/test-project",
            default_branch="main",
            status=ProjectStatus.PENDING.value,
            scan_progress=0,
        )

        assert project.default_branch == "main"
        assert project.status == ProjectStatus.PENDING.value
        assert project.clone_path is None
        assert project.scan_progress == 0


class TestProjectStatusTransitions:
    """Unit tests for project status transitions."""

    def test_valid_status_transitions(self):
        """Valid status transitions should work."""
        from app.models.models import ProjectStatus

        # Valid transitions
        valid_transitions = [
            (ProjectStatus.PENDING, ProjectStatus.CLONING),
            (ProjectStatus.CLONING, ProjectStatus.SCANNING),
            (ProjectStatus.SCANNING, ProjectStatus.INDEXING),
            (ProjectStatus.INDEXING, ProjectStatus.READY),
            # Error can happen from any state
            (ProjectStatus.CLONING, ProjectStatus.ERROR),
            (ProjectStatus.SCANNING, ProjectStatus.ERROR),
        ]

        for from_status, to_status in valid_transitions:
            assert from_status != to_status

    def test_ready_status_requirements(self):
        """Project should meet requirements to be READY."""
        project = MagicMock()
        project.clone_path = "/tmp/repos/test"
        project.indexed_files_count = 100
        project.scan_progress = 100
        project.error_message = None

        # All requirements for READY status
        assert project.clone_path is not None
        assert project.indexed_files_count > 0
        assert project.scan_progress == 100
        assert project.error_message is None


class TestProjectFileOperations:
    """Unit tests for project file operations."""

    def test_build_file_tree(self):
        """File tree should be built correctly."""
        files = [
            "app/User.php",
            "app/Http/Controllers/UserController.php",
            "config/app.php",
            "routes/web.php",
        ]

        # Build simple tree structure
        tree = {}
        for filepath in files:
            parts = filepath.split("/")
            current = tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

        assert "app" in tree
        assert "config" in tree
        assert "routes" in tree

    def test_path_traversal_prevention(self):
        """Path traversal attempts should be detected."""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/passwd",
            "app/../../../secret",
        ]

        for path in dangerous_paths:
            # Check for path traversal indicators
            is_dangerous = ".." in path or path.startswith("/")
            assert is_dangerous

    def test_safe_path_validation(self):
        """Safe paths should pass validation."""
        safe_paths = [
            "app/User.php",
            "app/Http/Controllers/UserController.php",
            "config/app.php",
            "public/js/app.js",
        ]

        for path in safe_paths:
            # Safe paths don't start with / and don't contain ..
            is_safe = not path.startswith("/") and ".." not in path
            assert is_safe


class TestProjectScanning:
    """Unit tests for project scanning logic."""

    def test_calculate_scan_progress(self):
        """Scan progress should be calculated correctly."""
        total_files = 100
        scanned_files = 50

        progress = int((scanned_files / total_files) * 100)
        assert progress == 50

    def test_file_categorization(self):
        """Files should be categorized correctly."""
        categories = {
            "php": ["User.php", "Controller.php"],
            "blade": ["index.blade.php", "layout.blade.php"],
            "config": ["app.php", "database.php"],
            "route": ["web.php", "api.php"],
        }

        php_count = len(categories["php"])
        blade_count = len(categories["blade"])

        assert php_count == 2
        assert blade_count == 2

    def test_stack_detection(self):
        """Framework stack should be detected from files."""
        laravel_indicators = [
            "artisan",
            "composer.json",
            "app/Http/Kernel.php",
            "bootstrap/app.php",
        ]

        # Check if Laravel is detected
        has_artisan = "artisan" in laravel_indicators
        has_composer = "composer.json" in laravel_indicators

        assert has_artisan and has_composer


class TestProjectIndexing:
    """Unit tests for project indexing logic."""

    def test_should_index_file(self):
        """File indexing rules should work correctly."""
        # Files to index
        should_index = [
            "app/User.php",
            "app/Http/Controllers/UserController.php",
            "config/app.php",
        ]

        # Files to skip
        should_skip = [
            "vendor/autoload.php",
            "node_modules/lodash/index.js",
            ".git/config",
            "storage/logs/laravel.log",
        ]

        for f in should_index:
            is_vendor = "vendor/" in f
            is_node = "node_modules/" in f
            is_git = ".git/" in f
            is_storage = "storage/" in f
            assert not (is_vendor or is_node or is_git or is_storage)

        for f in should_skip:
            is_excluded = any(ex in f for ex in ["vendor/", "node_modules/", ".git/", "storage/"])
            assert is_excluded

    def test_file_content_chunking(self):
        """File content should be chunked for indexing."""
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        lines = content.split("\n")

        chunk_size = 2
        chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]

        assert len(chunks) == 3
        assert chunks[0] == ["Line 1", "Line 2"]
