"""
Empire v7.3 - Document Processor Tests
Tests for universal document processing pipeline
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from app.services.document_processor import (
    DocumentProcessor,
    DocumentType,
    ExtractionMethod,
    get_document_processor
)


class TestDocumentTypeDetection:
    """Test document type detection logic"""

    @pytest.fixture
    def processor(self):
        return DocumentProcessor()

    def test_detect_pdf(self, processor):
        """Test PDF detection"""
        assert processor.detect_document_type("test.pdf") == DocumentType.PDF
        assert processor.detect_document_type("test.PDF") == DocumentType.PDF

    def test_detect_docx(self, processor):
        """Test DOCX detection"""
        assert processor.detect_document_type("test.docx") == DocumentType.DOCX
        assert processor.detect_document_type("test.DOCX") == DocumentType.DOCX

    def test_detect_pptx(self, processor):
        """Test PPTX detection"""
        assert processor.detect_document_type("test.pptx") == DocumentType.PPTX
        assert processor.detect_document_type("test.ppt") == DocumentType.PPTX

    def test_detect_image(self, processor):
        """Test image detection"""
        assert processor.detect_document_type("test.jpg") == DocumentType.IMAGE
        assert processor.detect_document_type("test.png") == DocumentType.IMAGE
        assert processor.detect_document_type("test.gif") == DocumentType.IMAGE

    def test_detect_audio(self, processor):
        """Test audio detection"""
        assert processor.detect_document_type("test.mp3") == DocumentType.AUDIO
        assert processor.detect_document_type("test.wav") == DocumentType.AUDIO
        assert processor.detect_document_type("test.m4a") == DocumentType.AUDIO

    def test_detect_video(self, processor):
        """Test video detection"""
        assert processor.detect_document_type("test.mp4") == DocumentType.VIDEO
        assert processor.detect_document_type("test.mov") == DocumentType.VIDEO
        assert processor.detect_document_type("test.avi") == DocumentType.VIDEO

    def test_detect_text(self, processor):
        """Test text file detection"""
        assert processor.detect_document_type("test.txt") == DocumentType.TEXT
        assert processor.detect_document_type("test.md") == DocumentType.TEXT
        assert processor.detect_document_type("test.json") == DocumentType.TEXT

    def test_detect_unknown(self, processor):
        """Test unknown file type detection"""
        assert processor.detect_document_type("test.xyz") == DocumentType.UNKNOWN
        assert processor.detect_document_type("test.unknown") == DocumentType.UNKNOWN


class TestPDFProcessing:
    """Test PDF document processing"""

    @pytest.mark.asyncio
    async def test_process_pdf_success(self, mock_pdf_document):
        """Test successful PDF processing"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PDF_SUPPORT', True), \
             patch('app.services.document_processor.PdfReader', return_value=mock_pdf_document, create=True):
            result = await processor._process_pdf(
                file_path="test.pdf",
                extract_tables=True,
                extract_images=True,
                track_pages=True
            )

            assert result["extraction_method"] == ExtractionMethod.PYPDF.value
            assert len(result["content"]["text"]) > 0
            assert len(result["content"]["pages"]) == 2
            assert result["metadata"]["page_count"] == 2
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_process_pdf_with_page_tracking(self, mock_pdf_document):
        """Test PDF processing with page tracking"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PDF_SUPPORT', True), \
             patch('app.services.document_processor.PdfReader', return_value=mock_pdf_document, create=True):
            result = await processor._process_pdf(
                file_path="test.pdf",
                extract_tables=False,
                extract_images=False,
                track_pages=True
            )

            pages = result["content"]["pages"]
            assert len(pages) == 2
            assert pages[0]["page_number"] == 1
            assert pages[1]["page_number"] == 2
            assert "text" in pages[0]
            assert "text" in pages[1]

    @pytest.mark.asyncio
    async def test_process_pdf_no_support(self):
        """Test PDF processing when pypdf not available"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PDF_SUPPORT', False):
            result = await processor._process_pdf(
                file_path="test.pdf",
                extract_tables=True,
                extract_images=True,
                track_pages=True
            )

            assert result["extraction_method"] is None
            assert len(result["errors"]) > 0
            assert "not available" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_process_pdf_with_errors(self, mock_pdf_document_with_errors):
        """Test PDF processing with page-level errors"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PDF_SUPPORT', True), \
             patch('app.services.document_processor.PdfReader', return_value=mock_pdf_document_with_errors, create=True):
            result = await processor._process_pdf(
                file_path="test.pdf",
                extract_tables=True,
                extract_images=True,
                track_pages=True
            )

            # Should still succeed but log errors
            assert len(result["errors"]) > 0
            assert "Page" in result["errors"][0]


class TestDOCXProcessing:
    """Test DOCX document processing"""

    @pytest.mark.asyncio
    async def test_process_docx_success(self, mock_docx_document):
        """Test successful DOCX processing"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.DOCX_SUPPORT', True), \
             patch('app.services.document_processor.Document', return_value=mock_docx_document, create=True):
            result = await processor._process_docx(
                file_path="test.docx",
                extract_tables=True,
                extract_images=True
            )

            assert result["extraction_method"] == ExtractionMethod.DOCX.value
            assert len(result["content"]["text"]) > 0
            assert "paragraph 1" in result["content"]["text"].lower()
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_process_docx_with_tables(self, mock_docx_document_with_tables):
        """Test DOCX processing with table extraction"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.DOCX_SUPPORT', True), \
             patch('app.services.document_processor.Document', return_value=mock_docx_document_with_tables, create=True):
            result = await processor._process_docx(
                file_path="test.docx",
                extract_tables=True,
                extract_images=False
            )

            assert len(result["content"]["tables"]) == 1
            assert result["metadata"]["table_count"] == 1
            assert len(result["content"]["tables"][0]["rows"]) > 0

    @pytest.mark.asyncio
    async def test_process_docx_no_support(self):
        """Test DOCX processing when python-docx not available"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.DOCX_SUPPORT', False):
            result = await processor._process_docx(
                file_path="test.docx",
                extract_tables=True,
                extract_images=True
            )

            assert result["extraction_method"] == ExtractionMethod.DOCX.value
            assert len(result["errors"]) > 0
            assert "not available" in result["errors"][0]


class TestPPTXProcessing:
    """Test PPTX document processing"""

    @pytest.mark.asyncio
    async def test_process_pptx_success(self, mock_pptx_presentation):
        """Test successful PPTX processing"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PPTX_SUPPORT', True), \
             patch('app.services.document_processor.Presentation', return_value=mock_pptx_presentation, create=True):
            result = await processor._process_pptx(
                file_path="test.pptx",
                extract_images=True
            )

            assert result["extraction_method"] == ExtractionMethod.PPTX.value
            assert len(result["content"]["text"]) > 0
            assert result["metadata"]["slide_count"] == 2
            assert len(result["content"]["pages"]) == 2
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_process_pptx_slides_as_pages(self, mock_pptx_presentation):
        """Test PPTX processing treats slides as pages"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PPTX_SUPPORT', True), \
             patch('app.services.document_processor.Presentation', return_value=mock_pptx_presentation, create=True):
            result = await processor._process_pptx(
                file_path="test.pptx",
                extract_images=False
            )

            pages = result["content"]["pages"]
            assert len(pages) == 2
            assert pages[0]["page_number"] == 1
            assert pages[1]["page_number"] == 2


class TestImageProcessing:
    """Test image processing with Claude Vision"""

    @pytest.mark.asyncio
    async def test_process_image_success(self, mock_claude_client):
        """Test successful image processing with Claude Vision"""
        processor = DocumentProcessor()
        processor.anthropic_client = mock_claude_client

        # Mock image file
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'fake_image_data'

            result = await processor._process_image("test.jpg")

            assert result["extraction_method"] == ExtractionMethod.CLAUDE_VISION.value
            assert len(result["content"]["text"]) > 0
            assert "Sales Training" in result["content"]["text"]
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_process_image_no_api_key(self):
        """Test image processing without Claude API key"""
        processor = DocumentProcessor()
        processor.anthropic_client = None

        result = await processor._process_image("test.png")

        assert len(result["errors"]) > 0
        assert "not available" in result["errors"][0]


class TestAudioVideoProcessing:
    """Test audio/video processing"""

    @pytest.mark.asyncio
    async def test_process_audio_success(self, mock_audio_file):
        """Test successful audio processing"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.MutagenFile') as mock_mutagen:
            mock_mutagen.return_value = mock_audio_file

            result = await processor._process_audio_video("test.mp3")

            assert result["extraction_method"] == ExtractionMethod.MUTAGEN.value
            assert "Duration:" in result["content"]["text"]
            assert result["metadata"]["duration_seconds"] == 180.5
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_process_video_success(self, mock_video_file):
        """Test successful video processing"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.MutagenFile') as mock_mutagen:
            mock_mutagen.return_value = mock_video_file

            result = await processor._process_audio_video("test.mp4")

            assert result["extraction_method"] == ExtractionMethod.MUTAGEN.value
            assert "Duration:" in result["content"]["text"]
            assert result["metadata"]["file_type"] == "video"


class TestTextProcessing:
    """Test plain text processing"""

    @pytest.mark.asyncio
    async def test_process_text_utf8(self, sample_text_file):
        """Test text processing with UTF-8 encoding"""
        processor = DocumentProcessor()

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = sample_text_file

            result = await processor._process_text("test.txt")

            assert result["extraction_method"] == ExtractionMethod.TEXT.value
            assert sample_text_file in result["content"]["text"]
            assert len(result["errors"]) == 0


class TestDocumentProcessorWorkflow:
    """Test end-to-end document processing workflow"""

    @pytest.mark.asyncio
    async def test_process_document_pdf(self, mock_pdf_document):
        """Test complete PDF document processing"""
        processor = DocumentProcessor()

        with patch('app.services.document_processor.PDF_SUPPORT', True), \
             patch('app.services.document_processor.PdfReader', return_value=mock_pdf_document, create=True), \
             patch('os.path.exists', return_value=True):
            result = await processor.process_document(
                file_path="test.pdf",
                extract_tables=True,
                extract_images=True,
                track_pages=True
            )

            assert result["success"] is True
            assert result["document_type"] == DocumentType.PDF.value
            assert result["extraction_method"] == ExtractionMethod.PYPDF.value
            assert len(result["content"]["text"]) > 0

    @pytest.mark.asyncio
    async def test_process_document_unknown_type(self):
        """Test processing unknown document type"""
        processor = DocumentProcessor()

        with patch('os.path.exists', return_value=True):
            result = await processor.process_document("test.xyz")

            assert result["success"] is False
            assert result["document_type"] == DocumentType.UNKNOWN.value
            assert len(result["errors"]) > 0


class TestSingletonPattern:
    """Test singleton pattern for DocumentProcessor"""

    def test_get_document_processor_singleton(self):
        """Test get_document_processor returns singleton"""
        processor1 = get_document_processor()
        processor2 = get_document_processor()

        assert processor1 is processor2
