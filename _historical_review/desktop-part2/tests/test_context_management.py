"""
Tests for Context Management Service and API Routes (Task 33)

Tests cover:
- Context window building with token budgets
- Recency and access-weighted retrieval
- Graph traversal for related memories
- Semantic search integration
- Token counting
- API endpoints
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timedelta
import math


# =============================================================================
# Unit Tests for Context Management Service
# =============================================================================

class TestContextConfig:
    """Tests for ContextConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from app.services.context_management_service import ContextConfig

        config = ContextConfig()
        assert config.max_tokens == 4096
        assert config.max_recent_messages == 5
        assert config.max_memory_nodes == 20
        assert config.max_graph_depth == 2
        assert config.recency_weight == 0.4
        assert config.importance_weight == 0.3
        assert config.access_weight == 0.2
        assert config.semantic_weight == 0.1
        assert config.time_decay_hours == 168  # 1 week
        assert config.min_relevance_threshold == 0.3
        assert config.include_graph_traversal is True
        assert config.include_semantic_search is True

    def test_custom_config(self):
        """Test custom configuration."""
        from app.services.context_management_service import ContextConfig

        config = ContextConfig(
            max_tokens=8192,
            max_recent_messages=10,
            recency_weight=0.6,
            importance_weight=0.4,
            access_weight=0.0,
            semantic_weight=0.0
        )
        assert config.max_tokens == 8192
        assert config.max_recent_messages == 10
        assert config.recency_weight == 0.6


class TestContextItem:
    """Tests for ContextItem dataclass."""

    def test_context_item_creation(self):
        """Test creating a context item."""
        from app.services.context_management_service import ContextItem, ContextSourceType

        item = ContextItem(
            content="Test content",
            source_type=ContextSourceType.MEMORY_NODE,
            source_id="test-123",
            relevance_score=0.85,
            token_count=10,
            timestamp=datetime.now()
        )

        assert item.content == "Test content"
        assert item.source_type == ContextSourceType.MEMORY_NODE
        assert item.relevance_score == 0.85
        assert item.token_count == 10

    def test_context_item_to_dict(self):
        """Test context item serialization."""
        from app.services.context_management_service import ContextItem, ContextSourceType

        now = datetime.now()
        item = ContextItem(
            content="Test",
            source_type=ContextSourceType.RECENT_MESSAGE,
            source_id="msg-1",
            relevance_score=1.0,
            token_count=5,
            timestamp=now,
            metadata={"key": "value"}
        )

        data = item.to_dict()
        assert data["content"] == "Test"
        assert data["source_type"] == "recent_message"
        assert data["source_id"] == "msg-1"
        assert data["relevance_score"] == 1.0
        assert data["token_count"] == 5
        assert "key" in data["metadata"]


class TestContextWindow:
    """Tests for ContextWindow dataclass."""

    def test_context_window_creation(self):
        """Test creating a context window."""
        from app.services.context_management_service import ContextWindow

        window = ContextWindow(
            items=[],
            total_tokens=0,
            max_tokens=4096,
            user_id="user-123"
        )

        assert window.total_tokens == 0
        assert window.max_tokens == 4096
        assert window.user_id == "user-123"
        assert len(window.items) == 0

    def test_context_window_to_dict(self):
        """Test context window serialization."""
        from app.services.context_management_service import ContextWindow, ContextItem, ContextSourceType

        item = ContextItem(
            content="Test",
            source_type=ContextSourceType.MEMORY_NODE,
            relevance_score=0.9,
            token_count=5
        )

        window = ContextWindow(
            items=[item],
            total_tokens=5,
            max_tokens=4096,
            user_id="user-123",
            query="test query"
        )

        data = window.to_dict()
        assert data["total_tokens"] == 5
        assert data["max_tokens"] == 4096
        assert data["item_count"] == 1
        assert data["token_utilization"] == round(5 / 4096, 4)
        assert len(data["items"]) == 1


class TestContextManagementService:
    """Tests for ContextManagementService."""

    @pytest.fixture
    def mock_memory_service(self):
        """Create a mock memory service."""
        service = Mock()
        service.supabase = Mock()

        # Create sample memory node
        sample_node = Mock()
        sample_node.id = uuid4()
        sample_node.user_id = "test-user"
        sample_node.content = "Test memory content"
        sample_node.node_type = "fact"
        sample_node.importance_score = 0.7
        sample_node.mention_count = 5
        sample_node.last_mentioned_at = datetime.now() - timedelta(hours=24)
        sample_node.session_id = "session-123"

        service.get_recent_conversation_context = AsyncMock(return_value=[sample_node])
        service.get_weighted_memories = AsyncMock(return_value=[(sample_node, 0.85)])
        service.search_similar_memories = AsyncMock(return_value=[(sample_node, 0.92)])

        return service

    @pytest.fixture
    def context_service(self, mock_memory_service):
        """Create context management service with mocked dependencies."""
        from app.services.context_management_service import ContextManagementService

        return ContextManagementService(memory_service=mock_memory_service)

    def test_count_tokens(self, context_service):
        """Test token counting."""
        # Short text
        tokens = context_service.count_tokens("Hello world")
        assert tokens > 0
        assert tokens < 10

        # Longer text
        long_text = "This is a much longer piece of text that should have more tokens." * 10
        more_tokens = context_service.count_tokens(long_text)
        assert more_tokens > tokens

        # Empty text
        assert context_service.count_tokens("") == 0
        assert context_service.count_tokens(None) == 0

    def test_calculate_recency_score_recent(self, context_service):
        """Test recency score for recent timestamps."""
        now = datetime.now()
        score = context_service._calculate_recency_score(now, time_decay_hours=168)

        # Very recent should be close to 1
        assert score > 0.9

    def test_calculate_recency_score_old(self, context_service):
        """Test recency score for old timestamps."""
        old_time = datetime.now() - timedelta(hours=168)  # 1 week ago
        score = context_service._calculate_recency_score(old_time, time_decay_hours=168)

        # At half-life, should be around 0.5
        assert 0.4 < score < 0.6

    def test_calculate_recency_score_very_old(self, context_service):
        """Test recency score for very old timestamps."""
        very_old = datetime.now() - timedelta(days=30)
        score = context_service._calculate_recency_score(very_old, time_decay_hours=168)

        # Very old should be close to 0
        assert score < 0.1

    def test_calculate_access_score(self, context_service):
        """Test access frequency score calculation."""
        # Low mention count
        score_low = context_service._calculate_access_score(1)
        assert 0 < score_low < 0.2

        # Medium mention count
        score_medium = context_service._calculate_access_score(10)
        assert score_low < score_medium

        # High mention count
        score_high = context_service._calculate_access_score(50)
        assert score_medium < score_high

        # Max mention count
        score_max = context_service._calculate_access_score(100)
        assert score_max <= 1.0

        # Zero mentions
        assert context_service._calculate_access_score(0) == 0

    def test_calculate_combined_score(self, context_service, mock_memory_service):
        """Test combined relevance score calculation."""
        node = Mock()
        node.importance_score = 0.8
        node.mention_count = 20
        node.last_mentioned_at = datetime.now() - timedelta(hours=12)

        score = context_service._calculate_combined_score(node, semantic_similarity=0.9)

        # Score should be between 0 and 1
        assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, context_service, mock_memory_service):
        """Test getting recent messages."""
        items = await context_service.get_recent_messages(
            user_id="test-user",
            session_id="session-123",
            limit=5
        )

        assert len(items) > 0
        assert items[0].source_type.value == "recent_message"
        mock_memory_service.get_recent_conversation_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_weighted_memories(self, context_service, mock_memory_service):
        """Test getting weighted memories."""
        items = await context_service.get_weighted_memories(
            user_id="test-user",
            limit=20
        )

        assert len(items) > 0
        assert items[0].source_type.value == "memory_node"
        mock_memory_service.get_weighted_memories.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_semantic_memories(self, context_service, mock_memory_service):
        """Test semantic memory search."""
        query_embedding = [0.1] * 768

        items = await context_service.get_semantic_memories(
            user_id="test-user",
            query_embedding=query_embedding,
            limit=10,
            threshold=0.7
        )

        mock_memory_service.search_similar_memories.assert_called_once()

    def test_fit_to_token_budget(self, context_service):
        """Test fitting items to token budget."""
        from app.services.context_management_service import ContextItem, ContextSourceType

        items = [
            ContextItem(content="A" * 100, source_type=ContextSourceType.MEMORY_NODE, relevance_score=0.9, token_count=100),
            ContextItem(content="B" * 50, source_type=ContextSourceType.MEMORY_NODE, relevance_score=0.8, token_count=50),
            ContextItem(content="C" * 200, source_type=ContextSourceType.MEMORY_NODE, relevance_score=0.7, token_count=200),
        ]

        # Budget allows only first two items
        fitted, total = context_service._fit_to_token_budget(items, max_tokens=150)

        assert total <= 150
        assert len(fitted) == 2
        # Higher relevance items should be included
        assert fitted[0].relevance_score == 0.9
        assert fitted[1].relevance_score == 0.8

    @pytest.mark.asyncio
    async def test_build_context_window(self, context_service, mock_memory_service):
        """Test building complete context window."""
        # Mock graph traversal RPC
        mock_memory_service.supabase.rpc.return_value.execute.return_value.data = []

        window = await context_service.build_context_window(
            user_id="test-user",
            query="Test query",
            session_id="session-123"
        )

        assert window.user_id == "test-user"
        assert window.query == "Test query"
        assert window.total_tokens <= window.max_tokens
        assert len(window.items) >= 0

    @pytest.mark.asyncio
    async def test_get_context_for_query(self, context_service, mock_memory_service):
        """Test getting formatted context for a query."""
        # Mock graph traversal RPC
        mock_memory_service.supabase.rpc.return_value.execute.return_value.data = []

        result = await context_service.get_context_for_query(
            user_id="test-user",
            query="Test query",
            max_tokens=4096
        )

        assert "context_text" in result
        assert "total_items" in result
        assert "total_tokens" in result
        assert "token_utilization" in result
        assert "sources" in result

        # Check sources breakdown
        assert "recent_messages" in result["sources"]
        assert "memory_nodes" in result["sources"]


# =============================================================================
# API Route Tests
# =============================================================================

@pytest.fixture
def mock_context_service():
    """Mock context management service for API tests."""
    with patch('app.routes.context_management.get_context_management_service') as mock:
        service = Mock()

        # Mock token counting
        service.count_tokens = Mock(return_value=10)

        # Mock context retrieval methods
        from app.services.context_management_service import ContextItem, ContextSourceType, ContextWindow

        sample_item = ContextItem(
            content="Test content",
            source_type=ContextSourceType.MEMORY_NODE,
            source_id=str(uuid4()),
            relevance_score=0.85,
            token_count=10,
            timestamp=datetime.now()
        )

        service.get_recent_messages = AsyncMock(return_value=[sample_item])
        service.get_weighted_memories = AsyncMock(return_value=[sample_item])
        service.get_graph_related_memories = AsyncMock(return_value=[sample_item])
        service.get_semantic_memories = AsyncMock(return_value=[sample_item])

        sample_window = ContextWindow(
            items=[sample_item],
            total_tokens=10,
            max_tokens=4096,
            user_id="test-user",
            query="test query"
        )
        service.build_context_window = AsyncMock(return_value=sample_window)

        service.get_context_for_query = AsyncMock(return_value={
            "context_text": "## Recent Conversation\n- Test content",
            "context_window": sample_window.to_dict(),
            "total_items": 1,
            "total_tokens": 10,
            "token_utilization": 0.0024,
            "sources": {
                "recent_messages": 1,
                "memory_nodes": 0,
                "graph_traversal": 0,
                "semantic_search": 0
            }
        })

        mock.return_value = service
        yield service


@pytest.fixture
def client(mock_context_service):
    """Create test client with mocked services."""
    from app.main import app
    from app.middleware.auth import get_current_user

    async def mock_get_current_user():
        return "test-user"

    app.dependency_overrides[get_current_user] = mock_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestContextQueryEndpoint:
    """Tests for POST /api/context/query endpoint."""

    def test_get_context_for_query_success(self, client, mock_context_service):
        """Test successful context query."""
        response = client.post("/api/context/query", json={
            "query": "What is the capital of France?",
            "max_tokens": 4096
        })

        assert response.status_code == 200
        data = response.json()
        assert "context_text" in data
        assert "total_items" in data
        assert "total_tokens" in data
        assert "sources" in data
        assert "query_time_ms" in data

    def test_get_context_with_embedding(self, client, mock_context_service):
        """Test context query with embedding."""
        embedding = [0.1] * 768

        response = client.post("/api/context/query", json={
            "query": "Test query",
            "query_embedding": embedding,
            "max_tokens": 4096
        })

        assert response.status_code == 200

    def test_get_context_invalid_embedding_dimension(self, client, mock_context_service):
        """Test context query with wrong embedding dimension."""
        wrong_embedding = [0.1] * 512

        response = client.post("/api/context/query", json={
            "query": "Test query",
            "query_embedding": wrong_embedding
        })

        assert response.status_code == 400
        data = response.json()
        error_message = data.get("detail") or data.get("error", "")
        assert "768" in error_message

    def test_get_context_with_session(self, client, mock_context_service):
        """Test context query with session ID."""
        response = client.post("/api/context/query", json={
            "query": "Test query",
            "session_id": "session-123",
            "max_tokens": 2048
        })

        assert response.status_code == 200


class TestBuildContextWindowEndpoint:
    """Tests for POST /api/context/window/build endpoint."""

    def test_build_context_window_success(self, client, mock_context_service):
        """Test building context window."""
        response = client.post("/api/context/window/build", json={
            "query": "Test query",
            "max_tokens": 4096,
            "max_recent_messages": 5,
            "max_memory_nodes": 20
        })

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_tokens" in data
        assert "max_tokens" in data
        assert "query_time_ms" in data

    def test_build_context_window_custom_config(self, client, mock_context_service):
        """Test building context window with custom config."""
        response = client.post("/api/context/window/build", json={
            "query": "Test query",
            "max_tokens": 8192,
            "max_recent_messages": 10,
            "include_graph_traversal": False,
            "include_semantic_search": False
        })

        assert response.status_code == 200


class TestRecentMessagesEndpoint:
    """Tests for POST /api/context/recent endpoint."""

    def test_get_recent_messages_success(self, client, mock_context_service):
        """Test getting recent messages."""
        response = client.post("/api/context/recent", json={
            "limit": 5
        })

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "total_tokens" in data

    def test_get_recent_messages_with_session(self, client, mock_context_service):
        """Test getting recent messages for a session."""
        response = client.post("/api/context/recent", json={
            "session_id": "session-123",
            "limit": 10
        })

        assert response.status_code == 200


class TestWeightedMemoriesEndpoint:
    """Tests for POST /api/context/weighted endpoint."""

    def test_get_weighted_memories_success(self, client, mock_context_service):
        """Test getting weighted memories."""
        response = client.post("/api/context/weighted", json={
            "limit": 20,
            "recency_weight": 0.5,
            "importance_weight": 0.3,
            "access_weight": 0.2
        })

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "weights" in data

    def test_get_weighted_memories_custom_weights(self, client, mock_context_service):
        """Test weighted memories with custom weights."""
        response = client.post("/api/context/weighted", json={
            "limit": 10,
            "recency_weight": 0.8,
            "importance_weight": 0.2,
            "access_weight": 0.0
        })

        assert response.status_code == 200
        data = response.json()
        assert data["weights"]["recency"] == 0.8


class TestGraphRelatedEndpoint:
    """Tests for POST /api/context/graph/related endpoint."""

    def test_get_graph_related_success(self, client, mock_context_service):
        """Test getting graph-related memories."""
        response = client.post("/api/context/graph/related", json={
            "start_node_ids": [str(uuid4())],
            "max_depth": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "start_nodes" in data
        assert "max_depth" in data

    def test_get_graph_related_multiple_nodes(self, client, mock_context_service):
        """Test graph traversal from multiple starting nodes."""
        response = client.post("/api/context/graph/related", json={
            "start_node_ids": [str(uuid4()), str(uuid4())],
            "max_depth": 1
        })

        assert response.status_code == 200


class TestSemanticEndpoint:
    """Tests for POST /api/context/semantic endpoint."""

    def test_get_semantic_memories_success(self, client, mock_context_service):
        """Test semantic memory search."""
        embedding = [0.1] * 768

        response = client.post("/api/context/semantic", json={
            "query_embedding": embedding,
            "limit": 10,
            "threshold": 0.7
        })

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "threshold" in data

    def test_get_semantic_memories_invalid_embedding(self, client, mock_context_service):
        """Test semantic search with wrong embedding dimension."""
        wrong_embedding = [0.1] * 512

        response = client.post("/api/context/semantic", json={
            "query_embedding": wrong_embedding,
            "limit": 10
        })

        assert response.status_code == 400


class TestTokenCountEndpoint:
    """Tests for POST /api/context/tokens/count endpoint."""

    def test_count_tokens_success(self, client, mock_context_service):
        """Test token counting."""
        response = client.post(
            "/api/context/tokens/count",
            params={"text": "Hello, how are you today?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "text_length" in data
        assert "token_count" in data
        assert "ratio" in data


class TestConfigEndpoint:
    """Tests for GET /api/context/config/defaults endpoint."""

    def test_get_default_config(self, client, mock_context_service):
        """Test getting default configuration."""
        response = client.get("/api/context/config/defaults")

        assert response.status_code == 200
        data = response.json()
        assert data["max_tokens"] == 4096
        assert data["max_recent_messages"] == 5
        assert data["max_graph_depth"] == 2
        assert "recency_weight" in data
        assert "importance_weight" in data


class TestHealthEndpoint:
    """Tests for GET /api/context/health endpoint."""

    def test_health_check_healthy(self, client, mock_context_service):
        """Test health check when healthy."""
        mock_context_service.memory_service = Mock()
        mock_context_service.memory_service.supabase = Mock()
        mock_context_service.tokenizer = Mock()

        response = client.get("/api/context/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "context_management"
        assert "status" in data
        assert "timestamp" in data

    def test_health_check_degraded(self, client, mock_context_service):
        """Test health check when degraded."""
        mock_context_service.memory_service = Mock()
        mock_context_service.memory_service.supabase = None
        mock_context_service.tokenizer = None

        response = client.get("/api/context/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"


# =============================================================================
# Integration Tests (Marked for actual database)
# =============================================================================

@pytest.mark.integration
class TestContextManagementIntegration:
    """Integration tests requiring actual database connection."""

    def test_full_context_retrieval_flow(self, client):
        """Test complete context retrieval workflow."""
        # This would require actual Supabase setup
        pass

    def test_graph_traversal_with_real_data(self, client):
        """Test graph traversal with real database."""
        # This would require actual Supabase setup
        pass

    def test_semantic_search_with_embeddings(self, client):
        """Test semantic search with real embeddings."""
        # This would require actual embedding service
        pass
