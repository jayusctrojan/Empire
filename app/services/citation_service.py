"""
Empire v7.3 - Citation Service
Extracts source metadata from RAG results and formats inline citations

Task 15: Update Chat Endpoint to Include Inline Citations
- Subtask 15.1: Source Metadata Retrieval from RAG
- Subtask 15.2: Citation Formatting Service
- Subtask 15.3: Inline Citation Integration

Author: Claude Code
Date: 2025-01-25
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CitationStyle(Enum):
    """Supported citation styles"""
    NUMERIC = "numeric"        # [1], [2], [3]
    AUTHOR_DATE = "author_date"  # (Smith, 2024)
    FOOTNOTE = "footnote"      # ¹, ², ³


@dataclass
class SourceMetadata:
    """
    Source metadata extracted from a document chunk

    Matches the source_metadata schema from Task 14:
    {
        "title": str,
        "author": str,
        "publication_date": str (YYYY-MM-DD),
        "page_count": int,
        "document_type": str,
        "language": str,
        "extracted_at": str (ISO timestamp),
        "extraction_method": str,
        "confidence_score": float (0.0-1.0),
        "additional_metadata": dict
    }
    """
    title: str
    author: Optional[str] = None
    publication_date: Optional[str] = None
    page_count: Optional[int] = None
    document_type: Optional[str] = None
    language: str = "en"
    confidence_score: float = 0.0
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None  # Specific page within document
    chunk_index: Optional[int] = None  # Position of chunk in document
    relevance_score: Optional[float] = None  # Search relevance score
    additional_metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_chunk_metadata(
        cls,
        chunk_data: Dict[str, Any],
        relevance_score: Optional[float] = None
    ) -> "SourceMetadata":
        """
        Create SourceMetadata from a chunk's metadata dictionary

        Args:
            chunk_data: Dictionary containing chunk and source metadata
            relevance_score: Optional search relevance score

        Returns:
            SourceMetadata instance
        """
        # Extract source_metadata if nested
        source_meta = chunk_data.get("source_metadata", {})
        if not source_meta:
            source_meta = chunk_data.get("metadata", {}).get("source_metadata", {})

        # Also check for flat structure
        if not source_meta:
            source_meta = chunk_data

        # Extract page number from chunk metadata
        chunk_meta = chunk_data.get("metadata", {})
        page_number = chunk_meta.get("page_number") or chunk_meta.get("page")

        return cls(
            title=source_meta.get("title") or chunk_data.get("filename", "Unknown Document"),
            author=source_meta.get("author"),
            publication_date=source_meta.get("publication_date"),
            page_count=source_meta.get("page_count"),
            document_type=source_meta.get("document_type") or chunk_data.get("file_type"),
            language=source_meta.get("language", "en"),
            confidence_score=source_meta.get("confidence_score", 0.0),
            chunk_id=chunk_data.get("id") or chunk_data.get("chunk_id"),
            document_id=chunk_data.get("document_id"),
            page_number=page_number,
            chunk_index=chunk_data.get("chunk_index"),
            relevance_score=relevance_score,
            additional_metadata=source_meta.get("additional_metadata", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "title": self.title,
            "author": self.author,
            "publication_date": self.publication_date,
            "page_count": self.page_count,
            "document_type": self.document_type,
            "language": self.language,
            "confidence_score": self.confidence_score,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "relevance_score": self.relevance_score,
            "additional_metadata": self.additional_metadata
        }


@dataclass
class Citation:
    """
    A formatted citation with reference number and full metadata
    """
    citation_number: int
    marker: str  # e.g., "[1]", "(Smith, 2024)", "¹"
    source: SourceMetadata
    formatted_citation: str  # Full formatted citation text

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "citation_number": self.citation_number,
            "marker": self.marker,
            "source": self.source.to_dict(),
            "formatted_citation": self.formatted_citation
        }


@dataclass
class CitedResponse:
    """
    AI response with inline citations and citation list
    """
    response_text: str  # Response with inline citation markers
    citations: List[Citation]
    total_sources: int
    citation_style: CitationStyle

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "response_text": self.response_text,
            "citations": [c.to_dict() for c in self.citations],
            "total_sources": self.total_sources,
            "citation_style": self.citation_style.value
        }


class CitationService:
    """
    Service for extracting source metadata and formatting citations

    Features:
    - Extract source metadata from RAG search results
    - Deduplicate sources across multiple chunks
    - Format citations in multiple styles (numeric, author-date, footnote)
    - Generate inline citation markers
    - Create citation list for response footer
    """

    def __init__(
        self,
        default_style: CitationStyle = CitationStyle.NUMERIC,
        include_page_numbers: bool = True,
        include_confidence: bool = False
    ):
        """
        Initialize citation service

        Args:
            default_style: Default citation style to use
            include_page_numbers: Include page numbers in citations when available
            include_confidence: Include confidence scores in citations
        """
        self.default_style = default_style
        self.include_page_numbers = include_page_numbers
        self.include_confidence = include_confidence

        logger.info(
            f"CitationService initialized "
            f"(style={default_style.value}, "
            f"page_numbers={include_page_numbers})"
        )

    def extract_sources_from_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[SourceMetadata]:
        """
        Extract source metadata from search result chunks

        Args:
            chunks: List of chunk dictionaries from RAG search

        Returns:
            List of SourceMetadata objects (deduplicated by document)
        """
        sources: Dict[str, SourceMetadata] = {}  # document_id -> SourceMetadata

        for chunk in chunks:
            try:
                # Get relevance score if available
                relevance = chunk.get("score") or chunk.get("similarity") or chunk.get("relevance_score")

                # Create source metadata from chunk
                source = SourceMetadata.from_chunk_metadata(chunk, relevance)

                # Use document_id for deduplication, fallback to chunk_id
                key = source.document_id or source.chunk_id or source.title

                if key not in sources:
                    sources[key] = source
                else:
                    # Update with better relevance score if this chunk is more relevant
                    existing = sources[key]
                    if relevance and (not existing.relevance_score or relevance > existing.relevance_score):
                        # Keep the more relevant chunk's page number
                        existing.relevance_score = relevance
                        if source.page_number:
                            existing.page_number = source.page_number
                        if source.chunk_index:
                            existing.chunk_index = source.chunk_index

            except Exception as e:
                logger.warning(f"Failed to extract source metadata from chunk: {e}")
                continue

        # Sort by relevance score (highest first)
        sorted_sources = sorted(
            sources.values(),
            key=lambda s: s.relevance_score or 0.0,
            reverse=True
        )

        logger.info(f"Extracted {len(sorted_sources)} unique sources from {len(chunks)} chunks")
        return sorted_sources

    def format_citation(
        self,
        source: SourceMetadata,
        citation_number: int,
        style: Optional[CitationStyle] = None
    ) -> Citation:
        """
        Format a single citation

        Args:
            source: Source metadata
            citation_number: Sequential citation number
            style: Citation style (uses default if not specified)

        Returns:
            Formatted Citation object
        """
        style = style or self.default_style

        # Generate marker based on style
        if style == CitationStyle.NUMERIC:
            marker = f"[{citation_number}]"
        elif style == CitationStyle.AUTHOR_DATE:
            author = source.author or "Unknown"
            year = source.publication_date[:4] if source.publication_date else "n.d."
            # Use last name for author-date citations (e.g., "John Doe" -> "Doe")
            marker = f"({author.split()[-1] if ' ' in author else author}, {year})"
        else:  # FOOTNOTE
            superscript = "".join(
                chr(0x2070 + int(d)) if d != '1' else '\u00B9'
                for d in str(citation_number)
            )
            marker = superscript

        # Generate full citation text
        formatted = self._format_full_citation(source, citation_number)

        return Citation(
            citation_number=citation_number,
            marker=marker,
            source=source,
            formatted_citation=formatted
        )

    def _format_full_citation(
        self,
        source: SourceMetadata,
        citation_number: int
    ) -> str:
        """
        Generate full formatted citation text

        Args:
            source: Source metadata
            citation_number: Citation number

        Returns:
            Formatted citation string
        """
        parts = [f"[{citation_number}]"]

        # Title (required)
        parts.append(f'"{source.title}"')

        # Author
        if source.author:
            parts.append(f"by {source.author}")

        # Document type
        if source.document_type:
            parts.append(f"({source.document_type.upper()})")

        # Publication date
        if source.publication_date:
            parts.append(f"Published: {source.publication_date}")

        # Page number
        if self.include_page_numbers and source.page_number:
            parts.append(f"Page {source.page_number}")

        # Confidence score
        if self.include_confidence and source.confidence_score:
            parts.append(f"[Confidence: {source.confidence_score:.0%}]")

        return " | ".join(parts)

    def create_citations_for_response(
        self,
        chunks: List[Dict[str, Any]],
        style: Optional[CitationStyle] = None
    ) -> Tuple[List[Citation], Dict[str, str]]:
        """
        Create citations from chunks and return mapping for inline insertion

        Args:
            chunks: List of chunk dictionaries from RAG search
            style: Citation style to use

        Returns:
            Tuple of (citations list, document_id -> marker mapping)
        """
        style = style or self.default_style

        # Extract and deduplicate sources
        sources = self.extract_sources_from_chunks(chunks)

        citations = []
        marker_map: Dict[str, str] = {}  # document_id/chunk_id -> marker

        for i, source in enumerate(sources, 1):
            citation = self.format_citation(source, i, style)
            citations.append(citation)

            # Map both document_id and chunk_id to the marker
            key = source.document_id or source.chunk_id or source.title
            marker_map[key] = citation.marker

            # Also map chunk_id if we used document_id as key
            if source.chunk_id and source.document_id:
                marker_map[source.chunk_id] = citation.marker

        return citations, marker_map

    def insert_inline_citations(
        self,
        response_text: str,
        chunks: List[Dict[str, Any]],
        style: Optional[CitationStyle] = None
    ) -> CitedResponse:
        """
        Insert inline citations into response text based on chunk usage

        This method analyzes which chunks contributed to which parts of the
        response and inserts appropriate citation markers.

        Args:
            response_text: AI-generated response text
            chunks: List of chunks that were used to generate the response
            style: Citation style to use

        Returns:
            CitedResponse with inline citations and citation list
        """
        style = style or self.default_style

        # Create citations and marker mapping
        citations, marker_map = self.create_citations_for_response(chunks, style)

        if not citations:
            return CitedResponse(
                response_text=response_text,
                citations=[],
                total_sources=0,
                citation_style=style
            )

        # For now, append all citations at the end of relevant paragraphs
        # A more sophisticated approach would match chunk content to response sentences
        cited_text = self._add_citations_to_response(
            response_text,
            chunks,
            marker_map,
            citations
        )

        return CitedResponse(
            response_text=cited_text,
            citations=citations,
            total_sources=len(citations),
            citation_style=style
        )

    def _add_citations_to_response(
        self,
        response_text: str,
        chunks: List[Dict[str, Any]],
        marker_map: Dict[str, str],
        citations: List[Citation]
    ) -> str:
        """
        Add citation markers to response text

        Strategy:
        1. If response has multiple paragraphs, add citations at end of relevant paragraphs
        2. If single paragraph, add all citations at the end
        3. Avoid duplicate citations in close proximity

        Args:
            response_text: Original response text
            chunks: Source chunks
            marker_map: Mapping of chunk/document IDs to citation markers
            citations: List of formatted citations

        Returns:
            Response text with inline citation markers
        """
        if not citations:
            return response_text

        # Split into paragraphs
        paragraphs = response_text.split('\n\n')

        if len(paragraphs) == 1:
            # Single paragraph - add all unique citations at the end
            unique_markers = list(dict.fromkeys(marker_map.values()))
            citation_str = " ".join(unique_markers)

            # Add citations before any trailing punctuation
            text = paragraphs[0].rstrip()
            if text and text[-1] in '.!?':
                return f"{text[:-1]} {citation_str}{text[-1]}"
            return f"{text} {citation_str}"

        # Multiple paragraphs - distribute citations based on chunk relevance
        # For now, add citations to the last content paragraph
        cited_paragraphs = []
        citations_added = False

        for i, para in enumerate(paragraphs):
            # Skip empty paragraphs
            if not para.strip():
                cited_paragraphs.append(para)
                continue

            # Add citations to the last substantive paragraph
            if i == len(paragraphs) - 1 or (i == len(paragraphs) - 2 and not paragraphs[-1].strip()):
                if not citations_added:
                    unique_markers = list(dict.fromkeys(marker_map.values()))
                    citation_str = " ".join(unique_markers)

                    text = para.rstrip()
                    if text and text[-1] in '.!?':
                        para = f"{text[:-1]} {citation_str}{text[-1]}"
                    else:
                        para = f"{text} {citation_str}"
                    citations_added = True

            cited_paragraphs.append(para)

        return '\n\n'.join(cited_paragraphs)

    def format_citations_footer(
        self,
        citations: List[Citation],
        header: str = "**Sources:**"
    ) -> str:
        """
        Format citations as a footer section for the response

        Args:
            citations: List of Citation objects
            header: Header text for the sources section

        Returns:
            Formatted footer string
        """
        if not citations:
            return ""

        lines = [header]
        for citation in citations:
            lines.append(f"- {citation.formatted_citation}")

        return "\n".join(lines)

    def create_source_attribution_json(
        self,
        citations: List[Citation]
    ) -> List[Dict[str, Any]]:
        """
        Create source attribution JSON for storing in chat_messages.source_attribution

        Args:
            citations: List of Citation objects

        Returns:
            List of dictionaries suitable for JSONB storage
        """
        return [
            {
                "citation_number": c.citation_number,
                "marker": c.marker,
                "title": c.source.title,
                "author": c.source.author,
                "document_id": c.source.document_id,
                "chunk_id": c.source.chunk_id,
                "page_number": c.source.page_number,
                "document_type": c.source.document_type,
                "relevance_score": c.source.relevance_score,
                "confidence_score": c.source.confidence_score
            }
            for c in citations
        ]


# Singleton instance
_citation_service: Optional[CitationService] = None


def get_citation_service(
    default_style: CitationStyle = CitationStyle.NUMERIC,
    include_page_numbers: bool = True,
    include_confidence: bool = False
) -> CitationService:
    """
    Get singleton instance of CitationService

    Args:
        default_style: Default citation style
        include_page_numbers: Include page numbers in citations
        include_confidence: Include confidence scores

    Returns:
        CitationService instance
    """
    global _citation_service

    if _citation_service is None:
        _citation_service = CitationService(
            default_style=default_style,
            include_page_numbers=include_page_numbers,
            include_confidence=include_confidence
        )

    return _citation_service
