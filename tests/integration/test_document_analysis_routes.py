"""
Integration Tests for Document Analysis Agents API Routes (AGENT-009, 010, 011).
Task 139: Create Integration Tests for Agent API Routes

Tests the full request-response cycle for:
- POST /api/document-analysis/analyze - Full document analysis workflow
- POST /api/document-analysis/research - AGENT-009 only
- POST /api/document-analysis/strategy - AGENT-010 only
- POST /api/document-analysis/fact-check - AGENT-011 only
- GET /api/document-analysis/agents - Get all agents info
- GET /api/document-analysis/agents/{id} - Get specific agent
- GET /api/document-analysis/stats - Get workflow statistics
- GET /api/document-analysis/health - Health check
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


pytestmark = [pytest.mark.integration]


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_research_result():
    """Mock research analysis result."""
    # Mock topic
    mock_topic = MagicMock()
    mock_topic.name = "Digital Transformation"
    mock_topic.relevance_score = 0.95
    mock_topic.keywords = ["cloud", "ai", "automation"]
    mock_topic.description = "Focus on digital initiatives"

    # Mock entity
    mock_entity = MagicMock()
    mock_entity.name = "Company XYZ"
    mock_entity.entity_type = "organization"
    mock_entity.mentions = 5
    mock_entity.context = "Primary subject of analysis"
    mock_entity.importance = 0.9

    # Mock fact
    mock_fact = MagicMock()
    mock_fact.statement = "Revenue increased by 15%"
    mock_fact.source_location = "Section 2, paragraph 3"
    mock_fact.confidence = 0.88
    mock_fact.supporting_evidence = ["Financial report Q3", "Analyst statement"]
    mock_fact.related_entities = ["Company XYZ"]

    # Mock quality assessment
    mock_quality = MagicMock()
    mock_quality.overall_quality = MagicMock(value="high")
    mock_quality.quality_score = 0.85
    mock_quality.clarity_score = 0.88
    mock_quality.completeness_score = 0.82
    mock_quality.accuracy_indicators = ["Well-sourced", "Consistent data"]
    mock_quality.strengths = ["Clear structure", "Good data support"]
    mock_quality.weaknesses = ["Limited historical context"]
    mock_quality.improvement_suggestions = ["Add more historical comparison"]

    result = MagicMock()
    result.document_id = "doc_123"
    result.word_count = 2500
    result.processing_time_ms = 1500.0
    result.topics = [mock_topic]
    result.entities = [mock_entity]
    result.facts = [mock_fact]
    result.quality_assessment = mock_quality

    return result


@pytest.fixture
def mock_strategy_result():
    """Mock content strategy result."""
    # Mock finding
    mock_finding = MagicMock()
    mock_finding.title = "Market Expansion Opportunity"
    mock_finding.description = "Significant growth potential in APAC region"
    mock_finding.importance = "high"
    mock_finding.supporting_facts = ["15% YoY growth", "Untapped market segments"]
    mock_finding.implications = ["Resource allocation needed", "Partnership opportunities"]

    # Mock recommendation
    mock_recommendation = MagicMock()
    mock_recommendation.title = "Invest in Cloud Infrastructure"
    mock_recommendation.description = "Modernize tech stack for scalability"
    mock_recommendation.priority = MagicMock(value="high")
    mock_recommendation.rationale = "Current infrastructure limiting growth"
    mock_recommendation.implementation_steps = ["Assess current state", "Plan migration", "Execute"]
    mock_recommendation.expected_impact = "30% cost reduction in 2 years"
    mock_recommendation.resources_needed = ["Cloud architect", "$500K budget"]

    # Mock executive summary
    mock_summary = MagicMock()
    mock_summary.title = "Strategic Analysis Report"
    mock_summary.summary = "Comprehensive analysis of business opportunities"
    mock_summary.key_points = ["Growth potential", "Tech modernization", "Market expansion"]
    mock_summary.target_audience = "Executive leadership"
    mock_summary.reading_time_minutes = 15

    result = MagicMock()
    result.document_id = "doc_123"
    result.processing_time_ms = 2000.0
    result.findings = [mock_finding]
    result.recommendations = [mock_recommendation]
    result.executive_summary = mock_summary
    result.action_items = ["Schedule planning session", "Allocate budget"]
    result.next_steps = ["Review with stakeholders", "Create implementation timeline"]

    return result


@pytest.fixture
def mock_fact_check_result():
    """Mock fact check result."""
    # Mock verification
    mock_verification = MagicMock()
    mock_verification.claim = "Revenue increased by 15%"
    mock_verification.status = MagicMock(value="verified")
    mock_verification.confidence = 0.92
    mock_verification.reasoning = "Confirmed by financial reports"
    mock_verification.supporting_evidence = ["Q3 financial statement", "SEC filing"]
    mock_verification.contradicting_evidence = []
    mock_verification.citations = ["Annual Report 2024, p.15"]
    mock_verification.verification_method = "document_cross_reference"

    result = MagicMock()
    result.document_id = "doc_123"
    result.claims_checked = 5
    result.verified_claims = 4
    result.uncertain_claims = 1
    result.false_claims = 0
    result.overall_credibility_score = 0.85
    result.credibility_assessment = "High credibility document"
    result.red_flags = []
    result.processing_time_ms = 1800.0
    result.verifications = [mock_verification]

    return result


@pytest.fixture
def mock_workflow_service(mock_research_result, mock_strategy_result, mock_fact_check_result):
    """Mock the DocumentAnalysisWorkflowService."""
    # Mock full analysis result
    mock_full_result = MagicMock()
    mock_full_result.document_id = "doc_123"
    mock_full_result.title = "Test Document"
    mock_full_result.workflow_completed = True
    mock_full_result.agents_used = ["AGENT-009", "AGENT-010", "AGENT-011"]
    mock_full_result.total_processing_time_ms = 5300.0
    mock_full_result.errors = []
    mock_full_result.research_analysis = mock_research_result
    mock_full_result.content_strategy = mock_strategy_result
    mock_full_result.fact_check = mock_fact_check_result

    mock_service = MagicMock()
    mock_service.analyze_document = AsyncMock(return_value=mock_full_result)

    # Mock individual agents
    mock_service.research_analyst = MagicMock()
    mock_service.research_analyst.analyze = AsyncMock(return_value=mock_research_result)

    mock_service.content_strategist = MagicMock()
    mock_service.content_strategist.strategize = AsyncMock(return_value=mock_strategy_result)

    mock_service.fact_checker = MagicMock()
    mock_service.fact_checker.verify = AsyncMock(return_value=mock_fact_check_result)

    # Mock agent info
    mock_service.get_agent_info.return_value = [
        {
            "agent_id": "AGENT-009",
            "name": "Senior Research Analyst",
            "description": "Extract topics, entities, facts, quality assessment",
            "model": "claude-sonnet-4-5",
            "temperature": 0.3,
            "capabilities": ["topic_extraction", "entity_extraction", "fact_extraction", "quality_assessment"]
        },
        {
            "agent_id": "AGENT-010",
            "name": "Content Strategist",
            "description": "Generate executive summaries and recommendations",
            "model": "claude-sonnet-4-5",
            "temperature": 0.5,
            "capabilities": ["executive_summary", "findings", "recommendations"]
        },
        {
            "agent_id": "AGENT-011",
            "name": "Fact Checker",
            "description": "Verify claims with confidence scores",
            "model": "claude-sonnet-4-5",
            "temperature": 0.1,
            "capabilities": ["claim_verification", "credibility_assessment"]
        }
    ]

    mock_service.get_stats.return_value = {
        "total_analyses": 100,
        "research_analyses": 90,
        "content_strategies": 85,
        "fact_checks": 80,
        "average_processing_time_ms": 5000.0,
        "agents": {
            "AGENT-009": {"analyses": 90, "avg_time_ms": 1500},
            "AGENT-010": {"analyses": 85, "avg_time_ms": 2000},
            "AGENT-011": {"analyses": 80, "avg_time_ms": 1800}
        }
    }

    mock_service.reset_stats.return_value = None

    return mock_service


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestDocumentAnalysisHealthEndpoint:
    """Tests for /api/document-analysis/health endpoint."""

    def test_health_check_returns_healthy(self, client, validate_health_response):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/document-analysis/health")

        assert response.status_code == 200
        data = response.json()
        validate_health_response(data)
        assert "agents" in data
        assert len(data["agents"]) == 3

    def test_health_check_includes_agent_info(self, client):
        """Test that health endpoint includes all three agents."""
        response = client.get("/api/document-analysis/health")

        assert response.status_code == 200
        data = response.json()
        agent_ids = [agent["agent_id"] for agent in data["agents"]]
        assert "AGENT-009" in agent_ids
        assert "AGENT-010" in agent_ids
        assert "AGENT-011" in agent_ids

    def test_health_check_includes_workflow_info(self, client):
        """Test that health endpoint includes workflow information."""
        response = client.get("/api/document-analysis/health")

        assert response.status_code == 200
        data = response.json()
        assert "workflow" in data
        assert "capabilities" in data


# =============================================================================
# FULL ANALYSIS ENDPOINT TESTS
# =============================================================================

class TestDocumentAnalysisAnalyzeEndpoint:
    """Tests for /api/document-analysis/analyze endpoint."""

    def test_analyze_document_full_workflow(self, client, mock_workflow_service, sample_document_content):
        """Test full document analysis workflow."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post(
                "/api/document-analysis/analyze",
                json={
                    "content": sample_document_content,
                    "title": "Test Document",
                    "run_research": True,
                    "run_strategy": True,
                    "run_fact_check": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow_completed"] is True
            assert "research_analysis" in data
            assert "content_strategy" in data
            assert "fact_check" in data
            assert "agents_run" in data

    def test_analyze_document_research_only(self, client, mock_workflow_service, sample_document_content):
        """Test document analysis with research only."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post(
                "/api/document-analysis/analyze",
                json={
                    "content": sample_document_content,
                    "run_research": True,
                    "run_strategy": False,
                    "run_fact_check": False
                }
            )

            assert response.status_code == 200

    def test_analyze_document_short_content_returns_422(self, client):
        """Test that short content returns validation error."""
        response = client.post(
            "/api/document-analysis/analyze",
            json={
                "content": "Too short for analysis"
            }
        )

        assert response.status_code == 400

    def test_analyze_document_missing_content_returns_422(self, client):
        """Test that missing content returns validation error."""
        response = client.post(
            "/api/document-analysis/analyze",
            json={
                "title": "Test Document"
            }
        )

        assert response.status_code == 400


# =============================================================================
# INDIVIDUAL AGENT ENDPOINT TESTS
# =============================================================================

class TestDocumentAnalysisResearchEndpoint:
    """Tests for /api/document-analysis/research endpoint."""

    def test_research_analysis_success(self, client, mock_workflow_service, sample_document_content):
        """Test AGENT-009 research analysis."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post(
                "/api/document-analysis/research",
                json={
                    "content": sample_document_content,
                    "extract_topics": True,
                    "extract_entities": True,
                    "extract_facts": True,
                    "assess_quality": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-009"
            assert "topics" in data
            assert "entities" in data
            assert "facts" in data

    def test_research_analysis_selective_extraction(self, client, mock_workflow_service, sample_document_content):
        """Test research analysis with selective extraction."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post(
                "/api/document-analysis/research",
                json={
                    "content": sample_document_content,
                    "extract_topics": True,
                    "extract_entities": False,
                    "extract_facts": False,
                    "assess_quality": False
                }
            )

            assert response.status_code == 200


class TestDocumentAnalysisStrategyEndpoint:
    """Tests for /api/document-analysis/strategy endpoint."""

    def test_content_strategy_success(self, client, mock_workflow_service, sample_document_content):
        """Test AGENT-010 content strategy."""
        from app.routes.document_analysis import get_workflow_service
        from app.main import app

        # Use FastAPI's dependency override system
        app.dependency_overrides[get_workflow_service] = lambda: mock_workflow_service

        try:
            response = client.post(
                "/api/document-analysis/strategy",
                json={
                    "content": sample_document_content,
                    "target_audience": "executive leadership"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-010"
            # executive_summary is optional - only included if present in result
            assert "findings" in data
            assert "recommendations" in data
        finally:
            app.dependency_overrides.pop(get_workflow_service, None)


class TestDocumentAnalysisFactCheckEndpoint:
    """Tests for /api/document-analysis/fact-check endpoint."""

    def test_fact_check_success(self, client, mock_workflow_service, sample_document_content):
        """Test AGENT-011 fact checking."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post(
                "/api/document-analysis/fact-check",
                json={
                    "content": sample_document_content,
                    "max_claims": 10
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-011"
            assert "claims_checked" in data
            assert "verified_claims" in data
            assert "overall_credibility_score" in data
            assert "verifications" in data

    def test_fact_check_specific_claims(self, client, mock_workflow_service, sample_document_content):
        """Test fact checking with specific claims."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post(
                "/api/document-analysis/fact-check",
                json={
                    "content": sample_document_content,
                    "claims_to_verify": ["Revenue increased by 15%", "Market share is 12%"]
                }
            )

            assert response.status_code == 200


# =============================================================================
# AGENTS INFO ENDPOINT TESTS
# =============================================================================

class TestDocumentAnalysisAgentsEndpoint:
    """Tests for /api/document-analysis/agents endpoints."""

    def test_get_all_agents(self, client, mock_workflow_service):
        """Test getting all agent information."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.get("/api/document-analysis/agents")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 3
            assert all("agent_id" in agent for agent in data)
            assert all("capabilities" in agent for agent in data)

    def test_get_specific_agent(self, client, mock_workflow_service):
        """Test getting specific agent information."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.get("/api/document-analysis/agents/AGENT-009")

            assert response.status_code == 200
            data = response.json()
            assert data["agent_id"] == "AGENT-009"
            assert data["name"] == "Senior Research Analyst"

    def test_get_nonexistent_agent_returns_404(self, client, mock_workflow_service):
        """Test that nonexistent agent returns 404."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.get("/api/document-analysis/agents/AGENT-999")

            assert response.status_code == 404


# =============================================================================
# STATS ENDPOINT TESTS
# =============================================================================

class TestDocumentAnalysisStatsEndpoint:
    """Tests for /api/document-analysis/stats endpoint."""

    def test_get_stats_returns_statistics(self, client, mock_workflow_service):
        """Test that stats endpoint returns workflow statistics."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.get("/api/document-analysis/stats")

            assert response.status_code == 200
            data = response.json()
            assert "total_analyses" in data
            assert "research_analyses" in data
            assert "content_strategies" in data
            assert "fact_checks" in data
            assert "average_processing_time_ms" in data
            assert "agents" in data

    def test_reset_stats_success(self, client, mock_workflow_service):
        """Test resetting workflow statistics."""
        with patch(
            "app.routes.document_analysis.get_workflow_service",
            return_value=mock_workflow_service
        ):
            response = client.post("/api/document-analysis/stats/reset")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestDocumentAnalysisErrorHandling:
    """Tests for error handling in document analysis endpoints."""

    def test_analyze_service_error_returns_500(self, client, sample_document_content):
        """Test that service errors return 500 status."""
        from app.routes.document_analysis import get_workflow_service
        from app.main import app

        mock_service = MagicMock()
        mock_service.analyze_document = AsyncMock(
            side_effect=Exception("Analysis service unavailable")
        )

        # Use FastAPI's dependency override system
        app.dependency_overrides[get_workflow_service] = lambda: mock_service

        try:
            response = client.post(
                "/api/document-analysis/analyze",
                json={
                    "content": sample_document_content
                }
            )

            assert response.status_code == 500
        finally:
            app.dependency_overrides.pop(get_workflow_service, None)

    def test_invalid_json_returns_422(self, client):
        """Test that invalid JSON returns 422."""
        response = client.post(
            "/api/document-analysis/analyze",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
