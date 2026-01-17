"""
Empire v7.3 - Rate Limit Tiers Configuration
Task 172: Tiered Rate Limiting for Sensitive Endpoints (US3 - Production Readiness)

Defines rate limit configurations for different endpoint patterns based on security
requirements from spec 009-production-readiness.

Rate Limits (from FR-008 to FR-014):
- Login endpoints: 5 requests/minute (FR-008)
- Registration endpoints: 3 requests/minute (FR-009)
- Upload endpoints: 10 requests/minute (FR-010)
- Query endpoints: 60 requests/minute (FR-011)
- AI orchestration endpoints: 30 requests/minute (FR-012)
- Default: 200 requests/minute
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import fnmatch
import re


@dataclass
class RateLimitTier:
    """
    Configuration for a rate limit tier.

    Attributes:
        limit: Maximum number of requests allowed
        period: Time period in seconds (60 = per minute)
        description: Human-readable description of the tier
    """
    limit: int
    period: int  # in seconds
    description: str

    @property
    def slowapi_format(self) -> str:
        """Return rate limit in slowapi format (e.g., '5/minute')."""
        if self.period == 60:
            return f"{self.limit}/minute"
        elif self.period == 3600:
            return f"{self.limit}/hour"
        elif self.period == 1:
            return f"{self.limit}/second"
        else:
            # For non-standard periods, use seconds
            return f"{self.limit}/{self.period}second"


# =============================================================================
# Rate Limit Tier Definitions (FR-008 to FR-012)
# =============================================================================

# Authentication tiers - most restrictive for security
LOGIN_TIER = RateLimitTier(
    limit=5,
    period=60,
    description="Login endpoint - 5 requests per minute (FR-008)"
)

REGISTRATION_TIER = RateLimitTier(
    limit=3,
    period=60,
    description="Registration endpoint - 3 requests per minute (FR-009)"
)

# Upload tier - prevent resource abuse
UPLOAD_TIER = RateLimitTier(
    limit=10,
    period=60,
    description="Upload endpoint - 10 requests per minute (FR-010)"
)

# Query tier - balance between usability and protection
QUERY_TIER = RateLimitTier(
    limit=60,
    period=60,
    description="Query endpoints - 60 requests per minute (FR-011)"
)

# AI orchestration tier - more restrictive due to resource intensity
ORCHESTRATION_TIER = RateLimitTier(
    limit=30,
    period=60,
    description="AI orchestration endpoints - 30 requests per minute (FR-012)"
)

# Default tier - general API protection
DEFAULT_TIER = RateLimitTier(
    limit=200,
    period=60,
    description="Default rate limit - 200 requests per minute"
)

# Health check tier - very permissive for monitoring
HEALTH_CHECK_TIER = RateLimitTier(
    limit=1000,
    period=60,
    description="Health check endpoints - 1000 requests per minute"
)


# =============================================================================
# Endpoint Pattern to Tier Mapping
# =============================================================================

# Patterns use fnmatch-style wildcards (* matches anything)
# More specific patterns should be listed first for correct matching
RATE_LIMIT_TIERS: Dict[str, RateLimitTier] = {
    # Authentication endpoints (most restrictive)
    "/api/users/login": LOGIN_TIER,
    "/api/users/register": REGISTRATION_TIER,
    "/api/auth/login": LOGIN_TIER,
    "/api/auth/register": REGISTRATION_TIER,
    "/api/auth/token": LOGIN_TIER,

    # Upload endpoints
    "/api/documents/upload": UPLOAD_TIER,
    "/api/documents/upload/*": UPLOAD_TIER,
    "/api/chat/files/*": UPLOAD_TIER,
    "/api/studio/assets/upload": UPLOAD_TIER,

    # Query endpoints (FR-011)
    "/api/query/*": QUERY_TIER,
    "/api/search/*": QUERY_TIER,
    "/api/hybrid-search/*": QUERY_TIER,
    "/api/semantic-cache/*": QUERY_TIER,

    # AI orchestration endpoints (FR-012)
    "/api/orchestration/*": ORCHESTRATION_TIER,
    "/api/multi-agent/*": ORCHESTRATION_TIER,
    "/api/crewai/*": ORCHESTRATION_TIER,
    "/api/document-analysis/*": ORCHESTRATION_TIER,
    "/api/content-prep/*": ORCHESTRATION_TIER,
    "/api/orchestrator/*": ORCHESTRATION_TIER,
    "/api/graph-agent/*": ORCHESTRATION_TIER,

    # Health check endpoints (very permissive)
    "/health": HEALTH_CHECK_TIER,
    "/api/health": HEALTH_CHECK_TIER,
    "/api/system/health": HEALTH_CHECK_TIER,
    "/monitoring/*": HEALTH_CHECK_TIER,

    # Default catch-all (must be last)
    "*": DEFAULT_TIER,
}


def get_tier_for_endpoint(path: str) -> RateLimitTier:
    """
    Get the rate limit tier for a given endpoint path.

    Uses pattern matching to find the most specific matching tier.
    Patterns are checked in order, so more specific patterns should be
    listed before general patterns in RATE_LIMIT_TIERS.

    Args:
        path: The request path (e.g., "/api/users/login")

    Returns:
        The matching RateLimitTier, or DEFAULT_TIER if no specific match

    Example:
        >>> tier = get_tier_for_endpoint("/api/users/login")
        >>> tier.limit
        5
        >>> tier.period
        60
    """
    # Normalize path - remove trailing slash
    path = path.rstrip("/")

    # Check each pattern in order
    for pattern, tier in RATE_LIMIT_TIERS.items():
        if pattern == "*":
            # Default catch-all
            return tier
        if fnmatch.fnmatch(path, pattern):
            return tier

    # Fallback to default
    return DEFAULT_TIER


def get_rate_limit_string(path: str) -> str:
    """
    Get the slowapi-compatible rate limit string for an endpoint.

    Args:
        path: The request path

    Returns:
        Rate limit string in slowapi format (e.g., "5/minute")

    Example:
        >>> get_rate_limit_string("/api/users/login")
        '5/minute'
    """
    tier = get_tier_for_endpoint(path)
    return tier.slowapi_format


def get_all_tiers() -> Dict[str, Dict]:
    """
    Get all rate limit tiers with their configurations.

    Returns:
        Dictionary mapping tier names to their configurations.
        Useful for documentation and monitoring endpoints.
    """
    return {
        "login": {
            "limit": LOGIN_TIER.limit,
            "period": LOGIN_TIER.period,
            "description": LOGIN_TIER.description,
            "format": LOGIN_TIER.slowapi_format,
        },
        "registration": {
            "limit": REGISTRATION_TIER.limit,
            "period": REGISTRATION_TIER.period,
            "description": REGISTRATION_TIER.description,
            "format": REGISTRATION_TIER.slowapi_format,
        },
        "upload": {
            "limit": UPLOAD_TIER.limit,
            "period": UPLOAD_TIER.period,
            "description": UPLOAD_TIER.description,
            "format": UPLOAD_TIER.slowapi_format,
        },
        "query": {
            "limit": QUERY_TIER.limit,
            "period": QUERY_TIER.period,
            "description": QUERY_TIER.description,
            "format": QUERY_TIER.slowapi_format,
        },
        "orchestration": {
            "limit": ORCHESTRATION_TIER.limit,
            "period": ORCHESTRATION_TIER.period,
            "description": ORCHESTRATION_TIER.description,
            "format": ORCHESTRATION_TIER.slowapi_format,
        },
        "health_check": {
            "limit": HEALTH_CHECK_TIER.limit,
            "period": HEALTH_CHECK_TIER.period,
            "description": HEALTH_CHECK_TIER.description,
            "format": HEALTH_CHECK_TIER.slowapi_format,
        },
        "default": {
            "limit": DEFAULT_TIER.limit,
            "period": DEFAULT_TIER.period,
            "description": DEFAULT_TIER.description,
            "format": DEFAULT_TIER.slowapi_format,
        },
    }
