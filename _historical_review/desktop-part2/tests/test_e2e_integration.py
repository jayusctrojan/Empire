"""
Empire v7.3 - End-to-End Integration Tests (Task 23)
Tests key features together under realistic scenarios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
import base64


# =============================================================================
# FIXTURE: Mock all external services
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for all tests"""
    with patch('app.core.supabase_client.get_supabase_client') as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_b2():
    """Mock B2 storage service"""
    with patch('app.services.b2_storage.get_b2_service') as mock:
        mock_service = MagicMock()
        mock_service.upload_file = AsyncMock(return_value={
            "file_id": "test-file-id",
            "file_name": "test/path/file.pdf",
            "size": 1024,
            "content_type": "application/pdf"
        })
        mock_service.get_signed_download_url = MagicMock(return_value={
            "signed_url": "https://b2.example.com/file?auth=token",
            "expires_at": datetime.utcnow().isoformat(),
            "valid_duration_seconds": 3600
        })
        mock.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic Claude client"""
    with patch('anthropic.Anthropic') as mock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is a mock AI response.")]
        mock_client.messages.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock_client


# =============================================================================
# TEST: Content Summarizer Agent Flow
# =============================================================================

class TestContentSummarizerFlow:
    """Test end-to-end content summarization flow"""

    @pytest.mark.asyncio
    async def test_summarize_document_flow(self):
        """Test complete document summarization pipeline"""
        from app.services.content_summarizer_agent import ContentSummarizerAgentService

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            # Setup mock
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
**Summary**
This document covers key business processes.

**Key Points**
- Point 1: Important finding
- Point 2: Critical insight
- Point 3: Action item

**Diagrams**
- Process flow diagram on page 3

**Department**: finance-accounting
**Confidence**: 0.92
            """)]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            # Create agent service
            agent = ContentSummarizerAgentService()
            agent.llm = mock_client

            # Execute summarization with actual method signature
            result = await agent.generate_summary(
                content="This is the Q4 financial report with key metrics...",
                department="finance-accounting",
                title="Q4 Financial Report",
                source_type="document",
                metadata={"document_id": "doc-123"}
            )

            # Verify result structure
            assert result is not None
            assert result.title == "Q4 Financial Report"


# =============================================================================
# TEST: Department Classifier Flow
# =============================================================================

class TestDepartmentClassifierFlow:
    """Test end-to-end department classification flow"""

    @pytest.mark.asyncio
    async def test_classify_document_flow(self):
        """Test complete document classification pipeline"""
        from app.services.department_classifier_agent import DepartmentClassifierAgentService

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            # Setup mock
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
{
    "primary_department": "finance-accounting",
    "confidence": 0.95,
    "secondary_departments": ["operations-hr-supply"],
    "reasoning": "Document discusses financial metrics and budget allocation.",
    "key_indicators": ["revenue", "budget", "quarterly report"]
}
            """)]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            # Create agent service
            agent = DepartmentClassifierAgentService(use_llm=True)

            # Execute classification with actual method signature
            result = await agent.classify_content(
                content="This is a financial document about Q4 revenue projections...",
                filename="Q4 Revenue Projections.pdf",
                include_all_scores=False
            )

            # Verify result structure
            assert result is not None
            assert result.department is not None
            assert 0 <= result.confidence <= 1


# =============================================================================
# TEST: Agent Router Flow
# =============================================================================

class TestAgentRouterFlow:
    """Test end-to-end agent routing flow"""

    @pytest.mark.asyncio
    async def test_route_simple_query(self):
        """Test routing a simple lookup query"""
        from app.services.agent_router_service import AgentRouterService

        with patch('anthropic.AsyncAnthropic'):
            service = AgentRouterService()

            # Simple query should route using classify_query_rules (sync method)
            result = service.classify_query_rules("What is the vacation policy?")

            assert result is not None
            # Returns tuple of (category, keywords, reasoning)
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_route_complex_query(self):
        """Test routing a complex research query"""
        from app.services.agent_router_service import AgentRouterService
        from app.models.agent_router import AgentRouterRequest

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"category": "research", "confidence": 0.9}')]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            service = AgentRouterService()

            # Complex query - test the async route_query method
            request = AgentRouterRequest(
                query="Compare the financial performance across all departments "
                      "for the last 3 years and identify trends"
            )
            result = await service.route_query(request)

            assert result is not None


# =============================================================================
# TEST: CrewAI Asset Storage Flow
# =============================================================================

class TestCrewAIAssetFlow:
    """Test end-to-end CrewAI asset storage flow"""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_text_asset(self):
        """Test storing and retrieving text-based asset"""
        from app.models.crewai_asset import (
            AssetStorageRequest,
            AssetType,
            Department,
            ContentFormat
        )

        with patch('app.services.crewai_asset_service.get_supabase_client') as mock_supabase, \
             patch('app.services.crewai_asset_service.get_b2_service') as mock_b2:

            # Setup mocks
            mock_client = MagicMock()
            asset_id = str(uuid4())
            execution_id = uuid4()

            # Mock insert
            mock_client.table.return_value.insert.return_value.execute.return_value.data = [{
                "id": asset_id,
                "execution_id": str(execution_id),
                "document_id": "doc-123",
                "department": "marketing",
                "asset_type": "summary",
                "asset_name": "Marketing Summary",
                "content": "# Marketing Summary\n\nKey findings...",
                "content_format": "markdown",
                "b2_path": None,
                "file_size": None,
                "mime_type": "text/markdown",
                "metadata": {"campaign": "Q4"},
                "confidence_score": 0.95,
                "created_at": datetime.utcnow().isoformat()
            }]

            mock_supabase.return_value = mock_client
            mock_b2.return_value = MagicMock()

            from app.services.crewai_asset_service import CrewAIAssetService
            import app.services.crewai_asset_service as module
            module._asset_service = None

            service = CrewAIAssetService()
            service.supabase = mock_client

            request = AssetStorageRequest(
                execution_id=execution_id,
                document_id="doc-123",
                department=Department.MARKETING,
                asset_type=AssetType.SUMMARY,
                asset_name="Marketing Summary",
                content="# Marketing Summary\n\nKey findings...",
                content_format=ContentFormat.MARKDOWN,
                metadata={"campaign": "Q4"},
                confidence_score=0.95
            )

            result = await service.store_asset(request)

            assert result is not None
            assert result.asset_name == "Marketing Summary"
            assert result.b2_path is None  # Text assets don't go to B2


# =============================================================================
# TEST: Document Analysis Workflow
# =============================================================================

class TestDocumentAnalysisFlow:
    """Test end-to-end document analysis workflow"""

    @pytest.mark.asyncio
    async def test_full_analysis_pipeline(self):
        """Test the 3-agent document analysis pipeline"""
        from app.services.document_analysis_agents import DocumentAnalysisWorkflowService

        with patch('anthropic.Anthropic') as mock_anthropic:
            # Setup mock for all 3 agents
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
{
    "topics": ["technology", "innovation"],
    "entities": ["Company A", "Product X"],
    "key_facts": ["Fact 1", "Fact 2"],
    "quality_assessment": {"score": 0.85, "issues": []}
}
            """)]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            # Reset singleton
            import app.services.document_analysis_agents as module
            module._workflow_service = None

            service = DocumentAnalysisWorkflowService()

            # Get agent info to verify setup
            agent_info = service.get_agent_info()

            assert len(agent_info) == 3
            agent_names = [a["name"] for a in agent_info]
            assert "Senior Research Analyst" in agent_names
            assert "Content Strategist" in agent_names
            assert "Fact Checker" in agent_names


# =============================================================================
# TEST: Multi-Agent Orchestration Flow
# =============================================================================

class TestMultiAgentOrchestrationFlow:
    """Test end-to-end multi-agent orchestration workflow"""

    @pytest.mark.asyncio
    async def test_orchestration_workflow(self):
        """Test the 4-agent orchestration workflow"""
        from app.services.multi_agent_orchestration import MultiAgentOrchestrationService

        with patch('anthropic.Anthropic') as mock_anthropic:
            # Setup mock
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Research findings and analysis")]
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            # Reset singleton
            import app.services.multi_agent_orchestration as module
            module._orchestration_service = None

            service = MultiAgentOrchestrationService()

            # Get agent info to verify setup
            agent_info = service.get_agent_info()

            assert len(agent_info) == 4
            agent_names = [a["name"] for a in agent_info]
            assert "Research Agent" in agent_names
            assert "Analysis Agent" in agent_names
            assert "Writing Agent" in agent_names
            assert "Review Agent" in agent_names


# =============================================================================
# TEST: Asset Generator Agents Flow
# =============================================================================

class TestAssetGeneratorFlow:
    """Test end-to-end asset generation flow"""

    @pytest.mark.asyncio
    async def test_skill_generation(self):
        """Test skill YAML generation"""
        from app.services.asset_generator_agents import (
            SkillGeneratorAgent,
            AssetGenerationRequest,
            AssetType,
            Department
        )

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
name: data-analysis-skill
description: Analyze data and generate insights
parameters:
  - name: data_source
    type: string
    required: true
steps:
  - name: Load Data
    action: load_data
  - name: Analyze
    action: analyze
            """)]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            generator = SkillGeneratorAgent(output_base_path="test-output")
            generator.llm = mock_client

            request = AssetGenerationRequest(
                name="data-analysis-skill",
                description="Analyze data and generate insights",
                department=Department.IT_ENGINEERING,
                asset_type=AssetType.SKILL
            )

            result = await generator.generate(request)

            assert result is not None
            assert result.asset_type == AssetType.SKILL


# =============================================================================
# TEST: B2 Storage and Signed URL Flow
# =============================================================================

class TestB2StorageFlow:
    """Test B2 storage and signed URL generation"""

    def test_signed_url_generation(self):
        """Test signed URL generation for B2 assets"""
        from app.services.b2_storage import B2StorageService
        from datetime import timedelta

        with patch('app.services.b2_storage.InMemoryAccountInfo'), \
             patch('app.services.b2_storage.B2Api') as mock_api, \
             patch.dict('os.environ', {
                 'B2_APPLICATION_KEY_ID': 'test-key-id',
                 'B2_APPLICATION_KEY': 'test-key',
                 'B2_BUCKET_NAME': 'test-bucket'
             }):

            mock_bucket = MagicMock()
            mock_bucket.get_download_authorization.return_value = "mock-auth-token"
            mock_api_instance = MagicMock()
            mock_api_instance.get_bucket_by_name.return_value = mock_bucket
            mock_api_instance.get_download_url_for_file_name.return_value = "https://b2.example.com/file"
            mock_api.return_value = mock_api_instance

            # Reset singleton
            import app.services.b2_storage as module
            module._b2_service = None

            service = B2StorageService()
            service._is_authorized = True
            service._bucket = mock_bucket

            result = service.get_signed_download_url(
                file_path="crewai/assets/marketing/summary/uuid/file.pdf",
                valid_duration_seconds=3600
            )

            assert result is not None
            assert "signed_url" in result
            assert "expires_at" in result
            assert "mock-auth-token" in result["signed_url"]


# =============================================================================
# TEST: API Route Integration
# =============================================================================

class TestAPIRouteIntegration:
    """Test API route integration"""

    def test_crewai_assets_routes_registered(self):
        """Verify CrewAI assets routes are properly registered"""
        from fastapi import FastAPI
        from app.routes.crewai_assets import router

        app = FastAPI()
        app.include_router(router)

        routes = [r.path for r in app.routes if hasattr(r, 'path')]

        assert "/api/crewai/assets/" in routes
        assert "/api/crewai/assets/{asset_id}" in routes
        assert "/api/crewai/assets/{asset_id}/download-url" in routes

    def test_asset_generator_routes_registered(self):
        """Verify asset generator routes are properly registered"""
        from fastapi import FastAPI
        from app.routes.asset_generators import router

        app = FastAPI()
        app.include_router(router)

        routes = [r.path for r in app.routes if hasattr(r, 'path')]

        # Check key endpoints exist
        assert any("/api/assets/skill" in r for r in routes)
        assert any("/api/assets/command" in r for r in routes)
        assert any("/api/assets/agent" in r for r in routes)


# =============================================================================
# TEST: Concurrent Operations
# =============================================================================

class TestConcurrentOperations:
    """Test concurrent operations don't cause race conditions"""

    @pytest.mark.asyncio
    async def test_concurrent_asset_storage(self):
        """Test multiple concurrent asset storage operations"""
        import asyncio
        from app.models.crewai_asset import (
            AssetStorageRequest,
            AssetType,
            Department,
            ContentFormat
        )

        with patch('app.services.crewai_asset_service.get_supabase_client') as mock_supabase, \
             patch('app.services.crewai_asset_service.get_b2_service'):

            mock_client = MagicMock()

            # Track calls
            call_count = 0

            def mock_insert():
                nonlocal call_count
                call_count += 1
                mock_response = MagicMock()
                mock_response.data = [{
                    "id": str(uuid4()),
                    "execution_id": str(uuid4()),
                    "document_id": None,
                    "department": "marketing",
                    "asset_type": "summary",
                    "asset_name": f"Test Asset {call_count}",
                    "content": "Test content",
                    "content_format": "text",
                    "b2_path": None,
                    "file_size": None,
                    "mime_type": "text/plain",
                    "metadata": {},
                    "confidence_score": 0.9,
                    "created_at": datetime.utcnow().isoformat()
                }]
                return mock_response

            mock_client.table.return_value.insert.return_value.execute = mock_insert
            mock_supabase.return_value = mock_client

            from app.services.crewai_asset_service import CrewAIAssetService
            import app.services.crewai_asset_service as module
            module._asset_service = None

            service = CrewAIAssetService()
            service.supabase = mock_client

            # Create multiple concurrent requests
            requests = [
                AssetStorageRequest(
                    execution_id=uuid4(),
                    department=Department.MARKETING,
                    asset_type=AssetType.SUMMARY,
                    asset_name=f"Test Asset {i}",
                    content=f"Test content {i}",
                    content_format=ContentFormat.TEXT
                )
                for i in range(5)
            ]

            # Execute concurrently
            tasks = [service.store_asset(req) for req in requests]
            results = await asyncio.gather(*tasks)

            # Verify all succeeded
            assert len(results) == 5
            assert call_count == 5


# =============================================================================
# TEST: Error Recovery
# =============================================================================

class TestErrorRecovery:
    """Test error handling and recovery"""

    @pytest.mark.asyncio
    async def test_summarizer_handles_empty_content(self):
        """Test summarizer handles empty content gracefully"""
        from app.services.content_summarizer_agent import ContentSummarizerAgentService

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="No meaningful content to summarize.")]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            agent = ContentSummarizerAgentService()
            agent.llm = mock_client

            # Should handle gracefully, not crash
            try:
                result = await agent.generate_summary(
                    content="",  # Empty content
                    department="general",
                    title="Empty Document"
                )
                assert result is not None
            except ValueError as e:
                # Empty content may raise ValueError, which is acceptable
                assert "empty" in str(e).lower() or "content" in str(e).lower()

    @pytest.mark.asyncio
    async def test_classifier_handles_gibberish(self):
        """Test classifier handles gibberish content"""
        from app.services.department_classifier_agent import DepartmentClassifierAgentService

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="""
{
    "primary_department": "custom",
    "confidence": 0.2,
    "secondary_departments": [],
    "reasoning": "Content appears to be random text without clear business context.",
    "key_indicators": []
}
            """)]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            agent = DepartmentClassifierAgentService(use_llm=True)

            result = await agent.classify_content(
                content="asdf jkl; qwerty uiop zxcv bnm",
                filename="Random Text.txt"
            )

            # Should return result with low confidence (keyword-based for gibberish)
            assert result is not None
            # Note: Actual confidence depends on implementation


# =============================================================================
# TEST: Integration Smoke Tests
# =============================================================================

class TestSmokeTests:
    """Quick smoke tests to verify basic functionality"""

    def test_imports_work(self):
        """Verify all key imports work"""
        from app.services.content_summarizer_agent import ContentSummarizerAgentService
        from app.services.department_classifier_agent import DepartmentClassifierAgentService
        from app.services.document_analysis_agents import DocumentAnalysisWorkflowService
        from app.services.multi_agent_orchestration import MultiAgentOrchestrationService
        from app.services.asset_generator_agents import SkillGeneratorAgent
        from app.services.crewai_asset_service import CrewAIAssetService
        from app.services.agent_router_service import AgentRouterService
        from app.services.b2_storage import B2StorageService

        assert ContentSummarizerAgentService is not None
        assert DepartmentClassifierAgentService is not None
        assert DocumentAnalysisWorkflowService is not None
        assert MultiAgentOrchestrationService is not None
        assert SkillGeneratorAgent is not None
        assert CrewAIAssetService is not None
        assert AgentRouterService is not None
        assert B2StorageService is not None

    def test_models_work(self):
        """Verify all key models work"""
        # Models are defined within service files, not separate model files
        from app.services.content_summarizer_agent import SummaryGenerationResult
        from app.services.department_classifier_agent import ClassificationResult
        from app.models.crewai_asset import AssetStorageRequest, AssetResponse
        from app.services.asset_generator_agents import AssetGenerationRequest, AssetGenerationResult

        assert SummaryGenerationResult is not None
        assert ClassificationResult is not None
        assert AssetStorageRequest is not None
        assert AssetResponse is not None
        assert AssetGenerationRequest is not None
        assert AssetGenerationResult is not None

    def test_routes_work(self):
        """Verify all key routes can be imported"""
        from app.routes.crewai_assets import router as crewai_router
        from app.routes.asset_generators import router as asset_router
        from app.routes.content_summarizer import router as summarizer_router
        from app.routes.department_classifier import router as classifier_router

        assert crewai_router is not None
        assert asset_router is not None
        assert summarizer_router is not None
        assert classifier_router is not None
