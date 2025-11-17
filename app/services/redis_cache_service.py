"""
Redis Cache Service for Empire RAG System

Provides L1 caching with semantic thresholds, TTL management, and cache-aside pattern.

Features:
- Query result caching with 5-minute TTL
- Embedding vector caching
- Semantic threshold filtering (only cache high-quality results >= 0.85)
- Cache-aside pattern implementation
- Hit/miss metrics tracking
- Bulk operations support
- Error handling with graceful fallbacks

Usage:
    from app.services.redis_cache_service import get_redis_cache_service

    cache = get_redis_cache_service()

    # Cache query result
    cache.cache_query_result("insurance policy", result)

    # Get cached result
    cached = cache.get_cached_query_result("insurance policy")
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
import redis

logger = logging.getLogger(__name__)


@dataclass
class RedisCacheConfig:
    """Configuration for Redis cache service"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    ttl_seconds: int = 300  # 5 minutes
    semantic_threshold: float = 0.85  # Only cache results with score >= 0.85
    enable_metrics: bool = True
    password: Optional[str] = None

    @classmethod
    def from_env(cls) -> "RedisCacheConfig":
        """Create config from environment variables"""
        import os
        from urllib.parse import urlparse

        # Support REDIS_URL (Upstash format: rediss://default:password@host:port)
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            parsed = urlparse(redis_url)
            return cls(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                db=int(os.getenv("REDIS_DB", "0")),
                ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", "300")),
                semantic_threshold=float(os.getenv("REDIS_SEMANTIC_THRESHOLD", "0.85")),
                enable_metrics=os.getenv("REDIS_ENABLE_METRICS", "true").lower() == "true",
                password=parsed.password
            )

        # Fallback to individual env vars
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", "300")),
            semantic_threshold=float(os.getenv("REDIS_SEMANTIC_THRESHOLD", "0.85")),
            enable_metrics=os.getenv("REDIS_ENABLE_METRICS", "true").lower() == "true",
            password=os.getenv("REDIS_PASSWORD")
        )


@dataclass
class CacheKey:
    """Cache key with metadata"""
    key: str
    key_type: str

    def __str__(self) -> str:
        return self.key


@dataclass
class CacheMetrics:
    """Cache metrics for monitoring"""
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate
        }


class RedisCacheService:
    """
    Redis L1 cache service with semantic thresholds and TTL management

    Implements cache-aside pattern:
    1. Check cache first
    2. On miss, fetch from source
    3. Populate cache
    4. Return result
    """

    def __init__(
        self,
        config: Optional[RedisCacheConfig] = None,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Initialize Redis cache service

        Args:
            config: Cache configuration
            redis_client: Optional pre-configured Redis client
        """
        self.config = config or RedisCacheConfig.from_env()

        # Use provided client or create new one
        if redis_client:
            self.redis_client = redis_client
        else:
            import os
            redis_url = os.getenv("REDIS_URL")

            # If REDIS_URL is provided, use from_url (handles SSL automatically)
            if redis_url:
                self.redis_client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=False,  # We'll handle encoding
                    ssl_cert_reqs=None  # Disable SSL verification for Upstash
                )
            else:
                # Fallback to manual connection
                self.redis_client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    decode_responses=False  # We'll handle encoding
                )

        # Metrics tracking
        self.metrics = CacheMetrics() if self.config.enable_metrics else None

        # Test connection
        try:
            self.redis_client.ping()
            logger.info(
                f"Connected to Redis at {self.config.host}:{self.config.port}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")

    def generate_cache_key(self, identifier: str, key_type: str = "query") -> str:
        """
        Generate a cache key from an identifier

        Args:
            identifier: Query text, document text, etc.
            key_type: Type of key (query, embedding, etc.)

        Returns:
            Hashed cache key
        """
        # Create consistent hash of identifier
        hash_obj = hashlib.sha256(identifier.encode('utf-8'))
        hash_str = hash_obj.hexdigest()[:16]  # Use first 16 chars

        # Format: cache_type:hash
        return f"{key_type}:{hash_str}"

    def cache_query_result(
        self,
        query: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Cache a query result with TTL

        Args:
            query: Search query
            result: Query result dictionary

        Returns:
            True if cached successfully
        """
        try:
            key = self.generate_cache_key(query, key_type="query")

            # Serialize result
            serialized = json.dumps(result)

            # Store with TTL
            self.redis_client.setex(
                key,
                self.config.ttl_seconds,
                serialized.encode('utf-8')
            )

            logger.debug(f"Cached query result: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache query result: {e}")
            return False

    def get_cached_query_result(
        self,
        query: str,
        refresh_ttl: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached query result

        Args:
            query: Search query
            refresh_ttl: Whether to refresh TTL on access

        Returns:
            Cached result or None if not found
        """
        try:
            key = self.generate_cache_key(query, key_type="query")

            # Get from cache
            cached = self.redis_client.get(key)

            if cached is None:
                # Cache miss
                if self.metrics:
                    self.metrics.misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

            # Cache hit
            if self.metrics:
                self.metrics.hits += 1

            # Refresh TTL if requested
            if refresh_ttl and hasattr(self, 'refresh_ttl'):
                self.redis_client.expire(key, self.config.ttl_seconds)

            # Deserialize
            result = json.loads(cached.decode('utf-8'))
            logger.debug(f"Cache hit: {key}")
            return result

        except Exception as e:
            logger.error(f"Failed to get cached query result: {e}")
            if self.metrics:
                self.metrics.misses += 1
            return None

    def cache_query_result_if_relevant(
        self,
        query: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Cache query result only if it meets semantic threshold

        Args:
            query: Search query
            result: Query result with max_score or results with scores

        Returns:
            True if cached (result was relevant enough)
        """
        try:
            # Extract max score from result
            max_score = result.get("max_score", 0.0)

            # If max_score not in result, check first result
            if max_score == 0.0 and "results" in result:
                results_list = result["results"]
                if results_list:
                    max_score = max(
                        r.get("score", 0.0) for r in results_list
                    )

            # Check against threshold
            if max_score < self.config.semantic_threshold:
                logger.debug(
                    f"Result score {max_score} below threshold "
                    f"{self.config.semantic_threshold}, not caching"
                )
                return False

            # Cache the result
            return self.cache_query_result(query, result)

        except Exception as e:
            logger.error(f"Failed to cache result if relevant: {e}")
            return False

    def cache_embedding(self, text: str, embedding: List[float]) -> bool:
        """
        Cache an embedding vector with TTL

        Args:
            text: Text that was embedded
            embedding: Embedding vector

        Returns:
            True if cached successfully
        """
        try:
            key = self.generate_cache_key(text, key_type="embedding")

            # Serialize embedding
            serialized = json.dumps(embedding)

            # Store with TTL
            self.redis_client.setex(
                key,
                self.config.ttl_seconds,
                serialized.encode('utf-8')
            )

            logger.debug(f"Cached embedding: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache embedding: {e}")
            return False

    def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """
        Retrieve cached embedding

        Args:
            text: Text to get embedding for

        Returns:
            Cached embedding or None if not found
        """
        try:
            key = self.generate_cache_key(text, key_type="embedding")

            # Get from cache
            cached = self.redis_client.get(key)

            if cached is None:
                logger.debug(f"Embedding cache miss: {key}")
                return None

            # Deserialize
            embedding = json.loads(cached.decode('utf-8'))
            logger.debug(f"Embedding cache hit: {key}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to get cached embedding: {e}")
            return None

    def invalidate_cache(self, identifier: str, key_type: str = "query") -> bool:
        """
        Invalidate (delete) a cache entry

        Args:
            identifier: Query, text, etc.
            key_type: Type of cache key

        Returns:
            True if deleted successfully
        """
        try:
            key = self.generate_cache_key(identifier, key_type=key_type)
            deleted = self.redis_client.delete(key)
            logger.debug(f"Invalidated cache: {key}")
            return deleted > 0

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache metrics

        Returns:
            Metrics dictionary
        """
        if self.metrics:
            return self.metrics.to_dict()
        return {"hits": 0, "misses": 0, "hit_rate": 0.0}

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache information and stats

        Returns:
            Cache information dictionary
        """
        try:
            info = self.redis_client.info()
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "connected": True
            }
        except Exception as e:
            logger.error(f"Failed to get cache info: {e}")
            return {"connected": False, "error": str(e)}

    def cache_multiple(
        self,
        items: List[Tuple[str, Dict[str, Any]]],
        key_type: str = "query"
    ) -> List[bool]:
        """
        Cache multiple items in batch

        Args:
            items: List of (identifier, result) tuples
            key_type: Type of cache keys

        Returns:
            List of success statuses
        """
        results = []

        for identifier, result in items:
            if key_type == "query":
                success = self.cache_query_result(identifier, result)
            elif key_type == "embedding":
                success = self.cache_embedding(identifier, result)
            else:
                success = False

            results.append(success)

        logger.info(f"Cached {sum(results)}/{len(items)} items")
        return results

    # ============================================================================
    # Generic Cache Interface (for compatibility with TieredCacheService)
    # ============================================================================

    def get(self, key: str) -> Optional[Any]:
        """
        Generic get method for cache compatibility

        Args:
            key: Cache key

        Returns:
            Cached value if found, else None
        """
        try:
            if not self.redis_client:
                return None

            cached = self.redis_client.get(key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode cached value for key: {key}")
                    return None

            return None

        except Exception as e:
            logger.error(f"Failed to get cached value for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Generic set method for cache compatibility

        Args:
            key: Cache key
            value: Data to cache
            ttl: Time to live in seconds (uses config default if None)

        Returns:
            True if cached successfully
        """
        try:
            if not self.redis_client:
                return False

            cache_ttl = ttl if ttl is not None else self.config.default_ttl
            serialized = json.dumps(value)

            self.redis_client.setex(
                key,
                cache_ttl,
                serialized
            )

            return True

        except Exception as e:
            logger.error(f"Failed to cache value for key {key}: {e}")
            return False

    async def scan_keys(self, pattern: str, count: int = 100) -> List[str]:
        """
        Scan Redis for keys matching pattern

        Args:
            pattern: Key pattern (e.g., "query:*")
            count: Maximum number of keys to return

        Returns:
            List of matching keys
        """
        try:
            if not self.redis_client:
                return []

            keys = []
            cursor = 0

            while len(keys) < count:
                cursor, batch = self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=min(count - len(keys), 100)
                )

                keys.extend([k.decode('utf-8') if isinstance(k, bytes) else k for k in batch])

                if cursor == 0:  # Scan complete
                    break

            return keys[:count]

        except Exception as e:
            logger.error(f"Failed to scan keys with pattern {pattern}: {e}")
            return []


# Singleton instance
_redis_cache_service: Optional[RedisCacheService] = None


def get_redis_cache_service(
    config: Optional[RedisCacheConfig] = None
) -> RedisCacheService:
    """
    Get or create singleton Redis cache service instance

    Args:
        config: Optional cache configuration

    Returns:
        RedisCacheService instance
    """
    global _redis_cache_service

    if _redis_cache_service is None:
        _redis_cache_service = RedisCacheService(config=config)

    return _redis_cache_service
