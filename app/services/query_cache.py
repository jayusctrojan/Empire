"""
Query Result Caching Service with Semantic Similarity

Task 43.3 - Performance Optimization

Caches query results in Redis using semantic similarity matching.
If a new query is semantically similar to a cached query (cosine > 0.95),
return the cached result instead of reprocessing.

Features:
- Exact match caching (hash-based)
- Semantic similarity search (embedding-based)
- Configurable similarity threshold
- TTL management
- Cache hit/miss tracking

Usage:
    from app.services.query_cache import cached_query

    @cached_query(cache_namespace="adaptive", ttl=1800)
    async def adaptive_query_endpoint(request: QueryRequest):
        # Expensive query processing
        return result
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class QueryCacheService:
    """Service for caching query results with semantic similarity matching"""

    def __init__(self):
        """Initialize query cache service"""
        # Lazy import to avoid circular dependencies
        from app.services.tiered_cache_service import get_tiered_cache_service

        self.cache = get_tiered_cache_service()
        self.similarity_threshold = 0.95  # High threshold for cache hits
        self.embedding_service = None  # Lazy loaded

        logger.info("Initialized QueryCacheService with similarity threshold 0.95")

    async def _get_embedding_service(self):
        """Lazy load embedding service"""
        if self.embedding_service is None:
            from app.services.embedding_service import get_embedding_service
            self.embedding_service = get_embedding_service()
        return self.embedding_service

    async def get_cached_result(
        self,
        query: str,
        cache_namespace: str = "query"
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result for semantically similar query

        Args:
            query: User query string
            cache_namespace: Cache namespace (e.g., "adaptive", "auto")

        Returns:
            Cached result if similar query found, else None
        """
        try:
            # Try exact match first (L1/L2 cache)
            cache_key = f"{cache_namespace}:{self._hash_query(query)}"

            exact_match = await self.cache.get(cache_key)
            if exact_match:
                logger.info(
                    f"Exact cache hit for query: {query[:50]}",
                    extra={"cache_type": "exact", "namespace": cache_namespace}
                )
                return exact_match

            # Semantic similarity search (if embedding service available)
            try:
                embedding_service = await self._get_embedding_service()

                # Generate embedding for query
                embedding_result = await embedding_service.generate_embedding(query)
                # Extract embedding vector from EmbeddingResult
                query_embedding = np.array(embedding_result.embedding)

                # Search for similar queries in cache
                similar_result = await self._find_similar_cached_query(
                    query_embedding,
                    cache_namespace
                )

                if similar_result:
                    logger.info(
                        f"Semantic cache hit for query: {query[:50]} "
                        f"(similarity: {similar_result['similarity']:.3f})",
                        extra={
                            "cache_type": "semantic",
                            "namespace": cache_namespace,
                            "similarity": similar_result['similarity']
                        }
                    )
                    return similar_result['result']

            except Exception as e:
                logger.warning(f"Semantic search failed, continuing: {e}")

            return None

        except Exception as e:
            logger.error(f"Failed to get cached result: {e}", exc_info=True)
            return None

    async def cache_result(
        self,
        query: str,
        result: Dict[str, Any],
        cache_namespace: str = "query",
        ttl: int = 3600  # 1 hour default
    ):
        """
        Cache query result with embedding for semantic search

        Args:
            query: User query string
            result: Query result to cache
            cache_namespace: Cache namespace
            ttl: Time to live in seconds
        """
        try:
            cache_key = f"{cache_namespace}:{self._hash_query(query)}"

            # Try to get embedding, but don't fail if unavailable
            embedding = None
            try:
                embedding_service = await self._get_embedding_service()
                embedding_result = await embedding_service.generate_embedding(query)
                # EmbeddingResult.embedding is already a List[float], no need for .tolist()
                embedding = embedding_result.embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding for cache, storing without: {e}")

            # Store result with embedding (if available)
            cache_data = {
                "query": query,
                "result": result,
                "cached_at": datetime.utcnow().isoformat()
            }

            if embedding:
                cache_data["embedding"] = embedding

            await self.cache.set(cache_key, cache_data, ttl=ttl)

            logger.info(
                f"Cached query result: {query[:50]} (TTL: {ttl}s, has_embedding: {embedding is not None})"
            )

        except Exception as e:
            logger.error(f"Failed to cache result: {e}", exc_info=True)

    async def _find_similar_cached_query(
        self,
        query_embedding: np.ndarray,
        cache_namespace: str,
        max_candidates: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Find cached query with similar embedding

        Args:
            query_embedding: Query embedding vector
            cache_namespace: Cache namespace to search
            max_candidates: Maximum cached queries to compare

        Returns:
            Similar cached result if found, else None
        """
        try:
            # Get all cached queries in namespace (limited to max_candidates)
            pattern = f"{cache_namespace}:*"

            # Use Redis SCAN to get keys (if Redis available)
            if hasattr(self.cache, 'redis_cache') and self.cache.redis_cache:
                cached_keys = await self.cache.redis_cache.scan_keys(
                    pattern,
                    count=max_candidates
                )
            else:
                # Fallback: no semantic search without Redis
                return None

            best_match = None
            best_similarity = 0.0

            for key in cached_keys[:max_candidates]:  # Limit comparisons
                cached_data = await self.cache.get(key)

                if not cached_data or 'embedding' not in cached_data:
                    continue

                # Calculate cosine similarity
                cached_embedding = np.array(cached_data['embedding'])
                similarity = self._cosine_similarity(query_embedding, cached_embedding)

                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = {
                        'result': cached_data['result'],
                        'similarity': similarity,
                        'original_query': cached_data['query'],
                        'cached_at': cached_data.get('cached_at')
                    }

            if best_match:
                logger.info(
                    f"Found similar query (similarity: {best_similarity:.3f}): "
                    f"{best_match['original_query'][:50]}"
                )

            return best_match

        except Exception as e:
            logger.error(f"Failed to find similar query: {e}", exc_info=True)
            return None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity (0.0 to 1.0)
        """
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return float(dot_product / (norm_a * norm_b))

        except Exception as e:
            logger.error(f"Failed to calculate cosine similarity: {e}")
            return 0.0

    def _hash_query(self, query: str) -> str:
        """
        Generate hash for query

        Args:
            query: Query string

        Returns:
            MD5 hash string
        """
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    async def invalidate_cache(self, cache_namespace: Optional[str] = None):
        """
        Invalidate cache entries

        Args:
            cache_namespace: Optional namespace to clear (clears all if None)
        """
        try:
            if cache_namespace:
                pattern = f"{cache_namespace}:*"
                logger.info(f"Invalidating cache namespace: {cache_namespace}")
            else:
                pattern = "query:*"
                logger.info("Invalidating all query cache")

            # Use Redis SCAN and delete if available
            if hasattr(self.cache, 'redis_cache') and self.cache.redis_cache:
                keys = await self.cache.redis_cache.scan_keys(pattern, count=1000)
                for key in keys:
                    await self.cache.delete(key)

                logger.info(f"Invalidated {len(keys)} cache entries")

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}", exc_info=True)


# Singleton
_query_cache_service: Optional[QueryCacheService] = None


def get_query_cache_service() -> QueryCacheService:
    """
    Get or create singleton query cache service

    Returns:
        QueryCacheService instance
    """
    global _query_cache_service
    if _query_cache_service is None:
        _query_cache_service = QueryCacheService()
    return _query_cache_service


def cached_query(cache_namespace: str = "query", ttl: int = 3600):
    """
    Decorator for caching query results with semantic similarity

    Args:
        cache_namespace: Cache namespace (e.g., "adaptive", "auto", "faceted")
        ttl: Time to live in seconds (default: 1 hour)

    Returns:
        Decorated function with caching

    Example:
        @cached_query(cache_namespace="adaptive", ttl=1800)
        async def adaptive_query_endpoint(request: QueryRequest):
            # Expensive query processing
            return result

        # Cached responses will include 'from_cache' metadata
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_service = get_query_cache_service()

            # Extract query from request (first arg or 'request' kwarg)
            request = kwargs.get('request') or (args[0] if args else None)

            # Only cache if request has 'query' attribute
            if not request or not hasattr(request, 'query'):
                logger.debug(f"No cacheable request for {func.__name__}, executing normally")
                return await func(*args, **kwargs)

            query_text = request.query

            # Try cache first
            cached_result = await cache_service.get_cached_result(
                query_text,
                cache_namespace=cache_namespace
            )

            if cached_result:
                # Reconstruct response from cached dict
                # Support both dict results and Pydantic models
                logger.info(f"Cache HIT for query: {query_text[:50]}")

                # If result is a dict, add metadata directly
                if isinstance(cached_result, dict) and 'result' in cached_result:
                    # Extract the actual result from cache wrapper
                    actual_result = cached_result['result']

                    # If it's a dict, add metadata
                    if isinstance(actual_result, dict):
                        actual_result['from_cache'] = True
                        actual_result['cache_namespace'] = cache_namespace
                        return actual_result

                    # If it's serialized model data, reconstruct it
                    return actual_result

                return cached_result

            # Cache miss - execute function
            logger.info(f"Cache MISS for query: {query_text[:50]}")
            result = await func(*args, **kwargs)

            # Serialize Pydantic models before caching
            cache_data = result
            if hasattr(result, 'model_dump'):  # Pydantic v2
                cache_data = result.model_dump()
            elif hasattr(result, 'dict'):  # Pydantic v1
                cache_data = result.dict()

            # Cache result (async, don't await to avoid blocking response)
            try:
                await cache_service.cache_result(
                    query_text,
                    cache_data,
                    cache_namespace=cache_namespace,
                    ttl=ttl
                )
            except Exception as e:
                logger.warning(f"Failed to cache result, continuing: {e}")

            # Add cache miss metadata if result is dict-like
            if isinstance(result, dict):
                result['from_cache'] = False
                result['cache_namespace'] = cache_namespace
            elif hasattr(result, '__dict__'):
                # For Pydantic models, set attributes if possible
                try:
                    result.from_cache = False
                    result.cache_namespace = cache_namespace
                except Exception:
                    pass  # Some models may be frozen

            return result

        return wrapper
    return decorator
