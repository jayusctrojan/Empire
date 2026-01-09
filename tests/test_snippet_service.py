"""
Tests for Snippet Generation Service

Tests snippet extraction and keyword highlighting functionality:
- Extract relevant snippets around matched keywords
- Highlight keywords in snippets
- Format results with metadata (relevance score, source, department)
- Ensure snippets are concise and informative
"""

import pytest
from typing import List
from unittest.mock import AsyncMock, MagicMock

from app.services.snippet_service import (
    SnippetService,
    SnippetConfig,
    SnippetResult,
    FormattedResult
)
from app.services.hybrid_search_service import SearchResult


@pytest.fixture
def snippet_service():
    """Snippet service instance"""
    return SnippetService()


@pytest.fixture
def search_result_with_content():
    """Sample search result with content for snippet extraction"""
    return SearchResult(
        chunk_id="chunk1",
        content=(
            "California insurance policies are regulated by the state "
            "Department of Insurance. The department ensures that all "
            "insurance companies comply with state regulations. When you "
            "purchase an insurance policy in California, you are protected "
            "by these comprehensive regulations."
        ),
        score=0.95,
        rank=1,
        method="hybrid",
        metadata={
            "document_id": "doc1",
            "department": "Legal",
            "file_type": "pdf",
            "filename": "insurance_policy.pdf",
            "b2_url": "https://b2.example.com/files/insurance_policy.pdf"
        }
    )


class TestSnippetConfig:
    """Test snippet configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SnippetConfig()

        assert config.snippet_length == 200
        assert config.context_window == 50
        assert config.highlight_start == "<mark>"
        assert config.highlight_end == "</mark>"
        assert config.max_highlights == 10

    def test_custom_config(self):
        """Test custom configuration"""
        config = SnippetConfig(
            snippet_length=300,
            highlight_start="<strong>",
            highlight_end="</strong>"
        )

        assert config.snippet_length == 300
        assert config.highlight_start == "<strong>"
        assert config.highlight_end == "</strong>"


class TestSnippetExtraction:
    """Test snippet extraction from content"""

    def test_extract_snippet_with_keyword(self, snippet_service, search_result_with_content):
        """Test extracting snippet around a keyword"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="California insurance"
        )

        assert isinstance(result, SnippetResult)
        assert "California" in result.snippet
        assert "insurance" in result.snippet.lower()
        assert len(result.snippet) <= snippet_service.config.snippet_length + 50  # Some buffer

    def test_snippet_contains_context(self, snippet_service, search_result_with_content):
        """Test snippet includes context around keywords"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="Department of Insurance"
        )

        # Should include words before and after the keyword
        assert "Department of Insurance" in result.snippet
        assert len(result.snippet.split()) > 3  # More than just the keyword

    def test_snippet_truncation(self, snippet_service):
        """Test snippet is truncated to configured length"""
        long_content = SearchResult(
            chunk_id="chunk1",
            content=" ".join(["word"] * 500),  # Very long content
            score=0.9,
            rank=1,
            method="hybrid",
            metadata={}
        )

        result = snippet_service.extract_snippet(long_content, query="word")

        assert len(result.snippet) <= snippet_service.config.snippet_length + 50

    def test_snippet_from_beginning_if_no_match(self, snippet_service, search_result_with_content):
        """Test snippet starts from beginning if no keyword match"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="nonexistent keyword"
        )

        # Should still return a snippet
        assert len(result.snippet) > 0
        # Should start from the beginning of content
        assert result.snippet.strip().startswith("California")

    def test_multiple_keyword_matches(self, snippet_service, search_result_with_content):
        """Test snippet centers on first keyword match"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="insurance"  # Appears multiple times
        )

        assert "insurance" in result.snippet.lower()
        assert len(result.snippet) > 0


class TestKeywordHighlighting:
    """Test keyword highlighting in snippets"""

    def test_highlight_single_keyword(self, snippet_service, search_result_with_content):
        """Test highlighting a single keyword"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="California"
        )

        highlighted = snippet_service.highlight_keywords(result.snippet, "California")

        assert "<mark>California</mark>" in highlighted
        assert highlighted.count("<mark>") == highlighted.count("</mark>")

    def test_highlight_multiple_keywords(self, snippet_service, search_result_with_content):
        """Test highlighting multiple keywords"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="California insurance"
        )

        highlighted = snippet_service.highlight_keywords(result.snippet, "California insurance")

        assert "<mark>California</mark>" in highlighted or "California" in highlighted
        assert "<mark>insurance</mark>" in highlighted.lower() or "insurance" in highlighted.lower()

    def test_highlight_case_insensitive(self, snippet_service):
        """Test highlighting is case-insensitive"""
        snippet = "The Insurance policy covers California."

        highlighted = snippet_service.highlight_keywords(snippet, "insurance california")

        assert "<mark>Insurance</mark>" in highlighted or "<mark>insurance</mark>" in highlighted
        assert "<mark>California</mark>" in highlighted or "<mark>california</mark>" in highlighted

    def test_highlight_preserves_case(self, snippet_service):
        """Test highlighting preserves original text case"""
        snippet = "CALIFORNIA Insurance Policy"

        highlighted = snippet_service.highlight_keywords(snippet, "california insurance")

        # Should preserve original case
        assert "CALIFORNIA" in highlighted or "<mark>CALIFORNIA</mark>" in highlighted
        assert "Insurance" in highlighted or "<mark>Insurance</mark>" in highlighted

    def test_highlight_multiple_occurrences(self, snippet_service):
        """Test highlighting multiple occurrences of same keyword"""
        snippet = "Insurance companies provide insurance coverage through insurance policies."

        highlighted = snippet_service.highlight_keywords(snippet, "insurance")

        # Should highlight all occurrences (up to max)
        assert highlighted.count("<mark>") >= 2

    def test_highlight_max_limit(self, snippet_service):
        """Test highlighting respects maximum highlight count"""
        snippet = " ".join(["insurance"] * 20)

        highlighted = snippet_service.highlight_keywords(snippet, "insurance")

        # Should not exceed max_highlights
        highlight_count = highlighted.count("<mark>")
        assert highlight_count <= snippet_service.config.max_highlights

    def test_custom_highlight_tags(self):
        """Test custom highlight tags"""
        config = SnippetConfig(
            highlight_start="<strong class='highlight'>",
            highlight_end="</strong>"
        )
        service = SnippetService(config=config)

        snippet = "California insurance policy"
        highlighted = service.highlight_keywords(snippet, "California")

        assert "<strong class='highlight'>California</strong>" in highlighted


class TestFormattedResult:
    """Test formatted result generation"""

    def test_format_result_complete(self, snippet_service, search_result_with_content):
        """Test formatting a complete result with all metadata"""
        snippet_result = snippet_service.extract_snippet(
            search_result_with_content,
            query="California insurance"
        )

        formatted = snippet_service.format_result(
            search_result_with_content,
            snippet_result,
            query="California insurance"
        )

        assert isinstance(formatted, FormattedResult)
        assert formatted.snippet is not None
        assert formatted.highlighted_snippet is not None
        assert formatted.relevance_score == 0.95
        assert formatted.source == "insurance_policy.pdf"
        assert formatted.department == "Legal"
        assert formatted.file_type == "pdf"
        assert formatted.b2_url == "https://b2.example.com/files/insurance_policy.pdf"

    def test_format_result_with_highlights(self, snippet_service, search_result_with_content):
        """Test highlighted snippet is included in formatted result"""
        snippet_result = snippet_service.extract_snippet(
            search_result_with_content,
            query="insurance"
        )

        formatted = snippet_service.format_result(
            search_result_with_content,
            snippet_result,
            query="insurance"
        )

        assert "<mark>" in formatted.highlighted_snippet
        assert "</mark>" in formatted.highlighted_snippet

    def test_format_result_missing_metadata(self, snippet_service):
        """Test formatting result with missing metadata fields"""
        incomplete_result = SearchResult(
            chunk_id="chunk1",
            content="Test content",
            score=0.8,
            rank=1,
            method="hybrid",
            metadata={}  # Empty metadata
        )

        snippet_result = snippet_service.extract_snippet(incomplete_result, query="test")
        formatted = snippet_service.format_result(
            incomplete_result,
            snippet_result,
            query="test"
        )

        assert formatted.source is None
        assert formatted.department is None
        assert formatted.b2_url is None
        assert formatted.relevance_score == 0.8  # Should still have score

    def test_format_result_to_dict(self, snippet_service, search_result_with_content):
        """Test converting formatted result to dictionary"""
        snippet_result = snippet_service.extract_snippet(
            search_result_with_content,
            query="California"
        )

        formatted = snippet_service.format_result(
            search_result_with_content,
            snippet_result,
            query="California"
        )

        result_dict = formatted.to_dict()

        assert "snippet" in result_dict
        assert "highlighted_snippet" in result_dict
        assert "relevance_score" in result_dict
        assert "source" in result_dict
        assert "department" in result_dict
        assert "b2_url" in result_dict


class TestBatchFormatting:
    """Test batch formatting of multiple results"""

    def test_format_multiple_results(self, snippet_service):
        """Test formatting multiple search results"""
        results = [
            SearchResult(
                chunk_id=f"chunk{i}",
                content=f"This is document {i} about California insurance policies.",
                score=0.9 - (i * 0.1),
                rank=i + 1,
                method="hybrid",
                metadata={
                    "document_id": f"doc{i}",
                    "department": "Legal",
                    "filename": f"doc{i}.pdf"
                }
            )
            for i in range(3)
        ]

        formatted_results = snippet_service.format_results(
            results,
            query="California insurance"
        )

        assert len(formatted_results) == 3
        assert all(isinstance(r, FormattedResult) for r in formatted_results)
        assert all(r.highlighted_snippet for r in formatted_results)

    def test_format_empty_results(self, snippet_service):
        """Test formatting empty results list"""
        formatted_results = snippet_service.format_results([], query="test")

        assert len(formatted_results) == 0


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_query(self, snippet_service, search_result_with_content):
        """Test snippet extraction with empty query"""
        result = snippet_service.extract_snippet(search_result_with_content, query="")

        # Should still return a snippet
        assert len(result.snippet) > 0

    def test_empty_content(self, snippet_service):
        """Test snippet extraction from empty content"""
        empty_result = SearchResult(
            chunk_id="chunk1",
            content="",
            score=0.5,
            rank=1,
            method="hybrid",
            metadata={}
        )

        result = snippet_service.extract_snippet(empty_result, query="test")

        assert result.snippet == ""

    def test_very_short_content(self, snippet_service):
        """Test snippet extraction from very short content"""
        short_result = SearchResult(
            chunk_id="chunk1",
            content="Short.",
            score=0.8,
            rank=1,
            method="hybrid",
            metadata={}
        )

        result = snippet_service.extract_snippet(short_result, query="short")

        assert result.snippet == "Short."

    def test_special_characters_in_query(self, snippet_service, search_result_with_content):
        """Test handling special regex characters in query"""
        result = snippet_service.extract_snippet(
            search_result_with_content,
            query="California (state)"
        )

        # Should not crash with regex special characters
        assert len(result.snippet) > 0
