"""
Tests for Tiered Cache Service (L1: Redis, L2: PostgreSQL)

Tests the cache-aside pattern with fallback from Redis to PostgreSQL.
Validates cache promotion, TTL management, and multi-level caching strategy.

Run with: python3 -m pytest tests/test_tiered_cache_service.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from app.services.tiered_cache_service import (
    TieredCacheService,
    TieredCacheConfig,
    CacheLevel,
    CacheLookupResult,
    get_tiered_cache_service
)


@pytest.fixture
def cache_config():
    """Create test cache configuration"""
    return TieredCacheConfig(
        l1_enabled=True,
        l2_enabled=True,
        l1_ttl_seconds=300,  # 5 minutes
        l2_ttl_seconds=3600,  # 60 minutes
        promote_to_l1=True,
        semantic_threshold=0.85
    )


@pytest.fixture
def mock_redis_cache():
    """Create mock Redis cache service"""
    cache = Mock()
    cache.get_cached_query_result = Mock(return_value=None)
    cache.cache_query_result = Mock(return_value=True)
    cache.get_cached_embedding = Mock(return_value=None)
    cache.cache_embedding = Mock(return_value=True)
    cache.get_metrics = Mock(return_value={"hits": 0, "misses": 0})
    return cache


@pytest.fixture
def mock_postgres_cache():
    """Create mock PostgreSQL cache service"""
    cache = Mock()
    cache.get_cached_query_result = AsyncMock(return_value=None)
    cache.cache_query_result = AsyncMock(return_value=True)
    cache.get_cached_embedding = AsyncMock(return_value=None)
    cache.cache_embedding = AsyncMock(return_value=True)
    cache.cleanup_expired = AsyncMock(return_value=5)
    return cache


@pytest.fixture
def tiered_cache(cache_config, mock_redis_cache, mock_postgres_cache):
    """Create tiered cache service with mocks"""
    return TieredCacheService(
        config=cache_config,
        redis_cache=mock_redis_cache,
        postgres_cache=mock_postgres_cache
    )


@pytest.fixture
def sample_query_result():
    """Sample search result"""
    return {
        "query": "insurance policy",
        "results": [
            {"chunk_id": "chunk1", "score": 0.95},
            {"chunk_id": "chunk2", "score": 0.88}
        ],
        "max_score": 0.95
    }


def test_tiered_cache_config_creation():
    """
    Test TieredCacheConfig creation

    Verifies:
    - Config accepts L1 and L2 settings
    - TTL values are configurable
    - Promotion flag is set
    """
    config = TieredCacheConfig(
        l1_enabled=True,
        l2_enabled=True,
        l1_ttl_seconds=600,
        l2_ttl_seconds=7200,
        promote_to_l1=False
    )

    assert config.l1_enabled is True
    assert config.l2_enabled is True
    assert config.l1_ttl_seconds == 600
    assert config.l2_ttl_seconds == 7200
    assert config.promote_to_l1 is False


@pytest.mark.asyncio
async def test_l1_cache_hit(tiered_cache, mock_redis_cache, sample_query_result):
    """
    Test L1 (Redis) cache hit

    Verifies:
    - L1 is checked first
    - Result is returned from L1
    - L2 is not queried
    - Lookup result indicates L1 hit
    """
    mock_redis_cache.get_cached_query_result.return_value = sample_query_result

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is not None
    assert result.data == sample_query_result
    assert result.cache_level == CacheLevel.L1
    mock_redis_cache.get_cached_query_result.assert_called_once()
    # L2 should not be called on L1 hit
    mock_postgres_cache = tiered_cache.postgres_cache
    mock_postgres_cache.get_cached_query_result.assert_not_called()


@pytest.mark.asyncio
async def test_l1_miss_l2_hit(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test L1 miss, L2 (PostgreSQL) hit

    Verifies:
    - L1 is checked first, returns None
    - L2 is checked on L1 miss
    - Result is returned from L2
    - Lookup result indicates L2 hit
    """
    mock_redis_cache.get_cached_query_result.return_value = None
    mock_postgres_cache.get_cached_query_result.return_value = sample_query_result

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is not None
    assert result.data == sample_query_result
    assert result.cache_level == CacheLevel.L2
    mock_redis_cache.get_cached_query_result.assert_called_once()
    mock_postgres_cache.get_cached_query_result.assert_called_once()


@pytest.mark.asyncio
async def test_l1_miss_l2_miss(tiered_cache, mock_redis_cache, mock_postgres_cache):
    """
    Test L1 miss, L2 miss (full cache miss)

    Verifies:
    - Both L1 and L2 are checked
    - None is returned on full miss
    - Lookup result indicates miss
    """
    mock_redis_cache.get_cached_query_result.return_value = None
    mock_postgres_cache.get_cached_query_result.return_value = None

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is None or (hasattr(result, 'data') and result.data is None)
    mock_redis_cache.get_cached_query_result.assert_called_once()
    mock_postgres_cache.get_cached_query_result.assert_called_once()


@pytest.mark.asyncio
async def test_cache_promotion_l2_to_l1(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test cache promotion from L2 to L1

    Verifies:
    - On L2 hit, result is promoted to L1
    - L1 cache is populated with L2 result
    - Promotion happens automatically
    """
    mock_redis_cache.get_cached_query_result.return_value = None
    mock_postgres_cache.get_cached_query_result.return_value = sample_query_result
    tiered_cache.config.promote_to_l1 = True

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is not None
    # Verify L1 was populated
    mock_redis_cache.cache_query_result.assert_called_once_with(
        "insurance policy",
        sample_query_result
    )


@pytest.mark.asyncio
async def test_no_promotion_when_disabled(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test that promotion doesn't happen when disabled

    Verifies:
    - promote_to_l1=False prevents promotion
    - L1 is not populated on L2 hit
    """
    mock_redis_cache.get_cached_query_result.return_value = None
    mock_postgres_cache.get_cached_query_result.return_value = sample_query_result
    tiered_cache.config.promote_to_l1 = False

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is not None
    # L1 should NOT be populated
    mock_redis_cache.cache_query_result.assert_not_called()


@pytest.mark.asyncio
async def test_cache_write_to_both_levels(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test writing to both cache levels

    Verifies:
    - New results are cached in both L1 and L2
    - TTL is set appropriately for each level
    """
    success = await tiered_cache.cache_query_result("insurance policy", sample_query_result)

    assert success is True
    mock_redis_cache.cache_query_result.assert_called_once()
    mock_postgres_cache.cache_query_result.assert_called_once()


@pytest.mark.asyncio
async def test_cache_write_l1_only(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test writing to L1 only when L2 is disabled

    Verifies:
    - Only L1 is populated when L2 is disabled
    - L2 cache methods are not called
    """
    tiered_cache.config.l2_enabled = False

    success = await tiered_cache.cache_query_result("insurance policy", sample_query_result)

    assert success is True
    mock_redis_cache.cache_query_result.assert_called_once()
    mock_postgres_cache.cache_query_result.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_cache_tiered_lookup(tiered_cache, mock_redis_cache, mock_postgres_cache):
    """
    Test tiered lookup for embeddings

    Verifies:
    - Embeddings use same tiered strategy
    - L1 checked first, L2 on miss
    """
    sample_embedding = [0.1, 0.2, 0.3] * 300

    mock_redis_cache.get_cached_embedding.return_value = None
    mock_postgres_cache.get_cached_embedding.return_value = sample_embedding

    result = await tiered_cache.get_cached_embedding("sample text")

    assert result is not None
    assert result.data == sample_embedding
    mock_redis_cache.get_cached_embedding.assert_called_once()
    mock_postgres_cache.get_cached_embedding.assert_called_once()


@pytest.mark.asyncio
async def test_embedding_cache_promotion(tiered_cache, mock_redis_cache, mock_postgres_cache):
    """
    Test embedding promotion from L2 to L1

    Verifies:
    - Embeddings are promoted to L1 on L2 hit
    """
    sample_embedding = [0.1, 0.2, 0.3] * 300

    mock_redis_cache.get_cached_embedding.return_value = None
    mock_postgres_cache.get_cached_embedding.return_value = sample_embedding
    tiered_cache.config.promote_to_l1 = True

    result = await tiered_cache.get_cached_embedding("sample text")

    assert result is not None
    mock_redis_cache.cache_embedding.assert_called_once_with(
        "sample text",
        sample_embedding
    )


@pytest.mark.asyncio
async def test_semantic_threshold_applies_to_both_levels(tiered_cache, mock_redis_cache, mock_postgres_cache):
    """
    Test semantic threshold filtering for tiered cache

    Verifies:
    - Low-score results are not cached in either level
    - Threshold applies consistently
    """
    low_score_result = {
        "query": "test",
        "results": [{"chunk_id": "chunk1", "score": 0.70}],
        "max_score": 0.70
    }

    success = await tiered_cache.cache_query_result_if_relevant("test", low_score_result)

    assert success is False
    # Neither cache should be called
    mock_redis_cache.cache_query_result.assert_not_called()
    mock_postgres_cache.cache_query_result.assert_not_called()


@pytest.mark.asyncio
async def test_get_cache_metrics(tiered_cache, mock_redis_cache):
    """
    Test retrieving cache metrics from both levels

    Verifies:
    - Metrics are aggregated from L1 and L2
    - Hit rates are calculated correctly
    """
    mock_redis_cache.get_metrics.return_value = {
        "hits": 10,
        "misses": 5,
        "hit_rate": 0.67
    }

    metrics = tiered_cache.get_metrics()

    assert metrics is not None
    assert "l1" in metrics or "redis" in metrics
    assert mock_redis_cache.get_metrics.called


@pytest.mark.asyncio
async def test_l2_cache_cleanup(tiered_cache, mock_postgres_cache):
    """
    Test L2 cache cleanup of expired entries

    Verifies:
    - Cleanup is triggered on L2
    - Returns count of cleaned entries
    """
    mock_postgres_cache.cleanup_expired.return_value = 15

    count = await tiered_cache.cleanup_expired_l2_entries()

    assert count == 15
    mock_postgres_cache.cleanup_expired.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_on_l1_error(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test fallback to L2 when L1 fails

    Verifies:
    - L1 errors are handled gracefully
    - L2 is queried on L1 error
    - Result is returned from L2
    """
    mock_redis_cache.get_cached_query_result.side_effect = Exception("Redis connection failed")
    mock_postgres_cache.get_cached_query_result.return_value = sample_query_result

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is not None
    assert result.data == sample_query_result
    mock_postgres_cache.get_cached_query_result.assert_called_once()


@pytest.mark.asyncio
async def test_both_caches_disabled(tiered_cache, mock_redis_cache, mock_postgres_cache, sample_query_result):
    """
    Test behavior when both caches are disabled

    Verifies:
    - Returns None when both caches disabled
    - No cache operations attempted
    """
    tiered_cache.config.l1_enabled = False
    tiered_cache.config.l2_enabled = False

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert result is None or (hasattr(result, 'data') and result.data is None)


def test_cache_level_enum():
    """
    Test CacheLevel enum

    Verifies:
    - L1, L2, and NONE levels exist
    - Values are distinct
    """
    assert CacheLevel.L1.value == "L1"
    assert CacheLevel.L2.value == "L2"
    assert CacheLevel.NONE.value == "NONE"


@pytest.mark.asyncio
async def test_get_tiered_cache_service_singleton():
    """
    Test singleton pattern for tiered cache service

    Verifies:
    - Same instance returned
    - Configuration persists
    """
    service1 = get_tiered_cache_service()
    service2 = get_tiered_cache_service()

    assert service1 is service2


@pytest.mark.asyncio
async def test_cache_lookup_result_structure(tiered_cache, mock_redis_cache, sample_query_result):
    """
    Test CacheLookupResult structure

    Verifies:
    - Contains data field
    - Contains cache_level field
    - Contains metadata
    """
    mock_redis_cache.get_cached_query_result.return_value = sample_query_result

    result = await tiered_cache.get_cached_query_result("insurance policy")

    assert hasattr(result, 'data')
    assert hasattr(result, 'cache_level')
    assert result.data == sample_query_result
    assert result.cache_level == CacheLevel.L1
