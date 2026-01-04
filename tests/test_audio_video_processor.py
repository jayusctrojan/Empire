"""
Empire v7.3 - Audio/Video Processor Tests
Tests for audio/video processing with ffmpeg, Soniox, and Claude Vision

NOTE: These are INTEGRATION tests - they require ffmpeg to be installed
"""

import pytest
import shutil
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from pathlib import Path
import base64
import json

from app.services.audio_video_processor import (
    AudioVideoProcessor,
    get_audio_video_processor
)

# Skip all tests if ffmpeg is not installed
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg not installed - skipping audio/video tests"
    )
]


class TestAudioExtraction:
    """Test audio extraction from video files"""

    @pytest.mark.asyncio
    async def test_extract_audio_success(self, tmp_path):
        """Test successful audio extraction from video"""
        processor = AudioVideoProcessor()

        video_path = str(tmp_path / "test_video.mp4")
        output_path = str(tmp_path / "test_audio.wav")

        # Mock ffmpeg operations
        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg:
            # Mock probe
            mock_probe = {
                "format": {
                    "duration": "120.5",
                    "format_name": "mp4"
                }
            }
            mock_ffmpeg.probe.return_value = mock_probe

            # Mock run
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.extract_audio_from_video(
                video_path=video_path,
                output_path=output_path,
                sample_rate=16000,
                channels=1
            )

            assert result["success"] is True
            assert result["audio_path"] == output_path
            assert result["duration_seconds"] == 120.5
            assert result["format"] == "wav"
            assert result["sample_rate"] == 16000
            assert result["channels"] == 1
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_extract_audio_default_output(self, tmp_path):
        """Test audio extraction with auto-generated output path"""
        processor = AudioVideoProcessor()

        video_path = str(tmp_path / "test_video.mp4")

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg:
            mock_probe = {"format": {"duration": "60.0", "format_name": "mp4"}}
            mock_ffmpeg.probe.return_value = mock_probe
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.extract_audio_from_video(
                video_path=video_path
            )

            assert result["success"] is True
            assert result["audio_path"].endswith(".wav")
            assert "test_video" in result["audio_path"]

    @pytest.mark.asyncio
    async def test_extract_audio_file_not_found(self):
        """Test audio extraction with non-existent video file"""
        processor = AudioVideoProcessor()

        result = await processor.extract_audio_from_video(
            video_path="/nonexistent/video.mp4"
        )

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Video file not found" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_extract_audio_ffmpeg_error(self, tmp_path):
        """Test audio extraction with ffmpeg error"""
        processor = AudioVideoProcessor()

        video_path = str(tmp_path / "test_video.mp4")

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg:
            mock_ffmpeg.probe.side_effect = Exception("FFmpeg error")

            result = await processor.extract_audio_from_video(
                video_path=video_path
            )

            assert result["success"] is False
            assert len(result["errors"]) > 0


class TestFrameExtraction:
    """Test frame extraction from video files"""

    @pytest.mark.asyncio
    async def test_extract_frames_success(self, tmp_path):
        """Test successful frame extraction"""
        processor = AudioVideoProcessor()

        video_path = str(tmp_path / "test_video.mp4")
        output_dir = str(tmp_path / "frames")

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg, \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=["frame_000001.jpg", "frame_000002.jpg", "frame_000003.jpg"]):

            # Mock probe
            mock_probe = {
                "format": {
                    "duration": "30.0",
                    "format_name": "mp4"
                }
            }
            mock_ffmpeg.probe.return_value = mock_probe

            # Mock ffmpeg operations
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.extract_frames_from_video(
                video_path=video_path,
                output_dir=output_dir,
                frame_interval=10.0,
                max_frames=3
            )

            assert result["success"] is True
            assert result["total_frames"] == 3
            assert result["video_duration"] == 30.0
            assert len(result["frames"]) == 3

            # Check frame structure
            for i, frame in enumerate(result["frames"]):
                assert "frame_path" in frame
                assert "timestamp_seconds" in frame
                assert frame["frame_number"] == i + 1

    @pytest.mark.asyncio
    async def test_extract_frames_max_limit(self, tmp_path):
        """Test frame extraction with max_frames limit"""
        processor = AudioVideoProcessor()

        video_path = str(tmp_path / "test_video.mp4")

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg, \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=[f"frame_{i:06d}.jpg" for i in range(1, 21)]):

            mock_probe = {"format": {"duration": "200.0", "format_name": "mp4"}}
            mock_ffmpeg.probe.return_value = mock_probe
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.extract_frames_from_video(
                video_path=video_path,
                frame_interval=1.0,
                max_frames=10
            )

            assert result["success"] is True
            # Should be limited to 10 frames even though 20 were generated
            assert len(result["frames"]) == 10

    @pytest.mark.asyncio
    async def test_extract_frames_file_not_found(self):
        """Test frame extraction with non-existent video file"""
        processor = AudioVideoProcessor()

        result = await processor.extract_frames_from_video(
            video_path="/nonexistent/video.mp4"
        )

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Video file not found" in result["errors"][0]


class TestSonioxTranscription:
    """Test Soniox audio transcription"""

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, tmp_path):
        """Test successful audio transcription with Soniox"""
        processor = AudioVideoProcessor()
        processor.soniox_api_key = "test_api_key"

        audio_path = str(tmp_path / "test_audio.wav")

        # Create fake audio file
        Path(audio_path).touch()

        # Mock Soniox API response
        mock_response = {
            "transcript": "This is a test transcription of the audio file.",
            "segments": [
                {
                    "text": "This is a test",
                    "start_time": 0.0,
                    "end_time": 1.2,
                    "speaker": "SPEAKER_00",
                    "words": [
                        {"word": "This", "start": 0.0, "end": 0.2},
                        {"word": "is", "start": 0.2, "end": 0.4},
                        {"word": "a", "start": 0.4, "end": 0.5},
                        {"word": "test", "start": 0.5, "end": 1.2}
                    ]
                },
                {
                    "text": "transcription of the audio file.",
                    "start_time": 1.5,
                    "end_time": 3.0,
                    "speaker": "SPEAKER_00",
                    "words": [
                        {"word": "transcription", "start": 1.5, "end": 2.0},
                        {"word": "of", "start": 2.0, "end": 2.1},
                        {"word": "the", "start": 2.1, "end": 2.3},
                        {"word": "audio", "start": 2.3, "end": 2.6},
                        {"word": "file.", "start": 2.6, "end": 3.0}
                    ]
                }
            ],
            "speakers": ["SPEAKER_00"],
            "duration_seconds": 3.0
        }

        with patch('builtins.open', mock_open(read_data=b'fake_audio_data')), \
             patch('httpx.AsyncClient') as mock_client:

            # Mock HTTP response
            mock_http_response = Mock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_response

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_http_response)

            result = await processor.transcribe_audio_with_soniox(
                audio_path=audio_path,
                enable_speaker_diarization=True,
                enable_word_timestamps=True
            )

            assert result["success"] is True
            assert result["transcript"] == "This is a test transcription of the audio file."
            assert len(result["segments"]) == 2
            assert len(result["speakers"]) == 1
            assert result["duration_seconds"] == 3.0
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_api_key(self, tmp_path):
        """Test transcription without Soniox API key"""
        processor = AudioVideoProcessor()
        processor.soniox_api_key = None

        audio_path = str(tmp_path / "test_audio.wav")

        result = await processor.transcribe_audio_with_soniox(
            audio_path=audio_path
        )

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "API key not configured" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_not_found(self):
        """Test transcription with non-existent audio file"""
        processor = AudioVideoProcessor()
        processor.soniox_api_key = "test_api_key"

        result = await processor.transcribe_audio_with_soniox(
            audio_path="/nonexistent/audio.wav"
        )

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Audio file not found" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_transcribe_audio_api_error(self, tmp_path):
        """Test transcription with Soniox API error"""
        processor = AudioVideoProcessor()
        processor.soniox_api_key = "test_api_key"

        audio_path = str(tmp_path / "test_audio.wav")
        Path(audio_path).touch()

        with patch('builtins.open', mock_open(read_data=b'fake_audio_data')), \
             patch('httpx.AsyncClient') as mock_client:

            # Mock HTTP error
            mock_http_response = Mock()
            mock_http_response.status_code = 500
            mock_http_response.text = "Internal Server Error"

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_http_response)

            result = await processor.transcribe_audio_with_soniox(
                audio_path=audio_path
            )

            assert result["success"] is False
            assert len(result["errors"]) > 0


class TestClaudeVisionFrameAnalysis:
    """Test Claude Vision frame analysis"""

    @pytest.mark.asyncio
    async def test_analyze_frame_success(self, tmp_path):
        """Test successful frame analysis with Claude Vision"""
        processor = AudioVideoProcessor()

        # Mock Anthropic client
        mock_client = Mock()
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "This frame shows a presentation slide about sales techniques with bullet points."
        mock_message.content = [mock_content]
        mock_client.messages.create.return_value = mock_message

        processor.anthropic_client = mock_client

        frame_path = str(tmp_path / "frame_001.jpg")
        Path(frame_path).touch()

        with patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            result = await processor.analyze_frame_with_claude_vision(
                frame_path=frame_path,
                timestamp_seconds=10.5
            )

            assert result["success"] is True
            assert result["timestamp_seconds"] == 10.5
            assert "presentation slide" in result["analysis"]
            assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_analyze_frame_custom_prompt(self, tmp_path):
        """Test frame analysis with custom prompt"""
        processor = AudioVideoProcessor()

        mock_client = Mock()
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "The speaker is gesturing towards a whiteboard."
        mock_message.content = [mock_content]
        mock_client.messages.create.return_value = mock_message

        processor.anthropic_client = mock_client

        frame_path = str(tmp_path / "frame_001.jpg")
        Path(frame_path).touch()

        custom_prompt = "Describe the speaker's body language and gestures in detail."

        with patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            result = await processor.analyze_frame_with_claude_vision(
                frame_path=frame_path,
                timestamp_seconds=5.0,
                analysis_prompt=custom_prompt
            )

            assert result["success"] is True
            # Check that custom prompt was used
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args
            messages = call_args[1]["messages"]
            assert any(custom_prompt in str(msg) for msg in messages)

    @pytest.mark.asyncio
    async def test_analyze_frame_no_api_key(self, tmp_path):
        """Test frame analysis without Claude API key"""
        processor = AudioVideoProcessor()
        processor.anthropic_client = None

        frame_path = str(tmp_path / "frame_001.jpg")

        result = await processor.analyze_frame_with_claude_vision(
            frame_path=frame_path,
            timestamp_seconds=0.0
        )

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "not available" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_analyze_frame_file_not_found(self):
        """Test frame analysis with non-existent frame file"""
        processor = AudioVideoProcessor()

        mock_client = Mock()
        processor.anthropic_client = mock_client

        result = await processor.analyze_frame_with_claude_vision(
            frame_path="/nonexistent/frame.jpg",
            timestamp_seconds=0.0
        )

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Frame file not found" in result["errors"][0]


class TestBatchFrameAnalysis:
    """Test batch frame analysis with concurrency control"""

    @pytest.mark.asyncio
    async def test_analyze_all_frames_success(self, tmp_path):
        """Test successful batch frame analysis"""
        processor = AudioVideoProcessor()

        # Create mock frames
        frames = [
            {"frame_path": str(tmp_path / f"frame_{i:03d}.jpg"), "timestamp_seconds": float(i)}
            for i in range(1, 6)
        ]

        # Create frame files
        for frame in frames:
            Path(frame["frame_path"]).touch()

        # Mock Anthropic client
        mock_client = Mock()
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Frame analysis result"
        mock_message.content = [mock_content]
        mock_client.messages.create.return_value = mock_message

        processor.anthropic_client = mock_client

        with patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            results = await processor.analyze_all_frames(
                frames=frames,
                max_concurrent=2
            )

            assert len(results) == 5
            for result in results:
                assert result["success"] is True
                assert "analysis" in result
                assert "timestamp_seconds" in result

    @pytest.mark.asyncio
    async def test_analyze_all_frames_partial_failure(self, tmp_path):
        """Test batch analysis with some failures"""
        processor = AudioVideoProcessor()

        frames = [
            {"frame_path": str(tmp_path / "frame_001.jpg"), "timestamp_seconds": 1.0},
            {"frame_path": "/nonexistent/frame_002.jpg", "timestamp_seconds": 2.0},
            {"frame_path": str(tmp_path / "frame_003.jpg"), "timestamp_seconds": 3.0},
        ]

        # Create only some frame files
        Path(frames[0]["frame_path"]).touch()
        Path(frames[2]["frame_path"]).touch()

        mock_client = Mock()
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Frame analysis"
        mock_message.content = [mock_content]
        mock_client.messages.create.return_value = mock_message

        processor.anthropic_client = mock_client

        with patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            results = await processor.analyze_all_frames(frames=frames)

            assert len(results) == 3
            # First and third should succeed
            assert results[0]["success"] is True
            assert results[2]["success"] is True
            # Second should fail
            assert results[1]["success"] is False


class TestCompleteVideoProcessing:
    """Test integrated video processing workflow"""

    @pytest.mark.asyncio
    async def test_process_video_complete_success(self, tmp_path):
        """Test complete video processing workflow"""
        processor = AudioVideoProcessor()
        processor.soniox_api_key = "test_api_key"

        # Mock Anthropic client
        mock_client = Mock()
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Frame shows presentation content"
        mock_message.content = [mock_content]
        mock_client.messages.create.return_value = mock_message
        processor.anthropic_client = mock_client

        video_path = str(tmp_path / "test_video.mp4")

        # Mock Soniox response
        mock_transcription = {
            "transcript": "This is the transcription.",
            "segments": [
                {
                    "text": "This is the transcription.",
                    "start_time": 0.0,
                    "end_time": 2.0,
                    "speaker": "SPEAKER_00",
                    "words": []
                }
            ],
            "speakers": ["SPEAKER_00"],
            "duration_seconds": 2.0
        }

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg, \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=["frame_000001.jpg", "frame_000002.jpg"]), \
             patch('builtins.open', mock_open(read_data=b'fake_data')), \
             patch('httpx.AsyncClient') as mock_http_client:

            # Mock ffmpeg
            mock_probe = {"format": {"duration": "10.0", "format_name": "mp4"}}
            mock_ffmpeg.probe.return_value = mock_probe
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            # Mock Soniox API
            mock_http_response = Mock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_transcription
            mock_http_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_http_response)

            result = await processor.process_video_complete(
                video_path=video_path,
                frame_interval=5.0,
                max_frames=2,
                transcribe=True,
                analyze_frames=True
            )

            assert result["success"] is True
            assert "audio_extraction" in result
            assert "frame_extraction" in result
            assert "transcription" in result
            assert "frame_analyses" in result
            assert "timeline" in result

            # Check timeline integration
            timeline = result["timeline"]
            assert len(timeline) > 0
            # Should have both transcript and frame analysis entries
            types = {item["type"] for item in timeline}
            assert "transcript" in types
            assert "frame_analysis" in types

    @pytest.mark.asyncio
    async def test_process_video_transcribe_only(self, tmp_path):
        """Test video processing with transcription only"""
        processor = AudioVideoProcessor()
        processor.soniox_api_key = "test_api_key"

        video_path = str(tmp_path / "test_video.mp4")

        mock_transcription = {
            "transcript": "Transcription text",
            "segments": [],
            "speakers": [],
            "duration_seconds": 5.0
        }

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg, \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=b'fake_data')), \
             patch('httpx.AsyncClient') as mock_http_client:

            mock_probe = {"format": {"duration": "5.0", "format_name": "mp4"}}
            mock_ffmpeg.probe.return_value = mock_probe
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            mock_http_response = Mock()
            mock_http_response.status_code = 200
            mock_http_response.json.return_value = mock_transcription
            mock_http_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_http_response)

            result = await processor.process_video_complete(
                video_path=video_path,
                transcribe=True,
                analyze_frames=False
            )

            assert result["success"] is True
            assert "transcription" in result
            assert result["frame_analyses"] == []

    @pytest.mark.asyncio
    async def test_process_video_frames_only(self, tmp_path):
        """Test video processing with frame analysis only"""
        processor = AudioVideoProcessor()

        mock_client = Mock()
        mock_message = Mock()
        mock_content = Mock()
        mock_content.text = "Frame content"
        mock_message.content = [mock_content]
        mock_client.messages.create.return_value = mock_message
        processor.anthropic_client = mock_client

        video_path = str(tmp_path / "test_video.mp4")

        with patch('app.services.audio_video_processor.FFMPEG_SUPPORT', True), \
             patch('app.services.audio_video_processor.ffmpeg', create=True) as mock_ffmpeg, \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=["frame_001.jpg"]), \
             patch('builtins.open', mock_open(read_data=b'fake_data')):

            mock_probe = {"format": {"duration": "3.0", "format_name": "mp4"}}
            mock_ffmpeg.probe.return_value = mock_probe
            mock_ffmpeg.input.return_value = MagicMock()
            mock_ffmpeg.filter.return_value = MagicMock()
            mock_ffmpeg.output.return_value = MagicMock()
            mock_ffmpeg.run = MagicMock()

            result = await processor.process_video_complete(
                video_path=video_path,
                transcribe=False,
                analyze_frames=True
            )

            assert result["success"] is True
            assert len(result["frame_analyses"]) > 0
            assert result["transcription"] == {}


class TestSingletonPattern:
    """Test singleton pattern for AudioVideoProcessor"""

    def test_get_audio_video_processor_singleton(self):
        """Test get_audio_video_processor returns singleton"""
        processor1 = get_audio_video_processor()
        processor2 = get_audio_video_processor()

        assert processor1 is processor2
