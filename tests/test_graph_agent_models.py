# tests/test_graph_agent_models.py
"""
Unit tests for Graph Agent Pydantic Models.

Task 103: Graph Agent - Pydantic Models
Feature: 005-graph-agent

Tests model validation, serialization, and schema correctness.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.graph_agent import (
    # Enums
    QueryType,
    TraversalDepth,
    CustomerType,
    TicketStatus,
    TicketPriority,
    InteractionType,
    OrderStatus,
    EntityType,
    # Customer 360 Models
    CustomerNode,
    TicketNode,
    OrderNode,
    InteractionNode,
    ProductNode,
    DocumentNode,
    SimilarCustomer,
    Customer360Request,
    Customer360Response,
    # Document Structure Models
    SectionNode,
    DefinedTermNode,
    CrossReference,
    CitationNode,
    DocumentStructureRequest,
    DocumentStructureResponse,
    SmartRetrievalRequest,
    SmartRetrievalResponse,
    # Graph-Enhanced RAG Models
    EntityNode,
    ChunkNode,
    EntityRelationship,
    GraphEnhancedRAGRequest,
    GraphExpansionResult,
    GraphEnhancedRAGResponse,
    # Health and Status Models
    GraphAgentHealth,
    GraphQueryMetrics,
    # Intent Detection Models
    QueryIntent,
    IntentDetectionRequest,
    IntentDetectionResponse,
)


class TestEnums:
    """Test enum definitions."""

    def test_query_type_values(self):
        """Test QueryType enum values."""
        assert QueryType.CUSTOMER_360 == "customer_360"
        assert QueryType.DOCUMENT_STRUCTURE == "document_structure"
        assert QueryType.GRAPH_ENHANCED_RAG == "graph_enhanced_rag"
        assert QueryType.ENTITY_LOOKUP == "entity_lookup"

    def test_traversal_depth_values(self):
        """Test TraversalDepth enum values."""
        assert TraversalDepth.SHALLOW == "shallow"
        assert TraversalDepth.MEDIUM == "medium"
        assert TraversalDepth.DEEP == "deep"

    def test_customer_type_values(self):
        """Test CustomerType enum values."""
        assert CustomerType.ENTERPRISE == "enterprise"
        assert CustomerType.SMB == "smb"
        assert CustomerType.INDIVIDUAL == "individual"
        assert CustomerType.UNKNOWN == "unknown"

    def test_ticket_status_values(self):
        """Test TicketStatus enum values."""
        assert TicketStatus.OPEN == "open"
        assert TicketStatus.IN_PROGRESS == "in_progress"
        assert TicketStatus.RESOLVED == "resolved"
        assert TicketStatus.CLOSED == "closed"

    def test_entity_type_values(self):
        """Test EntityType enum values."""
        assert EntityType.PERSON == "person"
        assert EntityType.ORGANIZATION == "organization"
        assert EntityType.LOCATION == "location"
        assert EntityType.CONCEPT == "concept"


class TestCustomerNode:
    """Test CustomerNode model."""

    def test_valid_customer_node(self):
        """Test creating a valid CustomerNode."""
        customer = CustomerNode(
            id="cust_123",
            name="Acme Corp",
            type=CustomerType.ENTERPRISE,
            industry="Technology"
        )

        assert customer.id == "cust_123"
        assert customer.name == "Acme Corp"
        assert customer.type == CustomerType.ENTERPRISE
        assert customer.industry == "Technology"

    def test_customer_node_defaults(self):
        """Test CustomerNode default values."""
        customer = CustomerNode(id="cust_456", name="Test Company")

        assert customer.type == CustomerType.UNKNOWN
        assert customer.industry is None
        assert customer.metadata == {}

    def test_customer_node_serialization(self):
        """Test CustomerNode JSON serialization."""
        customer = CustomerNode(
            id="cust_789",
            name="BigCorp Inc",
            type=CustomerType.SMB,
            metadata={"source": "CRM"}
        )

        data = customer.model_dump()

        assert data["id"] == "cust_789"
        assert data["name"] == "BigCorp Inc"
        assert data["type"] == "smb"
        assert data["metadata"] == {"source": "CRM"}

    def test_customer_node_missing_required_fields(self):
        """Test CustomerNode validation with missing fields."""
        with pytest.raises(ValidationError) as exc_info:
            CustomerNode(id="cust_001")  # Missing name

        assert "name" in str(exc_info.value)


class TestTicketNode:
    """Test TicketNode model."""

    def test_valid_ticket_node(self):
        """Test creating a valid TicketNode."""
        ticket = TicketNode(
            id="ticket_001",
            customer_id="cust_123",
            subject="Login Issue",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH
        )

        assert ticket.id == "ticket_001"
        assert ticket.customer_id == "cust_123"
        assert ticket.status == TicketStatus.OPEN
        assert ticket.priority == TicketPriority.HIGH

    def test_ticket_node_defaults(self):
        """Test TicketNode default values."""
        ticket = TicketNode(
            id="ticket_002",
            customer_id="cust_456",
            subject="Question"
        )

        assert ticket.status == TicketStatus.OPEN
        assert ticket.priority == TicketPriority.MEDIUM


class TestCustomer360Request:
    """Test Customer360Request model."""

    def test_request_with_query(self):
        """Test request with natural language query."""
        request = Customer360Request(query="Show me Acme Corp")

        assert request.query == "Show me Acme Corp"
        assert request.customer_id is None
        assert request.include_documents is True
        assert request.max_items_per_category == 10

    def test_request_with_customer_id(self):
        """Test request with direct customer ID."""
        request = Customer360Request(customer_id="cust_123")

        assert request.customer_id == "cust_123"
        assert request.query is None

    def test_request_custom_options(self):
        """Test request with custom options."""
        request = Customer360Request(
            customer_id="cust_456",
            include_documents=False,
            include_tickets=True,
            include_orders=False,
            include_interactions=False,
            max_items_per_category=25,
            traversal_depth=TraversalDepth.DEEP
        )

        assert request.include_documents is False
        assert request.include_tickets is True
        assert request.max_items_per_category == 25
        assert request.traversal_depth == TraversalDepth.DEEP

    def test_request_max_items_validation(self):
        """Test max_items_per_category validation."""
        with pytest.raises(ValidationError):
            Customer360Request(customer_id="cust_123", max_items_per_category=0)

        with pytest.raises(ValidationError):
            Customer360Request(customer_id="cust_123", max_items_per_category=101)


class TestCustomer360Response:
    """Test Customer360Response model."""

    def test_valid_response(self):
        """Test creating a valid response."""
        customer = CustomerNode(id="cust_001", name="Test Corp")
        response = Customer360Response(
            customer=customer,
            relationship_count=5,
            summary="Test Corp is an enterprise customer."
        )

        assert response.customer.id == "cust_001"
        assert response.relationship_count == 5
        assert response.summary == "Test Corp is an enterprise customer."
        assert response.documents == []
        assert response.tickets == []

    def test_response_with_related_data(self):
        """Test response with related entities."""
        customer = CustomerNode(id="cust_002", name="Big Corp")
        ticket = TicketNode(
            id="ticket_001",
            customer_id="cust_002",
            subject="Issue"
        )
        document = DocumentNode(id="doc_001", title="Contract")

        response = Customer360Response(
            customer=customer,
            tickets=[ticket],
            documents=[document]
        )

        assert len(response.tickets) == 1
        assert len(response.documents) == 1
        assert response.tickets[0].id == "ticket_001"

    def test_response_generated_at_default(self):
        """Test generated_at has default value."""
        customer = CustomerNode(id="cust_003", name="Corp")
        response = Customer360Response(customer=customer)

        assert response.generated_at is not None
        assert isinstance(response.generated_at, datetime)


class TestSectionNode:
    """Test SectionNode model."""

    def test_valid_section_node(self):
        """Test creating a valid SectionNode."""
        section = SectionNode(
            id="sec_001",
            title="Introduction",
            number="1",
            level=1
        )

        assert section.id == "sec_001"
        assert section.title == "Introduction"
        assert section.number == "1"
        assert section.level == 1

    def test_section_node_with_children(self):
        """Test SectionNode with child/reference counts."""
        section = SectionNode(
            id="sec_002",
            document_id="doc_001",
            title="Definitions",
            number="2",
            level=1,
            child_count=5,
            reference_count=3
        )

        assert section.child_count == 5
        assert section.reference_count == 3

    def test_section_level_validation(self):
        """Test section level must be >= 1."""
        with pytest.raises(ValidationError):
            SectionNode(
                id="sec_003",
                title="Bad Section",
                number="0",
                level=0  # Invalid
            )


class TestDefinedTermNode:
    """Test DefinedTermNode model."""

    def test_valid_defined_term(self):
        """Test creating a valid DefinedTermNode."""
        term = DefinedTermNode(
            id="term_001",
            document_id="doc_001",
            term="Party",
            definition="Any individual or entity that is a signatory to this Agreement."
        )

        assert term.term == "Party"
        assert "signatory" in term.definition

    def test_defined_term_usage_count(self):
        """Test usage_count field."""
        term = DefinedTermNode(
            id="term_002",
            document_id="doc_001",
            term="Confidential Information",
            definition="All non-public information...",
            usage_count=15
        )

        assert term.usage_count == 15


class TestCrossReference:
    """Test CrossReference model."""

    def test_valid_cross_reference(self):
        """Test creating a valid CrossReference."""
        ref = CrossReference(
            from_section_id="sec_001",
            from_section_number="1.2",
            to_section_id="sec_005",
            to_section_number="5.1",
            reference_text="See Section 5.1"
        )

        assert ref.from_section_number == "1.2"
        assert ref.to_section_number == "5.1"
        assert "Section 5.1" in ref.reference_text


class TestDocumentStructureRequest:
    """Test DocumentStructureRequest model."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = DocumentStructureRequest(document_id="doc_001")

        assert request.document_id == "doc_001"
        assert request.extract_sections is True
        assert request.extract_cross_refs is True
        assert request.extract_definitions is True
        assert request.max_depth == 5

    def test_request_custom_options(self):
        """Test request with custom options."""
        request = DocumentStructureRequest(
            document_id="doc_002",
            extract_cross_refs=False,
            max_depth=3
        )

        assert request.extract_cross_refs is False
        assert request.max_depth == 3

    def test_max_depth_validation(self):
        """Test max_depth validation bounds."""
        with pytest.raises(ValidationError):
            DocumentStructureRequest(document_id="doc_003", max_depth=0)

        with pytest.raises(ValidationError):
            DocumentStructureRequest(document_id="doc_004", max_depth=11)


class TestEntityNode:
    """Test EntityNode model."""

    def test_valid_entity_node(self):
        """Test creating a valid EntityNode."""
        entity = EntityNode(
            id="ent_001",
            name="John Smith",
            type=EntityType.PERSON
        )

        assert entity.name == "John Smith"
        assert entity.type == EntityType.PERSON
        assert entity.confidence == 1.0

    def test_entity_with_aliases(self):
        """Test EntityNode with aliases."""
        entity = EntityNode(
            id="ent_002",
            name="Acme Corporation",
            type=EntityType.ORGANIZATION,
            aliases=["Acme Corp", "ACME", "Acme Inc"]
        )

        assert len(entity.aliases) == 3
        assert "Acme Corp" in entity.aliases

    def test_confidence_validation(self):
        """Test confidence score validation."""
        with pytest.raises(ValidationError):
            EntityNode(
                id="ent_003",
                name="Invalid",
                type=EntityType.OTHER,
                confidence=1.5  # Invalid - must be <= 1.0
            )


class TestChunkNode:
    """Test ChunkNode model."""

    def test_valid_chunk_node(self):
        """Test creating a valid ChunkNode."""
        chunk = ChunkNode(
            id="chunk_001",
            document_id="doc_001",
            content="This is the chunk content.",
            position=0
        )

        assert chunk.content == "This is the chunk content."
        assert chunk.position == 0

    def test_chunk_position_validation(self):
        """Test position must be >= 0."""
        with pytest.raises(ValidationError):
            ChunkNode(
                id="chunk_002",
                document_id="doc_001",
                content="Content",
                position=-1  # Invalid
            )


class TestGraphEnhancedRAGRequest:
    """Test GraphEnhancedRAGRequest model."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = GraphEnhancedRAGRequest(query="What is the policy?")

        assert request.query == "What is the policy?"
        assert request.expansion_depth == TraversalDepth.MEDIUM
        assert request.max_expanded_chunks == 10

    def test_request_with_chunks(self):
        """Test request with pre-retrieved chunks."""
        request = GraphEnhancedRAGRequest(
            query="Related documents",
            chunk_ids=["chunk_001", "chunk_002"],
            expansion_depth=TraversalDepth.DEEP
        )

        assert len(request.chunk_ids) == 2
        assert request.expansion_depth == TraversalDepth.DEEP

    def test_max_expanded_chunks_validation(self):
        """Test max_expanded_chunks bounds."""
        with pytest.raises(ValidationError):
            GraphEnhancedRAGRequest(query="test", max_expanded_chunks=0)

        with pytest.raises(ValidationError):
            GraphEnhancedRAGRequest(query="test", max_expanded_chunks=51)


class TestGraphExpansionResult:
    """Test GraphExpansionResult model."""

    def test_empty_expansion_result(self):
        """Test empty expansion result."""
        result = GraphExpansionResult()

        assert result.original_chunks == []
        assert result.expanded_chunks == []
        assert result.extracted_entities == []
        assert result.expansion_method == "entity_expansion"

    def test_expansion_with_data(self):
        """Test expansion result with data."""
        chunk = ChunkNode(
            id="chunk_001",
            document_id="doc_001",
            content="Content",
            position=0
        )
        entity = EntityNode(
            id="ent_001",
            name="Policy",
            type=EntityType.CONCEPT
        )

        result = GraphExpansionResult(
            original_chunks=[chunk],
            extracted_entities=[entity],
            relationship_paths=[["chunk_001", "CONTAINS", "ent_001"]]
        )

        assert len(result.original_chunks) == 1
        assert len(result.extracted_entities) == 1
        assert len(result.relationship_paths) == 1


class TestGraphAgentHealth:
    """Test GraphAgentHealth model."""

    def test_healthy_status(self):
        """Test healthy status."""
        health = GraphAgentHealth(
            neo4j_connected=True,
            cache_connected=True
        )

        assert health.neo4j_connected is True
        assert health.cache_connected is True
        assert health.customer_360_available is True

    def test_unhealthy_status(self):
        """Test unhealthy status."""
        health = GraphAgentHealth(
            neo4j_connected=False,
            customer_360_available=False,
            document_structure_available=False,
            graph_enhanced_rag_available=False
        )

        assert health.neo4j_connected is False
        assert health.customer_360_available is False


class TestQueryIntent:
    """Test QueryIntent model."""

    def test_valid_intent(self):
        """Test creating a valid QueryIntent."""
        intent = QueryIntent(
            query_type=QueryType.CUSTOMER_360,
            confidence=0.95,
            extracted_customer="Acme Corp"
        )

        assert intent.query_type == QueryType.CUSTOMER_360
        assert intent.confidence == 0.95
        assert intent.extracted_customer == "Acme Corp"

    def test_intent_confidence_validation(self):
        """Test confidence bounds."""
        with pytest.raises(ValidationError):
            QueryIntent(
                query_type=QueryType.ENTITY_LOOKUP,
                confidence=1.5  # Invalid
            )


class TestIntentDetectionRequest:
    """Test IntentDetectionRequest model."""

    def test_valid_request(self):
        """Test creating a valid request."""
        request = IntentDetectionRequest(query="Show me customer data for Acme")

        assert request.query == "Show me customer data for Acme"
        assert request.conversation_context is None

    def test_request_with_context(self):
        """Test request with conversation context."""
        request = IntentDetectionRequest(
            query="What about their tickets?",
            conversation_context=[
                {"role": "user", "content": "Tell me about Acme Corp"},
                {"role": "assistant", "content": "Acme Corp is an enterprise customer..."}
            ]
        )

        assert len(request.conversation_context) == 2

    def test_empty_query_validation(self):
        """Test empty query validation."""
        with pytest.raises(ValidationError):
            IntentDetectionRequest(query="")


class TestModelSerialization:
    """Test JSON serialization of all models."""

    def test_customer360_response_serialization(self):
        """Test full Customer360Response serialization."""
        response = Customer360Response(
            customer=CustomerNode(
                id="cust_001",
                name="Test Corp",
                type=CustomerType.ENTERPRISE
            ),
            tickets=[
                TicketNode(
                    id="ticket_001",
                    customer_id="cust_001",
                    subject="Issue"
                )
            ],
            summary="Test Corp has 1 ticket."
        )

        data = response.model_dump()

        assert data["customer"]["id"] == "cust_001"
        assert len(data["tickets"]) == 1
        assert data["summary"] == "Test Corp has 1 ticket."

    def test_document_structure_response_serialization(self):
        """Test DocumentStructureResponse serialization."""
        response = DocumentStructureResponse(
            document_id="doc_001",
            title="Sample Contract",
            sections=[
                SectionNode(
                    id="sec_001",
                    title="Introduction",
                    number="1",
                    level=1
                )
            ],
            structure_depth=3
        )

        data = response.model_dump()

        assert data["document_id"] == "doc_001"
        assert len(data["sections"]) == 1
        assert data["structure_depth"] == 3

    def test_graph_enhanced_rag_response_serialization(self):
        """Test GraphEnhancedRAGResponse serialization."""
        expansion = GraphExpansionResult(expansion_method="entity_expansion")
        response = GraphEnhancedRAGResponse(
            query="What is the policy?",
            answer="The policy states...",
            graph_context=expansion,
            graph_enhanced=True
        )

        data = response.model_dump()

        assert data["query"] == "What is the policy?"
        assert data["answer"] == "The policy states..."
        assert data["graph_enhanced"] is True
        assert "graph_context" in data
