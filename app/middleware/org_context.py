"""
Empire v7.3 - Organization Context Middleware
Validates X-Org-Id header and caches org membership per request.

When present, validates:
1. Header is a valid UUID
2. User is a member of the org
3. Stores org_id and user_role in request.state for downstream use

Endpoints that don't require org context (health, auth, etc.) skip validation.
"""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

# Paths that don't require org context
SKIP_PATHS = frozenset({
    "/health", "/health/", "/health/detailed", "/health/ready", "/health/live",
    "/docs", "/redoc", "/openapi.json",
    "/monitoring/metrics", "/monitoring/stats",
    "/", "/api/organizations",
})

SKIP_PREFIXES = (
    "/static/",
    "/ws/",
    "/api/health",
)


class OrgContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates X-Org-Id header and caches membership.

    Sets on request.state:
      - org_id: str | None
      - org_role: str | None  (owner/admin/member/viewer)
    """

    async def dispatch(self, request: Request, call_next):
        # Initialize state
        request.state.org_id = None
        request.state.org_role = None

        # Skip paths that don't need org context
        path = request.url.path.rstrip("/")
        if path in SKIP_PATHS or any(path.startswith(p) for p in SKIP_PREFIXES):
            return await call_next(request)

        # Check for X-Org-Id header
        org_id = request.headers.get("X-Org-Id") or request.headers.get("x-org-id")
        if not org_id:
            # No org header — proceed without org context
            # Individual endpoints can enforce org requirement if needed
            return await call_next(request)

        # Validate UUID format
        import uuid
        try:
            uuid.UUID(org_id)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid X-Org-Id header: must be a valid UUID"},
            )

        # Get user_id from auth (may not be set yet if auth middleware runs after)
        # We'll do a lightweight check — if user isn't authed, let the auth middleware handle it
        user_id = getattr(request.state, "user_id", None)

        if user_id:
            # Validate membership
            try:
                from app.services.organization_service import get_organization_service
                org_service = get_organization_service()
                role = await org_service.verify_membership(org_id, user_id)

                if not role:
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Not a member of this organization"},
                    )

                request.state.org_id = org_id
                request.state.org_role = role
            except Exception as e:
                logger.warning("Org membership check failed", org_id=org_id, error=str(e))
                # Proceed without org context — let individual endpoints handle
                request.state.org_id = org_id
        else:
            # Auth hasn't run yet — store org_id, validation happens at endpoint level
            request.state.org_id = org_id

        return await call_next(request)


def configure_org_context(app):
    """Add org context middleware to the FastAPI app."""
    app.add_middleware(OrgContextMiddleware)
    logger.info("org_context_middleware_enabled")
