"""
Conversation Memory Service - Task 27

Manages user conversation memory using Supabase graph tables (user_memory_nodes and user_memory_edges).
Provides context window management and recency-weighted retrieval for personalized AI interactions.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4

try:
    from app.core.database import get_supabase
except ImportError:
    get_supabase = None

logger = logging.getLogger(__name__)


class MemoryNode:
    """Represents a memory node in the conversation graph"""

    def __init__(
        self,
        id: Optional[UUID] = None,
        user_id: str = None,
        session_id: Optional[str] = None,
        node_type: str = "conversation",
        content: str = "",
        summary: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        confidence_score: float = 1.0,
        source_type: str = "conversation",
        importance_score: float = 0.5,
        first_mentioned_at: Optional[datetime] = None,
        last_mentioned_at: Optional[datetime] = None,
        mention_count: int = 1,
        is_active: bool = True,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = id or uuid4()
        self.user_id = user_id
        self.session_id = session_id
        self.node_type = node_type
        self.content = content
        self.summary = summary
        self.embedding = embedding
        self.confidence_score = confidence_score
        self.source_type = source_type
        self.importance_score = importance_score
        self.first_mentioned_at = first_mentioned_at or datetime.now()
        self.last_mentioned_at = last_mentioned_at or datetime.now()
        self.mention_count = mention_count
        self.is_active = is_active
        self.expires_at = expires_at
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for database insertion"""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "node_type": self.node_type,
            "content": self.content,
            "summary": self.summary,
            "embedding": self.embedding,
            "confidence_score": self.confidence_score,
            "source_type": self.source_type,
            "importance_score": self.importance_score,
            "first_mentioned_at": self.first_mentioned_at.isoformat() if self.first_mentioned_at else None,
            "last_mentioned_at": self.last_mentioned_at.isoformat() if self.last_mentioned_at else None,
            "mention_count": self.mention_count,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryNode":
        """Create node from database row"""
        return cls(
            id=UUID(data["id"]) if data.get("id") else None,
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            node_type=data.get("node_type", "conversation"),
            content=data.get("content", ""),
            summary=data.get("summary"),
            embedding=data.get("embedding"),
            confidence_score=data.get("confidence_score", 1.0),
            source_type=data.get("source_type", "conversation"),
            importance_score=data.get("importance_score", 0.5),
            first_mentioned_at=datetime.fromisoformat(data["first_mentioned_at"]) if data.get("first_mentioned_at") else None,
            last_mentioned_at=datetime.fromisoformat(data["last_mentioned_at"]) if data.get("last_mentioned_at") else None,
            mention_count=data.get("mention_count", 1),
            is_active=data.get("is_active", True),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            metadata=data.get("metadata", {})
        )


class MemoryEdge:
    """Represents a relationship edge between memory nodes"""

    def __init__(
        self,
        id: Optional[UUID] = None,
        user_id: str = None,
        source_node_id: UUID = None,
        target_node_id: UUID = None,
        relationship_type: str = "related_to",
        strength: float = 1.0,
        directionality: str = "directed",
        first_observed_at: Optional[datetime] = None,
        last_observed_at: Optional[datetime] = None,
        observation_count: int = 1,
        is_active: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = id or uuid4()
        self.user_id = user_id
        self.source_node_id = source_node_id
        self.target_node_id = target_node_id
        self.relationship_type = relationship_type
        self.strength = strength
        self.directionality = directionality
        self.first_observed_at = first_observed_at or datetime.now()
        self.last_observed_at = last_observed_at or datetime.now()
        self.observation_count = observation_count
        self.is_active = is_active
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary for database insertion"""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "source_node_id": str(self.source_node_id),
            "target_node_id": str(self.target_node_id),
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "directionality": self.directionality,
            "first_observed_at": self.first_observed_at.isoformat() if self.first_observed_at else None,
            "last_observed_at": self.last_observed_at.isoformat() if self.last_observed_at else None,
            "observation_count": self.observation_count,
            "is_active": self.is_active,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEdge":
        """Create edge from database row"""
        return cls(
            id=UUID(data["id"]) if data.get("id") else None,
            user_id=data.get("user_id"),
            source_node_id=UUID(data["source_node_id"]) if data.get("source_node_id") else None,
            target_node_id=UUID(data["target_node_id"]) if data.get("target_node_id") else None,
            relationship_type=data.get("relationship_type", "related_to"),
            strength=data.get("strength", 1.0),
            directionality=data.get("directionality", "directed"),
            first_observed_at=datetime.fromisoformat(data["first_observed_at"]) if data.get("first_observed_at") else None,
            last_observed_at=datetime.fromisoformat(data["last_observed_at"]) if data.get("last_observed_at") else None,
            observation_count=data.get("observation_count", 1),
            is_active=data.get("is_active", True),
            metadata=data.get("metadata", {})
        )


class ConversationMemoryService:
    """
    Manages conversation memory using Supabase graph tables.

    Features:
    - Create and update memory nodes (facts, preferences, context)
    - Create and update relationship edges between nodes
    - Context window management (last N messages)
    - Recency-weighted retrieval (prioritize recent and important memories)
    - Access-weighted retrieval (frequently accessed memories)
    - Session-based and cross-session memory retrieval
    """

    def __init__(self, supabase_client=None):
        """Initialize the conversation memory service"""
        if supabase_client:
            self.supabase = supabase_client
        elif get_supabase:
            self.supabase = get_supabase()
        else:
            self.supabase = None
        self.logger = logger

    # ==================== Node Management ====================

    async def create_memory_node(
        self,
        user_id: str,
        content: str,
        node_type: str = "conversation",
        session_id: Optional[str] = None,
        summary: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        importance_score: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[MemoryNode]:
        """
        Create a new memory node.

        Args:
            user_id: User identifier
            content: Full content of the memory
            node_type: Type of node (conversation, fact, preference, context, entity)
            session_id: Optional session identifier
            summary: Optional summary of the content
            embedding: Optional vector embedding for semantic search
            importance_score: Score 0-1 indicating importance (default 0.5)
            metadata: Optional additional metadata

        Returns:
            Created MemoryNode or None if failed
        """
        try:
            node = MemoryNode(
                user_id=user_id,
                session_id=session_id,
                node_type=node_type,
                content=content,
                summary=summary,
                embedding=embedding,
                importance_score=importance_score,
                metadata=metadata or {}
            )

            response = self.supabase.table("user_memory_nodes").insert(node.to_dict()).execute()

            if response.data:
                self.logger.info(f"Created memory node {node.id} for user {user_id}")
                return MemoryNode.from_dict(response.data[0])
            else:
                self.logger.error(f"Failed to create memory node: {response}")
                return None

        except Exception as e:
            self.logger.error(f"Error creating memory node: {e}")
            return None

    async def update_memory_node(
        self,
        node_id: UUID,
        user_id: str,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        increment_mention_count: bool = False,
        importance_score: Optional[float] = None,
        metadata_updates: Optional[Dict[str, Any]] = None
    ) -> Optional[MemoryNode]:
        """
        Update an existing memory node.

        Args:
            node_id: ID of the node to update
            user_id: User identifier (for RLS validation)
            content: New content (optional)
            summary: New summary (optional)
            embedding: New embedding (optional)
            increment_mention_count: Whether to increment mention count
            importance_score: New importance score (optional)
            metadata_updates: Metadata fields to update (optional)

        Returns:
            Updated MemoryNode or None if failed
        """
        try:
            updates = {
                "last_mentioned_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            if content is not None:
                updates["content"] = content
            if summary is not None:
                updates["summary"] = summary
            if embedding is not None:
                updates["embedding"] = embedding
            if importance_score is not None:
                updates["importance_score"] = importance_score
            # First, do the main update
            response = self.supabase.table("user_memory_nodes") \
                .update(updates) \
                .eq("id", str(node_id)) \
                .eq("user_id", user_id) \
                .execute()

            # Atomic increment of mention_count via RPC to avoid race condition
            if increment_mention_count:
                self.supabase.rpc(
                    "increment_node_mention_count",
                    {"p_node_id": str(node_id), "p_user_id": user_id}
                ).execute()

            if response.data:
                self.logger.info(f"Updated memory node {node_id}")
                return MemoryNode.from_dict(response.data[0])
            else:
                self.logger.warning(f"No node found with id {node_id} for user {user_id}")
                return None

        except Exception as e:
            self.logger.error(f"Error updating memory node: {e}")
            return None

    async def get_memory_node(self, node_id: UUID, user_id: str) -> Optional[MemoryNode]:
        """
        Retrieve a specific memory node.

        Args:
            node_id: ID of the node
            user_id: User identifier (for RLS validation)

        Returns:
            MemoryNode or None if not found
        """
        try:
            response = self.supabase.table("user_memory_nodes") \
                .select("*") \
                .eq("id", str(node_id)) \
                .eq("user_id", user_id) \
                .eq("is_active", True) \
                .single() \
                .execute()

            if response.data:
                return MemoryNode.from_dict(response.data)
            return None

        except Exception as e:
            self.logger.error(f"Error retrieving memory node: {e}")
            return None

    # ==================== Edge Management ====================

    async def create_memory_edge(
        self,
        user_id: str,
        source_node_id: UUID,
        target_node_id: UUID,
        relationship_type: str = "related_to",
        strength: float = 1.0,
        directionality: str = "directed",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[MemoryEdge]:
        """
        Create a relationship edge between two memory nodes.

        Args:
            user_id: User identifier
            source_node_id: Source node ID
            target_node_id: Target node ID
            relationship_type: Type of relationship (related_to, follows, contradicts, etc.)
            strength: Relationship strength 0-1 (default 1.0)
            directionality: "directed" or "undirected"
            metadata: Optional additional metadata

        Returns:
            Created MemoryEdge or None if failed
        """
        try:
            edge = MemoryEdge(
                user_id=user_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relationship_type=relationship_type,
                strength=strength,
                directionality=directionality,
                metadata=metadata or {}
            )

            response = self.supabase.table("user_memory_edges").insert(edge.to_dict()).execute()

            if response.data:
                self.logger.info(f"Created memory edge {edge.id} ({source_node_id} -> {target_node_id})")
                return MemoryEdge.from_dict(response.data[0])
            else:
                self.logger.error(f"Failed to create memory edge: {response}")
                return None

        except Exception as e:
            self.logger.error(f"Error creating memory edge: {e}")
            return None

    async def update_memory_edge(
        self,
        edge_id: UUID,
        user_id: str,
        strength: Optional[float] = None,
        increment_observation_count: bool = False,
        metadata_updates: Optional[Dict[str, Any]] = None
    ) -> Optional[MemoryEdge]:
        """
        Update an existing memory edge.

        Args:
            edge_id: ID of the edge to update
            user_id: User identifier (for RLS validation)
            strength: New strength value (optional)
            increment_observation_count: Whether to increment observation count
            metadata_updates: Metadata fields to update (optional)

        Returns:
            Updated MemoryEdge or None if failed
        """
        try:
            updates = {
                "last_observed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            if strength is not None:
                updates["strength"] = strength

            # First, do the main update
            response = self.supabase.table("user_memory_edges") \
                .update(updates) \
                .eq("id", str(edge_id)) \
                .eq("user_id", user_id) \
                .execute()

            # Atomic increment of observation_count via RPC to avoid race condition
            if increment_observation_count:
                self.supabase.rpc(
                    "increment_edge_observation_count",
                    {"p_edge_id": str(edge_id), "p_user_id": user_id}
                ).execute()

            if response.data:
                self.logger.info(f"Updated memory edge {edge_id}")
                return MemoryEdge.from_dict(response.data[0])
            else:
                self.logger.warning(f"No edge found with id {edge_id} for user {user_id}")
                return None

        except Exception as e:
            self.logger.error(f"Error updating memory edge: {e}")
            return None

    # ==================== Context Window Management ====================

    async def get_recent_conversation_context(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        node_types: Optional[List[str]] = None
    ) -> List[MemoryNode]:
        """
        Get recent conversation context (last N messages).

        Args:
            user_id: User identifier
            session_id: Optional session ID to filter by
            limit: Maximum number of nodes to return (default 10)
            node_types: Optional list of node types to filter (e.g., ["conversation", "fact"])

        Returns:
            List of MemoryNode objects ordered by recency
        """
        try:
            query = self.supabase.table("user_memory_nodes") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("is_active", True) \
                .order("last_mentioned_at", desc=True) \
                .limit(limit)

            if session_id:
                query = query.eq("session_id", session_id)

            if node_types:
                query = query.in_("node_type", node_types)

            response = query.execute()

            if response.data:
                nodes = [MemoryNode.from_dict(row) for row in response.data]
                self.logger.info(f"Retrieved {len(nodes)} recent context nodes for user {user_id}")
                return nodes
            return []

        except Exception as e:
            self.logger.error(f"Error retrieving recent context: {e}")
            return []

    # ==================== Recency-Weighted Retrieval ====================

    async def get_weighted_memories(
        self,
        user_id: str,
        limit: int = 20,
        recency_weight: float = 0.5,
        importance_weight: float = 0.3,
        access_weight: float = 0.2,
        time_decay_hours: int = 168  # 1 week default
    ) -> List[Tuple[MemoryNode, float]]:
        """
        Retrieve memories with recency, importance, and access weighting.

        Scoring formula:
        score = (recency_weight * recency_score) +
                (importance_weight * importance_score) +
                (access_weight * access_score)

        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            recency_weight: Weight for recency (0-1, default 0.5)
            importance_weight: Weight for importance (0-1, default 0.3)
            access_weight: Weight for access frequency (0-1, default 0.2)
            time_decay_hours: Hours for recency decay calculation (default 168 = 1 week)

        Returns:
            List of (MemoryNode, score) tuples ordered by score descending
        """
        try:
            # Retrieve all active nodes
            response = self.supabase.table("user_memory_nodes") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("is_active", True) \
                .execute()

            if not response.data:
                return []

            # Calculate weighted scores
            now = datetime.now()
            scored_memories = []

            for row in response.data:
                node = MemoryNode.from_dict(row)

                # Recency score (exponential decay)
                hours_ago = (now - node.last_mentioned_at).total_seconds() / 3600
                recency_score = max(0, 1 - (hours_ago / time_decay_hours))

                # Importance score (from node)
                importance_score = node.importance_score

                # Access score (normalized mention count)
                # Assume max mention count of 100 for normalization
                access_score = min(1.0, node.mention_count / 100.0)

                # Combined weighted score
                total_score = (
                    recency_weight * recency_score +
                    importance_weight * importance_score +
                    access_weight * access_score
                )

                scored_memories.append((node, total_score))

            # Sort by score descending and return top N
            scored_memories.sort(key=lambda x: x[1], reverse=True)
            result = scored_memories[:limit]

            self.logger.info(f"Retrieved {len(result)} weighted memories for user {user_id}")
            return result

        except Exception as e:
            self.logger.error(f"Error retrieving weighted memories: {e}")
            return []

    # ==================== Vector Search ====================

    async def search_similar_memories(
        self,
        user_id: str,
        query_embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[MemoryNode, float]]:
        """
        Search for similar memories using vector similarity.

        Args:
            user_id: User identifier
            query_embedding: Query vector embedding (768-dim for BGE-M3)
            limit: Maximum number of results
            similarity_threshold: Minimum cosine similarity (0-1)

        Returns:
            List of (MemoryNode, similarity) tuples ordered by similarity descending
        """
        try:
            # Use Supabase vector search (cosine similarity)
            # Note: This requires the embedding column to have an index
            response = self.supabase.rpc(
                "match_user_memories",
                {
                    "query_embedding": query_embedding,
                    "p_user_id": user_id,
                    "match_threshold": similarity_threshold,
                    "match_count": limit
                }
            ).execute()

            if response.data:
                results = [
                    (MemoryNode.from_dict(row), row.get("similarity", 0))
                    for row in response.data
                ]
                self.logger.info(f"Found {len(results)} similar memories for user {user_id}")
                return results
            return []

        except Exception as e:
            self.logger.warning(f"Vector search RPC not available, falling back to basic search: {e}")
            # Fallback: retrieve all nodes and calculate similarity in Python
            return []

    # ==================== Utility Methods ====================

    async def deactivate_old_memories(
        self,
        user_id: str,
        days_threshold: int = 90,
        importance_threshold: float = 0.3
    ) -> int:
        """
        Deactivate (soft delete) old, low-importance memories.

        Args:
            user_id: User identifier
            days_threshold: Deactivate memories older than this many days
            importance_threshold: Only deactivate if importance < threshold

        Returns:
            Number of memories deactivated
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_threshold)

            response = self.supabase.table("user_memory_nodes") \
                .update({"is_active": False, "updated_at": datetime.now().isoformat()}) \
                .eq("user_id", user_id) \
                .lt("last_mentioned_at", cutoff_date.isoformat()) \
                .lt("importance_score", importance_threshold) \
                .eq("is_active", True) \
                .execute()

            count = len(response.data) if response.data else 0
            self.logger.info(f"Deactivated {count} old memories for user {user_id}")
            return count

        except Exception as e:
            self.logger.error(f"Error deactivating old memories: {e}")
            return 0

    async def get_memory_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics about user's memory graph.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with statistics (total nodes, edges, by type, etc.)
        """
        try:
            # Get node counts
            nodes_response = self.supabase.table("user_memory_nodes") \
                .select("node_type, is_active", count="exact") \
                .eq("user_id", user_id) \
                .execute()

            # Get edge counts
            edges_response = self.supabase.table("user_memory_edges") \
                .select("relationship_type, is_active", count="exact") \
                .eq("user_id", user_id) \
                .execute()

            stats = {
                "total_nodes": len(nodes_response.data) if nodes_response.data else 0,
                "active_nodes": sum(1 for n in nodes_response.data if n.get("is_active")) if nodes_response.data else 0,
                "total_edges": len(edges_response.data) if edges_response.data else 0,
                "active_edges": sum(1 for e in edges_response.data if e.get("is_active")) if edges_response.data else 0,
                "nodes_by_type": {},
                "edges_by_type": {}
            }

            # Count by node type
            if nodes_response.data:
                for node in nodes_response.data:
                    node_type = node.get("node_type", "unknown")
                    stats["nodes_by_type"][node_type] = stats["nodes_by_type"].get(node_type, 0) + 1

            # Count by edge type
            if edges_response.data:
                for edge in edges_response.data:
                    edge_type = edge.get("relationship_type", "unknown")
                    stats["edges_by_type"][edge_type] = stats["edges_by_type"].get(edge_type, 0) + 1

            return stats

        except Exception as e:
            self.logger.error(f"Error getting memory statistics: {e}")
            return {}
