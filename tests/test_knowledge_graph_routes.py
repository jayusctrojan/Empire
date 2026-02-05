"""
Tests for Knowledge Graph API Routes (Task 31)

Tests cover:
- Entity queries and context retrieval
- Document context queries
- Graph traversal
- Natural language to Cypher generation
- Path finding
- Common entities
- Graph-enhanced context
- Health and stats endpoints
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_graph_query_service():
    """Mock Neo4j graph query service."""
    with patch('app.routes.knowledge_graph.get_neo4j_graph_query_service') as mock:
        service = Mock()
        service.connection = Mock()
        service.connection.execute_query = Mock(return_value=[])
        service.connection.verify_connectivity = Mock(return_value=True)

        # Mock methods
        service.get_entity_context = Mock(return_value={
            "entity_id": "ent-test",
            "documents": [{"doc_id": "doc-1", "title": "Test Doc"}],
            "related_entities": [{"entity_id": "ent-2", "name": "Related"}]
        })

        service.get_document_context = Mock(return_value={
            "doc_id": "doc-test",
            "entities": [{"entity_id": "ent-1", "name": "Entity"}],
            "related_docs": [{"doc_id": "doc-2", "title": "Related Doc"}],
            "relationships": [{"type": "MENTIONS", "count": 5}]
        })

        service.traverse_relationships = Mock(return_value=[
            {"node_id": "doc-1", "node_type": "Document", "depth": 1},
            {"node_id": "ent-1", "node_type": "Entity", "depth": 2}
        ])

        service.find_shortest_path = Mock(return_value={
            "path": [{"doc_id": "doc-1"}, {"entity_id": "ent-1"}, {"doc_id": "doc-2"}],
            "length": 2
        })

        service.find_common_entities = Mock(return_value=[
            {"entity_id": "ent-1", "name": "Common Entity", "doc_count": 3}
        ])

        service.expand_context_incrementally = Mock(return_value=[
            {"node_id": "doc-3", "depth": 1}
        ])

        mock.return_value = service
        yield service


@pytest.fixture
def mock_cypher_service():
    """Mock Cypher generation service."""
    with patch('app.routes.knowledge_graph.get_cypher_generation_service') as mock:
        service = Mock()
        service.generate_cypher = AsyncMock(return_value={
            "cypher": "MATCH (d:Document) WHERE d.title CONTAINS 'test' RETURN d LIMIT 20",
            "explanation": "Finds documents with 'test' in title",
            "confidence": 0.9
        })
        mock.return_value = service
        yield service


@pytest.fixture
def mock_neo4j_connection():
    """Mock Neo4j connection for health checks."""
    with patch('app.services.neo4j_connection.get_neo4j_connection') as mock:
        connection = Mock()
        connection.verify_connectivity = Mock(return_value=True)
        connection.execute_query = Mock(return_value=[
            {"label": "Document", "count": 100},
            {"label": "Entity", "count": 500}
        ])
        mock.return_value = connection
        yield connection


@pytest.fixture
def client(mock_graph_query_service, mock_cypher_service):
    """Create test client with mocked services."""
    from app.main import app
    return TestClient(app)


# =============================================================================
# Entity Query Tests
# =============================================================================

class TestEntityQuery:
    """Tests for entity query endpoint."""

    def test_query_entity_success(self, client, mock_graph_query_service):
        """Test successful entity query."""
        response = client.post("/api/graph/entity/query", json={
            "entity_id": "ent-test",
            "max_depth": 2,
            "include_documents": True,
            "include_entities": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["entity_id"] == "ent-test"
        assert "documents" in data
        assert "related_entities" in data
        assert "query_time_ms" in data

    def test_query_entity_exclude_documents(self, client, mock_graph_query_service):
        """Test entity query excluding documents."""
        response = client.post("/api/graph/entity/query", json={
            "entity_id": "ent-test",
            "include_documents": False,
            "include_entities": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []

    def test_query_entity_max_depth_validation(self, client):
        """Test max depth validation."""
        response = client.post("/api/graph/entity/query", json={
            "entity_id": "ent-test",
            "max_depth": 10  # Exceeds max of 5
        })

        assert response.status_code in [400, 422]  # FastAPI/Pydantic v2 may return 400


# =============================================================================
# Document Context Tests
# =============================================================================

class TestDocumentContext:
    """Tests for document context endpoint."""

    def test_get_document_context_success(self, client, mock_graph_query_service):
        """Test successful document context retrieval."""
        response = client.post("/api/graph/document/context", json={
            "doc_id": "doc-test",
            "max_depth": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "doc-test"
        assert "entities" in data
        assert "related_docs" in data
        assert "relationships" in data

    def test_get_document_context_minimal(self, client, mock_graph_query_service):
        """Test document context with minimal options."""
        response = client.post("/api/graph/document/context", json={
            "doc_id": "doc-test",
            "include_entities": False,
            "include_related_docs": False
        })

        assert response.status_code == 200


# =============================================================================
# Graph Traversal Tests
# =============================================================================

class TestGraphTraversal:
    """Tests for graph traversal endpoint."""

    def test_traverse_graph_success(self, client, mock_graph_query_service):
        """Test successful graph traversal."""
        response = client.post("/api/graph/traverse", json={
            "start_id": "doc-12345",
            "max_depth": 3
        })

        assert response.status_code == 200
        data = response.json()
        assert data["start_id"] == "doc-12345"
        assert "nodes" in data
        assert "total_nodes" in data
        assert "max_depth_reached" in data

    def test_traverse_with_relationship_filter(self, client, mock_graph_query_service):
        """Test traversal with relationship type filter."""
        response = client.post("/api/graph/traverse", json={
            "start_id": "doc-12345",
            "relationship_types": ["MENTIONS", "REFERENCES"],
            "direction": "outgoing"
        })

        assert response.status_code == 200


# =============================================================================
# Natural Language Query Tests
# =============================================================================

class TestNaturalLanguageQuery:
    """Tests for natural language to Cypher endpoint."""

    def test_natural_language_query_success(self, client, mock_cypher_service, mock_graph_query_service):
        """Test successful natural language query."""
        mock_graph_query_service.connection.execute_query.return_value = [
            {"doc_id": "doc-1", "title": "Test Document"}
        ]

        response = client.post("/api/graph/query/natural", json={
            "question": "Find all documents about insurance",
            "execute": True,
            "max_results": 10
        })

        assert response.status_code == 200
        data = response.json()
        assert "generated_cypher" in data
        assert "explanation" in data
        assert data["executed"] == True

    def test_natural_language_query_no_execute(self, client, mock_cypher_service):
        """Test query without execution."""
        response = client.post("/api/graph/query/natural", json={
            "question": "Find all documents about insurance",
            "execute": False
        })

        assert response.status_code == 200
        data = response.json()
        assert data["executed"] == False
        assert data["results"] is None


# =============================================================================
# Path Finding Tests
# =============================================================================

class TestPathFinding:
    """Tests for path finding endpoint."""

    def test_find_path_success(self, client, mock_graph_query_service):
        """Test successful path finding."""
        response = client.post("/api/graph/path/find", json={
            "from_id": "doc-12345",
            "to_id": "doc-67890"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert "path" in data
        assert "path_length" in data

    def test_find_path_not_found(self, client, mock_graph_query_service):
        """Test when no path exists."""
        mock_graph_query_service.find_shortest_path.return_value = None

        response = client.post("/api/graph/path/find", json={
            "from_id": "doc-isolated-1",
            "to_id": "doc-isolated-2"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["found"] == False


# =============================================================================
# Common Entities Tests
# =============================================================================

class TestCommonEntities:
    """Tests for common entities endpoint."""

    def test_find_common_entities_success(self, client, mock_graph_query_service):
        """Test finding common entities."""
        response = client.post("/api/graph/entities/common", json={
            "doc_ids": ["doc-1", "doc-2", "doc-3"],
            "min_doc_count": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert "common_entities" in data
        assert "total_common" in data


# =============================================================================
# Graph-Enhanced Context Tests
# =============================================================================

class TestGraphEnhancedContext:
    """Tests for graph-enhanced context endpoint."""

    def test_get_enhanced_context_success(self, client, mock_graph_query_service):
        """Test graph-enhanced context retrieval."""
        response = client.post("/api/graph/context/enhanced", json={
            "query": "California insurance requirements",
            "doc_ids": ["doc-1", "doc-2"],
            "expansion_depth": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert "original_docs" in data
        assert "expanded_docs" in data
        assert "related_entities" in data
        assert "graph_context" in data


# =============================================================================
# Health and Stats Tests
# =============================================================================

class TestHealthAndStats:
    """Tests for health and stats endpoints."""

    def test_health_endpoint_healthy(self, client, mock_neo4j_connection):
        """Test health endpoint when healthy."""
        with patch('app.services.neo4j_connection.get_neo4j_connection', return_value=mock_neo4j_connection):
            response = client.get("/api/graph/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["neo4j_connected"] == True

    def test_health_endpoint_unhealthy(self, client):
        """Test health endpoint when Neo4j is down."""
        with patch('app.services.neo4j_connection.get_neo4j_connection') as mock:
            mock.return_value.verify_connectivity.return_value = False
            response = client.get("/api/graph/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_stats_endpoint(self, client, mock_neo4j_connection):
        """Test stats endpoint."""
        with patch('app.services.neo4j_connection.get_neo4j_connection', return_value=mock_neo4j_connection):
            mock_neo4j_connection.execute_query.side_effect = [
                [{"label": "Document", "count": 100}, {"label": "Entity", "count": 500}],
                [{"type": "MENTIONS", "count": 1000}]
            ]

            response = client.get("/api/graph/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_nodes" in data
            assert "total_relationships" in data


# =============================================================================
# Cypher Generation Service Tests
# =============================================================================

class TestCypherGenerationService:
    """Tests for Cypher generation service."""

    def test_cypher_generation_config_defaults(self):
        """Test default configuration."""
        from app.services.cypher_generation_service import CypherGenerationConfig

        config = CypherGenerationConfig()
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.max_tokens == 1024
        assert config.temperature == 0.0

    def test_is_safe_query_valid(self):
        """Test safe query validation for read queries."""
        from app.services.cypher_generation_service import CypherGenerationService

        service = CypherGenerationService()

        assert service._is_safe_query("MATCH (n) RETURN n") == True
        assert service._is_safe_query("MATCH (d:Document) WHERE d.title = 'test' RETURN d") == True
        assert service._is_safe_query("MATCH (a)-[r]->(b) RETURN a, r, b LIMIT 10") == True

    def test_is_safe_query_invalid(self):
        """Test safe query validation rejects write queries."""
        from app.services.cypher_generation_service import CypherGenerationService

        service = CypherGenerationService()

        assert service._is_safe_query("CREATE (n:Node {name: 'test'})") == False
        assert service._is_safe_query("MERGE (n:Node {id: 1})") == False
        assert service._is_safe_query("MATCH (n) SET n.name = 'new'") == False
        assert service._is_safe_query("MATCH (n) DELETE n") == False
        assert service._is_safe_query("MATCH (n) DETACH DELETE n") == False

    @pytest.mark.asyncio
    async def test_generate_cypher_with_mock(self, mock_cypher_service):
        """Test Cypher generation with mocked client."""
        result = await mock_cypher_service.generate_cypher(
            question="Find documents about insurance"
        )

        assert "cypher" in result
        assert "explanation" in result
        assert result["confidence"] > 0

    def test_singleton_pattern(self):
        """Test singleton pattern for service."""
        from app.services.cypher_generation_service import (
            get_cypher_generation_service,
            reset_cypher_generation_service
        )

        reset_cypher_generation_service()

        service1 = get_cypher_generation_service()
        service2 = get_cypher_generation_service()

        assert service1 is service2

        reset_cypher_generation_service()


# =============================================================================
# Integration Tests (require actual Neo4j)
# =============================================================================

@pytest.mark.integration
class TestKnowledgeGraphIntegration:
    """Integration tests requiring actual Neo4j connection."""

    def test_full_entity_query_flow(self, client):
        """Test complete entity query flow."""
        # This would require actual Neo4j setup
        pass

    def test_natural_language_to_cypher_flow(self, client):
        """Test natural language query with actual execution."""
        # This would require actual Neo4j and Anthropic API
        pass
