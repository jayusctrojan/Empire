"""
Empire v7.3 - Enhanced Health Check Routes
Task 190: Implement Enhanced Health Checks

Provides:
- /api/health - Basic health check
- /api/health/liveness - Kubernetes liveness probe (lightweight)
- /api/health/readiness - Kubernetes readiness probe (checks critical deps)
- /api/health/deep - Deep health check for all dependencies
- /api/health/orchestrator - Service orchestrator status (comprehensive 23-service check)
"""

import os
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, Response, status, Request
import structlog

from app.core.health import (
    HealthStatus,
    DependencyType,
    DependencyCheck,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
    DeepHealthResponse,
    check_with_timeout,
    sync_check_with_timeout,
    aggregate_status,
    get_degraded_services,
    is_critical_healthy,
)
from app.core.connections import connection_manager, get_connection_manager

if TYPE_CHECKING:
    from app.core.service_orchestrator import ServiceOrchestrator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/health", tags=["Health"])

# Service start time for uptime calculation
_service_start_time: Optional[float] = None


def get_service_start_time() -> float:
    """Get or set the service start time"""
    global _service_start_time
    if _service_start_time is None:
        _service_start_time = time.time()
    return _service_start_time


# Initialize start time on module load
get_service_start_time()


# =============================================================================
# Critical Services Definition
# =============================================================================

# Services that MUST be healthy for the app to be considered ready
CRITICAL_SERVICES = ["supabase", "redis"]

# Default timeout for health checks (seconds)
DEFAULT_TIMEOUT = 5.0


# =============================================================================
# Helper Functions
# =============================================================================


async def check_supabase_health() -> DependencyCheck:
    """Check Supabase (PostgreSQL) health"""
    start_time = time.perf_counter()

    try:
        if connection_manager.supabase:
            # Simple query to verify connection
            result = connection_manager.supabase.table("documents").select("id").limit(1).execute()
            duration_ms = (time.perf_counter() - start_time) * 1000

            return DependencyCheck(
                name="supabase",
                status=HealthStatus.OK,
                type=DependencyType.DATABASE,
                message="PostgreSQL connection healthy",
                duration_ms=round(duration_ms, 2),
                details={"query": "documents.select(id).limit(1)"}
            )
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheck(
                name="supabase",
                status=HealthStatus.WARNING,
                type=DependencyType.DATABASE,
                message="Supabase not configured",
                duration_ms=round(duration_ms, 2)
            )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Supabase health check failed", error=str(e))
        return DependencyCheck(
            name="supabase",
            status=HealthStatus.ERROR,
            type=DependencyType.DATABASE,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


async def check_redis_health() -> DependencyCheck:
    """Check Redis health"""
    start_time = time.perf_counter()

    try:
        if connection_manager.redis:
            # Ping to verify connection
            connection_manager.redis.ping()
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Get Redis info for details
            info = connection_manager.redis.info("server")

            return DependencyCheck(
                name="redis",
                status=HealthStatus.OK,
                type=DependencyType.CACHE,
                message="Redis connection healthy",
                duration_ms=round(duration_ms, 2),
                details={
                    "redis_version": info.get("redis_version", "unknown"),
                    "uptime_in_seconds": info.get("uptime_in_seconds", 0)
                }
            )
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheck(
                name="redis",
                status=HealthStatus.WARNING,
                type=DependencyType.CACHE,
                message="Redis not configured",
                duration_ms=round(duration_ms, 2)
            )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Redis health check failed", error=str(e))
        return DependencyCheck(
            name="redis",
            status=HealthStatus.ERROR,
            type=DependencyType.CACHE,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


async def check_neo4j_health() -> DependencyCheck:
    """Check Neo4j health"""
    start_time = time.perf_counter()

    try:
        if connection_manager.neo4j_driver:
            # Verify connectivity
            connection_manager.neo4j_driver.verify_connectivity()
            duration_ms = (time.perf_counter() - start_time) * 1000

            return DependencyCheck(
                name="neo4j",
                status=HealthStatus.OK,
                type=DependencyType.GRAPH,
                message="Neo4j connection healthy",
                duration_ms=round(duration_ms, 2)
            )
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheck(
                name="neo4j",
                status=HealthStatus.WARNING,
                type=DependencyType.GRAPH,
                message="Neo4j not configured",
                duration_ms=round(duration_ms, 2)
            )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Neo4j health check failed", error=str(e))
        return DependencyCheck(
            name="neo4j",
            status=HealthStatus.ERROR,
            type=DependencyType.GRAPH,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


async def check_b2_health() -> DependencyCheck:
    """Check B2 storage health"""
    start_time = time.perf_counter()

    try:
        from app.services.b2_storage import get_b2_service

        b2_service = get_b2_service()
        b2_service.check_connection()

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Get bucket info for details
        bucket_info = b2_service.get_bucket_info()

        return DependencyCheck(
            name="b2_storage",
            status=HealthStatus.OK,
            type=DependencyType.STORAGE,
            message="B2 storage connection healthy",
            duration_ms=round(duration_ms, 2),
            details=bucket_info
        )
    except ValueError as e:
        # B2 credentials not configured
        duration_ms = (time.perf_counter() - start_time) * 1000
        return DependencyCheck(
            name="b2_storage",
            status=HealthStatus.WARNING,
            type=DependencyType.STORAGE,
            message="B2 storage not configured",
            duration_ms=round(duration_ms, 2)
        )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("B2 health check failed", error=str(e))
        return DependencyCheck(
            name="b2_storage",
            status=HealthStatus.ERROR,
            type=DependencyType.STORAGE,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


async def check_celery_health() -> DependencyCheck:
    """Check Celery workers health"""
    start_time = time.perf_counter()

    try:
        from app.celery_app import celery_app

        # Ping workers with timeout
        celery_ping = celery_app.control.ping(timeout=2.0)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if celery_ping:
            worker_count = len(celery_ping)
            return DependencyCheck(
                name="celery",
                status=HealthStatus.OK,
                type=DependencyType.QUEUE,
                message=f"Celery healthy, {worker_count} worker(s) responded",
                duration_ms=round(duration_ms, 2),
                details={"workers": worker_count}
            )
        else:
            return DependencyCheck(
                name="celery",
                status=HealthStatus.WARNING,
                type=DependencyType.QUEUE,
                message="No Celery workers responded",
                duration_ms=round(duration_ms, 2),
                details={"workers": 0}
            )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("Celery health check failed", error=str(e))
        return DependencyCheck(
            name="celery",
            status=HealthStatus.WARNING,  # Warning not error - app can work without workers
            type=DependencyType.QUEUE,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


async def check_llamaindex_health() -> DependencyCheck:
    """Check LlamaIndex service health"""
    start_time = time.perf_counter()

    try:
        llamaindex_url = os.getenv("LLAMAINDEX_SERVICE_URL")
        if llamaindex_url and connection_manager.http_client:
            response = await connection_manager.http_client.get(
                f"{llamaindex_url}/health",
                timeout=DEFAULT_TIMEOUT
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                return DependencyCheck(
                    name="llamaindex",
                    status=HealthStatus.OK,
                    type=DependencyType.SERVICE,
                    message="LlamaIndex service healthy",
                    duration_ms=round(duration_ms, 2),
                    details={"url": llamaindex_url}
                )
            else:
                return DependencyCheck(
                    name="llamaindex",
                    status=HealthStatus.ERROR,
                    type=DependencyType.SERVICE,
                    message=f"LlamaIndex returned HTTP {response.status_code}",
                    duration_ms=round(duration_ms, 2)
                )
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheck(
                name="llamaindex",
                status=HealthStatus.WARNING,
                type=DependencyType.SERVICE,
                message="LlamaIndex service not configured",
                duration_ms=round(duration_ms, 2)
            )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("LlamaIndex health check failed", error=str(e))
        return DependencyCheck(
            name="llamaindex",
            status=HealthStatus.ERROR,
            type=DependencyType.SERVICE,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


async def check_crewai_health() -> DependencyCheck:
    """Check CrewAI service health"""
    start_time = time.perf_counter()

    try:
        crewai_url = os.getenv("CREWAI_SERVICE_URL")
        if crewai_url and connection_manager.http_client:
            response = await connection_manager.http_client.get(
                f"{crewai_url}/api/crewai/health",
                timeout=DEFAULT_TIMEOUT
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                return DependencyCheck(
                    name="crewai",
                    status=HealthStatus.OK,
                    type=DependencyType.SERVICE,
                    message="CrewAI service healthy",
                    duration_ms=round(duration_ms, 2),
                    details={"url": crewai_url}
                )
            else:
                return DependencyCheck(
                    name="crewai",
                    status=HealthStatus.ERROR,
                    type=DependencyType.SERVICE,
                    message=f"CrewAI returned HTTP {response.status_code}",
                    duration_ms=round(duration_ms, 2)
                )
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return DependencyCheck(
                name="crewai",
                status=HealthStatus.WARNING,
                type=DependencyType.SERVICE,
                message="CrewAI service not configured",
                duration_ms=round(duration_ms, 2)
            )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error("CrewAI health check failed", error=str(e))
        return DependencyCheck(
            name="crewai",
            status=HealthStatus.ERROR,
            type=DependencyType.SERVICE,
            message=str(e),
            duration_ms=round(duration_ms, 2)
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=HealthResponse,
    summary="Basic health check",
    description="Returns basic health status without checking dependencies"
)
async def basic_health_check():
    """
    Basic health check endpoint.

    Lightweight check that verifies the application is running.
    Does not check external dependencies.
    """
    uptime = time.time() - get_service_start_time()

    return HealthResponse(
        status=HealthStatus.OK,
        version="7.3.0",
        environment=os.getenv("ENVIRONMENT", "development"),
        uptime_seconds=round(uptime, 2),
        checks={}
    )


@router.get(
    "/liveness",
    response_model=LivenessResponse,
    summary="Kubernetes liveness probe",
    description="Lightweight check for Kubernetes liveness probe - only checks if app is running"
)
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.

    Checks if the application is running and responsive.
    Should be lightweight and not check external dependencies.
    If this fails, Kubernetes should restart the container.
    """
    return LivenessResponse(alive=True)


@router.get(
    "/readiness",
    response_model=ReadinessResponse,
    summary="Kubernetes readiness probe",
    description="Checks if critical dependencies are ready to receive traffic"
)
async def readiness_probe(response: Response):
    """
    Kubernetes readiness probe endpoint.

    Checks if all critical dependencies (database, cache) are available
    and the application is ready to receive traffic.

    Returns 503 if any critical dependency is unavailable.
    """
    start_time = time.perf_counter()
    checks = {}

    # Check critical dependencies only
    checks["supabase"] = await check_supabase_health()
    checks["redis"] = await check_redis_health()

    # Determine overall status
    overall_status = aggregate_status(checks)
    critical_ok = is_critical_healthy(checks, CRITICAL_SERVICES)

    # Set response status based on health
    if not critical_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    total_duration = (time.perf_counter() - start_time) * 1000

    return ReadinessResponse(
        ready=critical_ok,
        status=overall_status,
        message="Ready to receive traffic" if critical_ok else "Critical services unavailable",
        checks=checks
    )


@router.get(
    "/deep",
    response_model=DeepHealthResponse,
    summary="Deep health check",
    description="Comprehensive health check of all dependencies with detailed metrics"
)
async def deep_health_check(response: Response):
    """
    Deep health check endpoint.

    Performs comprehensive health checks on all dependencies:
    - Supabase (PostgreSQL + pgvector)
    - Redis (cache + Celery broker)
    - Neo4j (knowledge graph)
    - B2 Storage (file storage)
    - Celery workers (background tasks)
    - LlamaIndex service (document processing)
    - CrewAI service (multi-agent orchestration)

    This is a more expensive check and should not be used frequently.
    Recommended for monitoring dashboards and troubleshooting.
    """
    start_time = time.perf_counter()
    checks = {}

    # Check all dependencies
    checks["supabase"] = await check_supabase_health()
    checks["redis"] = await check_redis_health()
    checks["neo4j"] = await check_neo4j_health()
    checks["b2_storage"] = await check_b2_health()
    checks["celery"] = await check_celery_health()
    checks["llamaindex"] = await check_llamaindex_health()
    checks["crewai"] = await check_crewai_health()

    # Calculate totals
    total_duration = (time.perf_counter() - start_time) * 1000
    overall_status = aggregate_status(checks)
    degraded = get_degraded_services(checks)
    critical_ok = is_critical_healthy(checks, CRITICAL_SERVICES)
    uptime = time.time() - get_service_start_time()

    # Set response status
    if overall_status == HealthStatus.ERROR:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return DeepHealthResponse(
        status=overall_status,
        version="7.3.0",
        environment=os.getenv("ENVIRONMENT", "development"),
        uptime_seconds=round(uptime, 2),
        checks=checks,
        critical_healthy=critical_ok,
        degraded_services=degraded,
        total_check_duration_ms=round(total_duration, 2)
    )


@router.get(
    "/dependencies",
    summary="List health check dependencies",
    description="Returns list of all dependencies that are health checked"
)
async def list_dependencies():
    """
    List all dependencies that are health checked.

    Useful for understanding what the health checks cover.
    """
    return {
        "critical_services": CRITICAL_SERVICES,
        "all_dependencies": [
            {
                "name": "supabase",
                "type": "database",
                "description": "PostgreSQL with pgvector for document storage and vector search",
                "critical": True
            },
            {
                "name": "redis",
                "type": "cache",
                "description": "Redis for caching, Celery broker, and rate limiting",
                "critical": True
            },
            {
                "name": "neo4j",
                "type": "graph",
                "description": "Neo4j knowledge graph for entity relationships",
                "critical": False
            },
            {
                "name": "b2_storage",
                "type": "storage",
                "description": "Backblaze B2 for file storage",
                "critical": False
            },
            {
                "name": "celery",
                "type": "queue",
                "description": "Celery workers for background task processing",
                "critical": False
            },
            {
                "name": "llamaindex",
                "type": "service",
                "description": "LlamaIndex service for document parsing and indexing",
                "critical": False
            },
            {
                "name": "crewai",
                "type": "service",
                "description": "CrewAI service for multi-agent AI orchestration",
                "critical": False
            }
        ],
        "timeout_seconds": DEFAULT_TIMEOUT
    }


# =============================================================================
# Service Orchestrator Integration
# =============================================================================


@router.get(
    "/orchestrator",
    summary="Service orchestrator health status",
    description="Comprehensive health check using the service orchestrator (23 services)"
)
async def orchestrator_health_check(request: Request, response: Response):
    """
    Service orchestrator health check endpoint.

    Uses the service orchestrator for comprehensive health checks across all 23 services:
    - Required: Supabase, Redis
    - Important: Neo4j, B2, Celery, Anthropic, LlamaIndex, CrewAI
    - Optional: Arcade, Soniox, Claude Vision, ffmpeg, OpenAI, LlamaCloud, Ollama
    - Infrastructure: Prometheus, Grafana, Alertmanager, Node Exporter, Flower
    - Auth/Email: Clerk, SendGrid, Gmail SMTP

    Includes caching for performance (30-second TTL).
    """
    start_time = time.perf_counter()

    # Get service orchestrator from app state
    service_orchestrator: Optional["ServiceOrchestrator"] = getattr(
        request.app.state, "service_orchestrator", None
    )

    if not service_orchestrator:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "message": "Service orchestrator not initialized",
            "services": {},
            "ready": False
        }

    try:
        # Run preflight checks (uses caching)
        preflight_result = await service_orchestrator.check_all_services()
        total_duration = (time.perf_counter() - start_time) * 1000

        # Convert to response format
        services_data = {}
        for service_name, service_status in preflight_result.services.items():
            services_data[service_name] = {
                "status": service_status.status,
                "required": service_status.required,
                "latency_ms": service_status.latency_ms,
                "error_message": service_status.error_message
            }

        # Set response status based on health
        if not preflight_result.all_required_healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "ok" if preflight_result.ready else ("degraded" if preflight_result.all_required_healthy else "error"),
            "ready": preflight_result.ready,
            "all_required_healthy": preflight_result.all_required_healthy,
            "services": services_data,
            "startup_time_ms": preflight_result.startup_time_ms,
            "check_duration_ms": round(total_duration, 2),
            "service_counts": {
                "total": len(services_data),
                "healthy": sum(1 for s in services_data.values() if s["status"] == "running"),
                "degraded": sum(1 for s in services_data.values() if s["status"] == "degraded"),
                "error": sum(1 for s in services_data.values() if s["status"] in ["error", "stopped"]),
                "required": sum(1 for s in services_data.values() if s["required"])
            }
        }

    except Exception as e:
        logger.error("Orchestrator health check failed", error=str(e))
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "status": "error",
            "message": str(e),
            "services": {},
            "ready": False
        }


@router.get(
    "/orchestrator/degraded",
    summary="List degraded services",
    description="Returns list of services that are degraded or unavailable"
)
async def list_degraded_services(request: Request):
    """
    List all services that are currently degraded or unavailable.

    Useful for quickly identifying issues and planning remediation.
    """
    service_orchestrator: Optional["ServiceOrchestrator"] = getattr(
        request.app.state, "service_orchestrator", None
    )

    if not service_orchestrator:
        return {
            "degraded_services": [],
            "message": "Service orchestrator not initialized"
        }

    try:
        degraded = service_orchestrator.get_degraded_services()
        fallback_messages = {}

        for service in degraded:
            fallback_messages[service] = service_orchestrator.get_fallback_message(service)

        return {
            "degraded_services": degraded,
            "fallback_messages": fallback_messages,
            "total_degraded": len(degraded)
        }

    except Exception as e:
        logger.error("Failed to get degraded services", error=str(e))
        return {
            "degraded_services": [],
            "error": str(e)
        }


@router.get(
    "/orchestrator/features",
    summary="Available features based on service health",
    description="Returns which features are available based on current service health"
)
async def get_available_features(request: Request):
    """
    Get available features based on current service health.

    Features are enabled/disabled based on the health of their dependent services.
    """
    service_orchestrator: Optional["ServiceOrchestrator"] = getattr(
        request.app.state, "service_orchestrator", None
    )

    if not service_orchestrator:
        return {
            "features": {},
            "message": "Service orchestrator not initialized"
        }

    try:
        features = service_orchestrator.get_available_features()
        processing_mode = service_orchestrator.get_processing_mode()
        embedding_provider = service_orchestrator.get_embedding_provider()
        agent_mode = service_orchestrator.get_agent_mode()

        return {
            "features": features,
            "processing_mode": processing_mode,
            "embedding_provider": embedding_provider,
            "agent_mode": agent_mode
        }

    except Exception as e:
        logger.error("Failed to get available features", error=str(e))
        return {
            "features": {},
            "error": str(e)
        }
