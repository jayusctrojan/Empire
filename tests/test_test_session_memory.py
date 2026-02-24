"""
Tests for test session memory saving.

Covers:
1. save_test_session_memory returns None for <3 messages
2. save_test_session_memory saves memory for 5+ messages with correct asset_id
3. save_test_session_memory converts CKO messages to ContextMessage format
4. DELETE /{asset_id}/test fires memory save task before deleting
5. DELETE /{asset_id}/test still returns even if session lookup fails
6. GET /{asset_id}/test/context returns correct message count + token estimate
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =============================================================================
# Shared helpers
# =============================================================================

def _make_supabase_mock():
    """Build a chainable Supabase mock."""
    m = MagicMock()
    for attr in ("table", "select", "insert", "update", "delete",
                 "eq", "limit", "order", "rpc"):
        getattr(m, attr).return_value = m
    result = MagicMock()
    result.data = []
    m.execute.return_value = result
    return m


def _make_cko_service(supabase_inner=None):
    """Return a StudioCKOConversationService whose Supabase wrapper is mocked."""
    if supabase_inner is None:
        supabase_inner = _make_supabase_mock()

    storage_wrapper = MagicMock()
    storage_wrapper.supabase = supabase_inner

    with (
        patch("app.services.studio_cko_conversation_service.get_supabase_storage",
              return_value=storage_wrapper),
        patch("app.services.studio_cko_conversation_service.get_embedding_service",
              return_value=MagicMock()),
        patch("app.services.studio_cko_conversation_service.get_llm_client",
              return_value=MagicMock()),
        patch("app.services.studio_cko_conversation_service.get_query_expansion_service",
              return_value=MagicMock()),
        patch("app.services.studio_cko_conversation_service.get_prompt_engineer_service",
              return_value=MagicMock()),
        patch("app.services.studio_cko_conversation_service.get_output_architect_service",
              return_value=MagicMock()),
        patch("app.services.studio_cko_conversation_service.get_document_generator_service",
              return_value=MagicMock()),
    ):
        from app.services.studio_cko_conversation_service import StudioCKOConversationService
        service = StudioCKOConversationService.__new__(StudioCKOConversationService)
        service.supabase = storage_wrapper
        service.config = MagicMock()
        return service, supabase_inner


def _build_test_app():
    """Create a minimal FastAPI app with only the studio_assets router."""
    from app.routes.studio_assets import router
    app = FastAPI()
    app.include_router(router)
    return app


def _override_auth(app, user_id="test-user"):
    from app.middleware.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user_id
    return app


# =============================================================================
# Test 1 — save_test_session_memory returns None for <3 messages
# =============================================================================

@pytest.mark.asyncio
async def test_save_test_session_memory_returns_none_for_few_messages():
    service, db = _make_cko_service()

    result_mock = MagicMock()
    result_mock.data = [
        {"role": "user", "content": "Hello", "created_at": "2024-01-01T00:00:00Z"},
        {"role": "cko", "content": "Hi", "created_at": "2024-01-01T00:00:01Z"},
    ]
    db.execute.return_value = result_mock

    with patch(
        "app.services.session_memory_service.get_session_memory_service"
    ) as mock_factory:
        memory_id = await service.save_test_session_memory(
            session_id="sess-001",
            user_id="user-001",
            asset_id="asset-001",
        )

    assert memory_id is None
    mock_factory.assert_not_called()


# =============================================================================
# Test 2 — save_test_session_memory saves memory for 5+ messages + asset_id
# =============================================================================

@pytest.mark.asyncio
async def test_save_test_session_memory_saves_memory_and_attaches_asset_id():
    service, db = _make_cko_service()

    five_msgs = [
        {"role": "user", "content": f"msg {i}", "created_at": f"2024-01-01T00:00:0{i}Z"}
        for i in range(5)
    ]
    fetch_result = MagicMock()
    fetch_result.data = five_msgs
    db.execute.return_value = fetch_result

    mock_memory_service = MagicMock()
    mock_memory_service.save_session_memory = AsyncMock(return_value="mem-42")

    mock_direct_supabase = MagicMock()
    update_chain = MagicMock()
    mock_direct_supabase.table.return_value = update_chain
    update_chain.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock()

    with (
        patch(
            "app.services.session_memory_service.get_session_memory_service",
            return_value=mock_memory_service,
        ),
        patch(
            "app.core.database.get_supabase",
            return_value=mock_direct_supabase,
        ),
    ):
        memory_id = await service.save_test_session_memory(
            session_id="sess-002",
            user_id="user-002",
            asset_id="asset-XYZ",
        )

    assert memory_id == "mem-42"
    mock_memory_service.save_session_memory.assert_awaited_once()

    from app.models.context_models import RetentionType
    kwargs = mock_memory_service.save_session_memory.call_args.kwargs
    assert kwargs.get("retention_type") == RetentionType.CKO

    mock_direct_supabase.table.assert_called_with("session_memories")
    update_chain.update.assert_called_with({"asset_id": "asset-XYZ"})


# =============================================================================
# Test 3 — save_test_session_memory converts rows to ContextMessage correctly
# =============================================================================

@pytest.mark.asyncio
async def test_save_test_session_memory_converts_messages_to_context_message():
    service, db = _make_cko_service()

    rows = [
        {"role": "user", "content": "What is policy X?", "created_at": "2024-01-01T00:00:00Z"},
        {"role": "cko", "content": "Policy X covers ...", "created_at": "2024-01-01T00:00:01Z"},
        {"role": "user", "content": "Thanks", "created_at": "2024-01-01T00:00:02Z"},
    ]
    fetch_result = MagicMock()
    fetch_result.data = rows
    db.execute.return_value = fetch_result

    captured_messages = []

    async def capture_save(**kwargs):
        captured_messages.extend(kwargs["messages"])
        return "mem-99"

    mock_memory_service = MagicMock()
    mock_memory_service.save_session_memory = AsyncMock(side_effect=capture_save)

    mock_direct_supabase = MagicMock()
    chain = MagicMock()
    mock_direct_supabase.table.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock()

    with (
        patch(
            "app.services.session_memory_service.get_session_memory_service",
            return_value=mock_memory_service,
        ),
        patch(
            "app.core.database.get_supabase",
            return_value=mock_direct_supabase,
        ),
    ):
        await service.save_test_session_memory(
            session_id="sess-003",
            user_id="user-003",
            asset_id="asset-003",
        )

    from app.models.context_models import MessageRole
    assert len(captured_messages) == 3

    assert captured_messages[0].role == MessageRole.USER
    assert captured_messages[0].content == "What is policy X?"
    assert captured_messages[0].token_count == len("What is policy X?") // 4

    assert captured_messages[1].role == MessageRole.ASSISTANT
    assert captured_messages[2].role == MessageRole.USER
    assert captured_messages[2].position == 2


# =============================================================================
# Test 4 — DELETE fires memory save task before deleting
# =============================================================================

def test_clear_test_session_fires_memory_save_before_delete():
    app = _build_test_app()
    _override_auth(app)

    mock_cko = MagicMock()

    db_inner = _make_supabase_mock()
    session_result = MagicMock()
    session_result.data = [{"id": "sess-found"}]
    db_inner.execute.return_value = session_result

    storage_wrapper = MagicMock()
    storage_wrapper.supabase = db_inner
    mock_cko.supabase = storage_wrapper

    mock_cko.save_test_session_memory = AsyncMock(return_value="mem-task")
    mock_cko.delete_asset_test_session = AsyncMock(return_value=True)

    with patch(
        "app.services.studio_cko_conversation_service.get_cko_conversation_service",
        return_value=mock_cko,
    ):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.delete("/api/studio/assets/asset-AAA/test")

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] is True
    # save_test_session_memory is awaited (not fire-and-forget) before deletion
    mock_cko.save_test_session_memory.assert_awaited_once_with("sess-found", "test-user", "asset-AAA")
    mock_cko.delete_asset_test_session.assert_awaited_once_with("test-user", "asset-AAA")


# =============================================================================
# Test 5 — DELETE still returns 200 even if session lookup fails
# =============================================================================

def test_clear_test_session_returns_even_if_session_lookup_fails():
    app = _build_test_app()
    _override_auth(app)

    mock_cko = MagicMock()

    db_inner = _make_supabase_mock()
    db_inner.execute.side_effect = Exception("DB connection lost")

    storage_wrapper = MagicMock()
    storage_wrapper.supabase = db_inner
    mock_cko.supabase = storage_wrapper

    mock_cko.save_test_session_memory = AsyncMock(return_value=None)
    mock_cko.delete_asset_test_session = AsyncMock(return_value=False)

    with patch(
        "app.services.studio_cko_conversation_service.get_cko_conversation_service",
        return_value=mock_cko,
    ):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.delete("/api/studio/assets/asset-BBB/test")

    assert response.status_code == 200
    mock_cko.save_test_session_memory.assert_not_awaited()
    mock_cko.delete_asset_test_session.assert_awaited_once_with("test-user", "asset-BBB")


# =============================================================================
# Test 6 — GET /{id}/test/context returns correct message count + token estimate
# =============================================================================

def test_get_test_context_info_returns_message_count_and_tokens():
    app = _build_test_app()
    _override_auth(app)

    mock_cko = MagicMock()

    db_inner = _make_supabase_mock()
    session_result = MagicMock()
    session_result.data = [
        {"id": "sess-context-01", "message_count": 8, "created_at": "2024-06-15T12:00:00Z"}
    ]
    db_inner.execute.return_value = session_result

    storage_wrapper = MagicMock()
    storage_wrapper.supabase = db_inner
    mock_cko.supabase = storage_wrapper

    with patch(
        "app.services.studio_cko_conversation_service.get_cko_conversation_service",
        return_value=mock_cko,
    ):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/studio/assets/asset-CCC/test/context")

    assert response.status_code == 200
    data = response.json()
    assert data["sessionId"] == "sess-context-01"
    assert data["messageCount"] == 8
    assert data["approxTokens"] == 8 * 150
    assert data["createdAt"] == "2024-06-15T12:00:00Z"


def test_get_test_context_info_returns_zeros_when_no_session():
    app = _build_test_app()
    _override_auth(app)

    mock_cko = MagicMock()

    db_inner = _make_supabase_mock()
    empty_result = MagicMock()
    empty_result.data = []
    db_inner.execute.return_value = empty_result

    storage_wrapper = MagicMock()
    storage_wrapper.supabase = db_inner
    mock_cko.supabase = storage_wrapper

    with patch(
        "app.services.studio_cko_conversation_service.get_cko_conversation_service",
        return_value=mock_cko,
    ):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/studio/assets/asset-DDD/test/context")

    assert response.status_code == 200
    data = response.json()
    assert data["sessionId"] is None
    assert data["messageCount"] == 0
    assert data["approxTokens"] == 0
    assert data["createdAt"] is None
