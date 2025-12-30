"""
Empire v7.3 - Embedding Generation API Routes
Task 26: Implement Embedding Generation Service

Provides REST API endpoints for generating and managing embeddings.
Uses BGE-M3 (Ollama) for local development, OpenAI for production fallback.
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from pydantic import BaseModel, Field
import structlog

from app.services.embedding_service import (
    get_embedding_service,
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingModel
)
from app.tasks.embedding_generation import (
    generate_embeddings,
    generate_single_embedding,
    regenerate_document_embeddings,
    batch_generate_embeddings,
    update_vector_index
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["Embeddings"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GenerateEmbeddingRequest(BaseModel):
    """Request model for single embedding generation"""
    text: str = Field(..., min_length=1, max_length=32000, description="Text to embed")
    chunk_id: Optional[str] = Field(None, description="Optional chunk ID for caching")
    use_cache: bool = Field(True, description="Whether to use cached embeddings")
    namespace: str = Field("default", description="Namespace for embedding storage")


class GenerateEmbeddingResponse(BaseModel):
    """Response model for single embedding generation"""
    success: bool
    embedding: Optional[List[float]] = None
    dimensions: int = 0
    cached: bool = False
    model: str = ""
    generation_time_ms: float = 0.0
    cost: float = 0.0
    error: Optional[str] = None


class BatchEmbeddingRequest(BaseModel):
    """Request model for batch embedding generation"""
    texts: List[str] = Field(..., min_length=1, max_length=100, description="Texts to embed")
    chunk_ids: Optional[List[str]] = Field(None, description="Optional chunk IDs for caching")
    use_cache: bool = Field(True, description="Whether to use cached embeddings")
    namespace: str = Field("default", description="Namespace for embedding storage")


class BatchEmbeddingResponse(BaseModel):
    """Response model for batch embedding generation"""
    success: bool
    results_count: int = 0
    cached_count: int = 0
    generated_count: int = 0
    total_time_ms: float = 0.0
    avg_time_per_embedding_ms: float = 0.0
    total_cost: float = 0.0
    error: Optional[str] = None


class DocumentEmbeddingRequest(BaseModel):
    """Request model for document embedding generation (async)"""
    document_id: str = Field(..., description="Document ID to generate embeddings for")
    chunk_ids: List[str] = Field(..., min_length=1, description="Chunk IDs to embed")
    regenerate: bool = Field(False, description="Force regeneration even if cached")
    namespace: str = Field("default", description="Namespace for embedding storage")


class DocumentEmbeddingResponse(BaseModel):
    """Response model for document embedding generation (async task)"""
    success: bool
    task_id: Optional[str] = None
    document_id: str
    chunk_count: int = 0
    message: str = ""
    error: Optional[str] = None


class RegenerateEmbeddingsRequest(BaseModel):
    """Request model for embedding regeneration"""
    document_id: str = Field(..., description="Document ID to regenerate embeddings for")


class RegenerateEmbeddingsResponse(BaseModel):
    """Response model for embedding regeneration"""
    success: bool
    task_id: Optional[str] = None
    document_id: str
    chunk_count: int = 0
    message: str = ""
    error: Optional[str] = None


class BatchDocumentsRequest(BaseModel):
    """Request model for batch document embedding generation"""
    document_ids: List[str] = Field(..., min_length=1, max_length=50, description="Document IDs")
    priority: str = Field("normal", description="Task priority (high, normal, low)")


class BatchDocumentsResponse(BaseModel):
    """Response model for batch document embedding generation"""
    success: bool
    documents_queued: int = 0
    documents_failed: int = 0
    tasks: List[Dict[str, Any]] = []
    error: Optional[str] = None


class InvalidateCacheRequest(BaseModel):
    """Request model for cache invalidation"""
    chunk_ids: List[str] = Field(..., min_length=1, description="Chunk IDs to invalidate")


class InvalidateCacheResponse(BaseModel):
    """Response model for cache invalidation"""
    success: bool
    invalidated_count: int = 0
    error: Optional[str] = None


class EmbeddingStatsResponse(BaseModel):
    """Response model for embedding service statistics"""
    total_embeddings_generated: int
    total_cache_hits: int
    cache_hit_rate: float
    total_generation_time_seconds: float
    avg_generation_time_ms: float
    by_model: Dict[str, int]
    by_provider: Dict[str, int]


class SimilaritySearchRequest(BaseModel):
    """Request model for similarity search"""
    query_text: str = Field(..., min_length=1, description="Query text")
    top_k: int = Field(10, ge=1, le=100, description="Number of results to return")
    namespace: str = Field("default", description="Namespace to search")
    threshold: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")


class SimilaritySearchResult(BaseModel):
    """Single similarity search result"""
    chunk_id: str
    content_hash: str
    similarity: float
    metadata: Dict[str, Any] = {}


class SimilaritySearchResponse(BaseModel):
    """Response model for similarity search"""
    success: bool
    results: List[SimilaritySearchResult] = []
    query_embedding_time_ms: float = 0.0
    search_time_ms: float = 0.0
    error: Optional[str] = None


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_service() -> EmbeddingService:
    """Dependency for embedding service"""
    from app.services.supabase_storage import get_supabase_storage
    supabase_storage = get_supabase_storage()
    return get_embedding_service(supabase_storage=supabase_storage)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=GenerateEmbeddingResponse)
async def generate_embedding(
    request: GenerateEmbeddingRequest,
    service: EmbeddingService = Depends(get_service)
) -> GenerateEmbeddingResponse:
    """
    Generate embedding for a single text.

    Uses BGE-M3 (1024 dimensions) via Ollama for local development,
    with OpenAI fallback for production. Caching is enabled by default.
    """
    try:
        logger.info(
            "Embedding generation request",
            text_length=len(request.text),
            chunk_id=request.chunk_id,
            use_cache=request.use_cache
        )

        result = await service.generate_embedding(
            text=request.text,
            chunk_id=request.chunk_id,
            use_cache=request.use_cache
        )

        return GenerateEmbeddingResponse(
            success=True,
            embedding=result.embedding,
            dimensions=result.dimensions,
            cached=result.cached,
            model=result.model,
            generation_time_ms=round(result.generation_time * 1000, 2),
            cost=result.cost
        )

    except Exception as e:
        logger.error("Embedding generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/batch", response_model=BatchEmbeddingResponse)
async def generate_embeddings_batch(
    request: BatchEmbeddingRequest,
    service: EmbeddingService = Depends(get_service)
) -> BatchEmbeddingResponse:
    """
    Generate embeddings for multiple texts in batch.

    Processes up to 100 texts at once with optimized batch processing.
    Returns statistics about cached vs generated embeddings.
    """
    try:
        logger.info(
            "Batch embedding generation request",
            text_count=len(request.texts),
            use_cache=request.use_cache
        )

        # Use provided chunk_ids or generate placeholders
        chunk_ids = request.chunk_ids or [f"batch_{i}" for i in range(len(request.texts))]

        results = await service.generate_embeddings_batch(
            texts=request.texts,
            chunk_ids=chunk_ids,
            use_cache=request.use_cache
        )

        cached_count = sum(1 for r in results if r.cached)
        total_time = sum(r.generation_time for r in results)
        total_cost = sum(r.cost for r in results)

        return BatchEmbeddingResponse(
            success=True,
            results_count=len(results),
            cached_count=cached_count,
            generated_count=len(results) - cached_count,
            total_time_ms=round(total_time * 1000, 2),
            avg_time_per_embedding_ms=round((total_time / len(results)) * 1000, 2) if results else 0,
            total_cost=round(total_cost, 6)
        )

    except Exception as e:
        logger.error("Batch embedding generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/document", response_model=DocumentEmbeddingResponse)
async def generate_document_embeddings(
    request: DocumentEmbeddingRequest,
    background_tasks: BackgroundTasks
) -> DocumentEmbeddingResponse:
    """
    Queue embedding generation for a document's chunks (async).

    Processes embeddings asynchronously via Celery task.
    Returns task ID for status tracking.
    """
    try:
        logger.info(
            "Document embedding generation request",
            document_id=request.document_id,
            chunk_count=len(request.chunk_ids),
            regenerate=request.regenerate
        )

        # Queue Celery task
        task = generate_embeddings.delay(
            document_id=request.document_id,
            chunk_ids=request.chunk_ids,
            regenerate=request.regenerate,
            namespace=request.namespace
        )

        return DocumentEmbeddingResponse(
            success=True,
            task_id=task.id,
            document_id=request.document_id,
            chunk_count=len(request.chunk_ids),
            message=f"Embedding generation queued for {len(request.chunk_ids)} chunks"
        )

    except Exception as e:
        logger.error("Document embedding generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate", response_model=RegenerateEmbeddingsResponse)
async def regenerate_embeddings(
    request: RegenerateEmbeddingsRequest
) -> RegenerateEmbeddingsResponse:
    """
    Regenerate all embeddings for a document (async).

    Forces regeneration of embeddings even if cached.
    Useful when content has been updated.
    """
    try:
        logger.info(
            "Embedding regeneration request",
            document_id=request.document_id
        )

        # Queue Celery task
        task = regenerate_document_embeddings.delay(
            document_id=request.document_id
        )

        return RegenerateEmbeddingsResponse(
            success=True,
            task_id=task.id,
            document_id=request.document_id,
            message="Embedding regeneration queued"
        )

    except Exception as e:
        logger.error("Embedding regeneration failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-documents", response_model=BatchDocumentsResponse)
async def queue_batch_document_embeddings(
    request: BatchDocumentsRequest
) -> BatchDocumentsResponse:
    """
    Queue embedding generation for multiple documents (async).

    Processes multiple documents with specified priority.
    Returns task IDs for each document.
    """
    try:
        logger.info(
            "Batch document embedding request",
            document_count=len(request.document_ids),
            priority=request.priority
        )

        # Queue Celery task
        result = batch_generate_embeddings.delay(
            document_ids=request.document_ids,
            priority=request.priority
        )

        # Get task result (blocking for batch queue operation)
        task_result = result.get(timeout=30)

        return BatchDocumentsResponse(
            success=True,
            documents_queued=task_result.get("documents_queued", 0),
            documents_failed=task_result.get("documents_failed", 0),
            tasks=task_result.get("tasks", [])
        )

    except Exception as e:
        logger.error("Batch document embedding failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate-cache", response_model=InvalidateCacheResponse)
async def invalidate_cache(
    request: InvalidateCacheRequest,
    service: EmbeddingService = Depends(get_service)
) -> InvalidateCacheResponse:
    """
    Invalidate cached embeddings for specific chunks.

    Removes embeddings from cache, forcing regeneration on next request.
    """
    try:
        logger.info(
            "Cache invalidation request",
            chunk_count=len(request.chunk_ids)
        )

        invalidated_count = 0
        for chunk_id in request.chunk_ids:
            if await service.invalidate_chunk_cache(chunk_id):
                invalidated_count += 1

        return InvalidateCacheResponse(
            success=True,
            invalidated_count=invalidated_count
        )

    except Exception as e:
        logger.error("Cache invalidation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-index")
async def trigger_index_update(document_id: str) -> Dict[str, Any]:
    """
    Trigger vector index update for a document (async).

    Refreshes the HNSW index after new embeddings are added.
    """
    try:
        logger.info("Index update request", document_id=document_id)

        task = update_vector_index.delay(document_id=document_id)

        return {
            "success": True,
            "task_id": task.id,
            "document_id": document_id,
            "message": "Index update queued"
        }

    except Exception as e:
        logger.error("Index update failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=EmbeddingStatsResponse)
async def get_embedding_stats(
    service: EmbeddingService = Depends(get_service)
) -> EmbeddingStatsResponse:
    """Get embedding service statistics"""
    try:
        stats = await service.get_stats()

        return EmbeddingStatsResponse(
            total_embeddings_generated=stats.get("total_embeddings_generated", 0),
            total_cache_hits=stats.get("total_cache_hits", 0),
            cache_hit_rate=stats.get("cache_hit_rate", 0.0),
            total_generation_time_seconds=stats.get("total_generation_time_seconds", 0.0),
            avg_generation_time_ms=stats.get("avg_generation_time_ms", 0.0),
            by_model=stats.get("by_model", {}),
            by_provider=stats.get("by_provider", {})
        )

    except Exception as e:
        logger.error("Stats retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_available_models() -> Dict[str, Any]:
    """Get list of available embedding models"""
    return {
        "models": [
            {
                "id": EmbeddingModel.BGE_M3.value,
                "name": "BGE-M3",
                "provider": EmbeddingProvider.OLLAMA.value,
                "dimensions": 1024,
                "cost_per_million_tokens": 0.0,
                "description": "Local BGE-M3 via Ollama (free, development)"
            },
            {
                "id": EmbeddingModel.MISTRAL_EMBED.value,
                "name": "Mistral Embed",
                "provider": EmbeddingProvider.MISTRAL.value,
                "dimensions": 1024,
                "cost_per_million_tokens": 0.1,
                "description": "Mistral Embed with 1024 dims (production fallback)"
            }
        ],
        "default_model": EmbeddingModel.BGE_M3.value,
        "production_fallback": EmbeddingModel.MISTRAL_EMBED.value,
        "note": "Both models use 1024 dimensions for seamless switching"
    }


@router.get("/health")
async def embedding_health() -> Dict[str, Any]:
    """Health check for Embedding Service"""
    from app.services.supabase_storage import get_supabase_storage

    # Check Ollama availability
    ollama_available = False
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/version",
                timeout=5.0
            )
            ollama_available = response.status_code == 200
    except Exception:
        pass

    # Check Mistral availability (API key present)
    mistral_available = bool(os.getenv("MISTRAL_API_KEY"))

    # Check Supabase cache availability
    supabase_available = False
    try:
        storage = get_supabase_storage()
        supabase_available = storage.supabase is not None
    except Exception:
        pass

    return {
        "status": "healthy" if (ollama_available or mistral_available) else "degraded",
        "service": "Embedding Generation Service",
        "task": "Task 26",
        "version": "v7.3",
        "providers": {
            "ollama": {
                "available": ollama_available,
                "model": EmbeddingModel.BGE_M3.value,
                "dimensions": 1024,
                "cost": "free (local)"
            },
            "mistral": {
                "available": mistral_available,
                "model": EmbeddingModel.MISTRAL_EMBED.value,
                "dimensions": 1024,
                "cost": "$0.1/1M tokens"
            }
        },
        "cache": {
            "supabase_available": supabase_available,
            "table": "embeddings_cache"
        },
        "target_latency_ms": 100,
        "batch_size": 100,
        "note": "Both providers use 1024 dimensions for compatibility"
    }
