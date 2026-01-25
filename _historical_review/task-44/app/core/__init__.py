"""
Empire v7.3 - Core Utilities Package
Task 43.3+ Phase 2: Optimized Database Connection Pooling
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

# Maintain backward compatibility with existing imports
DatabaseManager = OptimizedDatabaseManager
db_manager = optimized_db_manager
get_supabase = get_supabase_optimized
get_neo4j = get_neo4j_optimized
get_redis = get_redis_optimized

__all__ = [
    "DatabaseManager",
    "db_manager",
    "get_supabase",
    "get_neo4j",
    "get_redis",
    "get_pool_metrics",
    "check_database_health"
]
