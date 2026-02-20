"""
Tests for Asset Test Endpoint (POST /api/studio/assets/{asset_id}/test)

Tests the SSE streaming endpoint that runs an asset through the CKO pipeline
with the asset content injected as context.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.studio_assets import router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_asset():
    """Sample asset for testing"""
    asset = MagicMock()
    asset.id = "asset-123"
    asset.user_id = "user-1"
    asset.asset_type = "skill"
    asset.department = "it-engineering"
    asset.name = "code-reviewer"
    asset.title = "Code Review Skill"
    asset.content = "name: code-reviewer\ndescription: Reviews code for best practices"
    asset.format = "yaml"
    asset.status = "draft"
    asset.source_document_id = None
    asset.source_document_title = None
    asset.classification_confidence = 0.95
    asset.classification_reasoning = "High confidence"
    asset.keywords_matched = ["code", "review"]
    asset.secondary_department = None
    asset.secondary_confidence = None
    asset.asset_decision_reasoning = None
    asset.storage_path = None
    asset.version = 1
    asset.parent_version_id = None
    asset.created_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    asset.updated_at = datetime(2026, 1, 16, tzinfo=timezone.utc)
    asset.published_at = None
    asset.archived_at = None
    return asset


@pytest.fixture
def mock_service():
    """Mock AssetManagementService"""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_cko_service():
    """Mock CKO conversation service"""
    cko = AsyncMock()
    session = MagicMock()
    session.id = "test-session-123"
    cko.create_session.return_value = session
    return cko


@pytest.fixture
def app(mock_service):
    """FastAPI test app with mocked dependencies"""
    from app.routes.studio_assets import get_service
    from app.middleware.auth import get_current_user

    test_app = FastAPI()
    test_app.include_router(router)

    test_app.dependency_overrides[get_current_user] = lambda: "user-1"
    test_app.dependency_overrides[get_service] = lambda: mock_service

    return test_app


@pytest.fixture
def client(app):
    """Test client"""
    return TestClient(app)


# ============================================================================
# Tests
# ============================================================================

class TestAssetTestEndpoint:
    """Tests for POST /api/studio/assets/{asset_id}/test"""

    def test_returns_404_for_nonexistent_asset(self, client, mock_service):
        """Test endpoint returns 404 for non-existent asset"""
        from app.services.asset_management_service import AssetNotFoundError
        mock_service.get_asset.side_effect = AssetNotFoundError("Not found")

        response = client.post(
            "/api/studio/assets/nonexistent/test",
            json={"query": "test query"}
        )

        assert response.status_code == 404
        assert "Asset not found" in response.json()["detail"]

    def test_returns_403_for_different_user_asset(self, client, mock_service):
        """Test endpoint returns 404 (not 403) when user doesn't own the asset.
        The service layer raises AssetNotFoundError for unauthorized access."""
        from app.services.asset_management_service import AssetNotFoundError
        mock_service.get_asset.side_effect = AssetNotFoundError("Not found")

        response = client.post(
            "/api/studio/assets/asset-other-user/test",
            json={"query": "test query"}
        )

        assert response.status_code == 404

    def test_streams_sse_events(self, client, mock_service, mock_asset, mock_cko_service):
        """Test endpoint streams SSE events (phase, token, done)"""
        mock_service.get_asset.return_value = mock_asset

        async def mock_stream(*args, **kwargs):
            yield {"type": "phase", "phase": "analyzing", "label": "Analyzing..."}
            yield {"type": "token", "content": "Here is "}
            yield {"type": "token", "content": "the response."}
            yield {"type": "done", "message": {"content": "Here is the response."}, "query_time_ms": 1500}

        mock_cko_service.stream_message = mock_stream

        with patch(
            "app.services.studio_cko_conversation_service.get_cko_conversation_service",
            return_value=mock_cko_service
        ):
            response = client.post(
                "/api/studio/assets/asset-123/test",
                json={"query": "Generate a sample output"}
            )

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")

        body = response.text
        assert "event: start" in body
        assert "event: phase" in body
        assert "event: token" in body
        assert "event: done" in body

    def test_includes_asset_content_in_context(self, client, mock_service, mock_asset, mock_cko_service):
        """Test endpoint includes asset content in the CKO context message"""
        mock_service.get_asset.return_value = mock_asset

        captured_message = None

        async def capture_stream(*args, **kwargs):
            nonlocal captured_message
            # The message is passed as a keyword arg or positional
            captured_message = kwargs.get("message") or (args[2] if len(args) > 2 else None)
            yield {"type": "done", "message": {"content": "done"}}

        mock_cko_service.stream_message = capture_stream

        with patch(
            "app.services.studio_cko_conversation_service.get_cko_conversation_service",
            return_value=mock_cko_service
        ):
            client.post(
                "/api/studio/assets/asset-123/test",
                json={"query": "test this skill"}
            )

        assert captured_message is not None
        assert "code-reviewer" in captured_message
        assert "Reviews code for best practices" in captured_message
        assert "test this skill" in captured_message

    def test_streams_artifact_events(self, client, mock_service, mock_asset, mock_cko_service):
        """Test endpoint returns proper artifact events when doc generation triggered"""
        mock_service.get_asset.return_value = mock_asset

        async def mock_stream_with_artifact(*args, **kwargs):
            yield {"type": "token", "content": "Generated document."}
            yield {
                "type": "artifact",
                "id": "artifact-1",
                "title": "Code Review Report",
                "format": "docx",
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "sizeBytes": 15000,
            }
            yield {"type": "done", "message": {"content": "Generated document."}}

        mock_cko_service.stream_message = mock_stream_with_artifact

        with patch(
            "app.services.studio_cko_conversation_service.get_cko_conversation_service",
            return_value=mock_cko_service
        ):
            response = client.post(
                "/api/studio/assets/asset-123/test",
                json={"query": "Show me an example DOCX"}
            )

        assert response.status_code == 200
        body = response.text
        assert "event: artifact" in body
        assert "Code Review Report" in body

    def test_handles_pipeline_errors_gracefully(self, client, mock_service, mock_asset, mock_cko_service):
        """Test endpoint handles CKO pipeline errors gracefully"""
        mock_service.get_asset.return_value = mock_asset

        async def mock_stream_error(*args, **kwargs):
            raise RuntimeError("Pipeline failed: model overloaded")
            yield  # Make it an async generator

        mock_cko_service.stream_message = mock_stream_error

        with patch(
            "app.services.studio_cko_conversation_service.get_cko_conversation_service",
            return_value=mock_cko_service
        ):
            response = client.post(
                "/api/studio/assets/asset-123/test",
                json={"query": "test query"}
            )

        # Should still return 200 (SSE stream) with error event
        assert response.status_code == 200
        body = response.text
        assert "event: error" in body
        assert "Pipeline failed" in body
