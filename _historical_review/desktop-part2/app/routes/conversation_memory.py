"""
Empire v7.3 - Conversation Memory API Routes (Task 32)

REST API endpoints for managing user conversation memory using graph tables.
Provides CRUD operations for memory nodes/edges, context retrieval,
semantic search, and graph traversal.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import time
import structlog

from app.services.conversation_memory_service import (
    ConversationMemoryService,
    MemoryNode,
    MemoryEdge
)
from app.middleware.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/memory", tags=["Conversation Memory"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateMemoryNodeRequest(BaseModel):
    """Request to create a memory node."""
    content: str = Field(..., min_length=1, max_length=10000, description="Memory content")
    node_type: str = Field(
        default="conversation",
        description="Node type: conversation, fact, preference, context, entity"
    )
    session_id: Optional[str] = Field(None, description="Session identifier")
    summary: Optional[str] = Field(None, max_length=500, description="Brief summary")
    importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Importance score 0-1"
    )
    embedding: Optional[List[float]] = Field(None, description="768-dim vector embedding")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateMemoryNodeRequest(BaseModel):
    """Request to update a memory node."""
    content: Optional[str] = Field(None, max_length=10000)
    summary: Optional[str] = Field(None, max_length=500)
    importance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    embedding: Optional[List[float]] = None
    increment_mention_count: bool = Field(default=False)
    metadata: Optional[Dict[str, Any]] = None


class MemoryNodeResponse(BaseModel):
    """Memory node response."""
    id: str
    user_id: str
    session_id: Optional[str]
    node_type: str
    content: str
    summary: Optional[str]
    importance_score: float
    confidence_score: float
    mention_count: int
    first_mentioned_at: Optional[datetime]
    last_mentioned_at: Optional[datetime]
    is_active: bool
    metadata: Dict[str, Any]


class CreateMemoryEdgeRequest(BaseModel):
    """Request to create a memory edge."""
    source_node_id: str = Field(..., description="Source node UUID")
    target_node_id: str = Field(..., description="Target node UUID")
    relationship_type: str = Field(
        default="related_to",
        description="Relationship: related_to, follows, contradicts, supports, mentions"
    )
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    directionality: str = Field(default="directed", description="directed or undirected")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MemoryEdgeResponse(BaseModel):
    """Memory edge response."""
    id: str
    user_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    strength: float
    directionality: str
    observation_count: int
    is_active: bool
    metadata: Dict[str, Any]


class ContextRequest(BaseModel):
    """Request for context retrieval."""
    session_id: Optional[str] = None
    node_types: Optional[List[str]] = Field(None, description="Filter by node types")
    limit: int = Field(default=10, ge=1, le=100)


class WeightedMemoryRequest(BaseModel):
    """Request for weighted memory retrieval."""
    limit: int = Field(default=20, ge=1, le=100)
    recency_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    access_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    time_decay_hours: int = Field(default=168, ge=1, description="Time decay window in hours")


class SemanticSearchRequest(BaseModel):
    """Request for semantic similarity search."""
    query_embedding: List[float] = Field(..., description="768-dim query vector")
    limit: int = Field(default=10, ge=1, le=50)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class GraphTraversalRequest(BaseModel):
    """Request for graph traversal."""
    start_node_id: str = Field(..., description="Starting node UUID")
    max_depth: int = Field(default=2, ge=1, le=5)
    relationship_types: Optional[List[str]] = Field(None, description="Filter by relationship types")


class MemoryStatsResponse(BaseModel):
    """Memory statistics response."""
    total_nodes: int
    active_nodes: int
    total_edges: int
    active_edges: int
    nodes_by_type: Dict[str, int]
    edges_by_type: Dict[str, int]


# =============================================================================
# Helper Functions
# =============================================================================

def get_memory_service() -> ConversationMemoryService:
    """Get conversation memory service instance."""
    return ConversationMemoryService()


def node_to_response(node: MemoryNode) -> MemoryNodeResponse:
    """Convert MemoryNode to response model."""
    return MemoryNodeResponse(
        id=str(node.id),
        user_id=node.user_id,
        session_id=node.session_id,
        node_type=node.node_type,
        content=node.content,
        summary=node.summary,
        importance_score=node.importance_score,
        confidence_score=node.confidence_score,
        mention_count=node.mention_count,
        first_mentioned_at=node.first_mentioned_at,
        last_mentioned_at=node.last_mentioned_at,
        is_active=node.is_active,
        metadata=node.metadata or {}
    )


def edge_to_response(edge: MemoryEdge) -> MemoryEdgeResponse:
    """Convert MemoryEdge to response model."""
    return MemoryEdgeResponse(
        id=str(edge.id),
        user_id=edge.user_id,
        source_node_id=str(edge.source_node_id),
        target_node_id=str(edge.target_node_id),
        relationship_type=edge.relationship_type,
        strength=edge.strength,
        directionality=edge.directionality,
        observation_count=edge.observation_count,
        is_active=edge.is_active,
        metadata=edge.metadata or {}
    )


# =============================================================================
# Memory Node Endpoints
# =============================================================================

@router.post("/nodes", response_model=MemoryNodeResponse)
async def create_memory_node(
    request: CreateMemoryNodeRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create a new memory node.

    Stores a fact, preference, or context in the user's memory graph.
    """
    start_time = time.time()

    try:
        service = get_memory_service()

        node = await service.create_memory_node(
            user_id=user_id,
            content=request.content,
            node_type=request.node_type,
            session_id=request.session_id,
            summary=request.summary,
            embedding=request.embedding,
            importance_score=request.importance_score,
            metadata=request.metadata
        )

        if not node:
            raise HTTPException(status_code=500, detail="Failed to create memory node")

        logger.info(
            "memory_node_created",
            node_id=str(node.id),
            user_id=user_id,
            node_type=request.node_type,
            duration_ms=int((time.time() - start_time) * 1000)
        )

        return node_to_response(node)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_memory_node_failed", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=f"Failed to create memory node: {str(e)}")


@router.get("/nodes/{node_id}", response_model=MemoryNodeResponse)
async def get_memory_node(
    node_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get a specific memory node by ID.
    """
    try:
        service = get_memory_service()
        node = await service.get_memory_node(
            node_id=UUID(node_id),
            user_id=user_id
        )

        if not node:
            raise HTTPException(status_code=404, detail="Memory node not found")

        return node_to_response(node)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")
    except Exception as e:
        logger.error("get_memory_node_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/nodes/{node_id}", response_model=MemoryNodeResponse)
async def update_memory_node(
    node_id: str,
    request: UpdateMemoryNodeRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Update an existing memory node.
    """
    try:
        service = get_memory_service()

        node = await service.update_memory_node(
            node_id=UUID(node_id),
            user_id=user_id,
            content=request.content,
            summary=request.summary,
            embedding=request.embedding,
            increment_mention_count=request.increment_mention_count,
            importance_score=request.importance_score,
            metadata_updates=request.metadata
        )

        if not node:
            raise HTTPException(status_code=404, detail="Memory node not found")

        logger.info("memory_node_updated", node_id=node_id, user_id=user_id)
        return node_to_response(node)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")
    except Exception as e:
        logger.error("update_memory_node_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/nodes/{node_id}")
async def deactivate_memory_node(
    node_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Soft-delete (deactivate) a memory node.
    """
    try:
        service = get_memory_service()

        # Deactivate by updating is_active to false
        node = await service.update_memory_node(
            node_id=UUID(node_id),
            user_id=user_id
        )

        if not node:
            raise HTTPException(status_code=404, detail="Memory node not found")

        # Actually deactivate via direct update
        service.supabase.table("user_memory_nodes") \
            .update({"is_active": False}) \
            .eq("id", node_id) \
            .eq("user_id", user_id) \
            .execute()

        logger.info("memory_node_deactivated", node_id=node_id, user_id=user_id)
        return {"message": "Memory node deactivated", "node_id": node_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("deactivate_memory_node_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Memory Edge Endpoints
# =============================================================================

@router.post("/edges", response_model=MemoryEdgeResponse)
async def create_memory_edge(
    request: CreateMemoryEdgeRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create a relationship edge between two memory nodes.
    """
    try:
        service = get_memory_service()

        edge = await service.create_memory_edge(
            user_id=user_id,
            source_node_id=UUID(request.source_node_id),
            target_node_id=UUID(request.target_node_id),
            relationship_type=request.relationship_type,
            strength=request.strength,
            directionality=request.directionality,
            metadata=request.metadata
        )

        if not edge:
            raise HTTPException(status_code=500, detail="Failed to create memory edge")

        logger.info(
            "memory_edge_created",
            edge_id=str(edge.id),
            source=request.source_node_id,
            target=request.target_node_id,
            relationship=request.relationship_type
        )

        return edge_to_response(edge)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")
    except Exception as e:
        logger.error("create_memory_edge_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/edges/{edge_id}", response_model=MemoryEdgeResponse)
async def update_memory_edge(
    edge_id: str,
    strength: Optional[float] = Query(None, ge=0.0, le=1.0),
    increment_observation: bool = Query(default=False),
    user_id: str = Depends(get_current_user)
):
    """
    Update a memory edge (strength, observation count).
    """
    try:
        service = get_memory_service()

        edge = await service.update_memory_edge(
            edge_id=UUID(edge_id),
            user_id=user_id,
            strength=strength,
            increment_observation_count=increment_observation
        )

        if not edge:
            raise HTTPException(status_code=404, detail="Memory edge not found")

        logger.info("memory_edge_updated", edge_id=edge_id, user_id=user_id)
        return edge_to_response(edge)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_memory_edge_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Context Retrieval Endpoints
# =============================================================================

@router.post("/context/recent", response_model=List[MemoryNodeResponse])
async def get_recent_context(
    request: ContextRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Get recent conversation context (last N memories).

    Useful for maintaining conversation continuity within a session.
    """
    start_time = time.time()

    try:
        service = get_memory_service()

        nodes = await service.get_recent_conversation_context(
            user_id=user_id,
            session_id=request.session_id,
            limit=request.limit,
            node_types=request.node_types
        )

        logger.info(
            "recent_context_retrieved",
            user_id=user_id,
            count=len(nodes),
            duration_ms=int((time.time() - start_time) * 1000)
        )

        return [node_to_response(node) for node in nodes]

    except Exception as e:
        logger.error("get_recent_context_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context/weighted")
async def get_weighted_context(
    request: WeightedMemoryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Get weighted memories based on recency, importance, and access frequency.

    Returns memories sorted by combined score for optimal context retrieval.
    """
    start_time = time.time()

    try:
        service = get_memory_service()

        weighted_memories = await service.get_weighted_memories(
            user_id=user_id,
            limit=request.limit,
            recency_weight=request.recency_weight,
            importance_weight=request.importance_weight,
            access_weight=request.access_weight,
            time_decay_hours=request.time_decay_hours
        )

        # Format response with scores
        results = [
            {
                "node": node_to_response(node).model_dump(),
                "weighted_score": round(score, 4)
            }
            for node, score in weighted_memories
        ]

        logger.info(
            "weighted_context_retrieved",
            user_id=user_id,
            count=len(results),
            duration_ms=int((time.time() - start_time) * 1000)
        )

        return {
            "memories": results,
            "count": len(results),
            "weights": {
                "recency": request.recency_weight,
                "importance": request.importance_weight,
                "access": request.access_weight
            },
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except Exception as e:
        logger.error("get_weighted_context_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Semantic Search Endpoint
# =============================================================================

@router.post("/search/semantic")
async def semantic_search(
    request: SemanticSearchRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Search memories by semantic similarity using vector embeddings.

    Requires a 768-dimensional query embedding (BGE-M3 format).
    """
    start_time = time.time()

    # Validate embedding dimension
    if len(request.query_embedding) != 768:
        raise HTTPException(
            status_code=400,
            detail=f"Query embedding must be 768 dimensions, got {len(request.query_embedding)}"
        )

    try:
        service = get_memory_service()

        results = await service.search_similar_memories(
            user_id=user_id,
            query_embedding=request.query_embedding,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )

        # Format response
        formatted_results = [
            {
                "node": node_to_response(node).model_dump(),
                "similarity": round(similarity, 4)
            }
            for node, similarity in results
        ]

        logger.info(
            "semantic_search_completed",
            user_id=user_id,
            results=len(formatted_results),
            threshold=request.similarity_threshold,
            duration_ms=int((time.time() - start_time) * 1000)
        )

        return {
            "results": formatted_results,
            "count": len(formatted_results),
            "threshold": request.similarity_threshold,
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except Exception as e:
        logger.error("semantic_search_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Graph Traversal Endpoint
# =============================================================================

@router.post("/graph/traverse")
async def traverse_memory_graph(
    request: GraphTraversalRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Traverse the memory graph from a starting node.

    Returns connected nodes up to max_depth hops away.
    """
    start_time = time.time()

    try:
        service = get_memory_service()

        # Use the RPC function for graph traversal if available
        try:
            response = service.supabase.rpc(
                "traverse_memory_graph",
                {
                    "p_user_id": user_id,
                    "p_start_node_id": request.start_node_id,
                    "p_max_depth": request.max_depth,
                    "p_relationship_types": request.relationship_types
                }
            ).execute()

            if response.data:
                nodes = response.data
            else:
                nodes = []

        except Exception as rpc_error:
            logger.warning(f"Graph traversal RPC not available: {rpc_error}")
            # Fallback: return empty result
            nodes = []

        logger.info(
            "graph_traversal_completed",
            user_id=user_id,
            start_node=request.start_node_id,
            nodes_found=len(nodes),
            duration_ms=int((time.time() - start_time) * 1000)
        )

        return {
            "start_node_id": request.start_node_id,
            "max_depth": request.max_depth,
            "nodes": nodes,
            "total_nodes": len(nodes),
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except Exception as e:
        logger.error("graph_traversal_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Statistics Endpoint
# =============================================================================

@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    user_id: str = Depends(get_current_user)
):
    """
    Get statistics about the user's memory graph.
    """
    try:
        service = get_memory_service()
        stats = await service.get_memory_statistics(user_id=user_id)

        if not stats:
            return MemoryStatsResponse(
                total_nodes=0,
                active_nodes=0,
                total_edges=0,
                active_edges=0,
                nodes_by_type={},
                edges_by_type={}
            )

        return MemoryStatsResponse(**stats)

    except Exception as e:
        logger.error("get_memory_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Maintenance Endpoints
# =============================================================================

@router.post("/maintenance/cleanup")
async def cleanup_old_memories(
    days_threshold: int = Query(default=90, ge=1, le=365),
    importance_threshold: float = Query(default=0.3, ge=0.0, le=1.0),
    user_id: str = Depends(get_current_user)
):
    """
    Deactivate old, low-importance memories.

    Only deactivates memories older than days_threshold with importance
    below importance_threshold.
    """
    try:
        service = get_memory_service()

        count = await service.deactivate_old_memories(
            user_id=user_id,
            days_threshold=days_threshold,
            importance_threshold=importance_threshold
        )

        logger.info(
            "memory_cleanup_completed",
            user_id=user_id,
            deactivated_count=count,
            days_threshold=days_threshold,
            importance_threshold=importance_threshold
        )

        return {
            "message": f"Deactivated {count} old memories",
            "deactivated_count": count,
            "days_threshold": days_threshold,
            "importance_threshold": importance_threshold
        }

    except Exception as e:
        logger.error("memory_cleanup_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for conversation memory service.
    """
    try:
        service = get_memory_service()

        # Check if Supabase connection is available
        is_healthy = service.supabase is not None

        return {
            "status": "healthy" if is_healthy else "degraded",
            "service": "conversation_memory",
            "supabase_connected": is_healthy,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "conversation_memory",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
