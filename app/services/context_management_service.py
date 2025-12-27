"""
Empire v7.3 - Context Management Service (Task 33)

Manages context retrieval for AI conversations by combining:
- Recent conversation history (last 5 messages)
- Relevant memory nodes from graph storage
- Graph traversal for related memories (1-2 hops)
- Recency and access-weighted retrieval
- Token budget management (4K tokens default)

Target: >90% context relevance, <200ms retrieval latency
"""

import structlog
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import math
import tiktoken

from app.services.conversation_memory_service import (
    ConversationMemoryService,
    MemoryNode
)

logger = structlog.get_logger(__name__)


class ContextSourceType(str, Enum):
    """Types of context sources"""
    RECENT_MESSAGE = "recent_message"
    MEMORY_NODE = "memory_node"
    GRAPH_TRAVERSAL = "graph_traversal"
    SEMANTIC_SEARCH = "semantic_search"


@dataclass
class ContextItem:
    """Represents a single item in the context window"""
    content: str
    source_type: ContextSourceType
    source_id: Optional[str] = None
    relevance_score: float = 1.0
    token_count: int = 0
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "relevance_score": self.relevance_score,
            "token_count": self.token_count,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }


@dataclass
class ContextWindow:
    """Represents the complete context window for a query"""
    items: List[ContextItem] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 4096
    user_id: str = ""
    session_id: Optional[str] = None
    query: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "query": self.query,
            "item_count": len(self.items),
            "token_utilization": round(self.total_tokens / self.max_tokens, 4) if self.max_tokens > 0 else 0
        }


@dataclass
class ContextConfig:
    """Configuration for context retrieval"""
    max_tokens: int = 4096
    max_recent_messages: int = 5
    max_memory_nodes: int = 20
    max_graph_depth: int = 2
    recency_weight: float = 0.4
    importance_weight: float = 0.3
    access_weight: float = 0.2
    semantic_weight: float = 0.1
    time_decay_hours: int = 168  # 1 week
    min_relevance_threshold: float = 0.3
    include_graph_traversal: bool = True
    include_semantic_search: bool = True


class ContextManagementService:
    """
    Manages context retrieval for AI conversations.

    Features:
    - Context window management with token budgets
    - Recency-weighted retrieval (recent > old)
    - Access-count-weighted retrieval (frequent > rare)
    - Graph traversal for related memories (1-2 hops)
    - Semantic similarity search for query-relevant memories
    - Token counting and budget management

    Target Performance:
    - >90% context relevance
    - <200ms retrieval latency
    """

    def __init__(
        self,
        memory_service: Optional[ConversationMemoryService] = None,
        config: Optional[ContextConfig] = None
    ):
        """
        Initialize the context management service.

        Args:
            memory_service: ConversationMemoryService instance
            config: ContextConfig for retrieval settings
        """
        self.memory_service = memory_service or ConversationMemoryService()
        self.config = config or ContextConfig()
        self.logger = logger

        # Initialize tokenizer for token counting (cl100k_base for GPT-4/Claude)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None
            self.logger.warning("tiktoken not available, using approximate token counting")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        if not text:
            return 0

        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Approximate: ~4 characters per token
            return len(text) // 4

    def _calculate_recency_score(
        self,
        timestamp: Optional[datetime],
        time_decay_hours: int = 168
    ) -> float:
        """
        Calculate recency score with exponential decay.

        Args:
            timestamp: When the memory was last mentioned
            time_decay_hours: Hours for decay calculation

        Returns:
            Score between 0 and 1 (1 = recent, 0 = old)
        """
        if not timestamp:
            return 0.5

        now = datetime.now()
        if timestamp.tzinfo:
            # Handle timezone-aware timestamps
            from datetime import timezone
            now = datetime.now(timezone.utc)

        hours_ago = (now - timestamp).total_seconds() / 3600

        # Exponential decay
        decay_rate = math.log(2) / time_decay_hours  # Half-life at time_decay_hours
        score = math.exp(-decay_rate * hours_ago)

        return max(0, min(1, score))

    def _calculate_access_score(
        self,
        mention_count: int,
        max_mentions: int = 100
    ) -> float:
        """
        Calculate access frequency score.

        Args:
            mention_count: Number of times memory was accessed
            max_mentions: Maximum expected mentions for normalization

        Returns:
            Score between 0 and 1
        """
        if mention_count <= 0:
            return 0

        # Logarithmic scaling to handle high mention counts
        score = math.log1p(mention_count) / math.log1p(max_mentions)
        return max(0, min(1, score))

    def _calculate_combined_score(
        self,
        node: MemoryNode,
        semantic_similarity: float = 0.0
    ) -> float:
        """
        Calculate combined relevance score for a memory node.

        Args:
            node: MemoryNode to score
            semantic_similarity: Optional semantic similarity score (0-1)

        Returns:
            Combined score between 0 and 1
        """
        recency_score = self._calculate_recency_score(
            node.last_mentioned_at,
            self.config.time_decay_hours
        )

        importance_score = node.importance_score

        access_score = self._calculate_access_score(node.mention_count)

        # Weighted combination
        combined = (
            self.config.recency_weight * recency_score +
            self.config.importance_weight * importance_score +
            self.config.access_weight * access_score +
            self.config.semantic_weight * semantic_similarity
        )

        # Normalize
        total_weight = (
            self.config.recency_weight +
            self.config.importance_weight +
            self.config.access_weight +
            self.config.semantic_weight
        )

        if total_weight > 0:
            combined /= total_weight

        return combined

    async def get_recent_messages(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 5
    ) -> List[ContextItem]:
        """
        Get recent conversation messages.

        Args:
            user_id: User identifier
            session_id: Optional session to filter by
            limit: Maximum messages to retrieve

        Returns:
            List of ContextItem objects
        """
        try:
            nodes = await self.memory_service.get_recent_conversation_context(
                user_id=user_id,
                session_id=session_id,
                limit=limit,
                node_types=["conversation"]
            )

            items = []
            for node in nodes:
                token_count = self.count_tokens(node.content)
                items.append(ContextItem(
                    content=node.content,
                    source_type=ContextSourceType.RECENT_MESSAGE,
                    source_id=str(node.id),
                    relevance_score=1.0,  # Recent messages are always relevant
                    token_count=token_count,
                    timestamp=node.last_mentioned_at,
                    metadata={
                        "node_type": node.node_type,
                        "session_id": node.session_id
                    }
                ))

            return items

        except Exception as e:
            self.logger.error("get_recent_messages_failed", error=str(e))
            return []

    async def get_weighted_memories(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[ContextItem]:
        """
        Get memories weighted by recency, importance, and access.

        Args:
            user_id: User identifier
            limit: Maximum memories to retrieve

        Returns:
            List of ContextItem objects sorted by relevance
        """
        try:
            weighted_memories = await self.memory_service.get_weighted_memories(
                user_id=user_id,
                limit=limit,
                recency_weight=self.config.recency_weight,
                importance_weight=self.config.importance_weight,
                access_weight=self.config.access_weight,
                time_decay_hours=self.config.time_decay_hours
            )

            items = []
            for node, score in weighted_memories:
                if score < self.config.min_relevance_threshold:
                    continue

                token_count = self.count_tokens(node.content)
                items.append(ContextItem(
                    content=node.content,
                    source_type=ContextSourceType.MEMORY_NODE,
                    source_id=str(node.id),
                    relevance_score=score,
                    token_count=token_count,
                    timestamp=node.last_mentioned_at,
                    metadata={
                        "node_type": node.node_type,
                        "importance_score": node.importance_score,
                        "mention_count": node.mention_count
                    }
                ))

            return items

        except Exception as e:
            self.logger.error("get_weighted_memories_failed", error=str(e))
            return []

    async def get_graph_related_memories(
        self,
        user_id: str,
        start_node_ids: List[str],
        max_depth: int = 2
    ) -> List[ContextItem]:
        """
        Get memories related via graph traversal (1-2 hops).

        Args:
            user_id: User identifier
            start_node_ids: Node IDs to start traversal from
            max_depth: Maximum hops (1-2 recommended)

        Returns:
            List of ContextItem objects from graph traversal
        """
        if not self.config.include_graph_traversal:
            return []

        items = []
        seen_ids = set(start_node_ids)

        try:
            for start_id in start_node_ids[:5]:  # Limit starting nodes
                try:
                    response = self.memory_service.supabase.rpc(
                        "traverse_memory_graph",
                        {
                            "p_user_id": user_id,
                            "p_start_node_id": start_id,
                            "p_max_depth": max_depth,
                            "p_relationship_types": None  # All relationship types
                        }
                    ).execute()

                    if response.data:
                        for row in response.data:
                            node_id = row.get("node_id")
                            if node_id and str(node_id) not in seen_ids:
                                seen_ids.add(str(node_id))

                                content = row.get("content", "")
                                depth = row.get("depth", 1)

                                # Score decreases with depth
                                depth_penalty = 1.0 / (1 + depth * 0.3)

                                token_count = self.count_tokens(content)
                                items.append(ContextItem(
                                    content=content,
                                    source_type=ContextSourceType.GRAPH_TRAVERSAL,
                                    source_id=str(node_id),
                                    relevance_score=depth_penalty,
                                    token_count=token_count,
                                    metadata={
                                        "depth": depth,
                                        "node_type": row.get("node_type"),
                                        "relationship_type": row.get("relationship_type")
                                    }
                                ))

                except Exception as rpc_error:
                    self.logger.warning(
                        "graph_traversal_rpc_failed",
                        start_id=start_id,
                        error=str(rpc_error)
                    )
                    continue

            # Sort by relevance and limit
            items.sort(key=lambda x: x.relevance_score, reverse=True)
            return items[:self.config.max_memory_nodes]

        except Exception as e:
            self.logger.error("get_graph_related_memories_failed", error=str(e))
            return []

    async def get_semantic_memories(
        self,
        user_id: str,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[ContextItem]:
        """
        Get memories similar to query via semantic search.

        Args:
            user_id: User identifier
            query_embedding: Query vector embedding (768-dim)
            limit: Maximum results
            threshold: Minimum similarity threshold

        Returns:
            List of ContextItem objects from semantic search
        """
        if not self.config.include_semantic_search:
            return []

        try:
            results = await self.memory_service.search_similar_memories(
                user_id=user_id,
                query_embedding=query_embedding,
                limit=limit,
                similarity_threshold=threshold
            )

            items = []
            for node, similarity in results:
                if similarity < self.config.min_relevance_threshold:
                    continue

                # Combine semantic similarity with other scores
                combined_score = self._calculate_combined_score(node, similarity)

                token_count = self.count_tokens(node.content)
                items.append(ContextItem(
                    content=node.content,
                    source_type=ContextSourceType.SEMANTIC_SEARCH,
                    source_id=str(node.id),
                    relevance_score=combined_score,
                    token_count=token_count,
                    timestamp=node.last_mentioned_at,
                    metadata={
                        "node_type": node.node_type,
                        "semantic_similarity": similarity,
                        "importance_score": node.importance_score
                    }
                ))

            return items

        except Exception as e:
            self.logger.error("get_semantic_memories_failed", error=str(e))
            return []

    def _fit_to_token_budget(
        self,
        items: List[ContextItem],
        max_tokens: int
    ) -> Tuple[List[ContextItem], int]:
        """
        Fit items to token budget, prioritizing by relevance.

        Args:
            items: List of context items
            max_tokens: Maximum token budget

        Returns:
            Tuple of (fitted items, total tokens used)
        """
        # Sort by relevance score descending
        sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)

        fitted_items = []
        total_tokens = 0

        for item in sorted_items:
            if total_tokens + item.token_count <= max_tokens:
                fitted_items.append(item)
                total_tokens += item.token_count
            elif item.token_count <= max_tokens - total_tokens:
                # Item fits in remaining space
                fitted_items.append(item)
                total_tokens += item.token_count

        return fitted_items, total_tokens

    async def build_context_window(
        self,
        user_id: str,
        query: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        session_id: Optional[str] = None,
        config: Optional[ContextConfig] = None
    ) -> ContextWindow:
        """
        Build a complete context window for a query.

        Combines:
        1. Recent conversation messages (last 5)
        2. Weighted memory nodes (recency + importance + access)
        3. Graph-traversed related memories (1-2 hops)
        4. Semantically similar memories (if embedding provided)

        All fitted to token budget (default 4K tokens).

        Args:
            user_id: User identifier
            query: Optional query text
            query_embedding: Optional query embedding for semantic search
            session_id: Optional session identifier
            config: Optional context config override

        Returns:
            ContextWindow with fitted items
        """
        import time
        start_time = time.time()

        cfg = config or self.config
        all_items: List[ContextItem] = []

        # 1. Get recent messages (highest priority - always included)
        recent_items = await self.get_recent_messages(
            user_id=user_id,
            session_id=session_id,
            limit=cfg.max_recent_messages
        )

        # Reserve tokens for recent messages
        recent_tokens = sum(item.token_count for item in recent_items)
        remaining_budget = cfg.max_tokens - recent_tokens

        # 2. Get weighted memories
        memory_items = await self.get_weighted_memories(
            user_id=user_id,
            limit=cfg.max_memory_nodes
        )

        # 3. Get graph-traversed memories (if we have recent items to start from)
        graph_items = []
        if recent_items and cfg.include_graph_traversal:
            start_ids = [item.source_id for item in recent_items[:3] if item.source_id]
            graph_items = await self.get_graph_related_memories(
                user_id=user_id,
                start_node_ids=start_ids,
                max_depth=cfg.max_graph_depth
            )

        # 4. Get semantic memories (if embedding provided)
        semantic_items = []
        if query_embedding and cfg.include_semantic_search:
            semantic_items = await self.get_semantic_memories(
                user_id=user_id,
                query_embedding=query_embedding,
                limit=10,
                threshold=cfg.min_relevance_threshold
            )

        # Combine all non-recent items
        all_memory_items = memory_items + graph_items + semantic_items

        # Deduplicate by source_id
        seen_ids = set()
        unique_items = []
        for item in all_memory_items:
            if item.source_id and item.source_id not in seen_ids:
                seen_ids.add(item.source_id)
                unique_items.append(item)
            elif not item.source_id:
                unique_items.append(item)

        # Fit memory items to remaining budget
        fitted_memory_items, memory_tokens = self._fit_to_token_budget(
            unique_items,
            remaining_budget
        )

        # Combine: recent messages first, then memory items
        all_items = recent_items + fitted_memory_items
        total_tokens = recent_tokens + memory_tokens

        # Build context window
        context_window = ContextWindow(
            items=all_items,
            total_tokens=total_tokens,
            max_tokens=cfg.max_tokens,
            user_id=user_id,
            session_id=session_id,
            query=query
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        self.logger.info(
            "context_window_built",
            user_id=user_id,
            total_items=len(all_items),
            recent_count=len(recent_items),
            memory_count=len(fitted_memory_items),
            total_tokens=total_tokens,
            max_tokens=cfg.max_tokens,
            token_utilization=round(total_tokens / cfg.max_tokens, 4),
            elapsed_ms=elapsed_ms
        )

        return context_window

    async def get_context_for_query(
        self,
        user_id: str,
        query: str,
        query_embedding: Optional[List[float]] = None,
        session_id: Optional[str] = None,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Get formatted context for a query.

        This is the main entry point for getting context.

        Args:
            user_id: User identifier
            query: The user's query
            query_embedding: Optional query embedding for semantic search
            session_id: Optional session identifier
            max_tokens: Maximum token budget

        Returns:
            Dictionary with context text and metadata
        """
        config = ContextConfig(max_tokens=max_tokens)

        context_window = await self.build_context_window(
            user_id=user_id,
            query=query,
            query_embedding=query_embedding,
            session_id=session_id,
            config=config
        )

        # Format context as text
        context_parts = []

        # Add recent messages section
        recent_items = [
            item for item in context_window.items
            if item.source_type == ContextSourceType.RECENT_MESSAGE
        ]
        if recent_items:
            context_parts.append("## Recent Conversation")
            for item in recent_items:
                context_parts.append(f"- {item.content}")

        # Add memories section
        memory_items = [
            item for item in context_window.items
            if item.source_type != ContextSourceType.RECENT_MESSAGE
        ]
        if memory_items:
            context_parts.append("\n## Relevant Memories")
            for item in sorted(memory_items, key=lambda x: x.relevance_score, reverse=True):
                context_parts.append(f"- {item.content} (relevance: {item.relevance_score:.2f})")

        context_text = "\n".join(context_parts)

        return {
            "context_text": context_text,
            "context_window": context_window.to_dict(),
            "total_items": len(context_window.items),
            "total_tokens": context_window.total_tokens,
            "token_utilization": round(context_window.total_tokens / max_tokens, 4),
            "sources": {
                "recent_messages": len(recent_items),
                "memory_nodes": len([
                    i for i in memory_items
                    if i.source_type == ContextSourceType.MEMORY_NODE
                ]),
                "graph_traversal": len([
                    i for i in memory_items
                    if i.source_type == ContextSourceType.GRAPH_TRAVERSAL
                ]),
                "semantic_search": len([
                    i for i in memory_items
                    if i.source_type == ContextSourceType.SEMANTIC_SEARCH
                ])
            }
        }


# =============================================================================
# Singleton pattern for service access
# =============================================================================

_context_service: Optional[ContextManagementService] = None


def get_context_management_service() -> ContextManagementService:
    """Get or create the context management service singleton."""
    global _context_service
    if _context_service is None:
        _context_service = ContextManagementService()
    return _context_service


def reset_context_management_service() -> None:
    """Reset the context management service singleton (for testing)."""
    global _context_service
    _context_service = None
