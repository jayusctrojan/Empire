"""
Empire v7.3 - WebSocket Authentication Tests
Task 152: WebSocket Authentication with JWT Validation

Tests for:
- JWT validation during WebSocket handshake
- Token extraction from query params and headers
- Token refresh mechanism
- Connection timeout and heartbeat functionality
"""

import pytest
import asyncio
import time
import jwt
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket, status
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.middleware.websocket_auth import (
    WebSocketAuthMiddleware,
    WebSocketAuthContext,
    WebSocketConnectionMonitor,
    websocket_auth_middleware,
    handle_websocket_message,
    create_token_refresh_message,
    create_timeout_warning_message,
    TOKEN_REFRESH_THRESHOLD,
)


# Test constants
TEST_SECRET_KEY = "test_secret_key_for_jwt_signing"
TEST_USER_ID = "user_123"
TEST_ALGORITHM = "HS256"


def create_test_token(
    user_id: str = TEST_USER_ID,
    expires_in: int = 3600,
    expired: bool = False,
    extra_claims: dict = None
) -> str:
    """Create a test JWT token."""
    now = datetime.utcnow()

    if expired:
        exp = now - timedelta(seconds=60)
    else:
        exp = now + timedelta(seconds=expires_in)

    payload = {
        "sub": user_id,
        "exp": exp,
        "iat": now,
        "email": f"{user_id}@test.com",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, TEST_SECRET_KEY, algorithm=TEST_ALGORITHM)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    websocket = MagicMock(spec=WebSocket)
    websocket.query_params = {}
    websocket.headers = {}
    websocket.state = MagicMock()
    websocket.close = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_json = AsyncMock()
    return websocket


@pytest.fixture
def auth_context():
    """Create a test auth context."""
    return WebSocketAuthContext(
        user_id=TEST_USER_ID,
        role="viewer",
        is_authenticated=True,
        token=create_test_token(),
        token_exp=datetime.utcnow() + timedelta(hours=1)
    )


class TestWebSocketAuthContext:
    """Tests for WebSocketAuthContext dataclass."""

    def test_default_values(self):
        """Test default context values."""
        context = WebSocketAuthContext()

        assert context.user_id is None
        assert context.role == "guest"
        assert context.token is None
        assert context.is_authenticated is False
        assert context.connection_time is not None
        assert context.last_heartbeat > 0

    def test_authenticated_context(self):
        """Test authenticated context initialization."""
        token = create_test_token()
        context = WebSocketAuthContext(
            user_id=TEST_USER_ID,
            role="admin",
            token=token,
            is_authenticated=True
        )

        assert context.user_id == TEST_USER_ID
        assert context.role == "admin"
        assert context.token == token
        assert context.is_authenticated is True


class TestWebSocketAuthMiddleware:
    """Tests for WebSocketAuthMiddleware class."""

    @pytest.mark.asyncio
    async def test_extract_token_from_query_param(self, mock_websocket):
        """Test token extraction from query parameter."""
        token = create_test_token()
        mock_websocket.query_params = {"token": token}

        middleware = WebSocketAuthMiddleware()
        extracted = await middleware._extract_token(mock_websocket)

        assert extracted == token

    @pytest.mark.asyncio
    async def test_extract_token_from_authorization_param(self, mock_websocket):
        """Test token extraction from authorization query parameter."""
        token = create_test_token()
        mock_websocket.query_params = {"authorization": f"Bearer {token}"}

        middleware = WebSocketAuthMiddleware()
        extracted = await middleware._extract_token(mock_websocket)

        assert extracted == token

    @pytest.mark.asyncio
    async def test_extract_token_from_subprotocol(self, mock_websocket):
        """Test token extraction from WebSocket subprotocol header."""
        token = create_test_token()
        mock_websocket.query_params = {}
        mock_websocket.headers = {"sec-websocket-protocol": f"Bearer.{token}"}

        middleware = WebSocketAuthMiddleware()
        extracted = await middleware._extract_token(mock_websocket)

        assert extracted == token

    @pytest.mark.asyncio
    async def test_extract_token_priority(self, mock_websocket):
        """Test that query param token takes priority over header."""
        token1 = create_test_token(user_id="user1")
        token2 = create_test_token(user_id="user2")

        mock_websocket.query_params = {"token": token1}
        mock_websocket.headers = {"sec-websocket-protocol": f"Bearer.{token2}"}

        middleware = WebSocketAuthMiddleware()
        extracted = await middleware._extract_token(mock_websocket)

        assert extracted == token1

    @pytest.mark.asyncio
    async def test_no_token_returns_none(self, mock_websocket):
        """Test that missing token returns None."""
        mock_websocket.query_params = {}
        mock_websocket.headers = {}

        middleware = WebSocketAuthMiddleware()
        extracted = await middleware._extract_token(mock_websocket)

        assert extracted is None

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_validate_valid_token(self):
        """Test validation of a valid token."""
        token = create_test_token()
        middleware = WebSocketAuthMiddleware()

        payload = await middleware._validate_token(token)

        assert payload is not None
        assert payload["sub"] == TEST_USER_ID

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_validate_expired_token_raises(self):
        """Test that expired token raises ExpiredSignatureError."""
        token = create_test_token(expired=True)
        middleware = WebSocketAuthMiddleware()

        with pytest.raises(jwt.ExpiredSignatureError):
            await middleware._validate_token(token)

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_validate_invalid_token_raises(self):
        """Test that invalid token raises InvalidTokenError."""
        middleware = WebSocketAuthMiddleware()

        with pytest.raises(jwt.InvalidTokenError):
            await middleware._validate_token("invalid.token.here")

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    @patch("app.middleware.websocket_auth.get_rbac_service")
    async def test_authenticate_success(self, mock_rbac, mock_websocket):
        """Test successful authentication."""
        token = create_test_token()
        mock_websocket.query_params = {"token": token}

        # Mock RBAC service
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_user_roles = AsyncMock(return_value=[
            {"role": {"role_name": "viewer"}}
        ])
        mock_rbac.return_value = mock_rbac_instance

        middleware = WebSocketAuthMiddleware()
        context = await middleware.authenticate(mock_websocket)

        assert context.is_authenticated is True
        assert context.user_id == TEST_USER_ID
        assert context.role == "viewer"
        assert context.token == token

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_authenticate_no_token_anonymous(self, mock_websocket):
        """Test anonymous connection when no token provided."""
        mock_websocket.query_params = {}

        middleware = WebSocketAuthMiddleware(
            require_auth=False,
            allow_anonymous=True
        )
        context = await middleware.authenticate(mock_websocket)

        assert context.is_authenticated is False
        assert context.user_id == "anonymous"
        assert context.role == "guest"

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_authenticate_required_no_token_closes(self, mock_websocket):
        """Test that required auth closes connection if no token."""
        mock_websocket.query_params = {}

        middleware = WebSocketAuthMiddleware(
            require_auth=True,
            allow_anonymous=False
        )

        from fastapi import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            await middleware.authenticate(mock_websocket)

        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_authenticate_expired_token_closes(self, mock_websocket):
        """Test that expired token closes connection when auth required."""
        token = create_test_token(expired=True)
        mock_websocket.query_params = {"token": token}

        middleware = WebSocketAuthMiddleware(require_auth=True)

        from fastapi import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            await middleware.authenticate(mock_websocket)

        mock_websocket.close.assert_called_once()


class TestWebSocketConnectionMonitor:
    """Tests for WebSocketConnectionMonitor class."""

    @pytest.mark.asyncio
    async def test_monitor_start_stop(self, mock_websocket, auth_context):
        """Test starting and stopping the monitor."""
        monitor = WebSocketConnectionMonitor(
            websocket=mock_websocket,
            auth_context=auth_context,
            heartbeat_interval=1
        )

        await monitor.start()
        assert monitor._running is True
        assert monitor._monitor_task is not None

        await monitor.stop()
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_heartbeat_update(self, mock_websocket, auth_context):
        """Test heartbeat timestamp update."""
        monitor = WebSocketConnectionMonitor(
            websocket=mock_websocket,
            auth_context=auth_context
        )

        old_heartbeat = auth_context.last_heartbeat
        time.sleep(0.1)  # Small delay
        monitor.update_heartbeat()

        assert auth_context.last_heartbeat > old_heartbeat

    @pytest.mark.asyncio
    async def test_timeout_callback(self, mock_websocket, auth_context):
        """Test timeout callback is called."""
        timeout_called = asyncio.Event()

        async def on_timeout():
            timeout_called.set()

        # Set last heartbeat to be very old
        auth_context.last_heartbeat = time.time() - 1000

        monitor = WebSocketConnectionMonitor(
            websocket=mock_websocket,
            auth_context=auth_context,
            heartbeat_interval=0.1,
            connection_timeout=1,
            on_timeout=on_timeout
        )

        await monitor.start()

        # Wait for timeout to be detected
        try:
            await asyncio.wait_for(timeout_called.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout callback was not called")
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_token_refresh_callback(self, mock_websocket):
        """Test token refresh callback is called when token expires soon."""
        refresh_called = asyncio.Event()

        async def on_refresh():
            refresh_called.set()

        # Create context with token expiring soon
        context = WebSocketAuthContext(
            user_id=TEST_USER_ID,
            token_exp=datetime.utcnow() + timedelta(seconds=60),  # Expires in 60s
            is_authenticated=True
        )

        monitor = WebSocketConnectionMonitor(
            websocket=mock_websocket,
            auth_context=context,
            heartbeat_interval=0.1,
            on_token_refresh_needed=on_refresh
        )

        await monitor.start()

        try:
            await asyncio.wait_for(refresh_called.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Token refresh callback was not called")
        finally:
            await monitor.stop()


class TestMessageHandling:
    """Tests for WebSocket message handling functions."""

    @pytest.mark.asyncio
    async def test_handle_heartbeat_message(self, mock_websocket, auth_context):
        """Test handling heartbeat/ping message."""
        message = {"event": "heartbeat"}

        response = await handle_websocket_message(
            mock_websocket, message, auth_context
        )

        assert response is not None
        assert response["event"] == "pong"
        assert "timestamp" in response
        assert "server_time" in response

    @pytest.mark.asyncio
    async def test_handle_ping_message(self, mock_websocket, auth_context):
        """Test handling ping message (alias for heartbeat)."""
        message = {"type": "ping"}

        response = await handle_websocket_message(
            mock_websocket, message, auth_context
        )

        assert response is not None
        assert response["event"] == "pong"

    @pytest.mark.asyncio
    async def test_heartbeat_updates_monitor(self, mock_websocket, auth_context):
        """Test that heartbeat updates monitor timestamp."""
        monitor = WebSocketConnectionMonitor(
            mock_websocket, auth_context
        )
        old_heartbeat = auth_context.last_heartbeat

        time.sleep(0.1)
        message = {"event": "heartbeat"}
        await handle_websocket_message(
            mock_websocket, message, auth_context, monitor
        )

        assert auth_context.last_heartbeat > old_heartbeat

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_handle_token_refresh(self, mock_websocket, auth_context):
        """Test handling token refresh message."""
        new_token = create_test_token(user_id="new_user_456")
        message = {
            "event": "refresh_token",
            "data": {"token": new_token}
        }

        response = await handle_websocket_message(
            mock_websocket, message, auth_context
        )

        assert response is not None
        assert response["event"] == "token_refresh_success"
        assert response["user_id"] == "new_user_456"
        assert auth_context.token == new_token

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_handle_token_refresh_invalid(self, mock_websocket, auth_context):
        """Test handling invalid token refresh."""
        message = {
            "event": "refresh_token",
            "token": "invalid.token.here"
        }

        response = await handle_websocket_message(
            mock_websocket, message, auth_context
        )

        assert response is not None
        assert response["event"] == "token_refresh_failed"

    @pytest.mark.asyncio
    async def test_handle_unknown_message(self, mock_websocket, auth_context):
        """Test that unknown messages return None."""
        message = {"event": "unknown_event", "data": {}}

        response = await handle_websocket_message(
            mock_websocket, message, auth_context
        )

        assert response is None


class TestHelperFunctions:
    """Tests for helper message creation functions."""

    def test_create_token_refresh_message(self):
        """Test token refresh notification message creation."""
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        message = create_token_refresh_message(expires_at)

        assert message["event"] == "token_refresh_needed"
        assert "expires_at" in message
        assert message["expires_in_seconds"] > 0
        assert "message" in message

    def test_create_timeout_warning_message(self):
        """Test timeout warning message creation."""
        message = create_timeout_warning_message(30)

        assert message["event"] == "timeout_warning"
        assert message["seconds_remaining"] == 30
        assert "message" in message


class TestWebSocketAuthMiddlewareFunction:
    """Tests for the websocket_auth_middleware convenience function."""

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_convenience_function_success(self, mock_websocket):
        """Test the convenience function with valid token."""
        token = create_test_token()
        mock_websocket.query_params = {"token": token}

        with patch("app.middleware.websocket_auth.get_rbac_service") as mock_rbac:
            mock_rbac_instance = MagicMock()
            mock_rbac_instance.get_user_roles = AsyncMock(return_value=[])
            mock_rbac.return_value = mock_rbac_instance

            context = await websocket_auth_middleware(
                mock_websocket,
                require_auth=False
            )

        assert context is not None
        assert context.user_id == TEST_USER_ID

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_convenience_function_auth_required_failure(self, mock_websocket):
        """Test convenience function returns None when auth fails."""
        mock_websocket.query_params = {}

        context = await websocket_auth_middleware(
            mock_websocket,
            require_auth=True,
            allow_anonymous=False
        )

        assert context is None
        mock_websocket.close.assert_called_once()


class TestRoleExtraction:
    """Tests for role extraction from RBAC service."""

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.get_rbac_service")
    async def test_get_user_role_admin(self, mock_rbac):
        """Test getting admin role."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_user_roles = AsyncMock(return_value=[
            {"role": {"role_name": "admin"}},
            {"role": {"role_name": "viewer"}}
        ])
        mock_rbac.return_value = mock_rbac_instance

        middleware = WebSocketAuthMiddleware()
        role = await middleware._get_user_role(TEST_USER_ID)

        assert role == "admin"

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.get_rbac_service")
    async def test_get_user_role_empty_returns_guest(self, mock_rbac):
        """Test that empty roles returns guest."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_user_roles = AsyncMock(return_value=[])
        mock_rbac.return_value = mock_rbac_instance

        middleware = WebSocketAuthMiddleware()
        role = await middleware._get_user_role(TEST_USER_ID)

        assert role == "guest"

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.get_rbac_service")
    async def test_get_user_role_error_returns_guest(self, mock_rbac):
        """Test that RBAC error returns guest role."""
        mock_rbac.side_effect = Exception("RBAC service unavailable")

        middleware = WebSocketAuthMiddleware()
        role = await middleware._get_user_role(TEST_USER_ID)

        assert role == "guest"


# Integration Tests

class TestWebSocketAuthIntegration:
    """Integration tests for WebSocket authentication flow."""

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_full_authentication_flow(self, mock_websocket):
        """Test complete authentication flow."""
        # Create valid token
        token = create_test_token(expires_in=3600)
        mock_websocket.query_params = {"token": token}

        with patch("app.middleware.websocket_auth.get_rbac_service") as mock_rbac:
            mock_rbac_instance = MagicMock()
            mock_rbac_instance.get_user_roles = AsyncMock(return_value=[
                {"role": {"role_name": "editor"}}
            ])
            mock_rbac.return_value = mock_rbac_instance

            # Authenticate
            middleware = WebSocketAuthMiddleware()
            context = await middleware.authenticate(mock_websocket)

            assert context.is_authenticated is True
            assert context.user_id == TEST_USER_ID
            assert context.role == "editor"

            # Create monitor
            monitor = WebSocketConnectionMonitor(
                mock_websocket, context, heartbeat_interval=1
            )
            await monitor.start()

            # Simulate heartbeat
            heartbeat_msg = {"event": "heartbeat"}
            response = await handle_websocket_message(
                mock_websocket, heartbeat_msg, context, monitor
            )

            assert response["event"] == "pong"

            # Cleanup
            await monitor.stop()

    @pytest.mark.asyncio
    @patch("app.middleware.websocket_auth.CLERK_SECRET_KEY", TEST_SECRET_KEY)
    async def test_anonymous_to_authenticated_upgrade(self, mock_websocket):
        """Test upgrading from anonymous to authenticated."""
        # Start anonymous
        mock_websocket.query_params = {}

        middleware = WebSocketAuthMiddleware(allow_anonymous=True)
        context = await middleware.authenticate(mock_websocket)

        assert context.user_id == "anonymous"
        assert context.is_authenticated is False

        # Simulate token refresh to upgrade
        new_token = create_test_token()
        refresh_msg = {"event": "refresh_token", "token": new_token}

        response = await handle_websocket_message(
            mock_websocket, refresh_msg, context
        )

        assert response["event"] == "token_refresh_success"
        assert context.user_id == TEST_USER_ID
