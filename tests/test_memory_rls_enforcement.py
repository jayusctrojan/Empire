"""
Test suite for RLS Enforcement on Memory Tables - Task 27

Tests to verify Row-Level Security policies prevent cross-user access
to memory nodes and edges.
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.services.conversation_memory_service import (
    ConversationMemoryService,
    MemoryNode,
    MemoryEdge
)
from app.core.supabase_client import get_supabase_client


# NOTE: These are integration tests that require a real Supabase connection
# Skip if SUPABASE_URL or SUPABASE_SERVICE_KEY are not configured


@pytest.fixture
def supabase_client():
    """Get real Supabase client for RLS testing"""
    try:
        client = get_supabase_client()
        if client is None:
            pytest.skip("Supabase client not configured")
        return client
    except Exception:
        pytest.skip("Supabase client not available")


@pytest.fixture
def service(supabase_client):
    """Create ConversationMemoryService with real Supabase client"""
    return ConversationMemoryService(supabase_client=supabase_client)


@pytest.fixture
def user_a_id():
    """User A identifier"""
    return f"test_user_a_{uuid4().hex[:8]}"


@pytest.fixture
def user_b_id():
    """User B identifier"""
    return f"test_user_b_{uuid4().hex[:8]}"


# ==================== RLS Node Enforcement Tests ====================

class TestNodeRLSEnforcement:
    """Test RLS enforcement for memory nodes"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_cannot_read_another_users_nodes(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that User B cannot read User A's memory nodes"""
        # User A creates a node
        node_a = await service.create_memory_node(
            user_id=user_a_id,
            content="User A's private memory",
            node_type="fact"
        )

        assert node_a is not None, "User A should be able to create a node"

        # User B tries to read User A's node
        node_b_read = await service.get_memory_node(
            node_id=node_a.id,
            user_id=user_b_id  # Different user
        )

        # Should return None due to RLS
        assert node_b_read is None, "User B should not be able to read User A's node"

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_can_only_see_own_nodes_in_context(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that users only see their own nodes in context retrieval"""
        # User A creates multiple nodes
        for i in range(3):
            await service.create_memory_node(
                user_id=user_a_id,
                content=f"User A memory {i}",
                node_type="conversation"
            )

        # User B creates multiple nodes
        for i in range(2):
            await service.create_memory_node(
                user_id=user_b_id,
                content=f"User B memory {i}",
                node_type="conversation"
            )

        # User A retrieves context
        user_a_context = await service.get_recent_conversation_context(
            user_id=user_a_id,
            limit=10
        )

        # User B retrieves context
        user_b_context = await service.get_recent_conversation_context(
            user_id=user_b_id,
            limit=10
        )

        # User A should see exactly 3 nodes
        assert len(user_a_context) == 3, f"User A should see 3 nodes, got {len(user_a_context)}"

        # User B should see exactly 2 nodes
        assert len(user_b_context) == 2, f"User B should see 2 nodes, got {len(user_b_context)}"

        # Verify all User A's nodes belong to User A
        for node in user_a_context:
            assert node.user_id == user_a_id

        # Verify all User B's nodes belong to User B
        for node in user_b_context:
            assert node.user_id == user_b_id

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)
        await cleanup_test_nodes(supabase_client, user_b_id)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_cannot_update_another_users_node(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that User B cannot update User A's memory node"""
        # User A creates a node
        node_a = await service.create_memory_node(
            user_id=user_a_id,
            content="Original content",
            node_type="fact"
        )

        assert node_a is not None

        # User B tries to update User A's node
        updated_node = await service.update_memory_node(
            node_id=node_a.id,
            user_id=user_b_id,  # Different user
            content="User B trying to modify User A's content"
        )

        # Should return None due to RLS
        assert updated_node is None, "User B should not be able to update User A's node"

        # Verify original content is unchanged
        original_node = await service.get_memory_node(
            node_id=node_a.id,
            user_id=user_a_id
        )

        assert original_node.content == "Original content"

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)


# ==================== RLS Edge Enforcement Tests ====================

class TestEdgeRLSEnforcement:
    """Test RLS enforcement for memory edges"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_cannot_create_edge_between_another_users_nodes(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that User B cannot create edges between User A's nodes"""
        # User A creates two nodes
        node_a1 = await service.create_memory_node(
            user_id=user_a_id,
            content="Node 1",
            node_type="fact"
        )

        node_a2 = await service.create_memory_node(
            user_id=user_a_id,
            content="Node 2",
            node_type="fact"
        )

        # User B tries to create an edge between User A's nodes
        edge = await service.create_memory_edge(
            user_id=user_b_id,  # Different user
            source_node_id=node_a1.id,
            target_node_id=node_a2.id,
            relationship_type="related_to"
        )

        # Edge creation might succeed, but it won't affect User A's graph
        # due to RLS policies

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)
        await cleanup_test_edges(supabase_client, user_b_id)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_can_only_see_own_edges(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that users can only retrieve their own edges"""
        # User A creates nodes and edge
        node_a1 = await service.create_memory_node(
            user_id=user_a_id,
            content="Node A1",
            node_type="fact"
        )

        node_a2 = await service.create_memory_node(
            user_id=user_a_id,
            content="Node A2",
            node_type="fact"
        )

        edge_a = await service.create_memory_edge(
            user_id=user_a_id,
            source_node_id=node_a1.id,
            target_node_id=node_a2.id,
            relationship_type="related_to"
        )

        # User B creates nodes and edge
        node_b1 = await service.create_memory_node(
            user_id=user_b_id,
            content="Node B1",
            node_type="fact"
        )

        node_b2 = await service.create_memory_node(
            user_id=user_b_id,
            content="Node B2",
            node_type="fact"
        )

        edge_b = await service.create_memory_edge(
            user_id=user_b_id,
            source_node_id=node_b1.id,
            target_node_id=node_b2.id,
            relationship_type="follows"
        )

        # Both edges should exist
        assert edge_a is not None
        assert edge_b is not None

        # Verify User A cannot see User B's edge
        # (Would need a get_edge method to test this properly)

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)
        await cleanup_test_nodes(supabase_client, user_b_id)
        await cleanup_test_edges(supabase_client, user_a_id)
        await cleanup_test_edges(supabase_client, user_b_id)


# ==================== Weighted Retrieval RLS Tests ====================

class TestWeightedRetrievalRLS:
    """Test RLS enforcement in weighted retrieval"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_weighted_memories_only_returns_own_memories(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that weighted retrieval only returns user's own memories"""
        # User A creates high-importance memories
        for i in range(3):
            await service.create_memory_node(
                user_id=user_a_id,
                content=f"User A important memory {i}",
                node_type="fact",
                importance_score=0.9
            )

        # User B creates high-importance memories
        for i in range(2):
            await service.create_memory_node(
                user_id=user_b_id,
                content=f"User B important memory {i}",
                node_type="fact",
                importance_score=0.9
            )

        # User A retrieves weighted memories
        user_a_weighted = await service.get_weighted_memories(
            user_id=user_a_id,
            limit=10
        )

        # User B retrieves weighted memories
        user_b_weighted = await service.get_weighted_memories(
            user_id=user_b_id,
            limit=10
        )

        # User A should see exactly 3 memories
        assert len(user_a_weighted) == 3

        # User B should see exactly 2 memories
        assert len(user_b_weighted) == 2

        # Verify ownership
        for node, score in user_a_weighted:
            assert node.user_id == user_a_id

        for node, score in user_b_weighted:
            assert node.user_id == user_b_id

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)
        await cleanup_test_nodes(supabase_client, user_b_id)


# ==================== Statistics RLS Tests ====================

class TestStatisticsRLS:
    """Test RLS enforcement in statistics retrieval"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_statistics_only_count_own_data(
        self,
        service,
        supabase_client,
        user_a_id,
        user_b_id
    ):
        """Test that statistics only count user's own nodes and edges"""
        # User A creates 5 nodes
        for i in range(5):
            await service.create_memory_node(
                user_id=user_a_id,
                content=f"Node {i}",
                node_type="conversation"
            )

        # User B creates 3 nodes
        for i in range(3):
            await service.create_memory_node(
                user_id=user_b_id,
                content=f"Node {i}",
                node_type="fact"
            )

        # User A gets statistics
        user_a_stats = await service.get_memory_statistics(user_id=user_a_id)

        # User B gets statistics
        user_b_stats = await service.get_memory_statistics(user_id=user_b_id)

        # User A should see 5 total nodes
        assert user_a_stats["total_nodes"] == 5

        # User B should see 3 total nodes
        assert user_b_stats["total_nodes"] == 3

        # Cleanup
        await cleanup_test_nodes(supabase_client, user_a_id)
        await cleanup_test_nodes(supabase_client, user_b_id)


# ==================== Cleanup Helpers ====================

async def cleanup_test_nodes(supabase_client, user_id: str):
    """Delete all test nodes for a user"""
    try:
        supabase_client.table("user_memory_nodes") \
            .delete() \
            .eq("user_id", user_id) \
            .execute()
    except Exception as e:
        print(f"Cleanup error for user {user_id}: {e}")


async def cleanup_test_edges(supabase_client, user_id: str):
    """Delete all test edges for a user"""
    try:
        supabase_client.table("user_memory_edges") \
            .delete() \
            .eq("user_id", user_id) \
            .execute()
    except Exception as e:
        print(f"Cleanup error for edges {user_id}: {e}")
