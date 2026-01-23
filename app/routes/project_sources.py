"""
Empire v7.3 - Project Sources API Routes
CRUD endpoints for NotebookLM-style project sources

Task 60: Implement Source CRUD API endpoints
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query, status
from fastapi.responses import JSONResponse
import structlog

from app.middleware.auth import get_current_user
from app.services.project_sources_service import (
    ProjectSourcesService,
    get_project_sources_service,
)
from app.models.project_sources import (
    SourceType,
    SourceStatus,
    SourceSortField,
    SortOrder,
    AddSourceRequest,
    AddMultipleSourcesRequest,
    UpdateSourceRequest,
    ProjectSource,
    AddSourceResponse,
    AddMultipleSourcesResponse,
    ListSourcesResponse,
    DeleteSourceResponse,
    RetrySourceResponse,
    ProjectSourceStats,
    CapacityWarning,
    CapacityExceededResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Project Sources"])


# ============================================================================
# Dependencies
# ============================================================================

def get_service() -> ProjectSourcesService:
    """Dependency for project sources service"""
    return get_project_sources_service()


# ============================================================================
# Source Creation Endpoints
# ============================================================================

@router.post(
    "/{project_id}/sources/upload",
    response_model=AddSourceResponse,
    responses={
        429: {
            "model": CapacityExceededResponse,
            "description": "Project capacity exceeded"
        }
    }
)
async def upload_file_source(
    project_id: str,
    file: UploadFile = File(..., description="File to upload as source"),
    title: Optional[str] = Form(None, description="Optional custom title"),
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> AddSourceResponse:
    """
    Upload a file as a project source.

    Supports 40+ file types including:
    - Documents: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, RTF
    - Images: PNG, JPG, GIF, WebP, BMP
    - Audio: MP3, WAV, M4A, OGG, FLAC
    - Video: MP4, MOV, AVI, MKV, WebM
    - Archives: ZIP, TAR, GZ, 7Z, RAR

    Maximum file size: 100MB
    Maximum sources per project: 100
    Maximum storage per project: 500MB

    **Returns 429 Too Many Requests when capacity exceeded.**
    """
    try:
        logger.info(
            "File source upload request",
            project_id=project_id,
            filename=file.filename,
            content_type=file.content_type,
            user_id=user_id
        )

        # Task 68: Check capacity before processing
        capacity = await service.check_capacity(project_id, user_id)
        if capacity.at_limit:
            logger.warning(
                "Capacity limit reached - blocking upload",
                project_id=project_id,
                current_count=capacity.current_count,
                current_size=capacity.current_size_bytes
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=CapacityExceededResponse(
                    message="Project has reached maximum capacity. Please delete some sources before adding new ones.",
                    capacity=capacity
                ).model_dump()
            )

        # Read file content
        content = await file.read()

        result = await service.add_file_source(
            project_id=project_id,
            user_id=user_id,
            file_content=content,
            filename=file.filename or "unknown",
            mime_type=file.content_type,
            title=title
        )

        if not result.success:
            # Check if this was a capacity error from storage check
            if "storage limit" in (result.error or "").lower() or "source limit" in (result.error or "").lower():
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content=CapacityExceededResponse(
                        message=result.error or "Capacity exceeded",
                        capacity=capacity
                    ).model_dump()
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to upload file"
            )

        # Task 68: Add capacity warning to successful response if approaching limit
        if capacity.warning:
            result.capacity_warning = capacity

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload failed", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.post(
    "/{project_id}/sources/url",
    response_model=AddSourceResponse,
    responses={
        429: {
            "model": CapacityExceededResponse,
            "description": "Project capacity exceeded"
        }
    }
)
async def add_url_source(
    project_id: str,
    request: AddSourceRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> AddSourceResponse:
    """
    Add a URL source to a project.

    Supports:
    - Website URLs (articles, documentation, etc.)
    - YouTube URLs (video transcripts will be extracted)

    YouTube URLs are automatically detected from:
    - youtube.com/watch?v=...
    - youtu.be/...
    - youtube.com/embed/...

    **Returns 429 Too Many Requests when capacity exceeded.**
    """
    try:
        logger.info(
            "URL source add request",
            project_id=project_id,
            url=request.url[:100],
            user_id=user_id
        )

        # Task 68: Check capacity before processing
        capacity = await service.check_capacity(project_id, user_id)
        if capacity.at_limit:
            logger.warning(
                "Capacity limit reached - blocking URL add",
                project_id=project_id,
                current_count=capacity.current_count
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=CapacityExceededResponse(
                    message="Project has reached maximum capacity. Please delete some sources before adding new ones.",
                    capacity=capacity
                ).model_dump()
            )

        result = await service.add_url_source(
            project_id=project_id,
            user_id=user_id,
            url=request.url,
            title=request.title
        )

        if not result.success:
            # Check if this was a capacity error
            if "source limit" in (result.error or "").lower():
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content=CapacityExceededResponse(
                        message=result.error or "Capacity exceeded",
                        capacity=capacity
                    ).model_dump()
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Failed to add URL"
            )

        # Task 68: Add capacity warning to successful response if approaching limit
        if capacity.warning:
            result.capacity_warning = capacity

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("URL add failed", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add URL: {str(e)}"
        )


@router.post(
    "/{project_id}/sources/urls",
    response_model=AddMultipleSourcesResponse,
    responses={
        429: {
            "model": CapacityExceededResponse,
            "description": "Project capacity exceeded"
        }
    }
)
async def add_multiple_url_sources(
    project_id: str,
    request: AddMultipleSourcesRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> AddMultipleSourcesResponse:
    """
    Add multiple URL sources to a project at once.

    Maximum 20 URLs per request.
    Each URL is processed independently - failures don't affect other URLs.

    **Returns 429 Too Many Requests when capacity exceeded.**
    """
    try:
        logger.info(
            "Multiple URL sources add request",
            project_id=project_id,
            url_count=len(request.urls),
            user_id=user_id
        )

        # Task 68: Check capacity before processing any URLs
        capacity = await service.check_capacity(project_id, user_id)
        if capacity.at_limit:
            logger.warning(
                "Capacity limit reached - blocking batch URL add",
                project_id=project_id,
                current_count=capacity.current_count,
                requested_count=len(request.urls)
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=CapacityExceededResponse(
                    message="Project has reached maximum capacity. Please delete some sources before adding new ones.",
                    capacity=capacity
                ).model_dump()
            )

        # Check if adding all URLs would exceed limit
        remaining_slots = capacity.max_count - capacity.current_count
        if len(request.urls) > remaining_slots:
            logger.warning(
                "Batch add would exceed capacity",
                project_id=project_id,
                remaining_slots=remaining_slots,
                requested_count=len(request.urls)
            )
            # Continue with partial add up to remaining slots
            request.urls = request.urls[:remaining_slots]

        results: List[AddSourceResponse] = []
        added = 0
        failed = 0

        for url in request.urls:
            result = await service.add_url_source(
                project_id=project_id,
                user_id=user_id,
                url=url
            )
            results.append(result)
            if result.success:
                added += 1
            else:
                failed += 1

        # Get updated capacity for warning
        updated_capacity = await service.check_capacity(project_id, user_id)

        message = f"Added {added} of {len(request.urls)} sources"
        if updated_capacity.warning:
            message += f". Warning: Project is at {int(updated_capacity.current_count / updated_capacity.max_count * 100)}% capacity."

        return AddMultipleSourcesResponse(
            success=added > 0,
            total=len(request.urls),
            added=added,
            failed=failed,
            sources=results,
            message=message
        )

    except Exception as e:
        logger.error("Multiple URL add failed", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add URLs: {str(e)}"
        )


# ============================================================================
# Source Retrieval Endpoints
# ============================================================================

@router.get("/{project_id}/sources", response_model=ListSourcesResponse)
async def list_project_sources(
    project_id: str,
    status_filter: Optional[SourceStatus] = Query(None, alias="status"),
    source_type: Optional[SourceType] = Query(None, alias="type"),
    search: Optional[str] = Query(None, max_length=200),
    sort_by: SourceSortField = Query(SourceSortField.CREATED_AT),
    sort_order: SortOrder = Query(SortOrder.DESC),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> ListSourcesResponse:
    """
    List all sources in a project with filtering and sorting.

    Filters:
    - status: pending, processing, ready, failed
    - type: pdf, docx, youtube, website, etc.
    - search: search in title

    Sorting:
    - sort_by: created_at, title, source_type, status, file_size
    - sort_order: asc, desc

    Pagination:
    - limit: 1-100 (default: 50)
    - offset: >= 0 (default: 0)
    """
    try:
        return await service.list_sources(
            project_id=project_id,
            user_id=user_id,
            status=status_filter,
            source_type=source_type,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error("List sources failed", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sources: {str(e)}"
        )


# NOTE: Static routes (/stats, /capacity) MUST be defined before parameterized routes (/{source_id})
# to prevent FastAPI from matching "stats" or "capacity" as a source_id

@router.get("/{project_id}/sources/stats", response_model=ProjectSourceStats)
async def get_project_source_stats(
    project_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> ProjectSourceStats:
    """
    Get statistics for project sources.

    Returns counts by status and type, plus total storage used.
    """
    try:
        return await service.get_project_stats(
            project_id=project_id,
            user_id=user_id
        )

    except Exception as e:
        logger.error("Get stats failed", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/{project_id}/sources/capacity", response_model=CapacityWarning)
async def check_project_capacity(
    project_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> CapacityWarning:
    """
    Check project capacity and get warnings.

    Returns:
    - Current source count vs max (100)
    - Current storage vs max (500MB)
    - Warning at 80% capacity
    - Blocked at 100% capacity
    """
    try:
        return await service.check_capacity(
            project_id=project_id,
            user_id=user_id
        )

    except Exception as e:
        logger.error("Check capacity failed", error=str(e), project_id=project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check capacity: {str(e)}"
        )


@router.get("/{project_id}/sources/{source_id}", response_model=ProjectSource)
async def get_source(
    project_id: str,
    source_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> ProjectSource:
    """
    Get details of a specific source.
    """
    try:
        source = await service.get_source(source_id=source_id, user_id=user_id)

        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found"
            )

        if source.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found in this project"
            )

        return source

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get source failed", error=str(e), source_id=source_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get source: {str(e)}"
        )


# ============================================================================
# Source Update Endpoints
# ============================================================================

@router.patch("/{project_id}/sources/{source_id}", response_model=ProjectSource)
async def update_source(
    project_id: str,
    source_id: str,
    request: UpdateSourceRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> ProjectSource:
    """
    Update source title or metadata.
    """
    try:
        # Verify source exists
        source = await service.get_source(source_id=source_id, user_id=user_id)
        if not source or source.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found"
            )

        success = await service.update_source_metadata(
            source_id=source_id,
            user_id=user_id,
            title=request.title,
            metadata=request.metadata
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update source"
            )

        # Return updated source
        updated_source = await service.get_source(source_id=source_id, user_id=user_id)
        if not updated_source:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated source"
            )

        return updated_source

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update source failed", error=str(e), source_id=source_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source: {str(e)}"
        )


# ============================================================================
# Source Deletion Endpoints
# ============================================================================

@router.delete("/{project_id}/sources/{source_id}", response_model=DeleteSourceResponse)
async def delete_source(
    project_id: str,
    source_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> DeleteSourceResponse:
    """
    Delete a source from the project.

    This will:
    - Delete the source record
    - Delete associated embeddings
    - Delete the file from storage (if applicable)
    """
    try:
        # Verify source exists in project
        source = await service.get_source(source_id=source_id, user_id=user_id)
        if not source or source.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found"
            )

        success, message = await service.delete_source(
            source_id=source_id,
            user_id=user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )

        return DeleteSourceResponse(
            success=True,
            source_id=source_id,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete source failed", error=str(e), source_id=source_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete source: {str(e)}"
        )


# ============================================================================
# Source Retry Endpoints
# ============================================================================

@router.post("/{project_id}/sources/{source_id}/retry", response_model=RetrySourceResponse)
async def retry_failed_source(
    project_id: str,
    source_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectSourcesService = Depends(get_service)
) -> RetrySourceResponse:
    """
    Retry processing a failed source.

    Only sources with status 'failed' can be retried.
    Maximum 3 retry attempts per source.
    """
    try:
        # Verify source exists in project
        source = await service.get_source(source_id=source_id, user_id=user_id)
        if not source or source.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found"
            )

        success, message, retry_count = await service.retry_source(
            source_id=source_id,
            user_id=user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return RetrySourceResponse(
            success=True,
            source_id=source_id,
            retry_count=retry_count,
            status=SourceStatus.PENDING,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Retry source failed", error=str(e), source_id=source_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry source: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/sources/health", tags=["Health"])
async def project_sources_health():
    """Health check for project sources service"""
    return {
        "status": "healthy",
        "service": "project_sources",
        "max_file_size_mb": 100,
        "max_sources_per_project": 100,
        "max_storage_per_project_mb": 500
    }
