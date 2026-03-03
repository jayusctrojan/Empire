"""
Empire v7.3 - AI Studio Asset Management API Routes
Task 76: Create Asset Management API Routes

Endpoints:
- GET /api/studio/assets - List all assets (filterable)
- GET /api/studio/assets/stats - Get asset statistics
- GET /api/studio/assets/{asset_id} - Get asset details
- PATCH /api/studio/assets/{asset_id} - Update asset content
- POST /api/studio/assets/{asset_id}/publish - Publish draft
- POST /api/studio/assets/{asset_id}/archive - Archive asset
- GET /api/studio/assets/{asset_id}/history - Get version history
- POST /api/studio/assets/{asset_id}/reclassify - Change asset type
- GET /api/studio/assets/health - Health check
"""

import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog
import json

from app.middleware.auth import get_current_user
from app.services.asset_management_service import (
    AssetManagementService,
    Asset,
    AssetFilters,
    AssetVersion,
    AssetType,
    AssetStatus,
    AssetNotFoundError,
    AssetUpdateError,
    AssetReclassifyError,
    get_asset_management_service,
)
from app.services.asset_dedup_service import (
    AssetDedupAssetNotFoundError,
    AssetDedupService,
    get_asset_dedup_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/studio/assets", tags=["AI Studio Assets"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AssetResponse(BaseModel):
    """Asset details response"""
    id: str
    userId: str
    assetType: str
    department: str
    name: str
    title: str
    content: str
    format: str
    status: str
    sourceDocumentId: Optional[str] = None
    sourceDocumentTitle: Optional[str] = None
    classificationConfidence: Optional[float] = None
    classificationReasoning: Optional[str] = None
    keywordsMatched: List[str] = []
    secondaryDepartment: Optional[str] = None
    secondaryConfidence: Optional[float] = None
    assetDecisionReasoning: Optional[str] = None
    storagePath: Optional[str] = None
    version: int = 1
    parentVersionId: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    publishedAt: Optional[str] = None
    archivedAt: Optional[str] = None

    @classmethod
    def from_asset(cls, asset: Asset) -> "AssetResponse":
        """Convert Asset model to response"""
        return cls(
            id=asset.id,
            userId=asset.user_id,
            assetType=asset.asset_type,
            department=asset.department,
            name=asset.name,
            title=asset.title,
            content=asset.content,
            format=asset.format,
            status=asset.status,
            sourceDocumentId=asset.source_document_id,
            sourceDocumentTitle=asset.source_document_title,
            classificationConfidence=asset.classification_confidence,
            classificationReasoning=asset.classification_reasoning,
            keywordsMatched=asset.keywords_matched or [],
            secondaryDepartment=asset.secondary_department,
            secondaryConfidence=asset.secondary_confidence,
            assetDecisionReasoning=asset.asset_decision_reasoning,
            storagePath=asset.storage_path,
            version=asset.version,
            parentVersionId=asset.parent_version_id,
            createdAt=asset.created_at.isoformat() if asset.created_at else None,
            updatedAt=asset.updated_at.isoformat() if asset.updated_at else None,
            publishedAt=asset.published_at.isoformat() if asset.published_at else None,
            archivedAt=asset.archived_at.isoformat() if asset.archived_at else None,
        )


class AssetListResponse(BaseModel):
    """Response for listing assets"""
    assets: List[AssetResponse]
    total: int
    skip: int
    limit: int


class AssetUpdateRequest(BaseModel):
    """Request to update an asset"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|archived)$")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Policy Document",
                "content": "# Updated Content\n\nNew policy text here...",
            }
        }


class AssetReclassifyRequest(BaseModel):
    """Request to reclassify an asset"""
    newType: str = Field(
        ...,
        pattern="^(skill|command|agent|prompt|workflow)$",
        description="New asset type"
    )
    newDepartment: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional new department"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "newType": "prompt",
                "newDepartment": "sales-marketing"
            }
        }


class AssetVersionResponse(BaseModel):
    """Asset version details"""
    id: str
    version: int
    content: str
    createdAt: Optional[str] = None
    isCurrent: bool = False

    @classmethod
    def from_version(cls, version: AssetVersion) -> "AssetVersionResponse":
        return cls(
            id=version.id,
            version=version.version,
            content=version.content,
            createdAt=version.created_at.isoformat() if version.created_at else None,
            isCurrent=version.is_current,
        )


class AssetHistoryResponse(BaseModel):
    """Asset version history response"""
    asset: AssetResponse
    history: List[AssetVersionResponse]


class AssetStatsResponse(BaseModel):
    """Asset statistics response"""
    total: int
    byType: Dict[str, int]
    byStatus: Dict[str, int]
    byDepartment: Dict[str, int]


class DedupCheckRequest(BaseModel):
    """Request to check for duplicate assets"""
    content: str = Field(..., min_length=1)
    assetType: Optional[str] = Field(None, pattern="^(skill|command|agent|prompt|workflow)$")


class DedupMatchResponse(BaseModel):
    """A duplicate match"""
    id: str
    title: str
    name: str
    assetType: str
    department: str
    similarity: Optional[float] = None


class DedupCheckResponse(BaseModel):
    """Response from duplicate check"""
    contentHash: str
    exactMatches: List[DedupMatchResponse]
    nearMatches: List[DedupMatchResponse]
    hasDuplicates: bool


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    assetTypes: List[str]
    statusTypes: List[str]


# ============================================================================
# Dependencies
# ============================================================================

def get_service() -> AssetManagementService:
    """Dependency for asset management service"""
    return get_asset_management_service()


def get_dedup_service() -> AssetDedupService:
    """Dependency for dedup service"""
    return get_asset_dedup_service()


# ============================================================================
# List & Stats Endpoints
# ============================================================================

@router.get("", response_model=AssetListResponse)
async def list_assets(
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    department: Optional[str] = Query(None, description="Filter by department"),
    asset_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetListResponse:
    """
    List all assets for the current user with optional filtering.

    Assets can be filtered by type (skill, command, agent, prompt, workflow),
    department, status (draft, published, archived), and a text search query.
    """
    try:
        logger.info(
            "Listing assets",
            user_id=user_id,
            asset_type=asset_type,
            department=department,
            status=asset_status,
            search=search
        )

        filters = AssetFilters(
            asset_type=asset_type,
            department=department,
            status=asset_status,
            search_query=search
        )

        assets = await service.list_assets(
            user_id=user_id,
            filters=filters,
            skip=skip,
            limit=limit
        )

        return AssetListResponse(
            assets=[AssetResponse.from_asset(a) for a in assets],
            total=len(assets),
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error("Failed to list assets", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list assets: {str(e)}"
        )


@router.get("/stats", response_model=AssetStatsResponse)
async def get_asset_stats(
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetStatsResponse:
    """
    Get statistics about the user's assets.

    Returns counts by asset type, status, and department.
    """
    try:
        logger.info("Getting asset stats", user_id=user_id)

        stats = await service.get_asset_stats(user_id)

        return AssetStatsResponse(
            total=stats["total"],
            byType=stats["by_type"],
            byStatus=stats["by_status"],
            byDepartment=stats["by_department"]
        )

    except Exception as e:
        logger.error("Failed to get asset stats", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get asset stats: {str(e)}"
        )


# ============================================================================
# Dedup Endpoints
# ============================================================================

@router.post("/duplicates/check", response_model=DedupCheckResponse)
async def check_duplicates(
    request: DedupCheckRequest,
    user_id: str = Depends(get_current_user),
    dedup: AssetDedupService = Depends(get_dedup_service),
) -> DedupCheckResponse:
    """Check content for duplicate assets across all departments."""
    try:
        result = await dedup.check_duplicates(
            content=request.content,
            user_id=user_id,
            asset_type=request.assetType,
        )
        return _build_dedup_response(result)
    except Exception:
        logger.exception("Dedup check failed", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check duplicates",
        ) from None


def _build_dedup_response(result: Dict[str, Any]) -> DedupCheckResponse:
    """Convert service-layer dedup result (snake_case) to API response (camelCase)."""
    def _to_match(m: Dict[str, Any]) -> DedupMatchResponse:
        return DedupMatchResponse(
            id=m["id"],
            title=m["title"],
            name=m["name"],
            assetType=m["asset_type"],
            department=m["department"],
            similarity=m.get("similarity"),
        )

    return DedupCheckResponse(
        contentHash=result["content_hash"],
        exactMatches=[_to_match(m) for m in result["exact_matches"]],
        nearMatches=[_to_match(m) for m in result["near_matches"]],
        hasDuplicates=result["has_duplicates"],
    )


@router.get("/{asset_id}/duplicates", response_model=DedupCheckResponse)
async def find_asset_duplicates(
    asset_id: str,
    user_id: str = Depends(get_current_user),
    dedup: AssetDedupService = Depends(get_dedup_service),
) -> DedupCheckResponse:
    """Find duplicates of an existing asset."""
    try:
        result = await dedup.find_duplicates_for_asset(asset_id, user_id)
        return _build_dedup_response(result)
    except AssetDedupAssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        ) from None
    except Exception:
        logger.exception("Dedup check failed", asset_id=asset_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find duplicates",
        ) from None


# ============================================================================
# Asset CRUD Endpoints
# ============================================================================

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetResponse:
    """Get a specific asset by ID."""
    try:
        logger.info("Getting asset", asset_id=asset_id, user_id=user_id)

        asset = await service.get_asset(asset_id, user_id)
        return AssetResponse.from_asset(asset)

    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    except Exception as e:
        logger.error("Failed to get asset", asset_id=asset_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get asset: {str(e)}"
        )


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    request: AssetUpdateRequest,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetResponse:
    """
    Update asset content or metadata.

    If content is changed, a new version of the asset is created.
    Other metadata changes (title, name, status) update the existing record.
    """
    try:
        logger.info("Updating asset", asset_id=asset_id, user_id=user_id)

        updates = request.model_dump(exclude_unset=True)

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )

        updated_asset = await service.update_asset(asset_id, user_id, updates)
        return AssetResponse.from_asset(updated_asset)

    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    except AssetUpdateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update asset", asset_id=asset_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update asset: {str(e)}"
        )


# ============================================================================
# Status Change Endpoints
# ============================================================================

@router.post("/{asset_id}/publish", response_model=AssetResponse)
async def publish_asset(
    asset_id: str,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetResponse:
    """
    Publish a draft asset.

    Changes the asset status from 'draft' to 'published' and
    records the publication timestamp.
    """
    try:
        logger.info("Publishing asset", asset_id=asset_id, user_id=user_id)

        updated_asset = await service.publish_asset(asset_id, user_id)
        return AssetResponse.from_asset(updated_asset)

    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    except AssetUpdateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to publish asset", asset_id=asset_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish asset: {str(e)}"
        )


@router.post("/{asset_id}/archive", response_model=AssetResponse)
async def archive_asset(
    asset_id: str,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetResponse:
    """
    Archive an asset.

    Changes the asset status to 'archived' and records the archival timestamp.
    Archived assets are hidden from normal lists but can still be retrieved.
    """
    try:
        logger.info("Archiving asset", asset_id=asset_id, user_id=user_id)

        updated_asset = await service.archive_asset(asset_id, user_id)
        return AssetResponse.from_asset(updated_asset)

    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    except AssetUpdateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to archive asset", asset_id=asset_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive asset: {str(e)}"
        )


# ============================================================================
# Version History Endpoint
# ============================================================================

@router.get("/{asset_id}/history", response_model=AssetHistoryResponse)
async def get_asset_history(
    asset_id: str,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetHistoryResponse:
    """
    Get version history for an asset.

    Returns the current asset along with all previous versions,
    ordered by version number descending (newest first).
    """
    try:
        logger.info("Getting asset history", asset_id=asset_id, user_id=user_id)

        asset = await service.get_asset(asset_id, user_id)
        history = await service.get_asset_history(asset_id, user_id)

        return AssetHistoryResponse(
            asset=AssetResponse.from_asset(asset),
            history=[AssetVersionResponse.from_version(v) for v in history]
        )

    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    except Exception as e:
        logger.error("Failed to get asset history", asset_id=asset_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get asset history: {str(e)}"
        )


# ============================================================================
# Reclassification Endpoint
# ============================================================================

@router.post("/{asset_id}/reclassify", response_model=AssetResponse)
async def reclassify_asset(
    asset_id: str,
    request: AssetReclassifyRequest,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
) -> AssetResponse:
    """
    Reclassify an asset to a different type or department.

    Changes the asset type and automatically updates the format
    (e.g., skill -> YAML, prompt -> MD). Optionally updates the department.

    Reclassifications are logged for feedback and model improvement.
    """
    try:
        logger.info(
            "Reclassifying asset",
            asset_id=asset_id,
            user_id=user_id,
            new_type=request.newType,
            new_department=request.newDepartment
        )

        updated_asset = await service.reclassify_asset(
            asset_id=asset_id,
            user_id=user_id,
            new_type=request.newType,
            new_department=request.newDepartment
        )

        return AssetResponse.from_asset(updated_asset)

    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    except AssetReclassifyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to reclassify asset", asset_id=asset_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reclassify asset: {str(e)}"
        )


# ============================================================================
# Asset Test Endpoint
# ============================================================================

class AssetTestRequest(BaseModel):
    """Request to test an asset through the CKO pipeline"""
    query: str = Field(..., min_length=1, max_length=5000)


@router.post("/{asset_id}/test")
async def test_asset(
    asset_id: str,
    request: AssetTestRequest,
    user_id: str = Depends(get_current_user),
    service: AssetManagementService = Depends(get_service)
):
    """
    Test an asset by running a query through the CKO pipeline with
    the asset content injected as system context.

    Session persists across requests for multi-turn testing.
    First message injects asset content; subsequent messages send only the user query.

    Returns SSE stream with events: start, phase, token, sources, artifact, done, error.
    """
    # Validate asset exists and belongs to user
    try:
        asset = await service.get_asset(asset_id, user_id)
    except AssetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        ) from None

    async def generate():
        try:
            from app.services.studio_cko_conversation_service import (
                CKOConfig,
                get_cko_conversation_service,
            )

            cko_service = get_cko_conversation_service()

            # Get or create persistent test session
            session = await cko_service.get_or_create_asset_test_session(
                user_id=user_id,
                asset_id=asset_id,
                asset_title=asset.title,
            )

            yield f"event: start\ndata: {json.dumps({'session_id': session.id, 'asset_id': asset_id})}\n\n"

            # First message: inject full asset context
            # Subsequent messages: send only the user query
            # Note: message_count could be stale if a prior stream_message failed
            # after saving the user msg but before _update_session_metadata.
            # Re-injecting context in that case is harmless (slightly noisy but safe).
            if session.message_count == 0:
                message = (
                    f"You are testing the following {asset.asset_type} asset.\n"
                    f"Asset Name: {asset.name}\n"
                    f"Asset Title: {asset.title}\n"
                    f"Department: {asset.department}\n"
                    f"Format: {asset.format}\n"
                    f"---\n"
                    f"Asset Content:\n{asset.content}\n"
                    f"---\n\n"
                    f"User's test query: {request.query}"
                )
            else:
                message = request.query

            config = CKOConfig()

            async for event in cko_service.stream_message(
                session_id=session.id,
                user_id=user_id,
                message=message,
                config=config
            ):
                event_type = event.get("type", "unknown")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

        except Exception:
            logger.exception(
                "Asset test streaming error",
                asset_id=asset_id,
                user_id=user_id,
            )
            yield f"event: error\ndata: {json.dumps({'error': 'An internal error occurred during asset test'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Test Message Management
# ============================================================================

@router.get("/{asset_id}/test/messages")
async def get_test_messages(
    asset_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get previous test conversation messages for an asset."""
    try:
        from app.services.studio_cko_conversation_service import get_cko_conversation_service

        cko_service = get_cko_conversation_service()
        session_id, messages = await cko_service.get_asset_test_messages(user_id, asset_id)

        if session_id is None:
            return {"sessionId": None, "messages": []}

        return {
            "sessionId": session_id,
            "messages": [m.to_dict() for m in messages],
        }

    except Exception:
        logger.exception("Failed to get test messages", asset_id=asset_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get test messages",
        ) from None


@router.delete("/{asset_id}/test")
async def clear_test_session(
    asset_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete test session and all messages for an asset."""
    try:
        from app.services.studio_cko_conversation_service import get_cko_conversation_service

        cko_service = get_cko_conversation_service()

        # Find session to save memory from (before deleting)
        session_id = await cko_service.find_test_session_id(user_id, asset_id)

        # Await memory save before deleting to avoid race (delete could remove messages)
        if session_id:
            try:
                await asyncio.wait_for(
                    cko_service.save_test_session_memory(session_id, user_id, asset_id),
                    timeout=30.0,
                )
            except Exception:
                logger.exception("save_test_session_memory failed", asset_id=asset_id)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to save test session memory; session was not cleared",
                ) from None

        deleted = await cko_service.delete_asset_test_session(user_id, asset_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to clear test session", asset_id=asset_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear test session",
        ) from None
    else:
        return {"deleted": deleted}


@router.get("/{asset_id}/test/context")
async def get_test_context_info(
    asset_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get lightweight context info for a test session."""
    try:
        from app.services.studio_cko_conversation_service import get_cko_conversation_service

        cko_service = get_cko_conversation_service()

        row = await cko_service.get_test_session_info(user_id, asset_id)

        if not row:
            return {
                "sessionId": None,
                "messageCount": 0,
                "approxTokens": 0,
                "createdAt": None,
            }

        msg_count = row.get("message_count", 0)

        return {
            "sessionId": row["id"],
            "messageCount": msg_count,
            "approxTokens": msg_count * 150 if msg_count > 0 else 0,
            "createdAt": row.get("created_at"),
        }
    except Exception:
        logger.exception("Failed to get test context info", asset_id=asset_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get test context info",
        ) from None


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the asset management service.

    Returns available asset types and status values.
    """
    return HealthResponse(
        status="healthy",
        service="AI Studio Asset Management",
        assetTypes=[t.value for t in AssetType],
        statusTypes=[s.value for s in AssetStatus]
    )
