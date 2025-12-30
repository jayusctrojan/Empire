"""
Empire v7.3 - Semantic Cache API Routes (Task 30)

REST API endpoints for semantic caching with tiered similarity thresholds.
Target: 60-80% cache hit rate with <200ms lookup time.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.services.semantic_cache_service import (
    SemanticCacheService,
    SemanticCacheConfig,
    CacheMatchTier,
    get_semantic_cache_service,
    reset_semantic_cache_service
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["Semantic Cache"])


# =============================================================================
# Pydantic Models
# =============================================================================

class CacheLookupRequest(BaseModel):
    """Request for cache lookup"""
    query: str = Field(..., description="Search query to look up")
    namespace: Optional[str] = Field("search", description="Cache namespace")
    embedding: Optional[List[float]] = Field(None, description="Pre-computed query embedding")


class CacheLookupResponse(BaseModel):
    """Response from cache lookup"""
    tier: str = Field(..., description="Cache match tier: exact, high, medium, low, miss")
    similarity: float = Field(..., description="Similarity score (0.0-1.0)")
    is_usable: bool = Field(..., description="Whether cached result should be used")
    needs_fresh_search: bool = Field(..., description="Whether fresh search is recommended")
    data: Optional[Dict[str, Any]] = Field(None, description="Cached data if usable")
    original_query: Optional[str] = Field(None, description="Original cached query")
    lookup_time_ms: float = Field(..., description="Lookup time in milliseconds")


class CacheStoreRequest(BaseModel):
    """Request to store in cache"""
    query: str = Field(..., description="Search query")
    result: Dict[str, Any] = Field(..., description="Search result to cache")
    namespace: Optional[str] = Field("search", description="Cache namespace")
    embedding: Optional[List[float]] = Field(None, description="Pre-computed query embedding")


class CacheStoreResponse(BaseModel):
    """Response from cache store"""
    success: bool
    query: str
    message: str


class CacheMetricsResponse(BaseModel):
    """Cache metrics response"""
    total_requests: int
    exact_hits: int
    high_hits: int
    medium_hits: int
    misses: int
    embedding_cache_hits: int
    embedding_cache_misses: int
    cache_hit_rate: float
    tier_distribution: Dict[str, float]
    target_hit_rate: str = "60-80%"


class CacheHealthResponse(BaseModel):
    """Cache health check response"""
    status: str
    redis_connected: bool
    thresholds: Dict[str, float]
    ttl_settings: Dict[str, int]


class CacheConfigResponse(BaseModel):
    """Cache configuration response"""
    exact_threshold: float
    high_threshold: float
    medium_threshold: float
    search_result_ttl: int
    embedding_ttl: int
    max_candidates: int
    metrics_enabled: bool


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/lookup", response_model=CacheLookupResponse)
async def cache_lookup(request: CacheLookupRequest):
    """
    Look up cached result using semantic similarity

    Uses tiered similarity thresholds:
    - **Exact (>0.98)**: Return cached result immediately
    - **High (0.93-0.97)**: Return cached result with high confidence
    - **Medium (0.88-0.92)**: Fresh search recommended
    - **Low (<0.88)**: Cache miss

    **Example:**
    ```json
    {
        "query": "What are California insurance requirements?",
        "namespace": "search"
    }
    ```

    **Returns:**
    Cache lookup result with tier classification and similarity score.
    """
    try:
        service = get_semantic_cache_service()
        result = await service.get_semantic_match(
            query=request.query,
            query_embedding=request.embedding,
            namespace=request.namespace
        )

        return CacheLookupResponse(
            tier=result.tier.value,
            similarity=result.similarity,
            is_usable=result.is_usable,
            needs_fresh_search=result.needs_fresh_search,
            data=result.data,
            original_query=result.original_query,
            lookup_time_ms=result.lookup_time_ms
        )

    except Exception as e:
        logger.error(f"Cache lookup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache lookup failed: {str(e)}")


@router.post("/store", response_model=CacheStoreResponse)
async def cache_store(request: CacheStoreRequest):
    """
    Store search result in semantic cache

    Stores the result with both exact hash key and semantic embedding
    for future similarity matching.

    **Example:**
    ```json
    {
        "query": "California insurance requirements",
        "result": {
            "results": [...],
            "total_count": 10
        },
        "namespace": "search"
    }
    ```
    """
    try:
        service = get_semantic_cache_service()
        success = await service.cache_search_result(
            query=request.query,
            result=request.result,
            embedding=request.embedding,
            namespace=request.namespace
        )

        return CacheStoreResponse(
            success=success,
            query=request.query,
            message="Cached successfully" if success else "Cache store failed"
        )

    except Exception as e:
        logger.error(f"Cache store failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache store failed: {str(e)}")


@router.delete("/invalidate")
async def cache_invalidate(
    query: str = Query(..., description="Query to invalidate"),
    namespace: str = Query("search", description="Cache namespace")
):
    """
    Invalidate cached result for specific query

    Removes both exact match and semantic match entries.
    """
    try:
        service = get_semantic_cache_service()
        success = await service.invalidate_query(query, namespace)

        return {
            "success": success,
            "query": query,
            "namespace": namespace,
            "message": "Cache invalidated" if success else "Invalidation failed"
        }

    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache invalidation failed: {str(e)}")


@router.delete("/clear/{namespace}")
async def cache_clear(namespace: str):
    """
    Clear all cached entries in namespace

    **Warning:** This removes all cached data in the specified namespace.
    """
    try:
        service = get_semantic_cache_service()
        count = await service.clear_namespace(namespace)

        return {
            "success": True,
            "namespace": namespace,
            "entries_cleared": count,
            "message": f"Cleared {count} cache entries"
        }

    except Exception as e:
        logger.error(f"Cache clear failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")


@router.get("/metrics", response_model=CacheMetricsResponse)
async def cache_metrics():
    """
    Get semantic cache performance metrics

    Returns hit rates, tier distribution, and performance statistics.
    Target: 60-80% cache hit rate.
    """
    try:
        service = get_semantic_cache_service()
        metrics = service.get_metrics()

        return CacheMetricsResponse(
            total_requests=metrics.get("total_requests", 0),
            exact_hits=metrics.get("exact_hits", 0),
            high_hits=metrics.get("high_hits", 0),
            medium_hits=metrics.get("medium_hits", 0),
            misses=metrics.get("misses", 0),
            embedding_cache_hits=metrics.get("embedding_cache_hits", 0),
            embedding_cache_misses=metrics.get("embedding_cache_misses", 0),
            cache_hit_rate=metrics.get("cache_hit_rate", 0.0),
            tier_distribution=metrics.get("tier_distribution", {})
        )

    except Exception as e:
        logger.error(f"Failed to get cache metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/metrics/reset")
async def reset_metrics():
    """
    Reset cache metrics to zero

    Useful for starting fresh measurements after configuration changes.
    """
    try:
        service = get_semantic_cache_service()
        service.reset_metrics()

        return {
            "success": True,
            "message": "Cache metrics reset successfully"
        }

    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")


@router.get("/health", response_model=CacheHealthResponse)
async def cache_health():
    """
    Check semantic cache health

    Verifies Redis connectivity and returns current configuration.
    """
    try:
        service = get_semantic_cache_service()

        # Try to get Redis client to check connectivity
        redis_connected = False
        try:
            redis = await service._get_redis_client()
            redis.redis_client.ping()
            redis_connected = True
        except Exception:
            pass

        config = service.config

        return CacheHealthResponse(
            status="healthy" if redis_connected else "degraded",
            redis_connected=redis_connected,
            thresholds={
                "exact": config.exact_threshold,
                "high": config.high_threshold,
                "medium": config.medium_threshold
            },
            ttl_settings={
                "search_result_seconds": config.search_result_ttl,
                "embedding_seconds": config.embedding_ttl
            }
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return CacheHealthResponse(
            status="unhealthy",
            redis_connected=False,
            thresholds={},
            ttl_settings={}
        )


@router.get("/config", response_model=CacheConfigResponse)
async def cache_config():
    """
    Get current cache configuration

    Returns all configurable cache parameters.
    """
    try:
        service = get_semantic_cache_service()
        config = service.config

        return CacheConfigResponse(
            exact_threshold=config.exact_threshold,
            high_threshold=config.high_threshold,
            medium_threshold=config.medium_threshold,
            search_result_ttl=config.search_result_ttl,
            embedding_ttl=config.embedding_ttl,
            max_candidates=config.max_candidates,
            metrics_enabled=config.enable_metrics
        )

    except Exception as e:
        logger.error(f"Failed to get config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.get("/tiers")
async def list_tiers():
    """
    List cache match tier definitions

    Returns the similarity thresholds for each tier.
    """
    service = get_semantic_cache_service()
    config = service.config

    return {
        "tiers": [
            {
                "tier": "exact",
                "threshold": f">{config.exact_threshold}",
                "description": "Identical or nearly identical query",
                "action": "Return cached result immediately"
            },
            {
                "tier": "high",
                "threshold": f"{config.high_threshold}-{config.exact_threshold}",
                "description": "Very similar query",
                "action": "Return cached result with high confidence"
            },
            {
                "tier": "medium",
                "threshold": f"{config.medium_threshold}-{config.high_threshold}",
                "description": "Somewhat similar query",
                "action": "Fresh search recommended"
            },
            {
                "tier": "low",
                "threshold": f"<{config.medium_threshold}",
                "description": "Different query",
                "action": "Cache miss, perform new search"
            }
        ],
        "target_hit_rate": "60-80%",
        "usable_tiers": ["exact", "high"]
    }


@router.get("/stats")
async def cache_stats():
    """
    Get comprehensive cache statistics

    Returns detailed statistics including tier breakdown and performance metrics.
    """
    try:
        service = get_semantic_cache_service()
        metrics = service.get_metrics()
        config = service.config

        # Calculate additional stats
        total = metrics.get("total_requests", 0)
        exact = metrics.get("exact_hits", 0)
        high = metrics.get("high_hits", 0)
        medium = metrics.get("medium_hits", 0)
        misses = metrics.get("misses", 0)

        return {
            "cache_performance": {
                "total_requests": total,
                "cache_hit_rate": metrics.get("cache_hit_rate", 0.0),
                "target_hit_rate": "60-80%",
                "meeting_target": 0.6 <= metrics.get("cache_hit_rate", 0.0) <= 0.8
            },
            "tier_breakdown": {
                "exact_hits": exact,
                "high_hits": high,
                "medium_hits": medium,
                "misses": misses,
                "usable_hits": exact + high
            },
            "tier_percentages": {
                "exact": (exact / total * 100) if total > 0 else 0,
                "high": (high / total * 100) if total > 0 else 0,
                "medium": (medium / total * 100) if total > 0 else 0,
                "miss": (misses / total * 100) if total > 0 else 0
            },
            "embedding_cache": {
                "hits": metrics.get("embedding_cache_hits", 0),
                "misses": metrics.get("embedding_cache_misses", 0),
                "hit_rate": (
                    metrics.get("embedding_cache_hits", 0) /
                    (metrics.get("embedding_cache_hits", 0) + metrics.get("embedding_cache_misses", 0))
                    if (metrics.get("embedding_cache_hits", 0) + metrics.get("embedding_cache_misses", 0)) > 0
                    else 0
                )
            },
            "configuration": {
                "thresholds": {
                    "exact": config.exact_threshold,
                    "high": config.high_threshold,
                    "medium": config.medium_threshold
                },
                "ttl_seconds": {
                    "search_results": config.search_result_ttl,
                    "embeddings": config.embedding_ttl
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
