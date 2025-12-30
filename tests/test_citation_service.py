"""
Tests for Citation Service (Task 15)

Tests the citation extraction, formatting, and inline citation features.

Author: Claude Code
Date: 2025-01-25
"""

import pytest
from app.services.citation_service import (
    CitationService,
    CitationStyle,
    SourceMetadata,
    Citation,
    CitedResponse,
    get_citation_service
)


class TestSourceMetadata:
    """Tests for SourceMetadata dataclass"""

    def test_from_chunk_metadata_with_source_metadata(self):
        """Test extracting source metadata from chunk with nested source_metadata"""
        chunk_data = {
            "id": "chunk-123",
            "document_id": "doc-456",
            "content": "Some content here",
            "chunk_index": 5,
            "source_metadata": {
                "title": "Test Document",
                "author": "John Doe",
                "publication_date": "2024-01-15",
                "page_count": 42,
                "document_type": "pdf",
                "language": "en",
                "confidence_score": 0.85,
                "additional_metadata": {"subject": "Testing"}
            },
            "metadata": {
                "page_number": 10
            }
        }

        source = SourceMetadata.from_chunk_metadata(chunk_data, relevance_score=0.92)

        assert source.title == "Test Document"
        assert source.author == "John Doe"
        assert source.publication_date == "2024-01-15"
        assert source.page_count == 42
        assert source.document_type == "pdf"
        assert source.chunk_id == "chunk-123"
        assert source.document_id == "doc-456"
        assert source.page_number == 10
        assert source.chunk_index == 5
        assert source.relevance_score == 0.92
        assert source.confidence_score == 0.85

    def test_from_chunk_metadata_minimal(self):
        """Test extracting from chunk with minimal data"""
        chunk_data = {
            "id": "chunk-789",
            "filename": "report.pdf"
        }

        source = SourceMetadata.from_chunk_metadata(chunk_data)

        assert source.title == "report.pdf"
        assert source.author is None
        assert source.chunk_id == "chunk-789"

    def test_to_dict(self):
        """Test conversion to dictionary"""
        source = SourceMetadata(
            title="Test Doc",
            author="Jane Smith",
            publication_date="2024-03-20",
            document_type="docx",
            chunk_id="chunk-001"
        )

        result = source.to_dict()

        assert result["title"] == "Test Doc"
        assert result["author"] == "Jane Smith"
        assert result["publication_date"] == "2024-03-20"
        assert result["document_type"] == "docx"
        assert result["chunk_id"] == "chunk-001"


class TestCitationService:
    """Tests for CitationService"""

    @pytest.fixture
    def service(self):
        """Create a fresh CitationService instance"""
        return CitationService(
            default_style=CitationStyle.NUMERIC,
            include_page_numbers=True,
            include_confidence=False
        )

    @pytest.fixture
    def sample_chunks(self):
        """Sample chunk data for testing"""
        return [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "content": "First chunk content",
                "score": 0.95,
                "source_metadata": {
                    "title": "Annual Report 2024",
                    "author": "Finance Team",
                    "publication_date": "2024-01-01",
                    "document_type": "pdf",
                    "confidence_score": 0.9
                },
                "metadata": {"page_number": 5}
            },
            {
                "id": "chunk-2",
                "document_id": "doc-1",  # Same document, different chunk
                "content": "Second chunk content",
                "score": 0.88,
                "source_metadata": {
                    "title": "Annual Report 2024",
                    "author": "Finance Team",
                    "publication_date": "2024-01-01",
                    "document_type": "pdf",
                    "confidence_score": 0.9
                },
                "metadata": {"page_number": 10}
            },
            {
                "id": "chunk-3",
                "document_id": "doc-2",
                "content": "Third chunk content",
                "score": 0.82,
                "source_metadata": {
                    "title": "Technical Manual",
                    "author": "Engineering Dept",
                    "publication_date": "2023-06-15",
                    "document_type": "docx",
                    "confidence_score": 0.85
                },
                "metadata": {"page_number": 22}
            }
        ]

    def test_extract_sources_deduplication(self, service, sample_chunks):
        """Test that chunks from same document are deduplicated"""
        sources = service.extract_sources_from_chunks(sample_chunks)

        # Should have 2 unique documents, not 3 chunks
        assert len(sources) == 2
        assert sources[0].title == "Annual Report 2024"
        assert sources[1].title == "Technical Manual"

    def test_extract_sources_relevance_ordering(self, service, sample_chunks):
        """Test that sources are ordered by relevance score"""
        sources = service.extract_sources_from_chunks(sample_chunks)

        # First source should have highest relevance
        assert sources[0].relevance_score == 0.95
        assert sources[1].relevance_score == 0.82

    def test_format_citation_numeric(self, service):
        """Test numeric citation formatting"""
        source = SourceMetadata(
            title="Test Document",
            author="John Doe",
            publication_date="2024-01-15",
            document_type="pdf",
            page_number=42
        )

        citation = service.format_citation(source, 1, CitationStyle.NUMERIC)

        assert citation.marker == "[1]"
        assert citation.citation_number == 1
        assert "Test Document" in citation.formatted_citation
        assert "John Doe" in citation.formatted_citation
        assert "Page 42" in citation.formatted_citation

    def test_format_citation_author_date(self, service):
        """Test author-date citation formatting"""
        source = SourceMetadata(
            title="Test Document",
            author="John Doe",
            publication_date="2024-01-15"
        )

        citation = service.format_citation(source, 1, CitationStyle.AUTHOR_DATE)

        assert citation.marker == "(Doe, 2024)"

    def test_format_citation_author_date_no_author(self, service):
        """Test author-date formatting with missing author"""
        source = SourceMetadata(
            title="Test Document",
            publication_date="2024-01-15"
        )

        citation = service.format_citation(source, 1, CitationStyle.AUTHOR_DATE)

        assert citation.marker == "(Unknown, 2024)"

    def test_format_citation_footnote(self, service):
        """Test footnote citation formatting"""
        source = SourceMetadata(title="Test Document")

        citation = service.format_citation(source, 1, CitationStyle.FOOTNOTE)

        assert citation.marker == "¹"

    def test_create_citations_for_response(self, service, sample_chunks):
        """Test creating citations and marker mapping"""
        citations, marker_map = service.create_citations_for_response(sample_chunks)

        assert len(citations) == 2
        assert "doc-1" in marker_map
        assert "doc-2" in marker_map
        assert marker_map["doc-1"] == "[1]"
        assert marker_map["doc-2"] == "[2]"

    def test_insert_inline_citations_single_paragraph(self, service, sample_chunks):
        """Test inserting citations into single paragraph response"""
        response_text = "This is a response based on the documents."

        result = service.insert_inline_citations(response_text, sample_chunks)

        assert isinstance(result, CitedResponse)
        assert "[1]" in result.response_text
        assert "[2]" in result.response_text
        assert result.total_sources == 2
        assert len(result.citations) == 2

    def test_insert_inline_citations_multiple_paragraphs(self, service, sample_chunks):
        """Test inserting citations into multi-paragraph response"""
        response_text = """First paragraph with some information.

Second paragraph with more details.

Third paragraph concluding the response."""

        result = service.insert_inline_citations(response_text, sample_chunks)

        # Citations should appear in the text
        assert "[1]" in result.response_text or "[2]" in result.response_text
        assert result.total_sources == 2

    def test_insert_inline_citations_empty_chunks(self, service):
        """Test handling of empty chunks list"""
        response_text = "Response without sources."

        result = service.insert_inline_citations(response_text, [])

        assert result.response_text == response_text
        assert result.total_sources == 0
        assert len(result.citations) == 0

    def test_format_citations_footer(self, service, sample_chunks):
        """Test generating citations footer"""
        citations, _ = service.create_citations_for_response(sample_chunks)

        footer = service.format_citations_footer(citations)

        assert "**Sources:**" in footer
        assert "Annual Report 2024" in footer
        assert "Technical Manual" in footer
        assert "[1]" in footer
        assert "[2]" in footer

    def test_create_source_attribution_json(self, service, sample_chunks):
        """Test creating JSON for database storage"""
        citations, _ = service.create_citations_for_response(sample_chunks)

        json_data = service.create_source_attribution_json(citations)

        assert len(json_data) == 2
        assert json_data[0]["citation_number"] == 1
        assert json_data[0]["title"] == "Annual Report 2024"
        assert json_data[0]["document_id"] == "doc-1"
        assert json_data[1]["title"] == "Technical Manual"


class TestCitedResponse:
    """Tests for CitedResponse dataclass"""

    def test_to_dict(self):
        """Test CitedResponse serialization"""
        source = SourceMetadata(title="Test", chunk_id="c1")
        citation = Citation(
            citation_number=1,
            marker="[1]",
            source=source,
            formatted_citation="[1] Test"
        )

        response = CitedResponse(
            response_text="Text [1]",
            citations=[citation],
            total_sources=1,
            citation_style=CitationStyle.NUMERIC
        )

        result = response.to_dict()

        assert result["response_text"] == "Text [1]"
        assert result["total_sources"] == 1
        assert result["citation_style"] == "numeric"
        assert len(result["citations"]) == 1
        assert result["citations"][0]["marker"] == "[1]"


class TestGetCitationService:
    """Tests for singleton getter"""

    def test_returns_same_instance(self):
        """Test that get_citation_service returns singleton"""
        service1 = get_citation_service()
        service2 = get_citation_service()

        assert service1 is service2

    def test_default_configuration(self):
        """Test default service configuration"""
        service = get_citation_service()

        assert service.default_style == CitationStyle.NUMERIC
        assert service.include_page_numbers is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
