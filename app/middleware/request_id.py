"""
Empire v7.3 - Request ID Middleware (Task 176 - Production Readiness)

Ensures every request has a unique request ID for tracing and correlation.
The request ID is:
- Extracted from the X-Request-ID header if provided
- Generated as a UUID if not provided
- Stored in request.state for use by handlers
- Added to all response headers
- Used for log correlation

Author: Claude Code
Date: 2025-01-16
"""

import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a unique request ID.

    The request ID is used for:
    - Distributed tracing across services
    - Log correlation
    - Error tracking and debugging
    - Request/response pairing

    Usage:
        from app.middleware.request_id import RequestIDMiddleware
        app.add_middleware(RequestIDMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and ensure request ID is set.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            Response with X-Request-ID header
        """
        # Extract existing request ID or generate new one
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = str(uuid.uuid4())

        # Store request ID in request state for use by handlers
        request.state.request_id = request_id

        # Store additional request context for logging
        request.state.client_ip = self._get_client_ip(request)
        request.state.user_agent = request.headers.get("User-Agent", "unknown")

        # Bind request ID to structlog context for this request
        # This makes all logs during this request include the request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            client_ip=request.state.client_ip,
        )

        try:
            # Process the request
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        finally:
            # Clear context vars after request completes
            structlog.contextvars.clear_contextvars()

    def _get_client_ip(self, request: Request) -> str:
        """
        Get the client IP address from the request.

        Checks X-Forwarded-For header first for proxy scenarios,
        then falls back to direct client address.

        Args:
            request: The incoming request

        Returns:
            Client IP address string
        """
        # Check for forwarded header (common in proxy/load balancer setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, get the first (client)
            return forwarded_for.split(",")[0].strip()

        # Check for real IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client address
        if request.client:
            return request.client.host

        return "unknown"


def get_request_id(request: Request) -> str:
    """
    Helper function to get request ID from request state.

    Args:
        request: The incoming request

    Returns:
        Request ID string
    """
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def get_client_ip(request: Request) -> str:
    """
    Helper function to get client IP from request state.

    Args:
        request: The incoming request

    Returns:
        Client IP address string
    """
    return getattr(request.state, "client_ip", "unknown")
