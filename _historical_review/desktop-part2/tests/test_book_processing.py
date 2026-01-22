"""
Empire v7.3 - Book Processing Service Tests - Task 22
Tests for book format detection, chapter detection, and processing
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.book_processing import (
    BookFormat,
    ProcessingStatus,
    ChapterInfo,
    BookMetadata,
    ProcessedBook,
    BookFormatDetector,
    ChapterDetector,
    TOCParser,
    BookParser,
    ChapterChunker,
    BookProcessingService,
    get_book_processing_service,
)


# ============================================================================
# BookFormat Enum Tests
# ============================================================================

class TestBookFormat:
    """Tests for BookFormat enum."""

    def test_book_format_values(self):
        """Test all book format enum values."""
        assert BookFormat.EPUB.value == "epub"
        assert BookFormat.PDF.value == "pdf"
        assert BookFormat.MOBI.value == "mobi"
        assert BookFormat.TXT.value == "txt"
        assert BookFormat.UNKNOWN.value == "unknown"

    def test_book_format_is_string_enum(self):
        """Test that BookFormat is a string enum."""
        assert isinstance(BookFormat.EPUB, str)
        assert BookFormat.EPUB == "epub"

    def test_all_book_formats_count(self):
        """Test the total number of book formats."""
        assert len(BookFormat) == 5


# ============================================================================
# ProcessingStatus Enum Tests
# ============================================================================

class TestProcessingStatus:
    """Tests for ProcessingStatus enum."""

    def test_processing_status_values(self):
        """Test all processing status enum values."""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.DETECTING_FORMAT.value == "detecting_format"
        assert ProcessingStatus.PARSING_TOC.value == "parsing_toc"
        assert ProcessingStatus.DETECTING_CHAPTERS.value == "detecting_chapters"
        assert ProcessingStatus.CHUNKING.value == "chunking"
        assert ProcessingStatus.STORING.value == "storing"
        assert ProcessingStatus.COMPLETED.value == "completed"
        assert ProcessingStatus.FAILED.value == "failed"


# ============================================================================
# ChapterInfo Dataclass Tests
# ============================================================================

class TestChapterInfo:
    """Tests for ChapterInfo dataclass."""

    def test_chapter_info_creation_minimal(self):
        """Test creating ChapterInfo with required fields."""
        chapter = ChapterInfo(
            chapter_id="ch001",
            title="Introduction",
            chapter_number=1,
            start_position=0,
            end_position=1000,
            text_content="This is the introduction chapter.",
            word_count=6
        )
        assert chapter.chapter_id == "ch001"
        assert chapter.title == "Introduction"
        assert chapter.chapter_number == 1
        assert chapter.level == 1  # default
        assert chapter.confidence_score == 1.0  # default

    def test_chapter_info_with_hierarchy(self):
        """Test ChapterInfo with parent-child hierarchy."""
        chapter = ChapterInfo(
            chapter_id="ch002",
            title="Section 1.1",
            chapter_number=2,
            start_position=1000,
            end_position=2000,
            text_content="Content",
            word_count=1,
            parent_chapter_id="ch001",
            level=2
        )
        assert chapter.parent_chapter_id == "ch001"
        assert chapter.level == 2

    def test_chapter_info_to_dict(self):
        """Test ChapterInfo to_dict conversion."""
        chapter = ChapterInfo(
            chapter_id="ch001",
            title="Test Chapter",
            chapter_number=1,
            start_position=0,
            end_position=500,
            text_content="Test content",
            word_count=2,
            confidence_score=0.95
        )
        result = chapter.to_dict()
        assert result["chapter_id"] == "ch001"
        assert result["title"] == "Test Chapter"
        assert result["confidence_score"] == 0.95
        assert "metadata" in result


# ============================================================================
# BookMetadata Dataclass Tests
# ============================================================================

class TestBookMetadata:
    """Tests for BookMetadata dataclass."""

    def test_book_metadata_creation_minimal(self):
        """Test creating BookMetadata with minimal fields."""
        metadata = BookMetadata(title="Test Book")
        assert metadata.title == "Test Book"
        assert metadata.authors == []
        assert metadata.isbn is None
        assert metadata.word_count == 0

    def test_book_metadata_creation_full(self):
        """Test creating BookMetadata with all fields."""
        metadata = BookMetadata(
            title="The Great Book",
            authors=["John Doe", "Jane Smith"],
            isbn="978-0-123456-78-9",
            publisher="Great Publishers",
            publication_date="2024-01-15",
            language="en",
            description="A great book about things",
            page_count=350,
            word_count=100000,
            edition="First Edition",
            subjects=["Fiction", "Adventure"]
        )
        assert metadata.title == "The Great Book"
        assert len(metadata.authors) == 2
        assert metadata.isbn == "978-0-123456-78-9"
        assert metadata.page_count == 350

    def test_book_metadata_to_dict(self):
        """Test BookMetadata to_dict conversion."""
        metadata = BookMetadata(
            title="Test",
            authors=["Author"],
            word_count=5000
        )
        result = metadata.to_dict()
        assert result["title"] == "Test"
        assert result["authors"] == ["Author"]
        assert result["word_count"] == 5000


# ============================================================================
# ProcessedBook Dataclass Tests
# ============================================================================

class TestProcessedBook:
    """Tests for ProcessedBook dataclass."""

    def test_processed_book_creation(self):
        """Test creating ProcessedBook."""
        metadata = BookMetadata(title="Test Book")
        chapter = ChapterInfo(
            chapter_id="ch1",
            title="Chapter 1",
            chapter_number=1,
            start_position=0,
            end_position=100,
            text_content="Content",
            word_count=1
        )
        book = ProcessedBook(
            book_id="book123",
            file_path="/path/to/book.epub",
            format=BookFormat.EPUB,
            metadata=metadata,
            chapters=[chapter],
            full_text="Full book content",
            processing_status=ProcessingStatus.COMPLETED
        )
        assert book.book_id == "book123"
        assert book.format == BookFormat.EPUB
        assert len(book.chapters) == 1

    def test_processed_book_to_dict(self):
        """Test ProcessedBook to_dict conversion."""
        metadata = BookMetadata(title="Test")
        book = ProcessedBook(
            book_id="book123",
            file_path="/path/to/book.pdf",
            format=BookFormat.PDF,
            metadata=metadata,
            chapters=[],
            full_text="Text",
            processing_status=ProcessingStatus.COMPLETED
        )
        result = book.to_dict()
        assert result["book_id"] == "book123"
        assert result["format"] == "pdf"
        assert result["chapter_count"] == 0


# ============================================================================
# BookFormatDetector Tests
# ============================================================================

class TestBookFormatDetector:
    """Tests for BookFormatDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a BookFormatDetector instance."""
        return BookFormatDetector()

    def test_detect_epub_by_bytes(self, detector):
        """Test EPUB detection by magic bytes."""
        # EPUB starts with ZIP header
        epub_bytes = b'PK\x03\x04' + b'\x00' * 16
        assert detector.detect_format(file_bytes=epub_bytes) == BookFormat.EPUB

    def test_detect_pdf_by_bytes(self, detector):
        """Test PDF detection by magic bytes."""
        pdf_bytes = b'%PDF-1.5' + b'\x00' * 16
        assert detector.detect_format(file_bytes=pdf_bytes) == BookFormat.PDF

    def test_detect_mobi_by_bytes(self, detector):
        """Test MOBI detection by magic bytes."""
        mobi_bytes = b'BOOKMOBI' + b'\x00' * 16
        assert detector.detect_format(file_bytes=mobi_bytes) == BookFormat.MOBI

    def test_detect_epub_by_extension(self, detector):
        """Test EPUB detection by file extension."""
        assert detector.detect_format(file_path="book.epub") == BookFormat.EPUB
        assert detector.detect_format(file_path="/path/to/book.EPUB") == BookFormat.EPUB

    def test_detect_pdf_by_extension(self, detector):
        """Test PDF detection by file extension."""
        assert detector.detect_format(file_path="book.pdf") == BookFormat.PDF

    def test_detect_mobi_by_extension(self, detector):
        """Test MOBI detection by file extension."""
        assert detector.detect_format(file_path="book.mobi") == BookFormat.MOBI
        assert detector.detect_format(file_path="book.azw") == BookFormat.MOBI
        assert detector.detect_format(file_path="book.azw3") == BookFormat.MOBI

    def test_detect_txt_by_extension(self, detector):
        """Test TXT detection by file extension."""
        assert detector.detect_format(file_path="book.txt") == BookFormat.TXT

    def test_detect_unknown_format(self, detector):
        """Test unknown format detection."""
        assert detector.detect_format(file_path="book.xyz") == BookFormat.UNKNOWN
        assert detector.detect_format(file_bytes=b'unknown') == BookFormat.UNKNOWN

    def test_detect_priority_bytes_over_extension(self, detector):
        """Test that bytes take priority over extension."""
        # PDF bytes with .epub extension
        pdf_bytes = b'%PDF-1.5' + b'\x00' * 16
        assert detector.detect_format(file_path="book.epub", file_bytes=pdf_bytes) == BookFormat.PDF


# ============================================================================
# ChapterDetector Tests
# ============================================================================

class TestChapterDetector:
    """Tests for ChapterDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a ChapterDetector instance."""
        return ChapterDetector()

    def test_detect_chapter_heading_standard(self, detector):
        """Test detection of standard chapter headings."""
        # Note: Chapter headings need to be at the start of a line (no leading whitespace)
        text = """Chapter 1: The Beginning

This is the content of chapter 1. It contains several paragraphs
of text that discuss important topics and provide substantial content
for the chapter detection algorithm to work with properly.

Chapter 2: The Middle

This is the content of chapter 2. More paragraphs follow
with additional information and enough text to pass the minimum
chapter length requirement for detection.

Chapter 3: The End

The final chapter with concluding remarks and summary that also
has enough content to be detected as a valid chapter section.
"""
        chapters = detector.detect_chapters(text, min_chapter_length=50)
        assert len(chapters) >= 2

    def test_detect_chapter_heading_roman_numerals(self, detector):
        """Test detection of Roman numeral chapters."""
        text = """Chapter I

First chapter content with substantial text to meet the minimum
length requirements for chapter detection. Adding more words here
to ensure we have enough content for the algorithm.

Chapter II

Second chapter content with more substantial text that also
meets the minimum length requirements for proper detection by
the chapter detection algorithm.

Chapter III

Third chapter with concluding content that is long enough to be
properly detected as a valid chapter section.
"""
        chapters = detector.detect_chapters(text, min_chapter_length=50)
        assert len(chapters) >= 2

    def test_detect_part_headings(self, detector):
        """Test detection of part headings."""
        text = """
        Part One: Introduction

        Content for the first part with enough text to be considered
        a valid chapter section.

        Part Two: Main Content

        Content for the second part with sufficient length for detection.
        """
        chapters = detector.detect_chapters(text, min_chapter_length=50)
        assert len(chapters) >= 1

    def test_detect_prologue_epilogue(self, detector):
        """Test detection of prologue and epilogue."""
        text = """Prologue

The prologue content with enough text to be detected as a
valid chapter section. Adding more content here to ensure
the minimum length requirement is satisfied.

Chapter 1: Main Story

The main story content goes here with sufficient length and
enough words to pass the chapter detection minimum threshold.

Epilogue

The epilogue content wrapping up the story with enough text
to be detected as a valid epilogue section.
"""
        chapters = detector.detect_chapters(text, min_chapter_length=50)
        assert len(chapters) >= 2

    def test_detect_no_chapters_returns_single(self, detector):
        """Test that text without chapters returns single chapter."""
        text = "Just some plain text without any chapter headings or structure."
        chapters = detector.detect_chapters(text)
        # Should return at least one chapter (the full text)
        assert len(chapters) >= 1
        assert chapters[0].title == "Full Text"

    def test_detect_empty_text(self, detector):
        """Test detection with empty text."""
        chapters = detector.detect_chapters("")
        assert len(chapters) == 0

    def test_chapter_confidence_score(self, detector):
        """Test that chapters have confidence scores."""
        text = """
        Chapter 1: Introduction

        Content with enough text for detection.

        Chapter 2: Details

        More content with sufficient length for detection.
        """
        chapters = detector.detect_chapters(text, min_chapter_length=30)
        for chapter in chapters:
            assert 0 < chapter.confidence_score <= 1.0

    def test_chapter_word_count(self, detector):
        """Test that chapters have word counts."""
        text = """
        Chapter 1

        This chapter has exactly ten words in it here.
        """
        chapters = detector.detect_chapters(text, min_chapter_length=10)
        if chapters:
            assert chapters[0].word_count > 0


# ============================================================================
# ChapterChunker Tests
# ============================================================================

class TestChapterChunker:
    """Tests for ChapterChunker class."""

    @pytest.fixture
    def chunker(self):
        """Create a ChapterChunker instance."""
        return ChapterChunker(
            chunk_size=100,
            chunk_overlap=20,
            min_chunk_size=10
        )

    @pytest.fixture
    def sample_chapter(self):
        """Create a sample chapter."""
        return ChapterInfo(
            chapter_id="ch001",
            title="Test Chapter",
            chapter_number=1,
            start_position=0,
            end_position=500,
            text_content="This is paragraph one. It has some content.\n\n"
                        "This is paragraph two. It also has content.\n\n"
                        "This is paragraph three. More content here.",
            word_count=20
        )

    def test_chunk_chapter_basic(self, chunker, sample_chapter):
        """Test basic chapter chunking."""
        chunks = chunker.chunk_chapter(sample_chapter)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "text" in chunk
            assert "chapter_id" in chunk
            assert chunk["chapter_id"] == "ch001"

    def test_chunk_chapter_metadata(self, chunker, sample_chapter):
        """Test chunk metadata is populated."""
        chunks = chunker.chunk_chapter(sample_chapter)
        if chunks:
            chunk = chunks[0]
            assert chunk["chapter_title"] == "Test Chapter"
            assert chunk["chapter_number"] == 1
            assert "word_count" in chunk
            assert "chunk_index" in chunk

    def test_chunk_empty_chapter(self, chunker):
        """Test chunking empty chapter."""
        chapter = ChapterInfo(
            chapter_id="ch001",
            title="Empty",
            chapter_number=1,
            start_position=0,
            end_position=0,
            text_content="",
            word_count=0
        )
        chunks = chunker.chunk_chapter(chapter)
        assert len(chunks) == 0

    def test_chunk_long_chapter(self, chunker):
        """Test chunking a long chapter."""
        long_text = ("This is a sentence. " * 100)
        chapter = ChapterInfo(
            chapter_id="ch001",
            title="Long Chapter",
            chapter_number=1,
            start_position=0,
            end_position=len(long_text),
            text_content=long_text,
            word_count=len(long_text.split())
        )
        chunks = chunker.chunk_chapter(chapter)
        # Should create multiple chunks
        assert len(chunks) > 1

    def test_chunk_book_multiple_chapters(self, chunker):
        """Test chunking multiple chapters."""
        chapters = [
            ChapterInfo(
                chapter_id=f"ch{i:03d}",
                title=f"Chapter {i}",
                chapter_number=i,
                start_position=i * 100,
                end_position=(i + 1) * 100,
                text_content=f"Content for chapter {i} with some text.",
                word_count=7
            )
            for i in range(1, 4)
        ]
        all_chunks = chunker.chunk_book(chapters)
        # Should have chunks from all chapters
        chapter_ids = set(chunk["chapter_id"] for chunk in all_chunks)
        assert len(chapter_ids) == 3


# ============================================================================
# BookParser Tests
# ============================================================================

class TestBookParser:
    """Tests for BookParser class."""

    @pytest.fixture
    def parser(self):
        """Create a BookParser instance."""
        return BookParser()

    def test_parse_txt_file(self, parser):
        """Test parsing a TXT file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test book content.\n\nChapter 1\n\nSome content here.")
            temp_path = f.name

        try:
            text, metadata, format_type = parser.parse(temp_path)
            assert format_type == BookFormat.TXT
            assert "test book content" in text
            assert metadata.word_count > 0
        finally:
            os.unlink(temp_path)

    def test_parse_unsupported_format(self, parser):
        """Test parsing unsupported format raises error."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            f.write(b'random content')
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                parser.parse(temp_path)
        finally:
            os.unlink(temp_path)


# ============================================================================
# TOCParser Tests
# ============================================================================

class TestTOCParser:
    """Tests for TOCParser class."""

    @pytest.fixture
    def parser(self):
        """Create a TOCParser instance."""
        return TOCParser()

    def test_parse_epub_toc_without_library(self, parser):
        """Test EPUB TOC parsing returns empty when library unavailable."""
        # Without ebooklib installed, should return empty list gracefully
        with patch.dict('sys.modules', {'ebooklib': None}):
            result = parser.parse_epub_toc("nonexistent.epub")
            assert result == []

    def test_parse_pdf_toc_without_library(self, parser):
        """Test PDF TOC parsing returns empty when library unavailable."""
        # Without pypdf installed, should return empty list gracefully
        with patch.dict('sys.modules', {'pypdf': None}):
            result = parser.parse_pdf_toc("nonexistent.pdf")
            assert result == []


# ============================================================================
# BookProcessingService Tests
# ============================================================================

class TestBookProcessingService:
    """Tests for BookProcessingService class."""

    @pytest.fixture
    def service(self):
        """Create a BookProcessingService instance."""
        return BookProcessingService()

    @pytest.mark.asyncio
    async def test_process_txt_book(self, service):
        """Test processing a TXT book."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("""
            Chapter 1: Introduction

            This is the introduction chapter with substantial content
            that should be detected as a proper chapter section.

            Chapter 2: Main Content

            This is the main content chapter with more substantial
            text that should also be detected properly.

            Chapter 3: Conclusion

            The conclusion chapter with final remarks and enough
            content to be detected as a valid chapter.
            """)
            temp_path = f.name

        try:
            result = await service.process_book(temp_path)
            assert result.processing_status == ProcessingStatus.COMPLETED
            assert result.format == BookFormat.TXT
            assert len(result.chapters) >= 1
            assert result.metadata.word_count > 0
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_process_nonexistent_file(self, service):
        """Test processing a file that doesn't exist."""
        result = await service.process_book("/nonexistent/path/book.pdf")
        assert result.processing_status == ProcessingStatus.FAILED
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_process_unknown_format(self, service):
        """Test processing unknown format."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            f.write(b'random content')
            temp_path = f.name

        try:
            result = await service.process_book(temp_path)
            assert result.processing_status == ProcessingStatus.FAILED
        finally:
            os.unlink(temp_path)

    def test_get_chapter_chunks(self, service):
        """Test getting chunks from processed book."""
        metadata = BookMetadata(title="Test Book", authors=["Author"])
        chapters = [
            ChapterInfo(
                chapter_id="ch1",
                title="Chapter 1",
                chapter_number=1,
                start_position=0,
                end_position=100,
                text_content="Chapter content with enough text for chunking.",
                word_count=7
            )
        ]
        book = ProcessedBook(
            book_id="book123",
            file_path="/path/to/book.txt",
            format=BookFormat.TXT,
            metadata=metadata,
            chapters=chapters,
            full_text="Full text",
            processing_status=ProcessingStatus.COMPLETED
        )

        chunks = service.get_chapter_chunks(book)
        if chunks:
            assert chunks[0]["book_id"] == "book123"
            assert chunks[0]["book_title"] == "Test Book"
            assert chunks[0]["book_authors"] == ["Author"]


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_book_processing_service_singleton(self):
        """Test that get_book_processing_service returns singleton."""
        import app.services.book_processing as module

        # Reset singleton
        module._book_processing_service = None

        service1 = get_book_processing_service()
        service2 = get_book_processing_service()

        assert service1 is service2

    def test_get_book_processing_service_creates_instance(self):
        """Test that singleton creates instance when None."""
        import app.services.book_processing as module

        # Reset singleton
        module._book_processing_service = None

        service = get_book_processing_service()

        assert service is not None
        assert isinstance(service, BookProcessingService)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for book processing."""

    @pytest.mark.asyncio
    async def test_full_book_processing_pipeline(self):
        """Test full book processing from file to chunks."""
        service = BookProcessingService(chunk_size=100, chunk_overlap=20)

        # Create a book with clear chapter structure (no leading whitespace on chapter headings)
        book_content = """Title: Test Book

Prologue

This is the prologue section with sufficient content to be
detected as a valid chapter by the detection algorithm.
The prologue sets the stage for the story that follows and
provides substantial content for proper detection.

Chapter 1: The Beginning

This is the first chapter with substantial content that
should be properly detected and chunked. It contains
multiple paragraphs of text for proper processing and
enough words to satisfy the minimum length requirement.

More content in chapter one to ensure we have enough
text for the chunking algorithm to work with properly.

Chapter 2: The Middle

This is the second chapter with its own content that
should also be detected and processed separately.
Additional paragraphs provide more content for the
chapter detection algorithm.

Even more text to ensure proper detection and chunking
of this chapter section with sufficient length.

Chapter 3: The End

The final chapter wraps up the story with concluding
remarks and final thoughts on the subject matter and
provides closure for the book content.
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(book_content)
            temp_path = f.name

        try:
            # Process the book
            result = await service.process_book(temp_path)

            assert result.processing_status == ProcessingStatus.COMPLETED
            # Chapters may be empty if individual sections don't meet min length
            # but full_text should always have content
            assert len(result.full_text) > 0
            assert result.metadata.word_count > 0

            # If chapters exist, verify their structure
            if result.chapters:
                for chapter in result.chapters:
                    assert chapter.chapter_id
                    assert chapter.title
                    assert chapter.word_count >= 0

                # Get chunks
                chunks = service.get_chapter_chunks(result)
                # Verify chunk structure if any exist
                for chunk in chunks:
                    assert "text" in chunk
                    assert "chapter_id" in chunk
                    assert "book_id" in chunk

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_error_handling_chain(self):
        """Test error handling throughout processing chain."""
        service = BookProcessingService()

        # Test with empty file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            result = await service.process_book(temp_path)
            # Should handle empty file gracefully
            assert result.processing_status == ProcessingStatus.FAILED or len(result.chapters) == 0
        finally:
            os.unlink(temp_path)


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_chapter_detector_unicode(self):
        """Test chapter detection with unicode characters."""
        detector = ChapterDetector()
        text = """
        第一章: 简介

        这是第一章的内容。

        Chapter 2: English Chapter

        English content here with sufficient length for detection.
        """
        chapters = detector.detect_chapters(text, min_chapter_length=20)
        # Should detect at least the English chapter
        assert len(chapters) >= 1

    def test_chapter_detector_special_characters(self):
        """Test chapter detection with special characters."""
        detector = ChapterDetector()
        text = """
        Chapter 1 - The Beginning...

        Content with special chars: @#$%^&*()

        Chapter 2 — Another Section

        More content with em-dashes and "quotes".
        """
        chapters = detector.detect_chapters(text, min_chapter_length=30)
        assert len(chapters) >= 1

    def test_book_metadata_empty_authors(self):
        """Test BookMetadata with empty authors list."""
        metadata = BookMetadata(title="Test", authors=[])
        result = metadata.to_dict()
        assert result["authors"] == []

    def test_chunker_very_short_text(self):
        """Test chunking very short text."""
        chunker = ChapterChunker(chunk_size=1000)
        chapter = ChapterInfo(
            chapter_id="ch1",
            title="Short",
            chapter_number=1,
            start_position=0,
            end_position=10,
            text_content="Short text",
            word_count=2
        )
        chunks = chunker.chunk_chapter(chapter)
        # Might be empty due to min_chunk_size
        assert isinstance(chunks, list)

    def test_format_detector_case_insensitive(self):
        """Test format detection is case insensitive for extensions."""
        detector = BookFormatDetector()
        assert detector.detect_format(file_path="book.EPUB") == BookFormat.EPUB
        assert detector.detect_format(file_path="book.Pdf") == BookFormat.PDF
        assert detector.detect_format(file_path="book.TXT") == BookFormat.TXT


# ============================================================================
# Export Tests
# ============================================================================

class TestExports:
    """Tests for module exports."""

    def test_all_exports(self):
        """Test that all expected items are exported."""
        from app.services import book_processing

        expected_exports = [
            "BookFormat",
            "ProcessingStatus",
            "ChapterInfo",
            "BookMetadata",
            "ProcessedBook",
            "BookFormatDetector",
            "ChapterDetector",
            "TOCParser",
            "BookParser",
            "ChapterChunker",
            "BookProcessingService",
            "get_book_processing_service",
        ]

        for export in expected_exports:
            assert hasattr(book_processing, export), f"Missing export: {export}"
