"""
Empire v7.5 - Unified Search API Tests
Tests for /api/search/unified endpoint across chats, projects, KB, artifacts.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client with chainable query builder."""
    mock = MagicMock()

    def make_builder(data):
        builder = MagicMock()
        builder.select.return_value = builder
        builder.eq.return_value = builder
        builder.limit.return_value = builder
        builder.execute.return_value = MagicMock(data=data)
        return builder

    mock._builders = {}
    mock._make_builder = make_builder
    return mock


@pytest.fixture
def app(mock_supabase):
    """Create test FastAPI app with unified search router."""
    from fastapi import FastAPI, Request
    from app.routes.unified_search import router

    app = FastAPI()

    # Middleware to set request.state
    @app.middleware("http")
    async def set_state(request: Request, call_next):
        request.state.org_id = "org-123"
        request.state.user_id = "user-456"
        return await call_next(request)

    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ============================================================================
# Endpoint Tests
# ============================================================================

class TestUnifiedSearchEndpoint:
    """Test the /api/search/unified endpoint."""

    def test_requires_min_query_length(self, client):
        response = client.get("/api/search/unified?q=a")
        assert response.status_code == 422  # validation error

    def test_returns_empty_for_no_matches(self, client, mock_supabase):
        empty_builder = mock_supabase._make_builder([])
        mock_supabase.table.return_value = empty_builder

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=nonexistent_query_xyz")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["results"] == []
        assert set(data["types_searched"]) == {"chat", "project", "kb", "artifact"}

    def test_filters_by_type(self, client, mock_supabase):
        empty_builder = mock_supabase._make_builder([])
        mock_supabase.table.return_value = empty_builder

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=test&types=chat,project")

        assert response.status_code == 200
        data = response.json()
        assert set(data["types_searched"]) == {"chat", "project"}

    def test_searches_chats(self, client, mock_supabase):
        """Chat sessions with matching titles should appear in results."""
        sessions = [
            {
                "id": "sess-1",
                "title": "Revenue Analysis Q4",
                "context_summary": "Discussed quarterly revenue trends",
                "message_count": 12,
                "last_message_at": "2026-02-15T10:00:00Z",
                "created_at": "2026-02-15T09:00:00Z",
            },
            {
                "id": "sess-2",
                "title": "Marketing Plan",
                "context_summary": "Budget allocation",
                "message_count": 5,
                "last_message_at": "2026-02-14T10:00:00Z",
                "created_at": "2026-02-14T09:00:00Z",
            },
        ]
        sessions_builder = mock_supabase._make_builder(sessions)
        empty_builder = mock_supabase._make_builder([])

        def table_router(name):
            if name == "studio_cko_sessions":
                return sessions_builder
            return empty_builder

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=revenue")

        data = response.json()
        assert data["total"] == 1
        assert data["results"][0]["type"] == "chat"
        assert data["results"][0]["title"] == "Revenue Analysis Q4"

    def test_searches_projects(self, client, mock_supabase):
        """Projects with matching names should appear."""
        projects = [
            {
                "id": "proj-1",
                "name": "Empire Sales Dashboard",
                "description": "Sales metrics and KPIs",
                "source_count": 8,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-02-01T00:00:00Z",
            },
        ]
        projects_builder = mock_supabase._make_builder(projects)
        empty_builder = mock_supabase._make_builder([])

        def table_router(name):
            if name == "projects":
                return projects_builder
            return empty_builder

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=sales&types=project")

        data = response.json()
        assert data["total"] == 1
        assert data["results"][0]["type"] == "project"
        assert "Sales" in data["results"][0]["title"]

    def test_searches_kb_documents(self, client, mock_supabase):
        """KB documents with matching filenames should appear."""
        docs = [
            {
                "id": "doc-1",
                "filename": "compliance_policy_2025.pdf",
                "file_type": "pdf",
                "status": "processed",
                "department": "Legal",
                "created_at": "2026-01-15T00:00:00Z",
                "updated_at": "2026-01-20T00:00:00Z",
            },
        ]
        docs_builder = mock_supabase._make_builder(docs)
        empty_builder = mock_supabase._make_builder([])

        def table_router(name):
            if name == "documents":
                return docs_builder
            return empty_builder

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=compliance&types=kb")

        data = response.json()
        assert data["total"] == 1
        assert data["results"][0]["type"] == "kb"
        assert "compliance" in data["results"][0]["title"].lower()

    def test_searches_artifacts(self, client, mock_supabase):
        """Artifacts with matching titles should appear."""
        artifacts = [
            {
                "id": "art-1",
                "title": "Q4 Financial Report",
                "format": "docx",
                "summary": "Quarterly financial summary",
                "size_bytes": 25000,
                "created_at": "2026-02-10T00:00:00Z",
                "session_id": "sess-99",
            },
        ]
        artifacts_builder = mock_supabase._make_builder(artifacts)
        empty_builder = mock_supabase._make_builder([])

        def table_router(name):
            if name == "studio_cko_artifacts":
                return artifacts_builder
            return empty_builder

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=financial&types=artifact")

        data = response.json()
        assert data["total"] == 1
        assert data["results"][0]["type"] == "artifact"
        assert data["results"][0]["metadata"]["format"] == "docx"

    def test_cross_type_search(self, client, mock_supabase):
        """Search across all types returns mixed results."""
        sessions = [{"id": "s1", "title": "Budget review", "context_summary": "", "message_count": 3, "last_message_at": "2026-02-15T10:00:00Z", "created_at": "2026-02-15T09:00:00Z"}]
        projects = [{"id": "p1", "name": "Budget Tracker", "description": "Track budgets", "source_count": 2, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z"}]
        docs = [{"id": "d1", "filename": "budget_2025.xlsx", "file_type": "xlsx", "status": "processed", "department": "Finance", "created_at": "2026-01-15T00:00:00Z", "updated_at": "2026-01-20T00:00:00Z"}]
        artifacts = [{"id": "a1", "title": "Budget Summary Report", "format": "pdf", "summary": "Annual budget overview", "size_bytes": 50000, "created_at": "2026-02-12T00:00:00Z", "session_id": "s1"}]

        def table_router(name):
            data_map = {
                "studio_cko_sessions": sessions,
                "projects": projects,
                "documents": docs,
                "studio_cko_artifacts": artifacts,
            }
            return mock_supabase._make_builder(data_map.get(name, []))

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=budget")

        data = response.json()
        assert data["total"] == 4
        types_found = {r["type"] for r in data["results"]}
        assert types_found == {"chat", "project", "kb", "artifact"}

    def test_respects_limit(self, client, mock_supabase):
        """Limit parameter caps total results."""
        sessions = [
            {"id": f"s{i}", "title": f"Test session {i}", "context_summary": "", "message_count": 1, "last_message_at": "2026-02-15T10:00:00Z", "created_at": "2026-02-15T09:00:00Z"}
            for i in range(30)
        ]
        empty_builder = mock_supabase._make_builder([])

        def table_router(name):
            if name == "studio_cko_sessions":
                return mock_supabase._make_builder(sessions)
            return empty_builder

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=test&limit=5")

        data = response.json()
        assert len(data["results"]) <= 5

    def test_invalid_type_ignored(self, client, mock_supabase):
        """Unknown types in the types param are silently ignored."""
        empty_builder = mock_supabase._make_builder([])
        mock_supabase.table.return_value = empty_builder

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=test&types=chat,invalid,project")

        data = response.json()
        assert set(data["types_searched"]) == {"chat", "project"}


class TestSearchResultScoring:
    """Test that results are scored correctly."""

    def test_title_match_scores_higher(self, client, mock_supabase):
        """Title matches should score higher than summary/description matches."""
        sessions = [
            {"id": "s1", "title": "Something else", "context_summary": "Meeting about revenue targets", "message_count": 3, "last_message_at": "2026-02-15T10:00:00Z", "created_at": "2026-02-15T09:00:00Z"},
            {"id": "s2", "title": "Revenue discussion", "context_summary": "Short chat", "message_count": 2, "last_message_at": "2026-02-14T10:00:00Z", "created_at": "2026-02-14T09:00:00Z"},
        ]
        empty_builder = mock_supabase._make_builder([])

        def table_router(name):
            if name == "studio_cko_sessions":
                return mock_supabase._make_builder(sessions)
            return empty_builder

        mock_supabase.table.side_effect = table_router

        with patch("app.core.database.get_supabase", return_value=mock_supabase):
            response = client.get("/api/search/unified?q=revenue&types=chat")

        data = response.json()
        assert len(data["results"]) == 2
        # Title match (s2) should score 0.9, summary match (s1) should score 0.6
        assert data["results"][0]["title"] == "Revenue discussion"
        assert data["results"][0]["relevance_score"] > data["results"][1]["relevance_score"]
