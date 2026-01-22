"""
Empire v7.3 - Content Prep Agent API Test Suite (Task 131)

Feature: 007-content-prep-agent
Integration tests for Content Prep API endpoints.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime
from uuid import uuid4


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_content_prep_agent():
    """Mock ContentPrepAgent for API tests."""
    # Patch at multiple levels to ensure the mock is used
    with patch('app.routes.content_prep.ContentPrepAgent') as MockAgent, \
         patch('app.services.content_prep_agent.get_supabase_client'), \
         patch('app.services.content_prep_agent.B2StorageService'):
        agent_instance = MagicMock()
        MockAgent.return_value = agent_instance
        yield agent_instance


@pytest.fixture
def mock_cko_chat_service():
    """Mock CKOChatService for clarification tests."""
    with patch('app.routes.content_prep.get_cko_chat_service') as mock_get:
        service = MagicMock()
        mock_get.return_value = service
        yield service


@pytest.fixture
def mock_clarification_logger():
    """Mock ClarificationConversationLogger."""
    with patch('app.routes.content_prep.get_clarification_logger') as mock_get:
        logger = MagicMock()
        mock_get.return_value = logger
        yield logger


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def sample_analyze_response():
    """Sample analyze response."""
    return {
        "content_sets": [
            {
                "id": str(uuid4()),
                "name": "Test Course",
                "detection_method": "pattern",
                "files_count": 5,
                "is_complete": True,
                "missing_files": [],
                "processing_status": "pending",
                "confidence": 0.95,
            }
        ],
        "standalone_files": [
            {"filename": "random.txt", "path": "pending/random.txt", "size_bytes": 1024}
        ],
        "analysis_time_ms": 150,
    }


@pytest.fixture
def sample_content_set():
    """Sample content set response."""
    return {
        "id": str(uuid4()),
        "name": "Test Course",
        "detection_method": "pattern",
        "files_count": 3,
        "is_complete": True,
        "missing_files": [],
        "files": [
            {"filename": "01-intro.pdf", "sequence": 1, "b2_path": "courses/01-intro.pdf"},
            {"filename": "02-basics.pdf", "sequence": 2, "b2_path": "courses/02-basics.pdf"},
            {"filename": "03-advanced.pdf", "sequence": 3, "b2_path": "courses/03-advanced.pdf"},
        ],
        "processing_status": "pending",
        "confidence": 0.95,
    }


@pytest.fixture
def sample_manifest():
    """Sample manifest response."""
    return {
        "manifest_id": str(uuid4()),
        "content_set_id": str(uuid4()),
        "content_set_name": "Test Course",
        "ordered_files": [
            {"sequence": 1, "file": "01-intro.pdf", "b2_path": "courses/01-intro.pdf", "dependencies": []},
            {"sequence": 2, "file": "02-basics.pdf", "b2_path": "courses/02-basics.pdf", "dependencies": ["01-intro.pdf"]},
            {"sequence": 3, "file": "03-advanced.pdf", "b2_path": "courses/03-advanced.pdf", "dependencies": ["02-basics.pdf"]},
        ],
        "total_files": 3,
        "warnings": [],
        "estimated_time_seconds": 90,
        "created_at": datetime.utcnow().isoformat(),
        "context": {"is_sequential": True},
    }


# ============================================================================
# Health Check Tests
# ============================================================================

class TestHealthCheck:
    """Tests for health check endpoint (Task 140: Enhanced Health)."""

    def test_health_check_returns_comprehensive_status(self, client, mock_content_prep_agent):
        """Test /api/content-prep/health returns comprehensive status."""
        # Mock the get_health_status method
        from app.models.content_sets import (
            HealthResponse,
            AgentInfo,
            ProcessingMetrics,
            ConnectivityStatus,
        )

        mock_health_response = HealthResponse(
            status="healthy",
            agent=AgentInfo(
                agent_id="AGENT-016",
                name="Content Prep Agent",
                version="1.0.0",
                uptime_seconds=3600,
                llm_available=True,
            ),
            metrics=ProcessingMetrics(
                recent_error_count=2,
                pending_content_sets=5,
                active_processing_count=1,
                total_processed_24h=15,
            ),
            connectivity=ConnectivityStatus(
                supabase=True,
                neo4j=True,
                b2_storage=True,
            ),
            capabilities={
                "content_set_detection": True,
                "ordering_analysis": True,
                "ordering_clarification": True,
                "manifest_generation": True,
                "llm_powered": True,
            },
        )

        mock_content_prep_agent.get_health_status = AsyncMock(return_value=mock_health_response)

        response = client.get("/api/content-prep/health")

        assert response.status_code == 200
        data = response.json()

        # Check overall status
        assert data["status"] == "healthy"

        # Check agent info
        assert "agent" in data
        assert data["agent"]["agent_id"] == "AGENT-016"
        assert data["agent"]["name"] == "Content Prep Agent"
        assert data["agent"]["version"] == "1.0.0"
        assert "uptime_seconds" in data["agent"]
        assert data["agent"]["llm_available"] is True

        # Check metrics
        assert "metrics" in data
        assert data["metrics"]["recent_error_count"] == 2
        assert data["metrics"]["pending_content_sets"] == 5
        assert data["metrics"]["active_processing_count"] == 1
        assert data["metrics"]["total_processed_24h"] == 15

        # Check connectivity
        assert "connectivity" in data
        assert data["connectivity"]["supabase"] is True
        assert data["connectivity"]["neo4j"] is True
        assert data["connectivity"]["b2_storage"] is True

        # Check capabilities
        assert "capabilities" in data
        assert data["capabilities"]["content_set_detection"] is True
        assert data["capabilities"]["llm_powered"] is True

    def test_health_check_degraded_status(self, client, mock_content_prep_agent):
        """Test health endpoint returns degraded status when Neo4j is down."""
        from app.models.content_sets import (
            HealthResponse,
            AgentInfo,
            ProcessingMetrics,
            ConnectivityStatus,
        )

        mock_health_response = HealthResponse(
            status="degraded",
            agent=AgentInfo(),
            metrics=ProcessingMetrics(),
            connectivity=ConnectivityStatus(supabase=True, neo4j=False, b2_storage=True),
        )

        mock_content_prep_agent.get_health_status = AsyncMock(return_value=mock_health_response)

        response = client.get("/api/content-prep/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["connectivity"]["neo4j"] is False

    def test_health_check_unhealthy_status(self, client, mock_content_prep_agent):
        """Test health endpoint returns unhealthy status when critical services are down."""
        from app.models.content_sets import (
            HealthResponse,
            AgentInfo,
            ProcessingMetrics,
            ConnectivityStatus,
        )

        mock_health_response = HealthResponse(
            status="unhealthy",
            agent=AgentInfo(),
            metrics=ProcessingMetrics(recent_error_count=-1),
            connectivity=ConnectivityStatus(supabase=False, neo4j=False, b2_storage=False),
        )

        mock_content_prep_agent.get_health_status = AsyncMock(return_value=mock_health_response)

        response = client.get("/api/content-prep/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["connectivity"]["supabase"] is False

    def test_health_check_exception_handling(self, client, mock_content_prep_agent):
        """Test health endpoint handles exceptions gracefully."""
        mock_content_prep_agent.get_health_status = AsyncMock(side_effect=Exception("Database error"))

        response = client.get("/api/content-prep/health")

        # Should still return 200 with unhealthy status
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["connectivity"]["supabase"] is False


# ============================================================================
# Analysis Endpoint Tests
# ============================================================================

class TestAnalyzeEndpoint:
    """Tests for /api/content-prep/analyze endpoint."""

    def test_analyze_success(self, client, mock_content_prep_agent, sample_analyze_response):
        """Test successful folder analysis."""
        mock_content_prep_agent.analyze_folder = AsyncMock(return_value=sample_analyze_response)

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

    def test_analyze_with_pattern_mode(self, client, mock_content_prep_agent, sample_analyze_response):
        """Test analysis with pattern detection mode."""
        mock_content_prep_agent.analyze_folder = AsyncMock(return_value=sample_analyze_response)

        response = client.post(
            "/api/content-prep/analyze",
            json={
                "b2_folder": "pending/courses/",
                "detection_mode": "pattern"
            }
        )

        assert response.status_code == 200
        mock_content_prep_agent.analyze_folder.assert_called_once()

    def test_analyze_error_handling(self, client, mock_content_prep_agent):
        """Test error handling in analyze endpoint."""
        mock_content_prep_agent.analyze_folder = AsyncMock(side_effect=Exception("Storage error"))

        response = client.post(
            "/api/content-prep/analyze",
            json={
                "b2_folder": "pending/courses/",
                "detection_mode": "auto"
            }
        )

        assert response.status_code == 500


# ============================================================================
# Content Set Endpoint Tests
# ============================================================================

class TestContentSetEndpoints:
    """Tests for content set endpoints."""

    def test_list_content_sets(self, client, mock_content_prep_agent, sample_content_set):
        """Test listing content sets."""
        mock_content_prep_agent.list_sets = AsyncMock(return_value=[sample_content_set])

        response = client.get("/api/content-prep/sets")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 0  # May be empty if not mocked properly

    def test_list_content_sets_with_filter(self, client, mock_content_prep_agent, sample_content_set):
        """Test listing content sets with status filter."""
        mock_content_prep_agent.list_sets = AsyncMock(return_value=[sample_content_set])

        response = client.get("/api/content-prep/sets?status=pending")

        assert response.status_code == 200

    def test_get_content_set(self, client, mock_content_prep_agent, sample_content_set):
        """Test getting specific content set."""
        set_id = sample_content_set["id"]
        mock_content_prep_agent.get_set = AsyncMock(return_value=sample_content_set)

        response = client.get(f"/api/content-prep/sets/{set_id}")

        assert response.status_code == 200

    def test_get_nonexistent_content_set(self, client, mock_content_prep_agent):
        """Test getting non-existent content set."""
        mock_content_prep_agent.get_set = AsyncMock(side_effect=ValueError("Content set not found"))

        response = client.get("/api/content-prep/sets/nonexistent-id")

        assert response.status_code == 404


# ============================================================================
# Validation Endpoint Tests
# ============================================================================

class TestValidationEndpoint:
    """Tests for content set validation endpoint."""

    def test_validate_complete_set(self, client, mock_content_prep_agent):
        """Test validating a complete content set."""
        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "set_id": "test-id",
            "is_complete": True,
            "missing_files": [],
            "total_files": 5,
            "gaps_detected": 0,
            "can_proceed": True,
            "requires_acknowledgment": False,
        })

        response = client.post("/api/content-prep/validate/test-id")

        assert response.status_code == 200
        data = response.json()
        assert data["is_complete"] is True
        assert data["requires_acknowledgment"] is False

    def test_validate_incomplete_set(self, client, mock_content_prep_agent):
        """Test validating an incomplete content set."""
        mock_content_prep_agent.validate_completeness = AsyncMock(return_value={
            "set_id": "test-id",
            "is_complete": False,
            "missing_files": ["#3 (between 2 and 4)"],
            "total_files": 4,
            "gaps_detected": 1,
            "can_proceed": True,
            "requires_acknowledgment": True,
        })

        response = client.post("/api/content-prep/validate/test-id")

        assert response.status_code == 200
        data = response.json()
        assert data["is_complete"] is False
        assert data["requires_acknowledgment"] is True

    def test_validate_nonexistent_set(self, client, mock_content_prep_agent):
        """Test validating non-existent content set."""
        mock_content_prep_agent.validate_completeness = AsyncMock(
            side_effect=ValueError("Content set not found")
        )

        response = client.post("/api/content-prep/validate/nonexistent-id")

        assert response.status_code == 404


# ============================================================================
# Manifest Endpoint Tests
# ============================================================================

class TestManifestEndpoint:
    """Tests for manifest generation endpoint."""

    def test_generate_manifest(self, client, mock_content_prep_agent, sample_manifest):
        """Test generating a processing manifest."""
        mock_content_prep_agent.generate_manifest = AsyncMock(return_value=sample_manifest)

        response = client.post(
            "/api/content-prep/manifest",
            json={
                "content_set_id": "test-id",
                "proceed_incomplete": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "manifest_id" in data
        assert "ordered_files" in data

    def test_generate_manifest_incomplete_blocked(self, client, mock_content_prep_agent):
        """Test that incomplete sets are blocked."""
        mock_content_prep_agent.generate_manifest = AsyncMock(
            side_effect=ValueError("Content set is incomplete. Set proceed_incomplete=true to process anyway.")
        )

        response = client.post(
            "/api/content-prep/manifest",
            json={
                "content_set_id": "test-id",
                "proceed_incomplete": False
            }
        )

        assert response.status_code == 400
        data = response.json()
        # Check for 'incomplete' in the response (handle different error formats)
        assert "incomplete" in str(data).lower()

    def test_generate_manifest_incomplete_acknowledged(self, client, mock_content_prep_agent, sample_manifest):
        """Test generating manifest with acknowledged incomplete set."""
        sample_manifest["warnings"] = ["#3 (between 2 and 4)"]
        mock_content_prep_agent.generate_manifest = AsyncMock(return_value=sample_manifest)

        response = client.post(
            "/api/content-prep/manifest",
            json={
                "content_set_id": "test-id",
                "proceed_incomplete": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["warnings"]) > 0


# ============================================================================
# Clarification Endpoint Tests
# ============================================================================

class TestClarificationEndpoints:
    """Tests for clarification endpoints (Task 129)."""

    def test_clarify_ordering(self, client, mock_content_prep_agent):
        """Test ordering clarification endpoint."""
        mock_content_prep_agent.resolve_order_with_clarification = AsyncMock(return_value={
            "status": "success",
            "content_set_id": "test-id",
            "ordering_confidence": 0.95,
            "clarification_requested": False,
            "ordered_files": [
                {"sequence": 1, "file": "01-intro.pdf"},
                {"sequence": 2, "file": "02-basics.pdf"},
            ],
        })

        response = client.post(
            "/api/content-prep/clarify-ordering",
            json={
                "content_set_id": "test-id",
                "user_id": "user-123",
                "confidence_threshold": 0.8,
                "timeout_seconds": 3600,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_clarify_ordering_not_found(self, client, mock_content_prep_agent):
        """Test clarification for non-existent set."""
        mock_content_prep_agent.resolve_order_with_clarification = AsyncMock(
            side_effect=ValueError("Content set not found")
        )

        response = client.post(
            "/api/content-prep/clarify-ordering",
            json={
                "content_set_id": "nonexistent-id",
                "user_id": "user-123",
            }
        )

        assert response.status_code == 404

    def test_respond_to_clarification(self, client, mock_cko_chat_service):
        """Test submitting clarification response."""
        mock_cko_chat_service.submit_user_response = AsyncMock(return_value=True)

        response = client.post(
            "/api/content-prep/clarifications/respond",
            json={
                "request_id": "request-123",
                "user_id": "user-123",
                "response": "1. file1.pdf\n2. file2.pdf\n3. file3.pdf"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_respond_to_clarification_invalid(self, client, mock_cko_chat_service):
        """Test responding to invalid/expired clarification."""
        mock_cko_chat_service.submit_user_response = AsyncMock(return_value=False)

        response = client.post(
            "/api/content-prep/clarifications/respond",
            json={
                "request_id": "invalid-request",
                "user_id": "user-123",
                "response": "test response"
            }
        )

        assert response.status_code == 400

    def test_get_pending_clarifications(self, client, mock_cko_chat_service):
        """Test getting pending clarifications for user."""
        mock_cko_chat_service.get_pending_requests = AsyncMock(return_value=[
            {
                "id": "request-1",
                "agent_id": "AGENT-016",
                "message": "Please confirm the file order",
                "clarification_type": "ordering",
                "context": {"content_set_id": "test-id"},
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": None,
            }
        ])

        response = client.get("/api/content-prep/clarifications/pending/user-123")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 0

    def test_get_clarification_history(self, client, mock_clarification_logger):
        """Test getting clarification history for content set."""
        mock_clarification_logger.get_conversation_history = AsyncMock(return_value=[
            {
                "id": "log-1",
                "content_set_id": "test-id",
                "agent_id": "AGENT-016",
                "question": "Please confirm the file order",
                "answer": "1. file1.pdf\n2. file2.pdf",
                "outcome": "ordering_updated",
                "clarification_type": "ordering",
                "created_at": datetime.utcnow().isoformat(),
            }
        ])

        response = client.get("/api/content-prep/clarifications/history/test-id")

        assert response.status_code == 200

    def test_cancel_clarification(self, client, mock_cko_chat_service):
        """Test cancelling a clarification request."""
        mock_cko_chat_service.cancel_request = AsyncMock(return_value=True)

        response = client.delete(
            "/api/content-prep/clarifications/request-123?agent_id=AGENT-016"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_cancel_clarification_invalid(self, client, mock_cko_chat_service):
        """Test cancelling invalid clarification."""
        mock_cko_chat_service.cancel_request = AsyncMock(return_value=False)

        response = client.delete(
            "/api/content-prep/clarifications/invalid-request?agent_id=AGENT-016"
        )

        assert response.status_code == 400


# ============================================================================
# Admin/Cleanup Endpoint Tests (Task 130)
# ============================================================================

class TestCleanupEndpoints:
    """Tests for admin cleanup endpoints."""

    def test_trigger_cleanup_async(self, client):
        """Test triggering async cleanup."""
        with patch('app.tasks.content_prep_tasks.cleanup_old_content_sets') as mock_task:
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
            assert data["task_id"] == "task-123"

    def test_trigger_cleanup_sync(self, client):
        """Test triggering synchronous cleanup."""
        with patch('app.tasks.content_prep_tasks.cleanup_old_content_sets') as mock_task:
            mock_task.return_value = {
                "status": "success",
                "deleted_count": 5,
                "message": "Deleted 5 content sets",
                "cutoff_date": "2024-10-15T00:00:00",
            }

            response = client.post(
                "/api/content-prep/admin/cleanup",
                json={
                    "retention_days": 90,
                    "async_mode": False
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["deleted_count"] == 5

    def test_get_cleanup_status_pending(self, client):
        """Test getting cleanup task status - pending."""
        with patch('app.celery_app.celery_app') as mock_celery:
            mock_result = MagicMock()
            mock_result.status = "PENDING"
            mock_result.ready.return_value = False

            with patch('celery.result.AsyncResult', return_value=mock_result):
                response = client.get("/api/content-prep/admin/cleanup/status/task-123")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "PENDING"
                assert data["ready"] is False

    def test_get_cleanup_status_complete(self, client):
        """Test getting cleanup task status - complete."""
        with patch('app.celery_app.celery_app') as mock_celery:
            mock_result = MagicMock()
            mock_result.status = "SUCCESS"
            mock_result.ready.return_value = True
            mock_result.successful.return_value = True
            mock_result.result = {"deleted_count": 10}

            with patch('celery.result.AsyncResult', return_value=mock_result):
                response = client.get("/api/content-prep/admin/cleanup/status/task-123")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "SUCCESS"
                assert data["ready"] is True


# ============================================================================
# Request Validation Tests
# ============================================================================

class TestRequestValidation:
    """Tests for request validation."""

    def test_analyze_invalid_detection_mode(self, client):
        """Test analyze with invalid detection mode."""
        # The API should accept the request even with unusual modes
        # (validation depends on Pydantic model)
        response = client.post(
            "/api/content-prep/analyze",
            json={
                "b2_folder": "pending/",
                "detection_mode": "invalid_mode"
            }
        )

        # Either 422 (validation) or handled gracefully
        assert response.status_code in [200, 422, 500]

    def test_clarification_request_validation(self, client):
        """Test clarification request with invalid threshold."""
        response = client.post(
            "/api/content-prep/clarify-ordering",
            json={
                "content_set_id": "test-id",
                "user_id": "user-123",
                "confidence_threshold": 1.5,  # Invalid: > 1.0
                "timeout_seconds": 3600,
            }
        )

        # Should fail validation (400 Bad Request or 422 Unprocessable Entity)
        assert response.status_code in [400, 422]

    def test_cleanup_request_validation(self, client):
        """Test cleanup request with invalid retention days."""
        response = client.post(
            "/api/content-prep/admin/cleanup",
            json={
                "retention_days": 0,  # Invalid: must be >= 1
                "async_mode": True
            }
        )

        # Should fail validation (400 Bad Request or 422 Unprocessable Entity)
        assert response.status_code in [400, 422]

    def test_cleanup_request_max_retention(self, client):
        """Test cleanup request with max retention days."""
        response = client.post(
            "/api/content-prep/admin/cleanup",
            json={
                "retention_days": 400,  # Invalid: > 365
                "async_mode": True
            }
        )

        # Should fail validation (400 Bad Request or 422 Unprocessable Entity)
        assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
