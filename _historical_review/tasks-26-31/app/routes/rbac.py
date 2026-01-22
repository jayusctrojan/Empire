"""
Empire v7.3 - RBAC API Routes
FastAPI endpoints for Role-Based Access Control (RBAC) and API key lifecycle management.

Endpoints:
- API Key Management (create, list, rotate, revoke)
- Role Management (list, assign, revoke, get user roles)
- Audit Logs (view all RBAC operations)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List, Optional
import structlog

from app.models.rbac import (
    APIKeyCreateRequest, APIKeyCreateResponse,
    APIKeyRotateRequest, APIKeyListResponse,
    APIKeyRevokeRequest, UserRoleAssignRequest,
    UserRoleRevokeRequest, RoleInfo, UserRoleInfo,
    AuditLogEntry
)
from app.services.rbac_service import RBACService, get_rbac_service
from app.middleware.auth import get_current_user, require_admin

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/rbac", tags=["RBAC"])


# ==================== API KEY ENDPOINTS ====================

@router.post(
    "/keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API Key",
    description="Generate a new API key. The full key is returned ONCE and never stored in plaintext."
)
async def create_api_key(
    request: APIKeyCreateRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Create a new API key with bcrypt hashing.

    **SECURITY**: Full key is shown ONLY in this response. Save it securely.
    
    Returns:
        APIKeyCreateResponse with full API key (emp_xxx...)
    """
    try:
        result = await rbac_service.create_api_key(
            user_id=current_user,
            key_name=request.key_name,
            role_id=request.role_id,
            scopes=request.scopes,
            rate_limit_per_hour=request.rate_limit_per_hour,
            expires_at=request.expires_at,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "api_key_created",
            key_id=result["key_id"],
            user_id=current_user,
            key_name=request.key_name
        )

        return APIKeyCreateResponse(**result)

    except Exception as e:
        logger.error("create_api_key_failed", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get(
    "/keys",
    response_model=APIKeyListResponse,
    summary="List API Keys",
    description="List all API keys for the current user (admins see all keys)"
)
async def list_api_keys(
    http_request: Request,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service),
    user_id: Optional[str] = None
):
    """
    List API keys. Regular users see only their keys, admins can filter by user_id.
    
    Args:
        user_id: Optional user ID to filter by (admin only)
        
    Returns:
        APIKeyListResponse with list of keys (prefix only, no full keys)
    """
    try:
        # Check if user is trying to access other user's keys
        if user_id and user_id != current_user:
            # Verify user is admin
            try:
                await require_admin(current_user=current_user, rbac_service=rbac_service)
            except HTTPException as e:
                logger.warning(
                    "non_admin_attempted_list_other_keys",
                    user_id=current_user,
                    requested_user=user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can view other users' API keys"
                )

        # If no user_id specified, default to current user
        target_user_id = user_id if user_id else current_user

        keys = await rbac_service.list_api_keys(user_id=target_user_id)

        logger.debug(
            "api_keys_listed",
            user_id=current_user,
            target_user=target_user_id,
            count=len(keys)
        )

        return APIKeyListResponse(
            keys=keys,
            total=len(keys)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_api_keys_failed", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.post(
    "/keys/rotate",
    response_model=APIKeyCreateResponse,
    summary="Rotate API Key",
    description="Generate a new key for an existing API key ID. Old key is revoked."
)
async def rotate_api_key(
    request: APIKeyRotateRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Rotate an API key by generating a new key and revoking the old one.
    
    Returns:
        APIKeyCreateResponse with new full API key (shown ONCE)
    """
    try:
        result = await rbac_service.rotate_api_key(
            key_id=request.key_id,
            user_id=current_user,
            new_key_name=request.new_key_name,
            expires_at=request.expires_at,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "api_key_rotated",
            old_key_id=request.key_id,
            new_key_id=result["key_id"],
            user_id=current_user
        )

        return APIKeyCreateResponse(**result)

    except PermissionError as e:
        logger.warning("rotate_api_key_forbidden", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        logger.warning("rotate_api_key_not_found", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("rotate_api_key_failed", error=str(e), key_id=request.key_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rotate API key: {str(e)}"
        )


@router.post(
    "/keys/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API Key",
    description="Permanently revoke an API key"
)
async def revoke_api_key(
    request: APIKeyRevokeRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Revoke an API key permanently.
    """
    try:
        await rbac_service.revoke_api_key(
            key_id=request.key_id,
            user_id=current_user,
            revoke_reason=request.revoke_reason,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "api_key_revoked",
            key_id=request.key_id,
            user_id=current_user,
            reason=request.revoke_reason
        )

    except PermissionError as e:
        logger.warning("revoke_api_key_forbidden", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        logger.warning("revoke_api_key_not_found", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("revoke_api_key_failed", error=str(e), key_id=request.key_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )


# ==================== ROLE MANAGEMENT ENDPOINTS ====================

@router.get(
    "/roles",
    response_model=List[RoleInfo],
    summary="List Available Roles",
    description="Get all available roles in the system"
)
async def list_roles(
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    List all roles (admin, editor, viewer, guest).
    """
    try:
        roles = await rbac_service.list_roles()

        logger.debug("roles_listed", count=len(roles))

        return roles

    except Exception as e:
        logger.error("list_roles_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list roles: {str(e)}"
        )


@router.post(
    "/users/assign-role",
    response_model=UserRoleInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Role to User",
    description="Assign a role to a user (admin only)"
)
async def assign_user_role(
    request: UserRoleAssignRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service),
    _: bool = Depends(require_admin)  # Only admins can assign roles
):
    """
    Assign a role to a user. Only admins can assign roles.
    """
    try:
        result = await rbac_service.assign_user_role(
            user_id=request.user_id,
            role_name=request.role_name.value,  # Convert enum to string
            granted_by=current_user,
            expires_at=request.expires_at,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "user_role_assigned",
            user_id=request.user_id,
            role=request.role_name,
            granted_by=current_user
        )

        return UserRoleInfo(**result)

    except ValueError as e:
        logger.warning("assign_role_invalid", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("assign_user_role_failed", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign role: {str(e)}"
        )


@router.post(
    "/users/revoke-role",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Role from User",
    description="Revoke a role from a user (admin only)"
)
async def revoke_user_role(
    request: UserRoleRevokeRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service),
    _: bool = Depends(require_admin)  # Only admins can revoke roles
):
    """
    Revoke a role from a user. Only admins can revoke roles.
    """
    try:
        await rbac_service.revoke_user_role(
            user_id=request.user_id,
            role_name=request.role_name.value,  # Convert enum to string
            revoked_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "user_role_revoked",
            user_id=request.user_id,
            role=request.role_name,
            revoked_by=current_user
        )

    except ValueError as e:
        logger.warning("revoke_role_invalid", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("revoke_user_role_failed", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke role: {str(e)}"
        )


@router.get(
    "/users/{user_id}/roles",
    response_model=List[UserRoleInfo],
    summary="Get User Roles",
    description="Get all active roles for a specific user"
)
async def get_user_roles(
    user_id: str,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Get all roles for a user. Regular users can only see their own roles.
    """
    try:
        # Check if user is trying to access other user's roles
        if user_id != current_user:
            # Verify user is admin
            try:
                await require_admin(current_user=current_user, rbac_service=rbac_service)
            except HTTPException:
                logger.warning(
                    "non_admin_attempted_view_other_roles",
                    user_id=current_user,
                    requested_user=user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own roles"
                )

        roles = await rbac_service.get_user_roles(user_id=user_id)

        logger.debug("user_roles_retrieved", user_id=user_id, count=len(roles))

        return roles

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_roles_failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user roles: {str(e)}"
        )


# ==================== AUDIT LOG ENDPOINTS ====================

@router.get(
    "/audit-logs",
    response_model=List[AuditLogEntry],
    summary="Get Audit Logs",
    description="Get audit logs for RBAC events (admin only)"
)
async def get_audit_logs(
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service),
    _: bool = Depends(require_admin),  # Only admins can view audit logs
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get audit logs for RBAC operations. Only admins can view audit logs.
    
    Args:
        event_type: Filter by event type (api_key_created, role_assigned, etc.)
        user_id: Filter by actor or target user ID
        limit: Maximum number of records (default 100)
        offset: Offset for pagination (default 0)
    """
    try:
        logs = await rbac_service.get_audit_logs(
            event_type=event_type,
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        logger.info(
            "audit_logs_retrieved",
            viewer=current_user,
            count=len(logs),
            event_type=event_type,
            user_id=user_id
        )

        return logs

    except Exception as e:
        logger.error("get_audit_logs_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit logs: {str(e)}"
        )
