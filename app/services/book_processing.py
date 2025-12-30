"""
Empire v7.3 - Book Processing Service - Task 22
Process books with automatic chapter detection and per-chapter knowledge base entries

Features:
- Book format detection (EPUB, PDF)
- Table of Contents parsing
- Intelligent chapter boundary detection
- Chapter-level chunking for knowledge base
- Book and chapter metadata storage
"""

import os
import re
import io
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class BookFormat(str, Enum):
    """Supported book formats."""
    EPUB = "epub"
    PDF = "pdf"
    MOBI = "mobi"  # Future support
    TXT = "txt"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """Status of book processing."""
    PENDING = "pending"
    DETECTING_FORMAT = "detecting_format"
    PARSING_TOC = "parsing_toc"
    DETECTING_CHAPTERS = "detecting_chapters"
    CHUNKING = "chunking"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ChapterInfo:
    """Information about a detected chapter."""
    chapter_id: str
    title: str
    chapter_number: int
    start_position: int
    end_position: int
    text_content: str
    word_count: int
    parent_chapter_id: Optional[str] = None
    level: int = 1  # Hierarchy level (1 = top level)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    confidence_score: float = 1.0  # How confident we are in detection
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "chapter_number": self.chapter_number,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "text_content": self.text_content,
            "word_count": self.word_count,
            "parent_chapter_id": self.parent_chapter_id,
            "level": self.level,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata
        }


@dataclass
class BookMetadata:
    """Metadata extracted from a book."""
    title: str
    authors: List[str] = field(default_factory=list)
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    page_count: int = 0
    word_count: int = 0
    edition: Optional[str] = None
    subjects: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "authors": self.authors,
            "isbn": self.isbn,
            "publisher": self.publisher,
            "publication_date": self.publication_date,
            "language": self.language,
            "description": self.description,
            "cover_image_url": self.cover_image_url,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "edition": self.edition,
            "subjects": self.subjects,
            "extra": self.extra
        }


@dataclass
class ProcessedBook:
    """Result of book processing."""
    book_id: str
    file_path: str
    format: BookFormat
    metadata: BookMetadata
    chapters: List[ChapterInfo]
    full_text: str
    processing_status: ProcessingStatus
    error_message: Optional[str] = None
    processed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "book_id": self.book_id,
            "file_path": self.file_path,
            "format": self.format.value,
            "metadata": self.metadata.to_dict(),
            "chapters": [ch.to_dict() for ch in self.chapters],
            "full_text": self.full_text,
            "processing_status": self.processing_status.value,
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat(),
            "chapter_count": len(self.chapters)
        }


# ============================================================================
# Book Format Detection
# ============================================================================

class BookFormatDetector:
    """
    Detects book formats based on file headers and extensions.
    """

    # Magic bytes for format detection
    FORMAT_SIGNATURES = {
        BookFormat.EPUB: [b'PK\x03\x04'],  # ZIP archive (EPUB is zipped XML)
        BookFormat.PDF: [b'%PDF-'],
        BookFormat.MOBI: [b'BOOKMOBI', b'PRC '],
    }

    # File extensions mapping
    EXTENSION_MAP = {
        '.epub': BookFormat.EPUB,
        '.pdf': BookFormat.PDF,
        '.mobi': BookFormat.MOBI,
        '.azw': BookFormat.MOBI,
        '.azw3': BookFormat.MOBI,
        '.txt': BookFormat.TXT,
    }

    def detect_format(self, file_path: str = None, file_bytes: bytes = None) -> BookFormat:
        """
        Detect book format from file path or bytes.

        Args:
            file_path: Path to the book file
            file_bytes: First bytes of the file

        Returns:
            Detected BookFormat
        """
        # Try magic bytes first
        if file_bytes:
            detected = self._detect_from_bytes(file_bytes)
            if detected != BookFormat.UNKNOWN:
                return detected

        # Fall back to extension
        if file_path:
            detected = self._detect_from_extension(file_path)
            if detected != BookFormat.UNKNOWN:
                return detected

            # Try reading file bytes if not provided
            if file_bytes is None and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        file_bytes = f.read(20)
                    return self._detect_from_bytes(file_bytes)
                except Exception:
                    pass

        return BookFormat.UNKNOWN

    def _detect_from_bytes(self, file_bytes: bytes) -> BookFormat:
        """Detect format from magic bytes."""
        for format_type, signatures in self.FORMAT_SIGNATURES.items():
            for sig in signatures:
                if file_bytes.startswith(sig):
                    return format_type
        return BookFormat.UNKNOWN

    def _detect_from_extension(self, file_path: str) -> BookFormat:
        """Detect format from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.EXTENSION_MAP.get(ext, BookFormat.UNKNOWN)


# ============================================================================
# Chapter Detection
# ============================================================================

class ChapterDetector:
    """
    Detects chapter boundaries using regex patterns and heuristics.
    """

    # Common chapter heading patterns
    CHAPTER_PATTERNS = [
        # "Chapter 1", "Chapter One", "CHAPTER I"
        r'^(?:CHAPTER|Chapter|chapter)\s+(?:\d+|[IVXLC]+|[A-Za-z]+)(?:\s*[:\.\-]?\s*.*)?$',
        # "Part 1", "Part One"
        r'^(?:PART|Part|part)\s+(?:\d+|[IVXLC]+|[A-Za-z]+)(?:\s*[:\.\-]?\s*.*)?$',
        # "Section 1", "Section One"
        r'^(?:SECTION|Section|section)\s+(?:\d+|[IVXLC]+|[A-Za-z]+)(?:\s*[:\.\-]?\s*.*)?$',
        # "1.", "I.", "1 -" at start of line
        r'^(?:\d+|[IVXLC]+)\s*[\.\-\:]\s+[A-Z][A-Za-z].*$',
        # "PROLOGUE", "EPILOGUE", "INTRODUCTION", "CONCLUSION"
        r'^(?:PROLOGUE|Prologue|EPILOGUE|Epilogue|INTRODUCTION|Introduction|CONCLUSION|Conclusion|PREFACE|Preface|FOREWORD|Foreword|AFTERWORD|Afterword)(?:\s*[:\.\-]?\s*.*)?$',
        # "Book One", "Book I"
        r'^(?:BOOK|Book|book)\s+(?:\d+|[IVXLC]+|[A-Za-z]+)(?:\s*[:\.\-]?\s*.*)?$',
    ]

    # Compiled patterns
    def __init__(self):
        self._compiled_patterns = [
            re.compile(p, re.MULTILINE) for p in self.CHAPTER_PATTERNS
        ]

    def detect_chapters(
        self,
        text: str,
        toc_chapters: Optional[List[ChapterInfo]] = None,
        min_chapter_length: int = 500
    ) -> List[ChapterInfo]:
        """
        Detect chapters in text.

        Args:
            text: Full text of the book
            toc_chapters: Chapters from TOC if available (used for validation)
            min_chapter_length: Minimum characters for a valid chapter

        Returns:
            List of ChapterInfo objects
        """
        if not text:
            return []

        # First, try to find chapter boundaries using patterns
        chapter_boundaries = self._find_chapter_boundaries(text)

        if not chapter_boundaries:
            # Fall back to paragraph-based detection
            chapter_boundaries = self._detect_by_structure(text)

        if not chapter_boundaries:
            # Last resort: treat entire text as one chapter
            return [self._create_single_chapter(text)]

        # Create chapter objects from boundaries
        chapters = self._create_chapters_from_boundaries(text, chapter_boundaries, min_chapter_length)

        # Validate against TOC if available
        if toc_chapters:
            chapters = self._validate_against_toc(chapters, toc_chapters)

        return chapters

    def _find_chapter_boundaries(self, text: str) -> List[Tuple[int, str, float]]:
        """
        Find chapter boundaries using regex patterns.

        Returns:
            List of (position, title, confidence_score) tuples
        """
        boundaries = []

        for pattern in self._compiled_patterns:
            for match in pattern.finditer(text):
                position = match.start()
                title = match.group(0).strip()
                # Higher confidence for more specific patterns
                confidence = 0.9 if 'chapter' in title.lower() else 0.7
                boundaries.append((position, title, confidence))

        # Sort by position and remove duplicates
        boundaries.sort(key=lambda x: x[0])
        return self._deduplicate_boundaries(boundaries)

    def _deduplicate_boundaries(
        self,
        boundaries: List[Tuple[int, str, float]],
        threshold: int = 100
    ) -> List[Tuple[int, str, float]]:
        """Remove duplicate boundaries that are too close together."""
        if not boundaries:
            return []

        deduped = [boundaries[0]]
        for boundary in boundaries[1:]:
            if boundary[0] - deduped[-1][0] > threshold:
                deduped.append(boundary)
            elif boundary[2] > deduped[-1][2]:
                # Replace with higher confidence match
                deduped[-1] = boundary

        return deduped

    def _detect_by_structure(self, text: str, min_gap: int = 500) -> List[Tuple[int, str, float]]:
        """
        Detect chapters by structural analysis (large gaps, formatting changes).
        """
        boundaries = []

        # Look for multiple blank lines as section breaks
        pattern = re.compile(r'\n\s*\n\s*\n\s*\n', re.MULTILINE)

        for match in pattern.finditer(text):
            position = match.end()
            # Extract potential title (first line after break)
            end_of_line = text.find('\n', position)
            if end_of_line == -1:
                end_of_line = min(position + 100, len(text))

            potential_title = text[position:end_of_line].strip()
            if potential_title and len(potential_title) < 100:
                boundaries.append((position, potential_title, 0.5))

        return self._deduplicate_boundaries(boundaries, min_gap)

    def _create_chapters_from_boundaries(
        self,
        text: str,
        boundaries: List[Tuple[int, str, float]],
        min_chapter_length: int
    ) -> List[ChapterInfo]:
        """Create ChapterInfo objects from boundary positions."""
        chapters = []

        for i, (position, title, confidence) in enumerate(boundaries):
            # Determine end position
            if i < len(boundaries) - 1:
                end_position = boundaries[i + 1][0]
            else:
                end_position = len(text)

            # Extract chapter content
            content = text[position:end_position].strip()

            # Skip very short "chapters"
            if len(content) < min_chapter_length:
                continue

            chapter_id = hashlib.md5(f"{title}_{position}".encode()).hexdigest()[:12]

            chapters.append(ChapterInfo(
                chapter_id=chapter_id,
                title=self._clean_title(title),
                chapter_number=len(chapters) + 1,
                start_position=position,
                end_position=end_position,
                text_content=content,
                word_count=len(content.split()),
                confidence_score=confidence
            ))

        return chapters

    def _clean_title(self, title: str) -> str:
        """Clean up chapter title."""
        # Remove leading/trailing whitespace and punctuation
        title = title.strip().strip('.:- ')

        # Limit length
        if len(title) > 200:
            title = title[:200] + "..."

        return title

    def _create_single_chapter(self, text: str) -> ChapterInfo:
        """Create a single chapter for the entire book."""
        chapter_id = hashlib.md5(text[:1000].encode()).hexdigest()[:12]

        return ChapterInfo(
            chapter_id=chapter_id,
            title="Full Text",
            chapter_number=1,
            start_position=0,
            end_position=len(text),
            text_content=text,
            word_count=len(text.split()),
            confidence_score=0.5
        )

    def _validate_against_toc(
        self,
        detected: List[ChapterInfo],
        toc_chapters: List[ChapterInfo]
    ) -> List[ChapterInfo]:
        """Validate detected chapters against TOC chapters."""
        # If TOC chapters are significantly different, prefer TOC
        if len(toc_chapters) > 0:
            toc_ratio = len(detected) / len(toc_chapters)
            if 0.7 <= toc_ratio <= 1.3:
                # Similar count, merge information
                for det_ch in detected:
                    for toc_ch in toc_chapters:
                        # Check if titles are similar
                        if self._titles_similar(det_ch.title, toc_ch.title):
                            det_ch.confidence_score = min(det_ch.confidence_score + 0.2, 1.0)
                            break

        return detected

    def _titles_similar(self, title1: str, title2: str, threshold: float = 0.6) -> bool:
        """Check if two titles are similar."""
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()

        # Exact match
        if t1 == t2:
            return True

        # One contains the other
        if t1 in t2 or t2 in t1:
            return True

        # Simple word overlap
        words1 = set(t1.split())
        words2 = set(t2.split())
        if words1 and words2:
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            return overlap >= threshold

        return False


# ============================================================================
# TOC Parser
# ============================================================================

class TOCParser:
    """
    Parses Table of Contents from books.
    """

    def parse_epub_toc(self, epub_path: str) -> List[ChapterInfo]:
        """
        Parse TOC from EPUB file.

        Args:
            epub_path: Path to EPUB file

        Returns:
            List of ChapterInfo from TOC
        """
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            logger.warning("ebooklib not installed, cannot parse EPUB TOC")
            return []

        chapters = []
        try:
            book = epub.read_epub(epub_path)

            # Get TOC
            toc = book.toc

            def process_toc_items(items, level=1, parent_id=None):
                for item in items:
                    if isinstance(item, tuple):
                        # Nested section
                        section_title = item[0].title if hasattr(item[0], 'title') else str(item[0])
                        chapter_id = hashlib.md5(section_title.encode()).hexdigest()[:12]
                        chapters.append(ChapterInfo(
                            chapter_id=chapter_id,
                            title=section_title,
                            chapter_number=len(chapters) + 1,
                            start_position=0,
                            end_position=0,
                            text_content="",
                            word_count=0,
                            parent_chapter_id=parent_id,
                            level=level
                        ))
                        # Process nested items
                        if len(item) > 1 and isinstance(item[1], list):
                            process_toc_items(item[1], level + 1, chapter_id)
                    elif hasattr(item, 'title'):
                        chapter_id = hashlib.md5(item.title.encode()).hexdigest()[:12]
                        chapters.append(ChapterInfo(
                            chapter_id=chapter_id,
                            title=item.title,
                            chapter_number=len(chapters) + 1,
                            start_position=0,
                            end_position=0,
                            text_content="",
                            word_count=0,
                            parent_chapter_id=parent_id,
                            level=level
                        ))

            process_toc_items(toc)

        except Exception as e:
            logger.error("Failed to parse EPUB TOC", error=str(e), path=epub_path)

        return chapters

    def parse_pdf_toc(self, pdf_path: str) -> List[ChapterInfo]:
        """
        Parse TOC from PDF bookmarks.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of ChapterInfo from PDF bookmarks
        """
        try:
            import pypdf
        except ImportError:
            logger.warning("pypdf not installed, cannot parse PDF TOC")
            return []

        chapters = []
        try:
            reader = pypdf.PdfReader(pdf_path)
            outlines = reader.outline

            def process_outlines(items, level=1, parent_id=None):
                for item in items:
                    if isinstance(item, list):
                        process_outlines(item, level + 1, parent_id)
                    else:
                        title = item.title if hasattr(item, 'title') else str(item)
                        chapter_id = hashlib.md5(title.encode()).hexdigest()[:12]

                        # Try to get page number
                        page_num = None
                        try:
                            if hasattr(item, 'page'):
                                page_num = reader.get_destination_page_number(item)
                        except Exception:
                            pass

                        chapters.append(ChapterInfo(
                            chapter_id=chapter_id,
                            title=title,
                            chapter_number=len(chapters) + 1,
                            start_position=0,
                            end_position=0,
                            text_content="",
                            word_count=0,
                            parent_chapter_id=parent_id,
                            level=level,
                            page_start=page_num
                        ))

            if outlines:
                process_outlines(outlines)

        except Exception as e:
            logger.error("Failed to parse PDF TOC", error=str(e), path=pdf_path)

        return chapters


# ============================================================================
# Book Parser
# ============================================================================

class BookParser:
    """
    Parses book content from various formats.
    """

    def __init__(self):
        self.format_detector = BookFormatDetector()
        self.toc_parser = TOCParser()

    def parse(self, file_path: str) -> Tuple[str, BookMetadata, BookFormat]:
        """
        Parse a book file.

        Args:
            file_path: Path to the book file

        Returns:
            Tuple of (full_text, metadata, format)
        """
        book_format = self.format_detector.detect_format(file_path)

        if book_format == BookFormat.EPUB:
            return self._parse_epub(file_path)
        elif book_format == BookFormat.PDF:
            return self._parse_pdf(file_path)
        elif book_format == BookFormat.TXT:
            return self._parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported book format: {book_format}")

    def _parse_epub(self, file_path: str) -> Tuple[str, BookMetadata, BookFormat]:
        """Parse EPUB format."""
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise ImportError(f"Required library not installed: {e}")

        book = epub.read_epub(file_path)

        # Extract metadata
        metadata = BookMetadata(
            title=book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else "Unknown",
            authors=[a[0] for a in book.get_metadata('DC', 'creator')] if book.get_metadata('DC', 'creator') else [],
            language=book.get_metadata('DC', 'language')[0][0] if book.get_metadata('DC', 'language') else None,
            publisher=book.get_metadata('DC', 'publisher')[0][0] if book.get_metadata('DC', 'publisher') else None,
            description=book.get_metadata('DC', 'description')[0][0] if book.get_metadata('DC', 'description') else None,
        )

        # Extract ISBN
        identifiers = book.get_metadata('DC', 'identifier')
        for id_val in identifiers:
            if 'isbn' in str(id_val).lower():
                metadata.isbn = id_val[0]
                break

        # Extract text from all chapters
        text_parts = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text = soup.get_text(separator='\n', strip=True)
                if text:
                    text_parts.append(text)

        full_text = '\n\n'.join(text_parts)
        metadata.word_count = len(full_text.split())

        return full_text, metadata, BookFormat.EPUB

    def _parse_pdf(self, file_path: str) -> Tuple[str, BookMetadata, BookFormat]:
        """Parse PDF format."""
        try:
            import pypdf
        except ImportError:
            raise ImportError("pypdf not installed")

        reader = pypdf.PdfReader(file_path)

        # Extract metadata
        pdf_metadata = reader.metadata or {}
        metadata = BookMetadata(
            title=pdf_metadata.get('/Title', 'Unknown') or "Unknown",
            authors=[pdf_metadata.get('/Author', '')] if pdf_metadata.get('/Author') else [],
            page_count=len(reader.pages)
        )

        # Extract text
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        full_text = '\n\n'.join(text_parts)
        metadata.word_count = len(full_text.split())

        return full_text, metadata, BookFormat.PDF

    def _parse_txt(self, file_path: str) -> Tuple[str, BookMetadata, BookFormat]:
        """Parse plain text format."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            full_text = f.read()

        # Extract title from filename
        title = Path(file_path).stem.replace('_', ' ').replace('-', ' ')

        metadata = BookMetadata(
            title=title,
            word_count=len(full_text.split())
        )

        return full_text, metadata, BookFormat.TXT


# ============================================================================
# Chapter Chunker
# ============================================================================

class ChapterChunker:
    """
    Creates optimal chunks from chapters for knowledge base entries.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_chapter(self, chapter: ChapterInfo) -> List[Dict[str, Any]]:
        """
        Chunk a chapter into smaller pieces.

        Args:
            chapter: ChapterInfo to chunk

        Returns:
            List of chunk dictionaries with text and metadata
        """
        text = chapter.text_content
        if not text:
            return []

        chunks = []

        # Split by paragraphs first
        paragraphs = re.split(r'\n\s*\n', text)

        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_length = len(para)

            # If single paragraph is too long, split by sentences
            if para_length > self.chunk_size:
                if current_chunk:
                    chunks.append(self._create_chunk(
                        ' '.join(current_chunk),
                        chapter,
                        len(chunks)
                    ))
                    current_chunk = []
                    current_length = 0

                # Split long paragraph by sentences
                sentence_chunks = self._split_by_sentences(para)
                chunks.extend([
                    self._create_chunk(s, chapter, len(chunks) + i)
                    for i, s in enumerate(sentence_chunks)
                ])
                continue

            # Check if adding this paragraph exceeds limit
            if current_length + para_length > self.chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    ' '.join(current_chunk),
                    chapter,
                    len(chunks)
                ))

                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    # Include last part of previous chunk for context
                    overlap_text = ' '.join(current_chunk)[-self.chunk_overlap:]
                    current_chunk = [overlap_text] if overlap_text else []
                    current_length = len(overlap_text)
                else:
                    current_chunk = []
                    current_length = 0

            current_chunk.append(para)
            current_length += para_length

        # Add remaining content
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(self._create_chunk(chunk_text, chapter, len(chunks)))

        return chunks

    def _split_by_sentences(self, text: str) -> List[str]:
        """Split text by sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current = []
        current_length = 0

        for sentence in sentences:
            if current_length + len(sentence) > self.chunk_size and current:
                chunks.append(' '.join(current))
                current = []
                current_length = 0

            current.append(sentence)
            current_length += len(sentence)

        if current:
            chunks.append(' '.join(current))

        return chunks

    def _create_chunk(
        self,
        text: str,
        chapter: ChapterInfo,
        chunk_index: int
    ) -> Dict[str, Any]:
        """Create a chunk dictionary with metadata."""
        return {
            "text": text,
            "chapter_id": chapter.chapter_id,
            "chapter_title": chapter.title,
            "chapter_number": chapter.chapter_number,
            "chunk_index": chunk_index,
            "word_count": len(text.split()),
            "char_count": len(text),
            "metadata": {
                "source_type": "book_chapter",
                "confidence_score": chapter.confidence_score
            }
        }

    def chunk_book(self, chapters: List[ChapterInfo]) -> List[Dict[str, Any]]:
        """
        Chunk all chapters in a book.

        Args:
            chapters: List of ChapterInfo

        Returns:
            List of all chunks from all chapters
        """
        all_chunks = []
        for chapter in chapters:
            chunks = self.chunk_chapter(chapter)
            all_chunks.extend(chunks)
        return all_chunks


# ============================================================================
# Book Processing Service
# ============================================================================

class BookProcessingService:
    """
    Main service for processing books with chapter detection.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.format_detector = BookFormatDetector()
        self.book_parser = BookParser()
        self.toc_parser = TOCParser()
        self.chapter_detector = ChapterDetector()
        self.chunker = ChapterChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    async def process_book(self, file_path: str) -> ProcessedBook:
        """
        Process a book file.

        Args:
            file_path: Path to the book file

        Returns:
            ProcessedBook with chapters and metadata
        """
        book_id = hashlib.md5(file_path.encode()).hexdigest()[:16]

        try:
            logger.info("Processing book", path=file_path, book_id=book_id)

            # Detect format
            book_format = self.format_detector.detect_format(file_path)
            if book_format == BookFormat.UNKNOWN:
                return self._create_failed_result(
                    book_id, file_path, "Unknown or unsupported book format"
                )

            # Parse book content
            full_text, metadata, _ = self.book_parser.parse(file_path)

            if not full_text:
                return self._create_failed_result(
                    book_id, file_path, "No text content extracted from book"
                )

            # Try to get TOC first
            toc_chapters = []
            if book_format == BookFormat.EPUB:
                toc_chapters = self.toc_parser.parse_epub_toc(file_path)
            elif book_format == BookFormat.PDF:
                toc_chapters = self.toc_parser.parse_pdf_toc(file_path)

            # Detect chapters
            chapters = self.chapter_detector.detect_chapters(
                full_text,
                toc_chapters=toc_chapters
            )

            logger.info(
                "Book processed successfully",
                book_id=book_id,
                chapter_count=len(chapters),
                word_count=metadata.word_count
            )

            return ProcessedBook(
                book_id=book_id,
                file_path=file_path,
                format=book_format,
                metadata=metadata,
                chapters=chapters,
                full_text=full_text,
                processing_status=ProcessingStatus.COMPLETED
            )

        except Exception as e:
            logger.error("Book processing failed", error=str(e), path=file_path)
            return self._create_failed_result(
                book_id, file_path, f"Processing failed: {str(e)}"
            )

    def _create_failed_result(
        self,
        book_id: str,
        file_path: str,
        error: str
    ) -> ProcessedBook:
        """Create a failed processing result."""
        return ProcessedBook(
            book_id=book_id,
            file_path=file_path,
            format=BookFormat.UNKNOWN,
            metadata=BookMetadata(title="Unknown"),
            chapters=[],
            full_text="",
            processing_status=ProcessingStatus.FAILED,
            error_message=error
        )

    def get_chapter_chunks(self, book: ProcessedBook) -> List[Dict[str, Any]]:
        """
        Get all chunks from a processed book.

        Args:
            book: ProcessedBook object

        Returns:
            List of chunk dictionaries
        """
        chunks = self.chunker.chunk_book(book.chapters)

        # Add book-level metadata to each chunk
        for chunk in chunks:
            chunk["book_id"] = book.book_id
            chunk["book_title"] = book.metadata.title
            chunk["book_authors"] = book.metadata.authors

        return chunks


# ============================================================================
# Singleton Instance
# ============================================================================

_book_processing_service: Optional[BookProcessingService] = None


def get_book_processing_service() -> BookProcessingService:
    """Get or create the book processing service singleton."""
    global _book_processing_service
    if _book_processing_service is None:
        _book_processing_service = BookProcessingService()
    return _book_processing_service


# ============================================================================
# Export
# ============================================================================

__all__ = [
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
