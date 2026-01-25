"""
Tests for Semantic Cache Service (Task 30)

Tests tiered similarity thresholds, embedding caching, and cache operations.
Target: 60-80% cache hit rate with <200ms lookup time.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from app.services.semantic_cache_service import (
    SemanticCacheService,
    SemanticCacheConfig,
    SemanticCacheMetrics,
    SemanticCacheResult,
    CacheMatchTier,
    get_semantic_cache_service,
    reset_semantic_cache_service
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_redis_client():
    """Create mock Redis client"""
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.set = MagicMock(return_value=True)
    redis.get_cached_query_result = MagicMock(return_value=None)
    redis.cache_query_result = MagicMock(return_value=True)
    redis.get_cached_embedding = MagicMock(return_value=None)
    redis.cache_embedding = MagicMock(return_value=True)
    redis.invalidate_cache = MagicMock(return_value=True)
    redis.scan_keys = AsyncMock(return_value=[])
    redis.redis_client = MagicMock()
    redis.redis_client.ping = MagicMock(return_value=True)
    redis.redis_client.delete = MagicMock(return_value=1)
    return redis


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service"""
    service = MagicMock()
    # Return a simple embedding result
    result = MagicMock()
    result.embedding = [0.1] * 1024  # 1024-dimensional embedding
    service.generate_embedding = AsyncMock(return_value=result)
    return service


@pytest.fixture
def config():
    """Create test config"""
    return SemanticCacheConfig(
        exact_threshold=0.98,
        high_threshold=0.93,
        medium_threshold=0.88,
        search_result_ttl=300,
        embedding_ttl=3600,
        max_candidates=100,
        enable_metrics=True
    )


@pytest.fixture
def service(config, mock_redis_client, mock_embedding_service):
    """Create service with mocks"""
    svc = SemanticCacheService(
        config=config,
        redis_client=mock_redis_client,
        embedding_service=mock_embedding_service
    )
    return svc


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test"""
    reset_semantic_cache_service()
    yield
    reset_semantic_cache_service()


# =============================================================================
# Config Tests
# =============================================================================

class TestSemanticCacheConfig:
    """Tests for cache configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SemanticCacheConfig()

        assert config.exact_threshold == 0.98
        assert config.high_threshold == 0.93
        assert config.medium_threshold == 0.88
        assert config.search_result_ttl == 300  # 5 minutes
        assert config.embedding_ttl == 3600  # 1 hour
        assert config.max_candidates == 100
        assert config.enable_metrics is True

    def test_custom_config(self):
        """Test custom configuration values"""
        config = SemanticCacheConfig(
            exact_threshold=0.99,
            high_threshold=0.95,
            medium_threshold=0.90,
            search_result_ttl=600,
            max_candidates=50
        )

        assert config.exact_threshold == 0.99
        assert config.high_threshold == 0.95
        assert config.medium_threshold == 0.90
        assert config.search_result_ttl == 600

    def test_config_from_env(self, monkeypatch):
        """Test configuration from environment variables"""
        monkeypatch.setenv("SEMANTIC_CACHE_EXACT_THRESHOLD", "0.97")
        monkeypatch.setenv("SEMANTIC_CACHE_HIGH_THRESHOLD", "0.92")
        monkeypatch.setenv("SEMANTIC_CACHE_RESULT_TTL", "600")

        config = SemanticCacheConfig.from_env()

        assert config.exact_threshold == 0.97
        assert config.high_threshold == 0.92
        assert config.search_result_ttl == 600


# =============================================================================
# Metrics Tests
# =============================================================================

class TestSemanticCacheMetrics:
    """Tests for cache metrics"""

    def test_initial_metrics(self):
        """Test initial metric values"""
        metrics = SemanticCacheMetrics()

        assert metrics.total_requests == 0
        assert metrics.exact_hits == 0
        assert metrics.high_hits == 0
        assert metrics.medium_hits == 0
        assert metrics.misses == 0
        assert metrics.cache_hit_rate == 0.0

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation"""
        metrics = SemanticCacheMetrics(
            total_requests=100,
            exact_hits=30,
            high_hits=40,
            medium_hits=10,
            misses=20
        )

        # Hit rate = (exact + high) / total = 70/100 = 0.7
        assert metrics.cache_hit_rate == 0.7

    def test_tier_distribution(self):
        """Test tier distribution calculation"""
        metrics = SemanticCacheMetrics(
            total_requests=100,
            exact_hits=25,
            high_hits=35,
            medium_hits=20,
            misses=20
        )

        dist = metrics.tier_distribution

        assert dist["exact"] == 0.25
        assert dist["high"] == 0.35
        assert dist["medium"] == 0.20
        assert dist["miss"] == 0.20

    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        metrics = SemanticCacheMetrics(
            total_requests=50,
            exact_hits=20,
            high_hits=15
        )

        result = metrics.to_dict()

        assert "total_requests" in result
        assert "cache_hit_rate" in result
        assert "tier_distribution" in result
        assert result["total_requests"] == 50


# =============================================================================
# Cache Match Tier Tests
# =============================================================================

class TestCacheMatchTier:
    """Tests for cache match tier classification"""

    def test_tier_values(self):
        """Test tier enum values"""
        assert CacheMatchTier.EXACT.value == "exact"
        assert CacheMatchTier.HIGH.value == "high"
        assert CacheMatchTier.MEDIUM.value == "medium"
        assert CacheMatchTier.LOW.value == "low"
        assert CacheMatchTier.MISS.value == "miss"


class TestSemanticCacheResult:
    """Tests for cache result structure"""

    def test_usable_exact_tier(self):
        """Test exact tier is usable"""
        result = SemanticCacheResult(
            tier=CacheMatchTier.EXACT,
            similarity=0.99,
            data={"results": []}
        )

        assert result.is_usable is True
        assert result.needs_fresh_search is False

    def test_usable_high_tier(self):
        """Test high tier is usable"""
        result = SemanticCacheResult(
            tier=CacheMatchTier.HIGH,
            similarity=0.95,
            data={"results": []}
        )

        assert result.is_usable is True
        assert result.needs_fresh_search is False

    def test_not_usable_medium_tier(self):
        """Test medium tier needs fresh search"""
        result = SemanticCacheResult(
            tier=CacheMatchTier.MEDIUM,
            similarity=0.90,
            data=None
        )

        assert result.is_usable is False
        assert result.needs_fresh_search is True

    def test_not_usable_miss(self):
        """Test cache miss needs fresh search"""
        result = SemanticCacheResult(
            tier=CacheMatchTier.MISS,
            similarity=0.0,
            data=None
        )

        assert result.is_usable is False
        assert result.needs_fresh_search is True


# =============================================================================
# Similarity Classification Tests
# =============================================================================

class TestSimilarityClassification:
    """Tests for similarity score classification"""

    def test_classify_exact(self, service):
        """Test exact match classification"""
        tier = service._classify_similarity(0.99)
        assert tier == CacheMatchTier.EXACT

        tier = service._classify_similarity(0.98)
        assert tier == CacheMatchTier.EXACT

    def test_classify_high(self, service):
        """Test high similarity classification"""
        tier = service._classify_similarity(0.97)
        assert tier == CacheMatchTier.HIGH

        tier = service._classify_similarity(0.93)
        assert tier == CacheMatchTier.HIGH

    def test_classify_medium(self, service):
        """Test medium similarity classification"""
        tier = service._classify_similarity(0.92)
        assert tier == CacheMatchTier.MEDIUM

        tier = service._classify_similarity(0.88)
        assert tier == CacheMatchTier.MEDIUM

    def test_classify_low(self, service):
        """Test low similarity classification"""
        tier = service._classify_similarity(0.87)
        assert tier == CacheMatchTier.LOW

        tier = service._classify_similarity(0.5)
        assert tier == CacheMatchTier.LOW


# =============================================================================
# Cosine Similarity Tests
# =============================================================================

class TestCosineSimilarity:
    """Tests for cosine similarity calculation"""

    def test_identical_vectors(self, service):
        """Test similarity of identical vectors"""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])

        similarity = service._cosine_similarity(a, b)
        assert similarity == pytest.approx(1.0)

    def test_orthogonal_vectors(self, service):
        """Test similarity of orthogonal vectors"""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])

        similarity = service._cosine_similarity(a, b)
        assert similarity == pytest.approx(0.0)

    def test_opposite_vectors(self, service):
        """Test similarity of opposite vectors"""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([-1.0, 0.0, 0.0])

        similarity = service._cosine_similarity(a, b)
        assert similarity == pytest.approx(-1.0)

    def test_similar_vectors(self, service):
        """Test similarity of similar vectors"""
        a = np.array([0.9, 0.1, 0.0])
        b = np.array([0.85, 0.15, 0.0])

        similarity = service._cosine_similarity(a, b)
        assert similarity > 0.95  # Should be very similar

    def test_zero_vector_handling(self, service):
        """Test handling of zero vectors"""
        a = np.array([0.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])

        similarity = service._cosine_similarity(a, b)
        assert similarity == 0.0


# =============================================================================
# Embedding Cache Tests
# =============================================================================

class TestEmbeddingCache:
    """Tests for embedding caching"""

    @pytest.mark.asyncio
    async def test_get_cached_embedding_hit(self, service, mock_redis_client):
        """Test embedding cache hit"""
        mock_redis_client.get_cached_embedding.return_value = [0.1] * 1024

        result = await service.get_cached_embedding("test query")

        assert result is not None
        assert len(result) == 1024
        assert service.metrics.embedding_cache_hits == 1

    @pytest.mark.asyncio
    async def test_get_cached_embedding_miss(self, service, mock_redis_client):
        """Test embedding cache miss"""
        mock_redis_client.get_cached_embedding.return_value = None

        result = await service.get_cached_embedding("test query")

        assert result is None
        assert service.metrics.embedding_cache_misses == 1

    @pytest.mark.asyncio
    async def test_cache_embedding(self, service, mock_redis_client):
        """Test caching an embedding"""
        embedding = [0.1] * 1024

        result = await service.cache_embedding("test query", embedding)

        assert result is True
        mock_redis_client.cache_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_embedding_cached(self, service, mock_redis_client):
        """Test get_or_create returns cached embedding"""
        cached_embedding = [0.2] * 1024
        mock_redis_client.get_cached_embedding.return_value = cached_embedding

        embedding, from_cache = await service.get_or_create_embedding("test")

        assert from_cache is True
        assert embedding == cached_embedding

    @pytest.mark.asyncio
    async def test_get_or_create_embedding_generate(
        self, service, mock_redis_client, mock_embedding_service
    ):
        """Test get_or_create generates new embedding"""
        mock_redis_client.get_cached_embedding.return_value = None

        embedding, from_cache = await service.get_or_create_embedding("test")

        assert from_cache is False
        assert len(embedding) == 1024
        mock_embedding_service.generate_embedding.assert_called_once()


# =============================================================================
# Semantic Match Tests
# =============================================================================

class TestSemanticMatch:
    """Tests for semantic matching"""

    @pytest.mark.asyncio
    async def test_exact_hash_match(self, service, mock_redis_client):
        """Test exact hash match returns immediately"""
        cached_result = {"results": [{"id": "doc1"}]}
        mock_redis_client.get_cached_query_result.return_value = cached_result

        result = await service.get_semantic_match("test query")

        assert result.tier == CacheMatchTier.EXACT
        assert result.similarity == 1.0
        assert result.data == cached_result
        assert service.metrics.exact_hits == 1

    @pytest.mark.asyncio
    async def test_cache_miss(self, service, mock_redis_client):
        """Test cache miss when no similar queries"""
        mock_redis_client.get_cached_query_result.return_value = None
        mock_redis_client.scan_keys = AsyncMock(return_value=[])

        result = await service.get_semantic_match(
            "test query",
            query_embedding=[0.1] * 1024
        )

        assert result.tier == CacheMatchTier.MISS
        assert result.similarity == 0.0
        assert result.data is None
        assert service.metrics.misses == 1

    @pytest.mark.asyncio
    async def test_high_similarity_match(self, service, mock_redis_client):
        """Test high similarity semantic match"""
        mock_redis_client.get_cached_query_result.return_value = None

        # Setup cached query with similar embedding
        query_embedding = np.array([0.1] * 1024)
        cached_embedding = query_embedding * 0.99  # Very similar

        cached_data = {
            "query": "similar query",
            "result": {"results": [{"id": "doc1"}]},
            "embedding": cached_embedding.tolist()
        }

        mock_redis_client.scan_keys = AsyncMock(return_value=["search:sem:abc123"])
        mock_redis_client.get.return_value = cached_data

        result = await service.get_semantic_match(
            "test query",
            query_embedding=query_embedding.tolist()
        )

        # Should find high similarity match
        assert result.similarity > 0.93

    @pytest.mark.asyncio
    async def test_metrics_update_on_lookup(self, service, mock_redis_client):
        """Test that metrics are updated correctly"""
        mock_redis_client.get_cached_query_result.return_value = None
        mock_redis_client.scan_keys = AsyncMock(return_value=[])

        # Initial state
        assert service.metrics.total_requests == 0

        # Perform lookup
        await service.get_semantic_match("query1", query_embedding=[0.1] * 1024)
        assert service.metrics.total_requests == 1

        # Another lookup
        await service.get_semantic_match("query2", query_embedding=[0.1] * 1024)
        assert service.metrics.total_requests == 2


# =============================================================================
# Cache Store Tests
# =============================================================================

class TestCacheStore:
    """Tests for caching search results"""

    @pytest.mark.asyncio
    async def test_cache_search_result(self, service, mock_redis_client):
        """Test caching a search result"""
        query = "test query"
        result = {"results": [{"id": "doc1", "score": 0.9}]}
        embedding = [0.1] * 1024

        success = await service.cache_search_result(
            query=query,
            result=result,
            embedding=embedding
        )

        assert success is True
        mock_redis_client.cache_query_result.assert_called_once()
        mock_redis_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_search_result_generates_embedding(
        self, service, mock_redis_client, mock_embedding_service
    ):
        """Test that embedding is generated if not provided"""
        mock_redis_client.get_cached_embedding.return_value = None

        query = "test query"
        result = {"results": []}

        await service.cache_search_result(query=query, result=result)

        # Should have called embedding service
        mock_embedding_service.generate_embedding.assert_called()


# =============================================================================
# Cache Invalidation Tests
# =============================================================================

class TestCacheInvalidation:
    """Tests for cache invalidation"""

    @pytest.mark.asyncio
    async def test_invalidate_query(self, service, mock_redis_client):
        """Test invalidating a cached query"""
        result = await service.invalidate_query("test query")

        assert result is True
        mock_redis_client.invalidate_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_namespace(self, service, mock_redis_client):
        """Test clearing a cache namespace"""
        mock_redis_client.scan_keys = AsyncMock(return_value=[
            "search:sem:abc",
            "search:sem:def",
            "search:exact:ghi"
        ])

        count = await service.clear_namespace("search")

        assert count == 3
        assert mock_redis_client.redis_client.delete.call_count == 3


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern"""

    def test_get_semantic_cache_service_singleton(self):
        """Test singleton returns same instance"""
        service1 = get_semantic_cache_service()
        service2 = get_semantic_cache_service()

        assert service1 is service2

    def test_reset_singleton(self):
        """Test singleton can be reset"""
        service1 = get_semantic_cache_service()
        reset_semantic_cache_service()
        service2 = get_semantic_cache_service()

        assert service1 is not service2


# =============================================================================
# Integration-like Tests
# =============================================================================

class TestCacheWorkflow:
    """Tests for complete cache workflows"""

    @pytest.mark.asyncio
    async def test_cache_then_retrieve_exact(self, service, mock_redis_client):
        """Test caching then retrieving with exact match"""
        query = "California insurance requirements"
        result = {"results": [{"id": "doc1", "title": "CA Insurance"}]}

        # Cache the result
        await service.cache_search_result(
            query=query,
            result=result,
            embedding=[0.1] * 1024
        )

        # Retrieve via exact match
        mock_redis_client.get_cached_query_result.return_value = result

        lookup = await service.get_semantic_match(query)

        assert lookup.tier == CacheMatchTier.EXACT
        assert lookup.is_usable is True

    @pytest.mark.asyncio
    async def test_target_hit_rate_simulation(self, service, mock_redis_client):
        """Simulate cache usage to test hit rate calculation"""
        # Simulate 100 requests with different outcomes
        for i in range(100):
            if i < 30:  # 30% exact hits
                service.metrics.exact_hits += 1
            elif i < 70:  # 40% high hits
                service.metrics.high_hits += 1
            elif i < 80:  # 10% medium hits
                service.metrics.medium_hits += 1
            else:  # 20% misses
                service.metrics.misses += 1
            service.metrics.total_requests += 1

        # Check hit rate meets target (60-80%)
        hit_rate = service.metrics.cache_hit_rate
        assert 0.6 <= hit_rate <= 0.8
        assert hit_rate == 0.7  # (30 + 40) / 100

    def test_metrics_reset(self, service):
        """Test resetting metrics"""
        # Add some data
        service.metrics.total_requests = 100
        service.metrics.exact_hits = 50

        # Reset
        service.reset_metrics()

        # Verify reset
        assert service.metrics.total_requests == 0
        assert service.metrics.exact_hits == 0
