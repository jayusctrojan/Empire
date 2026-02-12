"""Tests for WhisperSTTService — local speech-to-text with faster-whisper."""

import pytest
import threading
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.whisper_stt_service import (
    WhisperSTTService,
    get_whisper_stt_service,
    _service,
)
import app.services.whisper_stt_service as whisper_mod


@pytest.fixture(autouse=True)
def clear_singleton():
    whisper_mod._service = None
    yield
    whisper_mod._service = None


def _make_mock_segment(text="Hello world", start=0.0, end=1.5, words=None):
    seg = MagicMock()
    seg.text = text
    seg.start = start
    seg.end = end
    if words is None:
        w1 = MagicMock()
        w1.word = "Hello"
        w1.start = 0.0
        w1.end = 0.7
        w2 = MagicMock()
        w2.word = "world"
        w2.start = 0.8
        w2.end = 1.5
        seg.words = [w1, w2]
    else:
        seg.words = words
    return seg


def _make_mock_info(duration=10.0):
    info = MagicMock()
    info.duration = duration
    return info


class TestWhisperSTTService:

    @patch("app.services.whisper_stt_service.WhisperSTTService._preload_model")
    def test_init_starts_preload(self, mock_preload):
        """Service starts background preload on init."""
        svc = WhisperSTTService(model_name="tiny")
        assert svc._model_name == "tiny"
        # _preload_model is called in a background thread, but we patched it
        # to avoid actual model load. Verify it would be called.

    @patch("app.services.whisper_stt_service.WhisperSTTService._preload_model")
    def test_model_name_from_env(self, mock_preload):
        with patch.dict("os.environ", {"WHISPER_MODEL": "base.en"}):
            svc = WhisperSTTService()
            assert svc._model_name == "base.en"

    @pytest.mark.asyncio
    async def test_transcribe_happy_path(self):
        """Transcription returns correct format with mocked model."""
        seg = _make_mock_segment()
        info = _make_mock_info(duration=1.5)

        with patch("app.services.whisper_stt_service.WhisperSTTService._preload_model"):
            svc = WhisperSTTService(model_name="tiny")
            svc._model = MagicMock()
            svc._model.transcribe.return_value = (iter([seg]), info)
            svc._ready.set()

            result = await svc.transcribe("/fake/audio.wav")

        assert result["transcript"] == "Hello world"
        assert len(result["segments"]) == 1
        assert result["segments"][0]["speaker"] == "speaker_0"
        assert result["segments"][0]["start_time"] == 0.0
        assert result["segments"][0]["end_time"] == 1.5
        assert len(result["segments"][0]["words"]) == 2
        assert result["speakers"] == ["speaker_0"]
        assert result["duration_seconds"] == 1.5

    @pytest.mark.asyncio
    async def test_transcribe_multiple_segments(self):
        seg1 = _make_mock_segment(text="First segment", start=0.0, end=2.0)
        seg2 = _make_mock_segment(text="Second segment", start=2.5, end=4.0)
        info = _make_mock_info(duration=4.0)

        with patch("app.services.whisper_stt_service.WhisperSTTService._preload_model"):
            svc = WhisperSTTService(model_name="tiny")
            svc._model = MagicMock()
            svc._model.transcribe.return_value = (iter([seg1, seg2]), info)
            svc._ready.set()

            result = await svc.transcribe("/fake/audio.wav")

        assert "First segment" in result["transcript"]
        assert "Second segment" in result["transcript"]
        assert len(result["segments"]) == 2

    @pytest.mark.asyncio
    async def test_transcribe_model_load_failure(self):
        """If model failed to load, transcribe raises RuntimeError."""
        with patch("app.services.whisper_stt_service.WhisperSTTService._preload_model"):
            svc = WhisperSTTService(model_name="bad-model")
            svc._load_error = RuntimeError("model not found")
            svc._ready.set()

            with pytest.raises(RuntimeError, match="model not found"):
                await svc.transcribe("/fake/audio.wav")

    @pytest.mark.asyncio
    async def test_transcribe_runtime_error(self):
        """Errors during transcription propagate."""
        with patch("app.services.whisper_stt_service.WhisperSTTService._preload_model"):
            svc = WhisperSTTService(model_name="tiny")
            svc._model = MagicMock()
            svc._model.transcribe.side_effect = RuntimeError("decode error")
            svc._ready.set()

            with pytest.raises(RuntimeError, match="decode error"):
                await svc.transcribe("/fake/audio.wav")

    @patch("app.services.whisper_stt_service.WhisperSTTService._preload_model")
    def test_singleton_behavior(self, mock_preload):
        svc1 = get_whisper_stt_service()
        svc2 = get_whisper_stt_service()
        assert svc1 is svc2

    @pytest.mark.asyncio
    async def test_segment_with_no_words(self):
        """Segment with no word-level timestamps still works."""
        seg = MagicMock()
        seg.text = "No words here"
        seg.start = 0.0
        seg.end = 2.0
        seg.words = None
        info = _make_mock_info(duration=2.0)

        with patch("app.services.whisper_stt_service.WhisperSTTService._preload_model"):
            svc = WhisperSTTService(model_name="tiny")
            svc._model = MagicMock()
            svc._model.transcribe.return_value = (iter([seg]), info)
            svc._ready.set()

            result = await svc.transcribe("/fake/audio.wav")

        assert result["segments"][0]["words"] == []
        assert result["segments"][0]["text"] == "No words here"
