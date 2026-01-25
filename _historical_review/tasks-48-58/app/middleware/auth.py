"""
Empire v7.3 - Authentication Middleware
Handles authentication and authorization for RBAC endpoints.
Supports both API keys and JWT tokens.
"""

from fastapi import HTTPException, status, Header, Depends
from typing import Optional
import structlog

from app.services.rbac_service import RBACService, get_rbac_service

logger = structlog.get_logger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> str:
    """
    Extract and validate user from JWT or API key.

    Supports two authentication methods:
    1. API Key: Authorization header with emp_xxx format
    2. JWT Token: Authorization header with Bearer <token> format

    Args:
        authorization: Authorization header value
        rbac_service: RBAC service instance

    Returns:
        user_id: Validated user ID

    Raises:
        HTTPException: 401 if authentication fails
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check if API key (emp_xxx format)
    if authorization.startswith("emp_"):
        api_key = authorization
        key_record = await rbac_service.validate_api_key(api_key)

        if not key_record:
            logger.warning("api_key_authentication_failed", key_prefix=api_key[:12])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
                headers={"WWW-Authenticate": "Bearer"}
            )

        user_id = key_record["user_id"]
        logger.debug("api_key_authentication_success", user_id=user_id, key_id=key_record["id"])
        return user_id

    # Check if Bearer token (JWT from Clerk)
    elif authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1] if len(authorization.split(" ")) > 1 else ""

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Bearer token format",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Clerk JWT validation
        from app.middleware.clerk_auth import clerk_client

        try:
            # Verify the session token with Clerk
            session = clerk_client.sessions.verify_token(token)

            if not session:
                logger.warning("clerk_jwt_invalid")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired JWT token",
                    headers={"WWW-Authenticate": "Bearer"}
                )

            # Get user ID from session
            user_id = session.user_id
            logger.debug("jwt_authentication_success", user_id=user_id)
            return user_id

        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error("jwt_authentication_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"JWT authentication failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use API key (emp_xxx) or Bearer token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def require_admin(
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> bool:
    """
    Check if current user has admin role.

    Args:
        current_user: User ID from get_current_user dependency
        rbac_service: RBAC service instance

    Returns:
        True if user is admin

    Raises:
        HTTPException: 403 if user does not have admin role
    """
    try:
        # Get user's active roles
        roles = await rbac_service.get_user_roles(current_user)

        # Check if user has admin role
        is_admin = any(
            r.get("role", {}).get("role_name") == "admin"
            for r in roles
            if r.get("role")
        )

        if not is_admin:
            logger.warning(
                "admin_access_denied",
                user_id=current_user,
                roles=[r.get("role", {}).get("role_name") for r in roles]
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required for this operation"
            )

        logger.debug("admin_access_granted", user_id=current_user)
        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_check_failed", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify admin privileges: {str(e)}"
        )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> Optional[str]:
    """
    Optional authentication - returns None if no auth provided.

    Useful for endpoints that support both authenticated and anonymous access.

    Args:
        authorization: Authorization header value
        rbac_service: RBAC service instance

    Returns:
        user_id if authenticated, None if no auth provided

    Raises:
        HTTPException: 401 if auth provided but invalid
    """
    if not authorization:
        return None

    return await get_current_user(authorization=authorization, rbac_service=rbac_service)


async def require_role(
    required_role: str,
    current_user: str = Depends(get_current_user),
    rbac_service: RBACService = Depends(get_rbac_service)
) -> bool:
    """
    Check if current user has a specific role.

    Args:
        required_role: Role name required (admin, editor, viewer, guest)
        current_user: User ID from get_current_user dependency
        rbac_service: RBAC service instance

    Returns:
        True if user has the required role

    Raises:
        HTTPException: 403 if user does not have required role
    """
    try:
        # Get user's active roles
        roles = await rbac_service.get_user_roles(current_user)

        # Check if user has required role
        has_role = any(
            r.get("role", {}).get("role_name") == required_role
            for r in roles
            if r.get("role")
        )

        if not has_role:
            logger.warning(
                "role_access_denied",
                user_id=current_user,
                required_role=required_role,
                user_roles=[r.get("role", {}).get("role_name") for r in roles]
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required for this operation"
            )

        logger.debug("role_access_granted", user_id=current_user, role=required_role)
        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error("role_check_failed", error=str(e), user_id=current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify role privileges: {str(e)}"
        )
