"""
Empire v7.3 - Rate Limiting Middleware
Task 41.1: JWT Authentication hardening with rate limiting

Implements rate limiting to prevent:
- Brute force authentication attacks
- API abuse and DoS attacks
- Resource exhaustion

Uses slowapi library for flexible rate limiting with Redis backend support.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request, Response
from typing import Callable, Optional
import os
import redis


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
RATE_LIMITS = {
    # Authentication endpoints (most restrictive)
    "auth_login": "5/minute",  # 5 login attempts per minute
    "auth_register": "3/hour",  # 3 registrations per hour
    "auth_refresh": "10/minute",  # 10 token refreshes per minute
    "auth_logout": "10/minute",  # 10 logouts per minute

    # API key management
    "api_key_create": "10/hour",  # 10 API keys per hour
    "api_key_list": "100/minute",  # 100 list requests per minute
    "api_key_revoke": "20/minute",  # 20 revocations per minute

    # File upload endpoints
    "upload_single": "50/hour",  # 50 file uploads per hour
    "upload_bulk": "10/hour",  # 10 bulk uploads per hour

    # Query endpoints
    "query_simple": "100/minute",  # 100 queries per minute
    "query_complex": "20/minute",  # 20 complex queries per minute

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
    Custom handler for rate limit exceeded errors

    Args:
        request: FastAPI request object
        exc: RateLimitExceeded exception

    Returns:
        JSON response with error details
    """
    from fastapi.responses import JSONResponse

    # Log rate limit violation
    import structlog
    logger = structlog.get_logger(__name__)

    logger.warning(
        "rate_limit_exceeded",
        path=request.url.path,
        method=request.method,
        key=get_rate_limit_key(request),
        limit=str(exc)
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.detail if hasattr(exc, 'detail') else "60 seconds",
            "path": request.url.path
        },
        headers={
            "Retry-After": "60",  # Tell client to retry after 60 seconds
            "X-RateLimit-Limit": getattr(exc, 'limit', 'unknown'),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": getattr(exc, 'reset', 'unknown')
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


# Decorator helpers for common rate limits
def limit_auth_login(func):
    """Decorator for login endpoints (5 attempts/minute)"""
    return limiter.limit(RATE_LIMITS["auth_login"])(func)


def limit_auth_register(func):
    """Decorator for registration endpoints (3 attempts/hour)"""
    return limiter.limit(RATE_LIMITS["auth_register"])(func)


def limit_upload(func):
    """Decorator for upload endpoints (50/hour)"""
    return limiter.limit(RATE_LIMITS["upload_single"])(func)


def limit_query(func):
    """Decorator for query endpoints (100/minute)"""
    return limiter.limit(RATE_LIMITS["query_simple"])(func)


def limit_admin(func):
    """Decorator for admin endpoints (50/minute)"""
    return limiter.limit(RATE_LIMITS["admin_user_management"])(func)
