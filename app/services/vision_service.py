"""
Empire v7.5 - Vision Service (Local Perception Layer)
Image/frame analysis via local Qwen 3.5-35B (Ollama) with opt-in cloud fallback.

Primary: Ollama Qwen 3.5 (local, $0)
Fallback: Fireworks AI Kimi K2.5 (cloud, opt-in via VISION_CLOUD_FALLBACK=true)
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import structlog

from app.services.llm_client import get_llm_client
from app.services.chat_file_handler import (
    ChatFileHandler,
    ChatFileMetadata,
    ChatFileType,
    ChatFileStatus,
    get_chat_file_handler,
    IMAGE_MIME_TYPES,
)

logger = structlog.get_logger(__name__)


class VisionAnalysisType(str, Enum):
    """Types of vision analysis"""
    GENERAL = "general"
    DOCUMENT = "document"
    DIAGRAM = "diagram"
    CODE = "code"
    DETAILED = "detailed"


@dataclass
class VisionAnalysisResult:
    """Result of vision analysis"""
    success: bool
    file_id: str
    analysis_type: VisionAnalysisType
    description: str
    extracted_text: Optional[str] = None
    detected_objects: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[float] = None
    model_used: str = "qwen3.5:35b"
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "file_id": self.file_id,
            "analysis_type": self.analysis_type.value,
            "description": self.description,
            "extracted_text": self.extracted_text,
            "detected_objects": self.detected_objects,
            "confidence_score": self.confidence_score,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# Analysis prompts for different types
ANALYSIS_PROMPTS = {
    VisionAnalysisType.GENERAL: """Analyze this image and provide a clear, detailed description.
Include:
- Main subject or focus of the image
- Key visual elements and their arrangement
- Colors, lighting, and overall mood
- Any text visible in the image
- Context or setting if applicable

Be concise but thorough.""",

    VisionAnalysisType.DOCUMENT: """This image contains a document or text. Please:
1. Extract all visible text accurately
2. Preserve the document structure (headings, paragraphs, lists)
3. Note any formatting like bold, italics, or highlights
4. Identify the document type if apparent
5. Summarize the key content

Format the extracted text clearly.""",

    VisionAnalysisType.DIAGRAM: """Analyze this diagram, chart, or visualization. Please:
1. Identify the type of diagram (flowchart, bar chart, pie chart, etc.)
2. Describe the data or concepts being represented
3. Extract any labels, legends, or annotations
4. Explain the relationships or trends shown
5. Summarize the key insights

Be precise about numerical values if visible.""",

    VisionAnalysisType.CODE: """This image contains code or a screenshot. Please:
1. Identify the programming language if visible
2. Extract the code accurately with proper formatting
3. Explain what the code does
4. Note any visible errors, warnings, or highlights
5. Describe the IDE or environment if recognizable

Preserve indentation and syntax highlighting if mentioned.""",

    VisionAnalysisType.DETAILED: """Provide an extremely detailed analysis of this image. Include:
1. Overall composition and layout
2. Every visible element, object, or text
3. Colors, textures, and visual patterns
4. Spatial relationships between elements
5. Any symbols, logos, or identifiable marks
6. Quality, resolution, and image characteristics
7. Context clues about when/where the image was taken
8. Any notable or unusual aspects

Be as comprehensive as possible.""",
}


class VisionService:
    """
    Vision analysis using local Qwen 3.5-35B (Ollama) with opt-in cloud fallback.

    Primary: Ollama Qwen 3.5 (local, $0, native vision-language model)
    Fallback: Fireworks AI Kimi K2.5 (cloud, opt-in via VISION_CLOUD_FALLBACK=true)

    Features:
    - Multiple analysis types (general, document, diagram, code, detailed)
    - Video frame analysis via analyze_frames()
    - Caching of analysis results
    - Retry with is_retryable() classification
    - Opt-in cloud fallback (default: fully local)
    - Support for multiple images in single request
    - Integration with chat file handler
    """

    VISION_MODEL = "qwen3.5:35b"

    def __init__(
        self,
        max_tokens: int = 4096,
        max_retries: int = 2,
        cache_results: bool = True,
    ):
        self.primary_client = get_llm_client("ollama_vlm")
        self.primary_model = self.VISION_MODEL

        # Opt-in cloud fallback (default OFF)
        self.cloud_fallback_enabled = os.environ.get(
            "VISION_CLOUD_FALLBACK", "false"
        ).lower() == "true"
        self.fallback_client = (
            get_llm_client("fireworks") if self.cloud_fallback_enabled else None
        )
        self.fallback_model = (
            "accounts/fireworks/models/kimi-k2p5" if self.cloud_fallback_enabled else None
        )

        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.cache_results = cache_results
        self.file_handler = get_chat_file_handler()

        # Analysis cache (cache_key -> result)
        self._cache: Dict[str, VisionAnalysisResult] = {}

        logger.info(
            "VisionService initialized",
            primary_model=self.primary_model,
            cloud_fallback=self.cloud_fallback_enabled,
            max_retries=max_retries,
        )

    async def _analyze_vision(
        self,
        images: List[Dict[str, Any]],
        prompt: str,
        system: str = "You are an expert image analyst. Provide accurate, detailed analysis.",
        max_tokens: Optional[int] = None,
    ) -> Tuple[str, str]:
        """Core vision analysis with retry + optional cloud fallback.

        Both analyze_image() and analyze_frames() route through here.

        Returns:
            Tuple of (analysis_text, model_used).
        """
        max_tokens = max_tokens or self.max_tokens
        last_error = None

        # Primary: local Qwen-VL via Ollama
        for attempt in range(1, self.max_retries + 1):
            try:
                text = await self.primary_client.generate_with_images(
                    system=system,
                    prompt=prompt,
                    images=images,
                    max_tokens=max_tokens,
                    model=self.primary_model,
                )
                return text, self.primary_model
            except Exception as e:
                last_error = str(e)
                if self.primary_client.is_retryable(e) and attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                elif not self.primary_client.is_retryable(e):
                    break

        logger.warning("Primary vision analysis exhausted retries", retries=self.max_retries, last_error=last_error)

        # Optional cloud fallback
        if self.cloud_fallback_enabled and self.fallback_client:
            try:
                text = await self.fallback_client.generate_with_images(
                    system=system,
                    prompt=prompt,
                    images=images,
                    max_tokens=max_tokens,
                    model=self.fallback_model,
                )
                return text, self.fallback_model or "cloud_fallback"
            except Exception as fallback_err:
                raise RuntimeError(
                    f"Primary failed: {last_error}; Fallback failed: {fallback_err}"
                ) from fallback_err

        raise RuntimeError(f"Vision analysis failed: {last_error}")

    async def analyze_image(
        self,
        file_id: str,
        analysis_type: VisionAnalysisType = VisionAnalysisType.GENERAL,
        custom_prompt: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> VisionAnalysisResult:
        """Analyze an image using local Qwen-VL with opt-in cloud fallback."""
        start_time = datetime.utcnow()

        # Check cache (skip when custom_prompt is provided)
        cache_key = f"{file_id}_{analysis_type.value}"
        use_cache = self.cache_results and custom_prompt is None
        if use_cache and cache_key in self._cache:
            logger.info("Returning cached analysis", file_id=file_id, analysis_type=analysis_type.value)
            return self._cache[cache_key]

        # Get file metadata
        metadata = self.file_handler.get_file_by_id(file_id)
        if not metadata:
            return VisionAnalysisResult(
                success=False, file_id=file_id, analysis_type=analysis_type,
                description="", error="File not found",
            )

        if metadata.file_type != ChatFileType.IMAGE:
            return VisionAnalysisResult(
                success=False, file_id=file_id, analysis_type=analysis_type,
                description="", error=f"File is not an image: {metadata.file_type.value}",
            )

        if metadata.mime_type not in IMAGE_MIME_TYPES:
            return VisionAnalysisResult(
                success=False, file_id=file_id, analysis_type=analysis_type,
                description="", error=f"Unsupported image type: {metadata.mime_type}",
            )

        # Prepare image (provider-neutral format)
        image_data = self.file_handler.prepare_image_for_vision(file_id)
        if not image_data:
            return VisionAnalysisResult(
                success=False, file_id=file_id, analysis_type=analysis_type,
                description="", error="Failed to prepare image for analysis",
            )

        # Build prompt
        prompt = custom_prompt or ANALYSIS_PROMPTS.get(
            analysis_type, ANALYSIS_PROMPTS[VisionAnalysisType.GENERAL]
        )
        if additional_context:
            prompt = f"{prompt}\n\nAdditional context: {additional_context}"

        try:
            description, model_used = await self._analyze_vision(images=[image_data], prompt=prompt)
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = VisionAnalysisResult(
                success=True, file_id=file_id, analysis_type=analysis_type,
                description=description,
                extracted_text=description if analysis_type in (VisionAnalysisType.DOCUMENT, VisionAnalysisType.CODE) else None,
                processing_time_ms=processing_time,
                model_used=model_used,
            )
            metadata.status = ChatFileStatus.ANALYZED
            metadata.analysis_result = result.to_dict()
            if use_cache:
                self._cache[cache_key] = result
            return result

        except RuntimeError as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return VisionAnalysisResult(
                success=False, file_id=file_id, analysis_type=analysis_type,
                description="", processing_time_ms=processing_time,
                error=str(e),
            )

    async def analyze_frames(
        self,
        frames: List[Dict[str, Any]],
        segment_metadata: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None,
        max_concurrent: int = 1,
    ) -> List[Dict[str, Any]]:
        """Analyze video frames via local Qwen-VL.

        Called by AudioVideoProcessor. Returns per-frame results.

        Args:
            frames: List of frame dicts with path, timestamp_seconds, frame_number.
            segment_metadata: Optional video context to include in prompt.
            question: Custom analysis question.
            max_concurrent: Concurrent analyses (default 1 for local model).
        """
        if not frames:
            return []

        prompt = question or (
            "Describe what you see in this video frame. Include details about "
            "people, objects, actions, text, and the overall scene. Be concise."
        )
        if segment_metadata:
            prompt += f"\n\nVideo context: {segment_metadata}"

        semaphore = asyncio.Semaphore(max_concurrent)

        def _read_file(path: str) -> bytes:
            with open(path, "rb") as f:
                return f.read()

        async def analyze_single(frame: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    image_bytes = await asyncio.to_thread(_read_file, frame["path"])
                    import mimetypes
                    ext = Path(frame["path"]).suffix.lower()
                    mime = mimetypes.types_map.get(ext, "image/jpeg")

                    analysis, _ = await self._analyze_vision(
                        images=[{"data": image_bytes, "mime_type": mime}],
                        prompt=prompt,
                        max_tokens=300,
                    )
                    return {
                        "success": True,
                        "timestamp_seconds": frame["timestamp_seconds"],
                        "frame_number": frame.get("frame_number"),
                        "analysis": analysis,
                        "status": "analyzed",
                    }
                except Exception as e:
                    logger.warning(
                        "Frame analysis failed",
                        timestamp=frame["timestamp_seconds"],
                        error=str(e),
                    )
                    return {
                        "success": False,
                        "timestamp_seconds": frame["timestamp_seconds"],
                        "frame_number": frame.get("frame_number"),
                        "analysis": "",
                        "status": "vision_unavailable",
                        "error": str(e),
                    }

        tasks = [analyze_single(frame) for frame in frames]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def analyze_multiple_images(
        self,
        file_ids: List[str],
        prompt: str,
        compare: bool = False,
    ) -> Dict[str, Any]:
        """Analyze multiple images together via primary client."""
        start_time = datetime.utcnow()

        images = []
        valid_file_ids = []
        for file_id in file_ids:
            metadata = self.file_handler.get_file_by_id(file_id)
            if not metadata or metadata.file_type != ChatFileType.IMAGE:
                continue
            image_data = self.file_handler.prepare_image_for_vision(file_id)
            if image_data:
                images.append(image_data)
                valid_file_ids.append(file_id)

        if not images:
            return {"success": False, "error": "No valid images found", "file_ids": file_ids}

        if compare:
            full_prompt = f"I'm sharing {len(images)} images. Please compare them and: {prompt}"
        else:
            full_prompt = f"I'm sharing {len(images)} images. Please analyze them: {prompt}"

        try:
            description, model_used = await self._analyze_vision(images=images, prompt=full_prompt)
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return {
                "success": True,
                "file_ids": valid_file_ids,
                "description": description,
                "image_count": len(valid_file_ids),
                "processing_time_ms": processing_time,
                "model_used": model_used,
            }

        except Exception as e:
            logger.error("Multi-image analysis failed", file_ids=file_ids, error=str(e))
            return {"success": False, "file_ids": file_ids, "error": str(e)}

    async def describe_for_chat(
        self, file_id: str, user_query: Optional[str] = None,
    ) -> str:
        """Get a concise description suitable for chat context."""
        prompt = (
            "Provide a concise but informative description of this image suitable for "
            "chat context. Be brief (2-3 sentences) but capture the essential information."
        )
        if user_query:
            prompt = (
                f"User is asking about this image: '{user_query}'\n\n{prompt}\n\n"
                "Also address the user's question if relevant."
            )

        result = await self.analyze_image(
            file_id=file_id,
            analysis_type=VisionAnalysisType.GENERAL,
            custom_prompt=prompt,
        )
        return result.description if result.success else f"[Unable to analyze image: {result.error}]"

    async def extract_text_from_image(self, file_id: str) -> Optional[str]:
        """Extract text from an image (OCR-style)."""
        result = await self.analyze_image(file_id=file_id, analysis_type=VisionAnalysisType.DOCUMENT)
        return result.description if result.success else None

    async def answer_question_about_image(self, file_id: str, question: str) -> str:
        """Answer a specific question about an image."""
        custom_prompt = (
            f"Please answer this question about the image:\n\n"
            f"Question: {question}\n\n"
            "Provide a direct, helpful answer based on what you can see in the image. "
            "If the question cannot be answered from the image, explain why."
        )
        result = await self.analyze_image(
            file_id=file_id,
            analysis_type=VisionAnalysisType.GENERAL,
            custom_prompt=custom_prompt,
        )
        return result.description if result.success else f"I couldn't analyze the image: {result.error}"

    def clear_cache(self, file_id: Optional[str] = None) -> int:
        """Clear analysis cache."""
        if file_id:
            keys_to_delete = [k for k in self._cache if k.startswith(file_id)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
        else:
            count = len(self._cache)
            self._cache.clear()
            return count


# Global singleton instance
_vision_service: Optional[VisionService] = None


def get_vision_service() -> VisionService:
    """Get singleton instance of VisionService."""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
