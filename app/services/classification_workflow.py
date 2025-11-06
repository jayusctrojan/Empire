"""
Empire v7.3 - Classification Workflow Service
Orchestrates document classification and result storage
"""

import logging
from typing import Dict, Any, Optional
from io import BytesIO

from app.services.course_classifier import CourseClassifier, auto_classify_course
from app.services.supabase_storage import get_supabase_storage
from app.services.b2_storage import get_b2_service

logger = logging.getLogger(__name__)


class ClassificationWorkflow:
    """
    Orchestrates document classification and storage workflow

    Features:
    - Auto-classify documents using Claude Haiku
    - Store classification results in Supabase documents table
    - Store course metadata in courses table (if applicable)
    - Handle errors and retries
    - Provide detailed logging
    """

    def __init__(self):
        self.classifier = CourseClassifier()
        self.storage = get_supabase_storage()
        self.b2_service = get_b2_service()

    async def classify_and_store(
        self,
        b2_file_id: str,
        filename: str,
        content_preview: str,
        store_course_data: bool = True
    ) -> Dict[str, Any]:
        """
        Classify document and store results in Supabase

        Args:
            b2_file_id: B2 file ID (used to link classification results)
            filename: Original filename
            content_preview: Preview of file content (first 3000 chars)
            store_course_data: Whether to store course-specific metadata (default: True)

        Returns:
            {
                "success": True,
                "classification": {
                    "department": "sales-marketing",
                    "confidence": 0.92,
                    "subdepartment": None,
                    "suggested_tags": ["sales", "prospecting"],
                    "reasoning": "..."
                },
                "course_data": {...},  # If store_course_data=True
                "storage": {
                    "classification_stored": True,
                    "course_stored": True  # If applicable
                }
            }
        """
        result = {
            "success": False,
            "classification": None,
            "course_data": None,
            "storage": {
                "classification_stored": False,
                "course_stored": False
            },
            "errors": []
        }

        try:
            # Step 1: Classify document using Claude Haiku
            logger.info(f"Classifying document: {filename} (B2 ID: {b2_file_id})")
            classification_result = await self.classifier.classify_and_extract(
                filename,
                content_preview
            )

            result["classification"] = {
                "department": classification_result.get("department"),
                "confidence": classification_result.get("confidence"),
                "subdepartment": None,  # Can be added later if needed
                "suggested_tags": classification_result.get("suggested_tags", []),
                "reasoning": classification_result.get("reasoning")
            }

            result["course_data"] = classification_result.get("structure")

            # Step 2: Store classification results in documents table
            logger.info(f"Storing classification results for {b2_file_id}")
            classification_stored = await self.storage.store_classification_results(
                b2_file_id=b2_file_id,
                department=result["classification"]["department"],
                confidence=result["classification"]["confidence"],
                subdepartment=result["classification"]["subdepartment"],
                suggested_tags=result["classification"]["suggested_tags"],
                reasoning=result["classification"]["reasoning"]
            )

            result["storage"]["classification_stored"] = classification_stored

            if not classification_stored:
                result["errors"].append("Failed to store classification results in documents table")

            # Step 3: Store course metadata in courses table (if enabled and has structure)
            if store_course_data and result["course_data"]:
                logger.info(f"Storing course metadata for {b2_file_id}")

                # Combine classification and structure data for courses table
                course_data_with_classification = {
                    **result["course_data"],
                    "department": result["classification"]["department"],
                    "confidence": result["classification"]["confidence"]
                }

                course_stored = await self.storage.store_course_metadata(
                    b2_file_id=b2_file_id,
                    course_data=course_data_with_classification
                )

                result["storage"]["course_stored"] = course_stored is not None

                if not result["storage"]["course_stored"]:
                    result["errors"].append("Failed to store course metadata in courses table")

            # Step 4: Determine overall success
            result["success"] = (
                result["classification"] is not None and
                result["storage"]["classification_stored"] and
                (not store_course_data or result["storage"]["course_stored"])
            )

            if result["success"]:
                logger.info(
                    f"Classification workflow completed successfully for {b2_file_id}: "
                    f"{result['classification']['department']} "
                    f"(confidence: {result['classification']['confidence']:.2f})"
                )
            else:
                logger.warning(f"Classification workflow completed with errors for {b2_file_id}: {result['errors']}")

            return result

        except Exception as e:
            logger.error(f"Classification workflow failed for {b2_file_id}: {e}")
            result["errors"].append(str(e))
            return result

    async def classify_from_b2_file(
        self,
        b2_file_id: str,
        preview_bytes: int = 3000,
        store_course_data: bool = True
    ) -> Dict[str, Any]:
        """
        Classify document by downloading from B2 and extracting content preview

        Args:
            b2_file_id: B2 file ID
            preview_bytes: Number of bytes to read for content preview (default: 3000)
            store_course_data: Whether to store course metadata (default: True)

        Returns:
            Classification workflow result
        """
        try:
            # Download file from B2
            logger.info(f"Downloading file from B2: {b2_file_id}")
            file_info = await self.b2_service.get_file_info(b2_file_id)

            if not file_info:
                logger.error(f"File not found in B2: {b2_file_id}")
                return {
                    "success": False,
                    "errors": [f"File not found in B2: {b2_file_id}"]
                }

            filename = file_info.get("file_name", "unknown.pdf")

            # Download file content
            file_data = await self.b2_service.download_file(b2_file_id)

            if not file_data:
                logger.error(f"Failed to download file from B2: {b2_file_id}")
                return {
                    "success": False,
                    "errors": [f"Failed to download file from B2: {b2_file_id}"]
                }

            # Extract preview (first preview_bytes)
            if isinstance(file_data, BytesIO):
                content_bytes = file_data.read(preview_bytes)
            elif isinstance(file_data, bytes):
                content_bytes = file_data[:preview_bytes]
            else:
                content_bytes = bytes(file_data)[:preview_bytes]

            # Convert to string (try UTF-8, fallback to latin-1)
            try:
                content_preview = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                content_preview = content_bytes.decode('latin-1', errors='ignore')

            # Run classification and storage workflow
            return await self.classify_and_store(
                b2_file_id=b2_file_id,
                filename=filename,
                content_preview=content_preview,
                store_course_data=store_course_data
            )

        except Exception as e:
            logger.error(f"Failed to classify from B2 file {b2_file_id}: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }


# Global instance
_classification_workflow = None


def get_classification_workflow() -> ClassificationWorkflow:
    """
    Get singleton instance of ClassificationWorkflow

    Returns:
        ClassificationWorkflow instance
    """
    global _classification_workflow
    if _classification_workflow is None:
        _classification_workflow = ClassificationWorkflow()
    return _classification_workflow


# Standalone function for backward compatibility and Celery tasks
async def auto_classify_and_store(
    b2_file_id: str,
    filename: str,
    content_preview: str,
    store_course_data: bool = True
) -> Dict[str, Any]:
    """
    Auto-classify document and store results (standalone function)

    Args:
        b2_file_id: B2 file ID
        filename: Original filename
        content_preview: Preview of file content
        store_course_data: Whether to store course metadata

    Returns:
        Classification workflow result
    """
    workflow = get_classification_workflow()
    return await workflow.classify_and_store(
        b2_file_id=b2_file_id,
        filename=filename,
        content_preview=content_preview,
        store_course_data=store_course_data
    )
