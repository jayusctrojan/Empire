"""
Empire v7.3 - Local Whisper STT Service
Uses faster-whisper with distil-large-v3.5 for local speech-to-text.
Background model preload, singleton pattern, dedicated thread executor.
"""

import asyncio
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class WhisperSTTService:
    """Local speech-to-text using faster-whisper distil-large-v3.5."""

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or os.environ.get(
            "WHISPER_MODEL", "distil-large-v3.5"
        )
        self._model = None
        self._ready = threading.Event()
        self._load_error: Optional[Exception] = None
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Start background preload
        preload_thread = threading.Thread(
            target=self._preload_model, daemon=True
        )
        preload_thread.start()

    def _preload_model(self):
        """Load the Whisper model in a background thread."""
        try:
            from faster_whisper import WhisperModel

            logger.info("Loading Whisper model: %s", self._model_name)
            self._model = WhisperModel(
                self._model_name, device="auto", compute_type="float32"
            )
            logger.info("Whisper model loaded successfully")
        except Exception as exc:
            logger.error("Failed to load Whisper model: %s", exc)
            self._load_error = exc
        finally:
            self._ready.set()

    def _transcribe_sync(
        self, audio_path: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Blocking transcription called from the dedicated executor."""
        # Wait for model to be ready
        self._ready.wait()

        if self._load_error is not None:
            raise RuntimeError(
                f"Whisper model failed to load: {self._load_error}"
            )

        segments_iter, info = self._model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
        )

        transcript_parts: List[str] = []
        segments: List[Dict[str, Any]] = []

        for seg in segments_iter:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append({
                        "text": w.word.strip(),
                        "start_time": round(w.start, 3),
                        "end_time": round(w.end, 3),
                    })

            segment_dict = {
                "text": seg.text.strip(),
                "speaker": "speaker_0",  # No diarization — future: pyannote-audio
                "start_time": round(seg.start, 3),
                "end_time": round(seg.end, 3),
                "words": words,
            }
            segments.append(segment_dict)
            transcript_parts.append(seg.text.strip())

        duration = info.duration if hasattr(info, "duration") else 0.0

        return {
            "transcript": " ".join(transcript_parts),
            "segments": segments,
            "speakers": ["speaker_0"],
            "duration_seconds": round(duration, 3),
        }

    async def transcribe(
        self, audio_path: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Async transcription — runs in dedicated single-thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._transcribe_sync, audio_path, language
        )


# Module-level singleton
_service: Optional[WhisperSTTService] = None


def get_whisper_stt_service() -> WhisperSTTService:
    """Get or create the singleton WhisperSTTService."""
    global _service
    if _service is None:
        _service = WhisperSTTService()
    return _service
