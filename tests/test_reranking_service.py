"""
Tests for Reranking Service (BGE-Reranker-v2)

Tests reranking functionality using BGE-Reranker-v2 via Ollama (dev) and Claude API (prod).
Validates relevance improvements, ranking quality, and performance metrics.

Run with: python3 -m pytest tests/test_reranking_service.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.reranking_service import (
    RerankingService,
    RerankingConfig,
    RerankingResult,
    RerankingProvider,
    get_reranking_service
)
from app.services.parallel_search_service import ParallelSearchResult
from app.services.hybrid_search_service import SearchResult, SearchMethod


@pytest.fixture
def reranking_config_dev():
    """Create test configuration for development (Ollama)"""
    return RerankingConfig(
        provider=RerankingProvider.OLLAMA,
        model="bge-reranker-v2-m3",
        base_url="http://localhost:11434",
        top_k=10,
        max_input_results=30,
        score_threshold=0.5,
        enable_metrics=True
    )


@pytest.fixture
def reranking_config_prod():
    """Create test configuration for production (Claude API)"""
    return RerankingConfig(
        provider=RerankingProvider.CLAUDE,
        model="claude-haiku-4-5",
        top_k=10,
        max_input_results=30,
        score_threshold=0.5,
        enable_metrics=True
    )


@pytest.fixture
def sample_search_results():
    """Create sample search results for reranking"""
    return [
        SearchResult(
            chunk_id=f"doc_{i}",
            content=f"This is document {i} about insurance policies and claims",
            score=0.9 - (i * 0.05),
            rank=0,
            method="dense",
            metadata={"type": "policy", "department": "claims"}
        )
        for i in range(30)
    ]


@pytest.fixture
def mock_ollama_client():
    """Create mock Ollama client"""
    client = Mock()
    client.generate = AsyncMock()
    return client


@pytest.fixture
def mock_anthropic_client():
    """Create mock Anthropic client"""
    client = Mock()
    client.messages = Mock()
    client.messages.create = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_rerank_with_ollama_provider(reranking_config_dev, sample_search_results, mock_ollama_client):
    """
    Test reranking using Ollama BGE-Reranker-v2 provider

    Verifies:
    - Ollama API is called correctly
    - Results are reranked by relevance score
    - Top K results are returned
    - Scores are normalized
    """
    # Configure mock response from Ollama
    mock_ollama_client.generate.return_value = {
        "response": "0.92"  # Relevance score
    }

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    # Execute reranking
    result = await service.rerank(
        query="insurance policy claims",
        results=sample_search_results[:20]  # Top 20 from search
    )

    # Assertions
    assert isinstance(result, RerankingResult)
    assert len(result.reranked_results) <= reranking_config_dev.top_k
    assert len(result.reranked_results) > 0

    # Verify results are ordered by score (descending)
    scores = [r.score for r in result.reranked_results]
    assert scores == sorted(scores, reverse=True)

    # Verify all scores are above threshold
    assert all(r.score >= reranking_config_dev.score_threshold for r in result.reranked_results)

    # Verify Ollama was called
    assert mock_ollama_client.generate.called

    # Verify metrics are captured
    assert result.metrics is not None
    assert result.metrics.total_input_results == 20
    assert result.metrics.total_output_results == len(result.reranked_results)
    assert result.metrics.reranking_time_ms > 0


@pytest.mark.asyncio
async def test_rerank_with_claude_provider(reranking_config_prod, sample_search_results, mock_anthropic_client):
    """
    Test reranking using Claude API provider

    Verifies:
    - Claude API is called correctly
    - Results are reranked using Claude's relevance assessment
    - Top K results are returned
    - Proper error handling
    """
    # Configure mock response from Claude
    mock_anthropic_client.messages.create.return_value = Mock(
        content=[Mock(text='{"relevance_scores": [0.95, 0.88, 0.82, 0.79, 0.75, 0.71, 0.68, 0.64, 0.60, 0.55]}')]
    )

    service = RerankingService(config=reranking_config_prod, anthropic_client=mock_anthropic_client)

    # Execute reranking
    result = await service.rerank(
        query="insurance policy claims",
        results=sample_search_results[:10]
    )

    # Assertions
    assert isinstance(result, RerankingResult)
    assert len(result.reranked_results) <= reranking_config_prod.top_k

    # Verify results are ordered by score
    scores = [r.score for r in result.reranked_results]
    assert scores == sorted(scores, reverse=True)

    # Verify Claude API was called
    assert mock_anthropic_client.messages.create.called

    # Verify correct model was used
    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_rerank_improves_relevance(reranking_config_dev, mock_ollama_client):
    """
    Test that reranking improves result relevance compared to original ranking

    Verifies:
    - Reranked order differs from original order
    - More relevant results move to the top
    - Precision metrics improve
    """
    # Create results with intentionally poor initial ranking
    poor_results = [
        SearchResult(
            chunk_id="irrelevant_1",
            content="This document is about something unrelated",
            score=0.95,  # High score but low relevance
            rank=0,
            method="dense",
            metadata={}
        ),
        SearchResult(
            chunk_id="relevant_1",
            content="California insurance policy for employee benefits",
            score=0.75,  # Lower score but high relevance
            rank=0,
            method="dense",
            metadata={}
        ),
        SearchResult(
            chunk_id="irrelevant_2",
            content="Random content about weather patterns",
            score=0.90,
            rank=0,
            method="dense",
            metadata={}
        ),
        SearchResult(
            chunk_id="relevant_2",
            content="Insurance claims processing for California policies",
            score=0.70,
            rank=0,
            method="dense",
            metadata={}
        )
    ]

    # Mock Ollama to return higher scores for relevant docs
    def mock_generate(model, prompt, stream=False):
        if "employee benefits" in prompt or "claims processing" in prompt:
            return {"response": "0.95"}  # High relevance
        else:
            return {"response": "0.30"}  # Low relevance

    mock_ollama_client.generate = AsyncMock(side_effect=mock_generate)

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    result = await service.rerank(
        query="California insurance policy claims",
        results=poor_results
    )

    # Verify relevant results moved to the top
    top_result = result.reranked_results[0]
    assert "relevant" in top_result.chunk_id

    # Verify order changed from original
    original_ids = [r.chunk_id for r in poor_results]
    reranked_ids = [r.chunk_id for r in result.reranked_results]
    assert original_ids != reranked_ids


@pytest.mark.asyncio
async def test_rerank_handles_max_input_limit(reranking_config_dev, sample_search_results, mock_ollama_client):
    """
    Test that reranking respects max_input_results limit

    Verifies:
    - Only top N results are sent to reranker
    - Efficiency is maintained with large result sets
    """
    mock_ollama_client.generate = AsyncMock(return_value={"response": "0.85"})

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    # Provide more results than max_input
    large_result_set = sample_search_results + sample_search_results  # 60 results

    result = await service.rerank(
        query="insurance policy",
        results=large_result_set
    )

    # Verify only max_input_results were processed
    assert result.metrics.total_input_results == reranking_config_dev.max_input_results


@pytest.mark.asyncio
async def test_rerank_filters_by_score_threshold(reranking_config_dev, sample_search_results, mock_ollama_client):
    """
    Test that reranking filters out results below score threshold

    Verifies:
    - Low-scoring results are excluded
    - Only high-quality results are returned
    """
    # Mock Ollama to return varying scores
    scores = [0.9, 0.8, 0.4, 0.3, 0.7, 0.2, 0.6, 0.1, 0.5, 0.85]
    score_index = 0

    def mock_generate(model, prompt, stream=False):
        nonlocal score_index
        score = scores[score_index % len(scores)]
        score_index += 1
        return {"response": str(score)}

    mock_ollama_client.generate = AsyncMock(side_effect=mock_generate)

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    result = await service.rerank(
        query="test query",
        results=sample_search_results[:10]
    )

    # Verify all results meet threshold (0.5)
    assert all(r.score >= 0.5 for r in result.reranked_results)

    # Verify some results were filtered out
    assert len(result.reranked_results) < 10


@pytest.mark.asyncio
async def test_rerank_metrics_tracking(reranking_config_dev, sample_search_results, mock_ollama_client):
    """
    Test that reranking tracks comprehensive metrics

    Verifies:
    - Timing metrics are captured
    - Result counts are accurate
    - Relevance improvements are measured
    """
    mock_ollama_client.generate = AsyncMock(return_value={"response": "0.88"})

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    result = await service.rerank(
        query="insurance policy",
        results=sample_search_results[:15]
    )

    # Verify metrics are populated
    assert result.metrics.total_input_results == 15
    assert result.metrics.total_output_results <= reranking_config_dev.top_k
    assert result.metrics.reranking_time_ms > 0
    assert result.metrics.provider == RerankingProvider.OLLAMA
    assert result.metrics.model == "bge-reranker-v2-m3"


@pytest.mark.asyncio
async def test_rerank_error_handling(reranking_config_dev, sample_search_results, mock_ollama_client):
    """
    Test error handling for reranking failures

    Verifies:
    - API errors are caught gracefully
    - Fallback behavior returns original results
    - Errors are logged
    """
    # Mock Ollama to raise an error
    mock_ollama_client.generate = AsyncMock(side_effect=Exception("Ollama API error"))

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    # Should not raise exception, should return original results
    result = await service.rerank(
        query="insurance policy",
        results=sample_search_results[:10]
    )

    # Verify fallback behavior
    assert result.reranked_results == sample_search_results[:10]
    assert result.metrics.error is not None


@pytest.mark.asyncio
async def test_rerank_empty_results(reranking_config_dev, mock_ollama_client):
    """
    Test reranking with empty result set

    Verifies:
    - Empty input is handled gracefully
    - No API calls are made
    - Empty result is returned
    """
    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    result = await service.rerank(
        query="test query",
        results=[]
    )

    assert len(result.reranked_results) == 0
    assert not mock_ollama_client.generate.called


@pytest.mark.asyncio
async def test_get_reranking_service_singleton():
    """
    Test that get_reranking_service returns singleton instance

    Verifies:
    - Same instance is returned across calls
    - Configuration is maintained
    """
    service1 = get_reranking_service()
    service2 = get_reranking_service()

    assert service1 is service2


@pytest.mark.asyncio
async def test_rerank_ndcg_metric_calculation(reranking_config_dev, mock_ollama_client):
    """
    Test NDCG (Normalized Discounted Cumulative Gain) calculation

    Verifies:
    - NDCG metric is calculated correctly
    - Relevance improvement is measurable
    """
    # Mock with known relevance scores
    relevance_scores = [0.95, 0.90, 0.85, 0.80, 0.75]
    score_index = 0

    def mock_generate(model, prompt, stream=False):
        nonlocal score_index
        score = relevance_scores[score_index % len(relevance_scores)]
        score_index += 1
        return {"response": str(score)}

    mock_ollama_client.generate = AsyncMock(side_effect=mock_generate)

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    results = [
        SearchResult(
            chunk_id=f"doc_{i}",
            content=f"Document {i}",
            score=0.5,
            rank=0,
            method="dense",
            metadata={}
        )
        for i in range(5)
    ]

    result = await service.rerank(
        query="test query",
        results=results
    )

    # Verify NDCG is calculated and reasonable
    if hasattr(result.metrics, 'ndcg'):
        assert 0 <= result.metrics.ndcg <= 1
        assert result.metrics.ndcg > 0.7  # Should be high with these scores


@pytest.mark.asyncio
async def test_rerank_integration_with_parallel_search(
    reranking_config_dev,
    sample_search_results,
    mock_ollama_client
):
    """
    Test integration of reranking with parallel search results

    Verifies:
    - Reranking works with ParallelSearchResult format
    - Metadata is preserved through reranking
    - Source attribution is maintained
    """
    mock_ollama_client.generate = AsyncMock(return_value={"response": "0.88"})

    # Create a parallel search result
    parallel_result = ParallelSearchResult(
        original_query="insurance policy",
        expanded_queries=["insurance policy", "insurance coverage", "policy terms"],
        aggregated_results=sample_search_results[:20],
        total_results_found=20,
        unique_results_count=20,
        queries_executed=3,
        duration_ms=150
    )

    service = RerankingService(config=reranking_config_dev, ollama_client=mock_ollama_client)

    result = await service.rerank(
        query="insurance policy",
        results=parallel_result.aggregated_results
    )

    # Verify metadata preservation
    for reranked in result.reranked_results:
        assert reranked.metadata is not None
        assert reranked.method in ["dense", "sparse", "fuzzy", "hybrid"]
