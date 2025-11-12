"""
Empire v7.3 - User Management API Routes
FastAPI endpoints for user CRUD operations, password management, and account suspension.

Endpoints:
- User CRUD (create, list, get, update, delete)
- Password Management (change, admin reset)
- Account Status (suspend, activate)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import Optional
import structlog

from app.models.users import (
    CreateUserRequest, CreateUserResponse,
    UpdateUserRequest, UserResponse, UserListResponse,
    ChangePasswordRequest, AdminResetPasswordRequest, PasswordResetResponse,
    SuspendUserRequest, ActivateUserRequest, UserSuspensionResponse,
    ActivityLogEntry, ActivityLogListResponse,
    UserDataExport, GDPRDeleteResponse
)
from app.services.user_service import UserService, get_user_service
from app.middleware.auth import get_current_user, require_admin

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/users", tags=["User Management"])


# ==================== USER CRUD ENDPOINTS ====================

@router.post(
    "",
    response_model=CreateUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create a new admin user (admin only)"
)
async def create_user(
    request: CreateUserRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can create users
):
    """
    Create a new user account. Only admins can create users.

    Returns:
        CreateUserResponse with user_id, username, email
    """
    try:
        result = await user_service.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role.value,  # Convert enum to string
            created_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "User created via API",
            user_id=result["user_id"],
            username=result["username"],
            created_by=current_user
        )

        return CreateUserResponse(
            user_id=result["user_id"],
            username=result["username"],
            email=result["email"]
        )

    except ValueError as e:
        logger.warning("Create user validation failed", error=str(e), username=request.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Create user failed", error=str(e), username=request.username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get(
    "",
    response_model=UserListResponse,
    summary="List Users",
    description="List all users with pagination and filtering (admin only)"
)
async def list_users(
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin),  # Only admins can list users
    page: int = 1,
    page_size: int = 50,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """
    List all users. Only admins can view the user list.

    Args:
        page: Page number (1-indexed)
        page_size: Number of users per page
        role: Filter by role (admin, editor, viewer, guest)
        is_active: Filter by active status

    Returns:
        UserListResponse with users list and pagination info
    """
    try:
        offset = (page - 1) * page_size

        users = await user_service.list_users(
            limit=page_size + 1,  # Fetch one extra to check if there are more
            offset=offset,
            role_filter=role,
            is_active=is_active
        )

        # Check if there are more results
        has_more = len(users) > page_size
        if has_more:
            users = users[:page_size]  # Trim to page_size

        # Convert to response models
        user_responses = [
            UserResponse(**user) for user in users
        ]

        logger.debug(
            "Users listed",
            requester=current_user,
            count=len(user_responses),
            page=page,
            role_filter=role
        )

        return UserListResponse(
            users=user_responses,
            total=len(user_responses),  # Note: This is count for current page, not total in DB
            page=page,
            page_size=page_size,
            has_more=has_more
        )

    except Exception as e:
        logger.error("List users failed", error=str(e), requester=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get User",
    description="Get specific user details (admin only)"
)
async def get_user(
    user_id: str,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can view user details
):
    """
    Get details for a specific user. Only admins can view user details.

    Args:
        user_id: User ID to retrieve

    Returns:
        UserResponse with user details
    """
    try:
        user = await user_service.get_user(user_id=user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found"
            )

        logger.debug("User retrieved", user_id=user_id, requester=current_user)

        return UserResponse(**user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get user failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update User",
    description="Update user information (admin only)"
)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can update users
):
    """
    Update user information. Only admins can update users.

    Args:
        user_id: User ID to update
        request: Update request with new values

    Returns:
        UserResponse with updated user data
    """
    try:
        user = await user_service.update_user(
            user_id=user_id,
            email=request.email,
            full_name=request.full_name,
            role=request.role.value if request.role else None,
            updated_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "User updated",
            user_id=user_id,
            updated_by=current_user,
            changes=request.dict(exclude_none=True)
        )

        return UserResponse(**user)

    except ValueError as e:
        logger.warning("Update user validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Update user failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User",
    description="Delete user account (admin only)"
)
async def delete_user(
    user_id: str,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can delete users
):
    """
    Delete a user account. Only admins can delete users.

    Args:
        user_id: User ID to delete
    """
    try:
        await user_service.delete_user(
            user_id=user_id,
            deleted_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info("User deleted", user_id=user_id, deleted_by=current_user)

    except ValueError as e:
        logger.warning("Delete user validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Delete user failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


# ==================== PASSWORD MANAGEMENT ENDPOINTS ====================

@router.post(
    "/change-password",
    response_model=PasswordResetResponse,
    summary="Change Password",
    description="Change own password (requires current password)"
)
async def change_password(
    request: ChangePasswordRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """
    Change your own password. Requires current password for verification.

    Returns:
        PasswordResetResponse with success message
    """
    try:
        await user_service.change_password(
            user_id=current_user,
            current_password=request.current_password,
            new_password=request.new_password,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info("Password changed (self-service)", user_id=current_user)

        return PasswordResetResponse(user_id=current_user)

    except ValueError as e:
        logger.warning("Change password validation failed", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Change password failed", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    summary="Reset Password (Admin)",
    description="Admin-initiated password reset (admin only)"
)
async def admin_reset_password(
    user_id: str,
    request: AdminResetPasswordRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can reset passwords
):
    """
    Reset user password as admin. Only admins can reset passwords.

    Args:
        user_id: User ID whose password to reset
        request: New password

    Returns:
        PasswordResetResponse with success message
    """
    try:
        await user_service.admin_reset_password(
            user_id=user_id,
            new_password=request.new_password,
            admin_id=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info("Password reset by admin", user_id=user_id, admin_id=current_user)

        return PasswordResetResponse(
            user_id=user_id,
            message="Password reset successfully by admin"
        )

    except ValueError as e:
        logger.warning("Reset password validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Reset password failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset password: {str(e)}"
        )


# ==================== ACCOUNT STATUS ENDPOINTS ====================

@router.post(
    "/{user_id}/suspend",
    response_model=UserSuspensionResponse,
    summary="Suspend User",
    description="Suspend user account (admin only)"
)
async def suspend_user(
    user_id: str,
    request: SuspendUserRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can suspend users
):
    """
    Suspend a user account. Only admins can suspend users.

    Args:
        user_id: User ID to suspend
        request: Suspension request with reason

    Returns:
        UserSuspensionResponse with success message
    """
    try:
        await user_service.suspend_user(
            user_id=user_id,
            reason=request.reason,
            suspended_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info("User suspended", user_id=user_id, suspended_by=current_user, reason=request.reason)

        return UserSuspensionResponse(
            user_id=user_id,
            is_active=False,
            message="User suspended successfully"
        )

    except ValueError as e:
        logger.warning("Suspend user validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Suspend user failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to suspend user: {str(e)}"
        )


@router.post(
    "/{user_id}/activate",
    response_model=UserSuspensionResponse,
    summary="Activate User",
    description="Activate/reactivate user account (admin only)"
)
async def activate_user(
    user_id: str,
    request: ActivateUserRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can activate users
):
    """
    Activate or reactivate a user account. Only admins can activate users.

    Args:
        user_id: User ID to activate
        request: Activation request

    Returns:
        UserSuspensionResponse with success message
    """
    try:
        await user_service.activate_user(
            user_id=user_id,
            activated_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info("User activated", user_id=user_id, activated_by=current_user)

        return UserSuspensionResponse(
            user_id=user_id,
            is_active=True,
            message="User activated successfully"
        )

    except ValueError as e:
        logger.warning("Activate user validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Activate user failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}"
        )


# ==================== ACTIVITY LOG ENDPOINTS ====================

@router.get(
    "/activity-logs",
    response_model=ActivityLogListResponse,
    summary="Get Activity Logs",
    description="Get all user management activity logs (admin only)"
)
async def get_activity_logs(
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin),  # Only admins can view activity logs
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100
):
    """
    Get activity logs for user management operations. Only admins can view logs.

    Args:
        action_type: Filter by action type (user_created, user_updated, etc.)
        resource_type: Filter by resource type (user, role, etc.)
        user_id: Filter by user ID (either as actor or target)
        page: Page number (1-indexed)
        page_size: Number of logs per page (max 100)

    Returns:
        ActivityLogListResponse with activity logs and pagination info
    """
    try:
        # Limit page_size to 100
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size

        logs = await user_service.get_activity_logs(
            user_id=user_id,
            action_type=action_type,
            resource_type=resource_type,
            limit=page_size + 1,  # Fetch one extra to check if there are more
            offset=offset
        )

        # Check if there are more results
        has_more = len(logs) > page_size
        if has_more:
            logs = logs[:page_size]  # Trim to page_size

        # Convert to response models
        log_entries = [
            ActivityLogEntry(**log) for log in logs
        ]

        logger.debug(
            "Activity logs retrieved",
            requester=current_user,
            count=len(log_entries),
            page=page,
            filters={
                "action_type": action_type,
                "resource_type": resource_type,
                "user_id": user_id
            }
        )

        return ActivityLogListResponse(
            logs=log_entries,
            total=len(log_entries),  # Note: This is count for current page, not total in DB
            page=page,
            page_size=page_size,
            has_more=has_more
        )

    except Exception as e:
        logger.error("Get activity logs failed", error=str(e), requester=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity logs: {str(e)}"
        )


@router.get(
    "/{user_id}/activity",
    response_model=ActivityLogListResponse,
    summary="Get User Activity Logs",
    description="Get activity logs for a specific user (admin only)"
)
async def get_user_activity(
    user_id: str,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin),  # Only admins can view user activity
    action_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    """
    Get all activity logs related to a specific user. Only admins can view user activity.

    This includes both:
    - Actions performed BY the user (as admin_user_id)
    - Actions performed ON the user (as resource_id)

    Args:
        user_id: User ID to get activity for
        action_type: Optional filter by action type
        page: Page number (1-indexed)
        page_size: Number of logs per page (max 100)

    Returns:
        ActivityLogListResponse with activity logs for the user
    """
    try:
        # Limit page_size to 100
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size

        # Verify user exists
        user = await user_service.get_user(user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found"
            )

        logs = await user_service.get_activity_logs(
            user_id=user_id,
            action_type=action_type,
            resource_type="user",  # Focus on user-related actions
            limit=page_size + 1,
            offset=offset
        )

        # Check if there are more results
        has_more = len(logs) > page_size
        if has_more:
            logs = logs[:page_size]

        # Convert to response models
        log_entries = [
            ActivityLogEntry(**log) for log in logs
        ]

        logger.debug(
            "User activity logs retrieved",
            requester=current_user,
            target_user=user_id,
            count=len(log_entries),
            page=page
        )

        return ActivityLogListResponse(
            logs=log_entries,
            total=len(log_entries),
            page=page,
            page_size=page_size,
            has_more=has_more
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get user activity failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user activity: {str(e)}"
        )


# ==================== GDPR COMPLIANCE ENDPOINTS ====================

@router.get(
    "/{user_id}/export",
    response_model=UserDataExport,
    summary="Export User Data (GDPR)",
    description="Export all user data for GDPR compliance (admin only)"
)
async def export_user_data(
    user_id: str,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can export user data
):
    """
    Export all user data for GDPR compliance. Only admins can export user data.

    This includes:
    - User profile (username, email, role, etc.)
    - All activity logs (as actor and subject)
    - Session history
    - API keys (without sensitive key material)
    - Role assignments

    Args:
        user_id: User ID to export data for

    Returns:
        UserDataExport with complete user data in machine-readable format
    """
    try:
        # Verify user exists
        user = await user_service.get_user(user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found"
            )

        export_data = await user_service.export_user_data(
            user_id=user_id,
            exported_by=current_user
        )

        logger.info(
            "User data exported via API",
            user_id=user_id,
            exported_by=current_user
        )

        return UserDataExport(**export_data)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("Export user data validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Export user data failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export user data: {str(e)}"
        )


@router.delete(
    "/{user_id}/gdpr-delete",
    response_model=GDPRDeleteResponse,
    summary="Delete User (GDPR)",
    description="GDPR-compliant user deletion with audit log anonymization (admin only)"
)
async def gdpr_delete_user(
    user_id: str,
    http_request: Request,
    current_user: str = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    _: bool = Depends(require_admin)  # Only admins can perform GDPR deletion
):
    """
    GDPR-compliant deletion of user account. Only admins can perform GDPR deletion.

    This operation:
    - Deletes user profile from admin_users
    - Deletes all user sessions
    - Deletes all API keys
    - Deletes role assignments
    - Anonymizes activity logs (preserves audit trail but removes PII)

    **WARNING: This operation cannot be undone.**

    Args:
        user_id: User ID to delete

    Returns:
        GDPRDeleteResponse with deletion statistics
    """
    try:
        # Prevent self-deletion
        if user_id == current_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot perform GDPR deletion on your own account"
            )

        result = await user_service.gdpr_delete_user(
            user_id=user_id,
            deleted_by=current_user,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None
        )

        logger.info(
            "User GDPR deleted via API",
            user_id=user_id,
            deleted_by=current_user,
            items_deleted=result["items_deleted"],
            items_anonymized=result["items_anonymized"]
        )

        return GDPRDeleteResponse(
            user_id=user_id,
            deleted=result["deleted"],
            items_deleted=result["items_deleted"],
            anonymized=result["items_anonymized"],
            message="User data deleted successfully in accordance with GDPR"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("GDPR delete validation failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("GDPR delete failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform GDPR deletion: {str(e)}"
        )
