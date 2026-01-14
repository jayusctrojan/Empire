"""
Tests for Multi-Agent Orchestration Agents (Task 46)
AGENT-012: Research Agent
AGENT-013: Analysis Agent
AGENT-014: Writing Agent
AGENT-015: Review Agent

Tests cover:
- Individual agent functionality
- Workflow orchestration
- API endpoints
- Edge cases and error handling
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.multi_agent_orchestration import (
    # Enums
    OrchestrationAgentRole,
    ResearchSourceType,
    PatternType,
    ReportFormat,
    ReviewStatus,
    IssueType,
    IssueSeverity,
    ORCHESTRATION_AGENT_CONFIGS,
    # Models - Research
    ResearchSource,
    ResearchFinding,
    ResearchQuery,
    ResearchResult,
    # Models - Analysis
    DetectedPattern,
    StatisticalInsight,
    DataCorrelation,
    AnalysisResult,
    # Models - Writing
    ReportSection,
    Citation,
    GeneratedReport,
    WritingResult,
    # Models - Review
    ReviewIssue,
    FactCheckResult,
    ConsistencyCheck,
    ReviewResult,
    # Models - Workflow
    WorkflowTask,
    OrchestrationResult,
    # Agents
    ResearchAgent,
    AnalysisAgent,
    WritingAgent,
    ReviewAgent,
    # Service
    MultiAgentOrchestrationService,
    get_multi_agent_orchestration_service
)


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestEnums:
    """Test enum definitions"""

    def test_orchestration_agent_role_values(self):
        """Test OrchestrationAgentRole enum values"""
        assert OrchestrationAgentRole.RESEARCH == "research"
        assert OrchestrationAgentRole.ANALYSIS == "analysis"
        assert OrchestrationAgentRole.WRITING == "writing"
        assert OrchestrationAgentRole.REVIEW == "review"

    def test_research_source_type_values(self):
        """Test ResearchSourceType enum values"""
        assert ResearchSourceType.WEB == "web"
        assert ResearchSourceType.ACADEMIC == "academic"
        assert ResearchSourceType.NEWS == "news"
        assert ResearchSourceType.INTERNAL == "internal"
        assert ResearchSourceType.EXPERT == "expert"

    def test_pattern_type_values(self):
        """Test PatternType enum values"""
        assert PatternType.TREND == "trend"
        assert PatternType.ANOMALY == "anomaly"
        assert PatternType.CORRELATION == "correlation"
        assert PatternType.CLUSTER == "cluster"
        assert PatternType.OUTLIER == "outlier"

    def test_report_format_values(self):
        """Test ReportFormat enum values"""
        assert ReportFormat.MARKDOWN == "markdown"
        assert ReportFormat.HTML == "html"
        assert ReportFormat.TEXT == "text"
        assert ReportFormat.JSON == "json"

    def test_review_status_values(self):
        """Test ReviewStatus enum values"""
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.NEEDS_REVISION == "needs_revision"
        assert ReviewStatus.MAJOR_ISSUES == "major_issues"
        assert ReviewStatus.REJECTED == "rejected"

    def test_issue_type_values(self):
        """Test IssueType enum values"""
        assert IssueType.GRAMMAR == "grammar"
        assert IssueType.FACTUAL == "factual"
        assert IssueType.CONSISTENCY == "consistency"
        assert IssueType.CITATION == "citation"

    def test_issue_severity_values(self):
        """Test IssueSeverity enum values"""
        assert IssueSeverity.CRITICAL == "critical"
        assert IssueSeverity.MAJOR == "major"
        assert IssueSeverity.MINOR == "minor"
        assert IssueSeverity.SUGGESTION == "suggestion"


# =============================================================================
# AGENT CONFIG TESTS
# =============================================================================

class TestAgentConfigs:
    """Test agent configuration constants"""

    def test_research_agent_config(self):
        """Test Research Agent configuration"""
        config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.RESEARCH]
        assert config["agent_id"] == "AGENT-012"
        assert config["name"] == "Research Agent"
        assert "model" in config
        assert config["temperature"] == 0.2

    def test_analysis_agent_config(self):
        """Test Analysis Agent configuration"""
        config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.ANALYSIS]
        assert config["agent_id"] == "AGENT-013"
        assert config["name"] == "Analysis Agent"
        assert config["temperature"] == 0.1

    def test_writing_agent_config(self):
        """Test Writing Agent configuration"""
        config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.WRITING]
        assert config["agent_id"] == "AGENT-014"
        assert config["name"] == "Writing Agent"
        assert config["temperature"] == 0.4

    def test_review_agent_config(self):
        """Test Review Agent configuration"""
        config = ORCHESTRATION_AGENT_CONFIGS[OrchestrationAgentRole.REVIEW]
        assert config["agent_id"] == "AGENT-015"
        assert config["name"] == "Review Agent"
        assert config["temperature"] == 0.0


# =============================================================================
# DATA MODEL TESTS
# =============================================================================

class TestDataModels:
    """Test Pydantic data models"""

    def test_research_source_model(self):
        """Test ResearchSource model"""
        source = ResearchSource(
            title="Test Source",
            url="https://example.com",
            source_type=ResearchSourceType.WEB,
            credibility_score=0.85,
            summary="Test summary"
        )
        assert source.title == "Test Source"
        assert source.credibility_score == 0.85
        assert source.source_type == ResearchSourceType.WEB

    def test_research_finding_model(self):
        """Test ResearchFinding model"""
        finding = ResearchFinding(
            finding="Important discovery",
            relevance_score=0.9,
            sources=["Source 1"],
            confidence=0.85
        )
        assert finding.finding == "Important discovery"
        assert finding.relevance_score == 0.9

    def test_detected_pattern_model(self):
        """Test DetectedPattern model"""
        pattern = DetectedPattern(
            pattern_type=PatternType.TREND,
            name="Increasing trend",
            description="Values increasing over time",
            confidence=0.8
        )
        assert pattern.pattern_type == PatternType.TREND
        assert pattern.name == "Increasing trend"

    def test_statistical_insight_model(self):
        """Test StatisticalInsight model"""
        insight = StatisticalInsight(
            metric_name="Average",
            value="42.5",
            interpretation="Above baseline"
        )
        assert insight.metric_name == "Average"
        assert insight.value == "42.5"

    def test_report_section_model(self):
        """Test ReportSection model"""
        section = ReportSection(
            title="Introduction",
            content="This is the introduction.",
            section_type="introduction",
            order=1
        )
        assert section.title == "Introduction"
        assert section.order == 1

    def test_review_issue_model(self):
        """Test ReviewIssue model"""
        issue = ReviewIssue(
            issue_type=IssueType.GRAMMAR,
            severity=IssueSeverity.MINOR,
            location="Paragraph 2",
            description="Missing comma",
            suggestion="Add comma after 'however'"
        )
        assert issue.issue_type == IssueType.GRAMMAR
        assert issue.severity == IssueSeverity.MINOR

    def test_workflow_task_model(self):
        """Test WorkflowTask model"""
        task = WorkflowTask(
            task_id="task-123",
            title="Research Project",
            description="Conduct market research",
            context="Focus on technology sector",
            constraints=["Max 3000 words"],
            expected_output="Market analysis report"
        )
        assert task.task_id == "task-123"
        assert task.title == "Research Project"
        assert len(task.constraints) == 1


# =============================================================================
# RESEARCH AGENT TESTS
# =============================================================================

class TestResearchAgent:
    """Test Research Agent (AGENT-012)"""

    def test_agent_initialization(self):
        """Test Research Agent initializes correctly"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ResearchAgent()
            assert agent.AGENT_ID == "AGENT-012"
            assert agent.AGENT_NAME == "Research Agent"

    def test_agent_has_correct_config(self):
        """Test Research Agent uses correct configuration"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ResearchAgent()
            assert agent.config["agent_id"] == "AGENT-012"
            assert agent.config["temperature"] == 0.2

    @pytest.mark.asyncio
    async def test_research_without_llm(self):
        """Test research returns empty result without LLM"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ResearchAgent()
            agent.llm = None
            result = await agent.research(
                query="Test query",
                task_id="test-123"
            )
            assert isinstance(result, ResearchResult)
            assert result.task_id == "test-123"
            assert result.processing_time_ms >= 0


# =============================================================================
# ANALYSIS AGENT TESTS
# =============================================================================

class TestAnalysisAgent:
    """Test Analysis Agent (AGENT-013)"""

    def test_agent_initialization(self):
        """Test Analysis Agent initializes correctly"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = AnalysisAgent()
            assert agent.AGENT_ID == "AGENT-013"
            assert agent.AGENT_NAME == "Analysis Agent"

    def test_agent_has_correct_config(self):
        """Test Analysis Agent uses correct configuration"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = AnalysisAgent()
            assert agent.config["agent_id"] == "AGENT-013"
            assert agent.config["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_analyze_without_llm(self):
        """Test analysis returns empty result without LLM"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = AnalysisAgent()
            agent.llm = None
            result = await agent.analyze(
                raw_data="Sample data for analysis",
                task_id="test-456"
            )
            assert isinstance(result, AnalysisResult)
            assert result.task_id == "test-456"

    def test_prepare_input_data_with_research(self):
        """Test input data preparation with research result"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = AnalysisAgent()
            research_result = ResearchResult(
                task_id="research-1",
                original_query="Market trends",
                summary="Summary of findings",
                findings=[
                    ResearchFinding(finding="Finding 1", confidence=0.9, category="Market")
                ]
            )
            input_data = agent._prepare_input_data(research_result, "")
            assert "Market trends" in input_data
            assert "Finding 1" in input_data


# =============================================================================
# WRITING AGENT TESTS
# =============================================================================

class TestWritingAgent:
    """Test Writing Agent (AGENT-014)"""

    def test_agent_initialization(self):
        """Test Writing Agent initializes correctly"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = WritingAgent()
            assert agent.AGENT_ID == "AGENT-014"
            assert agent.AGENT_NAME == "Writing Agent"

    def test_agent_has_correct_config(self):
        """Test Writing Agent uses correct configuration"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = WritingAgent()
            assert agent.config["agent_id"] == "AGENT-014"
            assert agent.config["temperature"] == 0.4

    @pytest.mark.asyncio
    async def test_write_without_llm(self):
        """Test writing returns empty result without LLM"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = WritingAgent()
            agent.llm = None
            task = WorkflowTask(
                task_id="write-task",
                title="Test Report",
                description="Write a test report"
            )
            result = await agent.write(
                task=task,
                task_id="test-789"
            )
            assert isinstance(result, WritingResult)
            assert result.task_id == "test-789"

    def test_prepare_context(self):
        """Test context preparation from prior results"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = WritingAgent()
            task = WorkflowTask(
                task_id="task-1",
                title="Report",
                description="Write report",
                context="Additional context"
            )
            research_result = ResearchResult(
                task_id="r1",
                summary="Research summary"
            )
            context = agent._prepare_context(task, research_result, None)
            assert "Report" in context
            assert "Research summary" in context


# =============================================================================
# REVIEW AGENT TESTS
# =============================================================================

class TestReviewAgent:
    """Test Review Agent (AGENT-015)"""

    def test_agent_initialization(self):
        """Test Review Agent initializes correctly"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ReviewAgent()
            assert agent.AGENT_ID == "AGENT-015"
            assert agent.AGENT_NAME == "Review Agent"

    def test_agent_has_correct_config(self):
        """Test Review Agent uses correct configuration"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ReviewAgent()
            assert agent.config["agent_id"] == "AGENT-015"
            assert agent.config["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_review_without_llm(self):
        """Test review returns empty result without LLM"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ReviewAgent()
            agent.llm = None
            writing_result = WritingResult(
                task_id="write-1",
                raw_content="Sample document content"
            )
            result = await agent.review(
                writing_result=writing_result,
                task_id="test-review"
            )
            assert isinstance(result, ReviewResult)
            assert result.task_id == "test-review"

    def test_determine_status_approved(self):
        """Test status determination for approved document"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ReviewAgent()
            result = ReviewResult(
                task_id="r1",
                overall_quality_score=0.9,
                issues=[]
            )
            status = agent._determine_status(result)
            assert status == ReviewStatus.APPROVED

    def test_determine_status_needs_revision(self):
        """Test status determination for document needing revision"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ReviewAgent()
            result = ReviewResult(
                task_id="r1",
                overall_quality_score=0.75,
                issues=[
                    ReviewIssue(
                        issue_type=IssueType.GRAMMAR,
                        severity=IssueSeverity.MAJOR,
                        description="Issue 1"
                    )
                ]
            )
            status = agent._determine_status(result)
            assert status == ReviewStatus.NEEDS_REVISION

    def test_determine_status_major_issues(self):
        """Test status determination for document with major issues"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            agent = ReviewAgent()
            result = ReviewResult(
                task_id="r1",
                overall_quality_score=0.5,
                issues=[
                    ReviewIssue(
                        issue_type=IssueType.FACTUAL,
                        severity=IssueSeverity.CRITICAL,
                        description="Critical error"
                    )
                ]
            )
            status = agent._determine_status(result)
            assert status == ReviewStatus.MAJOR_ISSUES


# =============================================================================
# ORCHESTRATION SERVICE TESTS
# =============================================================================

class TestMultiAgentOrchestrationService:
    """Test MultiAgentOrchestrationService"""

    def test_service_initialization(self):
        """Test service initializes correctly"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()
            assert service.research_agent is not None
            assert service.analysis_agent is not None
            assert service.writing_agent is not None
            assert service.review_agent is not None

    def test_get_stats(self):
        """Test getting workflow statistics"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()
            stats = service.get_stats()
            assert "total_workflows" in stats
            assert "agents" in stats
            assert "AGENT-012" in stats["agents"]
            assert "AGENT-013" in stats["agents"]
            assert "AGENT-014" in stats["agents"]
            assert "AGENT-015" in stats["agents"]

    def test_reset_stats(self):
        """Test resetting workflow statistics"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()
            service._stats["workflows_completed"] = 10
            service.reset_stats()
            assert service._stats["workflows_completed"] == 0

    def test_get_agent_info(self):
        """Test getting agent information"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()
            agents = service.get_agent_info()
            assert len(agents) == 4
            agent_ids = [a["agent_id"] for a in agents]
            assert "AGENT-012" in agent_ids
            assert "AGENT-013" in agent_ids
            assert "AGENT-014" in agent_ids
            assert "AGENT-015" in agent_ids

    @pytest.mark.asyncio
    async def test_execute_workflow_without_llm(self):
        """Test workflow execution without LLM"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()
            service.research_agent.llm = None
            service.analysis_agent.llm = None
            service.writing_agent.llm = None
            service.review_agent.llm = None

            task = WorkflowTask(
                task_id="test-workflow",
                title="Test Task",
                description="Test workflow execution"
            )

            result = await service.execute_workflow(
                task=task,
                run_research=True,
                run_analysis=True,
                run_writing=True,
                run_review=False  # Skip review since writing has no content
            )

            assert isinstance(result, OrchestrationResult)
            assert result.workflow_completed
            assert "AGENT-012" in result.agents_used
            assert "AGENT-013" in result.agents_used
            assert "AGENT-014" in result.agents_used


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Test singleton pattern"""

    def test_singleton_returns_same_instance(self):
        """Test that singleton returns the same instance"""
        # Reset the singleton
        import app.services.multi_agent_orchestration as module
        module._orchestration_service = None

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service1 = get_multi_agent_orchestration_service()
            service2 = get_multi_agent_orchestration_service()
            assert service1 is service2


# =============================================================================
# API ENDPOINT TESTS
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client with isolated app"""
        from app.routes.multi_agent_orchestration import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/orchestration/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert len(data["agents"]) == 4

    def test_get_agents_endpoint(self, client):
        """Test get agents endpoint"""
        response = client.get("/api/orchestration/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 4

    def test_get_agent_by_id(self, client):
        """Test get specific agent endpoint"""
        response = client.get("/api/orchestration/agents/AGENT-012")
        assert response.status_code == 200
        agent = response.json()
        assert agent["agent_id"] == "AGENT-012"
        assert agent["name"] == "Research Agent"

    def test_get_agent_not_found(self, client):
        """Test get agent with invalid ID"""
        response = client.get("/api/orchestration/agents/AGENT-999")
        assert response.status_code == 404

    def test_get_stats_endpoint(self, client):
        """Test get stats endpoint"""
        response = client.get("/api/orchestration/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_workflows" in stats

    def test_reset_stats_endpoint(self, client):
        """Test reset stats endpoint"""
        response = client.post("/api/orchestration/stats/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Statistics reset successfully"

    def test_workflow_endpoint_validation(self, client):
        """Test workflow endpoint with invalid data"""
        response = client.post("/api/orchestration/workflow", json={
            "title": "AB",  # Too short
            "description": "Test"  # Too short
        })
        assert response.status_code == 422  # Validation error

    def test_research_endpoint_validation(self, client):
        """Test research endpoint with invalid data"""
        response = client.post("/api/orchestration/research", json={
            "query": "AB"  # Too short
        })
        assert response.status_code == 422

    def test_review_endpoint_validation(self, client):
        """Test review endpoint with invalid data"""
        response = client.post("/api/orchestration/review", json={
            "content": "Too short"  # Less than 50 chars
        })
        assert response.status_code == 422


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_research_result_empty_sources(self):
        """Test ResearchResult with empty sources"""
        result = ResearchResult(
            task_id="empty",
            original_query="Test",
            sources=[],
            findings=[]
        )
        assert len(result.sources) == 0
        assert len(result.findings) == 0

    def test_analysis_result_empty_patterns(self):
        """Test AnalysisResult with empty patterns"""
        result = AnalysisResult(
            task_id="empty",
            patterns=[],
            statistics=[],
            correlations=[]
        )
        assert len(result.patterns) == 0

    def test_writing_result_no_report(self):
        """Test WritingResult with no report"""
        result = WritingResult(
            task_id="no-report",
            raw_content="Just raw content"
        )
        assert result.report is None
        assert result.raw_content == "Just raw content"

    def test_review_result_no_issues(self):
        """Test ReviewResult with no issues"""
        result = ReviewResult(
            task_id="clean",
            status=ReviewStatus.APPROVED,
            issues=[]
        )
        assert result.status == ReviewStatus.APPROVED
        assert len(result.issues) == 0

    def test_workflow_task_no_constraints(self):
        """Test WorkflowTask with no constraints"""
        task = WorkflowTask(
            task_id="simple",
            title="Simple Task",
            description="A simple task with no constraints"
        )
        assert len(task.constraints) == 0

    def test_orchestration_result_partial_workflow(self):
        """Test OrchestrationResult from partial workflow"""
        result = OrchestrationResult(
            workflow_id="partial",
            agents_used=["AGENT-012", "AGENT-013"],
            workflow_completed=True
        )
        assert len(result.agents_used) == 2
        assert result.workflow_completed


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for multi-agent orchestration"""

    @pytest.mark.asyncio
    async def test_full_workflow_without_llm(self):
        """Test full workflow execution without LLM"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()

            # Disable all LLMs
            service.research_agent.llm = None
            service.analysis_agent.llm = None
            service.writing_agent.llm = None
            service.review_agent.llm = None

            task = WorkflowTask(
                task_id="integration-test",
                title="Integration Test Report",
                description="Test the full workflow integration",
                context="Testing context",
                constraints=["Keep it brief"],
                expected_output="A test report"
            )

            result = await service.execute_workflow(
                task=task,
                run_research=True,
                run_analysis=True,
                run_writing=True,
                run_review=False,  # Skip review for this test
                output_format=ReportFormat.MARKDOWN
            )

            assert result.workflow_completed
            assert result.total_processing_time_ms > 0
            assert "AGENT-012" in result.agents_used
            assert "AGENT-013" in result.agents_used
            assert "AGENT-014" in result.agents_used

    @pytest.mark.asyncio
    async def test_individual_agent_calls(self):
        """Test calling individual agents"""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}, clear=False):
            service = MultiAgentOrchestrationService()

            # Disable all LLMs
            service.research_agent.llm = None
            service.analysis_agent.llm = None
            service.writing_agent.llm = None
            service.review_agent.llm = None

            # Test research
            research_result = await service.quick_research("Test query")
            assert isinstance(research_result, ResearchResult)

            # Test analysis
            analysis_result = await service.analyze_data("Test data for analysis")
            assert isinstance(analysis_result, AnalysisResult)

            # Test writing
            task = WorkflowTask(
                task_id="write",
                title="Test",
                description="Write something"
            )
            writing_result = await service.generate_report(task)
            assert isinstance(writing_result, WritingResult)


# =============================================================================
# CONTENT ANALYSIS TESTS
# =============================================================================

class TestContentAnalysis:
    """Test content analysis functionality"""

    def test_research_query_expansion(self):
        """Test that research queries can be expanded"""
        query = ResearchQuery(
            original_query="AI trends",
            expanded_queries=["artificial intelligence trends", "machine learning trends"],
            key_terms=["AI", "ML", "trends"]
        )
        assert len(query.expanded_queries) == 2
        assert len(query.key_terms) == 3

    def test_pattern_detection_types(self):
        """Test different pattern types"""
        patterns = [
            DetectedPattern(pattern_type=PatternType.TREND, name="Growth", description=""),
            DetectedPattern(pattern_type=PatternType.ANOMALY, name="Spike", description=""),
            DetectedPattern(pattern_type=PatternType.CORRELATION, name="Linked", description=""),
        ]
        types = [p.pattern_type for p in patterns]
        assert PatternType.TREND in types
        assert PatternType.ANOMALY in types
        assert PatternType.CORRELATION in types

    def test_report_sections_ordering(self):
        """Test report sections can be ordered"""
        sections = [
            ReportSection(title="Conclusion", content="", order=4),
            ReportSection(title="Introduction", content="", order=1),
            ReportSection(title="Body", content="", order=2),
            ReportSection(title="Summary", content="", order=3),
        ]
        sorted_sections = sorted(sections, key=lambda s: s.order)
        assert sorted_sections[0].title == "Introduction"
        assert sorted_sections[-1].title == "Conclusion"

    def test_issue_severity_ordering(self):
        """Test issue severity can be compared"""
        issues = [
            ReviewIssue(issue_type=IssueType.GRAMMAR, severity=IssueSeverity.MINOR, description=""),
            ReviewIssue(issue_type=IssueType.FACTUAL, severity=IssueSeverity.CRITICAL, description=""),
            ReviewIssue(issue_type=IssueType.CONSISTENCY, severity=IssueSeverity.MAJOR, description=""),
        ]
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 1
        assert critical_issues[0].issue_type == IssueType.FACTUAL


# =============================================================================
# TASK 138: REVISION LOOP TESTS
# =============================================================================

class TestRevisionLoopModels:
    """Test Task 138 revision loop model enhancements"""

    def test_review_result_revision_fields(self):
        """Test ReviewResult has revision tracking fields"""
        review = ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            overall_quality_score=0.65,
            issues=[],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=[],
            revision_count=1,
            revision_requested=True,
            quality_threshold=0.75
        )
        assert review.revision_count == 1
        assert review.revision_requested is True
        assert review.quality_threshold == 0.75

    def test_review_result_default_revision_fields(self):
        """Test ReviewResult has correct defaults for revision fields"""
        review = ReviewResult(
            status=ReviewStatus.APPROVED,
            overall_quality_score=0.85,
            issues=[],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=[]
        )
        assert review.revision_count == 0
        assert review.revision_requested is False
        assert review.quality_threshold == 0.75

    def test_orchestration_result_revision_fields(self):
        """Test OrchestrationResult has revision tracking fields"""
        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        result = OrchestrationResult(
            workflow_id="wf-1",
            task=task,
            requires_human_review=True,
            quality_score_history=[0.6, 0.7, 0.75],
            revision_history=[
                {"revision_number": 0, "quality_score": 0.6},
                {"revision_number": 1, "quality_score": 0.7},
                {"revision_number": 2, "quality_score": 0.75}
            ]
        )
        assert result.requires_human_review is True
        assert len(result.quality_score_history) == 3
        assert len(result.revision_history) == 3

    def test_orchestration_result_default_revision_fields(self):
        """Test OrchestrationResult has correct defaults for revision fields"""
        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        result = OrchestrationResult(workflow_id="wf-1", task=task)
        assert result.requires_human_review is False
        assert result.quality_score_history == []
        assert result.revision_history == []

    def test_review_result_quality_threshold_bounds(self):
        """Test quality threshold validation"""
        # Valid threshold
        review = ReviewResult(
            status=ReviewStatus.APPROVED,
            overall_quality_score=0.8,
            issues=[],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=[],
            quality_threshold=0.5
        )
        assert review.quality_threshold == 0.5

        # Edge case: 0
        review_zero = ReviewResult(
            status=ReviewStatus.APPROVED,
            overall_quality_score=0.8,
            issues=[],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=[],
            quality_threshold=0.0
        )
        assert review_zero.quality_threshold == 0.0

        # Edge case: 1
        review_one = ReviewResult(
            status=ReviewStatus.APPROVED,
            overall_quality_score=1.0,
            issues=[],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=[],
            quality_threshold=1.0
        )
        assert review_one.quality_threshold == 1.0


class TestWritingAgentRevision:
    """Test WritingAgent.revise_content method (Task 138)"""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create mock Anthropic client"""
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = MagicMock()
        return client

    @pytest.fixture
    def writing_agent(self, mock_anthropic_client):
        """Create WritingAgent with mocked client"""
        agent = WritingAgent(client=mock_anthropic_client)
        return agent

    @pytest.fixture
    def sample_writing_result(self):
        """Create sample writing result for revision"""
        return WritingResult(
            raw_content="Original content that needs improvement.",
            word_count=6,
            format=ReportFormat.MARKDOWN,
            citations=[]
        )

    @pytest.fixture
    def sample_review_feedback(self):
        """Create sample review feedback"""
        return ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            overall_quality_score=0.65,
            issues=[
                ReviewIssue(
                    issue_type=IssueType.CLARITY,
                    severity=IssueSeverity.MAJOR,
                    description="Content lacks clear structure",
                    location="paragraph 1",
                    suggested_fix="Add section headers and improve transitions"
                )
            ],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=["Add more detail", "Improve flow"],
            revision_count=0,
            revision_requested=True,
            quality_threshold=0.75
        )

    @pytest.fixture
    def sample_task(self):
        """Create sample workflow task"""
        return WorkflowTask(task_id="task-1", title="Write Report", description="Write a report")

    @pytest.mark.asyncio
    async def test_revise_content_called_with_feedback(
        self, writing_agent, mock_anthropic_client,
        sample_writing_result, sample_review_feedback, sample_task
    ):
        """Test revise_content uses feedback in prompt"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Revised content with improvements.")]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await writing_agent.revise_content(
            original_writing=sample_writing_result,
            review_feedback=sample_review_feedback,
            task=sample_task,
            revision_number=1
        )

        # Verify the method was called
        mock_anthropic_client.messages.create.assert_called_once()

        # Check the prompt contains revision context
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args.kwargs.get("messages", [])
        assert len(messages) > 0

        # Verify result is a WritingResult
        assert isinstance(result, WritingResult)

    @pytest.mark.asyncio
    async def test_revise_content_tracks_revision_number(
        self, writing_agent, mock_anthropic_client,
        sample_writing_result, sample_review_feedback, sample_task
    ):
        """Test revise_content increments revision number correctly"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Revised content.")]
        mock_anthropic_client.messages.create.return_value = mock_response

        # First revision
        await writing_agent.revise_content(
            original_writing=sample_writing_result,
            review_feedback=sample_review_feedback,
            task=sample_task,
            revision_number=1
        )

        # Verify call was made
        assert mock_anthropic_client.messages.create.called


class TestRevisionLoopWorkflow:
    """Test revision loop in execute_workflow (Task 138)"""

    @pytest.fixture
    def mock_service(self):
        """Create service with mocked components"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            service = MultiAgentOrchestrationService()
            service.research_agent = MagicMock(spec=ResearchAgent)
            service.analysis_agent = MagicMock(spec=AnalysisAgent)
            service.writing_agent = MagicMock(spec=WritingAgent)
            service.review_agent = MagicMock(spec=ReviewAgent)

            return service

    @pytest.fixture
    def sample_writing_result(self):
        """Create sample writing result"""
        return WritingResult(
            raw_content="Test content",
            word_count=2,
            format=ReportFormat.MARKDOWN,
            citations=[]
        )

    def test_service_has_quality_threshold(self, mock_service):
        """Test service has quality threshold constant"""
        assert hasattr(mock_service, 'QUALITY_THRESHOLD')
        assert mock_service.QUALITY_THRESHOLD == 0.75

    def test_service_has_max_revisions(self, mock_service):
        """Test service has max revisions constant"""
        assert hasattr(mock_service, 'MAX_REVISIONS')
        assert mock_service.MAX_REVISIONS == 3

    @pytest.mark.asyncio
    async def test_workflow_approved_first_pass(self, mock_service, sample_writing_result):
        """Test workflow when content is approved on first pass"""
        # Setup mocks
        mock_service.research_agent.research = AsyncMock(return_value=ResearchResult(
            query=ResearchQuery(original_query="test", expanded_queries=[], key_terms=[]),
            sources=[],
            findings=[],
            summary=""
        ))
        mock_service.analysis_agent.analyze = AsyncMock(return_value=AnalysisResult(
            patterns=[],
            statistics=[],
            correlations=[],
            summary=""
        ))
        mock_service.writing_agent.write = AsyncMock(return_value=sample_writing_result)

        # Review approves on first try
        mock_service.review_agent.review = AsyncMock(return_value=ReviewResult(
            status=ReviewStatus.APPROVED,
            overall_quality_score=0.85,
            issues=[],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=[],
            approved_for_publication=True
        ))

        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        result = await mock_service.execute_workflow(task)

        # Verify successful first pass metrics
        stats = mock_service.get_stats()
        assert stats["revision_metrics"]["successful_first_pass"] >= 1
        assert result.revision_count == 0

    @pytest.mark.asyncio
    async def test_workflow_approved_after_revision(self, mock_service, sample_writing_result):
        """Test workflow when content is approved after revision"""
        mock_service.research_agent.research = AsyncMock(return_value=ResearchResult(
            query=ResearchQuery(original_query="test", expanded_queries=[], key_terms=[]),
            sources=[],
            findings=[],
            summary=""
        ))
        mock_service.analysis_agent.analyze = AsyncMock(return_value=AnalysisResult(
            patterns=[],
            statistics=[],
            correlations=[],
            summary=""
        ))
        mock_service.writing_agent.write = AsyncMock(return_value=sample_writing_result)
        mock_service.writing_agent.revise_content = AsyncMock(return_value=sample_writing_result)

        # First review: needs revision, second: approved
        mock_service.review_agent.review = AsyncMock(side_effect=[
            ReviewResult(
                status=ReviewStatus.NEEDS_REVISION,
                overall_quality_score=0.65,
                issues=[ReviewIssue(issue_type=IssueType.CLARITY, severity=IssueSeverity.MAJOR, description="Unclear")],
                fact_check_results=[],
                consistency_checks=[],
                suggestions=["Improve clarity"]
            ),
            ReviewResult(
                status=ReviewStatus.APPROVED,
                overall_quality_score=0.82,
                issues=[],
                fact_check_results=[],
                consistency_checks=[],
                suggestions=[],
                approved_for_publication=True
            )
        ])

        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        result = await mock_service.execute_workflow(task)

        # Verify revision was requested and succeeded
        mock_service.writing_agent.revise_content.assert_called()
        assert result.revision_count >= 1

    @pytest.mark.asyncio
    async def test_workflow_max_revisions_reached(self, mock_service, sample_writing_result):
        """Test workflow when max revisions reached without approval"""
        mock_service.research_agent.research = AsyncMock(return_value=ResearchResult(
            query=ResearchQuery(original_query="test", expanded_queries=[], key_terms=[]),
            sources=[],
            findings=[],
            summary=""
        ))
        mock_service.analysis_agent.analyze = AsyncMock(return_value=AnalysisResult(
            patterns=[],
            statistics=[],
            correlations=[],
            summary=""
        ))
        mock_service.writing_agent.write = AsyncMock(return_value=sample_writing_result)
        mock_service.writing_agent.revise_content = AsyncMock(return_value=sample_writing_result)

        # Always needs revision (never approved)
        mock_service.review_agent.review = AsyncMock(return_value=ReviewResult(
            status=ReviewStatus.NEEDS_REVISION,
            overall_quality_score=0.65,
            issues=[ReviewIssue(issue_type=IssueType.CLARITY, severity=IssueSeverity.MAJOR, description="Still unclear")],
            fact_check_results=[],
            consistency_checks=[],
            suggestions=["Keep improving"]
        ))

        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        result = await mock_service.execute_workflow(task, max_revisions=3)

        # Verify max revisions were attempted
        assert result.requires_human_review is True
        assert result.revision_count >= mock_service.MAX_REVISIONS

    def test_quality_score_history_tracking(self, mock_service):
        """Test that quality score history is properly structured"""
        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        result = OrchestrationResult(
            workflow_id="wf-1",
            task=task,
            quality_score_history=[0.55, 0.65, 0.75, 0.80]
        )
        assert len(result.quality_score_history) == 4
        assert result.quality_score_history[0] < result.quality_score_history[-1]

    def test_revision_history_structure(self, mock_service):
        """Test revision history contains expected fields"""
        task = WorkflowTask(task_id="test-1", title="Test Task", description="Test task")
        revision_entry = {
            "revision_number": 1,
            "quality_score": 0.72,
            "status": "needs_revision",
            "issues_count": 3,
            "critical_issues": 1,
            "approved": False
        }
        result = OrchestrationResult(
            workflow_id="wf-1",
            task=task,
            revision_history=[revision_entry]
        )
        assert result.revision_history[0]["revision_number"] == 1
        assert result.revision_history[0]["quality_score"] == 0.72
        assert result.revision_history[0]["critical_issues"] == 1


class TestRevisionMetrics:
    """Test revision metrics in get_stats (Task 138)"""

    @pytest.fixture
    def mock_service(self):
        """Create service with mocked components"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            service = MultiAgentOrchestrationService()
            return service

    def test_get_stats_includes_revision_metrics(self, mock_service):
        """Test get_stats returns revision metrics"""
        stats = mock_service.get_stats()
        assert "revision_metrics" in stats

    def test_revision_metrics_fields(self, mock_service):
        """Test revision_metrics contains expected fields"""
        stats = mock_service.get_stats()
        rm = stats["revision_metrics"]

        assert "successful_first_pass" in rm
        assert "successful_after_revision" in rm
        assert "failed_after_max_revisions" in rm
        assert "total_quality_improvement" in rm
        assert "revision_distribution" in rm
        assert "first_pass_success_rate" in rm
        assert "revision_success_rate" in rm
        assert "average_quality_improvement_per_revision" in rm
        assert "quality_threshold" in rm
        assert "max_revisions_allowed" in rm

    def test_revision_distribution_structure(self, mock_service):
        """Test revision distribution has correct structure"""
        stats = mock_service.get_stats()
        rd = stats["revision_metrics"]["revision_distribution"]

        assert 1 in rd
        assert 2 in rd
        assert 3 in rd

    def test_reset_stats_clears_revision_metrics(self, mock_service):
        """Test reset_stats clears revision metrics"""
        # Manually set some stats
        mock_service._stats["successful_first_pass"] = 5
        mock_service._stats["successful_after_revision"] = 3
        mock_service._stats["failed_after_max_revisions"] = 1
        mock_service._stats["total_quality_improvement"] = 0.45

        # Reset
        mock_service.reset_stats()

        # Verify all revision metrics are cleared
        assert mock_service._stats["successful_first_pass"] == 0
        assert mock_service._stats["successful_after_revision"] == 0
        assert mock_service._stats["failed_after_max_revisions"] == 0
        assert mock_service._stats["total_quality_improvement"] == 0.0

    def test_first_pass_success_rate_calculation(self, mock_service):
        """Test first pass success rate is calculated correctly"""
        mock_service._stats["successful_first_pass"] = 8
        mock_service._stats["successful_after_revision"] = 2
        mock_service._stats["failed_after_max_revisions"] = 0

        stats = mock_service.get_stats()
        rate = stats["revision_metrics"]["first_pass_success_rate"]

        # 8 / (8+2+0) = 0.8
        assert rate == 0.8

    def test_revision_success_rate_calculation(self, mock_service):
        """Test revision success rate is calculated correctly"""
        mock_service._stats["successful_after_revision"] = 3
        mock_service._stats["failed_after_max_revisions"] = 1

        stats = mock_service.get_stats()
        rate = stats["revision_metrics"]["revision_success_rate"]

        # 3 / (3+1) = 0.75
        assert rate == 0.75

    def test_average_quality_improvement_calculation(self, mock_service):
        """Test average quality improvement per revision is calculated correctly"""
        mock_service._stats["total_quality_improvement"] = 0.30
        mock_service._stats["total_revisions"] = 6

        stats = mock_service.get_stats()
        avg = stats["revision_metrics"]["average_quality_improvement_per_revision"]

        # 0.30 / 6 = 0.05
        assert avg == 0.05

    def test_metrics_handle_zero_division(self, mock_service):
        """Test metrics handle zero division gracefully"""
        mock_service.reset_stats()  # All zeros

        stats = mock_service.get_stats()
        rm = stats["revision_metrics"]

        # Should not raise and should use max(1, x) for division
        assert rm["first_pass_success_rate"] == 0.0
        assert rm["revision_success_rate"] == 0.0
        assert rm["average_quality_improvement_per_revision"] == 0.0

    def test_quality_threshold_in_metrics(self, mock_service):
        """Test quality threshold is exposed in metrics"""
        stats = mock_service.get_stats()
        assert stats["revision_metrics"]["quality_threshold"] == 0.75

    def test_max_revisions_in_metrics(self, mock_service):
        """Test max revisions is exposed in metrics"""
        stats = mock_service.get_stats()
        assert stats["revision_metrics"]["max_revisions_allowed"] == 3
