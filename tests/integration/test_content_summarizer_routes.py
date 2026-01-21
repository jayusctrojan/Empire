"""
Integration Tests for Content Summarizer Agent API Routes (AGENT-002).
Task 139: Create Integration Tests for Agent API Routes

Tests the full request-response cycle for:
- POST /api/summarizer/generate - Generate document summary
- POST /api/summarizer/diagram - Create visual diagram
- POST /api/summarizer/chart - Create chart
- GET /api/summarizer/stats - Get summarizer statistics
- GET /api/summarizer/departments - Get supported departments
- GET /api/summarizer/health - Health check
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_summarizer_service():
    """Mock the ContentSummarizerAgentService."""
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.pdf_path = "/processed/crewai-summaries/it-engineering/test_summary.pdf"
    mock_result.department = "it-engineering"
    mock_result.title = "Test Summary"
    mock_result.sections_generated = ["executive_summary", "key_concepts", "implementation"]
    mock_result.diagrams_generated = 2
    mock_result.tables_generated = 1
    mock_result.error = None
    mock_result.processing_time_seconds = 5.5
    mock_result.metadata = {"word_count": 500}

    mock_service = MagicMock()
    mock_service.generate_summary = AsyncMock(return_value=mock_result)
    mock_service.get_stats.return_value = {
        "agent_id": "AGENT-002",
        "agent_name": "Content Summarizer Agent",
        "summaries_generated": 10,
        "diagrams_created": 25,
        "charts_created": 15,
        "by_department": {"it-engineering": 5, "sales-marketing": 3, "finance-accounting": 2}
    }

    # Mock diagram creator
    mock_diagram_creator = MagicMock()
    mock_diagram_creator.create_diagram.return_value = "/processed/diagrams/test_diagram.png"
    mock_service.diagram_creator = mock_diagram_creator

    # Mock chart builder
    mock_chart_builder = MagicMock()
    mock_chart_builder.create_bar_chart.return_value = "/processed/charts/test_bar_chart.png"
    mock_chart_builder.create_pie_chart.return_value = "/processed/charts/test_pie_chart.png"
    mock_service.chart_builder = mock_chart_builder

    return mock_service


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestSummarizerHealthEndpoint:
    """Tests for /api/summarizer/health endpoint."""

    def test_health_check_returns_healthy(self, client, validate_health_response):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/summarizer/health")

        assert response.status_code == 200
        data = response.json()
        validate_health_response(data)
        assert data["agent_id"] == "AGENT-002"
        assert data["agent_name"] == "Content Summarizer Agent"
        assert "capabilities" in data

    def test_health_check_includes_capabilities(self, client):
        """Test that health endpoint includes capability information."""
        response = client.get("/api/summarizer/health")

        assert response.status_code == 200
        data = response.json()
        assert "capabilities" in data
        assert "pdf_generation" in data["capabilities"]
        assert "diagram_creation" in data["capabilities"]
        assert "chart_creation" in data["capabilities"]


# =============================================================================
# DEPARTMENTS ENDPOINT TESTS
# =============================================================================

class TestSummarizerDepartmentsEndpoint:
    """Tests for /api/summarizer/departments endpoint."""

    def test_get_departments_returns_list(self, client):
        """Test that departments endpoint returns list of departments."""
        response = client.get("/api/summarizer/departments")

        assert response.status_code == 200
        data = response.json()
        assert "departments" in data
        assert isinstance(data["departments"], list)
        assert len(data["departments"]) > 0

    def test_get_departments_includes_expected_departments(self, client):
        """Test that departments list includes expected values."""
        response = client.get("/api/summarizer/departments")

        assert response.status_code == 200
        data = response.json()
        expected_departments = ["it-engineering", "sales-marketing", "finance-accounting"]
        for dept in expected_departments:
            assert dept in data["departments"]

    def test_get_departments_includes_diagram_types(self, client):
        """Test that response includes diagram types."""
        response = client.get("/api/summarizer/departments")

        assert response.status_code == 200
        data = response.json()
        assert "diagram_types" in data
        assert isinstance(data["diagram_types"], list)

    def test_get_departments_includes_chart_types(self, client):
        """Test that response includes chart types."""
        response = client.get("/api/summarizer/departments")

        assert response.status_code == 200
        data = response.json()
        assert "chart_types" in data
        assert "bar" in data["chart_types"]
        assert "pie" in data["chart_types"]


# =============================================================================
# GENERATE SUMMARY ENDPOINT TESTS
# =============================================================================

class TestSummarizerGenerateEndpoint:
    """Tests for /api/summarizer/generate endpoint."""

    def test_generate_summary_success(self, client, mock_summarizer_service, sample_document_content):
        """Test successful summary generation."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/generate",
                json={
                    "content": sample_document_content,
                    "department": "it-engineering",
                    "title": "Test Summary"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["department"] == "it-engineering"
            assert data["title"] == "Test Summary"
            assert "pdf_path" in data
            assert "sections_generated" in data

    def test_generate_summary_with_metadata(self, client, mock_summarizer_service, sample_document_content):
        """Test summary generation with custom metadata."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/generate",
                json={
                    "content": sample_document_content,
                    "department": "sales-marketing",
                    "title": "Sales Report Summary",
                    "source_type": "report",
                    "metadata": {"author": "Test User", "version": "1.0"}
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_generate_summary_missing_content_returns_422(self, client):
        """Test that missing content returns validation error."""
        response = client.post(
            "/api/summarizer/generate",
            json={
                "department": "it-engineering",
                "title": "Test Summary"
            }
        )

        assert response.status_code == 400

    def test_generate_summary_short_content_returns_422(self, client):
        """Test that content below minimum length returns validation error."""
        response = client.post(
            "/api/summarizer/generate",
            json={
                "content": "Too short",
                "department": "it-engineering",
                "title": "Test Summary"
            }
        )

        assert response.status_code == 400

    def test_generate_summary_missing_department_returns_422(self, client, sample_document_content):
        """Test that missing department returns validation error."""
        response = client.post(
            "/api/summarizer/generate",
            json={
                "content": sample_document_content,
                "title": "Test Summary"
            }
        )

        assert response.status_code == 400

    def test_generate_summary_missing_title_returns_422(self, client, sample_document_content):
        """Test that missing title returns validation error."""
        response = client.post(
            "/api/summarizer/generate",
            json={
                "content": sample_document_content,
                "department": "it-engineering"
            }
        )

        assert response.status_code == 400


# =============================================================================
# DIAGRAM ENDPOINT TESTS
# =============================================================================

class TestSummarizerDiagramEndpoint:
    """Tests for /api/summarizer/diagram endpoint."""

    def test_create_flowchart_diagram(self, client, mock_summarizer_service):
        """Test creating a flowchart diagram."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/diagram",
                json={
                    "diagram_type": "flowchart",
                    "title": "Process Flow",
                    "department": "it-engineering",
                    "elements": [
                        {"id": "1", "label": "Start", "type": "start"},
                        {"id": "2", "label": "Process", "type": "process"},
                        {"id": "3", "label": "End", "type": "end"}
                    ],
                    "connections": [
                        {"from": "1", "to": "2"},
                        {"from": "2", "to": "3"}
                    ]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["diagram_type"] == "flowchart"
            assert "diagram_path" in data

    def test_create_hierarchy_diagram(self, client, mock_summarizer_service):
        """Test creating a hierarchy diagram."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/diagram",
                json={
                    "diagram_type": "hierarchy",
                    "title": "Organization Chart",
                    "department": "operations-hr-supply",
                    "elements": [
                        {"id": "1", "label": "CEO", "type": "root"},
                        {"id": "2", "label": "CTO", "type": "node"},
                        {"id": "3", "label": "CFO", "type": "node"}
                    ]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["diagram_type"] == "hierarchy"

    def test_create_diagram_missing_elements_returns_422(self, client):
        """Test that missing elements returns validation error."""
        response = client.post(
            "/api/summarizer/diagram",
            json={
                "diagram_type": "flowchart",
                "title": "Test Diagram",
                "department": "it-engineering"
            }
        )

        assert response.status_code == 400

    def test_create_diagram_empty_elements_returns_422(self, client):
        """Test that empty elements list returns validation error."""
        response = client.post(
            "/api/summarizer/diagram",
            json={
                "diagram_type": "flowchart",
                "title": "Test Diagram",
                "department": "it-engineering",
                "elements": []
            }
        )

        assert response.status_code == 400


# =============================================================================
# CHART ENDPOINT TESTS
# =============================================================================

class TestSummarizerChartEndpoint:
    """Tests for /api/summarizer/chart endpoint."""

    def test_create_bar_chart(self, client, mock_summarizer_service):
        """Test creating a bar chart."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/chart",
                json={
                    "chart_type": "bar",
                    "title": "Monthly Revenue",
                    "department": "finance-accounting",
                    "labels": ["Jan", "Feb", "Mar", "Apr"],
                    "values": [100, 150, 120, 180],
                    "ylabel": "Revenue ($K)"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["chart_type"] == "bar"
            assert "chart_path" in data

    def test_create_pie_chart(self, client, mock_summarizer_service):
        """Test creating a pie chart."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/chart",
                json={
                    "chart_type": "pie",
                    "title": "Market Share",
                    "department": "sales-marketing",
                    "labels": ["Product A", "Product B", "Product C"],
                    "values": [45, 30, 25]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["chart_type"] == "pie"

    def test_create_chart_invalid_type_returns_400(self, client, mock_summarizer_service):
        """Test that invalid chart type returns 400 error."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.post(
                "/api/summarizer/chart",
                json={
                    "chart_type": "invalid_type",
                    "title": "Test Chart",
                    "department": "it-engineering",
                    "labels": ["A", "B"],
                    "values": [10, 20]
                }
            )

            assert response.status_code == 400


# =============================================================================
# STATS ENDPOINT TESTS
# =============================================================================

class TestSummarizerStatsEndpoint:
    """Tests for /api/summarizer/stats endpoint."""

    def test_get_stats_returns_statistics(self, client, mock_summarizer_service):
        """Test that stats endpoint returns statistics."""
        with patch(
            "app.routes.content_summarizer.get_summarizer_service",
            return_value=mock_summarizer_service
        ):
            response = client.get("/api/summarizer/stats")

            assert response.status_code == 200
            data = response.json()
            assert "agent_id" in data
            assert data["agent_id"] == "AGENT-002"
            assert "summaries_generated" in data
            assert "diagrams_created" in data
            assert "charts_created" in data
            assert "by_department" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestSummarizerErrorHandling:
    """Tests for error handling in summarizer endpoints."""

    def test_generate_summary_service_error_returns_500(self, client, sample_document_content):
        """Test that service errors return 500 status."""
        from app.routes.content_summarizer import get_summarizer_service
        from app.main import app

        mock_service = MagicMock()
        mock_service.generate_summary = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        # Use FastAPI's dependency override system
        app.dependency_overrides[get_summarizer_service] = lambda: mock_service

        try:
            response = client.post(
                "/api/summarizer/generate",
                json={
                    "content": sample_document_content,
                    "department": "it-engineering",
                    "title": "Test Summary"
                }
            )

            assert response.status_code == 500
        finally:
            # Clean up the override
            app.dependency_overrides.pop(get_summarizer_service, None)

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/api/summarizer/generate",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
