"""
Integration Tests for Asset Generator API Routes (AGENT-003 to AGENT-007).
Task 139: Create Integration Tests for Agent API Routes

Tests the full request-response cycle for:
- POST /api/assets/skill - Generate Claude Code skill (AGENT-003)
- POST /api/assets/command - Generate slash command (AGENT-004)
- POST /api/assets/agent - Generate CrewAI agent (AGENT-005)
- POST /api/assets/prompt - Generate prompt template (AGENT-006)
- POST /api/assets/workflow - Generate n8n workflow (AGENT-007)
- POST /api/assets/generate/{asset_type} - Generic generation
- POST /api/assets/batch - Batch generation
- GET /api/assets/generators - List all generators
- GET /api/assets/types - Get asset types and departments
- GET /api/assets/departments - Get departments list
- GET /api/assets/stats - Get generator statistics
- GET /api/assets/health - Health check
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_generator_service():
    """Mock the AssetGeneratorService."""
    mock_service = MagicMock()

    # Mock generation result
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.asset_type = "skill"
    mock_result.asset_name = "test-skill"
    mock_result.file_path = "/processed/crewai-suggestions/skill/drafts/it-engineering/test-skill.yaml"
    mock_result.content = "name: test-skill\ndescription: Test skill\n"
    mock_result.department = "it-engineering"
    mock_result.error = None
    mock_result.processing_time_seconds = 2.5
    mock_result.metadata = {"version": "1.0"}

    mock_service.generate_skill = AsyncMock(return_value=mock_result)
    mock_service.generate_command = AsyncMock(return_value=mock_result)
    mock_service.generate_agent = AsyncMock(return_value=mock_result)
    mock_service.generate_prompt = AsyncMock(return_value=mock_result)
    mock_service.generate_workflow = AsyncMock(return_value=mock_result)
    mock_service.generate = AsyncMock(return_value=mock_result)

    # Mock list generators
    mock_service.list_generators.return_value = [
        {
            "agent_id": "AGENT-003",
            "agent_name": "Skill Generator",
            "asset_type": "skill",
            "file_extension": ".yaml"
        },
        {
            "agent_id": "AGENT-004",
            "agent_name": "Command Generator",
            "asset_type": "command",
            "file_extension": ".md"
        },
        {
            "agent_id": "AGENT-005",
            "agent_name": "Agent Generator",
            "asset_type": "agent",
            "file_extension": ".yaml"
        },
        {
            "agent_id": "AGENT-006",
            "agent_name": "Prompt Generator",
            "asset_type": "prompt",
            "file_extension": ".yaml"
        },
        {
            "agent_id": "AGENT-007",
            "agent_name": "Workflow Generator",
            "asset_type": "workflow",
            "file_extension": ".json"
        }
    ]

    # Mock get generator
    mock_generator = MagicMock()
    mock_generator.get_stats.return_value = {
        "agent_id": "AGENT-003",
        "agent_name": "Skill Generator",
        "asset_type": "skill",
        "assets_generated": 25,
        "by_department": {"it-engineering": 15, "sales-marketing": 10}
    }
    mock_service.get_generator.return_value = mock_generator

    # Mock get all stats
    mock_service.get_all_stats.return_value = {
        "AGENT-003": {
            "agent_id": "AGENT-003",
            "agent_name": "Skill Generator",
            "asset_type": "skill",
            "assets_generated": 25,
            "by_department": {"it-engineering": 15, "sales-marketing": 10}
        },
        "AGENT-004": {
            "agent_id": "AGENT-004",
            "agent_name": "Command Generator",
            "asset_type": "command",
            "assets_generated": 30,
            "by_department": {"it-engineering": 20, "operations-hr-supply": 10}
        },
        "AGENT-005": {
            "agent_id": "AGENT-005",
            "agent_name": "Agent Generator",
            "asset_type": "agent",
            "assets_generated": 15,
            "by_department": {"it-engineering": 10, "customer-support": 5}
        },
        "AGENT-006": {
            "agent_id": "AGENT-006",
            "agent_name": "Prompt Generator",
            "asset_type": "prompt",
            "assets_generated": 40,
            "by_department": {"sales-marketing": 25, "consulting": 15}
        },
        "AGENT-007": {
            "agent_id": "AGENT-007",
            "agent_name": "Workflow Generator",
            "asset_type": "workflow",
            "assets_generated": 20,
            "by_department": {"it-engineering": 12, "project-management": 8}
        }
    }

    mock_service.output_base_path = "processed/crewai-suggestions"

    return mock_service


@pytest.fixture
def sample_asset_request():
    """Sample asset generation request."""
    return {
        "name": "test-asset",
        "description": "A test asset for integration testing purposes",
        "department": "it-engineering",
        "context": "Used for automated testing",
        "metadata": {"version": "1.0", "author": "test"}
    }


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestAssetGeneratorsHealthEndpoint:
    """Tests for /api/assets/health endpoint."""

    def test_health_check_returns_healthy(self, client, mock_generator_service, validate_health_response):
        """Test that health endpoint returns healthy status."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/health")

            assert response.status_code == 200
            data = response.json()
            validate_health_response(data)
            assert data["service_name"] == "Asset Generator Service"

    def test_health_check_includes_all_generators(self, client, mock_generator_service):
        """Test that health endpoint includes all five generators."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/health")

            assert response.status_code == 200
            data = response.json()
            assert "generators" in data
            assert len(data["generators"]) == 5

            generator_ids = list(data["generators"].keys())
            assert "AGENT-003" in generator_ids
            assert "AGENT-004" in generator_ids
            assert "AGENT-005" in generator_ids
            assert "AGENT-006" in generator_ids
            assert "AGENT-007" in generator_ids

    def test_health_check_includes_capabilities(self, client, mock_generator_service):
        """Test that health endpoint includes capabilities."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/health")

            assert response.status_code == 200
            data = response.json()
            assert "capabilities" in data
            assert data["capabilities"]["skill_generation"] is True
            assert data["capabilities"]["batch_generation"] is True


# =============================================================================
# SKILL GENERATOR TESTS (AGENT-003)
# =============================================================================

class TestSkillGeneratorEndpoint:
    """Tests for /api/assets/skill endpoint (AGENT-003)."""

    def test_generate_skill_success(self, client, mock_generator_service, sample_asset_request):
        """Test successful skill generation."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/skill",
                json=sample_asset_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "file_path" in data
            assert "content" in data

    def test_generate_skill_missing_name_returns_422(self, client):
        """Test that missing name returns validation error."""
        response = client.post(
            "/api/assets/skill",
            json={
                "description": "Valid description here",
                "department": "it-engineering"
            }
        )

        assert response.status_code == 422

    def test_generate_skill_short_description_returns_422(self, client):
        """Test that short description returns validation error."""
        response = client.post(
            "/api/assets/skill",
            json={
                "name": "test-skill",
                "description": "Short",  # Less than min_length=10
                "department": "it-engineering"
            }
        )

        assert response.status_code == 422


# =============================================================================
# COMMAND GENERATOR TESTS (AGENT-004)
# =============================================================================

class TestCommandGeneratorEndpoint:
    """Tests for /api/assets/command endpoint (AGENT-004)."""

    def test_generate_command_success(self, client, mock_generator_service, sample_asset_request):
        """Test successful command generation."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/command",
                json=sample_asset_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# =============================================================================
# AGENT GENERATOR TESTS (AGENT-005)
# =============================================================================

class TestAgentGeneratorEndpoint:
    """Tests for /api/assets/agent endpoint (AGENT-005)."""

    def test_generate_agent_success(self, client, mock_generator_service, sample_asset_request):
        """Test successful agent generation."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/agent",
                json=sample_asset_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# =============================================================================
# PROMPT GENERATOR TESTS (AGENT-006)
# =============================================================================

class TestPromptGeneratorEndpoint:
    """Tests for /api/assets/prompt endpoint (AGENT-006)."""

    def test_generate_prompt_success(self, client, mock_generator_service, sample_asset_request):
        """Test successful prompt generation."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/prompt",
                json=sample_asset_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# =============================================================================
# WORKFLOW GENERATOR TESTS (AGENT-007)
# =============================================================================

class TestWorkflowGeneratorEndpoint:
    """Tests for /api/assets/workflow endpoint (AGENT-007)."""

    def test_generate_workflow_success(self, client, mock_generator_service, sample_asset_request):
        """Test successful workflow generation."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/workflow",
                json=sample_asset_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# =============================================================================
# GENERIC GENERATION TESTS
# =============================================================================

class TestGenericGenerateEndpoint:
    """Tests for /api/assets/generate/{asset_type} endpoint."""

    def test_generate_by_type_success(self, client, mock_generator_service, sample_asset_request):
        """Test successful generation by asset type."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/generate/skill",
                json=sample_asset_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_generate_invalid_type_returns_400(self, client, mock_generator_service, sample_asset_request):
        """Test that invalid asset type returns 400."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/generate/invalid_type",
                json=sample_asset_request
            )

            assert response.status_code == 400


# =============================================================================
# BATCH GENERATION TESTS
# =============================================================================

class TestBatchGenerateEndpoint:
    """Tests for /api/assets/batch endpoint."""

    def test_batch_generate_success(self, client, mock_generator_service):
        """Test successful batch generation."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/batch",
                json={
                    "asset_type": "skill",
                    "assets": [
                        {
                            "name": "skill-1",
                            "description": "First test skill for batch generation",
                            "department": "it-engineering"
                        },
                        {
                            "name": "skill-2",
                            "description": "Second test skill for batch generation",
                            "department": "sales-marketing"
                        }
                    ]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert data["total_requested"] == 2

    def test_batch_generate_empty_returns_422(self, client):
        """Test that empty batch returns validation error."""
        response = client.post(
            "/api/assets/batch",
            json={
                "asset_type": "skill",
                "assets": []
            }
        )

        assert response.status_code == 422

    def test_batch_generate_invalid_type_returns_400(self, client, mock_generator_service):
        """Test that invalid asset type in batch returns 400."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.post(
                "/api/assets/batch",
                json={
                    "asset_type": "invalid_type",
                    "assets": [
                        {
                            "name": "test",
                            "description": "Test description here",
                            "department": "it-engineering"
                        }
                    ]
                }
            )

            assert response.status_code == 400


# =============================================================================
# METADATA ENDPOINTS TESTS
# =============================================================================

class TestAssetMetadataEndpoints:
    """Tests for metadata endpoints."""

    def test_list_generators(self, client, mock_generator_service):
        """Test listing all generators."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/generators")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 5

    def test_get_asset_types(self, client):
        """Test getting asset types."""
        response = client.get("/api/assets/types")

        assert response.status_code == 200
        data = response.json()
        assert "asset_types" in data
        assert "departments" in data
        assert "file_extensions" in data
        assert "skill" in data["asset_types"]
        assert "command" in data["asset_types"]

    def test_get_departments(self, client):
        """Test getting departments list."""
        response = client.get("/api/assets/departments")

        assert response.status_code == 200
        data = response.json()
        assert "departments" in data
        assert len(data["departments"]) == 10


# =============================================================================
# STATS ENDPOINT TESTS
# =============================================================================

class TestAssetStatsEndpoints:
    """Tests for statistics endpoints."""

    def test_get_generator_stats(self, client, mock_generator_service):
        """Test getting stats for a specific generator."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/stats/skill")

            assert response.status_code == 200
            data = response.json()
            assert "agent_id" in data
            assert "assets_generated" in data
            assert "by_department" in data

    def test_get_generator_stats_invalid_type_returns_400(self, client, mock_generator_service):
        """Test that invalid asset type returns 400."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/stats/invalid_type")

            assert response.status_code == 400

    def test_get_all_stats(self, client, mock_generator_service):
        """Test getting stats for all generators."""
        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_generator_service
        ):
            response = client.get("/api/assets/stats")

            assert response.status_code == 200
            data = response.json()
            assert "generators" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestAssetGeneratorErrorHandling:
    """Tests for error handling in asset generator endpoints."""

    def test_generate_service_error_returns_500(self, client, sample_asset_request):
        """Test that service errors return 500 status."""
        mock_service = MagicMock()
        mock_service.generate_skill = AsyncMock(
            side_effect=Exception("Generator service unavailable")
        )

        with patch(
            "app.routes.asset_generators.get_generator_service",
            return_value=mock_service
        ):
            response = client.post(
                "/api/assets/skill",
                json=sample_asset_request
            )

            assert response.status_code == 500

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/api/assets/skill",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
