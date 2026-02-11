"""Comprehensive tests for VisionService (Kimi K2.5 primary + Gemini fallback)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.vision_service import (
    VisionService,
    VisionAnalysisType,
    VisionAnalysisResult,
    ANALYSIS_PROMPTS,
)
from app.services.chat_file_handler import (
    ChatFileMetadata,
    ChatFileType,
    ChatFileStatus,
    IMAGE_MIME_TYPES,
)
from app.services.llm_client import _clients


@pytest.fixture(autouse=True)
def clear_llm_singletons():
    _clients.clear()
    yield
    _clients.clear()


@pytest.fixture
def mock_primary():
    client = MagicMock()
    client.generate_with_images = AsyncMock(return_value="Primary analysis result")
    client.is_retryable = MagicMock(return_value=False)
    return client


@pytest.fixture
def mock_fallback():
    client = MagicMock()
    client.generate_with_images = AsyncMock(return_value="Fallback analysis result")
    client.is_retryable = MagicMock(return_value=False)
    return client


@pytest.fixture
def mock_file_handler():
    handler = MagicMock()
    handler.get_file_by_id.return_value = ChatFileMetadata(
        file_id="img-001",
        original_filename="test.jpg",
        stored_filename="test.jpg",
        file_type=ChatFileType.IMAGE,
        mime_type="image/jpeg",
        file_size=1000,
        file_hash="abc",
        session_id="s1",
        status=ChatFileStatus.READY,
    )
    handler.prepare_image_for_vision.return_value = {
        "data": b"\xff\xd8test",
        "mime_type": "image/jpeg",
    }
    return handler


@pytest.fixture
def service(mock_primary, mock_fallback, mock_file_handler):
    with patch("app.services.vision_service.get_llm_client") as mock_factory, \
         patch("app.services.vision_service.get_chat_file_handler", return_value=mock_file_handler):

        def factory_side_effect(provider):
            if provider == "together":
                return mock_primary
            elif provider == "gemini":
                return mock_fallback
            raise ValueError(f"Unknown: {provider}")

        mock_factory.side_effect = factory_side_effect
        svc = VisionService(max_retries=3)
    return svc


# ---------------------------------------------------------------------------
# analyze_image — happy paths per analysis type
# ---------------------------------------------------------------------------

class TestAnalyzeImageHappyPath:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("analysis_type", list(VisionAnalysisType))
    async def test_per_analysis_type(self, service, analysis_type):
        result = await service.analyze_image("img-001", analysis_type=analysis_type)
        assert result.success is True
        assert result.description == "Primary analysis result"
        assert result.model_used == "moonshotai/Kimi-K2.5-Thinking"
        assert result.file_id == "img-001"
        assert result.analysis_type == analysis_type

    @pytest.mark.asyncio
    async def test_document_type_populates_extracted_text(self, service):
        result = await service.analyze_image("img-001", analysis_type=VisionAnalysisType.DOCUMENT)
        assert result.extracted_text == "Primary analysis result"

    @pytest.mark.asyncio
    async def test_code_type_populates_extracted_text(self, service):
        result = await service.analyze_image("img-001", analysis_type=VisionAnalysisType.CODE)
        assert result.extracted_text == "Primary analysis result"

    @pytest.mark.asyncio
    async def test_general_type_no_extracted_text(self, service):
        result = await service.analyze_image("img-001", analysis_type=VisionAnalysisType.GENERAL)
        assert result.extracted_text is None


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

class TestCaching:

    @pytest.mark.asyncio
    async def test_second_call_returns_cached(self, service, mock_primary):
        await service.analyze_image("img-001")
        await service.analyze_image("img-001")
        assert mock_primary.generate_with_images.await_count == 1

    @pytest.mark.asyncio
    async def test_different_analysis_types_not_cached_together(self, service, mock_primary):
        await service.analyze_image("img-001", analysis_type=VisionAnalysisType.GENERAL)
        await service.analyze_image("img-001", analysis_type=VisionAnalysisType.DOCUMENT)
        assert mock_primary.generate_with_images.await_count == 2


# ---------------------------------------------------------------------------
# Retry and fallback
# ---------------------------------------------------------------------------

class TestRetryAndFallback:

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self, service, mock_primary):
        mock_primary.is_retryable.return_value = True
        call_count = 0

        async def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temp failure")
            return "Recovered"

        mock_primary.generate_with_images.side_effect = fail_then_succeed

        result = await service.analyze_image("img-001")
        assert result.success is True
        assert result.description == "Recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_fail_then_fallback_succeeds(self, service, mock_primary, mock_fallback):
        mock_primary.is_retryable.return_value = True
        mock_primary.generate_with_images.side_effect = ConnectionError("down")
        mock_fallback.generate_with_images.return_value = "Fallback analysis result"

        result = await service.analyze_image("img-001")
        assert result.success is True
        assert result.description == "Fallback analysis result"
        assert result.model_used == "gemini-3-flash-preview"

    @pytest.mark.asyncio
    async def test_both_primary_and_fallback_fail(self, service, mock_primary, mock_fallback):
        mock_primary.is_retryable.return_value = True
        mock_primary.generate_with_images.side_effect = ConnectionError("primary down")
        mock_fallback.generate_with_images.side_effect = RuntimeError("fallback down")

        result = await service.analyze_image("img-001")
        assert result.success is False
        assert "Primary failed" in result.error
        assert "Fallback failed" in result.error

    @pytest.mark.asyncio
    async def test_non_retryable_skips_to_fallback(self, service, mock_primary, mock_fallback):
        mock_primary.is_retryable.return_value = False
        mock_primary.generate_with_images.side_effect = ValueError("bad input")

        result = await service.analyze_image("img-001")
        assert result.success is True
        assert result.model_used == "gemini-3-flash-preview"
        assert mock_primary.generate_with_images.await_count == 1

    @pytest.mark.asyncio
    async def test_fallback_never_called_when_primary_succeeds(self, service, mock_fallback):
        result = await service.analyze_image("img-001")
        assert result.success is True
        mock_fallback.generate_with_images.assert_not_awaited()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestErrorCases:

    @pytest.mark.asyncio
    async def test_invalid_file_id(self, service):
        service.file_handler.get_file_by_id.return_value = None
        result = await service.analyze_image("nonexistent")
        assert result.success is False
        assert result.error == "File not found"

    @pytest.mark.asyncio
    async def test_non_image_file(self, service):
        service.file_handler.get_file_by_id.return_value = ChatFileMetadata(
            file_id="doc-001", original_filename="readme.txt",
            stored_filename="readme.txt", file_type=ChatFileType.TEXT,
            mime_type="text/plain", file_size=10, file_hash="x", session_id="s1",
        )
        result = await service.analyze_image("doc-001")
        assert result.success is False
        assert "not an image" in result.error

    @pytest.mark.asyncio
    async def test_unsupported_mime(self, service):
        service.file_handler.get_file_by_id.return_value = ChatFileMetadata(
            file_id="img-002", original_filename="photo.tiff",
            stored_filename="photo.tiff", file_type=ChatFileType.IMAGE,
            mime_type="image/tiff", file_size=100, file_hash="x", session_id="s1",
        )
        result = await service.analyze_image("img-002")
        assert result.success is False
        assert "Unsupported image type" in result.error

    @pytest.mark.asyncio
    async def test_prepare_image_returns_none(self, service):
        service.file_handler.prepare_image_for_vision.return_value = None
        result = await service.analyze_image("img-001")
        assert result.success is False
        assert "Failed to prepare" in result.error


# ---------------------------------------------------------------------------
# analyze_multiple_images
# ---------------------------------------------------------------------------

class TestAnalyzeMultipleImages:

    @pytest.mark.asyncio
    async def test_happy_path(self, service, mock_primary):
        mock_primary.generate_with_images.return_value = "Multi-image analysis"
        result = await service.analyze_multiple_images(
            file_ids=["img-001", "img-002"],
            prompt="Describe these",
        )
        assert result["success"] is True
        assert result["description"] == "Multi-image analysis"

    @pytest.mark.asyncio
    async def test_no_valid_images(self, service):
        service.file_handler.get_file_by_id.return_value = None
        result = await service.analyze_multiple_images(
            file_ids=["nonexistent"],
            prompt="Describe",
        )
        assert result["success"] is False
        assert "No valid images" in result["error"]


# ---------------------------------------------------------------------------
# describe_for_chat, answer_question_about_image
# ---------------------------------------------------------------------------

class TestHelperMethods:

    @pytest.mark.asyncio
    async def test_describe_for_chat(self, service):
        desc = await service.describe_for_chat("img-001")
        assert desc == "Primary analysis result"

    @pytest.mark.asyncio
    async def test_describe_for_chat_with_query(self, service):
        desc = await service.describe_for_chat("img-001", user_query="What color is this?")
        assert desc == "Primary analysis result"

    @pytest.mark.asyncio
    async def test_answer_question_about_image(self, service):
        answer = await service.answer_question_about_image("img-001", "What is this?")
        assert answer == "Primary analysis result"


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------

class TestClearCache:

    @pytest.mark.asyncio
    async def test_clear_all(self, service):
        await service.analyze_image("img-001")
        assert len(service._cache) > 0
        count = service.clear_cache()
        assert count > 0
        assert len(service._cache) == 0

    @pytest.mark.asyncio
    async def test_clear_specific_file(self, service):
        await service.analyze_image("img-001")
        count = service.clear_cache(file_id="img-001")
        assert count == 1
        assert len(service._cache) == 0

    @pytest.mark.asyncio
    async def test_clear_nonexistent_file(self, service):
        await service.analyze_image("img-001")
        count = service.clear_cache(file_id="other-file")
        assert count == 0
        assert len(service._cache) == 1
