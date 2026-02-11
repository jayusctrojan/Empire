"""
Empire v7.3 - Service Orchestrator
Central service health and startup orchestration for 23 services

Provides:
- Parallel health checks with aggressive timeouts
- Two-phase startup (required blocking, important/optional background)
- Health check caching (30s TTL)
- Graceful degradation support
- Performance target: App ready in < 3 seconds
"""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

import httpx
import structlog
from prometheus_client import Counter, Gauge, Histogram

from app.models.preflight import (
    DegradationRule,
    PreflightResult,
    ServiceCategory,
    ServiceConfig,
    ServiceHealthCheck,
    ServiceInventory,
    ServiceStatus,
    ServiceType,
    StartupPhase,
    StartupProgress,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

PREFLIGHT_CHECK_DURATION = Histogram(
    "empire_preflight_check_duration_seconds",
    "Duration of preflight checks",
    ["phase"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
)

SERVICE_HEALTH_STATUS = Gauge(
    "empire_service_health_status",
    "Current health status of services (1=running, 0=not running)",
    ["service", "category"]
)

SERVICE_CHECK_LATENCY = Histogram(
    "empire_service_check_latency_ms",
    "Health check latency per service in milliseconds",
    ["service"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2000, 5000]
)

PREFLIGHT_FAILURES = Counter(
    "empire_preflight_failures_total",
    "Total preflight check failures",
    ["service", "reason"]
)


# =============================================================================
# TIMEOUT CONFIGURATION
# =============================================================================

# Aggressive timeouts for fast startup
TIMEOUTS = {
    "required": 2.0,      # Required services get longer timeout
    "important": 1.0,     # Important services need quick check
    "optional": 0.5,      # Optional services - skip if slow
    "infrastructure": 0.5  # Nice to have, not critical
}


# =============================================================================
# SERVICE INVENTORY - 23 SERVICES
# =============================================================================

DEFAULT_SERVICE_INVENTORY = ServiceInventory(
    # REQUIRED (App Won't Function Without)
    required=[
        ServiceConfig(
            name="supabase",
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            timeout_ms=2000,
            fallback=None,
            required_env_vars=["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
        ),
        ServiceConfig(
            name="redis",
            category=ServiceCategory.REQUIRED,
            type=ServiceType.CACHE,
            timeout_ms=2000,
            fallback=None,
            required_env_vars=["REDIS_URL"]
        ),
    ],

    # IMPORTANT (Major Features Depend On)
    important=[
        ServiceConfig(
            name="neo4j",
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.GRAPH,
            timeout_ms=1000,
            fallback="Knowledge graph features disabled",
            startup_command="docker-compose up neo4j -d",
            required_env_vars=["NEO4J_URI", "NEO4J_PASSWORD"]
        ),
        ServiceConfig(
            name="b2",
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.STORAGE,
            timeout_ms=1000,
            fallback="File upload disabled",
            required_env_vars=["B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY"]
        ),
        ServiceConfig(
            name="celery",
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.QUEUE,
            timeout_ms=1000,
            fallback="Processing requests synchronously",
            startup_command="celery -A app.celery_app worker --loglevel=info"
        ),
        ServiceConfig(
            name="anthropic",
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.API,
            timeout_ms=1000,
            fallback="LLM features unavailable",
            required_env_vars=["ANTHROPIC_API_KEY"]
        ),
        ServiceConfig(
            name="llamaindex",
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.SERVICE,
            health_url="https://jb-llamaindex.onrender.com/health",
            timeout_ms=5000,
            fallback="Document parsing disabled"
        ),
        ServiceConfig(
            name="crewai",
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.SERVICE,
            health_url="https://jb-crewai.onrender.com/api/crewai/health",
            timeout_ms=5000,
            fallback="Multi-agent features disabled"
        ),
    ],

    # OPTIONAL (Graceful Degradation)
    optional=[
        ServiceConfig(
            name="arcade",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.API,
            timeout_ms=500,
            fallback="External tools unavailable",
            required_env_vars=["ARCADE_API_KEY"]
        ),
        ServiceConfig(
            name="whisper_local",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.LOCAL,
            timeout_ms=500,
            fallback="Audio transcription disabled"
        ),
        ServiceConfig(
            name="gemini",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.API,
            timeout_ms=500,
            fallback="Vision analysis disabled",
            required_env_vars=["GOOGLE_API_KEY"]
        ),
        ServiceConfig(
            name="ffmpeg",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.LOCAL,
            timeout_ms=500,
            fallback="Video processing unavailable"
        ),
        ServiceConfig(
            name="openai",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.API,
            timeout_ms=500,
            fallback="Fallback LLM unavailable",
            required_env_vars=["OPENAI_API_KEY"]
        ),
        ServiceConfig(
            name="llamacloud",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.API,
            timeout_ms=500,
            fallback="Advanced parsing disabled",
            required_env_vars=["LLAMA_CLOUD_API_KEY"]
        ),
        ServiceConfig(
            name="ollama",
            category=ServiceCategory.OPTIONAL,
            type=ServiceType.LOCAL,
            health_url="http://localhost:11434/api/tags",
            timeout_ms=1000,
            fallback="Using cloud embeddings"
        ),
    ],

    # INFRASTRUCTURE (Monitoring Stack)
    infrastructure=[
        ServiceConfig(
            name="prometheus",
            category=ServiceCategory.INFRASTRUCTURE,
            type=ServiceType.MONITORING,
            health_url="http://localhost:9090/-/healthy",
            timeout_ms=500,
            fallback="Metrics collection disabled"
        ),
        ServiceConfig(
            name="grafana",
            category=ServiceCategory.INFRASTRUCTURE,
            type=ServiceType.MONITORING,
            health_url="http://localhost:3001/api/health",
            timeout_ms=500,
            fallback="Dashboards unavailable"
        ),
        ServiceConfig(
            name="alertmanager",
            category=ServiceCategory.INFRASTRUCTURE,
            type=ServiceType.MONITORING,
            health_url="http://localhost:9093/-/healthy",
            timeout_ms=500,
            fallback="Alerting disabled"
        ),
        ServiceConfig(
            name="node_exporter",
            category=ServiceCategory.INFRASTRUCTURE,
            type=ServiceType.MONITORING,
            timeout_ms=500,
            fallback="System metrics unavailable"
        ),
        ServiceConfig(
            name="flower",
            category=ServiceCategory.INFRASTRUCTURE,
            type=ServiceType.MONITORING,
            health_url="http://localhost:5555/",
            timeout_ms=500,
            fallback="Celery monitoring unavailable"
        ),
    ]
)


# =============================================================================
# GRACEFUL DEGRADATION MATRIX
# =============================================================================

DEGRADATION_RULES: Dict[str, DegradationRule] = {
    "supabase": DegradationRule(
        service_name="supabase",
        impact="CRITICAL - App cannot start",
        fallback_behavior="None - service is required",
        affected_endpoints=["All endpoints"],
        user_message="Service temporarily unavailable. Please try again later."
    ),
    "redis": DegradationRule(
        service_name="redis",
        impact="CRITICAL - App cannot start",
        fallback_behavior="None - service is required",
        affected_endpoints=["All endpoints"],
        user_message="Service temporarily unavailable. Please try again later."
    ),
    "neo4j": DegradationRule(
        service_name="neo4j",
        impact="Graph features disabled",
        fallback_behavior="Log warning, skip graph sync",
        affected_endpoints=["/api/graph/*", "/api/knowledge-graph/*"],
        user_message="Knowledge graph features are temporarily unavailable."
    ),
    "b2": DegradationRule(
        service_name="b2",
        impact="File upload disabled",
        fallback_behavior="Return error on upload attempts",
        affected_endpoints=["/api/v1/upload/*", "/api/documents/upload"],
        user_message="File uploads are temporarily unavailable."
    ),
    "celery": DegradationRule(
        service_name="celery",
        impact="Sync processing only",
        fallback_behavior="Process requests synchronously",
        affected_endpoints=["Background task endpoints"],
        user_message="Processing may be slower than usual."
    ),
    "anthropic": DegradationRule(
        service_name="anthropic",
        impact="LLM features disabled",
        fallback_behavior="Return 'service unavailable'",
        affected_endpoints=["/api/query/*", "/api/chat/*"],
        user_message="AI features are temporarily unavailable."
    ),
    "llamaindex": DegradationRule(
        service_name="llamaindex",
        impact="Document parsing disabled",
        fallback_behavior="Skip indexing, manual upload only",
        affected_endpoints=["/api/llama-index/*"],
        user_message="Document parsing is temporarily unavailable."
    ),
    "crewai": DegradationRule(
        service_name="crewai",
        impact="Multi-agent disabled",
        fallback_behavior="Single-agent fallback",
        affected_endpoints=["/api/crewai/*", "/api/orchestration/*"],
        user_message="Advanced AI workflows are temporarily unavailable."
    ),
    "ollama": DegradationRule(
        service_name="ollama",
        impact="Local embeddings disabled",
        fallback_behavior="Use Anthropic embeddings",
        affected_endpoints=["/api/embeddings/*"],
        user_message="Using cloud-based embeddings instead of local."
    ),
}


# =============================================================================
# SERVICE ORCHESTRATOR
# =============================================================================

class ServiceOrchestrator:
    """
    Central service health and startup orchestration.

    Features:
    - Parallel health checks with asyncio.gather
    - Aggressive timeouts per service category
    - Two-phase startup (required blocking, rest background)
    - Health check caching (30s TTL)
    - Graceful degradation support

    Performance target: App ready in < 3 seconds
    """

    def __init__(
        self,
        inventory: Optional[ServiceInventory] = None,
        cache_ttl: float = 30.0
    ):
        self.inventory = inventory or DEFAULT_SERVICE_INVENTORY
        self.cache_ttl = cache_ttl

        # Health check cache: {service_name: (ServiceHealthCheck, timestamp)}
        self._cache: Dict[str, Tuple[ServiceHealthCheck, float]] = {}

        # HTTP client for health checks
        self._http_client: Optional[httpx.AsyncClient] = None

        # Startup state
        self._startup_phase = StartupPhase.INITIALIZING
        self._startup_time: Optional[float] = None

        # Connection references (set after initialization)
        self._connection_manager = None

        logger.info(
            "Service orchestrator initialized",
            total_services=len(self.inventory.get_all_services()),
            required=len(self.inventory.required),
            important=len(self.inventory.important),
            optional=len(self.inventory.optional),
            infrastructure=len(self.inventory.infrastructure)
        )

    async def initialize(self):
        """Initialize the orchestrator (call during app startup)"""
        self._http_client = httpx.AsyncClient(timeout=10.0)
        self._startup_time = time.time()

        # Get connection manager reference
        from app.core.connections import connection_manager
        self._connection_manager = connection_manager

    async def shutdown(self):
        """Clean up resources (call during app shutdown)"""
        if self._http_client:
            await self._http_client.aclose()

    def _get_cached(self, service_name: str) -> Optional[ServiceHealthCheck]:
        """Get cached health check if still valid"""
        if service_name in self._cache:
            check, timestamp = self._cache[service_name]
            if time.time() - timestamp < self.cache_ttl:
                return check
        return None

    def _set_cached(self, service_name: str, check: ServiceHealthCheck):
        """Cache a health check result"""
        self._cache[service_name] = (check, time.time())

    # =========================================================================
    # INDIVIDUAL SERVICE HEALTH CHECKS
    # =========================================================================

    async def check_supabase(self) -> ServiceHealthCheck:
        """Check Supabase PostgreSQL health"""
        start = time.perf_counter()
        try:
            if self._connection_manager and self._connection_manager.supabase:
                # Use asyncio.to_thread to avoid blocking the event loop
                await asyncio.to_thread(
                    lambda: self._connection_manager.supabase.table("documents").select("id").limit(1).execute()
                )
                latency = (time.perf_counter() - start) * 1000
                return ServiceHealthCheck(
                    name="supabase",
                    status=ServiceStatus.RUNNING,
                    category=ServiceCategory.REQUIRED,
                    type=ServiceType.DATABASE,
                    latency_ms=round(latency, 2),
                    details={"url": os.getenv("SUPABASE_URL", "")[:50]}
                )
            else:
                return ServiceHealthCheck(
                    name="supabase",
                    status=ServiceStatus.STOPPED,
                    category=ServiceCategory.REQUIRED,
                    type=ServiceType.DATABASE,
                    error_message="Supabase client not initialized"
                )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name="supabase",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.REQUIRED,
                type=ServiceType.DATABASE,
                latency_ms=round(latency, 2),
                error_message=str(e)
            )

    async def check_redis(self) -> ServiceHealthCheck:
        """Check Redis health"""
        start = time.perf_counter()
        try:
            if self._connection_manager and self._connection_manager.redis:
                # Use asyncio.to_thread to avoid blocking the event loop
                await asyncio.to_thread(self._connection_manager.redis.ping)
                latency = (time.perf_counter() - start) * 1000
                info = await asyncio.to_thread(self._connection_manager.redis.info, "server")
                return ServiceHealthCheck(
                    name="redis",
                    status=ServiceStatus.RUNNING,
                    category=ServiceCategory.REQUIRED,
                    type=ServiceType.CACHE,
                    latency_ms=round(latency, 2),
                    details={"redis_version": info.get("redis_version", "unknown")}
                )
            else:
                return ServiceHealthCheck(
                    name="redis",
                    status=ServiceStatus.STOPPED,
                    category=ServiceCategory.REQUIRED,
                    type=ServiceType.CACHE,
                    error_message="Redis client not initialized"
                )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name="redis",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.REQUIRED,
                type=ServiceType.CACHE,
                latency_ms=round(latency, 2),
                error_message=str(e)
            )

    async def check_neo4j(self) -> ServiceHealthCheck:
        """Check Neo4j health"""
        start = time.perf_counter()
        config = self.inventory.get_service("neo4j")
        try:
            if self._connection_manager and self._connection_manager.neo4j_driver:
                # Use asyncio.to_thread to avoid blocking the event loop
                await asyncio.to_thread(self._connection_manager.neo4j_driver.verify_connectivity)
                latency = (time.perf_counter() - start) * 1000
                return ServiceHealthCheck(
                    name="neo4j",
                    status=ServiceStatus.RUNNING,
                    category=ServiceCategory.IMPORTANT,
                    type=ServiceType.GRAPH,
                    latency_ms=round(latency, 2),
                    fallback_message=config.fallback if config else None
                )
            else:
                return ServiceHealthCheck(
                    name="neo4j",
                    status=ServiceStatus.STOPPED,
                    category=ServiceCategory.IMPORTANT,
                    type=ServiceType.GRAPH,
                    error_message="Neo4j driver not initialized",
                    fallback_message=config.fallback if config else None
                )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name="neo4j",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.GRAPH,
                latency_ms=round(latency, 2),
                error_message=str(e),
                fallback_message=config.fallback if config else None
            )

    async def check_b2(self) -> ServiceHealthCheck:
        """Check B2 storage health"""
        start = time.perf_counter()
        config = self.inventory.get_service("b2")
        try:
            from app.services.b2_storage import get_b2_service
            b2_service = get_b2_service()
            # Use asyncio.to_thread to avoid blocking the event loop
            await asyncio.to_thread(b2_service.check_connection)
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name="b2",
                status=ServiceStatus.RUNNING,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.STORAGE,
                latency_ms=round(latency, 2),
                fallback_message=config.fallback if config else None
            )
        except ValueError:
            return ServiceHealthCheck(
                name="b2",
                status=ServiceStatus.STOPPED,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.STORAGE,
                error_message="B2 credentials not configured",
                fallback_message=config.fallback if config else None
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name="b2",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.STORAGE,
                latency_ms=round(latency, 2),
                error_message=str(e),
                fallback_message=config.fallback if config else None
            )

    async def check_celery(self) -> ServiceHealthCheck:
        """Check Celery workers health"""
        start = time.perf_counter()
        config = self.inventory.get_service("celery")
        try:
            from app.celery_app import celery_app
            # Use asyncio.to_thread to avoid blocking the event loop
            celery_ping = await asyncio.to_thread(celery_app.control.ping, timeout=2.0)
            latency = (time.perf_counter() - start) * 1000

            if celery_ping:
                worker_count = len(celery_ping)
                return ServiceHealthCheck(
                    name="celery",
                    status=ServiceStatus.RUNNING,
                    category=ServiceCategory.IMPORTANT,
                    type=ServiceType.QUEUE,
                    latency_ms=round(latency, 2),
                    details={"workers": worker_count},
                    fallback_message=config.fallback if config else None
                )
            else:
                return ServiceHealthCheck(
                    name="celery",
                    status=ServiceStatus.DEGRADED,
                    category=ServiceCategory.IMPORTANT,
                    type=ServiceType.QUEUE,
                    latency_ms=round(latency, 2),
                    error_message="No workers responded",
                    fallback_message=config.fallback if config else None
                )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name="celery",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.QUEUE,
                latency_ms=round(latency, 2),
                error_message=str(e),
                fallback_message=config.fallback if config else None
            )

    async def check_anthropic(self) -> ServiceHealthCheck:
        """Check Anthropic API availability (via env var check)"""
        config = self.inventory.get_service("anthropic")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and len(api_key) > 10:
            return ServiceHealthCheck(
                name="anthropic",
                status=ServiceStatus.RUNNING,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.API,
                details={"key_configured": True},
                fallback_message=config.fallback if config else None
            )
        else:
            return ServiceHealthCheck(
                name="anthropic",
                status=ServiceStatus.STOPPED,
                category=ServiceCategory.IMPORTANT,
                type=ServiceType.API,
                error_message="API key not configured",
                fallback_message=config.fallback if config else None
            )

    async def check_http_service(
        self,
        name: str,
        health_url: str,
        category: ServiceCategory,
        timeout: float
    ) -> ServiceHealthCheck:
        """Generic HTTP service health check"""
        config = self.inventory.get_service(name)
        service_type = config.type if config else ServiceType.SERVICE
        start = time.perf_counter()
        try:
            if self._http_client:
                response = await self._http_client.get(health_url, timeout=timeout)
                latency = (time.perf_counter() - start) * 1000

                if response.status_code == 200:
                    return ServiceHealthCheck(
                        name=name,
                        status=ServiceStatus.RUNNING,
                        category=category,
                        type=service_type,
                        latency_ms=round(latency, 2),
                        details={"url": health_url},
                        fallback_message=config.fallback if config else None
                    )
                else:
                    return ServiceHealthCheck(
                        name=name,
                        status=ServiceStatus.ERROR,
                        category=category,
                        type=service_type,
                        latency_ms=round(latency, 2),
                        error_message=f"HTTP {response.status_code}",
                        fallback_message=config.fallback if config else None
                    )
            else:
                return ServiceHealthCheck(
                    name=name,
                    status=ServiceStatus.UNKNOWN,
                    category=category,
                    type=service_type,
                    error_message="HTTP client not initialized",
                    fallback_message=config.fallback if config else None
                )
        except httpx.TimeoutException:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name=name,
                status=ServiceStatus.ERROR,
                category=category,
                type=service_type,
                latency_ms=round(latency, 2),
                error_message="Timeout",
                fallback_message=config.fallback if config else None
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealthCheck(
                name=name,
                status=ServiceStatus.ERROR,
                category=category,
                type=service_type,
                latency_ms=round(latency, 2),
                error_message=str(e),
                fallback_message=config.fallback if config else None
            )

    async def check_env_service(
        self,
        name: str,
        category: ServiceCategory,
        service_type: ServiceType,
        env_vars: List[str]
    ) -> ServiceHealthCheck:
        """Check service by verifying environment variables are set"""
        config = self.inventory.get_service(name)
        missing = [var for var in env_vars if not os.getenv(var)]

        if not missing:
            return ServiceHealthCheck(
                name=name,
                status=ServiceStatus.RUNNING,
                category=category,
                type=service_type,
                details={"env_vars_configured": True},
                fallback_message=config.fallback if config else None
            )
        else:
            return ServiceHealthCheck(
                name=name,
                status=ServiceStatus.STOPPED,
                category=category,
                type=service_type,
                error_message=f"Missing env vars: {', '.join(missing)}",
                fallback_message=config.fallback if config else None
            )

    async def check_ollama(self) -> ServiceHealthCheck:
        """Check Ollama local service"""
        return await self.check_http_service(
            name="ollama",
            health_url="http://localhost:11434/api/tags",
            category=ServiceCategory.OPTIONAL,
            timeout=1.0
        )

    async def check_ffmpeg(self) -> ServiceHealthCheck:
        """Check if ffmpeg is available locally"""
        config = self.inventory.get_service("ffmpeg")
        try:
            import shutil
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                return ServiceHealthCheck(
                    name="ffmpeg",
                    status=ServiceStatus.RUNNING,
                    category=ServiceCategory.OPTIONAL,
                    type=ServiceType.LOCAL,
                    details={"path": ffmpeg_path},
                    fallback_message=config.fallback if config else None
                )
            else:
                return ServiceHealthCheck(
                    name="ffmpeg",
                    status=ServiceStatus.STOPPED,
                    category=ServiceCategory.OPTIONAL,
                    type=ServiceType.LOCAL,
                    error_message="ffmpeg not found in PATH",
                    fallback_message=config.fallback if config else None
                )
        except Exception as e:
            return ServiceHealthCheck(
                name="ffmpeg",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.OPTIONAL,
                type=ServiceType.LOCAL,
                error_message=str(e),
                fallback_message=config.fallback if config else None
            )

    # =========================================================================
    # AGGREGATED HEALTH CHECKS
    # =========================================================================

    async def check_service(self, service_name: str, use_cache: bool = True) -> ServiceHealthCheck:
        """
        Check a single service by name.

        Args:
            service_name: Name of the service to check
            use_cache: Whether to use cached results

        Returns:
            ServiceHealthCheck result
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached(service_name)
            if cached:
                return cached

        # Dispatch to appropriate checker
        checkers: Dict[str, Callable[[], Coroutine[Any, Any, ServiceHealthCheck]]] = {
            "supabase": self.check_supabase,
            "redis": self.check_redis,
            "neo4j": self.check_neo4j,
            "b2": self.check_b2,
            "celery": self.check_celery,
            "anthropic": self.check_anthropic,
            "llamaindex": lambda: self.check_http_service(
                "llamaindex",
                os.getenv("LLAMAINDEX_SERVICE_URL", "https://jb-llamaindex.onrender.com") + "/health",
                ServiceCategory.IMPORTANT,
                5.0
            ),
            "crewai": lambda: self.check_http_service(
                "crewai",
                os.getenv("CREWAI_SERVICE_URL", "https://jb-crewai.onrender.com") + "/api/crewai/health",
                ServiceCategory.IMPORTANT,
                5.0
            ),
            "ollama": self.check_ollama,
            "ffmpeg": self.check_ffmpeg,
            "arcade": lambda: self.check_env_service(
                "arcade", ServiceCategory.OPTIONAL, ServiceType.API, ["ARCADE_API_KEY"]
            ),
            "whisper_local": self.check_ffmpeg,  # Uses same local binary check pattern
            "gemini": lambda: self.check_env_service(
                "gemini", ServiceCategory.OPTIONAL, ServiceType.API, ["GOOGLE_API_KEY"]
            ),
            "openai": lambda: self.check_env_service(
                "openai", ServiceCategory.OPTIONAL, ServiceType.API, ["OPENAI_API_KEY"]
            ),
            "llamacloud": lambda: self.check_env_service(
                "llamacloud", ServiceCategory.OPTIONAL, ServiceType.API, ["LLAMA_CLOUD_API_KEY"]
            ),
            "prometheus": lambda: self.check_http_service(
                "prometheus", "http://localhost:9090/-/healthy",
                ServiceCategory.INFRASTRUCTURE, 0.5
            ),
            "grafana": lambda: self.check_http_service(
                "grafana", "http://localhost:3001/api/health",
                ServiceCategory.INFRASTRUCTURE, 0.5
            ),
            "alertmanager": lambda: self.check_http_service(
                "alertmanager", "http://localhost:9093/-/healthy",
                ServiceCategory.INFRASTRUCTURE, 0.5
            ),
            "flower": lambda: self.check_http_service(
                "flower", "http://localhost:5555/",
                ServiceCategory.INFRASTRUCTURE, 0.5
            ),
        }

        checker = checkers.get(service_name)
        if checker:
            result = await checker()
        else:
            # No checker - use inventory config if available
            config = self.inventory.get_service(service_name)
            if config:
                result = ServiceHealthCheck(
                    name=service_name,
                    status=ServiceStatus.UNKNOWN,
                    category=config.category,
                    type=config.type,
                    error_message="No health checker configured",
                    fallback_message=config.fallback,
                )
            else:
                result = ServiceHealthCheck(
                    name=service_name,
                    status=ServiceStatus.UNKNOWN,
                    category=ServiceCategory.OPTIONAL,
                    type=ServiceType.SERVICE,
                    error_message=f"Unknown service: {service_name}"
                )

        # Cache result and update metrics
        self._set_cached(service_name, result)
        SERVICE_HEALTH_STATUS.labels(
            service=service_name,
            category=result.category.value
        ).set(1 if result.status == ServiceStatus.RUNNING else 0)

        if result.latency_ms:
            SERVICE_CHECK_LATENCY.labels(service=service_name).observe(result.latency_ms)

        return result

    async def check_required_services(self) -> Tuple[bool, Dict[str, ServiceHealthCheck]]:
        """
        Check all required services in parallel.

        Returns:
            Tuple of (all_healthy, results_dict)
        """
        start = time.perf_counter()
        self._startup_phase = StartupPhase.CHECKING_REQUIRED

        tasks = [
            self.check_service(svc.name, use_cache=False)
            for svc in self.inventory.required
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        results_dict = {}
        all_healthy = True

        for i, result in enumerate(results):
            service_name = self.inventory.required[i].name
            if isinstance(result, Exception):
                results_dict[service_name] = ServiceHealthCheck(
                    name=service_name,
                    status=ServiceStatus.ERROR,
                    category=ServiceCategory.REQUIRED,
                    type=ServiceType.SERVICE,
                    error_message=str(result)
                )
                all_healthy = False
            else:
                results_dict[service_name] = result
                if result.status != ServiceStatus.RUNNING:
                    all_healthy = False

        duration = time.perf_counter() - start
        PREFLIGHT_CHECK_DURATION.labels(phase="required").observe(duration)

        return all_healthy, results_dict

    async def check_important_services(self) -> Dict[str, ServiceHealthCheck]:
        """Check all important services in parallel."""
        start = time.perf_counter()
        self._startup_phase = StartupPhase.CHECKING_IMPORTANT

        tasks = [
            self.check_service(svc.name, use_cache=False)
            for svc in self.inventory.important
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        results_dict = {}
        for i, result in enumerate(results):
            service_name = self.inventory.important[i].name
            if isinstance(result, Exception):
                results_dict[service_name] = ServiceHealthCheck(
                    name=service_name,
                    status=ServiceStatus.ERROR,
                    category=ServiceCategory.IMPORTANT,
                    type=ServiceType.SERVICE,
                    error_message=str(result)
                )
            else:
                results_dict[service_name] = result

        duration = time.perf_counter() - start
        PREFLIGHT_CHECK_DURATION.labels(phase="important").observe(duration)

        return results_dict

    async def check_optional_services(self) -> Dict[str, ServiceHealthCheck]:
        """Check all optional services in parallel."""
        start = time.perf_counter()
        self._startup_phase = StartupPhase.CHECKING_OPTIONAL

        tasks = [
            self.check_service(svc.name, use_cache=False)
            for svc in self.inventory.optional
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        results_dict = {}
        for i, result in enumerate(results):
            service_name = self.inventory.optional[i].name
            if isinstance(result, Exception):
                results_dict[service_name] = ServiceHealthCheck(
                    name=service_name,
                    status=ServiceStatus.ERROR,
                    category=ServiceCategory.OPTIONAL,
                    type=ServiceType.SERVICE,
                    error_message=str(result)
                )
            else:
                results_dict[service_name] = result

        duration = time.perf_counter() - start
        PREFLIGHT_CHECK_DURATION.labels(phase="optional").observe(duration)

        return results_dict

    async def check_infrastructure_services(self) -> Dict[str, ServiceHealthCheck]:
        """Check all infrastructure services in parallel."""
        tasks = [
            self.check_service(svc.name, use_cache=False)
            for svc in self.inventory.infrastructure
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        results_dict = {}
        for i, result in enumerate(results):
            service_name = self.inventory.infrastructure[i].name
            if isinstance(result, Exception):
                results_dict[service_name] = ServiceHealthCheck(
                    name=service_name,
                    status=ServiceStatus.ERROR,
                    category=ServiceCategory.INFRASTRUCTURE,
                    type=ServiceType.MONITORING,
                    error_message=str(result)
                )
            else:
                results_dict[service_name] = result

        return results_dict

    async def check_all_services(self) -> PreflightResult:
        """
        Run complete preflight check on all 23 services.

        Uses parallel health checks with asyncio.gather for performance.
        Total time = slowest single check, not sum of all checks.

        Returns:
            PreflightResult with all service statuses
        """
        start = time.perf_counter()
        all_services: Dict[str, ServiceHealthCheck] = {}
        warnings: List[str] = []
        errors: List[str] = []
        degraded_features: List[str] = []

        # Phase 1: Check required services (blocking)
        required_ok, required_results = await self.check_required_services()
        all_services.update(required_results)

        if not required_ok:
            for name, check in required_results.items():
                if check.status != ServiceStatus.RUNNING:
                    errors.append(f"Required service '{name}' is {check.status.value}: {check.error_message}")

        # Phase 2: Check important services (can continue if some fail)
        important_results = await self.check_important_services()
        all_services.update(important_results)

        important_ok = True
        for name, check in important_results.items():
            if check.status != ServiceStatus.RUNNING:
                important_ok = False
                warnings.append(f"Important service '{name}' is {check.status.value}")
                if check.fallback_message:
                    degraded_features.append(check.fallback_message)

        # Phase 3: Check optional services (no blocking)
        optional_results = await self.check_optional_services()
        all_services.update(optional_results)

        for check in optional_results.values():
            if check.status != ServiceStatus.RUNNING and check.fallback_message:
                degraded_features.append(check.fallback_message)

        # Phase 4: Check infrastructure services (no blocking)
        infra_results = await self.check_infrastructure_services()
        all_services.update(infra_results)

        # Calculate total time
        total_time_ms = (time.perf_counter() - start) * 1000

        self._startup_phase = StartupPhase.READY if required_ok else StartupPhase.FAILED

        return PreflightResult(
            ready=required_ok,
            all_required_healthy=required_ok,
            all_important_healthy=important_ok,
            services=all_services,
            startup_time_ms=round(total_time_ms, 2),
            degraded_features=degraded_features,
            warnings=warnings,
            errors=errors
        )

    def get_startup_progress(self) -> StartupProgress:
        """Get current startup progress"""
        phase_progress = {
            StartupPhase.INITIALIZING: 0,
            StartupPhase.CHECKING_REQUIRED: 25,
            StartupPhase.CHECKING_IMPORTANT: 50,
            StartupPhase.CHECKING_OPTIONAL: 75,
            StartupPhase.STARTING_SERVICES: 90,
            StartupPhase.READY: 100,
            StartupPhase.FAILED: 100,
        }

        elapsed = (time.time() - self._startup_time) * 1000 if self._startup_time else 0

        return StartupProgress(
            phase=self._startup_phase,
            progress_percent=phase_progress.get(self._startup_phase, 0),
            message=f"Phase: {self._startup_phase.value}",
            elapsed_ms=round(elapsed, 2)
        )

    def get_degradation_rule(self, service_name: str) -> Optional[DegradationRule]:
        """Get degradation rule for a service"""
        return DEGRADATION_RULES.get(service_name)

    def get_timeout(self, service_name: str) -> int:
        """
        Get timeout in milliseconds for a service based on its category.

        Timeout values by category:
        - Required services: 2000ms (must verify before proceeding)
        - Important services: 5000ms (quick check, fail fast - but allow more time for remote)
        - Optional services: 1000ms (non-blocking, skip if slow)
        - Infrastructure: 500ms (nice to have, not critical)

        Args:
            service_name: Name of the service

        Returns:
            Timeout in milliseconds
        """
        config = self.inventory.get_service(service_name)
        if config:
            return config.timeout_ms

        # Default timeouts by category if service not in inventory
        # Use the category-based defaults from the plan
        required_services = ["supabase", "redis"]
        important_services = ["neo4j", "b2", "celery", "anthropic", "llamaindex", "crewai"]
        optional_services = ["arcade", "whisper_local", "gemini", "ffmpeg", "openai", "llamacloud", "ollama"]

        if service_name in required_services:
            return 2000
        elif service_name in important_services:
            return 5000
        elif service_name in optional_services:
            return 1000
        else:
            return 500  # Infrastructure or unknown

    def get_fallback_message(self, service_name: str) -> Optional[str]:
        """
        Get the fallback/degradation message for a service.

        Args:
            service_name: Name of the service

        Returns:
            Fallback message describing what happens when service is unavailable,
            or None if service is required and has no fallback.
        """
        config = self.inventory.get_service(service_name)
        if config and config.fallback:
            return config.fallback

        # Check degradation rules as backup
        rule = DEGRADATION_RULES.get(service_name)
        if rule:
            return rule.fallback_behavior

        return None

    async def start_service(self, service_name: str) -> bool:
        """
        Start a locally manageable service (Docker containers, local processes).

        Cloud services (Supabase, Upstash, Render services) cannot be started
        locally and will return True without attempting to start.

        Args:
            service_name: Name of the service to start

        Returns:
            True if service was started successfully or is a cloud service,
            False if startup failed
        """
        import asyncio

        config = self.inventory.get_service(service_name)

        # Cloud services - nothing to do locally
        cloud_services = ["supabase", "redis", "llamaindex", "crewai", "anthropic",
                         "arcade", "gemini", "openai", "llamacloud"]
        if service_name in cloud_services:
            logger.info("Service is cloud-based, skipping local start", service=service_name)
            return True

        # Check if we have a startup command
        if not config or not config.startup_command:
            logger.warning("No startup command configured", service=service_name)
            return False

        try:
            # Parse and execute the startup command (non-blocking for long-running services)
            cmd_parts = config.startup_command.split()
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            # Brief sleep to allow process to start or fail immediately
            await asyncio.sleep(0.5)

            # Check if process failed immediately (returncode is None if still running)
            if process.returncode is not None and process.returncode != 0:
                logger.error("Failed to start service",
                            service=service_name,
                            returncode=process.returncode)
                return False

            logger.info("Successfully started service", service=service_name)
            return True

        except Exception as e:
            logger.exception("Error starting service", service=service_name, error=str(e))
            return False

    def clear_cache(self):
        """Clear all cached health checks"""
        self._cache.clear()


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_orchestrator: Optional[ServiceOrchestrator] = None


def get_service_orchestrator() -> ServiceOrchestrator:
    """Get the global service orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ServiceOrchestrator()
    return _orchestrator


async def initialize_orchestrator():
    """Initialize the global orchestrator (call during app startup)"""
    orchestrator = get_service_orchestrator()
    await orchestrator.initialize()
    return orchestrator


async def shutdown_orchestrator():
    """Shutdown the global orchestrator (call during app shutdown)"""
    orchestrator = get_service_orchestrator()
    await orchestrator.shutdown()
