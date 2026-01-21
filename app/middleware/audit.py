"""
Audit Logging Middleware - Task 41.5
Captures security events and persists to audit_logs table
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict, Any
import structlog
import time
from datetime import datetime
import json
import ipaddress

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log security-relevant events to audit_logs table

    Captures:
    - Authentication events (login, logout)
    - Data access (document queries, exports)
    - Administrative actions (config changes, user management)
    - Security violations (rate limiting, invalid input)
    - System errors (500 errors, exceptions)
    """

    def __init__(
        self,
        app,
        exempt_paths: Optional[list[str]] = None
    ):
        super().__init__(app)
        # Paths that don't need audit logging (health checks, metrics, docs)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/health/live",
            "/health/ready",
            "/health/detailed",
            "/monitoring/metrics",
            "/monitoring/stats",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static"
        ]

        # Event types mapping based on endpoints
        self.event_type_mapping = {
            "/api/users/login": "user_login",
            "/api/users/logout": "user_logout",
            "/api/documents/upload": "document_upload",
            "/api/documents/delete": "document_delete",
            "/api/users/export": "data_export",
            "/api/users/delete": "user_deletion",
            "/api/rbac": "rbac_change",
            "/api/monitoring": "config_change"
        }

    async def dispatch(self, request: Request, call_next):
        """Process request and log audit events"""

        # Skip exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Capture request start time
        start_time = time.time()

        # Extract user context from headers/auth
        user_id = self._extract_user_id(request)
        ip_address = self._extract_ip(request)

        # Process request
        response = None
        error_message = None

        try:
            response = await call_next(request)

            # Log audit event after successful processing
            await self._log_audit_event(
                request=request,
                response=response,
                user_id=user_id,
                ip_address=ip_address,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=None
            )

            return response

        except Exception as e:
            # Log system error
            error_message = str(e)

            logger.error(
                "request_failed",
                path=request.url.path,
                error=error_message,
                user_id=user_id
            )

            # Create error response
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )

            # Log audit event for error
            await self._log_audit_event(
                request=request,
                response=response,
                user_id=user_id,
                ip_address=ip_address,
                duration_ms=int((time.time() - start_time) * 1000),
                error_message=error_message
            )

            return response

    def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request headers or auth context"""

        # Try Authorization header (JWT)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # In production, decode JWT and extract user_id
            # For now, check if user context was set by RLS middleware
            pass

        # Try custom user ID header
        user_id = request.headers.get("x-user-id")
        if user_id:
            return user_id

        # Try session cookie
        # session = request.cookies.get("session_id")
        # if session:
        #     return self._lookup_session_user(session)

        # Anonymous user
        return None

    def _extract_ip(self, request: Request) -> str:
        """Extract client IP address from request"""

        def is_valid_ip(ip_str: str) -> bool:
            """Check if string is a valid IP address"""
            try:
                ipaddress.ip_address(ip_str)
                return True
            except ValueError:
                return False

        # Check for proxy headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take first IP if multiple (client IP)
            ip = forwarded.split(",")[0].strip()
            if is_valid_ip(ip):
                return ip

        real_ip = request.headers.get("x-real-ip")
        if real_ip and is_valid_ip(real_ip):
            return real_ip

        # Fallback to direct client
        if request.client and request.client.host:
            host = request.client.host
            if is_valid_ip(host):
                return host

        # Default to localhost for test clients or unknown sources
        return "127.0.0.1"

    def _determine_event_type(self, request: Request, response: Response) -> str:
        """Determine event type based on request path and response"""

        path = request.url.path
        method = request.method
        status = response.status_code

        # Check explicit mapping
        for pattern, event_type in self.event_type_mapping.items():
            if path.startswith(pattern):
                return event_type

        # Rate limiting violations
        if status == 429:
            return "policy_violation"

        # Authentication failures
        if status == 401:
            return "auth_failure"

        # Authorization failures
        if status == 403:
            return "authz_failure"

        # Server errors
        if status >= 500:
            return "system_error"

        # Data access (queries, retrieval)
        if "query" in path or "search" in path:
            return "data_access"

        # Default based on method
        if method in ["POST", "PUT", "PATCH"]:
            return "data_modification"
        elif method == "DELETE":
            return "data_deletion"
        elif method == "GET":
            return "data_access"

        return "other"

    async def _log_audit_event(
        self,
        request: Request,
        response: Response,
        user_id: Optional[str],
        ip_address: str,
        duration_ms: int,
        error_message: Optional[str]
    ):
        """Persist audit log to Supabase"""

        try:
            supabase = get_supabase_client()

            # Determine event type
            event_type = self._determine_event_type(request, response)

            # Build metadata
            metadata = {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_agent": request.headers.get("user-agent", "unknown"),
                "referer": request.headers.get("referer"),
            }

            # Add query parameters (sanitized)
            if request.query_params:
                metadata["query_params"] = dict(request.query_params)

            # Add error details if present
            if error_message:
                metadata["error"] = error_message

            # Add request body size
            content_length = request.headers.get("content-length")
            if content_length:
                metadata["content_length"] = int(content_length)

            # Insert audit log
            supabase.table("audit_logs").insert({
                "user_id": user_id,
                "event_type": event_type,
                "ip_address": ip_address,
                "resource_type": self._extract_resource_type(request.url.path),
                "resource_id": self._extract_resource_id(request.url.path),
                "action": f"{request.method} {request.url.path}",
                "metadata": json.dumps(metadata),
                "severity": self._determine_severity(response.status_code, event_type),
                "category": self._determine_category(request.url.path, event_type),
                "status": "success" if response.status_code < 400 else "failure"
            }).execute()

            logger.debug(
                "audit_log_created",
                event_type=event_type,
                user_id=user_id,
                status=response.status_code
            )

        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error(
                "audit_logging_failed",
                error=str(e),
                path=request.url.path
            )

    def _extract_resource_type(self, path: str) -> Optional[str]:
        """Extract resource type from URL path"""

        if "/documents" in path:
            return "document"
        elif "/users" in path:
            return "user"
        elif "/sessions" in path:
            return "session"
        elif "/crewai" in path:
            return "crewai_task"
        elif "/query" in path:
            return "query"

        return None

    def _extract_resource_id(self, path: str) -> Optional[str]:
        """Extract resource ID from URL path if present"""

        # Look for UUID or numeric ID in path segments
        import re

        # UUID pattern
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        uuid_match = re.search(uuid_pattern, path, re.IGNORECASE)
        if uuid_match:
            return uuid_match.group(0)

        # Numeric ID pattern (e.g., /users/123)
        id_pattern = r'/(\d+)(?:/|$)'
        id_match = re.search(id_pattern, path)
        if id_match:
            return id_match.group(1)

        return None

    def _determine_category(self, path: str, event_type: str) -> str:
        """Determine audit log category based on path and event type"""

        # Authentication/Authorization
        if event_type in ["user_login", "user_logout", "auth_failure", "authz_failure"]:
            return "authentication"

        # Security violations
        if event_type == "policy_violation":
            return "security"

        # Data operations
        if event_type in ["data_access", "data_modification", "data_deletion", "data_export"]:
            return "data"

        # System events
        if event_type == "system_error":
            return "system"

        # Administrative actions
        if event_type in ["rbac_change", "config_change", "user_deletion"]:
            return "admin"

        # Document operations
        if event_type in ["document_upload", "document_delete"]:
            return "document"

        # API operations (default)
        return "api"

    def _determine_severity(self, status_code: int, event_type: str) -> str:
        """Determine log severity level"""

        # Critical events
        if event_type in ["system_error", "policy_violation"]:
            return "error"

        # Server errors
        if status_code >= 500:
            return "error"

        # Client errors (except 401/403 which are info)
        if status_code >= 400:
            if status_code in [401, 403]:
                return "info"
            return "warning"

        # Security-relevant events
        if event_type in ["user_login", "user_logout", "data_export", "rbac_change"]:
            return "info"

        # Normal operations
        return "info"


def configure_audit_logging(app):
    """
    Configure audit logging middleware

    Args:
        app: FastAPI application instance
    """

    # Add audit logging middleware
    app.add_middleware(AuditLoggingMiddleware)

    logger.info("audit_logging_configured")
