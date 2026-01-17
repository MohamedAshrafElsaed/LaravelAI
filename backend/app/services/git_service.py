"""
Git service for cloning and managing repositories.
"""
import os
import shutil
import logging
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from git import Repo, GitCommandError
from git.exc import InvalidGitRepositoryError

logger = logging.getLogger(__name__)

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
        logger.info(f"[GIT] Starting clone for {repo_full_name}, project_id={project_id}, branch={branch}")
        clone_path = self._get_clone_path(project_id)
        logger.debug(f"[GIT] Clone path: {clone_path}")

        # Remove existing directory if it exists
        if os.path.exists(clone_path):
            logger.info(f"[GIT] Removing existing directory: {clone_path}")
            shutil.rmtree(clone_path)

        # Create parent directory
        logger.debug(f"[GIT] Creating parent directory for clone")
        os.makedirs(os.path.dirname(clone_path), exist_ok=True)

        try:
            # Get authenticated URL
            repo_url = self._get_authenticated_url(repo_full_name)
            logger.debug(f"[GIT] Using authenticated URL for cloning")

            # Clone with limited depth for faster initial clone
            clone_args = {
                "depth": 1,  # Shallow clone
                "single_branch": True,
            }

            if branch:
                clone_args["branch"] = branch

            # Clone the repository
            logger.info(f"[GIT] Executing git clone (shallow, single-branch)")
            repo = Repo.clone_from(repo_url, clone_path, **clone_args)
            logger.info(f"[GIT] Clone successful, configuring sparse checkout")

            # Configure sparse checkout to skip large directories
            self._configure_sparse_checkout(repo)
            logger.info(f"[GIT] Clone completed successfully at {clone_path}")

            return clone_path

        except GitCommandError as e:
            logger.error(f"[GIT] GitCommandError during clone: {str(e)}")
            # Clean up partial clone
            if os.path.exists(clone_path):
                logger.debug(f"[GIT] Cleaning up partial clone at {clone_path}")
                shutil.rmtree(clone_path, ignore_errors=True)

            error_msg = str(e)
            if "Authentication failed" in error_msg or "could not read Username" in error_msg:
                logger.error(f"[GIT] Authentication failed for {repo_full_name}")
                raise GitServiceError("GitHub authentication failed. Token may be invalid or expired.")
            if "Repository not found" in error_msg:
                logger.error(f"[GIT] Repository not found: {repo_full_name}")
                raise GitServiceError("Repository not found. Check if you have access.")

            raise GitServiceError(f"Failed to clone repository: {error_msg}")

        except Exception as e:
            logger.exception(f"[GIT] Unexpected error during clone: {str(e)}")
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
        logger.debug(f"[GIT] Configuring sparse checkout")
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
            logger.debug(f"[GIT] Sparse checkout configured successfully")

        except Exception as e:
            # Non-fatal - repo is still usable without sparse checkout
            logger.warning(f"[GIT] Failed to configure sparse checkout: {str(e)}")

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
        logger.info(f"[GIT] Pulling latest changes for {clone_path}")
        try:
            if not os.path.exists(clone_path):
                logger.error(f"[GIT] Repository not found at {clone_path}")
                raise GitServiceError("Repository not found at specified path.")

            repo = Repo(clone_path)

            if repo.bare:
                logger.error(f"[GIT] Cannot pull on bare repository: {clone_path}")
                raise GitServiceError("Cannot pull on a bare repository.")

            # Fetch first to check for changes
            origin = repo.remotes.origin

            # Re-authenticate the remote URL
            # (token might have changed or been refreshed)
            current_url = origin.url
            if "@github.com" not in current_url:
                # URL doesn't have auth, need to update
                # This shouldn't happen normally but handle it
                logger.warning(f"[GIT] Remote URL missing authentication")

            # Pull changes
            logger.debug(f"[GIT] Executing git pull")
            fetch_info = origin.pull()

            # Check if there were actual changes
            for info in fetch_info:
                if info.flags & info.HEAD_UPTODATE:
                    logger.info(f"[GIT] Repository already up to date")
                    return False

            logger.info(f"[GIT] Pulled new changes successfully")
            return True

        except InvalidGitRepositoryError:
            logger.error(f"[GIT] Invalid git repository: {clone_path}")
            raise GitServiceError("Directory is not a valid git repository.")

        except GitCommandError as e:
            logger.error(f"[GIT] GitCommandError during pull: {str(e)}")
            error_msg = str(e)
            if "Authentication failed" in error_msg:
                raise GitServiceError("GitHub authentication failed. Token may be invalid or expired.")
            raise GitServiceError(f"Failed to pull changes: {error_msg}")

        except Exception as e:
            logger.exception(f"[GIT] Unexpected error during pull: {str(e)}")
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
        logger.info(f"[GIT] Getting changed files for {clone_path}, since_commit={since_commit}")
        try:
            repo = Repo(clone_path)

            if since_commit:
                diff = repo.git.diff("--name-only", since_commit, "HEAD")
            else:
                # Compare with previous commit
                diff = repo.git.diff("--name-only", "HEAD~1", "HEAD")

            if not diff:
                logger.info(f"[GIT] No changed files found")
                return []

            changed = [f for f in diff.split("\n") if f.strip()]
            logger.info(f"[GIT] Found {len(changed)} changed files")
            return changed

        except Exception as e:
            logger.error(f"[GIT] Failed to get changed files: {str(e)}")
            raise GitServiceError(f"Failed to get changed files: {str(e)}")

    def cleanup_repo(self, project_id: str) -> bool:
        """
        Remove the cloned repository from disk.

        Args:
            project_id: The project's UUID

        Returns:
            True if cleanup succeeded, False if directory didn't exist
        """
        logger.info(f"[GIT] Cleaning up repository for project_id={project_id}")
        clone_path = self._get_clone_path(project_id)

        if not os.path.exists(clone_path):
            logger.info(f"[GIT] Repository directory does not exist: {clone_path}")
            return False

        try:
            shutil.rmtree(clone_path)
            logger.info(f"[GIT] Repository cleaned up successfully: {clone_path}")
            return True
        except Exception as e:
            logger.error(f"[GIT] Failed to cleanup repository: {str(e)}")
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
        logger.debug(f"[GIT] Reading file content: {full_path}")

        if not os.path.exists(full_path):
            logger.debug(f"[GIT] File does not exist: {full_path}")
            return None

        if not os.path.isfile(full_path):
            logger.debug(f"[GIT] Path is not a file: {full_path}")
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                logger.debug(f"[GIT] Read {len(content)} bytes from {file_path}")
                return content
        except Exception as e:
            logger.error(f"[GIT] Failed to read file {file_path}: {str(e)}")
            return None

    def list_php_files(self, clone_path: str) -> List[str]:
        """
        List all PHP files in the repository.

        Args:
            clone_path: Path to the cloned repository

        Returns:
            List of relative paths to PHP files
        """
        logger.info(f"[GIT] Listing PHP files in {clone_path}")
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

        logger.info(f"[GIT] Found {len(php_files)} PHP files")
        return php_files

    def list_branches(self, clone_path: str) -> List[Dict[str, Any]]:
        """
        List all branches in the repository.

        Args:
            clone_path: Path to the cloned repository

        Returns:
            List of branch info dictionaries
        """
        logger.info(f"[GIT] Listing branches for {clone_path}")
        try:
            repo = Repo(clone_path)
            branches = []

            # Local branches
            for branch in repo.branches:
                branches.append({
                    "name": branch.name,
                    "is_current": branch == repo.active_branch,
                    "commit": branch.commit.hexsha[:8],
                    "message": branch.commit.message.split("\n")[0][:80],
                    "author": branch.commit.author.name,
                    "date": branch.commit.committed_datetime.isoformat(),
                })

            # Remote branches (if fetched)
            for ref in repo.remotes.origin.refs:
                name = ref.remote_head
                if name != "HEAD" and not any(b["name"] == name for b in branches):
                    branches.append({
                        "name": name,
                        "is_current": False,
                        "is_remote": True,
                        "commit": ref.commit.hexsha[:8],
                        "message": ref.commit.message.split("\n")[0][:80],
                        "author": ref.commit.author.name,
                        "date": ref.commit.committed_datetime.isoformat(),
                    })

            logger.info(f"[GIT] Found {len(branches)} branches")
            return branches

        except Exception as e:
            logger.error(f"[GIT] Failed to list branches: {str(e)}")
            raise GitServiceError(f"Failed to list branches: {str(e)}")

    def get_current_branch(self, clone_path: str) -> str:
        """
        Get the current branch name.

        Args:
            clone_path: Path to the cloned repository

        Returns:
            Current branch name
        """
        try:
            repo = Repo(clone_path)
            return repo.active_branch.name
        except Exception as e:
            logger.error(f"[GIT] Failed to get current branch: {str(e)}")
            raise GitServiceError(f"Failed to get current branch: {str(e)}")

    def create_branch(
        self,
        clone_path: str,
        branch_name: str,
        from_branch: Optional[str] = None,
    ) -> str:
        """
        Create a new branch.

        Args:
            clone_path: Path to the cloned repository
            branch_name: Name for the new branch
            from_branch: Branch to create from (defaults to current branch)

        Returns:
            Name of the created branch

        Raises:
            GitServiceError: If branch creation fails
        """
        logger.info(f"[GIT] Creating branch '{branch_name}' in {clone_path}")
        try:
            repo = Repo(clone_path)

            # If from_branch specified, checkout to it first
            if from_branch:
                logger.debug(f"[GIT] Checking out to base branch: {from_branch}")
                repo.git.checkout(from_branch)

            # Create and checkout new branch
            logger.debug(f"[GIT] Creating new branch: {branch_name}")
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()

            logger.info(f"[GIT] Branch '{branch_name}' created and checked out")
            return branch_name

        except GitCommandError as e:
            logger.error(f"[GIT] GitCommandError creating branch: {str(e)}")
            if "already exists" in str(e):
                raise GitServiceError(f"Branch '{branch_name}' already exists.")
            raise GitServiceError(f"Failed to create branch: {str(e)}")

        except Exception as e:
            logger.exception(f"[GIT] Unexpected error creating branch: {str(e)}")
            raise GitServiceError(f"Failed to create branch: {str(e)}")

    def checkout_branch(self, clone_path: str, branch_name: str) -> None:
        """
        Checkout an existing branch.

        Args:
            clone_path: Path to the cloned repository
            branch_name: Name of the branch to checkout
        """
        logger.info(f"[GIT] Checking out branch '{branch_name}' in {clone_path}")
        try:
            repo = Repo(clone_path)

            # Check if branch exists locally
            if branch_name in [b.name for b in repo.branches]:
                repo.git.checkout(branch_name)
            else:
                # Try to checkout from remote
                repo.git.checkout("-b", branch_name, f"origin/{branch_name}")

            logger.info(f"[GIT] Checked out branch '{branch_name}'")

        except GitCommandError as e:
            logger.error(f"[GIT] Failed to checkout branch: {str(e)}")
            raise GitServiceError(f"Failed to checkout branch '{branch_name}': {str(e)}")

    def apply_changes(
        self,
        clone_path: str,
        changes: List[Dict[str, Any]],
        commit_message: str,
        author_name: str = "Laravel AI",
        author_email: str = "ai@laravelai.dev",
    ) -> str:
        """
        Apply file changes and create a commit.

        Args:
            clone_path: Path to the cloned repository
            changes: List of changes to apply, each with:
                - file: file path relative to repo root
                - action: 'create', 'modify', or 'delete'
                - content: new file content (for create/modify)
            commit_message: Message for the commit
            author_name: Name for commit author
            author_email: Email for commit author

        Returns:
            The commit hash

        Raises:
            GitServiceError: If applying changes fails
        """
        logger.info(f"[GIT] Applying {len(changes)} changes to {clone_path}")
        try:
            repo = Repo(clone_path)

            # Configure git user
            with repo.config_writer() as config:
                config.set_value("user", "name", author_name)
                config.set_value("user", "email", author_email)

            # Apply each change
            files_to_add = []
            files_to_remove = []

            for change in changes:
                file_path = change.get("file")
                action = change.get("action", "modify")
                content = change.get("content", "")
                full_path = os.path.join(clone_path, file_path)

                logger.debug(f"[GIT] Applying {action} to {file_path}")

                if action in ["create", "modify"]:
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)

                    # Write file content
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    files_to_add.append(file_path)
                    logger.debug(f"[GIT] Wrote {len(content)} bytes to {file_path}")

                elif action == "delete":
                    if os.path.exists(full_path):
                        os.remove(full_path)
                        files_to_remove.append(file_path)
                        logger.debug(f"[GIT] Deleted {file_path}")

            # Stage changes using git commands directly (avoids GitPython index format issues)
            if files_to_add:
                repo.git.add(files_to_add)
            if files_to_remove:
                repo.git.rm(files_to_remove)

            # Create commit using git command directly
            repo.git.commit("-m", commit_message)
            commit = repo.head.commit
            logger.info(f"[GIT] Created commit {commit.hexsha[:8]}: {commit_message[:50]}")

            return commit.hexsha

        except Exception as e:
            logger.exception(f"[GIT] Failed to apply changes: {str(e)}")
            raise GitServiceError(f"Failed to apply changes: {str(e)}")

    def push_branch(
        self,
        clone_path: str,
        branch_name: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """
        Push a branch to the remote repository.

        Args:
            clone_path: Path to the cloned repository
            branch_name: Branch to push (defaults to current branch)
            force: Force push if needed

        Returns:
            True if push succeeded

        Raises:
            GitServiceError: If push fails
        """
        logger.info(f"[GIT] Pushing branch to remote from {clone_path}")
        try:
            repo = Repo(clone_path)
            origin = repo.remotes.origin

            if branch_name is None:
                branch_name = repo.active_branch.name

            # Push the branch
            push_args = ["-u", "origin", branch_name]
            if force:
                push_args.insert(0, "--force")

            logger.debug(f"[GIT] Executing push: {' '.join(push_args)}")
            result = repo.git.push(*push_args)

            logger.info(f"[GIT] Push completed successfully")
            return True

        except GitCommandError as e:
            logger.error(f"[GIT] Push failed: {str(e)}")
            if "Authentication failed" in str(e):
                raise GitServiceError("GitHub authentication failed. Token may be invalid.")
            if "rejected" in str(e) and not force:
                raise GitServiceError("Push rejected. Remote has newer changes. Consider force push.")
            raise GitServiceError(f"Failed to push branch: {str(e)}")

        except Exception as e:
            logger.exception(f"[GIT] Unexpected error during push: {str(e)}")
            raise GitServiceError(f"Failed to push branch: {str(e)}")

    def get_diff(
        self,
        clone_path: str,
        base_branch: Optional[str] = None,
    ) -> str:
        """
        Get the diff between current branch and base branch.

        Args:
            clone_path: Path to the cloned repository
            base_branch: Branch to compare against (defaults to main/master)

        Returns:
            Unified diff string
        """
        logger.info(f"[GIT] Getting diff for {clone_path}")
        try:
            repo = Repo(clone_path)

            if base_branch is None:
                # Try main, then master
                base_branch = "main"
                if "master" in [b.name for b in repo.branches]:
                    base_branch = "master"

            diff = repo.git.diff(f"{base_branch}...HEAD")
            return diff

        except Exception as e:
            logger.error(f"[GIT] Failed to get diff: {str(e)}")
            return ""

    async def create_pull_request(
        self,
        repo_full_name: str,
        branch_name: str,
        base_branch: str,
        title: str,
        description: str,
        files_changed: List[str],
        ai_summary: str,
    ) -> Dict[str, Any]:
        """
        Create a pull request via GitHub API.

        Args:
            repo_full_name: Repository in owner/repo format
            branch_name: Source branch for the PR
            base_branch: Target branch (usually main/master)
            title: PR title
            description: PR description
            files_changed: List of files modified
            ai_summary: AI-generated summary of changes

        Returns:
            PR data including URL, number, etc.

        Raises:
            GitServiceError: If PR creation fails
        """
        logger.info(f"[GIT] Creating PR for {repo_full_name}: {branch_name} -> {base_branch}")

        # Build PR body
        body = f"""{description}

---

## AI-Generated Summary

{ai_summary}

## Files Changed

{chr(10).join(f'- `{f}`' for f in files_changed)}

---
*This PR was created by Laravel AI*
"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.github.com/repos/{repo_full_name}/pulls",
                    headers={
                        "Authorization": f"token {self.github_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    json={
                        "title": title,
                        "body": body,
                        "head": branch_name,
                        "base": base_branch,
                    },
                    timeout=30.0,
                )

                if response.status_code == 201:
                    pr_data = response.json()
                    logger.info(f"[GIT] PR created successfully: #{pr_data['number']}")
                    return {
                        "number": pr_data["number"],
                        "url": pr_data["html_url"],
                        "api_url": pr_data["url"],
                        "state": pr_data["state"],
                        "title": pr_data["title"],
                        "created_at": pr_data["created_at"],
                    }

                elif response.status_code == 422:
                    # Validation error - might be PR already exists
                    error_data = response.json()
                    errors = error_data.get("errors", [])
                    for error in errors:
                        if "pull request already exists" in error.get("message", "").lower():
                            raise GitServiceError("A pull request for this branch already exists.")
                    raise GitServiceError(f"GitHub validation error: {error_data}")

                elif response.status_code == 401:
                    raise GitServiceError("GitHub authentication failed. Token may be invalid.")

                elif response.status_code == 404:
                    raise GitServiceError("Repository not found or no access.")

                else:
                    error_text = response.text
                    logger.error(f"[GIT] GitHub API error {response.status_code}: {error_text}")
                    raise GitServiceError(f"GitHub API error: {error_text}")

        except httpx.RequestError as e:
            logger.error(f"[GIT] HTTP error creating PR: {str(e)}")
            raise GitServiceError(f"Failed to connect to GitHub: {str(e)}")

        except GitServiceError:
            raise

        except Exception as e:
            logger.exception(f"[GIT] Unexpected error creating PR: {str(e)}")
            raise GitServiceError(f"Failed to create pull request: {str(e)}")

    def reset_to_remote(self, clone_path: str, branch_name: Optional[str] = None) -> None:
        """
        Reset local branch to match remote.

        Args:
            clone_path: Path to the cloned repository
            branch_name: Branch to reset (defaults to current)
        """
        logger.info(f"[GIT] Resetting to remote for {clone_path}")
        try:
            repo = Repo(clone_path)

            if branch_name is None:
                branch_name = repo.active_branch.name

            # Fetch latest
            repo.remotes.origin.fetch()

            # Hard reset to remote
            repo.git.reset("--hard", f"origin/{branch_name}")
            logger.info(f"[GIT] Reset to origin/{branch_name} successful")

        except Exception as e:
            logger.error(f"[GIT] Failed to reset: {str(e)}")
            raise GitServiceError(f"Failed to reset to remote: {str(e)}")
