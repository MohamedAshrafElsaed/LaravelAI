"""
File Access Service - Unified file content retrieval.

Provides a single source of truth for reading file content with:
- Database-first approach (IndexedFile)
- Filesystem fallback for fresh/unindexed files
- Security validation (path traversal protection)
"""
import os
import logging
from typing import Optional
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Project, IndexedFile

logger = logging.getLogger(__name__)


class FileSource(str, Enum):
    """Source of file content."""
    DATABASE = "database"
    FILESYSTEM = "filesystem"
    NOT_FOUND = "not_found"


class PathTraversalError(Exception):
    """Attempted path traversal attack."""
    pass


class FileAccessService:
    """
    Unified service for accessing project file contents.

    Strategy:
    1. Try IndexedFile in database (fast, indexed)
    2. Fallback to filesystem if not in DB (fresh content)
    3. Security checks to prevent path traversal
    """

    def __init__(
            self,
            db: AsyncSession,
            max_file_size: int = 5 * 1024 * 1024,  # 5MB default
    ):
        self.db = db
        self.max_file_size = max_file_size

    async def get_file_content(
            self,
            project_id: str,
            file_path: str,
    ) -> Optional[str]:
        """
        Get file content with database-first, filesystem-fallback strategy.

        Args:
            project_id: The project UUID
            file_path: Relative path to the file

        Returns:
            File content string or None if not found
        """
        file_path = self._normalize_path(file_path)

        # 1. Try database first (fast)
        content = await self._get_from_database(project_id, file_path)
        if content:
            logger.debug(f"[FILE_ACCESS] {file_path} loaded from database")
            return content

        # 2. Fallback to filesystem
        content = await self._get_from_filesystem(project_id, file_path)
        if content:
            logger.info(f"[FILE_ACCESS] {file_path} loaded from filesystem (not in index)")
            return content

        logger.debug(f"[FILE_ACCESS] {file_path} not found")
        return None

    async def _get_from_database(
            self,
            project_id: str,
            file_path: str,
    ) -> Optional[str]:
        """Try to get file content from IndexedFile table."""
        try:
            stmt = select(IndexedFile).where(
                IndexedFile.project_id == project_id,
                IndexedFile.file_path == file_path,
            )
            result = await self.db.execute(stmt)
            indexed_file = result.scalar_one_or_none()

            if indexed_file and indexed_file.content:
                return indexed_file.content
        except Exception as e:
            logger.error(f"[FILE_ACCESS] Database error for {file_path}: {e}")

        return None

    async def _get_from_filesystem(
            self,
            project_id: str,
            file_path: str,
    ) -> Optional[str]:
        """Try to get file content from filesystem."""
        try:
            # Get project to find clone_path
            stmt = select(Project).where(Project.id == project_id)
            result = await self.db.execute(stmt)
            project = result.scalar_one_or_none()

            if not project or not project.clone_path:
                return None

            # Build full path
            full_path = os.path.join(project.clone_path, file_path)

            # Security check - prevent path traversal
            if not self._is_safe_path(project.clone_path, full_path):
                logger.warning(f"[FILE_ACCESS] Path traversal attempt blocked: {file_path}")
                raise PathTraversalError(f"Invalid path: {file_path}")

            # Check if file exists
            if not os.path.isfile(full_path):
                return None

            # Check file size
            file_size = os.path.getsize(full_path)
            if file_size > self.max_file_size:
                logger.warning(f"[FILE_ACCESS] File too large: {file_path} ({file_size} bytes)")
                return None

            # Read file content
            return self._read_file_safely(full_path)

        except PathTraversalError:
            raise
        except Exception as e:
            logger.error(f"[FILE_ACCESS] Filesystem error for {file_path}: {e}")
            return None

    def _is_safe_path(self, base_path: str, target_path: str) -> bool:
        """Check if target_path is safely within base_path."""
        real_base = os.path.realpath(base_path)
        real_target = os.path.realpath(target_path)
        return real_target.startswith(real_base + os.sep) or real_target == real_base

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for consistent lookups."""
        path = file_path.strip().strip('/')
        path = path.replace('\\', '/')
        return path

    def _read_file_safely(self, full_path: str) -> str:
        """Read file with encoding fallbacks."""
        encodings = ['utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(full_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        # Final fallback
        with open(full_path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')