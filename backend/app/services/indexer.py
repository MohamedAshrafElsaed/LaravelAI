"""
Indexer service for orchestrating project indexing.
Coordinates scanning, parsing, chunking, embedding, and storage.
"""
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Project, ProjectStatus, IndexedFile
from app.services.scanner import LaravelScanner, ScannerError, FileInfo
from app.services.parsers.php_parser import PHPParser
from app.services.parsers.blade_parser import BladeParser
from app.services.chunker import Chunker, chunk_file
from app.services.embeddings import EmbeddingService, EmbeddingProvider, EmbeddingError
from app.services.vector_store import VectorStore, VectorStoreError


logger = logging.getLogger(__name__)


class IndexingPhase(str, Enum):
    """Phases of the indexing process."""
    SCANNING = "scanning"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class IndexingProgress:
    """Tracks the progress of an indexing operation."""
    project_id: str
    phase: IndexingPhase = IndexingPhase.SCANNING
    progress: int = 0  # 0-100
    current_file: Optional[str] = None
    total_files: int = 0
    processed_files: int = 0
    total_chunks: int = 0
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "phase": self.phase.value,
            "progress": self.progress,
            "current_file": self.current_file,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "total_chunks": self.total_chunks,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class IndexingError(Exception):
    """Custom exception for indexing errors."""
    pass


# Global progress tracker
_indexing_progress: Dict[str, IndexingProgress] = {}


def get_indexing_progress(project_id: str) -> Optional[IndexingProgress]:
    """Get the current indexing progress for a project."""
    return _indexing_progress.get(project_id)


def set_indexing_progress(progress: IndexingProgress) -> None:
    """Update the indexing progress for a project."""
    _indexing_progress[progress.project_id] = progress


def clear_indexing_progress(project_id: str) -> None:
    """Clear the indexing progress for a project."""
    _indexing_progress.pop(project_id, None)


class ProjectIndexer:
    """Service for indexing Laravel project codebases."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
        embedding_model: Optional[str] = None,
        max_chunk_tokens: int = 500,
    ):
        """
        Initialize the indexer.

        Args:
            db: Database session
            embedding_provider: Provider for embeddings
            embedding_model: Model for embeddings (optional)
            max_chunk_tokens: Maximum tokens per chunk
        """
        self.db = db
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.max_chunk_tokens = max_chunk_tokens

        # Initialize services
        self.php_parser = PHPParser()
        self.blade_parser = BladeParser()
        self.chunker = Chunker(max_tokens=max_chunk_tokens)
        self.embedding_service: Optional[EmbeddingService] = None
        self.vector_store: Optional[VectorStore] = None

    async def _init_services(self) -> None:
        """Initialize external services (embeddings, vector store)."""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService(
                provider=self.embedding_provider,
                model=self.embedding_model,
            )

        if self.vector_store is None:
            self.vector_store = VectorStore()

    async def _cleanup_services(self) -> None:
        """Cleanup external services."""
        if self.embedding_service:
            await self.embedding_service.close()

    def _update_progress(
        self,
        progress: IndexingProgress,
        phase: Optional[IndexingPhase] = None,
        current_file: Optional[str] = None,
        processed_files: Optional[int] = None,
        total_chunks: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update indexing progress."""
        if phase:
            progress.phase = phase

        if current_file is not None:
            progress.current_file = current_file

        if processed_files is not None:
            progress.processed_files = processed_files
            if progress.total_files > 0:
                progress.progress = int((processed_files / progress.total_files) * 100)

        if total_chunks is not None:
            progress.total_chunks = total_chunks

        if error:
            progress.error = error
            progress.phase = IndexingPhase.ERROR

        set_indexing_progress(progress)

    async def _scan_project(
        self,
        project_path: str,
        progress: IndexingProgress,
    ) -> List[FileInfo]:
        """
        Scan the project directory.

        Args:
            project_path: Path to the cloned project
            progress: Progress tracker

        Returns:
            List of FileInfo objects
        """
        self._update_progress(progress, phase=IndexingPhase.SCANNING)

        try:
            scanner = LaravelScanner(project_path)
            scan_result = scanner.scan()

            progress.total_files = scan_result.stats.total_files
            self._update_progress(progress)

            return scan_result.files

        except ScannerError as e:
            raise IndexingError(f"Scanning failed: {str(e)}")

    def _parse_file(
        self,
        file_path: str,
        file_type: str,
        project_path: str,
    ) -> Dict[str, Any]:
        """
        Parse a file and extract structure.

        Args:
            file_path: Relative path to the file
            file_type: Type of file (php, blade, etc.)
            project_path: Base path of the project

        Returns:
            Parsed data dictionary
        """
        full_path = os.path.join(project_path, file_path)

        try:
            if file_type == "php":
                result = self.php_parser.parse_file(full_path)
                return result.to_dict()
            elif file_type == "blade":
                result = self.blade_parser.parse_file(full_path)
                return result.to_dict()
            else:
                return {}

        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {str(e)}")
            return {"errors": [str(e)]}

    def _read_file_content(self, file_path: str, project_path: str) -> str:
        """Read file content."""
        full_path = os.path.join(project_path, file_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return ""

    async def _process_files(
        self,
        files: List[FileInfo],
        project_path: str,
        progress: IndexingProgress,
    ) -> List[Dict[str, Any]]:
        """
        Parse and chunk all files.

        Args:
            files: List of FileInfo objects
            project_path: Base path of the project
            progress: Progress tracker

        Returns:
            List of all chunks
        """
        all_chunks = []

        # Filter to only indexable files
        indexable_types = {"php", "blade", "javascript", "typescript", "vue"}
        indexable_files = [f for f in files if f.type in indexable_types]

        self._update_progress(progress, phase=IndexingPhase.PARSING)

        for i, file_info in enumerate(indexable_files):
            self._update_progress(
                progress,
                current_file=file_info.path,
                processed_files=i,
            )

            # Read file content
            source_code = self._read_file_content(file_info.path, project_path)
            if not source_code.strip():
                continue

            # Parse the file
            parsed_data = self._parse_file(
                file_info.path,
                file_info.type,
                project_path,
            )

            # Chunk the file
            self._update_progress(progress, phase=IndexingPhase.CHUNKING)

            chunks = chunk_file(
                file_path=file_info.path,
                parsed_data=parsed_data if not parsed_data.get("errors") else None,
                source_code=source_code,
                file_type=file_info.type,
                max_tokens=self.max_chunk_tokens,
            )

            # Add laravel_type to each chunk
            for chunk in chunks:
                chunk["laravel_type"] = file_info.laravel_type
                chunk["file_hash"] = file_info.hash

            all_chunks.extend(chunks)

            # Yield to event loop periodically
            if i % 10 == 0:
                await asyncio.sleep(0)

        self._update_progress(
            progress,
            processed_files=len(indexable_files),
            total_chunks=len(all_chunks),
        )

        return all_chunks

    async def _generate_embeddings(
        self,
        chunks: List[Dict[str, Any]],
        progress: IndexingProgress,
    ) -> List[List[float]]:
        """
        Generate embeddings for all chunks.

        Args:
            chunks: List of chunk dictionaries
            progress: Progress tracker

        Returns:
            List of embedding vectors
        """
        self._update_progress(progress, phase=IndexingPhase.EMBEDDING)

        try:
            embeddings = await self.embedding_service.embed_chunks(chunks)
            return embeddings

        except EmbeddingError as e:
            raise IndexingError(f"Embedding generation failed: {str(e)}")

    async def _store_embeddings(
        self,
        project_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        progress: IndexingProgress,
    ) -> int:
        """
        Store embeddings in vector store.

        Args:
            project_id: The project's UUID
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors
            progress: Progress tracker

        Returns:
            Number of chunks stored
        """
        self._update_progress(progress, phase=IndexingPhase.STORING)

        try:
            # Create collection with correct dimension
            dimension = len(embeddings[0]) if embeddings else 1536
            self.vector_store.create_collection(
                project_id,
                dimension=dimension,
                recreate=True,  # Fresh index
            )

            # Group chunks by laravel_type for batch storage
            chunks_by_type: Dict[str, List[tuple]] = {}
            for chunk, embedding in zip(chunks, embeddings):
                laravel_type = chunk.get("laravel_type", "unknown")
                if laravel_type not in chunks_by_type:
                    chunks_by_type[laravel_type] = []
                chunks_by_type[laravel_type].append((chunk, embedding))

            total_stored = 0
            for laravel_type, items in chunks_by_type.items():
                type_chunks = [item[0] for item in items]
                type_embeddings = [item[1] for item in items]

                stored = self.vector_store.store_chunks(
                    project_id,
                    type_chunks,
                    type_embeddings,
                    laravel_type=laravel_type,
                )
                total_stored += stored

            return total_stored

        except VectorStoreError as e:
            raise IndexingError(f"Vector storage failed: {str(e)}")

    async def _update_database(
        self,
        project: Project,
        files: List[FileInfo],
        chunks: List[Dict[str, Any]],
    ) -> None:
        """
        Update database with indexing results.

        Args:
            project: The Project model instance
            files: List of indexed files
            chunks: List of chunks
        """
        try:
            # Clear existing indexed files
            existing_files = await self.db.execute(
                select(IndexedFile).where(IndexedFile.project_id == str(project.id))
            )
            for file in existing_files.scalars().all():
                await self.db.delete(file)

            # Create new indexed file records
            for file_info in files:
                # Find chunks for this file
                file_chunks = [c for c in chunks if c.get("file_path") == file_info.path]

                indexed_file = IndexedFile(
                    project_id=str(project.id),
                    file_path=file_info.path,
                    file_type=file_info.laravel_type,
                    file_hash=file_info.hash,
                    file_metadata={
                        "type": file_info.type,
                        "size": file_info.size,
                        "chunk_count": len(file_chunks),
                    },
                )
                self.db.add(indexed_file)

            # Update project status
            project.status = ProjectStatus.READY
            project.last_indexed_at = datetime.utcnow()
            project.indexed_files_count = len(files)
            project.error_message = None

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise IndexingError(f"Database update failed: {str(e)}")

    async def index_project(
        self,
        project_id: str,
        progress_callback: Optional[Callable[[IndexingProgress], None]] = None,
    ) -> IndexingProgress:
        """
        Index a project's codebase.

        This is the main orchestration method that:
        1. Scans files
        2. Parses each file
        3. Chunks parsed content
        4. Generates embeddings
        5. Stores in Qdrant
        6. Updates database

        Args:
            project_id: The project's UUID
            progress_callback: Optional callback for progress updates

        Returns:
            Final IndexingProgress
        """
        progress = IndexingProgress(project_id=project_id)
        set_indexing_progress(progress)

        try:
            # Initialize services
            await self._init_services()

            # Load project from database
            stmt = select(Project).where(Project.id == project_id)
            result = await self.db.execute(stmt)
            project = result.scalar_one_or_none()

            if not project:
                raise IndexingError(f"Project not found: {project_id}")

            if not project.clone_path:
                raise IndexingError("Project has no clone path. Clone the repository first.")

            if not os.path.exists(project.clone_path):
                raise IndexingError(f"Clone path does not exist: {project.clone_path}")

            # Update project status
            project.status = ProjectStatus.INDEXING
            await self.db.commit()

            # 1. Scan project
            logger.info(f"Scanning project {project_id}")
            files = await self._scan_project(project.clone_path, progress)

            if not files:
                raise IndexingError("No files found to index")

            # 2. Parse and chunk files
            logger.info(f"Processing {len(files)} files")
            chunks = await self._process_files(files, project.clone_path, progress)

            if not chunks:
                raise IndexingError("No chunks generated from files")

            # 3. Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            embeddings = await self._generate_embeddings(chunks, progress)

            # 4. Store in vector database
            logger.info(f"Storing {len(chunks)} chunks in vector database")
            stored_count = await self._store_embeddings(
                project_id, chunks, embeddings, progress
            )

            # 5. Update database
            logger.info("Updating database records")
            await self._update_database(project, files, chunks)

            # Mark as completed
            progress.phase = IndexingPhase.COMPLETED
            progress.progress = 100
            progress.completed_at = datetime.utcnow()
            set_indexing_progress(progress)

            logger.info(
                f"Indexing completed: {len(files)} files, "
                f"{len(chunks)} chunks, {stored_count} vectors stored"
            )

            return progress

        except IndexingError as e:
            logger.error(f"Indexing failed: {str(e)}")
            self._update_progress(progress, error=str(e))

            # Update project status to error
            try:
                stmt = select(Project).where(Project.id == project_id)
                result = await self.db.execute(stmt)
                project = result.scalar_one_or_none()
                if project:
                    project.status = ProjectStatus.ERROR
                    project.error_message = str(e)
                    await self.db.commit()
            except Exception:
                pass

            return progress

        except Exception as e:
            logger.exception(f"Unexpected error during indexing: {str(e)}")
            self._update_progress(progress, error=f"Unexpected error: {str(e)}")

            # Update project status to error
            try:
                stmt = select(Project).where(Project.id == project_id)
                result = await self.db.execute(stmt)
                project = result.scalar_one_or_none()
                if project:
                    project.status = ProjectStatus.ERROR
                    project.error_message = str(e)
                    await self.db.commit()
            except Exception:
                pass

            return progress

        finally:
            await self._cleanup_services()


async def index_project(
    project_id: str,
    db: AsyncSession,
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
    embedding_model: Optional[str] = None,
) -> IndexingProgress:
    """
    Convenience function to index a project.

    Args:
        project_id: The project's UUID
        db: Database session
        embedding_provider: Embedding provider to use
        embedding_model: Embedding model to use

    Returns:
        IndexingProgress
    """
    indexer = ProjectIndexer(
        db=db,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    return await indexer.index_project(project_id)
