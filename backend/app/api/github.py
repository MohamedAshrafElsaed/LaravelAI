"""GitHub API routes - fetch user's repositories."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from github import Github, GithubException

from app.core.database import get_db
from app.core.security import get_current_user, decrypt_token
from app.models.models import User
from app.services.github_token_service import (
    ensure_valid_token,
    handle_auth_failure,
    TokenInvalidError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class GitHubRepoResponse(BaseModel):
    """GitHub repository response model."""
    id: int
    name: str
    full_name: str
    default_branch: str
    private: bool
    updated_at: datetime
    html_url: str
    description: Optional[str] = None
    language: Optional[str] = None


@router.get("/repos", response_model=List[GitHubRepoResponse])
async def list_github_repos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GitHubRepoResponse]:
    """
    List user's GitHub repositories that are likely Laravel projects.

    Filters repositories to show only those with PHP as the primary language.
    Automatically refreshes the GitHub token if it has expired.
    """
    try:
        # Get valid token with auto-refresh
        github_token = await ensure_valid_token(current_user, db)

        # Create GitHub client
        g = Github(github_token)
        user = g.get_user()

        # Get all repositories the user has access to
        repos = []
        for repo in user.get_repos(sort="updated", direction="desc"):
            # Filter to only show PHP repositories (likely Laravel)
            # Also include repos without detected language (could still be PHP)
            if repo.language == "PHP" or repo.language is None:
                repos.append(GitHubRepoResponse(
                    id=repo.id,
                    name=repo.name,
                    full_name=repo.full_name,
                    default_branch=repo.default_branch or "main",
                    private=repo.private,
                    updated_at=repo.updated_at,
                    html_url=repo.html_url,
                    description=repo.description,
                    language=repo.language,
                ))

            # Limit to 100 repos to avoid slow responses
            if len(repos) >= 100:
                break

        return repos

    except TokenInvalidError as e:
        logger.error(f"[GITHUB API] Token invalid for user {current_user.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"X-Token-Refresh-Required": "true"},
        )

    except GithubException as e:
        if e.status == 401:
            # Try token refresh
            logger.warning(f"[GITHUB API] Auth failure listing repos, attempting token refresh")
            new_token = await handle_auth_failure(current_user, db)
            if new_token:
                try:
                    g = Github(new_token)
                    user = g.get_user()
                    repos = []
                    for repo in user.get_repos(sort="updated", direction="desc"):
                        if repo.language == "PHP" or repo.language is None:
                            repos.append(GitHubRepoResponse(
                                id=repo.id,
                                name=repo.name,
                                full_name=repo.full_name,
                                default_branch=repo.default_branch or "main",
                                private=repo.private,
                                updated_at=repo.updated_at,
                                html_url=repo.html_url,
                                description=repo.description,
                                language=repo.language,
                            ))
                        if len(repos) >= 100:
                            break
                    return repos
                except GithubException:
                    pass
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub token is invalid or expired. Please re-authenticate.",
                headers={"X-Token-Refresh-Required": "true"},
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {str(e)}",
        )


@router.get("/repos/{repo_id}", response_model=GitHubRepoResponse)
async def get_github_repo(
    repo_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GitHubRepoResponse:
    """
    Get a specific GitHub repository by ID.
    Automatically refreshes the GitHub token if it has expired.
    """
    try:
        # Get valid token with auto-refresh
        github_token = await ensure_valid_token(current_user, db)

        # Create GitHub client
        g = Github(github_token)
        repo = g.get_repo(repo_id)

        return GitHubRepoResponse(
            id=repo.id,
            name=repo.name,
            full_name=repo.full_name,
            default_branch=repo.default_branch or "main",
            private=repo.private,
            updated_at=repo.updated_at,
            html_url=repo.html_url,
            description=repo.description,
            language=repo.language,
        )

    except TokenInvalidError as e:
        logger.error(f"[GITHUB API] Token invalid for user {current_user.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"X-Token-Refresh-Required": "true"},
        )

    except GithubException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found or you don't have access.",
            )
        if e.status == 401:
            # Try token refresh
            logger.warning(f"[GITHUB API] Auth failure getting repo, attempting token refresh")
            new_token = await handle_auth_failure(current_user, db)
            if new_token:
                try:
                    g = Github(new_token)
                    repo = g.get_repo(repo_id)
                    return GitHubRepoResponse(
                        id=repo.id,
                        name=repo.name,
                        full_name=repo.full_name,
                        default_branch=repo.default_branch or "main",
                        private=repo.private,
                        updated_at=repo.updated_at,
                        html_url=repo.html_url,
                        description=repo.description,
                        language=repo.language,
                    )
                except GithubException:
                    pass
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub token is invalid or expired. Please re-authenticate.",
                headers={"X-Token-Refresh-Required": "true"},
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {str(e)}",
        )
