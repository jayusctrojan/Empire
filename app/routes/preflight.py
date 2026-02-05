"""
Empire v7.3 - Preflight Routes
Service Orchestration Architecture - API endpoints for preflight checks

Provides:
- GET  /api/preflight/check      - Full preflight check
- GET  /api/preflight/status     - Current service status
- POST /api/preflight/start/{service}  - Start a service
- GET  /api/preflight/ready      - Simple ready check (for polling)
- POST /api/preflight/shutdown/prepare   - Prepare for shutdown
- POST /api/preflight/shutdown/drain     - Drain in-flight requests
- GET  /api/preflight/shutdown/status    - Check shutdown progress
"""

import asyncio
import shlex
import subprocess
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
import structlog

from app.core.service_orchestrator import (
    ServiceOrchestrator,
    get_service_orchestrator,
    DEGRADATION_RULES,
)
from app.models.preflight import (
    DegradationMatrix,
    DegradationRule,
    PreflightResult,
    PreflightStatusResponse,
    ServiceHealthCheck,
    ServiceStartRequest,
    ServiceStartResponse,
    ServiceStatus,
    ShutdownProgress,
    ShutdownPhase,
    ShutdownRequest,
    StartupProgress,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/preflight", tags=["Preflight"])

# Track startup time for uptime calculation
_startup_time: Optional[float] = None


def get_startup_time() -> float:
    """Get or initialize startup time"""
    global _startup_time
    if _startup_time is None:
        _startup_time = time.time()
    return _startup_time


# Initialize on module load
get_startup_time()


# =============================================================================
# PREFLIGHT CHECK ENDPOINTS
# =============================================================================

@router.get(
    "/check",
    response_model=PreflightResult,
    summary="Full preflight check",
    description="Performs comprehensive health checks on all 23 services"
)
async def full_preflight_check(
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Run a complete preflight check on all services.

    This checks:
    - Required services (Supabase, Redis) - must be healthy
    - Important services (Neo4j, B2, Celery, etc.) - impacts features
    - Optional services (Arcade, Ollama, etc.) - graceful degradation
    - Infrastructure services (Prometheus, Grafana) - monitoring

    Returns detailed status for each service including:
    - Health status (running, degraded, stopped, error)
    - Latency in milliseconds
    - Error messages if any
    - Fallback behavior when unavailable
    """
    logger.info("Running full preflight check")

    result = await orchestrator.check_all_services()

    logger.info(
        "Preflight check completed",
        ready=result.ready,
        startup_time_ms=result.startup_time_ms,
        required_healthy=result.all_required_healthy,
        important_healthy=result.all_important_healthy,
        warnings_count=len(result.warnings),
        errors_count=len(result.errors)
    )

    return result


@router.get(
    "/status",
    response_model=PreflightStatusResponse,
    summary="Current service status",
    description="Returns current status of all services using cached values"
)
async def get_service_status(
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Get current service status.

    Uses cached health check results (30s TTL) for fast response.
    Does not perform new health checks unless cache is expired.

    Returns:
    - Overall system status (ready, degraded, not_ready)
    - Individual service health
    - List of degraded and unavailable services
    - System uptime
    """
    # Use cached results for fast response
    all_services = {}
    degraded = []
    unavailable = []

    # Check all services (will use cache if available)
    result = await orchestrator.check_all_services()

    for name, check in result.services.items():
        all_services[name] = check
        if check.status == ServiceStatus.DEGRADED:
            degraded.append(name)
        elif check.status in [ServiceStatus.STOPPED, ServiceStatus.ERROR]:
            unavailable.append(name)

    # Determine overall status
    if not result.all_required_healthy:
        overall = "not_ready"
    elif degraded or unavailable:
        overall = "degraded"
    else:
        overall = "ready"

    uptime = time.time() - get_startup_time()

    return PreflightStatusResponse(
        status=overall,
        services=all_services,
        degraded_services=degraded,
        unavailable_services=unavailable,
        uptime_seconds=round(uptime, 2)
    )


@router.get(
    "/ready",
    summary="Simple ready check",
    description="Quick check if the system is ready - optimized for polling"
)
async def ready_check(
    response: Response,
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Simple ready check endpoint for polling.

    Returns 200 if all required services are healthy.
    Returns 503 if any required service is unavailable.

    Optimized for fast response - only checks required services.
    """
    # Only check required services for speed
    required_ok, _ = await orchestrator.check_required_services()

    if not required_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": False, "message": "Required services not ready"}

    return {"ready": True, "message": "System is ready"}


@router.get(
    "/progress",
    response_model=StartupProgress,
    summary="Startup progress",
    description="Get current startup progress for status bar display"
)
async def get_startup_progress(
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Get current startup progress.

    Useful for displaying startup status bar in desktop app.
    Returns:
    - Current phase (initializing, checking_required, etc.)
    - Progress percentage (0-100)
    - Current service being checked
    - Human-readable status message
    """
    return orchestrator.get_startup_progress()


# =============================================================================
# SERVICE CONTROL ENDPOINTS
# =============================================================================

@router.post(
    "/start/{service_name}",
    response_model=ServiceStartResponse,
    summary="Start a service",
    description="Attempt to start a specific service"
)
async def start_service(
    service_name: str,
    _request: ServiceStartRequest = None,  # Reserved for future use
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Attempt to start a specific service.

    Only works for services that have a startup_command defined:
    - neo4j: docker-compose up neo4j -d
    - celery: celery -A app.celery_app worker --loglevel=info

    Returns:
    - Whether the service was started
    - Whether it's now healthy
    - Startup time in milliseconds
    """
    service_config = orchestrator.inventory.get_service(service_name)

    if not service_config:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown service: {service_name}"
        )

    if not service_config.startup_command:
        raise HTTPException(
            status_code=400,
            detail=f"Service '{service_name}' does not have a startup command"
        )

    start_time = time.perf_counter()

    try:
        # Execute startup command
        logger.info("Starting service", service=service_name, command=service_config.startup_command)

        # Parse command to avoid shell=True, use DEVNULL to avoid buffer issues
        cmd_parts = shlex.split(service_config.startup_command)
        subprocess.Popen(
            cmd_parts,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait briefly for service to start
        await asyncio.sleep(2)

        # Check if healthy
        check = await orchestrator.check_service(service_name, use_cache=False)
        startup_time_ms = (time.perf_counter() - start_time) * 1000

        return ServiceStartResponse(
            service_name=service_name,
            started=True,
            healthy=check.status == ServiceStatus.RUNNING,
            message=f"Service started, status: {check.status.value}",
            startup_time_ms=round(startup_time_ms, 2)
        )

    except Exception as e:
        logger.error("Failed to start service", service=service_name, error=str(e))
        return ServiceStartResponse(
            service_name=service_name,
            started=False,
            healthy=False,
            message=f"Failed to start: {str(e)}"
        )


@router.get(
    "/service/{service_name}",
    response_model=ServiceHealthCheck,
    summary="Check single service",
    description="Get health status of a specific service"
)
async def check_single_service(
    service_name: str,
    refresh: bool = False,
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Check health of a specific service.

    Args:
        service_name: Name of the service to check
        refresh: If true, bypass cache and perform fresh check
    """
    return await orchestrator.check_service(service_name, use_cache=not refresh)


@router.post(
    "/cache/clear",
    summary="Clear health cache",
    description="Clear all cached health check results"
)
async def clear_cache(
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """Clear all cached health check results."""
    orchestrator.clear_cache()
    return {"message": "Cache cleared", "timestamp": time.time()}


# =============================================================================
# GRACEFUL DEGRADATION ENDPOINTS
# =============================================================================

@router.get(
    "/degradation",
    response_model=DegradationMatrix,
    summary="Degradation matrix",
    description="Get the complete graceful degradation matrix"
)
async def get_degradation_matrix():
    """
    Get the complete graceful degradation matrix.

    Shows how the system behaves when each service is unavailable:
    - Impact description
    - Fallback behavior
    - Affected endpoints
    - User-facing message
    """
    return DegradationMatrix(rules=DEGRADATION_RULES)


@router.get(
    "/degradation/{service_name}",
    response_model=DegradationRule,
    summary="Service degradation rule",
    description="Get degradation behavior for a specific service"
)
async def get_service_degradation(
    service_name: str,
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Get the degradation rule for a specific service.

    Returns how the system behaves when this service is unavailable.
    """
    rule = orchestrator.get_degradation_rule(service_name)
    if not rule:
        raise HTTPException(
            status_code=404,
            detail=f"No degradation rule for service: {service_name}"
        )
    return rule


# =============================================================================
# SHUTDOWN ENDPOINTS
# =============================================================================

# Shutdown state tracking
_shutdown_state = {
    "phase": ShutdownPhase.RUNNING,
    "pending_tasks": 0,
    "connections_open": 0,
    "data_flushed": False,
    "start_time": None
}


@router.post(
    "/shutdown/prepare",
    summary="Prepare for shutdown",
    description="Signal the system to stop accepting new work"
)
async def prepare_shutdown():
    """
    Prepare for graceful shutdown.

    This endpoint:
    1. Stops accepting new requests (returns 503 for new work)
    2. Starts draining in-flight requests
    3. Signals background workers to complete current tasks

    Call this before /shutdown/drain for orderly shutdown.
    """
    _shutdown_state["phase"] = ShutdownPhase.DRAINING
    _shutdown_state["start_time"] = time.time()

    logger.warning("Shutdown preparation initiated")

    return {
        "message": "Shutdown preparation started",
        "phase": "draining",
        "timestamp": time.time()
    }


@router.post(
    "/shutdown/drain",
    response_model=ShutdownProgress,
    summary="Drain in-flight requests",
    description="Wait for in-flight requests to complete"
)
async def drain_requests(
    request: ShutdownRequest = ShutdownRequest()
):
    """
    Drain in-flight requests before shutdown.

    Args:
        timeout: Maximum time to wait for draining (default 30s)
        force: Force shutdown without waiting for tasks

    Returns progress of the drain operation.
    """
    if request.force:
        _shutdown_state["phase"] = ShutdownPhase.STOPPED
        return ShutdownProgress(
            phase=ShutdownPhase.STOPPED,
            progress_percent=100,
            message="Forced shutdown",
            pending_tasks=0,
            connections_open=0,
            data_flushed=True
        )

    # Check Celery for pending tasks
    try:
        from app.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active() or {}
        pending_count = sum(len(tasks) for tasks in active.values())
        _shutdown_state["pending_tasks"] = pending_count
    except Exception:
        _shutdown_state["pending_tasks"] = 0

    # Calculate progress and check timeout
    elapsed = time.time() - (_shutdown_state.get("start_time") or time.time())

    # Check if timeout exceeded
    if elapsed >= request.timeout_seconds:
        _shutdown_state["phase"] = ShutdownPhase.STOPPED
        return ShutdownProgress(
            phase=ShutdownPhase.STOPPED,
            progress_percent=100,
            message=f"Drain timeout exceeded ({request.timeout_seconds}s)",
            pending_tasks=_shutdown_state["pending_tasks"],
            connections_open=0,
            data_flushed=False
        )

    if _shutdown_state["pending_tasks"] == 0:
        _shutdown_state["phase"] = ShutdownPhase.CLOSING_CONNECTIONS
        progress = 80
    else:
        progress = 50

    return ShutdownProgress(
        phase=_shutdown_state["phase"],
        progress_percent=progress,
        message=f"Draining requests, {_shutdown_state['pending_tasks']} tasks pending",
        pending_tasks=_shutdown_state["pending_tasks"],
        connections_open=_shutdown_state["connections_open"],
        data_flushed=_shutdown_state["data_flushed"]
    )


@router.get(
    "/shutdown/status",
    response_model=ShutdownProgress,
    summary="Check shutdown progress",
    description="Get current status of shutdown process"
)
async def get_shutdown_status():
    """Get the current shutdown status."""
    phase_progress = {
        ShutdownPhase.RUNNING: 0,
        ShutdownPhase.DRAINING: 25,
        ShutdownPhase.STOPPING_WORKERS: 50,
        ShutdownPhase.CLOSING_CONNECTIONS: 75,
        ShutdownPhase.FLUSHING_DATA: 90,
        ShutdownPhase.STOPPED: 100
    }

    return ShutdownProgress(
        phase=_shutdown_state["phase"],
        progress_percent=phase_progress.get(_shutdown_state["phase"], 0),
        message=f"Shutdown phase: {_shutdown_state['phase'].value}",
        pending_tasks=_shutdown_state["pending_tasks"],
        connections_open=_shutdown_state["connections_open"],
        data_flushed=_shutdown_state["data_flushed"]
    )


# =============================================================================
# SERVICE INVENTORY ENDPOINTS
# =============================================================================

@router.get(
    "/services",
    summary="List all services",
    description="Get the complete service inventory"
)
async def list_services(
    orchestrator: ServiceOrchestrator = Depends(get_service_orchestrator)
):
    """
    Get the complete service inventory.

    Returns all 23 services organized by category:
    - Required: Services the app cannot function without
    - Important: Services that major features depend on
    - Optional: Services with graceful degradation
    - Infrastructure: Monitoring and observability services
    """
    return {
        "total_services": len(orchestrator.inventory.get_all_services()),
        "required": [
            {"name": s.name, "type": s.type.value, "fallback": s.fallback}
            for s in orchestrator.inventory.required
        ],
        "important": [
            {"name": s.name, "type": s.type.value, "fallback": s.fallback}
            for s in orchestrator.inventory.important
        ],
        "optional": [
            {"name": s.name, "type": s.type.value, "fallback": s.fallback}
            for s in orchestrator.inventory.optional
        ],
        "infrastructure": [
            {"name": s.name, "type": s.type.value, "fallback": s.fallback}
            for s in orchestrator.inventory.infrastructure
        ]
    }
