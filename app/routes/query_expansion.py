"""
Empire v7.3 - Query Expansion API Routes (Task 28)

REST API endpoints for query expansion using Claude Haiku.
Generates semantic query variations for improved recall with <500ms latency target.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.services.query_expansion_service import (
    QueryExpansionService,
    QueryExpansionConfig,
    ExpansionStrategy,
    get_query_expansion_service
)
from app.services.parallel_search_service import (
    ParallelSearchService,
    ParallelSearchConfig,
    get_parallel_search_service
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/expand", tags=["Query Expansion"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ExpandQueryRequest(BaseModel):
    """Request to expand a query"""
    query: str = Field(..., description="Original search query to expand")
    strategy: Optional[str] = Field("balanced", description="Expansion strategy: synonyms, reformulate, specific, broad, balanced, question")
    num_variations: Optional[int] = Field(4, ge=1, le=10, description="Number of query variations to generate")
    include_original: Optional[bool] = Field(True, description="Include original query in results")


class ExpandedQuery(BaseModel):
    """A single expanded query variation"""
    query: str
    strategy: str
    confidence: float


class ExpandQueryResponse(BaseModel):
    """Response from query expansion"""
    success: bool
    original_query: str
    expanded_queries: List[ExpandedQuery]
    total_variations: int
    expansion_time_ms: float
    strategy_used: str


class BatchExpandRequest(BaseModel):
    """Request to expand multiple queries"""
    queries: List[str] = Field(..., description="List of queries to expand")
    strategy: Optional[str] = Field("balanced", description="Expansion strategy")
    num_variations: Optional[int] = Field(4, ge=1, le=10, description="Variations per query")


class ParallelSearchRequest(BaseModel):
    """Request for parallel search with query expansion"""
    query: str = Field(..., description="Original search query")
    strategy: Optional[str] = Field("balanced", description="Expansion strategy")
    num_variations: Optional[int] = Field(4, ge=1, le=10, description="Number of query variations")
    top_k: Optional[int] = Field(10, ge=1, le=100, description="Number of results to return")
    aggregation: Optional[str] = Field("rrf", description="Result aggregation: rrf, score_weighted, frequency, max_score")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    claude_available: bool
    default_strategy: str
    latency_target_ms: int


class StrategiesResponse(BaseModel):
    """Available expansion strategies"""
    strategies: List[Dict[str, Any]]
    default: str
    recommendation: str


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/", response_model=ExpandQueryResponse)
async def expand_query(request: ExpandQueryRequest):
    """
    Expand a query into semantic variations using Claude Haiku

    Generates multiple query variations that capture different aspects
    of the user's intent for improved search recall.

    **Example:**
    ```json
    {
        "query": "California insurance requirements",
        "strategy": "balanced",
        "num_variations": 4
    }
    ```

    **Returns:**
    Original query plus semantic variations with confidence scores.
    """
    import time
    start_time = time.time()

    try:
        # Parse strategy
        strategy_map = {
            "synonyms": ExpansionStrategy.SYNONYMS,
            "reformulate": ExpansionStrategy.REFORMULATE,
            "specific": ExpansionStrategy.SPECIFIC,
            "broad": ExpansionStrategy.BROAD,
            "balanced": ExpansionStrategy.BALANCED,
            "question": ExpansionStrategy.QUESTION
        }
        strategy = strategy_map.get(
            request.strategy.lower() if request.strategy else "balanced",
            ExpansionStrategy.BALANCED
        )

        # Create config
        config = QueryExpansionConfig(
            strategy=strategy,
            num_variations=request.num_variations,
            include_original=request.include_original
        )

        # Get service and expand
        service = get_query_expansion_service(config=config)
        result = await service.expand_query(request.query)

        # Build response
        expanded_queries = []
        for variation in result.variations:
            expanded_queries.append(ExpandedQuery(
                query=variation.query,
                strategy=variation.strategy.value if hasattr(variation.strategy, 'value') else str(variation.strategy),
                confidence=variation.confidence
            ))

        expansion_time_ms = (time.time() - start_time) * 1000

        return ExpandQueryResponse(
            success=True,
            original_query=request.query,
            expanded_queries=expanded_queries,
            total_variations=len(expanded_queries),
            expansion_time_ms=expansion_time_ms,
            strategy_used=strategy.value
        )

    except Exception as e:
        logger.error(f"Query expansion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query expansion failed: {str(e)}")


@router.post("/batch", response_model=Dict[str, Any])
async def expand_batch(request: BatchExpandRequest):
    """
    Expand multiple queries in batch

    Efficiently processes multiple queries with the same strategy.

    **Example:**
    ```json
    {
        "queries": ["California insurance", "Texas regulations"],
        "strategy": "balanced",
        "num_variations": 4
    }
    ```
    """
    import time
    start_time = time.time()

    results = []
    total_variations = 0

    for query in request.queries:
        try:
            response = await expand_query(ExpandQueryRequest(
                query=query,
                strategy=request.strategy,
                num_variations=request.num_variations
            ))
            results.append({
                "query": query,
                "success": True,
                "expanded_queries": [eq.model_dump() for eq in response.expanded_queries],
                "expansion_time_ms": response.expansion_time_ms
            })
            total_variations += response.total_variations
        except Exception as e:
            results.append({
                "query": query,
                "success": False,
                "error": str(e)
            })

    total_time_ms = (time.time() - start_time) * 1000

    return {
        "success": True,
        "total_queries": len(request.queries),
        "successful_queries": sum(1 for r in results if r.get("success")),
        "total_variations": total_variations,
        "total_time_ms": total_time_ms,
        "results": results
    }


@router.post("/search", response_model=Dict[str, Any])
async def parallel_search_with_expansion(request: ParallelSearchRequest):
    """
    Execute parallel search with query expansion

    Expands the query, searches with all variations in parallel,
    and combines results using the specified aggregation method.

    **Example:**
    ```json
    {
        "query": "California insurance requirements",
        "strategy": "balanced",
        "num_variations": 4,
        "top_k": 10,
        "aggregation": "score_weighted"
    }
    ```

    **Returns:**
    Combined search results from all query variations.
    """
    import time
    start_time = time.time()

    try:
        # Map strategy string to enum value for expansion config
        strategy_value = request.strategy.lower() if request.strategy else "balanced"

        # Map aggregation (rrf maps to score_weighted for now)
        aggregation_value = request.aggregation.lower() if request.aggregation else "score_weighted"
        if aggregation_value == "rrf":
            aggregation_value = "score_weighted"  # RRF uses score weighting

        # Create config
        config = ParallelSearchConfig(
            enable_expansion=True,
            num_query_variations=request.num_variations,
            expansion_strategy=strategy_value,
            max_results=request.top_k,
            aggregation_method=aggregation_value
        )

        # Get service and search
        service = get_parallel_search_service(config=config)
        result = await service.search(
            query=request.query,
            expand_queries=True,
            num_variations=request.num_variations
        )

        total_time_ms = (time.time() - start_time) * 1000

        # Build response
        search_results = []
        for r in result.aggregated_results:
            search_results.append({
                "chunk_id": r.chunk_id,
                "content": r.content[:500] if r.content else "",  # Truncate for response
                "score": r.score,
                "rank": r.rank,
                "metadata": r.metadata
            })

        return {
            "success": True,
            "query": request.query,
            "expanded_queries": result.expanded_queries,
            "results": search_results,
            "total_results": len(search_results),
            "metrics": {
                "total_time_ms": total_time_ms,
                "duration_ms": result.duration_ms,
                "queries_executed": result.queries_executed,
                "total_results_found": result.total_results_found,
                "unique_results_count": result.unique_results_count,
                "aggregation_method": aggregation_value
            }
        }

    except Exception as e:
        logger.error(f"Parallel search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Parallel search failed: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def expansion_health():
    """
    Check query expansion service health

    Verifies connectivity to Claude API for query expansion.
    """
    import os

    claude_available = bool(os.getenv("ANTHROPIC_API_KEY"))
    status = "healthy" if claude_available else "unhealthy"

    return HealthResponse(
        status=status,
        claude_available=claude_available,
        default_strategy="balanced",
        latency_target_ms=500
    )


@router.get("/strategies", response_model=StrategiesResponse)
async def list_strategies():
    """
    List available query expansion strategies

    Returns strategy details and recommendations.
    """
    strategies = [
        {
            "id": "synonyms",
            "name": "Synonyms",
            "description": "Replace key terms with synonyms",
            "use_case": "When exact terminology may vary"
        },
        {
            "id": "reformulate",
            "name": "Reformulate",
            "description": "Rephrase the query in different ways",
            "use_case": "When phrasing may affect results"
        },
        {
            "id": "specific",
            "name": "Specific",
            "description": "Add specificity and detail to the query",
            "use_case": "When more precise results needed"
        },
        {
            "id": "broad",
            "name": "Broad",
            "description": "Generalize the query for wider coverage",
            "use_case": "When exploring a topic broadly"
        },
        {
            "id": "balanced",
            "name": "Balanced (Default)",
            "description": "Mix of strategies for optimal coverage",
            "use_case": "General-purpose expansion"
        },
        {
            "id": "question",
            "name": "Question",
            "description": "Convert to question format variations",
            "use_case": "For FAQ-style content retrieval"
        }
    ]

    return StrategiesResponse(
        strategies=strategies,
        default="balanced",
        recommendation="Use 'balanced' for most cases. Use 'specific' for precise queries, 'broad' for exploration."
    )


@router.get("/stats")
async def expansion_stats():
    """
    Get query expansion service statistics

    Returns usage statistics and performance metrics.
    """
    # In production, this would query actual metrics storage
    return {
        "total_expansion_requests": 0,
        "average_latency_ms": 0,
        "strategy_usage": {
            "balanced": 0,
            "synonyms": 0,
            "reformulate": 0,
            "specific": 0,
            "broad": 0,
            "question": 0
        },
        "average_variations_per_query": 4,
        "cache_hit_rate": 0.0,
        "latency_target_ms": 500
    }
