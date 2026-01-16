"""
Empire v7.3 - WebSocket Authentication Middleware
Task 152: WebSocket Authentication with JWT Validation

Implements JWT validation for WebSocket connections, token refresh
mechanism for long-running connections, and connection timeout/heartbeat
functionality.

Security Features:
- JWT validation during WebSocket handshake
- Token extraction from query params or headers
- Automatic token refresh before expiration
- Connection timeout with heartbeat monitoring
- Graceful degradation with anonymous support
"""

from fastapi import WebSocket, WebSocketDisconnect, status
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
import jwt
import os
import time
import structlog

from app.services.rbac_service import get_rbac_service

logger = structlog.get_logger(__name__)

# Configuration
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
JWT_ALGORITHM = "HS256"
DEFAULT_HEARTBEAT_INTERVAL = 30  # seconds
DEFAULT_CONNECTION_TIMEOUT = 120  # seconds
TOKEN_REFRESH_THRESHOLD = 300  # seconds before expiry to trigger refresh


@dataclass
class WebSocketAuthContext:
    """
    Authentication context for WebSocket connections.

    Stores user authentication state and connection metadata.
    """
    user_id: Optional[str] = None
    role: str = "guest"
    token: Optional[str] = None
    token_exp: Optional[datetime] = None
    is_authenticated: bool = False
    connection_time: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebSocketAuthMiddleware:
    """
    Middleware for authenticating WebSocket connections.

    Supports:
    - JWT token validation from query params or headers
    - Token refresh for long-running connections
    - Heartbeat monitoring for connection health
    - Graceful degradation for unauthenticated connections
    """

    def __init__(
        self,
        require_auth: bool = False,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT,
        allow_anonymous: bool = True
    ):
        """
        Initialize WebSocket authentication middleware.

        Args:
            require_auth: If True, reject unauthenticated connections
            heartbeat_interval: Seconds between expected heartbeats
            connection_timeout: Seconds before connection is considered stale
            allow_anonymous: If True, allow connections without auth
        """
        self.require_auth = require_auth
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout
        self.allow_anonymous = allow_anonymous

    async def authenticate(self, websocket: WebSocket) -> WebSocketAuthContext:
        """
        Authenticate a WebSocket connection.

        Extracts and validates JWT token from:
        1. Query parameter 'token'
        2. Query parameter 'authorization'
        3. WebSocket subprotocol header

        Args:
            websocket: WebSocket connection to authenticate

        Returns:
            WebSocketAuthContext with authentication state

        Raises:
            WebSocketDisconnect: If authentication fails and required
        """
        context = WebSocketAuthContext()

        # Extract token from various sources
        token = await self._extract_token(websocket)

        if token:
            try:
                # Validate the JWT token
                payload = await self._validate_token(token)

                if payload:
                    context.user_id = payload.get("sub")
                    context.token = token
                    context.is_authenticated = True

                    # Store expiration for refresh handling
                    if "exp" in payload:
                        context.token_exp = datetime.fromtimestamp(payload["exp"])

                    # Get user role from RBAC service
                    if context.user_id:
                        context.role = await self._get_user_role(context.user_id)

                    logger.info(
                        "websocket_auth_success",
                        user_id=context.user_id,
                        role=context.role
                    )

            except jwt.ExpiredSignatureError:
                logger.warning("websocket_token_expired")
                if self.require_auth:
                    await websocket.close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="Token expired"
                    )
                    raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            except jwt.InvalidTokenError as e:
                logger.warning("websocket_token_invalid", error=str(e))
                if self.require_auth:
                    await websocket.close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="Invalid token"
                    )
                    raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

        else:
            # No token provided
            if self.require_auth and not self.allow_anonymous:
                logger.warning("websocket_auth_missing_token")
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Authentication required"
                )
                raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

            # Set anonymous context
            context.user_id = "anonymous"
            context.role = "guest"
            logger.debug("websocket_anonymous_connection")

        # Store context in websocket state for later access
        websocket.state.auth_context = context

        return context

    async def _extract_token(self, websocket: WebSocket) -> Optional[str]:
        """
        Extract JWT token from WebSocket connection.

        Priority:
        1. Query parameter 'token'
        2. Query parameter 'authorization' (Bearer token)
        3. Sec-WebSocket-Protocol header

        Args:
            websocket: WebSocket connection

        Returns:
            Token string if found, None otherwise
        """
        # Try query parameters first (most common for WebSockets)
        token = websocket.query_params.get("token")
        if token:
            return token

        # Try authorization query param (Bearer format)
        auth = websocket.query_params.get("authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]

        # Try subprotocol header (for browsers that support it)
        # Format: "Bearer.{token}" as subprotocol
        protocols = websocket.headers.get("sec-websocket-protocol", "").split(",")
        for protocol in protocols:
            protocol = protocol.strip()
            if protocol.startswith("Bearer."):
                return protocol[7:]

        return None

    async def _validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and return payload.

        Args:
            token: JWT token string

        Returns:
            Token payload if valid, None otherwise

        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        if not CLERK_SECRET_KEY:
            logger.warning("websocket_auth_no_secret_key")
            return None

        payload = jwt.decode(
            token,
            CLERK_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_signature": True, "verify_exp": True}
        )

        return payload

    async def _get_user_role(self, user_id: str) -> str:
        """
        Get user's primary role from RBAC service.

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

            primary_role = max(
                user_roles,
                key=lambda r: role_priority.get(r, 0),
                default="guest"
            )
            return primary_role

        except Exception as e:
            logger.warning("websocket_get_role_failed", error=str(e), user_id=user_id)
            return "guest"


class WebSocketConnectionMonitor:
    """
    Monitor WebSocket connections for heartbeat and timeout.

    Implements:
    - Heartbeat ping/pong mechanism
    - Connection timeout detection
    - Token refresh notifications
    """

    def __init__(
        self,
        websocket: WebSocket,
        auth_context: WebSocketAuthContext,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT,
        on_timeout: Optional[Callable] = None,
        on_token_refresh_needed: Optional[Callable] = None
    ):
        """
        Initialize connection monitor.

        Args:
            websocket: WebSocket connection to monitor
            auth_context: Authentication context
            heartbeat_interval: Seconds between heartbeat checks
            connection_timeout: Seconds before connection is considered stale
            on_timeout: Callback when connection times out
            on_token_refresh_needed: Callback when token refresh is needed
        """
        self.websocket = websocket
        self.auth_context = auth_context
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout
        self.on_timeout = on_timeout
        self.on_token_refresh_needed = on_token_refresh_needed

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the connection monitor."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.debug(
            "websocket_monitor_started",
            user_id=self.auth_context.user_id,
            heartbeat_interval=self.heartbeat_interval
        )

    async def stop(self):
        """Stop the connection monitor."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.debug(
            "websocket_monitor_stopped",
            user_id=self.auth_context.user_id
        )

    def update_heartbeat(self):
        """Update the last heartbeat timestamp."""
        self.auth_context.last_heartbeat = time.time()

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval / 2)

                if not self._running:
                    break

                # Check for connection timeout
                elapsed = time.time() - self.auth_context.last_heartbeat
                if elapsed > self.connection_timeout:
                    logger.warning(
                        "websocket_connection_timeout",
                        user_id=self.auth_context.user_id,
                        elapsed=elapsed
                    )
                    if self.on_timeout:
                        await self.on_timeout()
                    break

                # Check if token refresh is needed
                if self.auth_context.token_exp:
                    time_to_expiry = (
                        self.auth_context.token_exp - datetime.utcnow()
                    ).total_seconds()

                    if 0 < time_to_expiry < TOKEN_REFRESH_THRESHOLD:
                        logger.info(
                            "websocket_token_refresh_needed",
                            user_id=self.auth_context.user_id,
                            expires_in=time_to_expiry
                        )
                        if self.on_token_refresh_needed:
                            await self.on_token_refresh_needed()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "websocket_monitor_error",
                    error=str(e),
                    user_id=self.auth_context.user_id
                )


async def websocket_auth_middleware(
    websocket: WebSocket,
    require_auth: bool = False,
    allow_anonymous: bool = True
) -> Optional[WebSocketAuthContext]:
    """
    Convenience function for WebSocket authentication.

    Use in WebSocket endpoints:

    ```python
    @router.websocket("/ws/protected")
    async def protected_websocket(websocket: WebSocket):
        auth_context = await websocket_auth_middleware(
            websocket,
            require_auth=True
        )
        if not auth_context:
            return

        # Connection is authenticated
        await websocket.accept()
        ...
    ```

    Args:
        websocket: WebSocket connection
        require_auth: If True, reject unauthenticated connections
        allow_anonymous: If True, allow connections without auth

    Returns:
        WebSocketAuthContext if authentication succeeds, None if connection closed
    """
    middleware = WebSocketAuthMiddleware(
        require_auth=require_auth,
        allow_anonymous=allow_anonymous
    )

    try:
        return await middleware.authenticate(websocket)
    except WebSocketDisconnect:
        return None


async def handle_websocket_message(
    websocket: WebSocket,
    message: Dict[str, Any],
    auth_context: WebSocketAuthContext,
    monitor: Optional[WebSocketConnectionMonitor] = None
) -> Optional[Dict[str, Any]]:
    """
    Handle incoming WebSocket messages with built-in support for
    heartbeat and token refresh events.

    Args:
        websocket: WebSocket connection
        message: Incoming message
        auth_context: Authentication context
        monitor: Optional connection monitor

    Returns:
        Response message if applicable, None otherwise
    """
    event_type = message.get("event") or message.get("type")

    if event_type == "heartbeat" or event_type == "ping":
        # Update heartbeat timestamp
        if monitor:
            monitor.update_heartbeat()

        return {
            "event": "pong",
            "timestamp": time.time(),
            "server_time": datetime.utcnow().isoformat()
        }

    elif event_type == "refresh_token":
        # Handle token refresh request
        new_token = message.get("data", {}).get("token") or message.get("token")

        if new_token:
            try:
                middleware = WebSocketAuthMiddleware()
                payload = await middleware._validate_token(new_token)

                if payload:
                    auth_context.token = new_token
                    auth_context.user_id = payload.get("sub")
                    if "exp" in payload:
                        auth_context.token_exp = datetime.fromtimestamp(payload["exp"])

                    logger.info(
                        "websocket_token_refreshed",
                        user_id=auth_context.user_id
                    )

                    return {
                        "event": "token_refresh_success",
                        "user_id": auth_context.user_id,
                        "expires_at": auth_context.token_exp.isoformat() if auth_context.token_exp else None
                    }

            except Exception as e:
                logger.warning("websocket_token_refresh_failed", error=str(e))
                return {
                    "event": "token_refresh_failed",
                    "error": str(e)
                }

    return None


def create_token_refresh_message(expires_at: datetime) -> Dict[str, Any]:
    """
    Create a token refresh notification message.

    Send this to clients when their token is about to expire.

    Args:
        expires_at: Token expiration time

    Returns:
        Message dict to send to client
    """
    return {
        "event": "token_refresh_needed",
        "expires_at": expires_at.isoformat(),
        "expires_in_seconds": max(0, (expires_at - datetime.utcnow()).total_seconds()),
        "message": "Please refresh your authentication token"
    }


def create_timeout_warning_message(seconds_remaining: int) -> Dict[str, Any]:
    """
    Create a connection timeout warning message.

    Send this to clients when connection is about to timeout.

    Args:
        seconds_remaining: Seconds until timeout

    Returns:
        Message dict to send to client
    """
    return {
        "event": "timeout_warning",
        "seconds_remaining": seconds_remaining,
        "message": "Send heartbeat to keep connection alive"
    }
