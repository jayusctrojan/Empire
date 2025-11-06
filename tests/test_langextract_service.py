"""
Empire v7.3 - LangExtract Service Tests
Test structured data extraction using LangExtract API
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Dict, Any, List
import os

# Import the service
import app.services.langextract_service as langextract_module
from app.services.langextract_service import (
    CourseMetadataSchema,
    LangExtractService,
    MetadataStorage,
    get_langextract_service
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_langextract_extraction():
    """Mock LangExtract extraction result"""
    mock_extraction = MagicMock()

    # Create mock extraction objects
    extractions = []

    # Instructor
    ext1 = MagicMock()
    ext1.extraction_class = "instructor"
    ext1.extraction_text = "Grant Cardone"
    ext1.attributes = {}
    ext1.start_char = 0
    ext1.end_char = 13
    extractions.append(ext1)

    # Course title
    ext2 = MagicMock()
    ext2.extraction_class = "course_title"
    ext2.extraction_text = "10X Sales System"
    ext2.attributes = {}
    ext2.start_char = 14
    ext2.end_char = 30
    extractions.append(ext2)

    # Module number
    ext3 = MagicMock()
    ext3.extraction_class = "module_number"
    ext3.extraction_text = "1"
    ext3.attributes = {"full_text": "Module 1"}
    ext3.start_char = 31
    ext3.end_char = 39
    extractions.append(ext3)

    # Module name
    ext4 = MagicMock()
    ext4.extraction_class = "module_name"
    ext4.extraction_text = "Prospecting Fundamentals"
    ext4.attributes = {}
    ext4.start_char = 41
    ext4.end_char = 65
    extractions.append(ext4)

    # Lesson number
    ext5 = MagicMock()
    ext5.extraction_class = "lesson_number"
    ext5.extraction_text = "1"
    ext5.attributes = {"full_text": "Lesson 1"}
    ext5.start_char = 66
    ext5.end_char = 74
    extractions.append(ext5)

    # Lesson name
    ext6 = MagicMock()
    ext6.extraction_class = "lesson_name"
    ext6.extraction_text = "Cold Calling Basics"
    ext6.attributes = {}
    ext6.start_char = 76
    ext6.end_char = 95
    extractions.append(ext6)

    mock_extraction.extractions = extractions
    return mock_extraction


@pytest.fixture
def sample_course_text():
    """Sample course document text"""
    return """
    10X Sales System by Grant Cardone
    Module 1: Prospecting Fundamentals
    Lesson 1: Cold Calling Basics

    In this lesson, we'll cover the fundamentals of cold calling,
    including how to identify prospects and overcome objections.
    """


@pytest.fixture
def sample_metadata():
    """Sample extracted metadata"""
    return {
        "instructor": "Grant Cardone",
        "course_title": "10X Sales System",
        "module_number": "1",
        "module_name": "Prospecting Fundamentals",
        "lesson_number": "1",
        "lesson_name": "Cold Calling Basics"
    }


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client"""
    mock_client = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"id": "course-123"}]

    mock_table.insert.return_value.execute.return_value = mock_response
    mock_client.table.return_value = mock_table

    return mock_client


# ============================================================================
# Test CourseMetadataSchema
# ============================================================================

class TestCourseMetadataSchema:
    """Test extraction schema and prompts"""

    def test_extraction_classes_defined(self):
        """Test that extraction classes are properly defined"""
        classes = CourseMetadataSchema.EXTRACTION_CLASSES

        assert "instructor" in classes
        assert "company" in classes
        assert "course_title" in classes
        assert "module_number" in classes
        assert "module_name" in classes
        assert "lesson_number" in classes
        assert "lesson_name" in classes
        assert "date" in classes
        assert "topic" in classes
        assert "duration" in classes
        assert len(classes) == 10

    def test_extraction_prompt_exists(self):
        """Test that extraction prompt is returned"""
        prompt = CourseMetadataSchema.get_extraction_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "instructor" in prompt.lower()
        assert "module" in prompt.lower()
        assert "lesson" in prompt.lower()

    def test_extraction_examples_without_langextract(self):
        """Test that examples return empty list when LangExtract unavailable"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', False):
            examples = CourseMetadataSchema.get_extraction_examples()
            assert examples == []

    def test_extraction_examples_with_langextract(self):
        """Test that examples are created when LangExtract available"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', True), \
             patch('app.services.langextract_service.lx', create=True) as mock_lx:

            # Mock lx.data.ExampleData and lx.data.Extraction
            mock_lx.data.ExampleData = MagicMock()
            mock_lx.data.Extraction = MagicMock()

            examples = CourseMetadataSchema.get_extraction_examples()

            # Should be a list (even if empty due to mocking)
            assert isinstance(examples, list)


# ============================================================================
# Test LangExtractService
# ============================================================================

class TestLangExtractService:
    """Test LangExtract API integration"""

    def test_initialization_with_api_key(self):
        """Test service initialization with API key"""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            service = LangExtractService()

            assert service.model_id == "gemini-2.0-flash-exp"
            assert service.api_key == "test-key"

    def test_initialization_without_api_key(self):
        """Test service initialization without API key"""
        with patch.dict(os.environ, {}, clear=True):
            service = LangExtractService()

            assert service.api_key is None

    def test_initialization_custom_model(self):
        """Test service initialization with custom model"""
        service = LangExtractService(model_id="gemini-1.5-flash")

        assert service.model_id == "gemini-1.5-flash"

    @pytest.mark.asyncio
    async def test_extract_course_metadata_no_langextract(self):
        """Test extraction fails gracefully when LangExtract unavailable"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', False):
            service = LangExtractService()

            result = await service.extract_course_metadata("Sample text")

            assert result["success"] is False
            assert "LangExtract library not available" in result["errors"]
            assert result["extractions"] == []
            assert result["metadata"] == {}

    @pytest.mark.asyncio
    async def test_extract_course_metadata_no_api_key(self):
        """Test extraction fails when no API key configured"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', True), \
             patch.dict(os.environ, {}, clear=True):

            service = LangExtractService()

            result = await service.extract_course_metadata("Sample text")

            assert result["success"] is False
            assert "Google API key not configured" in result["errors"]

    @pytest.mark.asyncio
    async def test_extract_course_metadata_success(self, sample_course_text, mock_langextract_extraction):
        """Test successful course metadata extraction"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', True), \
             patch('app.services.langextract_service.lx', create=True) as mock_lx, \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):

            # Mock the lx.extract function
            mock_lx.extract.return_value = mock_langextract_extraction

            service = LangExtractService()

            result = await service.extract_course_metadata(sample_course_text)

            assert result["success"] is True
            assert len(result["extractions"]) > 0
            assert "instructor" in result["metadata"]
            assert result["metadata"]["instructor"] == "Grant Cardone"
            assert result["metadata"]["course_title"] == "10X Sales System"
            assert result["metadata"]["module_number"] == "1"
            assert result["metadata"]["lesson_number"] == "1"

    @pytest.mark.asyncio
    async def test_extract_course_metadata_with_params(self, sample_course_text):
        """Test extraction with custom parameters"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', True), \
             patch('app.services.langextract_service.lx', create=True) as mock_lx, \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):

            mock_result = MagicMock()
            mock_result.extractions = []
            mock_lx.extract.return_value = mock_result

            service = LangExtractService()

            result = await service.extract_course_metadata(
                document_text=sample_course_text,
                extraction_passes=2,
                max_workers=4
            )

            # Verify lx.extract was called with correct params
            mock_lx.extract.assert_called_once()
            call_kwargs = mock_lx.extract.call_args[1]
            assert call_kwargs["extraction_passes"] == 2
            assert call_kwargs["max_workers"] == 4

    @pytest.mark.asyncio
    async def test_extract_course_metadata_no_extractions(self, sample_course_text):
        """Test when LangExtract returns no extractions"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', True), \
             patch('app.services.langextract_service.lx', create=True) as mock_lx, \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):

            # Mock result with no extractions attribute
            mock_result = MagicMock(spec=[])  # No 'extractions' attribute
            mock_lx.extract.return_value = mock_result

            service = LangExtractService()

            result = await service.extract_course_metadata(sample_course_text)

            assert result["success"] is False
            assert "No extractions returned" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_extract_course_metadata_exception(self, sample_course_text):
        """Test exception handling during extraction"""
        with patch('app.services.langextract_service.LANGEXTRACT_SUPPORT', True), \
             patch('app.services.langextract_service.lx', create=True) as mock_lx, \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):

            # Mock lx.extract to raise exception
            mock_lx.extract.side_effect = Exception("API error")

            service = LangExtractService()

            result = await service.extract_course_metadata(sample_course_text)

            assert result["success"] is False
            assert "Extraction error" in result["errors"][0]
            assert "API error" in result["errors"][0]

    def test_build_metadata_dict(self, sample_metadata):
        """Test building metadata dictionary from extractions"""
        service = LangExtractService()

        extractions = [
            {"class": "instructor", "text": "Grant Cardone", "attributes": {}},
            {"class": "course_title", "text": "10X Sales System", "attributes": {}},
            {"class": "module_number", "text": "1", "attributes": {}},
        ]

        metadata = service._build_metadata_dict(extractions)

        assert metadata["instructor"] == "Grant Cardone"
        assert metadata["course_title"] == "10X Sales System"
        assert metadata["module_number"] == "1"

    def test_build_metadata_dict_duplicates(self):
        """Test that first occurrence is kept for duplicate classes"""
        service = LangExtractService()

        extractions = [
            {"class": "instructor", "text": "Grant Cardone", "attributes": {}},
            {"class": "instructor", "text": "John Doe", "attributes": {}},  # Duplicate
        ]

        metadata = service._build_metadata_dict(extractions)

        # Should keep first occurrence
        assert metadata["instructor"] == "Grant Cardone"


# ============================================================================
# Test MetadataStorage
# ============================================================================

class TestMetadataStorage:
    """Test metadata storage and filename generation"""

    def test_generate_filename_full_metadata(self, sample_metadata):
        """Test filename generation with complete metadata"""
        filename = MetadataStorage.generate_filename(
            metadata=sample_metadata,
            original_filename="document.pdf"
        )

        expected = "Grant_Cardone-10X_Sales_System-M01-Prospecting_Fundamentals-L01-Cold_Calling_Basics.pdf"
        assert filename == expected

    def test_generate_filename_partial_metadata(self):
        """Test filename generation with partial metadata"""
        metadata = {
            "instructor": "Grant Cardone",
            "course_title": "10X Sales System",
            "module_number": "2"
            # Missing module_name, lesson_number, lesson_name
        }

        filename = MetadataStorage.generate_filename(
            metadata=metadata,
            original_filename="doc.pdf"
        )

        expected = "Grant_Cardone-10X_Sales_System-M02.pdf"
        assert filename == expected

    def test_generate_filename_no_extension(self, sample_metadata):
        """Test filename generation without original extension"""
        filename = MetadataStorage.generate_filename(
            metadata=sample_metadata,
            original_filename=None
        )

        expected = "Grant_Cardone-10X_Sales_System-M01-Prospecting_Fundamentals-L01-Cold_Calling_Basics"
        assert filename == expected

    def test_generate_filename_number_padding(self):
        """Test that module/lesson numbers are zero-padded"""
        metadata = {
            "instructor": "John Doe",
            "course_title": "Test Course",
            "module_number": "5",
            "lesson_number": "12"
        }

        filename = MetadataStorage.generate_filename(metadata)

        assert "M05" in filename
        assert "L12" in filename

    def test_generate_filename_special_characters(self):
        """Test that special characters are cleaned from filename"""
        metadata = {
            "instructor": "John O'Brien",
            "course_title": "Sales & Marketing: 101",
            "module_number": "1",
            "module_name": "Introduction (Part 1)"
        }

        filename = MetadataStorage.generate_filename(metadata, "doc.pdf")

        # Should remove special characters
        assert "'" not in filename
        assert "&" not in filename
        assert ":" not in filename
        assert "(" not in filename
        assert ")" not in filename

    def test_generate_filename_empty_metadata(self):
        """Test filename generation with empty metadata"""
        metadata = {}

        filename = MetadataStorage.generate_filename(
            metadata=metadata,
            original_filename="test.pdf"
        )

        # With empty metadata and extension, returns just extension
        # (Implementation note: This is edge case - may want to fix in future)
        assert filename == ".pdf"

    def test_generate_filename_spaces_to_underscores(self):
        """Test that spaces are converted to underscores"""
        metadata = {
            "instructor": "Grant Cardone",
            "course_title": "Sales Training",
            "lesson_number": "1",  # Needed for lesson_name to be included
            "lesson_name": "Cold Calling Basics"
        }

        filename = MetadataStorage.generate_filename(metadata)

        assert "Grant_Cardone" in filename
        assert "Sales_Training" in filename
        assert "Cold_Calling_Basics" in filename
        assert " " not in filename

    @pytest.mark.asyncio
    async def test_store_course_metadata_success(self, sample_metadata, mock_supabase_client):
        """Test successful storage of course metadata"""
        result = await MetadataStorage.store_course_metadata(
            metadata=sample_metadata,
            document_id="doc-123",
            supabase_client=mock_supabase_client
        )

        assert result["success"] is True
        assert result["course_id"] == "course-123"
        assert result["errors"] == []

        # Verify Supabase was called
        mock_supabase_client.table.assert_called_once_with("courses")

    @pytest.mark.asyncio
    async def test_store_course_metadata_with_numbers(self, mock_supabase_client):
        """Test that module/lesson numbers are converted to integers"""
        metadata = {
            "instructor": "John Doe",
            "module_number": "5",
            "lesson_number": "12"
        }

        await MetadataStorage.store_course_metadata(
            metadata=metadata,
            document_id="doc-123",
            supabase_client=mock_supabase_client
        )

        # Get the data that was sent to Supabase
        call_args = mock_supabase_client.table().insert.call_args
        course_data = call_args[0][0]

        assert course_data["module_number"] == 5
        assert course_data["lesson_number"] == 12
        assert isinstance(course_data["module_number"], int)
        assert isinstance(course_data["lesson_number"], int)

    @pytest.mark.asyncio
    async def test_store_course_metadata_exception(self, sample_metadata):
        """Test exception handling during storage"""
        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Database error")

        result = await MetadataStorage.store_course_metadata(
            metadata=sample_metadata,
            document_id="doc-123",
            supabase_client=mock_client
        )

        assert result["success"] is False
        assert "Storage error" in result["errors"][0]
        assert "Database error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_store_course_metadata_no_data_returned(self, sample_metadata):
        """Test when Supabase returns no data"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = None
        mock_client.table().insert().execute.return_value = mock_response

        result = await MetadataStorage.store_course_metadata(
            metadata=sample_metadata,
            document_id="doc-123",
            supabase_client=mock_client
        )

        assert result["success"] is False
        assert "No data returned from Supabase insert" in result["errors"]

    @pytest.mark.asyncio
    async def test_store_document_chunks_with_metadata_success(self, sample_metadata, mock_supabase_client):
        """Test successful storage of document chunks with metadata"""
        chunks = [
            {"id": "chunk-1", "content": "Text 1", "chunk_index": 0},
            {"id": "chunk-2", "content": "Text 2", "chunk_index": 1},
        ]

        # Update mock to return chunk IDs
        mock_response = MagicMock()
        mock_response.data = [{"id": "chunk-1"}, {"id": "chunk-2"}]
        mock_supabase_client.table().insert().execute.return_value = mock_response

        result = await MetadataStorage.store_document_chunks_with_metadata(
            chunks=chunks,
            metadata=sample_metadata,
            supabase_client=mock_supabase_client
        )

        assert result["success"] is True
        assert len(result["chunk_ids"]) == 2
        assert result["chunk_ids"] == ["chunk-1", "chunk-2"]
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_store_document_chunks_metadata_enrichment(self, sample_metadata, mock_supabase_client):
        """Test that chunks are enriched with metadata"""
        chunks = [{"id": "chunk-1", "content": "Text 1"}]

        mock_response = MagicMock()
        mock_response.data = [{"id": "chunk-1"}]
        mock_supabase_client.table().insert().execute.return_value = mock_response

        await MetadataStorage.store_document_chunks_with_metadata(
            chunks=chunks,
            metadata=sample_metadata,
            supabase_client=mock_supabase_client
        )

        # Get the enriched chunks that were sent
        call_args = mock_supabase_client.table().insert.call_args
        enriched_chunks = call_args[0][0]

        # Verify metadata was added
        assert enriched_chunks[0]["instructor"] == "Grant Cardone"
        assert enriched_chunks[0]["course_title"] == "10X Sales System"
        assert enriched_chunks[0]["module_number"] == "1"
        assert enriched_chunks[0]["lesson_number"] == "1"
        assert enriched_chunks[0]["metadata"] == sample_metadata

    @pytest.mark.asyncio
    async def test_store_document_chunks_exception(self, sample_metadata):
        """Test exception handling during chunk storage"""
        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Database error")

        chunks = [{"id": "chunk-1", "content": "Text"}]

        result = await MetadataStorage.store_document_chunks_with_metadata(
            chunks=chunks,
            metadata=sample_metadata,
            supabase_client=mock_client
        )

        assert result["success"] is False
        assert "Chunk storage error" in result["errors"][0]


# ============================================================================
# Test Singleton Pattern
# ============================================================================

class TestSingletonPattern:
    """Test singleton service instance"""

    def test_singleton_returns_same_instance(self):
        """Test that get_langextract_service returns singleton"""
        # Reset singleton
        langextract_module._langextract_service_instance = None

        service1 = get_langextract_service()
        service2 = get_langextract_service()

        assert service1 is service2

    def test_singleton_with_custom_model(self):
        """Test singleton with custom model ID"""
        # Reset singleton
        langextract_module._langextract_service_instance = None

        service = get_langextract_service(model_id="gemini-1.5-flash")

        assert service.model_id == "gemini-1.5-flash"
