"""
Empire v7.3 - Project Sources Service
Service layer for managing project sources (NotebookLM-style feature)

Task 60: Implement Source CRUD API endpoints
Task 67: File type validation and security scanning integration

Security Features:
- Enhanced file validation with 45+ file types
- URL sanitization with SSRF protection
- VirusTotal integration for malware scanning
- Comprehensive security event logging
"""

import os
import hashlib
import mimetypes
import io
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
import structlog
import re

from app.core.supabase_client import get_supabase_client
from app.models.project_sources import (
    SourceType,
    SourceStatus,
    SourceSortField,
    SortOrder,
    ProjectSource,
    SourceMetadata,
    AddSourceResponse,
    ListSourcesResponse,
    ProjectSourceStats,
    CapacityWarning,
    EXTENSION_TO_SOURCE_TYPE,
    MAGIC_BYTES,
    is_youtube_url,
    extract_youtube_video_id,
)

# Security imports (Task 67)
from app.services.file_validator import (
    get_file_validator,
    FileValidator,
    ValidationResult,
    FileRiskLevel,
)
from app.services.url_validator import (
    get_url_validator,
    URLValidator,
    URLValidationResult,
    URLRiskLevel,
)
from app.services.security_logger import (
    get_security_logger,
    SecurityLogger,
    SecurityEventType,
    SecuritySeverity,
)

# Optional: VirusTotal scanner (may not always be available)
try:
    from app.services.virus_scanner import VirusScanner, get_virus_scanner
    VIRUS_SCANNER_AVAILABLE = True
except ImportError:
    VIRUS_SCANNER_AVAILABLE = False
    get_virus_scanner = None

logger = structlog.get_logger(__name__)

# Configuration
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_SOURCES_PER_PROJECT = 100
MAX_STORAGE_PER_PROJECT = 500 * 1024 * 1024  # 500MB
CAPACITY_WARNING_THRESHOLD = 0.8  # 80%

# Security configuration
ENABLE_VIRUS_SCANNING = os.getenv("ENABLE_VIRUS_SCANNING", "true").lower() == "true"
VIRUS_SCAN_TIMEOUT = 60  # seconds


class ProjectSourcesService:
    """
    Service for managing project sources with integrated security validation.

    Security Features (Task 67):
    - Enhanced file validation (45+ types, magic bytes, MIME type checks)
    - URL sanitization (scheme whitelisting, SSRF protection)
    - VirusTotal integration (optional, configurable)
    - Security event logging to audit_logs
    """

    def __init__(self):
        self.supabase = get_supabase_client()

        # Initialize security services (Task 67)
        self.file_validator: FileValidator = get_file_validator()
        self.url_validator: URLValidator = get_url_validator()
        self.security_logger: SecurityLogger = get_security_logger(
            supabase_client=self.supabase
        )

        # Virus scanner (optional)
        self.virus_scanner = None
        if VIRUS_SCANNER_AVAILABLE and ENABLE_VIRUS_SCANNING:
            try:
                self.virus_scanner = get_virus_scanner()
                logger.info("VirusTotal scanner enabled for project sources")
            except Exception as e:
                logger.warning(f"VirusTotal scanner not available: {e}")

        logger.info(
            "ProjectSourcesService initialized with security features",
            virus_scanning=self.virus_scanner is not None
        )

    # ========================================================================
    # Source Creation
    # ========================================================================

    async def add_url_source(
        self,
        project_id: str,
        user_id: str,
        url: str,
        title: Optional[str] = None,
        ip_address: Optional[str] = None,  # For security logging
    ) -> AddSourceResponse:
        """
        Add a URL source (website or YouTube) to a project.

        Security (Task 67):
        - URL validation with scheme whitelisting (http/https only)
        - SSRF protection (blocks private IPs, metadata endpoints)
        - Security event logging for blocked URLs

        Args:
            project_id: Project ID
            user_id: User ID
            url: URL to add
            title: Optional custom title
            ip_address: Request IP for security logging

        Returns:
            AddSourceResponse with source details
        """
        try:
            # ===== SECURITY: URL Validation (Task 67) =====
            url_validation: URLValidationResult = self.url_validator.validate_url(url)

            if not url_validation.is_valid:
                # Log security event
                await self.security_logger.log_url_blocked(
                    url=url,
                    reason=url_validation.error_message or "Validation failed",
                    user_id=user_id,
                    ip_address=ip_address,
                )

                logger.warning(
                    "URL blocked by security validation",
                    user_id=user_id,
                    url_preview=url[:50],
                    error=url_validation.error_message,
                    risk_level=url_validation.risk_level.value
                )

                return AddSourceResponse(
                    success=False,
                    error=url_validation.error_message,
                    message="URL failed security validation"
                )

            # Use sanitized URL
            sanitized_url = url_validation.sanitized_url or url

            # Log warnings if any
            if url_validation.warnings:
                logger.info(
                    "URL validation warnings",
                    url_preview=sanitized_url[:50],
                    warnings=url_validation.warnings
                )

            # Check capacity limits
            capacity = await self.check_capacity(project_id, user_id)
            if capacity.at_limit:
                return AddSourceResponse(
                    success=False,
                    error="Project has reached maximum source limit (100 sources)",
                    message="Please delete some sources before adding new ones"
                )

            # Check for duplicate URL (using sanitized URL)
            existing = self.supabase.table("project_sources").select("id").eq(
                "project_id", project_id
            ).eq("url", sanitized_url).execute()

            if existing.data:
                return AddSourceResponse(
                    success=False,
                    source_id=existing.data[0]["id"],
                    error="Duplicate source",
                    message="This URL has already been added to the project"
                )

            # Determine source type from URL
            # Check for YouTube using our validator's method
            is_youtube, video_id = self.url_validator.is_youtube_url(sanitized_url)
            source_type = SourceType.YOUTUBE if is_youtube else SourceType.WEBSITE

            # Generate title if not provided
            if not title:
                if source_type == SourceType.YOUTUBE:
                    title = f"YouTube Video: {video_id}" if video_id else "YouTube Video"
                else:
                    # Use parsed host from validation
                    title = url_validation.parsed_host or sanitized_url[:50]

            # Create source record
            source_id = str(uuid4())
            source_data = {
                "id": source_id,
                "project_id": project_id,
                "user_id": user_id,
                "title": title[:500],  # Limit title length
                "source_type": source_type.value,
                "url": sanitized_url,  # Store sanitized URL
                "status": SourceStatus.PENDING.value,
                "processing_progress": 0,
                "retry_count": 0,
                "metadata": {
                    "original_url": url if url != sanitized_url else None,
                    "url_risk_level": url_validation.risk_level.value,
                    "resolved_ip": url_validation.resolved_ip,
                },
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            self.supabase.table("project_sources").insert(source_data).execute()

            # Queue Celery task for processing
            self._queue_source_processing(source_id, user_id)

            logger.info(
                "URL source added (security validated)",
                source_id=source_id,
                project_id=project_id,
                source_type=source_type.value,
                url=sanitized_url[:100],
                risk_level=url_validation.risk_level.value
            )

            return AddSourceResponse(
                success=True,
                source_id=source_id,
                title=title,
                source_type=source_type,
                status=SourceStatus.PENDING,
                message="Source added and queued for processing"
            )

        except Exception as e:
            logger.error("Failed to add URL source", error=str(e), url=url[:100])
            return AddSourceResponse(
                success=False,
                error=str(e),
                message="Failed to add source"
            )

    async def add_file_source(
        self,
        project_id: str,
        user_id: str,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        title: Optional[str] = None,
        ip_address: Optional[str] = None,  # For security logging
        skip_virus_scan: bool = False,  # For testing purposes
    ) -> AddSourceResponse:
        """
        Add a file source to a project with comprehensive security validation.

        Security (Task 67):
        - Enhanced file validation (45+ types, magic bytes, MIME checks)
        - Blocks executables, scripts, and dangerous file types
        - Optional VirusTotal scanning for malware detection
        - Security event logging for blocked files

        Args:
            project_id: Project ID
            user_id: User ID
            file_content: File bytes
            filename: Original filename
            mime_type: MIME type (optional, will be detected)
            title: Optional custom title
            ip_address: Request IP for security logging
            skip_virus_scan: Skip virus scanning (for testing only)

        Returns:
            AddSourceResponse with source details
        """
        try:
            file_size = len(file_content)
            ext = os.path.splitext(filename)[1].lower()

            # ===== SECURITY: Enhanced File Validation (Task 67) =====
            # Wrap bytes in file-like object for validator
            file_io = io.BytesIO(file_content)

            validation_result: ValidationResult = self.file_validator.validate_file(
                file_data=file_io,
                filename=filename,
                max_size=MAX_FILE_SIZE
            )

            if not validation_result.is_valid:
                # Log security event
                await self.security_logger.log_file_blocked(
                    filename=filename,
                    reason=validation_result.error_message or "Validation failed",
                    extension=ext,
                    mime_type=validation_result.detected_mime,
                    user_id=user_id,
                    ip_address=ip_address,
                )

                logger.warning(
                    "File blocked by security validation",
                    user_id=user_id,
                    filename=filename,
                    error=validation_result.error_message,
                    risk_level=validation_result.risk_level.value
                )

                return AddSourceResponse(
                    success=False,
                    error=validation_result.error_message,
                    message="File failed security validation"
                )

            # Log warnings if any
            if validation_result.warnings:
                logger.info(
                    "File validation warnings",
                    filename=filename,
                    warnings=validation_result.warnings
                )

            # Check capacity limits
            capacity = await self.check_capacity(project_id, user_id)
            if capacity.at_limit:
                return AddSourceResponse(
                    success=False,
                    error="Project has reached maximum source limit",
                    message="Please delete some sources before adding new ones"
                )

            # Check total storage
            if capacity.current_size_bytes + file_size > MAX_STORAGE_PER_PROJECT:
                return AddSourceResponse(
                    success=False,
                    error="Project storage limit exceeded",
                    message="Please delete some files to free up space"
                )

            # Map extension to source type
            source_type = EXTENSION_TO_SOURCE_TYPE.get(ext)
            if not source_type:
                # Check if it's a valid extension from our expanded list
                if ext in self.file_validator.get_allowed_extensions():
                    source_type = SourceType.DOCUMENT  # Default to document
                else:
                    return AddSourceResponse(
                        success=False,
                        error=f"Unsupported file type: {ext}",
                        message="Please upload a supported file type"
                    )

            # ===== SECURITY: Virus Scanning (Task 67) =====
            if self.virus_scanner and not skip_virus_scan:
                try:
                    scan_result = await self._scan_file_for_viruses(
                        file_content=file_content,
                        filename=filename,
                        user_id=user_id,
                        ip_address=ip_address,
                    )

                    if scan_result and not scan_result.get("is_clean", True):
                        # File is malicious!
                        virus_names = scan_result.get("virus_names", ["Unknown threat"])
                        error_msg = f"Malware detected: {', '.join(virus_names[:3])}"

                        logger.error(
                            "VIRUS DETECTED - File blocked",
                            filename=filename,
                            user_id=user_id,
                            virus_names=virus_names,
                        )

                        return AddSourceResponse(
                            success=False,
                            error=error_msg,
                            message="File blocked due to security threat detection"
                        )

                except Exception as scan_error:
                    # Log but don't block on scan failure
                    logger.warning(
                        "Virus scan failed, proceeding with upload",
                        filename=filename,
                        error=str(scan_error)
                    )

            # Calculate content hash for duplicate detection
            content_hash = hashlib.sha256(file_content).hexdigest()

            # Check for duplicate file
            existing = self.supabase.table("project_sources").select("id").eq(
                "project_id", project_id
            ).eq("content_hash", content_hash).execute()

            if existing.data:
                return AddSourceResponse(
                    success=False,
                    source_id=existing.data[0]["id"],
                    error="Duplicate file",
                    message="This file has already been added to the project"
                )

            # Upload to Supabase storage
            source_id = str(uuid4())
            storage_path = f"project_sources/{user_id}/{project_id}/{source_id}/{filename}"

            # Use detected MIME type from validation if not provided
            if not mime_type:
                mime_type = validation_result.detected_mime
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(filename)
                mime_type = mime_type or "application/octet-stream"

            # Upload file to storage
            storage = self.supabase.storage.from_("documents")
            storage.upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": mime_type}
            )

            # Create source record with security metadata
            source_data = {
                "id": source_id,
                "project_id": project_id,
                "user_id": user_id,
                "title": title or filename[:500],
                "source_type": source_type.value,
                "file_path": storage_path,
                "file_name": filename,
                "file_size": file_size,
                "mime_type": mime_type,
                "content_hash": content_hash,
                "status": SourceStatus.PENDING.value,
                "processing_progress": 0,
                "retry_count": 0,
                "metadata": {
                    "security_validated": True,
                    "file_risk_level": validation_result.risk_level.value,
                    "detected_mime": validation_result.detected_mime,
                    "virus_scanned": self.virus_scanner is not None and not skip_virus_scan,
                },
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            self.supabase.table("project_sources").insert(source_data).execute()

            # Queue Celery task for processing
            self._queue_source_processing(source_id, user_id)

            logger.info(
                "File source added (security validated)",
                source_id=source_id,
                project_id=project_id,
                source_type=source_type.value,
                filename=filename,
                file_size=file_size,
                risk_level=validation_result.risk_level.value
            )

            return AddSourceResponse(
                success=True,
                source_id=source_id,
                title=title or filename,
                source_type=source_type,
                status=SourceStatus.PENDING,
                message="File uploaded and queued for processing"
            )

        except Exception as e:
            logger.error("Failed to add file source", error=str(e), filename=filename)
            return AddSourceResponse(
                success=False,
                error=str(e),
                message="Failed to upload file"
            )

    async def _scan_file_for_viruses(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        ip_address: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Scan file content with VirusTotal.

        Returns:
            Dict with scan results or None if scanning unavailable
        """
        if not self.virus_scanner:
            return None

        try:
            # Calculate hash for lookup
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Check if we've seen this file before (cached result)
            # VirusTotal uses hash-first approach

            is_clean, virus_names, scan_details = await self.virus_scanner.scan_file(
                file_content=file_content,
                filename=filename,
            )

            if not is_clean and virus_names:
                # Log critical security event
                await self.security_logger.log_virus_detected(
                    filename=filename,
                    virus_names=virus_names,
                    scan_result=scan_details or {},
                    user_id=user_id,
                    ip_address=ip_address,
                )

            return {
                "is_clean": is_clean,
                "virus_names": virus_names or [],
                "details": scan_details,
                "hash": file_hash,
            }

        except Exception as e:
            logger.error(
                "Virus scan error",
                filename=filename,
                error=str(e)
            )
            return None

    def _queue_source_processing(self, source_id: str, user_id: str):
        """Queue Celery task for source processing"""
        try:
            from app.tasks.source_processing import process_source
            process_source.delay(source_id, user_id)
            logger.info("Queued source processing task", source_id=source_id)
        except Exception as e:
            logger.error("Failed to queue source processing", error=str(e), source_id=source_id)
            # Don't fail the add operation if queuing fails
            # The source can be manually retried later

    def _validate_magic_bytes(self, content: bytes, extension: str) -> bool:
        """Validate file magic bytes match expected type"""
        ext_key = extension.lstrip(".").lower()

        # Skip validation for text-based formats
        if ext_key in ("txt", "md", "csv", "markdown"):
            return True

        magic_list = MAGIC_BYTES.get(ext_key)
        if not magic_list:
            # No magic bytes defined, allow it
            return True

        # Check if any magic bytes match
        for magic in magic_list:
            if content.startswith(magic):
                return True

        # Special case: ZIP-based formats (docx, xlsx, pptx)
        if ext_key in ("docx", "xlsx", "pptx") and content.startswith(b"PK\x03\x04"):
            return True

        return False

    # ========================================================================
    # Source Retrieval
    # ========================================================================

    async def get_source(
        self,
        source_id: str,
        user_id: str
    ) -> Optional[ProjectSource]:
        """Get a single source by ID"""
        try:
            result = self.supabase.table("project_sources").select("*").eq(
                "id", source_id
            ).eq("user_id", user_id).execute()

            if not result.data:
                return None

            return self._to_project_source(result.data[0])

        except Exception as e:
            logger.error("Failed to get source", error=str(e), source_id=source_id)
            return None

    async def list_sources(
        self,
        project_id: str,
        user_id: str,
        status: Optional[SourceStatus] = None,
        source_type: Optional[SourceType] = None,
        search: Optional[str] = None,
        sort_by: SourceSortField = SourceSortField.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        limit: int = 50,
        offset: int = 0
    ) -> ListSourcesResponse:
        """List sources for a project with filtering and sorting"""
        try:
            # Build query
            query = self.supabase.table("project_sources").select(
                "*", count="exact"
            ).eq("project_id", project_id).eq("user_id", user_id)

            # Apply filters
            if status:
                query = query.eq("status", status.value)

            if source_type:
                query = query.eq("source_type", source_type.value)

            if search:
                query = query.ilike("title", f"%{search}%")

            # Apply sorting
            desc = sort_order == SortOrder.DESC
            query = query.order(sort_by.value, desc=desc)

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            result = query.execute()

            sources = [self._to_project_source(s) for s in result.data]
            total = result.count or 0

            return ListSourcesResponse(
                project_id=project_id,
                sources=sources,
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + len(sources)) < total
            )

        except Exception as e:
            logger.error("Failed to list sources", error=str(e), project_id=project_id)
            return ListSourcesResponse(
                project_id=project_id,
                sources=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

    def _to_project_source(self, data: Dict[str, Any]) -> ProjectSource:
        """Convert database row to ProjectSource model"""
        metadata = None
        if data.get("metadata"):
            try:
                metadata = SourceMetadata(**data["metadata"])
            except Exception:
                metadata = SourceMetadata(extra=data["metadata"])

        return ProjectSource(
            id=data["id"],
            project_id=data["project_id"],
            user_id=data["user_id"],
            title=data["title"],
            source_type=SourceType(data["source_type"]),
            url=data.get("url"),
            file_path=data.get("file_path"),
            file_name=data.get("file_name"),
            file_size=data.get("file_size"),
            mime_type=data.get("mime_type"),
            content_hash=data.get("content_hash"),
            status=SourceStatus(data["status"]),
            processing_progress=data.get("processing_progress", 0),
            processing_error=data.get("processing_error"),
            processing_started_at=datetime.fromisoformat(data["processing_started_at"]) if data.get("processing_started_at") else None,
            processing_completed_at=datetime.fromisoformat(data["processing_completed_at"]) if data.get("processing_completed_at") else None,
            retry_count=data.get("retry_count", 0),
            metadata=metadata,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    # ========================================================================
    # Source Updates
    # ========================================================================

    async def update_source_status(
        self,
        source_id: str,
        user_id: str,
        status: SourceStatus,
        progress: Optional[int] = None,
        error: Optional[str] = None
    ) -> bool:
        """Update source processing status"""
        try:
            update_data: Dict[str, Any] = {
                "status": status.value,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if progress is not None:
                update_data["processing_progress"] = min(max(progress, 0), 100)

            if error:
                update_data["processing_error"] = error

            if status == SourceStatus.PROCESSING:
                update_data["processing_started_at"] = datetime.utcnow().isoformat()
            elif status in (SourceStatus.READY, SourceStatus.FAILED):
                update_data["processing_completed_at"] = datetime.utcnow().isoformat()
                if status == SourceStatus.READY:
                    update_data["processing_progress"] = 100

            self.supabase.table("project_sources").update(update_data).eq(
                "id", source_id
            ).eq("user_id", user_id).execute()

            logger.info(
                "Source status updated",
                source_id=source_id,
                status=status.value,
                progress=progress
            )
            return True

        except Exception as e:
            logger.error("Failed to update source status", error=str(e), source_id=source_id)
            return False

    async def update_source_metadata(
        self,
        source_id: str,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update source title and metadata"""
        try:
            update_data: Dict[str, Any] = {
                "updated_at": datetime.utcnow().isoformat(),
            }

            if title:
                update_data["title"] = title[:500]

            if metadata:
                # Merge with existing metadata
                existing = self.supabase.table("project_sources").select(
                    "metadata"
                ).eq("id", source_id).execute()

                if existing.data:
                    current_metadata = existing.data[0].get("metadata", {}) or {}
                    current_metadata.update(metadata)
                    update_data["metadata"] = current_metadata

            self.supabase.table("project_sources").update(update_data).eq(
                "id", source_id
            ).eq("user_id", user_id).execute()

            return True

        except Exception as e:
            logger.error("Failed to update source metadata", error=str(e), source_id=source_id)
            return False

    # ========================================================================
    # Source Deletion
    # ========================================================================

    async def delete_source(
        self,
        source_id: str,
        user_id: str
    ) -> Tuple[bool, str]:
        """Delete a source and its associated data"""
        try:
            # Get source to find file path
            result = self.supabase.table("project_sources").select(
                "id, file_path, project_id"
            ).eq("id", source_id).eq("user_id", user_id).execute()

            if not result.data:
                return False, "Source not found"

            source = result.data[0]

            # Delete file from storage if exists
            if source.get("file_path"):
                try:
                    storage = self.supabase.storage.from_("documents")
                    storage.remove([source["file_path"]])
                except Exception as e:
                    logger.warning("Failed to delete file from storage", error=str(e))

            # Delete embeddings (cascade should handle this, but be explicit)
            self.supabase.table("source_embeddings").delete().eq(
                "source_id", source_id
            ).execute()

            # Delete source record
            self.supabase.table("project_sources").delete().eq(
                "id", source_id
            ).eq("user_id", user_id).execute()

            logger.info("Source deleted", source_id=source_id, project_id=source["project_id"])
            return True, "Source deleted successfully"

        except Exception as e:
            logger.error("Failed to delete source", error=str(e), source_id=source_id)
            return False, str(e)

    # ========================================================================
    # Source Retry
    # ========================================================================

    async def retry_source(
        self,
        source_id: str,
        user_id: str
    ) -> Tuple[bool, str, int]:
        """Retry processing a failed source"""
        try:
            # Get current source
            result = self.supabase.table("project_sources").select(
                "id, status, retry_count"
            ).eq("id", source_id).eq("user_id", user_id).execute()

            if not result.data:
                return False, "Source not found", 0

            source = result.data[0]

            if source["status"] != SourceStatus.FAILED.value:
                return False, "Only failed sources can be retried", source["retry_count"]

            if source["retry_count"] >= 3:
                return False, "Maximum retry attempts (3) exceeded", source["retry_count"]

            # Update source for retry
            new_retry_count = source["retry_count"] + 1
            self.supabase.table("project_sources").update({
                "status": SourceStatus.PENDING.value,
                "retry_count": new_retry_count,
                "processing_error": None,
                "processing_progress": 0,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", source_id).execute()

            # Queue Celery task for processing
            self._queue_source_processing(source_id, user_id)

            logger.info(
                "Source queued for retry",
                source_id=source_id,
                retry_count=new_retry_count
            )

            return True, "Source queued for reprocessing", new_retry_count

        except Exception as e:
            logger.error("Failed to retry source", error=str(e), source_id=source_id)
            return False, str(e), 0

    # ========================================================================
    # Capacity & Stats
    # ========================================================================

    async def check_capacity(
        self,
        project_id: str,
        user_id: str
    ) -> CapacityWarning:
        """Check project capacity and return warnings"""
        try:
            # Get source count and total size
            result = self.supabase.table("project_sources").select(
                "id, file_size"
            ).eq("project_id", project_id).eq("user_id", user_id).execute()

            current_count = len(result.data) if result.data else 0
            current_size = sum(s.get("file_size", 0) or 0 for s in (result.data or []))

            at_limit = current_count >= MAX_SOURCES_PER_PROJECT or current_size >= MAX_STORAGE_PER_PROJECT
            warning = (
                current_count >= int(MAX_SOURCES_PER_PROJECT * CAPACITY_WARNING_THRESHOLD) or
                current_size >= int(MAX_STORAGE_PER_PROJECT * CAPACITY_WARNING_THRESHOLD)
            )

            message = None
            if at_limit:
                message = "Project has reached capacity limit. Please delete some sources."
            elif warning:
                message = "Project is approaching capacity limit (80% used)."

            return CapacityWarning(
                at_limit=at_limit,
                warning=warning,
                current_count=current_count,
                max_count=MAX_SOURCES_PER_PROJECT,
                current_size_bytes=current_size,
                max_size_bytes=MAX_STORAGE_PER_PROJECT,
                message=message
            )

        except Exception as e:
            logger.error("Failed to check capacity", error=str(e), project_id=project_id)
            # Return safe defaults on error
            return CapacityWarning(
                at_limit=False,
                warning=False,
                current_count=0,
                current_size_bytes=0
            )

    async def get_project_stats(
        self,
        project_id: str,
        user_id: str
    ) -> ProjectSourceStats:
        """Get statistics for project sources"""
        try:
            result = self.supabase.table("project_sources").select(
                "id, status, source_type, file_size"
            ).eq("project_id", project_id).eq("user_id", user_id).execute()

            sources = result.data or []

            # Calculate counts
            status_counts = {
                SourceStatus.READY.value: 0,
                SourceStatus.PROCESSING.value: 0,
                SourceStatus.PENDING.value: 0,
                SourceStatus.FAILED.value: 0,
            }

            type_counts: Dict[str, int] = {}
            total_size = 0

            for s in sources:
                status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1
                type_counts[s["source_type"]] = type_counts.get(s["source_type"], 0) + 1
                total_size += s.get("file_size", 0) or 0

            return ProjectSourceStats(
                project_id=project_id,
                total_sources=len(sources),
                ready_count=status_counts[SourceStatus.READY.value],
                processing_count=status_counts[SourceStatus.PROCESSING.value],
                pending_count=status_counts[SourceStatus.PENDING.value],
                failed_count=status_counts[SourceStatus.FAILED.value],
                total_size_bytes=total_size,
                source_type_counts=type_counts
            )

        except Exception as e:
            logger.error("Failed to get project stats", error=str(e), project_id=project_id)
            return ProjectSourceStats(
                project_id=project_id,
                total_sources=0,
                ready_count=0,
                processing_count=0,
                pending_count=0,
                failed_count=0,
                total_size_bytes=0,
                source_type_counts={}
            )


# Singleton instance
_service_instance: Optional[ProjectSourcesService] = None


def get_project_sources_service() -> ProjectSourcesService:
    """Get or create the ProjectSourcesService singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ProjectSourcesService()
    return _service_instance
