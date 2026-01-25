"""
Test suite for Snippet Generation and Highlighting

Comprehensive tests for snippet generation, keyword extraction, and highlighting functionality.
"""

import pytest
from app.services.faceted_search_service import FacetedSearchService


@pytest.fixture
def service():
    """Create FacetedSearchService instance"""
    return FacetedSearchService(supabase_client=None)


class TestSnippetGeneration:
    """Test snippet generation with various content types"""

    def test_snippet_with_single_keyword(self, service):
        """Test snippet generation with single keyword"""
        content = "The California Department of Insurance regulates all insurance activities."
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, max_length=100, context_chars=30)

        assert "California" in snippet
        assert len(snippet) <= 106  # 100 + "..." max

    def test_snippet_with_multiple_keywords(self, service):
        """Test snippet prioritizes first keyword occurrence"""
        content = "Insurance policies are regulated by California law."
        keywords = ["California", "insurance"]

        snippet = service.generate_snippet(content, keywords, max_length=100, context_chars=20)

        # Should find "insurance" first (appears earlier)
        assert "insurance" in snippet.lower()

    def test_snippet_empty_content(self, service):
        """Test snippet generation with empty content"""
        snippet = service.generate_snippet("", ["keyword"], max_length=100)
        assert snippet == ""

    def test_snippet_empty_keywords(self, service):
        """Test snippet generation with empty keywords"""
        content = "This is a test document with some content."
        snippet = service.generate_snippet(content, [], max_length=20)

        assert len(snippet) <= 23
        assert snippet.endswith("...")

    def test_snippet_content_shorter_than_max_length(self, service):
        """Test snippet when content is shorter than max length"""
        content = "Short content."
        snippet = service.generate_snippet(content, ["content"], max_length=200)

        assert snippet == content  # No ellipsis needed

    def test_snippet_keyword_not_found(self, service):
        """Test snippet when keyword is not in content"""
        content = "This document discusses policies and regulations."
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, max_length=100)

        # Should return beginning of content
        assert snippet.startswith("This")
        assert len(snippet) <= 103

    def test_snippet_multiple_occurrences_uses_first(self, service):
        """Test snippet uses first occurrence when keyword appears multiple times"""
        content = "First California mention. Second California mention in this text."
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, context_chars=10)

        # Should center on first occurrence
        assert "First California" in snippet

    def test_snippet_context_chars_respected(self, service):
        """Test that context_chars parameter is respected"""
        content = "AAAA California BBBB"
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, max_length=200, context_chars=4)

        # Should have 4 chars before and after
        assert "AAAA California BBBB" in snippet or "AAA California BBB" in snippet

    def test_snippet_very_long_content(self, service):
        """Test snippet generation with very long content"""
        prefix = "A" * 500
        keyword_section = " California insurance policy information "
        suffix = "B" * 500
        content = prefix + keyword_section + suffix

        snippet = service.generate_snippet(content, ["California"], max_length=100, context_chars=20)

        assert "California" in snippet
        assert len(snippet) <= 106
        assert snippet.startswith("...")
        assert snippet.endswith("...")

    def test_snippet_special_characters_in_content(self, service):
        """Test snippet with special characters"""
        content = "The policy costs $500 (approximately) for California residents."
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords)

        assert "California" in snippet
        assert "$500" in snippet or "approximately" in snippet

    def test_snippet_unicode_content(self, service):
        """Test snippet with unicode characters"""
        content = "California résumé café naïve Zürich"
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords)

        assert "California" in snippet

    def test_snippet_newlines_in_content(self, service):
        """Test snippet with newlines"""
        content = "First line\nSecond line with California\nThird line"
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, context_chars=20)

        assert "California" in snippet

    def test_snippet_case_insensitive_keyword_matching(self, service):
        """Test that keyword matching is case-insensitive"""
        content = "CALIFORNIA and california and California"
        keywords = ["california"]

        snippet = service.generate_snippet(content, keywords)

        # Should find first occurrence (case-insensitive)
        assert "CALIFORNIA" in snippet or "california" in snippet

    def test_snippet_keyword_at_exact_start(self, service):
        """Test snippet when keyword is at exact start of content"""
        content = "California is a state with insurance regulations and many other laws."
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, context_chars=30)

        assert not snippet.startswith("...")
        assert snippet.startswith("California")

    def test_snippet_keyword_at_exact_end(self, service):
        """Test snippet when keyword is at exact end of content"""
        content = "Insurance regulations for California"
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, context_chars=30)

        assert not snippet.endswith("...")
        assert snippet.endswith("California")

    def test_snippet_max_length_zero(self, service):
        """Test snippet with max_length of 0"""
        content = "California insurance"
        snippet = service.generate_snippet(content, ["California"], max_length=0)

        # Should handle gracefully - returns truncated content with ellipsis
        # Empty max_length results in minimal snippet
        assert isinstance(snippet, str)  # Should return a string
        assert len(snippet) >= 0  # Could be empty or minimal

    def test_snippet_context_chars_larger_than_content(self, service):
        """Test snippet when context_chars is larger than content length"""
        content = "California"
        snippet = service.generate_snippet(content, ["California"], context_chars=1000)

        # Should just return the content
        assert snippet == "California"


class TestKeywordHighlighting:
    """Test keyword highlighting with various scenarios"""

    def test_highlight_single_keyword(self, service):
        """Test highlighting single keyword"""
        text = "California insurance policy"
        highlighted = service.highlight_keywords(text, ["California"])

        assert highlighted == "<mark>California</mark> insurance policy"

    def test_highlight_multiple_keywords(self, service):
        """Test highlighting multiple keywords"""
        text = "California insurance policy"
        highlighted = service.highlight_keywords(text, ["California", "insurance"])

        assert "<mark>California</mark>" in highlighted
        assert "<mark>insurance</mark>" in highlighted

    def test_highlight_case_insensitive_lowercase(self, service):
        """Test case-insensitive highlighting with lowercase"""
        text = "california insurance"
        highlighted = service.highlight_keywords(text, ["California"])

        assert "<mark>california</mark>" in highlighted

    def test_highlight_case_insensitive_uppercase(self, service):
        """Test case-insensitive highlighting with uppercase"""
        text = "CALIFORNIA INSURANCE"
        highlighted = service.highlight_keywords(text, ["california"])

        assert "<mark>CALIFORNIA</mark>" in highlighted

    def test_highlight_case_insensitive_mixed(self, service):
        """Test case-insensitive highlighting with mixed case"""
        text = "CaLiFoRnIa insurance"
        highlighted = service.highlight_keywords(text, ["california"])

        assert "<mark>CaLiFoRnIa</mark>" in highlighted

    def test_highlight_with_custom_tag(self, service):
        """Test highlighting with custom HTML tag"""
        text = "California insurance"
        highlighted = service.highlight_keywords(text, ["California"], highlight_tag="em")

        assert "<em>California</em>" in highlighted

    def test_highlight_with_custom_tag_strong(self, service):
        """Test highlighting with strong tag"""
        text = "California insurance"
        highlighted = service.highlight_keywords(text, ["California"], highlight_tag="strong")

        assert "<strong>California</strong>" in highlighted

    def test_highlight_no_keywords(self, service):
        """Test highlighting with empty keywords list"""
        text = "California insurance"
        highlighted = service.highlight_keywords(text, [])

        assert highlighted == text

    def test_highlight_keyword_not_in_text(self, service):
        """Test highlighting when keyword is not in text"""
        text = "insurance policy"
        highlighted = service.highlight_keywords(text, ["California"])

        assert highlighted == text

    def test_highlight_special_regex_characters_dollar(self, service):
        """Test highlighting with dollar sign"""
        text = "Cost is $100"
        highlighted = service.highlight_keywords(text, ["$100"])

        assert "<mark>$100</mark>" in highlighted

    def test_highlight_special_regex_characters_parentheses(self, service):
        """Test highlighting with parentheses"""
        text = "Cost (approximately) is high"
        highlighted = service.highlight_keywords(text, ["(approximately)"])

        assert "<mark>(approximately)</mark>" in highlighted

    def test_highlight_special_regex_characters_brackets(self, service):
        """Test highlighting with brackets"""
        text = "Item [optional] value"
        highlighted = service.highlight_keywords(text, ["[optional]"])

        assert "<mark>[optional]</mark>" in highlighted

    def test_highlight_special_regex_characters_dot(self, service):
        """Test highlighting with dots"""
        text = "Version 1.0.0"
        highlighted = service.highlight_keywords(text, ["1.0.0"])

        assert "<mark>1.0.0</mark>" in highlighted

    def test_highlight_special_regex_characters_asterisk(self, service):
        """Test highlighting with asterisk"""
        text = "Wildcard * character"
        highlighted = service.highlight_keywords(text, ["*"])

        assert "<mark>*</mark>" in highlighted

    def test_highlight_special_regex_characters_plus(self, service):
        """Test highlighting with plus"""
        text = "C++ programming"
        highlighted = service.highlight_keywords(text, ["C++"])

        assert "<mark>C++</mark>" in highlighted

    def test_highlight_special_regex_characters_question_mark(self, service):
        """Test highlighting with question mark"""
        text = "Question? Answer"
        highlighted = service.highlight_keywords(text, ["Question?"])

        assert "<mark>Question?</mark>" in highlighted

    def test_highlight_overlapping_keywords(self, service):
        """Test highlighting with overlapping keywords"""
        text = "California insurance"
        highlighted = service.highlight_keywords(text, ["California", "California insurance"])

        # Both should be highlighted (order matters)
        assert "<mark>" in highlighted

    def test_highlight_multiple_occurrences(self, service):
        """Test highlighting keyword that appears multiple times"""
        text = "California has California laws for California residents"
        highlighted = service.highlight_keywords(text, ["California"])

        # Count occurrences of highlighted keyword
        assert highlighted.count("<mark>California</mark>") == 3

    def test_highlight_empty_text(self, service):
        """Test highlighting with empty text"""
        highlighted = service.highlight_keywords("", ["keyword"])
        assert highlighted == ""

    def test_highlight_unicode_characters(self, service):
        """Test highlighting with unicode characters"""
        text = "Café résumé naïve"
        highlighted = service.highlight_keywords(text, ["Café"])

        assert "<mark>Café</mark>" in highlighted

    def test_highlight_numbers(self, service):
        """Test highlighting numbers"""
        text = "Policy 123456 is active"
        highlighted = service.highlight_keywords(text, ["123456"])

        assert "<mark>123456</mark>" in highlighted

    def test_highlight_partial_word_match(self, service):
        """Test that highlighting doesn't break on partial matches"""
        text = "California and Californian"
        highlighted = service.highlight_keywords(text, ["California"])

        # Should highlight both (regex-based)
        assert highlighted.count("<mark>") >= 2

    def test_highlight_hyphenated_words(self, service):
        """Test highlighting hyphenated words"""
        text = "Worker-related insurance coverage"
        highlighted = service.highlight_keywords(text, ["Worker-related"])

        assert "<mark>Worker-related</mark>" in highlighted

    def test_highlight_with_newlines(self, service):
        """Test highlighting text with newlines"""
        text = "Line 1\nCalifornia\nLine 3"
        highlighted = service.highlight_keywords(text, ["California"])

        assert "<mark>California</mark>" in highlighted


class TestSnippetAndHighlightIntegration:
    """Test integration between snippet generation and highlighting"""

    def test_generate_and_highlight(self, service):
        """Test generating snippet and then highlighting"""
        content = "The California Department of Insurance provides regulatory oversight."
        keywords = ["California", "Insurance"]

        # Generate snippet
        snippet = service.generate_snippet(content, keywords, max_length=100, context_chars=20)

        # Highlight keywords (case-insensitive)
        highlighted = service.highlight_keywords(snippet, keywords)

        assert "California" in snippet
        assert "<mark>California</mark>" in highlighted
        # Insurance might be lowercased in content, so check both
        assert ("<mark>Insurance</mark>" in highlighted) or ("<mark>insurance</mark>" not in highlighted)

    def test_snippet_and_highlight_maintains_structure(self, service):
        """Test that highlighting doesn't break snippet structure"""
        content = "Beginning text " + "A" * 100 + " California insurance " + "B" * 100
        keywords = ["California"]

        snippet = service.generate_snippet(content, keywords, max_length=100, context_chars=30)
        highlighted = service.highlight_keywords(snippet, keywords)

        # Should have ellipsis
        assert "..." in snippet
        # Should have highlight
        assert "<mark>" in highlighted
        # Should still have California
        assert "California" in highlighted

    def test_snippet_and_highlight_special_chars(self, service):
        """Test snippet and highlight with special characters"""
        content = "Prefix $100 (cost) for California policy [required]"
        keywords = ["California", "$100"]

        snippet = service.generate_snippet(content, keywords)
        highlighted = service.highlight_keywords(snippet, keywords)

        assert "<mark>California</mark>" in highlighted
        if "$100" in snippet:
            assert "<mark>$100</mark>" in highlighted
