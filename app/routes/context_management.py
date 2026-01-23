"""
Empire v7.3 - Context Management API Routes (Task 33)

REST API endpoints for context retrieval and management.
Provides context window building for AI conversations with:
- Recent message retrieval
- Weighted memory retrieval
- Graph traversal (1-2 hops)
- Semantic search
- Token budget management
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import time
import structlog

from app.services.context_management_service import (
    ContextManagementService,
    ContextConfig,
    ContextWindow,
    ContextItem,
    get_context_management_service
)
from app.middleware.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/context", tags=["Context Management"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ContextQueryRequest(BaseModel):
    """Request for building context window."""
    query: str = Field(..., min_length=1, max_length=10000, description="User query")
    query_embedding: Optional[List[float]] = Field(
        None,
        description="768-dim query embedding for semantic search"
    )
    session_id: Optional[str] = Field(None, description="Session identifier")
    max_tokens: int = Field(default=4096, ge=512, le=16384, description="Token budget")
    max_recent_messages: int = Field(default=5, ge=1, le=20)
    max_memory_nodes: int = Field(default=20, ge=1, le=100)
    include_graph_traversal: bool = Field(default=True)
    include_semantic_search: bool = Field(default=True)


class ContextConfigRequest(BaseModel):
    """Request to configure context retrieval."""
    max_tokens: int = Field(default=4096, ge=512, le=16384)
    max_recent_messages: int = Field(default=5, ge=1, le=20)
    max_memory_nodes: int = Field(default=20, ge=1, le=100)
    max_graph_depth: int = Field(default=2, ge=1, le=3)
    recency_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    access_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    semantic_weight: float = Field(default=0.1, ge=0.0, le=1.0)
    time_decay_hours: int = Field(default=168, ge=1, le=720)
    min_relevance_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    include_graph_traversal: bool = Field(default=True)
    include_semantic_search: bool = Field(default=True)


class ContextItemResponse(BaseModel):
    """Response model for a context item."""
    content: str
    source_type: str
    source_id: Optional[str]
    relevance_score: float
    token_count: int
    timestamp: Optional[datetime]
    metadata: Dict[str, Any]


class ContextWindowResponse(BaseModel):
    """Response model for a context window."""
    items: List[ContextItemResponse]
    total_tokens: int
    max_tokens: int
    user_id: str
    session_id: Optional[str]
    query: Optional[str]
    item_count: int
    token_utilization: float


class ContextResponse(BaseModel):
    """Full context response with text and metadata."""
    context_text: str
    total_items: int
    total_tokens: int
    token_utilization: float
    sources: Dict[str, int]
    query_time_ms: int


class RecentMessagesRequest(BaseModel):
    """Request for recent messages."""
    session_id: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)


class WeightedMemoriesRequest(BaseModel):
    """Request for weighted memories."""
    limit: int = Field(default=20, ge=1, le=100)
    recency_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    access_weight: float = Field(default=0.2, ge=0.0, le=1.0)


class GraphTraversalRequest(BaseModel):
    """Request for graph traversal."""
    start_node_ids: List[str] = Field(..., min_length=1, max_length=10)
    max_depth: int = Field(default=2, ge=1, le=3)


class SemanticSearchRequest(BaseModel):
    """Request for semantic search."""
    query_embedding: List[float] = Field(..., description="768-dim query embedding")
    limit: int = Field(default=10, ge=1, le=50)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


# =============================================================================
# Main Context Endpoints
# =============================================================================

@router.post("/query", response_model=ContextResponse)
async def get_context_for_query(
    request: ContextQueryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Build context window for a query.

    This is the main endpoint for getting context for AI conversations.
    Combines:
    - Recent conversation messages (last N)
    - Weighted memory nodes (recency + importance + access)
    - Graph-traversed related memories (1-2 hops)
    - Semantically similar memories (if embedding provided)

    All fitted to token budget (default 4K tokens).
    """
    start_time = time.time()

    try:
        service = get_context_management_service()

        # Validate embedding dimension if provided
        if request.query_embedding and len(request.query_embedding) != 768:
            raise HTTPException(
                status_code=400,
                detail=f"Query embedding must be 768 dimensions, got {len(request.query_embedding)}"
            )

        result = await service.get_context_for_query(
            user_id=user_id,
            query=request.query,
            query_embedding=request.query_embedding,
            session_id=request.session_id,
            max_tokens=request.max_tokens
        )

        query_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "context_query_completed",
            user_id=user_id,
            total_items=result["total_items"],
            total_tokens=result["total_tokens"],
            query_time_ms=query_time_ms
        )

        return ContextResponse(
            context_text=result["context_text"],
            total_items=result["total_items"],
            total_tokens=result["total_tokens"],
            token_utilization=result["token_utilization"],
            sources=result["sources"],
            query_time_ms=query_time_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_context_for_query_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while building context")


@router.post("/window/build")
async def build_context_window(
    request: ContextQueryRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Build a complete context window with all items.

    Returns detailed context window with all items and metadata.
    Use /query for a simpler response with formatted text.
    """
    start_time = time.time()

    try:
        service = get_context_management_service()

        # Build config from request
        config = ContextConfig(
            max_tokens=request.max_tokens,
            max_recent_messages=request.max_recent_messages,
            max_memory_nodes=request.max_memory_nodes,
            include_graph_traversal=request.include_graph_traversal,
            include_semantic_search=request.include_semantic_search
        )

        # Validate embedding dimension if provided
        if request.query_embedding and len(request.query_embedding) != 768:
            raise HTTPException(
                status_code=400,
                detail=f"Query embedding must be 768 dimensions, got {len(request.query_embedding)}"
            )

        context_window = await service.build_context_window(
            user_id=user_id,
            query=request.query,
            query_embedding=request.query_embedding,
            session_id=request.session_id,
            config=config
        )

        query_time_ms = int((time.time() - start_time) * 1000)

        response = context_window.to_dict()
        response["query_time_ms"] = query_time_ms

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("build_context_window_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while building context window")


# =============================================================================
# Individual Component Endpoints
# =============================================================================

@router.post("/recent")
async def get_recent_messages(
    request: RecentMessagesRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Get recent conversation messages.

    Returns the last N messages from conversation history.
    """
    start_time = time.time()

    try:
        service = get_context_management_service()

        items = await service.get_recent_messages(
            user_id=user_id,
            session_id=request.session_id,
            limit=request.limit
        )

        return {
            "items": [item.to_dict() for item in items],
            "count": len(items),
            "total_tokens": sum(item.token_count for item in items),
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except Exception as e:
        logger.error("get_recent_messages_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while retrieving recent messages")


@router.post("/weighted")
async def get_weighted_memories(
    request: WeightedMemoriesRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Get memories weighted by recency, importance, and access frequency.

    Returns memories sorted by combined relevance score.
    """
    start_time = time.time()

    try:
        service = get_context_management_service()

        # Update config weights temporarily
        original_config = service.config
        service.config = ContextConfig(
            recency_weight=request.recency_weight,
            importance_weight=request.importance_weight,
            access_weight=request.access_weight
        )

        items = await service.get_weighted_memories(
            user_id=user_id,
            limit=request.limit
        )

        # Restore original config
        service.config = original_config

        return {
            "items": [item.to_dict() for item in items],
            "count": len(items),
            "total_tokens": sum(item.token_count for item in items),
            "weights": {
                "recency": request.recency_weight,
                "importance": request.importance_weight,
                "access": request.access_weight
            },
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except Exception as e:
        logger.error("get_weighted_memories_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while retrieving weighted memories")


@router.post("/graph/related")
async def get_graph_related_memories(
    request: GraphTraversalRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Get memories related via graph traversal.

    Traverses the memory graph 1-2 hops from starting nodes
    to find related memories.
    """
    start_time = time.time()

    try:
        service = get_context_management_service()

        items = await service.get_graph_related_memories(
            user_id=user_id,
            start_node_ids=request.start_node_ids,
            max_depth=request.max_depth
        )

        return {
            "items": [item.to_dict() for item in items],
            "count": len(items),
            "total_tokens": sum(item.token_count for item in items),
            "start_nodes": request.start_node_ids,
            "max_depth": request.max_depth,
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except Exception as e:
        logger.error("get_graph_related_memories_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while retrieving graph-related memories")


@router.post("/semantic")
async def get_semantic_memories(
    request: SemanticSearchRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Get memories similar to query via semantic search.

    Requires a 768-dimensional query embedding (BGE-M3 format).
    """
    start_time = time.time()

    try:
        # Validate embedding dimension
        if len(request.query_embedding) != 768:
            raise HTTPException(
                status_code=400,
                detail=f"Query embedding must be 768 dimensions, got {len(request.query_embedding)}"
            )

        service = get_context_management_service()

        items = await service.get_semantic_memories(
            user_id=user_id,
            query_embedding=request.query_embedding,
            limit=request.limit,
            threshold=request.threshold
        )

        return {
            "items": [item.to_dict() for item in items],
            "count": len(items),
            "total_tokens": sum(item.token_count for item in items),
            "threshold": request.threshold,
            "query_time_ms": int((time.time() - start_time) * 1000)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_semantic_memories_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while performing semantic search")


# =============================================================================
# Utility Endpoints
# =============================================================================

@router.post("/tokens/count")
async def count_tokens(
    text: str = Query(..., min_length=1, max_length=100000)
):
    """
    Count tokens in text.

    Uses cl100k_base tokenizer (compatible with GPT-4/Claude).
    """
    try:
        service = get_context_management_service()
        token_count = service.count_tokens(text)

        return {
            "text_length": len(text),
            "token_count": token_count,
            "ratio": round(len(text) / token_count, 2) if token_count > 0 else 0
        }

    except Exception as e:
        logger.error("count_tokens_failed", error=str(e))
        raise HTTPException(status_code=500, detail="An internal error occurred while counting tokens")


@router.get("/config/defaults")
async def get_default_config():
    """
    Get default context configuration.
    """
    config = ContextConfig()
    return {
        "max_tokens": config.max_tokens,
        "max_recent_messages": config.max_recent_messages,
        "max_memory_nodes": config.max_memory_nodes,
        "max_graph_depth": config.max_graph_depth,
        "recency_weight": config.recency_weight,
        "importance_weight": config.importance_weight,
        "access_weight": config.access_weight,
        "semantic_weight": config.semantic_weight,
        "time_decay_hours": config.time_decay_hours,
        "min_relevance_threshold": config.min_relevance_threshold,
        "include_graph_traversal": config.include_graph_traversal,
        "include_semantic_search": config.include_semantic_search
    }


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def health_check():
    """
    Health check for context management service.
    """
    try:
        service = get_context_management_service()

        # Check memory service connection
        memory_service_healthy = (
            service.memory_service is not None and
            service.memory_service.supabase is not None
        )

        # Check tokenizer
        tokenizer_healthy = service.tokenizer is not None

        status = "healthy" if memory_service_healthy else "degraded"

        return {
            "status": status,
            "service": "context_management",
            "memory_service_connected": memory_service_healthy,
            "tokenizer_available": tokenizer_healthy,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "context_management",
            "error": "Service health check failed",
            "timestamp": datetime.now().isoformat()
        }
