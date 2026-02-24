"""
Tests for Project Memory API Routes

Tests cover the session memory HTTP layer:
- POST /api/session-memory/note  — create manual memory notes
- GET  /api/session-memory/project/{project_id} — list project memories
- PATCH /api/session-memory/{memory_id} — update memory metadata
- DELETE /api/session-memory/{memory_id} — delete a memory
- POST /api/session-memory/search — semantic search
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime
from uuid import uuid4


# =============================================================================
# Helpers
# =============================================================================

def _make_session_memory(
    memory_id: str | None = None,
    project_id: str = "proj-abc",
    summary: str = "We decided to use FastAPI for the backend.",
) -> Mock:
    """Return a mock that mimics a SessionMemory model instance."""
    m = Mock()
    m.id = memory_id or str(uuid4())
    m.conversation_id = f"manual-note-{uuid4()}"
    m.user_id = "test-user"
    m.project_id = project_id
    m.summary = summary
    m.key_decisions = []
    m.files_mentioned = []
    m.code_preserved = []
    m.tags = ["architecture", "backend"]
    m.retention_type = "indefinite"
    m.created_at = datetime(2025, 1, 15, 10, 0, 0)
    m.updated_at = datetime(2025, 1, 15, 10, 0, 0)
    m.expires_at = None
    return m


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_service():
    """
    Patch get_session_memory_service so the route receives a controlled Mock.
    """
    with patch("app.routes.session_memory.get_session_memory_service") as factory:
        svc = Mock()
        svc.add_note = AsyncMock(return_value=str(uuid4()))
        svc.get_project_memories = AsyncMock(return_value=[])
        svc.get_relevant_memories = AsyncMock(return_value=[])
        svc.update_memory = AsyncMock(return_value=True)
        svc.delete_memory = AsyncMock(return_value=True)
        factory.return_value = svc
        yield svc


@pytest.fixture
def client(mock_service):
    """
    Build a TestClient with a lightweight app containing only the session_memory router.
    """
    from app.routes.session_memory import router
    from app.middleware.auth import get_current_user

    app = FastAPI()
    app.include_router(router)

    async def _fake_user():
        return "test-user"

    app.dependency_overrides[get_current_user] = _fake_user

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


# =============================================================================
# Test 1 — POST /note creates memory with correct fields
# =============================================================================

class TestAddMemoryNote:
    """Tests for POST /api/session-memory/note."""

    def test_creates_memory_with_correct_fields(self, client, mock_service):
        fixed_id = str(uuid4())
        mock_service.add_note.return_value = fixed_id

        response = client.post(
            "/api/session-memory/note",
            json={
                "project_id": "proj-123",
                "content": "Decided to migrate DB to Supabase.",
                "tags": ["decision", "database"],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["memory_id"] == fixed_id
        assert "Decided to migrate DB to Supabase" in body["summary_preview"]

        mock_service.add_note.assert_awaited_once()
        call_kwargs = mock_service.add_note.call_args.kwargs
        assert call_kwargs["user_id"] == "test-user"
        assert call_kwargs["project_id"] == "proj-123"
        assert call_kwargs["summary"] == "Decided to migrate DB to Supabase."
        assert call_kwargs["tags"] == ["decision", "database"]
        from app.models.context_models import RetentionType
        assert call_kwargs["retention_type"] == RetentionType.INDEFINITE

    # Test 2 — POST /note validates required fields
    def test_rejects_missing_project_id(self, client):
        response = client.post(
            "/api/session-memory/note",
            json={"content": "Some note without a project."},
        )
        assert response.status_code == 422

    def test_rejects_missing_content(self, client):
        response = client.post(
            "/api/session-memory/note",
            json={"project_id": "proj-123"},
        )
        assert response.status_code == 422

    # Test 3 — POST /note rejects empty content
    def test_rejects_empty_content(self, client):
        response = client.post(
            "/api/session-memory/note",
            json={"project_id": "proj-123", "content": ""},
        )
        assert response.status_code == 422


# =============================================================================
# Test 4/5 — GET /project/{project_id}
# =============================================================================

class TestGetProjectMemories:

    def test_returns_memories_for_project(self, client, mock_service):
        mem1 = _make_session_memory(project_id="proj-xyz", summary="Used React for the frontend.")
        mem2 = _make_session_memory(project_id="proj-xyz", summary="Chose PostgreSQL for persistence.")
        mock_service.get_project_memories.return_value = [mem1, mem2]

        response = client.get("/api/session-memory/project/proj-xyz")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] == 2
        assert len(body["memories"]) == 2

        ids_in_response = {m["id"] for m in body["memories"]}
        assert mem1.id in ids_in_response
        assert mem2.id in ids_in_response

    def test_returns_empty_for_project_with_no_memories(self, client, mock_service):
        mock_service.get_project_memories.return_value = []

        response = client.get("/api/session-memory/project/proj-empty")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["memories"] == []
        assert body["total"] == 0


# =============================================================================
# Test 6 — PATCH /{memory_id} updates summary
# =============================================================================

class TestUpdateMemory:

    def test_updates_summary(self, client, mock_service):
        memory_id = str(uuid4())
        mock_service.update_memory.return_value = True

        supabase_row = {
            "id": memory_id,
            "conversation_id": "conv-999",
            "project_id": "proj-123",
            "summary": "Updated: we chose TypeScript.",
            "key_decisions": "[]",
            "files_mentioned": "[]",
            "code_preserved": "[]",
            "tags": [],
            "retention_type": "indefinite",
            "created_at": "2025-01-15T10:00:00",
            "updated_at": "2025-01-15T11:00:00",
            "expires_at": None,
        }

        mock_supabase = Mock()
        (
            mock_supabase.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .single.return_value
            .execute.return_value
        ) = Mock(data=supabase_row)

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.patch(
                f"/api/session-memory/{memory_id}",
                json={"summary": "Updated: we chose TypeScript."},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["memory"] is not None
        assert body["memory"]["id"] == memory_id

        mock_service.update_memory.assert_awaited_once_with(
            memory_id=memory_id,
            user_id="test-user",
            updates={"summary": "Updated: we chose TypeScript."},
        )


# =============================================================================
# Test 7 — DELETE /{memory_id}
# =============================================================================

class TestDeleteMemory:

    def test_deletes_memory_successfully(self, client, mock_service):
        memory_id = str(uuid4())
        mock_service.delete_memory.return_value = True

        response = client.delete(f"/api/session-memory/{memory_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["deleted_id"] == memory_id

    def test_returns_404_when_memory_not_found(self, client, mock_service):
        mock_service.delete_memory.return_value = False

        response = client.delete(f"/api/session-memory/{uuid4()}")

        assert response.status_code == 404


# =============================================================================
# Test 8 — POST /search
# =============================================================================

class TestSearchMemories:

    def test_finds_memories_by_query(self, client, mock_service):
        mem = _make_session_memory(summary="We decided to use Redis for caching.")
        mock_service.get_relevant_memories.return_value = [mem]

        response = client.post(
            "/api/session-memory/search",
            json={"query": "caching strategy", "project_id": "proj-123", "limit": 5},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] == 1
        assert body["memories"][0]["id"] == mem.id

        mock_service.get_relevant_memories.assert_awaited_once_with(
            user_id="test-user",
            query="caching strategy",
            project_id="proj-123",
            limit=5,
        )

    def test_search_returns_empty_when_no_match(self, client, mock_service):
        mock_service.get_relevant_memories.return_value = []

        response = client.post(
            "/api/session-memory/search",
            json={"query": "something obscure"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["memories"] == []

    def test_search_validates_short_query(self, client, mock_service):
        response = client.post(
            "/api/session-memory/search",
            json={"query": "ab"},  # min_length=3
        )
        assert response.status_code == 422
