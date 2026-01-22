"""
Tests for Conversation Memory API Routes (Task 32)

Tests cover:
- Memory node CRUD operations
- Memory edge creation and updates
- Context retrieval (recent and weighted)
- Semantic search
- Graph traversal
- Statistics and maintenance
- Health check
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_memory_service():
    """Mock conversation memory service."""
    with patch('app.routes.conversation_memory.get_memory_service') as mock:
        service = Mock()
        service.supabase = Mock()

        # Mock node methods
        sample_node = Mock()
        sample_node.id = uuid4()
        sample_node.user_id = "test-user"
        sample_node.session_id = "session-123"
        sample_node.node_type = "conversation"
        sample_node.content = "Test memory content"
        sample_node.summary = "Test summary"
        sample_node.importance_score = 0.7
        sample_node.confidence_score = 1.0
        sample_node.mention_count = 1
        sample_node.first_mentioned_at = datetime.now()
        sample_node.last_mentioned_at = datetime.now()
        sample_node.is_active = True
        sample_node.metadata = {}

        service.create_memory_node = AsyncMock(return_value=sample_node)
        service.get_memory_node = AsyncMock(return_value=sample_node)
        service.update_memory_node = AsyncMock(return_value=sample_node)

        # Mock edge methods
        sample_edge = Mock()
        sample_edge.id = uuid4()
        sample_edge.user_id = "test-user"
        sample_edge.source_node_id = uuid4()
        sample_edge.target_node_id = uuid4()
        sample_edge.relationship_type = "related_to"
        sample_edge.strength = 0.8
        sample_edge.directionality = "directed"
        sample_edge.observation_count = 1
        sample_edge.is_active = True
        sample_edge.metadata = {}

        service.create_memory_edge = AsyncMock(return_value=sample_edge)
        service.update_memory_edge = AsyncMock(return_value=sample_edge)

        # Mock context methods
        service.get_recent_conversation_context = AsyncMock(return_value=[sample_node])
        service.get_weighted_memories = AsyncMock(return_value=[(sample_node, 0.85)])
        service.search_similar_memories = AsyncMock(return_value=[(sample_node, 0.92)])

        # Mock stats
        service.get_memory_statistics = AsyncMock(return_value={
            "total_nodes": 100,
            "active_nodes": 95,
            "total_edges": 50,
            "active_edges": 48,
            "nodes_by_type": {"conversation": 60, "fact": 30, "preference": 10},
            "edges_by_type": {"related_to": 40, "follows": 10}
        })

        # Mock maintenance
        service.deactivate_old_memories = AsyncMock(return_value=5)

        mock.return_value = service
        yield service


@pytest.fixture
def client(mock_memory_service):
    """Create test client with mocked services and auth override."""
    from app.main import app
    from app.middleware.auth import get_current_user

    # Override the auth dependency
    async def mock_get_current_user():
        return "test-user"

    app.dependency_overrides[get_current_user] = mock_get_current_user

    yield TestClient(app)

    # Clean up overrides after test
    app.dependency_overrides.clear()


# =============================================================================
# Memory Node Tests
# =============================================================================

class TestMemoryNodes:
    """Tests for memory node endpoints."""

    def test_create_memory_node_success(self, client, mock_memory_service):
        """Test successful memory node creation."""
        response = client.post("/api/memory/nodes", json={
            "content": "User prefers dark mode",
            "node_type": "preference",
            "importance_score": 0.8
        })

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["node_type"] == "conversation"  # From mock
        assert data["is_active"] is True

    def test_create_memory_node_with_embedding(self, client, mock_memory_service):
        """Test creating node with embedding."""
        embedding = [0.1] * 768  # 768-dim vector

        response = client.post("/api/memory/nodes", json={
            "content": "Important fact to remember",
            "node_type": "fact",
            "embedding": embedding,
            "importance_score": 0.9
        })

        assert response.status_code == 200

    def test_create_memory_node_validation(self, client):
        """Test node creation validation."""
        # Empty content
        response = client.post("/api/memory/nodes", json={
            "content": "",
            "node_type": "fact"
        })
        assert response.status_code in [400, 422]  # FastAPI/Pydantic v2 may return 400

    def test_get_memory_node_success(self, client, mock_memory_service):
        """Test retrieving a memory node."""
        node_id = str(uuid4())
        response = client.get(f"/api/memory/nodes/{node_id}")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "content" in data

    def test_get_memory_node_not_found(self, client, mock_memory_service):
        """Test retrieving non-existent node."""
        mock_memory_service.get_memory_node.return_value = None

        response = client.get(f"/api/memory/nodes/{uuid4()}")
        assert response.status_code == 404

    def test_update_memory_node_success(self, client, mock_memory_service):
        """Test updating a memory node."""
        node_id = str(uuid4())
        response = client.patch(f"/api/memory/nodes/{node_id}", json={
            "content": "Updated content",
            "importance_score": 0.9
        })

        assert response.status_code == 200

    def test_deactivate_memory_node(self, client, mock_memory_service):
        """Test soft-deleting a memory node."""
        node_id = str(uuid4())

        # Mock the table operations
        mock_memory_service.supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = Mock()

        response = client.delete(f"/api/memory/nodes/{node_id}")

        assert response.status_code == 200
        assert "deactivated" in response.json()["message"].lower()


# =============================================================================
# Memory Edge Tests
# =============================================================================

class TestMemoryEdges:
    """Tests for memory edge endpoints."""

    def test_create_memory_edge_success(self, client, mock_memory_service):
        """Test successful memory edge creation."""
        response = client.post("/api/memory/edges", json={
            "source_node_id": str(uuid4()),
            "target_node_id": str(uuid4()),
            "relationship_type": "related_to",
            "strength": 0.8
        })

        assert response.status_code == 200
        data = response.json()
        assert data["relationship_type"] == "related_to"
        assert data["strength"] == 0.8

    def test_create_memory_edge_different_types(self, client, mock_memory_service):
        """Test creating edges with different relationship types."""
        for rel_type in ["follows", "contradicts", "supports", "mentions"]:
            response = client.post("/api/memory/edges", json={
                "source_node_id": str(uuid4()),
                "target_node_id": str(uuid4()),
                "relationship_type": rel_type
            })
            assert response.status_code == 200

    def test_update_memory_edge_success(self, client, mock_memory_service):
        """Test updating a memory edge."""
        edge_id = str(uuid4())
        response = client.patch(
            f"/api/memory/edges/{edge_id}",
            params={"strength": 0.95, "increment_observation": True}
        )

        assert response.status_code == 200


# =============================================================================
# Context Retrieval Tests
# =============================================================================

class TestContextRetrieval:
    """Tests for context retrieval endpoints."""

    def test_get_recent_context_success(self, client, mock_memory_service):
        """Test getting recent conversation context."""
        response = client.post("/api/memory/context/recent", json={
            "limit": 10
        })

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_recent_context_with_session(self, client, mock_memory_service):
        """Test getting context filtered by session."""
        response = client.post("/api/memory/context/recent", json={
            "session_id": "session-123",
            "limit": 5
        })

        assert response.status_code == 200

    def test_get_recent_context_with_node_types(self, client, mock_memory_service):
        """Test getting context filtered by node types."""
        response = client.post("/api/memory/context/recent", json={
            "node_types": ["conversation", "fact"],
            "limit": 10
        })

        assert response.status_code == 200

    def test_get_weighted_context_success(self, client, mock_memory_service):
        """Test getting weighted memory context."""
        response = client.post("/api/memory/context/weighted", json={
            "limit": 20,
            "recency_weight": 0.5,
            "importance_weight": 0.3,
            "access_weight": 0.2
        })

        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert "count" in data
        assert "weights" in data

    def test_get_weighted_context_custom_weights(self, client, mock_memory_service):
        """Test weighted context with custom weights."""
        response = client.post("/api/memory/context/weighted", json={
            "limit": 10,
            "recency_weight": 0.7,
            "importance_weight": 0.2,
            "access_weight": 0.1,
            "time_decay_hours": 72
        })

        assert response.status_code == 200


# =============================================================================
# Semantic Search Tests
# =============================================================================

class TestSemanticSearch:
    """Tests for semantic search endpoint."""

    def test_semantic_search_success(self, client, mock_memory_service):
        """Test successful semantic search."""
        query_embedding = [0.1] * 768

        response = client.post("/api/memory/search/semantic", json={
            "query_embedding": query_embedding,
            "limit": 10,
            "similarity_threshold": 0.7
        })

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data

    def test_semantic_search_invalid_embedding_dimension(self, client, mock_memory_service):
        """Test semantic search with wrong embedding dimension."""
        wrong_embedding = [0.1] * 512  # Wrong size

        response = client.post("/api/memory/search/semantic", json={
            "query_embedding": wrong_embedding,
            "limit": 10
        })

        assert response.status_code == 400
        data = response.json()
        # Response may have "detail" or "error" depending on exception handler
        error_message = data.get("detail") or data.get("error", "")
        assert "768" in error_message

    def test_semantic_search_custom_threshold(self, client, mock_memory_service):
        """Test semantic search with custom threshold."""
        query_embedding = [0.1] * 768

        response = client.post("/api/memory/search/semantic", json={
            "query_embedding": query_embedding,
            "limit": 5,
            "similarity_threshold": 0.9
        })

        assert response.status_code == 200


# =============================================================================
# Graph Traversal Tests
# =============================================================================

class TestGraphTraversal:
    """Tests for graph traversal endpoint."""

    def test_traverse_graph_success(self, client, mock_memory_service):
        """Test successful graph traversal."""
        # Mock RPC response
        mock_memory_service.supabase.rpc.return_value.execute.return_value.data = [
            {"node_id": str(uuid4()), "node_type": "fact", "content": "Related fact", "depth": 1}
        ]

        response = client.post("/api/memory/graph/traverse", json={
            "start_node_id": str(uuid4()),
            "max_depth": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "total_nodes" in data

    def test_traverse_graph_with_relationship_filter(self, client, mock_memory_service):
        """Test graph traversal with relationship type filter."""
        mock_memory_service.supabase.rpc.return_value.execute.return_value.data = []

        response = client.post("/api/memory/graph/traverse", json={
            "start_node_id": str(uuid4()),
            "max_depth": 3,
            "relationship_types": ["related_to", "follows"]
        })

        assert response.status_code == 200


# =============================================================================
# Statistics Tests
# =============================================================================

class TestStatistics:
    """Tests for statistics endpoint."""

    def test_get_memory_stats_success(self, client, mock_memory_service):
        """Test getting memory statistics."""
        response = client.get("/api/memory/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 100
        assert data["active_nodes"] == 95
        assert "nodes_by_type" in data
        assert "edges_by_type" in data

    def test_get_memory_stats_empty(self, client, mock_memory_service):
        """Test statistics with no data."""
        mock_memory_service.get_memory_statistics.return_value = {}

        response = client.get("/api/memory/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 0


# =============================================================================
# Maintenance Tests
# =============================================================================

class TestMaintenance:
    """Tests for maintenance endpoints."""

    def test_cleanup_old_memories_success(self, client, mock_memory_service):
        """Test cleaning up old memories."""
        response = client.post(
            "/api/memory/maintenance/cleanup",
            params={"days_threshold": 90, "importance_threshold": 0.3}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deactivated_count"] == 5

    def test_cleanup_with_custom_thresholds(self, client, mock_memory_service):
        """Test cleanup with custom thresholds."""
        response = client.post(
            "/api/memory/maintenance/cleanup",
            params={"days_threshold": 30, "importance_threshold": 0.5}
        )

        assert response.status_code == 200


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_healthy(self, client, mock_memory_service):
        """Test health check when healthy."""
        response = client.get("/api/memory/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "conversation_memory"
        assert data["supabase_connected"] is True

    def test_health_check_degraded(self, client, mock_memory_service):
        """Test health check when Supabase not connected."""
        mock_memory_service.supabase = None

        response = client.get("/api/memory/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"


# =============================================================================
# Integration Tests (Marked for actual database)
# =============================================================================

@pytest.mark.integration
class TestConversationMemoryIntegration:
    """Integration tests requiring actual Supabase connection."""

    def test_full_memory_workflow(self, client):
        """Test complete memory creation and retrieval workflow."""
        # This would require actual Supabase setup
        pass

    def test_graph_traversal_with_real_data(self, client):
        """Test graph traversal with real database."""
        # This would require actual Supabase setup
        pass
