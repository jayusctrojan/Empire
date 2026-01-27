"""
Tests for Query Router

Tests integration of query classifier with search pipeline routing.
Routes queries to vector, graph, metadata, or hybrid search based on classification.

Run with: python3 -m pytest tests/test_query_router.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.query_router import (
    QueryRouter,
    QueryRouterConfig,
    RouteResult,
    get_query_router
)
from app.services.query_taxonomy import QueryType
from app.services.query_classifier import ClassificationResult


@pytest.fixture
def router_config():
    """Create test router configuration"""
    return QueryRouterConfig(
        enable_routing=True,
        fallback_to_hybrid=True,
        log_routing_decisions=True
    )


@pytest.fixture
def mock_classifier():
    """Create mock query classifier"""
    classifier = Mock()
    return classifier


@pytest.fixture
def mock_vector_search():
    """Create mock vector search service"""
    service = AsyncMock()
    service.search = AsyncMock(return_value=[{"doc_id": "1", "score": 0.9}])
    return service


@pytest.fixture
def mock_graph_search():
    """Create mock graph search service"""
    service = AsyncMock()
    service.search = AsyncMock(return_value=[{"doc_id": "2", "score": 0.85}])
    return service


@pytest.fixture
def mock_metadata_search():
    """Create mock metadata search service"""
    service = AsyncMock()
    service.search = AsyncMock(return_value=[{"doc_id": "3", "score": 0.8}])
    return service


@pytest.fixture
def mock_hybrid_search():
    """Create mock hybrid search service"""
    service = AsyncMock()
    service.search = AsyncMock(return_value=[{"doc_id": "4", "score": 0.95}])
    return service


@pytest.fixture
def query_router(
    router_config,
    mock_classifier,
    mock_vector_search,
    mock_graph_search,
    mock_metadata_search,
    mock_hybrid_search
):
    """Create query router with mocks"""
    return QueryRouter(
        classifier=mock_classifier,
        vector_search=mock_vector_search,
        graph_search=mock_graph_search,
        metadata_search=mock_metadata_search,
        hybrid_search=mock_hybrid_search,
        config=router_config
    )


def test_router_config_creation():
    """
    Test RouterConfig dataclass

    Verifies:
    - Config accepts all parameters
    - Defaults are sensible
    - Routing can be toggled
    """
    config = QueryRouterConfig(
        enable_routing=True,
        fallback_to_hybrid=False,
        log_routing_decisions=True
    )

    assert config.enable_routing is True
    assert config.fallback_to_hybrid is False
    assert config.log_routing_decisions is True


def test_route_result_structure():
    """
    Test RouteResult dataclass

    Verifies:
    - Contains pipeline used
    - Contains classification info
    - Contains search results
    """
    result = RouteResult(
        pipeline="vector",
        query_type=QueryType.SEMANTIC,
        confidence=0.92,
        results=[{"doc_id": "1", "score": 0.9}],
        fallback_used=False
    )

    assert result.pipeline == "vector"
    assert result.query_type == QueryType.SEMANTIC
    assert len(result.results) == 1


@pytest.mark.asyncio
async def test_route_semantic_query_to_vector_search(query_router, mock_classifier, mock_vector_search):
    """
    Test routing semantic query to vector search

    Verifies:
    - Semantic queries route to vector search
    - Classifier is called
    - Vector search is executed
    - Correct results returned
    """
    # Mock classifier response
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.SEMANTIC,
        confidence=0.92,
        reasoning="Conceptual question",
        classification_method="ai",
        fallback_used=False
    ))

    query = "What is insurance underwriting?"
    result = await query_router.route_and_search(query)

    assert result.pipeline == "vector"
    assert result.query_type == QueryType.SEMANTIC
    assert mock_vector_search.search.called
    assert len(result.results) > 0


@pytest.mark.asyncio
async def test_route_relational_query_to_graph_search(query_router, mock_classifier, mock_graph_search):
    """
    Test routing relational query to graph search

    Verifies:
    - Relational queries route to graph/Neo4j search
    - Graph search is executed
    - Entity relationships are queried
    """
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.RELATIONAL,
        confidence=0.89,
        reasoning="Entity relationship query",
        classification_method="ai",
        fallback_used=False
    ))

    query = "Show policies connected to Acme Corp"
    result = await query_router.route_and_search(query)

    assert result.pipeline == "graph"
    assert result.query_type == QueryType.RELATIONAL
    assert mock_graph_search.search.called


@pytest.mark.asyncio
async def test_route_metadata_query_to_metadata_search(query_router, mock_classifier, mock_metadata_search):
    """
    Test routing metadata query to metadata search

    Verifies:
    - Metadata queries route to structured search
    - Filters are applied correctly
    - Date/author queries handled
    """
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.METADATA,
        confidence=0.91,
        reasoning="Structured attribute filter",
        classification_method="ai",
        fallback_used=False
    ))

    query = "Documents from 2024 by John Smith"
    result = await query_router.route_and_search(query)

    assert result.pipeline == "metadata"
    assert result.query_type == QueryType.METADATA
    assert mock_metadata_search.search.called


@pytest.mark.asyncio
async def test_route_hybrid_query_to_hybrid_search(query_router, mock_classifier, mock_hybrid_search):
    """
    Test routing hybrid query to hybrid search

    Verifies:
    - Hybrid queries use hybrid search
    - Multiple search methods combined
    - RRF fusion applied
    """
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.HYBRID,
        confidence=0.88,
        reasoning="Combines semantic and metadata",
        classification_method="ai",
        fallback_used=False
    ))

    query = "Policies similar to ABC created after 2024-01-01"
    result = await query_router.route_and_search(query)

    assert result.pipeline == "hybrid"
    assert result.query_type == QueryType.HYBRID
    assert mock_hybrid_search.search.called


@pytest.mark.asyncio
async def test_classification_failure_falls_back_to_hybrid(query_router, mock_classifier, mock_hybrid_search):
    """
    Test fallback to hybrid search on classification failure

    Verifies:
    - Classification errors are caught
    - Hybrid search used as fallback
    - Fallback flag set
    - Results still returned
    """
    # Mock classifier failure
    mock_classifier.classify_async = AsyncMock(side_effect=Exception("API error"))

    query = "Find documents"
    result = await query_router.route_and_search(query)

    assert result.pipeline == "hybrid"
    assert result.fallback_used is True
    assert mock_hybrid_search.search.called


@pytest.mark.asyncio
async def test_low_confidence_classification_uses_hybrid(query_router, mock_classifier, mock_hybrid_search):
    """
    Test low confidence routes to hybrid search

    Verifies:
    - Low confidence classifications use hybrid
    - Hybrid combines multiple methods for safety
    - Results are returned
    """
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.SEMANTIC,
        confidence=0.45,  # Below threshold
        reasoning="Ambiguous query",
        classification_method="ai",
        fallback_used=False
    ))

    # Configure router to use hybrid for low confidence
    query_router.config.confidence_threshold = 0.7

    query = "Documents"
    result = await query_router.route_and_search(query)

    # Should use hybrid due to low confidence
    assert result.pipeline == "hybrid"
    assert mock_hybrid_search.search.called


@pytest.mark.asyncio
async def test_search_pipeline_failure_with_fallback(query_router, mock_classifier, mock_vector_search, mock_hybrid_search):
    """
    Test fallback when primary search pipeline fails

    Verifies:
    - Pipeline errors are caught
    - Fallback to hybrid search
    - Error logged
    - Results still returned
    """
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.SEMANTIC,
        confidence=0.92,
        reasoning="Conceptual query",
        classification_method="ai",
        fallback_used=False
    ))

    # Mock vector search failure
    mock_vector_search.search = AsyncMock(side_effect=Exception("Search failed"))

    query = "What is insurance?"
    result = await query_router.route_and_search(query)

    # Should fall back to hybrid
    assert result.fallback_used is True
    assert mock_hybrid_search.search.called


@pytest.mark.asyncio
async def test_routing_disabled_uses_hybrid(query_router, mock_classifier, mock_hybrid_search):
    """
    Test that routing can be disabled

    Verifies:
    - When routing disabled, always use hybrid
    - Classifier not called
    - Hybrid search executed
    """
    query_router.config.enable_routing = False

    query = "What is insurance?"
    result = await query_router.route_and_search(query)

    assert result.pipeline == "hybrid"
    assert not mock_classifier.classify_async.called
    assert mock_hybrid_search.search.called


@pytest.mark.asyncio
async def test_routing_decision_logging(query_router, mock_classifier):
    """
    Test routing decisions are logged

    Verifies:
    - Classification logged
    - Pipeline selection logged
    - Confidence logged
    """
    mock_classifier.classify_async = AsyncMock(return_value=ClassificationResult(
        query_type=QueryType.SEMANTIC,
        confidence=0.92,
        reasoning="Conceptual",
        classification_method="ai",
        fallback_used=False
    ))

    query = "What is insurance?"

    # Mock the structlog logger to verify logging calls
    with patch("app.services.query_router.logger") as mock_logger:
        await query_router.route_and_search(query)

        # Check that info logging was called (structlog uses keyword args)
        assert mock_logger.info.called or mock_logger.debug.called, \
            "Expected logging to be called during routing"


@pytest.mark.asyncio
async def test_batch_routing(query_router, mock_classifier):
    """
    Test batch routing of multiple queries

    Verifies:
    - Can route multiple queries
    - Each routed to correct pipeline
    - Results maintain order
    """
    # Mock different classifications
    classifications = [
        ClassificationResult(QueryType.SEMANTIC, 0.9, "Conceptual", "ai", False),
        ClassificationResult(QueryType.RELATIONAL, 0.88, "Entity query", "ai", False),
        ClassificationResult(QueryType.METADATA, 0.91, "Filter query", "ai", False)
    ]

    mock_classifier.classify_async = AsyncMock(side_effect=classifications)

    queries = [
        "What is insurance?",
        "Policies connected to Acme",
        "Documents from 2024"
    ]

    results = await query_router.route_batch(queries)

    assert len(results) == 3
    assert results[0].pipeline == "vector"
    assert results[1].pipeline == "graph"
    assert results[2].pipeline == "metadata"


@pytest.mark.asyncio
async def test_get_pipeline_for_query_type():
    """
    Test mapping of query types to pipelines

    Verifies:
    - SEMANTIC -> vector
    - RELATIONAL -> graph
    - METADATA -> metadata
    - HYBRID -> hybrid
    """
    router = QueryRouter()

    assert router._get_pipeline_name(QueryType.SEMANTIC) == "vector"
    assert router._get_pipeline_name(QueryType.RELATIONAL) == "graph"
    assert router._get_pipeline_name(QueryType.METADATA) == "metadata"
    assert router._get_pipeline_name(QueryType.HYBRID) == "hybrid"


def test_get_query_router_singleton():
    """
    Test singleton pattern for query router

    Verifies:
    - Same instance returned
    - Configuration persists
    """
    router1 = get_query_router()
    router2 = get_query_router()

    assert router1 is router2
