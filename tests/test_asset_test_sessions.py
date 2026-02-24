"""
Tests for persistent asset test sessions
Empire v7.5 - CKO session extensions for asset testing
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_supabase_storage():
    """Mock Supabase storage."""
    mock = Mock()
    mock.supabase = Mock()
    # Chainable query builder
    table = Mock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.delete.return_value = table
    table.eq.return_value = table
    table.neq.return_value = table
    table.or_.return_value = table
    table.order.return_value = table
    table.range.return_value = table
    table.limit.return_value = table
    table.execute.return_value = Mock(data=[])
    mock.supabase.table.return_value = table
    return mock


@pytest.fixture
def cko_service(mock_supabase_storage):
    """Create CKO service with mocked dependencies."""
    with patch("app.services.studio_cko_conversation_service.get_supabase_storage", return_value=mock_supabase_storage), \
         patch("app.services.studio_cko_conversation_service.get_embedding_service"), \
         patch("app.services.studio_cko_conversation_service.get_llm_client"), \
         patch("app.services.studio_cko_conversation_service.get_query_expansion_service"), \
         patch("app.services.studio_cko_conversation_service.get_prompt_engineer_service"), \
         patch("app.services.studio_cko_conversation_service.get_output_architect_service"), \
         patch("app.services.studio_cko_conversation_service.get_document_generator_service"):
        from app.services.studio_cko_conversation_service import StudioCKOConversationService
        svc = StudioCKOConversationService()
        return svc


def _make_session_row(**overrides):
    """Build a mock session DB row."""
    row = {
        "id": "session-1",
        "user_id": "user-1",
        "title": "Asset Test: My Skill",
        "message_count": 0,
        "pending_clarifications": 0,
        "context_summary": None,
        "asset_id": "asset-1",
        "session_type": "asset_test",
        "created_at": "2026-02-20T00:00:00Z",
        "updated_at": "2026-02-20T00:00:00Z",
        "last_message_at": None,
    }
    row.update(overrides)
    return row


# =============================================================================
# CKOSession Dataclass Tests
# =============================================================================

class TestCKOSessionExtensions:
    def test_to_dict_includes_new_fields(self):
        from app.services.studio_cko_conversation_service import CKOSession
        session = CKOSession(
            id="s1", user_id="u1", asset_id="a1", session_type="asset_test"
        )
        d = session.to_dict()
        assert d["assetId"] == "a1"
        assert d["sessionType"] == "asset_test"

    def test_defaults(self):
        from app.services.studio_cko_conversation_service import CKOSession
        session = CKOSession(id="s1", user_id="u1")
        assert session.asset_id is None
        assert session.session_type == "cko"


# =============================================================================
# Helper Method Tests
# =============================================================================

class TestRowToSession:
    def test_converts_full_row(self, cko_service):
        row = _make_session_row()
        session = cko_service._row_to_session(row)
        assert session.id == "session-1"
        assert session.asset_id == "asset-1"
        assert session.session_type == "asset_test"
        assert session.created_at is not None

    def test_handles_null_session_type(self, cko_service):
        row = _make_session_row(session_type=None)
        session = cko_service._row_to_session(row)
        assert session.session_type == "cko"

    def test_parse_dt_handles_none(self, cko_service):
        assert cko_service._parse_dt(None) is None

    def test_parse_dt_handles_z_suffix(self, cko_service):
        dt = cko_service._parse_dt("2026-02-20T12:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None


# =============================================================================
# get_or_create_asset_test_session Tests
# =============================================================================

class TestGetOrCreateAssetTestSession:
    @pytest.mark.asyncio
    async def test_returns_existing_session(self, cko_service, mock_supabase_storage):
        """Should return existing session if one exists."""
        row = _make_session_row(message_count=3)
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = Mock(data=[row])

        session = await cko_service.get_or_create_asset_test_session(
            "user-1", "asset-1", "My Skill"
        )

        assert session.id == "session-1"
        assert session.message_count == 3

    @pytest.mark.asyncio
    async def test_creates_new_session(self, cko_service, mock_supabase_storage):
        """Should create new session when none exists."""
        new_row = _make_session_row()
        table = mock_supabase_storage.supabase.table.return_value
        # First query: no existing, then insert returns new row
        table.execute.side_effect = [
            Mock(data=[]),  # SELECT: not found
            Mock(data=[new_row]),  # INSERT: created
        ]

        session = await cko_service.get_or_create_asset_test_session(
            "user-1", "asset-1", "My Skill"
        )

        assert session.id == "session-1"
        assert session.session_type == "asset_test"

    @pytest.mark.asyncio
    async def test_handles_race_condition(self, cko_service, mock_supabase_storage):
        """Should re-query on unique constraint violation."""
        row = _make_session_row()
        table = mock_supabase_storage.supabase.table.return_value

        # First query: not found → Insert: raises unique constraint → Retry: found
        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Mock(data=[])  # SELECT: not found
            elif call_count == 2:
                raise Exception("duplicate key value violates unique constraint")
            else:
                return Mock(data=[row])  # Retry SELECT: found

        table.execute.side_effect = None
        table.execute = Mock(side_effect=side_effect)

        session = await cko_service.get_or_create_asset_test_session(
            "user-1", "asset-1", "My Skill"
        )

        assert session.id == "session-1"


# =============================================================================
# delete_asset_test_session Tests
# =============================================================================

class TestDeleteAssetTestSession:
    @pytest.mark.asyncio
    async def test_deletes_session(self, cko_service, mock_supabase_storage):
        """Should find and delete the test session."""
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.side_effect = [
            Mock(data=[{"id": "session-1"}]),  # Find session
            Mock(data=[]),  # Delete messages
            Mock(data=[{"id": "session-1"}]),  # Delete session
        ]

        result = await cko_service.delete_asset_test_session("user-1", "asset-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self, cko_service, mock_supabase_storage):
        """Should return False when no test session exists."""
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = Mock(data=[])

        result = await cko_service.delete_asset_test_session("user-1", "nonexistent")
        assert result is False


# =============================================================================
# list_sessions Filter Tests
# =============================================================================

class TestListSessionsFilter:
    @pytest.mark.asyncio
    async def test_excludes_asset_test_sessions(self, cko_service, mock_supabase_storage):
        """list_sessions should filter to only CKO sessions."""
        cko_row = _make_session_row(id="cko-1", session_type="cko", asset_id=None)
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = Mock(data=[cko_row])

        sessions = await cko_service.list_sessions("user-1")

        # Verify or_ filter was applied
        table.or_.assert_called_with("session_type.eq.cko,session_type.is.null")
        assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_returns_null_session_type(self, cko_service, mock_supabase_storage):
        """Backward compat: sessions with NULL session_type should be returned."""
        row = _make_session_row(id="old-1", session_type=None, asset_id=None)
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = Mock(data=[row])

        sessions = await cko_service.list_sessions("user-1")

        assert len(sessions) == 1
        assert sessions[0].session_type == "cko"  # Default
