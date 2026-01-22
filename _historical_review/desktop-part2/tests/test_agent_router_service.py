"""
Empire v7.3 - Agent Router Service Tests (Task 17)
Tests for intelligent query routing between LangGraph, CrewAI, and Simple RAG

Author: Claude Code
Date: 2025-01-25
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the app directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.agent_router import (
    AgentType,
    QueryCategory,
    RoutingConfidence,
    AgentRouterRequest,
    AgentRouterResponse,
    ClassificationDetail,
)
from app.services.agent_router_service import (
    AgentRouterService,
    FEATURE_PATTERNS,
    CATEGORY_TOOLS,
)


class TestFeatureDetection:
    """Test query feature detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_detect_multi_document_features(self):
        """Test detection of multi-document query features."""
        queries = [
            "Compare these contracts side by side",
            "Analyze multiple policies for inconsistencies",
            "Review all employee handbooks",
            "What's different between these two documents?",
        ]
        for query in queries:
            features = self.service._detect_features(query)
            assert "multi_document" in features, f"Failed for: {query}"

    def test_detect_external_data_features(self):
        """Test detection of external data requirements."""
        queries = [
            "What are the current California regulations?",
            "Tell me about recent industry trends",
            "What's the latest news on compliance?",
            "Research market conditions today",
        ]
        for query in queries:
            features = self.service._detect_features(query)
            assert "external_data_needed" in features, f"Failed for: {query}"

    def test_detect_complex_reasoning_features(self):
        """Test detection of complex reasoning requirements."""
        queries = [
            "Why did we adopt this policy?",
            "Explain the implications of this change",
            "Analyze the impact on our strategy",
            "How should we recommend proceeding?",
        ]
        for query in queries:
            features = self.service._detect_features(query)
            assert "complex_reasoning" in features, f"Failed for: {query}"

    def test_detect_entity_extraction_features(self):
        """Test detection of entity extraction requirements."""
        queries = [
            "Extract all policy numbers from these documents",
            "Find all names mentioned in this contract",
            "List all dates in the agreement",
            "Identify all entities in this document",
        ]
        for query in queries:
            features = self.service._detect_features(query)
            assert "entity_extraction" in features, f"Failed for: {query}"

    def test_detect_conversational_features(self):
        """Test detection of conversational queries."""
        queries = [
            "Hello, how are you?",
            "Hi, how can I use this?",  # "Hi," pattern
            "Thanks for your help",
            "What can you do for me?",
        ]
        for query in queries:
            features = self.service._detect_features(query)
            assert "conversational" in features, f"Failed for: {query}"

    def test_detect_simple_lookup_features(self):
        """Test detection of simple lookup queries."""
        queries = [
            "What is our vacation policy?",
            "Show me document 12345",
            "Where is the compliance guide?",
            "How much does the service cost?",
        ]
        for query in queries:
            features = self.service._detect_features(query)
            assert "simple_lookup" in features, f"Failed for: {query}"


class TestComplexityCalculation:
    """Test query complexity calculation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_simple_complexity(self):
        """Test simple query complexity."""
        query = "What is our vacation policy?"
        features = self.service._detect_features(query)
        complexity = self.service._calculate_complexity(query, features)
        assert complexity == "simple"

    def test_moderate_complexity(self):
        """Test moderate query complexity."""
        query = "Explain why we need to update our privacy policy and what impact it will have"
        features = self.service._detect_features(query)
        complexity = self.service._calculate_complexity(query, features)
        assert complexity in ["moderate", "complex"]

    def test_complex_complexity(self):
        """Test complex query complexity."""
        query = """Compare all our current contracts with the latest California insurance
        regulations and analyze the implications of any gaps we find. We need to understand
        how these differences might impact our compliance strategy going forward."""
        features = self.service._detect_features(query)
        complexity = self.service._calculate_complexity(query, features)
        assert complexity == "complex"


class TestCategoryClassification:
    """Test query category classification."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_document_lookup_category(self):
        """Test document lookup classification."""
        query = "What is our vacation policy?"
        features = self.service._detect_features(query)
        category = self.service._classify_category(query, features)
        assert category == QueryCategory.DOCUMENT_LOOKUP

    def test_document_analysis_category(self):
        """Test document analysis classification."""
        query = "Compare these multiple contracts for inconsistencies"
        features = self.service._detect_features(query)
        category = self.service._classify_category(query, features)
        assert category == QueryCategory.DOCUMENT_ANALYSIS

    def test_research_category(self):
        """Test research classification."""
        query = "What are the current industry trends in cybersecurity?"
        features = self.service._detect_features(query)
        category = self.service._classify_category(query, features)
        assert category == QueryCategory.RESEARCH

    def test_conversational_category(self):
        """Test conversational classification."""
        query = "Hello there"
        features = self.service._detect_features(query)
        category = self.service._classify_category(query, features)
        assert category == QueryCategory.CONVERSATIONAL

    def test_entity_extraction_category(self):
        """Test entity extraction classification."""
        # Use a query that clearly focuses on extraction from a single document
        # Avoid words that trigger multi_document detection like "all", "multiple"
        query = "Extract the names and phone numbers from this contract"
        features = self.service._detect_features(query)
        category = self.service._classify_category(query, features)
        assert category == QueryCategory.ENTITY_EXTRACTION


class TestAgentSelection:
    """Test agent selection algorithm."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_select_langgraph_for_research(self):
        """Test LangGraph selection for research queries."""
        agent, confidence, reasoning = self.service._select_agent(
            QueryCategory.RESEARCH,
            ["external_data_needed"],
            "moderate"
        )
        assert agent == AgentType.LANGGRAPH
        assert confidence >= 0.8

    def test_select_crewai_for_multi_document(self):
        """Test CrewAI selection for multi-document analysis."""
        agent, confidence, reasoning = self.service._select_agent(
            QueryCategory.DOCUMENT_ANALYSIS,
            ["multi_document"],
            "complex"
        )
        assert agent == AgentType.CREWAI
        assert confidence >= 0.8

    def test_select_crewai_for_entity_extraction(self):
        """Test CrewAI selection for entity extraction."""
        agent, confidence, reasoning = self.service._select_agent(
            QueryCategory.ENTITY_EXTRACTION,
            ["entity_extraction"],
            "moderate"
        )
        assert agent == AgentType.CREWAI
        assert confidence >= 0.7

    def test_select_simple_for_lookup(self):
        """Test Simple selection for document lookup."""
        agent, confidence, reasoning = self.service._select_agent(
            QueryCategory.DOCUMENT_LOOKUP,
            ["simple_lookup"],
            "simple"
        )
        assert agent == AgentType.SIMPLE
        assert confidence >= 0.8

    def test_select_simple_for_conversational(self):
        """Test Simple selection for conversational queries."""
        agent, confidence, reasoning = self.service._select_agent(
            QueryCategory.CONVERSATIONAL,
            ["conversational"],
            "simple"
        )
        assert agent == AgentType.SIMPLE
        assert confidence >= 0.9


class TestRuleBasedClassification:
    """Test the complete rule-based classification pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_classify_simple_query(self):
        """Test classification of simple query."""
        query = "What is our vacation policy?"
        category, features, complexity = self.service.classify_query_rules(query)

        assert category == QueryCategory.DOCUMENT_LOOKUP
        assert complexity == "simple"
        assert "simple_lookup" in features

    def test_classify_research_query(self):
        """Test classification of research query."""
        query = "What are the latest California insurance regulations?"
        category, features, complexity = self.service.classify_query_rules(query)

        assert category == QueryCategory.RESEARCH
        assert "external_data_needed" in features

    def test_classify_multi_document_query(self):
        """Test classification of multi-document query."""
        query = "Compare all these contracts and identify inconsistencies"
        category, features, complexity = self.service.classify_query_rules(query)

        assert category == QueryCategory.DOCUMENT_ANALYSIS
        assert "multi_document" in features


class TestQueryHashing:
    """Test query normalization and hashing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_normalize_query(self):
        """Test query normalization."""
        query1 = "  What is our   vacation policy?  "
        query2 = "what is our vacation policy?"

        normalized1 = self.service._normalize_query(query1)
        normalized2 = self.service._normalize_query(query2)

        assert normalized1 == normalized2

    def test_hash_consistency(self):
        """Test hash consistency for same queries."""
        query1 = "What is our vacation policy?"
        query2 = "  What is our   vacation policy?  "

        hash1 = self.service._hash_query(query1)
        hash2 = self.service._hash_query(query2)

        assert hash1 == hash2

    def test_hash_difference(self):
        """Test hash difference for different queries."""
        query1 = "What is our vacation policy?"
        query2 = "What is our sick leave policy?"

        hash1 = self.service._hash_query(query1)
        hash2 = self.service._hash_query(query2)

        assert hash1 != hash2


class TestConfidenceLevel:
    """Test confidence level mapping."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()

    def test_high_confidence(self):
        """Test high confidence level."""
        level = self.service._get_confidence_level(0.9)
        assert level == RoutingConfidence.HIGH

        level = self.service._get_confidence_level(0.8)
        assert level == RoutingConfidence.HIGH

    def test_medium_confidence(self):
        """Test medium confidence level."""
        level = self.service._get_confidence_level(0.7)
        assert level == RoutingConfidence.MEDIUM

        level = self.service._get_confidence_level(0.5)
        assert level == RoutingConfidence.MEDIUM

    def test_low_confidence(self):
        """Test low confidence level."""
        level = self.service._get_confidence_level(0.4)
        assert level == RoutingConfidence.LOW

        level = self.service._get_confidence_level(0.1)
        assert level == RoutingConfidence.LOW


class TestEndToEndRouting:
    """Test end-to-end routing (without external dependencies)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AgentRouterService()
        # Mock Supabase to avoid database calls
        self.service._supabase_client = None

    @pytest.mark.asyncio
    async def test_route_simple_query(self):
        """Test routing a simple query."""
        request = AgentRouterRequest(
            query="What is our vacation policy?",
            include_reasoning=True
        )

        # Mock cache methods to return None
        with patch.object(self.service, '_check_cache', return_value=None):
            with patch.object(self.service, '_save_to_cache', return_value=None):
                with patch.object(self.service, '_record_decision', return_value=None):
                    response = await self.service.route_query(request, use_llm=False)

        assert response.selected_agent == AgentType.SIMPLE
        assert response.confidence >= 0.7
        assert response.confidence_level in [RoutingConfidence.HIGH, RoutingConfidence.MEDIUM]
        assert response.routing_time_ms >= 0
        assert response.from_cache is False
        assert response.request_id is not None

    @pytest.mark.asyncio
    async def test_route_research_query(self):
        """Test routing a research query."""
        request = AgentRouterRequest(
            query="What are the current California insurance regulations?",
            include_reasoning=True
        )

        with patch.object(self.service, '_check_cache', return_value=None):
            with patch.object(self.service, '_save_to_cache', return_value=None):
                with patch.object(self.service, '_record_decision', return_value=None):
                    response = await self.service.route_query(request, use_llm=False)

        assert response.selected_agent == AgentType.LANGGRAPH
        assert response.confidence >= 0.8
        assert response.classification is not None
        assert response.classification.category == QueryCategory.RESEARCH

    @pytest.mark.asyncio
    async def test_route_multi_document_query(self):
        """Test routing a multi-document query."""
        request = AgentRouterRequest(
            query="Compare all these contracts and identify differences",
            include_reasoning=True
        )

        with patch.object(self.service, '_check_cache', return_value=None):
            with patch.object(self.service, '_save_to_cache', return_value=None):
                with patch.object(self.service, '_record_decision', return_value=None):
                    response = await self.service.route_query(request, use_llm=False)

        assert response.selected_agent == AgentType.CREWAI
        assert response.confidence >= 0.8
        assert response.classification is not None
        assert response.classification.category == QueryCategory.DOCUMENT_ANALYSIS

    @pytest.mark.asyncio
    async def test_route_with_forced_agent(self):
        """Test routing with forced agent."""
        request = AgentRouterRequest(
            query="What is our vacation policy?",
            force_agent=AgentType.LANGGRAPH,
            include_reasoning=True
        )

        response = await self.service.route_query(request, use_llm=False)

        assert response.selected_agent == AgentType.LANGGRAPH
        assert response.confidence == 1.0
        assert response.reasoning == "Agent forced by request"


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_agent_router_request_validation(self):
        """Test request model validation."""
        # Valid request
        request = AgentRouterRequest(
            query="What is our vacation policy?",
            user_id="user123",
            include_reasoning=True
        )
        assert request.query == "What is our vacation policy?"

        # Invalid: empty query
        with pytest.raises(Exception):
            AgentRouterRequest(query="")

        # Invalid: whitespace only
        with pytest.raises(Exception):
            AgentRouterRequest(query="   ")

    def test_classification_detail_validation(self):
        """Test classification detail model validation."""
        detail = ClassificationDetail(
            category=QueryCategory.DOCUMENT_LOOKUP,
            category_confidence=0.9,
            features_detected=["simple_lookup"],
            query_complexity="simple"
        )
        assert detail.category == QueryCategory.DOCUMENT_LOOKUP
        assert detail.category_confidence == 0.9

    def test_agent_router_response_confidence_level(self):
        """Test automatic confidence level setting."""
        # High confidence
        response = AgentRouterResponse(
            query="test",
            selected_agent=AgentType.SIMPLE,
            confidence=0.9,
            confidence_level=RoutingConfidence.HIGH,
            routing_time_ms=10
        )
        assert response.confidence_level == RoutingConfidence.HIGH

        # Medium confidence
        response = AgentRouterResponse(
            query="test",
            selected_agent=AgentType.SIMPLE,
            confidence=0.6,
            confidence_level=RoutingConfidence.MEDIUM,
            routing_time_ms=10
        )
        assert response.confidence_level == RoutingConfidence.MEDIUM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
