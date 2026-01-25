"""
Empire v7.3 - File Validation Service
Validates file formats, MIME types, and file integrity using python-magic
"""

import magic
import logging
from typing import BinaryIO, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Allowed MIME types mapping to extensions
ALLOWED_MIME_TYPES = {
    # Documents
    'application/pdf': ['.pdf'],
    'application/msword': ['.doc'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'text/plain': ['.txt'],
    'text/markdown': ['.md'],
    'application/rtf': ['.rtf'],

    # Presentations
    'application/vnd.ms-powerpoint': ['.ppt'],
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
    'application/x-iwork-keynote-sffkey': ['.key'],

    # Spreadsheets
    'application/vnd.ms-excel': ['.xls'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'text/csv': ['.csv'],

    # Images
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/bmp': ['.bmp'],
    'image/svg+xml': ['.svg'],
    'image/webp': ['.webp'],

    # Audio
    'audio/mpeg': ['.mp3'],
    'audio/wav': ['.wav'],
    'audio/x-m4a': ['.m4a'],
    'audio/mp4': ['.m4a'],

    # Video
    'video/mp4': ['.mp4'],
    'video/quicktime': ['.mov'],
    'video/x-msvideo': ['.avi'],
    'video/x-matroska': ['.mkv'],

    # Archives
    'application/zip': ['.zip'],
    'application/x-tar': ['.tar'],
    'application/gzip': ['.gz'],
    'application/x-7z-compressed': ['.7z'],
}

# File header magic numbers for validation
FILE_HEADERS = {
    '.pdf': [b'%PDF'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.gif': [b'GIF87a', b'GIF89a'],
    '.bmp': [b'BM'],
    '.zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
    '.tar': [b'ustar'],
    '.gz': [b'\x1f\x8b'],
    '.7z': [b'7z\xbc\xaf\x27\x1c'],
}


class FileValidator:
    """
    Validates uploaded files for security and integrity
    """

    def __init__(self):
        """Initialize the file validator with magic library"""
        try:
            self.mime_detector = magic.Magic(mime=True)
            logger.info("File validator initialized with python-magic")
        except Exception as e:
            logger.error(f"Failed to initialize file validator: {e}")
            self.mime_detector = None

    def validate_file(
        self,
        file_data: BinaryIO,
        filename: str,
        max_size: int = 100 * 1024 * 1024  # 100MB
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive file validation

        Args:
            file_data: File binary data
            filename: Original filename
            max_size: Maximum allowed file size in bytes

        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Get file extension
            file_ext = Path(filename).suffix.lower()

            # Check if extension is in allowed list
            if not self._is_extension_allowed(file_ext):
                return False, f"File extension '{file_ext}' is not allowed"

            # Read first chunk for header validation
            file_data.seek(0)
            file_header = file_data.read(8192)  # Read first 8KB
            file_data.seek(0)  # Reset for future reads

            # Validate MIME type
            is_valid_mime, mime_error = self._validate_mime_type(file_header, file_ext)
            if not is_valid_mime:
                return False, mime_error

            # Validate file header
            is_valid_header, header_error = self._validate_file_header(file_header, file_ext)
            if not is_valid_header:
                return False, header_error

            # Get file size
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Reset

            # Check file size
            if file_size > max_size:
                return False, f"File size ({file_size / (1024*1024):.2f}MB) exceeds maximum ({max_size / (1024*1024):.0f}MB)"

            # Check for suspiciously small files
            if file_size < 10:
                return False, f"File is too small ({file_size} bytes) and may be corrupted"

            logger.info(f"File validation passed: {filename} ({file_size / 1024:.2f}KB)")
            return True, None

        except Exception as e:
            logger.error(f"File validation error for {filename}: {e}")
            return False, f"Validation error: {str(e)}"

    def _is_extension_allowed(self, extension: str) -> bool:
        """Check if file extension is in allowed list"""
        for mime_type, extensions in ALLOWED_MIME_TYPES.items():
            if extension in extensions:
                return True
        return False

    def _validate_mime_type(self, file_data: bytes, extension: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file MIME type using python-magic

        Args:
            file_data: File header bytes
            extension: File extension

        Returns:
            tuple: (is_valid, error_message)
        """
        if not self.mime_detector:
            logger.warning("MIME detector not available, skipping MIME validation")
            return True, None

        try:
            # Detect MIME type from file content
            detected_mime = self.mime_detector.from_buffer(file_data)

            logger.debug(f"Detected MIME type: {detected_mime} for extension: {extension}")

            # Check if detected MIME type matches allowed types for this extension
            matching_mime = None
            for mime_type, extensions in ALLOWED_MIME_TYPES.items():
                if extension in extensions:
                    matching_mime = mime_type
                    break

            if not matching_mime:
                return False, f"Extension {extension} is not in allowed MIME types"

            # Some files have generic MIME types (like application/octet-stream)
            # We'll be lenient with these but log them
            if detected_mime == 'application/octet-stream':
                logger.warning(f"Generic MIME type detected for {extension}, allowing but flagging")
                return True, None

            # For specific MIME types, check if they match or are compatible
            if detected_mime.startswith(matching_mime.split('/')[0]):
                # Same category (e.g., both 'image/')
                return True, None

            # Special cases for common mismatches
            if extension == '.txt' and detected_mime.startswith('text/'):
                return True, None

            if extension == '.md' and detected_mime in ['text/plain', 'text/x-markdown']:
                return True, None

            # If exact match is required but not found
            if detected_mime != matching_mime:
                logger.warning(f"MIME type mismatch: expected {matching_mime}, got {detected_mime}")
                # Be lenient - log warning but don't reject
                return True, None

            return True, None

        except Exception as e:
            logger.error(f"MIME type validation error: {e}")
            # Don't fail upload on MIME detection errors
            return True, None

    def _validate_file_header(self, file_data: bytes, extension: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file header magic numbers

        Args:
            file_data: File header bytes
            extension: File extension

        Returns:
            tuple: (is_valid, error_message)
        """
        if extension not in FILE_HEADERS:
            # No specific header validation for this type
            return True, None

        expected_headers = FILE_HEADERS[extension]

        # Check if file starts with any of the expected headers
        for expected_header in expected_headers:
            if file_data.startswith(expected_header):
                logger.debug(f"Valid header found for {extension}")
                return True, None

        # For TAR files, header is at specific offset
        if extension == '.tar':
            tar_header = file_data[257:262]
            if tar_header == b'ustar':
                return True, None

        logger.warning(f"Invalid or missing header for {extension}")
        return False, f"File header does not match expected format for {extension}"

    def get_allowed_extensions(self) -> list:
        """Get list of all allowed file extensions"""
        extensions = set()
        for mime_type, exts in ALLOWED_MIME_TYPES.items():
            extensions.update(exts)
        return sorted(list(extensions))

    def get_allowed_mime_types(self) -> list:
        """Get list of all allowed MIME types"""
        return sorted(list(ALLOWED_MIME_TYPES.keys()))


# Global validator instance
_validator = None


def get_file_validator() -> FileValidator:
    """
    Get or create file validator singleton

    Returns:
        FileValidator instance
    """
    global _validator

    if _validator is None:
        _validator = FileValidator()

    return _validator
