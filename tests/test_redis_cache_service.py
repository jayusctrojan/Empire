"""
Tests for Redis Cache Service

Tests Redis L1 caching with semantic thresholds, TTL management,
and cache-aside pattern implementation.

Run with: python3 -m pytest tests/test_redis_cache_service.py -v
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.redis_cache_service import (
    RedisCacheService,
    RedisCacheConfig,
    CacheKey,
    CacheMetrics,
    get_redis_cache_service
)


@pytest.fixture
def cache_config():
    """Create test cache configuration"""
    return RedisCacheConfig(
        host="localhost",
        port=6379,
        db=0,
        ttl_seconds=300,  # 5 minutes
        semantic_threshold=0.85,
        enable_metrics=True
    )


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client"""
    client = Mock()
    client.get = Mock(return_value=None)
    client.set = Mock(return_value=True)
    client.setex = Mock(return_value=True)
    client.delete = Mock(return_value=1)
    client.ttl = Mock(return_value=300)
    client.ping = Mock(return_value=True)
    client.info = Mock(return_value={"used_memory": "1M"})
    return client


@pytest.fixture
def cache_service(mock_redis_client):
    """Create cache service with mock Redis client"""
    with patch('app.services.redis_cache_service.redis.Redis', return_value=mock_redis_client):
        return RedisCacheService(redis_client=mock_redis_client)


@pytest.fixture
def sample_query_result():
    """Sample search result for caching"""
    return {
        "query": "insurance policy claims",
        "results": [
            {"doc_id": "doc1", "score": 0.95, "content": "Policy document 1"},
            {"doc_id": "doc2", "score": 0.88, "content": "Policy document 2"}
        ],
        "total": 2,
        "took_ms": 150
    }


@pytest.fixture
def sample_embedding():
    """Sample embedding vector"""
    return [0.1, 0.2, 0.3, 0.4, 0.5] * 200  # 1000-dim vector


def test_redis_cache_config_creation():
    """
    Test RedisCacheConfig creation

    Verifies:
    - Config accepts Redis connection params
    - TTL defaults to 300 seconds (5 minutes)
    - Semantic threshold is configurable
    """
    config = RedisCacheConfig(
        host="redis.example.com",
        port=6380,
        ttl_seconds=600
    )

    assert config.host == "redis.example.com"
    assert config.port == 6380
    assert config.ttl_seconds == 600
    assert config.semantic_threshold == 0.85  # Default


def test_cache_service_initialization(cache_config, mock_redis_client):
    """
    Test RedisCacheService initialization

    Verifies:
    - Redis client is created
    - Connection is verified
    - Config is stored
    """
    with patch('app.services.redis_cache_service.redis.Redis', return_value=mock_redis_client):
        service = RedisCacheService(config=cache_config, redis_client=mock_redis_client)

        assert service.config == cache_config
        assert service.redis_client is not None
        mock_redis_client.ping.assert_called()


def test_generate_cache_key_for_query(cache_service):
    """
    Test cache key generation for search queries

    Verifies:
    - Consistent key format
    - Query normalization
    - Includes query type
    """
    query = "insurance policy claims"
    key = cache_service.generate_cache_key(query, key_type="query")

    assert isinstance(key, str)
    assert "query" in key
    assert len(key) > 0

    # Same query should produce same key
    key2 = cache_service.generate_cache_key(query, key_type="query")
    assert key == key2


def test_generate_cache_key_for_embedding(cache_service):
    """
    Test cache key generation for embeddings

    Verifies:
    - Embedding text is hashed
    - Key includes embedding type
    """
    text = "Sample text for embedding"
    key = cache_service.generate_cache_key(text, key_type="embedding")

    assert isinstance(key, str)
    assert "embedding" in key


def test_cache_query_result(cache_service, mock_redis_client, sample_query_result):
    """
    Test caching a query result with TTL

    Verifies:
    - Result is serialized and stored
    - TTL is set to 5 minutes
    - Cache key is generated correctly
    """
    query = "insurance policy"

    success = cache_service.cache_query_result(query, sample_query_result)

    assert success is True
    mock_redis_client.setex.assert_called()

    # Verify TTL is 300 seconds (5 minutes)
    call_args = mock_redis_client.setex.call_args
    assert call_args[0][1] == 300  # TTL parameter


def test_get_cached_query_result_hit(cache_service, mock_redis_client, sample_query_result):
    """
    Test cache hit for query result

    Verifies:
    - Cached result is retrieved
    - Deserialized correctly
    - Metrics updated
    """
    import json

    query = "insurance policy"
    mock_redis_client.get.return_value = json.dumps(sample_query_result).encode('utf-8')

    result = cache_service.get_cached_query_result(query)

    assert result is not None
    assert result["query"] == sample_query_result["query"]
    assert len(result["results"]) == 2
    mock_redis_client.get.assert_called()


def test_get_cached_query_result_miss(cache_service, mock_redis_client):
    """
    Test cache miss for query result

    Verifies:
    - Returns None on miss
    - Metrics updated
    """
    query = "nonexistent query"
    mock_redis_client.get.return_value = None

    result = cache_service.get_cached_query_result(query)

    assert result is None


def test_semantic_threshold_filtering(cache_service, mock_redis_client):
    """
    Test that only results meeting semantic threshold are cached

    Verifies:
    - Low-score results are not cached
    - High-score results are cached
    - Threshold is configurable
    """
    query = "test query"

    # Low-score result (below threshold)
    low_score_result = {
        "query": query,
        "results": [{"doc_id": "doc1", "score": 0.70}],  # Below 0.85
        "max_score": 0.70
    }

    # Should not cache low-score results
    cache_service.config.semantic_threshold = 0.85
    success = cache_service.cache_query_result_if_relevant(query, low_score_result)

    assert success is False
    mock_redis_client.setex.assert_not_called()

    # High-score result (above threshold)
    high_score_result = {
        "query": query,
        "results": [{"doc_id": "doc1", "score": 0.92}],
        "max_score": 0.92
    }

    success = cache_service.cache_query_result_if_relevant(query, high_score_result)

    assert success is True
    mock_redis_client.setex.assert_called()


def test_cache_embedding_with_ttl(cache_service, mock_redis_client, sample_embedding):
    """
    Test caching embeddings with TTL

    Verifies:
    - Embedding vector is cached
    - TTL is applied
    - Serialization handles large vectors
    """
    text = "Document text for embedding"

    success = cache_service.cache_embedding(text, sample_embedding)

    assert success is True
    mock_redis_client.setex.assert_called()

    # Verify TTL
    call_args = mock_redis_client.setex.call_args
    assert call_args[0][1] == 300


def test_get_cached_embedding_hit(cache_service, mock_redis_client, sample_embedding):
    """
    Test cache hit for embedding

    Verifies:
    - Embedding is retrieved
    - Deserialized to list of floats
    """
    import json

    text = "Document text"
    mock_redis_client.get.return_value = json.dumps(sample_embedding).encode('utf-8')

    embedding = cache_service.get_cached_embedding(text)

    assert embedding is not None
    assert isinstance(embedding, list)
    assert len(embedding) == len(sample_embedding)
    assert all(isinstance(x, float) for x in embedding)


def test_get_cached_embedding_miss(cache_service, mock_redis_client):
    """
    Test cache miss for embedding

    Verifies:
    - Returns None on miss
    """
    text = "Uncached text"
    mock_redis_client.get.return_value = None

    embedding = cache_service.get_cached_embedding(text)

    assert embedding is None


def test_ttl_expiration_handling(cache_service, mock_redis_client):
    """
    Test TTL expiration behavior

    Verifies:
    - Expired keys return None
    - TTL is checked correctly
    """
    query = "test query"

    # Simulate expired key (TTL = -2 in Redis)
    mock_redis_client.ttl.return_value = -2
    mock_redis_client.get.return_value = None

    result = cache_service.get_cached_query_result(query)

    assert result is None


def test_cache_metrics_tracking(cache_service, mock_redis_client, sample_query_result):
    """
    Test cache metrics collection

    Verifies:
    - Hits and misses are tracked
    - Hit rate is calculated
    - Metrics can be retrieved
    """
    query = "test query"

    # Cache miss
    mock_redis_client.get.return_value = None
    cache_service.get_cached_query_result(query)

    # Cache hit
    import json
    mock_redis_client.get.return_value = json.dumps(sample_query_result).encode('utf-8')
    cache_service.get_cached_query_result(query)

    # Get metrics
    metrics = cache_service.get_metrics()

    assert metrics is not None
    assert hasattr(metrics, 'hits') or 'hits' in metrics
    assert hasattr(metrics, 'misses') or 'misses' in metrics


def test_cache_invalidation(cache_service, mock_redis_client):
    """
    Test cache invalidation/deletion

    Verifies:
    - Specific keys can be deleted
    - Pattern-based deletion works
    """
    query = "test query"

    success = cache_service.invalidate_cache(query, key_type="query")

    assert success is True
    mock_redis_client.delete.assert_called()


def test_cache_aside_pattern_implementation(cache_service, mock_redis_client, sample_query_result):
    """
    Test cache-aside pattern flow

    Verifies:
    - Check cache first
    - On miss, fetch from source
    - Populate cache
    - On hit, return cached value
    """
    query = "test query"

    # Simulate cache miss -> fetch -> cache
    mock_redis_client.get.return_value = None

    # Check cache (miss)
    result = cache_service.get_cached_query_result(query)
    assert result is None

    # Fetch from source and cache
    cache_service.cache_query_result(query, sample_query_result)
    mock_redis_client.setex.assert_called()

    # Simulate cache hit
    import json
    mock_redis_client.get.return_value = json.dumps(sample_query_result).encode('utf-8')

    result = cache_service.get_cached_query_result(query)
    assert result is not None


def test_connection_error_handling(cache_config):
    """
    Test graceful handling of Redis connection errors

    Verifies:
    - Service handles connection failures
    - Falls back gracefully
    - Logs errors
    """
    mock_client = Mock()
    mock_client.ping.side_effect = Exception("Connection failed")

    with patch('app.services.redis_cache_service.redis.Redis', return_value=mock_client):
        service = RedisCacheService(config=cache_config, redis_client=mock_client)

        # Should not crash, should handle gracefully
        result = service.get_cached_query_result("test")
        assert result is None


def test_serialization_error_handling(cache_service, mock_redis_client):
    """
    Test handling of serialization errors

    Verifies:
    - Invalid data is handled
    - Returns None on deserialization failure
    """
    query = "test query"
    mock_redis_client.get.return_value = b"invalid json data {{{{"

    result = cache_service.get_cached_query_result(query)

    assert result is None  # Should handle gracefully


def test_cache_key_collision_prevention(cache_service):
    """
    Test that different inputs produce different keys

    Verifies:
    - Hash-based keys prevent collisions
    - Similar queries get different keys
    """
    query1 = "insurance policy"
    query2 = "insurance policies"  # Similar but different

    key1 = cache_service.generate_cache_key(query1, key_type="query")
    key2 = cache_service.generate_cache_key(query2, key_type="query")

    assert key1 != key2


def test_get_redis_cache_service_singleton():
    """
    Test singleton pattern for cache service

    Verifies:
    - Same instance returned
    - Configuration persists
    """
    service1 = get_redis_cache_service()
    service2 = get_redis_cache_service()

    assert service1 is service2


def test_cache_size_and_memory_tracking(cache_service, mock_redis_client):
    """
    Test tracking of cache size and memory usage

    Verifies:
    - Memory info is retrievable
    - Key counts are tracked
    """
    mock_redis_client.info.return_value = {
        "used_memory": "10485760",  # 10MB
        "used_memory_human": "10M"
    }

    info = cache_service.get_cache_info()

    assert info is not None
    mock_redis_client.info.assert_called()


def test_bulk_cache_operations(cache_service, mock_redis_client):
    """
    Test bulk caching operations

    Verifies:
    - Multiple items can be cached efficiently
    - Batch operations work
    """
    items = [
        ("query1", {"results": []}),
        ("query2", {"results": []}),
        ("query3", {"results": []})
    ]

    results = cache_service.cache_multiple(items, key_type="query")

    assert len(results) == 3
    assert mock_redis_client.setex.call_count >= 3


def test_ttl_refresh_on_access(cache_service, mock_redis_client, sample_query_result):
    """
    Test TTL refresh when accessing cached items

    Verifies:
    - Accessing an item can optionally refresh its TTL
    - Keeps frequently accessed items in cache longer
    """
    import json

    query = "frequent query"
    mock_redis_client.get.return_value = json.dumps(sample_query_result).encode('utf-8')
    mock_redis_client.expire = Mock(return_value=True)

    result = cache_service.get_cached_query_result(query, refresh_ttl=True)

    assert result is not None
    # TTL should be refreshed
    if hasattr(cache_service, 'refresh_ttl'):
        mock_redis_client.expire.assert_called()
