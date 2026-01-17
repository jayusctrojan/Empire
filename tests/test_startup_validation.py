"""
Tests for startup validation module (US1 - Task 170).

Tests fail-fast environment variable validation at application startup.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.core.startup_validation import (
    validate_environment,
    _get_env_value,
    CRITICAL_ENV_VARS,
    RECOMMENDED_ENV_VARS,
)


# =============================================================================
# Test Fixtures (T007)
# =============================================================================


@pytest.fixture
def all_critical_env_vars():
    """Fixture providing all critical environment variables."""
    return {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test-service-key",
        "REDIS_URL": "redis://localhost:6379",
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "ENVIRONMENT": "development",
    }


@pytest.fixture
def all_recommended_env_vars():
    """Fixture providing all recommended environment variables."""
    return {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_PASSWORD": "test-password",
        "LLAMAINDEX_SERVICE_URL": "https://llamaindex.test.com",
        "CREWAI_SERVICE_URL": "https://crewai.test.com",
    }


@pytest.fixture
def complete_env_vars(all_critical_env_vars, all_recommended_env_vars):
    """Fixture providing all environment variables (critical + recommended)."""
    return {**all_critical_env_vars, **all_recommended_env_vars}


@pytest.fixture
def mock_logger():
    """Mock structlog logger for testing log output."""
    with patch("app.core.startup_validation.logger") as mock:
        yield mock


# =============================================================================
# Test: _get_env_value helper function
# =============================================================================


class TestGetEnvValue:
    """Tests for _get_env_value helper function."""

    def test_returns_value_when_set(self):
        """Test that _get_env_value returns the value when set."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = _get_env_value("TEST_VAR")
            assert result == "test_value"

    def test_returns_none_when_not_set(self):
        """Test that _get_env_value returns None when variable is not set."""
        # Ensure variable is not in environment
        os.environ.pop("NONEXISTENT_VAR", None)
        result = _get_env_value("NONEXISTENT_VAR")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Test that _get_env_value treats empty string as missing (FR-004)."""
        with patch.dict(os.environ, {"TEST_VAR": ""}):
            result = _get_env_value("TEST_VAR")
            assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Test that _get_env_value treats whitespace-only as missing."""
        with patch.dict(os.environ, {"TEST_VAR": "   "}):
            result = _get_env_value("TEST_VAR")
            assert result is None

    def test_preserves_value_with_spaces(self):
        """Test that _get_env_value preserves values with leading/trailing spaces."""
        with patch.dict(os.environ, {"TEST_VAR": "  value with spaces  "}):
            result = _get_env_value("TEST_VAR")
            assert result == "  value with spaces  "


# =============================================================================
# Test: Missing Critical Env Var Causes Startup Failure (T008)
# =============================================================================


class TestMissingCriticalEnvVar:
    """Tests for missing critical environment variable behavior."""

    def test_raises_runtime_error_when_single_critical_var_missing(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that missing a single critical var raises RuntimeError."""
        env_vars = all_critical_env_vars.copy()
        del env_vars["SUPABASE_URL"]

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_environment()

            assert "Cannot start" in str(exc_info.value)
            assert "SUPABASE_URL" in str(exc_info.value)

    def test_raises_runtime_error_when_multiple_critical_vars_missing(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that missing multiple critical vars raises RuntimeError with all names."""
        env_vars = all_critical_env_vars.copy()
        del env_vars["SUPABASE_URL"]
        del env_vars["REDIS_URL"]

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_environment()

            error_msg = str(exc_info.value)
            assert "Cannot start" in error_msg
            assert "SUPABASE_URL" in error_msg
            assert "REDIS_URL" in error_msg

    def test_logs_critical_when_vars_missing(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that logger.critical is called when critical vars are missing."""
        env_vars = all_critical_env_vars.copy()
        del env_vars["ANTHROPIC_API_KEY"]

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError):
                validate_environment()

            mock_logger.critical.assert_called_once()
            call_args = mock_logger.critical.call_args
            assert "Missing critical environment variables" in call_args[0][0]
            assert "ANTHROPIC_API_KEY" in call_args.kwargs["missing_vars"]

    @pytest.mark.parametrize("missing_var", CRITICAL_ENV_VARS)
    def test_each_critical_var_causes_failure_when_missing(
        self, all_critical_env_vars, missing_var, mock_logger
    ):
        """Test that each critical variable causes startup failure when missing."""
        env_vars = all_critical_env_vars.copy()
        del env_vars[missing_var]

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_environment()

            assert missing_var in str(exc_info.value)


# =============================================================================
# Test: Missing Recommended Env Var Logs Warning (T009)
# =============================================================================


class TestMissingRecommendedEnvVar:
    """Tests for missing recommended environment variable behavior."""

    def test_continues_when_recommended_var_missing(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that app continues when recommended var is missing."""
        with patch.dict(os.environ, all_critical_env_vars, clear=True):
            # Should not raise
            result = validate_environment()

            # Should return with recommended vars listed as missing
            assert result["critical"] == []
            assert set(result["recommended"]) == set(RECOMMENDED_ENV_VARS)

    def test_logs_warning_for_missing_recommended_vars(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that warning is logged when recommended vars are missing."""
        with patch.dict(os.environ, all_critical_env_vars, clear=True):
            validate_environment()

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Missing recommended environment variables" in call_args[0][0]
            assert "some features may be unavailable" in call_args[0][0]

    def test_warning_includes_missing_var_names(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that warning log includes names of missing recommended vars."""
        with patch.dict(os.environ, all_critical_env_vars, clear=True):
            validate_environment()

            call_kwargs = mock_logger.warning.call_args.kwargs
            missing_vars = call_kwargs["missing_vars"]
            assert "NEO4J_URI" in missing_vars
            assert "NEO4J_PASSWORD" in missing_vars

    def test_partial_recommended_vars_logs_only_missing(
        self, all_critical_env_vars, all_recommended_env_vars, mock_logger
    ):
        """Test that only actually missing recommended vars are logged."""
        env_vars = {**all_critical_env_vars, "NEO4J_URI": "bolt://localhost:7687"}

        with patch.dict(os.environ, env_vars, clear=True):
            result = validate_environment()

            assert "NEO4J_URI" not in result["recommended"]
            assert "NEO4J_PASSWORD" in result["recommended"]
            assert "LLAMAINDEX_SERVICE_URL" in result["recommended"]


# =============================================================================
# Test: Empty String Env Var Treated as Missing (T010)
# =============================================================================


class TestEmptyStringEnvVar:
    """Tests for empty string environment variable handling (FR-004)."""

    def test_empty_critical_var_treated_as_missing(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that empty string critical var causes startup failure."""
        env_vars = all_critical_env_vars.copy()
        env_vars["SUPABASE_URL"] = ""

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_environment()

            assert "SUPABASE_URL" in str(exc_info.value)

    def test_whitespace_only_critical_var_treated_as_missing(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that whitespace-only critical var causes startup failure."""
        env_vars = all_critical_env_vars.copy()
        env_vars["REDIS_URL"] = "   "

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_environment()

            assert "REDIS_URL" in str(exc_info.value)

    def test_empty_recommended_var_included_in_missing(
        self, all_critical_env_vars, all_recommended_env_vars, mock_logger
    ):
        """Test that empty string recommended var is reported as missing."""
        env_vars = {**all_critical_env_vars, **all_recommended_env_vars}
        env_vars["NEO4J_URI"] = ""

        with patch.dict(os.environ, env_vars, clear=True):
            result = validate_environment()

            assert "NEO4J_URI" in result["recommended"]

    def test_tabs_and_newlines_treated_as_empty(
        self, all_critical_env_vars, mock_logger
    ):
        """Test that tabs and newlines are treated as empty/missing."""
        env_vars = all_critical_env_vars.copy()
        env_vars["ENVIRONMENT"] = "\t\n"

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_environment()

            assert "ENVIRONMENT" in str(exc_info.value)


# =============================================================================
# Test: All Env Vars Present Logs Success (T011)
# =============================================================================


class TestAllEnvVarsPresent:
    """Tests for successful validation when all vars are present."""

    def test_returns_empty_lists_when_all_present(
        self, complete_env_vars, mock_logger
    ):
        """Test that result contains empty lists when all vars are present."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            result = validate_environment()

            assert result["critical"] == []
            assert result["recommended"] == []

    def test_logs_success_when_all_present(
        self, complete_env_vars, mock_logger
    ):
        """Test that success message is logged when all vars are present."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            validate_environment()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "validated successfully" in call_args[0][0]

    def test_success_log_includes_counts(
        self, complete_env_vars, mock_logger
    ):
        """Test that success log includes variable counts."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            validate_environment()

            call_kwargs = mock_logger.info.call_args.kwargs
            assert call_kwargs["critical_vars_count"] == len(CRITICAL_ENV_VARS)
            assert call_kwargs["recommended_vars_missing"] == 0

    def test_no_warning_when_all_recommended_present(
        self, complete_env_vars, mock_logger
    ):
        """Test that no warning is logged when all recommended vars are present."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            validate_environment()

            mock_logger.warning.assert_not_called()

    def test_no_critical_log_when_all_present(
        self, complete_env_vars, mock_logger
    ):
        """Test that no critical log is emitted when all vars are present."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            validate_environment()

            mock_logger.critical.assert_not_called()


# =============================================================================
# Test: Constants Validation
# =============================================================================


class TestConstants:
    """Tests to verify the constant lists are correctly defined."""

    def test_critical_vars_list_not_empty(self):
        """Test that CRITICAL_ENV_VARS is not empty."""
        assert len(CRITICAL_ENV_VARS) > 0

    def test_recommended_vars_list_not_empty(self):
        """Test that RECOMMENDED_ENV_VARS is not empty."""
        assert len(RECOMMENDED_ENV_VARS) > 0

    def test_critical_vars_are_strings(self):
        """Test that all critical vars are strings."""
        for var in CRITICAL_ENV_VARS:
            assert isinstance(var, str)
            assert len(var) > 0

    def test_recommended_vars_are_strings(self):
        """Test that all recommended vars are strings."""
        for var in RECOMMENDED_ENV_VARS:
            assert isinstance(var, str)
            assert len(var) > 0

    def test_no_duplicate_vars(self):
        """Test that there are no duplicates between critical and recommended."""
        critical_set = set(CRITICAL_ENV_VARS)
        recommended_set = set(RECOMMENDED_ENV_VARS)
        overlap = critical_set.intersection(recommended_set)
        assert len(overlap) == 0, f"Overlapping vars: {overlap}"

    def test_expected_critical_vars_present(self):
        """Test that expected critical vars are in the list."""
        expected = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "REDIS_URL", "ANTHROPIC_API_KEY", "ENVIRONMENT"]
        for var in expected:
            assert var in CRITICAL_ENV_VARS

    def test_expected_recommended_vars_present(self):
        """Test that expected recommended vars are in the list."""
        expected = ["NEO4J_URI", "NEO4J_PASSWORD", "LLAMAINDEX_SERVICE_URL", "CREWAI_SERVICE_URL"]
        for var in expected:
            assert var in RECOMMENDED_ENV_VARS


# =============================================================================
# Test: Return Value Structure
# =============================================================================


class TestReturnValueStructure:
    """Tests for the structure of validate_environment return value."""

    def test_returns_dict(self, complete_env_vars, mock_logger):
        """Test that validate_environment returns a dictionary."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            result = validate_environment()
            assert isinstance(result, dict)

    def test_returns_required_keys(self, complete_env_vars, mock_logger):
        """Test that result contains 'critical' and 'recommended' keys."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            result = validate_environment()
            assert "critical" in result
            assert "recommended" in result

    def test_critical_is_list(self, complete_env_vars, mock_logger):
        """Test that 'critical' value is a list."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            result = validate_environment()
            assert isinstance(result["critical"], list)

    def test_recommended_is_list(self, complete_env_vars, mock_logger):
        """Test that 'recommended' value is a list."""
        with patch.dict(os.environ, complete_env_vars, clear=True):
            result = validate_environment()
            assert isinstance(result["recommended"], list)
