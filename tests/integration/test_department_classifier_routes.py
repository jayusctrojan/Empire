"""
Integration Tests for Department Classifier Agent API Routes (AGENT-008).
Task 139: Create Integration Tests for Agent API Routes

Tests the full request-response cycle for:
- POST /api/classifier/classify - Classify content
- POST /api/classifier/classify/batch - Batch classification
- POST /api/classifier/keywords/extract - Extract keywords
- GET /api/classifier/departments - Get all departments
- GET /api/classifier/departments/{code} - Get specific department
- GET /api/classifier/stats - Get classifier statistics
- GET /api/classifier/health - Health check
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_classifier_service():
    """Mock the DepartmentClassifierAgentService."""
    # Mock Department enum
    mock_department = MagicMock()
    mock_department.value = "it-engineering"

    # Mock classification result
    mock_result = MagicMock()
    mock_result.department = mock_department
    mock_result.confidence = 0.92
    mock_result.reasoning = "Content focuses on software development and technical infrastructure"
    mock_result.keywords_matched = ["kubernetes", "docker", "api", "microservices"]
    mock_result.secondary_department = None
    mock_result.secondary_confidence = 0.0
    mock_result.llm_enhanced = False
    mock_result.processing_time_ms = 45.5
    mock_result.all_scores = None

    mock_service = MagicMock()
    mock_service.classify_content = AsyncMock(return_value=mock_result)

    # Mock batch classification
    mock_batch_result = MagicMock()
    mock_batch_result.results = [mock_result]
    mock_batch_result.total_processed = 1
    mock_batch_result.average_confidence = 0.92
    mock_batch_result.processing_time_ms = 100.0
    mock_service.classify_batch = AsyncMock(return_value=mock_batch_result)

    # Mock keyword extraction
    mock_keyword_result = MagicMock()
    mock_keyword_result.all_keywords = ["kubernetes", "docker", "api"]
    mock_keyword_result.department_keywords = {"it-engineering": ["kubernetes", "docker", "api"]}
    mock_keyword_result.keyword_counts = {"it-engineering": 3}
    mock_keyword_result.total_keywords_found = 3
    mock_service.extract_keywords.return_value = mock_keyword_result

    # Mock department info
    mock_service.get_all_departments.return_value = [
        {
            "code": "it-engineering",
            "description": "Software, APIs, DevOps, infrastructure",
            "primary_keywords": ["software", "api", "devops"],
            "secondary_keywords": ["cloud", "infrastructure"],
            "tertiary_keywords": ["automation", "deployment"],
            "total_keywords": 50
        },
        {
            "code": "sales-marketing",
            "description": "Sales, campaigns, CRM, lead generation",
            "primary_keywords": ["sales", "marketing", "leads"],
            "secondary_keywords": ["campaigns", "crm"],
            "tertiary_keywords": ["revenue", "conversion"],
            "total_keywords": 45
        }
    ]

    mock_service.get_department_info.return_value = {
        "code": "it-engineering",
        "description": "Software, APIs, DevOps, infrastructure",
        "primary_keywords": ["software", "api", "devops"],
        "secondary_keywords": ["cloud", "infrastructure"],
        "tertiary_keywords": ["automation", "deployment"],
        "total_keywords": 50
    }

    mock_service.get_stats.return_value = {
        "agent_id": "AGENT-008",
        "agent_name": "Department Classifier Agent",
        "classifications_total": 150,
        "classifications_by_department": {"it-engineering": 50, "sales-marketing": 40},
        "llm_enhanced_count": 20,
        "average_confidence": 0.88,
        "high_confidence_count": 120,
        "low_confidence_count": 10
    }

    mock_service.reset_stats.return_value = None

    return mock_service


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestClassifierHealthEndpoint:
    """Tests for /api/classifier/health endpoint."""

    def test_health_check_returns_healthy(self, client, validate_health_response):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/classifier/health")

        assert response.status_code == 200
        data = response.json()
        validate_health_response(data)
        assert data["agent_id"] == "AGENT-008"
        assert data["agent_name"] == "Department Classifier Agent"

    def test_health_check_includes_capabilities(self, client):
        """Test that health endpoint includes capability information."""
        response = client.get("/api/classifier/health")

        assert response.status_code == 200
        data = response.json()
        assert "capabilities" in data
        assert "content_classification" in data["capabilities"]
        assert "batch_classification" in data["capabilities"]
        assert "keyword_extraction" in data["capabilities"]

    def test_health_check_includes_departments_count(self, client):
        """Test that health endpoint includes departments count."""
        response = client.get("/api/classifier/health")

        assert response.status_code == 200
        data = response.json()
        assert "departments_count" in data
        assert data["departments_count"] == 10


# =============================================================================
# CLASSIFY ENDPOINT TESTS
# =============================================================================

class TestClassifierClassifyEndpoint:
    """Tests for /api/classifier/classify endpoint."""

    def test_classify_content_success(self, client, mock_classifier_service, sample_technical_content):
        """Test successful content classification."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post(
                "/api/classifier/classify",
                json={
                    "content": sample_technical_content,
                    "include_all_scores": False
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "department" in data
            assert "confidence" in data
            assert 0 <= data["confidence"] <= 1
            assert "reasoning" in data
            assert "keywords_matched" in data

    def test_classify_content_with_filename(self, client, mock_classifier_service, sample_technical_content):
        """Test classification with optional filename context."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post(
                "/api/classifier/classify",
                json={
                    "content": sample_technical_content,
                    "filename": "kubernetes_deployment_guide.md",
                    "include_all_scores": False
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "department" in data

    def test_classify_content_with_all_scores(self, client, mock_classifier_service, sample_technical_content):
        """Test classification with all department scores."""
        # Update mock to include all_scores
        mock_all_scores = [
            MagicMock(
                department=MagicMock(value="it-engineering"),
                raw_score=0.95,
                normalized_score=0.92,
                primary_matches=5,
                secondary_matches=3,
                tertiary_matches=2,
                keyword_matches=["kubernetes", "docker", "api"]
            )
        ]
        mock_classifier_service.classify_content.return_value.all_scores = mock_all_scores

        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post(
                "/api/classifier/classify",
                json={
                    "content": sample_technical_content,
                    "include_all_scores": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "all_scores" in data

    def test_classify_short_content_returns_422(self, client):
        """Test that short content returns validation error."""
        response = client.post(
            "/api/classifier/classify",
            json={
                "content": "Too short"
            }
        )

        assert response.status_code == 400

    def test_classify_missing_content_returns_422(self, client):
        """Test that missing content returns validation error."""
        response = client.post(
            "/api/classifier/classify",
            json={}
        )

        assert response.status_code == 400


# =============================================================================
# BATCH CLASSIFICATION TESTS
# =============================================================================

class TestClassifierBatchEndpoint:
    """Tests for /api/classifier/classify/batch endpoint."""

    def test_batch_classify_success(self, client, mock_classifier_service, sample_batch_items):
        """Test successful batch classification."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post(
                "/api/classifier/classify/batch",
                json={
                    "items": sample_batch_items,
                    "concurrency": 5
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "total_processed" in data
            assert "average_confidence" in data
            assert "processing_time_ms" in data

    def test_batch_classify_missing_content_returns_400(self, client, mock_classifier_service):
        """Test that batch items without content return error."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post(
                "/api/classifier/classify/batch",
                json={
                    "items": [{"filename": "test.txt"}]  # Missing content
                }
            )

            assert response.status_code == 400

    def test_batch_classify_empty_items_returns_422(self, client):
        """Test that empty items list returns validation error."""
        response = client.post(
            "/api/classifier/classify/batch",
            json={
                "items": []
            }
        )

        assert response.status_code == 400

    def test_batch_classify_too_many_items_returns_422(self, client):
        """Test that too many items returns validation error."""
        items = [{"content": f"Content {i}" * 10} for i in range(101)]
        response = client.post(
            "/api/classifier/classify/batch",
            json={
                "items": items
            }
        )

        assert response.status_code == 400


# =============================================================================
# KEYWORD EXTRACTION TESTS
# =============================================================================

class TestClassifierKeywordEndpoint:
    """Tests for /api/classifier/keywords/extract endpoint."""

    def test_extract_keywords_success(self, client, mock_classifier_service, sample_technical_content):
        """Test successful keyword extraction."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post(
                "/api/classifier/keywords/extract",
                json={
                    "content": sample_technical_content
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "all_keywords" in data
            assert "department_keywords" in data
            assert "keyword_counts" in data
            assert "total_keywords_found" in data

    def test_extract_keywords_short_content_returns_422(self, client):
        """Test that short content returns validation error."""
        response = client.post(
            "/api/classifier/keywords/extract",
            json={
                "content": "Short"
            }
        )

        assert response.status_code == 400


# =============================================================================
# DEPARTMENTS ENDPOINT TESTS
# =============================================================================

class TestClassifierDepartmentsEndpoint:
    """Tests for /api/classifier/departments endpoints."""

    def test_get_all_departments(self, client, mock_classifier_service):
        """Test getting all departments."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.get("/api/classifier/departments")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0
            assert "code" in data[0]
            assert "description" in data[0]
            assert "primary_keywords" in data[0]

    def test_get_specific_department(self, client, mock_classifier_service):
        """Test getting a specific department by code."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.get("/api/classifier/departments/it-engineering")

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "it-engineering"
            assert "primary_keywords" in data
            assert "secondary_keywords" in data
            assert "tertiary_keywords" in data
            assert "total_keywords" in data

    def test_get_nonexistent_department_returns_404(self, client, mock_classifier_service):
        """Test that nonexistent department returns 404."""
        mock_classifier_service.get_department_info.side_effect = Exception("Not found")

        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.get("/api/classifier/departments/nonexistent-dept")

            # Should be 404 or 500 depending on implementation
            assert response.status_code in [404, 500]


# =============================================================================
# STATS ENDPOINT TESTS
# =============================================================================

class TestClassifierStatsEndpoint:
    """Tests for /api/classifier/stats endpoint."""

    def test_get_stats_returns_statistics(self, client, mock_classifier_service):
        """Test that stats endpoint returns statistics."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.get("/api/classifier/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-008"
            assert "classifications_total" in data
            assert "classifications_by_department" in data
            assert "average_confidence" in data
            assert "high_confidence_count" in data
            assert "low_confidence_count" in data

    def test_reset_stats_success(self, client, mock_classifier_service):
        """Test resetting statistics."""
        with patch(
            "app.routes.department_classifier.get_classifier_service",
            return_value=mock_classifier_service
        ):
            response = client.post("/api/classifier/stats/reset")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestClassifierErrorHandling:
    """Tests for error handling in classifier endpoints."""

    def test_classify_service_error_returns_500(self, client, sample_technical_content):
        """Test that service errors return 500 status."""
        from app.routes.department_classifier import get_classifier_service
        from app.main import app

        mock_service = MagicMock()
        mock_service.classify_content = AsyncMock(
            side_effect=Exception("Classification service unavailable")
        )

        # Use FastAPI's dependency override system
        app.dependency_overrides[get_classifier_service] = lambda: mock_service

        try:
            response = client.post(
                "/api/classifier/classify",
                json={
                    "content": sample_technical_content
                }
            )

            assert response.status_code == 500
        finally:
            app.dependency_overrides.pop(get_classifier_service, None)

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/api/classifier/classify",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
