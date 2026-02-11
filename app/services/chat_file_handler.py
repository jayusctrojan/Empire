"""
Empire v7.3 - Chat File Handler Service
Handles file and image uploads in chat for context-aware Q&A

Task 21: Enable File and Image Upload in Chat
Subtask 21.1: Implement File Handler Utility for Multipart Uploads
"""

import os
import io
import uuid
import hashlib
import mimetypes
import base64
from pathlib import Path
from typing import BinaryIO, Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

from app.services.file_validator import get_file_validator, ALLOWED_MIME_TYPES

logger = structlog.get_logger(__name__)


class ChatFileType(str, Enum):
    """Types of files that can be uploaded in chat"""
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    OTHER = "other"


class ChatFileStatus(str, Enum):
    """Status of uploaded chat files"""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ANALYZED = "analyzed"
    FAILED = "failed"


@dataclass
class ChatFileMetadata:
    """Metadata for uploaded chat files"""
    file_id: str
    original_filename: str
    stored_filename: str
    file_type: ChatFileType
    mime_type: str
    file_size: int
    file_hash: str
    session_id: str
    user_id: Optional[str] = None
    upload_timestamp: datetime = field(default_factory=datetime.utcnow)
    status: ChatFileStatus = ChatFileStatus.PENDING
    analysis_result: Optional[Dict[str, Any]] = None
    storage_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    page_count: Optional[int] = None
    extracted_text: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            "file_id": self.file_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_type": self.file_type.value,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "upload_timestamp": self.upload_timestamp.isoformat(),
            "status": self.status.value,
            "analysis_result": self.analysis_result,
            "storage_path": self.storage_path,
            "thumbnail_path": self.thumbnail_path,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "page_count": self.page_count,
            "extracted_text": self.extracted_text[:500] if self.extracted_text else None,
            "error_message": self.error_message
        }


@dataclass
class FileUploadResult:
    """Result of file upload operation"""
    success: bool
    file_id: Optional[str] = None
    metadata: Optional[ChatFileMetadata] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "file_id": self.file_id,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "error": self.error
        }


# Image MIME types for Claude Vision API
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp"
}

# Document MIME types for text extraction
DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/rtf"
}

# Maximum file sizes (in bytes)
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB for images
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB for documents
MAX_GENERAL_SIZE = 100 * 1024 * 1024  # 100MB general limit


class ChatFileHandler:
    """
    Handles file uploads for chat sessions with validation, storage, and metadata extraction

    Features:
    - Validates file types and sizes
    - Generates unique filenames
    - Extracts file metadata
    - Supports images for Claude Vision API
    - Supports documents for text extraction
    - Links files to chat sessions
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        max_files_per_session: int = 10,
        max_file_size: int = MAX_GENERAL_SIZE
    ):
        """
        Initialize chat file handler

        Args:
            storage_dir: Directory for temporary file storage (uses temp dir if not specified)
            max_files_per_session: Maximum files allowed per chat session
            max_file_size: Maximum file size in bytes
        """
        self.storage_dir = storage_dir or os.path.join(
            os.getenv("TEMP_STORAGE_DIR", "/tmp"),
            "empire_chat_uploads"
        )
        self.max_files_per_session = max_files_per_session
        self.max_file_size = max_file_size
        self.file_validator = get_file_validator()

        # Ensure storage directory exists
        os.makedirs(self.storage_dir, exist_ok=True)

        # In-memory session file tracking
        self._session_files: Dict[str, List[ChatFileMetadata]] = {}

        logger.info(
            "ChatFileHandler initialized",
            storage_dir=self.storage_dir,
            max_files_per_session=max_files_per_session,
            max_file_size=max_file_size
        )

    def _generate_file_id(self) -> str:
        """Generate unique file ID"""
        return str(uuid.uuid4())

    def _generate_stored_filename(self, original_filename: str) -> str:
        """Generate unique stored filename preserving extension"""
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{unique_id}{ext}"

    def _calculate_file_hash(self, file_data: bytes) -> str:
        """Calculate SHA-256 hash of file data"""
        return hashlib.sha256(file_data).hexdigest()

    def _detect_file_type(self, mime_type: str) -> ChatFileType:
        """Detect file type category from MIME type"""
        if mime_type in IMAGE_MIME_TYPES:
            return ChatFileType.IMAGE
        elif mime_type == "application/pdf":
            return ChatFileType.PDF
        elif mime_type in DOCUMENT_MIME_TYPES:
            return ChatFileType.DOCUMENT
        elif mime_type.startswith("text/"):
            return ChatFileType.TEXT
        elif mime_type.startswith("audio/"):
            return ChatFileType.AUDIO
        elif mime_type.startswith("video/"):
            return ChatFileType.VIDEO
        else:
            return ChatFileType.OTHER

    def _get_mime_type(self, filename: str, file_data: bytes) -> str:
        """Get MIME type from filename and content"""
        # Try from filename first
        mime_type, _ = mimetypes.guess_type(filename)

        if mime_type:
            return mime_type

        # Try from file content using magic
        try:
            import magic
            mime_detector = magic.Magic(mime=True)
            return mime_detector.from_buffer(file_data[:8192])
        except (ImportError, Exception) as e:
            logger.warning("Could not detect MIME type from content", error=str(e))
            return "application/octet-stream"

    def _get_image_dimensions(self, file_data: bytes) -> Tuple[Optional[int], Optional[int]]:
        """Get image dimensions from file data"""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_data))
            return img.width, img.height
        except (ImportError, Exception) as e:
            logger.warning("Could not get image dimensions", error=str(e))
            return None, None

    def validate_upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        session_id: str,
        file_type: Optional[ChatFileType] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate file upload

        Args:
            file_data: File content as bytes or file-like object
            filename: Original filename
            session_id: Chat session ID
            file_type: Expected file type (optional)

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Convert to bytes if needed
            if hasattr(file_data, 'read'):
                file_data.seek(0)
                data = file_data.read()
                file_data.seek(0)
            else:
                data = file_data

            # Check file size
            file_size = len(data)

            if file_size == 0:
                return False, "File is empty"

            if file_size > self.max_file_size:
                size_mb = file_size / (1024 * 1024)
                max_mb = self.max_file_size / (1024 * 1024)
                return False, f"File size ({size_mb:.2f}MB) exceeds maximum ({max_mb:.0f}MB)"

            # Get MIME type
            mime_type = self._get_mime_type(filename, data)
            detected_type = self._detect_file_type(mime_type)

            # Apply type-specific size limits
            if detected_type == ChatFileType.IMAGE and file_size > MAX_IMAGE_SIZE:
                size_mb = file_size / (1024 * 1024)
                max_mb = MAX_IMAGE_SIZE / (1024 * 1024)
                return False, f"Image size ({size_mb:.2f}MB) exceeds maximum ({max_mb:.0f}MB)"

            if detected_type in (ChatFileType.PDF, ChatFileType.DOCUMENT):
                if file_size > MAX_DOCUMENT_SIZE:
                    size_mb = file_size / (1024 * 1024)
                    max_mb = MAX_DOCUMENT_SIZE / (1024 * 1024)
                    return False, f"Document size ({size_mb:.2f}MB) exceeds maximum ({max_mb:.0f}MB)"

            # Check if type matches expected
            if file_type and detected_type != file_type:
                return False, f"Expected {file_type.value} but got {detected_type.value}"

            # Check session file limit
            session_files = self._session_files.get(session_id, [])
            if len(session_files) >= self.max_files_per_session:
                return False, f"Maximum files per session ({self.max_files_per_session}) exceeded"

            # Use file validator for additional checks
            if hasattr(file_data, 'read'):
                file_data.seek(0)
            file_io = io.BytesIO(data)
            is_valid, error = self.file_validator.validate_file_simple(file_io, filename)

            if not is_valid:
                return False, error

            return True, None

        except Exception as e:
            logger.error("File validation error", error=str(e), filename=filename)
            return False, f"Validation error: {str(e)}"

    async def process_upload(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        session_id: str,
        user_id: Optional[str] = None,
        extract_text: bool = True
    ) -> FileUploadResult:
        """
        Process file upload for chat session

        Args:
            file_data: File content as bytes or file-like object
            filename: Original filename
            session_id: Chat session ID
            user_id: Optional user ID
            extract_text: Whether to extract text from documents

        Returns:
            FileUploadResult with success status and metadata
        """
        try:
            # Convert to bytes if needed
            if hasattr(file_data, 'read'):
                file_data.seek(0)
                data = file_data.read()
            else:
                data = file_data

            # Validate upload
            is_valid, error = self.validate_upload(data, filename, session_id)
            if not is_valid:
                return FileUploadResult(success=False, error=error)

            # Generate identifiers
            file_id = self._generate_file_id()
            stored_filename = self._generate_stored_filename(filename)
            file_hash = self._calculate_file_hash(data)

            # Detect MIME type and file type
            mime_type = self._get_mime_type(filename, data)
            file_type = self._detect_file_type(mime_type)

            # Create storage path
            session_dir = os.path.join(self.storage_dir, session_id)
            os.makedirs(session_dir, exist_ok=True)
            storage_path = os.path.join(session_dir, stored_filename)

            # Save file
            with open(storage_path, 'wb') as f:
                f.write(data)

            # Create metadata
            metadata = ChatFileMetadata(
                file_id=file_id,
                original_filename=filename,
                stored_filename=stored_filename,
                file_type=file_type,
                mime_type=mime_type,
                file_size=len(data),
                file_hash=file_hash,
                session_id=session_id,
                user_id=user_id,
                status=ChatFileStatus.PROCESSING,
                storage_path=storage_path
            )

            # Extract type-specific metadata
            if file_type == ChatFileType.IMAGE:
                width, height = self._get_image_dimensions(data)
                metadata.width = width
                metadata.height = height

            # Extract text from documents if requested
            if extract_text and file_type in (ChatFileType.TEXT, ChatFileType.DOCUMENT, ChatFileType.PDF):
                extracted = await self._extract_text(data, mime_type, filename)
                if extracted:
                    metadata.extracted_text = extracted

            # Mark as ready
            metadata.status = ChatFileStatus.READY

            # Track in session
            if session_id not in self._session_files:
                self._session_files[session_id] = []
            self._session_files[session_id].append(metadata)

            logger.info(
                "File upload processed successfully",
                file_id=file_id,
                filename=filename,
                file_type=file_type.value,
                size=len(data),
                session_id=session_id
            )

            return FileUploadResult(
                success=True,
                file_id=file_id,
                metadata=metadata
            )

        except Exception as e:
            logger.error(
                "File upload processing failed",
                error=str(e),
                filename=filename,
                session_id=session_id
            )
            return FileUploadResult(success=False, error=str(e))

    async def _extract_text(
        self,
        file_data: bytes,
        mime_type: str,
        filename: str
    ) -> Optional[str]:
        """
        Extract text content from file

        Args:
            file_data: File content
            mime_type: MIME type
            filename: Original filename

        Returns:
            Extracted text or None
        """
        try:
            if mime_type == "text/plain" or mime_type == "text/markdown":
                # Direct text extraction
                try:
                    return file_data.decode('utf-8')
                except UnicodeDecodeError:
                    return file_data.decode('latin-1')

            if mime_type == "application/pdf":
                # Extract text from PDF
                try:
                    import pypdf
                    pdf_reader = pypdf.PdfReader(io.BytesIO(file_data))
                    text_parts = []
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                    return "\n\n".join(text_parts) if text_parts else None
                except ImportError:
                    logger.warning("pypdf not installed, cannot extract PDF text")
                    return None

            # For other document types, return None for now
            # Could integrate with document processor service
            return None

        except Exception as e:
            logger.warning("Text extraction failed", error=str(e), filename=filename)
            return None

    def get_file_by_id(self, file_id: str) -> Optional[ChatFileMetadata]:
        """Get file metadata by ID"""
        for session_files in self._session_files.values():
            for file_meta in session_files:
                if file_meta.file_id == file_id:
                    return file_meta
        return None

    def get_session_files(self, session_id: str) -> List[ChatFileMetadata]:
        """Get all files for a session"""
        return self._session_files.get(session_id, [])

    def get_file_content(self, file_id: str) -> Optional[bytes]:
        """Get file content by ID"""
        metadata = self.get_file_by_id(file_id)
        if metadata and metadata.storage_path and os.path.exists(metadata.storage_path):
            with open(metadata.storage_path, 'rb') as f:
                return f.read()
        return None

    def get_file_as_base64(self, file_id: str) -> Optional[str]:
        """Get file content as base64 string"""
        content = self.get_file_content(file_id)
        if content:
            return base64.b64encode(content).decode('utf-8')
        return None

    def prepare_image_for_vision(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Prepare image file for vision analysis (provider-neutral).

        Args:
            file_id: File ID

        Returns:
            ``{"data": bytes, "mime_type": "image/jpeg"}`` or None
        """
        metadata = self.get_file_by_id(file_id)
        if not metadata:
            return None

        if metadata.file_type != ChatFileType.IMAGE:
            logger.warning("File is not an image", file_id=file_id, file_type=metadata.file_type)
            return None

        if metadata.mime_type not in IMAGE_MIME_TYPES:
            logger.warning("Unsupported image type for vision", mime_type=metadata.mime_type)
            return None

        content = self.get_file_content(file_id)
        if not content:
            return None

        return {
            "data": content,
            "mime_type": metadata.mime_type,
        }

    def delete_file(self, file_id: str) -> bool:
        """Delete file by ID"""
        metadata = self.get_file_by_id(file_id)
        if not metadata:
            return False

        try:
            # Remove from disk
            if metadata.storage_path and os.path.exists(metadata.storage_path):
                os.remove(metadata.storage_path)

            # Remove thumbnail if exists
            if metadata.thumbnail_path and os.path.exists(metadata.thumbnail_path):
                os.remove(metadata.thumbnail_path)

            # Remove from session tracking
            session_files = self._session_files.get(metadata.session_id, [])
            self._session_files[metadata.session_id] = [
                f for f in session_files if f.file_id != file_id
            ]

            logger.info("File deleted", file_id=file_id)
            return True

        except Exception as e:
            logger.error("Failed to delete file", file_id=file_id, error=str(e))
            return False

    def cleanup_session(self, session_id: str) -> int:
        """
        Clean up all files for a session

        Args:
            session_id: Session ID to clean up

        Returns:
            Number of files deleted
        """
        session_files = self._session_files.get(session_id, [])
        deleted_count = 0

        for file_meta in session_files:
            try:
                if file_meta.storage_path and os.path.exists(file_meta.storage_path):
                    os.remove(file_meta.storage_path)
                if file_meta.thumbnail_path and os.path.exists(file_meta.thumbnail_path):
                    os.remove(file_meta.thumbnail_path)
                deleted_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to delete file during cleanup",
                    file_id=file_meta.file_id,
                    error=str(e)
                )

        # Remove session directory if empty
        session_dir = os.path.join(self.storage_dir, session_id)
        if os.path.exists(session_dir):
            try:
                os.rmdir(session_dir)
            except OSError:
                pass  # Directory not empty

        # Remove from tracking
        if session_id in self._session_files:
            del self._session_files[session_id]

        logger.info(
            "Session cleanup completed",
            session_id=session_id,
            files_deleted=deleted_count
        )

        return deleted_count

    def get_supported_types(self) -> Dict[str, List[str]]:
        """Get supported file types and their extensions"""
        return {
            "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
            "pdf": [".pdf"],
            "document": [".doc", ".docx", ".rtf"],
            "text": [".txt", ".md"]
        }


# Global singleton instance
_chat_file_handler: Optional[ChatFileHandler] = None


def get_chat_file_handler() -> ChatFileHandler:
    """
    Get singleton instance of ChatFileHandler

    Returns:
        ChatFileHandler instance
    """
    global _chat_file_handler
    if _chat_file_handler is None:
        _chat_file_handler = ChatFileHandler()
    return _chat_file_handler
