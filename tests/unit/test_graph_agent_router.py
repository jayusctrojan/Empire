"""
Unit tests for Graph Agent Router (Task 107).

Tests the FastAPI endpoints for Customer 360, Document Structure,
and Graph-Enhanced RAG functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routes.graph_agent import router
from app.models.graph_agent import (
    Customer360Request,
    Customer360Response,
    CustomerNode,
    DocumentStructureRequest,
    DocumentStructureResponse,
    SmartRetrievalRequest,
    SmartRetrievalResponse,
    GraphEnhancedRAGRequest,
    GraphEnhancedRAGResponse,
    GraphExpansionResult,
    SectionNode,
    CrossReference,
    ChunkNode,
    EntityNode,
    TraversalDepth,
)

# Create a test app with the router
app = FastAPI()
app.include_router(router)

client = TestClient(app)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_customer360_service():
    """Create a mock Customer360Service."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_document_structure_service():
    """Create a mock DocumentStructureService."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_graph_rag_service():
    """Create a mock GraphEnhancedRAGService."""
    service = AsyncMock()
    return service


@pytest.fixture
def sample_customer():
    """Sample customer data."""
    return CustomerNode(
        id="cust_001",
        name="Acme Corporation",
        type="enterprise",
        industry="Technology",
        properties={"region": "North America", "tier": "platinum"},
    )


@pytest.fixture
def sample_customer_response(sample_customer):
    """Sample Customer360Response."""
    from app.models.graph_agent import (
        DocumentNode,
        TicketNode,
        OrderNode,
        InteractionNode,
        InteractionType,
    )

    return Customer360Response(
        customer=sample_customer,
        documents=[
            DocumentNode(
                id="doc1",
                title="Contract",
                type="contract",
            )
        ],
        tickets=[
            TicketNode(
                id="tick1",
                customer_id="cust_001",
                subject="Support request",
            )
        ],
        orders=[
            OrderNode(
                id="ord1",
                customer_id="cust_001",
                total_amount=10000,
            )
        ],
        interactions=[
            InteractionNode(
                id="int1",
                customer_id="cust_001",
                type=InteractionType.CALL,
            )
        ],
        relationship_count=4,
    )


@pytest.fixture
def sample_section():
    """Sample section node."""
    return SectionNode(
        id="sec_001",
        document_id="doc_001",
        number="1.1",
        title="Introduction",
        content="This is the introduction section.",
        level=2,
        parent_id="sec_000",
    )


@pytest.fixture
def sample_document_structure_response(sample_section):
    """Sample DocumentStructureResponse."""
    return DocumentStructureResponse(
        document_id="doc_001",
        title="Sample Contract",
        sections=[sample_section],
        definitions=[],
        cross_references=[],
        citations=[],
        total_sections=1,
        extracted_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_smart_retrieval_response(sample_section):
    """Sample SmartRetrievalResponse."""
    return SmartRetrievalResponse(
        sections=[sample_section],
        parent_context=[],
        cross_referenced_sections=[],
        relevant_definitions=[],
        breadcrumb=["doc_001", "Introduction"],
    )


@pytest.fixture
def sample_chunk():
    """Sample chunk node."""
    return ChunkNode(
        id="chunk_001",
        document_id="doc_001",
        content="This is sample text from a document about Acme Corp.",
        position=0,
    )


@pytest.fixture
def sample_graph_expansion_result(sample_chunk):
    """Sample GraphExpansionResult."""
    return GraphExpansionResult(
        original_chunks=[sample_chunk],
        expanded_chunks=[],
        extracted_entities=[],
        related_entities=[],
        entity_relationships=[],
        relationship_paths=[],
        expansion_method="entity_expansion",
    )


@pytest.fixture
def sample_graph_rag_response(sample_chunk, sample_graph_expansion_result):
    """Sample GraphEnhancedRAGResponse."""
    return GraphEnhancedRAGResponse(
        query="Tell me about Acme Corp",
        answer="Acme Corp is a technology company...",
        original_chunks=[sample_chunk],
        graph_context=sample_graph_expansion_result,
        sources=[{"id": "doc_001", "title": "Contract"}],
        graph_enhanced=True,
        latency_ms=200.0,
    )


# =============================================================================
# CUSTOMER 360 ENDPOINT TESTS
# =============================================================================

class TestCustomer360Endpoints:
    """Tests for Customer 360 endpoints."""

    @patch("app.routes.graph_agent.get_customer360_service")
    def test_query_customer_success(self, mock_get_service, sample_customer_response):
        """Test successful customer query."""
        mock_service = AsyncMock()
        mock_service.process_customer_query.return_value = sample_customer_response
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/customer360/query",
            json={"query": "Show me Acme Corp"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer"]["name"] == "Acme Corporation"
        assert "documents" in data
        assert "tickets" in data

    @patch("app.routes.graph_agent.get_customer360_service")
    def test_query_customer_error(self, mock_get_service):
        """Test customer query error handling."""
        mock_service = AsyncMock()
        mock_service.process_customer_query.side_effect = Exception("Database error")
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/customer360/query",
            json={"query": "Show me Acme Corp"},
        )

        assert response.status_code == 500
        assert "Customer 360 query failed" in response.json()["detail"]

    @patch("app.routes.graph_agent.get_customer360_service")
    def test_get_customer_success(self, mock_get_service, sample_customer_response):
        """Test successful customer retrieval by ID."""
        mock_service = AsyncMock()
        mock_service.get_customer_360.return_value = sample_customer_response
        mock_get_service.return_value = mock_service

        response = client.get("/api/graph/customer360/cust_001")

        assert response.status_code == 200
        data = response.json()
        assert data["customer"]["id"] == "cust_001"

    @patch("app.routes.graph_agent.get_customer360_service")
    def test_get_customer_not_found(self, mock_get_service):
        """Test customer not found."""
        from app.services.customer360_service import CustomerNotFoundError

        mock_service = AsyncMock()
        mock_service.get_customer_360.side_effect = CustomerNotFoundError(
            "Customer nonexistent not found"
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/graph/customer360/nonexistent")

        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    @patch("app.routes.graph_agent.get_customer360_service")
    def test_get_customer_with_filters(self, mock_get_service, sample_customer_response):
        """Test customer retrieval with filters."""
        mock_service = AsyncMock()
        mock_service.get_customer_360.return_value = sample_customer_response
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/graph/customer360/cust_001",
            params={
                "include_documents": True,
                "include_tickets": False,
                "include_orders": True,
                "include_interactions": False,
                "max_items": 100,
            },
        )

        assert response.status_code == 200
        mock_service.get_customer_360.assert_called_once_with(
            customer_id="cust_001",
            include_documents=True,
            include_tickets=False,
            include_orders=True,
            include_interactions=False,
            max_items=100,
        )

    @patch("app.routes.graph_agent.get_customer360_service")
    def test_find_similar_customers(self, mock_get_service, sample_customer):
        """Test finding similar customers."""
        mock_service = AsyncMock()
        mock_service.find_similar_customers.return_value = [sample_customer]
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/graph/customer360/similar/cust_001",
            params={"limit": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Acme Corporation"


# =============================================================================
# DOCUMENT STRUCTURE ENDPOINT TESTS
# =============================================================================

class TestDocumentStructureEndpoints:
    """Tests for Document Structure endpoints."""

    @patch("app.routes.graph_agent.get_document_structure_service")
    def test_extract_document_structure(
        self, mock_get_service, sample_document_structure_response
    ):
        """Test document structure extraction."""
        mock_service = AsyncMock()
        mock_service.extract_document_structure.return_value = (
            sample_document_structure_response
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/document-structure/extract",
            json={
                "document_id": "doc_001",
                "extract_cross_refs": True,
                "extract_definitions": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc_001"
        assert len(data["sections"]) == 1

    @patch("app.routes.graph_agent.get_document_structure_service")
    def test_get_document_structure(
        self, mock_get_service, sample_document_structure_response
    ):
        """Test getting document structure."""
        mock_service = AsyncMock()
        mock_service.get_document_structure.return_value = (
            sample_document_structure_response
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/graph/document-structure/doc_001")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc_001"

    @patch("app.routes.graph_agent.get_document_structure_service")
    def test_smart_retrieve(self, mock_get_service, sample_smart_retrieval_response):
        """Test smart document retrieval."""
        mock_service = AsyncMock()
        mock_service.smart_retrieve.return_value = sample_smart_retrieval_response
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/document-structure/smart-retrieve",
            json={
                "document_id": "doc_001",
                "query": "What is in the introduction?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sections"]) == 1
        assert "breadcrumb" in data

    @patch("app.routes.graph_agent.get_document_structure_service")
    def test_get_cross_references(self, mock_get_service):
        """Test getting cross-references."""
        mock_service = AsyncMock()
        mock_service.get_cross_references.return_value = [
            CrossReference(
                from_section_id="sec_001",
                from_section_number="1.1",
                to_section_id="sec_002",
                to_section_number="2.0",
                reference_text="See Section 2",
            )
        ]
        mock_get_service.return_value = mock_service

        response = client.get("/api/graph/document-structure/doc_001/cross-refs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["reference_text"] == "See Section 2"

    @patch("app.routes.graph_agent.get_document_structure_service")
    def test_get_cross_references_with_section_filter(self, mock_get_service):
        """Test getting cross-references with section filter."""
        mock_service = AsyncMock()
        mock_service.get_cross_references.return_value = []
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/graph/document-structure/doc_001/cross-refs",
            params={"section_id": "sec_001"},
        )

        assert response.status_code == 200
        mock_service.get_cross_references.assert_called_once_with(
            document_id="doc_001",
            section_id="sec_001",
        )


# =============================================================================
# GRAPH-ENHANCED RAG ENDPOINT TESTS
# =============================================================================

class TestGraphEnhancedRAGEndpoints:
    """Tests for Graph-Enhanced RAG endpoints."""

    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_graph_enhanced_query(self, mock_get_service, sample_graph_rag_response):
        """Test graph-enhanced RAG query."""
        mock_service = AsyncMock()
        mock_service.query.return_value = sample_graph_rag_response
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/enhanced-rag/query",
            json={
                "query": "Tell me about Acme Corp",
                "expansion_depth": "medium",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Tell me about Acme Corp"
        assert data["graph_enhanced"] is True

    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_graph_enhanced_query_with_chunk_ids(
        self, mock_get_service, sample_graph_rag_response
    ):
        """Test graph-enhanced RAG query with chunk IDs."""
        mock_service = AsyncMock()
        mock_service.query.return_value = sample_graph_rag_response
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/enhanced-rag/query",
            json={
                "query": "Tell me about Acme Corp",
                "chunk_ids": ["chunk_001", "chunk_002"],
                "expansion_depth": "shallow",
            },
        )

        assert response.status_code == 200

    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_expand_results(self, mock_get_service, sample_graph_expansion_result):
        """Test expanding results with graph context."""
        mock_service = AsyncMock()
        mock_service.expand_results.return_value = sample_graph_expansion_result
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/enhanced-rag/expand",
            json=[
                {
                    "id": "chunk_001",
                    "text": "Sample text",
                    "source": "doc_001",
                }
            ],
            params={"expansion_depth": "medium"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "original_chunks" in data
        assert "extracted_entities" in data

    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_get_entity_related_success(self, mock_get_service):
        """Test getting entity context."""
        mock_service = AsyncMock()
        mock_service.get_entity_context.return_value = {
            "entity": {"id": "ent_001", "name": "Acme Corp"},
            "neighbors": [{"id": "ent_002", "name": "Related Entity"}],
            "chunks": [],
        }
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/graph/enhanced-rag/entities/ent_001/related",
            params={"depth": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["entity"]["name"] == "Acme Corp"
        assert len(data["neighbors"]) == 1

    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_get_entity_related_not_found(self, mock_get_service):
        """Test entity not found."""
        mock_service = AsyncMock()
        mock_service.get_entity_context.return_value = {
            "entity": None,
            "neighbors": [],
            "chunks": [],
        }
        mock_get_service.return_value = mock_service

        response = client.get("/api/graph/enhanced-rag/entities/nonexistent/related")

        assert response.status_code == 404
        assert "Entity not found" in response.json()["detail"]

    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_get_query_context(self, mock_get_service, sample_graph_expansion_result):
        """Test getting graph context for a query."""
        mock_service = AsyncMock()
        mock_service.expand_results.return_value = sample_graph_expansion_result
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/enhanced-rag/context",
            json={
                "query": "What is Acme Corp's policy?",
                "depth": "shallow",
            },
        )

        assert response.status_code == 200


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestHealthCheck:
    """Tests for health check endpoint."""

    @patch("app.routes.graph_agent.get_customer360_service")
    @patch("app.routes.graph_agent.get_document_structure_service")
    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_health_check_all_healthy(
        self,
        mock_graph_rag,
        mock_doc_structure,
        mock_customer360,
    ):
        """Test health check when all services are healthy."""
        mock_customer360.return_value = MagicMock()
        mock_doc_structure.return_value = MagicMock()
        mock_graph_rag.return_value = MagicMock()

        response = client.get("/api/graph/agent/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["customer360"]["status"] == "healthy"
        assert data["services"]["document_structure"]["status"] == "healthy"
        assert data["services"]["graph_enhanced_rag"]["status"] == "healthy"

    @patch("app.routes.graph_agent.get_customer360_service")
    @patch("app.routes.graph_agent.get_document_structure_service")
    @patch("app.routes.graph_agent.get_graph_enhanced_rag_service")
    def test_health_check_degraded(
        self,
        mock_graph_rag,
        mock_doc_structure,
        mock_customer360,
    ):
        """Test health check when a service is unhealthy."""
        mock_customer360.side_effect = Exception("Service error")
        mock_doc_structure.return_value = MagicMock()
        mock_graph_rag.return_value = MagicMock()

        response = client.get("/api/graph/agent/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["customer360"]["status"] == "unhealthy"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_request_body(self):
        """Test handling of invalid request body."""
        response = client.post(
            "/api/graph/customer360/query",
            json={},  # Missing required query field
        )

        # FastAPI returns 422 for Pydantic validation errors
        assert response.status_code == 422

    def test_invalid_expansion_depth(self):
        """Test handling of invalid expansion depth."""
        response = client.post(
            "/api/graph/enhanced-rag/query",
            json={
                "query": "Test query",
                "expansion_depth": "invalid_depth",
            },
        )

        # FastAPI returns 422 for Pydantic validation errors
        assert response.status_code == 422

    @patch("app.routes.graph_agent.get_document_structure_service")
    def test_service_exception_handling(self, mock_get_service):
        """Test that service exceptions are properly caught."""
        mock_service = AsyncMock()
        mock_service.extract_document_structure.side_effect = RuntimeError("Unexpected error")
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/graph/document-structure/extract",
            json={"document_id": "doc_001"},
        )

        assert response.status_code == 500
        assert "Failed to extract document structure" in response.json()["detail"]
