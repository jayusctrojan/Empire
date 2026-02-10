"""
Empire v7.3 - Audio & Video Processing Service
Transcribe audio, extract speakers/timestamps using Soniox, and analyze video frames with Claude Vision
"""

import os
import logging
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import timedelta
import asyncio

# ffmpeg for audio/video extraction
try:
    import ffmpeg
    FFMPEG_SUPPORT = True
except ImportError:
    FFMPEG_SUPPORT = False
    logging.warning("ffmpeg-python not available - install with: pip install ffmpeg-python")

# Anthropic for Claude Vision
try:
    import anthropic
    CLAUDE_VISION_SUPPORT = True
except ImportError:
    CLAUDE_VISION_SUPPORT = False
    logging.warning("Anthropic library not available")

# HTTP client for Soniox API
import httpx

logger = logging.getLogger(__name__)


class AudioVideoProcessor:
    """
    Comprehensive audio/video processor integrating:
    - ffmpeg-python for audio/video extraction and frame extraction
    - Soniox API for transcription and speaker diarization
    - Claude Vision API for frame analysis
    """

    def __init__(self):
        """Initialize processor with API credentials"""
        self.soniox_api_key = os.getenv("SONIOX_API_KEY")
        self.soniox_base_url = os.getenv("SONIOX_BASE_URL", "https://api.soniox.com/v1")

        # Initialize Claude client for vision
        self.anthropic_client = None
        if CLAUDE_VISION_SUPPORT:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)

        # Default extraction settings
        self.default_audio_sample_rate = 16000  # 16kHz for Soniox
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
        channels: int = 1
    ) -> Dict[str, Any]:
        """
        Extract audio track from video file in Soniox-compatible format (16kHz mono WAV).

        Args:
            video_path: Path to input video file
            output_path: Path for output audio file (default: temp file)
            sample_rate: Audio sample rate in Hz (default: 16000 for Soniox)
            channels: Number of audio channels (default: 1 for mono)

        Returns:
            Dict with:
                - success: bool
                - audio_path: str (path to extracted audio)
                - duration_seconds: float
                - format: str
                - sample_rate: int
                - channels: int
                - errors: list
        """
        result = {
            "success": False,
            "audio_path": None,
            "duration_seconds": 0.0,
            "format": "wav",
            "sample_rate": sample_rate,
            "channels": channels,
            "errors": []
        }

        if not FFMPEG_SUPPORT:
            result["errors"].append("ffmpeg-python not available - cannot extract audio")
            return result

        try:
            # Create output path if not provided
            if output_path is None:
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, "extracted_audio.wav")

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Extract audio using ffmpeg
            logger.info(f"Extracting audio from {video_path} to {output_path}")

            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='pcm_s16le',  # WAV codec
                ar=sample_rate,  # Sample rate
                ac=channels,  # Number of channels
                format='wav'
            )
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True, overwrite_output=True)

            # Get duration using ffprobe
            probe = ffmpeg.probe(output_path)
            duration = float(probe['format']['duration'])

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
        max_frames: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract frames from video at specified intervals.

        Args:
            video_path: Path to input video file
            output_dir: Directory for output frames (default: temp directory)
            frame_interval: Seconds between extracted frames (default: 1.0)
            max_frames: Maximum number of frames to extract (default: unlimited)

        Returns:
            Dict with:
                - success: bool
                - frames: list of dicts with {path, timestamp_seconds, frame_number}
                - total_frames: int
                - video_duration: float
                - errors: list
        """
        result = {
            "success": False,
            "frames": [],
            "total_frames": 0,
            "video_duration": 0.0,
            "errors": []
        }

        if not FFMPEG_SUPPORT:
            result["errors"].append("ffmpeg-python not available - cannot extract frames")
            return result

        try:
            # Create output directory if not provided
            if output_dir is None:
                output_dir = tempfile.mkdtemp()

            os.makedirs(output_dir, exist_ok=True)

            # Get video duration and frame rate
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])

            result["video_duration"] = duration

            # Calculate frame rate for extraction
            fps = 1.0 / frame_interval

            # Extract frames using ffmpeg
            logger.info(f"Extracting frames from {video_path} at {frame_interval}s intervals")

            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")

            stream = ffmpeg.input(video_path)
            stream = ffmpeg.filter(stream, 'fps', fps=fps)

            if max_frames:
                stream = ffmpeg.filter(stream, 'select', f'lt(n,{max_frames})')

            stream = ffmpeg.output(stream, output_pattern, **{'q:v': 2})  # High quality JPEG
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True, overwrite_output=True)

            # Collect extracted frames
            frame_files = sorted(Path(output_dir).glob("frame_*.jpg"))

            for idx, frame_path in enumerate(frame_files):
                timestamp = idx * frame_interval
                result["frames"].append({
                    "path": str(frame_path),
                    "timestamp_seconds": timestamp,
                    "frame_number": idx + 1
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
    # SUBTASK 11.2: Transcribe with Soniox API
    # ========================

    async def transcribe_audio_with_soniox(
        self,
        audio_path: str,
        enable_speaker_diarization: bool = True,
        enable_word_timestamps: bool = True,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Soniox API with speaker diarization and timestamps.

        Args:
            audio_path: Path to audio file (must be 16kHz mono WAV)
            enable_speaker_diarization: Enable speaker identification (default: True)
            enable_word_timestamps: Include word-level timestamps (default: True)
            language: Language code (default: "en")

        Returns:
            Dict with:
                - success: bool
                - transcript: str (full transcript)
                - segments: list of dicts with {text, speaker, start_time, end_time, words}
                - speakers: list of identified speaker IDs
                - duration_seconds: float
                - errors: list
        """
        result = {
            "success": False,
            "transcript": "",
            "segments": [],
            "speakers": [],
            "duration_seconds": 0.0,
            "errors": []
        }

        if not self.soniox_api_key:
            result["errors"].append("Soniox API key not configured - set SONIOX_API_KEY")
            return result

        try:
            # Read audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            # Prepare Soniox API request
            headers = {
                "Authorization": f"Bearer {self.soniox_api_key}",
                "Content-Type": "application/json"
            }

            # Build request payload
            payload = {
                "audio": base64.b64encode(audio_data).decode('utf-8'),
                "model": "enhanced",
                "language": language,
                "enable_speaker_diarization": enable_speaker_diarization,
                "enable_word_time_offsets": enable_word_timestamps,
                "include_nonfinal": False
            }

            logger.info(f"Sending {len(audio_data)} bytes to Soniox for transcription")

            # Make async HTTP request to Soniox
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.soniox_base_url}/transcribe",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                soniox_result = response.json()

            # Parse Soniox response
            if "words" in soniox_result:
                # Extract full transcript
                result["transcript"] = " ".join([w["text"] for w in soniox_result["words"]])

                # Process segments with speaker information
                current_segment = None
                speaker_ids = set()

                for word in soniox_result["words"]:
                    speaker_id = word.get("speaker", "unknown")
                    speaker_ids.add(speaker_id)

                    # Start new segment on speaker change
                    if current_segment is None or current_segment["speaker"] != speaker_id:
                        if current_segment:
                            result["segments"].append(current_segment)

                        current_segment = {
                            "text": word["text"],
                            "speaker": speaker_id,
                            "start_time": word.get("start_time", 0.0),
                            "end_time": word.get("end_time", 0.0),
                            "words": [{
                                "text": word["text"],
                                "start_time": word.get("start_time", 0.0),
                                "end_time": word.get("end_time", 0.0)
                            }]
                        }
                    else:
                        # Continue current segment
                        current_segment["text"] += " " + word["text"]
                        current_segment["end_time"] = word.get("end_time", 0.0)
                        current_segment["words"].append({
                            "text": word["text"],
                            "start_time": word.get("start_time", 0.0),
                            "end_time": word.get("end_time", 0.0)
                        })

                # Add final segment
                if current_segment:
                    result["segments"].append(current_segment)

                result["speakers"] = sorted(list(speaker_ids))

                # Calculate duration from last word
                if soniox_result["words"]:
                    result["duration_seconds"] = soniox_result["words"][-1].get("end_time", 0.0)

                result["success"] = True
                logger.info(f"Transcription successful: {len(result['segments'])} segments, {len(result['speakers'])} speakers")

            else:
                result["errors"].append("No transcription data in Soniox response")

        except httpx.HTTPStatusError as e:
            error_msg = f"Soniox API error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            result["errors"].append(f"Transcription error: {str(e)}")

        return result

    # ========================
    # SUBTASK 11.3: Analyze Frames with Claude Vision
    # ========================

    async def analyze_frame_with_claude_vision(
        self,
        frame_path: str,
        timestamp_seconds: float,
        analysis_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a video frame using Claude Vision API.

        Args:
            frame_path: Path to frame image
            timestamp_seconds: Timestamp of this frame in the video
            analysis_prompt: Custom analysis prompt (default: general scene description)

        Returns:
            Dict with:
                - success: bool
                - timestamp_seconds: float
                - analysis: str (Claude's description)
                - errors: list
        """
        result = {
            "success": False,
            "timestamp_seconds": timestamp_seconds,
            "analysis": "",
            "errors": []
        }

        if not self.anthropic_client:
            result["errors"].append("Claude Vision not available - check ANTHROPIC_API_KEY")
            return result

        try:
            # Read and encode image
            with open(frame_path, 'rb') as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            # Determine media type from file extension
            ext = Path(frame_path).suffix.lower()
            media_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

            # Default analysis prompt
            if analysis_prompt is None:
                analysis_prompt = "Describe what you see in this video frame. Include details about people, objects, actions, text, and the overall scene."

            # Call Claude Vision API
            logger.info(f"Analyzing frame at {timestamp_seconds:.2f}s with Claude Vision")

            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": analysis_prompt
                        }
                    ]
                }]
            )

            # Extract analysis from response
            result["analysis"] = message.content[0].text
            result["success"] = True

            logger.info(f"Frame analysis complete for timestamp {timestamp_seconds:.2f}s")

        except Exception as e:
            logger.error(f"Frame analysis failed: {e}")
            result["errors"].append(f"Claude Vision error: {str(e)}")

        return result

    async def analyze_all_frames(
        self,
        frames: List[Dict[str, Any]],
        analysis_prompt: Optional[str] = None,
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple video frames with Claude Vision (with concurrency control).

        Args:
            frames: List of frame dicts from extract_frames_from_video()
            analysis_prompt: Custom prompt for all frames
            max_concurrent: Maximum concurrent API calls (default: 3)

        Returns:
            List of analysis results with timestamp and description
        """
        results = []

        # Create tasks for all frames
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(frame):
            async with semaphore:
                return await self.analyze_frame_with_claude_vision(
                    frame["path"],
                    frame["timestamp_seconds"],
                    analysis_prompt
                )

        # Execute with concurrency limit
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
        frame_analysis_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete video processing workflow:
        1. Extract audio and frames
        2. Transcribe audio with Soniox
        3. Analyze frames with Claude Vision
        4. Return integrated timeline

        Args:
            video_path: Path to video file
            output_dir: Output directory for extracted files
            frame_interval: Seconds between frames
            max_frames: Maximum frames to extract
            transcribe: Enable transcription (default: True)
            analyze_frames: Enable frame analysis (default: True)
            frame_analysis_prompt: Custom prompt for frame analysis

        Returns:
            Complete processing result with timeline integration
        """
        result = {
            "success": False,
            "video_path": video_path,
            "audio_extraction": None,
            "frame_extraction": None,
            "transcription": None,
            "frame_analyses": [],
            "timeline": [],
            "errors": []
        }

        try:
            # Create output directory
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
                video_path,
                frames_dir,
                frame_interval,
                max_frames
            )
            result["frame_extraction"] = frame_result

            if not frame_result["success"]:
                result["errors"].extend(frame_result["errors"])

            # Step 3: Transcribe audio if enabled and successful
            if transcribe and audio_result["success"]:
                transcription_result = await self.transcribe_audio_with_soniox(audio_path)
                result["transcription"] = transcription_result

                if not transcription_result["success"]:
                    result["errors"].extend(transcription_result["errors"])

            # Step 4: Analyze frames if enabled and successful
            if analyze_frames and frame_result["success"] and frame_result["frames"]:
                frame_analyses = await self.analyze_all_frames(
                    frame_result["frames"],
                    frame_analysis_prompt
                )
                result["frame_analyses"] = frame_analyses

            # Step 5: Build integrated timeline
            timeline = []

            # Add transcription segments to timeline
            if result["transcription"] and result["transcription"]["success"]:
                for segment in result["transcription"]["segments"]:
                    timeline.append({
                        "type": "transcript",
                        "timestamp": segment["start_time"],
                        "end_time": segment["end_time"],
                        "speaker": segment["speaker"],
                        "text": segment["text"]
                    })

            # Add frame analyses to timeline
            for frame_analysis in result["frame_analyses"]:
                if frame_analysis["success"]:
                    timeline.append({
                        "type": "frame_analysis",
                        "timestamp": frame_analysis["timestamp_seconds"],
                        "analysis": frame_analysis["analysis"]
                    })

            # Sort timeline by timestamp
            timeline.sort(key=lambda x: x["timestamp"])
            result["timeline"] = timeline

            # Mark as successful if we got some results
            result["success"] = (
                (audio_result["success"] or frame_result["success"]) and
                len(result["errors"]) == 0
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
