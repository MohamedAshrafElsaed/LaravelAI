#!/usr/bin/env python3
"""
Re-index a project to fix missing content in indexed files.
Run from backend directory: python reindex_project.py <project_id>
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.indexer import ProjectIndexer
from app.services.embeddings import EmbeddingProvider
from app.services.vector_store import VectorStore
from sqlalchemy import select, delete
from app.models.models import Project, IndexedFile, ProjectStatus


async def reindex_project(project_id: str, force: bool = False):
    """Re-index a project with the fixed indexer that stores file content."""
    print(f"\n{'='*60}")
    print(f"RE-INDEXING PROJECT: {project_id}")
    print(f"{'='*60}\n")

    async with async_session_factory() as db:
        # 1. Get project
        print("[1] FETCHING PROJECT...")
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            print(f"   ❌ Project not found!")
            print(f"\n   Available projects:")
            stmt = select(Project.id, Project.name, Project.status)
            result = await db.execute(stmt)
            projects = result.all()
            for p in projects:
                print(f"      - {p.id}: {p.name} (status: {p.status})")
            return

        print(f"   ✓ Found project: {project.name}")
        print(f"     Clone path: {project.clone_path}")
        print(f"     Current status: {project.status}")

        if not project.clone_path:
            print(f"\n   ❌ Project has not been cloned yet!")
            print(f"   Clone the project first via the API.")
            return

        if not os.path.exists(project.clone_path):
            print(f"\n   ❌ Clone path does not exist: {project.clone_path}")
            return

        # 2. Clear existing indexed files
        print(f"\n[2] CLEARING EXISTING DATA...")

        # Delete from IndexedFile table
        stmt = delete(IndexedFile).where(IndexedFile.project_id == project_id)
        result = await db.execute(stmt)
        await db.commit()
        print(f"   ✓ Deleted existing indexed files from database")

        # Delete Qdrant collection
        try:
            vector_store = VectorStore()
            if vector_store.collection_exists(project_id):
                vector_store.delete_collection(project_id)
                print(f"   ✓ Deleted Qdrant collection")
            else:
                print(f"   ℹ No existing Qdrant collection")
        except Exception as e:
            print(f"   ⚠ Could not delete Qdrant collection: {e}")

        # 3. Update project status
        print(f"\n[3] STARTING INDEXING...")
        project.status = ProjectStatus.INDEXING.value
        project.error_message = None
        await db.commit()

        # 4. Run indexer
        try:
            # Determine embedding provider
            provider = (
                EmbeddingProvider.VOYAGE
                if settings.embedding_provider == "voyage"
                else EmbeddingProvider.OPENAI
            )
            print(f"   Using embedding provider: {provider.value}")

            indexer = ProjectIndexer(
                db=db,
                embedding_provider=provider,
            )

            print(f"   Starting indexer.index_project()...")
            print(f"   This may take a few minutes...\n")

            await indexer.index_project(project_id)

            print(f"\n   ✓ Indexing completed!")

        except Exception as e:
            print(f"\n   ❌ Indexing failed: {e}")
            import traceback
            traceback.print_exc()

            # Update project status
            project.status = ProjectStatus.ERROR.value
            project.error_message = f"Re-indexing failed: {str(e)}"
            await db.commit()
            return

        # 5. Verify results
        print(f"\n[4] VERIFYING RESULTS...")

        # Re-fetch project
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        print(f"   Project status: {project.status}")
        print(f"   Indexed files count: {project.indexed_files_count}")

        # Check files with content
        from sqlalchemy import func
        stmt = select(func.count(IndexedFile.id)).where(
            IndexedFile.project_id == project_id,
            func.length(IndexedFile.content) > 0
        )
        result = await db.execute(stmt)
        files_with_content = result.scalar()

        stmt = select(func.count(IndexedFile.id)).where(IndexedFile.project_id == project_id)
        result = await db.execute(stmt)
        total_files = result.scalar()

        print(f"   Files with content: {files_with_content} / {total_files}")

        if files_with_content == 0 and total_files > 0:
            print(f"\n   ❌ WARNING: Files were indexed but still have no content!")
            print(f"   This suggests the indexer fix was not applied correctly.")
        elif files_with_content > 0:
            print(f"\n   ✓ SUCCESS! Files now have content stored.")

        # Check Qdrant
        try:
            vector_store = VectorStore()
            if vector_store.collection_exists(project_id):
                info = vector_store.get_collection_info(project_id)
                print(f"\n   Qdrant collection:")
                print(f"     - Points count: {info['points_count']}")
                print(f"     - Vectors count: {info['vectors_count']}")
            else:
                print(f"\n   ⚠ No Qdrant collection created")
        except Exception as e:
            print(f"\n   ⚠ Could not check Qdrant: {e}")

    print(f"\n{'='*60}")
    print("RE-INDEXING COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reindex_project.py <project_id>")
        print("\nTo list all projects:")
        print("  python debug_indexing.py list")
        sys.exit(1)

    project_id = sys.argv[1]
    asyncio.run(reindex_project(project_id))
