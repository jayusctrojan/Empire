"""
Tests for CORS production hardening (US2 - Task 171).

Tests CORS validation at application startup to ensure:
- Production rejects wildcard origins
- Production requires explicit CORS_ORIGINS
- Development allows wildcard with warning
"""

import os
import pytest
from unittest.mock import patch

from app.core.startup_validation import validate_cors_origins


# =============================================================================
# Test Fixtures (T016 - Subtask 1)
# =============================================================================


@pytest.fixture
def production_env():
    """Fixture for production environment."""
    return "production"


@pytest.fixture
def development_env():
    """Fixture for development environment."""
    return "development"


@pytest.fixture
def staging_env():
    """Fixture for staging environment."""
    return "staging"


@pytest.fixture
def valid_production_origins():
    """Fixture for valid production CORS origins."""
    return "https://app.example.com,https://admin.example.com"


@pytest.fixture
def single_origin():
    """Fixture for a single CORS origin."""
    return "https://app.example.com"


@pytest.fixture
def mock_logger():
    """Mock structlog logger for testing log output."""
    with patch("app.core.startup_validation.logger") as mock:
        yield mock


# =============================================================================
# Test: Wildcard CORS in Production Causes Startup Failure (T017 - Subtask 2)
# =============================================================================


class TestWildcardCorsInProduction:
    """Tests for wildcard CORS detection in production environment."""

    def test_wildcard_cors_raises_runtime_error(self, production_env, mock_logger):
        """Test that wildcard CORS in production raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_cors_origins("*", production_env)

        assert "CORS_ORIGINS cannot be '*' in production" in str(exc_info.value)

    def test_wildcard_with_other_origins_raises_error(self, production_env, mock_logger):
        """Test that wildcard mixed with other origins in production raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_cors_origins("https://app.example.com,*", production_env)

        assert "CORS_ORIGINS cannot be '*' in production" in str(exc_info.value)

    def test_wildcard_cors_logs_critical(self, production_env, mock_logger):
        """Test that wildcard CORS in production logs critical message."""
        with pytest.raises(RuntimeError):
            validate_cors_origins("*", production_env)

        mock_logger.critical.assert_called()
        call_args = mock_logger.critical.call_args
        assert "Wildcard CORS origin detected" in call_args[0][0]

    def test_error_message_includes_guidance(self, production_env, mock_logger):
        """Test that error message includes guidance on what to set."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_cors_origins("*", production_env)

        error_msg = str(exc_info.value)
        assert "Set specific allowed origins" in error_msg


# =============================================================================
# Test: Missing CORS_ORIGINS in Production Causes Startup Failure (T018 - Subtask 3)
# =============================================================================


class TestMissingCorsInProduction:
    """Tests for missing CORS_ORIGINS in production environment."""

    def test_empty_cors_raises_runtime_error(self, production_env, mock_logger):
        """Test that empty CORS_ORIGINS in production raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_cors_origins("", production_env)

        assert "CORS_ORIGINS must be explicitly set in production" in str(exc_info.value)

    def test_none_cors_raises_runtime_error(self, production_env, mock_logger):
        """Test that None CORS_ORIGINS in production raises RuntimeError."""
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=False):
            with pytest.raises(RuntimeError) as exc_info:
                validate_cors_origins(None, production_env)

            assert "CORS_ORIGINS must be explicitly set in production" in str(exc_info.value)

    def test_whitespace_only_cors_raises_error(self, production_env, mock_logger):
        """Test that whitespace-only CORS_ORIGINS in production raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_cors_origins("   ", production_env)

        assert "CORS_ORIGINS must be explicitly set in production" in str(exc_info.value)

    def test_missing_cors_logs_critical(self, production_env, mock_logger):
        """Test that missing CORS_ORIGINS in production logs critical message."""
        with pytest.raises(RuntimeError):
            validate_cors_origins("", production_env)

        mock_logger.critical.assert_called()
        call_args = mock_logger.critical.call_args
        assert "CORS_ORIGINS not set" in call_args[0][0]

    def test_error_message_includes_example(self, production_env, mock_logger):
        """Test that error message includes example of valid configuration."""
        with pytest.raises(RuntimeError) as exc_info:
            validate_cors_origins("", production_env)

        error_msg = str(exc_info.value)
        assert "https://app.example.com" in error_msg


# =============================================================================
# Test: Wildcard CORS in Development Allowed with Warning (T019 - Subtask 4)
# =============================================================================


class TestWildcardCorsInDevelopment:
    """Tests for wildcard CORS in development environment."""

    def test_wildcard_cors_allowed_in_development(self, development_env, mock_logger):
        """Test that wildcard CORS is allowed in development."""
        result = validate_cors_origins("*", development_env)
        assert result == ["*"]

    def test_empty_cors_defaults_to_wildcard_in_development(self, development_env, mock_logger):
        """Test that empty CORS_ORIGINS defaults to wildcard in development."""
        result = validate_cors_origins("", development_env)
        assert result == ["*"]

    def test_none_cors_defaults_to_wildcard_in_development(self, development_env, mock_logger):
        """Test that None CORS_ORIGINS defaults to wildcard in development."""
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=False):
            result = validate_cors_origins(None, development_env)
            assert result == ["*"]

    def test_default_wildcard_logs_warning(self, development_env, mock_logger):
        """Test that defaulting to wildcard in development logs a warning."""
        validate_cors_origins("", development_env)

        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args
        assert "CORS defaulting to '*'" in call_args[0][0]

    def test_explicit_wildcard_logs_warning(self, development_env, mock_logger):
        """Test that explicit wildcard in development logs a warning."""
        validate_cors_origins("*", development_env)

        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args
        assert "Wildcard CORS origin configured" in call_args[0][0]

    def test_explicit_origins_in_development_no_warning(self, development_env, mock_logger):
        """Test that explicit origins in development do not log warning."""
        validate_cors_origins("https://localhost:3000", development_env)

        mock_logger.warning.assert_not_called()
        mock_logger.info.assert_called()


# =============================================================================
# Test: Staging Environment Behavior
# =============================================================================


class TestStagingEnvironment:
    """Tests for CORS behavior in staging environment."""

    def test_staging_allows_wildcard(self, staging_env, mock_logger):
        """Test that staging environment allows wildcard CORS."""
        result = validate_cors_origins("*", staging_env)
        assert result == ["*"]

    def test_staging_defaults_to_wildcard(self, staging_env, mock_logger):
        """Test that staging environment defaults to wildcard when not set."""
        result = validate_cors_origins("", staging_env)
        assert result == ["*"]

    def test_staging_logs_warning_for_wildcard(self, staging_env, mock_logger):
        """Test that staging logs warning for wildcard."""
        validate_cors_origins("*", staging_env)
        mock_logger.warning.assert_called()


# =============================================================================
# Test: Valid Production Configuration
# =============================================================================


class TestValidProductionConfiguration:
    """Tests for valid CORS configuration in production."""

    def test_single_origin_accepted(self, production_env, single_origin, mock_logger):
        """Test that single valid origin is accepted in production."""
        result = validate_cors_origins(single_origin, production_env)
        assert result == ["https://app.example.com"]

    def test_multiple_origins_accepted(self, production_env, valid_production_origins, mock_logger):
        """Test that multiple valid origins are accepted in production."""
        result = validate_cors_origins(valid_production_origins, production_env)
        assert "https://app.example.com" in result
        assert "https://admin.example.com" in result

    def test_valid_origins_log_info(self, production_env, valid_production_origins, mock_logger):
        """Test that valid origins in production log info message."""
        validate_cors_origins(valid_production_origins, production_env)

        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args
        assert "CORS origins validated for production" in call_args[0][0]

    def test_no_critical_log_for_valid_config(self, production_env, valid_production_origins, mock_logger):
        """Test that valid configuration does not log critical."""
        validate_cors_origins(valid_production_origins, production_env)
        mock_logger.critical.assert_not_called()


# =============================================================================
# Test: Origin Parsing
# =============================================================================


class TestOriginParsing:
    """Tests for CORS origin string parsing."""

    def test_trims_whitespace_from_origins(self, development_env, mock_logger):
        """Test that whitespace is trimmed from origins."""
        result = validate_cors_origins("  https://app.example.com  ,  https://admin.example.com  ", development_env)
        assert "https://app.example.com" in result
        assert "https://admin.example.com" in result
        # Ensure no leading/trailing whitespace
        for origin in result:
            assert origin == origin.strip()

    def test_filters_empty_origins(self, development_env, mock_logger):
        """Test that empty origins are filtered out."""
        result = validate_cors_origins("https://app.example.com,,https://admin.example.com", development_env)
        assert len(result) == 2
        assert "" not in result

    def test_handles_single_origin_no_comma(self, development_env, mock_logger):
        """Test that single origin without comma is handled."""
        result = validate_cors_origins("https://app.example.com", development_env)
        assert result == ["https://app.example.com"]

    def test_handles_trailing_comma(self, development_env, mock_logger):
        """Test that trailing comma is handled."""
        result = validate_cors_origins("https://app.example.com,", development_env)
        assert result == ["https://app.example.com"]


# =============================================================================
# Test: Environment Variable Reading
# =============================================================================


class TestEnvironmentVariableReading:
    """Tests for reading from environment variables."""

    def test_reads_cors_from_env_when_none(self, mock_logger):
        """Test that CORS_ORIGINS is read from env when parameter is None."""
        with patch.dict(os.environ, {
            "CORS_ORIGINS": "https://from-env.example.com",
            "ENVIRONMENT": "development"
        }):
            result = validate_cors_origins(None, None)
            assert "https://from-env.example.com" in result

    def test_reads_environment_from_env_when_none(self, mock_logger):
        """Test that ENVIRONMENT is read from env when parameter is None."""
        with patch.dict(os.environ, {
            "CORS_ORIGINS": "*",
            "ENVIRONMENT": "production"
        }):
            with pytest.raises(RuntimeError):
                validate_cors_origins(None, None)

    def test_defaults_to_development_when_env_not_set(self, mock_logger):
        """Test that environment defaults to development when not set."""
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=True):
            result = validate_cors_origins("", None)
            assert result == ["*"]  # Development default

    def test_parameter_overrides_env_var(self, mock_logger):
        """Test that explicit parameter overrides environment variable."""
        with patch.dict(os.environ, {
            "CORS_ORIGINS": "https://from-env.example.com",
            "ENVIRONMENT": "production"
        }):
            # Explicit development should allow wildcard
            result = validate_cors_origins("*", "development")
            assert result == ["*"]


# =============================================================================
# Test: Case Sensitivity
# =============================================================================


class TestCaseSensitivity:
    """Tests for case sensitivity in environment detection."""

    def test_production_case_insensitive(self, mock_logger):
        """Test that 'Production', 'PRODUCTION' are treated as production."""
        with pytest.raises(RuntimeError):
            validate_cors_origins("*", "Production")

        with pytest.raises(RuntimeError):
            validate_cors_origins("*", "PRODUCTION")

    def test_development_case_insensitive(self, mock_logger):
        """Test that 'Development', 'DEVELOPMENT' are treated as development."""
        result1 = validate_cors_origins("*", "Development")
        result2 = validate_cors_origins("*", "DEVELOPMENT")
        assert result1 == ["*"]
        assert result2 == ["*"]
