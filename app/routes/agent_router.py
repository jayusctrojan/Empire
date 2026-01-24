"""
Empire v7.3 - Agent Router API Routes (Task 17.5)
FastAPI endpoints for intelligent query routing between LangGraph, CrewAI, and Simple RAG

Author: Claude Code
Date: 2025-01-25
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from prometheus_client import Counter, Histogram, Gauge
import structlog
import time

from app.middleware.auth import require_admin
from app.services.agent_router_service import (
    AgentRouterService,
    get_agent_router_service,
)
from app.models.agent_router import (
    AgentType,
    QueryCategory,
    RoutingConfidence,
    AgentRouterRequest,
    AgentRouterResponse,
    BatchRouterRequest,
    BatchRouterResponse,
    RoutingFeedbackRequest,
    RoutingFeedbackResponse,
    RoutingAnalyticsResponse,
    RoutingMetrics,
    AgentPerformanceMetrics,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/router", tags=["Agent Router"])


# ==================== Prometheus Metrics ====================

ROUTING_REQUESTS_TOTAL = Counter(
    "agent_router_requests_total",
    "Total agent routing requests",
    ["agent_type", "confidence_level", "from_cache"]
)

ROUTING_LATENCY = Histogram(
    "agent_router_latency_seconds",
    "Agent routing latency in seconds",
    ["use_llm"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

ROUTING_BY_CATEGORY = Counter(
    "agent_router_by_category_total",
    "Routing requests by query category",
    ["category"]
)

ROUTING_ERRORS = Counter(
    "agent_router_errors_total",
    "Agent routing errors",
    ["error_type"]
)

BATCH_ROUTING_SIZE = Histogram(
    "agent_router_batch_size",
    "Batch routing request sizes",
    buckets=[1, 5, 10, 25, 50, 100]
)

# Task 19: Additional metrics for accuracy tracking
ROUTING_FEEDBACK_TOTAL = Counter(
    "agent_router_feedback_total",
    "Total routing feedback submissions",
    ["feedback_type", "agent_type"]
)

ROUTING_ACCURACY = Gauge(
    "agent_router_accuracy_rate",
    "Rolling routing accuracy based on feedback",
    ["agent_type"]
)

ROUTING_CACHE_HITS = Counter(
    "agent_router_cache_hits_total",
    "Total cache hits for routing decisions"
)

ROUTING_CACHE_MISSES = Counter(
    "agent_router_cache_misses_total",
    "Total cache misses for routing decisions"
)

ROUTING_CONFIDENCE_AVG = Gauge(
    "agent_router_confidence_avg",
    "Average confidence score for routing decisions",
    ["agent_type"]
)

ROUTING_PROCESSING_TIME_MS = Histogram(
    "agent_router_processing_time_ms",
    "Routing processing time in milliseconds",
    ["agent_type"],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000]
)


# ==================== Dependency Injection ====================

def get_router_service() -> AgentRouterService:
    """Dependency to get AgentRouterService instance."""
    return get_agent_router_service()


# ==================== Health & Info Endpoints ====================

@router.get(
    "/health",
    summary="Health Check",
    description="Check Agent Router service health and dependencies"
)
async def health_check(
    service: AgentRouterService = Depends(get_router_service)
):
    """Check if Agent Router service is available and healthy."""
    try:
        # Check if Supabase connection is available
        supabase_healthy = service.supabase is not None

        return {
            "status": "healthy",
            "service": "agent_router",
            "dependencies": {
                "supabase_cache": "healthy" if supabase_healthy else "unavailable",
                "llm": "healthy"  # LLM is lazily initialized
            },
            "config": {
                "cache_ttl_hours": service.cache_ttl_hours,
                "similarity_threshold": service.similarity_threshold,
                "semantic_cache_enabled": service.use_semantic_cache
            }
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "agent_router",
                "error": str(e)
            }
        )


@router.get(
    "/agents",
    summary="List Available Agents",
    description="Get list of available agent types and their capabilities"
)
async def list_agents():
    """List all available agent types with descriptions."""
    return {
        "agents": [
            {
                "type": AgentType.LANGGRAPH.value,
                "name": "LangGraph Adaptive",
                "description": "Adaptive query processing with iterative refinement",
                "capabilities": [
                    "External web search",
                    "Iterative quality evaluation",
                    "Adaptive branching",
                    "Research tasks"
                ],
                "best_for": [
                    "Current events and regulations",
                    "Market trends and news",
                    "Complex research requiring multiple sources",
                    "Queries needing verification"
                ]
            },
            {
                "type": AgentType.CREWAI.value,
                "name": "CrewAI Multi-Agent",
                "description": "Multi-agent collaboration for complex workflows",
                "capabilities": [
                    "Multi-agent coordination",
                    "Sequential processing",
                    "Role-based specialization",
                    "Entity extraction"
                ],
                "best_for": [
                    "Multi-document analysis",
                    "Cross-document comparison",
                    "Entity extraction from multiple sources",
                    "Complex sequential workflows"
                ]
            },
            {
                "type": AgentType.SIMPLE.value,
                "name": "Simple RAG",
                "description": "Direct retrieval from knowledge base",
                "capabilities": [
                    "Vector similarity search",
                    "Direct document retrieval",
                    "Conversational responses"
                ],
                "best_for": [
                    "Factual lookups",
                    "Policy questions",
                    "Conversational queries",
                    "Simple document retrieval"
                ]
            }
        ],
        "count": 3
    }


@router.get(
    "/categories",
    summary="List Query Categories",
    description="Get list of query categories used for classification"
)
async def list_categories():
    """List all query categories with descriptions."""
    return {
        "categories": [
            {
                "category": QueryCategory.DOCUMENT_LOOKUP.value,
                "description": "Direct factual lookup from documents",
                "typical_agent": AgentType.SIMPLE.value
            },
            {
                "category": QueryCategory.DOCUMENT_ANALYSIS.value,
                "description": "Multi-document analysis and comparison",
                "typical_agent": AgentType.CREWAI.value
            },
            {
                "category": QueryCategory.RESEARCH.value,
                "description": "Research requiring external data sources",
                "typical_agent": AgentType.LANGGRAPH.value
            },
            {
                "category": QueryCategory.CONVERSATIONAL.value,
                "description": "General chat and follow-up questions",
                "typical_agent": AgentType.SIMPLE.value
            },
            {
                "category": QueryCategory.MULTI_STEP.value,
                "description": "Complex queries requiring multiple steps",
                "typical_agent": AgentType.LANGGRAPH.value
            },
            {
                "category": QueryCategory.ENTITY_EXTRACTION.value,
                "description": "Extract structured data from documents",
                "typical_agent": AgentType.CREWAI.value
            }
        ],
        "count": 6
    }


# ==================== Routing Endpoints ====================

@router.post(
    "/route",
    response_model=AgentRouterResponse,
    summary="Route Query",
    description="Route a single query to the optimal agent"
)
async def route_query(
    request: AgentRouterRequest,
    use_llm: bool = False,
    service: AgentRouterService = Depends(get_router_service)
):
    """
    Route a query to the optimal agent.

    Args:
        request: Query routing request
        use_llm: Use LLM for classification (more accurate, slower)

    Returns:
        AgentRouterResponse with selected agent and metadata
    """
    start_time = time.time()

    try:
        response = await service.route_query(request, use_llm=use_llm)

        # Record metrics
        ROUTING_REQUESTS_TOTAL.labels(
            agent_type=response.selected_agent.value,
            confidence_level=response.confidence_level.value,
            from_cache=str(response.from_cache).lower()
        ).inc()

        ROUTING_LATENCY.labels(use_llm=str(use_llm).lower()).observe(
            time.time() - start_time
        )

        # Task 19: Track cache hits/misses
        if response.from_cache:
            ROUTING_CACHE_HITS.inc()
        else:
            ROUTING_CACHE_MISSES.inc()

        # Task 19: Track processing time by agent type
        ROUTING_PROCESSING_TIME_MS.labels(
            agent_type=response.selected_agent.value
        ).observe(response.routing_time_ms)

        if response.classification:
            ROUTING_BY_CATEGORY.labels(
                category=response.classification.category.value
            ).inc()

        logger.info(
            "Query routed successfully",
            request_id=response.request_id,
            agent=response.selected_agent.value,
            confidence=response.confidence,
            from_cache=response.from_cache,
            routing_time_ms=response.routing_time_ms
        )

        return response

    except Exception as e:
        ROUTING_ERRORS.labels(error_type=type(e).__name__).inc()
        logger.error("Query routing failed", error=str(e), query=request.query[:100])
        raise HTTPException(
            status_code=500,
            detail=f"Query routing failed: {str(e)}"
        )


@router.post(
    "/route/batch",
    response_model=BatchRouterResponse,
    summary="Route Multiple Queries",
    description="Route multiple queries in batch"
)
async def route_batch(
    request: BatchRouterRequest,
    service: AgentRouterService = Depends(get_router_service)
):
    """
    Route multiple queries in batch.

    Args:
        request: Batch routing request with list of queries

    Returns:
        BatchRouterResponse with results for all queries
    """
    try:
        # Record batch size
        BATCH_ROUTING_SIZE.observe(len(request.queries))

        response = await service.route_batch(
            queries=request.queries,
            user_id=request.user_id,
            context=request.context
        )

        # Record metrics for each result
        for result in response.results:
            ROUTING_REQUESTS_TOTAL.labels(
                agent_type=result.selected_agent.value,
                confidence_level=result.confidence_level.value,
                from_cache=str(result.from_cache).lower()
            ).inc()

            if result.classification:
                ROUTING_BY_CATEGORY.labels(
                    category=result.classification.category.value
                ).inc()

        logger.info(
            "Batch routing completed",
            total_queries=response.total_queries,
            cache_hits=response.cache_hits,
            processing_time_ms=response.processing_time_ms
        )

        return response

    except Exception as e:
        ROUTING_ERRORS.labels(error_type=type(e).__name__).inc()
        logger.error("Batch routing failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Batch routing failed: {str(e)}"
        )


@router.post(
    "/classify",
    summary="Classify Query Only",
    description="Classify a query without routing (for debugging/analysis)"
)
async def classify_query(
    query: str,
    service: AgentRouterService = Depends(get_router_service)
):
    """
    Classify a query and return classification details.

    This endpoint only performs classification without full routing,
    useful for debugging and understanding classification behavior.
    """
    try:
        category, features, complexity = service.classify_query_rules(query)

        return {
            "query": query,
            "category": category.value,
            "features_detected": features,
            "complexity": complexity,
            "suggested_agent": service._select_agent(category, features, complexity)[0].value
        }

    except Exception as e:
        logger.error("Query classification failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


# ==================== Feedback Endpoints ====================

@router.post(
    "/feedback",
    response_model=RoutingFeedbackResponse,
    summary="Submit Routing Feedback",
    description="Submit feedback on a routing decision"
)
async def submit_feedback(
    request: RoutingFeedbackRequest,
    service: AgentRouterService = Depends(get_router_service)
):
    """
    Submit feedback on a routing decision.

    This helps improve routing accuracy over time.
    """
    try:
        if not service.supabase:
            return RoutingFeedbackResponse(
                success=False,
                message="Database not available for feedback storage"
            )

        # Update the routing decision with feedback
        feedback_data = {
            "user_feedback": request.feedback,
            "feedback_comment": request.comment,
        }

        if request.correct_agent:
            feedback_data["correct_agent"] = request.correct_agent.value

        result = service.supabase.table("routing_decision_history").update(
            feedback_data
        ).eq("request_id", request.request_id).execute()

        if result.data:
            # Task 19: Track feedback metrics
            agent_type = result.data[0].get("selected_agent", "unknown")
            ROUTING_FEEDBACK_TOTAL.labels(
                feedback_type=request.feedback,
                agent_type=agent_type
            ).inc()

            logger.info(
                "Feedback recorded",
                request_id=request.request_id,
                feedback=request.feedback,
                agent_type=agent_type
            )
            return RoutingFeedbackResponse(
                success=True,
                message="Feedback recorded successfully",
                feedback_id=result.data[0].get("id")
            )
        else:
            return RoutingFeedbackResponse(
                success=False,
                message=f"No routing decision found for request_id: {request.request_id}"
            )

    except Exception as e:
        logger.error("Feedback submission failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Feedback submission failed: {str(e)}"
        )


# ==================== Analytics Endpoints ====================

@router.get(
    "/analytics",
    response_model=RoutingAnalyticsResponse,
    summary="Get Routing Analytics",
    description="Get aggregated routing analytics and metrics"
)
async def get_analytics(
    time_period: str = "24h",
    service: AgentRouterService = Depends(get_router_service)
):
    """
    Get routing analytics for a specified time period.

    Args:
        time_period: Time period for analytics (1h, 24h, 7d, 30d)
    """
    try:
        if not service.supabase:
            # Return mock data if database not available
            return RoutingAnalyticsResponse(
                metrics=RoutingMetrics(
                    time_period=time_period,
                    total_requests=0,
                    cache_hit_rate=0.0,
                    avg_routing_time_ms=0.0
                ),
                agent_performance=[],
                top_queries=[],
                recent_fallbacks=[]
            )

        # Calculate time range
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if time_period == "1h":
            start_time = now - timedelta(hours=1)
        elif time_period == "24h":
            start_time = now - timedelta(hours=24)
        elif time_period == "7d":
            start_time = now - timedelta(days=7)
        elif time_period == "30d":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=24)

        # Query routing decision history
        result = service.supabase.table("routing_decision_history").select(
            "*"
        ).gte(
            "created_at", start_time.isoformat()
        ).execute()

        decisions = result.data or []

        # Calculate metrics
        total_requests = len(decisions)
        cache_hits = sum(1 for d in decisions if d.get("cache_entry_id"))
        cache_hit_rate = cache_hits / total_requests if total_requests > 0 else 0.0

        # Agent distribution
        agent_counts = {"langgraph": 0, "crewai": 0, "simple": 0}
        confidence_counts = {"high": 0, "medium": 0, "low": 0}
        total_routing_time = 0

        for decision in decisions:
            agent = decision.get("selected_agent", "simple")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

            conf_level = decision.get("confidence_level", "medium")
            confidence_counts[conf_level] = confidence_counts.get(conf_level, 0) + 1

        avg_routing_time_ms = total_routing_time / total_requests if total_requests > 0 else 0.0

        # Calculate feedback stats
        positive_feedback = sum(1 for d in decisions if d.get("user_feedback") == "positive")
        negative_feedback = sum(1 for d in decisions if d.get("user_feedback") == "negative")
        total_feedback = positive_feedback + negative_feedback
        positive_rate = positive_feedback / total_feedback if total_feedback > 0 else None

        metrics = RoutingMetrics(
            time_period=time_period,
            total_requests=total_requests,
            cache_hit_rate=cache_hit_rate,
            avg_routing_time_ms=avg_routing_time_ms,
            langgraph_count=agent_counts.get("langgraph", 0),
            crewai_count=agent_counts.get("crewai", 0),
            simple_count=agent_counts.get("simple", 0),
            high_confidence_count=confidence_counts.get("high", 0),
            medium_confidence_count=confidence_counts.get("medium", 0),
            low_confidence_count=confidence_counts.get("low", 0),
            positive_feedback_rate=positive_rate
        )

        # Agent performance breakdown
        agent_performance = []
        for agent_type in [AgentType.LANGGRAPH, AgentType.CREWAI, AgentType.SIMPLE]:
            agent_decisions = [d for d in decisions if d.get("selected_agent") == agent_type.value]
            if agent_decisions:
                agent_positive = sum(1 for d in agent_decisions if d.get("user_feedback") == "positive")
                agent_total_feedback = sum(1 for d in agent_decisions if d.get("user_feedback"))
                agent_conf = sum(d.get("confidence", 0) for d in agent_decisions) / len(agent_decisions)

                agent_performance.append(AgentPerformanceMetrics(
                    agent_type=agent_type,
                    total_requests=len(agent_decisions),
                    avg_processing_time_ms=0.0,  # Would need to track this separately
                    success_rate=1.0,  # Placeholder
                    avg_confidence=agent_conf,
                    positive_feedback_rate=agent_positive / agent_total_feedback if agent_total_feedback > 0 else None
                ))

        return RoutingAnalyticsResponse(
            metrics=metrics,
            agent_performance=agent_performance,
            top_queries=[],  # Would need query frequency tracking
            recent_fallbacks=[]  # Would need fallback tracking
        )

    except Exception as e:
        logger.error("Analytics retrieval failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Analytics retrieval failed: {str(e)}"
        )


@router.get(
    "/analytics/cache",
    summary="Get Cache Analytics",
    description="Get cache performance analytics"
)
async def get_cache_analytics(
    service: AgentRouterService = Depends(get_router_service)
):
    """Get cache hit/miss statistics and performance metrics."""
    try:
        if not service.supabase:
            return {
                "status": "database_unavailable",
                "cache_enabled": service.use_semantic_cache,
                "cache_ttl_hours": service.cache_ttl_hours
            }

        # Query cache statistics
        result = service.supabase.table("agent_router_cache").select(
            "id", "hit_count", "created_at", "last_hit_at", "is_active"
        ).eq("is_active", True).execute()

        entries = result.data or []
        total_entries = len(entries)
        total_hits = sum(e.get("hit_count", 0) for e in entries)
        avg_hits = total_hits / total_entries if total_entries > 0 else 0

        return {
            "cache_enabled": service.use_semantic_cache,
            "cache_ttl_hours": service.cache_ttl_hours,
            "similarity_threshold": service.similarity_threshold,
            "statistics": {
                "total_entries": total_entries,
                "total_hits": total_hits,
                "avg_hits_per_entry": round(avg_hits, 2)
            }
        }

    except Exception as e:
        logger.error("Cache analytics failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Cache analytics failed: {str(e)}"
        )


# ==================== Admin Endpoints ====================

@router.delete(
    "/cache/clear",
    summary="Clear Routing Cache",
    description="Clear all or expired cache entries (admin only)"
)
async def clear_cache(
    expired_only: bool = True,
    service: AgentRouterService = Depends(get_router_service),
    admin_user: dict = Depends(require_admin)
):
    """
    Clear routing cache entries.

    Args:
        expired_only: If True, only clear expired entries. If False, clear all.
    """
    try:
        if not service.supabase:
            return {"success": False, "message": "Database not available"}

        if expired_only:
            # Call cleanup function
            service.supabase.rpc("cleanup_expired_router_cache").execute()
            message = "Expired cache entries cleared"
        else:
            # Delete all cache entries
            service.supabase.table("agent_router_cache").delete().neq(
                "id", "00000000-0000-0000-0000-000000000000"  # Delete all
            ).execute()
            message = "All cache entries cleared"

        logger.info(message, expired_only=expired_only)

        return {
            "success": True,
            "message": message,
            "expired_only": expired_only
        }

    except Exception as e:
        logger.error("Cache clear failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Cache clear failed: {str(e)}"
        )
