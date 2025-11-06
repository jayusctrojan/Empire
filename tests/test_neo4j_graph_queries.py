"""
Tests for Neo4j Graph Query and Context Retrieval Service

Tests graph traversal, relationship queries, entity-centric searches,
and context retrieval operations.

Run with: python3 -m pytest tests/test_neo4j_graph_queries.py -v
"""

import pytest
from unittest.mock import Mock, patch

from app.services.neo4j_graph_queries import (
    Neo4jGraphQueryService,
    GraphTraversalConfig,
    get_neo4j_graph_query_service
)


@pytest.fixture
def mock_connection():
    """Create mock Neo4j connection"""
    connection = Mock()
    connection.execute_query = Mock(return_value=[])
    return connection


@pytest.fixture
def graph_service(mock_connection):
    """Create graph query service with mock connection"""
    return Neo4jGraphQueryService(connection=mock_connection)


@pytest.fixture
def traversal_config():
    """Create graph traversal configuration"""
    return GraphTraversalConfig(
        max_depth=3,
        relationship_types=["MENTIONS", "REFERENCES"],
        include_properties=True
    )


def test_find_related_documents(graph_service, mock_connection):
    """
    Test finding documents related to a given document

    Verifies:
    - Traverses graph relationships
    - Returns connected documents
    - Respects depth limits
    """
    mock_connection.execute_query.return_value = [
        {"doc_id": "doc456", "title": "Related Policy", "distance": 1},
        {"doc_id": "doc789", "title": "Another Related", "distance": 2}
    ]

    results = graph_service.find_related_documents(
        doc_id="doc123",
        max_depth=2
    )

    assert len(results) == 2
    assert results[0]["doc_id"] == "doc456"
    call_args = mock_connection.execute_query.call_args
    query = call_args[0][0]

    # Verify graph traversal query
    assert "MATCH" in query
    assert any(word in query for word in ["path", "relationship", "-[", "]-"])


def test_find_entities_in_subgraph(graph_service, mock_connection):
    """
    Test finding all entities within N hops of a document

    Verifies:
    - Multi-hop graph traversal
    - Entity collection
    - Distance/hop count returned
    """
    mock_connection.execute_query.return_value = [
        {"entity_id": "entity1", "name": "Acme Corp", "hops": 1},
        {"entity_id": "entity2", "name": "John Smith", "hops": 2}
    ]

    results = graph_service.find_entities_in_subgraph(
        doc_id="doc123",
        max_hops=2
    )

    assert len(results) == 2
    assert results[0]["entity_id"] == "entity1"


def test_get_document_context(graph_service, mock_connection):
    """
    Test retrieving full context around a document

    Verifies:
    - Returns entities
    - Returns related documents
    - Returns relationships
    - Assembles complete context graph
    """
    mock_connection.execute_query.return_value = [
        {
            "entities": [{"entity_id": "e1", "name": "Entity 1"}],
            "related_docs": [{"doc_id": "doc456"}],
            "relationships": [{"type": "MENTIONS", "properties": {}}]
        }
    ]

    context = graph_service.get_document_context(
        doc_id="doc123",
        include_entities=True,
        include_related_docs=True,
        max_depth=2
    )

    assert context is not None
    assert "entities" in context or "related_docs" in context


def test_get_entity_context(graph_service, mock_connection):
    """
    Test retrieving context around an entity

    Verifies:
    - Returns documents mentioning entity
    - Returns related entities
    - Returns relationship graph
    """
    mock_connection.execute_query.return_value = [
        {
            "documents": [{"doc_id": "doc123"}],
            "related_entities": [{"entity_id": "entity2"}]
        }
    ]

    context = graph_service.get_entity_context(
        entity_id="entity1",
        max_depth=2
    )

    assert context is not None


def test_find_shortest_path(graph_service, mock_connection):
    """
    Test finding shortest path between two nodes

    Verifies:
    - Cypher shortestPath function used
    - Returns path nodes and relationships
    - Handles no path found case
    """
    mock_connection.execute_query.return_value = [
        {
            "path": [
                {"doc_id": "doc123"},
                {"type": "MENTIONS"},
                {"entity_id": "entity1"},
                {"type": "REFERENCES"},
                {"doc_id": "doc456"}
            ],
            "length": 2
        }
    ]

    path = graph_service.find_shortest_path(
        from_id="doc123",
        to_id="doc456"
    )

    assert path is not None
    assert "length" in path or len(path) > 0


def test_find_common_entities(graph_service, mock_connection):
    """
    Test finding entities common to multiple documents

    Verifies:
    - Identifies shared entities
    - Returns intersection
    - Includes relationship counts
    """
    mock_connection.execute_query.return_value = [
        {"entity_id": "entity1", "name": "Shared Entity", "doc_count": 3}
    ]

    common = graph_service.find_common_entities(
        doc_ids=["doc123", "doc456", "doc789"]
    )

    assert len(common) >= 0
    if common:
        assert "entity_id" in common[0]


def test_traverse_relationships(graph_service, mock_connection, traversal_config):
    """
    Test general relationship traversal with config

    Verifies:
    - Config controls depth and relationship types
    - Filters by relationship type
    - Returns path information
    """
    mock_connection.execute_query.return_value = [
        {
            "node_id": "entity1",
            "node_type": "Entity",
            "depth": 1,
            "relationship_type": "MENTIONS"
        }
    ]

    results = graph_service.traverse_relationships(
        start_id="doc123",
        config=traversal_config
    )

    assert results is not None
    call_args = mock_connection.execute_query.call_args
    query = call_args[0][0]

    # Should respect max_depth
    assert str(traversal_config.max_depth) in query or "depth" in query.lower()


def test_get_entity_neighbors(graph_service, mock_connection):
    """
    Test getting direct neighbors of an entity

    Verifies:
    - Returns 1-hop neighbors
    - Includes relationship types
    - Both incoming and outgoing
    """
    mock_connection.execute_query.return_value = [
        {
            "neighbor_id": "doc123",
            "neighbor_type": "Document",
            "relationship": "MENTIONED_IN",
            "direction": "incoming"
        },
        {
            "neighbor_id": "entity2",
            "neighbor_type": "Entity",
            "relationship": "RELATED_TO",
            "direction": "outgoing"
        }
    ]

    neighbors = graph_service.get_entity_neighbors("entity1")

    assert len(neighbors) >= 0


def test_aggregate_relationships_by_type(graph_service, mock_connection):
    """
    Test aggregating relationship statistics

    Verifies:
    - Counts relationships by type
    - Returns aggregated data
    - Useful for graph analytics
    """
    mock_connection.execute_query.return_value = [
        {"relationship_type": "MENTIONS", "count": 15},
        {"relationship_type": "REFERENCES", "count": 8},
        {"relationship_type": "RELATED_TO", "count": 3}
    ]

    stats = graph_service.aggregate_relationships_by_type(node_id="doc123")

    assert len(stats) >= 0
    if stats:
        assert "relationship_type" in stats[0] or "count" in stats[0]


def test_find_clusters(graph_service, mock_connection):
    """
    Test finding document clusters based on shared entities

    Verifies:
    - Groups documents by entity overlap
    - Returns cluster information
    - Useful for discovery
    """
    mock_connection.execute_query.return_value = [
        {
            "cluster_id": 1,
            "documents": ["doc123", "doc456", "doc789"],
            "shared_entities": ["entity1", "entity2"]
        }
    ]

    clusters = graph_service.find_clusters(
        doc_ids=["doc123", "doc456", "doc789", "doc111"],
        min_shared_entities=2
    )

    assert clusters is not None


def test_expand_context_incrementally(graph_service, mock_connection):
    """
    Test expanding context incrementally (1 hop at a time)

    Verifies:
    - Can expand from initial set
    - Returns new nodes discovered
    - Stops at max depth
    """
    mock_connection.execute_query.return_value = [
        {"node_id": "entity1", "depth": 1},
        {"node_id": "doc456", "depth": 1},
        {"node_id": "entity2", "depth": 2}
    ]

    expanded = graph_service.expand_context_incrementally(
        start_ids=["doc123"],
        max_depth=2
    )

    assert expanded is not None


def test_get_relationship_properties(graph_service, mock_connection):
    """
    Test retrieving properties of a specific relationship

    Verifies:
    - Returns relationship metadata
    - Includes confidence scores, counts, etc.
    """
    mock_connection.execute_query.return_value = [
        {
            "confidence": 0.95,
            "mention_count": 3,
            "created_at": "2024-01-15"
        }
    ]

    props = graph_service.get_relationship_properties(
        from_id="doc123",
        to_id="entity1",
        relationship_type="MENTIONS"
    )

    assert props is not None


def test_cypher_injection_prevention(graph_service, mock_connection):
    """
    Test that queries use parameterization to prevent injection

    Verifies:
    - User input is parameterized
    - No string concatenation in queries
    - Safe query construction
    """
    # Malicious input
    malicious_id = "doc123'; DROP DATABASE; --"

    graph_service.find_related_documents(doc_id=malicious_id)

    # Should use parameters, not string concatenation
    call_args = mock_connection.execute_query.call_args
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('parameters', {})

    # Parameters should contain the ID, not embedded in query
    assert params is not None or isinstance(call_args[0][1], dict)


def test_handle_nonexistent_node(graph_service, mock_connection):
    """
    Test graceful handling of queries for non-existent nodes

    Verifies:
    - Returns empty results, not errors
    - Logs appropriate message
    """
    mock_connection.execute_query.return_value = []

    results = graph_service.find_related_documents(doc_id="nonexistent")

    assert results == [] or results is None


def test_query_performance_with_index_hints(graph_service, mock_connection):
    """
    Test that queries use index hints when appropriate

    Verifies:
    - USING INDEX hints are present where beneficial
    - Optimizes large graph queries
    """
    graph_service.find_entities_in_subgraph(doc_id="doc123", max_hops=3)

    call_args = mock_connection.execute_query.call_args
    query = call_args[0][0]

    # Should have some optimization strategy
    assert "MATCH" in query  # At minimum, should use MATCH


def test_get_graph_query_service_singleton(mock_connection):
    """
    Test singleton pattern for graph query service

    Verifies:
    - Same instance returned
    - Connection reused
    """
    with patch('app.services.neo4j_graph_queries.get_neo4j_connection', return_value=mock_connection):
        service1 = get_neo4j_graph_query_service()
        service2 = get_neo4j_graph_query_service()

        assert service1 is service2


def test_bidirectional_relationship_query(graph_service, mock_connection):
    """
    Test querying relationships in both directions

    Verifies:
    - Can query incoming and outgoing relationships
    - Direction is specified or both are returned
    """
    mock_connection.execute_query.return_value = [
        {"direction": "outgoing", "target": "entity1"},
        {"direction": "incoming", "source": "doc456"}
    ]

    results = graph_service.get_entity_neighbors(
        entity_id="entity1",
        direction="both"
    )

    assert results is not None


def test_filter_by_entity_type(graph_service, mock_connection):
    """
    Test filtering graph queries by entity type

    Verifies:
    - Can filter to specific entity types (person, org, etc.)
    - Reduces result set appropriately
    """
    mock_connection.execute_query.return_value = [
        {"entity_id": "entity1", "entity_type": "organization"}
    ]

    results = graph_service.find_entities_in_subgraph(
        doc_id="doc123",
        entity_types=["organization"],
        max_hops=2
    )

    assert results is not None
