"""
Empire v7.3 - Audio & Video Processing Service
Transcribe audio with local Whisper, analyze video frames with Gemini 3 Flash.
"""

import os
import logging
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio

# ffmpeg for audio/video extraction
try:
    import ffmpeg
    FFMPEG_SUPPORT = True
except ImportError:
    FFMPEG_SUPPORT = False
    logging.warning("ffmpeg-python not available - install with: pip install ffmpeg-python")

from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class AudioVideoProcessor:
    """
    Comprehensive audio/video processor integrating:
    - ffmpeg-python for audio/video extraction and frame extraction
    - Local distil-whisper for transcription (via WhisperSTTService)
    - Gemini 3 Flash for frame analysis
    """

    def __init__(self):
        """Initialize processor with Gemini vision client."""
        self.vision_client = get_llm_client("gemini")

        # Default extraction settings
        self.default_audio_sample_rate = 16000  # 16kHz for Whisper
        self.default_audio_channels = 1  # Mono
        self.default_frame_interval = 1.0  # Extract 1 frame per second

    # ========================
    # SUBTASK 11.1: Extract Audio and Video Frames
    # ========================

    async def extract_audio_from_video(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Dict[str, Any]:
        """
        Extract audio track from video file in Whisper-compatible format (16kHz mono WAV).

        Args:
            video_path: Path to input video file
            output_path: Path for output audio file (default: temp file)
            sample_rate: Audio sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)

        Returns:
            Dict with success, audio_path, duration_seconds, format, sample_rate, channels, errors
        """
        result = {
            "success": False,
            "audio_path": None,
            "duration_seconds": 0.0,
            "format": "wav",
            "sample_rate": sample_rate,
            "channels": channels,
            "errors": [],
        }

        if not FFMPEG_SUPPORT:
            result["errors"].append("ffmpeg-python not available - cannot extract audio")
            return result

        try:
            if output_path is None:
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, "extracted_audio.wav")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            logger.info(f"Extracting audio from {video_path} to {output_path}")

            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec="pcm_s16le",
                ar=sample_rate,
                ac=channels,
                format="wav",
            )
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True, overwrite_output=True)

            probe = ffmpeg.probe(output_path)
            duration = float(probe["format"]["duration"])

            result["success"] = True
            result["audio_path"] = output_path
            result["duration_seconds"] = duration

            logger.info(f"Audio extracted successfully: {duration:.2f}s, {sample_rate}Hz, {channels}ch")

        except ffmpeg.Error as e:
            error_msg = f"ffmpeg error: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(f"Audio extraction failed: {error_msg}")
            result["errors"].append(error_msg)
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            result["errors"].append(f"Audio extraction error: {str(e)}")

        return result

    async def extract_frames_from_video(
        self,
        video_path: str,
        output_dir: Optional[str] = None,
        frame_interval: float = 1.0,
        max_frames: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Extract frames from video at specified intervals.

        Args:
            video_path: Path to input video file
            output_dir: Directory for output frames (default: temp directory)
            frame_interval: Seconds between extracted frames (default: 1.0)
            max_frames: Maximum number of frames to extract (default: unlimited)

        Returns:
            Dict with success, frames list, total_frames, video_duration, errors
        """
        result = {
            "success": False,
            "frames": [],
            "total_frames": 0,
            "video_duration": 0.0,
            "errors": [],
        }

        if not FFMPEG_SUPPORT:
            result["errors"].append("ffmpeg-python not available - cannot extract frames")
            return result

        try:
            if output_dir is None:
                output_dir = tempfile.mkdtemp()

            os.makedirs(output_dir, exist_ok=True)

            probe = ffmpeg.probe(video_path)
            duration = float(probe["format"]["duration"])
            result["video_duration"] = duration

            fps = 1.0 / frame_interval

            logger.info(f"Extracting frames from {video_path} at {frame_interval}s intervals")

            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.filter(stream, "fps", fps=fps)

            if max_frames:
                stream = ffmpeg.filter(stream, "select", f"lt(n,{max_frames})")

            stream = ffmpeg.output(stream, output_pattern, **{"q:v": 2})
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True, overwrite_output=True)

            frame_files = sorted(Path(output_dir).glob("frame_*.jpg"))

            for idx, frame_path in enumerate(frame_files):
                timestamp = idx * frame_interval
                result["frames"].append({
                    "path": str(frame_path),
                    "timestamp_seconds": timestamp,
                    "frame_number": idx + 1,
                })

            result["total_frames"] = len(frame_files)
            result["success"] = True

            logger.info(f"Extracted {result['total_frames']} frames from {duration:.2f}s video")

        except ffmpeg.Error as e:
            error_msg = f"ffmpeg error: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error(f"Frame extraction failed: {error_msg}")
            result["errors"].append(error_msg)
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            result["errors"].append(f"Frame extraction error: {str(e)}")

        return result

    # ========================
    # SUBTASK 11.2: Transcribe with local Whisper
    # ========================

    async def transcribe_audio(
        self,
        audio_path: str,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Transcribe audio using local distil-whisper model.

        Args:
            audio_path: Path to audio file
            language: Language code (default: "en")

        Returns:
            Dict with success, transcript, segments, speakers, duration_seconds, errors
        """
        result = {
            "success": False,
            "transcript": "",
            "segments": [],
            "speakers": [],
            "duration_seconds": 0.0,
            "errors": [],
        }

        try:
            from app.services.whisper_stt_service import get_whisper_stt_service

            stt = get_whisper_stt_service()
            whisper_result = await stt.transcribe(audio_path, language=language)

            result["transcript"] = whisper_result.get("transcript", "")
            result["segments"] = whisper_result.get("segments", [])
            result["speakers"] = whisper_result.get("speakers", [])
            result["duration_seconds"] = whisper_result.get("duration_seconds", 0.0)
            result["success"] = True

            logger.info(
                f"Transcription successful: {len(result['segments'])} segments, "
                f"{len(result['speakers'])} speakers"
            )

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            result["errors"].append(f"Transcription error: {str(e)}")

        return result

    # ========================
    # SUBTASK 11.3: Analyze Frames with Gemini Vision
    # ========================

    async def analyze_frame_with_vision(
        self,
        frame_path: str,
        timestamp_seconds: float,
        analysis_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a video frame using Gemini 3 Flash.

        Args:
            frame_path: Path to frame image
            timestamp_seconds: Timestamp of this frame in the video
            analysis_prompt: Custom analysis prompt

        Returns:
            Dict with success, timestamp_seconds, analysis, errors
        """
        result = {
            "success": False,
            "timestamp_seconds": timestamp_seconds,
            "analysis": "",
            "errors": [],
        }

        try:
            with open(frame_path, "rb") as f:
                image_bytes = f.read()

            ext = Path(frame_path).suffix.lower()
            mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

            if analysis_prompt is None:
                analysis_prompt = (
                    "Describe what you see in this video frame. Include details about "
                    "people, objects, actions, text, and the overall scene."
                )

            logger.info(f"Analyzing frame at {timestamp_seconds:.2f}s with Gemini")

            analysis = await self.vision_client.generate_with_images(
                system="You are a video frame analyst. Be concise and accurate.",
                prompt=analysis_prompt,
                images=[{"data": image_bytes, "mime_type": mime_type}],
                max_tokens=300,
                model="gemini-3-flash-preview",
            )

            result["analysis"] = analysis
            result["success"] = True

            logger.info(f"Frame analysis complete for timestamp {timestamp_seconds:.2f}s")

        except Exception as e:
            logger.error(f"Frame analysis failed: {e}")
            result["errors"].append(f"Gemini Vision error: {str(e)}")

        return result

    async def analyze_all_frames(
        self,
        frames: List[Dict[str, Any]],
        analysis_prompt: Optional[str] = None,
        max_concurrent: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple video frames with Gemini Vision (with concurrency control).

        Args:
            frames: List of frame dicts from extract_frames_from_video()
            analysis_prompt: Custom prompt for all frames
            max_concurrent: Maximum concurrent API calls (default: 3)

        Returns:
            List of analysis results with timestamp and description
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(frame):
            async with semaphore:
                return await self.analyze_frame_with_vision(
                    frame["path"],
                    frame["timestamp_seconds"],
                    analysis_prompt,
                )

        tasks = [analyze_with_semaphore(frame) for frame in frames]
        results = await asyncio.gather(*tasks)
        return results

    # ========================
    # INTEGRATED WORKFLOW
    # ========================

    async def process_video_complete(
        self,
        video_path: str,
        output_dir: Optional[str] = None,
        frame_interval: float = 1.0,
        max_frames: Optional[int] = None,
        transcribe: bool = True,
        analyze_frames: bool = True,
        frame_analysis_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete video processing workflow:
        1. Extract audio and frames
        2. Transcribe audio with local Whisper
        3. Analyze frames with Gemini Vision
        4. Return integrated timeline
        """
        result = {
            "success": False,
            "video_path": video_path,
            "audio_extraction": None,
            "frame_extraction": None,
            "transcription": None,
            "frame_analyses": [],
            "timeline": [],
            "errors": [],
        }

        try:
            if output_dir is None:
                output_dir = tempfile.mkdtemp()
            os.makedirs(output_dir, exist_ok=True)

            # Step 1: Extract audio
            audio_path = os.path.join(output_dir, "audio.wav")
            audio_result = await self.extract_audio_from_video(video_path, audio_path)
            result["audio_extraction"] = audio_result

            if not audio_result["success"]:
                result["errors"].extend(audio_result["errors"])

            # Step 2: Extract frames
            frames_dir = os.path.join(output_dir, "frames")
            frame_result = await self.extract_frames_from_video(
                video_path, frames_dir, frame_interval, max_frames,
            )
            result["frame_extraction"] = frame_result

            if not frame_result["success"]:
                result["errors"].extend(frame_result["errors"])

            # Step 3: Transcribe audio with local Whisper
            if transcribe and audio_result["success"]:
                transcription_result = await self.transcribe_audio(audio_path)
                result["transcription"] = transcription_result

                if not transcription_result["success"]:
                    result["errors"].extend(transcription_result["errors"])

            # Step 4: Analyze frames with Gemini
            if analyze_frames and frame_result["success"] and frame_result["frames"]:
                frame_analyses = await self.analyze_all_frames(
                    frame_result["frames"], frame_analysis_prompt,
                )
                result["frame_analyses"] = frame_analyses

            # Step 5: Build integrated timeline
            timeline = []

            if result["transcription"] and result["transcription"]["success"]:
                for segment in result["transcription"]["segments"]:
                    timeline.append({
                        "type": "transcript",
                        "timestamp": segment["start_time"],
                        "end_time": segment["end_time"],
                        "speaker": segment["speaker"],
                        "text": segment["text"],
                    })

            for frame_analysis in result["frame_analyses"]:
                if frame_analysis["success"]:
                    timeline.append({
                        "type": "frame_analysis",
                        "timestamp": frame_analysis["timestamp_seconds"],
                        "analysis": frame_analysis["analysis"],
                    })

            timeline.sort(key=lambda x: x["timestamp"])
            result["timeline"] = timeline

            result["success"] = (
                (audio_result["success"] or frame_result["success"])
                and len(result["errors"]) == 0
            )

            logger.info(f"Video processing complete: {len(timeline)} timeline events")

        except Exception as e:
            logger.error(f"Complete video processing failed: {e}")
            result["errors"].append(f"Processing error: {str(e)}")

        return result


# Singleton instance
_processor_instance = None


def get_audio_video_processor() -> AudioVideoProcessor:
    """Get singleton instance of AudioVideoProcessor"""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = AudioVideoProcessor()
    return _processor_instance
