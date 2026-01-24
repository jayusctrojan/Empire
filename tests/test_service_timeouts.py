"""
Tests for External Service Timeouts (US4 - Task 173).

Tests timeout configurations, exception handling, and ExternalServiceClient
functionality for production readiness.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.core.service_timeouts import (
    ServiceTimeout,
    SERVICE_TIMEOUTS,
    get_timeout_for_service,
    get_httpx_timeout,
    ServiceTimeoutError,
    ServiceConnectionError,
    ExternalServiceClient,
    get_all_service_timeouts,
    create_timeout_aware_client,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def service_timeout():
    """Fixture for a basic ServiceTimeout instance."""
    return ServiceTimeout(
        read_timeout=60.0,
        connect_timeout=5.0,
        write_timeout=30.0,
        pool_timeout=5.0,
    )


@pytest.fixture
def mock_httpx_client():
    """Fixture for a mock httpx AsyncClient."""
    with patch("app.core.service_timeouts.httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        client_instance.is_closed = False
        mock.return_value = client_instance
        yield mock, client_instance


# =============================================================================
# Test: ServiceTimeout Dataclass (FR-015 to FR-019)
# =============================================================================


class TestServiceTimeoutDataclass:
    """Tests for the ServiceTimeout dataclass."""

    def test_service_timeout_creation(self, service_timeout):
        """Test that ServiceTimeout can be created with all parameters."""
        assert service_timeout.read_timeout == 60.0
        assert service_timeout.connect_timeout == 5.0
        assert service_timeout.write_timeout == 30.0
        assert service_timeout.pool_timeout == 5.0

    def test_service_timeout_default_connect_timeout(self):
        """Test that connect_timeout defaults to 5.0 (FR-019)."""
        timeout = ServiceTimeout(read_timeout=30.0)
        assert timeout.connect_timeout == 5.0

    def test_service_timeout_default_write_timeout(self):
        """Test that write_timeout defaults to 30.0."""
        timeout = ServiceTimeout(read_timeout=30.0)
        assert timeout.write_timeout == 30.0

    def test_service_timeout_default_pool_timeout(self):
        """Test that pool_timeout defaults to 5.0."""
        timeout = ServiceTimeout(read_timeout=30.0)
        assert timeout.pool_timeout == 5.0

    def test_to_httpx_timeout(self, service_timeout):
        """Test conversion to httpx.Timeout object."""
        httpx_timeout = service_timeout.to_httpx_timeout()

        assert isinstance(httpx_timeout, httpx.Timeout)
        assert httpx_timeout.connect == 5.0
        assert httpx_timeout.read == 60.0
        assert httpx_timeout.write == 30.0
        assert httpx_timeout.pool == 5.0


# =============================================================================
# Test: SERVICE_TIMEOUTS Configuration (FR-015 to FR-018)
# =============================================================================


class TestServiceTimeoutsConfiguration:
    """Tests for the SERVICE_TIMEOUTS dictionary."""

    def test_llama_index_timeout_fr015(self):
        """Test LlamaIndex timeout is 60 seconds (FR-015)."""
        timeout = SERVICE_TIMEOUTS["llama_index"]
        assert timeout.read_timeout == 60.0
        assert timeout.connect_timeout == 5.0

    def test_crewai_timeout_fr016(self):
        """Test CrewAI timeout is 120 seconds (FR-016)."""
        timeout = SERVICE_TIMEOUTS["crewai"]
        assert timeout.read_timeout == 120.0
        assert timeout.connect_timeout == 5.0

    def test_ollama_timeout_fr017(self):
        """Test Ollama timeout is 30 seconds (FR-017)."""
        timeout = SERVICE_TIMEOUTS["ollama"]
        assert timeout.read_timeout == 30.0
        assert timeout.connect_timeout == 5.0

    def test_neo4j_timeout_fr018(self):
        """Test Neo4j HTTP timeout is 15 seconds (FR-018)."""
        timeout = SERVICE_TIMEOUTS["neo4j"]
        assert timeout.read_timeout == 15.0
        assert timeout.connect_timeout == 5.0

    def test_all_services_have_5_second_connect_timeout_fr019(self):
        """Test all services have 5-second connection timeout (FR-019)."""
        for service_name, timeout in SERVICE_TIMEOUTS.items():
            assert timeout.connect_timeout == 5.0, (
                f"{service_name} should have 5s connect timeout"
            )

    def test_default_timeout_exists(self):
        """Test that a default timeout configuration exists."""
        assert "default" in SERVICE_TIMEOUTS
        timeout = SERVICE_TIMEOUTS["default"]
        assert timeout.read_timeout == 30.0

    def test_b2_storage_timeout(self):
        """Test B2 storage timeout configuration."""
        timeout = SERVICE_TIMEOUTS["b2_storage"]
        assert timeout.read_timeout == 60.0
        assert timeout.write_timeout == 120.0  # Large file uploads

    def test_supabase_timeout(self):
        """Test Supabase timeout configuration."""
        timeout = SERVICE_TIMEOUTS["supabase"]
        assert timeout.read_timeout == 10.0


# =============================================================================
# Test: get_timeout_for_service Function
# =============================================================================


class TestGetTimeoutForService:
    """Tests for the get_timeout_for_service function."""

    def test_returns_llama_index_timeout(self):
        """Test that llama_index returns correct timeout."""
        timeout = get_timeout_for_service("llama_index")
        assert timeout.read_timeout == 60.0

    def test_returns_crewai_timeout(self):
        """Test that crewai returns correct timeout."""
        timeout = get_timeout_for_service("crewai")
        assert timeout.read_timeout == 120.0

    def test_returns_default_for_unknown_service(self):
        """Test that unknown services return default timeout."""
        timeout = get_timeout_for_service("unknown_service")
        assert timeout == SERVICE_TIMEOUTS["default"]
        assert timeout.read_timeout == 30.0

    def test_returns_default_for_empty_string(self):
        """Test that empty string returns default timeout."""
        timeout = get_timeout_for_service("")
        assert timeout == SERVICE_TIMEOUTS["default"]


# =============================================================================
# Test: get_httpx_timeout Function
# =============================================================================


class TestGetHttpxTimeout:
    """Tests for the get_httpx_timeout function."""

    def test_returns_httpx_timeout_object(self):
        """Test that function returns httpx.Timeout object."""
        timeout = get_httpx_timeout("llama_index")
        assert isinstance(timeout, httpx.Timeout)

    def test_llama_index_httpx_timeout(self):
        """Test LlamaIndex httpx timeout values."""
        timeout = get_httpx_timeout("llama_index")
        assert timeout.read == 60.0
        assert timeout.connect == 5.0

    def test_unknown_service_returns_default(self):
        """Test unknown service returns default httpx timeout."""
        timeout = get_httpx_timeout("unknown")
        assert timeout.read == 30.0


# =============================================================================
# Test: ServiceTimeoutError Exception (FR-020)
# =============================================================================


class TestServiceTimeoutError:
    """Tests for the ServiceTimeoutError exception class."""

    def test_exception_creation(self):
        """Test ServiceTimeoutError can be created."""
        error = ServiceTimeoutError(
            service_name="llama_index",
            timeout_seconds=60.0,
            endpoint="/parse",
        )
        assert error.service_name == "llama_index"
        assert error.timeout_seconds == 60.0
        assert error.endpoint == "/parse"

    def test_default_message(self):
        """Test default error message is generated."""
        error = ServiceTimeoutError(
            service_name="llama_index",
            timeout_seconds=60.0,
        )
        assert "llama_index" in str(error)
        assert "60" in str(error)
        assert "timed out" in str(error)

    def test_custom_message(self):
        """Test custom message overrides default."""
        custom_msg = "Custom timeout message"
        error = ServiceTimeoutError(
            service_name="llama_index",
            timeout_seconds=60.0,
            message=custom_msg,
        )
        assert str(error) == custom_msg

    def test_to_error_response_format(self):
        """Test to_error_response returns correct format (FR-020)."""
        error = ServiceTimeoutError(
            service_name="llama_index",
            timeout_seconds=60.0,
            endpoint="/parse",
        )
        response = error.to_error_response(request_id="test-123")

        assert "error" in response
        assert response["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
        assert "timeout" in response["error"]["message"]
        assert response["error"]["details"]["service"] == "llama_index"
        assert response["error"]["details"]["reason"] == "timeout"
        assert response["error"]["details"]["timeout_seconds"] == 60.0
        assert response["error"]["request_id"] == "test-123"
        assert "timestamp" in response["error"]

    def test_to_error_response_includes_endpoint(self):
        """Test error response includes endpoint in details."""
        error = ServiceTimeoutError(
            service_name="crewai",
            timeout_seconds=120.0,
            endpoint="/run-crew",
        )
        response = error.to_error_response()
        assert response["error"]["details"]["endpoint"] == "/run-crew"


# =============================================================================
# Test: ServiceConnectionError Exception
# =============================================================================


class TestServiceConnectionError:
    """Tests for the ServiceConnectionError exception class."""

    def test_exception_creation(self):
        """Test ServiceConnectionError can be created."""
        error = ServiceConnectionError(service_name="neo4j")
        assert error.service_name == "neo4j"

    def test_default_message(self):
        """Test default error message is generated."""
        error = ServiceConnectionError(service_name="neo4j")
        assert "neo4j" in str(error)
        assert "Failed to connect" in str(error)

    def test_custom_message(self):
        """Test custom message is used."""
        error = ServiceConnectionError(
            service_name="neo4j",
            message="Connection refused",
        )
        assert str(error) == "Connection refused"

    def test_to_error_response_format(self):
        """Test to_error_response returns correct format."""
        error = ServiceConnectionError(service_name="neo4j")
        response = error.to_error_response(request_id="test-456")

        assert response["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
        assert "unavailable" in response["error"]["message"]
        assert response["error"]["details"]["service"] == "neo4j"
        assert response["error"]["details"]["reason"] == "connection_failed"


# =============================================================================
# Test: ExternalServiceClient Class
# =============================================================================


class TestExternalServiceClient:
    """Tests for the ExternalServiceClient class."""

    def test_client_initialization(self):
        """Test client can be initialized with service name."""
        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )
        assert client.base_url == "https://api.example.com"
        assert client.service_name == "llama_index"
        assert client.timeout_config.read_timeout == 60.0

    def test_client_uses_correct_timeout(self):
        """Test client uses service-specific timeout."""
        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="crewai",
        )
        assert client.timeout_config.read_timeout == 120.0

    def test_client_uses_default_for_unknown_service(self):
        """Test client uses default timeout for unknown service."""
        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="unknown",
        )
        assert client.timeout_config.read_timeout == 30.0

    @pytest.mark.asyncio
    async def test_context_manager_entry(self, mock_httpx_client):
        """Test async context manager entry creates client."""
        mock_class, mock_instance = mock_httpx_client

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_exit_closes_client(self, mock_httpx_client):
        """Test async context manager exit closes client."""
        mock_class, mock_instance = mock_httpx_client

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            pass

        mock_instance.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_request(self, mock_httpx_client):
        """Test GET request method."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(return_value=MagicMock(status_code=200))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            response = await client.get("/health")

        mock_instance.request.assert_called_with("GET", "/health")

    @pytest.mark.asyncio
    async def test_post_request(self, mock_httpx_client):
        """Test POST request method."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(return_value=MagicMock(status_code=200))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            response = await client.post("/parse", json={"url": "test"})

        mock_instance.request.assert_called_with("POST", "/parse", json={"url": "test"})

    @pytest.mark.asyncio
    async def test_timeout_exception_conversion(self, mock_httpx_client):
        """Test httpx timeout exception is converted to ServiceTimeoutError."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(side_effect=httpx.ReadTimeout("Read timeout"))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            with pytest.raises(ServiceTimeoutError) as exc_info:
                await client.get("/slow-endpoint")

        assert exc_info.value.service_name == "llama_index"
        assert exc_info.value.timeout_seconds == 60.0

    @pytest.mark.asyncio
    async def test_connect_error_conversion(self, mock_httpx_client):
        """Test httpx connect error is converted to ServiceConnectionError."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            with pytest.raises(ServiceConnectionError) as exc_info:
                await client.get("/health")

        assert exc_info.value.service_name == "llama_index"

    @pytest.mark.asyncio
    async def test_other_http_errors_propagate(self, mock_httpx_client):
        """Test other HTTP errors propagate without conversion."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        ))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get("/error-endpoint")


# =============================================================================
# Test: HTTP Methods Coverage
# =============================================================================


class TestExternalServiceClientHttpMethods:
    """Tests for all HTTP methods on ExternalServiceClient."""

    @pytest.mark.asyncio
    async def test_put_request(self, mock_httpx_client):
        """Test PUT request method."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(return_value=MagicMock(status_code=200))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            await client.put("/update", json={"data": "test"})

        mock_instance.request.assert_called_with("PUT", "/update", json={"data": "test"})

    @pytest.mark.asyncio
    async def test_delete_request(self, mock_httpx_client):
        """Test DELETE request method."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(return_value=MagicMock(status_code=204))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            await client.delete("/resource/123")

        mock_instance.request.assert_called_with("DELETE", "/resource/123")

    @pytest.mark.asyncio
    async def test_patch_request(self, mock_httpx_client):
        """Test PATCH request method."""
        mock_class, mock_instance = mock_httpx_client
        mock_instance.request = AsyncMock(return_value=MagicMock(status_code=200))

        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        async with client:
            await client.patch("/partial-update", json={"field": "value"})

        mock_instance.request.assert_called_with("PATCH", "/partial-update", json={"field": "value"})


# =============================================================================
# Test: Utility Functions
# =============================================================================


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_all_service_timeouts(self):
        """Test get_all_service_timeouts returns all configurations."""
        all_timeouts = get_all_service_timeouts()

        assert "llama_index" in all_timeouts
        assert "crewai" in all_timeouts
        assert "ollama" in all_timeouts
        assert "neo4j" in all_timeouts
        assert "default" in all_timeouts

        # Check structure
        llama_config = all_timeouts["llama_index"]
        assert "read_timeout" in llama_config
        assert "connect_timeout" in llama_config
        assert "write_timeout" in llama_config
        assert "pool_timeout" in llama_config

        assert llama_config["read_timeout"] == 60.0

    @pytest.mark.skip(reason="Event loop not available in sync test - needs async refactor")
    def test_create_timeout_aware_client(self):
        """Test create_timeout_aware_client creates configured client."""
        client = create_timeout_aware_client(
            base_url="https://api.example.com",
            service_name="llama_index",
        )

        assert isinstance(client, httpx.AsyncClient)
        # Cleanup
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.aclose())

    @pytest.mark.skip(reason="Event loop not available in sync test - needs async refactor")
    def test_create_timeout_aware_client_uses_correct_timeout(self):
        """Test that create_timeout_aware_client uses service-specific timeout."""
        client = create_timeout_aware_client(
            base_url="https://api.example.com",
            service_name="crewai",
        )

        assert client.timeout.read == 120.0
        assert client.timeout.connect == 5.0
        # Cleanup
        import asyncio
        asyncio.get_event_loop().run_until_complete(client.aclose())


# =============================================================================
# Test: Error Response Timestamp Format
# =============================================================================


class TestErrorResponseTimestamp:
    """Tests for error response timestamp format."""

    def test_timeout_error_timestamp_is_iso_format(self):
        """Test that timeout error timestamp is ISO format."""
        error = ServiceTimeoutError(
            service_name="llama_index",
            timeout_seconds=60.0,
        )
        response = error.to_error_response()
        timestamp = response["error"]["timestamp"]

        # Should be ISO format with timezone
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp

    def test_connection_error_timestamp_is_iso_format(self):
        """Test that connection error timestamp is ISO format."""
        error = ServiceConnectionError(service_name="neo4j")
        response = error.to_error_response()
        timestamp = response["error"]["timestamp"]

        # Should be ISO format with timezone
        assert "T" in timestamp


# =============================================================================
# Test: Connection Pool Configuration
# =============================================================================


class TestConnectionPoolConfiguration:
    """Tests for connection pool configuration."""

    def test_default_max_connections(self):
        """Test default max connections is 100."""
        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )
        assert client._limits.max_connections == 100

    def test_default_max_keepalive_connections(self):
        """Test default max keepalive connections is 20."""
        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
        )
        assert client._limits.max_keepalive_connections == 20

    def test_custom_connection_limits(self):
        """Test custom connection limits can be set."""
        client = ExternalServiceClient(
            base_url="https://api.example.com",
            service_name="llama_index",
            max_connections=50,
            max_keepalive_connections=10,
        )
        assert client._limits.max_connections == 50
        assert client._limits.max_keepalive_connections == 10
