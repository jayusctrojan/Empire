"""
Test Suite for SessionManagementService - Task 28

Tests for session creation, tracking, timeout, export, and deletion.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

from app.services.session_management_service import (
    SessionManagementService,
    Session
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    mock = Mock()
    mock.table = Mock(return_value=mock)
    mock.select = Mock(return_value=mock)
    mock.insert = Mock(return_value=mock)
    mock.update = Mock(return_value=mock)
    mock.delete = Mock(return_value=mock)
    mock.eq = Mock(return_value=mock)
    mock.order = Mock(return_value=mock)
    mock.limit = Mock(return_value=mock)
    mock.single = Mock(return_value=mock)
    mock.execute = Mock()
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = Mock()
    mock.get = Mock(return_value=None)
    mock.setex = Mock(return_value=True)
    mock.delete = Mock(return_value=1)
    mock.expire = Mock(return_value=True)
    mock.keys = Mock(return_value=[])
    return mock


@pytest.fixture
def service(mock_supabase, mock_redis):
    """SessionManagementService instance with mocked dependencies"""
    return SessionManagementService(
        supabase_client=mock_supabase,
        redis_client=mock_redis,
        session_timeout_minutes=60,
        max_sessions_per_user=10
    )


@pytest.fixture
def user_id():
    """Test user ID"""
    return f"test_user_{uuid4().hex[:8]}"


@pytest.fixture
def session_id():
    """Test session ID"""
    return f"session_{uuid4().hex[:8]}"


# ==================== Session Object Tests ====================

class TestSession:
    """Test Session data class"""

    def test_session_creation(self, session_id, user_id):
        """Test creating a Session object"""
        session = Session(
            id=session_id,
            user_id=user_id,
            title="Test Session",
            is_active=True,
            message_count=0,
            total_tokens=0
        )

        assert session.id == session_id
        assert session.user_id == user_id
        assert session.title == "Test Session"
        assert session.is_active is True
        assert session.message_count == 0
        assert session.total_tokens == 0

    def test_session_to_dict(self, session_id, user_id):
        """Test Session.to_dict() method"""
        session = Session(
            id=session_id,
            user_id=user_id,
            title="Test",
            is_active=True,
            message_count=5,
            total_tokens=150
        )

        data = session.to_dict()

        assert data["id"] == session_id
        assert data["user_id"] == user_id
        assert data["title"] == "Test"
        assert data["is_active"] is True
        assert data["message_count"] == 5
        assert data["total_tokens"] == 150

    def test_session_from_dict(self, session_id, user_id):
        """Test Session.from_dict() class method"""
        data = {
            "id": session_id,
            "user_id": user_id,
            "title": "Test",
            "summary": "Test summary",
            "is_active": True,
            "message_count": 3,
            "total_tokens": 100,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "first_message_at": datetime.utcnow().isoformat(),
            "last_message_at": datetime.utcnow().isoformat(),
            "session_metadata": {"key": "value"}
        }

        session = Session.from_dict(data)

        assert session.id == session_id
        assert session.user_id == user_id
        assert session.title == "Test"
        assert session.summary == "Test summary"
        assert session.is_active is True
        assert session.message_count == 3
        assert session.total_tokens == 100


# ==================== Session Creation Tests ====================

class TestSessionCreation:
    """Test session creation"""

    @pytest.mark.asyncio
    async def test_create_session_success(self, service, mock_supabase, user_id):
        """Test successful session creation"""
        # Mock Supabase response
        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": "session_123",
                "user_id": user_id,
                "title": "New Session",
                "is_active": True,
                "message_count": 0,
                "total_tokens": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
        )

        session = await service.create_session(
            user_id=user_id,
            title="New Session"
        )

        assert session is not None
        assert session.user_id == user_id
        assert session.title == "New Session"
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, service, mock_supabase, user_id):
        """Test creating session with custom metadata"""
        metadata = {"source": "web", "device": "desktop"}

        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": "session_123",
                "user_id": user_id,
                "title": "Session",
                "session_metadata": metadata,
                "is_active": True,
                "message_count": 0,
                "total_tokens": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
        )

        session = await service.create_session(
            user_id=user_id,
            metadata=metadata
        )

        assert session is not None
        assert session.session_metadata == metadata

    @pytest.mark.asyncio
    async def test_create_session_max_limit_cleanup(self, service, mock_supabase, user_id):
        """Test that oldest session is deleted when max limit is reached"""
        # Mock 10 existing active sessions
        existing_sessions = [
            {"id": f"session_{i}", "created_at": datetime.utcnow().isoformat()}
            for i in range(10)
        ]

        mock_supabase.execute.side_effect = [
            Mock(data=existing_sessions),  # get_active_sessions
            Mock(data=[]),  # delete oldest
            Mock(data=[{  # create new session
                "id": "new_session",
                "user_id": user_id,
                "is_active": True,
                "message_count": 0,
                "total_tokens": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }])
        ]

        session = await service.create_session(user_id=user_id)

        assert session is not None
        # Verify delete was called for oldest session
        assert mock_supabase.delete.called


# ==================== Session Activity Tracking Tests ====================

class TestSessionActivity:
    """Test session activity tracking"""

    @pytest.mark.asyncio
    async def test_update_session_activity(self, service, mock_supabase, mock_redis, user_id, session_id):
        """Test updating session activity"""
        # Mock Supabase response
        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": session_id,
                "user_id": user_id,
                "message_count": 5,
                "total_tokens": 150,
                "last_message_at": datetime.utcnow().isoformat(),
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
        )

        session = await service.update_session_activity(
            session_id=session_id,
            user_id=user_id,
            message_count_delta=1,
            tokens_delta=50
        )

        assert session is not None
        assert mock_supabase.update.called
        assert mock_redis.setex.called  # Redis cache update

    @pytest.mark.asyncio
    async def test_update_activity_refreshes_redis_ttl(self, service, mock_redis, user_id, session_id):
        """Test that activity updates refresh Redis TTL"""
        mock_supabase = service.supabase
        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": session_id,
                "user_id": user_id,
                "is_active": True,
                "message_count": 1,
                "total_tokens": 10,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
        )

        await service.update_session_activity(
            session_id=session_id,
            user_id=user_id
        )

        # Verify Redis setex was called with expire time
        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args
        assert len(call_args.args) >= 3  # key, ttl, value


# ==================== Session Retrieval Tests ====================

class TestSessionRetrieval:
    """Test session retrieval operations"""

    @pytest.mark.asyncio
    async def test_get_session_from_cache(self, service, mock_redis, session_id, user_id):
        """Test retrieving session from Redis cache"""
        import json

        cached_session = {
            "id": session_id,
            "user_id": user_id,
            "title": "Cached Session",
            "is_active": True,
            "message_count": 3,
            "total_tokens": 100
        }

        mock_redis.get.return_value = json.dumps(cached_session).encode()

        session = await service.get_session(session_id, user_id)

        assert session is not None
        assert session.id == session_id
        assert session.title == "Cached Session"
        assert mock_redis.get.called

    @pytest.mark.asyncio
    async def test_get_session_from_database(self, service, mock_redis, mock_supabase, session_id, user_id):
        """Test retrieving session from database when not in cache"""
        # Cache miss
        mock_redis.get.return_value = None

        # Database hit
        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": session_id,
                "user_id": user_id,
                "title": "DB Session",
                "is_active": True,
                "message_count": 5,
                "total_tokens": 200,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
        )

        session = await service.get_session(session_id, user_id)

        assert session is not None
        assert session.id == session_id
        # Should have cached the result
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, service, mock_supabase, user_id):
        """Test getting all active sessions for a user"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "id": "session_1",
                    "user_id": user_id,
                    "is_active": True,
                    "message_count": 3,
                    "total_tokens": 100,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                },
                {
                    "id": "session_2",
                    "user_id": user_id,
                    "is_active": True,
                    "message_count": 5,
                    "total_tokens": 150,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            ]
        )

        sessions = await service.get_active_sessions(user_id)

        assert len(sessions) == 2
        assert all(s.is_active for s in sessions)


# ==================== Session Deactivation Tests ====================

class TestSessionDeactivation:
    """Test session deactivation"""

    @pytest.mark.asyncio
    async def test_deactivate_session(self, service, mock_supabase, mock_redis, session_id, user_id):
        """Test deactivating a session"""
        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": session_id,
                "user_id": user_id,
                "is_active": False,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }]
        )

        success = await service.deactivate_session(session_id, user_id)

        assert success is True
        assert mock_supabase.update.called
        assert mock_redis.delete.called  # Should remove from cache


# ==================== Session Deletion Tests ====================

class TestSessionDeletion:
    """Test session deletion"""

    @pytest.mark.asyncio
    async def test_delete_session(self, service, mock_supabase, mock_redis, session_id, user_id):
        """Test deleting a session"""
        mock_supabase.execute.return_value = Mock(data=[])

        success = await service.delete_session(session_id, user_id)

        assert success is True
        assert mock_supabase.delete.called
        assert mock_redis.delete.called


# ==================== Session Export Tests ====================

class TestSessionExport:
    """Test session export functionality"""

    @pytest.mark.asyncio
    async def test_export_session_basic(self, service, mock_supabase, session_id, user_id):
        """Test exporting session without messages"""
        mock_supabase.execute.return_value = Mock(
            data=[{
                "id": session_id,
                "user_id": user_id,
                "title": "Export Test",
                "summary": "Test summary",
                "message_count": 5,
                "total_tokens": 200,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "session_metadata": {"test": "data"}
            }]
        )

        export = await service.export_session(
            session_id=session_id,
            user_id=user_id,
            include_messages=False
        )

        assert export is not None
        assert export["session_id"] == session_id
        assert export["user_id"] == user_id
        assert "messages" not in export


# ==================== Session Statistics Tests ====================

class TestSessionStatistics:
    """Test session statistics"""

    @pytest.mark.asyncio
    async def test_get_session_statistics(self, service, mock_supabase, user_id):
        """Test getting session statistics for a user"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {"id": "1", "is_active": True, "message_count": 5, "total_tokens": 100},
                {"id": "2", "is_active": True, "message_count": 3, "total_tokens": 50},
                {"id": "3", "is_active": False, "message_count": 10, "total_tokens": 300}
            ]
        )

        stats = await service.get_session_statistics(user_id)

        assert stats is not None
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 2
        assert stats["total_messages"] == 18
        assert stats["total_tokens"] == 450
