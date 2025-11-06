"""
Empire v7.3 - Classification Workflow Tests
Tests for AI-powered document classification and storage integration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

from app.services.classification_workflow import (
    get_classification_workflow,
    auto_classify_and_store
)


class TestClassificationWorkflow:
    """Test suite for ClassificationWorkflow"""

    @pytest.mark.asyncio
    async def test_classify_and_store_success(
        self,
        classification_workflow,
        mock_supabase_storage,
        mock_claude_classifier,
        sample_course_content
    ):
        """Test successful classification and storage workflow"""
        result = await classification_workflow.classify_and_store(
            b2_file_id="test_file_123",
            filename="sales_course.pdf",
            content_preview=sample_course_content,
            store_course_data=True
        )

        # Verify success
        assert result["success"] is True
        assert len(result["errors"]) == 0

        # Verify classification results
        assert result["classification"]["department"] == "sales-marketing"
        assert result["classification"]["confidence"] == 0.92
        assert "sales" in result["classification"]["suggested_tags"]

        # Verify storage was called
        assert result["storage"]["classification_stored"] is True
        assert result["storage"]["course_stored"] is True

        # Verify mock calls
        mock_claude_classifier.classify_and_extract.assert_called_once()
        mock_supabase_storage.store_classification_results.assert_called_once()
        mock_supabase_storage.store_course_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_without_course_storage(
        self,
        classification_workflow,
        sample_course_content
    ):
        """Test classification without storing course metadata"""
        result = await classification_workflow.classify_and_store(
            b2_file_id="test_file_456",
            filename="sales_doc.pdf",
            content_preview=sample_course_content,
            store_course_data=False
        )

        # Verify success
        assert result["success"] is True

        # Verify storage flags
        assert result["storage"]["classification_stored"] is True
        assert result["storage"]["course_stored"] is False

        # Verify course metadata was not stored
        classification_workflow.storage.store_course_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_with_classification_storage_failure(
        self,
        classification_workflow,
        sample_course_content
    ):
        """Test workflow when classification storage fails"""
        # Make classification storage fail
        classification_workflow.storage.store_classification_results = AsyncMock(return_value=False)

        result = await classification_workflow.classify_and_store(
            b2_file_id="test_file_789",
            filename="test.pdf",
            content_preview=sample_course_content,
            store_course_data=True
        )

        # Verify failure
        assert result["success"] is False
        assert "Failed to store classification results" in result["errors"][0]
        assert result["storage"]["classification_stored"] is False

    @pytest.mark.asyncio
    async def test_classify_with_course_storage_failure(
        self,
        classification_workflow,
        sample_course_content
    ):
        """Test workflow when course storage fails"""
        # Make course storage fail
        classification_workflow.storage.store_course_metadata = AsyncMock(return_value=None)

        result = await classification_workflow.classify_and_store(
            b2_file_id="test_file_abc",
            filename="course.pdf",
            content_preview=sample_course_content,
            store_course_data=True
        )

        # Verify partial failure
        assert result["success"] is False
        assert "Failed to store course metadata" in result["errors"][0]
        assert result["storage"]["classification_stored"] is True
        assert result["storage"]["course_stored"] is False

    @pytest.mark.asyncio
    async def test_classify_with_exception(
        self,
        classification_workflow,
        sample_course_content
    ):
        """Test workflow handles exceptions gracefully"""
        # Make classifier raise exception
        classification_workflow.classifier.classify_and_extract = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        result = await classification_workflow.classify_and_store(
            b2_file_id="test_file_def",
            filename="test.pdf",
            content_preview=sample_course_content
        )

        # Verify failure is handled
        assert result["success"] is False
        assert "API rate limit exceeded" in result["errors"][0]
        assert result["classification"] is None

    @pytest.mark.asyncio
    async def test_classify_from_b2_file_success(
        self,
        classification_workflow
    ):
        """Test classification from B2 file download"""
        # Mock B2 service
        classification_workflow.b2_service.get_file_info = AsyncMock(return_value={
            "file_id": "b2_file_123",
            "file_name": "sales_training.pdf",
            "size": 10240
        })
        classification_workflow.b2_service.download_file = AsyncMock(return_value=BytesIO(
            b"Sales Training Content - Module 1: Prospecting..."
        ))

        result = await classification_workflow.classify_from_b2_file(
            b2_file_id="b2_file_123",
            preview_bytes=1000,
            store_course_data=True
        )

        # Verify success
        assert result["success"] is True
        assert result["classification"] is not None

        # Verify B2 calls
        classification_workflow.b2_service.get_file_info.assert_called_once_with("b2_file_123")
        classification_workflow.b2_service.download_file.assert_called_once_with("b2_file_123")

    @pytest.mark.asyncio
    async def test_classify_from_b2_file_not_found(self, classification_workflow):
        """Test classification when B2 file not found"""
        # Mock B2 service - file not found
        classification_workflow.b2_service.get_file_info = AsyncMock(return_value=None)

        result = await classification_workflow.classify_from_b2_file(
            b2_file_id="nonexistent_file",
            store_course_data=True
        )

        # Verify failure
        assert result["success"] is False
        assert "File not found" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_classify_from_b2_file_download_failure(self, classification_workflow):
        """Test classification when B2 download fails"""
        # Mock B2 service - download fails
        classification_workflow.b2_service.get_file_info = AsyncMock(return_value={
            "file_id": "b2_file_456",
            "file_name": "test.pdf"
        })
        classification_workflow.b2_service.download_file = AsyncMock(return_value=None)

        result = await classification_workflow.classify_from_b2_file(
            b2_file_id="b2_file_456"
        )

        # Verify failure
        assert result["success"] is False
        assert "Failed to download" in result["errors"][0]


class TestClassificationStandaloneFunctions:
    """Test standalone functions"""

    @pytest.mark.asyncio
    async def test_auto_classify_and_store(
        self,
        mock_claude_classifier,
        mock_supabase_storage,
        sample_course_content
    ):
        """Test auto_classify_and_store standalone function"""
        with patch('app.services.classification_workflow.ClassificationWorkflow') as MockWorkflow:
            # Create mock workflow instance
            mock_workflow = MockWorkflow.return_value
            mock_workflow.classifier = mock_claude_classifier
            mock_workflow.storage = mock_supabase_storage
            mock_workflow.classify_and_store = AsyncMock(return_value={
                "success": True,
                "classification": {"department": "sales-marketing"},
                "storage": {"classification_stored": True}
            })

            result = await auto_classify_and_store(
                b2_file_id="test_123",
                filename="test.pdf",
                content_preview=sample_course_content
            )

            assert result["success"] is True


class TestGetClassificationWorkflow:
    """Test singleton pattern"""

    def test_get_classification_workflow_singleton(self):
        """Test get_classification_workflow returns singleton"""
        workflow1 = get_classification_workflow()
        workflow2 = get_classification_workflow()

        assert workflow1 is workflow2


class TestDepartmentClassification:
    """Test department classification logic"""

    @pytest.mark.asyncio
    async def test_it_engineering_classification(self, classification_workflow):
        """Test IT/Engineering department classification"""
        # Override classifier response
        classification_workflow.classifier.classify_and_extract = AsyncMock(return_value={
            "department": "it-engineering",
            "confidence": 0.95,
            "reasoning": "Content focuses on cloud architecture and DevOps practices",
            "suggested_tags": ["aws", "kubernetes", "devops"],
            "structure": None
        })

        result = await classification_workflow.classify_and_store(
            b2_file_id="tech_doc_123",
            filename="kubernetes_guide.pdf",
            content_preview="Kubernetes deployment best practices...",
            store_course_data=False
        )

        assert result["classification"]["department"] == "it-engineering"
        assert result["classification"]["confidence"] >= 0.9

    @pytest.mark.asyncio
    async def test_finance_classification(self, classification_workflow):
        """Test Finance/Accounting department classification"""
        classification_workflow.classifier.classify_and_extract = AsyncMock(return_value={
            "department": "finance-accounting",
            "confidence": 0.88,
            "reasoning": "Content covers financial planning and analysis",
            "suggested_tags": ["fpa", "budgeting", "forecasting"],
            "structure": None
        })

        result = await classification_workflow.classify_and_store(
            b2_file_id="finance_doc_456",
            filename="fpa_guide.pdf",
            content_preview="Financial Planning & Analysis overview...",
            store_course_data=False
        )

        assert result["classification"]["department"] == "finance-accounting"
        assert "fpa" in result["classification"]["suggested_tags"]


class TestCourseMetadataExtraction:
    """Test course structure metadata extraction"""

    @pytest.mark.asyncio
    async def test_modular_course_extraction(
        self,
        classification_workflow
    ):
        """Test extraction of modular course structure"""
        result = await classification_workflow.classify_and_store(
            b2_file_id="course_123",
            filename="grant_cardone_sales.pdf",
            content_preview="Module 1: Prospecting...",
            store_course_data=True
        )

        # Verify course structure
        structure = result["course_data"]
        assert structure["has_modules"] is True
        assert structure["total_modules"] == 10
        assert structure["current_module"] == 1
        assert structure["module_name"] == "Prospecting Fundamentals"

    @pytest.mark.asyncio
    async def test_simple_course_extraction(
        self,
        classification_workflow
    ):
        """Test extraction of simple (non-modular) course"""
        # Mock classifier for simple course
        classification_workflow.classifier.classify_and_extract = AsyncMock(return_value={
            "department": "consulting",
            "confidence": 0.90,
            "reasoning": "McKinsey strategy frameworks",
            "suggested_tags": ["strategy", "frameworks"],
            "structure": {
                "instructor": None,
                "company": "McKinsey",
                "course_title": "Strategy Frameworks",
                "has_modules": False,
                "total_modules": None,
                "current_module": None,
                "module_name": None,
                "has_lessons": False,
                "current_lesson": None,
                "lesson_name": None,
                "total_lessons_in_module": None
            },
            "suggested_filename": "McKinsey-Strategy_Frameworks.pdf"
        })

        result = await classification_workflow.classify_and_store(
            b2_file_id="simple_course_456",
            filename="mckinsey.pdf",
            content_preview="McKinsey Strategy Frameworks...",
            store_course_data=True
        )

        structure = result["course_data"]
        assert structure["has_modules"] is False
        assert structure["company"] == "McKinsey"
        assert structure["instructor"] is None
