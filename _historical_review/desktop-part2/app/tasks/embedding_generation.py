"""
Empire v7.3 - Embedding Generation Tasks (Task 26)
Celery tasks for generating and storing document embeddings using BGE-M3

Features:
- Batch processing (100 chunks per batch)
- Supabase pgvector caching
- Regeneration on content updates
- Target latency: <100ms per chunk locally
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async code in Celery tasks"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(
    name='app.tasks.embedding_generation.generate_embeddings',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def generate_embeddings(
    self,
    document_id: str,
    chunk_ids: List[str],
    regenerate: bool = False,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Generate embeddings for document chunks using BGE-M3

    Args:
        document_id: Unique document identifier
        chunk_ids: List of chunk IDs to generate embeddings for
        regenerate: Force regeneration even if cached
        namespace: Namespace for embedding storage

    Returns:
        Embedding generation result with statistics
    """
    try:
        logger.info(f"🔢 Generating embeddings for document: {document_id} ({len(chunk_ids)} chunks)")

        # Import services inside task to avoid circular imports
        from app.services.embedding_service import get_embedding_service
        from app.services.supabase_storage import get_supabase_storage

        # Get services
        supabase_storage = get_supabase_storage()
        embedding_service = get_embedding_service(
            supabase_storage=supabase_storage
        )

        # Fetch chunks from Supabase
        chunks_data = run_async(_fetch_chunks(supabase_storage, chunk_ids))

        if not chunks_data:
            logger.warning(f"No chunks found for IDs: {chunk_ids}")
            return {
                "status": "warning",
                "document_id": document_id,
                "chunks_processed": 0,
                "message": "No chunks found for provided IDs"
            }

        # Extract texts and IDs
        texts = [chunk["content"] for chunk in chunks_data]
        valid_chunk_ids = [chunk["id"] for chunk in chunks_data]

        # Invalidate cache if regenerating
        if regenerate:
            for chunk_id in valid_chunk_ids:
                run_async(embedding_service.invalidate_chunk_cache(chunk_id))

        # Generate embeddings in batch
        results = run_async(
            embedding_service.generate_embeddings_batch(
                texts=texts,
                chunk_ids=valid_chunk_ids,
                use_cache=not regenerate
            )
        )

        # Store embeddings in chunks table
        embeddings_stored = run_async(
            _store_embeddings_in_chunks(supabase_storage, results)
        )

        # Calculate statistics
        cached_count = sum(1 for r in results if r.cached)
        generated_count = len(results) - cached_count
        total_time = sum(r.generation_time for r in results)
        avg_time = total_time / len(results) if results else 0

        logger.info(
            f"✅ Embeddings complete for {document_id}: "
            f"{generated_count} generated, {cached_count} cached, "
            f"avg time: {avg_time*1000:.1f}ms"
        )

        return {
            "status": "success",
            "document_id": document_id,
            "chunks_processed": len(results),
            "chunks_generated": generated_count,
            "chunks_cached": cached_count,
            "embeddings_stored": embeddings_stored,
            "total_time_seconds": round(total_time, 3),
            "avg_time_per_chunk_ms": round(avg_time * 1000, 1),
            "model": results[0].model if results else "bge-m3",
            "dimensions": results[0].dimensions if results else 1024
        }

    except Exception as e:
        logger.error(f"❌ Embedding generation failed for {document_id}: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    name='app.tasks.embedding_generation.generate_single_embedding',
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def generate_single_embedding(
    self,
    chunk_id: str,
    content: str,
    regenerate: bool = False
) -> Dict[str, Any]:
    """
    Generate embedding for a single chunk

    Args:
        chunk_id: Chunk identifier
        content: Text content to embed
        regenerate: Force regeneration even if cached

    Returns:
        Embedding generation result
    """
    try:
        logger.info(f"🔢 Generating embedding for chunk: {chunk_id}")

        from app.services.embedding_service import get_embedding_service
        from app.services.supabase_storage import get_supabase_storage

        supabase_storage = get_supabase_storage()
        embedding_service = get_embedding_service(
            supabase_storage=supabase_storage
        )

        # Invalidate cache if regenerating
        if regenerate:
            run_async(embedding_service.invalidate_chunk_cache(chunk_id))

        # Generate embedding
        result = run_async(
            embedding_service.generate_embedding(
                text=content,
                chunk_id=chunk_id,
                use_cache=not regenerate
            )
        )

        # Store in chunks table
        run_async(
            _store_single_embedding(supabase_storage, chunk_id, result.embedding)
        )

        return {
            "status": "success",
            "chunk_id": chunk_id,
            "cached": result.cached,
            "dimensions": result.dimensions,
            "generation_time_ms": round(result.generation_time * 1000, 1),
            "model": result.model,
            "cost": result.cost
        }

    except Exception as e:
        logger.error(f"❌ Embedding generation failed for chunk {chunk_id}: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(
    name='app.tasks.embedding_generation.update_vector_index',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def update_vector_index(self, document_id: str) -> Dict[str, Any]:
    """
    Update vector search index after new embeddings

    Args:
        document_id: Unique document identifier

    Returns:
        Index update result
    """
    try:
        logger.info(f"🔄 Updating vector index for: {document_id}")

        from app.services.supabase_storage import get_supabase_storage

        supabase_storage = get_supabase_storage()

        # Refresh HNSW index (runs REINDEX)
        # Note: In production, this might be scheduled during low-traffic periods
        index_refreshed = run_async(_refresh_vector_index(supabase_storage))

        # Clear related cache entries for document
        cache_cleared = run_async(_clear_document_cache(supabase_storage, document_id))

        logger.info(f"✅ Vector index updated for {document_id}")

        return {
            "status": "success",
            "document_id": document_id,
            "index_refreshed": index_refreshed,
            "cache_cleared": cache_cleared
        }

    except Exception as e:
        logger.error(f"❌ Vector index update failed for {document_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(
    name='app.tasks.embedding_generation.regenerate_document_embeddings',
    bind=True,
    max_retries=2,
    default_retry_delay=120
)
def regenerate_document_embeddings(self, document_id: str) -> Dict[str, Any]:
    """
    Regenerate all embeddings for a document (on content update)

    Args:
        document_id: Document to regenerate embeddings for

    Returns:
        Regeneration result
    """
    try:
        logger.info(f"🔄 Regenerating embeddings for document: {document_id}")

        from app.services.supabase_storage import get_supabase_storage

        supabase_storage = get_supabase_storage()

        # Get all chunk IDs for document
        chunk_ids = run_async(_get_document_chunk_ids(supabase_storage, document_id))

        if not chunk_ids:
            return {
                "status": "warning",
                "document_id": document_id,
                "message": "No chunks found for document"
            }

        # Call generate_embeddings with regenerate=True
        result = generate_embeddings.delay(
            document_id=document_id,
            chunk_ids=chunk_ids,
            regenerate=True
        )

        return {
            "status": "queued",
            "document_id": document_id,
            "chunk_count": len(chunk_ids),
            "task_id": result.id,
            "message": f"Regeneration queued for {len(chunk_ids)} chunks"
        }

    except Exception as e:
        logger.error(f"❌ Embedding regeneration failed for {document_id}: {e}")
        raise self.retry(exc=e, countdown=120)


@celery_app.task(name='app.tasks.embedding_generation.batch_generate_embeddings')
def batch_generate_embeddings(
    document_ids: List[str],
    priority: str = "normal"
) -> Dict[str, Any]:
    """
    Queue embedding generation for multiple documents

    Args:
        document_ids: List of document IDs
        priority: Task priority ("high", "normal", "low")

    Returns:
        Batch queuing result
    """
    logger.info(f"📦 Batch queueing embeddings for {len(document_ids)} documents")

    from app.services.supabase_storage import get_supabase_storage

    supabase_storage = get_supabase_storage()
    queued_tasks = []

    for doc_id in document_ids:
        try:
            # Get chunk IDs for each document
            chunk_ids = run_async(_get_document_chunk_ids(supabase_storage, doc_id))

            if chunk_ids:
                # Queue with appropriate priority
                task = generate_embeddings.apply_async(
                    args=[doc_id, chunk_ids],
                    queue=f"embeddings_{priority}"
                )
                queued_tasks.append({
                    "document_id": doc_id,
                    "task_id": task.id,
                    "chunk_count": len(chunk_ids)
                })
        except Exception as e:
            logger.error(f"Failed to queue embeddings for {doc_id}: {e}")
            queued_tasks.append({
                "document_id": doc_id,
                "error": str(e)
            })

    return {
        "status": "queued",
        "documents_queued": len([t for t in queued_tasks if "task_id" in t]),
        "documents_failed": len([t for t in queued_tasks if "error" in t]),
        "tasks": queued_tasks
    }


# ============================================================================
# Helper Functions (async)
# ============================================================================

async def _fetch_chunks(supabase_storage, chunk_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch chunk data from Supabase"""
    try:
        result = await asyncio.to_thread(
            lambda: supabase_storage.supabase.table("chunks")
            .select("id, content, document_id, metadata")
            .in_("id", chunk_ids)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to fetch chunks: {e}")
        # Fallback: try document_chunks table
        try:
            result = await asyncio.to_thread(
                lambda: supabase_storage.supabase.table("document_chunks")
                .select("id, content, document_id, metadata")
                .in_("id", chunk_ids)
                .execute()
            )
            return result.data if result.data else []
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            return []


async def _store_embeddings_in_chunks(
    supabase_storage,
    results: List
) -> int:
    """Store embeddings in chunks table"""
    stored_count = 0

    for result in results:
        try:
            await asyncio.to_thread(
                lambda r=result: supabase_storage.supabase.table("chunks")
                .update({"embedding": r.embedding})
                .eq("id", r.chunk_id)
                .execute()
            )
            stored_count += 1
        except Exception as e:
            # Try document_chunks table
            try:
                await asyncio.to_thread(
                    lambda r=result: supabase_storage.supabase.table("document_chunks")
                    .update({"embedding": r.embedding})
                    .eq("id", r.chunk_id)
                    .execute()
                )
                stored_count += 1
            except Exception as e2:
                logger.error(f"Failed to store embedding for {result.chunk_id}: {e2}")

    return stored_count


async def _store_single_embedding(
    supabase_storage,
    chunk_id: str,
    embedding: List[float]
) -> bool:
    """Store single embedding in chunks table"""
    try:
        await asyncio.to_thread(
            lambda: supabase_storage.supabase.table("chunks")
            .update({"embedding": embedding})
            .eq("id", chunk_id)
            .execute()
        )
        return True
    except Exception as e:
        # Try document_chunks table
        try:
            await asyncio.to_thread(
                lambda: supabase_storage.supabase.table("document_chunks")
                .update({"embedding": embedding})
                .eq("id", chunk_id)
                .execute()
            )
            return True
        except Exception as e2:
            logger.error(f"Failed to store embedding for {chunk_id}: {e2}")
            return False


async def _get_document_chunk_ids(supabase_storage, document_id: str) -> List[str]:
    """Get all chunk IDs for a document"""
    try:
        result = await asyncio.to_thread(
            lambda: supabase_storage.supabase.table("chunks")
            .select("id")
            .eq("document_id", document_id)
            .execute()
        )
        return [row["id"] for row in result.data] if result.data else []
    except Exception as e:
        # Try document_chunks table
        try:
            result = await asyncio.to_thread(
                lambda: supabase_storage.supabase.table("document_chunks")
                .select("id")
                .eq("document_id", document_id)
                .execute()
            )
            return [row["id"] for row in result.data] if result.data else []
        except Exception as e2:
            logger.error(f"Failed to get chunk IDs for {document_id}: {e2}")
            return []


async def _refresh_vector_index(supabase_storage) -> bool:
    """Refresh HNSW vector index"""
    try:
        # Note: REINDEX requires appropriate permissions
        # In production, this should be done with care
        await asyncio.to_thread(
            lambda: supabase_storage.supabase.rpc(
                "refresh_embedding_index",
                {}
            ).execute()
        )
        return True
    except Exception as e:
        logger.warning(f"Index refresh skipped (may require manual intervention): {e}")
        return False


async def _clear_document_cache(supabase_storage, document_id: str) -> int:
    """Clear cached embeddings for a document"""
    try:
        # Get chunk IDs for document
        chunk_ids = await _get_document_chunk_ids(supabase_storage, document_id)

        if not chunk_ids:
            return 0

        # Delete from embeddings_cache
        result = await asyncio.to_thread(
            lambda: supabase_storage.supabase.table("embeddings_cache")
            .delete()
            .in_("chunk_id", chunk_ids)
            .execute()
        )

        deleted_count = len(result.data) if result.data else 0
        logger.info(f"Cleared {deleted_count} cached embeddings for document {document_id}")
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to clear cache for {document_id}: {e}")
        return 0
