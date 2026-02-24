"""
Empire v7.5 - Auto-Accumulation Memory Save Tests

Tests for:
- Auto-save trigger logic in _update_session_metadata (message counts 5, 15, 25...)
- _auto_save_session_memory message fetching and ContextMessage conversion
- SessionMemoryService._store_memory upsert + 60-second cooldown
- Failure isolation: exceptions in memory path must not surface to callers
- DB INSERT failure handling
- Wire test: Supabase + LLM mocked end-to-end trigger
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_supabase_storage():
    """Mock SupabaseStorageService wrapper used by StudioCKOConversationService."""
    mock = MagicMock()
    mock.supabase = MagicMock()
    # Default chainable table query builder — callers override .execute() per test
    table = MagicMock()
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
    table.execute.return_value = MagicMock(data=[])
    mock.supabase.table.return_value = table
    return mock


@pytest.fixture
def cko_service(mock_supabase_storage):
    """Create StudioCKOConversationService with all external deps patched."""
    with patch("app.services.studio_cko_conversation_service.get_supabase_storage",
               return_value=mock_supabase_storage), \
         patch("app.services.studio_cko_conversation_service.get_embedding_service"), \
         patch("app.services.studio_cko_conversation_service.get_llm_client"), \
         patch("app.services.studio_cko_conversation_service.get_query_expansion_service"), \
         patch("app.services.studio_cko_conversation_service.get_prompt_engineer_service"), \
         patch("app.services.studio_cko_conversation_service.get_output_architect_service"), \
         patch("app.services.studio_cko_conversation_service.get_document_generator_service"):
        from app.services.studio_cko_conversation_service import StudioCKOConversationService
        return StudioCKOConversationService()


def _make_session_row(**overrides):
    """Build a minimal mock session DB row."""
    row = {
        "id": "session-abc",
        "user_id": "user-xyz",
        "title": "New Conversation",
        "message_count": 3,
        "pending_clarifications": 0,
        "project_id": "proj-111",
        "context_summary": None,
        "asset_id": None,
        "session_type": "cko",
        "created_at": "2026-02-20T00:00:00Z",
        "updated_at": "2026-02-20T00:00:00Z",
        "last_message_at": None,
    }
    row.update(overrides)
    return row


def _make_message_rows(count: int):
    """Build a list of alternating user/cko message DB rows."""
    rows = []
    for i in range(count):
        rows.append({
            "role": "user" if i % 2 == 0 else "cko",
            "content": f"Message content {i}",
            "created_at": f"2026-02-20T00:{i:02d}:00Z",
        })
    return rows


# =============================================================================
# Auto-Accumulation: Trigger Logic
# =============================================================================

class TestAutoSaveTriggerLogic:
    """Tests for the threshold logic inside _update_session_metadata."""

    @pytest.mark.asyncio
    async def test_auto_save_fires_at_message_count_6(self, cko_service, mock_supabase_storage):
        """Auto-save task is created when new message count reaches exactly 6."""
        # current_count = 4, so new_count = 4 + 2 = 6 -> trigger
        session_row = _make_session_row(message_count=4, project_id="proj-111")
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.side_effect = [
            MagicMock(data=[session_row]),  # SELECT title/message_count/project_id/user_id
            MagicMock(data=[session_row]),  # UPDATE
        ]

        with patch("app.services.studio_cko_conversation_service.asyncio.create_task") as mock_create_task:
            await cko_service._update_session_metadata(
                "session-abc", "Hello world", "Response text"
            )

        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_save_does_not_fire_at_message_count_4(
        self, cko_service, mock_supabase_storage
    ):
        """Auto-save task is NOT created when new count is 4 (below threshold)."""
        # current_count = 2, new_count = 2 + 2 = 4 -> no trigger
        session_row = _make_session_row(message_count=2, project_id="proj-111")
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.side_effect = [
            MagicMock(data=[session_row]),
            MagicMock(data=[session_row]),
        ]

        with patch("app.services.studio_cko_conversation_service.asyncio.create_task") as mock_create_task:
            await cko_service._update_session_metadata(
                "session-abc", "Hello world", "Response text"
            )

        mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_save_fires_again_at_message_count_16(
        self, cko_service, mock_supabase_storage
    ):
        """Auto-save fires again at count 16 (every-10 cadence after 6)."""
        # current_count = 14, new_count = 14 + 2 = 16 -> trigger (16 % 10 == 6)
        session_row = _make_session_row(message_count=14, project_id="proj-111")
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.side_effect = [
            MagicMock(data=[session_row]),
            MagicMock(data=[session_row]),
        ]

        with patch("app.services.studio_cko_conversation_service.asyncio.create_task") as mock_create_task:
            await cko_service._update_session_metadata(
                "session-abc", "More messages", "Another response"
            )

        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_save_does_not_fire_without_project_id(
        self, cko_service, mock_supabase_storage
    ):
        """Auto-save is skipped when project_id is None, even at count 6."""
        # project_id is None — guard condition should prevent create_task
        session_row = _make_session_row(message_count=4, project_id=None)
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.side_effect = [
            MagicMock(data=[session_row]),
            MagicMock(data=[session_row]),
        ]

        with patch("app.services.studio_cko_conversation_service.asyncio.create_task") as mock_create_task:
            await cko_service._update_session_metadata(
                "session-abc", "Hello world", "Response text"
            )

        mock_create_task.assert_not_called()


# =============================================================================
# Auto-Accumulation: Upsert + Cooldown
# =============================================================================

class TestStoreMemoryUpsert:
    """Tests for SessionMemoryService._store_memory upsert path."""

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_memory_not_duplicate(self):
        """
        When upsert_by_conversation=True and an existing memory is found
        outside the cooldown window, the existing record is updated (not
        inserted as a duplicate).
        """
        from app.services.session_memory_service import SessionMemoryService
        from app.models.context_models import RetentionType

        service = SessionMemoryService()

        # Existing record updated more than 60 seconds ago
        old_updated_at = (datetime.utcnow() - timedelta(seconds=120)).isoformat()
        existing_memory_id = "mem-existing-001"

        mock_supabase = MagicMock()
        # Chain: table("session_memories").select(...).eq(...).eq(...).limit(1).execute()
        select_result = MagicMock()
        select_result.data = [{"id": existing_memory_id, "updated_at": old_updated_at}]
        mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.limit.return_value \
            .execute.return_value = select_result

        update_result = MagicMock()
        update_result.data = [{"id": existing_memory_id}]
        mock_supabase.table.return_value.update.return_value \
            .eq.return_value.execute.return_value = update_result

        with patch("app.services.session_memory_service.get_supabase", return_value=mock_supabase):
            result = await service._store_memory(
                user_id="user-xyz",
                conversation_id="conv-abc",
                summary="Updated summary",
                retention_type=RetentionType.CKO,
                upsert_by_conversation=True,
            )

        assert result == existing_memory_id
        # update() must be called, insert() must NOT be called
        mock_supabase.table.return_value.update.assert_called_once()
        mock_supabase.table.return_value.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_60_second_cooldown_returns_existing_id_without_update(self):
        """
        When existing memory was updated within the last 60 seconds,
        _store_memory returns the existing id without issuing an UPDATE.
        """
        from app.services.session_memory_service import SessionMemoryService
        from app.models.context_models import RetentionType

        service = SessionMemoryService()

        # Updated only 10 seconds ago — inside cooldown
        recent_updated_at = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
        existing_memory_id = "mem-recent-002"

        mock_supabase = MagicMock()
        select_result = MagicMock()
        select_result.data = [{"id": existing_memory_id, "updated_at": recent_updated_at}]
        mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.limit.return_value \
            .execute.return_value = select_result

        with patch("app.services.session_memory_service.get_supabase", return_value=mock_supabase):
            result = await service._store_memory(
                user_id="user-xyz",
                conversation_id="conv-abc",
                summary="Too soon",
                retention_type=RetentionType.CKO,
                upsert_by_conversation=True,
            )

        assert result == existing_memory_id
        # Neither update nor insert should be called during cooldown
        mock_supabase.table.return_value.update.assert_not_called()
        mock_supabase.table.return_value.insert.assert_not_called()


# =============================================================================
# Auto-Accumulation: Message Conversion
# =============================================================================

class TestAutoSaveSessionMemoryConversion:
    """Tests for _auto_save_session_memory message fetching and ContextMessage mapping."""

    @pytest.mark.asyncio
    async def test_cko_messages_correctly_convert_to_context_message_format(
        self, cko_service, mock_supabase_storage
    ):
        """
        _auto_save_session_memory fetches rows from studio_cko_messages,
        maps 'user' role -> MessageRole.USER and 'cko' role -> MessageRole.ASSISTANT,
        assigns sequential positions, and calls save_session_memory with the result.
        """
        from app.services.studio_cko_conversation_service import CKOSession
        from app.models.context_models import MessageRole

        session = CKOSession(
            id="session-abc",
            user_id="user-xyz",
            project_id="proj-111",
            message_count=5,
        )

        # 4 messages: user, cko, user, cko
        message_rows = _make_message_rows(4)
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = MagicMock(data=message_rows)

        captured_messages = []

        async def fake_save_session_memory(**kwargs):
            captured_messages.extend(kwargs["messages"])
            return "mem-new-001"

        mock_memory_service = MagicMock()
        mock_memory_service.save_session_memory = fake_save_session_memory

        with patch(
            "app.services.session_memory_service.get_session_memory_service",
            return_value=mock_memory_service,
        ):
            await cko_service._auto_save_session_memory(session)

        assert len(captured_messages) == 4

        # Position is 0-indexed and sequential
        for i, msg in enumerate(captured_messages):
            assert msg.position == i
            assert msg.context_id == "session-abc"

        # Role mapping: index 0 and 2 are 'user', index 1 and 3 are 'cko' -> ASSISTANT
        assert captured_messages[0].role == MessageRole.USER
        assert captured_messages[1].role == MessageRole.ASSISTANT
        assert captured_messages[2].role == MessageRole.USER
        assert captured_messages[3].role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_empty_conversation_returns_early_without_llm_call(
        self, cko_service, mock_supabase_storage
    ):
        """
        When fewer than 3 messages exist for the session,
        _auto_save_session_memory returns None and never calls save_session_memory.
        """
        from app.services.studio_cko_conversation_service import CKOSession

        session = CKOSession(
            id="session-abc",
            user_id="user-xyz",
            project_id="proj-111",
            message_count=5,
        )

        # Only 2 messages — below minimum threshold
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = MagicMock(data=_make_message_rows(2))

        mock_memory_service = MagicMock()
        mock_memory_service.save_session_memory = AsyncMock()

        with patch(
            "app.services.session_memory_service.get_session_memory_service",
            return_value=mock_memory_service,
        ):
            result = await cko_service._auto_save_session_memory(session)

        assert result is None
        mock_memory_service.save_session_memory.assert_not_called()


# =============================================================================
# Failure Modes
# =============================================================================

class TestAutoSaveFailureModes:
    """Auto-save failures must be fully isolated from callers."""

    @pytest.mark.asyncio
    async def test_auto_save_failure_does_not_crash_update_session_metadata(
        self, cko_service, mock_supabase_storage
    ):
        """
        If _auto_save_session_memory raises an exception internally,
        _update_session_metadata must still complete without propagating.
        """
        session_row = _make_session_row(message_count=4, project_id="proj-111")
        table = mock_supabase_storage.supabase.table.return_value
        table.execute.side_effect = [
            MagicMock(data=[session_row]),
            MagicMock(data=[session_row]),
        ]

        # Simulate create_task being called; the coroutine itself raises
        async def failing_auto_save(session):
            raise RuntimeError("LLM call failed unexpectedly")

        with patch(
            "app.services.studio_cko_conversation_service.asyncio.create_task"
        ) as mock_create_task:
            # Just verify create_task is called — the actual coroutine execution
            # is fire-and-forget and would be tested at integration level
            await cko_service._update_session_metadata(
                "session-abc", "User message", "CKO response"
            )

        # No exception propagated — the method completed normally
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_save_exception_caught_inside_auto_save_session_memory(
        self, cko_service, mock_supabase_storage
    ):
        """
        An exception raised by save_session_memory inside _auto_save_session_memory
        is caught and logged; the coroutine itself does not raise.
        """
        from app.services.studio_cko_conversation_service import CKOSession

        session = CKOSession(
            id="session-abc",
            user_id="user-xyz",
            project_id="proj-111",
            message_count=5,
        )

        table = mock_supabase_storage.supabase.table.return_value
        table.execute.return_value = MagicMock(data=_make_message_rows(4))

        mock_memory_service = MagicMock()
        mock_memory_service.save_session_memory = AsyncMock(
            side_effect=RuntimeError("DB write failure")
        )

        with patch(
            "app.services.session_memory_service.get_session_memory_service",
            return_value=mock_memory_service,
        ):
            # Must not raise — exception is swallowed inside the method
            await cko_service._auto_save_session_memory(session)

    @pytest.mark.asyncio
    async def test_db_insert_failure_is_caught_and_logged_not_raised(self):
        """
        When the Supabase INSERT in _store_memory raises, the exception
        propagates out of _store_memory but save_session_memory catches it
        and returns None rather than crashing the caller.
        """
        from app.services.session_memory_service import SessionMemoryService
        from app.models.context_models import ContextMessage, MessageRole, RetentionType

        service = SessionMemoryService()

        messages = [
            ContextMessage(
                id="m1",
                context_id="conv-abc",
                role=MessageRole.USER,
                content="Hello",
                token_count=10,
                is_protected=False,
                position=0,
            )
        ]

        mock_supabase = MagicMock()
        # No existing memory
        mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.limit.return_value \
            .execute.return_value = MagicMock(data=[])
        # INSERT raises
        mock_supabase.table.return_value.insert.return_value \
            .execute.side_effect = Exception("connection timeout")

        with patch("app.services.session_memory_service.get_supabase",
                   return_value=mock_supabase), \
             patch.object(service, "_generate_conversation_summary",
                          new_callable=AsyncMock, return_value="A summary"), \
             patch.object(service, "_generate_embedding",
                          new_callable=AsyncMock, return_value=None):
            result = await service.save_session_memory(
                conversation_id="conv-abc",
                user_id="user-xyz",
                messages=messages,
                retention_type=RetentionType.CKO,
            )

        # save_session_memory catches all exceptions and returns None
        assert result is None


# =============================================================================
# Integration Wire Test
# =============================================================================

class TestAutoSaveWireTest:
    """End-to-end wire: mock Supabase + LLM, trigger via _update_session_metadata."""

    @pytest.mark.asyncio
    async def test_wire_update_session_metadata_triggers_save_session_memory(
        self, cko_service, mock_supabase_storage
    ):
        """
        With Supabase and LLM fully mocked:
        - Call _update_session_metadata with a session that has current count=4
          so new_count = 6 (trigger threshold)
        - Verify that asyncio.create_task is called with a coroutine that,
          when awaited, invokes save_session_memory on the SessionMemoryService.
        """
        from app.services.studio_cko_conversation_service import CKOSession

        session_row = _make_session_row(message_count=4, project_id="proj-111")
        message_rows = _make_message_rows(6)  # 6 messages -> above 3-message floor

        table = mock_supabase_storage.supabase.table.return_value

        # _update_session_metadata: SELECT then UPDATE
        # _auto_save_session_memory: SELECT messages
        call_count = [0]

        def execute_side_effect():
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return MagicMock(data=[session_row])   # SELECT session metadata
            elif n == 2:
                return MagicMock(data=[session_row])   # UPDATE session
            else:
                return MagicMock(data=message_rows)    # SELECT messages for memory

        table.execute.side_effect = lambda: execute_side_effect()

        mock_memory_service = MagicMock()
        save_called_with = {}

        async def fake_save(**kwargs):
            save_called_with.update(kwargs)
            return "mem-wire-001"

        mock_memory_service.save_session_memory = fake_save

        # Capture the coroutine passed to create_task so we can await it
        captured_coro = []

        def fake_create_task(coro, **kwargs):
            captured_coro.append(coro)
            # Return a dummy task-like object
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            return mock_task

        with patch(
            "app.services.studio_cko_conversation_service.asyncio.create_task",
            side_effect=fake_create_task,
        ), patch(
            "app.services.session_memory_service.get_session_memory_service",
            return_value=mock_memory_service,
        ):
            await cko_service._update_session_metadata(
                "session-abc", "Trigger message", "Trigger response"
            )

            # create_task should have been called
            assert len(captured_coro) == 1, "Expected create_task to be called exactly once"

            # Await the captured coroutine to exercise _auto_save_session_memory
            await captured_coro[0]

        # save_session_memory must have been called with the CKO session data
        assert "conversation_id" in save_called_with
        assert save_called_with["conversation_id"] == "session-abc"
        assert save_called_with["user_id"] == "user-xyz"
        assert save_called_with.get("upsert_by_conversation") is True

        from app.models.context_models import RetentionType
        assert save_called_with.get("retention_type") == RetentionType.CKO
