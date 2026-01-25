"""
Snippet Generation Service

Extracts relevant snippets from search results and highlights matched keywords.
Provides formatted results with metadata for presentation.

Features:
- Extract snippets around matched keywords
- Keyword highlighting with configurable tags
- Metadata formatting (relevance score, source, department)
- Batch processing support
- Context window configuration

Usage:
    from app.services.snippet_service import get_snippet_service

    service = get_snippet_service()
    formatted_results = service.format_results(
        search_results,
        query="California insurance"
    )

    for result in formatted_results:
        print(f"Snippet: {result.highlighted_snippet}")
        print(f"Source: {result.source}")
        print(f"Score: {result.relevance_score}")
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.services.hybrid_search_service import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class SnippetConfig:
    """Configuration for snippet generation"""
    snippet_length: int = 200  # Maximum snippet length in characters
    context_window: int = 50  # Characters of context before/after keyword
    highlight_start: str = "<mark>"  # HTML tag for highlighting
    highlight_end: str = "</mark>"  # HTML tag for highlighting
    max_highlights: int = 10  # Maximum number of highlights per snippet


@dataclass
class SnippetResult:
    """Result of snippet extraction"""
    snippet: str
    keyword_positions: List[int] = field(default_factory=list)
    is_truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "snippet": self.snippet,
            "keyword_positions": self.keyword_positions,
            "is_truncated": self.is_truncated
        }


@dataclass
class FormattedResult:
    """Formatted search result with snippet and metadata"""
    chunk_id: str
    snippet: str
    highlighted_snippet: str
    relevance_score: float
    source: Optional[str] = None
    department: Optional[str] = None
    file_type: Optional[str] = None
    b2_url: Optional[str] = None
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "chunk_id": self.chunk_id,
            "snippet": self.snippet,
            "highlighted_snippet": self.highlighted_snippet,
            "relevance_score": self.relevance_score,
            "source": self.source,
            "department": self.department,
            "file_type": self.file_type,
            "b2_url": self.b2_url,
            "rank": self.rank,
            "metadata": self.metadata
        }


class SnippetService:
    """
    Service for generating snippets and highlighting keywords

    Features:
    - Extract relevant snippets around matched keywords
    - Highlight keywords with configurable HTML tags
    - Format results with metadata for presentation
    - Batch processing support
    """

    def __init__(self, config: Optional[SnippetConfig] = None):
        """
        Initialize snippet service

        Args:
            config: Snippet configuration
        """
        self.config = config or SnippetConfig()

        logger.info(
            f"Initialized SnippetService "
            f"(snippet_length={self.config.snippet_length}, "
            f"context_window={self.config.context_window})"
        )

    def extract_snippet(
        self,
        result: SearchResult,
        query: str
    ) -> SnippetResult:
        """
        Extract relevant snippet from search result content

        Args:
            result: Search result to extract snippet from
            query: Search query to find in content

        Returns:
            SnippetResult with extracted snippet and metadata
        """
        content = result.content
        if not content:
            return SnippetResult(snippet="", keyword_positions=[])

        if not query:
            # No query - return beginning of content
            snippet = content[:self.config.snippet_length]
            return SnippetResult(
                snippet=snippet,
                is_truncated=len(content) > self.config.snippet_length
            )

        # Find first keyword match (case-insensitive)
        keywords = self._extract_keywords(query)
        match_pos = -1

        for keyword in keywords:
            pos = content.lower().find(keyword.lower())
            if pos != -1:
                match_pos = pos
                break

        if match_pos == -1:
            # No match found - return beginning
            snippet = content[:self.config.snippet_length]
            return SnippetResult(
                snippet=snippet,
                is_truncated=len(content) > self.config.snippet_length
            )

        # Extract snippet centered on match
        start = max(0, match_pos - self.config.context_window)
        end = min(len(content), match_pos + self.config.snippet_length - self.config.context_window)

        # Adjust to word boundaries if possible
        snippet = content[start:end]

        # Trim to word boundaries
        if start > 0:
            # Find first space to avoid cutting words
            first_space = snippet.find(' ')
            if first_space != -1 and first_space < 20:
                snippet = snippet[first_space + 1:]

        if end < len(content):
            # Find last space to avoid cutting words
            last_space = snippet.rfind(' ')
            if last_space != -1 and last_space > len(snippet) - 20:
                snippet = snippet[:last_space]

        # Ensure snippet is not too long
        if len(snippet) > self.config.snippet_length:
            snippet = snippet[:self.config.snippet_length]
            # Trim to last complete word
            last_space = snippet.rfind(' ')
            if last_space != -1:
                snippet = snippet[:last_space]

        return SnippetResult(
            snippet=snippet.strip(),
            is_truncated=True
        )

    def highlight_keywords(
        self,
        text: str,
        query: str
    ) -> str:
        """
        Highlight keywords in text

        Args:
            text: Text to highlight keywords in
            query: Query containing keywords to highlight

        Returns:
            Text with keywords wrapped in highlight tags
        """
        if not query or not text:
            return text

        keywords = self._extract_keywords(query)
        highlighted = text
        highlight_count = 0

        # Sort keywords by length (longest first) to avoid partial matches
        keywords.sort(key=len, reverse=True)

        for keyword in keywords:
            if highlight_count >= self.config.max_highlights:
                break

            # Escape special regex characters
            escaped_keyword = re.escape(keyword)

            # Case-insensitive replacement, preserving original case
            pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)

            # Count how many times we'll replace
            matches = list(pattern.finditer(highlighted))
            remaining_highlights = self.config.max_highlights - highlight_count

            if len(matches) > remaining_highlights:
                matches = matches[:remaining_highlights]

            # Replace matches
            for match in reversed(matches):  # Reverse to maintain positions
                start, end = match.span()
                matched_text = highlighted[start:end]
                highlighted = (
                    highlighted[:start] +
                    f"{self.config.highlight_start}{matched_text}{self.config.highlight_end}" +
                    highlighted[end:]
                )
                highlight_count += 1

        return highlighted

    def format_result(
        self,
        result: SearchResult,
        snippet_result: SnippetResult,
        query: str
    ) -> FormattedResult:
        """
        Format search result with snippet and metadata

        Args:
            result: Original search result
            snippet_result: Extracted snippet
            query: Search query for highlighting

        Returns:
            FormattedResult with snippet and metadata
        """
        highlighted_snippet = self.highlight_keywords(snippet_result.snippet, query)

        return FormattedResult(
            chunk_id=result.chunk_id,
            snippet=snippet_result.snippet,
            highlighted_snippet=highlighted_snippet,
            relevance_score=result.score,
            source=result.metadata.get("filename"),
            department=result.metadata.get("department"),
            file_type=result.metadata.get("file_type"),
            b2_url=result.metadata.get("b2_url"),
            rank=result.rank,
            metadata=result.metadata
        )

    def format_results(
        self,
        results: List[SearchResult],
        query: str
    ) -> List[FormattedResult]:
        """
        Format multiple search results with snippets

        Args:
            results: List of search results
            query: Search query for snippet extraction and highlighting

        Returns:
            List of formatted results
        """
        formatted_results = []

        for result in results:
            snippet_result = self.extract_snippet(result, query)
            formatted = self.format_result(result, snippet_result, query)
            formatted_results.append(formatted)

        logger.debug(f"Formatted {len(formatted_results)} results with snippets")

        return formatted_results

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract individual keywords from query

        Args:
            query: Search query

        Returns:
            List of keywords
        """
        # Simple tokenization - split on whitespace
        keywords = query.split()

        # Remove very short words (< 2 chars) and common words
        keywords = [k for k in keywords if len(k) >= 2]

        return keywords


# Singleton instance
_snippet_service: Optional[SnippetService] = None


def get_snippet_service(
    config: Optional[SnippetConfig] = None
) -> SnippetService:
    """
    Get or create singleton snippet service instance

    Args:
        config: Optional snippet configuration

    Returns:
        SnippetService instance
    """
    global _snippet_service

    if _snippet_service is None:
        _snippet_service = SnippetService(config=config)

    return _snippet_service
