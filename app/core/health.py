"""
Empire v7.3 - Enhanced Health Check Models and Utilities
Task 190: Implement Enhanced Health Checks

Provides:
- Pydantic models for health check responses
- Timeout handling utilities for dependency checks
- Health status aggregation
"""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class HealthStatus(str, Enum):
    """Health check status values"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """Types of dependencies that can be health checked"""
    DATABASE = "database"
    CACHE = "cache"
    STORAGE = "storage"
    GRAPH = "graph"
    QUEUE = "queue"
    API = "api"
    SERVICE = "service"


# =============================================================================
# Pydantic Models
# =============================================================================


class DependencyCheck(BaseModel):
    """Result of a single dependency health check"""
    name: str = Field(..., description="Name of the dependency")
    status: HealthStatus = Field(..., description="Health status")
    type: Optional[DependencyType] = Field(None, description="Type of dependency")
    message: Optional[str] = Field(None, description="Status message or error")
    duration_ms: float = Field(..., description="Check duration in milliseconds")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    last_check: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Standard health check response"""
    status: HealthStatus = Field(..., description="Overall health status")
    version: str = Field(default="7.3.0", description="Service version")
    environment: str = Field(default="production", description="Deployment environment")
    service: str = Field(default="Empire FastAPI", description="Service name")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    uptime_seconds: Optional[float] = Field(None, description="Service uptime")
    checks: Dict[str, DependencyCheck] = Field(default_factory=dict)


class LivenessResponse(BaseModel):
    """Kubernetes liveness probe response"""
    alive: bool = Field(..., description="Is the application alive")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReadinessResponse(BaseModel):
    """Kubernetes readiness probe response"""
    ready: bool = Field(..., description="Is the application ready")
    status: HealthStatus = Field(..., description="Overall status")
    message: str = Field(..., description="Status message")
    checks: Dict[str, DependencyCheck] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DeepHealthResponse(HealthResponse):
    """Deep health check response with detailed dependency info"""
    critical_healthy: bool = Field(..., description="Are all critical deps healthy")
    degraded_services: List[str] = Field(default_factory=list)
    total_check_duration_ms: float = Field(..., description="Total check duration")


# =============================================================================
# Timeout Handling
# =============================================================================


async def check_with_timeout(
    check_fn: Callable[[], Coroutine[Any, Any, Any]],
    timeout_seconds: float = 5.0,
    default_result: Any = None
) -> tuple[Any, float, Optional[str]]:
    """
    Execute a health check function with timeout.

    Args:
        check_fn: Async function to execute
        timeout_seconds: Maximum time to wait
        default_result: Result to return on timeout/error

    Returns:
        tuple: (result, duration_ms, error_message)
    """
    start_time = time.perf_counter()
    error_message = None
    result = default_result

    try:
        result = await asyncio.wait_for(check_fn(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        error_message = f"Check timed out after {timeout_seconds}s"
        logger.warning("Health check timed out", timeout=timeout_seconds)
    except Exception as e:
        error_message = str(e)
        logger.error("Health check failed", error=error_message)

    duration_ms = (time.perf_counter() - start_time) * 1000
    return result, duration_ms, error_message


def sync_check_with_timeout(
    check_fn: Callable[[], Any],
    timeout_seconds: float = 5.0,
    default_result: Any = None
) -> tuple[Any, float, Optional[str]]:
    """
    Execute a synchronous health check with timing.

    Args:
        check_fn: Sync function to execute
        timeout_seconds: Not enforced for sync, just for reference
        default_result: Result to return on error

    Returns:
        tuple: (result, duration_ms, error_message)
    """
    start_time = time.perf_counter()
    error_message = None
    result = default_result

    try:
        result = check_fn()
    except Exception as e:
        error_message = str(e)
        logger.error("Sync health check failed", error=error_message)

    duration_ms = (time.perf_counter() - start_time) * 1000
    return result, duration_ms, error_message


# =============================================================================
# Status Aggregation
# =============================================================================


def aggregate_status(checks: Dict[str, DependencyCheck]) -> HealthStatus:
    """
    Aggregate multiple dependency checks into overall status.

    Rules:
    - If any check is ERROR -> ERROR
    - If any check is WARNING -> WARNING
    - If all checks are OK or UNKNOWN -> OK
    """
    if not checks:
        return HealthStatus.UNKNOWN

    has_error = any(c.status == HealthStatus.ERROR for c in checks.values())
    has_warning = any(c.status == HealthStatus.WARNING for c in checks.values())

    if has_error:
        return HealthStatus.ERROR
    elif has_warning:
        return HealthStatus.WARNING
    else:
        return HealthStatus.OK


def get_degraded_services(checks: Dict[str, DependencyCheck]) -> List[str]:
    """Get list of services that are not fully healthy"""
    return [
        name for name, check in checks.items()
        if check.status in [HealthStatus.ERROR, HealthStatus.WARNING]
    ]


def is_critical_healthy(
    checks: Dict[str, DependencyCheck],
    critical_services: List[str]
) -> bool:
    """
    Check if all critical services are healthy.

    Args:
        checks: All dependency checks
        critical_services: Names of critical services

    Returns:
        True if all critical services are healthy
    """
    for service in critical_services:
        check = checks.get(service)
        if check and check.status == HealthStatus.ERROR:
            return False
    return True


# =============================================================================
# Health Check Registry
# =============================================================================


class HealthCheckRegistry:
    """
    Registry for managing health checks.

    Allows registering custom health checks that will be included
    in the enhanced health check endpoints.
    """

    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._critical: List[str] = []

    def register(
        self,
        name: str,
        check_fn: Callable,
        critical: bool = False
    ) -> None:
        """
        Register a health check function.

        Args:
            name: Unique name for the check
            check_fn: Function that returns (status, message, details)
            critical: Whether this is a critical dependency
        """
        self._checks[name] = check_fn
        if critical and name not in self._critical:
            self._critical.append(name)
        logger.info("Health check registered", name=name, critical=critical)

    def unregister(self, name: str) -> None:
        """Remove a health check"""
        self._checks.pop(name, None)
        if name in self._critical:
            self._critical.remove(name)

    def get_checks(self) -> Dict[str, Callable]:
        """Get all registered checks"""
        return self._checks.copy()

    def get_critical_services(self) -> List[str]:
        """Get names of critical services"""
        return self._critical.copy()


# Global registry instance
health_registry = HealthCheckRegistry()


def get_health_registry() -> HealthCheckRegistry:
    """Get the global health check registry"""
    return health_registry
