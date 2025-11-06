"""
Empire v7.3 - Structured Data Extraction Service
Extract course metadata, entities, and key-value pairs using LangExtract API
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re

# LangExtract for structured extraction
try:
    import langextract as lx
    LANGEXTRACT_SUPPORT = True
except ImportError:
    LANGEXTRACT_SUPPORT = False
    logging.warning("langextract not available - install with: pip install langextract")

logger = logging.getLogger(__name__)


# ============================================================================
# SUBTASK 12.1: Extraction Schema and Example Prompts
# ============================================================================

class CourseMetadataSchema:
    """
    Defines the extraction schema for course documents.

    Fields to extract:
    - instructor: Name of the course instructor/teacher
    - company: Organization or company offering the course
    - course_title: Full title of the course
    - module_number: Module/section number (e.g., 1, 2, 3)
    - module_name: Name/title of the module
    - lesson_number: Lesson number within the module
    - lesson_name: Name/title of the lesson
    - date: Date mentioned in the document
    - topic: Main topic or subject area
    - duration: Length of course/lesson (if mentioned)
    """

    # Extraction classes for LangExtract
    EXTRACTION_CLASSES = [
        "instructor",
        "company",
        "course_title",
        "module_number",
        "module_name",
        "lesson_number",
        "lesson_name",
        "date",
        "topic",
        "duration"
    ]

    @staticmethod
    def get_extraction_prompt() -> str:
        """
        Returns the prompt for guiding LangExtract extraction.
        """
        return """
        Extract course and lesson metadata from the document in order of appearance.

        Look for:
        - instructor: The person teaching or presenting the course
        - company: Organization or company name (if mentioned)
        - course_title: The full name of the course or training program
        - module_number: Module or section number (extract just the number)
        - module_name: Name or title of the module/section
        - lesson_number: Lesson number within the module (extract just the number)
        - lesson_name: Name or title of the specific lesson
        - date: Any dates mentioned in the document
        - topic: Main subject or topic area
        - duration: Course or lesson length (if mentioned)

        Be precise and extract exact text from the document with proper source grounding.
        """

    @staticmethod
    def get_extraction_examples() -> List:
        """
        Returns example extractions to guide the model.
        """
        if not LANGEXTRACT_SUPPORT:
            return []

        examples = [
            # Example 1: Sales training document
            lx.data.ExampleData(
                text="""
                10X Sales System by Grant Cardone
                Module 1: Prospecting Fundamentals
                Lesson 1: Cold Calling Basics

                In this lesson, we'll cover the fundamentals of cold calling,
                including how to identify prospects and overcome objections.
                """,
                extractions=[
                    lx.data.Extraction(
                        extraction_class="instructor",
                        extraction_text="Grant Cardone",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="course_title",
                        extraction_text="10X Sales System",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="module_number",
                        extraction_text="1",
                        attributes={"full_text": "Module 1"}
                    ),
                    lx.data.Extraction(
                        extraction_class="module_name",
                        extraction_text="Prospecting Fundamentals",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="lesson_number",
                        extraction_text="1",
                        attributes={"full_text": "Lesson 1"}
                    ),
                    lx.data.Extraction(
                        extraction_class="lesson_name",
                        extraction_text="Cold Calling Basics",
                        attributes={}
                    ),
                ]
            ),

            # Example 2: Business course with company
            lx.data.ExampleData(
                text="""
                Leadership Essentials - Harvard Business School
                Session 2: Team Management Strategies
                Part 3: Conflict Resolution
                Duration: 45 minutes
                """,
                extractions=[
                    lx.data.Extraction(
                        extraction_class="company",
                        extraction_text="Harvard Business School",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="course_title",
                        extraction_text="Leadership Essentials",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="module_number",
                        extraction_text="2",
                        attributes={"full_text": "Session 2"}
                    ),
                    lx.data.Extraction(
                        extraction_class="module_name",
                        extraction_text="Team Management Strategies",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="lesson_number",
                        extraction_text="3",
                        attributes={"full_text": "Part 3"}
                    ),
                    lx.data.Extraction(
                        extraction_class="lesson_name",
                        extraction_text="Conflict Resolution",
                        attributes={}
                    ),
                    lx.data.Extraction(
                        extraction_class="duration",
                        extraction_text="45 minutes",
                        attributes={}
                    ),
                ]
            ),
        ]

        return examples


# ============================================================================
# SUBTASK 12.2: LangExtract API Integration
# ============================================================================

class LangExtractService:
    """
    Service for extracting structured course metadata using LangExtract API.
    """

    def __init__(self, model_id: str = "gemini-2.0-flash-exp"):
        """
        Initialize LangExtract service.

        Args:
            model_id: Model to use for extraction (default: gemini-2.0-flash-exp)
        """
        self.model_id = model_id
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not LANGEXTRACT_SUPPORT:
            logger.warning("LangExtract library not available")
        elif not self.api_key:
            logger.warning("No Google API key found - LangExtract may not work")

    async def extract_course_metadata(
        self,
        document_text: str,
        extraction_passes: int = 1,
        max_workers: int = 1
    ) -> Dict[str, Any]:
        """
        Extract structured course metadata from document text.

        Args:
            document_text: The full text of the document
            extraction_passes: Number of extraction passes for long documents
            max_workers: Number of parallel workers for processing

        Returns:
            Dict containing:
                - success: bool
                - extractions: List of extracted entities with source grounding
                - metadata: Extracted course metadata fields
                - errors: List of error messages
        """
        result = {
            "success": False,
            "extractions": [],
            "metadata": {},
            "errors": []
        }

        if not LANGEXTRACT_SUPPORT:
            result["errors"].append("LangExtract library not available")
            return result

        if not self.api_key:
            result["errors"].append("Google API key not configured")
            return result

        try:
            logger.info(f"Extracting course metadata from {len(document_text)} characters")

            # Get prompt and examples
            prompt = CourseMetadataSchema.get_extraction_prompt()
            examples = CourseMetadataSchema.get_extraction_examples()

            # Run extraction
            extraction_result = lx.extract(
                text_or_documents=document_text,
                prompt_description=prompt,
                examples=examples,
                model_id=self.model_id,
                extraction_passes=extraction_passes,
                max_workers=max_workers,
                api_key=self.api_key
            )

            # Parse extractions
            if hasattr(extraction_result, 'extractions'):
                result["extractions"] = [
                    {
                        "class": ext.extraction_class,
                        "text": ext.extraction_text,
                        "attributes": ext.attributes if hasattr(ext, 'attributes') else {},
                        "start_char": ext.start_char if hasattr(ext, 'start_char') else None,
                        "end_char": ext.end_char if hasattr(ext, 'end_char') else None,
                    }
                    for ext in extraction_result.extractions
                ]

                # Build metadata dict from extractions
                result["metadata"] = self._build_metadata_dict(result["extractions"])

                result["success"] = True
                logger.info(f"Extracted {len(result['extractions'])} entities")
            else:
                result["errors"].append("No extractions returned from LangExtract")

        except Exception as e:
            logger.error(f"LangExtract extraction failed: {e}")
            result["errors"].append(f"Extraction error: {str(e)}")

        return result

    def _build_metadata_dict(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build structured metadata dictionary from extractions.

        Args:
            extractions: List of extraction dicts

        Returns:
            Dict with course metadata fields
        """
        metadata = {}

        for ext in extractions:
            class_name = ext["class"]
            text = ext["text"]

            # Take first occurrence of each field
            if class_name not in metadata:
                metadata[class_name] = text

        return metadata


# ============================================================================
# SUBTASK 12.3: Supabase Storage & Filename Generation
# ============================================================================

class MetadataStorage:
    """
    Handles storage of extracted metadata and filename generation.
    """

    @staticmethod
    def generate_filename(metadata: Dict[str, Any], original_filename: Optional[str] = None) -> str:
        """
        Generate intelligent filename in M01-L02 format from extracted metadata.

        Format: {Instructor}-{CourseTitle}-M{module_number}-{ModuleName}-L{lesson_number}-{LessonName}.{ext}
        Example: Grant_Cardone-10X_Sales_System-M01-Prospecting_Fundamentals-L01-Cold_Calling_Basics.pdf

        Args:
            metadata: Extracted metadata dictionary
            original_filename: Original filename (for extension)

        Returns:
            Generated filename string
        """
        parts = []

        # Instructor name
        if "instructor" in metadata:
            instructor = metadata["instructor"].replace(" ", "_")
            parts.append(instructor)

        # Course title
        if "course_title" in metadata:
            title = metadata["course_title"].replace(" ", "_")
            parts.append(title)

        # Module number and name
        if "module_number" in metadata:
            module_num = str(metadata["module_number"]).zfill(2)  # Pad to 2 digits
            parts.append(f"M{module_num}")

            if "module_name" in metadata:
                module_name = metadata["module_name"].replace(" ", "_")
                parts.append(module_name)

        # Lesson number and name
        if "lesson_number" in metadata:
            lesson_num = str(metadata["lesson_number"]).zfill(2)  # Pad to 2 digits
            parts.append(f"L{lesson_num}")

            if "lesson_name" in metadata:
                lesson_name = metadata["lesson_name"].replace(" ", "_")
                parts.append(lesson_name)

        # Join parts
        filename = "-".join(parts)

        # Clean filename (remove invalid characters)
        filename = re.sub(r'[^\w\-_.]', '', filename)

        # Add extension from original filename
        if original_filename:
            ext = os.path.splitext(original_filename)[1]
            if ext:
                filename += ext

        # Fallback if no metadata available
        if not filename:
            filename = f"document_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            if original_filename:
                ext = os.path.splitext(original_filename)[1]
                if ext:
                    filename += ext

        return filename

    @staticmethod
    async def store_course_metadata(
        metadata: Dict[str, Any],
        document_id: str,
        supabase_client: Any
    ) -> Dict[str, Any]:
        """
        Store extracted course metadata in Supabase courses table.

        Args:
            metadata: Extracted metadata dictionary
            document_id: ID of the source document
            supabase_client: Supabase client instance

        Returns:
            Dict with:
                - success: bool
                - course_id: ID of created/updated course record
                - errors: List of error messages
        """
        result = {
            "success": False,
            "course_id": None,
            "errors": []
        }

        try:
            # Prepare course data
            course_data = {
                "document_id": document_id,
                "instructor": metadata.get("instructor"),
                "company": metadata.get("company"),
                "course_title": metadata.get("course_title"),
                "module_number": int(metadata["module_number"]) if "module_number" in metadata else None,
                "module_name": metadata.get("module_name"),
                "lesson_number": int(metadata["lesson_number"]) if "lesson_number" in metadata else None,
                "lesson_name": metadata.get("lesson_name"),
                "topic": metadata.get("topic"),
                "duration": metadata.get("duration"),
                "created_at": datetime.utcnow().isoformat(),
                "metadata": metadata  # Store full metadata as JSONB
            }

            # Insert into courses table
            response = supabase_client.table("courses").insert(course_data).execute()

            if response.data:
                result["course_id"] = response.data[0].get("id")
                result["success"] = True
                logger.info(f"Stored course metadata with ID: {result['course_id']}")
            else:
                result["errors"].append("No data returned from Supabase insert")

        except Exception as e:
            logger.error(f"Failed to store course metadata: {e}")
            result["errors"].append(f"Storage error: {str(e)}")

        return result

    @staticmethod
    async def store_document_chunks_with_metadata(
        chunks: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        supabase_client: Any
    ) -> Dict[str, Any]:
        """
        Store document chunks with associated metadata in Supabase.

        Args:
            chunks: List of document chunks to store
            metadata: Extracted metadata to associate with chunks
            supabase_client: Supabase client instance

        Returns:
            Dict with:
                - success: bool
                - chunk_ids: List of created chunk IDs
                - errors: List of error messages
        """
        result = {
            "success": False,
            "chunk_ids": [],
            "errors": []
        }

        try:
            # Add metadata to each chunk
            enriched_chunks = []
            for chunk in chunks:
                chunk_data = {
                    **chunk,
                    "instructor": metadata.get("instructor"),
                    "course_title": metadata.get("course_title"),
                    "module_number": metadata.get("module_number"),
                    "lesson_number": metadata.get("lesson_number"),
                    "metadata": metadata
                }
                enriched_chunks.append(chunk_data)

            # Batch insert chunks
            response = supabase_client.table("document_chunks").insert(enriched_chunks).execute()

            if response.data:
                result["chunk_ids"] = [chunk.get("id") for chunk in response.data]
                result["success"] = True
                logger.info(f"Stored {len(result['chunk_ids'])} chunks with metadata")
            else:
                result["errors"].append("No data returned from chunks insert")

        except Exception as e:
            logger.error(f"Failed to store document chunks: {e}")
            result["errors"].append(f"Chunk storage error: {str(e)}")

        return result


# Singleton instance
_langextract_service_instance = None

def get_langextract_service(model_id: str = "gemini-2.0-flash-exp") -> LangExtractService:
    """Get singleton instance of LangExtractService"""
    global _langextract_service_instance
    if _langextract_service_instance is None:
        _langextract_service_instance = LangExtractService(model_id=model_id)
    return _langextract_service_instance
