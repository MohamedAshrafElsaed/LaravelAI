# ============================================================================
# FILE: backend/app/services/github_sync_service.py
# ============================================================================
"""
GitHub data synchronization service.

Syncs repository data from GitHub:
- Collaborators/Team members
- Issues
- Actions (workflow runs)
- Projects
- Wiki pages
- Repository insights
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from github import Github, GithubException, Repository
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Project
from app.models.team_models import Team, TeamMember, TeamRole, TeamMemberStatus
from app.models.github_models import (
    GitHubIssue, GitHubAction, GitHubProject, GitHubWikiPage, GitHubInsights
)

logger = logging.getLogger(__name__)


class GitHubSyncError(Exception):
    """GitHub sync error."""
    pass


class GitHubSyncService:
    """
    Service for synchronizing GitHub repository data.

    Handles fetching and caching:
    - Repository collaborators
    - Issues and pull requests
    - GitHub Actions workflow runs
    - GitHub Projects (classic and v2)
    - Wiki pages
    - Repository insights and statistics
    """

    def __init__(self, db: AsyncSession, github_token: str):
        self.db = db
        self.github = Github(github_token)
        self.token = github_token

    # ========== Collaborators Sync ==========

    async def sync_collaborators(
            self,
            project: Project,
            team: Team,
    ) -> List[TeamMember]:
        """
        Sync GitHub repository collaborators to team members.

        Args:
            project: Project to sync collaborators for
            team: Team to add collaborators to

        Returns:
            List of synced team members
        """
        logger.info(f"[GITHUB_SYNC] Syncing collaborators for {project.repo_full_name}")

        try:
            repo = self.github.get_repo(project.repo_full_name)
            collaborators = list(repo.get_collaborators())

            synced_members = []

            for collab in collaborators:
                try:
                    # Check if already a member
                    existing = await self._get_member_by_github_id(team.id, collab.id)

                    if existing:
                        # Update existing member info
                        existing.github_username = collab.login
                        existing.github_avatar_url = collab.avatar_url
                        synced_members.append(existing)
                    else:
                        # Add new member
                        permission = repo.get_collaborator_permission(collab)
                        role = self._map_github_permission_to_role(permission)

                        member = TeamMember(
                            id=str(uuid4()),
                            team_id=team.id,
                            github_id=collab.id,
                            github_username=collab.login,
                            github_avatar_url=collab.avatar_url,
                            role=role.value,
                            status=TeamMemberStatus.PENDING.value,
                            invited_at=datetime.utcnow(),
                        )
                        self.db.add(member)
                        synced_members.append(member)

                except GithubException as e:
                    logger.warning(f"[GITHUB_SYNC] Failed to process collaborator {collab.login}: {e}")
                    continue

            await self.db.commit()
            logger.info(f"[GITHUB_SYNC] Synced {len(synced_members)} collaborators")
            return synced_members

        except GithubException as e:
            logger.error(f"[GITHUB_SYNC] Failed to sync collaborators: {e}")
            raise GitHubSyncError(f"Failed to sync collaborators: {e}")

    async def _get_member_by_github_id(self, team_id: str, github_id: int) -> Optional[TeamMember]:
        """Get team member by GitHub ID."""
        stmt = select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.github_id == github_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _map_github_permission_to_role(self, permission: str) -> TeamRole:
        """Map GitHub permission to team role."""
        mapping = {
            "admin": TeamRole.ADMIN,
            "maintain": TeamRole.ADMIN,
            "write": TeamRole.MEMBER,
            "triage": TeamRole.MEMBER,
            "read": TeamRole.VIEWER,
        }
        return mapping.get(permission, TeamRole.VIEWER)

    # ========== Issues Sync ==========

    async def sync_issues(
            self,
            project: Project,
            state: str = "all",
            limit: int = 100,
    ) -> List[GitHubIssue]:
        """
        Sync GitHub issues for a project.

        Args:
            project: Project to sync issues for
            state: Issue state filter (open, closed, all)
            limit: Maximum issues to sync

        Returns:
            List of synced issues
        """
        logger.info(f"[GITHUB_SYNC] Syncing issues for {project.repo_full_name}")

        try:
            repo = self.github.get_repo(project.repo_full_name)
            issues = repo.get_issues(state=state, sort="updated", direction="desc")

            synced_issues = []
            count = 0

            for issue in issues:
                if count >= limit:
                    break

                # Skip pull requests (they appear in issues API)
                if issue.pull_request:
                    continue

                try:
                    # Check if issue exists
                    existing = await self._get_issue_by_github_id(issue.id)

                    issue_data = {
                        "project_id": project.id,
                        "github_id": issue.id,
                        "number": issue.number,
                        "title": issue.title,
                        "body": issue.body,
                        "state": issue.state,
                        "author_id": issue.user.id if issue.user else None,
                        "author_username": issue.user.login if issue.user else None,
                        "author_avatar_url": issue.user.avatar_url if issue.user else None,
                        "labels": [{"name": l.name, "color": l.color} for l in issue.labels],
                        "assignees": [{"login": a.login, "avatar_url": a.avatar_url} for a in issue.assignees],
                        "comments_count": issue.comments,
                        "html_url": issue.html_url,
                        "github_created_at": issue.created_at,
                        "github_updated_at": issue.updated_at,
                        "github_closed_at": issue.closed_at,
                        "synced_at": datetime.utcnow(),
                    }

                    if existing:
                        for key, value in issue_data.items():
                            setattr(existing, key, value)
                        synced_issues.append(existing)
                    else:
                        new_issue = GitHubIssue(id=str(uuid4()), **issue_data)
                        self.db.add(new_issue)
                        synced_issues.append(new_issue)

                    count += 1

                except Exception as e:
                    logger.warning(f"[GITHUB_SYNC] Failed to process issue #{issue.number}: {e}")
                    continue

            await self.db.commit()
            logger.info(f"[GITHUB_SYNC] Synced {len(synced_issues)} issues")
            return synced_issues

        except GithubException as e:
            logger.error(f"[GITHUB_SYNC] Failed to sync issues: {e}")
            raise GitHubSyncError(f"Failed to sync issues: {e}")

    async def _get_issue_by_github_id(self, github_id: int) -> Optional[GitHubIssue]:
        """Get issue by GitHub ID."""
        stmt = select(GitHubIssue).where(GitHubIssue.github_id == github_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ========== Actions Sync ==========

    async def sync_actions(
            self,
            project: Project,
            limit: int = 50,
    ) -> List[GitHubAction]:
        """
        Sync GitHub Actions workflow runs.

        Args:
            project: Project to sync actions for
            limit: Maximum runs to sync

        Returns:
            List of synced action runs
        """
        logger.info(f"[GITHUB_SYNC] Syncing actions for {project.repo_full_name}")

        try:
            repo = self.github.get_repo(project.repo_full_name)
            runs = repo.get_workflow_runs()

            synced_actions = []
            count = 0

            for run in runs:
                if count >= limit:
                    break

                try:
                    existing = await self._get_action_by_github_id(run.id)

                    action_data = {
                        "project_id": project.id,
                        "github_id": run.id,
                        "workflow_id": run.workflow_id,
                        "workflow_name": run.name or "Unknown",
                        "run_number": run.run_number,
                        "status": run.status,
                        "conclusion": run.conclusion,
                        "head_branch": run.head_branch,
                        "head_sha": run.head_sha,
                        "actor_id": run.actor.id if run.actor else None,
                        "actor_username": run.actor.login if run.actor else None,
                        "actor_avatar_url": run.actor.avatar_url if run.actor else None,
                        "html_url": run.html_url,
                        "logs_url": run.logs_url,
                        "github_created_at": run.created_at,
                        "github_updated_at": run.updated_at,
                        "run_started_at": run.run_started_at,
                        "synced_at": datetime.utcnow(),
                    }

                    if existing:
                        for key, value in action_data.items():
                            setattr(existing, key, value)
                        synced_actions.append(existing)
                    else:
                        new_action = GitHubAction(id=str(uuid4()), **action_data)
                        self.db.add(new_action)
                        synced_actions.append(new_action)

                    count += 1

                except Exception as e:
                    logger.warning(f"[GITHUB_SYNC] Failed to process run {run.id}: {e}")
                    continue

            await self.db.commit()
            logger.info(f"[GITHUB_SYNC] Synced {len(synced_actions)} action runs")
            return synced_actions

        except GithubException as e:
            logger.error(f"[GITHUB_SYNC] Failed to sync actions: {e}")
            raise GitHubSyncError(f"Failed to sync actions: {e}")

    async def _get_action_by_github_id(self, github_id: int) -> Optional[GitHubAction]:
        """Get action by GitHub ID."""
        stmt = select(GitHubAction).where(GitHubAction.github_id == github_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ========== Projects Sync ==========

    async def sync_projects(self, project: Project) -> List[GitHubProject]:
        """
        Sync GitHub Projects (classic).

        Args:
            project: Project to sync GitHub projects for

        Returns:
            List of synced GitHub projects
        """
        logger.info(f"[GITHUB_SYNC] Syncing GitHub projects for {project.repo_full_name}")

        try:
            repo = self.github.get_repo(project.repo_full_name)
            gh_projects = repo.get_projects(state="all")

            synced_projects = []

            for gh_proj in gh_projects:
                try:
                    existing = await self._get_project_by_github_id(gh_proj.id)

                    project_data = {
                        "project_id": project.id,
                        "github_id": gh_proj.id,
                        "number": gh_proj.number,
                        "title": gh_proj.name,
                        "body": gh_proj.body,
                        "state": gh_proj.state,
                        "html_url": gh_proj.html_url,
                        "items_count": gh_proj.get_columns().totalCount if hasattr(gh_proj.get_columns(),
                                                                                   'totalCount') else 0,
                        "github_created_at": gh_proj.created_at,
                        "github_updated_at": gh_proj.updated_at,
                        "synced_at": datetime.utcnow(),
                    }

                    if existing:
                        for key, value in project_data.items():
                            setattr(existing, key, value)
                        synced_projects.append(existing)
                    else:
                        new_proj = GitHubProject(id=str(uuid4()), **project_data)
                        self.db.add(new_proj)
                        synced_projects.append(new_proj)

                except Exception as e:
                    logger.warning(f"[GITHUB_SYNC] Failed to process project {gh_proj.id}: {e}")
                    continue

            await self.db.commit()
            logger.info(f"[GITHUB_SYNC] Synced {len(synced_projects)} GitHub projects")
            return synced_projects

        except GithubException as e:
            logger.error(f"[GITHUB_SYNC] Failed to sync projects: {e}")
            raise GitHubSyncError(f"Failed to sync projects: {e}")

    async def _get_project_by_github_id(self, github_id: int) -> Optional[GitHubProject]:
        """Get GitHub project by ID."""
        stmt = select(GitHubProject).where(GitHubProject.github_id == github_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ========== Wiki Sync ==========

    async def sync_wiki(self, project: Project) -> List[GitHubWikiPage]:
        """
        Sync GitHub Wiki pages.

        Note: GitHub API doesn't directly support wiki. This uses the wiki repo clone.
        For now, returns empty list - can be enhanced with git clone of wiki repo.
        """
        logger.info(f"[GITHUB_SYNC] Wiki sync requested for {project.repo_full_name}")

        # Wiki requires cloning the wiki repo (repo_name.wiki.git)
        # This is a placeholder - implement wiki clone if needed
        wiki_url = f"https://github.com/{project.repo_full_name}/wiki"

        return []

    # ========== Insights Sync ==========

    async def sync_insights(self, project: Project) -> GitHubInsights:
        """
        Sync repository insights and statistics.

        Args:
            project: Project to sync insights for

        Returns:
            GitHubInsights object
        """
        logger.info(f"[GITHUB_SYNC] Syncing insights for {project.repo_full_name}")

        try:
            repo = self.github.get_repo(project.repo_full_name)

            # Get existing or create new
            existing = await self._get_insights(project.id)

            # Fetch statistics
            insights_data = {
                "project_id": project.id,
                "stars_count": repo.stargazers_count,
                "forks_count": repo.forks_count,
                "watchers_count": repo.watchers_count,
                "open_issues_count": repo.open_issues_count,
                "synced_at": datetime.utcnow(),
            }

            # Traffic (requires push access)
            try:
                views = repo.get_views_traffic()
                insights_data["views_count"] = views.get("count", 0)
                insights_data["views_uniques"] = views.get("uniques", 0)

                clones = repo.get_clones_traffic()
                insights_data["clones_count"] = clones.get("count", 0)
                insights_data["clones_uniques"] = clones.get("uniques", 0)
            except GithubException:
                logger.debug("[GITHUB_SYNC] Traffic stats not available (requires push access)")

            # Code frequency
            try:
                code_freq = list(repo.get_stats_code_frequency())
                insights_data["code_frequency"] = [
                    {"week": cf.week.isoformat(), "additions": cf.additions, "deletions": cf.deletions}
                    for cf in code_freq[-12:]  # Last 12 weeks
                ]
            except Exception:
                logger.debug("[GITHUB_SYNC] Code frequency stats not available")

            # Commit activity
            try:
                commit_activity = list(repo.get_stats_commit_activity())
                insights_data["commit_activity"] = [
                    {"week": ca.week.isoformat(), "total": ca.total, "days": ca.days}
                    for ca in commit_activity[-12:]
                ]
            except Exception:
                logger.debug("[GITHUB_SYNC] Commit activity stats not available")

            # Top contributors
            try:
                contributors = list(repo.get_stats_contributors())
                insights_data["contributors"] = [
                    {
                        "login": c.author.login if c.author else "Unknown",
                        "avatar_url": c.author.avatar_url if c.author else None,
                        "total": c.total,
                    }
                    for c in sorted(contributors, key=lambda x: x.total, reverse=True)[:10]
                ]
            except Exception:
                logger.debug("[GITHUB_SYNC] Contributors stats not available")

            # Languages
            try:
                languages = repo.get_languages()
                total_bytes = sum(languages.values())
                insights_data["languages"] = {
                    lang: {"bytes": bytes, "percentage": round(bytes / total_bytes * 100, 2)}
                    for lang, bytes in languages.items()
                }
            except Exception:
                logger.debug("[GITHUB_SYNC] Language stats not available")

            if existing:
                for key, value in insights_data.items():
                    setattr(existing, key, value)
                await self.db.commit()
                await self.db.refresh(existing)
                return existing
            else:
                insights = GitHubInsights(id=str(uuid4()), **insights_data)
                self.db.add(insights)
                await self.db.commit()
                await self.db.refresh(insights)
                return insights

        except GithubException as e:
            logger.error(f"[GITHUB_SYNC] Failed to sync insights: {e}")
            raise GitHubSyncError(f"Failed to sync insights: {e}")

    async def _get_insights(self, project_id: str) -> Optional[GitHubInsights]:
        """Get insights for a project."""
        stmt = select(GitHubInsights).where(GitHubInsights.project_id == project_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ========== Full Sync ==========

    async def full_sync(
            self,
            project: Project,
            team: Team,
    ) -> Dict[str, Any]:
        """
        Perform a full sync of all GitHub data.

        Args:
            project: Project to sync
            team: Team associated with project

        Returns:
            Dictionary with sync results
        """
        logger.info(f"[GITHUB_SYNC] Starting full sync for {project.repo_full_name}")

        results = {
            "collaborators": [],
            "issues": [],
            "actions": [],
            "projects": [],
            "insights": None,
            "errors": [],
        }

        # Sync collaborators
        try:
            results["collaborators"] = await self.sync_collaborators(project, team)
        except Exception as e:
            results["errors"].append(f"Collaborators: {str(e)}")

        # Sync issues
        try:
            results["issues"] = await self.sync_issues(project)
        except Exception as e:
            results["errors"].append(f"Issues: {str(e)}")

        # Sync actions
        try:
            results["actions"] = await self.sync_actions(project)
        except Exception as e:
            results["errors"].append(f"Actions: {str(e)}")

        # Sync projects
        try:
            results["projects"] = await self.sync_projects(project)
        except Exception as e:
            results["errors"].append(f"Projects: {str(e)}")

        # Sync insights
        try:
            results["insights"] = await self.sync_insights(project)
        except Exception as e:
            results["errors"].append(f"Insights: {str(e)}")

        logger.info(f"[GITHUB_SYNC] Full sync completed with {len(results['errors'])} errors")
        return results