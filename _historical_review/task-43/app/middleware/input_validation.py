"""
Input Validation Middleware - Task 41.4
Provides request body size limits and basic input validation
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request body size to prevent DoS attacks

    Benefits:
    - Prevents memory exhaustion from large payloads
    - Protects against DoS attacks
    - Configurable per-environment limits
    """

    def __init__(
        self,
        app,
        max_body_size: int = 100 * 1024 * 1024,  # 100MB default
        exempt_paths: Optional[list[str]] = None
    ):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.exempt_paths = exempt_paths or ["/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        """Check request body size before processing"""

        # Skip size check for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Check Content-Length header
        content_length = request.headers.get("content-length")

        if content_length:
            content_length = int(content_length)

            if content_length > self.max_body_size:
                logger.warning(
                    "request_body_too_large",
                    path=request.url.path,
                    content_length=content_length,
                    max_allowed=self.max_body_size,
                    ip=request.client.host if request.client else "unknown"
                )

                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={
                        "error": "Request body too large",
                        "max_size_bytes": self.max_body_size,
                        "max_size_mb": self.max_body_size // (1024 * 1024),
                        "received_bytes": content_length,
                        "message": f"Request body must not exceed {self.max_body_size // (1024 * 1024)}MB"
                    }
                )

        # Process request
        response = await call_next(request)
        return response


def configure_input_validation(app, max_body_size: int = 100 * 1024 * 1024):
    """
    Configure input validation middleware

    Args:
        app: FastAPI application instance
        max_body_size: Maximum request body size in bytes (default 100MB)
    """

    # Add request size limit middleware
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_body_size=max_body_size,
        exempt_paths=["/docs", "/redoc", "/openapi.json", "/health"]
    )

    logger.info(
        "input_validation_configured",
        max_body_size_mb=max_body_size // (1024 * 1024)
    )
