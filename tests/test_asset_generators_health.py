"""
Empire v7.3 - Asset Generator Health Endpoint Tests
Task 134: Implement Health Endpoint for Asset Generators

Comprehensive tests for the Asset Generator health endpoint:
- Service health status
- Individual generator health
- LLM availability checks
- Capabilities and metrics
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient

from app.routes.asset_generators import (
    router,
    GeneratorHealthStatus,
    ServiceHealthResponse,
    get_generator_service,
)
from app.services.asset_generator_agents import (
    AssetGeneratorService,
    AssetType,
    Department,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_generator_service():
    """Create a mock AssetGeneratorService"""
    mock_service = Mock(spec=AssetGeneratorService)
    mock_service.output_base_path = "processed/crewai-suggestions"
    mock_service.list_generators.return_value = [
        {"agent_id": "AGENT-003", "agent_name": "Skill Generator", "asset_type": "skill", "file_extension": ".yaml"},
        {"agent_id": "AGENT-004", "agent_name": "Command Generator", "asset_type": "command", "file_extension": ".md"},
        {"agent_id": "AGENT-005", "agent_name": "Agent Generator", "asset_type": "agent", "file_extension": ".yaml"},
        {"agent_id": "AGENT-006", "agent_name": "Prompt Generator", "asset_type": "prompt", "file_extension": ".yaml"},
        {"agent_id": "AGENT-007", "agent_name": "Workflow Generator", "asset_type": "workflow", "file_extension": ".json"},
    ]
    mock_service.get_all_stats.return_value = {
        "AGENT-003": {"agent_id": "AGENT-003", "agent_name": "Skill Generator", "asset_type": "skill", "assets_generated": 10, "by_department": {}},
        "AGENT-004": {"agent_id": "AGENT-004", "agent_name": "Command Generator", "asset_type": "command", "assets_generated": 5, "by_department": {}},
        "AGENT-005": {"agent_id": "AGENT-005", "agent_name": "Agent Generator", "asset_type": "agent", "assets_generated": 3, "by_department": {}},
        "AGENT-006": {"agent_id": "AGENT-006", "agent_name": "Prompt Generator", "asset_type": "prompt", "assets_generated": 8, "by_department": {}},
        "AGENT-007": {"agent_id": "AGENT-007", "agent_name": "Workflow Generator", "asset_type": "workflow", "assets_generated": 2, "by_department": {}},
    }
    return mock_service


@pytest.fixture
def app_with_mock_service(mock_generator_service):
    """Create FastAPI app with mock service"""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    # Override the dependency
    app.dependency_overrides[get_generator_service] = lambda: mock_generator_service
    return app


@pytest.fixture
def client(app_with_mock_service):
    """Create test client"""
    return TestClient(app_with_mock_service)


# =============================================================================
# PYDANTIC MODEL TESTS
# =============================================================================

class TestGeneratorHealthStatus:
    """Test GeneratorHealthStatus Pydantic model"""

    def test_create_healthy_status(self):
        """Test creating a healthy generator status"""
        status = GeneratorHealthStatus(
            agent_id="AGENT-003",
            agent_name="Skill Generator",
            asset_type="skill",
            status="healthy",
            file_extension=".yaml",
            output_directory="processed/crewai-suggestions/skill/drafts/",
            capabilities=["Generate Claude Code skills", "Create tool definitions"]
        )

        assert status.agent_id == "AGENT-003"
        assert status.status == "healthy"
        assert status.error_message is None

    def test_create_degraded_status(self):
        """Test creating a degraded generator status"""
        status = GeneratorHealthStatus(
            agent_id="AGENT-004",
            agent_name="Command Generator",
            asset_type="command",
            status="degraded",
            file_extension=".md",
            output_directory="processed/crewai-suggestions/command/drafts/",
            capabilities=["Generate slash commands"],
            error_message="LLM API key not configured"
        )

        assert status.status == "degraded"
        assert status.error_message == "LLM API key not configured"

    def test_create_unhealthy_status(self):
        """Test creating an unhealthy generator status"""
        status = GeneratorHealthStatus(
            agent_id="AGENT-005",
            agent_name="Agent Generator",
            asset_type="agent",
            status="unhealthy",
            file_extension=".yaml",
            output_directory="processed/crewai-suggestions/agent/drafts/",
            capabilities=[],
            error_message="Service unavailable"
        )

        assert status.status == "unhealthy"


class TestServiceHealthResponse:
    """Test ServiceHealthResponse Pydantic model"""

    def test_create_service_health_response(self):
        """Test creating a complete service health response"""
        generator_health = GeneratorHealthStatus(
            agent_id="AGENT-003",
            agent_name="Skill Generator",
            asset_type="skill",
            status="healthy",
            file_extension=".yaml",
            output_directory="processed/crewai-suggestions/skill/drafts/",
            capabilities=["Generate Claude Code skills"]
        )

        response = ServiceHealthResponse(
            status="healthy",
            timestamp="2025-01-01T00:00:00Z",
            generators_count=5,
            generators={"AGENT-003": generator_health},
            llm_available=True,
            llm_model="claude-sonnet-4-5",
            output_base_path="processed/crewai-suggestions",
            supported_departments=["it-engineering", "sales-marketing"],
            supported_asset_types=["skill", "command"],
            capabilities={"skill_generation": True},
            metrics={"total_assets_generated": 28}
        )

        assert response.status == "healthy"
        assert response.generators_count == 5
        assert response.llm_available is True
        assert "AGENT-003" in response.generators


# =============================================================================
# HEALTH ENDPOINT TESTS
# =============================================================================

class TestHealthEndpoint:
    """Test the /health endpoint"""

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_healthy(self, client, mock_generator_service):
        """Test health endpoint returns healthy status when all is well"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service_name"] == "Asset Generator Service"
        assert data["version"] == "7.3.0"
        assert data["generators_count"] == 5
        assert data["llm_available"] is True
        assert data["llm_model"].startswith("claude-sonnet-4-5")

    @patch.dict('os.environ', {}, clear=True)
    def test_health_endpoint_degraded_no_llm(self, client, mock_generator_service):
        """Test health endpoint returns degraded when LLM not available"""
        # Clear ANTHROPIC_API_KEY
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["llm_available"] is False

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_includes_all_generators(self, client, mock_generator_service):
        """Test health endpoint includes all 5 generators"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        generators = data["generators"]
        assert "AGENT-003" in generators
        assert "AGENT-004" in generators
        assert "AGENT-005" in generators
        assert "AGENT-006" in generators
        assert "AGENT-007" in generators

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_generator_details(self, client, mock_generator_service):
        """Test generator details in health response"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        skill_generator = data["generators"]["AGENT-003"]
        assert skill_generator["agent_name"] == "Skill Generator"
        assert skill_generator["asset_type"] == "skill"
        assert skill_generator["file_extension"] == ".yaml"
        assert len(skill_generator["capabilities"]) > 0

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_capabilities(self, client, mock_generator_service):
        """Test capabilities in health response"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        capabilities = data["capabilities"]
        assert capabilities["skill_generation"] is True
        assert capabilities["command_generation"] is True
        assert capabilities["agent_generation"] is True
        assert capabilities["prompt_generation"] is True
        assert capabilities["workflow_generation"] is True
        assert capabilities["batch_generation"] is True
        assert capabilities["department_organization"] is True
        assert capabilities["file_persistence"] is True

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_metrics(self, client, mock_generator_service):
        """Test metrics in health response"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        metrics = data["metrics"]
        assert metrics["total_assets_generated"] == 28  # 10+5+3+8+2
        assert metrics["generators_active"] == 5
        assert metrics["generators_expected"] == 5

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_supported_departments(self, client, mock_generator_service):
        """Test supported departments in health response"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        departments = data["supported_departments"]
        assert "it-engineering" in departments
        assert "sales-marketing" in departments
        assert "customer-support" in departments
        assert "finance-accounting" in departments
        assert len(departments) == 10

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_supported_asset_types(self, client, mock_generator_service):
        """Test supported asset types in health response"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        asset_types = data["supported_asset_types"]
        assert "skill" in asset_types
        assert "command" in asset_types
        assert "agent" in asset_types
        assert "prompt" in asset_types
        assert "workflow" in asset_types
        assert len(asset_types) == 5

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_timestamp_format(self, client, mock_generator_service):
        """Test timestamp is in ISO format"""
        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        timestamp = data["timestamp"]
        assert timestamp.endswith("Z")
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestHealthEndpointEdgeCases:
    """Test edge cases for health endpoint"""

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_partial_generators(self, client, mock_generator_service):
        """Test health endpoint with partial generators available"""
        # Simulate only 3 generators available
        mock_generator_service.list_generators.return_value = [
            {"agent_id": "AGENT-003", "agent_name": "Skill Generator", "asset_type": "skill", "file_extension": ".yaml"},
            {"agent_id": "AGENT-004", "agent_name": "Command Generator", "asset_type": "command", "file_extension": ".md"},
            {"agent_id": "AGENT-005", "agent_name": "Agent Generator", "asset_type": "agent", "file_extension": ".yaml"},
        ]

        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        # Should be degraded because not all generators are available
        assert data["status"] == "degraded"
        assert data["generators_count"] == 3

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_health_endpoint_no_stats(self, client, mock_generator_service):
        """Test health endpoint when no generation stats exist"""
        mock_generator_service.get_all_stats.return_value = {}

        response = client.get("/api/assets/health")

        assert response.status_code == 200
        data = response.json()

        assert data["metrics"]["total_assets_generated"] == 0


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
