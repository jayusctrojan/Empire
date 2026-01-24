"""
Empire v7.3 - Supabase Storage Service
Handles document metadata storage in Supabase PostgreSQL database
"""

import os
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from supabase import create_client, Client
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """
    Supabase storage service for document metadata

    Features:
    - Store document metadata in documents table
    - Error handling and logging
    - Schema validation
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase storage service

        Args:
            url: Supabase project URL (defaults to SUPABASE_URL env var)
            key: Supabase service key (defaults to SUPABASE_SERVICE_KEY env var)
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_KEY")

        if not self.url or not self.key:
            logger.warning("Supabase URL or key not configured - storage disabled")
            self.enabled = False
            self.client = None
        else:
            try:
                self.client: Client = create_client(self.url, self.key)
                self.enabled = True
                logger.info(f"Supabase storage initialized: {self.url}")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                self.enabled = False
                self.client = None

    async def store_document_metadata(
        self,
        file_id: str,
        filename: str,
        metadata: Dict[str, Any],
        b2_url: Optional[str] = None,
        folder: Optional[str] = None,
        update_if_duplicate: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Store document metadata in Supabase documents table

        Args:
            file_id: Unique file ID (from B2)
            filename: Original filename
            metadata: Extracted metadata dictionary
            b2_url: URL to file in B2 storage
            folder: Folder path in B2
            update_if_duplicate: If True, update existing record on hash collision instead of failing

        Returns:
            Inserted/updated record or None if failed
        """
        if not self.enabled:
            logger.warning("Supabase storage not enabled - skipping metadata storage")
            return None

        try:
            # Generate a unique document_id (UUID) - B2 file IDs are too long for the 64 char limit
            doc_uuid = str(uuid.uuid4())

            # Prepare document record matching actual documents table schema
            document_data = {
                "document_id": doc_uuid,  # Use UUID for document_id (max 64 chars)
                "filename": filename,
                "file_type": metadata.get("file_extension", "").lstrip("."),  # Remove leading dot
                "file_size_bytes": metadata.get("file_size_bytes"),
                "file_hash": metadata.get("file_hash"),  # If available from metadata
                "b2_file_id": file_id,  # Store full B2 file ID here (max 255 chars)
                "b2_url": b2_url,
                "uploaded_by": "web_ui",  # Could be user_id if available
                "department": folder,  # Use folder as department for now
                "processing_status": "uploaded",
            }

            # Insert into documents table
            result = self.client.table("documents").insert(document_data).execute()

            if result.data:
                logger.info(f"Stored metadata for {filename} (ID: {file_id})")
                return result.data[0]
            else:
                logger.error(f"Failed to store metadata for {filename}: No data returned")
                return None

        except Exception as e:
            # Check if it's a duplicate hash error and update_if_duplicate is enabled
            error_str = str(e)
            if update_if_duplicate and "file_hash" in error_str and "already exists" in error_str:
                try:
                    logger.info(f"Duplicate hash detected for {filename}, updating existing record...")
                    # Find the existing record by hash
                    file_hash = metadata.get("file_hash")
                    existing = self.client.table("documents").select("*").eq("file_hash", file_hash).execute()

                    if existing.data and len(existing.data) > 0:
                        _existing_doc = existing.data[0]  # noqa: F841
                        # Update with new B2 file ID and URL
                        update_data = {
                            "b2_file_id": file_id,
                            "b2_url": b2_url,
                            "filename": filename,  # Update filename in case it changed
                            "updated_at": datetime.utcnow().isoformat()
                        }
                        updated = self.client.table("documents").update(update_data).eq("file_hash", file_hash).execute()

                        if updated.data:
                            logger.info(f"Updated existing metadata for duplicate file {filename}")
                            return updated.data[0]

                except Exception as update_error:
                    logger.error(f"Failed to update duplicate record: {update_error}")

            logger.error(f"Error storing document metadata for {filename}: {e}")
            return None

    async def get_document_by_file_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve document metadata by file ID

        Args:
            file_id: B2 file ID

        Returns:
            Document record or None if not found
        """
        if not self.enabled:
            return None

        try:
            result = self.client.table("documents").select("*").eq("file_id", file_id).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Error retrieving document {file_id}: {e}")
            return None

    async def update_document_status(
        self,
        b2_file_id: str,
        status: str,
        processing_error: Optional[str] = None
    ) -> bool:
        """
        Update document processing status

        Args:
            b2_file_id: B2 file ID (stored in b2_file_id column)
            status: New status (uploaded, processing, processed, failed)
            processing_error: Error message if status is 'failed'

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            update_data = {
                "processing_status": status,
                "updated_at": datetime.utcnow().isoformat()
            }

            # Add processed_at timestamp if status is 'processed'
            if status == "processed":
                update_data["processed_at"] = datetime.utcnow().isoformat()

            # Store processing error if provided
            if processing_error:
                update_data["processing_error"] = processing_error

            result = self.client.table("documents").update(update_data).eq("b2_file_id", b2_file_id).execute()

            if result.data:
                logger.info(f"Updated document {b2_file_id} status to {status}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error updating document status: {e}")
            return False

    async def update_source_metadata(
        self,
        b2_file_id: str,
        source_metadata: Dict[str, Any]
    ) -> bool:
        """
        Update source metadata for a document

        Args:
            b2_file_id: B2 file ID (stored in b2_file_id column)
            source_metadata: Source metadata dict (title, author, publication_date, etc.)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            update_data = {
                "source_metadata": source_metadata,
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.client.table("documents").update(update_data).eq("b2_file_id", b2_file_id).execute()

            if result.data:
                logger.info(f"Updated source metadata for document {b2_file_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error updating source metadata: {e}")
            return False

    async def list_documents(
        self,
        status: Optional[str] = None,
        folder: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        List documents with optional filters

        Args:
            status: Filter by status
            folder: Filter by B2 folder
            limit: Maximum number of results

        Returns:
            List of document records
        """
        if not self.enabled:
            return []

        try:
            query = self.client.table("documents").select("*")

            if status:
                query = query.eq("status", status)

            if folder:
                query = query.eq("b2_folder", folder)

            query = query.limit(limit).order("uploaded_at", desc=True)

            result = query.execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    async def check_duplicate_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Check if a file with the same hash already exists (exact duplicate detection)

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            Existing document record if duplicate found, None otherwise
        """
        if not self.enabled:
            return None

        try:
            result = self.client.table("documents").select("*").eq("file_hash", file_hash).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Duplicate file found with hash: {file_hash}")
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Error checking for duplicate by hash: {e}")
            return None

    async def find_similar_filenames(
        self,
        filename: str,
        similarity_threshold: float = 85.0,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find files with similar filenames using fuzzy matching (near-duplicate detection)

        Args:
            filename: Filename to compare against
            similarity_threshold: Minimum similarity score (0-100) to consider a match (default: 85)
            limit: Maximum number of similar files to return (default: 5)

        Returns:
            List of documents with similar filenames, sorted by similarity score (highest first)
        """
        if not self.enabled:
            return []

        try:
            # Get all documents (or limit to recent ones for performance)
            result = self.client.table("documents").select("document_id, filename, b2_url, created_at").limit(1000).execute()

            if not result.data:
                return []

            # Calculate similarity scores for each filename
            similar_files = []
            for doc in result.data:
                doc_filename = doc.get('filename', '')
                if not doc_filename:
                    continue

                # Use rapidfuzz's ratio for similarity (0-100 scale)
                similarity = fuzz.ratio(filename.lower(), doc_filename.lower())

                if similarity >= similarity_threshold and similarity < 100:  # Exclude exact matches (100)
                    similar_files.append({
                        **doc,
                        'similarity_score': similarity
                    })

            # Sort by similarity score (highest first) and limit results
            similar_files.sort(key=lambda x: x['similarity_score'], reverse=True)
            similar_files = similar_files[:limit]

            if similar_files:
                logger.info(f"Found {len(similar_files)} similar filenames for '{filename}'")

            return similar_files

        except Exception as e:
            logger.error(f"Error finding similar filenames: {e}")
            return []

    async def store_classification_results(
        self,
        b2_file_id: str,
        department: str,
        confidence: float,
        subdepartment: Optional[str] = None,
        suggested_tags: Optional[List[str]] = None,
        reasoning: Optional[str] = None
    ) -> bool:
        """
        Store AI classification results for a document

        Args:
            b2_file_id: B2 file ID (stored in b2_file_id column)
            department: Classified department (e.g., 'sales-marketing')
            confidence: Confidence score (0.0 to 1.0)
            subdepartment: Optional subdepartment
            suggested_tags: Optional list of suggested tags
            reasoning: Optional classification reasoning

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.warning("Supabase storage not enabled - skipping classification storage")
            return False

        try:
            # Prepare update data
            update_data = {
                "department": department,
                "classification_confidence": confidence,
                "updated_at": datetime.utcnow().isoformat()
            }

            # Add optional fields if provided
            if subdepartment:
                update_data["subdepartment"] = subdepartment

            if suggested_tags:
                update_data["tags"] = suggested_tags  # Store as JSONB array

            if reasoning:
                update_data["classification_reasoning"] = reasoning

            # Update documents table
            result = self.client.table("documents").update(update_data).eq("b2_file_id", b2_file_id).execute()

            if result.data:
                logger.info(
                    f"Stored classification for {b2_file_id}: "
                    f"{department} (confidence: {confidence:.2f})"
                )
                return True
            else:
                logger.error(f"Failed to store classification for {b2_file_id}: No data returned")
                return False

        except Exception as e:
            logger.error(f"Error storing classification results for {b2_file_id}: {e}")
            return False

    async def store_course_metadata(
        self,
        b2_file_id: str,
        course_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Store course-specific metadata in courses table

        Args:
            b2_file_id: B2 file ID to link to parent document
            course_data: Dictionary containing course metadata
                {
                    "instructor": "Grant Cardone",
                    "company": None,
                    "course_title": "10X Sales System",
                    "has_modules": True,
                    "total_modules": 10,
                    "current_module": 1,
                    "module_name": "Prospecting Fundamentals",
                    "has_lessons": True,
                    "current_lesson": 1,
                    "lesson_name": "Cold Calling Basics",
                    "total_lessons_in_module": 3,
                    "suggested_filename": "Grant_Cardone-10X_Sales_System-M01-L01.pdf",
                    "department": "sales-marketing",
                    "confidence": 0.92
                }

        Returns:
            Inserted course record or None if failed
        """
        if not self.enabled:
            logger.warning("Supabase storage not enabled - skipping course metadata storage")
            return None

        try:
            # First get the document_id from documents table
            doc_result = self.client.table("documents").select("document_id").eq("b2_file_id", b2_file_id).execute()

            if not doc_result.data or len(doc_result.data) == 0:
                logger.error(f"Cannot store course metadata: document not found for B2 file ID {b2_file_id}")
                return None

            document_id = doc_result.data[0]["document_id"]

            # Prepare course record
            course_record = {
                "course_id": str(uuid.uuid4()),
                "document_id": document_id,
                "instructor": course_data.get("instructor"),
                "company": course_data.get("company"),
                "course_title": course_data.get("course_title"),
                "has_modules": course_data.get("has_modules", False),
                "total_modules": course_data.get("total_modules"),
                "current_module": course_data.get("current_module"),
                "module_name": course_data.get("module_name"),
                "has_lessons": course_data.get("has_lessons", False),
                "current_lesson": course_data.get("current_lesson"),
                "lesson_name": course_data.get("lesson_name"),
                "total_lessons_in_module": course_data.get("total_lessons_in_module"),
                "suggested_filename": course_data.get("suggested_filename"),
                "department": course_data.get("department"),
                "confidence": course_data.get("confidence"),
            }

            # Insert into courses table
            result = self.client.table("courses").insert(course_record).execute()

            if result.data:
                logger.info(f"Stored course metadata for document {document_id}")
                return result.data[0]
            else:
                logger.error("Failed to store course metadata: No data returned")
                return None

        except Exception as e:
            logger.error(f"Error storing course metadata for {b2_file_id}: {e}")
            return None

    async def insert_processing_log(self, log_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Insert a processing log entry

        Args:
            log_data: Processing log data containing error details

        Returns:
            Inserted record or None if failed
        """
        if not self.enabled:
            logger.warning("Supabase storage not enabled - skipping log insertion")
            return None

        try:
            # Insert into processing_logs table
            result = self.client.table("processing_logs").insert(log_data).execute()

            if result.data:
                return result.data[0]
            else:
                logger.error("Failed to insert processing log: No data returned")
                return None

        except Exception as e:
            logger.error(f"Error inserting processing log: {e}")
            return None

    async def get_processing_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        order_by: str = "timestamp",
        descending: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Query processing logs with filters

        Args:
            filters: Optional filters (severity, category, task_id, etc.)
            limit: Maximum number of records to return
            order_by: Field to order by
            descending: Order descending if True

        Returns:
            List of processing log records
        """
        if not self.enabled:
            logger.warning("Supabase storage not enabled - skipping log query")
            return []

        try:
            query = self.client.table("processing_logs").select("*")

            # Apply filters
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            # Apply ordering
            query = query.order(order_by, desc=descending)

            # Apply limit
            query = query.limit(limit)

            result = query.execute()
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Error querying processing logs: {e}")
            return []


# Global instance
_supabase_storage = None


def get_supabase_storage() -> SupabaseStorage:
    """
    Get singleton instance of SupabaseStorage

    Returns:
        SupabaseStorage instance
    """
    global _supabase_storage
    if _supabase_storage is None:
        _supabase_storage = SupabaseStorage()
    return _supabase_storage
