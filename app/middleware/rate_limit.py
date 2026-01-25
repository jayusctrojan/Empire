"""
Empire v7.3 - Rate Limiting Middleware
Task 41.1: JWT Authentication hardening with rate limiting
Task 172: Tiered Rate Limiting for Sensitive Endpoints (US3 - Production Readiness)

Implements rate limiting to prevent:
- Brute force authentication attacks
- API abuse and DoS attacks
- Resource exhaustion

Rate Limits (from spec 009-production-readiness):
- Login endpoints: 5 requests/minute (FR-008)
- Registration endpoints: 3 requests/minute (FR-009)
- Upload endpoints: 10 requests/minute (FR-010)
- Query endpoints: 60 requests/minute (FR-011)
- AI orchestration endpoints: 30 requests/minute (FR-012)

Uses slowapi library for flexible rate limiting with Redis backend support (FR-014).
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request, Response
from typing import Callable, Optional
from datetime import datetime, timezone
import os
import redis
import time
import uuid

# Import tiered rate limit configurations
from app.middleware.rate_limit_tiers import (
    get_tier_for_endpoint,
    get_rate_limit_string,
    LOGIN_TIER,
    REGISTRATION_TIER,
    UPLOAD_TIER,
    QUERY_TIER,
    ORCHESTRATION_TIER,
    DEFAULT_TIER,
)


# Rate limit storage backend
def get_rate_limit_backend():
    """
    Get rate limit storage backend (Redis or in-memory)

    In production, uses Redis for distributed rate limiting.
    In development, uses in-memory storage.

    Returns:
        Redis client or None for in-memory storage
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        try:
            # Use Redis for distributed rate limiting in production
            # Handle SSL parameters properly for Upstash Redis
            import ssl

            # Remove invalid ssl_cert_reqs parameter from URL if present
            clean_redis_url = redis_url.split("?")[0] if "?" in redis_url else redis_url

            # For rediss:// URLs (TLS), let redis-py handle SSL automatically
            if clean_redis_url.startswith("rediss://"):
                redis_client = redis.from_url(
                    clean_redis_url,
                    decode_responses=True
                )
            else:
                redis_client = redis.from_url(clean_redis_url, decode_responses=True)

            redis_client.ping()  # Test connection
            print(f"✅ Rate limiting using Redis: {clean_redis_url.split('@')[-1] if '@' in clean_redis_url else clean_redis_url}")
            return redis_client
        except Exception as e:
            print(f"⚠️  Redis connection failed for rate limiting: {e}")
            print("⚠️  Falling back to in-memory rate limiting")
            return None
    else:
        # Use in-memory storage for development
        print("📝 Rate limiting using in-memory storage (development mode)")
        return None


# Custom key function that considers both IP and user ID
def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key from request

    Uses user ID from JWT if authenticated, otherwise uses IP address.
    This allows:
    - Authenticated users to have per-user limits
    - Anonymous users to have per-IP limits

    Args:
        request: FastAPI request object

    Returns:
        Rate limit key (user ID or IP address)
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)

    if user_id:
        # Use user ID for authenticated requests
        return f"user:{user_id}"
    else:
        # Use IP address for anonymous requests
        return f"ip:{get_remote_address(request)}"


# Initialize limiter with custom key function
limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=None,  # Set via get_rate_limit_backend()
    default_limits=["1000/hour"],  # Default limit for all endpoints
    headers_enabled=True,  # Return rate limit info in response headers
)


# Rate limit configurations for different endpoint types
# Updated for Task 172 to match spec 009-production-readiness requirements (FR-008 to FR-012)
RATE_LIMITS = {
    # Authentication endpoints - most restrictive (FR-008, FR-009)
    "auth_login": LOGIN_TIER.slowapi_format,  # 5/minute (FR-008)
    "auth_register": REGISTRATION_TIER.slowapi_format,  # 3/minute (FR-009)
    "auth_refresh": "10/minute",  # 10 token refreshes per minute
    "auth_logout": "10/minute",  # 10 logouts per minute

    # API key management
    "api_key_create": "10/hour",  # 10 API keys per hour
    "api_key_list": "100/minute",  # 100 list requests per minute
    "api_key_revoke": "20/minute",  # 20 revocations per minute

    # File upload endpoints (FR-010)
    "upload_single": UPLOAD_TIER.slowapi_format,  # 10/minute (FR-010)
    "upload_bulk": "5/minute",  # 5 bulk uploads per minute

    # Query endpoints (FR-011)
    "query_simple": QUERY_TIER.slowapi_format,  # 60/minute (FR-011)
    "query_complex": "30/minute",  # 30 complex queries per minute

    # AI Orchestration endpoints (FR-012)
    "orchestration": ORCHESTRATION_TIER.slowapi_format,  # 30/minute (FR-012)

    # Document management
    "document_create": "100/hour",  # 100 document creates per hour
    "document_read": "500/minute",  # 500 document reads per minute
    "document_update": "100/hour",  # 100 document updates per hour
    "document_delete": "50/hour",  # 50 document deletes per hour

    # Admin endpoints (more restrictive)
    "admin_user_management": "50/minute",  # 50 user management operations per minute
    "admin_role_management": "30/minute",  # 30 role management operations per minute

    # Health checks and metrics (least restrictive)
    "health_check": "1000/minute",  # High limit for health checks
    "metrics": "100/minute",  # Metrics endpoint

    # Default rate limit
    "default": DEFAULT_TIER.slowapi_format,  # 200/minute
}


def get_rate_limit_for_endpoint(endpoint_type: str) -> str:
    """
    Get rate limit configuration for endpoint type

    Args:
        endpoint_type: Type of endpoint (from RATE_LIMITS dict)

    Returns:
        Rate limit string (e.g., "5/minute")
    """
    return RATE_LIMITS.get(endpoint_type, "100/minute")


# Exception handler for rate limit exceeded
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors (FR-013).

    Returns standardized error response with:
    - error.code: "RATE_LIMITED"
    - error.message: Human-readable message
    - error.details: Rate limit specific info
    - request_id: For correlation
    - timestamp: When the error occurred
    - Retry-After header (FR-013)

    Args:
        request: FastAPI request object
        exc: RateLimitExceeded exception

    Returns:
        JSON response with standardized error details
    """
    from fastapi.responses import JSONResponse
    import structlog

    logger = structlog.get_logger(__name__)

    # Get request ID from header or generate one
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Get the rate limit tier for this endpoint
    tier = get_tier_for_endpoint(request.url.path)

    # Calculate retry_after in seconds (use tier's period)
    retry_after_seconds = tier.period

    # Calculate reset timestamp
    reset_timestamp = int(time.time()) + retry_after_seconds

    # Log rate limit violation with structured logging
    logger.warning(
        "rate_limit_exceeded",
        path=request.url.path,
        method=request.method,
        key=get_rate_limit_key(request),
        limit=tier.limit,
        period=tier.period,
        request_id=request_id,
    )

    # Standardized error response format (matches api-contracts.yaml)
    error_response = {
        "error": {
            "code": "RATE_LIMITED",
            "message": "Rate limit exceeded. Please try again later.",
            "details": {
                "retry_after": retry_after_seconds,
                "limit": tier.limit,
                "window": tier.period,
                "path": request.url.path,
            },
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }

    return JSONResponse(
        status_code=429,
        content=error_response,
        headers={
            "Retry-After": str(retry_after_seconds),
            "X-RateLimit-Limit": str(tier.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_timestamp),
            "X-Request-ID": request_id,
        }
    )


def configure_rate_limiting(app):
    """
    Configure rate limiting for FastAPI application

    Args:
        app: FastAPI application instance
    """
    # Set storage backend
    backend = get_rate_limit_backend()
    if backend:
        limiter.storage_uri = backend

    # Add rate limit middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Add SlowAPI middleware
    app.add_middleware(SlowAPIMiddleware)

    print("✅ Rate limiting configured")


# =============================================================================
# Decorator Helpers for Common Rate Limits (Task 172)
# =============================================================================

def limit_auth_login(func):
    """
    Decorator for login endpoints (FR-008: 5 requests/minute).

    Apply this decorator to login endpoints to enforce the security
    rate limit that prevents brute force attacks.
    """
    return limiter.limit(RATE_LIMITS["auth_login"])(func)


def limit_auth_register(func):
    """
    Decorator for registration endpoints (FR-009: 3 requests/minute).

    Apply this decorator to registration endpoints to prevent
    spam account creation.
    """
    return limiter.limit(RATE_LIMITS["auth_register"])(func)


def limit_upload(func):
    """
    Decorator for upload endpoints (FR-010: 10 requests/minute).

    Apply this decorator to file upload endpoints to prevent
    resource abuse and storage exhaustion.
    """
    return limiter.limit(RATE_LIMITS["upload_single"])(func)


def limit_query(func):
    """
    Decorator for query endpoints (FR-011: 60 requests/minute).

    Apply this decorator to search and query endpoints to balance
    usability with protection against API abuse.
    """
    return limiter.limit(RATE_LIMITS["query_simple"])(func)


def limit_orchestration(func):
    """
    Decorator for AI orchestration endpoints (FR-012: 30 requests/minute).

    Apply this decorator to multi-agent, CrewAI, and other AI orchestration
    endpoints that are computationally intensive.
    """
    return limiter.limit(RATE_LIMITS["orchestration"])(func)


def limit_admin(func):
    """Decorator for admin endpoints (50/minute)"""
    return limiter.limit(RATE_LIMITS["admin_user_management"])(func)


def limit_default(func):
    """Decorator for general endpoints (200/minute default)"""
    return limiter.limit(RATE_LIMITS["default"])(func)
