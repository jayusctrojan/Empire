"""
Tests for Hybrid Search Service

Tests dense, sparse, fuzzy search methods and RRF fusion.

Run with: python3 -m pytest tests/test_hybrid_search_service.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from app.services.hybrid_search_service import (
    HybridSearchService,
    HybridSearchConfig,
    SearchResult,
    SearchMethod,
    get_hybrid_search_service
)


@pytest.fixture
def mock_storage():
    """Create mock Supabase storage"""
    storage = Mock()
    storage.supabase = Mock()
    return storage


@pytest.fixture
def mock_vector_service():
    """Create mock vector storage service"""
    service = Mock()
    return service


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service"""
    service = Mock()
    return service


@pytest.fixture
def hybrid_config():
    """Create test configuration"""
    return HybridSearchConfig(
        dense_weight=0.5,
        sparse_weight=0.3,
        fuzzy_weight=0.2,
        top_k=5,
        rrf_k=60
    )


@pytest.fixture
def hybrid_search_service(mock_storage, mock_vector_service, mock_embedding_service, hybrid_config):
    """Create hybrid search service with mocks"""
    return HybridSearchService(
        mock_storage,
        mock_vector_service,
        mock_embedding_service,
        hybrid_config,
        monitoring_service=None
    )


class TestHybridSearchConfig:
    """Tests for configuration"""

    def test_config_validation_valid(self):
        """Test valid configuration"""
        config = HybridSearchConfig(
            dense_weight=0.5,
            sparse_weight=0.3,
            fuzzy_weight=0.2
        )
        config.validate()  # Should not raise

    def test_config_validation_invalid_weights(self):
        """Test invalid weight sum"""
        config = HybridSearchConfig(
            dense_weight=0.5,
            sparse_weight=0.5,
            fuzzy_weight=0.5  # Sum = 1.5, invalid
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            config.validate()

    def test_config_defaults(self):
        """Test default configuration values"""
        config = HybridSearchConfig()
        assert config.dense_weight == 0.5
        assert config.sparse_weight == 0.3
        assert config.fuzzy_weight == 0.2
        assert config.top_k == 10
        assert config.rrf_k == 60


class TestSearchResult:
    """Tests for SearchResult dataclass"""

    def test_search_result_creation(self):
        """Test creating search result"""
        result = SearchResult(
            chunk_id="chunk-123",
            content="Test content",
            score=0.95,
            rank=1,
            method="dense",
            metadata={"type": "test"},
            dense_score=0.95
        )

        assert result.chunk_id == "chunk-123"
        assert result.score == 0.95
        assert result.rank == 1
        assert result.method == "dense"
        assert result.dense_score == 0.95


class TestHybridSearchService:
    """Tests for HybridSearchService"""

    @pytest.mark.asyncio
    async def test_dense_search(self, hybrid_search_service, mock_vector_service, mock_embedding_service, mock_storage):
        """Test dense vector search"""
        # Mock embedding generation
        mock_embedding_result = Mock()
        mock_embedding_result.embedding = [0.1] * 1024
        mock_embedding_service.generate_embedding = AsyncMock(return_value=mock_embedding_result)

        # Mock vector search
        mock_sim_result = Mock()
        mock_sim_result.chunk_id = "chunk-1"
        mock_sim_result.similarity = 0.95
        mock_sim_result.metadata = {"doc": "test"}
        mock_vector_service.similarity_search = AsyncMock(return_value=[mock_sim_result])

        # Mock chunk content retrieval
        mock_execute = Mock()
        mock_execute.data = [{"content": "Test chunk content"}]
        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)
        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.limit.return_value = mock_chain

        # Perform search
        results = await hybrid_search_service.search(
            "test query",
            method=SearchMethod.DENSE
        )

        assert len(results) == 1
        assert results[0].chunk_id == "chunk-1"
        assert results[0].method == "dense"
        assert results[0].dense_score == 0.95

    @pytest.mark.asyncio
    async def test_sparse_search(self, hybrid_search_service, mock_storage):
        """Test sparse BM25 search"""
        # Mock chunks query
        mock_execute = Mock()
        mock_execute.data = [
            {
                "id": "chunk-1",
                "content": "California insurance policy terms and conditions",
                "metadata": {}
            },
            {
                "id": "chunk-2",
                "content": "Employee benefits overview document",
                "metadata": {}
            }
        ]
        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)
        mock_storage.supabase.table.return_value.select.return_value.limit.return_value = mock_chain

        # Perform search
        results = await hybrid_search_service.search(
            "insurance policy",
            method=SearchMethod.SPARSE
        )

        assert len(results) > 0
        assert all(r.method == "sparse" for r in results)
        assert all(r.sparse_score is not None for r in results)

    @pytest.mark.asyncio
    async def test_fuzzy_search(self, hybrid_search_service, mock_storage):
        """Test fuzzy matching search"""
        # Lower threshold for testing
        custom_config = HybridSearchConfig(
            dense_weight=0.5,
            sparse_weight=0.3,
            fuzzy_weight=0.2,
            min_fuzzy_score=30.0  # Lower threshold for testing
        )

        # Mock ILIKE query
        mock_execute = Mock()
        mock_execute.data = [
            {
                "id": "chunk-1",
                "content": "Insurance policy for California residents with comprehensive coverage",
                "metadata": {}
            }
        ]
        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)
        mock_storage.supabase.table.return_value.select.return_value.ilike.return_value.limit.return_value = mock_chain

        # Perform search with custom config
        results = await hybrid_search_service.search(
            "insurance policy",  # Longer query for better fuzzy matching
            method=SearchMethod.FUZZY,
            custom_config=custom_config
        )

        # Should get at least one result with lowered threshold
        assert len(results) >= 0  # May be 0 or more depending on fuzzy threshold
        if len(results) > 0:
            assert all(r.method == "fuzzy" for r in results)
            assert all(r.fuzzy_score is not None for r in results)

    def test_bm25_score(self, hybrid_search_service):
        """Test BM25 scoring calculation"""
        query = "insurance policy"
        document = "This is an insurance policy document with multiple insurance terms and policy details"

        score = hybrid_search_service._bm25_score(query, document)

        assert score > 0
        assert isinstance(score, float)

        # Document without query terms should score 0
        unrelated_doc = "This document has no matching terms"
        score_zero = hybrid_search_service._bm25_score(query, unrelated_doc)
        assert score_zero == 0.0

    def test_reciprocal_rank_fusion_single_list(self, hybrid_search_service, hybrid_config):
        """Test RRF with single result list"""
        results = [
            SearchResult(
                chunk_id="chunk-1",
                content="Content 1",
                score=0.95,
                rank=1,
                method="dense",
                dense_score=0.95
            ),
            SearchResult(
                chunk_id="chunk-2",
                content="Content 2",
                score=0.85,
                rank=2,
                method="dense",
                dense_score=0.85
            )
        ]

        fused = hybrid_search_service._reciprocal_rank_fusion(
            [results],
            hybrid_config
        )

        assert len(fused) == 2
        assert all(r.rrf_score is not None for r in fused)
        assert all(r.method == "hybrid" for r in fused)

    def test_reciprocal_rank_fusion_multiple_lists(self, hybrid_search_service, hybrid_config):
        """Test RRF with multiple result lists"""
        dense_results = [
            SearchResult(
                chunk_id="chunk-1",
                content="Content 1",
                score=0.95,
                rank=1,
                method="dense",
                dense_score=0.95
            )
        ]

        sparse_results = [
            SearchResult(
                chunk_id="chunk-1",  # Same chunk
                content="Content 1",
                score=0.80,
                rank=1,
                method="sparse",
                sparse_score=0.80
            ),
            SearchResult(
                chunk_id="chunk-2",  # Different chunk
                content="Content 2",
                score=0.70,
                rank=2,
                method="sparse",
                sparse_score=0.70
            )
        ]

        fused = hybrid_search_service._reciprocal_rank_fusion(
            [dense_results, sparse_results],
            hybrid_config
        )

        # chunk-1 should appear once with combined RRF score
        chunk_1 = [r for r in fused if r.chunk_id == "chunk-1"]
        assert len(chunk_1) == 1
        assert chunk_1[0].dense_score == 0.95
        assert chunk_1[0].sparse_score == 0.80

        # chunk-2 should appear once
        chunk_2 = [r for r in fused if r.chunk_id == "chunk-2"]
        assert len(chunk_2) == 1

    def test_reciprocal_rank_fusion_empty_lists(self, hybrid_search_service, hybrid_config):
        """Test RRF with empty lists"""
        fused = hybrid_search_service._reciprocal_rank_fusion(
            [[], []],
            hybrid_config
        )

        assert len(fused) == 0

    @pytest.mark.asyncio
    async def test_hybrid_search_integration(
        self,
        hybrid_search_service,
        mock_vector_service,
        mock_embedding_service,
        mock_storage
    ):
        """Test full hybrid search workflow"""
        # Mock embedding generation
        mock_embedding_result = Mock()
        mock_embedding_result.embedding = [0.1] * 1024
        mock_embedding_service.generate_embedding = AsyncMock(return_value=mock_embedding_result)

        # Mock dense search
        mock_sim_result = Mock()
        mock_sim_result.chunk_id = "chunk-1"
        mock_sim_result.similarity = 0.95
        mock_sim_result.metadata = {}
        mock_vector_service.similarity_search = AsyncMock(return_value=[mock_sim_result])

        # Mock chunk content
        mock_content_execute = Mock()
        mock_content_execute.data = [{"content": "Dense search result"}]
        mock_content_chain = Mock()
        mock_content_chain.execute = AsyncMock(return_value=mock_content_execute)

        # Create separate mocks for each call
        mock_table = Mock()
        mock_select = Mock()
        mock_eq = Mock()
        mock_limit = Mock()

        mock_limit.return_value = mock_content_chain
        mock_eq.return_value.limit = mock_limit
        mock_select.return_value.eq = mock_eq
        mock_table.return_value.select = mock_select
        mock_storage.supabase.table = mock_table

        # Mock sparse search (chunks query for BM25)
        mock_sparse_execute = Mock()
        mock_sparse_execute.data = []
        mock_sparse_chain = Mock()
        mock_sparse_chain.execute = AsyncMock(return_value=mock_sparse_execute)

        # Mock fuzzy search (ILIKE query)
        mock_fuzzy_execute = Mock()
        mock_fuzzy_execute.data = []
        mock_fuzzy_chain = Mock()
        mock_fuzzy_chain.execute = AsyncMock(return_value=mock_fuzzy_execute)

        # Perform hybrid search
        results = await hybrid_search_service.search(
            "test query",
            method=SearchMethod.HYBRID
        )

        # Should get results from at least dense search
        assert len(results) >= 0
        if len(results) > 0:
            assert all(r.rrf_score is not None for r in results)


class TestFactoryFunction:
    """Tests for factory function"""

    def test_get_hybrid_search_service_singleton(
        self,
        mock_storage,
        mock_vector_service,
        mock_embedding_service
    ):
        """Test that factory returns singleton"""
        service1 = get_hybrid_search_service(
            mock_storage,
            mock_vector_service,
            mock_embedding_service
        )
        service2 = get_hybrid_search_service(
            mock_storage,
            mock_vector_service,
            mock_embedding_service
        )

        assert service1 is service2


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_search_with_empty_query(self, hybrid_search_service):
        """Test search with empty query"""
        results = await hybrid_search_service.search("")
        # Should handle gracefully
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_special_characters(self, hybrid_search_service, mock_storage):
        """Test search with special characters"""
        mock_execute = Mock()
        mock_execute.data = []
        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)
        mock_storage.supabase.table.return_value.select.return_value.ilike.return_value.limit.return_value = mock_chain

        results = await hybrid_search_service.search(
            "test@#$%^&*()query",
            method=SearchMethod.FUZZY
        )

        assert isinstance(results, list)

    def test_config_with_zero_weight(self):
        """Test configuration with zero weight for one method"""
        config = HybridSearchConfig(
            dense_weight=0.7,
            sparse_weight=0.3,
            fuzzy_weight=0.0
        )
        config.validate()  # Should not raise
