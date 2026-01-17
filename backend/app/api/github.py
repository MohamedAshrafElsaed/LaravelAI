"""GitHub API routes - fetch user's repositories."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime

from github import Github, GithubException

from app.core.security import get_current_user, decrypt_token
from app.models.models import User

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
) -> List[GitHubRepoResponse]:
    """
    List user's GitHub repositories that are likely Laravel projects.

    Filters repositories to show only those with PHP as the primary language.
    """
    try:
        # Decrypt user's GitHub token
        github_token = decrypt_token(current_user.github_access_token)

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

    except GithubException as e:
        if e.status == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub token is invalid or expired. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {str(e)}",
        )


@router.get("/repos/{repo_id}", response_model=GitHubRepoResponse)
async def get_github_repo(
    repo_id: int,
    current_user: User = Depends(get_current_user),
) -> GitHubRepoResponse:
    """
    Get a specific GitHub repository by ID.
    """
    try:
        # Decrypt user's GitHub token
        github_token = decrypt_token(current_user.github_access_token)

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

    except GithubException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found or you don't have access.",
            )
        if e.status == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub token is invalid or expired. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error: {str(e)}",
        )
