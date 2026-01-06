"""
Empire v7.3 - Source Content Cache Service
Task 69: Caching layer for processed project source content

Provides:
- Content hash-based caching to avoid reprocessing
- Embedding cache for duplicate chunks
- Summary cache for similar content
- TTL-based expiration
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import structlog
import redis
from prometheus_client import Counter, Histogram, Gauge

logger = structlog.get_logger(__name__)

# ============================================================================
# Prometheus Metrics
# ============================================================================

CACHE_HITS = Counter(
    'empire_source_cache_hits_total',
    'Total cache hits for source content',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'empire_source_cache_misses_total',
    'Total cache misses for source content',
    ['cache_type']
)

CACHE_SIZE = Gauge(
    'empire_source_cache_size_bytes',
    'Current size of source cache',
    ['cache_type']
)

CACHE_LATENCY = Histogram(
    'empire_source_cache_latency_seconds',
    'Cache operation latency',
    ['operation', 'cache_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)


# ============================================================================
# Cache Configuration
# ============================================================================

@dataclass
class CacheConfig:
    """Configuration for source content cache"""
    # TTL settings
    content_ttl_hours: int = 24 * 7  # 7 days for extracted content
    summary_ttl_hours: int = 24 * 30  # 30 days for summaries
    embedding_ttl_hours: int = 24 * 30  # 30 days for embeddings

    # Size limits
    max_content_size_bytes: int = 5 * 1024 * 1024  # 5MB max for cached content
    max_embedding_batch_size: int = 100  # Max embeddings per cache entry

    # Similarity thresholds
    summary_similarity_threshold: float = 0.95  # Reuse summary if content 95% similar

    # Cache prefixes
    content_prefix: str = "src:content:"
    summary_prefix: str = "src:summary:"
    embedding_prefix: str = "src:embed:"
    metadata_prefix: str = "src:meta:"


DEFAULT_CONFIG = CacheConfig()


# ============================================================================
# Source Content Cache Service
# ============================================================================

class SourceContentCache:
    """
    Caching service for processed project source content.

    Caches:
    - Extracted content by content hash (avoid re-extraction)
    - Summaries by content hash (avoid re-summarization)
    - Embeddings by chunk hash (avoid re-embedding)

    Uses Redis for distributed caching with TTL-based expiration.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        config: Optional[CacheConfig] = None
    ):
        """
        Initialize the cache service.

        Args:
            redis_url: Redis connection URL (defaults to env var)
            config: Cache configuration
        """
        self.config = config or DEFAULT_CONFIG

        # Get Redis URL from environment
        raw_redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        # Clean URL to remove invalid SSL parameters
        self.redis_url = raw_redis_url.split("?")[0] if "?" in raw_redis_url else raw_redis_url

        # Initialize Redis connection
        try:
            self.redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis.ping()
            self._connected = True
            logger.info("Source content cache initialized", redis_url=self.redis_url[:20] + "...")
        except Exception as e:
            logger.warning(f"Redis connection failed, caching disabled: {e}")
            self.redis = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if cache is connected and available"""
        return self._connected and self.redis is not None

    def _compute_content_hash(self, content: str) -> str:
        """Compute hash of content for cache key"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _compute_chunk_hash(self, chunk: str) -> str:
        """Compute hash of chunk for embedding cache"""
        return hashlib.md5(chunk.encode('utf-8')).hexdigest()

    # =========================================================================
    # Content Cache (Extracted content from sources)
    # =========================================================================

    async def get_cached_content(
        self,
        file_hash: str,
        source_type: str
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Get cached extracted content by file hash.

        Args:
            file_hash: MD5/SHA256 hash of source file/URL
            source_type: Type of source (pdf, youtube, etc.)

        Returns:
            Tuple of (content, metadata) or None if not cached
        """
        if not self.is_connected:
            return None

        try:
            import time
            start = time.time()

            key = f"{self.config.content_prefix}{source_type}:{file_hash}"
            cached = self.redis.get(key)

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="get", cache_type="content").observe(latency)

            if cached:
                CACHE_HITS.labels(cache_type="content").inc()
                data = json.loads(cached)
                logger.debug(
                    "Cache hit for content",
                    file_hash=file_hash[:16],
                    source_type=source_type
                )
                return data.get("content"), data.get("metadata", {})

            CACHE_MISSES.labels(cache_type="content").inc()
            return None

        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    async def cache_content(
        self,
        file_hash: str,
        source_type: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Cache extracted content.

        Args:
            file_hash: Hash of source file/URL
            source_type: Type of source
            content: Extracted content text
            metadata: Extraction metadata

        Returns:
            True if cached successfully
        """
        if not self.is_connected:
            return False

        # Check size limits
        content_size = len(content.encode('utf-8'))
        if content_size > self.config.max_content_size_bytes:
            logger.warning(
                "Content too large to cache",
                size_bytes=content_size,
                max_bytes=self.config.max_content_size_bytes
            )
            return False

        try:
            import time
            start = time.time()

            key = f"{self.config.content_prefix}{source_type}:{file_hash}"
            data = json.dumps({
                "content": content,
                "metadata": metadata,
                "cached_at": datetime.utcnow().isoformat()
            })

            ttl_seconds = self.config.content_ttl_hours * 3600
            self.redis.setex(key, ttl_seconds, data)

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="set", cache_type="content").observe(latency)

            logger.debug(
                "Cached content",
                file_hash=file_hash[:16],
                source_type=source_type,
                size_bytes=content_size
            )
            return True

        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    # =========================================================================
    # Summary Cache
    # =========================================================================

    async def get_cached_summary(
        self,
        content_hash: str
    ) -> Optional[str]:
        """
        Get cached summary by content hash.

        Args:
            content_hash: SHA256 hash of content

        Returns:
            Summary text or None if not cached
        """
        if not self.is_connected:
            return None

        try:
            import time
            start = time.time()

            key = f"{self.config.summary_prefix}{content_hash}"
            cached = self.redis.get(key)

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="get", cache_type="summary").observe(latency)

            if cached:
                CACHE_HITS.labels(cache_type="summary").inc()
                logger.debug("Cache hit for summary", content_hash=content_hash[:16])
                return cached

            CACHE_MISSES.labels(cache_type="summary").inc()
            return None

        except Exception as e:
            logger.error(f"Summary cache get failed: {e}")
            return None

    async def cache_summary(
        self,
        content_hash: str,
        summary: str
    ) -> bool:
        """
        Cache summary for content.

        Args:
            content_hash: SHA256 hash of content
            summary: Generated summary

        Returns:
            True if cached successfully
        """
        if not self.is_connected:
            return False

        try:
            import time
            start = time.time()

            key = f"{self.config.summary_prefix}{content_hash}"
            ttl_seconds = self.config.summary_ttl_hours * 3600
            self.redis.setex(key, ttl_seconds, summary)

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="set", cache_type="summary").observe(latency)

            logger.debug("Cached summary", content_hash=content_hash[:16])
            return True

        except Exception as e:
            logger.error(f"Summary cache set failed: {e}")
            return False

    # =========================================================================
    # Embedding Cache
    # =========================================================================

    async def get_cached_embedding(
        self,
        chunk_hash: str
    ) -> Optional[List[float]]:
        """
        Get cached embedding for a chunk.

        Args:
            chunk_hash: MD5 hash of chunk text

        Returns:
            Embedding vector or None if not cached
        """
        if not self.is_connected:
            return None

        try:
            import time
            start = time.time()

            key = f"{self.config.embedding_prefix}{chunk_hash}"
            cached = self.redis.get(key)

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="get", cache_type="embedding").observe(latency)

            if cached:
                CACHE_HITS.labels(cache_type="embedding").inc()
                return json.loads(cached)

            CACHE_MISSES.labels(cache_type="embedding").inc()
            return None

        except Exception as e:
            logger.error(f"Embedding cache get failed: {e}")
            return None

    async def cache_embedding(
        self,
        chunk_hash: str,
        embedding: List[float]
    ) -> bool:
        """
        Cache embedding for a chunk.

        Args:
            chunk_hash: MD5 hash of chunk text
            embedding: Embedding vector

        Returns:
            True if cached successfully
        """
        if not self.is_connected:
            return False

        try:
            import time
            start = time.time()

            key = f"{self.config.embedding_prefix}{chunk_hash}"
            ttl_seconds = self.config.embedding_ttl_hours * 3600
            self.redis.setex(key, ttl_seconds, json.dumps(embedding))

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="set", cache_type="embedding").observe(latency)

            return True

        except Exception as e:
            logger.error(f"Embedding cache set failed: {e}")
            return False

    async def get_cached_embeddings_batch(
        self,
        chunk_hashes: List[str]
    ) -> Dict[str, Optional[List[float]]]:
        """
        Get cached embeddings for multiple chunks (batch operation).

        Args:
            chunk_hashes: List of chunk hashes

        Returns:
            Dict mapping hash to embedding (None if not cached)
        """
        if not self.is_connected:
            return {h: None for h in chunk_hashes}

        try:
            import time
            start = time.time()

            keys = [f"{self.config.embedding_prefix}{h}" for h in chunk_hashes]
            cached_values = self.redis.mget(keys)

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="mget", cache_type="embedding").observe(latency)

            result = {}
            hits = 0
            for i, (chunk_hash, cached) in enumerate(zip(chunk_hashes, cached_values)):
                if cached:
                    result[chunk_hash] = json.loads(cached)
                    hits += 1
                else:
                    result[chunk_hash] = None

            if hits > 0:
                CACHE_HITS.labels(cache_type="embedding_batch").inc(hits)
            if len(chunk_hashes) - hits > 0:
                CACHE_MISSES.labels(cache_type="embedding_batch").inc(len(chunk_hashes) - hits)

            logger.debug(
                "Batch embedding cache lookup",
                total=len(chunk_hashes),
                hits=hits
            )

            return result

        except Exception as e:
            logger.error(f"Batch embedding cache get failed: {e}")
            return {h: None for h in chunk_hashes}

    async def cache_embeddings_batch(
        self,
        embeddings: Dict[str, List[float]]
    ) -> int:
        """
        Cache multiple embeddings (batch operation).

        Args:
            embeddings: Dict mapping chunk hash to embedding

        Returns:
            Number of embeddings cached
        """
        if not self.is_connected or not embeddings:
            return 0

        try:
            import time
            start = time.time()

            pipe = self.redis.pipeline()
            ttl_seconds = self.config.embedding_ttl_hours * 3600

            for chunk_hash, embedding in embeddings.items():
                key = f"{self.config.embedding_prefix}{chunk_hash}"
                pipe.setex(key, ttl_seconds, json.dumps(embedding))

            pipe.execute()

            latency = time.time() - start
            CACHE_LATENCY.labels(operation="mset", cache_type="embedding").observe(latency)

            logger.debug("Batch cached embeddings", count=len(embeddings))
            return len(embeddings)

        except Exception as e:
            logger.error(f"Batch embedding cache set failed: {e}")
            return 0

    # =========================================================================
    # Cache Statistics
    # =========================================================================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_connected:
            return {"connected": False}

        try:
            info = self.redis.info(section="memory")

            # Count keys by prefix
            content_keys = len(self.redis.keys(f"{self.config.content_prefix}*"))
            summary_keys = len(self.redis.keys(f"{self.config.summary_prefix}*"))
            embedding_keys = len(self.redis.keys(f"{self.config.embedding_prefix}*"))

            return {
                "connected": True,
                "memory_used_bytes": info.get("used_memory", 0),
                "memory_used_human": info.get("used_memory_human", "0B"),
                "keys": {
                    "content": content_keys,
                    "summary": summary_keys,
                    "embedding": embedding_keys,
                    "total": content_keys + summary_keys + embedding_keys
                }
            }

        except Exception as e:
            logger.error(f"Cache stats failed: {e}")
            return {"connected": False, "error": str(e)}

    async def clear_cache(self, cache_type: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            cache_type: Type of cache to clear (content, summary, embedding, or None for all)

        Returns:
            Number of keys deleted
        """
        if not self.is_connected:
            return 0

        try:
            prefixes = {
                "content": self.config.content_prefix,
                "summary": self.config.summary_prefix,
                "embedding": self.config.embedding_prefix,
            }

            if cache_type and cache_type in prefixes:
                pattern = f"{prefixes[cache_type]}*"
                keys = self.redis.keys(pattern)
            else:
                keys = []
                for prefix in prefixes.values():
                    keys.extend(self.redis.keys(f"{prefix}*"))

            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries", cache_type=cache_type or "all")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return 0


# ============================================================================
# Singleton Instance
# ============================================================================

_cache_service: Optional[SourceContentCache] = None


def get_source_content_cache() -> SourceContentCache:
    """Get or create singleton SourceContentCache instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = SourceContentCache()
    return _cache_service
