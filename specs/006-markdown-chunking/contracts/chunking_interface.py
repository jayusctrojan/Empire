"""
Contract: MarkdownChunkerStrategy Interface

Feature: 006-markdown-chunking
Date: 2026-01-11

This file defines the interface contract for the MarkdownChunkerStrategy.
Implementation must satisfy all method signatures and docstring requirements.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from llama_index.core.schema import TextNode


@dataclass
class MarkdownSection:
    """
    A document section extracted from markdown content.

    Attributes:
        header: Full header text including # markers (e.g., '## Methods')
        header_text: Header text without # markers (e.g., 'Methods')
        level: Header level 1-6 (h1=1, h2=2, etc.)
        content: Section content including the header line
        start_line: Line number where section starts (0-indexed)
        end_line: Line number where section ends (exclusive)
        parent_headers: Parent header chain, e.g., ['# Chapter 1', '## Introduction']
    """

    header: str
    header_text: str
    level: int
    content: str
    start_line: int
    end_line: int
    parent_headers: list[str]


@dataclass
class MarkdownChunkerConfig:
    """
    Configuration for MarkdownChunkerStrategy.

    Attributes:
        max_chunk_size: Maximum tokens per chunk (default: 1024)
        chunk_overlap: Token overlap for sentence-split chunks (default: 200)
        min_headers_threshold: Minimum headers to trigger markdown splitting (default: 2)
        include_header_in_chunk: Include header in chunk content (default: True)
        preserve_hierarchy: Build and store header hierarchy (default: True)
        max_header_length: Max header text in metadata (default: 200)
    """

    max_chunk_size: int = 1024
    chunk_overlap: int = 200
    min_headers_threshold: int = 2
    include_header_in_chunk: bool = True
    preserve_hierarchy: bool = True
    max_header_length: int = 200


class ChunkingStrategy(ABC):
    """Abstract base class for all chunking strategies."""

    @abstractmethod
    def chunk(self, text: str, metadata: Optional[dict] = None) -> list[TextNode]:
        """
        Split text into chunks.

        Args:
            text: The text content to chunk
            metadata: Optional base metadata to include in all chunks

        Returns:
            List of TextNode objects with content and metadata
        """
        pass


class MarkdownChunkerStrategy(ChunkingStrategy):
    """
    Chunking strategy that splits markdown documents by headers.

    This strategy:
    1. Detects markdown headers in the input text
    2. Splits content into sections based on headers
    3. Preserves header hierarchy in chunk metadata
    4. Falls back to sentence splitting for oversized sections

    Usage:
        chunker = MarkdownChunkerStrategy()
        nodes = chunker.chunk(markdown_text)

    Each returned TextNode will have metadata including:
        - section_header: The header text for this section
        - header_level: Header level 1-6
        - header_hierarchy: Parent headers by level
        - is_header_split: True if split by header, False if sentence-split
        - chunk_index: Position within section
        - total_section_chunks: Total chunks in this section
    """

    def __init__(self, config: Optional[MarkdownChunkerConfig] = None):
        """
        Initialize the markdown chunker.

        Args:
            config: Configuration options. Uses defaults if not provided.
        """
        self.config = config or MarkdownChunkerConfig()

    def chunk(self, text: str, metadata: Optional[dict] = None) -> list[TextNode]:
        """
        Split markdown text into nodes by headers.

        Args:
            text: Markdown text to split
            metadata: Base metadata to include in all chunks

        Returns:
            List of TextNode objects, one per section (or multiple for large sections)

        Raises:
            ValueError: If text is empty
        """
        raise NotImplementedError("Implementation required")

    def is_markdown_content(self, text: str) -> bool:
        """
        Detect if text contains sufficient markdown headers.

        Args:
            text: Text to analyze

        Returns:
            True if text contains >= min_headers_threshold headers
        """
        raise NotImplementedError("Implementation required")

    def _split_by_headers(self, text: str) -> list[MarkdownSection]:
        """
        Extract sections from markdown text.

        Args:
            text: Markdown text to split

        Returns:
            List of MarkdownSection objects
        """
        raise NotImplementedError("Implementation required")

    def _build_header_hierarchy(
        self, sections: list[MarkdownSection], index: int
    ) -> dict[str, str]:
        """
        Build parent header chain for a section.

        Args:
            sections: All extracted sections
            index: Index of section to build hierarchy for

        Returns:
            Dict mapping 'h1', 'h2', etc. to header text
        """
        raise NotImplementedError("Implementation required")

    def _chunk_oversized_section(
        self, section: MarkdownSection, base_metadata: dict
    ) -> list[TextNode]:
        """
        Split an oversized section using sentence-aware splitting.

        Args:
            section: Section exceeding max_chunk_size
            base_metadata: Metadata to include in all sub-chunks

        Returns:
            List of TextNode objects for the subdivided section
        """
        raise NotImplementedError("Implementation required")

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count

        Returns:
            Token count
        """
        raise NotImplementedError("Implementation required")


# Type aliases for clarity
ChunkList = list[TextNode]
HeaderHierarchy = dict[str, str]
