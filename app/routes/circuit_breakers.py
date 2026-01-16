"""
Empire v7.3 - Circuit Breaker Management API (Task 159)

API endpoints for managing circuit breakers across all external services.
Provides visibility into circuit states, manual reset capabilities,
and configuration viewing.

Author: Claude Code
Date: 2025-01-15
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.circuit_breaker import (
    get_all_circuit_statuses,
    reset_circuit,
    get_circuit_breaker_sync,
    CircuitBreakerConfig,
    _circuit_registry,
)

router = APIRouter(
    prefix="/api/system/circuit-breakers",
    tags=["System - Circuit Breakers"],
    responses={
        404: {"description": "Circuit breaker not found"},
        503: {"description": "Service unavailable"},
    }
)


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class CircuitStatus(BaseModel):
    """Individual circuit breaker status"""
    service_name: str = Field(description="Name of the service")
    state: str = Field(description="Current state: CLOSED, OPEN, or HALF_OPEN")
    failure_count: int = Field(description="Current failure count")
    success_count: int = Field(description="Success count in half-open state")
    last_failure_time: Optional[str] = Field(description="ISO timestamp of last failure")
    last_success_time: Optional[str] = Field(description="ISO timestamp of last success")
    total_calls: int = Field(description="Total calls made through circuit")
    total_failures: int = Field(description="Total failures recorded")
    total_successes: int = Field(description="Total successes recorded")
    fallback_calls: int = Field(description="Number of fallback invocations")
    is_open: bool = Field(description="Whether circuit is currently open")
    time_until_recovery: Optional[float] = Field(
        description="Seconds until half-open transition (if open)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "service_name": "supabase",
                "state": "CLOSED",
                "failure_count": 0,
                "success_count": 0,
                "last_failure_time": None,
                "last_success_time": "2025-01-15T12:00:00.000000",
                "total_calls": 150,
                "total_failures": 2,
                "total_successes": 148,
                "fallback_calls": 1,
                "is_open": False,
                "time_until_recovery": None
            }
        }


class AllCircuitsResponse(BaseModel):
    """Response containing all circuit breaker statuses"""
    circuits: Dict[str, CircuitStatus] = Field(
        description="Map of service names to their circuit status"
    )
    total_circuits: int = Field(description="Total number of registered circuits")
    open_circuits: int = Field(description="Number of currently open circuits")
    timestamp: str = Field(description="ISO timestamp of status check")


class CircuitResetResponse(BaseModel):
    """Response after resetting a circuit breaker"""
    service_name: str
    success: bool
    message: str
    previous_state: str
    new_state: str


class CircuitConfigResponse(BaseModel):
    """Circuit breaker configuration response"""
    service_name: str
    failure_threshold: int
    success_threshold: int
    recovery_timeout: float
    max_retries: int
    retry_base_delay: float
    retry_max_delay: float
    retry_multiplier: float
    operation_timeout: float


class SystemHealthResponse(BaseModel):
    """Overall system health based on circuit breaker states"""
    status: str = Field(description="Overall status: healthy, degraded, or unhealthy")
    healthy_services: List[str]
    degraded_services: List[str]
    unhealthy_services: List[str]
    total_services: int
    timestamp: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "",
    response_model=AllCircuitsResponse,
    summary="Get All Circuit Breaker States",
    description="Retrieve the current state of all registered circuit breakers."
)
async def get_circuit_states() -> AllCircuitsResponse:
    """
    Get the status of all registered circuit breakers.

    Returns:
        Status information for each circuit breaker including state,
        failure counts, and timing information.
    """
    statuses = get_all_circuit_statuses()

    circuits = {}
    open_count = 0

    for service_name, status in statuses.items():
        circuit_status = CircuitStatus(
            service_name=service_name,
            state=status.get("state", "UNKNOWN"),
            failure_count=status.get("failure_count", 0),
            success_count=status.get("success_count", 0),
            last_failure_time=status.get("last_failure_time"),
            last_success_time=status.get("last_success_time"),
            total_calls=status.get("total_calls", 0),
            total_failures=status.get("total_failures", 0),
            total_successes=status.get("total_successes", 0),
            fallback_calls=status.get("fallback_calls", 0),
            is_open=status.get("is_open", False),
            time_until_recovery=status.get("time_until_recovery"),
        )
        circuits[service_name] = circuit_status

        if status.get("is_open", False):
            open_count += 1

    return AllCircuitsResponse(
        circuits=circuits,
        total_circuits=len(circuits),
        open_circuits=open_count,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get(
    "/{service_name}",
    response_model=CircuitStatus,
    summary="Get Single Circuit Breaker State",
    description="Retrieve the state of a specific circuit breaker by service name."
)
async def get_circuit_state(service_name: str) -> CircuitStatus:
    """
    Get the status of a specific circuit breaker.

    Args:
        service_name: Name of the service (e.g., "supabase", "anthropic")

    Returns:
        Detailed status information for the specified circuit breaker.

    Raises:
        HTTPException: If the circuit breaker is not found.
    """
    statuses = get_all_circuit_statuses()

    if service_name not in statuses:
        raise HTTPException(
            status_code=404,
            detail=f"Circuit breaker '{service_name}' not found. "
                   f"Available circuits: {list(statuses.keys())}"
        )

    status = statuses[service_name]

    return CircuitStatus(
        service_name=service_name,
        state=status.get("state", "UNKNOWN"),
        failure_count=status.get("failure_count", 0),
        success_count=status.get("success_count", 0),
        last_failure_time=status.get("last_failure_time"),
        last_success_time=status.get("last_success_time"),
        total_calls=status.get("total_calls", 0),
        total_failures=status.get("total_failures", 0),
        total_successes=status.get("total_successes", 0),
        fallback_calls=status.get("fallback_calls", 0),
        is_open=status.get("is_open", False),
        time_until_recovery=status.get("time_until_recovery"),
    )


@router.post(
    "/{service_name}/reset",
    response_model=CircuitResetResponse,
    summary="Reset Circuit Breaker",
    description="Manually reset a circuit breaker to closed state."
)
async def reset_circuit_breaker(service_name: str) -> CircuitResetResponse:
    """
    Reset a circuit breaker to its closed state.

    This is useful for manually recovering from an open circuit
    after addressing the underlying issue.

    Args:
        service_name: Name of the service to reset

    Returns:
        Reset result including previous and new state.

    Raises:
        HTTPException: If the circuit breaker is not found.
    """
    statuses = get_all_circuit_statuses()

    if service_name not in statuses:
        raise HTTPException(
            status_code=404,
            detail=f"Circuit breaker '{service_name}' not found"
        )

    previous_state = statuses[service_name].get("state", "UNKNOWN")

    try:
        await reset_circuit(service_name)
        new_statuses = get_all_circuit_statuses()
        new_state = new_statuses.get(service_name, {}).get("state", "CLOSED")

        return CircuitResetResponse(
            service_name=service_name,
            success=True,
            message=f"Circuit breaker '{service_name}' reset successfully",
            previous_state=previous_state,
            new_state=new_state
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset circuit breaker: {str(e)}"
        )


@router.get(
    "/{service_name}/config",
    response_model=CircuitConfigResponse,
    summary="Get Circuit Breaker Configuration",
    description="Retrieve the configuration for a specific circuit breaker."
)
async def get_circuit_config(service_name: str) -> CircuitConfigResponse:
    """
    Get the configuration for a specific circuit breaker.

    Args:
        service_name: Name of the service

    Returns:
        Configuration including thresholds, timeouts, and retry settings.

    Raises:
        HTTPException: If the circuit breaker is not found.
    """
    if service_name not in _circuit_registry:
        raise HTTPException(
            status_code=404,
            detail=f"Circuit breaker '{service_name}' not found"
        )

    circuit = _circuit_registry[service_name]
    config = circuit._config

    return CircuitConfigResponse(
        service_name=service_name,
        failure_threshold=config.failure_threshold,
        success_threshold=config.success_threshold,
        recovery_timeout=config.recovery_timeout,
        max_retries=config.max_retries,
        retry_base_delay=config.retry_base_delay,
        retry_max_delay=config.retry_max_delay,
        retry_multiplier=config.retry_multiplier,
        operation_timeout=config.operation_timeout,
    )


@router.get(
    "/health/summary",
    response_model=SystemHealthResponse,
    summary="System Health Summary",
    description="Get overall system health based on circuit breaker states."
)
async def get_system_health() -> SystemHealthResponse:
    """
    Get overall system health based on circuit breaker states.

    Categorizes services as:
    - healthy: Circuit closed, normal operation
    - degraded: Circuit half-open, recovering
    - unhealthy: Circuit open, service unavailable

    Returns:
        System health summary with categorized services.
    """
    statuses = get_all_circuit_statuses()

    healthy = []
    degraded = []
    unhealthy = []

    for service_name, status in statuses.items():
        state = status.get("state", "UNKNOWN")

        if state == "CLOSED":
            healthy.append(service_name)
        elif state == "HALF_OPEN":
            degraded.append(service_name)
        else:  # OPEN or UNKNOWN
            unhealthy.append(service_name)

    # Determine overall status
    if unhealthy:
        overall_status = "unhealthy"
    elif degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return SystemHealthResponse(
        status=overall_status,
        healthy_services=healthy,
        degraded_services=degraded,
        unhealthy_services=unhealthy,
        total_services=len(statuses),
        timestamp=datetime.utcnow().isoformat()
    )


@router.get(
    "/metrics/summary",
    summary="Circuit Breaker Metrics Summary",
    description="Get aggregated metrics across all circuit breakers."
)
async def get_metrics_summary() -> Dict[str, Any]:
    """
    Get aggregated metrics across all circuit breakers.

    Returns:
        Summary metrics including total calls, failures, and success rates.
    """
    statuses = get_all_circuit_statuses()

    total_calls = 0
    total_failures = 0
    total_successes = 0
    total_fallback_calls = 0

    service_metrics = {}

    for service_name, status in statuses.items():
        calls = status.get("total_calls", 0)
        failures = status.get("total_failures", 0)
        successes = status.get("total_successes", 0)
        fallbacks = status.get("fallback_calls", 0)

        total_calls += calls
        total_failures += failures
        total_successes += successes
        total_fallback_calls += fallbacks

        success_rate = (successes / calls * 100) if calls > 0 else 100.0

        service_metrics[service_name] = {
            "total_calls": calls,
            "total_failures": failures,
            "total_successes": successes,
            "fallback_calls": fallbacks,
            "success_rate_percent": round(success_rate, 2),
        }

    overall_success_rate = (
        (total_successes / total_calls * 100) if total_calls > 0 else 100.0
    )

    return {
        "summary": {
            "total_calls": total_calls,
            "total_failures": total_failures,
            "total_successes": total_successes,
            "total_fallback_calls": total_fallback_calls,
            "overall_success_rate_percent": round(overall_success_rate, 2),
        },
        "by_service": service_metrics,
        "timestamp": datetime.utcnow().isoformat()
    }
