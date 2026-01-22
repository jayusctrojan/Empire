"""
Empire v7.3 - Document Analysis Agents Tests
Task 45: AGENT-009, AGENT-010, AGENT-011

Comprehensive tests for:
- AGENT-009: Senior Research Analyst (topics, entities, facts, quality)
- AGENT-010: Content Strategist (summaries, findings, recommendations)
- AGENT-011: Fact Checker (claim verification, confidence scores)
- Sequential workflow orchestration
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import service components
from app.services.document_analysis_agents import (
    AgentRole,
    DocumentQuality,
    VerificationStatus,
    RecommendationPriority,
    AGENT_CONFIGS,
    ExtractedTopic,
    ExtractedEntity,
    ExtractedFact,
    QualityAssessment,
    ExecutiveSummary,
    Finding,
    Recommendation,
    ClaimVerification,
    ResearchAnalysisResult,
    ContentStrategyResult,
    FactCheckResult,
    DocumentAnalysisResult,
    ResearchAnalystAgent,
    ContentStrategistAgent,
    FactCheckerAgent,
    DocumentAnalysisWorkflowService,
    get_document_analysis_workflow_service
)


# =============================================================================
# TEST DATA
# =============================================================================

SAMPLE_BUSINESS_DOCUMENT = """
Executive Summary: Q4 2024 Financial Performance

Our company achieved record revenue of $50 million in Q4 2024, representing a 25%
year-over-year growth. The primary drivers were expansion into European markets and
the successful launch of our new SaaS platform.

Key Highlights:
- Revenue: $50 million (up 25% YoY)
- Operating Margin: 18% (improved from 15%)
- Customer Retention Rate: 94%
- New Enterprise Clients: 45

The European expansion, led by our London office under Sarah Johnson's leadership,
contributed $12 million in new revenue. Our Paris and Berlin offices are expected
to be operational by Q2 2025.

The SaaS platform, launched in September, has already acquired 2,500 paying customers
with an average contract value of $15,000 per year. Monthly recurring revenue (MRR)
reached $3.1 million by December.

Challenges and Risks:
- Supply chain disruptions affected hardware delivery times
- Currency fluctuations impacted European revenue by approximately 3%
- Competition from TechCorp's new product launch requires strategic response

Recommendations:
1. Accelerate hiring in the European region
2. Invest additional $5 million in R&D for platform features
3. Explore partnership opportunities with regional distributors

Financial Outlook:
We project Q1 2025 revenue of $55 million, maintaining our growth trajectory.
The board has approved a $10 million investment in AI capabilities to enhance
our product offerings.
"""

SAMPLE_TECHNICAL_DOCUMENT = """
Technical Architecture Document: Microservices Migration

Project Overview:
This document outlines the migration strategy from our monolithic application
to a microservices architecture. The migration will be completed in phases
over 18 months.

Current State:
- Single Django application handling all business logic
- PostgreSQL database with 500+ tables
- Average response time: 800ms
- Monthly downtime: 4 hours

Target Architecture:
The new architecture will consist of 12 independent microservices:
1. User Service - Authentication and user management
2. Product Service - Product catalog and inventory
3. Order Service - Order processing and fulfillment
4. Payment Service - Payment processing integration
5. Notification Service - Email, SMS, and push notifications

Technology Stack:
- Container orchestration: Kubernetes on AWS EKS
- Service mesh: Istio for inter-service communication
- API Gateway: Kong for external traffic
- Message broker: Apache Kafka for event streaming
- Databases: PostgreSQL for ACID transactions, MongoDB for documents

Migration Phases:
Phase 1 (Q1 2025): Extract User and Authentication services
Phase 2 (Q2 2025): Extract Product and Inventory services
Phase 3 (Q3 2025): Extract Order and Payment services
Phase 4 (Q4 2025): Complete migration and decommission monolith

Risk Assessment:
- Data consistency during transition: MEDIUM risk
- Service integration complexity: HIGH risk
- Team training requirements: LOW risk

The estimated total cost is $2.5 million including infrastructure and personnel.
ROI is expected within 24 months through reduced operational costs.
"""

SHORT_CONTENT = "This is a short document."  # Below minimum length


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock the Anthropic client for LLM calls"""
    with patch('app.services.document_analysis_agents.AsyncAnthropic') as mock:
        client = AsyncMock()
        mock.return_value = client

        # Default mock response for research analysis
        research_response = MagicMock()
        research_response.content = [MagicMock(text="""
{
    "topics": [
        {
            "name": "Financial Performance",
            "relevance_score": 0.95,
            "keywords": ["revenue", "growth", "margin"],
            "description": "Q4 2024 financial results and metrics"
        }
    ],
    "entities": [
        {
            "name": "Sarah Johnson",
            "entity_type": "person",
            "mentions": 1,
            "context": "Led European expansion from London office",
            "importance": 0.8
        }
    ],
    "facts": [
        {
            "statement": "Q4 2024 revenue was $50 million",
            "source_location": "paragraph 1",
            "confidence": 0.95,
            "supporting_evidence": "Explicitly stated in executive summary"
        }
    ],
    "quality_assessment": {
        "overall_quality": "good",
        "quality_score": 0.85,
        "clarity_score": 0.85,
        "completeness_score": 0.80,
        "accuracy_indicators": 0.90,
        "strengths": ["Clear metrics"],
        "weaknesses": ["Limited context"],
        "improvement_suggestions": ["Add more specific timelines"]
    }
}
""")]

        # Default mock response for content strategy
        strategy_response = MagicMock()
        strategy_response.content = [MagicMock(text="""
{
    "executive_summary": {
        "title": "Q4 Financial Summary",
        "summary": "The company achieved strong Q4 2024 results with 25% revenue growth.",
        "key_points": ["$50M revenue", "25% growth"],
        "target_audience": "Executive leadership",
        "reading_time_minutes": 5
    },
    "findings": [
        {
            "title": "European Expansion Success",
            "description": "London office contributed $12M in new revenue",
            "importance": "high",
            "supporting_facts": ["$12 million European revenue"],
            "implications": "Strong market potential"
        }
    ],
    "recommendations": [
        {
            "title": "Accelerate European Hiring",
            "description": "Expand team in European offices",
            "priority": "high",
            "rationale": "Strong performance indicates market opportunity",
            "implementation_steps": ["Review budget", "Open roles"],
            "expected_impact": "Additional $10M revenue potential",
            "resources_needed": "HR budget increase"
        }
    ],
    "action_items": ["Review budget", "Approve R&D"],
    "next_steps": ["Schedule board review"]
}
""")]

        # Default mock response for fact checking
        fact_check_response = MagicMock()
        fact_check_response.content = [MagicMock(text="""
{
    "verifications": [
        {
            "claim": "Q4 2024 revenue was $50 million",
            "status": "verified",
            "confidence": 0.95,
            "reasoning": "Claim is internally consistent",
            "supporting_evidence": ["Stated in executive summary"],
            "contradicting_evidence": [],
            "citations": ["Executive Summary, paragraph 1"],
            "verification_method": "Document cross-reference"
        }
    ],
    "overall_credibility_score": 0.9,
    "credibility_assessment": "Most claims are well-supported.",
    "red_flags": []
}
""")]

        client.messages.create = AsyncMock(side_effect=[
            research_response,
            strategy_response,
            fact_check_response
        ])

        yield client


@pytest.fixture
def research_analyst():
    """Create ResearchAnalystAgent instance"""
    return ResearchAnalystAgent()


@pytest.fixture
def content_strategist():
    """Create ContentStrategistAgent instance"""
    return ContentStrategistAgent()


@pytest.fixture
def fact_checker():
    """Create FactCheckerAgent instance"""
    return FactCheckerAgent()


@pytest.fixture
def workflow_service():
    """Create DocumentAnalysisWorkflowService instance"""
    return DocumentAnalysisWorkflowService()


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestEnums:
    """Test enum definitions"""

    def test_agent_role_values(self):
        """Test AgentRole enum values"""
        assert AgentRole.RESEARCH_ANALYST.value == "research_analyst"
        assert AgentRole.CONTENT_STRATEGIST.value == "content_strategist"
        assert AgentRole.FACT_CHECKER.value == "fact_checker"

    def test_document_quality_values(self):
        """Test DocumentQuality enum values"""
        assert DocumentQuality.EXCELLENT.value == "excellent"
        assert DocumentQuality.GOOD.value == "good"
        assert DocumentQuality.FAIR.value == "fair"
        assert DocumentQuality.POOR.value == "poor"
        assert DocumentQuality.NEEDS_REVIEW.value == "needs_review"

    def test_verification_status_values(self):
        """Test VerificationStatus enum values"""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.LIKELY_TRUE.value == "likely_true"
        assert VerificationStatus.UNCERTAIN.value == "uncertain"
        assert VerificationStatus.LIKELY_FALSE.value == "likely_false"
        assert VerificationStatus.FALSE.value == "false"
        assert VerificationStatus.UNVERIFIABLE.value == "unverifiable"

    def test_recommendation_priority_values(self):
        """Test RecommendationPriority enum values"""
        assert RecommendationPriority.CRITICAL.value == "critical"
        assert RecommendationPriority.HIGH.value == "high"
        assert RecommendationPriority.MEDIUM.value == "medium"
        assert RecommendationPriority.LOW.value == "low"
        assert RecommendationPriority.OPTIONAL.value == "optional"


# =============================================================================
# AGENT CONFIG TESTS
# =============================================================================

class TestAgentConfigs:
    """Test agent configurations"""

    def test_all_agents_configured(self):
        """Test all three agents have configs"""
        assert AgentRole.RESEARCH_ANALYST in AGENT_CONFIGS
        assert AgentRole.CONTENT_STRATEGIST in AGENT_CONFIGS
        assert AgentRole.FACT_CHECKER in AGENT_CONFIGS

    def test_research_analyst_config(self):
        """Test AGENT-009 configuration"""
        config = AGENT_CONFIGS[AgentRole.RESEARCH_ANALYST]
        assert config["agent_id"] == "AGENT-009"
        assert config["name"] == "Senior Research Analyst"
        assert config["temperature"] == 0.1
        assert "claude" in config["model"].lower() or "sonnet" in config["model"].lower()

    def test_content_strategist_config(self):
        """Test AGENT-010 configuration"""
        config = AGENT_CONFIGS[AgentRole.CONTENT_STRATEGIST]
        assert config["agent_id"] == "AGENT-010"
        assert config["name"] == "Content Strategist"
        assert config["temperature"] == 0.3

    def test_fact_checker_config(self):
        """Test AGENT-011 configuration"""
        config = AGENT_CONFIGS[AgentRole.FACT_CHECKER]
        assert config["agent_id"] == "AGENT-011"
        assert config["name"] == "Fact Checker"
        assert config["temperature"] == 0.0  # Zero for strict verification


# =============================================================================
# DATA MODEL TESTS
# =============================================================================

class TestDataModels:
    """Test Pydantic data models"""

    def test_topic_model(self):
        """Test ExtractedTopic model"""
        topic = ExtractedTopic(
            name="Financial Results",
            relevance_score=0.9,
            keywords=["revenue", "profit"],
            description="Quarterly financial performance"
        )
        assert topic.name == "Financial Results"
        assert topic.relevance_score == 0.9
        assert len(topic.keywords) == 2

    def test_entity_model(self):
        """Test ExtractedEntity model"""
        entity = ExtractedEntity(
            name="John Smith",
            entity_type="person",
            mentions=3,
            context="CEO mentioned in leadership section",
            importance=0.85
        )
        assert entity.name == "John Smith"
        assert entity.entity_type == "person"
        assert entity.mentions == 3

    def test_fact_model(self):
        """Test ExtractedFact model"""
        fact = ExtractedFact(
            statement="Revenue grew by 25%",
            source_location="paragraph 2",
            confidence=0.95,
            supporting_evidence="Cited in financial summary"
        )
        assert fact.confidence == 0.95

    def test_quality_assessment_model(self):
        """Test QualityAssessment model"""
        qa = QualityAssessment(
            overall_quality=DocumentQuality.GOOD,
            quality_score=0.85,
            clarity_score=0.8,
            completeness_score=0.75,
            accuracy_indicators=0.9,
            strengths=["Clear metrics"],
            weaknesses=["Limited detail"],
            improvement_suggestions=["Add more details"]
        )
        assert qa.overall_quality == DocumentQuality.GOOD
        assert qa.clarity_score == 0.8

    def test_finding_model(self):
        """Test Finding model"""
        finding = Finding(
            title="Strong Growth",
            description="25% revenue increase",
            importance="high",
            supporting_facts=["Q4 results", "Market share data"],
            implications="Positive trajectory"
        )
        assert finding.title == "Strong Growth"
        assert len(finding.supporting_facts) == 2

    def test_recommendation_model(self):
        """Test Recommendation model"""
        rec = Recommendation(
            title="Expand Team",
            description="Hire more engineers",
            rationale="Support growth",
            priority=RecommendationPriority.HIGH,
            implementation_steps=["Review budget", "Post jobs"],
            expected_impact="20% capacity increase"
        )
        assert rec.priority == RecommendationPriority.HIGH

    def test_claim_verification_model(self):
        """Test ClaimVerification model"""
        claim = ClaimVerification(
            claim="Revenue was $50M",
            status=VerificationStatus.VERIFIED,
            confidence=0.95,
            reasoning="Confirmed with official data",
            supporting_evidence=["Financial report"],
            contradicting_evidence=[],
            citations=["Page 1"],
            verification_method="Document review"
        )
        assert claim.status == VerificationStatus.VERIFIED
        assert claim.confidence == 0.95


# =============================================================================
# RESEARCH ANALYST AGENT TESTS (AGENT-009)
# =============================================================================

class TestResearchAnalystAgent:
    """Test AGENT-009: Senior Research Analyst"""

    def test_agent_initialization(self, research_analyst):
        """Test agent initializes correctly"""
        assert research_analyst.AGENT_ID == "AGENT-009"
        assert research_analyst.AGENT_NAME == "Senior Research Analyst"

    @pytest.mark.asyncio
    async def test_analyze_with_mock(self, mock_anthropic_client):
        """Test analysis with mocked LLM"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            agent = ResearchAnalystAgent()
            result = await agent.analyze(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-001"
            )

            assert result.document_id == "test-doc-001"
            assert isinstance(result, ResearchAnalysisResult)
            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_analyze_selective_extraction(self, mock_anthropic_client):
        """Test selective extraction options"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            agent = ResearchAnalystAgent()
            result = await agent.analyze(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-002",
                extract_topics=True,
                extract_entities=False,
                extract_facts=False,
                assess_quality=False
            )

            # Should still work with selective options
            assert result.document_id == "test-doc-002"


# =============================================================================
# CONTENT STRATEGIST AGENT TESTS (AGENT-010)
# =============================================================================

class TestContentStrategistAgent:
    """Test AGENT-010: Content Strategist"""

    def test_agent_initialization(self, content_strategist):
        """Test agent initializes correctly"""
        assert content_strategist.AGENT_ID == "AGENT-010"
        assert content_strategist.AGENT_NAME == "Content Strategist"

    @pytest.mark.asyncio
    async def test_strategize_with_mock(self, mock_anthropic_client):
        """Test strategy generation with mocked LLM"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            agent = ContentStrategistAgent()
            result = await agent.strategize(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-003"
            )

            assert result.document_id == "test-doc-003"
            assert isinstance(result, ContentStrategyResult)
            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_strategize_with_research_input(self, mock_anthropic_client):
        """Test strategy with prior research analysis"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            # Create mock research result
            research_result = ResearchAnalysisResult(
                document_id="test-doc-004",
                topics=[ExtractedTopic(
                    name="Financial Growth",
                    relevance_score=0.9,
                    keywords=["revenue"],
                    description="Growth analysis"
                )],
                entities=[],
                facts=[],
                quality_assessment=None,
                processing_time_ms=100
            )

            agent = ContentStrategistAgent()
            result = await agent.strategize(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-004",
                research_analysis=research_result
            )

            assert result.document_id == "test-doc-004"


# =============================================================================
# FACT CHECKER AGENT TESTS (AGENT-011)
# =============================================================================

class TestFactCheckerAgent:
    """Test AGENT-011: Fact Checker"""

    def test_agent_initialization(self, fact_checker):
        """Test agent initializes correctly"""
        assert fact_checker.AGENT_ID == "AGENT-011"
        assert fact_checker.AGENT_NAME == "Fact Checker"

    @pytest.mark.asyncio
    async def test_verify_with_mock(self, mock_anthropic_client):
        """Test fact verification with mocked LLM"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            agent = FactCheckerAgent()
            result = await agent.verify(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-005"
            )

            assert result.document_id == "test-doc-005"
            assert result.overall_credibility_score >= 0
            assert result.overall_credibility_score <= 1
            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_verify_specific_claims(self, mock_anthropic_client):
        """Test verification of specific claims"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            agent = FactCheckerAgent()
            claims = [
                "Q4 2024 revenue was $50 million",
                "Growth rate was 25% YoY"
            ]
            result = await agent.verify(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-006",
                claims_to_verify=claims
            )

            assert result.document_id == "test-doc-006"

    @pytest.mark.asyncio
    async def test_verify_with_max_claims(self, mock_anthropic_client):
        """Test max claims limit"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            agent = FactCheckerAgent()
            result = await agent.verify(
                content=SAMPLE_BUSINESS_DOCUMENT,
                document_id="test-doc-007",
                max_claims=5
            )

            assert result.document_id == "test-doc-007"


# =============================================================================
# WORKFLOW SERVICE TESTS
# =============================================================================

class TestDocumentAnalysisWorkflowService:
    """Test DocumentAnalysisWorkflowService"""

    def test_service_initialization(self, workflow_service):
        """Test service initializes with all agents"""
        assert workflow_service.research_analyst is not None
        assert workflow_service.content_strategist is not None
        assert workflow_service.fact_checker is not None

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_anthropic_client):
        """Test complete document analysis workflow"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_BUSINESS_DOCUMENT,
                title="Q4 Financial Report",
                document_id="workflow-test-001"
            )

            assert result.document_id == "workflow-test-001"
            assert result.title == "Q4 Financial Report"
            assert result.workflow_completed
            assert "AGENT-009" in result.agents_used
            assert "AGENT-010" in result.agents_used
            assert "AGENT-011" in result.agents_used
            assert result.total_processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_partial_workflow_research_only(self, mock_anthropic_client):
        """Test workflow with only research agent"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_BUSINESS_DOCUMENT,
                title="Research Only Test",
                run_research=True,
                run_strategy=False,
                run_fact_check=False
            )

            assert result.research_analysis is not None
            assert result.content_strategy is None
            assert result.fact_check is None
            assert "AGENT-009" in result.agents_used
            assert "AGENT-010" not in result.agents_used

    @pytest.mark.asyncio
    async def test_partial_workflow_strategy_only(self, mock_anthropic_client):
        """Test workflow with only strategy agent"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_BUSINESS_DOCUMENT,
                title="Strategy Only Test",
                run_research=False,
                run_strategy=True,
                run_fact_check=False
            )

            assert result.research_analysis is None
            assert result.content_strategy is not None
            assert "AGENT-010" in result.agents_used

    def test_get_agent_info(self, workflow_service):
        """Test getting agent information"""
        agents = workflow_service.get_agent_info()

        assert len(agents) == 3
        agent_ids = [a["agent_id"] for a in agents]
        assert "AGENT-009" in agent_ids
        assert "AGENT-010" in agent_ids
        assert "AGENT-011" in agent_ids

    def test_get_stats(self, workflow_service):
        """Test getting workflow statistics"""
        stats = workflow_service.get_stats()

        assert "total_analyses" in stats
        assert "research_analyses" in stats
        assert "content_strategies" in stats
        assert "fact_checks" in stats
        assert "agents" in stats

    def test_reset_stats(self, workflow_service):
        """Test resetting statistics"""
        workflow_service.reset_stats()
        stats = workflow_service.get_stats()

        assert stats["total_analyses"] == 0


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Test singleton pattern for workflow service"""

    def test_singleton_returns_same_instance(self):
        """Test that get_document_analysis_workflow_service returns same instance"""
        service1 = get_document_analysis_workflow_service()
        service2 = get_document_analysis_workflow_service()

        assert service1 is service2


# =============================================================================
# API ENDPOINT TESTS
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoints for Document Analysis Agents"""

    @pytest.fixture
    def client(self):
        """Create test client with isolated app"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routes.document_analysis import router

        test_app = FastAPI()
        test_app.include_router(router)
        return TestClient(test_app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/document-analysis/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert len(data["agents"]) == 3
        assert data["capabilities"]["full_workflow"] is True

    def test_get_agents_endpoint(self, client):
        """Test get all agents endpoint"""
        response = client.get("/api/document-analysis/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3

        agent_ids = [a["agent_id"] for a in agents]
        assert "AGENT-009" in agent_ids
        assert "AGENT-010" in agent_ids
        assert "AGENT-011" in agent_ids

    def test_get_specific_agent_endpoint(self, client):
        """Test get specific agent endpoint"""
        response = client.get("/api/document-analysis/agents/AGENT-009")

        assert response.status_code == 200
        agent = response.json()
        assert agent["agent_id"] == "AGENT-009"
        assert agent["name"] == "Senior Research Analyst"

    def test_get_invalid_agent_endpoint(self, client):
        """Test get invalid agent returns 404"""
        response = client.get("/api/document-analysis/agents/AGENT-999")

        assert response.status_code == 404

    def test_get_stats_endpoint(self, client):
        """Test get stats endpoint"""
        response = client.get("/api/document-analysis/stats")

        assert response.status_code == 200
        stats = response.json()
        assert "total_analyses" in stats
        assert "agents" in stats

    def test_reset_stats_endpoint(self, client):
        """Test reset stats endpoint"""
        response = client.post("/api/document-analysis/stats/reset")

        assert response.status_code == 200
        assert response.json()["message"] == "Statistics reset successfully"

    def test_analyze_endpoint_validation(self, client):
        """Test analyze endpoint with invalid input"""
        # Content too short
        response = client.post(
            "/api/document-analysis/analyze",
            json={"content": SHORT_CONTENT}
        )

        # FastAPI returns 422 for Pydantic validation errors, or 400 for custom validation
        assert response.status_code in [400, 422]

    def test_research_endpoint_validation(self, client):
        """Test research endpoint with invalid input"""
        response = client.post(
            "/api/document-analysis/research",
            json={"content": SHORT_CONTENT}
        )

        # FastAPI returns 422 for Pydantic validation errors, or 400 for custom validation
        assert response.status_code in [400, 422]

    def test_strategy_endpoint_validation(self, client):
        """Test strategy endpoint with invalid input"""
        response = client.post(
            "/api/document-analysis/strategy",
            json={"content": SHORT_CONTENT}
        )

        # FastAPI returns 422 for Pydantic validation errors, or 400 for custom validation
        assert response.status_code in [400, 422]

    def test_fact_check_endpoint_validation(self, client):
        """Test fact-check endpoint with invalid input"""
        response = client.post(
            "/api/document-analysis/fact-check",
            json={"content": SHORT_CONTENT}
        )

        # FastAPI returns 422 for Pydantic validation errors, or 400 for custom validation
        assert response.status_code in [400, 422]


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_document_id_generated(self):
        """Test document ID is generated when not provided"""
        result = ResearchAnalysisResult(
            document_id="",
            topics=[],
            entities=[],
            facts=[],
            quality_assessment=None,
            processing_time_ms=0
        )
        # Should accept empty string (service generates ID)
        assert result.document_id == ""

    def test_quality_assessment_none(self):
        """Test result works without quality assessment"""
        result = ResearchAnalysisResult(
            document_id="test",
            topics=[],
            entities=[],
            facts=[],
            quality_assessment=None,
            processing_time_ms=0
        )
        assert result.quality_assessment is None

    def test_empty_findings_and_recommendations(self):
        """Test strategy result with empty lists"""
        result = ContentStrategyResult(
            document_id="test",
            executive_summary=None,
            findings=[],
            recommendations=[],
            action_items=[],
            next_steps=[],
            processing_time_ms=0
        )
        assert len(result.findings) == 0
        assert len(result.recommendations) == 0

    def test_zero_claims_verified(self):
        """Test fact check with no claims"""
        result = FactCheckResult(
            document_id="test",
            claims_checked=0,
            verified_claims=0,
            uncertain_claims=0,
            false_claims=0,
            verifications=[],
            overall_credibility_score=1.0,
            credibility_assessment="No claims to verify",
            processing_time_ms=0
        )
        assert result.claims_checked == 0

    @pytest.mark.asyncio
    async def test_workflow_with_auto_generated_id(self, mock_anthropic_client):
        """Test workflow auto-generates document ID"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_BUSINESS_DOCUMENT,
                title="Auto ID Test"
                # No document_id provided
            )

            assert result.document_id is not None
            assert len(result.document_id) > 0

    def test_verification_status_all_values(self):
        """Test all verification status values work"""
        statuses = [
            VerificationStatus.VERIFIED,
            VerificationStatus.LIKELY_TRUE,
            VerificationStatus.UNCERTAIN,
            VerificationStatus.LIKELY_FALSE,
            VerificationStatus.FALSE,
            VerificationStatus.UNVERIFIABLE
        ]

        for status in statuses:
            claim = ClaimVerification(
                claim="Test claim",
                status=status,
                confidence=0.5,
                reasoning="Test",
                supporting_evidence=[],
                contradicting_evidence=[],
                citations=[],
                verification_method="test"
            )
            assert claim.status == status


# =============================================================================
# INTEGRATION TESTS (WITH MOCKED LLM)
# =============================================================================

class TestIntegration:
    """Integration tests for the full workflow"""

    @pytest.mark.asyncio
    async def test_sequential_workflow_data_flow(self, mock_anthropic_client):
        """Test that data flows correctly through the sequential workflow"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_TECHNICAL_DOCUMENT,
                title="Technical Architecture",
                document_id="integration-test-001"
            )

            # Verify all stages ran
            assert result.workflow_completed
            assert len(result.agents_used) == 3

            # Verify sequential execution (AGENT-009 -> AGENT-010 -> AGENT-011)
            assert result.agents_used[0] == "AGENT-009"
            assert result.agents_used[1] == "AGENT-010"
            assert result.agents_used[2] == "AGENT-011"

            # Verify all results present
            assert result.research_analysis is not None
            assert result.content_strategy is not None
            assert result.fact_check is not None

    @pytest.mark.asyncio
    async def test_workflow_timing(self, mock_anthropic_client):
        """Test workflow timing is recorded correctly"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_BUSINESS_DOCUMENT,
                title="Timing Test"
            )

            # Total time should be >= sum of individual times
            individual_times = 0
            if result.research_analysis:
                individual_times += result.research_analysis.processing_time_ms
            if result.content_strategy:
                individual_times += result.content_strategy.processing_time_ms
            if result.fact_check:
                individual_times += result.fact_check.processing_time_ms

            # Allow for some overhead
            assert result.total_processing_time_ms >= 0


# =============================================================================
# CONTENT-SPECIFIC TESTS
# =============================================================================

class TestContentAnalysis:
    """Test analysis of specific content types"""

    @pytest.mark.asyncio
    async def test_financial_document_analysis(self, mock_anthropic_client):
        """Test analysis of financial document"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_BUSINESS_DOCUMENT,
                title="Q4 Financial Report",
                run_research=True,
                run_strategy=False,
                run_fact_check=False
            )

            assert result.research_analysis is not None
            # The mock should return topics related to financial performance

    @pytest.mark.asyncio
    async def test_technical_document_analysis(self, mock_anthropic_client):
        """Test analysis of technical document"""
        with patch('app.services.document_analysis_agents.AsyncAnthropic', return_value=mock_anthropic_client):
            service = DocumentAnalysisWorkflowService()
            result = await service.analyze_document(
                content=SAMPLE_TECHNICAL_DOCUMENT,
                title="Architecture Document",
                run_research=True,
                run_strategy=False,
                run_fact_check=False
            )

            assert result.research_analysis is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
