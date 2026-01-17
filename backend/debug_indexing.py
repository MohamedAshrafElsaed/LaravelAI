#!/usr/bin/env python3
"""
Debug script to check project indexing status.
Run from backend directory: python debug_indexing.py <project_id>
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.vector_store import VectorStore
from app.services.embeddings import EmbeddingService, EmbeddingProvider
from sqlalchemy import select, func
from app.models.models import Project, IndexedFile


async def debug_project(project_id: str):
    """Debug indexing status for a project."""
    print(f"\n{'='*60}")
    print(f"DEBUGGING PROJECT: {project_id}")
    print(f"{'='*60}\n")

    # 1. Check database records
    print("[1] CHECKING DATABASE RECORDS...")
    async with async_session_factory() as db:
        # Get project
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            print(f"   ❌ Project not found in database!")
            print(f"   Try listing all projects:")
            stmt = select(Project.id, Project.name, Project.status)
            result = await db.execute(stmt)
            projects = result.all()
            for p in projects:
                print(f"      - {p.id}: {p.name} (status: {p.status})")
            return

        print(f"   ✓ Project found: {project.name}")
        print(f"     Status: {project.status}")
        print(f"     Last indexed: {project.last_indexed_at}")
        print(f"     Indexed files count: {project.indexed_files_count}")
        print(f"     Clone path: {project.clone_path}")

        # Count indexed files
        stmt = select(func.count(IndexedFile.id)).where(IndexedFile.project_id == project_id)
        result = await db.execute(stmt)
        indexed_count = result.scalar()
        print(f"\n   Indexed files in DB: {indexed_count}")

        if indexed_count == 0:
            print(f"   ❌ No files indexed in database!")
            print(f"   → You need to run indexing first")
            return

        # Sample indexed files
        print(f"\n   Sample indexed files:")
        stmt = select(IndexedFile.file_path, func.length(IndexedFile.content)).where(
            IndexedFile.project_id == project_id
        ).limit(10)
        result = await db.execute(stmt)
        files = result.all()
        for f in files:
            print(f"      - {f[0]} ({f[1] or 0} chars)")

        # Check for files WITH content
        stmt = select(func.count(IndexedFile.id)).where(
            IndexedFile.project_id == project_id,
            func.length(IndexedFile.content) > 0
        )
        result = await db.execute(stmt)
        files_with_content = result.scalar()
        print(f"\n   Files WITH content: {files_with_content} / {indexed_count}")

        if files_with_content == 0:
            print(f"\n   ❌ CRITICAL: All indexed files have EMPTY content!")
            print(f"   This means the indexer stored file paths but NOT file content.")
            print(f"   → Vector embeddings cannot be created without content.")
            print(f"   → You need to re-index the project to store file content.")

        # Show sample files WITH content
        if files_with_content > 0:
            print(f"\n   Sample files WITH content:")
            stmt = select(IndexedFile.file_path, func.length(IndexedFile.content)).where(
                IndexedFile.project_id == project_id,
                func.length(IndexedFile.content) > 0
            ).order_by(func.length(IndexedFile.content).desc()).limit(5)
            result = await db.execute(stmt)
            files = result.all()
            for f in files:
                print(f"      - {f[0]} ({f[1]} chars)")

    # 2. Check Qdrant vector store
    print(f"\n[2] CHECKING QDRANT VECTOR STORE...")
    try:
        vector_store = VectorStore()
        print(f"   ✓ Connected to Qdrant at {vector_store.url}")

        # Check if collection exists
        collection_name = vector_store._get_collection_name(project_id)
        if vector_store.collection_exists(project_id):
            print(f"   ✓ Collection exists: {collection_name}")

            # Try to get basic info directly from client to avoid parsing issues
            try:
                info = vector_store.get_collection_info(project_id)
                print(f"     - Points count: {info['points_count']}")
                print(f"     - Vectors count: {info['vectors_count']}")
                print(f"     - Status: {info['status']}")
                print(f"     - Dimension: {info['dimension']}")

                if info['points_count'] == 0:
                    print(f"\n   ❌ Collection exists but has 0 vectors!")
                    print(f"   → This means embeddings were not stored properly")
            except Exception as parse_err:
                # Fallback: try scroll to count points
                print(f"   ⚠️ Could not parse collection info (client/server version mismatch)")
                print(f"   Trying alternative count method...")
                try:
                    # Use scroll to check if there are any points
                    scroll_result = vector_store.client.scroll(
                        collection_name=collection_name,
                        limit=1,
                        with_payload=False,
                        with_vectors=False,
                    )
                    points, next_page = scroll_result
                    if points:
                        print(f"   ✓ Collection has vectors (at least 1 found)")
                        # Try to count using count API
                        try:
                            count_result = vector_store.client.count(collection_name=collection_name)
                            print(f"     - Points count: {count_result.count}")
                        except:
                            print(f"     - Points count: unknown (count API failed)")
                    else:
                        print(f"   ❌ Collection exists but appears empty!")
                except Exception as scroll_err:
                    print(f"   ❌ Could not check collection: {scroll_err}")
        else:
            print(f"   ❌ No Qdrant collection found for project!")
            print(f"   → Embeddings have not been created")

    except Exception as e:
        print(f"   ❌ Qdrant error: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Test embedding generation
    print(f"\n[3] TESTING EMBEDDING GENERATION...")
    try:
        provider = (
            EmbeddingProvider.VOYAGE
            if settings.embedding_provider == "voyage"
            else EmbeddingProvider.OPENAI
        )
        embedding_service = EmbeddingService(provider=provider)
        print(f"   Using provider: {provider}")

        test_query = "get user information api"
        embedding = await embedding_service.embed_query(test_query)

        if embedding:
            print(f"   ✓ Embedding generated successfully")
            print(f"     Dimension: {len(embedding)}")
        else:
            print(f"   ❌ Failed to generate embedding!")
            return
    except Exception as e:
        print(f"   ❌ Embedding error: {e}")
        return

    # 4. Test actual search
    print(f"\n[4] TESTING VECTOR SEARCH...")
    try:
        if not vector_store.collection_exists(project_id):
            print(f"   ❌ Cannot search - no collection")
            return

        results = vector_store.search(
            project_id=project_id,
            query_embedding=embedding,
            limit=5,
            score_threshold=0.0,  # No threshold - show all
        )

        print(f"   Results found: {len(results)}")
        if results:
            print(f"\n   Top results:")
            for i, r in enumerate(results, 1):
                print(f"      {i}. {r.file_path} (score: {r.score:.4f})")
                print(f"         Type: {r.chunk_type}")
                print(f"         Content preview: {r.content[:100]}...")
        else:
            print(f"\n   ❌ No results returned!")
            print(f"   Possible causes:")
            print(f"   - Collection dimension mismatch (check embedding provider)")
            print(f"   - All embeddings have 0 similarity (try different query)")

        # Try with very low threshold
        results_no_thresh = vector_store.search(
            project_id=project_id,
            query_embedding=embedding,
            limit=5,
            score_threshold=-1.0,  # Accept negative scores
        )
        print(f"\n   Results with no threshold: {len(results_no_thresh)}")

    except Exception as e:
        print(f"   ❌ Search error: {e}")
        import traceback
        traceback.print_exc()

    # 5. Check embedding dimension match
    print(f"\n[5] CHECKING DIMENSION COMPATIBILITY...")
    try:
        info = vector_store.get_collection_info(project_id)
        stored_dim = info['dimension']
        query_dim = len(embedding)

        print(f"   Stored vectors dimension: {stored_dim}")
        print(f"   Query embedding dimension: {query_dim}")

        if stored_dim != query_dim:
            print(f"\n   ❌ DIMENSION MISMATCH!")
            print(f"   This is likely the problem. You may have:")
            print(f"   - Indexed with one embedding provider")
            print(f"   - Searching with a different provider")
            print(f"   → Solution: Re-index the project with current provider")
        else:
            print(f"   ✓ Dimensions match")

    except Exception as e:
        print(f"   Error checking dimensions: {e}")

    print(f"\n{'='*60}")
    print("DEBUG COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_indexing.py <project_id>")
        print("\nTo list all projects, pass 'list' as argument:")
        print("  python debug_indexing.py list")
        sys.exit(1)

    project_id = sys.argv[1]

    if project_id == "list":
        async def list_projects():
            async with async_session_factory() as db:
                stmt = select(Project.id, Project.name, Project.status, Project.indexed_files_count)
                result = await db.execute(stmt)
                projects = result.all()
                print("\nAll projects:")
                for p in projects:
                    print(f"  {p.id}: {p.name} (status: {p.status}, indexed: {p.indexed_files_count})")
        asyncio.run(list_projects())
    else:
        asyncio.run(debug_project(project_id))
