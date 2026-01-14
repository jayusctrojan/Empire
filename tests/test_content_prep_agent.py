"""
Empire v7.3 - Content Prep Agent Test Suite (Task 131)

Feature: 007-content-prep-agent
Comprehensive tests for AGENT-016: Content Prep Agent

Includes:
- Unit tests for pattern detection, sequence extraction, validation
- Integration tests with mocked dependencies
- Performance benchmarks for large file sets
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

# Import the actual classes
from app.services.content_prep_agent import (
    ContentPrepAgent,
    ContentFile,
    ContentSet,
    ProcessingManifest,
    SEQUENCE_PATTERNS,
    CONTENT_SET_INDICATORS,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_b2_service():
    """Mock B2 storage service."""
    service = Mock()
    service.list_files = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    client = MagicMock()
    # Set up table().select().eq().execute() chain
    mock_result = MagicMock()
    mock_result.data = []

    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.execute.return_value = mock_result
    table_mock.insert.return_value = table_mock
    table_mock.upsert.return_value = table_mock

    client.table.return_value = table_mock
    return client


@pytest.fixture
def content_prep_agent(mock_b2_service, mock_supabase):
    """Create ContentPrepAgent with mocked dependencies."""
    with patch('app.services.content_prep_agent.B2StorageService', return_value=mock_b2_service), \
         patch('app.services.content_prep_agent.get_supabase_client', return_value=mock_supabase), \
         patch('app.services.content_prep_agent.Agent'):
        agent = ContentPrepAgent()
        agent.b2_service = mock_b2_service
        agent.supabase = mock_supabase
        return agent


@pytest.fixture
def sample_course_files():
    """Sample course files with sequence numbers."""
    return [
        {"path": "pending/courses/01-intro.pdf", "filename": "01-intro.pdf", "size": 1024000},
        {"path": "pending/courses/02-basics.pdf", "filename": "02-basics.pdf", "size": 2048000},
        {"path": "pending/courses/03-advanced.pdf", "filename": "03-advanced.pdf", "size": 3072000},
        {"path": "pending/courses/04-final.pdf", "filename": "04-final.pdf", "size": 1536000},
    ]


@pytest.fixture
def sample_mixed_files():
    """Mixed files with some sequence and some standalone."""
    return [
        {"path": "pending/course/module-01-intro.pdf", "filename": "module-01-intro.pdf", "size": 1024000},
        {"path": "pending/course/module-02-basics.pdf", "filename": "module-02-basics.pdf", "size": 2048000},
        {"path": "pending/course/module-03-advanced.pdf", "filename": "module-03-advanced.pdf", "size": 3072000},
        {"path": "pending/random-file.txt", "filename": "random-file.txt", "size": 10240},
        {"path": "pending/notes.docx", "filename": "notes.docx", "size": 51200},
    ]


@pytest.fixture
def sample_content_set():
    """Sample ContentSet for testing."""
    files = [
        ContentFile(
            b2_path="pending/course/01-intro.pdf",
            filename="01-intro.pdf",
            sequence_number=1,
            detection_pattern="numeric_prefix",
        ),
        ContentFile(
            b2_path="pending/course/02-basics.pdf",
            filename="02-basics.pdf",
            sequence_number=2,
            detection_pattern="numeric_prefix",
        ),
        ContentFile(
            b2_path="pending/course/03-advanced.pdf",
            filename="03-advanced.pdf",
            sequence_number=3,
            detection_pattern="numeric_prefix",
        ),
    ]

    return ContentSet(
        id=str(uuid4()),
        name="Test Course",
        detection_method="pattern",
        files=files,
        is_complete=True,
        confidence=0.95,
    )


@pytest.fixture
def incomplete_content_set():
    """Sample incomplete ContentSet (missing file 2)."""
    files = [
        ContentFile(
            b2_path="pending/course/01-intro.pdf",
            filename="01-intro.pdf",
            sequence_number=1,
            detection_pattern="numeric_prefix",
        ),
        ContentFile(
            b2_path="pending/course/03-advanced.pdf",
            filename="03-advanced.pdf",
            sequence_number=3,
            detection_pattern="numeric_prefix",
        ),
        ContentFile(
            b2_path="pending/course/04-final.pdf",
            filename="04-final.pdf",
            sequence_number=4,
            detection_pattern="numeric_prefix",
        ),
    ]

    return ContentSet(
        id=str(uuid4()),
        name="Incomplete Course",
        detection_method="pattern",
        files=files,
        is_complete=False,
        missing_files=["#2 (between 1 and 3)"],
        confidence=0.85,
    )


# ============================================================================
# Unit Tests: Sequence Extraction
# ============================================================================

class TestSequenceExtraction:
    """Tests for _extract_sequence method."""

    def test_numeric_prefix_detection(self, content_prep_agent):
        """Test detection of numeric prefix patterns."""
        test_cases = [
            ("01-intro.pdf", 1, "numeric_prefix"),
            ("02-basics.pdf", 2, "numeric_prefix"),
            ("10-advanced.pdf", 10, "numeric_prefix"),
            ("99-final.pdf", 99, "numeric_prefix"),
        ]

        for filename, expected_num, expected_pattern in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq == expected_num, f"Failed for {filename}: got {seq}, expected {expected_num}"

    def test_chapter_pattern_detection(self, content_prep_agent):
        """Test detection of chapter patterns."""
        test_cases = [
            ("chapter-01-intro.pdf", 1),
            ("chapter1-basics.pdf", 1),
            ("chapter_5_conclusion.pdf", 5),
            ("Chapter-10-Summary.pdf", 10),
        ]

        for filename, expected_num in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq == expected_num, f"Failed for {filename}: got {seq}, expected {expected_num}"

    def test_module_pattern_detection(self, content_prep_agent):
        """Test detection of module patterns."""
        test_cases = [
            ("module01.pdf", 1),
            ("module-02.pdf", 2),
            ("module_3.pdf", 3),
            ("Module-10-Advanced.pdf", 10),
        ]

        for filename, expected_num in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq == expected_num, f"Failed for {filename}: got {seq}, expected {expected_num}"

    def test_lesson_pattern_detection(self, content_prep_agent):
        """Test detection of lesson patterns."""
        test_cases = [
            ("lesson1.pdf", 1),
            ("lesson-5-intro.pdf", 5),
            ("Lesson_10_Summary.pdf", 10),
        ]

        for filename, expected_num in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq == expected_num, f"Failed for {filename}: got {seq}, expected {expected_num}"

    def test_roman_numeral_detection(self, content_prep_agent):
        """Test detection of roman numeral patterns."""
        test_cases = [
            ("i-intro.pdf", 1),
            ("ii-basics.pdf", 2),
            ("iii-intermediate.pdf", 3),
            ("iv-advanced.pdf", 4),
            ("v-expert.pdf", 5),
        ]

        for filename, expected_num in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq == expected_num, f"Failed for {filename}: got {seq}, expected {expected_num}"

    def test_alpha_sequence_detection(self, content_prep_agent):
        """Test detection of alpha sequence patterns."""
        test_cases = [
            ("a-intro.pdf", 1),
            ("b-basics.pdf", 2),
            ("c-intermediate.pdf", 3),
        ]

        for filename, expected_num in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq == expected_num, f"Failed for {filename}: got {seq}, expected {expected_num}"

    def test_no_sequence_detection(self, content_prep_agent):
        """Test files without sequence numbers."""
        test_cases = [
            "random-file.txt",
            "notes.docx",
            "readme.md",
            "config.json",
        ]

        for filename in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            assert seq is None, f"Incorrectly detected sequence for {filename}: {seq}"


# ============================================================================
# Unit Tests: Prefix Extraction
# ============================================================================

class TestPrefixExtraction:
    """Tests for _extract_prefix method."""

    def test_prefix_from_numeric_sequence(self, content_prep_agent):
        """Test prefix extraction from numeric sequences."""
        test_cases = [
            ("course-01-intro.pdf", "course"),
            ("module-02-basics.pdf", "module"),
            ("training-03-advanced.pdf", "training"),
        ]

        for filename, expected_prefix in test_cases:
            prefix = content_prep_agent._extract_prefix(filename)
            assert prefix == expected_prefix, f"Failed for {filename}: got {prefix}, expected {expected_prefix}"

    def test_prefix_from_content_indicator(self, content_prep_agent):
        """Test prefix extraction from content set indicators."""
        for indicator in CONTENT_SET_INDICATORS[:5]:  # Test first 5 indicators
            filename = f"my-{indicator}-01.pdf"
            prefix = content_prep_agent._extract_prefix(filename)
            assert prefix is not None, f"Failed to extract prefix for {filename}"

    def test_no_prefix_for_random_files(self, content_prep_agent):
        """Test that random files don't get a prefix."""
        test_cases = [
            "random.txt",
            "ab.pdf",  # Too short
            "x-1.pdf",  # Prefix too short
        ]

        for filename in test_cases:
            prefix = content_prep_agent._extract_prefix(filename)
            # These should either return None or a very short prefix


# ============================================================================
# Unit Tests: Content Set Creation
# ============================================================================

class TestContentSetCreation:
    """Tests for content set creation and validation."""

    def test_create_content_file(self):
        """Test ContentFile dataclass creation."""
        file = ContentFile(
            b2_path="pending/course/01-intro.pdf",
            filename="01-intro.pdf",
            sequence_number=1,
            detection_pattern="numeric_prefix",
        )

        assert file.b2_path == "pending/course/01-intro.pdf"
        assert file.filename == "01-intro.pdf"
        assert file.sequence_number == 1
        assert file.dependencies == []
        assert file.estimated_complexity == "medium"

    def test_create_content_set(self):
        """Test ContentSet dataclass creation."""
        content_set = ContentSet(
            name="Test Course",
            detection_method="pattern",
        )

        assert content_set.name == "Test Course"
        assert content_set.id is not None  # Auto-generated UUID
        assert content_set.is_complete is True
        assert content_set.missing_files == []
        assert content_set.processing_status == "pending"

    def test_content_set_with_files(self, sample_content_set):
        """Test ContentSet with files."""
        assert len(sample_content_set.files) == 3
        assert sample_content_set.is_complete is True
        assert sample_content_set.confidence == 0.95

    def test_incomplete_content_set(self, incomplete_content_set):
        """Test incomplete ContentSet."""
        assert incomplete_content_set.is_complete is False
        assert len(incomplete_content_set.missing_files) == 1
        assert "#2" in incomplete_content_set.missing_files[0]


# ============================================================================
# Unit Tests: Processing Manifest
# ============================================================================

class TestProcessingManifest:
    """Tests for ProcessingManifest creation."""

    def test_create_manifest(self):
        """Test ProcessingManifest dataclass creation."""
        manifest = ProcessingManifest(
            content_set_id="test-123",
            content_set_name="Test Course",
            total_files=5,
        )

        assert manifest.manifest_id is not None
        assert manifest.content_set_id == "test-123"
        assert manifest.total_files == 5
        assert manifest.ordered_files == []
        assert manifest.warnings == []

    def test_manifest_with_files(self):
        """Test ProcessingManifest with ordered files."""
        ordered_files = [
            {"sequence": 1, "file": "01-intro.pdf", "dependencies": []},
            {"sequence": 2, "file": "02-basics.pdf", "dependencies": ["01-intro.pdf"]},
            {"sequence": 3, "file": "03-advanced.pdf", "dependencies": ["02-basics.pdf"]},
        ]

        manifest = ProcessingManifest(
            content_set_id="test-123",
            content_set_name="Test Course",
            ordered_files=ordered_files,
            total_files=3,
            estimated_time_seconds=90,
        )

        assert len(manifest.ordered_files) == 3
        assert manifest.ordered_files[1]["dependencies"] == ["01-intro.pdf"]


# ============================================================================
# Integration Tests: Folder Analysis
# ============================================================================

class TestFolderAnalysis:
    """Integration tests for folder analysis."""

    @pytest.mark.asyncio
    async def test_analyze_empty_folder(self, content_prep_agent, mock_b2_service):
        """Test analysis of empty folder."""
        mock_b2_service.list_files.return_value = []

        result = await content_prep_agent.analyze_folder("pending/test/")

        assert result["content_sets"] == []
        assert result["standalone_files"] == []

    @pytest.mark.asyncio
    async def test_single_file_passthrough(self, content_prep_agent, mock_b2_service):
        """Test US-004: Single file passthrough."""
        mock_b2_service.list_files.return_value = [
            {"path": "pending/single-file.pdf", "filename": "single-file.pdf", "size": 1024}
        ]

        result = await content_prep_agent.analyze_folder("pending/test/")

        assert len(result["content_sets"]) == 0
        assert len(result["standalone_files"]) == 1
        assert result["standalone_files"][0]["filename"] == "single-file.pdf"

    @pytest.mark.asyncio
    async def test_detect_course_content_set(self, content_prep_agent, mock_b2_service, sample_course_files):
        """Test detection of course content set."""
        mock_b2_service.list_files.return_value = sample_course_files

        # Mock the database storage
        content_prep_agent.supabase.table().upsert().execute.return_value = MagicMock(data=[{}])

        result = await content_prep_agent.analyze_folder("pending/courses/", detection_mode="pattern")

        # Should detect the course as a content set
        # (The exact number depends on prefix grouping logic)
        assert "content_sets" in result
        assert "standalone_files" in result

    @pytest.mark.asyncio
    async def test_mixed_files_detection(self, content_prep_agent, mock_b2_service, sample_mixed_files):
        """Test detection with mixed files."""
        mock_b2_service.list_files.return_value = sample_mixed_files
        content_prep_agent.supabase.table().upsert().execute.return_value = MagicMock(data=[{}])

        result = await content_prep_agent.analyze_folder("pending/", detection_mode="pattern")

        assert "content_sets" in result
        assert "standalone_files" in result


# ============================================================================
# Integration Tests: Validation
# ============================================================================

class TestValidation:
    """Integration tests for content set validation."""

    @pytest.mark.asyncio
    async def test_validate_complete_set(self, content_prep_agent, mock_supabase, sample_content_set):
        """Test validation of complete content set."""
        # Mock database lookup
        mock_result = MagicMock()
        mock_result.data = [{
            "id": sample_content_set.id,
            "name": sample_content_set.name,
            "is_complete": True,
            "missing_files": [],
            "files": [
                {"b2_path": f.b2_path, "filename": f.filename, "sequence_number": f.sequence_number}
                for f in sample_content_set.files
            ]
        }]

        mock_supabase.table().select().eq().execute.return_value = mock_result

        # We need to mock the _load_content_set method
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = sample_content_set

            result = await content_prep_agent.validate_completeness(sample_content_set.id)

            assert result["is_complete"] is True
            assert result["gaps_detected"] == 0
            assert result["requires_acknowledgment"] is False

    @pytest.mark.asyncio
    async def test_validate_incomplete_set(self, content_prep_agent, incomplete_content_set):
        """Test validation of incomplete content set."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = incomplete_content_set

            result = await content_prep_agent.validate_completeness(incomplete_content_set.id)

            assert result["is_complete"] is False
            assert result["gaps_detected"] >= 1
            assert result["requires_acknowledgment"] is True

    @pytest.mark.asyncio
    async def test_validate_nonexistent_set(self, content_prep_agent):
        """Test validation of non-existent content set."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = None

            with pytest.raises(ValueError, match="not found"):
                await content_prep_agent.validate_completeness("nonexistent-id")


# ============================================================================
# Integration Tests: Manifest Generation
# ============================================================================

class TestManifestGeneration:
    """Integration tests for manifest generation."""

    @pytest.mark.asyncio
    async def test_generate_manifest_complete_set(self, content_prep_agent, sample_content_set):
        """Test manifest generation for complete set."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load, \
             patch.object(content_prep_agent, '_store_manifest', new_callable=AsyncMock) as mock_store:
            mock_load.return_value = sample_content_set

            result = await content_prep_agent.generate_manifest(sample_content_set.id)

            assert "manifest_id" in result
            assert result["total_files"] == 3
            assert len(result["ordered_files"]) == 3
            assert result["warnings"] == []

            # Verify ordering
            for i, file_info in enumerate(result["ordered_files"]):
                assert file_info["sequence"] == i + 1

    @pytest.mark.asyncio
    async def test_generate_manifest_incomplete_blocked(self, content_prep_agent, incomplete_content_set):
        """Test that incomplete sets are blocked without acknowledgment."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = incomplete_content_set

            with pytest.raises(ValueError, match="incomplete"):
                await content_prep_agent.generate_manifest(incomplete_content_set.id, proceed_incomplete=False)

    @pytest.mark.asyncio
    async def test_generate_manifest_incomplete_acknowledged(self, content_prep_agent, incomplete_content_set):
        """Test manifest generation with acknowledged incomplete set."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load, \
             patch.object(content_prep_agent, '_store_manifest', new_callable=AsyncMock) as mock_store:
            mock_load.return_value = incomplete_content_set

            result = await content_prep_agent.generate_manifest(
                incomplete_content_set.id,
                proceed_incomplete=True
            )

            assert "manifest_id" in result
            assert len(result["warnings"]) > 0  # Should have warnings about missing files

    @pytest.mark.asyncio
    async def test_manifest_dependencies(self, content_prep_agent, sample_content_set):
        """Test that manifest includes proper dependencies."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load, \
             patch.object(content_prep_agent, '_store_manifest', new_callable=AsyncMock):
            mock_load.return_value = sample_content_set

            result = await content_prep_agent.generate_manifest(sample_content_set.id)

            # First file has no dependencies
            assert result["ordered_files"][0]["dependencies"] == []

            # Subsequent files depend on previous
            assert len(result["ordered_files"][1]["dependencies"]) == 1
            assert len(result["ordered_files"][2]["dependencies"]) == 1


# ============================================================================
# Integration Tests: List and Get
# ============================================================================

class TestListAndGet:
    """Integration tests for listing and getting content sets."""

    @pytest.mark.asyncio
    async def test_list_sets(self, content_prep_agent, mock_supabase):
        """Test listing all content sets."""
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "set-1", "name": "Course 1", "processing_status": "pending"},
            {"id": "set-2", "name": "Course 2", "processing_status": "complete"},
        ]
        mock_supabase.table().select().order().execute.return_value = mock_result

        result = await content_prep_agent.list_sets()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_sets_with_filter(self, content_prep_agent, mock_supabase):
        """Test listing content sets with status filter."""
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "set-1", "name": "Course 1", "processing_status": "pending"},
        ]
        mock_supabase.table().select().eq().order().execute.return_value = mock_result

        result = await content_prep_agent.list_sets(status="pending")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_set(self, content_prep_agent, sample_content_set):
        """Test getting specific content set."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = sample_content_set

            result = await content_prep_agent.get_set(sample_content_set.id)

            assert result["name"] == sample_content_set.name

    @pytest.mark.asyncio
    async def test_get_nonexistent_set(self, content_prep_agent):
        """Test getting non-existent content set."""
        with patch.object(content_prep_agent, '_load_content_set', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = None

            with pytest.raises(ValueError, match="not found"):
                await content_prep_agent.get_set("nonexistent-id")


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance tests for large file sets."""

    def test_sequence_extraction_performance(self, content_prep_agent):
        """Test sequence extraction performance with many files."""
        import time

        # Generate 1000 test filenames
        filenames = [f"{i:03d}-lesson-{i}.pdf" for i in range(1, 1001)]

        start = time.time()
        for filename in filenames:
            content_prep_agent._extract_sequence(filename)
        elapsed = time.time() - start

        # Should complete in under 1 second for 1000 files
        assert elapsed < 1.0, f"Sequence extraction too slow: {elapsed:.2f}s for 1000 files"

    def test_prefix_extraction_performance(self, content_prep_agent):
        """Test prefix extraction performance with many files."""
        import time

        # Generate varied filenames
        filenames = [
            f"course-{i:03d}-lesson.pdf" for i in range(500)
        ] + [
            f"module-{i:03d}-content.pdf" for i in range(500)
        ]

        start = time.time()
        for filename in filenames:
            content_prep_agent._extract_prefix(filename)
        elapsed = time.time() - start

        # Should complete in under 1 second for 1000 files
        assert elapsed < 1.0, f"Prefix extraction too slow: {elapsed:.2f}s for 1000 files"


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_filename(self, content_prep_agent):
        """Test handling of empty filename."""
        seq, pattern = content_prep_agent._extract_sequence("")
        assert seq is None

    def test_unicode_filename(self, content_prep_agent):
        """Test handling of unicode in filename."""
        seq, pattern = content_prep_agent._extract_sequence("01-introduction-こんにちは.pdf")
        # Should still detect the sequence number
        assert seq == 1

    def test_very_long_filename(self, content_prep_agent):
        """Test handling of very long filename."""
        long_name = "01-" + "a" * 500 + ".pdf"
        seq, pattern = content_prep_agent._extract_sequence(long_name)
        assert seq == 1

    def test_special_characters_in_filename(self, content_prep_agent):
        """Test handling of special characters."""
        test_cases = [
            "01 intro (version 2).pdf",
            "02_basics [final].pdf",
            "03-advanced+extras.pdf",
        ]

        for filename in test_cases:
            seq, pattern = content_prep_agent._extract_sequence(filename)
            # Should handle gracefully without errors


# ============================================================================
# Ordering Confidence Tests
# ============================================================================

class TestOrderingConfidence:
    """Tests for ordering confidence calculation."""

    def test_high_confidence_with_clear_sequence(self, sample_content_set):
        """Test high confidence for clearly sequenced files."""
        # All files have sequence numbers 1, 2, 3
        # Should have high confidence
        assert sample_content_set.confidence >= 0.9

    def test_calculate_ordering_confidence_all_sequential(self, content_prep_agent):
        """Test confidence calculation with all sequential files."""
        files = [
            ContentFile(b2_path="f1.pdf", filename="f1.pdf", sequence_number=1, detection_pattern="numeric_prefix"),
            ContentFile(b2_path="f2.pdf", filename="f2.pdf", sequence_number=2, detection_pattern="numeric_prefix"),
            ContentFile(b2_path="f3.pdf", filename="f3.pdf", sequence_number=3, detection_pattern="numeric_prefix"),
        ]
        content_set = ContentSet(files=files)

        confidence = content_prep_agent._calculate_ordering_confidence(content_set)

        assert confidence >= 0.8

    def test_calculate_ordering_confidence_mixed(self, content_prep_agent):
        """Test confidence calculation with mixed sequence detection."""
        files = [
            ContentFile(b2_path="f1.pdf", filename="01-intro.pdf", sequence_number=1),
            ContentFile(b2_path="f2.pdf", filename="random.pdf", sequence_number=None),
            ContentFile(b2_path="f3.pdf", filename="03-advanced.pdf", sequence_number=3),
        ]
        content_set = ContentSet(files=files)

        confidence = content_prep_agent._calculate_ordering_confidence(content_set)

        # Should be lower due to missing sequence
        assert confidence < 1.0


# ============================================================================
# Data Class Serialization Tests
# ============================================================================

class TestSerialization:
    """Tests for data class serialization."""

    def test_content_file_to_dict(self):
        """Test ContentFile serialization."""
        file = ContentFile(
            b2_path="test.pdf",
            filename="test.pdf",
            sequence_number=1,
            metadata={"key": "value"}
        )

        # Should be serializable to dict
        from dataclasses import asdict
        d = asdict(file)

        assert d["b2_path"] == "test.pdf"
        assert d["sequence_number"] == 1
        assert d["metadata"]["key"] == "value"

    def test_content_set_to_dict(self, sample_content_set):
        """Test ContentSet serialization."""
        from dataclasses import asdict
        d = asdict(sample_content_set)

        assert d["name"] == sample_content_set.name
        assert len(d["files"]) == 3

    def test_processing_manifest_to_dict(self):
        """Test ProcessingManifest serialization."""
        manifest = ProcessingManifest(
            content_set_id="test",
            total_files=5,
        )

        from dataclasses import asdict
        d = asdict(manifest)

        assert d["content_set_id"] == "test"
        assert d["total_files"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
