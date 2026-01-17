"""
Git service for cloning and managing repositories.
"""
import os
import shutil
from pathlib import Path
from typing import Optional, List

from git import Repo, GitCommandError
from git.exc import InvalidGitRepositoryError


# Base directory for cloned repositories
REPOS_BASE_DIR = "/tmp/repos"


class GitServiceError(Exception):
    """Custom exception for git service errors."""
    pass


class GitService:
    """Service for Git operations on repositories."""

    def __init__(self, github_token: str):
        """
        Initialize the git service.

        Args:
            github_token: GitHub personal access token for authentication
        """
        self.github_token = github_token

    def _get_clone_path(self, project_id: str) -> str:
        """
        Get the local clone path for a project.

        Args:
            project_id: The project's UUID

        Returns:
            Full path where the repo will be cloned
        """
        return os.path.join(REPOS_BASE_DIR, project_id)

    def _get_authenticated_url(self, repo_full_name: str) -> str:
        """
        Get the authenticated git URL for cloning private repos.

        Args:
            repo_full_name: The repo in owner/name format

        Returns:
            HTTPS URL with embedded token for authentication
        """
        return f"https://x-access-token:{self.github_token}@github.com/{repo_full_name}.git"

    def clone_repo(
        self,
        project_id: str,
        repo_full_name: str,
        branch: Optional[str] = None,
    ) -> str:
        """
        Clone a GitHub repository.

        Uses sparse checkout to skip large directories like node_modules and vendor.

        Args:
            project_id: The project's UUID (used for directory name)
            repo_full_name: The repo in owner/name format
            branch: The branch to checkout (defaults to default branch)

        Returns:
            Path to the cloned repository

        Raises:
            GitServiceError: If cloning fails
        """
        clone_path = self._get_clone_path(project_id)

        # Remove existing directory if it exists
        if os.path.exists(clone_path):
            shutil.rmtree(clone_path)

        # Create parent directory
        os.makedirs(os.path.dirname(clone_path), exist_ok=True)

        try:
            # Get authenticated URL
            repo_url = self._get_authenticated_url(repo_full_name)

            # Clone with limited depth for faster initial clone
            clone_args = {
                "depth": 1,  # Shallow clone
                "single_branch": True,
            }

            if branch:
                clone_args["branch"] = branch

            # Clone the repository
            repo = Repo.clone_from(repo_url, clone_path, **clone_args)

            # Configure sparse checkout to skip large directories
            self._configure_sparse_checkout(repo)

            return clone_path

        except GitCommandError as e:
            # Clean up partial clone
            if os.path.exists(clone_path):
                shutil.rmtree(clone_path, ignore_errors=True)

            error_msg = str(e)
            if "Authentication failed" in error_msg or "could not read Username" in error_msg:
                raise GitServiceError("GitHub authentication failed. Token may be invalid or expired.")
            if "Repository not found" in error_msg:
                raise GitServiceError("Repository not found. Check if you have access.")

            raise GitServiceError(f"Failed to clone repository: {error_msg}")

        except Exception as e:
            # Clean up partial clone
            if os.path.exists(clone_path):
                shutil.rmtree(clone_path, ignore_errors=True)
            raise GitServiceError(f"Unexpected error during clone: {str(e)}")

    def _configure_sparse_checkout(self, repo: Repo) -> None:
        """
        Configure sparse checkout to exclude large directories.

        This helps reduce disk usage and clone time by skipping:
        - node_modules/
        - vendor/
        - .git/ (large objects)
        - storage/
        - bootstrap/cache/

        Args:
            repo: The cloned repository object
        """
        try:
            # Enable sparse checkout
            repo.config_writer().set_value("core", "sparseCheckout", "true").release()

            # Define patterns to include (everything except excluded dirs)
            sparse_checkout_path = os.path.join(repo.git_dir, "info", "sparse-checkout")
            os.makedirs(os.path.dirname(sparse_checkout_path), exist_ok=True)

            with open(sparse_checkout_path, "w") as f:
                # Include all files
                f.write("/*\n")
                # Exclude large directories
                f.write("!node_modules/\n")
                f.write("!vendor/\n")
                f.write("!storage/\n")
                f.write("!bootstrap/cache/\n")
                f.write("!.next/\n")
                f.write("!dist/\n")
                f.write("!build/\n")

            # Apply sparse checkout
            repo.git.checkout()

        except Exception:
            # Non-fatal - repo is still usable without sparse checkout
            pass

    def pull_latest(self, clone_path: str) -> bool:
        """
        Pull latest changes from the remote repository.

        Args:
            clone_path: Path to the cloned repository

        Returns:
            True if there were changes, False if already up to date

        Raises:
            GitServiceError: If pull fails
        """
        try:
            if not os.path.exists(clone_path):
                raise GitServiceError("Repository not found at specified path.")

            repo = Repo(clone_path)

            if repo.bare:
                raise GitServiceError("Cannot pull on a bare repository.")

            # Fetch first to check for changes
            origin = repo.remotes.origin

            # Re-authenticate the remote URL
            # (token might have changed or been refreshed)
            current_url = origin.url
            if "@github.com" not in current_url:
                # URL doesn't have auth, need to update
                # This shouldn't happen normally but handle it
                pass

            # Pull changes
            fetch_info = origin.pull()

            # Check if there were actual changes
            for info in fetch_info:
                if info.flags & info.HEAD_UPTODATE:
                    return False

            return True

        except InvalidGitRepositoryError:
            raise GitServiceError("Directory is not a valid git repository.")

        except GitCommandError as e:
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                raise GitServiceError("GitHub authentication failed. Token may be invalid or expired.")
            raise GitServiceError(f"Failed to pull changes: {error_msg}")

        except Exception as e:
            raise GitServiceError(f"Unexpected error during pull: {str(e)}")

    def get_changed_files(
        self,
        clone_path: str,
        since_commit: Optional[str] = None,
    ) -> List[str]:
        """
        Get list of changed files since a specific commit.

        Args:
            clone_path: Path to the cloned repository
            since_commit: Commit hash to compare from (defaults to HEAD~1)

        Returns:
            List of changed file paths

        Raises:
            GitServiceError: If operation fails
        """
        try:
            repo = Repo(clone_path)

            if since_commit:
                diff = repo.git.diff("--name-only", since_commit, "HEAD")
            else:
                # Compare with previous commit
                diff = repo.git.diff("--name-only", "HEAD~1", "HEAD")

            if not diff:
                return []

            return [f for f in diff.split("\n") if f.strip()]

        except Exception as e:
            raise GitServiceError(f"Failed to get changed files: {str(e)}")

    def cleanup_repo(self, project_id: str) -> bool:
        """
        Remove the cloned repository from disk.

        Args:
            project_id: The project's UUID

        Returns:
            True if cleanup succeeded, False if directory didn't exist
        """
        clone_path = self._get_clone_path(project_id)

        if not os.path.exists(clone_path):
            return False

        try:
            shutil.rmtree(clone_path)
            return True
        except Exception:
            return False

    def get_file_content(
        self,
        clone_path: str,
        file_path: str,
    ) -> Optional[str]:
        """
        Read the content of a file from the cloned repository.

        Args:
            clone_path: Path to the cloned repository
            file_path: Relative path to the file within the repo

        Returns:
            File content as string, or None if file doesn't exist
        """
        full_path = os.path.join(clone_path, file_path)

        if not os.path.exists(full_path):
            return None

        if not os.path.isfile(full_path):
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return None

    def list_php_files(self, clone_path: str) -> List[str]:
        """
        List all PHP files in the repository.

        Args:
            clone_path: Path to the cloned repository

        Returns:
            List of relative paths to PHP files
        """
        php_files = []
        base_path = Path(clone_path)

        # Directories to skip
        skip_dirs = {
            "node_modules", "vendor", "storage", "bootstrap",
            ".git", ".next", "dist", "build", "tests", "test"
        }

        for root, dirs, files in os.walk(clone_path):
            # Filter out directories to skip
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                if file.endswith(".php"):
                    full_path = Path(root) / file
                    relative_path = full_path.relative_to(base_path)
                    php_files.append(str(relative_path))

        return php_files
