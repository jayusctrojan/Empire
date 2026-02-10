"""
Empire v7.3 - Claude Vision Service
Integrates Claude Vision API for image analysis in chat

Task 21: Enable File and Image Upload in Chat
Subtask 21.2: Integrate Claude Vision API for Image Analysis
"""

import os
import base64
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import structlog
from anthropic import AsyncAnthropic

from app.services.chat_file_handler import (
    ChatFileHandler,
    ChatFileMetadata,
    ChatFileType,
    ChatFileStatus,
    get_chat_file_handler,
    IMAGE_MIME_TYPES
)

logger = structlog.get_logger(__name__)


class VisionAnalysisType(str, Enum):
    """Types of vision analysis"""
    GENERAL = "general"  # General description
    DOCUMENT = "document"  # Document/text extraction
    DIAGRAM = "diagram"  # Diagram/chart analysis
    CODE = "code"  # Code/screenshot analysis
    DETAILED = "detailed"  # Highly detailed analysis


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
    model_used: str = "claude-sonnet-4-5-20250929"
    error: Optional[str] = None
    timestamp: datetime = None

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
            "timestamp": self.timestamp.isoformat()
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

Be as comprehensive as possible."""
}


class VisionService:
    """
    Claude Vision API integration for image analysis in chat

    Features:
    - Multiple analysis types (general, document, diagram, code, detailed)
    - Caching of analysis results
    - Rate limiting and retries
    - Support for multiple images in single request
    - Integration with chat file handler
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        max_retries: int = 3,
        cache_results: bool = True
    ):
        """
        Initialize Vision Service

        Args:
            model: Claude model to use for vision
            max_tokens: Maximum tokens in response
            max_retries: Maximum retry attempts
            cache_results: Whether to cache analysis results
        """
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.cache_results = cache_results
        self.file_handler = get_chat_file_handler()

        # Analysis cache (file_id -> result)
        self._cache: Dict[str, VisionAnalysisResult] = {}

        logger.info(
            "VisionService initialized",
            model=model,
            max_tokens=max_tokens,
            max_retries=max_retries
        )

    async def analyze_image(
        self,
        file_id: str,
        analysis_type: VisionAnalysisType = VisionAnalysisType.GENERAL,
        custom_prompt: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> VisionAnalysisResult:
        """
        Analyze an image using Claude Vision API

        Args:
            file_id: ID of the uploaded file
            analysis_type: Type of analysis to perform
            custom_prompt: Custom prompt to use instead of default
            additional_context: Additional context to include

        Returns:
            VisionAnalysisResult with analysis details
        """
        start_time = datetime.utcnow()

        # Check cache first
        cache_key = f"{file_id}_{analysis_type.value}"
        if self.cache_results and cache_key in self._cache:
            logger.info("Returning cached analysis", file_id=file_id, analysis_type=analysis_type.value)
            return self._cache[cache_key]

        # Get file metadata
        metadata = self.file_handler.get_file_by_id(file_id)
        if not metadata:
            return VisionAnalysisResult(
                success=False,
                file_id=file_id,
                analysis_type=analysis_type,
                description="",
                error="File not found"
            )

        # Validate file type
        if metadata.file_type != ChatFileType.IMAGE:
            return VisionAnalysisResult(
                success=False,
                file_id=file_id,
                analysis_type=analysis_type,
                description="",
                error=f"File is not an image: {metadata.file_type.value}"
            )

        if metadata.mime_type not in IMAGE_MIME_TYPES:
            return VisionAnalysisResult(
                success=False,
                file_id=file_id,
                analysis_type=analysis_type,
                description="",
                error=f"Unsupported image type: {metadata.mime_type}"
            )

        # Prepare image for API
        image_data = self.file_handler.prepare_for_claude_vision(file_id)
        if not image_data:
            return VisionAnalysisResult(
                success=False,
                file_id=file_id,
                analysis_type=analysis_type,
                description="",
                error="Failed to prepare image for analysis"
            )

        # Build prompt
        prompt = custom_prompt or ANALYSIS_PROMPTS.get(analysis_type, ANALYSIS_PROMPTS[VisionAnalysisType.GENERAL])
        if additional_context:
            prompt = f"{prompt}\n\nAdditional context: {additional_context}"

        # Make API call with retries
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "Analyzing image",
                    file_id=file_id,
                    analysis_type=analysis_type.value,
                    attempt=attempt
                )

                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                image_data,
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                )

                # Extract response text
                description = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        description += block.text

                # Calculate processing time
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                # Create result
                result = VisionAnalysisResult(
                    success=True,
                    file_id=file_id,
                    analysis_type=analysis_type,
                    description=description,
                    extracted_text=description if analysis_type in (VisionAnalysisType.DOCUMENT, VisionAnalysisType.CODE) else None,
                    processing_time_ms=processing_time,
                    model_used=self.model
                )

                # Update file metadata with analysis
                metadata.status = ChatFileStatus.ANALYZED
                metadata.analysis_result = result.to_dict()

                # Cache result
                if self.cache_results:
                    self._cache[cache_key] = result

                logger.info(
                    "Image analysis completed",
                    file_id=file_id,
                    analysis_type=analysis_type.value,
                    processing_time_ms=processing_time
                )

                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Image analysis attempt failed",
                    file_id=file_id,
                    attempt=attempt,
                    error=str(e)
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed
        return VisionAnalysisResult(
            success=False,
            file_id=file_id,
            analysis_type=analysis_type,
            description="",
            error=f"Analysis failed after {self.max_retries} attempts: {last_error}"
        )

    async def analyze_multiple_images(
        self,
        file_ids: List[str],
        prompt: str,
        compare: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze multiple images together

        Args:
            file_ids: List of file IDs to analyze
            prompt: Analysis prompt
            compare: Whether to compare images

        Returns:
            Combined analysis result
        """
        start_time = datetime.utcnow()

        # Prepare all images
        image_contents = []
        valid_file_ids = []

        for file_id in file_ids:
            metadata = self.file_handler.get_file_by_id(file_id)
            if not metadata or metadata.file_type != ChatFileType.IMAGE:
                continue

            image_data = self.file_handler.prepare_for_claude_vision(file_id)
            if image_data:
                image_contents.append(image_data)
                valid_file_ids.append(file_id)

        if not image_contents:
            return {
                "success": False,
                "error": "No valid images found",
                "file_ids": file_ids
            }

        # Build prompt for multiple images
        if compare:
            full_prompt = f"I'm sharing {len(image_contents)} images. Please compare them and: {prompt}"
        else:
            full_prompt = f"I'm sharing {len(image_contents)} images. Please analyze them: {prompt}"

        # Build content list
        content = image_contents + [{"type": "text", "text": full_prompt}]

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": content}]
            )

            description = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    description += block.text

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                "success": True,
                "file_ids": valid_file_ids,
                "description": description,
                "image_count": len(valid_file_ids),
                "processing_time_ms": processing_time,
                "model_used": self.model
            }

        except Exception as e:
            logger.error(
                "Multi-image analysis failed",
                file_ids=file_ids,
                error=str(e)
            )
            return {
                "success": False,
                "file_ids": file_ids,
                "error": str(e)
            }

    async def describe_for_chat(
        self,
        file_id: str,
        user_query: Optional[str] = None
    ) -> str:
        """
        Get a concise description suitable for chat context

        Args:
            file_id: ID of the uploaded file
            user_query: Optional user query about the image

        Returns:
            Concise description string
        """
        prompt = """Provide a concise but informative description of this image suitable for chat context.
Be brief (2-3 sentences) but capture the essential information."""

        if user_query:
            prompt = f"User is asking about this image: '{user_query}'\n\n{prompt}\n\nAlso address the user's question if relevant."

        result = await self.analyze_image(
            file_id=file_id,
            analysis_type=VisionAnalysisType.GENERAL,
            custom_prompt=prompt
        )

        if result.success:
            return result.description
        else:
            return f"[Unable to analyze image: {result.error}]"

    async def extract_text_from_image(self, file_id: str) -> Optional[str]:
        """
        Extract text from an image (OCR-style)

        Args:
            file_id: ID of the uploaded file

        Returns:
            Extracted text or None
        """
        result = await self.analyze_image(
            file_id=file_id,
            analysis_type=VisionAnalysisType.DOCUMENT
        )

        if result.success:
            return result.description
        return None

    async def answer_question_about_image(
        self,
        file_id: str,
        question: str
    ) -> str:
        """
        Answer a specific question about an image

        Args:
            file_id: ID of the uploaded file
            question: Question to answer

        Returns:
            Answer string
        """
        custom_prompt = f"""Please answer this question about the image:

Question: {question}

Provide a direct, helpful answer based on what you can see in the image.
If the question cannot be answered from the image, explain why."""

        result = await self.analyze_image(
            file_id=file_id,
            analysis_type=VisionAnalysisType.GENERAL,
            custom_prompt=custom_prompt
        )

        if result.success:
            return result.description
        else:
            return f"I couldn't analyze the image: {result.error}"

    def clear_cache(self, file_id: Optional[str] = None) -> int:
        """
        Clear analysis cache

        Args:
            file_id: Specific file to clear, or None for all

        Returns:
            Number of cached items cleared
        """
        if file_id:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(file_id)]
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
    """
    Get singleton instance of VisionService

    Returns:
        VisionService instance
    """
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
