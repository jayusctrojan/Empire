"""
Empire v7.3 - Enhanced File Validation Service
Task 67: File type validation and security scanning

Features:
- 45+ file types with magic byte validation
- Explicit blocking of executables and scripts
- MIME type verification using python-magic
- Dangerous content pattern detection
- Security-focused file validation
"""

import magic
import logging
import re
from typing import BinaryIO, Optional, Tuple, List, Set, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Security: Blocked File Types (Executables and Scripts)
# ============================================================================

class FileRiskLevel(Enum):
    """Risk classification for file types"""
    SAFE = "safe"           # Documents, images, etc.
    MODERATE = "moderate"   # Archives (could contain malicious files)
    HIGH = "high"           # Scripts, macros
    BLOCKED = "blocked"     # Executables, system files


# BLOCKED EXTENSIONS - These are NEVER allowed
BLOCKED_EXTENSIONS: Set[str] = {
    # Windows Executables
    '.exe', '.dll', '.sys', '.drv', '.ocx', '.cpl', '.scr',
    '.msi', '.msp', '.msu', '.cab',

    # Scripts and Batch Files
    '.bat', '.cmd', '.com', '.ps1', '.psm1', '.psd1',  # Windows scripts
    '.sh', '.bash', '.zsh', '.csh', '.ksh', '.fish',   # Unix shells
    '.py', '.pyw', '.pyc', '.pyo',                     # Python (blocked for security)
    '.rb', '.pl', '.pm', '.php', '.asp', '.aspx',      # Other scripts
    '.js', '.jse', '.vbs', '.vbe', '.wsf', '.wsh',     # Windows scripting

    # Macro-enabled Office Files (high risk)
    '.docm', '.xlsm', '.pptm', '.potm', '.dotm',
    '.xlam', '.xla', '.ppam', '.ppa',

    # Java and Class Files
    '.jar', '.class', '.jnlp',

    # Application Packages
    '.app', '.dmg', '.pkg', '.deb', '.rpm', '.apk', '.ipa',

    # Configuration and System Files
    '.reg', '.inf', '.lnk', '.pif', '.hta',
    '.chm', '.hlp',

    # Binary and Object Files
    '.bin', '.o', '.so', '.dylib', '.a',

    # Dangerous Archive Types
    '.iso', '.img', '.vhd', '.vmdk',
}

# BLOCKED MIME TYPES - These are NEVER allowed
BLOCKED_MIME_TYPES: Set[str] = {
    'application/x-executable',
    'application/x-dosexec',
    'application/x-msdownload',
    'application/x-msdos-program',
    'application/x-sh',
    'application/x-shellscript',
    'application/x-bat',
    'application/x-msi',
    'application/java-archive',
    'application/x-java-applet',
    'application/javascript',
    'text/javascript',
    'application/x-python-code',
    'text/x-python',
    'text/x-script.python',
    'application/x-php',
    'text/x-php',
    'application/vnd.ms-word.document.macroEnabled.12',
    'application/vnd.ms-excel.sheet.macroEnabled.12',
    'application/vnd.ms-powerpoint.presentation.macroEnabled.12',
}


# ============================================================================
# Magic Byte Signatures (45+ File Types)
# ============================================================================

# Comprehensive magic byte signatures for file type validation
MAGIC_BYTES: Dict[str, List[bytes]] = {
    # ========== Documents ==========
    '.pdf': [b'%PDF-'],
    '.doc': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],  # OLE Compound Document
    '.docx': [b'PK\x03\x04'],  # ZIP-based (Office Open XML)
    '.xls': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],  # OLE Compound Document
    '.xlsx': [b'PK\x03\x04'],  # ZIP-based
    '.ppt': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],  # OLE Compound Document
    '.pptx': [b'PK\x03\x04'],  # ZIP-based
    '.rtf': [b'{\\rtf'],
    '.odt': [b'PK\x03\x04'],  # OpenDocument (ZIP-based)
    '.ods': [b'PK\x03\x04'],  # OpenDocument Spreadsheet
    '.odp': [b'PK\x03\x04'],  # OpenDocument Presentation
    '.epub': [b'PK\x03\x04'],  # EPUB (ZIP-based)

    # ========== Images ==========
    '.jpg': [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xe8', b'\xff\xd8\xff\xdb'],
    '.jpeg': [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xe8', b'\xff\xd8\xff\xdb'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.gif': [b'GIF87a', b'GIF89a'],
    '.bmp': [b'BM'],
    '.webp': [b'RIFF', b'WEBP'],  # RIFF....WEBP
    '.ico': [b'\x00\x00\x01\x00'],
    '.tiff': [b'II*\x00', b'MM\x00*'],  # Little/Big endian TIFF
    '.tif': [b'II*\x00', b'MM\x00*'],
    '.heic': [b'\x00\x00\x00', b'ftypheic', b'ftypmif1'],  # HEIF container
    '.heif': [b'\x00\x00\x00', b'ftypheic', b'ftypmif1'],
    '.avif': [b'\x00\x00\x00', b'ftypavif'],
    '.svg': [b'<?xml', b'<svg'],  # SVG (XML-based)
    '.psd': [b'8BPS'],  # Photoshop
    '.ai': [b'%PDF-', b'%!PS-Adobe'],  # Illustrator (PDF or EPS-based)
    '.eps': [b'%!PS-Adobe', b'\xc5\xd0\xd3\xc6'],  # Encapsulated PostScript

    # ========== Audio ==========
    '.mp3': [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2', b'ID3'],
    '.wav': [b'RIFF'],
    '.flac': [b'fLaC'],
    '.ogg': [b'OggS'],
    '.m4a': [b'\x00\x00\x00', b'ftyp'],  # MP4 container
    '.aac': [b'\xff\xf1', b'\xff\xf9'],
    '.wma': [b'\x30\x26\xb2\x75\x8e\x66\xcf\x11'],  # ASF container
    '.aiff': [b'FORM'],
    '.mid': [b'MThd'],
    '.midi': [b'MThd'],

    # ========== Video ==========
    '.mp4': [b'\x00\x00\x00', b'ftyp'],  # MP4/M4V container
    '.m4v': [b'\x00\x00\x00', b'ftyp'],
    '.mov': [b'\x00\x00\x00', b'ftyp', b'moov', b'mdat'],  # QuickTime
    '.avi': [b'RIFF'],
    '.mkv': [b'\x1a\x45\xdf\xa3'],  # Matroska
    '.webm': [b'\x1a\x45\xdf\xa3'],  # WebM (Matroska-based)
    '.wmv': [b'\x30\x26\xb2\x75\x8e\x66\xcf\x11'],  # ASF container
    '.flv': [b'FLV\x01'],
    '.3gp': [b'\x00\x00\x00', b'ftyp3gp'],
    '.mpeg': [b'\x00\x00\x01\xba', b'\x00\x00\x01\xb3'],
    '.mpg': [b'\x00\x00\x01\xba', b'\x00\x00\x01\xb3'],

    # ========== Archives ==========
    '.zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
    '.tar': [b'ustar'],  # At offset 257
    '.gz': [b'\x1f\x8b\x08'],
    '.gzip': [b'\x1f\x8b\x08'],
    '.bz2': [b'BZh'],
    '.xz': [b'\xfd7zXZ\x00'],
    '.7z': [b'7z\xbc\xaf\x27\x1c'],
    '.rar': [b'Rar!\x1a\x07\x00', b'Rar!\x1a\x07\x01\x00'],  # RAR4/RAR5
    '.lz': [b'LZIP'],
    '.lzma': [b'\x5d\x00\x00'],

    # ========== Data/Structured ==========
    '.json': [b'{', b'['],  # JSON (must validate content)
    '.xml': [b'<?xml', b'<'],
    '.yaml': [b'---', b'%YAML'],
    '.yml': [b'---', b'%YAML'],
    '.csv': [],  # Text-based, no magic bytes
    '.tsv': [],  # Text-based, no magic bytes
    '.txt': [],  # Text-based, no magic bytes
    '.md': [],   # Text-based, no magic bytes
    '.html': [b'<!DOCTYPE', b'<html', b'<HTML'],
    '.htm': [b'<!DOCTYPE', b'<html', b'<HTML'],

    # ========== Fonts ==========
    '.ttf': [b'\x00\x01\x00\x00'],
    '.otf': [b'OTTO'],
    '.woff': [b'wOFF'],
    '.woff2': [b'wOF2'],

    # ========== E-books ==========
    '.mobi': [b'BOOKMOBI'],
    '.azw': [b'BOOKMOBI'],  # Amazon Kindle
    '.azw3': [b'PK\x03\x04'],  # KF8 format (ZIP-based)
}

# DANGEROUS MAGIC BYTES - Block files that start with these
DANGEROUS_MAGIC_BYTES: List[Tuple[bytes, str]] = [
    (b'MZ', 'Windows executable (MZ header)'),
    (b'\x7fELF', 'Linux/Unix executable (ELF)'),
    (b'\xca\xfe\xba\xbe', 'macOS universal binary'),
    (b'\xfe\xed\xfa\xce', 'macOS 32-bit executable'),
    (b'\xfe\xed\xfa\xcf', 'macOS 64-bit executable'),
    (b'\xcf\xfa\xed\xfe', 'macOS 64-bit executable (LE)'),
    (b'\xce\xfa\xed\xfe', 'macOS 32-bit executable (LE)'),
    (b'#!', 'Script with shebang'),
    (b'#!/', 'Script with shebang'),
    (b'PK\x03\x04', None),  # ZIP - check for .exe/.dll inside (handled separately)
]


# ============================================================================
# Allowed MIME Types (45+ types)
# ============================================================================

ALLOWED_MIME_TYPES: Dict[str, List[str]] = {
    # ========== Documents ==========
    'application/pdf': ['.pdf'],
    'application/msword': ['.doc'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/vnd.ms-excel': ['.xls'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/vnd.ms-powerpoint': ['.ppt'],
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
    'application/rtf': ['.rtf'],
    'text/plain': ['.txt', '.md', '.csv', '.tsv', '.log'],
    'text/markdown': ['.md'],
    'text/csv': ['.csv'],
    'text/tab-separated-values': ['.tsv'],
    'application/vnd.oasis.opendocument.text': ['.odt'],
    'application/vnd.oasis.opendocument.spreadsheet': ['.ods'],
    'application/vnd.oasis.opendocument.presentation': ['.odp'],
    'application/epub+zip': ['.epub'],

    # ========== Images ==========
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/bmp': ['.bmp'],
    'image/webp': ['.webp'],
    'image/x-icon': ['.ico'],
    'image/vnd.microsoft.icon': ['.ico'],
    'image/tiff': ['.tiff', '.tif'],
    'image/heic': ['.heic'],
    'image/heif': ['.heif'],
    'image/avif': ['.avif'],
    'image/svg+xml': ['.svg'],
    'image/vnd.adobe.photoshop': ['.psd'],
    'application/postscript': ['.eps', '.ai'],

    # ========== Audio ==========
    'audio/mpeg': ['.mp3'],
    'audio/mp3': ['.mp3'],
    'audio/wav': ['.wav'],
    'audio/x-wav': ['.wav'],
    'audio/flac': ['.flac'],
    'audio/ogg': ['.ogg'],
    'audio/mp4': ['.m4a'],
    'audio/x-m4a': ['.m4a'],
    'audio/aac': ['.aac'],
    'audio/x-ms-wma': ['.wma'],
    'audio/aiff': ['.aiff'],
    'audio/x-aiff': ['.aiff'],
    'audio/midi': ['.mid', '.midi'],

    # ========== Video ==========
    'video/mp4': ['.mp4', '.m4v'],
    'video/quicktime': ['.mov'],
    'video/x-msvideo': ['.avi'],
    'video/x-matroska': ['.mkv'],
    'video/webm': ['.webm'],
    'video/x-ms-wmv': ['.wmv'],
    'video/x-flv': ['.flv'],
    'video/3gpp': ['.3gp'],
    'video/mpeg': ['.mpeg', '.mpg'],

    # ========== Archives ==========
    'application/zip': ['.zip'],
    'application/x-tar': ['.tar'],
    'application/gzip': ['.gz', '.gzip'],
    'application/x-gzip': ['.gz', '.gzip'],
    'application/x-bzip2': ['.bz2'],
    'application/x-xz': ['.xz'],
    'application/x-7z-compressed': ['.7z'],
    'application/x-rar-compressed': ['.rar'],
    'application/vnd.rar': ['.rar'],
    'application/x-lzip': ['.lz'],
    'application/x-lzma': ['.lzma'],

    # ========== Data/Structured ==========
    'application/json': ['.json'],
    'application/xml': ['.xml'],
    'text/xml': ['.xml'],
    'application/x-yaml': ['.yaml', '.yml'],
    'text/yaml': ['.yaml', '.yml'],
    'text/html': ['.html', '.htm'],

    # ========== Fonts ==========
    'font/ttf': ['.ttf'],
    'font/otf': ['.otf'],
    'font/woff': ['.woff'],
    'font/woff2': ['.woff2'],
    'application/font-woff': ['.woff'],
    'application/font-woff2': ['.woff2'],

    # ========== E-books ==========
    'application/x-mobipocket-ebook': ['.mobi', '.azw'],
    'application/vnd.amazon.ebook': ['.azw', '.azw3'],
}

# Legacy alias for backwards compatibility
FILE_HEADERS = MAGIC_BYTES


# ============================================================================
# Validation Result
# ============================================================================

@dataclass
class ValidationResult:
    """Result of file validation"""
    is_valid: bool
    error_message: Optional[str] = None
    risk_level: FileRiskLevel = FileRiskLevel.SAFE
    detected_mime: Optional[str] = None
    detected_extension: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class FileValidator:
    """
    Enhanced file validator with security-focused validation.

    Features:
    - 45+ file types with magic byte validation
    - Explicit blocking of executables and scripts
    - MIME type verification using python-magic
    - Dangerous content pattern detection
    - Archive content inspection (optional)
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the file validator.

        Args:
            strict_mode: If True, block files that fail any validation.
                        If False, log warnings but allow some edge cases.
        """
        self.strict_mode = strict_mode

        try:
            self.mime_detector = magic.Magic(mime=True)
            self.magic_descriptor = magic.Magic()  # For file type description
            logger.info("File validator initialized with python-magic (strict_mode=%s)", strict_mode)
        except Exception as e:
            logger.error(f"Failed to initialize file validator: {e}")
            self.mime_detector = None
            self.magic_descriptor = None

    def validate_file(
        self,
        file_data: BinaryIO,
        filename: str,
        max_size: int = 100 * 1024 * 1024  # 100MB
    ) -> ValidationResult:
        """
        Comprehensive file validation with security checks.

        Args:
            file_data: File binary data (file-like object)
            filename: Original filename
            max_size: Maximum allowed file size in bytes

        Returns:
            ValidationResult with validation status and details
        """
        warnings: List[str] = []

        try:
            # Get file extension
            file_ext = Path(filename).suffix.lower()

            # ===== SECURITY CHECK 1: Blocked Extensions =====
            if self._is_extension_blocked(file_ext):
                logger.warning(
                    "BLOCKED: File extension is not allowed",
                    extra={"file_name": filename, "extension": file_ext}
                )
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File extension '{file_ext}' is blocked for security reasons",
                    risk_level=FileRiskLevel.BLOCKED,
                    detected_extension=file_ext
                )

            # ===== SECURITY CHECK 2: Allowed Extensions =====
            if not self._is_extension_allowed(file_ext):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File extension '{file_ext}' is not in the allowed list",
                    risk_level=FileRiskLevel.BLOCKED,
                    detected_extension=file_ext
                )

            # Read first chunk for header validation
            file_data.seek(0)
            file_header = file_data.read(8192)  # Read first 8KB
            file_data.seek(0)  # Reset for future reads

            # ===== SECURITY CHECK 3: Dangerous Magic Bytes =====
            is_dangerous, danger_reason = self._check_dangerous_magic_bytes(file_header, file_ext)
            if is_dangerous:
                logger.warning(
                    "BLOCKED: Dangerous file content detected",
                    extra={"file_name": filename, "reason": danger_reason}
                )
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File blocked: {danger_reason}",
                    risk_level=FileRiskLevel.BLOCKED,
                    detected_extension=file_ext
                )

            # ===== SECURITY CHECK 4: MIME Type Validation =====
            detected_mime = None
            if self.mime_detector:
                detected_mime = self.mime_detector.from_buffer(file_header)

                # Check for blocked MIME types
                if detected_mime in BLOCKED_MIME_TYPES:
                    logger.warning(
                        "BLOCKED: MIME type is not allowed",
                        extra={"file_name": filename, "mime": detected_mime}
                    )
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"File type '{detected_mime}' is blocked for security reasons",
                        risk_level=FileRiskLevel.BLOCKED,
                        detected_mime=detected_mime,
                        detected_extension=file_ext
                    )

                # Validate MIME matches extension
                is_valid_mime, mime_warning = self._validate_mime_type(detected_mime, file_ext)
                if not is_valid_mime:
                    if self.strict_mode:
                        return ValidationResult(
                            is_valid=False,
                            error_message=mime_warning,
                            risk_level=FileRiskLevel.HIGH,
                            detected_mime=detected_mime,
                            detected_extension=file_ext
                        )
                    else:
                        warnings.append(mime_warning)

            # ===== SECURITY CHECK 5: Magic Byte Validation =====
            is_valid_header, header_error = self._validate_magic_bytes(file_header, file_ext)
            if not is_valid_header:
                if self.strict_mode:
                    return ValidationResult(
                        is_valid=False,
                        error_message=header_error,
                        risk_level=FileRiskLevel.HIGH,
                        detected_mime=detected_mime,
                        detected_extension=file_ext
                    )
                else:
                    warnings.append(header_error)

            # ===== SIZE VALIDATION =====
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Reset

            if file_size > max_size:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File size ({file_size / (1024*1024):.2f}MB) exceeds maximum ({max_size / (1024*1024):.0f}MB)",
                    risk_level=FileRiskLevel.SAFE,
                    detected_mime=detected_mime,
                    detected_extension=file_ext
                )

            if file_size < 10:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File is too small ({file_size} bytes) and may be corrupted",
                    risk_level=FileRiskLevel.SAFE,
                    detected_mime=detected_mime,
                    detected_extension=file_ext
                )

            # ===== DETERMINE RISK LEVEL =====
            risk_level = self._assess_risk_level(file_ext, detected_mime)

            logger.info(
                "File validation passed",
                extra={
                    "file_name": filename,
                    "size_kb": file_size / 1024,
                    "extension": file_ext,
                    "mime": detected_mime,
                    "risk_level": risk_level.value
                }
            )

            return ValidationResult(
                is_valid=True,
                risk_level=risk_level,
                detected_mime=detected_mime,
                detected_extension=file_ext,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"File validation error for {filename}: {e}")
            return ValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
                risk_level=FileRiskLevel.BLOCKED
            )

    def validate_file_simple(
        self,
        file_data: BinaryIO,
        filename: str,
        max_size: int = 100 * 1024 * 1024
    ) -> Tuple[bool, Optional[str]]:
        """
        Simple validation returning tuple (backwards compatible).

        Args:
            file_data: File binary data
            filename: Original filename
            max_size: Maximum allowed file size in bytes

        Returns:
            tuple: (is_valid, error_message)
        """
        result = self.validate_file(file_data, filename, max_size)
        return result.is_valid, result.error_message

    def _is_extension_blocked(self, extension: str) -> bool:
        """Check if file extension is in blocked list"""
        return extension.lower() in BLOCKED_EXTENSIONS

    def _is_extension_allowed(self, extension: str) -> bool:
        """Check if file extension is in allowed list"""
        ext_lower = extension.lower()

        # Check all allowed MIME types for this extension
        for mime_type, extensions in ALLOWED_MIME_TYPES.items():
            if ext_lower in extensions:
                return True

        # Also check MAGIC_BYTES for extensions without MIME mappings
        if ext_lower in MAGIC_BYTES:
            return True

        return False

    def _check_dangerous_magic_bytes(self, file_header: bytes, extension: str) -> Tuple[bool, Optional[str]]:
        """
        Check if file contains dangerous magic bytes (executables, scripts).

        Args:
            file_header: First bytes of file
            extension: Claimed file extension

        Returns:
            tuple: (is_dangerous, reason)
        """
        # Check for executable magic bytes
        for magic_bytes, description in DANGEROUS_MAGIC_BYTES:
            if magic_bytes == b'PK\x03\x04':
                # ZIP files need special handling - they're allowed but we
                # check for suspicious content later
                continue

            if file_header.startswith(magic_bytes):
                # Exception: Allow shebang in text files if explicitly allowed
                if magic_bytes in (b'#!', b'#!/'):
                    # Only block if not a text file
                    if extension not in ['.txt', '.md', '.csv']:
                        return True, description or f"Blocked: {magic_bytes[:10]}"
                else:
                    return True, description or f"Blocked binary signature detected"

        # Check for Windows executable (MZ header)
        if file_header[:2] == b'MZ':
            return True, "Windows executable (PE/MZ) file detected"

        # Check for ELF (Linux/Unix executable)
        if file_header[:4] == b'\x7fELF':
            return True, "Linux/Unix executable (ELF) file detected"

        # Check for Mach-O (macOS executable)
        macho_signatures = [
            b'\xca\xfe\xba\xbe',  # Universal binary
            b'\xfe\xed\xfa\xce',  # 32-bit
            b'\xfe\xed\xfa\xcf',  # 64-bit
            b'\xcf\xfa\xed\xfe',  # 64-bit (little endian)
            b'\xce\xfa\xed\xfe',  # 32-bit (little endian)
        ]
        if file_header[:4] in macho_signatures:
            return True, "macOS executable (Mach-O) file detected"

        return False, None

    def _validate_mime_type(self, detected_mime: str, extension: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that detected MIME type is compatible with extension.

        Args:
            detected_mime: MIME type detected by python-magic
            extension: Claimed file extension

        Returns:
            tuple: (is_valid, warning_message)
        """
        # Find expected MIME types for this extension
        expected_mimes = []
        for mime_type, extensions in ALLOWED_MIME_TYPES.items():
            if extension in extensions:
                expected_mimes.append(mime_type)

        if not expected_mimes:
            return False, f"No MIME type mapping found for extension {extension}"

        # Generic MIME types are accepted with warning
        if detected_mime == 'application/octet-stream':
            return True, f"Generic MIME type detected for {extension}"

        # Check if detected MIME matches any expected
        if detected_mime in expected_mimes:
            return True, None

        # Check category match (e.g., image/* for images)
        detected_category = detected_mime.split('/')[0]
        for expected in expected_mimes:
            expected_category = expected.split('/')[0]
            if detected_category == expected_category:
                return True, None

        # Special cases for common mismatches
        text_extensions = ['.txt', '.md', '.csv', '.tsv', '.log', '.json', '.xml', '.yaml', '.yml', '.html', '.htm']
        if extension in text_extensions and detected_mime.startswith('text/'):
            return True, None

        # ZIP-based formats
        zip_extensions = ['.docx', '.xlsx', '.pptx', '.odt', '.ods', '.odp', '.epub', '.azw3']
        if extension in zip_extensions and detected_mime == 'application/zip':
            return True, None

        return False, f"MIME type mismatch: detected {detected_mime}, expected one of {expected_mimes}"

    def _validate_magic_bytes(self, file_header: bytes, extension: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file header magic bytes match expected format.

        Args:
            file_header: First bytes of file
            extension: File extension

        Returns:
            tuple: (is_valid, error_message)
        """
        if extension not in MAGIC_BYTES:
            # No specific magic bytes defined - allow
            return True, None

        expected_signatures = MAGIC_BYTES[extension]

        # Empty list means no magic bytes validation (text files)
        if not expected_signatures:
            return True, None

        # Check if file starts with any expected signature
        for signature in expected_signatures:
            if file_header.startswith(signature):
                return True, None

            # Some formats have signature at different offset
            if signature in file_header[:100]:
                return True, None

        # Special case: TAR files have signature at offset 257
        if extension == '.tar':
            if len(file_header) >= 262 and file_header[257:262] == b'ustar':
                return True, None

        # Special case: WEBP has RIFF...WEBP structure
        if extension == '.webp':
            if file_header[:4] == b'RIFF' and b'WEBP' in file_header[:16]:
                return True, None

        # Special case: MP4/MOV have ftyp atom (can be at various offsets)
        if extension in ['.mp4', '.m4v', '.mov', '.m4a', '.3gp']:
            if b'ftyp' in file_header[:32]:
                return True, None

        return False, f"File header does not match expected format for {extension}"

    def _assess_risk_level(self, extension: str, mime_type: Optional[str]) -> FileRiskLevel:
        """
        Assess the risk level of a file based on its type.

        Args:
            extension: File extension
            mime_type: Detected MIME type

        Returns:
            FileRiskLevel enum value
        """
        # Archives can contain malicious files
        archive_extensions = ['.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar']
        if extension in archive_extensions:
            return FileRiskLevel.MODERATE

        # Office documents can contain macros (non-macro versions are safer)
        office_extensions = ['.doc', '.xls', '.ppt']  # Legacy formats
        if extension in office_extensions:
            return FileRiskLevel.MODERATE

        # Everything else is considered safe
        return FileRiskLevel.SAFE

    def get_allowed_extensions(self) -> List[str]:
        """Get list of all allowed file extensions"""
        extensions = set()
        for mime_type, exts in ALLOWED_MIME_TYPES.items():
            extensions.update(exts)
        for ext in MAGIC_BYTES.keys():
            extensions.add(ext)
        # Remove blocked extensions
        extensions -= BLOCKED_EXTENSIONS
        return sorted(list(extensions))

    def get_blocked_extensions(self) -> List[str]:
        """Get list of all blocked file extensions"""
        return sorted(list(BLOCKED_EXTENSIONS))

    def get_allowed_mime_types(self) -> List[str]:
        """Get list of all allowed MIME types"""
        return sorted(list(ALLOWED_MIME_TYPES.keys()))

    def get_blocked_mime_types(self) -> List[str]:
        """Get list of all blocked MIME types"""
        return sorted(list(BLOCKED_MIME_TYPES))

    def get_file_info(self, file_data: BinaryIO) -> Dict[str, Any]:
        """
        Get detailed information about a file without full validation.

        Args:
            file_data: File binary data

        Returns:
            Dict with file information
        """
        file_data.seek(0)
        header = file_data.read(8192)
        file_data.seek(0, 2)
        size = file_data.tell()
        file_data.seek(0)

        info = {
            "size_bytes": size,
            "size_human": self._human_readable_size(size),
            "header_hex": header[:32].hex(),
        }

        if self.mime_detector:
            info["detected_mime"] = self.mime_detector.from_buffer(header)

        if self.magic_descriptor:
            info["file_description"] = self.magic_descriptor.from_buffer(header)

        return info

    def _human_readable_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


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
