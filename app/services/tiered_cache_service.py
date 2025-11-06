"""
Tiered Cache Service (L1: Redis, L2: PostgreSQL)

Implements cache-aside pattern with fallback from Redis to PostgreSQL.

Features:
- L1 (Redis): Fast, volatile cache with 5-minute TTL
- L2 (PostgreSQL): Persistent cache with 60-minute TTL
- Automatic promotion from L2 to L1 on L2 hits
- Graceful fallback on L1 failures
- Semantic threshold filtering
- Metrics aggregation across both levels

Usage:
    from app.services.tiered_cache_service import get_tiered_cache_service

    cache = get_tiered_cache_service()

    # Cache-aside pattern
    result = await cache.get_cached_query_result("query")
    if result is None:
        # Fetch from source
        result = await fetch_from_source("query")
        # Cache in both levels
        await cache.cache_query_result("query", result)
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from app.services.redis_cache_service import (
    RedisCacheService,
    get_redis_cache_service
)
from app.services.postgres_cache_service import (
    PostgresCacheService,
    get_postgres_cache_service
)

logger = logging.getLogger(__name__)


class CacheLevel(str, Enum):
    """Cache level indicator"""
    L1 = "L1"  # Redis
    L2 = "L2"  # PostgreSQL
    NONE = "NONE"  # Cache miss


@dataclass
class CacheLookupResult:
    """Result of cache lookup with metadata"""
    data: Optional[Any]
    cache_level: CacheLevel

    @property
    def is_hit(self) -> bool:
        """Check if cache hit occurred"""
        return self.data is not None and self.cache_level != CacheLevel.NONE


@dataclass
class TieredCacheConfig:
    """Configuration for tiered cache"""
    l1_enabled: bool = True
    l2_enabled: bool = True
    l1_ttl_seconds: int = 300  # 5 minutes
    l2_ttl_seconds: int = 3600  # 60 minutes
    promote_to_l1: bool = True  # Promote L2 hits to L1
    semantic_threshold: float = 0.85

    @classmethod
    def from_env(cls) -> "TieredCacheConfig":
        """Create config from environment variables"""
        import os
        return cls(
            l1_enabled=os.getenv("CACHE_L1_ENABLED", "true").lower() == "true",
            l2_enabled=os.getenv("CACHE_L2_ENABLED", "true").lower() == "true",
            l1_ttl_seconds=int(os.getenv("CACHE_L1_TTL", "300")),
            l2_ttl_seconds=int(os.getenv("CACHE_L2_TTL", "3600")),
            promote_to_l1=os.getenv("CACHE_PROMOTE_TO_L1", "true").lower() == "true",
            semantic_threshold=float(os.getenv("CACHE_SEMANTIC_THRESHOLD", "0.85"))
        )


class TieredCacheService:
    """
    Tiered cache service with L1 (Redis) and L2 (PostgreSQL) fallback

    Implements cache-aside pattern:
    1. Check L1 (Redis)
    2. On L1 miss, check L2 (PostgreSQL)
    3. On L2 hit, optionally promote to L1
    4. On both miss, fetch from source and cache in both levels
    """

    def __init__(
        self,
        config: Optional[TieredCacheConfig] = None,
        redis_cache: Optional[RedisCacheService] = None,
        postgres_cache: Optional[PostgresCacheService] = None
    ):
        """
        Initialize tiered cache service

        Args:
            config: Cache configuration
            redis_cache: Optional Redis cache instance
            postgres_cache: Optional PostgreSQL cache instance
        """
        self.config = config or TieredCacheConfig.from_env()

        # Initialize cache layers
        self.redis_cache = redis_cache or (
            get_redis_cache_service() if self.config.l1_enabled else None
        )
        self.postgres_cache = postgres_cache or (
            get_postgres_cache_service() if self.config.l2_enabled else None
        )

        logger.info(
            f"Initialized TieredCacheService "
            f"(L1: {self.config.l1_enabled}, L2: {self.config.l2_enabled})"
        )

    async def get_cached_query_result(
        self,
        query: str
    ) -> Optional[CacheLookupResult]:
        """
        Retrieve cached query result from tiered cache

        Args:
            query: Search query

        Returns:
            CacheLookupResult with data and cache level
        """
        # Check L1 (Redis)
        if self.config.l1_enabled and self.redis_cache:
            try:
                l1_result = self.redis_cache.get_cached_query_result(query)
                if l1_result is not None:
                    logger.debug(f"L1 cache hit for query: {query[:50]}")
                    return CacheLookupResult(
                        data=l1_result,
                        cache_level=CacheLevel.L1
                    )
            except Exception as e:
                logger.warning(f"L1 cache error, falling back to L2: {e}")

        # Check L2 (PostgreSQL)
        if self.config.l2_enabled and self.postgres_cache:
            try:
                l2_result = await self.postgres_cache.get_cached_query_result(query)
                if l2_result is not None:
                    logger.debug(f"L2 cache hit for query: {query[:50]}")

                    # Promote to L1 if enabled
                    if self.config.promote_to_l1 and self.redis_cache:
                        try:
                            self.redis_cache.cache_query_result(query, l2_result)
                            logger.debug(f"Promoted L2 hit to L1: {query[:50]}")
                        except Exception as e:
                            logger.warning(f"Failed to promote to L1: {e}")

                    return CacheLookupResult(
                        data=l2_result,
                        cache_level=CacheLevel.L2
                    )
            except Exception as e:
                logger.error(f"L2 cache error: {e}")

        # Cache miss
        logger.debug(f"Cache miss for query: {query[:50]}")
        return CacheLookupResult(data=None, cache_level=CacheLevel.NONE)

    async def cache_query_result(
        self,
        query: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Cache query result in both L1 and L2

        Args:
            query: Search query
            result: Query result

        Returns:
            True if cached in at least one level
        """
        success = False

        # Cache in L1 (Redis)
        if self.config.l1_enabled and self.redis_cache:
            try:
                if self.redis_cache.cache_query_result(query, result):
                    success = True
                    logger.debug(f"Cached in L1: {query[:50]}")
            except Exception as e:
                logger.warning(f"Failed to cache in L1: {e}")

        # Cache in L2 (PostgreSQL)
        if self.config.l2_enabled and self.postgres_cache:
            try:
                if await self.postgres_cache.cache_query_result(query, result):
                    success = True
                    logger.debug(f"Cached in L2: {query[:50]}")
            except Exception as e:
                logger.warning(f"Failed to cache in L2: {e}")

        return success

    async def cache_query_result_if_relevant(
        self,
        query: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Cache query result only if it meets semantic threshold

        Args:
            query: Search query
            result: Query result with scores

        Returns:
            True if cached
        """
        # Extract max score
        max_score = result.get("max_score", 0.0)
        if max_score == 0.0 and "results" in result:
            results_list = result["results"]
            if results_list:
                max_score = max(r.get("score", 0.0) for r in results_list)

        # Check threshold
        if max_score < self.config.semantic_threshold:
            logger.debug(
                f"Result score {max_score} below threshold "
                f"{self.config.semantic_threshold}, not caching"
            )
            return False

        # Cache in both levels
        return await self.cache_query_result(query, result)

    async def get_cached_embedding(self, text: str) -> Optional[CacheLookupResult]:
        """
        Retrieve cached embedding from tiered cache

        Args:
            text: Text to get embedding for

        Returns:
            CacheLookupResult with embedding and cache level
        """
        # Check L1 (Redis)
        if self.config.l1_enabled and self.redis_cache:
            try:
                l1_embedding = self.redis_cache.get_cached_embedding(text)
                if l1_embedding is not None:
                    return CacheLookupResult(
                        data=l1_embedding,
                        cache_level=CacheLevel.L1
                    )
            except Exception as e:
                logger.warning(f"L1 embedding cache error: {e}")

        # Check L2 (PostgreSQL)
        if self.config.l2_enabled and self.postgres_cache:
            try:
                l2_embedding = await self.postgres_cache.get_cached_embedding(text)
                if l2_embedding is not None:
                    # Promote to L1
                    if self.config.promote_to_l1 and self.redis_cache:
                        try:
                            self.redis_cache.cache_embedding(text, l2_embedding)
                        except Exception as e:
                            logger.warning(f"Failed to promote embedding to L1: {e}")

                    return CacheLookupResult(
                        data=l2_embedding,
                        cache_level=CacheLevel.L2
                    )
            except Exception as e:
                logger.error(f"L2 embedding cache error: {e}")

        return CacheLookupResult(data=None, cache_level=CacheLevel.NONE)

    async def cache_embedding(self, text: str, embedding: List[float]) -> bool:
        """
        Cache embedding in both L1 and L2

        Args:
            text: Text that was embedded
            embedding: Embedding vector

        Returns:
            True if cached in at least one level
        """
        success = False

        # Cache in L1
        if self.config.l1_enabled and self.redis_cache:
            try:
                if self.redis_cache.cache_embedding(text, embedding):
                    success = True
            except Exception as e:
                logger.warning(f"Failed to cache embedding in L1: {e}")

        # Cache in L2
        if self.config.l2_enabled and self.postgres_cache:
            try:
                if await self.postgres_cache.cache_embedding(text, embedding):
                    success = True
            except Exception as e:
                logger.warning(f"Failed to cache embedding in L2: {e}")

        return success

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics from both cache levels

        Returns:
            Aggregated metrics dictionary
        """
        metrics = {
            "l1": {},
            "l2": {},
            "config": {
                "l1_enabled": self.config.l1_enabled,
                "l2_enabled": self.config.l2_enabled,
                "promote_to_l1": self.config.promote_to_l1
            }
        }

        # Get L1 metrics
        if self.redis_cache:
            try:
                metrics["l1"] = self.redis_cache.get_metrics()
            except Exception as e:
                logger.warning(f"Failed to get L1 metrics: {e}")

        return metrics

    async def cleanup_expired_l2_entries(self) -> int:
        """
        Clean up expired entries from L2 cache

        Returns:
            Count of deleted entries
        """
        if self.config.l2_enabled and self.postgres_cache:
            try:
                return await self.postgres_cache.cleanup_expired()
            except Exception as e:
                logger.error(f"Failed to cleanup L2 cache: {e}")

        return 0


# Singleton instance
_tiered_cache_service: Optional[TieredCacheService] = None


def get_tiered_cache_service(
    config: Optional[TieredCacheConfig] = None
) -> TieredCacheService:
    """
    Get or create singleton tiered cache service instance

    Args:
        config: Optional cache configuration

    Returns:
        TieredCacheService instance
    """
    global _tiered_cache_service

    if _tiered_cache_service is None:
        _tiered_cache_service = TieredCacheService(config=config)

    return _tiered_cache_service
