"""
Test suite for Search Result Presentation

Tests for SearchResultWithFacets formatting, metadata handling, and display.
"""

import pytest
from datetime import datetime
from app.services.faceted_search_service import (
    FacetedSearchService,
    SearchResultWithFacets
)


@pytest.fixture
def service():
    """Create FacetedSearchService instance"""
    return FacetedSearchService(supabase_client=None)


@pytest.fixture
def sample_metadata():
    """Sample document metadata"""
    return {
        "filename": "insurance_policy.pdf",
        "department": "legal",
        "file_type": "pdf",
        "created_at": datetime(2024, 1, 15, 10, 30),
        "b2_url": "https://b2.example.com/files/insurance_policy.pdf",
        "file_size": 1024000,
        "author": "John Doe"
    }


class TestSearchResultWithFacets:
    """Test SearchResultWithFacets dataclass"""

    def test_search_result_creation(self):
        """Test creating SearchResultWithFacets instance"""
        result = SearchResultWithFacets(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="California insurance policy",
            snippet="California insurance",
            highlighted_snippet="<mark>California</mark> insurance",
            score=0.95,
            rank=1,
            relevance_score=0.95,
            source_file="policy.pdf"
        )

        assert result.chunk_id == "chunk-123"
        assert result.document_id == "doc-456"
        assert result.score == 0.95
        assert result.rank == 1

    def test_search_result_optional_fields(self):
        """Test SearchResultWithFacets with optional fields"""
        result = SearchResultWithFacets(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Content",
            snippet="Snippet",
            highlighted_snippet="<mark>Snippet</mark>",
            score=0.8,
            rank=2,
            relevance_score=0.8,
            source_file="test.pdf",
            department="engineering",
            file_type="pdf",
            created_at=datetime(2024, 1, 1),
            b2_url="https://example.com/file.pdf"
        )

        assert result.department == "engineering"
        assert result.file_type == "pdf"
        assert result.b2_url == "https://example.com/file.pdf"

    def test_search_result_metadata_field(self):
        """Test SearchResultWithFacets metadata field"""
        metadata = {"custom_field": "value", "tags": ["tag1", "tag2"]}

        result = SearchResultWithFacets(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Content",
            snippet="Snippet",
            highlighted_snippet="Highlighted",
            score=0.9,
            rank=1,
            relevance_score=0.9,
            source_file="file.pdf",
            metadata=metadata
        )

        assert result.metadata["custom_field"] == "value"
        assert result.metadata["tags"] == ["tag1", "tag2"]


class TestFormatSearchResult:
    """Test format_search_result method"""

    def test_format_basic_result(self, service, sample_metadata):
        """Test formatting basic search result"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="This is a test document about California insurance policies.",
            score=0.95,
            rank=1,
            query_keywords=["California"],
            document_metadata=sample_metadata
        )

        assert isinstance(result, SearchResultWithFacets)
        assert result.chunk_id == "chunk-123"
        assert result.document_id == "doc-456"
        assert result.score == 0.95
        assert result.rank == 1
        assert result.source_file == "insurance_policy.pdf"

    def test_format_result_extracts_metadata(self, service, sample_metadata):
        """Test that metadata is correctly extracted"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test content",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        assert result.department == "legal"
        assert result.file_type == "pdf"
        assert result.created_at == datetime(2024, 1, 15, 10, 30)
        assert result.b2_url == "https://b2.example.com/files/insurance_policy.pdf"

    def test_format_result_generates_snippet(self, service, sample_metadata):
        """Test that snippet is generated"""
        long_content = "A" * 100 + " California " + "B" * 100

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=long_content,
            score=0.9,
            rank=1,
            query_keywords=["California"],
            document_metadata=sample_metadata
        )

        assert "California" in result.snippet
        assert len(result.snippet) < len(long_content)

    def test_format_result_highlights_snippet(self, service, sample_metadata):
        """Test that snippet is highlighted"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="California insurance policy document.",
            score=0.9,
            rank=1,
            query_keywords=["California", "insurance"],
            document_metadata=sample_metadata
        )

        assert "<mark>California</mark>" in result.highlighted_snippet
        assert "<mark>insurance</mark>" in result.highlighted_snippet

    def test_format_result_missing_metadata_filename(self, service):
        """Test formatting with missing filename"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test content",
            score=0.85,
            rank=2,
            query_keywords=[],
            document_metadata={}
        )

        assert result.source_file == "Unknown"

    def test_format_result_missing_metadata_department(self, service):
        """Test formatting with missing department"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test content",
            score=0.85,
            rank=2,
            query_keywords=[],
            document_metadata={"filename": "test.pdf"}
        )

        assert result.department is None
        assert result.file_type is None
        assert result.created_at is None

    def test_format_result_relevance_score_matches_score(self, service, sample_metadata):
        """Test that relevance_score is set to score"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test content",
            score=0.87,
            rank=3,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        assert result.relevance_score == 0.87
        assert result.relevance_score == result.score

    def test_format_result_preserves_full_content(self, service, sample_metadata):
        """Test that full content is preserved"""
        long_content = "This is a very long document about California insurance policies. " * 50

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=long_content,
            score=0.9,
            rank=1,
            query_keywords=["California"],
            document_metadata=sample_metadata
        )

        assert result.content == long_content  # Full content preserved
        assert len(result.snippet) < len(long_content)  # Snippet is truncated

    def test_format_result_multiple_keywords(self, service, sample_metadata):
        """Test formatting with multiple keywords"""
        content = "California insurance policies require compliance with state regulations."

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=content,
            score=0.95,
            rank=1,
            query_keywords=["California", "insurance", "regulations"],
            document_metadata=sample_metadata
        )

        # Keywords should appear in the snippet (some may be outside snippet bounds)
        highlighted = result.highlighted_snippet
        # At least the first keyword should be highlighted
        assert "<mark>California</mark>" in highlighted or "<mark>insurance</mark>" in highlighted

    def test_format_result_no_keywords(self, service, sample_metadata):
        """Test formatting with no keywords"""
        content = "This is a test document."

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=content,
            score=0.8,
            rank=5,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        # Snippet should be plain text
        assert result.snippet == content
        assert result.highlighted_snippet == content

    def test_format_result_metadata_passthrough(self, service):
        """Test that metadata dict is passed through"""
        metadata = {
            "filename": "test.pdf",
            "custom_field": "custom_value",
            "tags": ["tag1", "tag2"],
            "extra": {"nested": "value"}
        }

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata=metadata
        )

        assert result.metadata["custom_field"] == "custom_value"
        assert result.metadata["tags"] == ["tag1", "tag2"]
        assert result.metadata["extra"]["nested"] == "value"


class TestResultRanking:
    """Test result ranking and ordering"""

    def test_result_rank_preserved(self, service, sample_metadata):
        """Test that rank is preserved"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=5,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        assert result.rank == 5

    def test_result_score_preserved(self, service, sample_metadata):
        """Test that score is preserved"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.8765,
            rank=1,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        assert result.score == 0.8765


class TestResultMetadata:
    """Test metadata handling in results"""

    def test_result_with_b2_url(self, service):
        """Test result includes B2 URL"""
        metadata = {
            "filename": "document.pdf",
            "b2_url": "https://b2-cdn.example.com/bucket/document.pdf"
        }

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata=metadata
        )

        assert result.b2_url == "https://b2-cdn.example.com/bucket/document.pdf"

    def test_result_with_department(self, service):
        """Test result includes department"""
        metadata = {
            "filename": "policy.pdf",
            "department": "human_resources"
        }

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata=metadata
        )

        assert result.department == "human_resources"

    def test_result_with_file_type(self, service):
        """Test result includes file type"""
        metadata = {
            "filename": "document.docx",
            "file_type": "docx"
        }

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata=metadata
        )

        assert result.file_type == "docx"

    def test_result_with_created_at(self, service):
        """Test result includes created_at timestamp"""
        created = datetime(2024, 6, 15, 14, 30, 0)
        metadata = {
            "filename": "report.pdf",
            "created_at": created
        }

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata=metadata
        )

        assert result.created_at == created

    def test_result_all_metadata_none(self, service):
        """Test result with all metadata fields as None"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.9,
            rank=1,
            query_keywords=[],
            document_metadata={}
        )

        assert result.department is None
        assert result.file_type is None
        assert result.created_at is None
        assert result.b2_url is None


class TestEdgeCases:
    """Test edge cases in result formatting"""

    def test_format_result_empty_content(self, service, sample_metadata):
        """Test formatting with empty content"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="",
            score=0.5,
            rank=10,
            query_keywords=["keyword"],
            document_metadata=sample_metadata
        )

        assert result.content == ""
        assert result.snippet == ""

    def test_format_result_very_long_content(self, service, sample_metadata):
        """Test formatting with very long content"""
        long_content = "X" * 10000  # 10KB of content

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=long_content,
            score=0.8,
            rank=1,
            query_keywords=["X"],
            document_metadata=sample_metadata
        )

        assert len(result.content) == 10000
        assert len(result.snippet) < 210  # Max 200 + ellipsis

    def test_format_result_unicode_content(self, service, sample_metadata):
        """Test formatting with unicode content"""
        content = "Café résumé naïve Zürich California"

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=content,
            score=0.9,
            rank=1,
            query_keywords=["California"],
            document_metadata=sample_metadata
        )

        assert "California" in result.snippet
        assert "Café" in result.content or "résumé" in result.content

    def test_format_result_special_characters_content(self, service, sample_metadata):
        """Test formatting with special characters"""
        content = "Price: $500 (discount) [required] California policy"

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=content,
            score=0.9,
            rank=1,
            query_keywords=["California", "$500"],
            document_metadata=sample_metadata
        )

        assert "$500" in result.content
        assert "California" in result.snippet

    def test_format_result_newlines_in_content(self, service, sample_metadata):
        """Test formatting with newlines"""
        content = "Line 1\nCalifornia content\nLine 3"

        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content=content,
            score=0.9,
            rank=1,
            query_keywords=["California"],
            document_metadata=sample_metadata
        )

        assert "California" in result.snippet

    def test_format_result_zero_score(self, service, sample_metadata):
        """Test formatting with zero score"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=0.0,
            rank=100,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        assert result.score == 0.0
        assert result.relevance_score == 0.0

    def test_format_result_perfect_score(self, service, sample_metadata):
        """Test formatting with perfect score"""
        result = service.format_search_result(
            chunk_id="chunk-123",
            document_id="doc-456",
            content="Test",
            score=1.0,
            rank=1,
            query_keywords=[],
            document_metadata=sample_metadata
        )

        assert result.score == 1.0
        assert result.relevance_score == 1.0
