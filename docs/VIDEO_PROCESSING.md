# Video & Audio Processing

## Quick Reference

| What | File |
|------|------|
| API upload endpoint | `app/routes/chat_files.py` — `POST /api/chat/upload` |
| Orchestrator | `app/services/audio_video_processor.py` — `AudioVideoProcessor` |
| Speech-to-text | `app/services/whisper_stt_service.py` — `WhisperSTTService` |
| Frame analysis | `app/services/vision_service.py` — `VisionService` |
| LLM abstraction | `app/services/llm_client.py` — `generate_with_images()` |
| Tests | `tests/test_audio_video_processor.py`, `tests/test_whisper_stt_service.py`, `tests/test_vision_service.py` |

## Pipeline

```
Video upload (POST /api/chat/upload)
    |
    v
AudioVideoProcessor.process_video_complete()
    |
    +---> 1. extract_audio_from_video()    — ffmpeg -> 16kHz mono WAV
    +---> 2. extract_frames_from_video()   — ffmpeg -> 1280px JPEGs at N-sec interval
    +---> 3. transcribe_audio()            — WhisperSTTService (distil-large-v3.5, local)
    +---> 4. analyze_video_frames()        — VisionService (Qwen2.5-VL-32B, Ollama local)
    +---> 5. Build integrated timeline     — merge transcripts + frame analyses by timestamp
```

## Models

| Stage | Model | Where | Cost |
|-------|-------|-------|------|
| Audio transcription | `distil-whisper/distil-large-v3.5` | Local via `faster-whisper` | $0 |
| Frame analysis (primary) | `qwen2.5vl:32b-q8_0` | Local via Ollama | $0 |
| Frame analysis (fallback) | Kimi K2.5 Thinking | Together AI (opt-in: `VISION_CLOUD_FALLBACK=true`) | per-token |

## Environment Variables

```bash
WHISPER_MODEL=distil-large-v3.5          # Whisper model name
OLLAMA_BASE_URL=http://localhost:11434   # Ollama endpoint
VISION_CLOUD_FALLBACK=false              # Enable cloud fallback for vision
TOGETHER_API_KEY=...                     # Only needed if cloud fallback enabled
```

## Key Method Signatures

```python
# Full pipeline — does everything
await processor.process_video_complete(
    video_path="path/to/video.mp4",
    frame_interval=1.0,       # seconds between frames
    max_frames=None,          # cap frame count
    transcribe=True,          # run Whisper
    analyze_frames=True,      # run Qwen-VL
    frame_analysis_prompt=None # custom prompt for frame analysis
)
# Returns: { success, audio_extraction, frame_extraction, transcription, frame_analyses, timeline, errors }

# Individual steps
await processor.extract_audio_from_video(video_path, sample_rate=16000, channels=1)
await processor.extract_frames_from_video(video_path, frame_interval=1.0, max_frames=None, frame_width=1280)
await processor.transcribe_audio(audio_path, language="en")
await processor.analyze_video_frames(frames, analysis_prompt=None)
```

## Dependencies

```
ffmpeg-python>=0.2.0       # audio/video extraction
faster-whisper>=1.0.0      # local Whisper STT
pydub>=0.25.1              # audio processing
mutagen>=1.47.0            # media metadata
opencv-python-headless>=4.9.0
```

Plus system FFmpeg 6.0+ and Ollama with `qwen2.5vl:32b-q8_0` pulled.
