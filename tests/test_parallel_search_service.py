"""
Tests for Parallel Search Service

Tests query expansion integration, parallel execution, result aggregation,
and deduplication strategies.

Run with: python3 -m pytest tests/test_parallel_search_service.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.parallel_search_service import (
    ParallelSearchService,
    ParallelSearchConfig,
    ParallelSearchResult,
    get_parallel_search_service
)
from app.services.query_expansion_service import QueryExpansionResult, ExpansionStrategy
from app.services.hybrid_search_service import SearchResult, SearchMethod


@pytest.fixture
def parallel_config():
    """Create test configuration"""
    return ParallelSearchConfig(
        enable_expansion=True,
        num_query_variations=3,
        max_concurrent_searches=5,
        enable_deduplication=True,
        max_results=10,
        aggregation_method="score_weighted"
    )


@pytest.fixture
def mock_query_expander():
    """Create mock query expansion service"""
    expander = Mock()
    expander.get_cache_stats = Mock(return_value={"cache_size": 0})
    return expander


@pytest.fixture
def mock_hybrid_searcher():
    """Create mock hybrid search service"""
    searcher = Mock()
    return searcher


@pytest.fixture
def parallel_search_service(parallel_config, mock_query_expander, mock_hybrid_searcher):
    """Create parallel search service with mocks"""
    return ParallelSearchService(
        query_expansion_service=mock_query_expander,
        hybrid_search_service=mock_hybrid_searcher,
        config=parallel_config,
        monitoring_service=None
    )


class TestParallelSearchConfig:
    """Tests for configuration"""

    def test_config_defaults(self):
        """Test default configuration values"""
        config = ParallelSearchConfig()
        assert config.enable_expansion is True
        assert config.num_query_variations == 5
        assert config.max_concurrent_searches == 10
        assert config.aggregation_method == "score_weighted"

    def test_config_custom_values(self):
        """Test custom configuration"""
        config = ParallelSearchConfig(
            enable_expansion=False,
            num_query_variations=10,
            aggregation_method="frequency"
        )
        assert config.enable_expansion is False
        assert config.num_query_variations == 10
        assert config.aggregation_method == "frequency"


class TestParallelSearchService:
    """Tests for ParallelSearchService"""

    @pytest.mark.asyncio
    async def test_search_with_expansion(
        self,
        parallel_search_service,
        mock_query_expander,
        mock_hybrid_searcher
    ):
        """Test search with query expansion enabled"""
        # Mock query expansion
        mock_query_expander.expand_query = AsyncMock(return_value=QueryExpansionResult(
            original_query="insurance policy",
            expanded_queries=[
                "insurance policy",
                "insurance coverage",
                "insurance plan"
            ],
            strategy="balanced",
            model_used="claude-3-5-haiku-20241022",
            tokens_used=100,
            duration_ms=500.0
        ))

        # Mock hybrid search results
        mock_hybrid_searcher.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id="chunk-1",
                content="Insurance policy content",
                score=0.95,
                rank=1,
                method="hybrid"
            )
        ])

        # Execute search
        result = await parallel_search_service.search(
            "insurance policy",
            expand_queries=True,
            num_variations=3
        )

        # Verify
        assert result.original_query == "insurance policy"
        assert len(result.expanded_queries) == 3
        assert result.queries_executed == 3
        assert result.unique_results_count > 0
        assert mock_query_expander.expand_query.called
        assert mock_hybrid_searcher.search.call_count == 3

    @pytest.mark.asyncio
    async def test_search_without_expansion(
        self,
        parallel_search_service,
        mock_query_expander,
        mock_hybrid_searcher
    ):
        """Test search without query expansion"""
        mock_hybrid_searcher.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id="chunk-1",
                content="Content",
                score=0.9,
                rank=1,
                method="hybrid"
            )
        ])

        result = await parallel_search_service.search(
            "test query",
            expand_queries=False
        )

        assert result.queries_executed == 1
        assert len(result.expanded_queries) == 1
        assert result.expanded_queries[0] == "test query"
        assert not mock_query_expander.expand_query.called
        assert mock_hybrid_searcher.search.call_count == 1

    @pytest.mark.asyncio
    async def test_search_expansion_failure_fallback(
        self,
        parallel_search_service,
        mock_query_expander,
        mock_hybrid_searcher
    ):
        """Test fallback to original query when expansion fails"""
        # Mock expansion failure
        mock_query_expander.expand_query = AsyncMock(side_effect=Exception("Expansion failed"))

        mock_hybrid_searcher.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id="chunk-1",
                content="Content",
                score=0.9,
                rank=1,
                method="hybrid"
            )
        ])

        result = await parallel_search_service.search(
            "test query",
            expand_queries=True
        )

        # Should fall back to original query only
        assert result.queries_executed == 1
        assert result.expanded_queries == ["test query"]


class TestAggregation:
    """Tests for result aggregation and deduplication"""

    def create_search_results(self, results_data):
        """Helper to create SearchResult objects"""
        return [
            SearchResult(
                chunk_id=data["chunk_id"],
                content=data.get("content", "Test content"),
                score=data["score"],
                rank=idx + 1,
                method="hybrid",
                metadata=data.get("metadata", {})
            )
            for idx, data in enumerate(results_data)
        ]

    def test_aggregate_results_score_weighted(self, parallel_search_service):
        """Test score-weighted aggregation"""
        # Two queries with overlapping results
        all_results = [
            # Query 1 results
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.9},
                {"chunk_id": "chunk-2", "score": 0.8}
            ]),
            # Query 2 results
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.85},  # Duplicate
                {"chunk_id": "chunk-3", "score": 0.7}
            ])
        ]

        queries = ["query1", "query2"]
        aggregated = parallel_search_service._aggregate_results(all_results, queries)

        # Should have 3 unique results
        assert len(aggregated) == 3
        chunk_ids = [r.chunk_id for r in aggregated]
        assert "chunk-1" in chunk_ids
        assert "chunk-2" in chunk_ids
        assert "chunk-3" in chunk_ids

        # chunk-1 should have weighted score (appeared in both queries)
        chunk_1 = [r for r in aggregated if r.chunk_id == "chunk-1"][0]
        assert chunk_1.metadata["appearances"] == 2

    def test_aggregate_results_frequency(self, parallel_search_service):
        """Test frequency-based aggregation"""
        parallel_search_service.config.aggregation_method = "frequency"

        all_results = [
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.9}
            ]),
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.8}
            ]),
            self.create_search_results([
                {"chunk_id": "chunk-2", "score": 0.95}
            ])
        ]

        queries = ["q1", "q2", "q3"]
        aggregated = parallel_search_service._aggregate_results(all_results, queries)

        chunk_1 = [r for r in aggregated if r.chunk_id == "chunk-1"][0]
        chunk_2 = [r for r in aggregated if r.chunk_id == "chunk-2"][0]

        # chunk-1 appeared in 2/3 queries = 0.667
        # chunk-2 appeared in 1/3 queries = 0.333
        assert chunk_1.score > chunk_2.score

    def test_aggregate_results_max_score(self, parallel_search_service):
        """Test max score aggregation"""
        parallel_search_service.config.aggregation_method = "max_score"

        all_results = [
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.8}
            ]),
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.95}  # Higher score
            ])
        ]

        queries = ["q1", "q2"]
        aggregated = parallel_search_service._aggregate_results(all_results, queries)

        chunk_1 = aggregated[0]
        # Should use max score
        assert chunk_1.score == 0.95

    def test_aggregate_results_no_deduplication(self, parallel_search_service):
        """Test aggregation without deduplication"""
        parallel_search_service.config.enable_deduplication = False

        all_results = [
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.9}
            ]),
            self.create_search_results([
                {"chunk_id": "chunk-1", "score": 0.8}  # Duplicate
            ])
        ]

        queries = ["q1", "q2"]
        aggregated = parallel_search_service._aggregate_results(all_results, queries)

        # Should have duplicates
        assert len(aggregated) == 2

    def test_sort_and_limit_results(self, parallel_search_service):
        """Test sorting and limiting results"""
        results = self.create_search_results([
            {"chunk_id": "chunk-1", "score": 0.7},
            {"chunk_id": "chunk-2", "score": 0.9},
            {"chunk_id": "chunk-3", "score": 0.8},
            {"chunk_id": "chunk-4", "score": 0.95}
        ])

        sorted_limited = parallel_search_service._sort_and_limit_results(results, max_results=2)

        # Should return top 2
        assert len(sorted_limited) == 2
        assert sorted_limited[0].chunk_id == "chunk-4"  # Highest score
        assert sorted_limited[1].chunk_id == "chunk-2"  # Second highest

    def test_sort_and_limit_with_min_score(self, parallel_search_service):
        """Test filtering by minimum score"""
        parallel_search_service.config.min_similarity_score = 0.8

        results = self.create_search_results([
            {"chunk_id": "chunk-1", "score": 0.7},  # Below threshold
            {"chunk_id": "chunk-2", "score": 0.9},
            {"chunk_id": "chunk-3", "score": 0.85}
        ])

        filtered = parallel_search_service._sort_and_limit_results(results, max_results=10)

        # Only results >= 0.8
        assert len(filtered) == 2
        assert all(r.score >= 0.8 for r in filtered)


class TestParallelExecution:
    """Tests for parallel search execution"""

    @pytest.mark.asyncio
    async def test_execute_parallel_searches(
        self,
        parallel_search_service,
        mock_hybrid_searcher
    ):
        """Test parallel execution of multiple searches"""
        # Mock different results for different queries
        async def mock_search(query, **kwargs):
            if "query1" in query:
                return [SearchResult(chunk_id="chunk-1", content="Content 1",
                                   score=0.9, rank=1, method="hybrid")]
            elif "query2" in query:
                return [SearchResult(chunk_id="chunk-2", content="Content 2",
                                   score=0.8, rank=1, method="hybrid")]
            else:
                return []

        mock_hybrid_searcher.search = AsyncMock(side_effect=mock_search)

        queries = ["query1", "query2", "query3"]
        results = await parallel_search_service._execute_parallel_searches(
            queries,
            SearchMethod.HYBRID,
            None,
            None,
            None
        )

        assert len(results) == 3
        assert len(results[0]) == 1  # query1 result
        assert len(results[1]) == 1  # query2 result
        assert len(results[2]) == 0  # query3 no results

    @pytest.mark.asyncio
    async def test_execute_parallel_searches_with_timeout(
        self,
        parallel_search_service,
        mock_hybrid_searcher
    ):
        """Test handling of search timeouts"""
        import asyncio

        # Mock slow search
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(100)  # Very slow
            return []

        mock_hybrid_searcher.search = AsyncMock(side_effect=slow_search)
        parallel_search_service.config.search_timeout_seconds = 0.1

        queries = ["query1"]
        results = await parallel_search_service._execute_parallel_searches(
            queries,
            SearchMethod.HYBRID,
            None,
            None,
            None
        )

        # Should return empty due to timeout
        assert len(results) == 1
        assert results[0] == []

    @pytest.mark.asyncio
    async def test_execute_parallel_searches_with_errors(
        self,
        parallel_search_service,
        mock_hybrid_searcher
    ):
        """Test handling of search errors"""
        # First search fails, second succeeds
        mock_hybrid_searcher.search = AsyncMock(side_effect=[
            Exception("Search error"),
            [SearchResult(chunk_id="chunk-1", content="Content", score=0.9, rank=1, method="hybrid")]
        ])

        queries = ["query1", "query2"]
        results = await parallel_search_service._execute_parallel_searches(
            queries,
            SearchMethod.HYBRID,
            None,
            None,
            None
        )

        assert len(results) == 2
        assert results[0] == []  # Failed search
        assert len(results[1]) == 1  # Successful search


class TestBatchSearch:
    """Tests for batch search functionality"""

    @pytest.mark.asyncio
    async def test_batch_search(
        self,
        parallel_search_service,
        mock_query_expander,
        mock_hybrid_searcher
    ):
        """Test batch processing of multiple queries"""
        mock_query_expander.expand_query = AsyncMock(return_value=QueryExpansionResult(
            original_query="test",
            expanded_queries=["test", "query"],
            strategy="balanced",
            model_used="claude",
            tokens_used=50,
            duration_ms=100.0
        ))

        mock_hybrid_searcher.search = AsyncMock(return_value=[
            SearchResult(chunk_id="chunk-1", content="Content", score=0.9, rank=1, method="hybrid")
        ])

        queries = ["query1", "query2", "query3"]
        results = await parallel_search_service.batch_search(
            queries,
            expand_queries=True,
            num_variations=2
        )

        assert len(results) == 3
        assert all(isinstance(r, ParallelSearchResult) for r in results)
        assert results[0].original_query == "query1"
        assert results[1].original_query == "query2"
        assert results[2].original_query == "query3"

    @pytest.mark.asyncio
    async def test_batch_search_with_errors(
        self,
        parallel_search_service,
        mock_query_expander,
        mock_hybrid_searcher
    ):
        """Test batch search error handling"""
        # First query fails, second succeeds
        async def mock_search_side_effect(query, **kwargs):
            if query == "query1":
                raise Exception("Search failed")
            return [SearchResult(chunk_id="chunk-1", content="Content", score=0.9, rank=1, method="hybrid")]

        mock_query_expander.expand_query = AsyncMock(side_effect=[
            Exception("Expansion failed"),
            QueryExpansionResult(
                original_query="query2",
                expanded_queries=["query2"],
                strategy="balanced",
                model_used="claude",
                tokens_used=50,
                duration_ms=100.0
            )
        ])

        mock_hybrid_searcher.search = AsyncMock(side_effect=mock_search_side_effect)

        queries = ["query1", "query2"]
        results = await parallel_search_service.batch_search(queries, expand_queries=True)

        assert len(results) == 2
        # First result should have error
        assert results[0].queries_executed == 1  # Fell back to original
        # Second result should succeed
        assert results[1].unique_results_count > 0


class TestUtilities:
    """Tests for utility functions"""

    def test_get_stats(self, parallel_search_service, mock_query_expander):
        """Test statistics retrieval"""
        stats = parallel_search_service.get_stats()

        assert "config" in stats
        assert "query_expander_cache" in stats
        assert stats["config"]["enable_expansion"] is True
        assert stats["config"]["aggregation_method"] == "score_weighted"


class TestFactoryFunction:
    """Tests for factory function"""

    def test_get_parallel_search_service_singleton(self, monkeypatch):
        """Test that factory returns singleton"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        with patch('app.services.query_expansion_service.AsyncAnthropic'), \
             patch('app.services.parallel_search_service.get_query_expansion_service'), \
             patch('app.services.parallel_search_service.get_hybrid_search_service'):
            service1 = get_parallel_search_service()
            service2 = get_parallel_search_service()

            assert service1 is service2
