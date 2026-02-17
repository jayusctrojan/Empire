"""
Empire v7.3 - Artifact System Tests
Phase 3: Artifact DB + API + Pipeline Wiring

Tests for:
- Artifact API routes (list, get, download, delete)
- Response model serialization
- Access control (user_id scoping)
- B2 storage integration (download, cleanup on delete)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from io import BytesIO
from fastapi.testclient import TestClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_artifact_row():
    return {
        "id": "art-001",
        "message_id": "msg-123",
        "session_id": "sess-456",
        "user_id": "user-789",
        "org_id": "org-111",
        "title": "Q4 Revenue Report",
        "format": "docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 15360,
        "storage_url": "https://b2.example.com/artifacts/report.docx",
        "storage_path": "user-789/sess-456/20260215_report.docx",
        "preview_markdown": "## Q4 Revenue\n\nRevenue grew 15%.",
        "summary": "Q4 financial analysis",
        "intent": "analytical",
        "content_block_count": 8,
        "created_at": "2026-02-15T10:00:00+00:00",
        "updated_at": "2026-02-15T10:00:00+00:00",
    }


@pytest.fixture
def mock_supabase():
    mock = MagicMock()
    mock.supabase = MagicMock()
    return mock


# ============================================================================
# Response Model Tests
# ============================================================================

class TestArtifactResponseModel:
    def test_row_to_response(self, sample_artifact_row):
        from app.routes.artifacts import _row_to_response

        resp = _row_to_response(sample_artifact_row)

        assert resp.id == "art-001"
        assert resp.messageId == "msg-123"
        assert resp.sessionId == "sess-456"
        assert resp.title == "Q4 Revenue Report"
        assert resp.format == "docx"
        assert resp.sizeBytes == 15360
        assert resp.storageUrl == "https://b2.example.com/artifacts/report.docx"
        assert resp.previewMarkdown is not None
        assert resp.contentBlockCount == 8

    def test_row_with_missing_optional_fields(self):
        from app.routes.artifacts import _row_to_response

        minimal_row = {
            "id": "art-002",
            "session_id": "sess-1",
            "title": "Test",
            "format": "md",
            "mime_type": "text/markdown",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

        resp = _row_to_response(minimal_row)
        assert resp.id == "art-002"
        assert resp.messageId is None
        assert resp.sizeBytes == 0
        assert resp.storageUrl is None
        assert resp.previewMarkdown is None


# ============================================================================
# API Route Tests (using mocked dependencies)
# ============================================================================

class TestArtifactListEndpoint:
    @pytest.mark.asyncio
    async def test_list_returns_artifacts(self, mock_supabase, sample_artifact_row):
        """Test list_artifacts endpoint returns properly formatted response."""
        from app.routes.artifacts import list_artifacts

        # Mock the Supabase query chain
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[sample_artifact_row],
            count=1,
        )
        mock_supabase.supabase.table.return_value = mock_query

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            result = await list_artifacts(
                session_id=None,
                format=None,
                limit=50,
                offset=0,
                user_id="user-789",
            )

        assert result.total == 1
        assert len(result.artifacts) == 1
        assert result.artifacts[0].title == "Q4 Revenue Report"

    @pytest.mark.asyncio
    async def test_list_filters_by_session(self, mock_supabase, sample_artifact_row):
        from app.routes.artifacts import list_artifacts

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[sample_artifact_row], count=1)
        mock_supabase.supabase.table.return_value = mock_query

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            result = await list_artifacts(
                session_id="sess-456",
                format=None,
                limit=50,
                offset=0,
                user_id="user-789",
            )

        assert result.total == 1


class TestArtifactGetEndpoint:
    @pytest.mark.asyncio
    async def test_get_existing_artifact(self, mock_supabase, sample_artifact_row):
        from app.routes.artifacts import get_artifact

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[sample_artifact_row])
        mock_supabase.supabase.table.return_value = mock_query

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            result = await get_artifact(artifact_id="art-001", user_id="user-789")

        assert result.id == "art-001"
        assert result.format == "docx"

    @pytest.mark.asyncio
    async def test_get_nonexistent_artifact(self, mock_supabase):
        from app.routes.artifacts import get_artifact
        from fastapi import HTTPException

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        mock_supabase.supabase.table.return_value = mock_query

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await get_artifact(artifact_id="nonexistent", user_id="user-789")
            assert exc_info.value.status_code == 404


class TestArtifactDownloadEndpoint:
    @pytest.mark.asyncio
    async def test_download_existing_artifact(self, mock_supabase, sample_artifact_row):
        from app.routes.artifacts import download_artifact

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[{
            "storage_path": sample_artifact_row["storage_path"],
            "mime_type": sample_artifact_row["mime_type"],
            "title": sample_artifact_row["title"],
            "format": sample_artifact_row["format"],
        }])
        mock_supabase.supabase.table.return_value = mock_query

        mock_b2 = MagicMock()
        mock_b2.download_file = MagicMock(return_value=b"fake file content")

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            with patch("app.routes.artifacts.get_b2_service", return_value=mock_b2):
                result = await download_artifact(artifact_id="art-001", user_id="user-789")

        # Should return a StreamingResponse
        assert result.media_type == sample_artifact_row["mime_type"]

    @pytest.mark.asyncio
    async def test_download_missing_storage_path(self, mock_supabase):
        from app.routes.artifacts import download_artifact
        from fastapi import HTTPException

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[{
            "storage_path": None,
            "mime_type": "text/markdown",
            "title": "Test",
            "format": "md",
        }])
        mock_supabase.supabase.table.return_value = mock_query

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await download_artifact(artifact_id="art-002", user_id="user-789")
            assert exc_info.value.status_code == 404
            assert "not available" in exc_info.value.detail


class TestArtifactDeleteEndpoint:
    @pytest.mark.asyncio
    async def test_delete_existing_artifact(self, mock_supabase, sample_artifact_row):
        from app.routes.artifacts import delete_artifact

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.delete.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[{
            "storage_path": sample_artifact_row["storage_path"]
        }])
        mock_supabase.supabase.table.return_value = mock_query

        mock_b2 = MagicMock()
        mock_b2.delete_file = MagicMock()

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            with patch("app.routes.artifacts.get_b2_service", return_value=mock_b2):
                # Should not raise
                await delete_artifact(artifact_id="art-001", user_id="user-789")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_artifact(self, mock_supabase):
        from app.routes.artifacts import delete_artifact
        from fastapi import HTTPException

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[])
        mock_supabase.supabase.table.return_value = mock_query

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            with pytest.raises(HTTPException) as exc_info:
                await delete_artifact(artifact_id="nonexistent", user_id="user-789")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_b2_failure_is_best_effort(self, mock_supabase, sample_artifact_row):
        """B2 cleanup failure should not prevent DB deletion."""
        from app.routes.artifacts import delete_artifact

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.delete.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[{
            "storage_path": sample_artifact_row["storage_path"]
        }])
        mock_supabase.supabase.table.return_value = mock_query

        mock_b2 = MagicMock()
        mock_b2.delete_file = MagicMock(side_effect=Exception("B2 connection failed"))

        with patch("app.routes.artifacts._get_supabase", return_value=mock_supabase):
            with patch("app.routes.artifacts.get_b2_service", return_value=mock_b2):
                # Should not raise even though B2 failed
                await delete_artifact(artifact_id="art-001", user_id="user-789")
