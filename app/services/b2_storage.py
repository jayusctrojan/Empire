"""
Empire v7.3 - Backblaze B2 Storage Service
Handles file uploads to B2 with folder structure management
"""

import os
from typing import Optional, BinaryIO, List, Dict, Any
from enum import Enum
from b2sdk.v2 import InMemoryAccountInfo, B2Api
from b2sdk.v2.exception import B2Error, FileNotPresent
import logging
from pathlib import Path

from app.services.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class B2Folder(str, Enum):
    """B2 folder paths for file lifecycle management"""
    PENDING = "pending/courses"
    PROCESSING = "processing/courses"
    PROCESSED = "processed/courses"
    FAILED = "failed/courses"

    # Additional content folders
    CONTENT_COURSE = "content/course"
    YOUTUBE_CONTENT = "youtube-content"

    # CrewAI generated assets base path
    # Actual path format: crewai/assets/{department}/{asset_type}/{execution_id}/
    CREWAI_ASSETS = "crewai/assets"

    # Archive folder for long-term storage
    ARCHIVE = "archive/courses"


class ProcessingStatus(str, Enum):
    """File processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class B2StorageService:
    """
    Backblaze B2 storage service for managing file uploads with folder-based workflow

    Folder Structure & Workflow:
    1. pending/courses/      - Files awaiting processing (initial upload)
    2. processing/courses/   - Files currently being processed
    3. processed/courses/    - Successfully processed documents
    4. failed/courses/       - Failed processing attempts
    5. archive/courses/      - Long-term archived files
    6. content/course/       - Course materials
    7. youtube-content/      - YouTube transcripts and metadata

    File Lifecycle:
    - Upload → pending/courses/
    - Start processing → processing/courses/
    - Success → processed/courses/
    - Failure → failed/courses/
    - Archive → archive/courses/
    """

    def __init__(self):
        """Initialize B2 API with credentials from environment"""
        self.application_key_id = os.getenv("B2_APPLICATION_KEY_ID")
        self.application_key = os.getenv("B2_APPLICATION_KEY")
        self.bucket_name = os.getenv("B2_BUCKET_NAME")

        if not all([self.application_key_id, self.application_key, self.bucket_name]):
            raise ValueError(
                "Missing B2 credentials. Required: B2_APPLICATION_KEY_ID, "
                "B2_APPLICATION_KEY, B2_BUCKET_NAME"
            )

        # Initialize B2 API
        self.info = InMemoryAccountInfo()
        self.b2_api = B2Api(self.info)
        self._bucket = None
        self._is_authorized = False

        # Initialize encryption service
        self.encryption_service = get_encryption_service()

    def _get_bucket(self):
        """Get or create bucket connection"""
        if not self._is_authorized:
            try:
                self.b2_api.authorize_account("production", self.application_key_id, self.application_key)
                self._is_authorized = True
                logger.info("B2 API authorized successfully")
            except B2Error as e:
                logger.error(f"Failed to authorize B2 API: {e}")
                raise

        if self._bucket is None:
            try:
                self._bucket = self.b2_api.get_bucket_by_name(self.bucket_name)
                logger.info(f"Connected to B2 bucket: {self.bucket_name}")
            except B2Error as e:
                logger.error(f"Failed to connect to B2 bucket: {e}")
                raise
        return self._bucket

    def verify_folders(self) -> Dict[str, bool]:
        """
        Verify all required folders exist by checking for files

        Returns:
            dict: Folder existence status {folder_path: exists}
        """
        results = {}
        for folder in B2Folder:
            try:
                # Try to list files in folder (even if empty)
                bucket = self._get_bucket()
                # List with limit 1 to just check existence
                list(bucket.ls(folder_to_list=folder.value, limit=1))
                results[folder.value] = True
                logger.debug(f"Folder exists: {folder.value}")
            except B2Error as e:
                logger.warning(f"Folder may not exist or is inaccessible: {folder.value} - {e}")
                results[folder.value] = False

        return results

    def get_folder_for_status(self, status: ProcessingStatus) -> B2Folder:
        """
        Get the appropriate B2 folder for a processing status

        Args:
            status: Processing status

        Returns:
            B2Folder: Corresponding folder

        Raises:
            ValueError: If status is invalid
        """
        status_to_folder = {
            ProcessingStatus.PENDING: B2Folder.PENDING,
            ProcessingStatus.PROCESSING: B2Folder.PROCESSING,
            ProcessingStatus.PROCESSED: B2Folder.PROCESSED,
            ProcessingStatus.FAILED: B2Folder.FAILED,
            ProcessingStatus.ARCHIVED: B2Folder.ARCHIVE,
        }

        folder = status_to_folder.get(status)
        if folder is None:
            raise ValueError(f"Invalid processing status: {status}")

        return folder

    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        folder: B2Folder = B2Folder.PENDING,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
        encrypt: bool = False,
        encryption_password: Optional[str] = None
    ) -> dict:
        """
        Upload a file to B2 storage with optional encryption

        Args:
            file_data: File-like object containing the data to upload
            filename: Name of the file
            folder: Destination folder in B2 (default: pending/courses)
            content_type: MIME type of the file
            metadata: Optional metadata dictionary
            encrypt: Whether to encrypt the file before upload
            encryption_password: Password for encryption (required if encrypt=True)

        Returns:
            dict: Upload result with file_id, file_name, url, and encryption metadata

        Raises:
            B2Error: If upload fails
            ValueError: If encryption enabled but password not provided
        """
        try:
            bucket = self._get_bucket()

            # Construct full file path (handle both B2Folder enum and string)
            folder_path = folder.value if isinstance(folder, B2Folder) else folder
            file_path = f"{folder_path}/{filename}"

            # Handle optional encryption
            encryption_metadata = {}
            if encrypt:
                if not encryption_password:
                    raise ValueError("Encryption password required when encrypt=True")

                logger.info(f"Encrypting {filename} before upload")

                # Encrypt file data
                encrypted_data, encryption_metadata = self.encryption_service.encrypt_file(
                    file_data=file_data,
                    password=encryption_password
                )

                # Use encrypted data for upload
                file_data = encrypted_data

                # Update filename to indicate encryption
                file_path = f"{folder_path}/{filename}.encrypted"

                logger.info(f"File encrypted successfully")

            # Prepare metadata
            file_info = metadata or {}
            file_info.update({
                "uploaded_by": "empire_v7.3",
                "folder": folder_path,
                **encryption_metadata  # Include encryption metadata if encrypted
            })

            # Upload file
            logger.info(f"Uploading {filename} to {file_path}")

            # Read file data
            file_bytes = file_data.read()

            # Upload to B2
            file_version = bucket.upload_bytes(
                data_bytes=file_bytes,
                file_name=file_path,
                content_type=content_type,
                file_infos=file_info
            )

            result = {
                "file_id": file_version.id_,
                "file_name": file_version.file_name,
                "size": file_version.size,
                "content_type": file_version.content_type,
                "upload_timestamp": file_version.upload_timestamp,
                "url": self.b2_api.get_download_url_for_file_name(self.bucket_name, file_path),
                "encrypted": encrypt,
                "encryption_metadata": encryption_metadata if encrypt else None
            }

            logger.info(f"Successfully uploaded {filename} (ID: {file_version.id_}), encrypted: {encrypt}")
            return result

        except B2Error as e:
            logger.error(f"B2 upload failed for {filename}: {e}")
            raise

    async def list_files(self, folder: str = "pending/courses", limit: int = 100) -> list:
        """
        List files in a specific folder

        Args:
            folder: Folder path to list
            limit: Maximum number of files to return

        Returns:
            list: List of file information dictionaries
        """
        try:
            bucket = self._get_bucket()

            files = []
            for file_version, _ in bucket.ls(folder_to_list=folder, limit=limit):
                files.append({
                    "file_id": file_version.id_,
                    "file_name": file_version.file_name,
                    "size": file_version.size,
                    "content_type": file_version.content_type,
                    "upload_timestamp": file_version.upload_timestamp
                })

            return files

        except B2Error as e:
            logger.error(f"Failed to list files in {folder}: {e}")
            raise

    async def move_file(self, file_id: str, from_folder: str, to_folder: str) -> dict:
        """
        Move a file between folders by copying and deleting original

        Args:
            file_id: B2 file ID
            from_folder: Source folder
            to_folder: Destination folder

        Returns:
            dict: New file information
        """
        try:
            bucket = self._get_bucket()

            # Get original file info
            file_info = bucket.get_file_info_by_id(file_id)
            old_name = file_info.file_name
            new_name = old_name.replace(from_folder, to_folder, 1)

            # Copy file to new location
            new_file = bucket.copy_file(file_id, new_name)

            # Delete original file
            bucket.delete_file_version(file_id, old_name)

            logger.info(f"Moved file from {old_name} to {new_name}")

            return {
                "file_id": new_file.id_,
                "file_name": new_file.file_name,
                "size": new_file.size
            }

        except B2Error as e:
            logger.error(f"Failed to move file {file_id}: {e}")
            raise

    async def delete_file(self, file_id: str, file_name: str) -> bool:
        """
        Delete a file from B2

        Args:
            file_id: B2 file ID
            file_name: Full file path

        Returns:
            bool: True if successful
        """
        try:
            bucket = self._get_bucket()
            bucket.delete_file_version(file_id, file_name)
            logger.info(f"Deleted file {file_name} (ID: {file_id})")
            return True

        except B2Error as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            raise

    async def download_file(self, file_id: str, file_name: str, destination_path: str) -> bool:
        """
        Download a file from B2 to local filesystem

        Args:
            file_id: B2 file ID
            file_name: Full file path in B2
            destination_path: Local path to save the file

        Returns:
            bool: True if successful

        Raises:
            B2Error: If download fails
            FileNotFoundError: If file doesn't exist in B2
        """
        try:
            bucket = self._get_bucket()

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            # Download file
            downloaded_file = bucket.download_file_by_id(file_id)
            downloaded_file.save_to(destination_path)

            logger.info(f"Downloaded file {file_name} to {destination_path}")
            return True

        except FileNotPresent:
            logger.error(f"File not found in B2: {file_name} (ID: {file_id})")
            raise FileNotFoundError(f"File not found in B2: {file_name}")

        except B2Error as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    async def move_to_status(
        self,
        file_id: str,
        current_status: ProcessingStatus,
        new_status: ProcessingStatus,
        metadata: Optional[dict] = None
    ) -> dict:
        """
        Move file based on processing status transition

        Args:
            file_id: B2 file ID
            current_status: Current processing status
            new_status: New processing status
            metadata: Optional metadata to update

        Returns:
            dict: New file information

        Raises:
            ValueError: If status transition is invalid
            B2Error: If move fails
        """
        # Get folders for status transition
        from_folder = self.get_folder_for_status(current_status)
        to_folder = self.get_folder_for_status(new_status)

        logger.info(f"Moving file {file_id} from {from_folder.value} to {to_folder.value}")

        # Move file between folders
        result = await self.move_file(file_id, from_folder.value, to_folder.value)

        # Update metadata if provided
        if metadata:
            try:
                bucket = self._get_bucket()
                bucket.update_file_metadata(file_id, metadata)
            except B2Error as e:
                logger.warning(f"Failed to update metadata after move: {e}")

        return result

    async def list_files_by_status(
        self,
        status: ProcessingStatus,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List all files in a status-specific folder

        Args:
            status: Processing status to filter by
            limit: Maximum number of files to return

        Returns:
            list: List of file information dictionaries
        """
        folder = self.get_folder_for_status(status)
        return await self.list_files(folder.value, limit)

    async def batch_move_to_status(
        self,
        file_ids: List[str],
        current_status: ProcessingStatus,
        new_status: ProcessingStatus
    ) -> Dict[str, Any]:
        """
        Move multiple files based on status transition

        Args:
            file_ids: List of B2 file IDs
            current_status: Current processing status
            new_status: New processing status

        Returns:
            dict: Summary of successful and failed moves
        """
        results = {
            "successful": [],
            "failed": []
        }

        for file_id in file_ids:
            try:
                result = await self.move_to_status(file_id, current_status, new_status)
                results["successful"].append({
                    "file_id": file_id,
                    "new_name": result["file_name"]
                })
            except Exception as e:
                logger.error(f"Failed to move file {file_id}: {e}")
                results["failed"].append({
                    "file_id": file_id,
                    "error": str(e)
                })

        logger.info(
            f"Batch move complete: {len(results['successful'])} successful, "
            f"{len(results['failed'])} failed"
        )

        return results


# Singleton instance
_b2_service = None


def get_b2_service() -> B2StorageService:
    """Get or create B2 storage service singleton"""
    global _b2_service
    if _b2_service is None:
        _b2_service = B2StorageService()
    return _b2_service
