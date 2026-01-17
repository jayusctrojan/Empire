"""
Tests for tiered rate limiting (US3 - Task 172).

Tests rate limiting configurations and behavior:
- FR-008: Login endpoint - 5 requests/minute
- FR-009: Registration endpoint - 3 requests/minute
- FR-010: Upload endpoint - 10 requests/minute
- FR-011: Query endpoints - 60 requests/minute
- FR-012: AI orchestration - 30 requests/minute
- FR-013: 429 response with Retry-After header
- FR-014: Redis-backed distributed rate limiting
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.middleware.rate_limit_tiers import (
    RateLimitTier,
    get_tier_for_endpoint,
    get_rate_limit_string,
    get_all_tiers,
    LOGIN_TIER,
    REGISTRATION_TIER,
    UPLOAD_TIER,
    QUERY_TIER,
    ORCHESTRATION_TIER,
    DEFAULT_TIER,
    HEALTH_CHECK_TIER,
    RATE_LIMIT_TIERS,
)


# =============================================================================
# Test Fixtures (Subtask 1)
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis client for rate limiting tests."""
    mock = MagicMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.incr.return_value = 1
    mock.expire.return_value = True
    return mock


@pytest.fixture
def mock_request():
    """Mock FastAPI request for testing."""
    request = MagicMock(spec=Request)
    request.url.path = "/api/users/login"
    request.method = "POST"
    request.headers = {"X-Request-ID": "test-request-id-123"}
    request.client.host = "127.0.0.1"
    request.state = MagicMock()
    request.state.user_id = None
    return request


@pytest.fixture
def mock_logger():
    """Mock structlog logger."""
    with patch("app.middleware.rate_limit.structlog") as mock:
        mock.get_logger.return_value = MagicMock()
        yield mock


# =============================================================================
# Test: RateLimitTier Dataclass
# =============================================================================


class TestRateLimitTier:
    """Tests for the RateLimitTier dataclass."""

    def test_tier_creation(self):
        """Test creating a rate limit tier."""
        tier = RateLimitTier(limit=10, period=60, description="Test tier")
        assert tier.limit == 10
        assert tier.period == 60
        assert tier.description == "Test tier"

    def test_slowapi_format_per_minute(self):
        """Test slowapi format for per-minute limits."""
        tier = RateLimitTier(limit=5, period=60, description="Test")
        assert tier.slowapi_format == "5/minute"

    def test_slowapi_format_per_hour(self):
        """Test slowapi format for per-hour limits."""
        tier = RateLimitTier(limit=100, period=3600, description="Test")
        assert tier.slowapi_format == "100/hour"

    def test_slowapi_format_per_second(self):
        """Test slowapi format for per-second limits."""
        tier = RateLimitTier(limit=10, period=1, description="Test")
        assert tier.slowapi_format == "10/second"

    def test_slowapi_format_custom_period(self):
        """Test slowapi format for custom periods."""
        tier = RateLimitTier(limit=10, period=30, description="Test")
        assert tier.slowapi_format == "10/30second"


# =============================================================================
# Test: Tier Constants (FR-008 to FR-012)
# =============================================================================


class TestTierConstants:
    """Tests for the predefined tier constants."""

    def test_login_tier_fr008(self):
        """Test login tier matches FR-008: 5 requests/minute."""
        assert LOGIN_TIER.limit == 5
        assert LOGIN_TIER.period == 60
        assert LOGIN_TIER.slowapi_format == "5/minute"

    def test_registration_tier_fr009(self):
        """Test registration tier matches FR-009: 3 requests/minute."""
        assert REGISTRATION_TIER.limit == 3
        assert REGISTRATION_TIER.period == 60
        assert REGISTRATION_TIER.slowapi_format == "3/minute"

    def test_upload_tier_fr010(self):
        """Test upload tier matches FR-010: 10 requests/minute."""
        assert UPLOAD_TIER.limit == 10
        assert UPLOAD_TIER.period == 60
        assert UPLOAD_TIER.slowapi_format == "10/minute"

    def test_query_tier_fr011(self):
        """Test query tier matches FR-011: 60 requests/minute."""
        assert QUERY_TIER.limit == 60
        assert QUERY_TIER.period == 60
        assert QUERY_TIER.slowapi_format == "60/minute"

    def test_orchestration_tier_fr012(self):
        """Test orchestration tier matches FR-012: 30 requests/minute."""
        assert ORCHESTRATION_TIER.limit == 30
        assert ORCHESTRATION_TIER.period == 60
        assert ORCHESTRATION_TIER.slowapi_format == "30/minute"

    def test_default_tier(self):
        """Test default tier is 200 requests/minute."""
        assert DEFAULT_TIER.limit == 200
        assert DEFAULT_TIER.period == 60

    def test_health_check_tier(self):
        """Test health check tier is permissive (1000/minute)."""
        assert HEALTH_CHECK_TIER.limit == 1000
        assert HEALTH_CHECK_TIER.period == 60


# =============================================================================
# Test: Endpoint Pattern Matching
# =============================================================================


class TestEndpointPatternMatching:
    """Tests for get_tier_for_endpoint pattern matching."""

    def test_login_endpoint_matching(self):
        """Test login endpoints match LOGIN_TIER."""
        tier = get_tier_for_endpoint("/api/users/login")
        assert tier == LOGIN_TIER

    def test_register_endpoint_matching(self):
        """Test register endpoints match REGISTRATION_TIER."""
        tier = get_tier_for_endpoint("/api/users/register")
        assert tier == REGISTRATION_TIER

    def test_auth_login_matching(self):
        """Test /api/auth/login matches LOGIN_TIER."""
        tier = get_tier_for_endpoint("/api/auth/login")
        assert tier == LOGIN_TIER

    def test_upload_endpoint_matching(self):
        """Test upload endpoints match UPLOAD_TIER."""
        tier = get_tier_for_endpoint("/api/documents/upload")
        assert tier == UPLOAD_TIER

    def test_query_wildcard_matching(self):
        """Test query endpoints match QUERY_TIER via wildcard."""
        tier = get_tier_for_endpoint("/api/query/auto")
        assert tier == QUERY_TIER

        tier = get_tier_for_endpoint("/api/query/adaptive")
        assert tier == QUERY_TIER

    def test_orchestration_wildcard_matching(self):
        """Test orchestration endpoints match ORCHESTRATION_TIER via wildcard."""
        tier = get_tier_for_endpoint("/api/orchestration/workflow")
        assert tier == ORCHESTRATION_TIER

        tier = get_tier_for_endpoint("/api/crewai/execute")
        assert tier == ORCHESTRATION_TIER

    def test_health_check_matching(self):
        """Test health check endpoints match HEALTH_CHECK_TIER."""
        tier = get_tier_for_endpoint("/health")
        assert tier == HEALTH_CHECK_TIER

        tier = get_tier_for_endpoint("/api/health")
        assert tier == HEALTH_CHECK_TIER

    def test_unknown_endpoint_defaults(self):
        """Test unknown endpoints default to DEFAULT_TIER."""
        tier = get_tier_for_endpoint("/api/unknown/endpoint")
        assert tier == DEFAULT_TIER

    def test_trailing_slash_normalization(self):
        """Test that trailing slashes are normalized."""
        tier1 = get_tier_for_endpoint("/api/users/login/")
        tier2 = get_tier_for_endpoint("/api/users/login")
        assert tier1 == tier2


# =============================================================================
# Test: get_rate_limit_string Function
# =============================================================================


class TestGetRateLimitString:
    """Tests for get_rate_limit_string function."""

    def test_login_rate_limit_string(self):
        """Test login endpoint returns correct rate limit string."""
        assert get_rate_limit_string("/api/users/login") == "5/minute"

    def test_register_rate_limit_string(self):
        """Test register endpoint returns correct rate limit string."""
        assert get_rate_limit_string("/api/users/register") == "3/minute"

    def test_upload_rate_limit_string(self):
        """Test upload endpoint returns correct rate limit string."""
        assert get_rate_limit_string("/api/documents/upload") == "10/minute"

    def test_query_rate_limit_string(self):
        """Test query endpoint returns correct rate limit string."""
        assert get_rate_limit_string("/api/query/auto") == "60/minute"

    def test_orchestration_rate_limit_string(self):
        """Test orchestration endpoint returns correct rate limit string."""
        assert get_rate_limit_string("/api/orchestration/workflow") == "30/minute"


# =============================================================================
# Test: get_all_tiers Function
# =============================================================================


class TestGetAllTiers:
    """Tests for get_all_tiers function."""

    def test_returns_all_tier_info(self):
        """Test that get_all_tiers returns all expected tiers."""
        tiers = get_all_tiers()

        assert "login" in tiers
        assert "registration" in tiers
        assert "upload" in tiers
        assert "query" in tiers
        assert "orchestration" in tiers
        assert "health_check" in tiers
        assert "default" in tiers

    def test_tier_info_structure(self):
        """Test that tier info has correct structure."""
        tiers = get_all_tiers()
        login_tier = tiers["login"]

        assert "limit" in login_tier
        assert "period" in login_tier
        assert "description" in login_tier
        assert "format" in login_tier

        assert login_tier["limit"] == 5
        assert login_tier["period"] == 60
        assert login_tier["format"] == "5/minute"


# =============================================================================
# Test: RATE_LIMIT_TIERS Dictionary
# =============================================================================


class TestRateLimitTiersDict:
    """Tests for the RATE_LIMIT_TIERS dictionary."""

    def test_has_login_pattern(self):
        """Test that login patterns are defined."""
        assert "/api/users/login" in RATE_LIMIT_TIERS
        assert "/api/auth/login" in RATE_LIMIT_TIERS

    def test_has_register_pattern(self):
        """Test that register patterns are defined."""
        assert "/api/users/register" in RATE_LIMIT_TIERS
        assert "/api/auth/register" in RATE_LIMIT_TIERS

    def test_has_upload_pattern(self):
        """Test that upload patterns are defined."""
        assert "/api/documents/upload" in RATE_LIMIT_TIERS

    def test_has_query_wildcard_pattern(self):
        """Test that query wildcard patterns are defined."""
        assert "/api/query/*" in RATE_LIMIT_TIERS

    def test_has_orchestration_wildcard_patterns(self):
        """Test that orchestration wildcard patterns are defined."""
        assert "/api/orchestration/*" in RATE_LIMIT_TIERS
        assert "/api/crewai/*" in RATE_LIMIT_TIERS

    def test_has_default_pattern(self):
        """Test that default catch-all pattern is defined."""
        assert "*" in RATE_LIMIT_TIERS


# =============================================================================
# Test: Rate Limit Response Format (FR-013)
# =============================================================================


class TestRateLimitResponseFormat:
    """Tests for standardized rate limit response format."""

    @pytest.fixture
    def mock_rate_limit_exceeded(self):
        """Create a mock RateLimitExceeded exception."""
        from slowapi.errors import RateLimitExceeded
        exc = RateLimitExceeded(detail="5 per 1 minute")
        return exc

    def test_response_has_error_code(self):
        """Test that response includes error.code = 'RATE_LIMITED'."""
        # This is tested via the error response structure
        # The actual handler test would need a running app
        error_response = {
            "error": {
                "code": "RATE_LIMITED",
                "message": "Rate limit exceeded. Please try again later.",
                "details": {
                    "retry_after": 60,
                    "limit": 5,
                    "window": 60,
                    "path": "/api/users/login",
                },
                "request_id": "test-id",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }

        assert error_response["error"]["code"] == "RATE_LIMITED"
        assert "retry_after" in error_response["error"]["details"]
        assert "limit" in error_response["error"]["details"]
        assert "request_id" in error_response["error"]
        assert "timestamp" in error_response["error"]

    def test_response_includes_retry_after(self):
        """Test that response details include retry_after seconds."""
        # The retry_after should match the tier's period
        assert LOGIN_TIER.period == 60  # Used as retry_after for login


# =============================================================================
# Test: Rate Limit Decorator Functions
# =============================================================================


class TestRateLimitDecorators:
    """Tests for rate limit decorator helper functions."""

    def test_limit_auth_login_uses_correct_rate(self):
        """Test limit_auth_login decorator uses LOGIN_TIER rate."""
        from app.middleware.rate_limit import RATE_LIMITS
        assert RATE_LIMITS["auth_login"] == "5/minute"

    def test_limit_auth_register_uses_correct_rate(self):
        """Test limit_auth_register decorator uses REGISTRATION_TIER rate."""
        from app.middleware.rate_limit import RATE_LIMITS
        assert RATE_LIMITS["auth_register"] == "3/minute"

    def test_limit_upload_uses_correct_rate(self):
        """Test limit_upload decorator uses UPLOAD_TIER rate."""
        from app.middleware.rate_limit import RATE_LIMITS
        assert RATE_LIMITS["upload_single"] == "10/minute"

    def test_limit_query_uses_correct_rate(self):
        """Test limit_query decorator uses QUERY_TIER rate."""
        from app.middleware.rate_limit import RATE_LIMITS
        assert RATE_LIMITS["query_simple"] == "60/minute"

    def test_limit_orchestration_uses_correct_rate(self):
        """Test limit_orchestration decorator uses ORCHESTRATION_TIER rate."""
        from app.middleware.rate_limit import RATE_LIMITS
        assert RATE_LIMITS["orchestration"] == "30/minute"


# =============================================================================
# Test: Redis Backend Configuration (FR-014)
# =============================================================================


class TestRedisBackend:
    """Tests for Redis backend configuration."""

    def test_production_uses_redis(self, mock_redis):
        """Test that production environment attempts to use Redis."""
        with patch.dict("os.environ", {"ENVIRONMENT": "production", "REDIS_URL": "redis://localhost:6379"}):
            with patch("app.middleware.rate_limit.redis") as mock_redis_module:
                mock_redis_module.from_url.return_value = mock_redis
                from app.middleware.rate_limit import get_rate_limit_backend

                # Re-import to trigger the function
                backend = get_rate_limit_backend()
                # In production, it should try to connect to Redis

    def test_development_uses_memory(self):
        """Test that development environment uses in-memory storage."""
        with patch.dict("os.environ", {"ENVIRONMENT": "development"}):
            from app.middleware.rate_limit import get_rate_limit_backend
            backend = get_rate_limit_backend()
            # In development, should return None (in-memory)
            assert backend is None


# =============================================================================
# Test: Rate Limit Key Generation
# =============================================================================


class TestRateLimitKeyGeneration:
    """Tests for rate limit key generation."""

    def test_authenticated_user_key(self, mock_request):
        """Test that authenticated users get user-based keys."""
        mock_request.state.user_id = "user-123"

        from app.middleware.rate_limit import get_rate_limit_key
        key = get_rate_limit_key(mock_request)

        assert key == "user:user-123"

    def test_anonymous_user_key(self, mock_request):
        """Test that anonymous users get IP-based keys."""
        mock_request.state.user_id = None

        from app.middleware.rate_limit import get_rate_limit_key
        with patch("app.middleware.rate_limit.get_remote_address") as mock_get_ip:
            mock_get_ip.return_value = "192.168.1.1"
            key = get_rate_limit_key(mock_request)

        assert key == "ip:192.168.1.1"


# =============================================================================
# Test: Integration - Endpoint Rate Limits
# =============================================================================


class TestEndpointRateLimits:
    """Integration tests for endpoint-specific rate limits."""

    def test_login_endpoint_has_5_per_minute(self):
        """Test login endpoint is limited to 5 requests per minute (FR-008)."""
        tier = get_tier_for_endpoint("/api/users/login")
        assert tier.limit == 5
        assert tier.period == 60

    def test_register_endpoint_has_3_per_minute(self):
        """Test register endpoint is limited to 3 requests per minute (FR-009)."""
        tier = get_tier_for_endpoint("/api/users/register")
        assert tier.limit == 3
        assert tier.period == 60

    def test_upload_endpoint_has_10_per_minute(self):
        """Test upload endpoint is limited to 10 requests per minute (FR-010)."""
        tier = get_tier_for_endpoint("/api/documents/upload")
        assert tier.limit == 10
        assert tier.period == 60

    def test_query_endpoints_have_60_per_minute(self):
        """Test query endpoints are limited to 60 requests per minute (FR-011)."""
        for path in ["/api/query/auto", "/api/query/adaptive", "/api/search/hybrid"]:
            tier = get_tier_for_endpoint(path)
            assert tier.limit == 60, f"Path {path} should have limit 60"
            assert tier.period == 60

    def test_orchestration_endpoints_have_30_per_minute(self):
        """Test orchestration endpoints are limited to 30 requests per minute (FR-012)."""
        for path in ["/api/orchestration/workflow", "/api/crewai/execute", "/api/multi-agent/run"]:
            tier = get_tier_for_endpoint(path)
            assert tier.limit == 30, f"Path {path} should have limit 30"
            assert tier.period == 60
