"""
Empire v7.3 - Feature Flag Management System

Zero-cost feature flag system using Supabase PostgreSQL + Upstash Redis cache.
Provides <5ms cached lookups and comprehensive flag management capabilities.

Features:
- Database-backed flag storage (Supabase PostgreSQL)
- Redis caching with 60-second TTL (<5ms lookups)
- Rollout percentage support for gradual rollouts
- User segment targeting
- Automatic audit logging
- Admin API for flag management
- Zero additional infrastructure cost

Usage:
    from app.core.feature_flags import get_feature_flag_manager

    ff = get_feature_flag_manager()

    # Check if flag is enabled
    if await ff.is_enabled("feature_course_management", user_id="user_123"):
        # Feature is enabled for this user
        pass

    # Get all flags
    flags = await ff.list_flags()

    # Update flag
    await ff.update_flag("feature_course_management", enabled=True, updated_by="admin@empire.com")
"""

import logging
import os
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
from prometheus_client import Counter, Histogram, Gauge

from app.core.supabase_client import get_supabase_client
from app.services.redis_cache_service import get_redis_cache_service

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Metrics for Feature Flags
# ============================================================================

FEATURE_FLAG_CHECKS_TOTAL = Counter(
    'empire_feature_flag_checks_total',
    'Total feature flag checks',
    ['flag_name', 'status']  # status: enabled, disabled
)

FEATURE_FLAG_CACHE_HITS = Counter(
    'empire_feature_flag_cache_hits_total',
    'Feature flag cache hits',
    ['flag_name']
)

FEATURE_FLAG_CACHE_MISSES = Counter(
    'empire_feature_flag_cache_misses_total',
    'Feature flag cache misses',
    ['flag_name']
)

FEATURE_FLAG_CHECK_DURATION = Histogram(
    'empire_feature_flag_check_duration_seconds',
    'Feature flag check duration',
    ['flag_name', 'cache_hit'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

FEATURE_FLAG_UPDATES_TOTAL = Counter(
    'empire_feature_flag_updates_total',
    'Total feature flag updates',
    ['flag_name', 'operation']  # operation: enable, disable, update_rollout
)

FEATURE_FLAG_ERRORS = Counter(
    'empire_feature_flag_errors_total',
    'Feature flag operation errors',
    ['flag_name', 'operation', 'error_type']
)

FEATURE_FLAGS_ACTIVE = Gauge(
    'empire_feature_flags_active',
    'Number of active (enabled) feature flags'
)

FEATURE_FLAG_ROLLOUT_PERCENTAGE = Gauge(
    'empire_feature_flag_rollout_percentage',
    'Current rollout percentage for feature flag',
    ['flag_name']
)


@dataclass
class FeatureFlag:
    """Feature flag data model"""
    id: str
    flag_name: str
    enabled: bool
    description: Optional[str]
    rollout_percentage: int
    user_segments: List[str]
    metadata: Dict[str, Any]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureFlag":
        """Create FeatureFlag from database row"""
        return cls(
            id=data["id"],
            flag_name=data["flag_name"],
            enabled=data["enabled"],
            description=data.get("description"),
            rollout_percentage=data.get("rollout_percentage", 0),
            user_segments=data.get("user_segments", []),
            metadata=data.get("metadata", {}),
            created_by=data.get("created_by"),
            updated_by=data.get("updated_by"),
            created_at=data["created_at"],
            updated_at=data["updated_at"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "flag_name": self.flag_name,
            "enabled": self.enabled,
            "description": self.description,
            "rollout_percentage": self.rollout_percentage,
            "user_segments": self.user_segments,
            "metadata": self.metadata,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class FeatureFlagManager:
    """
    Centralized feature flag management with Redis caching.

    Performance characteristics:
    - Cached lookups: <5ms (Redis L1 cache)
    - Uncached lookups: <50ms (Supabase query)
    - Cache TTL: 60 seconds (configurable)
    - Supports up to 1,000 flags and 100k requests/day
    """

    def __init__(
        self,
        cache_ttl: int = 60,
        enable_cache: bool = True
    ):
        """
        Initialize feature flag manager

        Args:
            cache_ttl: Cache TTL in seconds (default: 60)
            enable_cache: Whether to enable Redis caching (default: True)
        """
        self.supabase = get_supabase_client()
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache

        # Initialize Redis cache if enabled
        if self.enable_cache:
            try:
                self.redis_cache = get_redis_cache_service()
                logger.info("Feature flag manager initialized with Redis cache")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}. Running without cache.")
                self.enable_cache = False
                self.redis_cache = None
        else:
            self.redis_cache = None
            logger.info("Feature flag manager initialized without cache")

    def _get_cache_key(self, flag_name: str, user_id: Optional[str] = None) -> str:
        """Generate cache key for flag lookup"""
        if user_id:
            return f"feature_flag:{flag_name}:{user_id}"
        return f"feature_flag:{flag_name}"

    async def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if a feature flag is enabled for a given user.

        Args:
            flag_name: Name of the feature flag (e.g., "feature_course_management")
            user_id: Optional user ID for user-specific checks
            context: Optional additional context for decision making

        Returns:
            True if flag is enabled, False otherwise

        Performance:
        - Cached: <5ms
        - Uncached: <50ms
        """
        start_time = time.time()

        try:
            # Try cache first if enabled
            if self.enable_cache and self.redis_cache:
                cache_key = self._get_cache_key(flag_name, user_id)
                cached = self.redis_cache.get(cache_key)

                if cached is not None:
                    is_enabled = cached.get("enabled", False)
                    logger.debug(f"Feature flag cache hit: {flag_name}")

                    # Record metrics
                    FEATURE_FLAG_CACHE_HITS.labels(flag_name=flag_name).inc()
                    FEATURE_FLAG_CHECKS_TOTAL.labels(
                        flag_name=flag_name,
                        status="enabled" if is_enabled else "disabled"
                    ).inc()
                    FEATURE_FLAG_CHECK_DURATION.labels(
                        flag_name=flag_name,
                        cache_hit="true"
                    ).observe(time.time() - start_time)

                    return is_enabled

            # Cache miss - record metric
            FEATURE_FLAG_CACHE_MISSES.labels(flag_name=flag_name).inc()

            # Query database using helper function
            result = self.supabase.rpc(
                "get_feature_flag",
                {
                    "p_flag_name": flag_name,
                    "p_user_id": user_id
                }
            ).execute()

            if not result.data:
                logger.warning(f"Feature flag not found: {flag_name}")

                # Record metrics for not found
                FEATURE_FLAG_CHECKS_TOTAL.labels(
                    flag_name=flag_name,
                    status="disabled"
                ).inc()
                FEATURE_FLAG_CHECK_DURATION.labels(
                    flag_name=flag_name,
                    cache_hit="false"
                ).observe(time.time() - start_time)

                return False

            flag_state = result.data
            is_enabled = flag_state.get("enabled", False)

            # Cache the result if caching is enabled
            if self.enable_cache and self.redis_cache:
                cache_key = self._get_cache_key(flag_name, user_id)
                self.redis_cache.set(cache_key, flag_state, ttl=self.cache_ttl)
                logger.debug(f"Cached feature flag state: {flag_name}")

            # Record metrics
            FEATURE_FLAG_CHECKS_TOTAL.labels(
                flag_name=flag_name,
                status="enabled" if is_enabled else "disabled"
            ).inc()
            FEATURE_FLAG_CHECK_DURATION.labels(
                flag_name=flag_name,
                cache_hit="false"
            ).observe(time.time() - start_time)

            return is_enabled

        except Exception as e:
            logger.error(f"Error checking feature flag {flag_name}: {e}")

            # Record error metric
            FEATURE_FLAG_ERRORS.labels(
                flag_name=flag_name,
                operation="check",
                error_type=type(e).__name__
            ).inc()

            # Fail-safe: return False to disable feature on error
            return False

    async def get_flag(self, flag_name: str) -> Optional[FeatureFlag]:
        """
        Get detailed feature flag information.

        Args:
            flag_name: Name of the feature flag

        Returns:
            FeatureFlag object or None if not found
        """
        try:
            result = self.supabase.table("feature_flags")\
                .select("*")\
                .eq("flag_name", flag_name)\
                .execute()

            if not result.data:
                logger.warning(f"Feature flag not found: {flag_name}")
                return None

            return FeatureFlag.from_dict(result.data[0])

        except Exception as e:
            logger.error(f"Error getting feature flag {flag_name}: {e}")
            return None

    async def list_flags(
        self,
        enabled_only: bool = False
    ) -> List[FeatureFlag]:
        """
        List all feature flags.

        Args:
            enabled_only: If True, only return enabled flags

        Returns:
            List of FeatureFlag objects
        """
        try:
            query = self.supabase.table("feature_flags").select("*")

            if enabled_only:
                query = query.eq("enabled", True)

            result = query.order("flag_name").execute()

            return [FeatureFlag.from_dict(row) for row in result.data]

        except Exception as e:
            logger.error(f"Error listing feature flags: {e}")
            return []

    async def update_flag(
        self,
        flag_name: str,
        enabled: Optional[bool] = None,
        rollout_percentage: Optional[int] = None,
        user_segments: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        updated_by: str = "system"
    ) -> bool:
        """
        Update a feature flag.

        Args:
            flag_name: Name of the feature flag
            enabled: Whether to enable or disable the flag
            rollout_percentage: Percentage of users to enable for (0-100)
            user_segments: List of user IDs or segment criteria
            metadata: Additional metadata
            updated_by: Email/ID of person making the change

        Returns:
            True if update succeeded
        """
        try:
            update_data: Dict[str, Any] = {
                "updated_by": updated_by,
                "updated_at": "now()"
            }

            # Track which operation is being performed
            operation = "update"
            if enabled is not None:
                update_data["enabled"] = enabled
                operation = "enable" if enabled else "disable"

            if rollout_percentage is not None:
                if not 0 <= rollout_percentage <= 100:
                    raise ValueError("rollout_percentage must be between 0 and 100")
                update_data["rollout_percentage"] = rollout_percentage
                operation = "update_rollout"

            if user_segments is not None:
                update_data["user_segments"] = json.dumps(user_segments)

            if metadata is not None:
                update_data["metadata"] = json.dumps(metadata)

            # Update in database
            _result = self.supabase.table("feature_flags")\
                .update(update_data)\
                .eq("flag_name", flag_name)\
                .execute()

            if not _result.data:
                logger.error(f"Failed to update feature flag: {flag_name}")
                return False

            # Invalidate cache for this flag
            if self.enable_cache and self.redis_cache:
                # Invalidate all cached entries for this flag
                cache_pattern = f"feature_flag:{flag_name}*"
                keys = await self.redis_cache.scan_keys(cache_pattern, count=1000)
                for key in keys:
                    self.redis_cache.redis_client.delete(key)
                logger.debug(f"Invalidated cache for flag: {flag_name} ({len(keys)} keys)")

            # Record metrics
            FEATURE_FLAG_UPDATES_TOTAL.labels(
                flag_name=flag_name,
                operation=operation
            ).inc()

            # Update rollout percentage gauge if changed
            if rollout_percentage is not None:
                FEATURE_FLAG_ROLLOUT_PERCENTAGE.labels(flag_name=flag_name).set(rollout_percentage)

            logger.info(f"Updated feature flag: {flag_name} by {updated_by}")
            return True

        except Exception as e:
            logger.error(f"Error updating feature flag {flag_name}: {e}")

            # Record error metric
            FEATURE_FLAG_ERRORS.labels(
                flag_name=flag_name,
                operation="update",
                error_type=type(e).__name__
            ).inc()

            return False

    async def create_flag(
        self,
        flag_name: str,
        enabled: bool = False,
        description: Optional[str] = None,
        rollout_percentage: int = 0,
        user_segments: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> Optional[FeatureFlag]:
        """
        Create a new feature flag.

        Args:
            flag_name: Name of the feature flag (must be unique)
            enabled: Initial enabled state
            description: Human-readable description
            rollout_percentage: Initial rollout percentage (0-100)
            user_segments: Initial user segments
            metadata: Additional metadata
            created_by: Email/ID of person creating the flag

        Returns:
            Created FeatureFlag object or None on error
        """
        try:
            insert_data = {
                "flag_name": flag_name,
                "enabled": enabled,
                "description": description,
                "rollout_percentage": rollout_percentage,
                "user_segments": json.dumps(user_segments or []),
                "metadata": json.dumps(metadata or {}),
                "created_by": created_by,
                "updated_by": created_by
            }

            result = self.supabase.table("feature_flags")\
                .insert(insert_data)\
                .execute()

            if not result.data:
                logger.error(f"Failed to create feature flag: {flag_name}")
                return None

            logger.info(f"Created feature flag: {flag_name} by {created_by}")
            return FeatureFlag.from_dict(result.data[0])

        except Exception as e:
            logger.error(f"Error creating feature flag {flag_name}: {e}")
            return None

    async def delete_flag(
        self,
        flag_name: str,
        deleted_by: str = "system"
    ) -> bool:
        """
        Delete a feature flag.

        Args:
            flag_name: Name of the feature flag to delete
            deleted_by: Email/ID of person deleting the flag

        Returns:
            True if deletion succeeded
        """
        try:
            # Log deletion in audit table (trigger handles this automatically)
            result = self.supabase.table("feature_flags")\
                .delete()\
                .eq("flag_name", flag_name)\
                .execute()  # noqa: F841

            # Invalidate cache
            if self.enable_cache and self.redis_cache:
                cache_pattern = f"feature_flag:{flag_name}*"
                keys = await self.redis_cache.scan_keys(cache_pattern, count=1000)
                for key in keys:
                    self.redis_cache.redis_client.delete(key)

            logger.info(f"Deleted feature flag: {flag_name} by {deleted_by}")
            return True

        except Exception as e:
            logger.error(f"Error deleting feature flag {flag_name}: {e}")
            return False

    async def get_flag_statistics(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all feature flags from the view.

        Returns:
            List of flag statistics dictionaries
        """
        try:
            result = self.supabase.table("feature_flag_statistics")\
                .select("*")\
                .order("flag_name")\
                .execute()

            return result.data

        except Exception as e:
            logger.error(f"Error getting flag statistics: {e}")
            return []

    async def get_audit_trail(
        self,
        flag_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for feature flag changes.

        Args:
            flag_name: Optional flag name to filter by
            limit: Maximum number of audit entries to return

        Returns:
            List of audit log entries
        """
        try:
            query = self.supabase.table("feature_flag_audit")\
                .select("*")\
                .order("changed_at", desc=True)\
                .limit(limit)

            if flag_name:
                query = query.eq("flag_name", flag_name)

            result = query.execute()

            return result.data

        except Exception as e:
            logger.error(f"Error getting audit trail: {e}")
            return []


# Singleton instance
_feature_flag_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager(
    cache_ttl: int = 60,
    enable_cache: bool = True
) -> FeatureFlagManager:
    """
    Get or create singleton feature flag manager instance.

    Args:
        cache_ttl: Cache TTL in seconds (default: 60)
        enable_cache: Whether to enable Redis caching (default: True)

    Returns:
        FeatureFlagManager instance
    """
    global _feature_flag_manager

    if _feature_flag_manager is None:
        _feature_flag_manager = FeatureFlagManager(
            cache_ttl=cache_ttl,
            enable_cache=enable_cache
        )

    return _feature_flag_manager


def reset_feature_flag_manager():
    """
    Reset the singleton feature flag manager instance.
    Useful for testing or when configuration changes.
    """
    global _feature_flag_manager
    _feature_flag_manager = None
