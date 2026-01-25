"""
Empire v7.3 - Project Sources Models
Pydantic models for NotebookLM-style project sources feature

Task 59-60: Project Sources Database & CRUD API
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, validator
import re


# ============================================================================
# Enums
# ============================================================================

class SourceType(str, Enum):
    """Supported source types"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    MD = "md"
    CSV = "csv"
    RTF = "rtf"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    YOUTUBE = "youtube"
    WEBSITE = "website"
    ARCHIVE = "archive"


class SourceStatus(str, Enum):
    """Processing status for sources"""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SourceSortField(str, Enum):
    """Fields available for sorting sources"""
    CREATED_AT = "created_at"
    TITLE = "title"
    SOURCE_TYPE = "source_type"
    STATUS = "status"
    FILE_SIZE = "file_size"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


# ============================================================================
# File Type Validation
# ============================================================================

# Magic bytes for file type validation (first few bytes of file)
MAGIC_BYTES = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # ZIP-based (Office Open XML)
    "xlsx": [b"PK\x03\x04"],  # ZIP-based (Office Open XML)
    "pptx": [b"PK\x03\x04"],  # ZIP-based (Office Open XML)
    "doc": [b"\xd0\xcf\x11\xe0"],  # OLE Compound Document
    "xls": [b"\xd0\xcf\x11\xe0"],  # OLE Compound Document
    "ppt": [b"\xd0\xcf\x11\xe0"],  # OLE Compound Document
    "zip": [b"PK\x03\x04"],
    "gz": [b"\x1f\x8b"],
    "tar": [b"ustar"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF"],
    "mp3": [b"ID3", b"\xff\xfb", b"\xff\xfa"],
    "mp4": [b"ftyp", b"\x00\x00\x00"],
    "wav": [b"RIFF"],
    "rtf": [b"{\\rtf"],
}

# Extension to source type mapping
EXTENSION_TO_SOURCE_TYPE: Dict[str, SourceType] = {
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
    ".doc": SourceType.DOCX,
    ".xlsx": SourceType.XLSX,
    ".xls": SourceType.XLSX,
    ".pptx": SourceType.PPTX,
    ".ppt": SourceType.PPTX,
    ".txt": SourceType.TXT,
    ".md": SourceType.MD,
    ".markdown": SourceType.MD,
    ".csv": SourceType.CSV,
    ".rtf": SourceType.RTF,
    ".png": SourceType.IMAGE,
    ".jpg": SourceType.IMAGE,
    ".jpeg": SourceType.IMAGE,
    ".gif": SourceType.IMAGE,
    ".webp": SourceType.IMAGE,
    ".bmp": SourceType.IMAGE,
    ".mp3": SourceType.AUDIO,
    ".wav": SourceType.AUDIO,
    ".m4a": SourceType.AUDIO,
    ".ogg": SourceType.AUDIO,
    ".flac": SourceType.AUDIO,
    ".mp4": SourceType.VIDEO,
    ".mov": SourceType.VIDEO,
    ".avi": SourceType.VIDEO,
    ".mkv": SourceType.VIDEO,
    ".webm": SourceType.VIDEO,
    ".zip": SourceType.ARCHIVE,
    ".tar": SourceType.ARCHIVE,
    ".gz": SourceType.ARCHIVE,
    ".7z": SourceType.ARCHIVE,
    ".rar": SourceType.ARCHIVE,
}

# YouTube URL patterns
YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+",
]


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL"""
    for pattern in YOUTUBE_PATTERNS:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    return False


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL"""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


# ============================================================================
# Request Models
# ============================================================================

class AddSourceRequest(BaseModel):
    """Request model for adding a single source via URL"""
    url: str = Field(..., description="URL of the source (website or YouTube)")
    title: Optional[str] = Field(None, description="Optional custom title for the source")

    @validator("url")
    def validate_url(cls, v):
        """Validate URL format"""
        url_pattern = r"^https?://.+"
        if not re.match(url_pattern, v, re.IGNORECASE):
            raise ValueError("Invalid URL format. Must start with http:// or https://")
        return v


class AddMultipleSourcesRequest(BaseModel):
    """Request model for adding multiple sources (URLs)"""
    urls: List[str] = Field(..., description="List of URLs to add as sources")

    @validator("urls")
    def validate_urls(cls, v):
        """Validate URL list"""
        if not v:
            raise ValueError("At least one URL is required")
        if len(v) > 20:
            raise ValueError("Maximum 20 URLs can be added at once")

        url_pattern = r"^https?://.+"
        for url in v:
            if not re.match(url_pattern, url, re.IGNORECASE):
                raise ValueError(f"Invalid URL format: {url}")
        return v


class UpdateSourceRequest(BaseModel):
    """Request model for updating source metadata"""
    title: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = Field(None)


class SourceFilterParams(BaseModel):
    """Filter parameters for listing sources"""
    status: Optional[SourceStatus] = None
    source_type: Optional[SourceType] = None
    search: Optional[str] = Field(None, max_length=200)
    sort_by: SourceSortField = SourceSortField.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ============================================================================
# Response Models
# ============================================================================

class SourceMetadata(BaseModel):
    """Metadata for a source"""
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    duration_seconds: Optional[int] = None
    channel: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[str] = None
    thumbnail_url: Optional[str] = None
    chapters: Optional[List[Dict[str, Any]]] = None
    extra: Optional[Dict[str, Any]] = None


class ProjectSource(BaseModel):
    """Complete project source model"""
    id: str
    project_id: str
    user_id: str
    title: str
    source_type: SourceType
    url: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    content_hash: Optional[str] = None
    status: SourceStatus
    processing_progress: int = 0
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Optional[SourceMetadata] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AddSourceResponse(BaseModel):
    """Response for adding a source"""
    success: bool
    source_id: Optional[str] = None
    title: Optional[str] = None
    source_type: Optional[SourceType] = None
    status: SourceStatus = SourceStatus.PENDING
    message: str = ""
    error: Optional[str] = None
    # Task 68: Capacity warning info
    capacity_warning: Optional["CapacityWarning"] = None


class CapacityExceededResponse(BaseModel):
    """Response when project capacity is exceeded (HTTP 429)"""
    error: str = "capacity_exceeded"
    message: str
    capacity: "CapacityWarning"
    suggestions: List[str] = [
        "Delete unused or failed sources to free up space",
        "Remove duplicate sources if any exist",
        "Consider upgrading your plan for more capacity"
    ]


class AddMultipleSourcesResponse(BaseModel):
    """Response for adding multiple sources"""
    success: bool
    total: int
    added: int
    failed: int
    sources: List[AddSourceResponse]
    message: str = ""


class ListSourcesResponse(BaseModel):
    """Response for listing sources"""
    project_id: str
    sources: List[ProjectSource]
    total: int
    limit: int
    offset: int
    has_more: bool


class DeleteSourceResponse(BaseModel):
    """Response for deleting a source"""
    success: bool
    source_id: str
    message: str = ""


class RetrySourceResponse(BaseModel):
    """Response for retrying a failed source"""
    success: bool
    source_id: str
    retry_count: int
    status: SourceStatus
    message: str = ""


class ProjectSourceStats(BaseModel):
    """Statistics for project sources"""
    project_id: str
    total_sources: int
    ready_count: int
    processing_count: int
    pending_count: int
    failed_count: int
    total_size_bytes: int
    source_type_counts: Dict[str, int]


class CapacityWarning(BaseModel):
    """Capacity warning response"""
    at_limit: bool
    warning: bool
    current_count: int
    max_count: int = 100
    current_size_bytes: int
    max_size_bytes: int = 500 * 1024 * 1024  # 500MB
    message: Optional[str] = None
