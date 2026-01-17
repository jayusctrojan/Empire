"""
Startup validation module for Empire v7.3.

This module provides fail-fast validation of environment variables at application
startup. Critical variables cause immediate failure if missing; recommended
variables log warnings but allow startup to continue.

Usage:
    from app.core.startup_validation import validate_environment

    # Call at application startup before initializing services
    validate_environment()
"""

import os
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


# Critical environment variables - application WILL NOT start without these
CRITICAL_ENV_VARS: List[str] = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "REDIS_URL",
    "ANTHROPIC_API_KEY",
    "ENVIRONMENT",
]

# Recommended environment variables - warnings logged if missing, but app continues
RECOMMENDED_ENV_VARS: List[str] = [
    "NEO4J_URI",
    "NEO4J_PASSWORD",
    "LLAMAINDEX_SERVICE_URL",
    "CREWAI_SERVICE_URL",
]


def _get_env_value(var_name: str) -> Optional[str]:
    """
    Get environment variable value, treating empty strings as missing.

    Args:
        var_name: Name of the environment variable

    Returns:
        The value if set and non-empty, None otherwise
    """
    value = os.getenv(var_name)
    # Treat empty string same as missing (FR-004)
    if value is not None and value.strip() == "":
        return None
    return value


def validate_environment() -> Dict[str, List[str]]:
    """
    Validate required environment variables at application startup.

    This function implements fail-fast validation:
    - Critical variables: Application exits with clear error if any are missing
    - Recommended variables: Warnings logged, but startup continues

    Returns:
        Dictionary with keys 'critical' and 'recommended', each containing
        a list of missing variable names (empty lists if all present)

    Raises:
        RuntimeError: If any critical environment variables are missing

    Example:
        >>> result = validate_environment()
        >>> # If successful, result is {'critical': [], 'recommended': []}
        >>> # or {'critical': [], 'recommended': ['NEO4J_URI']} with warning logged
    """
    missing_critical: List[str] = []
    missing_recommended: List[str] = []

    # Check critical variables
    for var in CRITICAL_ENV_VARS:
        if _get_env_value(var) is None:
            missing_critical.append(var)

    # Check recommended variables
    for var in RECOMMENDED_ENV_VARS:
        if _get_env_value(var) is None:
            missing_recommended.append(var)

    # Handle missing critical variables - fail fast
    if missing_critical:
        logger.critical(
            "Missing critical environment variables",
            missing_vars=missing_critical,
            required_vars=CRITICAL_ENV_VARS,
        )
        raise RuntimeError(
            f"Cannot start: Missing critical env vars: {', '.join(missing_critical)}"
        )

    # Handle missing recommended variables - warn but continue
    if missing_recommended:
        logger.warning(
            "Missing recommended environment variables - some features may be unavailable",
            missing_vars=missing_recommended,
            recommended_vars=RECOMMENDED_ENV_VARS,
        )

    # All critical vars present
    logger.info(
        "All environment variables validated successfully",
        critical_vars_count=len(CRITICAL_ENV_VARS),
        recommended_vars_missing=len(missing_recommended),
    )

    return {
        "critical": missing_critical,
        "recommended": missing_recommended,
    }


def validate_cors_origins(cors_origins_str: Optional[str] = None, environment: Optional[str] = None) -> List[str]:
    """
    Validate and parse CORS origins based on environment.

    In production: CORS_ORIGINS must be explicitly set and cannot be wildcard.
    In development/staging: Defaults to ["*"] with a warning if not set.

    Args:
        cors_origins_str: Comma-separated string of allowed origins (from CORS_ORIGINS env var).
                         If None, reads from environment variable.
        environment: Current environment (from ENVIRONMENT env var).
                    If None, reads from environment variable.

    Returns:
        List of validated CORS origins

    Raises:
        RuntimeError: If CORS configuration is invalid for production environment
            - CORS_ORIGINS is not set or empty in production
            - CORS_ORIGINS contains "*" in production

    Example:
        >>> origins = validate_cors_origins("https://app.example.com,https://admin.example.com", "production")
        >>> # Returns: ["https://app.example.com", "https://admin.example.com"]

        >>> origins = validate_cors_origins(None, "development")
        >>> # Returns: ["*"] with warning logged
    """
    # Get values from environment if not provided
    if cors_origins_str is None:
        cors_origins_str = os.getenv("CORS_ORIGINS", "")
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    # Parse origins - handle empty string and whitespace
    if cors_origins_str and cors_origins_str.strip():
        cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]
    else:
        cors_origins = []

    is_production = environment.lower() == "production"

    # Production validation (FR-005)
    if is_production:
        # Check if CORS_ORIGINS is not set or empty
        if not cors_origins:
            logger.critical(
                "CORS_ORIGINS not set in production environment",
                environment=environment,
            )
            raise RuntimeError(
                "CORS_ORIGINS must be explicitly set in production. "
                "Set to specific origins like 'https://app.example.com,https://admin.example.com'"
            )

        # Check for wildcard in production
        if "*" in cors_origins:
            logger.critical(
                "Wildcard CORS origin detected in production",
                environment=environment,
                cors_origins=cors_origins,
            )
            raise RuntimeError(
                "CORS_ORIGINS cannot be '*' in production. "
                "Set specific allowed origins for security."
            )

        # Log successful validation in production
        logger.info(
            "CORS origins validated for production",
            environment=environment,
            allowed_origins=cors_origins,
            origins_count=len(cors_origins),
        )

    else:
        # Non-production (development, staging, etc.) - FR-006
        if not cors_origins:
            # Default to wildcard with warning
            cors_origins = ["*"]
            logger.warning(
                "CORS defaulting to '*' in non-production environment",
                environment=environment,
                warning="This allows all origins - do not use in production",
            )
        elif "*" in cors_origins:
            # Wildcard explicitly set - log warning
            logger.warning(
                "Wildcard CORS origin configured in non-production environment",
                environment=environment,
                cors_origins=cors_origins,
                warning="Ensure this is intentional for development/testing",
            )
        else:
            # Explicit origins in non-production
            logger.info(
                "CORS origins configured for non-production",
                environment=environment,
                allowed_origins=cors_origins,
            )

    return cors_origins


# Alias for backward compatibility with tests
validate_cors_config = validate_cors_origins
