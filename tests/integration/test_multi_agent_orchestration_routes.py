"""
Integration Tests for Multi-Agent Orchestration API Routes (AGENT-012 to AGENT-015).
Task 139: Create Integration Tests for Agent API Routes

Tests the full request-response cycle for:
- POST /api/orchestration/workflow - Full workflow execution
- POST /api/orchestration/research - Research agent only (AGENT-012)
- POST /api/orchestration/analyze - Analysis agent only (AGENT-013)
- POST /api/orchestration/write - Writing agent only (AGENT-014)
- POST /api/orchestration/review - Review agent only (AGENT-015)
- GET /api/orchestration/agents - List all agents
- GET /api/orchestration/agents/{agent_id} - Get specific agent
- GET /api/orchestration/stats - Get workflow statistics
- GET /api/orchestration/health - Health check
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_orchestration_service():
    """Mock the MultiAgentOrchestrationService."""
    mock_service = MagicMock()

    # Mock research result
    mock_research_result = MagicMock()
    mock_research_result.task_id = "task-123"
    mock_research_result.original_query = "Test query"
    mock_research_result.processing_time_ms = 1500.0
    mock_research_result.summary = "Research summary"
    mock_research_result.queries_executed = []
    mock_research_result.sources = []
    mock_research_result.findings = []
    mock_research_result.gaps_identified = []
    mock_research_result.recommended_followup = []

    # Mock analysis result
    mock_analysis_result = MagicMock()
    mock_analysis_result.task_id = "task-123"
    mock_analysis_result.processing_time_ms = 1200.0
    mock_analysis_result.data_quality_score = 0.85
    mock_analysis_result.patterns = []
    mock_analysis_result.statistics = []
    mock_analysis_result.correlations = []
    mock_analysis_result.key_insights = ["Insight 1", "Insight 2"]
    mock_analysis_result.limitations = []
    mock_analysis_result.visualization_specs = []

    # Mock writing result
    mock_writing_result = MagicMock()
    mock_writing_result.task_id = "task-123"
    mock_writing_result.format = MagicMock(value="markdown")
    mock_writing_result.processing_time_ms = 2000.0
    mock_writing_result.style_guide_compliance = 0.95
    mock_writing_result.terminology_consistency = 0.90
    mock_writing_result.raw_content = "# Generated Report\n\nContent here..."
    mock_writing_result.report = None

    # Mock review result
    mock_review_result = MagicMock()
    mock_review_result.task_id = "task-123"
    mock_review_result.processing_time_ms = 800.0
    mock_review_result.status = MagicMock(value="approved")
    mock_review_result.approved_for_publication = True
    mock_review_result.overall_quality_score = 0.88
    mock_review_result.grammar_score = 0.92
    mock_review_result.clarity_score = 0.85
    mock_review_result.completeness_score = 0.87
    mock_review_result.issues = []
    mock_review_result.fact_checks = []
    mock_review_result.consistency_checks = []
    mock_review_result.strengths = ["Well-structured", "Clear language"]
    mock_review_result.improvement_summary = "Minor improvements suggested"

    # Mock orchestration result
    mock_orch_result = MagicMock()
    mock_orch_result.workflow_id = "workflow-123"
    mock_orch_result.workflow_completed = True
    mock_orch_result.agents_used = ["AGENT-012", "AGENT-013", "AGENT-014", "AGENT-015"]
    mock_orch_result.revision_count = 1
    mock_orch_result.total_processing_time_ms = 5500.0
    mock_orch_result.errors = []
    mock_orch_result.final_output = "Final report content"
    mock_orch_result.task = MagicMock(
        task_id="task-123",
        title="Test Task",
        description="Test description"
    )
    mock_orch_result.research_result = mock_research_result
    mock_orch_result.analysis_result = mock_analysis_result
    mock_orch_result.writing_result = mock_writing_result
    mock_orch_result.review_result = mock_review_result

    mock_service.execute_workflow = AsyncMock(return_value=mock_orch_result)

    # Mock research agent
    mock_research_agent = MagicMock()
    mock_research_agent.research = AsyncMock(return_value=mock_research_result)
    mock_service.research_agent = mock_research_agent

    # Mock analysis agent
    mock_analysis_agent = MagicMock()
    mock_analysis_agent.analyze = AsyncMock(return_value=mock_analysis_result)
    mock_service.analysis_agent = mock_analysis_agent

    # Mock writing agent
    mock_writing_agent = MagicMock()
    mock_writing_agent.write = AsyncMock(return_value=mock_writing_result)
    mock_service.writing_agent = mock_writing_agent

    # Mock review agent
    mock_review_agent = MagicMock()
    mock_review_agent.review = AsyncMock(return_value=mock_review_result)
    mock_service.review_agent = mock_review_agent

    # Mock agent info
    mock_service.get_agent_info.return_value = [
        {
            "agent_id": "AGENT-012",
            "name": "Research Agent",
            "description": "Web/academic search and information gathering",
            "model": "claude-sonnet-4-5-20250514",
            "temperature": 0.7,
            "capabilities": ["web_search", "academic_search", "source_credibility"]
        },
        {
            "agent_id": "AGENT-013",
            "name": "Analysis Agent",
            "description": "Pattern detection and statistical analysis",
            "model": "claude-sonnet-4-5-20250514",
            "temperature": 0.5,
            "capabilities": ["pattern_detection", "statistics", "correlations"]
        },
        {
            "agent_id": "AGENT-014",
            "name": "Writing Agent",
            "description": "Report generation and documentation",
            "model": "claude-sonnet-4-5-20250514",
            "temperature": 0.8,
            "capabilities": ["report_generation", "formatting", "citations"]
        },
        {
            "agent_id": "AGENT-015",
            "name": "Review Agent",
            "description": "Quality assurance and consistency checking",
            "model": "claude-sonnet-4-5-20250514",
            "temperature": 0.3,
            "capabilities": ["quality_check", "fact_verification", "grammar_check"]
        }
    ]

    # Mock stats
    mock_service.get_stats.return_value = {
        "total_workflows": 50,
        "total_revisions": 75,
        "research_invocations": 100,
        "analysis_invocations": 95,
        "writing_invocations": 90,
        "review_invocations": 88,
        "average_processing_time_ms": 5500.0,
        "agents": {}
    }

    mock_service.reset_stats.return_value = None

    return mock_service


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestOrchestrationHealthEndpoint:
    """Tests for /api/orchestration/health endpoint."""

    def test_health_check_returns_healthy(self, client, validate_health_response):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/orchestration/health")

        assert response.status_code == 200
        data = response.json()
        validate_health_response(data)
        assert "agents" in data
        assert len(data["agents"]) == 4

    def test_health_check_lists_all_agents(self, client):
        """Test that health endpoint lists all four agents."""
        response = client.get("/api/orchestration/health")

        assert response.status_code == 200
        data = response.json()

        agent_ids = [agent["agent_id"] for agent in data["agents"]]
        assert "AGENT-012" in agent_ids
        assert "AGENT-013" in agent_ids
        assert "AGENT-014" in agent_ids
        assert "AGENT-015" in agent_ids

    def test_health_check_includes_workflow_info(self, client):
        """Test that health endpoint includes workflow information."""
        response = client.get("/api/orchestration/health")

        assert response.status_code == 200
        data = response.json()
        assert "workflow" in data
        assert "capabilities" in data


# =============================================================================
# WORKFLOW ENDPOINT TESTS
# =============================================================================

class TestOrchestrationWorkflowEndpoint:
    """Tests for /api/orchestration/workflow endpoint."""

    def test_full_workflow_success(self, client, mock_orchestration_service):
        """Test successful full workflow execution."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/workflow",
                json={
                    "title": "Research Task",
                    "description": "Analyze market trends in AI industry",
                    "context": "Focus on 2024 developments",
                    "constraints": ["Use verified sources only"],
                    "expected_output": "Comprehensive report",
                    "run_research": True,
                    "run_analysis": True,
                    "run_writing": True,
                    "run_review": True,
                    "max_revisions": 2,
                    "output_format": "markdown",
                    "target_audience": "business executives"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow_completed"] is True
            assert "workflow_id" in data
            assert len(data["agents_used"]) == 4
            assert "final_output" in data

    def test_workflow_with_selected_agents(self, client, mock_orchestration_service):
        """Test workflow with only selected agents enabled."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/workflow",
                json={
                    "title": "Quick Analysis",
                    "description": "Brief analysis of the data",
                    "run_research": False,
                    "run_analysis": True,
                    "run_writing": True,
                    "run_review": False
                }
            )

            assert response.status_code == 200

    def test_workflow_missing_title_returns_422(self, client):
        """Test that missing title returns validation error."""
        response = client.post(
            "/api/orchestration/workflow",
            json={
                "description": "Some description"
            }
        )

        assert response.status_code == 422

    def test_workflow_short_title_returns_422(self, client):
        """Test that short title returns validation error."""
        response = client.post(
            "/api/orchestration/workflow",
            json={
                "title": "AB",  # Less than min_length=3
                "description": "Valid description here"
            }
        )

        assert response.status_code == 422

    def test_workflow_short_description_returns_422(self, client):
        """Test that short description returns validation error."""
        response = client.post(
            "/api/orchestration/workflow",
            json={
                "title": "Valid Title",
                "description": "Short"  # Less than min_length=10
            }
        )

        assert response.status_code == 422


# =============================================================================
# RESEARCH ENDPOINT TESTS
# =============================================================================

class TestOrchestrationResearchEndpoint:
    """Tests for /api/orchestration/research endpoint (AGENT-012)."""

    def test_research_success(self, client, mock_orchestration_service):
        """Test successful research request."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/research",
                json={
                    "query": "Latest developments in quantum computing",
                    "context": "Focus on practical applications",
                    "search_types": ["web", "academic"],
                    "max_sources": 15
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-012"
            assert data["agent_name"] == "Research Agent"
            assert "summary" in data
            assert "sources" in data
            assert "findings" in data

    def test_research_with_defaults(self, client, mock_orchestration_service):
        """Test research with default parameters."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/research",
                json={
                    "query": "Artificial intelligence trends"
                }
            )

            assert response.status_code == 200

    def test_research_short_query_returns_422(self, client):
        """Test that short query returns validation error."""
        response = client.post(
            "/api/orchestration/research",
            json={
                "query": "AI"  # Less than min_length=5
            }
        )

        assert response.status_code == 422


# =============================================================================
# ANALYSIS ENDPOINT TESTS
# =============================================================================

class TestOrchestrationAnalysisEndpoint:
    """Tests for /api/orchestration/analyze endpoint (AGENT-013)."""

    def test_analysis_success(self, client, mock_orchestration_service):
        """Test successful analysis request."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/analyze",
                json={
                    "data": "Sales data for Q1 2024: January $1.2M, February $1.5M, March $1.8M",
                    "analysis_focus": "trend analysis",
                    "detect_patterns": True,
                    "compute_statistics": True,
                    "find_correlations": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-013"
            assert data["agent_name"] == "Analysis Agent"
            assert "data_quality_score" in data
            assert "patterns" in data
            assert "statistics" in data
            assert "key_insights" in data

    def test_analysis_short_data_returns_422(self, client):
        """Test that short data returns validation error."""
        response = client.post(
            "/api/orchestration/analyze",
            json={
                "data": "Short data"  # Less than min_length=20
            }
        )

        assert response.status_code == 422


# =============================================================================
# WRITING ENDPOINT TESTS
# =============================================================================

class TestOrchestrationWritingEndpoint:
    """Tests for /api/orchestration/write endpoint (AGENT-014)."""

    def test_writing_success(self, client, mock_orchestration_service):
        """Test successful writing request."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/write",
                json={
                    "title": "Quarterly Report",
                    "description": "Comprehensive overview of Q1 2024 performance",
                    "context": "Include financial metrics and growth projections",
                    "constraints": ["Professional tone", "Include charts recommendations"],
                    "output_format": "markdown",
                    "target_audience": "C-level executives",
                    "max_length": 2000
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-014"
            assert data["agent_name"] == "Writing Agent"
            assert "raw_content" in data
            assert "style_guide_compliance" in data

    def test_writing_missing_title_returns_422(self, client):
        """Test that missing title returns validation error."""
        response = client.post(
            "/api/orchestration/write",
            json={
                "description": "Valid description here"
            }
        )

        assert response.status_code == 422


# =============================================================================
# REVIEW ENDPOINT TESTS
# =============================================================================

class TestOrchestrationReviewEndpoint:
    """Tests for /api/orchestration/review endpoint (AGENT-015)."""

    def test_review_success(self, client, mock_orchestration_service):
        """Test successful review request."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post(
                "/api/orchestration/review",
                json={
                    "content": "This is the document content that needs to be reviewed. It contains multiple paragraphs and should be checked for quality.",
                    "title": "Review Document",
                    "check_facts": True,
                    "check_consistency": True,
                    "check_grammar": True,
                    "strict_mode": False
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-015"
            assert data["agent_name"] == "Review Agent"
            assert "approved_for_publication" in data
            assert "overall_quality_score" in data
            assert "issues" in data
            assert "strengths" in data

    def test_review_short_content_returns_422(self, client):
        """Test that short content returns validation error."""
        response = client.post(
            "/api/orchestration/review",
            json={
                "content": "Too short"  # Less than min_length=50
            }
        )

        assert response.status_code == 422


# =============================================================================
# AGENTS ENDPOINT TESTS
# =============================================================================

class TestOrchestrationAgentsEndpoint:
    """Tests for /api/orchestration/agents endpoints."""

    def test_list_agents_returns_all_four(self, client, mock_orchestration_service):
        """Test that agents endpoint lists all four agents."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.get("/api/orchestration/agents")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 4

            agent_ids = [agent["agent_id"] for agent in data]
            assert "AGENT-012" in agent_ids
            assert "AGENT-013" in agent_ids
            assert "AGENT-014" in agent_ids
            assert "AGENT-015" in agent_ids

    def test_get_specific_agent(self, client, mock_orchestration_service):
        """Test getting a specific agent by ID."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.get("/api/orchestration/agents/AGENT-012")

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-012"
            assert data["name"] == "Research Agent"
            assert "capabilities" in data

    def test_get_nonexistent_agent_returns_404(self, client, mock_orchestration_service):
        """Test that nonexistent agent returns 404."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.get("/api/orchestration/agents/AGENT-999")

            assert response.status_code == 404


# =============================================================================
# STATS ENDPOINT TESTS
# =============================================================================

class TestOrchestrationStatsEndpoint:
    """Tests for /api/orchestration/stats endpoints."""

    def test_get_stats_returns_statistics(self, client, mock_orchestration_service):
        """Test that stats endpoint returns workflow statistics."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.get("/api/orchestration/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_workflows" in data
            assert "total_revisions" in data
            assert "research_invocations" in data
            assert "analysis_invocations" in data
            assert "writing_invocations" in data
            assert "review_invocations" in data
            assert "average_processing_time_ms" in data

    def test_reset_stats_success(self, client, mock_orchestration_service):
        """Test resetting workflow statistics."""
        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_orchestration_service
        ):
            response = client.post("/api/orchestration/stats/reset")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestOrchestrationErrorHandling:
    """Tests for error handling in orchestration endpoints."""

    def test_workflow_service_error_returns_500(self, client):
        """Test that service errors return 500 status."""
        mock_service = MagicMock()
        mock_service.execute_workflow = AsyncMock(
            side_effect=Exception("Orchestration service unavailable")
        )

        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_service
        ):
            response = client.post(
                "/api/orchestration/workflow",
                json={
                    "title": "Test Workflow",
                    "description": "This is a test workflow"
                }
            )

            assert response.status_code == 500

    def test_research_service_error_returns_500(self, client):
        """Test that research errors return 500 status."""
        mock_service = MagicMock()
        mock_research_agent = MagicMock()
        mock_research_agent.research = AsyncMock(
            side_effect=Exception("Research service unavailable")
        )
        mock_service.research_agent = mock_research_agent

        with patch(
            "app.routes.multi_agent_orchestration.get_orchestration_service",
            return_value=mock_service
        ):
            response = client.post(
                "/api/orchestration/research",
                json={
                    "query": "Test research query"
                }
            )

            assert response.status_code == 500

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/api/orchestration/workflow",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
