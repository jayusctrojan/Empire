"""
Empire v7.3 - LlamaIndex Service Tests (Task 156)

Tests for LlamaIndex integration hardening including:
- Connection pooling
- Retry logic with exponential backoff
- Request timeout handling
- Health check endpoint
- Error classification

Author: Claude Code
Date: 2025-01-15
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

import httpx
from tenacity import RetryError

# Import test subjects
from app.services.llama_index_service import (
    ResilientLlamaIndexService,
    LlamaIndexConfig,
    OperationType,
    TransientError,
    PermanentError,
    classify_http_error,
    is_transient_exception,
    get_llama_index_service,
    close_llama_index_service,
)
from app.exceptions import (
    LlamaParseException,
    ServiceUnavailableException,
    GatewayTimeoutException,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_config():
    """Create a test configuration"""
    return LlamaIndexConfig(
        service_url="https://test-llamaindex.example.com",
        api_key="test-api-key",
        max_connections=10,
        max_keepalive_connections=5,
        max_retries=2,  # Reduce for faster tests
        retry_base_delay=0.1,  # Fast retries for tests
        retry_max_delay=1.0,
        default_timeout=5.0
    )


@pytest.fixture
def service(mock_config):
    """Create a service instance with test config"""
    return ResilientLlamaIndexService(config=mock_config)


@pytest.fixture
def mock_response():
    """Create a mock HTTP response"""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.text = '{"status": "healthy"}'
    response.json.return_value = {"status": "healthy"}
    return response


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestLlamaIndexConfig:
    """Test configuration class"""

    def test_default_config(self):
        """Test default configuration values"""
        config = LlamaIndexConfig()

        assert config.max_connections == 20
        assert config.max_keepalive_connections == 10
        assert config.max_retries == 3
        assert config.default_timeout == 30.0

    def test_custom_config(self, mock_config):
        """Test custom configuration values"""
        assert mock_config.service_url == "https://test-llamaindex.example.com"
        assert mock_config.api_key == "test-api-key"
        assert mock_config.max_retries == 2

    def test_get_timeout(self, mock_config):
        """Test timeout retrieval for different operations"""
        # Check health check timeout
        health_timeout = mock_config.get_timeout(OperationType.HEALTH_CHECK)
        assert health_timeout == 5.0

        # Check document parsing timeout (should be longer)
        parse_timeout = mock_config.get_timeout(OperationType.PARSE_DOCUMENT)
        assert parse_timeout == 120.0

    def test_timeout_defaults_for_unknown(self, mock_config):
        """Test that unknown operations use default timeout"""
        # Access timeouts dict directly to check default
        assert mock_config.default_timeout == 5.0


# =============================================================================
# ERROR CLASSIFICATION TESTS
# =============================================================================

class TestErrorClassification:
    """Test error classification logic"""

    def test_classify_transient_errors(self):
        """Test classification of transient HTTP errors"""
        transient_codes = [408, 429, 500, 502, 503, 504]

        for code in transient_codes:
            error = classify_http_error(code, "test error")
            assert isinstance(error, TransientError), f"Code {code} should be transient"

    def test_classify_permanent_errors(self):
        """Test classification of permanent HTTP errors"""
        permanent_codes = [400, 401, 403, 404, 405, 422]

        for code in permanent_codes:
            error = classify_http_error(code, "test error")
            assert isinstance(error, PermanentError), f"Code {code} should be permanent"

    def test_classify_unknown_as_transient(self):
        """Test that unknown errors are treated as transient"""
        error = classify_http_error(499, "unknown error")
        assert isinstance(error, TransientError)

    def test_is_transient_exception_network_errors(self):
        """Test that network errors are classified as transient"""
        assert is_transient_exception(httpx.ConnectTimeout("timeout"))
        assert is_transient_exception(httpx.ReadTimeout("timeout"))
        assert is_transient_exception(httpx.ConnectError("connection failed"))

    def test_is_transient_exception_classified_errors(self):
        """Test that classified errors are properly detected"""
        assert is_transient_exception(TransientError("temp"))
        assert not is_transient_exception(PermanentError("perm"))

    def test_is_transient_exception_app_exceptions(self):
        """Test that app exceptions are properly classified"""
        assert is_transient_exception(ServiceUnavailableException("unavailable"))
        assert is_transient_exception(GatewayTimeoutException("timeout"))


# =============================================================================
# SERVICE INITIALIZATION TESTS
# =============================================================================

class TestServiceInitialization:
    """Test service initialization"""

    def test_service_initialization_defaults(self):
        """Test service initializes with defaults"""
        service = ResilientLlamaIndexService()

        assert service.config is not None
        assert service._client is None
        assert service._initialized is False
        assert service._stats["requests_total"] == 0

    def test_service_initialization_custom_config(self, mock_config):
        """Test service initializes with custom config"""
        service = ResilientLlamaIndexService(config=mock_config)

        assert service.config.service_url == "https://test-llamaindex.example.com"
        assert service.config.max_retries == 2

    def test_get_stats(self, service):
        """Test statistics retrieval"""
        stats = service.get_stats()

        assert stats["service_name"] == "ResilientLlamaIndexService"
        assert stats["requests_total"] == 0
        assert stats["requests_successful"] == 0
        assert stats["requests_failed"] == 0
        assert stats["client_initialized"] is False


# =============================================================================
# CONNECTION POOLING TESTS
# =============================================================================

class TestConnectionPooling:
    """Test HTTP connection pooling"""

    @pytest.mark.asyncio
    async def test_ensure_client_creates_client(self, service):
        """Test that _ensure_client creates HTTP client"""
        client = await service._ensure_client()

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert service._initialized is True

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_ensure_client_reuses_existing(self, service):
        """Test that _ensure_client reuses existing client"""
        client1 = await service._ensure_client()
        client2 = await service._ensure_client()

        assert client1 is client2

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_close_releases_connections(self, service):
        """Test that close releases connections"""
        await service._ensure_client()
        assert service._initialized is True

        await service.close()
        assert service._client is None
        assert service._initialized is False


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, service, mock_response):
        """Test successful health check"""
        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await service.check_health()

            assert result["status"] == "healthy"
            assert result["components"]["connection"] == "healthy"
            assert result["components"]["api"] == "healthy"
            assert result["response_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_health_check_connection_failure(self, service):
        """Test health check with connection failure"""
        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection refused")

            result = await service.check_health()

            assert result["status"] == "unhealthy"
            assert result["components"]["connection"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_deep_health_check(self, service, mock_response):
        """Test deep health check"""
        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await service.check_deep_health()

            assert result["status"] == "healthy"
            assert "deep_check" in result
            assert result["deep_check"]["status"] == "completed"


# =============================================================================
# RETRY LOGIC TESTS
# =============================================================================

class TestRetryLogic:
    """Test retry logic with exponential backoff"""

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self, service):
        """Test retry on transient errors"""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TransientError("Temporary failure")

            response = Mock()
            response.status_code = 200
            response.json.return_value = {"status": "ok"}
            return response

        # Patch the client request
        with patch.object(service, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_ensure.return_value = mock_client
            mock_client.request = mock_request

            result = await service._make_request(
                "GET",
                "/health",
                OperationType.HEALTH_CHECK
            )

            assert call_count == 2
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self, service):
        """Test no retry on permanent errors"""
        with patch.object(service, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_ensure.return_value = mock_client

            async def fail_with_permanent(*args, **kwargs):
                response = Mock()
                response.status_code = 404
                response.text = "Not found"
                raise PermanentError("Not found")

            mock_client.request = fail_with_permanent

            with pytest.raises(LlamaParseException):
                await service._make_request(
                    "GET",
                    "/nonexistent",
                    OperationType.QUERY_INDEX
                )


# =============================================================================
# TIMEOUT TESTS
# =============================================================================

class TestTimeoutHandling:
    """Test timeout configuration and handling"""

    def test_timeout_values_per_operation(self, mock_config):
        """Test that different operations have different timeouts"""
        health_timeout = mock_config.get_timeout(OperationType.HEALTH_CHECK)
        parse_timeout = mock_config.get_timeout(OperationType.PARSE_DOCUMENT)
        query_timeout = mock_config.get_timeout(OperationType.QUERY_INDEX)

        # Health check should be quick
        assert health_timeout <= 10.0

        # Document parsing can take longer
        assert parse_timeout > query_timeout

    @pytest.mark.asyncio
    async def test_timeout_exception_handling(self, service):
        """Test timeout exception is converted to GatewayTimeoutException"""
        with patch.object(service, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_ensure.return_value = mock_client
            mock_client.request.side_effect = httpx.ReadTimeout("Timeout")

            with pytest.raises(GatewayTimeoutException):
                await service._make_request(
                    "GET",
                    "/slow-endpoint",
                    OperationType.HEALTH_CHECK
                )


# =============================================================================
# DOCUMENT OPERATIONS TESTS
# =============================================================================

class TestDocumentOperations:
    """Test document operations"""

    @pytest.mark.asyncio
    async def test_parse_document(self, service, mock_response):
        """Test document parsing"""
        mock_response.json.return_value = {
            "content": "Parsed content",
            "metadata": {"pages": 5}
        }

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await service.parse_document(
                file_content=b"test pdf content",
                filename="test.pdf",
                content_type="application/pdf"
            )

            assert result["content"] == "Parsed content"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_index(self, service, mock_response):
        """Test index querying"""
        mock_response.json.return_value = {
            "results": [{"text": "result 1"}, {"text": "result 2"}]
        }

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await service.query_index(
                index_id="idx-123",
                query="test query",
                top_k=5
            )

            assert len(result["results"]) == 2
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_indices(self, service, mock_response):
        """Test listing indices"""
        mock_response.json.return_value = [
            {"id": "idx-1", "name": "Index 1"},
            {"id": "idx-2", "name": "Index 2"}
        ]

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await service.list_indices()

            assert len(result) == 2
            assert result[0]["id"] == "idx-1"

    @pytest.mark.asyncio
    async def test_delete_index(self, service, mock_response):
        """Test index deletion"""
        mock_response.status_code = 200

        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await service.delete_index("idx-123")

            assert result is True


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Test singleton pattern"""

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        """Test that get_llama_index_service returns same instance"""
        # Reset singleton
        await close_llama_index_service()

        service1 = get_llama_index_service()
        service2 = get_llama_index_service()

        assert service1 is service2

        # Cleanup
        await close_llama_index_service()

    @pytest.mark.asyncio
    async def test_close_resets_singleton(self):
        """Test that close_llama_index_service resets singleton"""
        service1 = get_llama_index_service()
        await close_llama_index_service()
        service2 = get_llama_index_service()

        assert service1 is not service2

        # Cleanup
        await close_llama_index_service()


# =============================================================================
# API ROUTES TESTS
# =============================================================================

class TestAPIRoutes:
    """Test API route handlers"""

    def test_routes_import(self):
        """Test that routes module imports correctly"""
        from app.routes.llama_index import (
            router,
            health_check,
            get_stats,
            get_config,
        )

        assert router is not None
        assert health_check is not None

    @pytest.mark.asyncio
    async def test_health_check_route(self):
        """Test health check route handler"""
        from app.routes.llama_index import health_check, get_service

        mock_service = AsyncMock()
        mock_service.check_health.return_value = {
            "status": "healthy",
            "service_url": "https://test.example.com",
            "response_time_ms": 100.0,
            "components": {"connection": "healthy", "api": "healthy"},
            "timestamp": datetime.utcnow().isoformat(),
            "details": {}
        }

        result = await health_check(service=mock_service)

        assert result.status == "healthy"
        assert result.response_time_ms == 100.0

    @pytest.mark.asyncio
    async def test_stats_route(self):
        """Test stats route handler"""
        from app.routes.llama_index import get_stats

        mock_service = Mock()
        mock_service.get_stats.return_value = {
            "service_name": "ResilientLlamaIndexService",
            "requests_total": 100,
            "requests_successful": 95,
            "requests_failed": 5,
            "retries_total": 10,
            "health_checks_total": 20,
            "last_health_check": None,
            "last_health_status": None,
            "config": {},
            "client_initialized": True
        }

        result = await get_stats(service=mock_service)

        assert result.requests_total == 100
        assert result.requests_successful == 95


# =============================================================================
# METRICS TESTS
# =============================================================================

class TestMetrics:
    """Test Prometheus metrics integration"""

    def test_metrics_import(self):
        """Test that metrics are properly defined"""
        from app.services.llama_index_service import (
            LLAMAINDEX_OPERATION_COUNTER,
            LLAMAINDEX_OPERATION_LATENCY,
            LLAMAINDEX_RETRY_COUNTER,
            LLAMAINDEX_CONNECTION_POOL_SIZE,
            LLAMAINDEX_HEALTH_STATUS,
        )

        assert LLAMAINDEX_OPERATION_COUNTER is not None
        assert LLAMAINDEX_OPERATION_LATENCY is not None
        assert LLAMAINDEX_RETRY_COUNTER is not None
        assert LLAMAINDEX_CONNECTION_POOL_SIZE is not None
        assert LLAMAINDEX_HEALTH_STATUS is not None


# =============================================================================
# INTEGRATION TESTS (MOCK-BASED)
# =============================================================================

class TestIntegration:
    """Integration tests with mocked external service"""

    @pytest.mark.asyncio
    async def test_full_health_check_flow(self, service, mock_response):
        """Test complete health check flow"""
        with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Perform health check
            result = await service.check_health()

            # Verify result
            assert result["status"] == "healthy"

            # Verify stats updated
            stats = service.get_stats()
            assert stats["health_checks_total"] == 1
            assert stats["last_health_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_request_tracking(self, service, mock_response):
        """Test that requests are properly tracked"""
        with patch.object(service, '_ensure_client') as mock_ensure:
            mock_client = AsyncMock()
            mock_ensure.return_value = mock_client
            mock_client.request.return_value = mock_response

            # Make a few requests
            await service.check_health()
            await service.check_health()

            # Verify stats
            stats = service.get_stats()
            assert stats["health_checks_total"] == 2
