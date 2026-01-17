"""
Empire v7.3 - Core Utilities Package
Task 43.3+ Phase 2: Optimized Database Connection Pooling
Task 170: Startup Environment Validation
Task 173: External Service Timeouts
"""

# Use optimized database manager with connection pooling
from app.core.database_optimized import (
    OptimizedDatabaseManager,
    optimized_db_manager,
    get_supabase_optimized,
    get_neo4j_optimized,
    get_redis_optimized,
    get_pool_metrics,
    check_database_health
)

# Task 170, 171: Startup validation exports
from app.core.startup_validation import (
    validate_environment,
    validate_cors_origins,
    CRITICAL_ENV_VARS,
    RECOMMENDED_ENV_VARS,
)
# Alias for backward compatibility with tests
validate_cors_config = validate_cors_origins

# Task 173: External service timeout exports
from app.core.service_timeouts import (
    ServiceTimeout,
    SERVICE_TIMEOUTS,
    get_timeout_for_service,
    get_httpx_timeout,
    ServiceTimeoutError,
    ServiceConnectionError,
    ExternalServiceClient,
    get_all_service_timeouts,
    create_timeout_aware_client,
)

# Maintain backward compatibility with existing imports
DatabaseManager = OptimizedDatabaseManager
db_manager = optimized_db_manager
get_supabase = get_supabase_optimized
get_neo4j = get_neo4j_optimized
get_redis = get_redis_optimized

__all__ = [
    # Database connections
    "DatabaseManager",
    "db_manager",
    "get_supabase",
    "get_neo4j",
    "get_redis",
    "get_pool_metrics",
    "check_database_health",
    # Startup validation (Task 170, 171)
    "validate_environment",
    "validate_cors_origins",
    "validate_cors_config",  # Alias for backward compatibility
    "CRITICAL_ENV_VARS",
    "RECOMMENDED_ENV_VARS",
    # Service timeouts (Task 173)
    "ServiceTimeout",
    "SERVICE_TIMEOUTS",
    "get_timeout_for_service",
    "get_httpx_timeout",
    "ServiceTimeoutError",
    "ServiceConnectionError",
    "ExternalServiceClient",
    "get_all_service_timeouts",
    "create_timeout_aware_client",
]
