"""
Empire v7.3 - File Upload API
Handles multi-file uploads with drag-and-drop support and B2 integration
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
from datetime import datetime
import os
from pathlib import Path

from app.services.b2_storage import get_b2_service
from app.services.file_validator import get_file_validator
from app.services.virus_scanner import get_virus_scanner
from app.services.metadata_extractor import get_metadata_extractor
from app.services.supabase_storage import get_supabase_storage
import tempfile
import shutil

logger = logging.getLogger(__name__)

# Optional Celery task import
try:
    from app.tasks.document_processing import submit_document_processing
    from app.celery_app import PRIORITY_HIGH, PRIORITY_NORMAL
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery not available - background processing disabled")

router = APIRouter()

# File upload constraints
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FILES_PER_UPLOAD = 10
ALLOWED_EXTENSIONS = {
    # Documents
    ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf",
    # Presentations
    ".ppt", ".pptx", ".key",
    # Spreadsheets
    ".xls", ".xlsx", ".csv",
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg",
    # Audio/Video
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".mkv",
    # Archives
    ".zip", ".tar", ".gz", ".7z"
}


def validate_file(file: UploadFile) -> tuple[bool, Optional[str]]:
    """
    Validate file size and type

    Returns:
        tuple: (is_valid, error_message)
    """
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{file_ext}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"

    # Check file size (if provided in headers)
    if file.size and file.size > MAX_FILE_SIZE:
        return False, f"File size ({file.size / (1024*1024):.2f}MB) exceeds maximum allowed size (100MB)"

    return True, None


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    folder: str = "pending/courses",
    process_immediately: bool = True,
    scan_for_malware: bool = False,
    force_upload: bool = False
):
    """
    Upload multiple files to B2 storage

    Args:
        files: List of files to upload (max 10, 100MB each)
        background_tasks: FastAPI background tasks
        folder: Destination folder in B2 (default: pending/courses)
        process_immediately: Whether to process files immediately (default: True)
        scan_for_malware: Whether to scan files with VirusTotal (default: False)
        force_upload: Force upload even if duplicate detected (default: False)

    Returns:
        JSON response with upload results

    Constraints:
        - Maximum 10 files per upload
        - Maximum 100MB per file
        - Allowed file types: PDF, DOC, DOCX, PPT, PPTX, images, audio, video, etc.
        - Malware scanning (optional): Scans with 70+ antivirus engines via VirusTotal
        - Duplicate detection: Files with matching SHA-256 hashes are flagged as duplicates unless force_upload=true
    """
    try:
        # Validate number of files
        if len(files) > MAX_FILES_PER_UPLOAD:
            raise HTTPException(
                status_code=400,
                detail=f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} files allowed per upload"
            )

        if len(files) == 0:
            raise HTTPException(
                status_code=400,
                detail="No files provided"
            )

        b2_service = get_b2_service()
        upload_results = []
        errors = []

        # Get file validator, virus scanner, metadata extractor, and Supabase storage
        file_validator = get_file_validator()
        virus_scanner = get_virus_scanner()
        metadata_extractor = get_metadata_extractor()
        supabase_storage = get_supabase_storage()

        for file in files:
            temp_file_path = None
            try:
                # Basic validation (size, extension check)
                is_valid, error_msg = validate_file(file)
                if not is_valid:
                    errors.append({
                        "filename": file.filename,
                        "error": error_msg
                    })
                    continue

                # Advanced validation (MIME type, file header)
                is_valid_advanced, advanced_error = file_validator.validate_file(
                    file.file,
                    file.filename,
                    max_size=MAX_FILE_SIZE
                )

                if not is_valid_advanced:
                    logger.warning(f"Advanced validation failed for {file.filename}: {advanced_error}")
                    errors.append({
                        "filename": file.filename,
                        "error": advanced_error
                    })
                    continue

                # Virus scanning (optional)
                if scan_for_malware:
                    logger.info(f"Scanning {file.filename} for malware...")

                    # Save to temporary file for scanning
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
                        temp_file_path = temp_file.name
                        shutil.copyfileobj(file.file, temp_file)

                    # Reset file position for subsequent upload
                    file.file.seek(0)

                    # Scan the file
                    is_clean, scan_error, scan_results = await virus_scanner.scan_file(temp_file_path)

                    if not is_clean:
                        logger.warning(f"Malware detected in {file.filename}: {scan_error}")
                        errors.append({
                            "filename": file.filename,
                            "error": f"Malware detected: {scan_error}"
                        })
                        continue

                    logger.info(f"File {file.filename} passed malware scan")

                # Extract metadata
                extracted_metadata = {}
                try:
                    # Create temp file if not already created (for virus scanning)
                    if temp_file_path is None:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
                            temp_file_path = temp_file.name
                            shutil.copyfileobj(file.file, temp_file)

                        # Reset file position for subsequent upload
                        file.file.seek(0)

                    # Extract metadata from temp file
                    logger.info(f"Extracting metadata from {file.filename}...")
                    extracted_metadata = metadata_extractor.extract_metadata(temp_file_path)
                    logger.info(f"Successfully extracted metadata from {file.filename}")

                except Exception as metadata_error:
                    logger.warning(f"Metadata extraction failed for {file.filename}: {metadata_error}")
                    extracted_metadata['metadata_extraction_error'] = str(metadata_error)

                # Check for duplicate by hash (exact duplicate detection)
                duplicate_file = None
                if extracted_metadata.get('file_hash') and not force_upload:
                    logger.info(f"Checking for duplicate of {file.filename} by hash...")
                    duplicate_file = await supabase_storage.check_duplicate_by_hash(extracted_metadata['file_hash'])

                    if duplicate_file:
                        logger.warning(f"Duplicate file detected: {file.filename} matches existing file {duplicate_file.get('filename')}")
                        upload_results.append({
                            "filename": file.filename,
                            "status": "duplicate",
                            "duplicate_of": {
                                "document_id": duplicate_file.get('document_id'),
                                "filename": duplicate_file.get('filename'),
                                "b2_url": duplicate_file.get('b2_url'),
                                "uploaded_at": duplicate_file.get('created_at')
                            },
                            "file_hash": extracted_metadata['file_hash'],
                            "message": f"File already exists as '{duplicate_file.get('filename')}'. Use 'force_upload=true' to upload anyway."
                        })
                        continue  # Skip to next file
                elif extracted_metadata.get('file_hash') and force_upload:
                    logger.info(f"Force upload enabled - skipping duplicate check for {file.filename}")

                # Check for similar filenames (fuzzy matching - warning only, doesn't block upload)
                similar_files = []
                try:
                    logger.info(f"Checking for similar filenames to {file.filename}...")
                    similar_files = await supabase_storage.find_similar_filenames(
                        filename=file.filename,
                        similarity_threshold=85.0,  # 85% similarity or higher
                        limit=3  # Top 3 most similar files
                    )
                    if similar_files:
                        logger.warning(f"Found {len(similar_files)} similar files to {file.filename}")
                except Exception as fuzzy_error:
                    logger.error(f"Error during fuzzy matching for {file.filename}: {fuzzy_error}")

                # Upload to B2
                logger.info(f"Processing upload: {file.filename} ({file.content_type})")

                result = await b2_service.upload_file(
                    file_data=file.file,
                    filename=file.filename,
                    folder=folder,
                    content_type=file.content_type,
                    metadata={
                        "original_filename": file.filename,
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "source": "web_ui"
                    }
                )

                # Store metadata in Supabase
                supabase_record = None
                try:
                    logger.info(f"Storing metadata in Supabase for {file.filename}...")
                    supabase_record = await supabase_storage.store_document_metadata(
                        file_id=result["file_id"],
                        filename=file.filename,
                        metadata=extracted_metadata,
                        b2_url=result["url"],
                        folder=folder,
                        update_if_duplicate=force_upload  # Update existing record if force_upload enabled
                    )
                    if supabase_record:
                        logger.info(f"Successfully stored metadata in Supabase for {file.filename}")
                    else:
                        logger.warning(f"Failed to store metadata in Supabase for {file.filename}")
                except Exception as supabase_error:
                    logger.error(f"Error storing metadata in Supabase for {file.filename}: {supabase_error}")

                # Prepare upload result
                upload_result = {
                    "filename": file.filename,
                    "file_id": result["file_id"],
                    "size": result["size"],
                    "url": result["url"],
                    "status": "uploaded",
                    "metadata": extracted_metadata,  # Include extracted metadata
                    "supabase_stored": supabase_record is not None  # Indicate if stored in Supabase
                }

                # Include similar files if found (fuzzy match warning)
                if similar_files:
                    upload_result["similar_files"] = [
                        {
                            "filename": sf.get('filename'),
                            "b2_url": sf.get('b2_url'),
                            "similarity_score": sf.get('similarity_score'),
                            "uploaded_at": sf.get('created_at')
                        }
                        for sf in similar_files
                    ]
                    upload_result["warning"] = f"Found {len(similar_files)} similar filename(s). These may be near-duplicates."

                upload_results.append(upload_result)

                # Queue for processing if requested and Celery is available
                if process_immediately and CELERY_AVAILABLE:
                    # User uploads get HIGH priority (7 out of 9)
                    submit_document_processing(
                        file_id=result["file_id"],
                        filename=file.filename,
                        b2_path=result["file_name"],
                        priority=PRIORITY_HIGH  # Prioritize user-uploaded files
                    )
                    logger.info(f"Queued {file.filename} for high-priority processing")
                elif process_immediately and not CELERY_AVAILABLE:
                    logger.warning(f"Celery not available - {file.filename} will not be auto-processed")

            except Exception as e:
                logger.error(f"Upload failed for {file.filename}: {e}")
                errors.append({
                    "filename": file.filename,
                    "error": str(e)
                })
            finally:
                # Clean up temporary file if it was created
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                        logger.debug(f"Cleaned up temporary file: {temp_file_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to clean up temporary file {temp_file_path}: {cleanup_error}")

        # Prepare response
        response = {
            "uploaded": len(upload_results),
            "failed": len(errors),
            "total": len(files),
            "results": upload_results,
            "timestamp": datetime.utcnow().isoformat()
        }

        if errors:
            response["errors"] = errors

        status_code = 200 if len(upload_results) > 0 else 400

        return JSONResponse(content=response, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/upload/allowed-types")
async def get_allowed_types():
    """
    Get list of allowed file types

    Returns:
        List of allowed file extensions
    """
    return {
        "allowed_extensions": sorted(list(ALLOWED_EXTENSIONS)),
        "max_file_size_mb": MAX_FILE_SIZE / (1024 * 1024),
        "max_files_per_upload": MAX_FILES_PER_UPLOAD
    }


@router.get("/upload/status/{file_id}")
async def get_upload_status(file_id: str):
    """
    Check status of an uploaded file

    Args:
        file_id: B2 file ID

    Returns:
        File status information
    """
    try:
        # TODO: Use b2_service to verify file exists
        # b2_service = get_b2_service()

        # TODO: Check processing status from database
        # For now, just return a status placeholder

        return {
            "file_id": file_id,
            "status": "uploaded",
            "message": "File successfully uploaded to B2"
        }

    except Exception as e:
        logger.error(f"Failed to get status for {file_id}: {e}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")


@router.get("/upload/list")
async def list_uploads(folder: str = "pending/courses", limit: int = 100):
    """
    List uploaded files in a folder

    Args:
        folder: Folder path (default: pending/courses)
        limit: Maximum number of files to return (default: 100)

    Returns:
        List of uploaded files
    """
    try:
        b2_service = get_b2_service()
        files = await b2_service.list_files(folder=folder, limit=limit)

        return {
            "folder": folder,
            "count": len(files),
            "files": files
        }

    except Exception as e:
        logger.error(f"Failed to list files in {folder}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/upload/{file_id}")
async def delete_upload(file_id: str, file_name: str):
    """
    Delete an uploaded file

    Args:
        file_id: B2 file ID
        file_name: Full file path in B2

    Returns:
        Deletion confirmation
    """
    try:
        b2_service = get_b2_service()
        await b2_service.delete_file(file_id, file_name)

        return {
            "file_id": file_id,
            "file_name": file_name,
            "status": "deleted",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to delete file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
