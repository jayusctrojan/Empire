"""
Empire v7.3 - Hybrid Search API Routes (Task 27 & 34)

Provides REST API endpoints for hybrid search combining:
- Dense vector search (pgvector similarity)
- Sparse BM25 search (PostgreSQL full-text search)
- Fuzzy search (trigram similarity)
- ILIKE pattern matching
- Reciprocal Rank Fusion (RRF) for result combination
- User preference-based result boosting (Task 34.4)

Author: Empire AI Team
Date: January 2025
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Preference Boosting Helper (Task 34.4)
# ============================================================================

async def apply_preference_boost(
    results: List[Any],
    user_id: Optional[str],
    boost_factor: float = 0.2
) -> List[Any]:
    """
    Apply user preference-based boosting to search results (Task 34.4).

    Boosts results that match user's content preferences:
    - Topics of interest
    - Preferred document types
    - Domain preferences

    Args:
        results: Search results to boost
        user_id: User ID to get preferences for (None = no boosting)
        boost_factor: Maximum boost factor (0.0-1.0)

    Returns:
        Results with adjusted scores based on preferences
    """
    if not user_id or not results:
        return results

    try:
        from app.services.user_preference_service import UserPreferenceService
        from app.services.conversation_memory_service import ConversationMemoryService
        from app.core.database import get_supabase

        supabase = get_supabase()
        memory_service = ConversationMemoryService(supabase_client=supabase)
        pref_service = UserPreferenceService(memory_service=memory_service)

        # Get user's content preferences
        boost_data = await pref_service.get_content_preferences(user_id)

        if not boost_data.get("topics") and not boost_data.get("domains"):
            # No preferences to apply
            return results

        # Build lookup for topic/domain matching
        topic_weights = {t["topic"].lower(): t["weight"] for t in boost_data.get("topics", [])}
        domain_weights = {d["domain"].lower(): d["weight"] for d in boost_data.get("domains", [])}
        doc_type_weights = {dt["type"].lower(): dt["weight"] for dt in boost_data.get("document_types", [])}

        # Apply boosts to results
        boosted_results = []
        for result in results:
            content = result.content.lower() if hasattr(result, 'content') else ""
            metadata = result.metadata if hasattr(result, 'metadata') else {}

            boost = 0.0

            # Check topic matches
            for topic, weight in topic_weights.items():
                if topic in content:
                    boost += weight * boost_factor
                    break  # Only one topic boost per result

            # Check domain matches
            doc_domain = metadata.get("domain", "").lower()
            if doc_domain in domain_weights:
                boost += domain_weights[doc_domain] * boost_factor

            # Check document type matches
            doc_type = metadata.get("document_type", "").lower()
            if doc_type in doc_type_weights:
                boost += doc_type_weights[doc_type] * boost_factor

            # Apply boost (cap at boost_factor * 2)
            if boost > 0:
                result.score = min(1.0, result.score + min(boost, boost_factor * 2))

            boosted_results.append(result)

        # Re-sort by score and re-rank
        boosted_results.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(boosted_results):
            r.rank = i + 1

        return boosted_results

    except Exception as e:
        logger.warning(f"Preference boosting failed for user {user_id}: {e}")
        return results  # Return original results on error

router = APIRouter(prefix="/api/search", tags=["Hybrid Search"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SearchMethodEnum(str, Enum):
    """Available search methods"""
    DENSE = "dense"
    SPARSE = "sparse"
    FUZZY = "fuzzy"
    ILIKE = "ilike"
    HYBRID = "hybrid"
    HYBRID_RPC = "hybrid_rpc"


class HybridSearchRequest(BaseModel):
    """Request model for hybrid search"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    method: SearchMethodEnum = Field(
        default=SearchMethodEnum.HYBRID,
        description="Search method to use"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    namespace: Optional[str] = Field(default=None, description="Filter by namespace")
    metadata_filter: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filter by metadata fields"
    )

    # Weight configuration (for hybrid methods)
    dense_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Weight for dense search")
    sparse_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight for sparse search")
    fuzzy_weight: float = Field(default=0.2, ge=0.0, le=1.0, description="Weight for fuzzy search")

    # Threshold configuration
    min_dense_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum dense score")
    min_sparse_score: float = Field(default=0.0, ge=0.0, description="Minimum sparse score")
    min_fuzzy_score: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum fuzzy score")

    # RRF configuration
    rrf_k: int = Field(default=60, ge=1, le=1000, description="RRF k parameter")

    # Preference boosting configuration (Task 34.4)
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for preference-based result boosting"
    )
    apply_preference_boost: bool = Field(
        default=True,
        description="Whether to apply user preference boosting (requires user_id)"
    )
    preference_boost_factor: float = Field(
        default=0.2,
        ge=0.0,
        le=0.5,
        description="Maximum preference boost factor (0.0-0.5)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "California insurance policy requirements",
                "method": "hybrid",
                "top_k": 10,
                "dense_weight": 0.5,
                "sparse_weight": 0.3,
                "fuzzy_weight": 0.2,
                "user_id": "user-123",
                "apply_preference_boost": True
            }
        }


class SearchResultModel(BaseModel):
    """Single search result"""
    chunk_id: str
    content: str
    score: float
    rank: int
    method: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    file_id: Optional[str] = None
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    fuzzy_score: Optional[float] = None
    rrf_score: Optional[float] = None


class HybridSearchResponse(BaseModel):
    """Response model for hybrid search"""
    success: bool
    query: str
    method: str
    results: List[SearchResultModel]
    total_results: int
    search_time_ms: float
    config: Dict[str, Any]


class SearchStatsResponse(BaseModel):
    """Response model for search statistics"""
    total_chunks: int
    chunks_with_tsv: int
    total_embeddings: int
    unique_namespaces: int
    avg_content_length: Optional[float] = None


class SearchHealthResponse(BaseModel):
    """Response model for search health check"""
    status: str
    services: Dict[str, str]
    stats: Optional[SearchStatsResponse] = None


class SearchMethodsResponse(BaseModel):
    """Response model for available search methods"""
    methods: List[Dict[str, str]]
    recommended: str
    default_config: Dict[str, Any]


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest):
    """
    Perform hybrid search combining multiple retrieval methods

    **Search Methods:**
    - `dense`: Vector similarity search using embeddings
    - `sparse`: BM25 full-text search using PostgreSQL ts_rank_cd
    - `fuzzy`: Trigram similarity search
    - `ilike`: Simple case-insensitive pattern matching
    - `hybrid`: All methods combined with RRF (Python-side)
    - `hybrid_rpc`: All methods combined with RRF (server-side, recommended)

    **Reciprocal Rank Fusion (RRF):**
    Combines results from multiple search methods using the formula:
    `score = Σ (weight_i / (k + rank_i))`

    This provides +40-60% improvement over vector-only search.
    """
    import time
    from app.services.hybrid_search_service import (
        get_hybrid_search_service,
        SearchMethod,
        HybridSearchConfig
    )

    start_time = time.time()

    try:
        # Validate weights sum to 1.0
        weight_sum = request.dense_weight + request.sparse_weight + request.fuzzy_weight
        if abs(weight_sum - 1.0) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Weights must sum to 1.0, got {weight_sum}"
            )

        # Create custom config
        config = HybridSearchConfig(
            dense_weight=request.dense_weight,
            sparse_weight=request.sparse_weight,
            fuzzy_weight=request.fuzzy_weight,
            top_k=request.top_k,
            min_dense_score=request.min_dense_score,
            min_sparse_score=request.min_sparse_score,
            min_fuzzy_score=request.min_fuzzy_score,
            rrf_k=request.rrf_k,
            use_rpc=request.method == SearchMethodEnum.HYBRID_RPC
        )

        # Get search service
        search_service = get_hybrid_search_service()

        # Map string method to enum
        method_map = {
            SearchMethodEnum.DENSE: SearchMethod.DENSE,
            SearchMethodEnum.SPARSE: SearchMethod.SPARSE,
            SearchMethodEnum.FUZZY: SearchMethod.FUZZY,
            SearchMethodEnum.ILIKE: SearchMethod.ILIKE,
            SearchMethodEnum.HYBRID: SearchMethod.HYBRID,
            SearchMethodEnum.HYBRID_RPC: SearchMethod.HYBRID_RPC,
        }
        search_method = method_map.get(request.method, SearchMethod.HYBRID)

        # Perform search
        results = await search_service.search(
            query=request.query,
            method=search_method,
            namespace=request.namespace,
            metadata_filter=request.metadata_filter,
            custom_config=config
        )

        # Apply preference-based boosting if user_id provided (Task 34.4)
        preference_boosted = False
        if request.user_id and request.apply_preference_boost:
            original_order = [r.chunk_id for r in results]
            results = await apply_preference_boost(
                results,
                request.user_id,
                request.preference_boost_factor
            )
            new_order = [r.chunk_id for r in results]
            preference_boosted = original_order != new_order

        search_time_ms = (time.time() - start_time) * 1000

        return HybridSearchResponse(
            success=True,
            query=request.query,
            method=request.method.value,
            results=[
                SearchResultModel(
                    chunk_id=r.chunk_id,
                    content=r.content,
                    score=r.score,
                    rank=r.rank,
                    method=r.method,
                    metadata=r.metadata,
                    file_id=r.file_id,
                    dense_score=r.dense_score,
                    sparse_score=r.sparse_score,
                    fuzzy_score=r.fuzzy_score,
                    rrf_score=r.rrf_score
                )
                for r in results
            ],
            total_results=len(results),
            search_time_ms=round(search_time_ms, 2),
            config={
                "dense_weight": request.dense_weight,
                "sparse_weight": request.sparse_weight,
                "fuzzy_weight": request.fuzzy_weight,
                "top_k": request.top_k,
                "rrf_k": request.rrf_k,
                "preference_boosting": {
                    "enabled": request.apply_preference_boost and request.user_id is not None,
                    "user_id": request.user_id,
                    "boost_factor": request.preference_boost_factor,
                    "results_reordered": preference_boosted
                }
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/dense", response_model=HybridSearchResponse)
async def dense_search(
    query: str = Query(..., min_length=1, max_length=1000),
    top_k: int = Query(default=10, ge=1, le=100),
    namespace: Optional[str] = Query(default=None),
    min_score: float = Query(default=0.5, ge=0.0, le=1.0)
):
    """
    Perform dense vector similarity search only

    Uses BGE-M3 embeddings with pgvector cosine similarity.
    """
    import time
    from app.services.hybrid_search_service import (
        get_hybrid_search_service,
        SearchMethod,
        HybridSearchConfig
    )

    start_time = time.time()

    try:
        config = HybridSearchConfig(
            top_k=top_k,
            min_dense_score=min_score
        )

        search_service = get_hybrid_search_service()
        results = await search_service.search(
            query=query,
            method=SearchMethod.DENSE,
            namespace=namespace,
            custom_config=config
        )

        search_time_ms = (time.time() - start_time) * 1000

        return HybridSearchResponse(
            success=True,
            query=query,
            method="dense",
            results=[
                SearchResultModel(
                    chunk_id=r.chunk_id,
                    content=r.content,
                    score=r.score,
                    rank=r.rank,
                    method=r.method,
                    metadata=r.metadata,
                    file_id=r.file_id,
                    dense_score=r.dense_score
                )
                for r in results
            ],
            total_results=len(results),
            search_time_ms=round(search_time_ms, 2),
            config={"top_k": top_k, "min_score": min_score}
        )

    except Exception as e:
        logger.error(f"Dense search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/sparse", response_model=HybridSearchResponse)
async def sparse_search(
    query: str = Query(..., min_length=1, max_length=1000),
    top_k: int = Query(default=10, ge=1, le=100),
    namespace: Optional[str] = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0)
):
    """
    Perform BM25 full-text search only

    Uses PostgreSQL ts_rank_cd for BM25-like scoring.
    """
    import time
    from app.services.hybrid_search_service import (
        get_hybrid_search_service,
        SearchMethod,
        HybridSearchConfig
    )

    start_time = time.time()

    try:
        config = HybridSearchConfig(
            top_k=top_k,
            sparse_top_k=top_k,
            min_sparse_score=min_score,
            use_rpc=True
        )

        search_service = get_hybrid_search_service()
        results = await search_service.search(
            query=query,
            method=SearchMethod.SPARSE,
            namespace=namespace,
            custom_config=config
        )

        search_time_ms = (time.time() - start_time) * 1000

        return HybridSearchResponse(
            success=True,
            query=query,
            method="sparse",
            results=[
                SearchResultModel(
                    chunk_id=r.chunk_id,
                    content=r.content,
                    score=r.score,
                    rank=r.rank,
                    method=r.method,
                    metadata=r.metadata,
                    file_id=r.file_id,
                    sparse_score=r.sparse_score
                )
                for r in results
            ],
            total_results=len(results),
            search_time_ms=round(search_time_ms, 2),
            config={"top_k": top_k, "min_score": min_score}
        )

    except Exception as e:
        logger.error(f"Sparse search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/fuzzy", response_model=HybridSearchResponse)
async def fuzzy_search(
    query: str = Query(..., min_length=1, max_length=1000),
    top_k: int = Query(default=10, ge=1, le=100),
    namespace: Optional[str] = Query(default=None),
    min_similarity: float = Query(default=0.3, ge=0.0, le=1.0)
):
    """
    Perform fuzzy trigram similarity search only

    Uses PostgreSQL pg_trgm extension for fuzzy matching.
    """
    import time
    from app.services.hybrid_search_service import (
        get_hybrid_search_service,
        SearchMethod,
        HybridSearchConfig
    )

    start_time = time.time()

    try:
        config = HybridSearchConfig(
            top_k=top_k,
            fuzzy_top_k=top_k,
            min_fuzzy_score=min_similarity,
            use_rpc=True
        )

        search_service = get_hybrid_search_service()
        results = await search_service.search(
            query=query,
            method=SearchMethod.FUZZY,
            namespace=namespace,
            custom_config=config
        )

        search_time_ms = (time.time() - start_time) * 1000

        return HybridSearchResponse(
            success=True,
            query=query,
            method="fuzzy",
            results=[
                SearchResultModel(
                    chunk_id=r.chunk_id,
                    content=r.content,
                    score=r.score,
                    rank=r.rank,
                    method=r.method,
                    metadata=r.metadata,
                    file_id=r.file_id,
                    fuzzy_score=r.fuzzy_score
                )
                for r in results
            ],
            total_results=len(results),
            search_time_ms=round(search_time_ms, 2),
            config={"top_k": top_k, "min_similarity": min_similarity}
        )

    except Exception as e:
        logger.error(f"Fuzzy search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/health", response_model=SearchHealthResponse)
async def search_health():
    """
    Health check for hybrid search service

    Returns service status and search statistics.
    """
    from app.services.hybrid_search_service import get_hybrid_search_service

    try:
        search_service = get_hybrid_search_service()
        stats = await search_service.get_search_stats()

        return SearchHealthResponse(
            status="healthy",
            services={
                "hybrid_search": "available",
                "embedding_service": "available",
                "vector_storage": "available",
                "full_text_search": "available",
                "fuzzy_search": "available"
            },
            stats=SearchStatsResponse(
                total_chunks=stats.get("total_chunks", 0),
                chunks_with_tsv=stats.get("chunks_with_tsv", 0),
                total_embeddings=stats.get("total_embeddings", 0),
                unique_namespaces=stats.get("unique_namespaces", 0),
                avg_content_length=stats.get("avg_content_length")
            )
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return SearchHealthResponse(
            status="degraded",
            services={
                "hybrid_search": f"error: {str(e)}"
            },
            stats=None
        )


@router.get("/methods", response_model=SearchMethodsResponse)
async def get_search_methods():
    """
    Get available search methods and their descriptions

    Returns list of search methods with recommendations.
    """
    return SearchMethodsResponse(
        methods=[
            {
                "name": "dense",
                "description": "Vector similarity search using BGE-M3 embeddings",
                "best_for": "Semantic similarity, meaning-based queries"
            },
            {
                "name": "sparse",
                "description": "BM25 full-text search using PostgreSQL ts_rank_cd",
                "best_for": "Exact keyword matching, technical terms"
            },
            {
                "name": "fuzzy",
                "description": "Trigram similarity search for fuzzy matching",
                "best_for": "Typo tolerance, approximate matching"
            },
            {
                "name": "ilike",
                "description": "Simple case-insensitive pattern matching",
                "best_for": "Known exact patterns, fast substring search"
            },
            {
                "name": "hybrid",
                "description": "Combined search with RRF fusion (Python-side)",
                "best_for": "General purpose, balanced results"
            },
            {
                "name": "hybrid_rpc",
                "description": "Combined search with RRF fusion (server-side)",
                "best_for": "Production use, best performance"
            }
        ],
        recommended="hybrid_rpc",
        default_config={
            "dense_weight": 0.5,
            "sparse_weight": 0.3,
            "fuzzy_weight": 0.2,
            "top_k": 10,
            "rrf_k": 60
        }
    )


@router.get("/stats", response_model=SearchStatsResponse)
async def get_search_stats():
    """
    Get search statistics

    Returns statistics about indexed content.
    """
    from app.services.hybrid_search_service import get_hybrid_search_service

    try:
        search_service = get_hybrid_search_service()
        stats = await search_service.get_search_stats()

        return SearchStatsResponse(
            total_chunks=stats.get("total_chunks", 0),
            chunks_with_tsv=stats.get("chunks_with_tsv", 0),
            total_embeddings=stats.get("total_embeddings", 0),
            unique_namespaces=stats.get("unique_namespaces", 0),
            avg_content_length=stats.get("avg_content_length")
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
