"""
Empire v7.3 - Tests for Gradio Citation Component (Task 16)
Tests for inline citations, expandable cards, and source display.
"""

import pytest
from html import escape

from app.ui.components.citation_cards import (
    SourceType,
    CitationSource,
    CitationGroup,
    CITATION_CSS,
    CITATION_JS,
    SOURCE_TYPE_STYLES,
    create_inline_citation_html,
    create_citation_card_html,
    create_citations_list_html,
    create_inline_text_with_citations,
    parse_citations_from_response,
    format_response_with_sources,
)


# ============================================================================
# Test Data Models
# ============================================================================

class TestSourceType:
    """Tests for SourceType enum."""

    def test_all_source_types_defined(self):
        """Verify all expected source types exist."""
        expected = ["document", "webpage", "database", "knowledge_graph", "api", "user_memory", "unknown"]
        for source in expected:
            assert SourceType(source) is not None

    def test_source_type_values(self):
        """Test source type value property."""
        assert SourceType.DOCUMENT.value == "document"
        assert SourceType.WEBPAGE.value == "webpage"
        assert SourceType.KNOWLEDGE_GRAPH.value == "knowledge_graph"


class TestCitationSource:
    """Tests for CitationSource dataclass."""

    def test_basic_citation(self):
        """Test creating a basic citation."""
        citation = CitationSource(
            citation_id="cite-1",
            title="Test Document",
            source_type=SourceType.DOCUMENT,
            excerpt="This is a test excerpt."
        )
        assert citation.citation_id == "cite-1"
        assert citation.title == "Test Document"
        assert citation.source_type == SourceType.DOCUMENT
        assert citation.excerpt == "This is a test excerpt."

    def test_full_citation(self):
        """Test citation with all fields."""
        citation = CitationSource(
            citation_id="cite-full",
            title="Complete Document",
            source_type=SourceType.DOCUMENT,
            excerpt="Short excerpt",
            full_content="Full content of the document...",
            document_id="doc-123",
            page_number=42,
            section="Chapter 3",
            url="https://example.com/doc",
            author="John Doe",
            date="2024-01-15",
            relevance_score=0.95,
            metadata={"category": "legal"}
        )
        assert citation.page_number == 42
        assert citation.author == "John Doe"
        assert citation.relevance_score == 0.95
        assert citation.metadata["category"] == "legal"

    def test_to_dict(self):
        """Test converting citation to dictionary."""
        citation = CitationSource(
            citation_id="cite-dict",
            title="Dict Test",
            source_type=SourceType.WEBPAGE,
            relevance_score=0.8
        )
        data = citation.to_dict()

        assert data["citation_id"] == "cite-dict"
        assert data["title"] == "Dict Test"
        assert data["source_type"] == "webpage"
        assert data["relevance_score"] == 0.8


class TestCitationGroup:
    """Tests for CitationGroup dataclass."""

    def test_create_empty_group(self):
        """Test creating an empty citation group."""
        group = CitationGroup(response_id="response-1")
        assert group.response_id == "response-1"
        assert len(group.citations) == 0

    def test_add_citation(self):
        """Test adding citations to a group."""
        group = CitationGroup(response_id="response-2")

        citation1 = CitationSource(citation_id="c1", title="Doc 1")
        citation2 = CitationSource(citation_id="c2", title="Doc 2")

        group.add_citation(citation1)
        group.add_citation(citation2)

        assert len(group.citations) == 2

    def test_get_citation(self):
        """Test retrieving a citation by ID."""
        group = CitationGroup(response_id="response-3")
        citation = CitationSource(citation_id="findme", title="Find Me")
        group.add_citation(citation)

        found = group.get_citation("findme")
        assert found is not None
        assert found.title == "Find Me"

        not_found = group.get_citation("nonexistent")
        assert not_found is None


# ============================================================================
# Test Style Definitions
# ============================================================================

class TestSourceTypeStyles:
    """Tests for source type style definitions."""

    def test_all_source_types_have_styles(self):
        """Verify all source types have style definitions."""
        for source_type in SourceType:
            assert source_type in SOURCE_TYPE_STYLES, f"Missing style for {source_type}"

    def test_style_has_required_keys(self):
        """Verify each style has required keys."""
        required_keys = ["icon", "color", "label", "bg_color"]
        for source_type, style in SOURCE_TYPE_STYLES.items():
            for key in required_keys:
                assert key in style, f"Missing {key} in style for {source_type}"

    def test_document_style(self):
        """Test document source type style."""
        style = SOURCE_TYPE_STYLES[SourceType.DOCUMENT]
        assert style["icon"] == "📄"
        assert style["label"] == "Document"
        assert style["color"].startswith("#")


# ============================================================================
# Test HTML Generation
# ============================================================================

class TestInlineCitationHTML:
    """Tests for inline citation marker HTML generation."""

    def test_basic_marker(self):
        """Test basic inline citation marker."""
        html = create_inline_citation_html(1, "cite-1")
        assert "citation-marker" in html
        assert "1" in html
        assert "cite-1" in html

    def test_marker_accessibility(self):
        """Test accessibility attributes."""
        html = create_inline_citation_html(3, "cite-3")
        assert 'role="link"' in html
        assert 'aria-label="Citation 3"' in html
        assert 'tabindex="0"' in html

    def test_marker_escapes_special_chars(self):
        """Test that special characters are escaped."""
        html = create_inline_citation_html(1, 'cite-<script>alert("xss")</script>')
        assert "<script>" not in html
        assert "&lt;script&gt;" in html or "cite-" in html


class TestCitationCardHTML:
    """Tests for citation card HTML generation."""

    def test_basic_card(self):
        """Test basic citation card."""
        citation = CitationSource(
            citation_id="card-1",
            title="Test Card",
            source_type=SourceType.DOCUMENT,
            excerpt="Test excerpt content."
        )
        html = create_citation_card_html(citation, 1)

        assert "citation-card" in html
        assert "Test Card" in html
        assert "Test excerpt content" in html
        assert "📄" in html  # Document icon

    def test_card_with_metadata(self):
        """Test card with full metadata."""
        citation = CitationSource(
            citation_id="card-meta",
            title="Full Metadata Card",
            source_type=SourceType.WEBPAGE,
            excerpt="Excerpt",
            author="Jane Smith",
            date="2024-03-20",
            page_number=15,
            section="Introduction"
        )
        html = create_citation_card_html(citation, 2)

        assert "Jane Smith" in html
        assert "2024-03-20" in html
        assert "Page 15" in html
        assert "Introduction" in html

    def test_card_expanded_state(self):
        """Test expanded card state."""
        citation = CitationSource(
            citation_id="expand-test",
            title="Expandable Card",
            full_content="This is the full content."
        )
        html = create_citation_card_html(citation, 1, expanded=True)

        assert "expanded" in html
        assert "This is the full content" in html

    def test_card_collapsed_state(self):
        """Test collapsed card state."""
        citation = CitationSource(
            citation_id="collapse-test",
            title="Collapsed Card",
            full_content="Hidden content."
        )
        html = create_citation_card_html(citation, 1, expanded=False)

        # Content div should not have 'visible' class
        assert 'citation-content"' in html or 'citation-content visible' not in html

    def test_card_relevance_score_display(self):
        """Test relevance score display."""
        citation = CitationSource(
            citation_id="rel-test",
            title="High Relevance",
            relevance_score=0.85
        )
        html = create_citation_card_html(citation, 1)

        assert "85%" in html
        assert "relevance-score" in html

    def test_card_with_url(self):
        """Test card with source URL."""
        citation = CitationSource(
            citation_id="url-test",
            title="URL Card",
            url="https://example.com/source"
        )
        html = create_citation_card_html(citation, 1)

        assert "View Source" in html
        assert "https://example.com/source" in html

    def test_card_accessibility(self):
        """Test card ARIA attributes."""
        citation = CitationSource(
            citation_id="a11y-test",
            title="Accessible Card"
        )
        html = create_citation_card_html(citation, 1)

        assert 'role="article"' in html
        assert 'aria-labelledby=' in html
        assert 'role="button"' in html


class TestCitationsListHTML:
    """Tests for citations list HTML generation."""

    def test_empty_list(self):
        """Test empty citations list."""
        html = create_citations_list_html([])
        assert "No citations available" in html

    def test_single_citation(self):
        """Test list with single citation."""
        citations = [
            CitationSource(citation_id="single", title="Single Source")
        ]
        html = create_citations_list_html(citations)

        assert "1 Sources" in html
        assert "Single Source" in html

    def test_multiple_citations(self):
        """Test list with multiple citations."""
        citations = [
            CitationSource(citation_id="c1", title="Source 1"),
            CitationSource(citation_id="c2", title="Source 2"),
            CitationSource(citation_id="c3", title="Source 3"),
        ]
        html = create_citations_list_html(citations)

        assert "3 Sources" in html
        assert "Source 1" in html
        assert "Source 2" in html
        assert "Source 3" in html

    def test_list_with_filter(self):
        """Test list with filter controls."""
        citations = [
            CitationSource(citation_id="c1", title="Doc 1", source_type=SourceType.DOCUMENT),
            CitationSource(citation_id="c2", title="Web 1", source_type=SourceType.WEBPAGE),
            CitationSource(citation_id="c3", title="Doc 2", source_type=SourceType.DOCUMENT),
            CitationSource(citation_id="c4", title="API 1", source_type=SourceType.API),
        ]
        html = create_citations_list_html(citations, show_filter=True)

        assert "citations-filter" in html
        assert "All" in html

    def test_list_accessibility(self):
        """Test list ARIA attributes."""
        citations = [CitationSource(citation_id="c1", title="Test")]
        html = create_citations_list_html(citations, title="References")

        assert 'role="region"' in html
        assert 'aria-label="References"' in html
        assert 'role="list"' in html


class TestInlineTextWithCitations:
    """Tests for processing text with inline citations."""

    def test_single_citation_replacement(self):
        """Test replacing a single citation marker."""
        citations = [
            CitationSource(citation_id="ref-1", title="Reference 1")
        ]
        text = "This is a statement [1] with a citation."
        html = create_inline_text_with_citations(text, citations)

        assert "[1]" not in html
        assert "citation-marker" in html
        assert "ref-1" in html

    def test_multiple_citations_replacement(self):
        """Test replacing multiple citation markers."""
        citations = [
            CitationSource(citation_id="ref-1", title="First"),
            CitationSource(citation_id="ref-2", title="Second"),
            CitationSource(citation_id="ref-3", title="Third"),
        ]
        text = "Point A [1] and point B [2] with conclusion [3]."
        html = create_inline_text_with_citations(text, citations)

        assert "[1]" not in html
        assert "[2]" not in html
        assert "[3]" not in html
        assert html.count("citation-marker") == 3

    def test_out_of_range_citation_preserved(self):
        """Test that out-of-range markers are preserved."""
        citations = [
            CitationSource(citation_id="ref-1", title="Only One")
        ]
        text = "Valid [1] and invalid [5]."
        html = create_inline_text_with_citations(text, citations)

        assert "[5]" in html  # Out of range preserved
        assert "[1]" not in html  # Valid one replaced

    def test_text_without_citations(self):
        """Test text with no citation markers."""
        citations = [CitationSource(citation_id="unused", title="Unused")]
        text = "Plain text without any markers."
        html = create_inline_text_with_citations(text, citations)

        assert html == text


# ============================================================================
# Test Utility Functions
# ============================================================================

class TestParseCitationsFromResponse:
    """Tests for parsing citations from response."""

    def test_parse_basic_response(self):
        """Test parsing a basic response with sources."""
        response = "The answer is 42 [1]."
        sources = [
            {
                "id": "src-1",
                "title": "Hitchhiker's Guide",
                "type": "document",
                "excerpt": "The answer to everything..."
            }
        ]
        processed_text, citations = parse_citations_from_response(response, sources)

        assert len(citations) == 1
        assert citations[0].title == "Hitchhiker's Guide"
        assert "[1]" not in processed_text

    def test_parse_multiple_sources(self):
        """Test parsing response with multiple sources."""
        response = "Fact A [1] and Fact B [2]."
        sources = [
            {"id": "s1", "title": "Source A", "type": "document"},
            {"id": "s2", "title": "Source B", "type": "webpage"}
        ]
        processed_text, citations = parse_citations_from_response(response, sources)

        assert len(citations) == 2
        assert citations[0].source_type == SourceType.DOCUMENT
        assert citations[1].source_type == SourceType.WEBPAGE

    def test_parse_with_relevance_scores(self):
        """Test parsing sources with relevance scores."""
        sources = [
            {"id": "high", "title": "High Score", "score": 0.95},
            {"id": "low", "title": "Low Score", "relevance": 0.3}
        ]
        _, citations = parse_citations_from_response("Text [1] [2]", sources)

        assert citations[0].relevance_score == 0.95
        assert citations[1].relevance_score == 0.3


class TestFormatResponseWithSources:
    """Tests for formatting complete responses."""

    def test_format_with_sources_section(self):
        """Test formatting with sources section included."""
        answer = "The result is X [1]."
        sources = [{"id": "s1", "title": "Evidence", "type": "document"}]

        html = format_response_with_sources(answer, sources, include_sources_section=True)

        assert "response-content" in html
        assert "citations-list" in html or "citation-container" in html
        assert "Evidence" in html

    def test_format_without_sources_section(self):
        """Test formatting without sources section."""
        answer = "The result is X [1]."
        sources = [{"id": "s1", "title": "Evidence", "type": "document"}]

        html = format_response_with_sources(answer, sources, include_sources_section=False)

        assert "response-content" in html
        # The inline citation marker should still be present, but not the full citations list
        assert "citations-list" not in html or "citation-container" not in html

    def test_format_includes_javascript(self):
        """Test that JavaScript is included."""
        answer = "Text [1]"
        sources = [{"id": "s1", "title": "Source"}]

        html = format_response_with_sources(answer, sources)

        assert "<script>" in html
        assert "toggleCitation" in html


# ============================================================================
# Test CSS and JavaScript
# ============================================================================

class TestCitationCSS:
    """Tests for CSS definitions."""

    def test_css_contains_required_classes(self):
        """Verify CSS contains all required class definitions."""
        required_classes = [
            ".citation-container",
            ".citation-marker",
            ".citation-card",
            ".citation-header",
            ".citation-title",
            ".citation-excerpt",
            ".source-badge",
            ".relevance-score",
            ".citations-list"
        ]
        for class_name in required_classes:
            assert class_name in CITATION_CSS, f"Missing CSS class: {class_name}"

    def test_css_contains_responsive_styles(self):
        """Verify CSS contains responsive media queries."""
        assert "@media (max-width: 768px)" in CITATION_CSS

    def test_css_contains_accessibility_styles(self):
        """Verify CSS contains accessibility media queries."""
        assert "@media (prefers-contrast: high)" in CITATION_CSS
        assert "@media (prefers-reduced-motion: reduce)" in CITATION_CSS

    def test_css_contains_print_styles(self):
        """Verify CSS contains print styles."""
        assert "@media print" in CITATION_CSS


class TestCitationJS:
    """Tests for JavaScript code."""

    def test_js_contains_toggle_function(self):
        """Verify toggle function exists."""
        assert "function toggleCitation" in CITATION_JS

    def test_js_contains_expand_function(self):
        """Verify expand function exists."""
        assert "function expandCitation" in CITATION_JS

    def test_js_contains_filter_function(self):
        """Verify filter function exists."""
        assert "function filterCitations" in CITATION_JS

    def test_js_contains_keyboard_navigation(self):
        """Verify keyboard navigation handler."""
        assert "keydown" in CITATION_JS
        assert "Enter" in CITATION_JS


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for citation components."""

    def test_full_citation_workflow(self):
        """Test complete citation workflow."""
        # Create citations
        citations = [
            CitationSource(
                citation_id="int-1",
                title="Policy Document A",
                source_type=SourceType.DOCUMENT,
                excerpt="Key policy provisions state that...",
                full_content="Full text of the policy document...",
                author="Legal Dept",
                date="2024-01-01",
                page_number=5,
                relevance_score=0.92
            ),
            CitationSource(
                citation_id="int-2",
                title="Industry Report",
                source_type=SourceType.WEBPAGE,
                excerpt="Market analysis shows...",
                url="https://example.com/report",
                relevance_score=0.78
            )
        ]

        # Create response text
        response = "According to internal policies [1], our approach aligns with industry standards [2]."

        # Process inline citations
        inline_html = create_inline_text_with_citations(response, citations)
        assert "[1]" not in inline_html
        assert "[2]" not in inline_html
        assert inline_html.count("citation-marker") == 2

        # Create citations list
        list_html = create_citations_list_html(citations)
        assert "Policy Document A" in list_html
        assert "Industry Report" in list_html
        assert "92%" in list_html  # Relevance score

    def test_citation_group_management(self):
        """Test managing citations in a group."""
        group = CitationGroup(response_id="test-response")

        # Add citations from different sources
        group.add_citation(CitationSource(
            citation_id="g1",
            title="Database Record",
            source_type=SourceType.DATABASE
        ))
        group.add_citation(CitationSource(
            citation_id="g2",
            title="Graph Entity",
            source_type=SourceType.KNOWLEDGE_GRAPH
        ))

        # Verify group management
        assert len(group.citations) == 2
        assert group.get_citation("g1").source_type == SourceType.DATABASE
        assert group.get_citation("g2").source_type == SourceType.KNOWLEDGE_GRAPH

    def test_xss_prevention(self):
        """Test that XSS attacks are prevented."""
        malicious_citation = CitationSource(
            citation_id="xss-test",
            title='<script>alert("XSS")</script>',
            excerpt='<img src=x onerror="alert(1)">',
            author='<a href="javascript:void(0)">Click</a>'
        )

        html = create_citation_card_html(malicious_citation, 1)

        # Verify script tags are escaped (raw tags should not appear)
        assert "<script>" not in html
        # The content is escaped, so <script> becomes &lt;script&gt;
        assert "&lt;script&gt;" in html
        # Original unescaped attributes should not appear
        assert 'onerror="alert(1)"' not in html
        # Escaped version should be present
        assert "onerror=&quot;" in html or "&lt;img" in html

    def test_empty_and_none_values(self):
        """Test handling of empty and None values."""
        citation = CitationSource(
            citation_id="empty-test",
            title="Minimal Citation",
            source_type=SourceType.UNKNOWN
        )

        html = create_citation_card_html(citation, 1)

        # Should render without errors
        assert "Minimal Citation" in html
        assert "citation-card" in html
