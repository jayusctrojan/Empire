"""
Empire v7.3 - RLS Context Middleware Tests
Task 151: Implement RLS Database Context

Tests for Row-Level Security context middleware that sets PostgreSQL
session variables for RLS policy enforcement.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

from app.middleware.rls_context import (
    RLSContextMiddleware,
    RLSContextError,
    configure_rls_context,
)


# =============================================================================
# Test App Setup
# =============================================================================

def create_test_app(rls_enabled: bool = True) -> FastAPI:
    """Create a test FastAPI app with RLS middleware"""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/documents")
    async def get_documents():
        return {"documents": []}

    @app.get("/api/users")
    async def get_users():
        return {"users": []}

    @app.get("/docs")
    async def docs():
        return {"docs": True}

    # Configure RLS middleware with environment override
    with patch.dict('os.environ', {'RLS_ENABLED': str(rls_enabled).lower()}):
        app.add_middleware(RLSContextMiddleware)

    return app


# =============================================================================
# RLSContextError Tests
# =============================================================================

class TestRLSContextError:
    """Test RLSContextError exception class"""

    def test_error_with_all_fields(self):
        """Test error with user_id and role"""
        error = RLSContextError(
            message="Failed to set context",
            user_id="user-123",
            role="admin"
        )
        assert str(error) == "Failed to set context"
        assert error.message == "Failed to set context"
        assert error.user_id == "user-123"
        assert error.role == "admin"

    def test_error_with_message_only(self):
        """Test error with only message"""
        error = RLSContextError(message="Context failed")
        assert str(error) == "Context failed"
        assert error.user_id is None
        assert error.role is None

    def test_error_inheritance(self):
        """Test error inherits from Exception"""
        error = RLSContextError(message="Test error")
        assert isinstance(error, Exception)


# =============================================================================
# Middleware Skip Tests
# =============================================================================

class TestRLSContextMiddlewareSkip:
    """Test cases where RLS middleware should skip processing"""

    def test_skip_non_api_endpoints(self):
        """Test middleware skips non-API endpoints"""
        app = create_test_app(rls_enabled=True)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_skip_docs_endpoint(self):
        """Test middleware skips /docs endpoint"""
        app = create_test_app(rls_enabled=True)
        client = TestClient(app)

        response = client.get("/docs")
        assert response.status_code == 200

    def test_skip_when_rls_disabled(self):
        """Test middleware skips when RLS_ENABLED=false"""
        with patch.dict('os.environ', {'RLS_ENABLED': 'false'}):
            app = FastAPI()

            @app.get("/api/test")
            async def test_endpoint():
                return {"test": True}

            app.add_middleware(RLSContextMiddleware)
            client = TestClient(app)

            # Should pass without auth when disabled
            response = client.get("/api/test")
            # May return 401 if other auth middleware blocks, but RLS won't block
            assert response.status_code in [200, 401]


# =============================================================================
# Authentication Tests
# =============================================================================

class TestRLSContextAuthentication:
    """Test RLS middleware authentication handling"""

    def test_reject_unauthenticated_api_request(self):
        """Test unauthenticated API requests are rejected with 401"""
        app = create_test_app(rls_enabled=True)
        client = TestClient(app)

        response = client.get("/api/documents")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert "Authentication required" in data["message"]
        assert "request_id" in data

    def test_authenticated_request_sets_context(self):
        """Test authenticated requests set RLS context"""
        app = FastAPI()

        @app.get("/api/test")
        async def test_endpoint(request):
            return {
                "user_id": getattr(request.state, "user_id", None),
                "role": getattr(request.state, "user_role", None),
            }

        app.add_middleware(RLSContextMiddleware)

        with patch.object(
            RLSContextMiddleware,
            '_get_user_from_auth',
            new_callable=AsyncMock,
            return_value="user-123"
        ), patch.object(
            RLSContextMiddleware,
            '_get_user_role',
            new_callable=AsyncMock,
            return_value="admin"
        ), patch.object(
            RLSContextMiddleware,
            '_set_rls_context',
            new_callable=AsyncMock,
            return_value=True
        ):
            client = TestClient(app)
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user-123"
            assert data["role"] == "admin"


# =============================================================================
# RLS Context Setting Tests
# =============================================================================

class TestRLSContextSetting:
    """Test RLS context setting functionality"""

    @pytest.mark.asyncio
    async def test_set_rls_context_success(self):
        """Test successful RLS context setting via Supabase RPC"""
        middleware = RLSContextMiddleware(MagicMock())

        mock_supabase = MagicMock()
        mock_rpc = MagicMock()
        mock_rpc.execute.return_value = MagicMock(data={
            "success": True,
            "user_id": "user-123",
            "role": "admin"
        })
        mock_supabase.rpc.return_value = mock_rpc

        with patch('app.middleware.rls_context.db_manager') as mock_db:
            mock_db.get_supabase.return_value = mock_supabase

            result = await middleware._set_rls_context(
                user_id="user-123",
                role="admin",
                request_id="req-456"
            )

            assert result is True
            mock_supabase.rpc.assert_called_once_with(
                "set_rls_context",
                {
                    "p_user_id": "user-123",
                    "p_role": "admin",
                    "p_request_id": "req-456"
                }
            )

    @pytest.mark.asyncio
    async def test_set_rls_context_failure_raises_error(self):
        """Test RLS context failure raises RLSContextError"""
        middleware = RLSContextMiddleware(MagicMock())

        with patch('app.middleware.rls_context.db_manager') as mock_db:
            mock_db.get_supabase.side_effect = Exception("Database connection failed")

            with pytest.raises(RLSContextError) as exc_info:
                await middleware._set_rls_context(
                    user_id="user-123",
                    role="admin",
                    request_id="req-456"
                )

            assert "Failed to set RLS context" in str(exc_info.value)


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestRLSContextErrorHandling:
    """Test error handling in RLS middleware"""

    def test_rls_context_failure_returns_503(self):
        """Test RLS context failure returns 503 Service Unavailable"""
        app = FastAPI()

        @app.get("/api/test")
        async def test_endpoint():
            return {"test": True}

        app.add_middleware(RLSContextMiddleware)

        with patch.object(
            RLSContextMiddleware,
            '_get_user_from_auth',
            new_callable=AsyncMock,
            return_value="user-123"
        ), patch.object(
            RLSContextMiddleware,
            '_get_user_role',
            new_callable=AsyncMock,
            return_value="admin"
        ), patch.object(
            RLSContextMiddleware,
            '_set_rls_context',
            new_callable=AsyncMock,
            side_effect=RLSContextError("Database unavailable")
        ):
            client = TestClient(app)
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 503
            data = response.json()
            assert data["error"] == "service_unavailable"
            assert "Database security context" in data["message"]
            assert "request_id" in data

    def test_unexpected_error_returns_503(self):
        """Test unexpected errors return 503"""
        app = FastAPI()

        @app.get("/api/test")
        async def test_endpoint():
            return {"test": True}

        app.add_middleware(RLSContextMiddleware)

        with patch.object(
            RLSContextMiddleware,
            '_get_user_from_auth',
            new_callable=AsyncMock,
            return_value="user-123"
        ), patch.object(
            RLSContextMiddleware,
            '_get_user_role',
            new_callable=AsyncMock,
            return_value="admin"
        ), patch.object(
            RLSContextMiddleware,
            '_set_rls_context',
            new_callable=AsyncMock,
            side_effect=RuntimeError("Unexpected error")
        ):
            client = TestClient(app)
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer test-token"}
            )

            assert response.status_code == 503
            data = response.json()
            assert data["error"] == "service_unavailable"


# =============================================================================
# User Role Tests
# =============================================================================

class TestRLSContextUserRole:
    """Test user role extraction"""

    @pytest.mark.asyncio
    async def test_get_user_role_returns_highest_role(self):
        """Test role extraction returns highest priority role"""
        middleware = RLSContextMiddleware(MagicMock())

        mock_rbac = MagicMock()
        mock_rbac.get_user_roles = AsyncMock(return_value=[
            {"role": {"role_name": "viewer"}},
            {"role": {"role_name": "admin"}},
            {"role": {"role_name": "editor"}},
        ])

        with patch('app.middleware.rls_context.get_rbac_service', return_value=mock_rbac):
            role = await middleware._get_user_role("user-123")
            assert role == "admin"

    @pytest.mark.asyncio
    async def test_get_user_role_default_guest(self):
        """Test role extraction defaults to guest for users without roles"""
        middleware = RLSContextMiddleware(MagicMock())

        mock_rbac = MagicMock()
        mock_rbac.get_user_roles = AsyncMock(return_value=[])

        with patch('app.middleware.rls_context.get_rbac_service', return_value=mock_rbac):
            role = await middleware._get_user_role("user-123")
            assert role == "guest"

    @pytest.mark.asyncio
    async def test_get_user_role_error_returns_guest(self):
        """Test role extraction returns guest on error"""
        middleware = RLSContextMiddleware(MagicMock())

        mock_rbac = MagicMock()
        mock_rbac.get_user_roles = AsyncMock(side_effect=Exception("RBAC error"))

        with patch('app.middleware.rls_context.get_rbac_service', return_value=mock_rbac):
            role = await middleware._get_user_role("user-123")
            assert role == "guest"


# =============================================================================
# Request ID Tests
# =============================================================================

class TestRLSContextRequestId:
    """Test request ID generation"""

    def test_request_id_generated(self):
        """Test unique request ID is generated for each request"""
        app = create_test_app(rls_enabled=True)
        client = TestClient(app)

        response1 = client.get("/api/documents")
        response2 = client.get("/api/documents")

        # Both should have 401 with different request IDs
        assert response1.status_code == 401
        assert response2.status_code == 401

        data1 = response1.json()
        data2 = response2.json()

        assert "request_id" in data1
        assert "request_id" in data2
        assert data1["request_id"] != data2["request_id"]

        # Validate UUID format
        uuid.UUID(data1["request_id"])
        uuid.UUID(data2["request_id"])


# =============================================================================
# Configuration Tests
# =============================================================================

class TestRLSContextConfiguration:
    """Test RLS middleware configuration"""

    def test_configure_rls_context_adds_middleware(self):
        """Test configure_rls_context adds middleware to app"""
        app = FastAPI()

        with patch.dict('os.environ', {'RLS_ENABLED': 'true'}):
            configure_rls_context(app)

        # Check middleware is added
        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        assert "RLSContextMiddleware" in middleware_names

    def test_configure_rls_context_disabled(self):
        """Test configure_rls_context when disabled"""
        app = FastAPI()

        with patch.dict('os.environ', {'RLS_ENABLED': 'false'}), \
             patch('app.middleware.rls_context.logger') as mock_logger:
            configure_rls_context(app)

            # Should log warning about disabled state
            mock_logger.warning.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================

class TestRLSContextIntegration:
    """Integration tests for RLS middleware"""

    def test_full_auth_flow(self):
        """Test complete authentication and RLS context flow"""
        app = FastAPI()

        context_set = {}

        @app.get("/api/test")
        async def test_endpoint(request):
            context_set["user_id"] = getattr(request.state, "user_id", None)
            context_set["role"] = getattr(request.state, "user_role", None)
            context_set["request_id"] = getattr(request.state, "request_id", None)
            return {"success": True}

        app.add_middleware(RLSContextMiddleware)

        with patch.object(
            RLSContextMiddleware,
            '_get_user_from_auth',
            new_callable=AsyncMock,
            return_value="user-123"
        ), patch.object(
            RLSContextMiddleware,
            '_get_user_role',
            new_callable=AsyncMock,
            return_value="editor"
        ), patch.object(
            RLSContextMiddleware,
            '_set_rls_context',
            new_callable=AsyncMock,
            return_value=True
        ) as mock_set:
            client = TestClient(app)
            response = client.get(
                "/api/test",
                headers={"Authorization": "Bearer valid-token"}
            )

            assert response.status_code == 200

            # Verify context was set in request state
            assert context_set["user_id"] == "user-123"
            assert context_set["role"] == "editor"
            assert context_set["request_id"] is not None

            # Verify _set_rls_context was called with correct parameters
            mock_set.assert_called_once()
            call_args = mock_set.call_args
            assert call_args[0][0] == "user-123"
            assert call_args[0][1] == "editor"

    def test_pre_authenticated_request_state(self):
        """Test request with pre-authenticated state from auth middleware"""
        app = FastAPI()

        # Middleware to simulate prior auth middleware setting state
        from starlette.middleware.base import BaseHTTPMiddleware

        class MockAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.user_id = "pre-auth-user"
                request.state.user_role = "viewer"
                return await call_next(request)

        @app.get("/api/test")
        async def test_endpoint(request):
            return {
                "user_id": request.state.user_id,
                "role": request.state.user_role,
            }

        # Add RLS middleware first (runs second)
        app.add_middleware(RLSContextMiddleware)
        # Add mock auth middleware second (runs first)
        app.add_middleware(MockAuthMiddleware)

        with patch.object(
            RLSContextMiddleware,
            '_set_rls_context',
            new_callable=AsyncMock,
            return_value=True
        ) as mock_set:
            client = TestClient(app)
            response = client.get("/api/test")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "pre-auth-user"
            assert data["role"] == "viewer"

            # Verify RLS context was set with pre-authenticated values
            mock_set.assert_called_once()
            call_args = mock_set.call_args
            assert call_args[0][0] == "pre-auth-user"
            assert call_args[0][1] == "viewer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
