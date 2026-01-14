"""
RAG Metrics Dashboard API Routes - Task 149

Provides REST endpoints for the RAG quality metrics dashboard.
Supports real-time monitoring, trend analysis, and drill-down capabilities.

Endpoints:
- GET /api/rag-metrics/dashboard - Complete dashboard data
- GET /api/rag-metrics/summary - RAGAS summary metrics
- GET /api/rag-metrics/trends/{metric} - Trend data for a metric
- GET /api/rag-metrics/agents - Agent performance breakdown
- GET /api/rag-metrics/queries - Query type breakdown
- GET /api/rag-metrics/opportunities - Optimization opportunities
- GET /api/rag-metrics/health - Service health check
"""

import structlog
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.rag_metrics_service import (
    RAGMetricsService,
    TimeRange,
    RAGASSummary,
    MetricTrend,
    AgentPerformanceSummary,
    QueryTypeBreakdown,
    OptimizationOpportunity,
    DashboardData,
    get_rag_metrics_service
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/rag-metrics", tags=["RAG Metrics"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str = "rag-metrics"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    database_connected: bool = False


class SummaryResponse(BaseModel):
    """RAGAS summary response."""
    summary: RAGASSummary
    time_range: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrendResponse(BaseModel):
    """Trend data response."""
    trend: MetricTrend
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentsResponse(BaseModel):
    """Agent performance response."""
    agents: List[AgentPerformanceSummary]
    total_agents: int
    time_range: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueriesResponse(BaseModel):
    """Query breakdown response."""
    queries: List[QueryTypeBreakdown]
    total_query_types: int
    time_range: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpportunitiesResponse(BaseModel):
    """Optimization opportunities response."""
    opportunities: List[OptimizationOpportunity]
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _parse_time_range(time_range_str: str) -> TimeRange:
    """Parse time range string to enum."""
    mapping = {
        "1h": TimeRange.LAST_HOUR,
        "24h": TimeRange.LAST_24_HOURS,
        "7d": TimeRange.LAST_7_DAYS,
        "30d": TimeRange.LAST_30_DAYS,
    }
    return mapping.get(time_range_str, TimeRange.LAST_24_HOURS)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check RAG metrics service health.

    Returns service status and database connectivity.
    """
    metrics_service = get_rag_metrics_service()

    return HealthResponse(
        status="healthy",
        database_connected=metrics_service.supabase is not None
    )


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard(
    time_range: str = Query(
        default="24h",
        description="Time range: 1h, 24h, 7d, or 30d"
    )
):
    """
    Get complete dashboard data in a single request.

    Optimized endpoint that returns all dashboard components:
    - RAGAS summary metrics
    - Metric trends
    - Agent performance
    - Query type breakdown
    - Optimization opportunities

    Performance target: <2 seconds for 30-day data.
    """
    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        dashboard = await metrics_service.get_dashboard_data(tr)

        logger.info(
            "dashboard_data_served",
            time_range=time_range,
            freshness_ms=dashboard.data_freshness_seconds * 1000
        )

        return dashboard

    except Exception as e:
        logger.error("dashboard_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to load dashboard: {str(e)}")


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    time_range: str = Query(default="24h", description="Time range: 1h, 24h, 7d, or 30d"),
    query_type: Optional[str] = Query(default=None, description="Filter by query type"),
    agent_id: Optional[str] = Query(default=None, description="Filter by agent ID")
):
    """
    Get RAGAS metrics summary.

    Returns aggregated scores for:
    - Context Relevance
    - Answer Relevance
    - Faithfulness
    - Coverage
    - Overall Score
    """
    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        summary = await metrics_service.get_ragas_summary(
            time_range=tr,
            query_type=query_type,
            agent_id=agent_id
        )

        return SummaryResponse(summary=summary, time_range=time_range)

    except Exception as e:
        logger.error("summary_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")


@router.get("/trends/{metric}", response_model=TrendResponse)
async def get_trend(
    metric: str,
    time_range: str = Query(default="7d", description="Time range: 1h, 24h, 7d, or 30d"),
    granularity: str = Query(default="hour", description="Granularity: hour or day")
):
    """
    Get trend data for a specific metric.

    Available metrics:
    - context_relevance
    - answer_relevance
    - faithfulness
    - coverage
    - overall_score

    Returns time-series data points with trend direction.
    """
    valid_metrics = [
        "context_relevance",
        "answer_relevance",
        "faithfulness",
        "coverage",
        "overall_score"
    ]

    if metric not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric. Choose from: {', '.join(valid_metrics)}"
        )

    if granularity not in ["hour", "day"]:
        raise HTTPException(
            status_code=400,
            detail="Granularity must be 'hour' or 'day'"
        )

    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        trend = await metrics_service.get_metric_trend(
            metric_name=metric,
            time_range=tr,
            granularity=granularity
        )

        return TrendResponse(trend=trend)

    except Exception as e:
        logger.error("trend_error", metric=metric, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get trend: {str(e)}")


@router.get("/agents", response_model=AgentsResponse)
async def get_agents(
    time_range: str = Query(default="7d", description="Time range: 1h, 24h, 7d, or 30d")
):
    """
    Get agent performance breakdown.

    Returns for each agent:
    - Total executions
    - Success rate
    - Average quality score
    - Average latency
    - Task types handled
    """
    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        agents = await metrics_service.get_agent_performance(tr)

        return AgentsResponse(
            agents=agents,
            total_agents=len(agents),
            time_range=time_range
        )

    except Exception as e:
        logger.error("agents_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get agents: {str(e)}")


@router.get("/queries", response_model=QueriesResponse)
async def get_queries(
    time_range: str = Query(default="7d", description="Time range: 1h, 24h, 7d, or 30d")
):
    """
    Get query type breakdown.

    Returns for each query type:
    - Query count
    - Average quality score
    - Average latency
    - Success rate
    """
    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        queries = await metrics_service.get_query_breakdown(tr)

        return QueriesResponse(
            queries=queries,
            total_query_types=len(queries),
            time_range=time_range
        )

    except Exception as e:
        logger.error("queries_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get queries: {str(e)}")


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def get_opportunities(
    time_range: str = Query(default="7d", description="Time range: 1h, 24h, 7d, or 30d")
):
    """
    Get optimization opportunities.

    Analyzes current metrics and identifies areas for improvement:
    - Low-performing metrics
    - Underperforming agents
    - Slow query types
    - Potential improvements
    """
    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        # Get required data for analysis
        summary = await metrics_service.get_ragas_summary(tr)
        agents = await metrics_service.get_agent_performance(tr)
        queries = await metrics_service.get_query_breakdown(tr)

        opportunities = await metrics_service.get_optimization_opportunities(
            summary, agents, queries
        )

        return OpportunitiesResponse(
            opportunities=opportunities,
            high_priority_count=sum(1 for o in opportunities if o.severity == "high"),
            medium_priority_count=sum(1 for o in opportunities if o.severity == "medium"),
            low_priority_count=sum(1 for o in opportunities if o.severity == "low")
        )

    except Exception as e:
        logger.error("opportunities_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get opportunities: {str(e)}")


@router.get("/export")
async def export_metrics(
    time_range: str = Query(default="30d", description="Time range: 1h, 24h, 7d, or 30d"),
    format: str = Query(default="json", description="Export format: json or csv")
):
    """
    Export metrics data for external analysis.

    Returns raw metrics data in JSON or CSV format.
    """
    if format not in ["json", "csv"]:
        raise HTTPException(
            status_code=400,
            detail="Format must be 'json' or 'csv'"
        )

    try:
        metrics_service = get_rag_metrics_service()
        tr = _parse_time_range(time_range)

        dashboard = await metrics_service.get_dashboard_data(tr)

        if format == "json":
            return dashboard.model_dump()
        else:
            # CSV export - simplified for summary data
            import io
            import csv

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                "metric", "value", "sample_count", "time_range"
            ])

            # Summary data
            summary = dashboard.summary
            writer.writerow(["context_relevance", summary.context_relevance, summary.sample_count, time_range])
            writer.writerow(["answer_relevance", summary.answer_relevance, summary.sample_count, time_range])
            writer.writerow(["faithfulness", summary.faithfulness, summary.sample_count, time_range])
            writer.writerow(["coverage", summary.coverage, summary.sample_count, time_range])
            writer.writerow(["overall_score", summary.overall_score, summary.sample_count, time_range])

            from fastapi.responses import StreamingResponse
            output.seek(0)

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=rag_metrics_{time_range}.csv"}
            )

    except Exception as e:
        logger.error("export_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to export: {str(e)}")
