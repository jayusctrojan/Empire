# app/services/graph_query_cache.py
"""
Redis Caching Service for Graph Queries.

Task 110: Graph Agent - Redis Caching
Feature: 005-graph-agent

Provides caching layer for graph query results to improve performance.
Supports cache key generation, TTL management, and invalidation strategies.
"""

import json
import hashlib
import structlog
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

class CacheKeyPrefix(str, Enum):
    """Cache key prefixes for different query types."""
    CUSTOMER_360 = "graph:customer360"
    DOCUMENT_STRUCTURE = "graph:docstructure"
    GRAPH_RAG = "graph:rag"
    ENTITY = "graph:entity"
    CROSS_REFERENCE = "graph:crossref"


@dataclass
class CacheTTLConfig:
    """TTL configuration for different cache types."""
    # Default TTLs in seconds
    CUSTOMER_360: int = 1800  # 30 minutes - customer data changes less frequently
    DOCUMENT_STRUCTURE: int = 3600  # 1 hour - document structure rarely changes
    GRAPH_RAG: int = 600  # 10 minutes - RAG results can change with new documents
    ENTITY: int = 1800  # 30 minutes
    CROSS_REFERENCE: int = 3600  # 1 hour
    DEFAULT: int = 900  # 15 minutes


# =============================================================================
# CACHE STATISTICS
# =============================================================================

@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    invalidations: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "invalidations": self.invalidations,
            "errors": self.errors,
            "hit_rate": round(self.hit_rate, 4),
        }


# =============================================================================
# GRAPH QUERY CACHE
# =============================================================================

class GraphQueryCache:
    """
    Redis-based caching layer for graph query results.

    Provides transparent caching for Customer 360, Document Structure,
    and Graph-Enhanced RAG queries with configurable TTLs and
    invalidation strategies.
    """

    def __init__(
        self,
        redis_client: Any,
        ttl_config: Optional[CacheTTLConfig] = None,
        enabled: bool = True,
    ):
        """
        Initialize the graph query cache.

        Args:
            redis_client: Redis client instance (sync or async)
            ttl_config: Optional TTL configuration
            enabled: Whether caching is enabled
        """
        self.redis = redis_client
        self.ttl_config = ttl_config or CacheTTLConfig()
        self.enabled = enabled
        self._stats = CacheStats()

        logger.info(
            "GraphQueryCache initialized",
            enabled=enabled,
            default_ttl=self.ttl_config.DEFAULT,
        )

    # =========================================================================
    # CORE CACHE OPERATIONS
    # =========================================================================

    async def get(
        self,
        query_type: str,
        query_params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result for a query.

        Args:
            query_type: Type of query (customer360, docstructure, etc.)
            query_params: Query parameters used to generate cache key

        Returns:
            Cached result if found, None otherwise
        """
        if not self.enabled:
            return None

        try:
            cache_key = self._generate_cache_key(query_type, query_params)

            # Handle both sync and async Redis clients
            if hasattr(self.redis, 'get'):
                if hasattr(self.redis.get, '__await__'):
                    cached = await self.redis.get(cache_key)
                else:
                    cached = self.redis.get(cache_key)
            else:
                cached = None

            if cached:
                self._stats.hits += 1
                logger.debug(
                    "Cache hit",
                    query_type=query_type,
                    cache_key=cache_key[:50],
                )

                # Handle bytes or string
                if isinstance(cached, bytes):
                    cached = cached.decode('utf-8')

                return json.loads(cached)

            self._stats.misses += 1
            logger.debug(
                "Cache miss",
                query_type=query_type,
                cache_key=cache_key[:50],
            )
            return None

        except Exception as e:
            self._stats.errors += 1
            logger.error("Cache get error", error=str(e), query_type=query_type)
            return None

    async def set(
        self,
        query_type: str,
        query_params: Dict[str, Any],
        result: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache a query result.

        Args:
            query_type: Type of query
            query_params: Query parameters used to generate cache key
            result: Result to cache
            ttl: Optional TTL override in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            cache_key = self._generate_cache_key(query_type, query_params)
            ttl_seconds = ttl or self._get_ttl_for_type(query_type)

            # Serialize result
            serialized = json.dumps(result, default=str)

            # Handle both sync and async Redis clients
            if hasattr(self.redis, 'setex'):
                if hasattr(self.redis.setex, '__await__'):
                    await self.redis.setex(cache_key, ttl_seconds, serialized)
                else:
                    self.redis.setex(cache_key, ttl_seconds, serialized)
            elif hasattr(self.redis, 'set'):
                if hasattr(self.redis.set, '__await__'):
                    await self.redis.set(cache_key, serialized, ex=ttl_seconds)
                else:
                    self.redis.set(cache_key, serialized, ex=ttl_seconds)

            self._stats.sets += 1
            logger.debug(
                "Cache set",
                query_type=query_type,
                cache_key=cache_key[:50],
                ttl=ttl_seconds,
            )
            return True

        except Exception as e:
            self._stats.errors += 1
            logger.error("Cache set error", error=str(e), query_type=query_type)
            return False

    async def invalidate(
        self,
        query_type: str,
        query_params: Dict[str, Any],
    ) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            query_type: Type of query
            query_params: Query parameters

        Returns:
            True if invalidated successfully
        """
        if not self.enabled:
            return False

        try:
            cache_key = self._generate_cache_key(query_type, query_params)

            if hasattr(self.redis, 'delete'):
                if hasattr(self.redis.delete, '__await__'):
                    await self.redis.delete(cache_key)
                else:
                    self.redis.delete(cache_key)

            self._stats.invalidations += 1
            logger.debug(
                "Cache invalidated",
                query_type=query_type,
                cache_key=cache_key[:50],
            )
            return True

        except Exception as e:
            self._stats.errors += 1
            logger.error("Cache invalidate error", error=str(e))
            return False

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "graph:customer360:*")

        Returns:
            Number of keys invalidated
        """
        if not self.enabled:
            return 0

        try:
            # Get matching keys
            if hasattr(self.redis, 'keys'):
                if hasattr(self.redis.keys, '__await__'):
                    keys = await self.redis.keys(pattern)
                else:
                    keys = self.redis.keys(pattern)
            else:
                return 0

            if not keys:
                return 0

            # Delete matching keys
            if hasattr(self.redis, 'delete'):
                if hasattr(self.redis.delete, '__await__'):
                    deleted = await self.redis.delete(*keys)
                else:
                    deleted = self.redis.delete(*keys)
            else:
                deleted = 0

            self._stats.invalidations += deleted
            logger.info(
                "Cache pattern invalidated",
                pattern=pattern,
                keys_deleted=deleted,
            )
            return deleted

        except Exception as e:
            self._stats.errors += 1
            logger.error("Cache pattern invalidate error", error=str(e), pattern=pattern)
            return 0

    # =========================================================================
    # ENTITY-SPECIFIC INVALIDATION
    # =========================================================================

    async def invalidate_customer(self, customer_id: str) -> int:
        """
        Invalidate all cache entries for a specific customer.

        Args:
            customer_id: Customer ID

        Returns:
            Number of keys invalidated
        """
        pattern = f"{CacheKeyPrefix.CUSTOMER_360.value}:*{customer_id}*"
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_document(self, document_id: str) -> int:
        """
        Invalidate all cache entries for a specific document.

        Args:
            document_id: Document ID

        Returns:
            Number of keys invalidated
        """
        # Invalidate document structure cache
        doc_pattern = f"{CacheKeyPrefix.DOCUMENT_STRUCTURE.value}:*{document_id}*"
        count1 = await self.invalidate_by_pattern(doc_pattern)

        # Invalidate cross-reference cache
        ref_pattern = f"{CacheKeyPrefix.CROSS_REFERENCE.value}:*{document_id}*"
        count2 = await self.invalidate_by_pattern(ref_pattern)

        # Invalidate RAG cache that might include this document
        rag_pattern = f"{CacheKeyPrefix.GRAPH_RAG.value}:*{document_id}*"
        count3 = await self.invalidate_by_pattern(rag_pattern)

        return count1 + count2 + count3

    async def invalidate_all(self) -> int:
        """
        Invalidate all graph cache entries.

        Returns:
            Number of keys invalidated
        """
        total = 0
        for prefix in CacheKeyPrefix:
            count = await self.invalidate_by_pattern(f"{prefix.value}:*")
            total += count
        return total

    # =========================================================================
    # CACHE KEY GENERATION
    # =========================================================================

    def _generate_cache_key(
        self,
        query_type: str,
        query_params: Dict[str, Any],
    ) -> str:
        """
        Generate deterministic cache key from query parameters.

        Args:
            query_type: Type of query
            query_params: Query parameters

        Returns:
            Cache key string
        """
        # Normalize query type to prefix
        prefix = self._get_prefix_for_type(query_type)

        # Sort keys for deterministic hashing
        sorted_params = self._normalize_params(query_params)
        params_str = json.dumps(sorted_params, sort_keys=True, default=str)

        # Generate hash
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]

        return f"{prefix}:{params_hash}"

    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize parameters for consistent cache key generation.

        Args:
            params: Query parameters

        Returns:
            Normalized parameters
        """
        normalized = {}

        for key, value in params.items():
            # Skip None values
            if value is None:
                continue

            # Convert lists to sorted tuples
            if isinstance(value, list):
                normalized[key] = tuple(sorted(str(v) for v in value))
            # Convert datetime to ISO string
            elif isinstance(value, datetime):
                normalized[key] = value.isoformat()
            # Convert other types to string
            else:
                normalized[key] = value

        return normalized

    def _get_prefix_for_type(self, query_type: str) -> str:
        """Get cache key prefix for query type."""
        type_lower = query_type.lower()

        if "customer" in type_lower or "360" in type_lower:
            return CacheKeyPrefix.CUSTOMER_360.value
        elif "doc" in type_lower or "structure" in type_lower:
            return CacheKeyPrefix.DOCUMENT_STRUCTURE.value
        elif "rag" in type_lower or "enhanced" in type_lower:
            return CacheKeyPrefix.GRAPH_RAG.value
        elif "entity" in type_lower:
            return CacheKeyPrefix.ENTITY.value
        elif "cross" in type_lower or "ref" in type_lower:
            return CacheKeyPrefix.CROSS_REFERENCE.value
        else:
            return f"graph:{type_lower}"

    def _get_ttl_for_type(self, query_type: str) -> int:
        """Get TTL for query type."""
        type_lower = query_type.lower()

        if "customer" in type_lower or "360" in type_lower:
            return self.ttl_config.CUSTOMER_360
        elif "doc" in type_lower or "structure" in type_lower:
            return self.ttl_config.DOCUMENT_STRUCTURE
        elif "rag" in type_lower or "enhanced" in type_lower:
            return self.ttl_config.GRAPH_RAG
        elif "entity" in type_lower:
            return self.ttl_config.ENTITY
        elif "cross" in type_lower or "ref" in type_lower:
            return self.ttl_config.CROSS_REFERENCE
        else:
            return self.ttl_config.DEFAULT

    # =========================================================================
    # STATISTICS AND MONITORING
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._stats.to_dict()

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = CacheStats()


# =============================================================================
# CACHE DECORATOR
# =============================================================================

def cached_graph_query(
    query_type: str,
    ttl: Optional[int] = None,
):
    """
    Decorator for caching graph query results.

    Usage:
        @cached_graph_query("customer360")
        async def get_customer_360(customer_id: str) -> Dict:
            ...

    Args:
        query_type: Type of query for cache key prefix
        ttl: Optional TTL override
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get cache instance from kwargs or global
            cache = kwargs.pop('_cache', None) or _cache_instance

            if not cache or not cache.enabled:
                return await func(*args, **kwargs)

            # Build cache key from function arguments
            cache_params = {
                "func": func.__name__,
                "args": str(args),
                **kwargs,
            }

            # Try to get from cache
            cached_result = await cache.get(query_type, cache_params)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)

            # Cache the result
            if result is not None:
                await cache.set(query_type, cache_params, result, ttl=ttl)

            return result

        return wrapper
    return decorator


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_cache_instance: Optional[GraphQueryCache] = None


def get_graph_query_cache(
    redis_client: Optional[Any] = None,
    ttl_config: Optional[CacheTTLConfig] = None,
    enabled: bool = True,
) -> GraphQueryCache:
    """
    Get or create the GraphQueryCache singleton.

    Args:
        redis_client: Optional Redis client (required on first call)
        ttl_config: Optional TTL configuration
        enabled: Whether caching is enabled

    Returns:
        GraphQueryCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        if redis_client is None:
            # Create a mock cache that does nothing
            logger.warning("No Redis client provided, creating disabled cache")
            enabled = False

        _cache_instance = GraphQueryCache(
            redis_client=redis_client,
            ttl_config=ttl_config,
            enabled=enabled,
        )

    return _cache_instance


def reset_graph_query_cache() -> None:
    """Reset the cache singleton (useful for testing)."""
    global _cache_instance
    _cache_instance = None
