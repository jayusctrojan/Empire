"""
Integration Tests for Content Prep Agent API Routes (AGENT-016).
Task 139: Create Integration Tests for Agent API Routes

Tests the full request-response cycle for:
- POST /api/content-prep/analyze - Analyze pending files
- GET /api/content-prep/sets - List content sets
- GET /api/content-prep/sets/{set_id} - Get specific content set
- POST /api/content-prep/validate/{set_id} - Validate completeness
- POST /api/content-prep/manifest - Generate processing manifest
- GET /api/content-prep/health - Health check
- POST /api/content-prep/clarify-ordering - Clarification endpoint
- POST /api/content-prep/clarifications/respond - User response
- GET /api/content-prep/clarifications/pending/{user_id} - Pending requests
- GET /api/content-prep/clarifications/history/{content_set_id} - History
- DELETE /api/content-prep/clarifications/{request_id} - Cancel clarification
- POST /api/content-prep/admin/cleanup - Trigger cleanup
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_content_prep_agent():
    """Mock the ContentPrepAgent."""
    mock_agent = MagicMock()

    # Mock analyze_folder result
    mock_agent.analyze_folder = AsyncMock(return_value={
        "folder": "pending/courses/",
        "content_sets": [
            {
                "id": "set-123",
                "name": "Python Course",
                "set_type": "course",
                "file_count": 10,
                "ordering_confidence": 0.95,
                "files": []
            }
        ],
        "standalone_files": [],
        "total_files": 10,
        "detection_mode": "auto"
    })

    # Mock list_sets result
    mock_agent.list_sets = AsyncMock(return_value=[
        {
            "id": "set-123",
            "name": "Python Course",
            "set_type": "course",
            "status": "pending",
            "file_count": 10,
            "ordering_confidence": 0.95,
            "files": []
        },
        {
            "id": "set-456",
            "name": "JavaScript Guide",
            "set_type": "documentation",
            "status": "processing",
            "file_count": 5,
            "ordering_confidence": 0.88,
            "files": []
        }
    ])

    # Mock get_set result
    mock_agent.get_set = AsyncMock(return_value={
        "id": "set-123",
        "name": "Python Course",
        "set_type": "course",
        "status": "pending",
        "file_count": 10,
        "ordering_confidence": 0.95,
        "files": [
            {"file_id": "f1", "name": "01-intro.pdf", "sequence": 1},
            {"file_id": "f2", "name": "02-basics.pdf", "sequence": 2},
            {"file_id": "f3", "name": "03-advanced.pdf", "sequence": 3}
        ]
    })

    # Mock validate_completeness result
    mock_agent.validate_completeness = AsyncMock(return_value={
        "content_set_id": "set-123",
        "is_complete": True,
        "missing_files": [],
        "requires_acknowledgment": False,
        "validation_details": {"checked_sequences": True}
    })

    # Mock generate_manifest result
    mock_agent.generate_manifest = AsyncMock(return_value={
        "manifest_id": "manifest-123",
        "content_set_id": "set-123",
        "processing_queue": [
            {"file_id": "f1", "order": 1, "dependencies": []},
            {"file_id": "f2", "order": 2, "dependencies": ["f1"]},
            {"file_id": "f3", "order": 3, "dependencies": ["f2"]}
        ],
        "total_files": 3,
        "created_at": "2024-01-15T10:30:00Z"
    })

    # Mock resolve_order_with_clarification result
    mock_agent.resolve_order_with_clarification = AsyncMock(return_value={
        "status": "success",
        "content_set_id": "set-123",
        "ordering_confidence": 0.95,
        "clarification_requested": False,
        "clarification_answered": None,
        "clarification_timeout": None,
        "files_reordered": 0,
        "ordered_files": [
            {"file_id": "f1", "name": "01-intro.pdf", "sequence": 1},
            {"file_id": "f2", "name": "02-basics.pdf", "sequence": 2}
        ]
    })

    # Mock get_health_status result
    from app.models.content_sets import HealthResponse, AgentInfo, ProcessingMetrics, ConnectivityStatus
    mock_agent.get_health_status = AsyncMock(return_value=HealthResponse(
        status="healthy",
        agent=AgentInfo(
            agent_id="AGENT-016",
            name="Content Prep Agent",
            version="7.3.0",
            uptime_seconds=3600,
            llm_available=True
        ),
        metrics=ProcessingMetrics(
            pending_content_sets=5,
            active_processing=2,
            recent_error_count=0
        ),
        connectivity=ConnectivityStatus(
            supabase=True,
            neo4j=True,
            b2_storage=True
        ),
        capabilities={
            "content_set_detection": True,
            "ordering_analysis": True,
            "ordering_clarification": True,
            "manifest_generation": True,
            "llm_powered": True
        }
    ))

    return mock_agent


@pytest.fixture
def mock_cko_chat_service():
    """Mock the CKO Chat service."""
    mock_service = MagicMock()

    mock_service.submit_user_response = AsyncMock(return_value=True)

    mock_service.get_pending_requests = AsyncMock(return_value=[
        {
            "id": "req-123",
            "agent_id": "AGENT-016",
            "message": "Please confirm the file ordering for Python Course",
            "clarification_type": "ordering",
            "context": {"content_set_id": "set-123"},
            "created_at": "2024-01-15T10:30:00Z",
            "expires_at": "2024-01-15T11:30:00Z"
        }
    ])

    mock_service.cancel_request = AsyncMock(return_value=True)

    return mock_service


@pytest.fixture
def mock_clarification_logger():
    """Mock the clarification logger."""
    mock_logger = MagicMock()

    mock_logger.get_conversation_history = AsyncMock(return_value=[
        {
            "id": "conv-123",
            "content_set_id": "set-123",
            "agent_id": "AGENT-016",
            "question": "Is this the correct file order?",
            "answer": "Yes, confirmed",
            "outcome": "confirmed",
            "clarification_type": "ordering",
            "created_at": "2024-01-15T10:00:00Z"
        }
    ])

    return mock_logger


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestContentPrepHealthEndpoint:
    """Tests for /api/content-prep/health endpoint."""

    def test_health_check_returns_healthy(self, client, mock_content_prep_agent, validate_health_response):
        """Test that health endpoint returns healthy status."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/health")

            assert response.status_code == 200
            data = response.json()
            validate_health_response(data)
            assert data["agent"]["agent_id"] == "AGENT-016"
            assert data["agent"]["name"] == "Content Prep Agent"

    def test_health_check_includes_capabilities(self, client, mock_content_prep_agent):
        """Test that health endpoint includes capability information."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/health")

            assert response.status_code == 200
            data = response.json()
            assert "capabilities" in data
            assert data["capabilities"]["content_set_detection"] is True
            assert data["capabilities"]["ordering_analysis"] is True
            assert data["capabilities"]["manifest_generation"] is True

    def test_health_check_includes_connectivity(self, client, mock_content_prep_agent):
        """Test that health endpoint includes connectivity status."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/health")

            assert response.status_code == 200
            data = response.json()
            assert "connectivity" in data
            assert data["connectivity"]["supabase"] is True
            assert data["connectivity"]["neo4j"] is True
            assert data["connectivity"]["b2_storage"] is True


# =============================================================================
# ANALYZE ENDPOINT TESTS
# =============================================================================

class TestContentPrepAnalyzeEndpoint:
    """Tests for /api/content-prep/analyze endpoint."""

    def test_analyze_success(self, client, mock_content_prep_agent):
        """Test successful folder analysis."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post(
                "/api/content-prep/analyze",
                json={
                    "b2_folder": "pending/courses/",
                    "detection_mode": "auto"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "content_sets" in data
            assert "standalone_files" in data
            assert data["total_files"] == 10

    def test_analyze_with_pattern_mode(self, client, mock_content_prep_agent):
        """Test analysis with pattern detection mode."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post(
                "/api/content-prep/analyze",
                json={
                    "b2_folder": "pending/docs/",
                    "detection_mode": "pattern"
                }
            )

            assert response.status_code == 200


# =============================================================================
# CONTENT SETS ENDPOINT TESTS
# =============================================================================

class TestContentPrepSetsEndpoints:
    """Tests for /api/content-prep/sets endpoints."""

    def test_list_content_sets(self, client, mock_content_prep_agent):
        """Test listing all content sets."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/sets")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_list_content_sets_with_filter(self, client, mock_content_prep_agent):
        """Test listing content sets with status filter."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/sets?status=pending")

            assert response.status_code == 200

    def test_get_specific_content_set(self, client, mock_content_prep_agent):
        """Test getting a specific content set."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/sets/set-123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "set-123"
            assert data["name"] == "Python Course"
            assert "files" in data

    def test_get_nonexistent_set_returns_404(self, client, mock_content_prep_agent):
        """Test that nonexistent content set returns 404."""
        mock_content_prep_agent.get_set = AsyncMock(
            side_effect=ValueError("Content set not found")
        )

        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.get("/api/content-prep/sets/nonexistent")

            assert response.status_code == 404


# =============================================================================
# VALIDATE ENDPOINT TESTS
# =============================================================================

class TestContentPrepValidateEndpoint:
    """Tests for /api/content-prep/validate/{set_id} endpoint."""

    def test_validate_complete_set(self, client, mock_content_prep_agent):
        """Test validating a complete content set."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post("/api/content-prep/validate/set-123")

            assert response.status_code == 200
            data = response.json()
            assert data["is_complete"] is True
            assert data["requires_acknowledgment"] is False
            assert len(data["missing_files"]) == 0

    def test_validate_incomplete_set(self, client, mock_content_prep_agent):
        """Test validating an incomplete content set."""
        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "content_set_id": "set-123",
            "is_complete": False,
            "missing_files": ["04-conclusion.pdf"],
            "requires_acknowledgment": True,
            "validation_details": {"checked_sequences": True}
        })

        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post("/api/content-prep/validate/set-123")

            assert response.status_code == 200
            data = response.json()
            assert data["is_complete"] is False
            assert data["requires_acknowledgment"] is True

    def test_validate_nonexistent_set_returns_404(self, client, mock_content_prep_agent):
        """Test that validating nonexistent set returns 404."""
        mock_content_prep_agent.validate_completeness = AsyncMock(
            side_effect=ValueError("Content set not found")
        )

        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post("/api/content-prep/validate/nonexistent")

            assert response.status_code == 404


# =============================================================================
# MANIFEST ENDPOINT TESTS
# =============================================================================

class TestContentPrepManifestEndpoint:
    """Tests for /api/content-prep/manifest endpoint."""

    def test_generate_manifest_success(self, client, mock_content_prep_agent):
        """Test successful manifest generation."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post(
                "/api/content-prep/manifest",
                json={
                    "content_set_id": "set-123",
                    "proceed_incomplete": False
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "manifest_id" in data
            assert "processing_queue" in data
            assert data["total_files"] == 3

    def test_generate_manifest_incomplete_without_acknowledgment_returns_400(self, client, mock_content_prep_agent):
        """Test that incomplete set without acknowledgment returns 400."""
        mock_content_prep_agent.generate_manifest = AsyncMock(
            side_effect=ValueError("Content set is incomplete. Set proceed_incomplete=true to proceed.")
        )

        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post(
                "/api/content-prep/manifest",
                json={
                    "content_set_id": "set-123",
                    "proceed_incomplete": False
                }
            )

            assert response.status_code == 400


# =============================================================================
# CLARIFICATION ENDPOINT TESTS
# =============================================================================

class TestContentPrepClarificationEndpoints:
    """Tests for /api/content-prep/clarify-ordering and related endpoints."""

    def test_clarify_ordering_success(self, client, mock_content_prep_agent):
        """Test successful ordering clarification."""
        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_content_prep_agent
        ):
            response = client.post(
                "/api/content-prep/clarify-ordering",
                json={
                    "content_set_id": "set-123",
                    "user_id": "user-456",
                    "confidence_threshold": 0.8,
                    "timeout_seconds": 3600
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["content_set_id"] == "set-123"
            assert "ordered_files" in data

    def test_respond_to_clarification(self, client, mock_cko_chat_service):
        """Test submitting user response to clarification."""
        with patch(
            "app.routes.content_prep.get_cko_chat_service",
            return_value=mock_cko_chat_service
        ):
            response = client.post(
                "/api/content-prep/clarifications/respond",
                json={
                    "request_id": "req-123",
                    "user_id": "user-456",
                    "response": "Yes, the order is correct"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_respond_invalid_request_returns_400(self, client, mock_cko_chat_service):
        """Test that invalid response submission returns 400."""
        mock_cko_chat_service.submit_user_response = AsyncMock(return_value=False)

        with patch(
            "app.routes.content_prep.get_cko_chat_service",
            return_value=mock_cko_chat_service
        ):
            response = client.post(
                "/api/content-prep/clarifications/respond",
                json={
                    "request_id": "invalid-req",
                    "user_id": "user-456",
                    "response": "Yes"
                }
            )

            assert response.status_code == 400

    def test_get_pending_clarifications(self, client, mock_cko_chat_service):
        """Test getting pending clarification requests."""
        with patch(
            "app.routes.content_prep.get_cko_chat_service",
            return_value=mock_cko_chat_service
        ):
            response = client.get("/api/content-prep/clarifications/pending/user-456")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["agent_id"] == "AGENT-016"

    def test_get_clarification_history(self, client, mock_clarification_logger):
        """Test getting clarification history."""
        with patch(
            "app.routes.content_prep.get_clarification_logger",
            return_value=mock_clarification_logger
        ):
            response = client.get("/api/content-prep/clarifications/history/set-123")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["agent_id"] == "AGENT-016"

    def test_cancel_clarification(self, client, mock_cko_chat_service):
        """Test canceling a clarification request."""
        with patch(
            "app.routes.content_prep.get_cko_chat_service",
            return_value=mock_cko_chat_service
        ):
            response = client.delete(
                "/api/content-prep/clarifications/req-123?agent_id=AGENT-016"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"


# =============================================================================
# ADMIN CLEANUP ENDPOINT TESTS
# =============================================================================

class TestContentPrepCleanupEndpoint:
    """Tests for /api/content-prep/admin/cleanup endpoint."""

    def test_trigger_async_cleanup(self, client):
        """Test triggering async cleanup."""
        with patch(
            "app.routes.content_prep.cleanup_old_content_sets"
        ) as mock_task:
            mock_result = MagicMock()
            mock_result.id = "task-123"
            mock_task.apply_async.return_value = mock_result

            response = client.post(
                "/api/content-prep/admin/cleanup",
                json={
                    "retention_days": 90,
                    "async_mode": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
            assert "task_id" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestContentPrepErrorHandling:
    """Tests for error handling in content prep endpoints."""

    def test_analyze_service_error_returns_500(self, client):
        """Test that service errors return 500 status."""
        mock_agent = MagicMock()
        mock_agent.analyze_folder = AsyncMock(
            side_effect=Exception("Storage service unavailable")
        )

        with patch(
            "app.routes.content_prep.ContentPrepAgent",
            return_value=mock_agent
        ):
            response = client.post(
                "/api/content-prep/analyze",
                json={
                    "b2_folder": "pending/courses/",
                    "detection_mode": "auto"
                }
            )

            assert response.status_code == 500

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/api/content-prep/analyze",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
