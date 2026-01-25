"""
Monitoring and metrics endpoints for Empire v7.2
Provides Prometheus metrics and JSON endpoints for Grafana dashboards
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime

from app.services.metrics_service import MetricsService
from app.core.connections import get_supabase
from supabase import Client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# Prometheus metrics
document_total = Gauge("empire_documents_total", "Total number of documents")
document_recent = Gauge("empire_documents_recent_24h", "Documents uploaded in last 24 hours")
storage_total_gb = Gauge("empire_storage_total_gb", "Total storage usage in GB")

query_total = Counter("empire_queries_total", "Total number of queries")
query_latency = Histogram("empire_query_latency_seconds", "Query latency in seconds")
cache_hit_rate = Gauge("empire_cache_hit_rate_percent", "Cache hit rate percentage")

active_users = Gauge("empire_active_users", "Number of active users")
active_sessions = Gauge("empire_active_sessions", "Number of active sessions")
user_actions_total = Counter("empire_user_actions_total", "Total user actions")

api_requests_total = Counter("empire_api_requests_total", "Total API requests", ["endpoint"])


def get_metrics_service(supabase: Client = Depends(get_supabase)) -> MetricsService:
    """Dependency to get MetricsService instance"""
    return MetricsService(supabase)


@router.get("/health", summary="Health Check", description="Check monitoring service health")
async def health_check():
    """Health check endpoint for monitoring service"""
    return {
        "status": "healthy",
        "service": "monitoring",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus Metrics",
    description="Prometheus-compatible metrics endpoint"
)
async def prometheus_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """
    Prometheus metrics endpoint

    Returns metrics in Prometheus text format for scraping
    """
    try:
        # Collect current metrics
        all_metrics = await metrics_service.get_all_metrics(time_range_hours=24)

        # Update Prometheus gauges/counters
        document_total.set(all_metrics["documents"]["total_documents"])
        document_recent.set(all_metrics["documents"]["recent_documents"])
        storage_total_gb.set(all_metrics["storage"]["total"]["size_gb"])

        cache_hit_rate.set(all_metrics["queries"]["cache_hit_rate_percent"])

        active_users.set(all_metrics["users"]["active_users"])
        active_sessions.set(all_metrics["users"]["active_sessions"])

        # Generate Prometheus format
        return PlainTextResponse(
            content=generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST
        )

    except Exception as e:
        logger.error("Failed to generate Prometheus metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate metrics: {str(e)}")


@router.get(
    "/metrics/json",
    summary="JSON Metrics",
    description="Get all metrics in JSON format for Grafana"
)
async def json_metrics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours (1-168)"),
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """
    Get all metrics in JSON format

    Suitable for Grafana JSON data source or direct consumption

    Args:
        time_range_hours: Time range for metrics (1-168 hours, default: 24)

    Returns:
        JSON with all metric categories
    """
    try:
        metrics = await metrics_service.get_all_metrics(time_range_hours=time_range_hours)
        return JSONResponse(content=metrics)

    except Exception as e:
        logger.error("Failed to get JSON metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get(
    "/metrics/documents",
    summary="Document Metrics",
    description="Get document statistics"
)
async def document_metrics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """Get document-specific metrics"""
    try:
        metrics = await metrics_service.get_document_stats(time_range_hours=time_range_hours)
        return JSONResponse(content={
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "metrics": metrics
        })
    except Exception as e:
        logger.error("Failed to get document metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get document metrics: {str(e)}")


@router.get(
    "/metrics/queries",
    summary="Query Metrics",
    description="Get query performance metrics"
)
async def query_metrics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """Get query-specific metrics"""
    try:
        metrics = await metrics_service.get_query_metrics(time_range_hours=time_range_hours)
        return JSONResponse(content={
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "metrics": metrics
        })
    except Exception as e:
        logger.error("Failed to get query metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get query metrics: {str(e)}")


@router.get(
    "/metrics/users",
    summary="User Activity Metrics",
    description="Get user activity metrics"
)
async def user_metrics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """Get user activity metrics"""
    try:
        metrics = await metrics_service.get_user_activity_metrics(time_range_hours=time_range_hours)
        return JSONResponse(content={
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "metrics": metrics
        })
    except Exception as e:
        logger.error("Failed to get user metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get user metrics: {str(e)}")


@router.get(
    "/metrics/storage",
    summary="Storage Usage Metrics",
    description="Get storage usage across all components"
)
async def storage_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """Get storage usage metrics"""
    try:
        metrics = await metrics_service.get_storage_usage()
        return JSONResponse(content={
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics
        })
    except Exception as e:
        logger.error("Failed to get storage metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get storage metrics: {str(e)}")


@router.get(
    "/metrics/api",
    summary="API Endpoint Metrics",
    description="Get API endpoint usage statistics"
)
async def api_metrics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """Get API endpoint usage metrics"""
    try:
        metrics = await metrics_service.get_api_endpoint_metrics(time_range_hours=time_range_hours)
        return JSONResponse(content={
            "timestamp": datetime.utcnow().isoformat(),
            "time_range_hours": time_range_hours,
            "metrics": metrics
        })
    except Exception as e:
        logger.error("Failed to get API metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get API metrics: {str(e)}")
