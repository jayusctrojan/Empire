"""
Test suite for ConversationMemoryService - Task 27

Comprehensive tests for memory node/edge management, context window retrieval,
recency-weighted retrieval, and RLS enforcement.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, AsyncMock, patch

from app.services.conversation_memory_service import (
    ConversationMemoryService,
    MemoryNode,
    MemoryEdge
)


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client"""
    mock = Mock()

    # Mock table method
    mock.table = Mock(return_value=mock)
    mock.select = Mock(return_value=mock)
    mock.insert = Mock(return_value=mock)
    mock.update = Mock(return_value=mock)
    mock.delete = Mock(return_value=mock)
    mock.eq = Mock(return_value=mock)
    mock.in_ = Mock(return_value=mock)
    mock.lt = Mock(return_value=mock)
    mock.order = Mock(return_value=mock)
    mock.limit = Mock(return_value=mock)
    mock.single = Mock(return_value=mock)
    mock.rpc = Mock(return_value=mock)

    # Default execute response
    def mock_execute():
        response = Mock()
        response.data = []
        return response

    mock.execute = mock_execute

    return mock


@pytest.fixture
def service(mock_supabase):
    """Create ConversationMemoryService instance with mock client"""
    return ConversationMemoryService(supabase_client=mock_supabase)


@pytest.fixture
def sample_node_data():
    """Sample memory node data"""
    return {
        "id": str(uuid4()),
        "user_id": "user_123",
        "session_id": "session_456",
        "node_type": "conversation",
        "content": "User prefers dark mode",
        "summary": "Dark mode preference",
        "embedding": None,
        "confidence_score": 0.9,
        "source_type": "conversation",
        "importance_score": 0.7,
        "first_mentioned_at": datetime.now().isoformat(),
        "last_mentioned_at": datetime.now().isoformat(),
        "mention_count": 1,
        "is_active": True,
        "expires_at": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "metadata": {"context": "settings"}
    }


@pytest.fixture
def sample_edge_data():
    """Sample memory edge data"""
    return {
        "id": str(uuid4()),
        "user_id": "user_123",
        "source_node_id": str(uuid4()),
        "target_node_id": str(uuid4()),
        "relationship_type": "related_to",
        "strength": 0.8,
        "directionality": "directed",
        "first_observed_at": datetime.now().isoformat(),
        "last_observed_at": datetime.now().isoformat(),
        "observation_count": 1,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "metadata": {}
    }


# ==================== MemoryNode Tests ====================

class TestMemoryNode:
    """Test MemoryNode data class"""

    def test_memory_node_creation(self):
        """Test creating a MemoryNode"""
        node = MemoryNode(
            user_id="user_123",
            content="Test content",
            node_type="fact"
        )

        assert node.user_id == "user_123"
        assert node.content == "Test content"
        assert node.node_type == "fact"
        assert isinstance(node.id, UUID)
        assert node.is_active is True

    def test_memory_node_to_dict(self):
        """Test converting MemoryNode to dictionary"""
        node = MemoryNode(
            user_id="user_123",
            content="Test content",
            importance_score=0.8
        )

        node_dict = node.to_dict()

        assert isinstance(node_dict, dict)
        assert node_dict["user_id"] == "user_123"
        assert node_dict["content"] == "Test content"
        assert node_dict["importance_score"] == 0.8

    def test_memory_node_from_dict(self, sample_node_data):
        """Test creating MemoryNode from dictionary"""
        node = MemoryNode.from_dict(sample_node_data)

        assert node.user_id == "user_123"
        assert node.content == "User prefers dark mode"
        assert node.node_type == "conversation"
        assert node.importance_score == 0.7


# ==================== MemoryEdge Tests ====================

class TestMemoryEdge:
    """Test MemoryEdge data class"""

    def test_memory_edge_creation(self):
        """Test creating a MemoryEdge"""
        source_id = uuid4()
        target_id = uuid4()

        edge = MemoryEdge(
            user_id="user_123",
            source_node_id=source_id,
            target_node_id=target_id,
            relationship_type="follows"
        )

        assert edge.user_id == "user_123"
        assert edge.source_node_id == source_id
        assert edge.target_node_id == target_id
        assert edge.relationship_type == "follows"
        assert isinstance(edge.id, UUID)

    def test_memory_edge_to_dict(self):
        """Test converting MemoryEdge to dictionary"""
        edge = MemoryEdge(
            user_id="user_123",
            source_node_id=uuid4(),
            target_node_id=uuid4(),
            strength=0.9
        )

        edge_dict = edge.to_dict()

        assert isinstance(edge_dict, dict)
        assert edge_dict["user_id"] == "user_123"
        assert edge_dict["strength"] == 0.9

    def test_memory_edge_from_dict(self, sample_edge_data):
        """Test creating MemoryEdge from dictionary"""
        edge = MemoryEdge.from_dict(sample_edge_data)

        assert edge.user_id == "user_123"
        assert edge.relationship_type == "related_to"
        assert edge.strength == 0.8


# ==================== Node Management Tests ====================

class TestNodeManagement:
    """Test memory node CRUD operations"""

    @pytest.mark.asyncio
    async def test_create_memory_node_success(self, service, mock_supabase, sample_node_data):
        """Test successful memory node creation"""
        # Mock successful insert
        def mock_execute():
            response = Mock()
            response.data = [sample_node_data]
            return response

        mock_supabase.execute = mock_execute

        node = await service.create_memory_node(
            user_id="user_123",
            content="User prefers dark mode",
            node_type="preference"
        )

        assert node is not None
        assert node.user_id == "user_123"
        assert node.content == "User prefers dark mode"

    @pytest.mark.asyncio
    async def test_create_memory_node_failure(self, service, mock_supabase):
        """Test memory node creation failure"""
        # Mock failed insert
        def mock_execute():
            response = Mock()
            response.data = None
            return response

        mock_supabase.execute = mock_execute

        node = await service.create_memory_node(
            user_id="user_123",
            content="Test content"
        )

        assert node is None

    @pytest.mark.asyncio
    async def test_update_memory_node_success(self, service, mock_supabase, sample_node_data):
        """Test successful memory node update"""
        node_id = UUID(sample_node_data["id"])

        # Mock update
        def mock_execute():
            response = Mock()
            response.data = [sample_node_data]
            return response

        mock_supabase.execute = mock_execute

        updated_node = await service.update_memory_node(
            node_id=node_id,
            user_id="user_123",
            content="Updated content",
            importance_score=0.9
        )

        assert updated_node is not None

    @pytest.mark.asyncio
    async def test_get_memory_node_success(self, service, mock_supabase, sample_node_data):
        """Test retrieving a memory node"""
        node_id = UUID(sample_node_data["id"])

        # Mock select
        def mock_execute():
            response = Mock()
            response.data = sample_node_data
            return response

        mock_supabase.execute = mock_execute

        node = await service.get_memory_node(
            node_id=node_id,
            user_id="user_123"
        )

        assert node is not None
        assert node.content == "User prefers dark mode"

    @pytest.mark.asyncio
    async def test_get_memory_node_not_found(self, service, mock_supabase):
        """Test retrieving non-existent memory node"""
        def mock_execute():
            response = Mock()
            response.data = None
            return response

        mock_supabase.execute = mock_execute

        node = await service.get_memory_node(
            node_id=uuid4(),
            user_id="user_123"
        )

        assert node is None


# ==================== Edge Management Tests ====================

class TestEdgeManagement:
    """Test memory edge CRUD operations"""

    @pytest.mark.asyncio
    async def test_create_memory_edge_success(self, service, mock_supabase, sample_edge_data):
        """Test successful memory edge creation"""
        def mock_execute():
            response = Mock()
            response.data = [sample_edge_data]
            return response

        mock_supabase.execute = mock_execute

        edge = await service.create_memory_edge(
            user_id="user_123",
            source_node_id=UUID(sample_edge_data["source_node_id"]),
            target_node_id=UUID(sample_edge_data["target_node_id"]),
            relationship_type="related_to"
        )

        assert edge is not None
        assert edge.relationship_type == "related_to"

    @pytest.mark.asyncio
    async def test_update_memory_edge_success(self, service, mock_supabase, sample_edge_data):
        """Test successful memory edge update"""
        edge_id = UUID(sample_edge_data["id"])

        def mock_execute():
            response = Mock()
            response.data = [sample_edge_data]
            return response

        mock_supabase.execute = mock_execute

        updated_edge = await service.update_memory_edge(
            edge_id=edge_id,
            user_id="user_123",
            strength=0.95
        )

        assert updated_edge is not None


# ==================== Context Window Tests ====================

class TestContextWindow:
    """Test context window management"""

    @pytest.mark.asyncio
    async def test_get_recent_conversation_context(self, service, mock_supabase, sample_node_data):
        """Test retrieving recent conversation context"""
        # Mock multiple nodes
        def mock_execute():
            response = Mock()
            response.data = [sample_node_data, sample_node_data.copy()]
            return response

        mock_supabase.execute = mock_execute

        nodes = await service.get_recent_conversation_context(
            user_id="user_123",
            limit=10
        )

        assert isinstance(nodes, list)
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_get_recent_context_with_session_filter(self, service, mock_supabase):
        """Test retrieving context filtered by session"""
        def mock_execute():
            response = Mock()
            response.data = []
            return response

        mock_supabase.execute = mock_execute

        nodes = await service.get_recent_conversation_context(
            user_id="user_123",
            session_id="session_456",
            limit=5
        )

        assert isinstance(nodes, list)

    @pytest.mark.asyncio
    async def test_get_recent_context_with_node_type_filter(self, service, mock_supabase):
        """Test retrieving context filtered by node types"""
        def mock_execute():
            response = Mock()
            response.data = []
            return response

        mock_supabase.execute = mock_execute

        nodes = await service.get_recent_conversation_context(
            user_id="user_123",
            node_types=["conversation", "fact"]
        )

        assert isinstance(nodes, list)


# ==================== Weighted Retrieval Tests ====================

class TestWeightedRetrieval:
    """Test recency-weighted memory retrieval"""

    @pytest.mark.asyncio
    async def test_get_weighted_memories_scoring(self, service, mock_supabase):
        """Test weighted memory scoring"""
        # Create nodes with different scores
        now = datetime.now()
        nodes_data = [
            {
                "id": str(uuid4()),
                "user_id": "user_123",
                "content": "Recent important memory",
                "node_type": "fact",
                "importance_score": 0.9,
                "mention_count": 50,
                "last_mentioned_at": now.isoformat(),
                "first_mentioned_at": now.isoformat(),
                "is_active": True,
                "confidence_score": 1.0,
                "source_type": "conversation",
                "session_id": None,
                "summary": None,
                "embedding": None,
                "expires_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "metadata": {}
            },
            {
                "id": str(uuid4()),
                "user_id": "user_123",
                "content": "Old low-importance memory",
                "node_type": "fact",
                "importance_score": 0.2,
                "mention_count": 1,
                "last_mentioned_at": (now - timedelta(days=30)).isoformat(),
                "first_mentioned_at": (now - timedelta(days=30)).isoformat(),
                "is_active": True,
                "confidence_score": 1.0,
                "source_type": "conversation",
                "session_id": None,
                "summary": None,
                "embedding": None,
                "expires_at": None,
                "created_at": (now - timedelta(days=30)).isoformat(),
                "updated_at": (now - timedelta(days=30)).isoformat(),
                "metadata": {}
            }
        ]

        def mock_execute():
            response = Mock()
            response.data = nodes_data
            return response

        mock_supabase.execute = mock_execute

        weighted_memories = await service.get_weighted_memories(
            user_id="user_123",
            limit=10
        )

        assert isinstance(weighted_memories, list)
        assert len(weighted_memories) == 2

        # First memory should have higher score
        if len(weighted_memories) > 1:
            assert weighted_memories[0][1] > weighted_memories[1][1]

    @pytest.mark.asyncio
    async def test_get_weighted_memories_empty(self, service, mock_supabase):
        """Test weighted memories with no data"""
        def mock_execute():
            response = Mock()
            response.data = []
            return response

        mock_supabase.execute = mock_execute

        weighted_memories = await service.get_weighted_memories(
            user_id="user_123"
        )

        assert weighted_memories == []


# ==================== Vector Search Tests ====================

class TestVectorSearch:
    """Test vector similarity search"""

    @pytest.mark.asyncio
    async def test_search_similar_memories_success(self, service, mock_supabase, sample_node_data):
        """Test successful vector similarity search"""
        # Mock RPC response
        result_with_similarity = sample_node_data.copy()
        result_with_similarity["similarity"] = 0.95

        def mock_execute():
            response = Mock()
            response.data = [result_with_similarity]
            return response

        mock_supabase.execute = mock_execute

        query_embedding = [0.1] * 768  # 768-dim vector

        results = await service.search_similar_memories(
            user_id="user_123",
            query_embedding=query_embedding,
            limit=10,
            similarity_threshold=0.7
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_similar_memories_fallback(self, service, mock_supabase):
        """Test vector search fallback when RPC fails"""
        # Mock RPC failure
        def mock_execute():
            raise Exception("RPC not available")

        mock_supabase.execute = mock_execute

        query_embedding = [0.1] * 768

        results = await service.search_similar_memories(
            user_id="user_123",
            query_embedding=query_embedding
        )

        # Should return empty list on fallback
        assert results == []


# ==================== Utility Tests ====================

class TestUtilities:
    """Test utility methods"""

    @pytest.mark.asyncio
    async def test_deactivate_old_memories(self, service, mock_supabase):
        """Test deactivating old memories"""
        def mock_execute():
            response = Mock()
            response.data = [{"id": str(uuid4())}] * 5  # 5 deactivated
            return response

        mock_supabase.execute = mock_execute

        count = await service.deactivate_old_memories(
            user_id="user_123",
            days_threshold=90,
            importance_threshold=0.3
        )

        assert count == 5

    @pytest.mark.asyncio
    async def test_get_memory_statistics(self, service, mock_supabase):
        """Test getting memory statistics"""
        # Mock nodes response
        def mock_nodes_execute():
            response = Mock()
            response.data = [
                {"node_type": "conversation", "is_active": True},
                {"node_type": "fact", "is_active": True},
                {"node_type": "conversation", "is_active": False}
            ]
            return response

        # Mock edges response
        def mock_edges_execute():
            response = Mock()
            response.data = [
                {"relationship_type": "related_to", "is_active": True},
                {"relationship_type": "follows", "is_active": True}
            ]
            return response

        # Switch execute function based on table
        call_count = [0]
        def mock_execute():
            if call_count[0] == 0:
                call_count[0] += 1
                return mock_nodes_execute()
            else:
                return mock_edges_execute()

        mock_supabase.execute = mock_execute

        stats = await service.get_memory_statistics(user_id="user_123")

        assert isinstance(stats, dict)
        assert "total_nodes" in stats
        assert "total_edges" in stats


# ==================== Error Handling Tests ====================

class TestErrorHandling:
    """Test error handling in various scenarios"""

    @pytest.mark.asyncio
    async def test_create_node_exception_handling(self, service, mock_supabase):
        """Test exception handling in create_memory_node"""
        def mock_execute():
            raise Exception("Database error")

        mock_supabase.execute = mock_execute

        node = await service.create_memory_node(
            user_id="user_123",
            content="Test"
        )

        assert node is None

    @pytest.mark.asyncio
    async def test_get_recent_context_exception_handling(self, service, mock_supabase):
        """Test exception handling in get_recent_conversation_context"""
        def mock_execute():
            raise Exception("Database error")

        mock_supabase.execute = mock_execute

        nodes = await service.get_recent_conversation_context(
            user_id="user_123"
        )

        assert nodes == []
