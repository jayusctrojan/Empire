"""
Unit tests for Master Orchestrator API Routes (AGENT-001).

Task 133: Implement Orchestrator API Routes
Tests for: /api/orchestrator/*
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
import os

# Set test environment
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_orchestrator_service():
    """Create mock orchestrator service."""
    with patch("app.routes.orchestrator._orchestrator_service", None):
        with patch("app.routes.orchestrator.create_orchestrator_agent") as mock_create:
            mock_service = MagicMock()

            # Mock the pattern analyzer
            mock_service.pattern_analyzer = MagicMock()
            mock_analysis = MagicMock()
            mock_analysis.word_count = 100
            mock_analysis.char_count = 500
            mock_analysis.has_code = False
            mock_analysis.has_tables = False
            mock_analysis.has_structured_data = False
            mock_analysis.complexity_score = 0.5
            mock_analysis.privacy_level = "cloud_eligible"
            mock_analysis.content_type = "document"
            mock_service.pattern_analyzer.analyze.return_value = mock_analysis

            # Mock the department classifier
            mock_service.department_classifier = MagicMock()
            mock_classification = MagicMock()
            mock_classification.department = MagicMock()
            mock_classification.department.value = "sales-marketing"
            mock_classification.confidence = 0.92
            mock_classification.reasoning = "High keyword match"
            mock_classification.keywords_matched = ["sales", "pipeline"]
            mock_classification.secondary_department = None
            mock_classification.secondary_confidence = 0.0
            mock_service.department_classifier.classify = AsyncMock(return_value=mock_classification)

            # Mock process_content
            mock_result = MagicMock()
            mock_result.classification = mock_classification
            mock_result.asset_decision = MagicMock()
            mock_result.asset_decision.asset_types = [MagicMock(value="prompt")]
            mock_result.asset_decision.primary_type = MagicMock(value="prompt")
            mock_result.asset_decision.reasoning = "Template detected"
            mock_result.asset_decision.needs_summary = True
            mock_result.asset_decision.summary_reasoning = "Long document"
            mock_result.delegation_targets = ["Content Summarizer Agent"]
            mock_result.output_paths = {"summary": "path/to/summary"}
            mock_result.processing_metadata = {"processing_time_seconds": 1.0}
            mock_service.process_content = AsyncMock(return_value=mock_result)

            # Mock get_stats
            mock_service.get_stats.return_value = {
                "agent_id": "AGENT-001",
                "agent_name": "Master Content Analyzer & Asset Orchestrator",
                "total_processed": 50,
                "by_department": {"sales-marketing": 20, "it-engineering": 15},
                "by_asset_type": {"prompt": 30, "skill": 10},
                "average_confidence": 0.85,
                "summaries_generated": 25
            }

            mock_create.return_value = mock_service
            yield mock_service


@pytest.fixture
def test_client():
    """Create test client."""
    from app.main import app
    with TestClient(app) as client:
        yield client


# ============================================================================
# Test: Coordinate Endpoint
# ============================================================================


@pytest.mark.integration
class TestCoordinateEndpoint:
    """Tests for POST /api/orchestrator/coordinate."""

    def test_coordinate_success(self, test_client, mock_orchestrator_service):
        """Test successful content orchestration."""
        response = test_client.post(
            "/api/orchestrator/coordinate",
            json={
                "content": "Advanced Sales Pipeline Management Framework for enterprise B2B sales.",
                "filename": "sales_guide.pdf",
                "user_id": "user-123"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "classification" in data
        assert data["classification"]["department"] == "sales-marketing"
        assert data["classification"]["confidence"] >= 0.0

        assert "asset_decision" in data
        assert "delegation_targets" in data
        assert "output_paths" in data

    def test_coordinate_minimal_request(self, test_client, mock_orchestrator_service):
        """Test orchestration with minimal request."""
        response = test_client.post(
            "/api/orchestrator/coordinate",
            json={
                "content": "This is some test content for processing."
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "classification" in data

    def test_coordinate_empty_content(self, test_client):
        """Test orchestration with empty content fails validation."""
        response = test_client.post(
            "/api/orchestrator/coordinate",
            json={
                "content": ""
            }
        )

        assert response.status_code == 422  # Validation error

    def test_coordinate_short_content(self, test_client):
        """Test orchestration with too short content fails validation."""
        response = test_client.post(
            "/api/orchestrator/coordinate",
            json={
                "content": "short"
            }
        )

        assert response.status_code == 422  # Validation error (min_length=10)

    def test_coordinate_with_metadata(self, test_client, mock_orchestrator_service):
        """Test orchestration with additional metadata."""
        response = test_client.post(
            "/api/orchestrator/coordinate",
            json={
                "content": "Technical documentation for API integration.",
                "metadata": {"source": "api_upload", "priority": "high"}
            }
        )

        assert response.status_code == 200


# ============================================================================
# Test: Classify Endpoint
# ============================================================================


@pytest.mark.integration
class TestClassifyEndpoint:
    """Tests for POST /api/orchestrator/classify."""

    def test_classify_success(self, test_client, mock_orchestrator_service):
        """Test successful classification."""
        response = test_client.post(
            "/api/orchestrator/classify",
            json={
                "content": "Quarterly financial report with revenue analysis and forecasts."
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "department" in data
        assert "confidence" in data
        assert "reasoning" in data
        assert data["confidence"] >= 0.0
        assert data["confidence"] <= 1.0

    def test_classify_with_filename(self, test_client, mock_orchestrator_service):
        """Test classification with filename hint."""
        response = test_client.post(
            "/api/orchestrator/classify",
            json={
                "content": "Some financial data and analysis.",
                "filename": "q3_financials.xlsx"
            }
        )

        assert response.status_code == 200

    def test_classify_force_llm(self, test_client, mock_orchestrator_service):
        """Test classification with forced LLM enhancement."""
        response = test_client.post(
            "/api/orchestrator/classify",
            json={
                "content": "Ambiguous content that could fit multiple departments.",
                "force_llm": True
            }
        )

        assert response.status_code == 200

    def test_classify_empty_content(self, test_client):
        """Test classification with empty content fails."""
        response = test_client.post(
            "/api/orchestrator/classify",
            json={
                "content": ""
            }
        )

        assert response.status_code == 422


# ============================================================================
# Test: Analyze Endpoint
# ============================================================================


@pytest.mark.integration
class TestAnalyzeEndpoint:
    """Tests for POST /api/orchestrator/analyze."""

    def test_analyze_success(self, test_client, mock_orchestrator_service):
        """Test successful content analysis."""
        response = test_client.post(
            "/api/orchestrator/analyze",
            json={
                "content": "def calculate_revenue():\n    return sum(sales) * 1.1"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "word_count" in data
        assert "char_count" in data
        assert "has_code" in data
        assert "complexity_score" in data
        assert "privacy_level" in data
        assert "content_type" in data

    def test_analyze_with_filename(self, test_client, mock_orchestrator_service):
        """Test analysis with filename hint."""
        response = test_client.post(
            "/api/orchestrator/analyze",
            json={
                "content": "Some Python code here...",
                "filename": "revenue.py"
            }
        )

        assert response.status_code == 200

    def test_analyze_empty_content(self, test_client):
        """Test analysis with empty content fails."""
        response = test_client.post(
            "/api/orchestrator/analyze",
            json={
                "content": ""
            }
        )

        assert response.status_code == 422


# ============================================================================
# Test: Agents Endpoints
# ============================================================================


@pytest.mark.integration
class TestAgentsEndpoints:
    """Tests for agent listing endpoints."""

    def test_list_agents(self, test_client):
        """Test listing all agents."""
        response = test_client.get("/api/orchestrator/agents")

        assert response.status_code == 200
        data = response.json()

        assert "total_agents" in data
        assert "agents" in data
        assert "by_status" in data
        assert "by_type" in data
        assert len(data["agents"]) > 0

    def test_list_agents_filter_by_type(self, test_client):
        """Test filtering agents by type."""
        response = test_client.get(
            "/api/orchestrator/agents",
            params={"agent_type": "orchestrator"}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned agents should be orchestrator type
        for agent in data["agents"]:
            assert agent["agent_type"] == "orchestrator"

    def test_list_agents_filter_by_status(self, test_client):
        """Test filtering agents by status."""
        response = test_client.get(
            "/api/orchestrator/agents",
            params={"status": "available"}
        )

        assert response.status_code == 200
        data = response.json()

        for agent in data["agents"]:
            assert agent["status"] == "available"

    def test_get_agent_by_id(self, test_client):
        """Test getting a specific agent by ID."""
        response = test_client.get("/api/orchestrator/agents/AGENT-001")

        assert response.status_code == 200
        data = response.json()

        assert data["agent_id"] == "AGENT-001"
        assert "name" in data
        assert "capabilities" in data

    def test_get_agent_not_found(self, test_client):
        """Test getting a non-existent agent."""
        response = test_client.get("/api/orchestrator/agents/AGENT-999")

        assert response.status_code == 404

    def test_agent_has_capabilities(self, test_client):
        """Test that agents have capabilities listed."""
        response = test_client.get("/api/orchestrator/agents/AGENT-001")

        assert response.status_code == 200
        data = response.json()

        assert "capabilities" in data
        assert len(data["capabilities"]) > 0


# ============================================================================
# Test: Health Endpoint
# ============================================================================


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for GET /api/orchestrator/health."""

    def test_health_check(self, test_client):
        """Test health check returns correct structure."""
        response = test_client.get("/api/orchestrator/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert data["agent_id"] == "AGENT-001"
        assert "version" in data
        assert "capabilities" in data
        assert "dependencies" in data

    def test_health_check_with_api_key(self, test_client):
        """Test health shows LLM available with API key."""
        # API key is set in the test environment
        response = test_client.get("/api/orchestrator/health")

        assert response.status_code == 200
        data = response.json()

        # With test API key set, llm_available should be True
        assert "llm_available" in data


# ============================================================================
# Test: Stats Endpoint
# ============================================================================


@pytest.mark.integration
class TestStatsEndpoint:
    """Tests for GET /api/orchestrator/stats."""

    def test_get_stats(self, test_client, mock_orchestrator_service):
        """Test getting orchestrator statistics."""
        response = test_client.get("/api/orchestrator/stats")

        assert response.status_code == 200
        data = response.json()

        assert "agent_id" in data
        assert "total_processed" in data
        assert "by_department" in data
        assert "by_asset_type" in data
        assert "average_confidence" in data
        assert "summaries_generated" in data

    def test_reset_stats(self, test_client, mock_orchestrator_service):
        """Test resetting statistics."""
        response = test_client.post("/api/orchestrator/stats/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Statistics reset successfully"


# ============================================================================
# Test: Info Endpoints
# ============================================================================


@pytest.mark.integration
class TestInfoEndpoints:
    """Tests for department and asset type info endpoints."""

    def test_list_departments(self, test_client):
        """Test listing all departments."""
        response = test_client.get("/api/orchestrator/departments")

        assert response.status_code == 200
        data = response.json()

        assert "total_departments" in data
        assert "departments" in data
        assert data["total_departments"] == 12
        assert "it-engineering" in data["departments"]
        assert "sales-marketing" in data["departments"]
        assert "_global" in data["departments"]

    def test_list_asset_types(self, test_client):
        """Test listing all asset types."""
        response = test_client.get("/api/orchestrator/asset-types")

        assert response.status_code == 200
        data = response.json()

        assert "total_asset_types" in data
        assert "asset_types" in data
        assert "default" in data
        assert data["default"] == "prompt"
        assert "skill" in data["asset_types"]
        assert "workflow" in data["asset_types"]


# ============================================================================
# Test: Model Validation
# ============================================================================


@pytest.mark.integration
class TestModelValidation:
    """Tests for Pydantic model validation."""

    def test_orchestration_request_validation(self, test_client):
        """Test OrchestrationRequest validation."""
        # Missing required field
        response = test_client.post(
            "/api/orchestrator/coordinate",
            json={}
        )
        assert response.status_code == 422

    def test_classification_request_validation(self, test_client):
        """Test ClassificationRequest validation."""
        # Content too short
        response = test_client.post(
            "/api/orchestrator/classify",
            json={"content": "short"}
        )
        assert response.status_code == 422

    def test_analyze_request_validation(self, test_client):
        """Test AnalyzeContentRequest validation."""
        # Content too short
        response = test_client.post(
            "/api/orchestrator/analyze",
            json={"content": "short"}
        )
        assert response.status_code == 422


# ============================================================================
# Test: Error Handling
# ============================================================================


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling."""

    def test_coordinate_service_error(self, test_client):
        """Test handling of service errors in coordinate endpoint."""
        with patch("app.routes.orchestrator.get_orchestrator_service") as mock:
            mock.return_value.process_content = AsyncMock(
                side_effect=Exception("Service unavailable")
            )

            response = test_client.post(
                "/api/orchestrator/coordinate",
                json={"content": "Valid content for testing error handling."}
            )

            assert response.status_code == 500

    def test_classify_service_error(self, test_client):
        """Test handling of service errors in classify endpoint."""
        with patch("app.routes.orchestrator.get_orchestrator_service") as mock:
            mock.return_value.department_classifier.classify = AsyncMock(
                side_effect=Exception("Classification failed")
            )

            response = test_client.post(
                "/api/orchestrator/classify",
                json={"content": "Valid content for testing."}
            )

            assert response.status_code == 500

    def test_invalid_json_body(self, test_client):
        """Test handling of invalid JSON body."""
        response = test_client.post(
            "/api/orchestrator/coordinate",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422


# ============================================================================
# Run Tests
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
