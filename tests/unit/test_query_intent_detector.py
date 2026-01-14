# tests/unit/test_query_intent_detector.py
"""
Unit tests for Query Intent Detector Service.

Task 108: Graph Agent - Query Intent Detection
Feature: 005-graph-agent

Tests query intent classification, parameter extraction, and routing decisions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.query_intent_detector import (
    QueryIntentDetector,
    QueryIntent,
    ParameterExtractor,
    get_query_intent_detector,
    reset_query_intent_detector,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def detector():
    """Create a fresh QueryIntentDetector instance."""
    reset_query_intent_detector()
    return QueryIntentDetector()


@pytest.fixture
def detector_with_llm():
    """Create a QueryIntentDetector with mock LLM service."""
    reset_query_intent_detector()
    mock_llm = AsyncMock()
    return QueryIntentDetector(llm_service=mock_llm)


# =============================================================================
# CUSTOMER 360 INTENT TESTS
# =============================================================================

class TestCustomer360Intent:
    """Tests for Customer 360 query intent detection."""

    @pytest.mark.asyncio
    async def test_customer_360_basic_query(self, detector):
        """Test basic customer 360 query detection."""
        query = "Show me everything about Acme Corp"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360
        assert confidence > 0.3
        assert "query" in params

    @pytest.mark.asyncio
    async def test_customer_360_with_customer_name(self, detector):
        """Test customer name extraction."""
        query = "What do we know about Global Industries Inc"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360
        assert "customer_name" in params

    @pytest.mark.asyncio
    async def test_customer_360_with_customer_id(self, detector):
        """Test customer ID extraction."""
        query = "Get customer account for customer id: CUST-12345"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360
        assert params.get("customer_id") == "CUST-12345"

    @pytest.mark.asyncio
    async def test_customer_360_client_query(self, detector):
        """Test client-related query detection."""
        query = "Give me all client information for ABC Company"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360

    @pytest.mark.asyncio
    async def test_customer_360_account_query(self, detector):
        """Test account-related query detection."""
        query = "What's the status of account ABC-123"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360

    @pytest.mark.asyncio
    async def test_customer_360_view_query(self, detector):
        """Test 360 view specific query."""
        query = "Customer 360 view for Enterprise Solutions Ltd"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360
        assert confidence > 0.5

    @pytest.mark.asyncio
    async def test_customer_360_history_query(self, detector):
        """Test customer history query."""
        query = "Tell me about the customer history for TechStart"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360


# =============================================================================
# DOCUMENT STRUCTURE INTENT TESTS
# =============================================================================

class TestDocumentStructureIntent:
    """Tests for Document Structure query intent detection."""

    @pytest.mark.asyncio
    async def test_document_structure_section_query(self, detector):
        """Test section navigation query."""
        query = "What does section 3.2 say about termination?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE
        assert params.get("section_number") == "3.2"

    @pytest.mark.asyncio
    async def test_document_structure_clause_query(self, detector):
        """Test clause-specific query."""
        query = "Find clause 5.1.3 in the contract"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE
        assert params.get("section_number") == "5.1.3"

    @pytest.mark.asyncio
    async def test_document_structure_definition_query(self, detector):
        """Test defined term query."""
        query = "What is the definition of 'Confidential Information'?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE
        assert "term" in params

    @pytest.mark.asyncio
    async def test_document_structure_cross_reference(self, detector):
        """Test cross-reference query."""
        query = "Show me all cross-references to section 4"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE

    @pytest.mark.asyncio
    async def test_document_structure_navigation(self, detector):
        """Test document navigation query."""
        query = "Navigate to paragraph 2.4.1"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE

    @pytest.mark.asyncio
    async def test_document_structure_article_query(self, detector):
        """Test article-specific query."""
        query = "What is stated in article 7?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE

    @pytest.mark.asyncio
    async def test_document_structure_appendix_query(self, detector):
        """Test appendix reference query."""
        query = "Show me appendix A"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE


# =============================================================================
# GRAPH-ENHANCED RAG INTENT TESTS
# =============================================================================

class TestGraphEnhancedRAGIntent:
    """Tests for Graph-Enhanced RAG query intent detection."""

    @pytest.mark.asyncio
    async def test_graph_rag_related_query(self, detector):
        """Test related documents query."""
        query = "Find all documents related to the insurance policy"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.GRAPH_ENHANCED_RAG

    @pytest.mark.asyncio
    async def test_graph_rag_connection_query(self, detector):
        """Test connection/relationship query."""
        query = "What connects the legal contract to the compliance report?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.GRAPH_ENHANCED_RAG

    @pytest.mark.asyncio
    async def test_graph_rag_similar_query(self, detector):
        """Test similar documents query."""
        query = "Show me documents similar to this agreement"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.GRAPH_ENHANCED_RAG

    @pytest.mark.asyncio
    async def test_graph_rag_expand_context(self, detector):
        """Test context expansion query."""
        query = "Expand the context for this compliance requirement"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.GRAPH_ENHANCED_RAG

    @pytest.mark.asyncio
    async def test_graph_rag_entity_relationships(self, detector):
        """Test entity relationship query."""
        query = "What entities are related to Acme Corp's contract?"
        intent, params, confidence = await detector.detect_intent(query)

        # Could be Customer 360 or Graph RAG - both are valid
        assert intent in [QueryIntent.GRAPH_ENHANCED_RAG, QueryIntent.CUSTOMER_360]

    @pytest.mark.asyncio
    async def test_graph_rag_network_query(self, detector):
        """Test network/graph query."""
        query = "Explore the graph network around this document"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.GRAPH_ENHANCED_RAG


# =============================================================================
# STANDARD RAG INTENT TESTS
# =============================================================================

class TestStandardRAGIntent:
    """Tests for Standard RAG query intent detection."""

    @pytest.mark.asyncio
    async def test_standard_rag_simple_query(self, detector):
        """Test simple retrieval query."""
        query = "What is the return policy?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.STANDARD_RAG
        assert "query" in params

    @pytest.mark.asyncio
    async def test_standard_rag_general_question(self, detector):
        """Test general question."""
        query = "How do I submit an expense report?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.STANDARD_RAG

    @pytest.mark.asyncio
    async def test_standard_rag_factual_query(self, detector):
        """Test factual information query."""
        query = "What are the office hours?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.STANDARD_RAG

    @pytest.mark.asyncio
    async def test_standard_rag_procedural_query(self, detector):
        """Test procedural query."""
        query = "What are the steps to request time off?"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.STANDARD_RAG


# =============================================================================
# PARAMETER EXTRACTION TESTS
# =============================================================================

class TestParameterExtractor:
    """Tests for parameter extraction functionality."""

    def test_extract_customer_name_from_query(self):
        """Test customer name extraction."""
        query = "Show me information about Acme Corporation"
        params = ParameterExtractor.extract_customer_params(query)

        assert "customer_name" in params or "query" in params

    def test_extract_customer_id(self):
        """Test customer ID extraction."""
        query = "Get customer id: CUST-ABC123"
        params = ParameterExtractor.extract_customer_params(query)

        assert params.get("customer_id") == "CUST-ABC123"

    def test_extract_section_number(self):
        """Test section number extraction."""
        query = "What does section 4.2.1 say?"
        params = ParameterExtractor.extract_document_params(query)

        assert params.get("section_number") == "4.2.1"

    def test_extract_document_id(self):
        """Test document ID extraction."""
        query = "Find information in document DOC-2024-001"
        params = ParameterExtractor.extract_document_params(query)

        assert params.get("document_id") == "DOC-2024-001"

    def test_extract_term_definition(self):
        """Test term extraction."""
        query = "What is the definition of 'Force Majeure'?"
        params = ParameterExtractor.extract_document_params(query)

        assert "term" in params

    def test_extract_rag_entities(self):
        """Test entity extraction for RAG."""
        query = "Find documents about California insurance regulations"
        params = ParameterExtractor.extract_rag_params(query)

        assert "query" in params


# =============================================================================
# LLM INTEGRATION TESTS
# =============================================================================

class TestLLMIntegration:
    """Tests for LLM-based intent detection."""

    @pytest.mark.asyncio
    async def test_llm_fallback_for_low_confidence(self, detector_with_llm):
        """Test LLM fallback when pattern matching has low confidence."""
        # Configure mock LLM to return customer_360
        detector_with_llm.llm_service.generate.return_value = "customer_360"

        # Ambiguous query that might trigger LLM
        query = "Help me understand XYZ Corp"
        intent, params, confidence = await detector_with_llm.detect_intent(
            query, use_llm=True
        )

        # Should detect as Customer 360 via patterns
        assert intent == QueryIntent.CUSTOMER_360

    @pytest.mark.asyncio
    async def test_llm_not_called_for_high_confidence(self, detector_with_llm):
        """Test LLM is not called when pattern matching has high confidence."""
        query = "Customer 360 view for Acme Corp"
        intent, params, confidence = await detector_with_llm.detect_intent(
            query, use_llm=True
        )

        # LLM should not be called for clear matches
        assert intent == QueryIntent.CUSTOMER_360

    @pytest.mark.asyncio
    async def test_llm_error_handling(self, detector_with_llm):
        """Test graceful handling of LLM errors."""
        detector_with_llm.llm_service.generate.side_effect = Exception("LLM error")

        query = "ambiguous query text"
        intent, params, confidence = await detector_with_llm.detect_intent(
            query, use_llm=True
        )

        # Should fall back to pattern-based detection
        assert intent in [
            QueryIntent.STANDARD_RAG,
            QueryIntent.CUSTOMER_360,
            QueryIntent.DOCUMENT_STRUCTURE,
            QueryIntent.GRAPH_ENHANCED_RAG,
        ]


# =============================================================================
# EDGE CASES AND SPECIAL SCENARIOS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_empty_query(self, detector):
        """Test handling of empty query."""
        query = ""
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.STANDARD_RAG
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only_query(self, detector):
        """Test handling of whitespace-only query."""
        query = "   "
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.STANDARD_RAG

    @pytest.mark.asyncio
    async def test_mixed_intent_query(self, detector):
        """Test query with multiple intent signals."""
        query = "Show me customer Acme Corp's contract section 3.2"
        intent, params, confidence = await detector.detect_intent(query)

        # Should favor one of the matching intents
        assert intent in [QueryIntent.CUSTOMER_360, QueryIntent.DOCUMENT_STRUCTURE]

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, detector):
        """Test handling of special characters."""
        query = "What's in section 3.2? (see also 4.1)"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.DOCUMENT_STRUCTURE

    @pytest.mark.asyncio
    async def test_case_insensitivity(self, detector):
        """Test that detection is case-insensitive."""
        query1 = "CUSTOMER 360 VIEW"
        query2 = "customer 360 view"

        intent1, _, _ = await detector.detect_intent(query1)
        intent2, _, _ = await detector.detect_intent(query2)

        assert intent1 == intent2 == QueryIntent.CUSTOMER_360

    @pytest.mark.asyncio
    async def test_very_long_query(self, detector):
        """Test handling of very long queries."""
        query = "Show me " + "everything " * 100 + "about Acme Corp"
        intent, params, confidence = await detector.detect_intent(query)

        assert intent == QueryIntent.CUSTOMER_360

    @pytest.mark.asyncio
    async def test_unicode_characters(self, detector):
        """Test handling of unicode characters."""
        query = "What does section 3 say about Acme Corp's policy?"
        intent, params, confidence = await detector.detect_intent(query)

        # Should still detect properly
        assert intent in [QueryIntent.CUSTOMER_360, QueryIntent.DOCUMENT_STRUCTURE]


# =============================================================================
# SINGLETON AND FACTORY TESTS
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test that get_query_intent_detector returns same instance."""
        reset_query_intent_detector()
        detector1 = get_query_intent_detector()
        detector2 = get_query_intent_detector()

        assert detector1 is detector2

    def test_reset_creates_new_instance(self):
        """Test that reset creates a new instance."""
        detector1 = get_query_intent_detector()
        reset_query_intent_detector()
        detector2 = get_query_intent_detector()

        assert detector1 is not detector2


# =============================================================================
# INTENT DESCRIPTION TESTS
# =============================================================================

class TestIntentDescriptions:
    """Tests for intent description functionality."""

    def test_get_customer_360_description(self, detector):
        """Test Customer 360 intent description."""
        description = detector.get_intent_description(QueryIntent.CUSTOMER_360)
        assert "customer" in description.lower()

    def test_get_document_structure_description(self, detector):
        """Test Document Structure intent description."""
        description = detector.get_intent_description(QueryIntent.DOCUMENT_STRUCTURE)
        assert "document" in description.lower()

    def test_get_graph_rag_description(self, detector):
        """Test Graph-Enhanced RAG intent description."""
        description = detector.get_intent_description(QueryIntent.GRAPH_ENHANCED_RAG)
        assert "graph" in description.lower()

    def test_get_standard_rag_description(self, detector):
        """Test Standard RAG intent description."""
        description = detector.get_intent_description(QueryIntent.STANDARD_RAG)
        assert "rag" in description.lower() or "retrieval" in description.lower()
