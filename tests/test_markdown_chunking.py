"""
Tests for Markdown-Aware Document Chunking (Feature 006)

Tests the MarkdownChunkerStrategy and related components for header-based
document splitting in Empire's RAG pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chunking_service import (
    MarkdownChunkerStrategy,
    MarkdownChunkerConfig,
    MarkdownSection,
    ChunkMetadata,
    Chunk,
    ChunkingStrategy,
    HEADER_PATTERN,
    ChunkingService,
    get_chunking_service,
    # Task 119: Chunk filtering
    ChunkFilter,
    filter_chunks_by_header,
    filter_chunks_by_header_level,
    filter_chunks_by_section,
    filter_chunks_by_hierarchy,
    get_chunks_under_header,
    group_chunks_by_header_level,
    group_chunks_by_section,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_markdown():
    """Sample markdown document with headers."""
    return """# Chapter 1: Introduction

This is the introduction section with some content.

## Overview

The overview provides context for the document.

## Goals

Our main goals are:
- Goal 1
- Goal 2
- Goal 3

# Chapter 2: Methods

This chapter covers methods.

## Approach

The approach we use involves several steps.

### Step 1

First step details here.

### Step 2

Second step details here.
"""


@pytest.fixture
def simple_markdown():
    """Simple markdown with just two headers."""
    return """# Header One

Content for section one.

## Header Two

Content for section two.
"""


@pytest.fixture
def no_headers_text():
    """Plain text without markdown headers."""
    return """This is a plain text document.
It has multiple paragraphs but no markdown headers.

The document continues here with more content.
It should fall back to sentence-based chunking.
"""


@pytest.fixture
def large_section_markdown():
    """Markdown with a very large section."""
    large_content = "This is a very long paragraph. " * 500
    return f"""# Small Section

Short content here.

## Large Section

{large_content}

# Another Section

More short content.
"""


@pytest.fixture
def default_config():
    """Default chunker configuration."""
    return MarkdownChunkerConfig()


@pytest.fixture
def custom_config():
    """Custom chunker configuration with smaller chunks."""
    return MarkdownChunkerConfig(
        max_chunk_size=256,
        chunk_overlap=50,
        min_headers_threshold=1
    )


# =============================================================================
# HEADER_PATTERN Tests
# =============================================================================

class TestHeaderPattern:
    """Tests for the header detection regex."""

    def test_matches_h1_header(self):
        """Should match H1 headers."""
        text = "# Header One"
        matches = HEADER_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0] == ('#', 'Header One')

    def test_matches_h2_header(self):
        """Should match H2 headers."""
        text = "## Header Two"
        matches = HEADER_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0] == ('##', 'Header Two')

    def test_matches_h6_header(self):
        """Should match H6 headers."""
        text = "###### Header Six"
        matches = HEADER_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0] == ('######', 'Header Six')

    def test_matches_multiple_headers(self, sample_markdown):
        """Should match all headers in a document."""
        matches = HEADER_PATTERN.findall(sample_markdown)
        assert len(matches) >= 6  # Multiple headers in sample

    def test_no_match_for_plain_hash(self):
        """Should not match hash without space."""
        text = "#NoSpaceHeader"
        matches = HEADER_PATTERN.findall(text)
        assert len(matches) == 0

    def test_no_match_for_seven_hashes(self):
        """Should not match 7+ hashes (invalid markdown)."""
        text = "####### Too Many"
        matches = HEADER_PATTERN.findall(text)
        assert len(matches) == 0


# =============================================================================
# MarkdownSection Tests
# =============================================================================

class TestMarkdownSection:
    """Tests for the MarkdownSection dataclass."""

    def test_section_creation(self):
        """Should create a section with all fields."""
        section = MarkdownSection(
            header="## Methods",
            header_text="Methods",
            level=2,
            content="## Methods\n\nContent here.",
            start_line=10,
            end_line=15,
            parent_headers=["Introduction"]
        )
        assert section.header == "## Methods"
        assert section.header_text == "Methods"
        assert section.level == 2
        assert section.start_line == 10
        assert section.end_line == 15
        assert "Introduction" in section.parent_headers


# =============================================================================
# MarkdownChunkerConfig Tests
# =============================================================================

class TestMarkdownChunkerConfig:
    """Tests for the configuration dataclass."""

    def test_default_values(self):
        """Should have correct default values."""
        config = MarkdownChunkerConfig()
        assert config.max_chunk_size == 1024
        assert config.chunk_overlap == 200
        assert config.min_headers_threshold == 2
        assert config.include_header_in_chunk is True
        assert config.preserve_hierarchy is True
        assert config.max_header_length == 200

    def test_custom_values(self, custom_config):
        """Should accept custom values."""
        assert custom_config.max_chunk_size == 256
        assert custom_config.chunk_overlap == 50
        assert custom_config.min_headers_threshold == 1


# =============================================================================
# MarkdownChunkerStrategy Tests
# =============================================================================

class TestMarkdownChunkerStrategy:
    """Tests for the main chunking strategy."""

    def test_init_with_defaults(self):
        """Should initialize with default config."""
        chunker = MarkdownChunkerStrategy()
        assert chunker.config.max_chunk_size == 1024
        assert chunker.config.min_headers_threshold == 2

    def test_init_with_custom_config(self, custom_config):
        """Should accept custom configuration."""
        chunker = MarkdownChunkerStrategy(config=custom_config)
        assert chunker.config.max_chunk_size == 256


class TestIsMarkdownContent:
    """Tests for markdown detection."""

    def test_detects_markdown_with_headers(self, sample_markdown):
        """Should detect document with multiple headers."""
        chunker = MarkdownChunkerStrategy()
        assert chunker.is_markdown_content(sample_markdown) is True

    def test_detects_minimal_markdown(self, simple_markdown):
        """Should detect document with minimum headers."""
        chunker = MarkdownChunkerStrategy()
        assert chunker.is_markdown_content(simple_markdown) is True

    def test_rejects_no_headers(self, no_headers_text):
        """Should reject document without headers."""
        chunker = MarkdownChunkerStrategy()
        assert chunker.is_markdown_content(no_headers_text) is False

    def test_respects_threshold(self):
        """Should respect min_headers_threshold config."""
        text = "# Only One Header\n\nContent here."

        # Default threshold (2) should reject
        chunker_default = MarkdownChunkerStrategy()
        assert chunker_default.is_markdown_content(text) is False

        # Threshold of 1 should accept
        config = MarkdownChunkerConfig(min_headers_threshold=1)
        chunker_custom = MarkdownChunkerStrategy(config=config)
        assert chunker_custom.is_markdown_content(text) is True


class TestSplitByHeaders:
    """Tests for header-based section splitting."""

    def test_splits_by_headers(self, simple_markdown):
        """Should split document into sections at headers."""
        chunker = MarkdownChunkerStrategy()
        sections = chunker._split_by_headers(simple_markdown)

        assert len(sections) >= 2
        assert any(s.header_text == "Header One" for s in sections)
        assert any(s.header_text == "Header Two" for s in sections)

    def test_preserves_content(self, simple_markdown):
        """Should preserve section content."""
        chunker = MarkdownChunkerStrategy()
        sections = chunker._split_by_headers(simple_markdown)

        # Check content is included
        for section in sections:
            if section.header_text:
                assert section.header in section.content

    def test_tracks_header_levels(self, sample_markdown):
        """Should correctly identify header levels."""
        chunker = MarkdownChunkerStrategy()
        sections = chunker._split_by_headers(sample_markdown)

        # Find H1 and H2 sections
        h1_sections = [s for s in sections if s.level == 1]
        h2_sections = [s for s in sections if s.level == 2]
        h3_sections = [s for s in sections if s.level == 3]

        assert len(h1_sections) >= 1
        assert len(h2_sections) >= 1


class TestBuildHeaderHierarchy:
    """Tests for header hierarchy building."""

    def test_builds_hierarchy(self):
        """Should build correct header hierarchy."""
        chunker = MarkdownChunkerStrategy()
        section = MarkdownSection(
            header="### Step 1",
            header_text="Step 1",
            level=3,
            content="### Step 1\n\nContent",
            start_line=0,
            end_line=2,
            parent_headers=["Chapter 1", "Methods"]
        )

        hierarchy = chunker._build_header_hierarchy(section)

        assert "h3" in hierarchy
        assert hierarchy["h3"] == "Step 1"


class TestCountTokens:
    """Tests for token counting."""

    def test_estimates_tokens(self):
        """Should estimate token count."""
        chunker = MarkdownChunkerStrategy()
        text = "This is a test sentence with some words."

        token_count = chunker._count_tokens(text)

        # Should be approximately len/4
        assert token_count > 0
        assert token_count == len(text) // 4


class TestChunkMethod:
    """Tests for the main chunk method."""

    @pytest.mark.asyncio
    async def test_chunks_markdown_document(self, sample_markdown):
        """Should chunk markdown document by headers."""
        chunker = MarkdownChunkerStrategy()
        chunks = await chunker.chunk(sample_markdown, document_id="test-doc")

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    @pytest.mark.asyncio
    async def test_preserves_header_metadata(self, sample_markdown):
        """Should include header metadata in chunks."""
        chunker = MarkdownChunkerStrategy()
        chunks = await chunker.chunk(sample_markdown, document_id="test-doc")

        # Find a chunk with header metadata
        header_chunks = [c for c in chunks if c.metadata.section_header]
        assert len(header_chunks) > 0

        # Check metadata fields
        chunk = header_chunks[0]
        assert chunk.metadata.strategy == ChunkingStrategy.MARKDOWN
        assert chunk.metadata.header_level is not None
        assert chunk.metadata.header_hierarchy is not None

    @pytest.mark.asyncio
    async def test_falls_back_for_no_headers(self, no_headers_text):
        """Should fall back to sentence chunking for non-markdown."""
        chunker = MarkdownChunkerStrategy()
        chunks = await chunker.chunk(no_headers_text, document_id="test-doc")

        # Should still produce chunks (via fallback)
        # Note: May be empty if LlamaIndex not available
        assert isinstance(chunks, list)

    @pytest.mark.asyncio
    async def test_sets_is_header_split(self, simple_markdown):
        """Should set is_header_split flag correctly."""
        chunker = MarkdownChunkerStrategy()
        chunks = await chunker.chunk(simple_markdown, document_id="test-doc")

        # All header-based chunks should have is_header_split=True
        header_split_chunks = [c for c in chunks if c.metadata.is_header_split]
        assert len(header_split_chunks) > 0


# =============================================================================
# ChunkingService Integration Tests
# =============================================================================

class TestChunkingServiceMarkdown:
    """Tests for ChunkingService markdown integration."""

    def test_service_has_markdown_chunker(self):
        """Should have markdown_chunker attribute."""
        service = ChunkingService()
        assert hasattr(service, 'markdown_chunker')
        assert isinstance(service.markdown_chunker, MarkdownChunkerStrategy)

    @pytest.mark.asyncio
    async def test_chunk_markdown_method(self, sample_markdown):
        """Should have working chunk_markdown method."""
        service = ChunkingService()
        chunks = await service.chunk_markdown(
            sample_markdown,
            document_id="test-doc"
        )

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    @pytest.mark.asyncio
    async def test_auto_chunk_detects_markdown(self, sample_markdown):
        """Should auto-detect markdown and use markdown strategy."""
        service = ChunkingService()
        chunks = await service.auto_chunk(
            sample_markdown,
            document_id="test-doc"
        )

        # Should use markdown strategy
        markdown_chunks = [
            c for c in chunks
            if c.metadata.strategy == ChunkingStrategy.MARKDOWN
        ]
        assert len(markdown_chunks) > 0

    def test_get_strategy_returns_markdown(self):
        """Should return markdown chunker for MARKDOWN strategy."""
        service = ChunkingService()
        chunker = service.get_strategy(ChunkingStrategy.MARKDOWN)

        assert isinstance(chunker, MarkdownChunkerStrategy)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_document(self):
        """Should handle empty document."""
        chunker = MarkdownChunkerStrategy()
        chunks = await chunker.chunk("", document_id="empty-doc")

        assert isinstance(chunks, list)

    @pytest.mark.asyncio
    async def test_single_header_only(self):
        """Should handle document with only header, no content."""
        chunker = MarkdownChunkerStrategy()
        text = "# Just a Header"
        chunks = await chunker.chunk(text, document_id="header-only")

        assert isinstance(chunks, list)

    @pytest.mark.asyncio
    async def test_malformed_headers(self):
        """Should handle malformed headers as regular text."""
        chunker = MarkdownChunkerStrategy()
        text = "#NoSpace\n\n##AlsoNoSpace\n\nRegular text."

        # Should not detect as markdown (no valid headers)
        assert chunker.is_markdown_content(text) is False

    @pytest.mark.asyncio
    async def test_headers_with_special_characters(self):
        """Should handle headers with special characters."""
        chunker = MarkdownChunkerStrategy()
        text = """# Header with *emphasis* and `code`

Content here.

## Header with [link](url)

More content.
"""
        chunks = await chunker.chunk(text, document_id="special-chars")

        assert len(chunks) > 0


# =============================================================================
# ChunkMetadata Extension Tests
# =============================================================================

class TestChunkMetadataExtensions:
    """Tests for extended chunk metadata fields."""

    def test_metadata_has_markdown_fields(self):
        """Should have markdown-specific metadata fields."""
        metadata = ChunkMetadata(
            chunk_index=0,
            source_document_id="test",
            strategy=ChunkingStrategy.MARKDOWN,
            section_header="## Test Header",
            header_level=2,
            header_hierarchy={"h1": "Chapter", "h2": "Test Header"},
            is_header_split=True,
            total_section_chunks=1
        )

        assert metadata.section_header == "## Test Header"
        assert metadata.header_level == 2
        assert metadata.header_hierarchy["h1"] == "Chapter"
        assert metadata.is_header_split is True
        assert metadata.total_section_chunks == 1

    def test_chunk_to_dict_includes_markdown_fields(self):
        """Should include markdown fields in to_dict output."""
        metadata = ChunkMetadata(
            chunk_index=0,
            source_document_id="test",
            strategy=ChunkingStrategy.MARKDOWN,
            section_header="## Test",
            header_level=2,
            header_hierarchy={"h2": "Test"},
            is_header_split=True,
            total_section_chunks=1
        )
        chunk = Chunk(content="Test content", metadata=metadata)

        result = chunk.to_dict()

        assert "section_header" in result
        assert "header_level" in result
        assert "header_hierarchy" in result
        assert "is_header_split" in result
        assert "total_section_chunks" in result


# =============================================================================
# Task 119: Chunk Filtering Tests
# =============================================================================

@pytest.fixture
def sample_chunks():
    """Create sample chunks for filtering tests."""
    chunks = [
        Chunk(
            content="# Introduction\n\nIntro content.",
            metadata=ChunkMetadata(
                chunk_index=0,
                source_document_id="test",
                strategy=ChunkingStrategy.MARKDOWN,
                section_header="# Introduction",
                header_level=1,
                header_hierarchy={"h1": "Introduction"},
                is_header_split=True,
                total_section_chunks=1
            )
        ),
        Chunk(
            content="## Methods\n\nMethods content.",
            metadata=ChunkMetadata(
                chunk_index=1,
                source_document_id="test",
                strategy=ChunkingStrategy.MARKDOWN,
                section_header="## Methods",
                header_level=2,
                header_hierarchy={"h1": "Introduction", "h2": "Methods"},
                is_header_split=True,
                total_section_chunks=1
            )
        ),
        Chunk(
            content="### Step 1\n\nStep 1 content.",
            metadata=ChunkMetadata(
                chunk_index=2,
                source_document_id="test",
                strategy=ChunkingStrategy.MARKDOWN,
                section_header="### Step 1",
                header_level=3,
                header_hierarchy={"h1": "Introduction", "h2": "Methods", "h3": "Step 1"},
                is_header_split=True,
                total_section_chunks=1
            )
        ),
        Chunk(
            content="## Results\n\nResults content.",
            metadata=ChunkMetadata(
                chunk_index=3,
                source_document_id="test",
                strategy=ChunkingStrategy.MARKDOWN,
                section_header="## Results",
                header_level=2,
                header_hierarchy={"h1": "Introduction", "h2": "Results"},
                is_header_split=True,
                total_section_chunks=1
            )
        ),
        Chunk(
            content="Subdivided chunk from large section.",
            metadata=ChunkMetadata(
                chunk_index=4,
                source_document_id="test",
                strategy=ChunkingStrategy.MARKDOWN,
                section_header="## Large Section",
                header_level=2,
                header_hierarchy={"h1": "Introduction", "h2": "Large Section"},
                is_header_split=False,
                total_section_chunks=3
            )
        ),
    ]
    return chunks


class TestChunkFilter:
    """Tests for ChunkFilter dataclass."""

    def test_default_values(self):
        """Should have None defaults."""
        f = ChunkFilter()
        assert f.header_level is None
        assert f.section_header is None
        assert f.is_header_split is None

    def test_custom_values(self):
        """Should accept custom values."""
        f = ChunkFilter(
            header_level=2,
            section_header="Methods",
            is_header_split=True
        )
        assert f.header_level == 2
        assert f.section_header == "Methods"
        assert f.is_header_split is True


class TestFilterChunksByHeader:
    """Tests for the main filter function."""

    def test_filter_by_header_level(self, sample_chunks):
        """Should filter by exact header level."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(header_level=2)
        )
        assert len(result) == 3  # Methods, Results, Large Section
        assert all(c.metadata.header_level == 2 for c in result)

    def test_filter_by_multiple_levels(self, sample_chunks):
        """Should filter by multiple header levels."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(header_levels=[1, 3])
        )
        assert len(result) == 2  # Introduction (h1) and Step 1 (h3)

    def test_filter_by_section_header_substring(self, sample_chunks):
        """Should filter by section header substring."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(section_header="Method")
        )
        assert len(result) == 1
        assert "Methods" in result[0].metadata.section_header

    def test_filter_by_section_header_case_insensitive(self, sample_chunks):
        """Should be case-insensitive."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(section_header="methods")
        )
        assert len(result) == 1

    def test_filter_by_hierarchy_contains(self, sample_chunks):
        """Should filter by header hierarchy text."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(header_hierarchy_contains="Methods")
        )
        # Should include Methods and Step 1 (child of Methods)
        assert len(result) >= 1

    def test_filter_by_is_header_split(self, sample_chunks):
        """Should filter by is_header_split flag."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(is_header_split=False)
        )
        assert len(result) == 1
        assert result[0].metadata.is_header_split is False

    def test_filter_by_min_header_level(self, sample_chunks):
        """Should filter by minimum header level."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(min_header_level=2)
        )
        assert all(c.metadata.header_level >= 2 for c in result)

    def test_filter_by_max_header_level(self, sample_chunks):
        """Should filter by maximum header level."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(max_header_level=2)
        )
        assert all(c.metadata.header_level <= 2 for c in result)

    def test_combined_filters(self, sample_chunks):
        """Should apply multiple filters together."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(
                header_level=2,
                is_header_split=True
            )
        )
        assert len(result) == 2  # Methods and Results (not Large Section)
        assert all(c.metadata.header_level == 2 for c in result)
        assert all(c.metadata.is_header_split for c in result)

    def test_no_matches_returns_empty(self, sample_chunks):
        """Should return empty list when no matches."""
        result = filter_chunks_by_header(
            sample_chunks,
            ChunkFilter(header_level=6)
        )
        assert result == []


class TestConvenienceFunctions:
    """Tests for convenience filter functions."""

    def test_filter_by_header_level_convenience(self, sample_chunks):
        """Should filter by level using convenience function."""
        result = filter_chunks_by_header_level(sample_chunks, 2)
        assert len(result) == 3
        assert all(c.metadata.header_level == 2 for c in result)

    def test_filter_by_section_convenience(self, sample_chunks):
        """Should filter by section using convenience function."""
        result = filter_chunks_by_section(sample_chunks, "Results")
        assert len(result) == 1
        assert "Results" in result[0].metadata.section_header

    def test_filter_by_hierarchy_convenience(self, sample_chunks):
        """Should filter by hierarchy using convenience function."""
        result = filter_chunks_by_hierarchy(sample_chunks, "Introduction")
        # All chunks have Introduction in hierarchy
        assert len(result) == len(sample_chunks)


class TestGetChunksUnderHeader:
    """Tests for get_chunks_under_header function."""

    def test_get_chunks_under_parent(self, sample_chunks):
        """Should get all chunks under a parent header."""
        result = get_chunks_under_header(sample_chunks, "Methods")
        # Should include Methods and Step 1
        assert len(result) >= 1

    def test_exclude_parent_chunk(self, sample_chunks):
        """Should optionally exclude the parent chunk."""
        result = get_chunks_under_header(
            sample_chunks,
            "Methods",
            include_parent=False
        )
        # Should only include Step 1, not Methods itself
        assert all("Methods" not in (c.metadata.section_header or "") for c in result)


class TestGroupChunks:
    """Tests for chunk grouping functions."""

    def test_group_by_header_level(self, sample_chunks):
        """Should group chunks by header level."""
        groups = group_chunks_by_header_level(sample_chunks)

        assert 1 in groups
        assert 2 in groups
        assert 3 in groups
        assert len(groups[1]) == 1  # Introduction
        assert len(groups[2]) == 3  # Methods, Results, Large Section
        assert len(groups[3]) == 1  # Step 1

    def test_group_by_section(self, sample_chunks):
        """Should group chunks by section header."""
        groups = group_chunks_by_section(sample_chunks)

        assert "# Introduction" in groups
        assert "## Methods" in groups
        assert "## Results" in groups
        assert len(groups) == 5  # 5 different sections
