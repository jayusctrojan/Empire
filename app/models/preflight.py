"""
Empire v7.3 - Preflight Models
Service Orchestration Architecture - Pydantic models for preflight checks

Provides models for:
- Service health status representation
- Preflight check results
- Startup sequence tracking
- Graceful degradation state
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# SERVICE STATUS ENUMS
# =============================================================================

class ServiceStatus(str, Enum):
    """Status of a service health check"""
    RUNNING = "running"       # Service is healthy and operational
    DEGRADED = "degraded"     # Service is partially functional
    STOPPED = "stopped"       # Service is not running
    ERROR = "error"           # Service encountered an error
    CHECKING = "checking"     # Health check in progress
    UNKNOWN = "unknown"       # Status not yet determined


class ServiceCategory(str, Enum):
    """Category classification for services"""
    REQUIRED = "required"           # App won't function without
    IMPORTANT = "important"         # Major features depend on
    OPTIONAL = "optional"           # Graceful degradation available
    INFRASTRUCTURE = "infrastructure"  # Monitoring stack


class ServiceType(str, Enum):
    """Type of service"""
    DATABASE = "database"
    CACHE = "cache"
    GRAPH = "graph"
    STORAGE = "storage"
    QUEUE = "queue"
    SERVICE = "service"
    API = "api"
    MONITORING = "monitoring"
    LOCAL = "local"


# =============================================================================
# SERVICE CHECK MODELS
# =============================================================================

class ServiceHealthCheck(BaseModel):
    """Result of a single service health check"""
    name: str = Field(..., description="Service identifier")
    status: ServiceStatus = Field(..., description="Current service status")
    category: ServiceCategory = Field(..., description="Service category")
    type: ServiceType = Field(..., description="Type of service")
    latency_ms: Optional[float] = Field(None, description="Health check latency in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details about the service")
    last_checked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the check was performed")
    fallback_message: Optional[str] = Field(None, description="Message about fallback behavior when unavailable")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "supabase",
                "status": "running",
                "category": "required",
                "type": "database",
                "latency_ms": 45.2,
                "error_message": None,
                "details": {"version": "15.1", "connections": 10},
                "last_checked": "2025-01-19T12:00:00Z",
                "fallback_message": None
            }
        }


class ServiceConfig(BaseModel):
    """Configuration for a service health check"""
    name: str = Field(..., description="Service identifier")
    category: ServiceCategory = Field(..., description="Service category")
    type: ServiceType = Field(..., description="Type of service")
    health_url: Optional[str] = Field(None, description="Health check URL (for HTTP services)")
    timeout_ms: int = Field(2000, description="Health check timeout in milliseconds")
    fallback: Optional[str] = Field(None, description="Fallback behavior when service unavailable")
    required_env_vars: List[str] = Field(default_factory=list, description="Required environment variables")
    startup_command: Optional[str] = Field(None, description="Command to start the service")


# =============================================================================
# PREFLIGHT RESULT MODELS
# =============================================================================

class PreflightResult(BaseModel):
    """Complete preflight check result"""
    ready: bool = Field(..., description="Whether the app is ready to start")
    all_required_healthy: bool = Field(..., description="Whether all required services are healthy")
    all_important_healthy: bool = Field(..., description="Whether all important services are healthy")
    services: Dict[str, ServiceHealthCheck] = Field(..., description="Health check results by service name")
    startup_time_ms: float = Field(..., description="Total time for preflight checks")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When preflight was run")
    degraded_features: List[str] = Field(default_factory=list, description="Features unavailable due to service issues")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking warnings")
    errors: List[str] = Field(default_factory=list, description="Blocking errors")

    class Config:
        json_schema_extra = {
            "example": {
                "ready": True,
                "all_required_healthy": True,
                "all_important_healthy": False,
                "services": {},
                "startup_time_ms": 1250.5,
                "timestamp": "2025-01-19T12:00:00Z",
                "degraded_features": ["Knowledge graph queries unavailable"],
                "warnings": ["Neo4j is not responding - graph features disabled"],
                "errors": []
            }
        }


class PreflightStatusResponse(BaseModel):
    """Response for current service status endpoint"""
    status: Literal["ready", "degraded", "not_ready"] = Field(..., description="Overall system status")
    services: Dict[str, ServiceHealthCheck] = Field(..., description="Current service health")
    degraded_services: List[str] = Field(default_factory=list, description="Services in degraded state")
    unavailable_services: List[str] = Field(default_factory=list, description="Services that are unavailable")
    uptime_seconds: float = Field(..., description="Time since last startup")


# =============================================================================
# STARTUP SEQUENCE MODELS
# =============================================================================

class StartupPhase(str, Enum):
    """Phases of the startup sequence"""
    INITIALIZING = "initializing"
    CHECKING_REQUIRED = "checking_required"
    CHECKING_IMPORTANT = "checking_important"
    CHECKING_OPTIONAL = "checking_optional"
    STARTING_SERVICES = "starting_services"
    READY = "ready"
    FAILED = "failed"


class StartupProgress(BaseModel):
    """Progress of the startup sequence"""
    phase: StartupPhase = Field(..., description="Current startup phase")
    progress_percent: float = Field(..., ge=0, le=100, description="Overall progress percentage")
    current_service: Optional[str] = Field(None, description="Service currently being checked")
    message: str = Field(..., description="Human-readable status message")
    services_checked: int = Field(0, description="Number of services checked")
    services_total: int = Field(0, description="Total number of services to check")
    elapsed_ms: float = Field(0, description="Elapsed time in milliseconds")


# =============================================================================
# SHUTDOWN MODELS
# =============================================================================

class ShutdownPhase(str, Enum):
    """Phases of graceful shutdown"""
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING_WORKERS = "stopping_workers"
    CLOSING_CONNECTIONS = "closing_connections"
    FLUSHING_DATA = "flushing_data"
    STOPPED = "stopped"


class ShutdownProgress(BaseModel):
    """Progress of the shutdown sequence"""
    phase: ShutdownPhase = Field(..., description="Current shutdown phase")
    progress_percent: float = Field(..., ge=0, le=100, description="Overall progress percentage")
    message: str = Field(..., description="Human-readable status message")
    pending_tasks: int = Field(0, description="Number of tasks still in flight")
    connections_open: int = Field(0, description="Number of connections still open")
    data_flushed: bool = Field(False, description="Whether all data has been flushed")


class ShutdownRequest(BaseModel):
    """Request to initiate shutdown"""
    timeout_seconds: int = Field(30, ge=5, le=300, description="Maximum time to wait for graceful shutdown")
    force: bool = Field(False, description="Force shutdown without waiting for tasks")


# =============================================================================
# SERVICE START/STOP MODELS
# =============================================================================

class ServiceStartRequest(BaseModel):
    """Request to start a service"""
    service_name: str = Field(..., description="Name of service to start")
    wait_for_healthy: bool = Field(True, description="Wait for service to become healthy")
    timeout_seconds: int = Field(60, ge=5, le=300, description="Timeout for startup")


class ServiceStartResponse(BaseModel):
    """Response from service start request"""
    service_name: str = Field(..., description="Name of service")
    started: bool = Field(..., description="Whether service was started successfully")
    healthy: bool = Field(..., description="Whether service is healthy after start")
    message: str = Field(..., description="Status message")
    startup_time_ms: Optional[float] = Field(None, description="Time to start in milliseconds")


# =============================================================================
# GRACEFUL DEGRADATION MODELS
# =============================================================================

class DegradationRule(BaseModel):
    """Rule for graceful degradation when a service is unavailable"""
    service_name: str = Field(..., description="Service this rule applies to")
    impact: str = Field(..., description="Description of impact when service is unavailable")
    fallback_behavior: str = Field(..., description="What happens instead")
    affected_endpoints: List[str] = Field(default_factory=list, description="Endpoints affected")
    user_message: str = Field(..., description="Message to show users")


class DegradationMatrix(BaseModel):
    """Complete degradation matrix for all services"""
    rules: Dict[str, DegradationRule] = Field(..., description="Degradation rules by service name")


# =============================================================================
# SERVICE INVENTORY MODELS
# =============================================================================

class ServiceInventory(BaseModel):
    """Complete inventory of all services"""
    required: List[ServiceConfig] = Field(default_factory=list, description="Required services")
    important: List[ServiceConfig] = Field(default_factory=list, description="Important services")
    optional: List[ServiceConfig] = Field(default_factory=list, description="Optional services")
    infrastructure: List[ServiceConfig] = Field(default_factory=list, description="Infrastructure services")

    def get_all_services(self) -> List[ServiceConfig]:
        """Get all services in startup order"""
        return self.required + self.important + self.optional + self.infrastructure

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """Get a specific service configuration by name"""
        for service in self.get_all_services():
            if service.name == name:
                return service
        return None
