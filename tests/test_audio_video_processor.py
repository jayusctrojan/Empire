"""
Empire v7.4 - Audio/Video Processor Tests
Tests for audio/video processing with ffmpeg, local Whisper, and Qwen-VL (via VisionService).

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
def mock_vision_service():
    svc = MagicMock()
    svc.analyze_frames = AsyncMock(return_value=[
        {
            "success": True,
            "timestamp_seconds": 0.0,
            "frame_number": 1,
            "analysis": "Frame analysis result",
            "status": "analyzed",
        }
    ])
    return svc


@pytest.fixture
def processor(mock_vision_service):
    with patch("app.services.vision_service.get_vision_service") as mock_get_vs:
        mock_get_vs.return_value = mock_vision_service
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

    @pytest.mark.asyncio
    async def test_extract_frames_with_custom_width(self, processor, tmp_path):
        """Verify frame_width parameter is passed to ffmpeg scale filter."""
        video_path = str(tmp_path / "test_video.mp4")
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        (frames_dir / "frame_000001.jpg").touch()

        with patch("app.services.audio_video_processor.FFMPEG_SUPPORT", True), \
             patch("app.services.audio_video_processor.ffmpeg", create=True) as mock_ffmpeg:
            mock_ffmpeg.probe.return_value = {"format": {"duration": "10.0"}}
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            await processor.extract_frames_from_video(
                video_path=video_path,
                output_dir=str(frames_dir),
                frame_width=720,
            )

            # Verify scale filter was called (second filter call after fps)
            scale_calls = [
                c for c in mock_ffmpeg.filter.call_args_list
                if c[0][1] == "scale"
            ]
            assert len(scale_calls) == 1
            assert scale_calls[0][1]["w"] == 720


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


class TestFrameAnalysis:
    """Test frame analysis delegation to VisionService"""

    @pytest.mark.asyncio
    async def test_analyze_video_frames_delegates(self, processor, mock_vision_service, tmp_path):
        frames = [
            {"path": str(tmp_path / "f1.jpg"), "timestamp_seconds": 0.0, "frame_number": 1},
            {"path": str(tmp_path / "f2.jpg"), "timestamp_seconds": 1.0, "frame_number": 2},
        ]
        mock_vision_service.analyze_frames.return_value = [
            {"success": True, "timestamp_seconds": 0.0, "analysis": "A", "status": "analyzed"},
            {"success": True, "timestamp_seconds": 1.0, "analysis": "B", "status": "analyzed"},
        ]

        results = await processor.analyze_video_frames(frames)

        assert len(results) == 2
        mock_vision_service.analyze_frames.assert_awaited_once_with(
            frames=frames, question=None,
        )

    @pytest.mark.asyncio
    async def test_analyze_video_frames_custom_prompt(self, processor, mock_vision_service):
        frames = [{"path": "/fake.jpg", "timestamp_seconds": 0.0}]

        await processor.analyze_video_frames(frames, analysis_prompt="Describe the speaker.")

        mock_vision_service.analyze_frames.assert_awaited_once_with(
            frames=frames, question="Describe the speaker.",
        )


class TestCompleteVideoProcessing:
    """Test integrated video processing workflow"""

    @pytest.mark.asyncio
    async def test_process_video_complete_success(self, processor, mock_vision_service, tmp_path):
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

        mock_vision_service.analyze_frames.return_value = [
            {"success": True, "timestamp_seconds": 0.0, "analysis": "Scene 1", "status": "analyzed"},
            {"success": True, "timestamp_seconds": 5.0, "analysis": "Scene 2", "status": "analyzed"},
        ]

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
            mock_vision_service.analyze_frames.assert_awaited_once()


class TestSingletonPattern:
    """Test singleton pattern for AudioVideoProcessor"""

    def test_get_audio_video_processor_singleton(self):
        with patch("app.services.vision_service.get_vision_service") as mock_get_vs:
            mock_get_vs.return_value = MagicMock()
            # Reset singleton
            import app.services.audio_video_processor as avp
            avp._processor_instance = None

            p1 = get_audio_video_processor()
            p2 = get_audio_video_processor()
            assert p1 is p2

            # Clean up
            avp._processor_instance = None
