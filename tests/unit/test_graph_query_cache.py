# tests/unit/test_graph_query_cache.py
"""
Unit tests for Graph Query Cache Service.

Task 110: Graph Agent - Redis Caching
Feature: 005-graph-agent

Tests cache operations, key generation, TTL management, and invalidation.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.graph_query_cache import (
    GraphQueryCache,
    CacheKeyPrefix,
    CacheTTLConfig,
    CacheStats,
    get_graph_query_cache,
    reset_graph_query_cache,
    cached_graph_query,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.setex = MagicMock(return_value=True)
    redis.delete = MagicMock(return_value=1)
    redis.keys = MagicMock(return_value=[])
    return redis


@pytest.fixture
def async_mock_redis():
    """Create an async mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.keys = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def cache(mock_redis):
    """Create a GraphQueryCache instance with mock Redis."""
    reset_graph_query_cache()
    return GraphQueryCache(redis_client=mock_redis, enabled=True)


@pytest.fixture
def async_cache(async_mock_redis):
    """Create a GraphQueryCache instance with async mock Redis."""
    reset_graph_query_cache()
    return GraphQueryCache(redis_client=async_mock_redis, enabled=True)


@pytest.fixture
def disabled_cache(mock_redis):
    """Create a disabled GraphQueryCache instance."""
    reset_graph_query_cache()
    return GraphQueryCache(redis_client=mock_redis, enabled=False)


# =============================================================================
# CACHE GET TESTS
# =============================================================================

class TestCacheGet:
    """Tests for cache get operations."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache):
        """Test that cache miss returns None."""
        result = await cache.get("customer360", {"customer_id": "cust_001"})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_data(self, cache, mock_redis):
        """Test that cache hit returns cached data."""
        cached_data = {"customer": {"id": "cust_001", "name": "Acme Corp"}}
        mock_redis.get.return_value = json.dumps(cached_data).encode('utf-8')

        result = await cache.get("customer360", {"customer_id": "cust_001"})

        assert result == cached_data
        assert cache._stats.hits == 1

    @pytest.mark.asyncio
    async def test_cache_hit_with_string_response(self, cache, mock_redis):
        """Test cache hit with string (not bytes) response."""
        cached_data = {"sections": [{"id": "sec1", "title": "Introduction"}]}
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await cache.get("docstructure", {"doc_id": "doc_001"})

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_disabled_returns_none(self, disabled_cache):
        """Test that disabled cache always returns None."""
        result = await disabled_cache.get("customer360", {"customer_id": "cust_001"})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_error_handling(self, cache, mock_redis):
        """Test that cache get errors are handled gracefully."""
        mock_redis.get.side_effect = Exception("Redis connection error")

        result = await cache.get("customer360", {"customer_id": "cust_001"})

        assert result is None
        assert cache._stats.errors == 1


# =============================================================================
# CACHE SET TESTS
# =============================================================================

class TestCacheSet:
    """Tests for cache set operations."""

    @pytest.mark.asyncio
    async def test_cache_set_success(self, cache, mock_redis):
        """Test successful cache set."""
        data = {"customer": {"id": "cust_001", "name": "Acme Corp"}}

        result = await cache.set(
            "customer360",
            {"customer_id": "cust_001"},
            data,
        )

        assert result is True
        assert cache._stats.sets == 1
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_set_with_custom_ttl(self, cache, mock_redis):
        """Test cache set with custom TTL."""
        data = {"result": "test"}

        await cache.set(
            "customer360",
            {"id": "123"},
            data,
            ttl=300,  # 5 minutes
        )

        # Verify TTL was passed
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 300  # TTL should be 300 seconds

    @pytest.mark.asyncio
    async def test_cache_set_disabled(self, disabled_cache):
        """Test that set on disabled cache returns False."""
        result = await disabled_cache.set(
            "customer360",
            {"id": "123"},
            {"data": "test"},
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_set_error_handling(self, cache, mock_redis):
        """Test cache set error handling."""
        mock_redis.setex.side_effect = Exception("Redis write error")

        result = await cache.set(
            "customer360",
            {"id": "123"},
            {"data": "test"},
        )

        assert result is False
        assert cache._stats.errors == 1

    @pytest.mark.asyncio
    async def test_cache_set_with_datetime(self, cache, mock_redis):
        """Test cache set with datetime values."""
        data = {"created_at": datetime.now(), "name": "Test"}

        result = await cache.set(
            "customer360",
            {"id": "123"},
            data,
        )

        assert result is True


# =============================================================================
# CACHE INVALIDATION TESTS
# =============================================================================

class TestCacheInvalidation:
    """Tests for cache invalidation operations."""

    @pytest.mark.asyncio
    async def test_invalidate_single_key(self, cache, mock_redis):
        """Test invalidating a single cache entry."""
        result = await cache.invalidate(
            "customer360",
            {"customer_id": "cust_001"},
        )

        assert result is True
        assert cache._stats.invalidations == 1
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern(self, cache, mock_redis):
        """Test invalidating by pattern."""
        mock_redis.keys.return_value = [
            b"graph:customer360:abc123",
            b"graph:customer360:def456",
        ]
        mock_redis.delete.return_value = 2

        count = await cache.invalidate_by_pattern("graph:customer360:*")

        assert count == 2
        mock_redis.keys.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern_no_matches(self, cache, mock_redis):
        """Test pattern invalidation with no matching keys."""
        mock_redis.keys.return_value = []

        count = await cache.invalidate_by_pattern("graph:nonexistent:*")

        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_customer(self, cache, mock_redis):
        """Test invalidating all cache for a customer."""
        mock_redis.keys.return_value = [b"graph:customer360:key1"]
        mock_redis.delete.return_value = 1

        count = await cache.invalidate_customer("cust_001")

        assert count == 1

    @pytest.mark.asyncio
    async def test_invalidate_document(self, cache, mock_redis):
        """Test invalidating all cache for a document."""
        # First call for doc structure, second for cross-refs, third for RAG
        mock_redis.keys.side_effect = [
            [b"graph:docstructure:key1"],
            [b"graph:crossref:key2"],
            [b"graph:rag:key3"],
        ]
        mock_redis.delete.return_value = 1

        count = await cache.invalidate_document("doc_001")

        assert count == 3

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache, mock_redis):
        """Test invalidating all graph cache entries."""
        mock_redis.keys.return_value = [b"key1", b"key2"]
        mock_redis.delete.return_value = 2

        count = await cache.invalidate_all()

        assert count > 0

    @pytest.mark.asyncio
    async def test_invalidate_disabled(self, disabled_cache):
        """Test that invalidate on disabled cache returns False."""
        result = await disabled_cache.invalidate(
            "customer360",
            {"id": "123"},
        )
        assert result is False


# =============================================================================
# CACHE KEY GENERATION TESTS
# =============================================================================

class TestCacheKeyGeneration:
    """Tests for cache key generation."""

    def test_deterministic_key_generation(self, cache):
        """Test that same params produce same key."""
        params = {"customer_id": "cust_001", "include_docs": True}

        key1 = cache._generate_cache_key("customer360", params)
        key2 = cache._generate_cache_key("customer360", params)

        assert key1 == key2

    def test_different_params_different_keys(self, cache):
        """Test that different params produce different keys."""
        key1 = cache._generate_cache_key("customer360", {"customer_id": "cust_001"})
        key2 = cache._generate_cache_key("customer360", {"customer_id": "cust_002"})

        assert key1 != key2

    def test_key_prefix_for_customer360(self, cache):
        """Test correct prefix for Customer 360."""
        key = cache._generate_cache_key("customer360", {"id": "123"})
        assert key.startswith(CacheKeyPrefix.CUSTOMER_360.value)

    def test_key_prefix_for_docstructure(self, cache):
        """Test correct prefix for Document Structure."""
        key = cache._generate_cache_key("docstructure", {"id": "123"})
        assert key.startswith(CacheKeyPrefix.DOCUMENT_STRUCTURE.value)

    def test_key_prefix_for_graph_rag(self, cache):
        """Test correct prefix for Graph RAG."""
        key = cache._generate_cache_key("enhanced_rag", {"id": "123"})
        assert key.startswith(CacheKeyPrefix.GRAPH_RAG.value)

    def test_normalize_params_with_list(self, cache):
        """Test parameter normalization with lists."""
        params = {"ids": ["b", "a", "c"]}
        normalized = cache._normalize_params(params)

        assert normalized["ids"] == ("a", "b", "c")  # Sorted tuple

    def test_normalize_params_with_none(self, cache):
        """Test parameter normalization skips None values."""
        params = {"id": "123", "optional": None}
        normalized = cache._normalize_params(params)

        assert "id" in normalized
        assert "optional" not in normalized

    def test_normalize_params_with_datetime(self, cache):
        """Test parameter normalization with datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        params = {"timestamp": dt}
        normalized = cache._normalize_params(params)

        assert normalized["timestamp"] == dt.isoformat()


# =============================================================================
# TTL CONFIGURATION TESTS
# =============================================================================

class TestTTLConfiguration:
    """Tests for TTL configuration."""

    def test_default_ttl_config(self, cache):
        """Test default TTL configuration values."""
        assert cache.ttl_config.CUSTOMER_360 == 1800
        assert cache.ttl_config.DOCUMENT_STRUCTURE == 3600
        assert cache.ttl_config.GRAPH_RAG == 600

    def test_custom_ttl_config(self, mock_redis):
        """Test custom TTL configuration."""
        custom_config = CacheTTLConfig(
            CUSTOMER_360=300,
            DOCUMENT_STRUCTURE=600,
        )
        cache = GraphQueryCache(
            redis_client=mock_redis,
            ttl_config=custom_config,
        )

        assert cache.ttl_config.CUSTOMER_360 == 300
        assert cache.ttl_config.DOCUMENT_STRUCTURE == 600

    def test_ttl_for_type_customer360(self, cache):
        """Test TTL selection for Customer 360."""
        ttl = cache._get_ttl_for_type("customer360")
        assert ttl == cache.ttl_config.CUSTOMER_360

    def test_ttl_for_type_docstructure(self, cache):
        """Test TTL selection for Document Structure."""
        ttl = cache._get_ttl_for_type("document_structure")
        assert ttl == cache.ttl_config.DOCUMENT_STRUCTURE

    def test_ttl_for_unknown_type(self, cache):
        """Test TTL selection for unknown type."""
        ttl = cache._get_ttl_for_type("unknown_type")
        assert ttl == cache.ttl_config.DEFAULT


# =============================================================================
# CACHE STATISTICS TESTS
# =============================================================================

class TestCacheStatistics:
    """Tests for cache statistics."""

    @pytest.mark.asyncio
    async def test_stats_track_hits(self, cache, mock_redis):
        """Test that hits are tracked."""
        mock_redis.get.return_value = json.dumps({"data": "test"}).encode()

        await cache.get("customer360", {"id": "123"})
        await cache.get("customer360", {"id": "456"})

        stats = cache.get_stats()
        assert stats["hits"] == 2

    @pytest.mark.asyncio
    async def test_stats_track_misses(self, cache, mock_redis):
        """Test that misses are tracked."""
        mock_redis.get.return_value = None

        await cache.get("customer360", {"id": "123"})

        stats = cache.get_stats()
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_stats_track_sets(self, cache, mock_redis):
        """Test that sets are tracked."""
        await cache.set("customer360", {"id": "123"}, {"data": "test"})

        stats = cache.get_stats()
        assert stats["sets"] == 1

    @pytest.mark.asyncio
    async def test_stats_track_invalidations(self, cache, mock_redis):
        """Test that invalidations are tracked."""
        await cache.invalidate("customer360", {"id": "123"})

        stats = cache.get_stats()
        assert stats["invalidations"] == 1

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_hit_rate_zero_total(self):
        """Test hit rate with zero requests."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_reset_stats(self, cache):
        """Test stats reset."""
        cache._stats.hits = 100
        cache._stats.misses = 50

        cache.reset_stats()

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


# =============================================================================
# ASYNC REDIS TESTS
# =============================================================================

class TestAsyncRedis:
    """Tests with async Redis client."""

    @pytest.mark.asyncio
    async def test_async_get(self, mock_redis):
        """Test cache get with sync Redis (simulating async pattern)."""
        reset_graph_query_cache()
        mock_redis.get.return_value = json.dumps({"data": "test"}).encode()
        cache = GraphQueryCache(redis_client=mock_redis, enabled=True)

        result = await cache.get("customer360", {"id": "123"})

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_async_set(self, async_cache, async_mock_redis):
        """Test cache set with async Redis."""
        result = await async_cache.set(
            "customer360",
            {"id": "123"},
            {"data": "test"},
        )

        assert result is True
        async_mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_invalidate(self, async_cache, async_mock_redis):
        """Test cache invalidate with async Redis."""
        result = await async_cache.invalidate("customer360", {"id": "123"})

        assert result is True
        async_mock_redis.delete.assert_called_once()


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_cache_singleton(self, mock_redis):
        """Test that get_graph_query_cache returns singleton."""
        reset_graph_query_cache()
        cache1 = get_graph_query_cache(redis_client=mock_redis)
        cache2 = get_graph_query_cache()

        assert cache1 is cache2

    def test_reset_creates_new_instance(self, mock_redis):
        """Test that reset creates new instance."""
        cache1 = get_graph_query_cache(redis_client=mock_redis)
        reset_graph_query_cache()
        cache2 = get_graph_query_cache(redis_client=mock_redis)

        assert cache1 is not cache2

    def test_get_cache_without_redis_creates_disabled(self):
        """Test that getting cache without Redis creates disabled cache."""
        reset_graph_query_cache()
        cache = get_graph_query_cache()

        assert cache.enabled is False


# =============================================================================
# DECORATOR TESTS
# =============================================================================

class TestCacheDecorator:
    """Tests for cache decorator."""

    @pytest.mark.asyncio
    async def test_decorator_caches_result(self, cache):
        """Test that decorator caches function results."""
        call_count = 0

        @cached_graph_query("customer360")
        async def get_customer(customer_id: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"id": customer_id, "name": "Test"}

        # First call - should execute function
        result1 = await get_customer("cust_001", _cache=cache)

        assert result1 == {"id": "cust_001", "name": "Test"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_no_cache(self):
        """Test decorator works without cache."""
        @cached_graph_query("customer360")
        async def get_customer(customer_id: str) -> dict:
            return {"id": customer_id}

        # Should work without cache
        reset_graph_query_cache()
        result = await get_customer("cust_001")
        assert result == {"id": "cust_001"}
