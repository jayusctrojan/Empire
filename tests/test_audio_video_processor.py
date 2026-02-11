"""
Empire v7.3 - Audio/Video Processor Tests
Tests for audio/video processing with ffmpeg, local Whisper, and Gemini Vision.

NOTE: These are INTEGRATION tests - they require ffmpeg to be installed.
"""

import pytest
import shutil
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from pathlib import Path

from app.services.audio_video_processor import (
    AudioVideoProcessor,
    get_audio_video_processor,
)
from app.services.llm_client import _clients

# Skip all tests if ffmpeg is not installed
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg not installed - skipping audio/video tests",
    ),
]


@pytest.fixture(autouse=True)
def clear_llm_singletons():
    _clients.clear()
    yield
    _clients.clear()


@pytest.fixture
def mock_gemini():
    client = MagicMock()
    client.generate_with_images = AsyncMock(return_value="Frame analysis result")
    client.is_retryable = MagicMock(return_value=False)
    return client


@pytest.fixture
def processor(mock_gemini):
    with patch("app.services.audio_video_processor.get_llm_client") as mock_factory:
        mock_factory.return_value = mock_gemini
        proc = AudioVideoProcessor()
    return proc


class TestAudioExtraction:
    """Test audio extraction from video files"""

    @pytest.mark.asyncio
    async def test_extract_audio_success(self, processor, tmp_path):
        video_path = str(tmp_path / "test_video.mp4")
        output_path = str(tmp_path / "test_audio.wav")

        with patch("app.services.audio_video_processor.FFMPEG_SUPPORT", True), \
             patch("app.services.audio_video_processor.ffmpeg", create=True) as mock_ffmpeg:
            mock_ffmpeg.probe.return_value = {"format": {"duration": "120.5"}}
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.extract_audio_from_video(
                video_path=video_path, output_path=output_path,
            )

            assert result["success"] is True
            assert result["audio_path"] == output_path
            assert result["duration_seconds"] == 120.5
            assert result["format"] == "wav"
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_extract_audio_ffmpeg_error(self, processor, tmp_path):
        video_path = str(tmp_path / "test_video.mp4")

        with patch("app.services.audio_video_processor.FFMPEG_SUPPORT", True), \
             patch("app.services.audio_video_processor.ffmpeg", create=True) as mock_ffmpeg:
            mock_ffmpeg.Error = type("Error", (Exception,), {})
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run.side_effect = Exception("FFmpeg error")

            result = await processor.extract_audio_from_video(video_path=video_path)
            assert result["success"] is False
            assert len(result["errors"]) > 0


class TestFrameExtraction:
    """Test frame extraction from video files"""

    @pytest.mark.asyncio
    async def test_extract_frames_success(self, processor, tmp_path):
        video_path = str(tmp_path / "test_video.mp4")
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()

        # Pre-create frame files so glob finds them
        for i in range(1, 4):
            (frames_dir / f"frame_{i:06d}.jpg").touch()

        with patch("app.services.audio_video_processor.FFMPEG_SUPPORT", True), \
             patch("app.services.audio_video_processor.ffmpeg", create=True) as mock_ffmpeg:
            mock_ffmpeg.probe.return_value = {"format": {"duration": "30.0"}}
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.extract_frames_from_video(
                video_path=video_path,
                output_dir=str(frames_dir),
                frame_interval=10.0,
            )

            assert result["success"] is True
            assert result["total_frames"] == 3
            assert result["video_duration"] == 30.0
            assert len(result["frames"]) == 3


class TestWhisperTranscription:
    """Test local Whisper transcription"""

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, processor):
        mock_whisper_result = {
            "transcript": "Hello world this is a test.",
            "segments": [
                {
                    "text": "Hello world this is a test.",
                    "speaker": "speaker_0",
                    "start_time": 0.0,
                    "end_time": 2.0,
                    "words": [
                        {"text": "Hello", "start_time": 0.0, "end_time": 0.5},
                        {"text": "world", "start_time": 0.6, "end_time": 1.0},
                    ],
                }
            ],
            "speakers": ["speaker_0"],
            "duration_seconds": 2.0,
        }

        with patch(
            "app.services.whisper_stt_service.get_whisper_stt_service"
        ) as mock_get_stt:
            mock_stt = MagicMock()
            mock_stt.transcribe = AsyncMock(return_value=mock_whisper_result)
            mock_get_stt.return_value = mock_stt

            result = await processor.transcribe_audio("/fake/audio.wav")

        assert result["success"] is True
        assert result["transcript"] == "Hello world this is a test."
        assert len(result["segments"]) == 1
        assert result["speakers"] == ["speaker_0"]
        assert result["duration_seconds"] == 2.0

    @pytest.mark.asyncio
    async def test_transcribe_audio_error(self, processor):
        with patch(
            "app.services.whisper_stt_service.get_whisper_stt_service"
        ) as mock_get_stt:
            mock_stt = MagicMock()
            mock_stt.transcribe = AsyncMock(side_effect=RuntimeError("model failed"))
            mock_get_stt.return_value = mock_stt

            result = await processor.transcribe_audio("/fake/audio.wav")

        assert result["success"] is False
        assert "model failed" in result["errors"][0]


class TestGeminiFrameAnalysis:
    """Test Gemini Vision frame analysis"""

    @pytest.mark.asyncio
    async def test_analyze_frame_success(self, processor, mock_gemini, tmp_path):
        frame_path = tmp_path / "frame_001.jpg"
        frame_path.write_bytes(b"\xff\xd8fake_jpeg")

        result = await processor.analyze_frame_with_vision(
            frame_path=str(frame_path), timestamp_seconds=10.5,
        )

        assert result["success"] is True
        assert result["timestamp_seconds"] == 10.5
        assert result["analysis"] == "Frame analysis result"
        assert len(result["errors"]) == 0
        mock_gemini.generate_with_images.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_analyze_frame_custom_prompt(self, processor, mock_gemini, tmp_path):
        frame_path = tmp_path / "frame_001.jpg"
        frame_path.write_bytes(b"\xff\xd8fake_jpeg")

        await processor.analyze_frame_with_vision(
            frame_path=str(frame_path),
            timestamp_seconds=5.0,
            analysis_prompt="Describe the speaker's gestures.",
        )

        call_kwargs = mock_gemini.generate_with_images.call_args[1]
        assert "gestures" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_analyze_frame_file_not_found(self, processor):
        result = await processor.analyze_frame_with_vision(
            frame_path="/nonexistent/frame.jpg", timestamp_seconds=0.0,
        )
        assert result["success"] is False
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_frame_api_error(self, processor, mock_gemini, tmp_path):
        frame_path = tmp_path / "frame_001.jpg"
        frame_path.write_bytes(b"\xff\xd8fake_jpeg")

        mock_gemini.generate_with_images.side_effect = RuntimeError("Gemini error")

        result = await processor.analyze_frame_with_vision(
            frame_path=str(frame_path), timestamp_seconds=1.0,
        )
        assert result["success"] is False
        assert "Gemini Vision error" in result["errors"][0]


class TestBatchFrameAnalysis:
    """Test batch frame analysis with concurrency control"""

    @pytest.mark.asyncio
    async def test_analyze_all_frames_success(self, processor, mock_gemini, tmp_path):
        frames = []
        for i in range(1, 4):
            path = tmp_path / f"frame_{i:03d}.jpg"
            path.write_bytes(b"\xff\xd8fake")
            frames.append({"path": str(path), "timestamp_seconds": float(i)})

        results = await processor.analyze_all_frames(frames=frames, max_concurrent=2)

        assert len(results) == 3
        for r in results:
            assert r["success"] is True

    @pytest.mark.asyncio
    async def test_analyze_all_frames_partial_failure(self, processor, mock_gemini, tmp_path):
        good_path = tmp_path / "frame_001.jpg"
        good_path.write_bytes(b"\xff\xd8fake")

        frames = [
            {"path": str(good_path), "timestamp_seconds": 1.0},
            {"path": "/nonexistent/frame.jpg", "timestamp_seconds": 2.0},
        ]

        results = await processor.analyze_all_frames(frames=frames)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False


class TestCompleteVideoProcessing:
    """Test integrated video processing workflow"""

    @pytest.mark.asyncio
    async def test_process_video_complete_success(self, processor, mock_gemini, tmp_path):
        video_path = str(tmp_path / "test_video.mp4")
        frames_dir = tmp_path / "output" / "frames"
        frames_dir.mkdir(parents=True)
        for i in range(1, 3):
            (frames_dir / f"frame_{i:06d}.jpg").write_bytes(b"\xff\xd8fake")

        mock_whisper_result = {
            "transcript": "This is the transcription.",
            "segments": [{
                "text": "This is the transcription.",
                "start_time": 0.0, "end_time": 2.0,
                "speaker": "speaker_0", "words": [],
            }],
            "speakers": ["speaker_0"],
            "duration_seconds": 2.0,
        }

        with patch("app.services.audio_video_processor.FFMPEG_SUPPORT", True), \
             patch("app.services.audio_video_processor.ffmpeg", create=True) as mock_ffmpeg, \
             patch("app.services.whisper_stt_service.get_whisper_stt_service") as mock_get_stt:

            mock_ffmpeg.probe.return_value = {"format": {"duration": "10.0"}}
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            mock_stt = MagicMock()
            mock_stt.transcribe = AsyncMock(return_value=mock_whisper_result)
            mock_get_stt.return_value = mock_stt

            result = await processor.process_video_complete(
                video_path=video_path,
                output_dir=str(tmp_path / "output"),
                frame_interval=5.0,
                max_frames=2,
                transcribe=True,
                analyze_frames=True,
            )

            assert result["audio_extraction"] is not None
            assert result["frame_extraction"] is not None
            assert result["transcription"] is not None
            assert "timeline" in result


class TestSingletonPattern:
    """Test singleton pattern for AudioVideoProcessor"""

    def test_get_audio_video_processor_singleton(self):
        with patch("app.services.audio_video_processor.get_llm_client") as mock_factory:
            mock_factory.return_value = MagicMock()
            # Reset singleton
            import app.services.audio_video_processor as avp
            avp._processor_instance = None

            p1 = get_audio_video_processor()
            p2 = get_audio_video_processor()
            assert p1 is p2

            # Clean up
            avp._processor_instance = None
