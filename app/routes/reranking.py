"""
Empire v7.3 - Reranking API Routes (Task 29)

REST API endpoints for reranking search results using:
- BGE-Reranker-v2 via Ollama (local, <200ms latency) - Primary
- Claude API (fallback)

Target: +15-25% precision improvement over raw retrieval
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.services.reranking_service import (
    RerankingService,
    RerankingConfig,
    RerankingProvider,
    RerankingResult,
    get_reranking_service
)
from app.services.hybrid_search_service import SearchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rerank", tags=["Reranking"])


# =============================================================================
# Pydantic Models
# =============================================================================

class DocumentToRerank(BaseModel):
    """Document to be reranked"""
    id: str = Field(..., description="Document/chunk ID")
    content: str = Field(..., description="Document content text")
    score: Optional[float] = Field(0.5, description="Original relevance score")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class RerankRequest(BaseModel):
    """Request to rerank documents"""
    query: str = Field(..., description="Search query to rank documents against")
    documents: List[DocumentToRerank] = Field(..., description="Documents to rerank")
    provider: Optional[str] = Field("ollama", description="Reranking provider: ollama (primary), claude (fallback)")
    model: Optional[str] = Field(None, description="Model name (provider-specific)")
    top_k: Optional[int] = Field(10, ge=1, le=100, description="Number of top results to return")
    score_threshold: Optional[float] = Field(0.3, ge=0.0, le=1.0, description="Minimum score threshold")


class RerankResponse(BaseModel):
    """Response from reranking operation"""
    success: bool
    query: str
    reranked_documents: List[Dict[str, Any]]
    metrics: Dict[str, Any]


class RerankHealthResponse(BaseModel):
    """Health check response"""
    status: str
    providers: Dict[str, bool]
    default_provider: str
    latency_target_ms: int


class RerankProvidersResponse(BaseModel):
    """Available reranking providers"""
    providers: List[Dict[str, Any]]
    default: str
    recommendation: str


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    """
    Rerank documents by relevance to a query

    Uses BGE-Reranker-v2 (Ollama) by default for <200ms local latency.
    Claude API available as fallback.

    **Example:**
    ```json
    {
        "query": "What are California insurance requirements?",
        "documents": [
            {"id": "doc1", "content": "California requires auto insurance..."},
            {"id": "doc2", "content": "Insurance policies must cover..."},
            {"id": "doc3", "content": "Weather in California is sunny..."}
        ],
        "provider": "ollama",
        "top_k": 5
    }
    ```

    **Returns:**
    Reranked documents sorted by relevance with new scores.
    """
    try:
        # Parse provider
        provider_map = {
            "ollama": RerankingProvider.OLLAMA,
            "claude": RerankingProvider.CLAUDE
        }
        provider = provider_map.get(
            request.provider.lower() if request.provider else "ollama",
            RerankingProvider.OLLAMA
        )

        # Create config
        config = RerankingConfig(
            provider=provider,
            model=request.model or ("bge-reranker-v2-m3" if provider == RerankingProvider.OLLAMA else None),
            top_k=request.top_k,
            max_input_results=len(request.documents),
            score_threshold=request.score_threshold,
            enable_metrics=True
        )

        # Convert documents to SearchResult objects
        search_results = [
            SearchResult(
                chunk_id=doc.id,
                content=doc.content,
                score=doc.score or 0.5,
                rank=i + 1,
                method="input",
                metadata=doc.metadata or {}
            )
            for i, doc in enumerate(request.documents)
        ]

        # Create service and rerank
        service = RerankingService(config=config)
        try:
            result = await service.rerank(query=request.query, results=search_results)

            # Convert results to response format
            reranked_docs = []
            for i, r in enumerate(result.reranked_results, 1):
                reranked_docs.append({
                    "id": r.chunk_id,
                    "content": r.content[:500],  # Truncate for response
                    "score": r.score,
                    "rank": i,
                    "original_rank": r.rank,
                    "metadata": r.metadata
                })

            # Build metrics
            metrics = {
                "input_count": result.metrics.total_input_results if result.metrics else len(request.documents),
                "output_count": result.metrics.total_output_results if result.metrics else len(reranked_docs),
                "reranking_time_ms": result.metrics.reranking_time_ms if result.metrics else 0,
                "provider": result.metrics.provider.value if result.metrics and result.metrics.provider else provider.value,
                "model": result.metrics.model if result.metrics else config.model,
                "ndcg": result.metrics.ndcg if result.metrics else None
            }

            return RerankResponse(
                success=True,
                query=request.query,
                reranked_documents=reranked_docs,
                metrics=metrics
            )

        finally:
            await service.close()

    except Exception as e:
        logger.error(f"Reranking failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reranking failed: {str(e)}")


@router.post("/batch", response_model=Dict[str, Any])
async def rerank_batch(
    queries: List[str] = Body(..., description="List of queries"),
    documents: List[List[DocumentToRerank]] = Body(..., description="Documents for each query"),
    provider: str = Body("ollama", description="Reranking provider"),
    top_k: int = Body(10, ge=1, le=100, description="Results per query")
):
    """
    Batch rerank multiple queries

    Efficiently processes multiple query-document pairs in parallel.

    **Example:**
    ```json
    {
        "queries": ["query1", "query2"],
        "documents": [
            [{"id": "d1", "content": "..."}],
            [{"id": "d2", "content": "..."}]
        ],
        "provider": "ollama",
        "top_k": 5
    }
    ```
    """
    if len(queries) != len(documents):
        raise HTTPException(
            status_code=400,
            detail=f"Number of queries ({len(queries)}) must match document groups ({len(documents)})"
        )

    results = []
    total_time_ms = 0

    for query, docs in zip(queries, documents):
        try:
            response = await rerank_documents(RerankRequest(
                query=query,
                documents=docs,
                provider=provider,
                top_k=top_k
            ))
            results.append({
                "query": query,
                "success": True,
                "reranked_documents": response.reranked_documents,
                "metrics": response.metrics
            })
            total_time_ms += response.metrics.get("reranking_time_ms", 0)
        except Exception as e:
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })

    return {
        "success": True,
        "total_queries": len(queries),
        "successful_queries": sum(1 for r in results if r.get("success")),
        "total_time_ms": total_time_ms,
        "results": results
    }


@router.get("/health", response_model=RerankHealthResponse)
async def reranking_health():
    """
    Check reranking service health

    Verifies connectivity to reranking providers.
    """
    import httpx
    import os

    providers = {}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://localhost:11434/api/tags")
            ollama_available = response.status_code == 200
            # Check if bge-reranker model is available
            if ollama_available:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                ollama_available = any("bge-reranker" in m.lower() for m in models)
    except Exception:
        ollama_available = False
    providers["ollama"] = ollama_available

    # Check Claude (via API key presence)
    providers["claude"] = bool(os.getenv("ANTHROPIC_API_KEY"))

    # Determine default provider
    if ollama_available:
        default = "ollama"
    elif providers["claude"]:
        default = "claude"
    else:
        default = "none"

    status = "healthy" if any(providers.values()) else "unhealthy"

    return RerankHealthResponse(
        status=status,
        providers=providers,
        default_provider=default,
        latency_target_ms=200
    )


@router.get("/providers", response_model=RerankProvidersResponse)
async def list_providers():
    """
    List available reranking providers

    Returns provider details and recommendations.
    """
    providers = [
        {
            "id": "ollama",
            "name": "Ollama BGE-Reranker-v2",
            "model": "bge-reranker-v2-m3",
            "description": "Local reranking with BGE-Reranker-v2-M3 via Ollama",
            "latency": "<200ms",
            "cost": "Free (local)",
            "use_case": "Primary - development and production"
        },
        {
            "id": "claude",
            "name": "Claude Haiku",
            "model": "claude-haiku-4-5",
            "description": "Fast LLM-based reranking using Claude Haiku",
            "latency": "300-800ms",
            "cost": "$0.25/1M input, $1.25/1M output tokens",
            "use_case": "Fallback when Ollama unavailable"
        }
    ]

    return RerankProvidersResponse(
        providers=providers,
        default="ollama",
        recommendation="Use 'ollama' for best performance (<200ms latency). Claude Haiku available as fallback."
    )


@router.get("/stats")
async def reranking_stats():
    """
    Get reranking service statistics

    Returns usage statistics and performance metrics.
    """
    # In production, this would query actual metrics storage
    return {
        "total_reranking_requests": 0,
        "average_latency_ms": 0,
        "provider_usage": {
            "ollama": 0,
            "claude": 0
        },
        "average_ndcg": 0.0,
        "precision_improvement": "+15-25% (target)"
    }
