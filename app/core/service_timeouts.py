"""
Empire v7.3 - Service Timeout Configuration
Task 173: External Service Timeouts (US4 - Production Readiness)

Provides configurable timeouts for all external HTTP calls to prevent
indefinite hanging when external services are slow or unresponsive.

Timeout Configuration (from spec 009-production-readiness):
- FR-015: LlamaIndex service - 60 seconds
- FR-016: CrewAI service - 120 seconds
- FR-017: Ollama embeddings - 30 seconds
- FR-018: Neo4j HTTP - 15 seconds
- FR-019: Connection timeout - 5 seconds for all services
- FR-020: Return appropriate error when timeout occurs
"""

from dataclasses import dataclass
from typing import Optional, Any, Dict
from datetime import datetime, timezone
import httpx
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Timeout Configuration Constants
# =============================================================================

@dataclass
class ServiceTimeout:
    """
    Configuration for a service timeout.

    Attributes:
        read_timeout: Maximum time to wait for a response (seconds)
        connect_timeout: Maximum time to wait for connection (seconds)
        write_timeout: Maximum time to wait for sending request (seconds)
        pool_timeout: Maximum time to wait for pool connection (seconds)
    """
    read_timeout: float
    connect_timeout: float = 5.0  # FR-019: 5-second connection timeout
    write_timeout: float = 30.0
    pool_timeout: float = 5.0

    def to_httpx_timeout(self) -> httpx.Timeout:
        """Convert to httpx.Timeout object."""
        return httpx.Timeout(
            timeout=self.read_timeout,
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.write_timeout,
            pool=self.pool_timeout,
        )


# Service-specific timeout configurations (FR-015 to FR-019)
SERVICE_TIMEOUTS: Dict[str, ServiceTimeout] = {
    # FR-015: LlamaIndex - 60 seconds (document parsing can be slow)
    "llama_index": ServiceTimeout(
        read_timeout=60.0,
        connect_timeout=5.0,
        write_timeout=30.0,
    ),

    # FR-016: CrewAI - 120 seconds (multi-agent workflows are slow)
    "crewai": ServiceTimeout(
        read_timeout=120.0,
        connect_timeout=5.0,
        write_timeout=60.0,
    ),

    # FR-017: Ollama - 30 seconds (embeddings generation)
    "ollama": ServiceTimeout(
        read_timeout=30.0,
        connect_timeout=5.0,
        write_timeout=10.0,
    ),

    # FR-018: Neo4j HTTP - 15 seconds
    "neo4j": ServiceTimeout(
        read_timeout=15.0,
        connect_timeout=5.0,
        write_timeout=10.0,
    ),

    # B2 Storage - 60 seconds (file uploads can be large)
    "b2_storage": ServiceTimeout(
        read_timeout=60.0,
        connect_timeout=5.0,
        write_timeout=120.0,  # Large file uploads
    ),

    # Supabase - 10 seconds
    "supabase": ServiceTimeout(
        read_timeout=10.0,
        connect_timeout=5.0,
        write_timeout=10.0,
    ),

    # Default timeout for unknown services
    "default": ServiceTimeout(
        read_timeout=30.0,
        connect_timeout=5.0,
        write_timeout=30.0,
    ),
}


def get_timeout_for_service(service_name: str) -> ServiceTimeout:
    """
    Get timeout configuration for a service.

    Args:
        service_name: Name of the service (e.g., 'llama_index', 'crewai')

    Returns:
        ServiceTimeout configuration for the service

    Example:
        >>> timeout = get_timeout_for_service("llama_index")
        >>> timeout.read_timeout
        60.0
    """
    return SERVICE_TIMEOUTS.get(service_name, SERVICE_TIMEOUTS["default"])


def get_httpx_timeout(service_name: str) -> httpx.Timeout:
    """
    Get httpx.Timeout object for a service.

    Args:
        service_name: Name of the service

    Returns:
        httpx.Timeout object configured for the service
    """
    return get_timeout_for_service(service_name).to_httpx_timeout()


# =============================================================================
# Custom Exceptions (FR-020)
# =============================================================================

class ServiceTimeoutError(Exception):
    """
    Exception raised when an external service call times out.

    Attributes:
        service_name: Name of the service that timed out
        timeout_seconds: Configured timeout value
        endpoint: The endpoint that was called
        message: Human-readable error message
    """

    def __init__(
        self,
        service_name: str,
        timeout_seconds: float,
        endpoint: str = "",
        message: str = "",
    ):
        self.service_name = service_name
        self.timeout_seconds = timeout_seconds
        self.endpoint = endpoint
        self.message = message or f"{service_name} service timed out after {timeout_seconds}s"
        super().__init__(self.message)

    def to_error_response(self, request_id: str = "") -> Dict[str, Any]:
        """
        Convert to standardized error response format.

        Returns:
            Dict matching the ErrorResponse schema from api-contracts.yaml
        """
        return {
            "error": {
                "code": "EXTERNAL_SERVICE_ERROR",
                "message": f"{self.service_name} service timeout",
                "details": {
                    "service": self.service_name,
                    "reason": "timeout",
                    "timeout_seconds": self.timeout_seconds,
                    "endpoint": self.endpoint,
                },
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }


class ServiceConnectionError(Exception):
    """
    Exception raised when unable to connect to an external service.

    Attributes:
        service_name: Name of the service
        message: Human-readable error message
    """

    def __init__(self, service_name: str, message: str = ""):
        self.service_name = service_name
        self.message = message or f"Failed to connect to {service_name} service"
        super().__init__(self.message)

    def to_error_response(self, request_id: str = "") -> Dict[str, Any]:
        """Convert to standardized error response format."""
        return {
            "error": {
                "code": "EXTERNAL_SERVICE_ERROR",
                "message": f"{self.service_name} service unavailable",
                "details": {
                    "service": self.service_name,
                    "reason": "connection_failed",
                },
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }


# =============================================================================
# External Service Client
# =============================================================================

class ExternalServiceClient:
    """
    HTTP client wrapper with built-in timeout handling for external services.

    Provides:
    - Configurable timeouts per service type
    - Automatic timeout exception conversion
    - Structured logging for timeout events
    - Connection pooling with limits

    Example:
        >>> client = ExternalServiceClient("https://api.example.com", "llama_index")
        >>> async with client:
        ...     response = await client.post("/parse", json={"url": "..."})
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
    ):
        """
        Initialize the external service client.

        Args:
            base_url: Base URL for the service
            service_name: Service name for timeout lookup
            max_connections: Maximum number of connections in pool
            max_keepalive_connections: Maximum keepalive connections
        """
        self.base_url = base_url
        self.service_name = service_name
        self.timeout_config = get_timeout_for_service(service_name)

        self._client: Optional[httpx.AsyncClient] = None
        self._limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )

    async def __aenter__(self) -> "ExternalServiceClient":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure the httpx client is initialized."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_config.to_httpx_timeout(),
                limits=self._limits,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _handle_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Execute an HTTP request with timeout handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments passed to httpx

        Returns:
            httpx.Response object

        Raises:
            ServiceTimeoutError: If the request times out
            ServiceConnectionError: If unable to connect
        """
        client = await self._ensure_client()

        try:
            response = await client.request(method, endpoint, **kwargs)
            return response

        except httpx.TimeoutException as e:
            logger.error(
                "external_service_timeout",
                service=self.service_name,
                endpoint=endpoint,
                timeout_seconds=self.timeout_config.read_timeout,
                error_type=type(e).__name__,
            )
            raise ServiceTimeoutError(
                service_name=self.service_name,
                timeout_seconds=self.timeout_config.read_timeout,
                endpoint=endpoint,
            ) from e

        except httpx.ConnectError as e:
            logger.error(
                "external_service_connection_error",
                service=self.service_name,
                endpoint=endpoint,
                error=str(e),
            )
            raise ServiceConnectionError(
                service_name=self.service_name,
                message=f"Failed to connect to {self.service_name}: {str(e)}",
            ) from e

        except httpx.HTTPError as e:
            logger.error(
                "external_service_http_error",
                service=self.service_name,
                endpoint=endpoint,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def get(self, endpoint: str, **kwargs) -> httpx.Response:
        """Execute a GET request."""
        return await self._handle_request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> httpx.Response:
        """Execute a POST request."""
        return await self._handle_request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> httpx.Response:
        """Execute a PUT request."""
        return await self._handle_request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> httpx.Response:
        """Execute a DELETE request."""
        return await self._handle_request("DELETE", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> httpx.Response:
        """Execute a PATCH request."""
        return await self._handle_request("PATCH", endpoint, **kwargs)


# =============================================================================
# Utility Functions
# =============================================================================

def get_all_service_timeouts() -> Dict[str, Dict[str, float]]:
    """
    Get all service timeout configurations.

    Returns:
        Dictionary mapping service names to their timeout configurations.
        Useful for documentation and monitoring endpoints.
    """
    return {
        name: {
            "read_timeout": config.read_timeout,
            "connect_timeout": config.connect_timeout,
            "write_timeout": config.write_timeout,
            "pool_timeout": config.pool_timeout,
        }
        for name, config in SERVICE_TIMEOUTS.items()
    }


def create_timeout_aware_client(
    base_url: str,
    service_name: str,
) -> httpx.AsyncClient:
    """
    Create an httpx.AsyncClient with appropriate timeout for a service.

    This is a convenience function for services that don't need the full
    ExternalServiceClient wrapper.

    Args:
        base_url: Base URL for the service
        service_name: Service name for timeout lookup

    Returns:
        Configured httpx.AsyncClient
    """
    timeout = get_httpx_timeout(service_name)
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
        ),
    )
