"""Comprehensive tests for VisionService (local Qwen-VL + opt-in cloud fallback)."""

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
def service(mock_primary, mock_file_handler):
    """Service with local-only vision (no cloud fallback)."""
    with patch("app.services.vision_service.get_llm_client") as mock_factory, \
         patch("app.services.vision_service.get_chat_file_handler", return_value=mock_file_handler), \
         patch.dict("os.environ", {"VISION_CLOUD_FALLBACK": "false"}):

        def factory_side_effect(provider):
            if provider == "ollama_vlm":
                return mock_primary
            raise ValueError(f"Unexpected provider: {provider}")

        mock_factory.side_effect = factory_side_effect
        svc = VisionService(max_retries=2)
    return svc


@pytest.fixture
def service_with_fallback(mock_primary, mock_fallback, mock_file_handler):
    """Service with cloud fallback enabled."""
    with patch("app.services.vision_service.get_llm_client") as mock_factory, \
         patch("app.services.vision_service.get_chat_file_handler", return_value=mock_file_handler), \
         patch.dict("os.environ", {"VISION_CLOUD_FALLBACK": "true"}):

        def factory_side_effect(provider):
            if provider == "ollama_vlm":
                return mock_primary
            elif provider == "together":
                return mock_fallback
            raise ValueError(f"Unexpected provider: {provider}")

        mock_factory.side_effect = factory_side_effect
        svc = VisionService(max_retries=2)
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
        assert result.model_used == "qwen2.5vl:32b-q8_0"
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
            if call_count < 2:
                raise ConnectionError("temp failure")
            return "Recovered"

        mock_primary.generate_with_images.side_effect = fail_then_succeed

        result = await service.analyze_image("img-001")
        assert result.success is True
        assert result.description == "Recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_fail_no_fallback(self, service, mock_primary):
        """Without cloud fallback, all retries exhausted → failure."""
        mock_primary.is_retryable.return_value = True
        mock_primary.generate_with_images.side_effect = ConnectionError("down")

        result = await service.analyze_image("img-001")
        assert result.success is False
        assert "Vision analysis failed" in result.error

    @pytest.mark.asyncio
    async def test_all_retries_fail_then_fallback_succeeds(
        self, service_with_fallback, mock_primary, mock_fallback
    ):
        mock_primary.is_retryable.return_value = True
        mock_primary.generate_with_images.side_effect = ConnectionError("down")
        mock_fallback.generate_with_images.return_value = "Fallback analysis result"

        result = await service_with_fallback.analyze_image("img-001")
        assert result.success is True
        assert result.description == "Fallback analysis result"

    @pytest.mark.asyncio
    async def test_both_primary_and_fallback_fail(
        self, service_with_fallback, mock_primary, mock_fallback
    ):
        mock_primary.is_retryable.return_value = True
        mock_primary.generate_with_images.side_effect = ConnectionError("primary down")
        mock_fallback.generate_with_images.side_effect = RuntimeError("fallback down")

        result = await service_with_fallback.analyze_image("img-001")
        assert result.success is False
        assert "Primary failed" in result.error
        assert "Fallback failed" in result.error

    @pytest.mark.asyncio
    async def test_non_retryable_skips_to_fallback(
        self, service_with_fallback, mock_primary, mock_fallback
    ):
        mock_primary.is_retryable.return_value = False
        mock_primary.generate_with_images.side_effect = ValueError("bad input")

        result = await service_with_fallback.analyze_image("img-001")
        assert result.success is True
        assert result.description == "Fallback analysis result"
        assert mock_primary.generate_with_images.await_count == 1

    @pytest.mark.asyncio
    async def test_fallback_never_called_when_primary_succeeds(
        self, service_with_fallback, mock_fallback
    ):
        result = await service_with_fallback.analyze_image("img-001")
        assert result.success is True
        mock_fallback.generate_with_images.assert_not_awaited()


# ---------------------------------------------------------------------------
# Cloud fallback configuration
# ---------------------------------------------------------------------------

class TestCloudFallbackConfig:

    def test_cloud_fallback_disabled_by_default(self, service):
        assert service.cloud_fallback_enabled is False
        assert service.fallback_client is None

    def test_cloud_fallback_enabled_via_env(self, service_with_fallback):
        assert service_with_fallback.cloud_fallback_enabled is True
        assert service_with_fallback.fallback_client is not None
        assert service_with_fallback.fallback_model == "moonshotai/Kimi-K2.5-Thinking"


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
# analyze_frames
# ---------------------------------------------------------------------------

class TestAnalyzeFrames:

    @pytest.mark.asyncio
    async def test_happy_path(self, service, mock_primary, tmp_path):
        frames = []
        for i in range(5):
            path = tmp_path / f"frame_{i:03d}.jpg"
            path.write_bytes(b"\xff\xd8fake_jpeg")
            frames.append({"path": str(path), "timestamp_seconds": float(i), "frame_number": i})

        results = await service.analyze_frames(frames)
        assert len(results) == 5
        for r in results:
            assert r["success"] is True
            assert r["analysis"] == "Primary analysis result"
            assert r["status"] == "analyzed"

    @pytest.mark.asyncio
    async def test_empty_list(self, service):
        results = await service.analyze_frames([])
        assert results == []

    @pytest.mark.asyncio
    async def test_single_frame(self, service, tmp_path):
        path = tmp_path / "single.jpg"
        path.write_bytes(b"\xff\xd8fake")
        results = await service.analyze_frames(
            [{"path": str(path), "timestamp_seconds": 0.0, "frame_number": 1}]
        )
        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_mixed_success_failure(self, service, tmp_path):
        good_path = tmp_path / "good.jpg"
        good_path.write_bytes(b"\xff\xd8fake")
        frames = [
            {"path": str(good_path), "timestamp_seconds": 0.0, "frame_number": 1},
            {"path": "/nonexistent/bad.jpg", "timestamp_seconds": 1.0, "frame_number": 2},
        ]
        results = await service.analyze_frames(frames)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[1]["status"] == "vision_unavailable"

    @pytest.mark.asyncio
    async def test_with_metadata(self, service, mock_primary, tmp_path):
        path = tmp_path / "frame.jpg"
        path.write_bytes(b"\xff\xd8fake")
        frames = [{"path": str(path), "timestamp_seconds": 5.0, "frame_number": 1}]

        await service.analyze_frames(
            frames, segment_metadata={"title": "Demo Video", "duration": 60}
        )

        call_kwargs = mock_primary.generate_with_images.call_args[1]
        assert "Demo Video" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_with_question(self, service, mock_primary, tmp_path):
        path = tmp_path / "frame.jpg"
        path.write_bytes(b"\xff\xd8fake")
        frames = [{"path": str(path), "timestamp_seconds": 1.0}]

        await service.analyze_frames(frames, question="What color is the car?")

        call_kwargs = mock_primary.generate_with_images.call_args[1]
        assert "What color is the car?" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_large_batch(self, service, tmp_path):
        frames = []
        for i in range(20):
            path = tmp_path / f"frame_{i:03d}.jpg"
            path.write_bytes(b"\xff\xd8fake")
            frames.append({"path": str(path), "timestamp_seconds": float(i)})

        results = await service.analyze_frames(frames)
        assert len(results) == 20
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_timeout_on_frame(self, service, mock_primary, tmp_path):
        path = tmp_path / "frame.jpg"
        path.write_bytes(b"\xff\xd8fake")

        mock_primary.generate_with_images.side_effect = TimeoutError("slow model")
        mock_primary.is_retryable.return_value = False

        results = await service.analyze_frames(
            [{"path": str(path), "timestamp_seconds": 0.0}]
        )
        assert results[0]["success"] is False
        assert "vision_unavailable" == results[0]["status"]


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


# ---------------------------------------------------------------------------
# VisionAnalysisResult default model
# ---------------------------------------------------------------------------

class TestVisionAnalysisResultDefault:

    def test_default_model_is_qwen(self):
        result = VisionAnalysisResult(
            success=True, file_id="test", analysis_type=VisionAnalysisType.GENERAL,
            description="test",
        )
        assert result.model_used == "qwen2.5vl:32b-q8_0"
