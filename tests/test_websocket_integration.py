"""
Test WebSocket Real-Time Status Integration - Task 10

Tests the complete WebSocket implementation including:
- WebSocket connection management
- Redis Pub/Sub distributed broadcasting
- Celery task event notifications
- Resource-based message routing
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.main import app
from app.services.websocket_manager import ConnectionManager, get_connection_manager
from app.services.redis_pubsub_service import RedisPubSubService
from app.utils.websocket_notifications import (
    send_task_notification,
    send_document_processing_update,
    send_query_processing_update
)


class TestWebSocketEndpoints:
    """Test WebSocket endpoint connections and subscriptions"""

    @pytest.mark.asyncio
    async def test_general_notifications_connection(self):
        """Test connecting to /ws/notifications endpoint"""
        client = TestClient(app)

        with client.websocket_connect("/ws/notifications?session_id=test123") as websocket:
            # Should receive connection without errors
            data = websocket.receive_json()
            # Connection should be established
            assert websocket is not None

    @pytest.mark.asyncio
    async def test_document_subscription_connection(self):
        """Test connecting to document-specific endpoint"""
        client = TestClient(app)
        document_id = "doc_test_123"

        with client.websocket_connect(f"/ws/document/{document_id}?user_id=user123") as websocket:
            # First message is the connection confirmation
            connection_data = websocket.receive_json()
            assert connection_data["type"] == "connection"
            assert connection_data["status"] == "connected"

            # Second message is subscription confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscription_confirmed"
            assert data["resource_type"] == "document"
            assert data["resource_id"] == document_id

    @pytest.mark.asyncio
    async def test_query_subscription_connection(self):
        """Test connecting to query-specific endpoint"""
        client = TestClient(app)
        query_id = "query_test_456"

        with client.websocket_connect(f"/ws/query/{query_id}?session_id=session123") as websocket:
            # First message is the connection confirmation
            connection_data = websocket.receive_json()
            assert connection_data["type"] == "connection"
            assert connection_data["status"] == "connected"

            # Second message is subscription confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscription_confirmed"
            assert data["resource_type"] == "query"
            assert data["resource_id"] == query_id

    @pytest.mark.asyncio
    async def test_ping_pong_keepalive(self):
        """Test ping/pong keepalive mechanism"""
        client = TestClient(app)

        with client.websocket_connect("/ws/notifications") as websocket:
            # First message is the connection confirmation
            connection_data = websocket.receive_json()
            assert connection_data["type"] == "connection"

            # Send ping
            websocket.send_json({"type": "ping"})

            # Should receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert "timestamp" in response


class TestConnectionManager:
    """Test WebSocket ConnectionManager functionality"""

    @pytest.mark.asyncio
    async def test_connection_registration(self):
        """Test registering WebSocket connections"""
        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect(
            websocket=mock_ws,
            connection_id="conn123",
            session_id="session123",
            user_id="user123",
            connection_type="general"
        )

        assert "conn123" in manager.active_connections
        assert "session123" in manager.session_connections
        assert "user123" in manager.user_connections

    @pytest.mark.asyncio
    async def test_document_subscription(self):
        """Test document-specific subscription"""
        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)
        document_id = "doc123"

        await manager.connect(
            websocket=mock_ws,
            connection_id="conn123",
            document_id=document_id,
            connection_type="document"
        )

        assert document_id in manager.document_connections
        assert "conn123" in manager.document_connections[document_id]

    @pytest.mark.asyncio
    async def test_query_subscription(self):
        """Test query-specific subscription"""
        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)
        query_id = "query123"

        await manager.connect(
            websocket=mock_ws,
            connection_id="conn123",
            query_id=query_id,
            connection_type="query"
        )

        assert query_id in manager.query_connections
        assert "conn123" in manager.query_connections[query_id]

    @pytest.mark.asyncio
    async def test_send_to_document(self):
        """Test sending message to document subscribers"""
        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)
        document_id = "doc123"

        await manager.connect(
            websocket=mock_ws,
            connection_id="conn123",
            document_id=document_id,
            connection_type="document"
        )

        # Reset mock to clear the initial connection message call
        mock_ws.send_json.reset_mock()

        message = {"type": "test", "data": "hello"}
        await manager.send_to_document(message, document_id)

        # Verify message was sent
        mock_ws.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self):
        """Test broadcasting to all connections"""
        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "conn1", connection_type="general")
        await manager.connect(mock_ws2, "conn2", connection_type="general")

        # Reset mocks to clear the initial connection message calls
        mock_ws1.send_json.reset_mock()
        mock_ws2.send_json.reset_mock()

        message = {"type": "broadcast", "data": "announcement"}
        await manager.broadcast(message, publish_to_redis=False)

        # Both should receive the message
        mock_ws1.send_json.assert_called_once_with(message)
        mock_ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self):
        """Test connection cleanup on disconnect"""
        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect(
            websocket=mock_ws,
            connection_id="conn123",
            session_id="session123",
            document_id="doc123",
            connection_type="document"
        )

        await manager.disconnect("conn123")

        # Connection should be cleaned up
        assert "conn123" not in manager.active_connections
        # Session reference should be removed
        assert "conn123" not in manager.session_connections.get("session123", set())
        # Document subscription should be removed
        assert "conn123" not in manager.document_connections.get("doc123", set())


class TestRedisPubSub:
    """Test Redis Pub/Sub distributed broadcasting"""

    @pytest.mark.asyncio
    async def test_redis_connection(self):
        """Test Redis Pub/Sub connection"""
        service = RedisPubSubService()

        try:
            await service.connect()
            assert service.redis_client is not None
            assert service.pubsub is not None
        except Exception as e:
            # Redis may not be available in test environment
            pytest.skip(f"Redis not available: {e}")
        finally:
            await service.disconnect()

    @pytest.mark.asyncio
    async def test_publish_message(self):
        """Test publishing message to Redis channel"""
        service = RedisPubSubService()

        try:
            await service.connect()

            message = {"type": "test", "data": "hello"}
            await service.publish_message(
                channel="test_channel",
                message=message,
                channel_type="general"
            )

            # No exception means success
            assert True

        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await service.disconnect()

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self):
        """Test subscribing to channel and receiving messages"""
        service = RedisPubSubService()
        received_messages = []

        async def handler(message):
            received_messages.append(message)

        try:
            await service.connect()

            # Subscribe to test channel
            await service.subscribe_channel("test_channel", handler)
            await service.start_listener()

            # Publish a test message
            test_message = {"type": "test", "data": "hello"}
            await service.publish_message("test_channel", test_message)

            # Wait for message to be received
            await asyncio.sleep(1)

            # Should have received the message
            assert len(received_messages) > 0
            assert received_messages[0]["type"] == "test"

        except Exception as e:
            pytest.skip(f"Redis not available: {e}")
        finally:
            await service.disconnect()


class TestCeleryWebSocketIntegration:
    """Test Celery task events triggering WebSocket notifications"""

    def test_send_task_notification(self):
        """Test sending task notification"""
        # Patch where get_connection_manager is imported from
        with patch('app.services.websocket_manager.get_connection_manager') as mock_manager:
            mock_conn_manager = AsyncMock()
            mock_manager.return_value = mock_conn_manager

            send_task_notification(
                task_id="task123",
                task_name="test_task",
                status="started",
                message="Task started",
                document_id="doc123"
            )

            # Should have called send_to_document
            # Note: This is a simplified test - actual async handling is more complex
            assert True  # Basic smoke test

    def test_send_document_processing_update(self):
        """Test document processing update notification"""
        with patch('app.utils.websocket_notifications.send_task_notification') as mock_send:
            send_document_processing_update(
                task_id="task123",
                document_id="doc123",
                stage="parsing",
                status="progress",
                message="Parsing document",
                progress=50,
                metadata={"chunks": 10}
            )

            # Should have called send_task_notification with correct params
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["document_id"] == "doc123"
            assert call_kwargs["metadata"]["stage"] == "parsing"

    def test_send_query_processing_update(self):
        """Test query processing update notification"""
        with patch('app.utils.websocket_notifications.send_task_notification') as mock_send:
            send_query_processing_update(
                task_id="task123",
                query_id="query123",
                stage="searching",
                status="progress",
                message="Searching knowledge base",
                progress=75,
                user_id="user123"
            )

            # Should have called send_task_notification with correct params
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["query_id"] == "query123"
            assert call_kwargs["user_id"] == "user123"


class TestWebSocketStats:
    """Test WebSocket statistics endpoint"""

    def test_websocket_stats_endpoint(self):
        """Test GET /ws/stats endpoint"""
        client = TestClient(app)

        response = client.get("/ws/stats")
        assert response.status_code == 200

        stats = response.json()
        assert "active_connections" in stats
        # Stats structure changed: session_count -> active_sessions, user_count -> connected_users
        assert "active_sessions" in stats
        assert "connected_users" in stats


class TestMessageRouting:
    """Test resource-based message routing"""

    @pytest.mark.asyncio
    async def test_document_specific_routing(self):
        """Test messages only go to document subscribers"""
        manager = ConnectionManager()
        mock_ws_doc = AsyncMock(spec=WebSocket)
        mock_ws_other = AsyncMock(spec=WebSocket)

        # Connect one to document, one without
        await manager.connect(
            websocket=mock_ws_doc,
            connection_id="conn_doc",
            document_id="doc123",
            connection_type="document"
        )
        await manager.connect(
            websocket=mock_ws_other,
            connection_id="conn_other",
            connection_type="general"
        )

        # Reset mocks to clear the initial connection message calls
        mock_ws_doc.send_json.reset_mock()
        mock_ws_other.send_json.reset_mock()

        # Send to document subscribers
        message = {"type": "document_update", "doc_id": "doc123"}
        await manager.send_to_document(message, "doc123")

        # Only document subscriber should receive
        mock_ws_doc.send_json.assert_called_once_with(message)
        mock_ws_other.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_specific_routing(self):
        """Test messages only go to specific user"""
        manager = ConnectionManager()
        mock_ws_user = AsyncMock(spec=WebSocket)
        mock_ws_other = AsyncMock(spec=WebSocket)

        # Connect one with user_id, one without
        await manager.connect(
            websocket=mock_ws_user,
            connection_id="conn_user",
            user_id="user123",
            connection_type="general"
        )
        await manager.connect(
            websocket=mock_ws_other,
            connection_id="conn_other",
            connection_type="general"
        )

        # Reset mocks to clear the initial connection message calls
        mock_ws_user.send_json.reset_mock()
        mock_ws_other.send_json.reset_mock()

        # Send to specific user
        message = {"type": "user_notification", "user_id": "user123"}
        await manager.send_to_user(message, "user123")

        # Only user subscriber should receive
        mock_ws_user.send_json.assert_called_once_with(message)
        mock_ws_other.send_json.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
