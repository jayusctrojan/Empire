"""
Semantic Cache Service with Tiered Similarity Thresholds (Task 30)

Implements intelligent semantic caching using Redis with tiered similarity thresholds:
- Exact match (>0.98): Return cached result immediately
- High similarity (0.93-0.97): Return cached result with high confidence
- Medium similarity (0.88-0.92): Fresh search recommended
- Low similarity (<0.88): Cache miss, perform new search

Features:
- Tiered semantic similarity matching with configurable thresholds
- Embedding caching to avoid recomputation
- Search result caching with 5-minute TTL
- Cache hit/miss metrics with tier tracking
- Target: 60-80% cache hit rate

Usage:
    from app.services.semantic_cache_service import get_semantic_cache_service

    cache = get_semantic_cache_service()

    # Check cache with semantic matching
    result = await cache.get_semantic_match(query, embedding)

    # Cache search results
    await cache.cache_search_result(query, embedding, results)
"""

import logging
import json
import hashlib
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class CacheMatchTier(str, Enum):
    """Cache match quality tiers based on semantic similarity"""
    EXACT = "exact"           # >0.98 - Identical or nearly identical query
    HIGH = "high"             # 0.93-0.97 - Very similar query, use cached
    MEDIUM = "medium"         # 0.88-0.92 - Somewhat similar, recommend fresh search
    LOW = "low"               # <0.88 - Different query, cache miss
    MISS = "miss"             # No cached entry found


@dataclass
class SemanticCacheConfig:
    """Configuration for semantic cache service"""
    # Similarity thresholds (Task 30 requirements)
    exact_threshold: float = 0.98      # Exact match threshold
    high_threshold: float = 0.93       # High similarity threshold
    medium_threshold: float = 0.88     # Medium similarity threshold

    # TTL settings
    search_result_ttl: int = 300       # 5 minutes for search results
    embedding_ttl: int = 3600          # 1 hour for embeddings
    query_metadata_ttl: int = 1800     # 30 minutes for query metadata

    # Performance settings
    max_candidates: int = 100          # Max cached queries to compare
    enable_metrics: bool = True

    # Cache behavior
    cache_medium_similarity: bool = False  # Don't cache medium matches by default
    promote_high_to_exact: bool = True     # Promote high similarity hits

    @classmethod
    def from_env(cls) -> "SemanticCacheConfig":
        """Create config from environment variables"""
        import os
        return cls(
            exact_threshold=float(os.getenv("SEMANTIC_CACHE_EXACT_THRESHOLD", "0.98")),
            high_threshold=float(os.getenv("SEMANTIC_CACHE_HIGH_THRESHOLD", "0.93")),
            medium_threshold=float(os.getenv("SEMANTIC_CACHE_MEDIUM_THRESHOLD", "0.88")),
            search_result_ttl=int(os.getenv("SEMANTIC_CACHE_RESULT_TTL", "300")),
            embedding_ttl=int(os.getenv("SEMANTIC_CACHE_EMBEDDING_TTL", "3600")),
            max_candidates=int(os.getenv("SEMANTIC_CACHE_MAX_CANDIDATES", "100")),
            enable_metrics=os.getenv("SEMANTIC_CACHE_METRICS", "true").lower() == "true"
        )


@dataclass
class SemanticCacheMetrics:
    """Metrics for semantic cache performance"""
    total_requests: int = 0
    exact_hits: int = 0
    high_hits: int = 0
    medium_hits: int = 0
    misses: int = 0
    embedding_cache_hits: int = 0
    embedding_cache_misses: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate overall cache hit rate (exact + high hits)"""
        if self.total_requests == 0:
            return 0.0
        hits = self.exact_hits + self.high_hits
        return hits / self.total_requests

    @property
    def tier_distribution(self) -> Dict[str, float]:
        """Get distribution of cache tiers"""
        total = self.total_requests or 1
        return {
            "exact": self.exact_hits / total,
            "high": self.high_hits / total,
            "medium": self.medium_hits / total,
            "miss": self.misses / total
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_requests": self.total_requests,
            "exact_hits": self.exact_hits,
            "high_hits": self.high_hits,
            "medium_hits": self.medium_hits,
            "misses": self.misses,
            "embedding_cache_hits": self.embedding_cache_hits,
            "embedding_cache_misses": self.embedding_cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "tier_distribution": self.tier_distribution
        }


@dataclass
class SemanticCacheResult:
    """Result of semantic cache lookup"""
    tier: CacheMatchTier
    similarity: float
    data: Optional[Dict[str, Any]] = None
    original_query: Optional[str] = None
    cached_at: Optional[str] = None
    lookup_time_ms: float = 0.0

    @property
    def is_usable(self) -> bool:
        """Check if cached result should be used (exact or high similarity)"""
        return self.tier in (CacheMatchTier.EXACT, CacheMatchTier.HIGH)

    @property
    def needs_fresh_search(self) -> bool:
        """Check if fresh search is recommended"""
        return self.tier in (CacheMatchTier.MEDIUM, CacheMatchTier.LOW, CacheMatchTier.MISS)


class SemanticCacheService:
    """
    Semantic cache service with tiered similarity thresholds

    Implements Task 30: Semantic Caching with Redis
    Target: 60-80% cache hit rate with <200ms lookup time
    """

    def __init__(
        self,
        config: Optional[SemanticCacheConfig] = None,
        redis_client: Optional[Any] = None,
        embedding_service: Optional[Any] = None
    ):
        """
        Initialize semantic cache service

        Args:
            config: Cache configuration
            redis_client: Optional Redis client (for testing)
            embedding_service: Optional embedding service (for testing)
        """
        self.config = config or SemanticCacheConfig.from_env()
        self._redis_client = redis_client
        self._embedding_service = embedding_service
        self.metrics = SemanticCacheMetrics() if self.config.enable_metrics else None

        logger.info(
            f"Initialized SemanticCacheService with thresholds: "
            f"exact={self.config.exact_threshold}, "
            f"high={self.config.high_threshold}, "
            f"medium={self.config.medium_threshold}"
        )

    async def _get_redis_client(self):
        """Lazy load Redis client"""
        if self._redis_client is None:
            from app.services.redis_cache_service import get_redis_cache_service
            self._redis_client = get_redis_cache_service()
        return self._redis_client

    async def _get_embedding_service(self):
        """Lazy load embedding service"""
        if self._embedding_service is None:
            from app.services.embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    def _hash_query(self, query: str) -> str:
        """Generate hash for exact match lookup"""
        return hashlib.sha256(query.lower().strip().encode('utf-8')).hexdigest()[:16]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    def _classify_similarity(self, similarity: float) -> CacheMatchTier:
        """Classify similarity score into cache tier"""
        if similarity >= self.config.exact_threshold:
            return CacheMatchTier.EXACT
        elif similarity >= self.config.high_threshold:
            return CacheMatchTier.HIGH
        elif similarity >= self.config.medium_threshold:
            return CacheMatchTier.MEDIUM
        else:
            return CacheMatchTier.LOW

    async def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get cached embedding for text

        Args:
            text: Text to get embedding for

        Returns:
            Cached embedding vector or None
        """
        try:
            redis = await self._get_redis_client()
            cache_key = f"emb:{self._hash_query(text)}"  # noqa: F841

            cached = redis.get_cached_embedding(text)

            if cached:
                if self.metrics:
                    self.metrics.embedding_cache_hits += 1
                logger.debug(f"Embedding cache hit for: {text[:50]}")
                return cached

            if self.metrics:
                self.metrics.embedding_cache_misses += 1
            return None

        except Exception as e:
            logger.error(f"Error getting cached embedding: {e}")
            return None

    async def cache_embedding(self, text: str, embedding: List[float]) -> bool:
        """
        Cache embedding for text

        Args:
            text: Text that was embedded
            embedding: Embedding vector

        Returns:
            True if cached successfully
        """
        try:
            redis = await self._get_redis_client()
            return redis.cache_embedding(text, embedding)
        except Exception as e:
            logger.error(f"Error caching embedding: {e}")
            return False

    async def get_or_create_embedding(self, text: str) -> Tuple[List[float], bool]:
        """
        Get embedding from cache or generate new one

        Args:
            text: Text to embed

        Returns:
            Tuple of (embedding, from_cache)
        """
        # Try cache first
        cached = await self.get_cached_embedding(text)
        if cached:
            return cached, True

        # Generate new embedding
        try:
            embedding_service = await self._get_embedding_service()
            result = await embedding_service.generate_embedding(text)
            embedding = result.embedding

            # Cache for future use
            await self.cache_embedding(text, embedding)

            return embedding, False
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def get_semantic_match(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        namespace: str = "search"
    ) -> SemanticCacheResult:
        """
        Find semantically similar cached query result

        Args:
            query: Search query
            query_embedding: Optional pre-computed embedding
            namespace: Cache namespace

        Returns:
            SemanticCacheResult with tier and data
        """
        start_time = time.time()

        if self.metrics:
            self.metrics.total_requests += 1

        try:
            redis = await self._get_redis_client()

            # Step 1: Try exact hash match first (fastest)
            exact_key = f"{namespace}:exact:{self._hash_query(query)}"  # noqa: F841
            exact_match = redis.get_cached_query_result(query)

            if exact_match:
                lookup_time = (time.time() - start_time) * 1000
                if self.metrics:
                    self.metrics.exact_hits += 1

                logger.info(f"Exact cache hit for query: {query[:50]}")
                return SemanticCacheResult(
                    tier=CacheMatchTier.EXACT,
                    similarity=1.0,
                    data=exact_match,
                    original_query=query,
                    lookup_time_ms=lookup_time
                )

            # Step 2: Semantic similarity search
            if query_embedding is None:
                query_embedding, from_cache = await self.get_or_create_embedding(query)

            query_vec = np.array(query_embedding)

            # Get cached queries with embeddings
            pattern = f"{namespace}:sem:*"
            cached_keys = await redis.scan_keys(pattern, count=self.config.max_candidates)

            best_match = None
            best_similarity = 0.0

            for key in cached_keys:
                try:
                    cached_data = redis.get(key)
                    if not cached_data or 'embedding' not in cached_data:
                        continue

                    cached_embedding = np.array(cached_data['embedding'])
                    similarity = self._cosine_similarity(query_vec, cached_embedding)

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = cached_data
                except Exception as e:
                    logger.warning(f"Error comparing cached query: {e}")
                    continue

            lookup_time = (time.time() - start_time) * 1000

            if best_match is None:
                if self.metrics:
                    self.metrics.misses += 1
                return SemanticCacheResult(
                    tier=CacheMatchTier.MISS,
                    similarity=0.0,
                    lookup_time_ms=lookup_time
                )

            # Classify the match tier
            tier = self._classify_similarity(best_similarity)

            # Update metrics
            if self.metrics:
                if tier == CacheMatchTier.EXACT:
                    self.metrics.exact_hits += 1
                elif tier == CacheMatchTier.HIGH:
                    self.metrics.high_hits += 1
                elif tier == CacheMatchTier.MEDIUM:
                    self.metrics.medium_hits += 1
                else:
                    self.metrics.misses += 1

            # Determine if result is usable based on tier
            is_usable_tier = tier in (CacheMatchTier.EXACT, CacheMatchTier.HIGH)

            logger.info(
                f"Semantic cache {tier.value} (similarity={best_similarity:.3f}) "
                f"for query: {query[:50]}"
            )

            return SemanticCacheResult(
                tier=tier,
                similarity=best_similarity,
                data=best_match.get('result') if is_usable_tier else None,
                original_query=best_match.get('query'),
                cached_at=best_match.get('cached_at'),
                lookup_time_ms=lookup_time
            )

        except Exception as e:
            logger.error(f"Error in semantic cache lookup: {e}", exc_info=True)
            if self.metrics:
                self.metrics.misses += 1
            return SemanticCacheResult(
                tier=CacheMatchTier.MISS,
                similarity=0.0,
                lookup_time_ms=(time.time() - start_time) * 1000
            )

    async def cache_search_result(
        self,
        query: str,
        result: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        namespace: str = "search"
    ) -> bool:
        """
        Cache search result with embedding for semantic matching

        Args:
            query: Search query
            result: Search result to cache
            embedding: Optional pre-computed query embedding
            namespace: Cache namespace

        Returns:
            True if cached successfully
        """
        try:
            redis = await self._get_redis_client()

            # Get or generate embedding
            if embedding is None:
                embedding, _ = await self.get_or_create_embedding(query)

            # Cache data structure
            cache_data = {
                "query": query,
                "result": result,
                "embedding": embedding,
                "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

            # Store for exact match lookup
            exact_key = f"{namespace}:exact:{self._hash_query(query)}"  # noqa: F841
            redis.cache_query_result(query, result)

            # Store for semantic search
            sem_key = f"{namespace}:sem:{self._hash_query(query)}"
            redis.set(sem_key, cache_data, ttl=self.config.search_result_ttl)

            logger.info(f"Cached search result for query: {query[:50]}")
            return True

        except Exception as e:
            logger.error(f"Error caching search result: {e}", exc_info=True)
            return False

    async def invalidate_query(self, query: str, namespace: str = "search") -> bool:
        """
        Invalidate cached result for specific query

        Args:
            query: Query to invalidate
            namespace: Cache namespace

        Returns:
            True if invalidated
        """
        try:
            redis = await self._get_redis_client()

            exact_key = f"{namespace}:exact:{self._hash_query(query)}"  # noqa: F841
            sem_key = f"{namespace}:sem:{self._hash_query(query)}"  # noqa: F841

            redis.invalidate_cache(query, key_type="query")

            logger.info(f"Invalidated cache for query: {query[:50]}")
            return True

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False

    async def clear_namespace(self, namespace: str = "search") -> int:
        """
        Clear all cached entries in namespace

        Args:
            namespace: Cache namespace to clear

        Returns:
            Number of entries cleared
        """
        try:
            redis = await self._get_redis_client()

            pattern = f"{namespace}:*"
            keys = await redis.scan_keys(pattern, count=10000)

            for key in keys:
                redis.redis_client.delete(key)

            logger.info(f"Cleared {len(keys)} entries from namespace: {namespace}")
            return len(keys)

        except Exception as e:
            logger.error(f"Error clearing namespace: {e}")
            return 0

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        if self.metrics:
            return self.metrics.to_dict()
        return {
            "total_requests": 0,
            "cache_hit_rate": 0.0,
            "message": "Metrics not enabled"
        }

    def reset_metrics(self):
        """Reset cache metrics"""
        if self.metrics:
            self.metrics = SemanticCacheMetrics()
            logger.info("Reset semantic cache metrics")


# Singleton instance
_semantic_cache_service: Optional[SemanticCacheService] = None


def get_semantic_cache_service(
    config: Optional[SemanticCacheConfig] = None
) -> SemanticCacheService:
    """
    Get or create singleton semantic cache service instance

    Args:
        config: Optional cache configuration

    Returns:
        SemanticCacheService instance
    """
    global _semantic_cache_service

    if _semantic_cache_service is None:
        _semantic_cache_service = SemanticCacheService(config=config)

    return _semantic_cache_service


def reset_semantic_cache_service():
    """Reset singleton for testing"""
    global _semantic_cache_service
    _semantic_cache_service = None
