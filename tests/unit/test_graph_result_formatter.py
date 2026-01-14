# tests/unit/test_graph_result_formatter.py
"""
Unit tests for Graph Result Formatter Service.

Task 109: Graph Agent - Graph Result Formatter
Feature: 005-graph-agent

Tests formatting of graph query results for the CKO Chat UI.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.services.graph_result_formatter import (
    GraphResultFormatter,
    OutputFormat,
    SectionType,
    FormattedSection,
    get_graph_result_formatter,
    reset_graph_result_formatter,
)
from app.models.graph_agent import (
    Customer360Response,
    CustomerNode,
    CustomerType,
    DocumentNode,
    TicketNode,
    TicketStatus,
    TicketPriority,
    OrderNode,
    OrderStatus,
    InteractionNode,
    InteractionType,
    DocumentStructureResponse,
    SectionNode,
    DefinedTermNode,
    CrossReference,
    SmartRetrievalResponse,
    GraphEnhancedRAGResponse,
    GraphExpansionResult,
    ChunkNode,
    EntityNode,
    EntityType,
    EntityRelationship,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def formatter():
    """Create a GraphResultFormatter instance."""
    reset_graph_result_formatter()
    return GraphResultFormatter()


@pytest.fixture
def sample_customer():
    """Create a sample CustomerNode."""
    return CustomerNode(
        id="cust_001",
        name="Acme Corporation",
        type=CustomerType.ENTERPRISE,
        industry="Technology",
        created_at=datetime(2024, 1, 15),
    )


@pytest.fixture
def sample_customer_360_response(sample_customer):
    """Create a sample Customer360Response."""
    return Customer360Response(
        customer=sample_customer,
        documents=[
            DocumentNode(id="doc1", title="Contract 2024", type="contract"),
            DocumentNode(id="doc2", title="NDA", type="legal"),
        ],
        tickets=[
            TicketNode(
                id="tick1",
                customer_id="cust_001",
                subject="Support request",
                status=TicketStatus.OPEN,
                priority=TicketPriority.HIGH,
            ),
        ],
        orders=[
            OrderNode(
                id="ord1",
                customer_id="cust_001",
                total_amount=50000,
                status=OrderStatus.COMPLETED,
            ),
        ],
        interactions=[
            InteractionNode(
                id="int1",
                customer_id="cust_001",
                type=InteractionType.CALL,
                summary="Sales call",
            ),
        ],
        relationship_count=5,
    )


@pytest.fixture
def sample_document_structure_response():
    """Create a sample DocumentStructureResponse."""
    return DocumentStructureResponse(
        document_id="doc_001",
        title="Master Services Agreement",
        sections=[
            SectionNode(
                id="sec1",
                document_id="doc_001",
                number="1",
                title="Definitions",
                level=1,
                content_preview="This section contains definitions...",
            ),
            SectionNode(
                id="sec2",
                document_id="doc_001",
                number="1.1",
                title="Defined Terms",
                level=2,
                content_preview="The following terms are defined...",
            ),
        ],
        definitions=[
            DefinedTermNode(
                id="def1",
                document_id="doc_001",
                term="Service",
                definition="The software services provided by Provider",
                section_id="sec1",
            ),
        ],
        cross_references=[
            CrossReference(
                from_section_id="sec2",
                from_section_number="1.1",
                to_section_id="sec1",
                to_section_number="1",
                reference_text="See Section 1",
            ),
        ],
    )


@pytest.fixture
def sample_smart_retrieval_response():
    """Create a sample SmartRetrievalResponse."""
    return SmartRetrievalResponse(
        sections=[
            SectionNode(
                id="sec1",
                document_id="doc_001",
                number="3.2",
                title="Payment Terms",
                level=2,
                content_preview="Payment shall be made within 30 days...",
            ),
        ],
        cross_referenced_sections=[
            SectionNode(
                id="sec2",
                document_id="doc_001",
                number="5.1",
                title="Referenced Section",
                level=2,
                content_preview="This is the referenced section...",
            ),
        ],
        relevant_definitions=[
            DefinedTermNode(
                id="def1",
                document_id="doc_001",
                term="Payment",
                definition="Monetary compensation for services",
                section_id="sec1",
            ),
        ],
    )


@pytest.fixture
def sample_rag_response():
    """Create a sample GraphEnhancedRAGResponse."""
    return GraphEnhancedRAGResponse(
        query="What is Acme Corp's payment policy?",
        answer="Acme Corp requires payment within 30 days of invoice.",
        original_chunks=[
            ChunkNode(
                id="chunk1",
                document_id="doc_001",
                content="Payment is due within 30 days of invoice date.",
                position=0,
            ),
        ],
        graph_context=GraphExpansionResult(
            extracted_entities=[
                EntityNode(
                    id="ent1",
                    name="Acme Corporation",
                    type=EntityType.ORGANIZATION,
                ),
            ],
            entity_relationships=[
                EntityRelationship(
                    from_entity_id="ent1",
                    to_entity_id="doc_001",
                    relationship_type="HAS_DOCUMENT",
                ),
            ],
            expanded_chunks=[],
        ),
    )


@pytest.fixture
def sample_graph_expansion_result():
    """Create a sample GraphExpansionResult."""
    return GraphExpansionResult(
        original_chunks=[
            ChunkNode(
                id="chunk1",
                document_id="doc_001",
                content="Original content",
                position=0,
            ),
        ],
        expanded_chunks=[
            ChunkNode(
                id="chunk1",
                document_id="doc_001",
                content="Original content",
                position=0,
            ),
            ChunkNode(
                id="chunk2",
                document_id="doc_002",
                content="Related content found through graph",
                position=0,
            ),
        ],
        extracted_entities=[
            EntityNode(
                id="ent1",
                name="Test Entity",
                type=EntityType.ORGANIZATION,
            ),
        ],
        entity_relationships=[],
    )


# =============================================================================
# CUSTOMER 360 FORMATTING TESTS
# =============================================================================

class TestCustomer360Formatting:
    """Tests for Customer 360 result formatting."""

    def test_format_customer_360_chat(self, formatter, sample_customer_360_response):
        """Test Customer 360 formatting for chat UI."""
        result = formatter.format_customer_360(sample_customer_360_response)

        assert result["type"] == "customer_360"
        assert "content" in result
        assert "summary" in result["content"]
        assert "sections" in result["content"]
        assert len(result["content"]["sections"]) > 0

    def test_format_customer_360_has_profile_section(self, formatter, sample_customer_360_response):
        """Test that profile section is included and expanded."""
        result = formatter.format_customer_360(sample_customer_360_response)

        sections = result["content"]["sections"]
        profile_section = next(
            (s for s in sections if s["type"] == SectionType.PROFILE.value),
            None
        )

        assert profile_section is not None
        assert profile_section["expanded"] is True

    def test_format_customer_360_has_document_section(self, formatter, sample_customer_360_response):
        """Test that documents section is included."""
        result = formatter.format_customer_360(sample_customer_360_response)

        sections = result["content"]["sections"]
        doc_section = next(
            (s for s in sections if s["type"] == SectionType.DOCUMENTS.value),
            None
        )

        assert doc_section is not None
        assert doc_section["count"] == 2

    def test_format_customer_360_markdown(self, formatter, sample_customer_360_response):
        """Test Customer 360 markdown formatting."""
        result = formatter.format_customer_360(
            sample_customer_360_response,
            output_format=OutputFormat.MARKDOWN,
        )

        assert result["format"] == "markdown"
        assert "## Customer: Acme Corporation" in result["content"]

    def test_format_customer_360_summary_only(self, formatter, sample_customer_360_response):
        """Test Customer 360 summary-only format."""
        result = formatter.format_customer_360(
            sample_customer_360_response,
            output_format=OutputFormat.SUMMARY,
        )

        assert result["type"] == "customer_360"
        assert "summary" in result
        assert "Acme Corporation" in result["summary"]

    def test_format_customer_360_json(self, formatter, sample_customer_360_response):
        """Test Customer 360 JSON format."""
        result = formatter.format_customer_360(
            sample_customer_360_response,
            output_format=OutputFormat.JSON,
        )

        assert result["type"] == "customer_360"
        assert "data" in result

    def test_generate_customer_summary(self, formatter, sample_customer_360_response):
        """Test customer summary generation."""
        summary = formatter._generate_customer_summary(sample_customer_360_response)

        assert "Acme Corporation" in summary
        assert "Technology" in summary
        assert "documents" in summary.lower()


# =============================================================================
# DOCUMENT STRUCTURE FORMATTING TESTS
# =============================================================================

class TestDocumentStructureFormatting:
    """Tests for Document Structure result formatting."""

    def test_format_document_structure_chat(self, formatter, sample_document_structure_response):
        """Test Document Structure formatting for chat UI."""
        result = formatter.format_document_structure(sample_document_structure_response)

        assert result["type"] == "document_structure"
        assert "content" in result
        assert "summary" in result["content"]
        assert "sections" in result["content"]

    def test_format_document_structure_has_sections(self, formatter, sample_document_structure_response):
        """Test that sections are included."""
        result = formatter.format_document_structure(sample_document_structure_response)

        sections = result["content"]["sections"]
        section_section = next(
            (s for s in sections if s["type"] == SectionType.SECTIONS.value),
            None
        )

        assert section_section is not None
        assert section_section["count"] == 2

    def test_format_document_structure_has_definitions(self, formatter, sample_document_structure_response):
        """Test that definitions are included."""
        result = formatter.format_document_structure(sample_document_structure_response)

        sections = result["content"]["sections"]
        def_section = next(
            (s for s in sections if s["type"] == SectionType.DEFINITIONS.value),
            None
        )

        assert def_section is not None
        assert def_section["count"] == 1

    def test_format_document_structure_markdown(self, formatter, sample_document_structure_response):
        """Test Document Structure markdown formatting."""
        result = formatter.format_document_structure(
            sample_document_structure_response,
            output_format=OutputFormat.MARKDOWN,
        )

        assert result["format"] == "markdown"
        assert "Master Services Agreement" in result["content"]
        assert "Table of Contents" in result["content"]

    def test_format_section_tree(self, formatter, sample_document_structure_response):
        """Test section tree formatting."""
        sections = sample_document_structure_response.sections
        tree = formatter._format_section_tree(sections)

        assert len(tree) == 2
        assert tree[0]["number"] == "1"
        assert tree[1]["number"] == "1.1"
        assert tree[1]["level"] == 2  # Second section is a subsection


# =============================================================================
# SMART RETRIEVAL FORMATTING TESTS
# =============================================================================

class TestSmartRetrievalFormatting:
    """Tests for Smart Retrieval result formatting."""

    def test_format_smart_retrieval_chat(self, formatter, sample_smart_retrieval_response):
        """Test Smart Retrieval formatting for chat UI."""
        result = formatter.format_smart_retrieval(sample_smart_retrieval_response)

        assert result["type"] == "smart_retrieval"
        assert "content" in result
        assert "sections" in result["content"]

    def test_format_smart_retrieval_has_sections(self, formatter, sample_smart_retrieval_response):
        """Test that retrieved sections are included."""
        result = formatter.format_smart_retrieval(sample_smart_retrieval_response)

        sections = result["content"]["sections"]
        main_section = next(
            (s for s in sections if s["type"] == SectionType.SECTIONS.value),
            None
        )

        assert main_section is not None
        assert main_section["expanded"] is True

    def test_format_smart_retrieval_has_cross_refs(self, formatter, sample_smart_retrieval_response):
        """Test that cross-references are included."""
        result = formatter.format_smart_retrieval(sample_smart_retrieval_response)

        sections = result["content"]["sections"]
        ref_section = next(
            (s for s in sections if s["type"] == SectionType.CROSS_REFERENCES.value),
            None
        )

        assert ref_section is not None


# =============================================================================
# GRAPH-ENHANCED RAG FORMATTING TESTS
# =============================================================================

class TestGraphEnhancedRAGFormatting:
    """Tests for Graph-Enhanced RAG result formatting."""

    def test_format_graph_enhanced_rag_chat(self, formatter, sample_rag_response):
        """Test Graph-Enhanced RAG formatting for chat UI."""
        result = formatter.format_graph_enhanced_rag(sample_rag_response)

        assert result["type"] == "graph_enhanced_rag"
        assert "content" in result
        assert result["content"]["answer"] is not None
        assert result["content"]["query"] == "What is Acme Corp's payment policy?"

    def test_format_graph_enhanced_rag_has_chunks(self, formatter, sample_rag_response):
        """Test that source chunks are included."""
        result = formatter.format_graph_enhanced_rag(sample_rag_response)

        sections = result["content"]["sections"]
        context_section = next(
            (s for s in sections if s["type"] == SectionType.CONTEXT.value),
            None
        )

        assert context_section is not None
        assert context_section["count"] == 1

    def test_format_graph_enhanced_rag_has_entities(self, formatter, sample_rag_response):
        """Test that entities are included."""
        result = formatter.format_graph_enhanced_rag(sample_rag_response)

        sections = result["content"]["sections"]
        entity_section = next(
            (s for s in sections if s["type"] == SectionType.ENTITIES.value),
            None
        )

        assert entity_section is not None
        assert entity_section["count"] == 1

    def test_format_graph_enhanced_rag_has_graph(self, formatter, sample_rag_response):
        """Test that graph visualization is included."""
        result = formatter.format_graph_enhanced_rag(sample_rag_response)

        sections = result["content"]["sections"]
        graph_section = next(
            (s for s in sections if s["type"] == SectionType.GRAPH.value),
            None
        )

        assert graph_section is not None
        assert "nodes" in graph_section["content"]
        assert "edges" in graph_section["content"]

    def test_format_graph_enhanced_rag_markdown(self, formatter, sample_rag_response):
        """Test Graph-Enhanced RAG markdown formatting."""
        result = formatter.format_graph_enhanced_rag(
            sample_rag_response,
            output_format=OutputFormat.MARKDOWN,
        )

        assert result["format"] == "markdown"
        assert "## Answer" in result["content"]
        assert "### Sources" in result["content"]

    def test_format_graph_enhanced_rag_summary(self, formatter, sample_rag_response):
        """Test Graph-Enhanced RAG summary format."""
        result = formatter.format_graph_enhanced_rag(
            sample_rag_response,
            output_format=OutputFormat.SUMMARY,
        )

        assert result["type"] == "graph_enhanced_rag"
        assert "answer" in result


# =============================================================================
# GRAPH EXPANSION FORMATTING TESTS
# =============================================================================

class TestGraphExpansionFormatting:
    """Tests for Graph Expansion result formatting."""

    def test_format_graph_expansion_chat(self, formatter, sample_graph_expansion_result):
        """Test Graph Expansion formatting for chat UI."""
        result = formatter.format_graph_expansion(sample_graph_expansion_result)

        assert result["type"] == "graph_expansion"
        assert "content" in result
        assert "summary" in result["content"]

    def test_format_graph_expansion_has_chunks(self, formatter, sample_graph_expansion_result):
        """Test that expanded chunks are included."""
        result = formatter.format_graph_expansion(sample_graph_expansion_result)

        sections = result["content"]["sections"]
        context_section = next(
            (s for s in sections if s["type"] == SectionType.CONTEXT.value),
            None
        )

        assert context_section is not None
        assert context_section["count"] == 2

    def test_format_graph_expansion_has_entities(self, formatter, sample_graph_expansion_result):
        """Test that extracted entities are included."""
        result = formatter.format_graph_expansion(sample_graph_expansion_result)

        sections = result["content"]["sections"]
        entity_section = next(
            (s for s in sections if s["type"] == SectionType.ENTITIES.value),
            None
        )

        assert entity_section is not None
        assert entity_section["count"] == 1


# =============================================================================
# HELPER FORMATTING TESTS
# =============================================================================

class TestHelperFormatting:
    """Tests for helper formatting methods."""

    def test_format_chunk_list(self, formatter):
        """Test chunk list formatting."""
        chunks = [
            ChunkNode(
                id="chunk1",
                document_id="doc_001",
                content="Short content",
                position=0,
            ),
            ChunkNode(
                id="chunk2",
                document_id="doc_002",
                content="x" * 500,  # Long content
                position=1,
            ),
        ]

        formatted = formatter._format_chunk_list(chunks)

        assert len(formatted) == 2
        assert formatted[0]["content"] == "Short content"
        assert formatted[1]["content"].endswith("...")  # Truncated

    def test_format_entity_list(self, formatter):
        """Test entity list formatting."""
        entities = [
            EntityNode(
                id="ent1",
                name="Acme Corp",
                type=EntityType.ORGANIZATION,
                description="A technology company",
            ),
        ]

        formatted = formatter._format_entity_list(entities)

        assert len(formatted) == 1
        assert formatted[0]["name"] == "Acme Corp"
        assert formatted[0]["type"] == "organization"
        assert formatted[0]["description"] == "A technology company"

    def test_generate_graph_visualization(self, formatter, sample_rag_response):
        """Test graph visualization generation."""
        viz = formatter._generate_graph_visualization(sample_rag_response)

        assert viz is not None
        assert "nodes" in viz
        assert "edges" in viz
        assert viz["layout"] == "force-directed"


# =============================================================================
# FORMATTED SECTION TESTS
# =============================================================================

class TestFormattedSection:
    """Tests for FormattedSection dataclass."""

    def test_formatted_section_to_dict(self):
        """Test FormattedSection to_dict conversion."""
        section = FormattedSection(
            title="Test Section",
            type=SectionType.DOCUMENTS,
            content=["doc1", "doc2"],
            expanded=True,
            count=2,
            icon="file",
        )

        result = section.to_dict()

        assert result["title"] == "Test Section"
        assert result["type"] == "documents"
        assert result["expanded"] is True
        assert result["count"] == 2
        assert result["icon"] == "file"

    def test_formatted_section_optional_fields(self):
        """Test FormattedSection with optional fields missing."""
        section = FormattedSection(
            title="Test",
            type=SectionType.CONTEXT,
            content=[],
        )

        result = section.to_dict()

        assert "count" not in result
        assert "icon" not in result


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_formatter_singleton(self):
        """Test that get_graph_result_formatter returns singleton."""
        reset_graph_result_formatter()
        formatter1 = get_graph_result_formatter()
        formatter2 = get_graph_result_formatter()

        assert formatter1 is formatter2

    def test_reset_creates_new_instance(self):
        """Test that reset creates new instance."""
        formatter1 = get_graph_result_formatter()
        reset_graph_result_formatter()
        formatter2 = get_graph_result_formatter()

        assert formatter1 is not formatter2


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_customer_360_response(self, formatter, sample_customer):
        """Test formatting with minimal data."""
        response = Customer360Response(
            customer=sample_customer,
            documents=[],
            tickets=[],
            orders=[],
            interactions=[],
            relationship_count=0,
        )

        result = formatter.format_customer_360(response)

        assert result["type"] == "customer_360"
        # Should only have profile section
        sections = result["content"]["sections"]
        assert len(sections) == 1
        assert sections[0]["type"] == SectionType.PROFILE.value

    def test_empty_document_structure_response(self, formatter):
        """Test formatting with empty document structure."""
        response = DocumentStructureResponse(
            document_id="doc_001",
            title="Empty Document",
            sections=[],
            definitions=[],
            cross_references=[],
        )

        result = formatter.format_document_structure(response)

        assert result["type"] == "document_structure"
        assert result["content"]["sections"] == []

    def test_rag_response_with_empty_graph_context(self, formatter):
        """Test RAG formatting with empty graph context."""
        response = GraphEnhancedRAGResponse(
            query="Test query",
            answer="Test answer",
            original_chunks=[
                ChunkNode(
                    id="chunk1",
                    document_id="doc1",
                    content="Content",
                    position=0,
                ),
            ],
            graph_context=GraphExpansionResult(
                # Empty graph context - no entities or relationships
                extracted_entities=[],
                entity_relationships=[],
            ),
        )

        result = formatter.format_graph_enhanced_rag(response)

        assert result["type"] == "graph_enhanced_rag"
        # Should have chunks but no entities section (empty)
        sections = result["content"]["sections"]
        context_sections = [s for s in sections if s["type"] == SectionType.CONTEXT.value]
        entity_sections = [s for s in sections if s["type"] == SectionType.ENTITIES.value]

        assert len(context_sections) == 1
        assert len(entity_sections) == 0  # No entities to show
