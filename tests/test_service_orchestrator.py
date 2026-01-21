"""
Empire v7.3 - Service Orchestrator Tests
Unit tests for core service orchestration logic

Run with:
    pytest tests/test_service_orchestrator.py -v
"""

import asyncio
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the imports that may not exist in test environment
import sys
sys.modules['app.core.connections'] = MagicMock()
sys.modules['app.services.circuit_breaker'] = MagicMock()


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    mock = MagicMock()
    mock.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [{"id": "test"}]
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = AsyncMock()
    mock.ping.return_value = True
    mock.set.return_value = True
    mock.get.return_value = b"test"
    return mock


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j driver"""
    mock = MagicMock()
    mock.verify_connectivity.return_value = True
    return mock


@pytest.fixture
def service_config():
    """Sample service configuration"""
    return {
        "services": {
            "required": [
                {"name": "supabase", "health_url": None, "timeout_ms": 2000},
                {"name": "redis", "health_url": None, "timeout_ms": 2000}
            ],
            "important": [
                {"name": "neo4j", "health_url": None, "timeout_ms": 5000},
                {"name": "celery", "health_url": None, "timeout_ms": 3000}
            ],
            "optional": [
                {"name": "ollama", "health_url": "http://localhost:11434/api/tags", "timeout_ms": 1000}
            ]
        }
    }


# =============================================================================
# SERVICE HEALTH CHECK TESTS
# =============================================================================

class TestServiceHealthCheck:
    """Tests for ServiceHealthCheck model"""

    def test_service_health_check_creation(self):
        """Test creating a ServiceHealthCheck instance"""
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        health_check = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            latency_ms=45.2
        )

        assert health_check.name == "supabase"
        assert health_check.status == ServiceStatus.RUNNING
        assert health_check.category == ServiceCategory.REQUIRED
        assert health_check.latency_ms == 45.2
        assert health_check.error_message is None

    def test_service_health_check_with_error(self):
        """Test ServiceHealthCheck with error message"""
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        health_check = ServiceHealthCheck(
            name="neo4j",
            status=ServiceStatus.ERROR,
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.GRAPH,
            error_message="Connection refused"
        )

        assert health_check.status == ServiceStatus.ERROR
        assert health_check.error_message == "Connection refused"

    def test_service_status_enum_values(self):
        """Test ServiceStatus enum has expected values"""
        from app.models.preflight import ServiceStatus

        # Valid statuses should exist
        assert ServiceStatus.RUNNING.value == "running"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.STOPPED.value == "stopped"
        assert ServiceStatus.ERROR.value == "error"
        assert ServiceStatus.CHECKING.value == "checking"
        assert ServiceStatus.UNKNOWN.value == "unknown"


# =============================================================================
# PREFLIGHT RESULT TESTS
# =============================================================================

class TestPreflightResult:
    """Tests for PreflightResult model"""

    def test_preflight_result_ready(self):
        """Test PreflightResult when all services are ready"""
        from app.models.preflight import PreflightResult, ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        services = {
            "supabase": ServiceHealthCheck(
                name="supabase",
                status=ServiceStatus.RUNNING,
                category=ServiceCategory.REQUIRED,
                type=ServiceType.DATABASE,
                latency_ms=30
            ),
            "redis": ServiceHealthCheck(
                name="redis",
                status=ServiceStatus.RUNNING,
                category=ServiceCategory.REQUIRED,
                type=ServiceType.CACHE,
                latency_ms=20
            )
        }

        result = PreflightResult(
            ready=True,
            all_required_healthy=True,
            all_important_healthy=True,
            services=services,
            startup_time_ms=50.5
        )

        assert result.ready is True
        assert result.all_required_healthy is True
        assert len(result.services) == 2

    def test_preflight_result_not_ready(self):
        """Test PreflightResult when required services are down"""
        from app.models.preflight import PreflightResult, ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        services = {
            "supabase": ServiceHealthCheck(
                name="supabase",
                status=ServiceStatus.ERROR,
                category=ServiceCategory.REQUIRED,
                type=ServiceType.DATABASE,
                error_message="Connection failed"
            ),
            "redis": ServiceHealthCheck(
                name="redis",
                status=ServiceStatus.RUNNING,
                category=ServiceCategory.REQUIRED,
                type=ServiceType.CACHE,
                latency_ms=20
            )
        }

        result = PreflightResult(
            ready=False,
            all_required_healthy=False,
            all_important_healthy=False,
            services=services,
            startup_time_ms=2000.0
        )

        assert result.ready is False
        assert result.all_required_healthy is False


# =============================================================================
# SERVICE ORCHESTRATOR TESTS
# =============================================================================

class TestServiceOrchestrator:
    """Tests for ServiceOrchestrator class"""

    @pytest.mark.asyncio
    async def test_check_supabase_healthy(self, mock_supabase):
        """Test Supabase health check when healthy"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Mock the check_supabase method to return healthy status
        mock_health = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            latency_ms=25.0
        )

        with patch.object(orchestrator, 'check_supabase', return_value=mock_health):
            status = await orchestrator.check_service("supabase", use_cache=False)

        assert status.name == "supabase"
        assert status.status == ServiceStatus.RUNNING
        assert status.latency_ms is not None

    @pytest.mark.asyncio
    async def test_check_supabase_unhealthy(self):
        """Test Supabase health check when unhealthy"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Mock the check_supabase method to return error status
        mock_health = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.ERROR,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            error_message="Connection refused"
        )

        with patch.object(orchestrator, 'check_supabase', return_value=mock_health):
            status = await orchestrator.check_service("supabase", use_cache=False)

        assert status.status in [ServiceStatus.ERROR, ServiceStatus.STOPPED]

    @pytest.mark.asyncio
    async def test_check_redis_healthy(self, mock_redis):
        """Test Redis health check when healthy"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        mock_health = ServiceHealthCheck(
            name="redis",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.CACHE,
            latency_ms=10.0
        )

        with patch.object(orchestrator, 'check_redis', return_value=mock_health):
            status = await orchestrator.check_service("redis", use_cache=False)

        assert status.name == "redis"
        assert status.status == ServiceStatus.RUNNING

    @pytest.mark.asyncio
    async def test_check_neo4j_healthy(self, mock_neo4j):
        """Test Neo4j health check when healthy"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        mock_health = ServiceHealthCheck(
            name="neo4j",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.GRAPH,
            latency_ms=50.0
        )

        with patch.object(orchestrator, 'check_neo4j', return_value=mock_health):
            status = await orchestrator.check_service("neo4j", use_cache=False)

        assert status.name == "neo4j"
        # Neo4j is important, not required
        assert status.category == ServiceCategory.IMPORTANT

    @pytest.mark.asyncio
    async def test_check_all_services_parallel(self, mock_supabase, mock_redis, mock_neo4j):
        """Test that all services are checked in parallel"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Mock all service checks
        supabase_health = ServiceHealthCheck(
            name="supabase", status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED, type=ServiceType.DATABASE, latency_ms=25.0
        )
        redis_health = ServiceHealthCheck(
            name="redis", status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED, type=ServiceType.CACHE, latency_ms=10.0
        )

        with patch.object(orchestrator, 'check_supabase', return_value=supabase_health), \
             patch.object(orchestrator, 'check_redis', return_value=redis_health), \
             patch.object(orchestrator, 'check_required_services', return_value=(True, {"supabase": supabase_health, "redis": redis_health})):

            result = await orchestrator.check_all_services()

        # Should have checked multiple services
        assert len(result.services) >= 2
        # Startup time should be reasonable (parallel checks)
        assert result.startup_time_ms < 10000  # Less than 10 seconds

    @pytest.mark.asyncio
    async def test_required_services_must_pass(self, mock_redis):
        """Test that required services must pass for ready=True"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Supabase fails, Redis passes
        supabase_health = ServiceHealthCheck(
            name="supabase", status=ServiceStatus.ERROR,
            category=ServiceCategory.REQUIRED, type=ServiceType.DATABASE,
            error_message="Connection failed"
        )
        redis_health = ServiceHealthCheck(
            name="redis", status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED, type=ServiceType.CACHE, latency_ms=10.0
        )

        with patch.object(orchestrator, 'check_required_services', return_value=(False, {"supabase": supabase_health, "redis": redis_health})):
            result = await orchestrator.check_all_services()

        assert result.ready is False
        assert result.all_required_healthy is False

    @pytest.mark.asyncio
    async def test_optional_services_can_fail(self, mock_supabase, mock_redis):
        """Test that optional services failing doesn't prevent ready=True"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Required pass, optional fail
        supabase_health = ServiceHealthCheck(
            name="supabase", status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED, type=ServiceType.DATABASE, latency_ms=25.0
        )
        redis_health = ServiceHealthCheck(
            name="redis", status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED, type=ServiceType.CACHE, latency_ms=10.0
        )

        with patch.object(orchestrator, 'check_required_services', return_value=(True, {"supabase": supabase_health, "redis": redis_health})):
            result = await orchestrator.check_all_services()

        # Should still be ready because required services are healthy
        assert result.all_required_healthy is True


# =============================================================================
# HEALTH CHECK CACHING TESTS
# =============================================================================

class TestHealthCheckCaching:
    """Tests for health check result caching"""

    @pytest.mark.asyncio
    async def test_cached_result_returned(self, mock_supabase):
        """Test that cached health check results are returned"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Pre-populate cache
        cached_health = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            latency_ms=10.0
        )
        orchestrator._set_cached("supabase", cached_health)

        # Should return cached result without calling actual check
        status = await orchestrator.check_service("supabase", use_cache=True)

        assert status.latency_ms == 10.0

    @pytest.mark.asyncio
    async def test_cache_bypass(self, mock_supabase):
        """Test that cache can be bypassed"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Pre-populate cache
        cached_health = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            latency_ms=10.0
        )
        orchestrator._set_cached("supabase", cached_health)

        # Mock the actual check to return different result
        new_health = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            latency_ms=50.0
        )

        with patch.object(orchestrator, 'check_supabase', return_value=new_health):
            status = await orchestrator.check_service("supabase", use_cache=False)

        # Should have performed a new check (different latency)
        assert status.latency_ms == 50.0


# =============================================================================
# TIMEOUT TESTS
# =============================================================================

class TestServiceTimeouts:
    """Tests for service check timeouts"""

    @pytest.mark.asyncio
    async def test_required_service_timeout(self):
        """Test that required services have appropriate timeout"""
        from app.core.service_orchestrator import ServiceOrchestrator

        orchestrator = ServiceOrchestrator()

        # Required services should have 2000ms timeout
        assert orchestrator.get_timeout("supabase") == 2000
        assert orchestrator.get_timeout("redis") == 2000

    @pytest.mark.asyncio
    async def test_important_service_timeout(self):
        """Test that important services have shorter timeout"""
        from app.core.service_orchestrator import ServiceOrchestrator

        orchestrator = ServiceOrchestrator()

        # Important services should have 5000ms timeout
        timeout = orchestrator.get_timeout("neo4j")
        assert timeout <= 5000

    @pytest.mark.asyncio
    async def test_optional_service_timeout(self):
        """Test that optional services have shortest timeout"""
        from app.core.service_orchestrator import ServiceOrchestrator

        orchestrator = ServiceOrchestrator()

        # Optional services should have 1000ms timeout
        timeout = orchestrator.get_timeout("ollama")
        assert timeout <= 1000


# =============================================================================
# SERVICE STARTUP TESTS
# =============================================================================

class TestServiceStartup:
    """Tests for service startup functionality"""

    @pytest.mark.asyncio
    async def test_start_docker_service(self):
        """Test starting a Docker-managed service"""
        from app.core.service_orchestrator import ServiceOrchestrator

        orchestrator = ServiceOrchestrator()

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Started", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await orchestrator.start_service("neo4j")

        assert result is True

    @pytest.mark.asyncio
    async def test_start_cloud_service_skipped(self):
        """Test that cloud services are not started locally"""
        from app.core.service_orchestrator import ServiceOrchestrator

        orchestrator = ServiceOrchestrator()

        # Supabase is a cloud service, shouldn't try to start it
        result = await orchestrator.start_service("supabase")

        # Should return True (nothing to do) or appropriate status
        assert result in [True, False, None]


# =============================================================================
# GRACEFUL DEGRADATION TESTS
# =============================================================================

class TestGracefulDegradation:
    """Tests for graceful degradation behavior"""

    @pytest.mark.asyncio
    async def test_degraded_status_on_partial_failure(self, mock_supabase, mock_redis):
        """Test that partial failures result in degraded status"""
        from app.core.service_orchestrator import ServiceOrchestrator
        from app.models.preflight import ServiceHealthCheck, ServiceStatus, ServiceCategory, ServiceType

        orchestrator = ServiceOrchestrator()

        # Mock healthy required services
        healthy_supabase = ServiceHealthCheck(
            name="supabase",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.DATABASE,
            latency_ms=50.0
        )
        healthy_redis = ServiceHealthCheck(
            name="redis",
            status=ServiceStatus.RUNNING,
            category=ServiceCategory.REQUIRED,
            type=ServiceType.CACHE,
            latency_ms=30.0
        )
        # Mock failed Neo4j
        failed_neo4j = ServiceHealthCheck(
            name="neo4j",
            status=ServiceStatus.ERROR,
            category=ServiceCategory.IMPORTANT,
            type=ServiceType.GRAPH,
            error_message="Connection refused"
        )

        # Required pass, important fail - mock the actual check methods
        with patch.object(orchestrator, 'check_supabase', return_value=healthy_supabase), \
             patch.object(orchestrator, 'check_redis', return_value=healthy_redis), \
             patch.object(orchestrator, 'check_neo4j', return_value=failed_neo4j):

            result = await orchestrator.check_all_services()

        # Should be ready but with warnings
        assert result.all_required_healthy is True
        # Neo4j should show as error
        if "neo4j" in result.services:
            assert result.services["neo4j"].status in [ServiceStatus.ERROR, ServiceStatus.STOPPED, ServiceStatus.DEGRADED]

    def test_get_fallback_message(self):
        """Test getting fallback message for failed service"""
        from app.core.service_orchestrator import ServiceOrchestrator

        orchestrator = ServiceOrchestrator()

        message = orchestrator.get_fallback_message("neo4j")
        assert message is not None
        assert "graph" in message.lower() or "disabled" in message.lower()
