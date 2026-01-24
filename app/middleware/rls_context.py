"""
Empire v7.3 - Row-Level Security (RLS) Context Middleware
Task 41.2 + Task 151: Database-Level Data Isolation

Sets PostgreSQL session variables for RLS policy enforcement.
This ensures that database-level policies can enforce user data isolation.

How it works:
1. After authentication succeeds, this middleware extracts user_id and role
2. Calls set_rls_context RPC to set PostgreSQL session variables
3. RLS policies in the database use these variables to filter queries
4. Ensures data isolation even if application-level security is bypassed

Security Benefits:
- Defense in depth: Database enforces isolation independently
- SQL injection mitigation: Attackers cannot access other users' data
- Compliance: GDPR, HIPAA, SOC 2 enforced at database level
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import structlog
import os
import uuid

from app.services.rbac_service import get_rbac_service
from app.core.database import db_manager

logger = structlog.get_logger(__name__)


class RLSContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set PostgreSQL session variables for RLS enforcement

    This middleware runs AFTER authentication but BEFORE route handlers.
    It extracts user context (user_id, role) and sets PostgreSQL session
    variables that RLS policies use to filter data.
    """

    def __init__(self, app):
        """
        Initialize RLS context middleware

        Args:
            app: FastAPI application
        """
        super().__init__(app)
        self.is_enabled = os.getenv("RLS_ENABLED", "true").lower() == "true"

        if not self.is_enabled:
            logger.warning("RLS context middleware disabled - set RLS_ENABLED=true to enable")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Set RLS context for authenticated requests

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response with RLS context set
        """
        # Skip RLS context for non-API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Skip RLS context for health checks and docs
        if request.url.path in ["/health", "/health/detailed", "/health/ready", "/health/live", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Skip if RLS is disabled
        if not self.is_enabled:
            return await call_next(request)

        # Extract user context from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        user_role = getattr(request.state, "user_role", "guest")

        # If no user_id, try to extract from authorization header
        if not user_id:
            authorization = request.headers.get("Authorization")

            if authorization:
                try:
                    # Get user_id from authentication
                    user_id = await self._get_user_from_auth(authorization, request)

                    # Get user's role
                    if user_id:
                        user_role = await self._get_user_role(user_id)

                        # Store in request state for other middleware
                        request.state.user_id = user_id
                        request.state.user_role = user_role

                except Exception as e:
                    logger.warning(
                        "rls_auth_extraction_failed",
                        error=str(e),
                        path=request.url.path
                    )

        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Set PostgreSQL session variables if user is authenticated
        if user_id:
            await self._set_rls_context(user_id, user_role, request_id)
            logger.debug(
                "rls_context_set",
                user_id=user_id,
                role=user_role,
                request_id=request_id,
                path=request.url.path
            )
        else:
            # For unauthenticated requests, set guest context
            await self._set_rls_context("anonymous", "guest", request_id)
            logger.debug(
                "rls_context_set_anonymous",
                request_id=request_id,
                path=request.url.path
            )

        # Process the request
        response = await call_next(request)

        # Clear RLS context after request (optional - connection pooling handles this)
        # await self._clear_rls_context()

        return response

    async def _get_user_from_auth(self, authorization: str, request: Request) -> str:
        """
        Extract user ID from authorization header

        Args:
            authorization: Authorization header value
            request: FastAPI request object

        Returns:
            User ID if authentication succeeds, None otherwise
        """
        from app.middleware.auth import get_current_user
        from app.services.rbac_service import get_rbac_service

        try:
            rbac_service = get_rbac_service()
            user_id = await get_current_user(authorization=authorization, rbac_service=rbac_service)
            return user_id
        except Exception as e:
            logger.debug("auth_extraction_failed", error=str(e))
            return None

    async def _get_user_role(self, user_id: str) -> str:
        """
        Get user's primary role

        Args:
            user_id: User ID

        Returns:
            Role name (admin, editor, viewer, guest)
        """
        try:
            rbac_service = get_rbac_service()
            roles = await rbac_service.get_user_roles(user_id)

            if not roles:
                return "guest"

            # Priority: admin > editor > viewer > guest
            role_priority = {"admin": 4, "editor": 3, "viewer": 2, "guest": 1}

            user_roles = [
                r.get("role", {}).get("role_name", "guest")
                for r in roles
                if r.get("role")
            ]

            # Return highest priority role
            primary_role = max(user_roles, key=lambda r: role_priority.get(r, 0), default="guest")
            return primary_role

        except Exception as e:
            logger.warning("get_user_role_failed", error=str(e), user_id=user_id)
            return "guest"

    async def _set_rls_context(self, user_id: str, role: str, request_id: str = None):
        """
        Set PostgreSQL session variables for RLS enforcement

        Calls the set_rls_context RPC function to set session variables:
        - app.current_user_id: Current user's ID
        - app.user_role: Current user's role (admin, editor, viewer, guest)
        - app.request_id: Unique request identifier for tracing

        These variables are used by RLS policies to filter data.

        Args:
            user_id: User ID to set
            role: User role to set
            request_id: Optional request ID for tracing
        """
        if not request_id:
            request_id = str(uuid.uuid4())

        try:
            # Get Supabase client and call the RPC function
            supabase = db_manager.get_supabase()

            result = supabase.rpc(  # noqa: F841
                "set_rls_context",
                {
                    "p_user_id": user_id,
                    "p_role": role,
                    "p_request_id": request_id
                }
            ).execute()

            logger.debug(
                "rls_context_set_success",
                user_id=user_id,
                role=role,
                request_id=request_id
            )

        except Exception as e:
            # Log but don't fail - graceful degradation
            logger.warning(
                "rls_context_rpc_failed",
                user_id=user_id,
                role=role,
                request_id=request_id,
                error=str(e),
                note="Continuing without database-level RLS context"
            )

    async def _clear_rls_context(self):
        """
        Clear PostgreSQL session variables (optional)

        Note: This is usually not necessary as connection pooling
        will reset the session variables automatically.
        """
        try:
            supabase = db_manager.get_supabase()
            supabase.rpc("clear_rls_context", {}).execute()
        except Exception as e:
            logger.debug("rls_context_clear_failed", error=str(e))


def configure_rls_context(app):
    """
    Configure RLS context middleware for FastAPI application

    Args:
        app: FastAPI application instance
    """
    # Add RLS context middleware
    app.add_middleware(RLSContextMiddleware)

    is_enabled = os.getenv("RLS_ENABLED", "true").lower() == "true"

    if is_enabled:
        logger.info("🔒 RLS context middleware enabled - database-level data isolation active")
    else:
        logger.warning("⚠️  RLS context middleware disabled - set RLS_ENABLED=true to enable")
