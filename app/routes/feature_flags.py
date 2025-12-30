"""
Empire v7.3 - Feature Flags API Routes (Admin Interface)

Admin API for managing feature flags in the Empire system.
Provides endpoints for listing, creating, updating, and deleting feature flags.

Features:
- List all flags with optional filtering
- Get individual flag details
- Create new flags
- Update existing flags (enable/disable, rollout percentage, user segments)
- Delete flags
- View audit trail
- Get flag statistics
- Bulk operations (enable/disable multiple flags)
- Scheduled flag changes (future activation/deactivation)

Security:
- Admin-only endpoints: CREATE, UPDATE, DELETE, BULK operations
- Public/Optional Auth: LIST, GET, CHECK (read-only operations)
- All admin actions logged in feature_flag_audit table
- Supports both API key (emp_xxx) and JWT (Bearer token) authentication

Usage:
    # Public/Read-Only (No Auth Required)
    GET  /api/feature-flags                - List all flags
    GET  /api/feature-flags/{name}         - Get specific flag
    POST /api/feature-flags/{name}/check   - Check if flag is enabled

    # Admin-Only (Requires admin role)
    POST   /api/feature-flags              - Create new flag
    PUT    /api/feature-flags/{name}       - Update flag
    DELETE /api/feature-flags/{name}       - Delete flag
    POST   /api/feature-flags/bulk/enable  - Enable multiple flags
    POST   /api/feature-flags/bulk/disable - Disable multiple flags
    POST   /api/feature-flags/schedule     - Schedule flag change

    # Admin/Optional Auth (Stats/Audit)
    GET  /api/feature-flags/{name}/audit   - Get audit trail
    GET  /api/feature-flags/stats/all      - Get statistics
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field

from app.core.feature_flags import get_feature_flag_manager, FeatureFlag
from app.middleware.auth import require_admin, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feature-flags", tags=["Feature Flags"])


# ============================================================================
# Pydantic Models
# ============================================================================

class FeatureFlagCreate(BaseModel):
    """Request model for creating a feature flag"""
    flag_name: str = Field(..., min_length=1, max_length=100, description="Unique flag name")
    enabled: bool = Field(default=False, description="Initial enabled state")
    description: Optional[str] = Field(None, description="Human-readable description")
    rollout_percentage: int = Field(default=0, ge=0, le=100, description="Rollout percentage (0-100)")
    user_segments: List[str] = Field(default_factory=list, description="User segments for targeting")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    created_by: str = Field(default="system", description="Creator email/ID")


class FeatureFlagUpdate(BaseModel):
    """Request model for updating a feature flag"""
    enabled: Optional[bool] = Field(None, description="Enable or disable the flag")
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100, description="Rollout percentage (0-100)")
    user_segments: Optional[List[str]] = Field(None, description="User segments for targeting")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    updated_by: str = Field(default="system", description="Updater email/ID")


class FeatureFlagCheck(BaseModel):
    """Request model for checking if a flag is enabled"""
    user_id: Optional[str] = Field(None, description="User ID for user-specific checks")
    context: Optional[dict] = Field(None, description="Additional context for decision making")


class FeatureFlagResponse(BaseModel):
    """Response model for feature flag"""
    id: str
    flag_name: str
    enabled: bool
    description: Optional[str]
    rollout_percentage: int
    user_segments: List[str]
    metadata: dict
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: str
    updated_at: str


class BulkFlagOperation(BaseModel):
    """Request model for bulk flag operations"""
    flag_names: List[str] = Field(..., min_items=1, description="List of flag names to operate on")
    updated_by: str = Field(default="admin", description="Updater email/ID")


class ScheduledFlagChange(BaseModel):
    """Request model for scheduling flag changes"""
    flag_name: str = Field(..., description="Name of the flag to schedule")
    enabled: Optional[bool] = Field(None, description="Target enabled state")
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100, description="Target rollout percentage")
    scheduled_at: datetime = Field(..., description="When to apply the change (ISO 8601 format)")
    updated_by: str = Field(default="admin", description="Updater email/ID")


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=List[FeatureFlagResponse])
async def list_feature_flags(
    enabled_only: bool = Query(default=False, description="Filter to only enabled flags")
):
    """
    List all feature flags.

    Args:
        enabled_only: If True, only return enabled flags

    Returns:
        List of all feature flags
    """
    try:
        ff_manager = get_feature_flag_manager()
        flags = await ff_manager.list_flags(enabled_only=enabled_only)

        return [FeatureFlagResponse(**flag.to_dict()) for flag in flags]

    except Exception as e:
        logger.error(f"Error listing feature flags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list feature flags: {str(e)}"
        )


@router.get("/{flag_name}", response_model=FeatureFlagResponse)
async def get_feature_flag(flag_name: str):
    """
    Get a specific feature flag by name.

    Args:
        flag_name: Name of the feature flag

    Returns:
        Feature flag details
    """
    try:
        ff_manager = get_feature_flag_manager()
        flag = await ff_manager.get_flag(flag_name)

        if not flag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature flag not found: {flag_name}"
            )

        return FeatureFlagResponse(**flag.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feature flag {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feature flag: {str(e)}"
        )


@router.post("/{flag_name}/check")
async def check_feature_flag(
    flag_name: str,
    request: FeatureFlagCheck = FeatureFlagCheck()
):
    """
    Check if a feature flag is enabled for a given user.

    Args:
        flag_name: Name of the feature flag
        request: Check request with optional user_id and context

    Returns:
        Enabled status
    """
    try:
        ff_manager = get_feature_flag_manager()
        is_enabled = await ff_manager.is_enabled(
            flag_name=flag_name,
            user_id=request.user_id,
            context=request.context
        )

        return {
            "flag_name": flag_name,
            "enabled": is_enabled,
            "user_id": request.user_id
        }

    except Exception as e:
        logger.error(f"Error checking feature flag {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check feature flag: {str(e)}"
        )


@router.post("", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_feature_flag(
    request: FeatureFlagCreate,
    _admin: bool = Depends(require_admin)
):
    """
    Create a new feature flag. **Admin only**.

    Requires admin role for authentication.

    Args:
        request: Feature flag creation request

    Returns:
        Created feature flag
    """
    try:
        ff_manager = get_feature_flag_manager()
        flag = await ff_manager.create_flag(
            flag_name=request.flag_name,
            enabled=request.enabled,
            description=request.description,
            rollout_percentage=request.rollout_percentage,
            user_segments=request.user_segments,
            metadata=request.metadata,
            created_by=request.created_by
        )

        if not flag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create feature flag (may already exist): {request.flag_name}"
            )

        return FeatureFlagResponse(**flag.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating feature flag: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create feature flag: {str(e)}"
        )


@router.put("/{flag_name}", response_model=dict)
async def update_feature_flag(
    flag_name: str,
    request: FeatureFlagUpdate,
    _admin: bool = Depends(require_admin)
):
    """
    Update an existing feature flag. **Admin only**.

    Requires admin role for authentication.

    Args:
        flag_name: Name of the feature flag to update
        request: Update request

    Returns:
        Success message
    """
    try:
        ff_manager = get_feature_flag_manager()
        success = await ff_manager.update_flag(
            flag_name=flag_name,
            enabled=request.enabled,
            rollout_percentage=request.rollout_percentage,
            user_segments=request.user_segments,
            metadata=request.metadata,
            updated_by=request.updated_by
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature flag not found or update failed: {flag_name}"
            )

        return {
            "message": f"Feature flag updated successfully: {flag_name}",
            "flag_name": flag_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feature flag {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feature flag: {str(e)}"
        )


@router.delete("/{flag_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_flag(
    flag_name: str,
    deleted_by: str = Query(default="system", description="Deleter email/ID"),
    _admin: bool = Depends(require_admin)
):
    """
    Delete a feature flag. **Admin only**.

    Requires admin role for authentication.

    Args:
        flag_name: Name of the feature flag to delete
        deleted_by: Email/ID of person deleting the flag

    Returns:
        No content on success
    """
    try:
        ff_manager = get_feature_flag_manager()
        success = await ff_manager.delete_flag(flag_name, deleted_by=deleted_by)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feature flag not found or deletion failed: {flag_name}"
            )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feature flag {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete feature flag: {str(e)}"
        )


@router.get("/{flag_name}/audit")
async def get_feature_flag_audit(
    flag_name: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max audit entries to return")
):
    """
    Get audit trail for a specific feature flag.

    Args:
        flag_name: Name of the feature flag
        limit: Maximum number of audit entries to return

    Returns:
        List of audit log entries
    """
    try:
        ff_manager = get_feature_flag_manager()
        audit_trail = await ff_manager.get_audit_trail(flag_name=flag_name, limit=limit)

        return {
            "flag_name": flag_name,
            "audit_trail": audit_trail,
            "count": len(audit_trail)
        }

    except Exception as e:
        logger.error(f"Error getting audit trail for {flag_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit trail: {str(e)}"
        )


@router.get("/stats/all")
async def get_feature_flag_statistics():
    """
    Get statistics for all feature flags.

    Returns:
        List of flag statistics with change counts and timestamps
    """
    try:
        ff_manager = get_feature_flag_manager()
        stats = await ff_manager.get_flag_statistics()

        return {
            "statistics": stats,
            "count": len(stats)
        }

    except Exception as e:
        logger.error(f"Error getting flag statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


# ============================================================================
# Admin-Only Bulk Operations
# ============================================================================

@router.post("/bulk/enable")
async def bulk_enable_flags(
    request: BulkFlagOperation,
    _admin: bool = Depends(require_admin)
):
    """
    Enable multiple feature flags at once. **Admin only**.

    Useful for activating multiple related flags simultaneously.

    Args:
        request: Bulk operation request with flag names

    Returns:
        Summary of successful and failed operations
    """
    try:
        ff_manager = get_feature_flag_manager()
        results = {"success": [], "failed": []}

        for flag_name in request.flag_names:
            try:
                success = await ff_manager.update_flag(
                    flag_name=flag_name,
                    enabled=True,
                    updated_by=request.updated_by
                )
                if success:
                    results["success"].append(flag_name)
                else:
                    results["failed"].append({"flag_name": flag_name, "reason": "Update returned False"})
            except Exception as e:
                results["failed"].append({"flag_name": flag_name, "reason": str(e)})

        return {
            "message": f"Bulk enable completed: {len(results['success'])} succeeded, {len(results['failed'])} failed",
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in bulk enable operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk enable operation failed: {str(e)}"
        )


@router.post("/bulk/disable")
async def bulk_disable_flags(
    request: BulkFlagOperation,
    _admin: bool = Depends(require_admin)
):
    """
    Disable multiple feature flags at once. **Admin only**.

    Useful for deactivating multiple related flags simultaneously (e.g., rollback scenario).

    Args:
        request: Bulk operation request with flag names

    Returns:
        Summary of successful and failed operations
    """
    try:
        ff_manager = get_feature_flag_manager()
        results = {"success": [], "failed": []}

        for flag_name in request.flag_names:
            try:
                success = await ff_manager.update_flag(
                    flag_name=flag_name,
                    enabled=False,
                    updated_by=request.updated_by
                )
                if success:
                    results["success"].append(flag_name)
                else:
                    results["failed"].append({"flag_name": flag_name, "reason": "Update returned False"})
            except Exception as e:
                results["failed"].append({"flag_name": flag_name, "reason": str(e)})

        return {
            "message": f"Bulk disable completed: {len(results['success'])} succeeded, {len(results['failed'])} failed",
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in bulk disable operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk disable operation failed: {str(e)}"
        )


# ============================================================================
# Scheduled Flag Changes (Admin-Only)
# ============================================================================

# In-memory storage for scheduled changes (in production, use database or Redis)
_scheduled_changes = []


@router.post("/schedule", status_code=status.HTTP_201_CREATED)
async def schedule_flag_change(
    request: ScheduledFlagChange,
    _admin: bool = Depends(require_admin)
):
    """
    Schedule a feature flag change for future execution. **Admin only**.

    Allows planning flag activations/deactivations in advance for controlled rollouts.

    **Note**: This is a simple in-memory implementation. For production use,
    integrate with Celery task scheduler or database-backed scheduler.

    Args:
        request: Scheduled change request

    Returns:
        Confirmation with schedule details
    """
    try:
        # Validate that scheduled_at is in the future
        if request.scheduled_at <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scheduled_at must be in the future"
            )

        # Store scheduled change (in-memory for now)
        schedule_entry = {
            "id": len(_scheduled_changes) + 1,
            "flag_name": request.flag_name,
            "enabled": request.enabled,
            "rollout_percentage": request.rollout_percentage,
            "scheduled_at": request.scheduled_at.isoformat(),
            "updated_by": request.updated_by,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }

        _scheduled_changes.append(schedule_entry)

        logger.info(
            "flag_change_scheduled",
            flag_name=request.flag_name,
            scheduled_at=request.scheduled_at,
            updated_by=request.updated_by
        )

        return {
            "message": f"Flag change scheduled successfully for {request.scheduled_at.isoformat()}",
            "schedule": schedule_entry,
            "note": "IMPORTANT: This is an in-memory scheduler. For production, integrate with Celery or database-backed scheduler."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling flag change: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule flag change: {str(e)}"
        )


@router.get("/schedule")
async def list_scheduled_changes(
    _admin: bool = Depends(require_admin)
):
    """
    List all scheduled flag changes. **Admin only**.

    Returns:
        List of pending and completed scheduled changes
    """
    try:
        return {
            "scheduled_changes": _scheduled_changes,
            "count": len(_scheduled_changes),
            "note": "This is an in-memory scheduler. For production, integrate with Celery or database-backed scheduler."
        }

    except Exception as e:
        logger.error(f"Error listing scheduled changes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scheduled changes: {str(e)}"
        )
