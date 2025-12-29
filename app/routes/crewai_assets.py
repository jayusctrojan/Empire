"""
Empire v7.3 - CrewAI Asset API Routes
REST endpoints for storing and retrieving CrewAI generated assets
"""

from fastapi import APIRouter, HTTPException, status, Depends
from uuid import UUID
from typing import Optional
import logging

from app.models.crewai_asset import (
    AssetStorageRequest,
    AssetUpdateRequest,
    AssetResponse,
    AssetListResponse,
    AssetRetrievalFilters,
    Department,
    AssetType
)
from app.services.crewai_asset_service import get_asset_service, CrewAIAssetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crewai/assets", tags=["CrewAI Assets"])


def get_service() -> CrewAIAssetService:
    """Dependency for asset service"""
    return get_asset_service()


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store CrewAI Generated Asset",
    description="""
    Store a CrewAI generated asset (summary, analysis, report, chart, etc.)

    **For text-based assets**: Provide `content` field (stored in database)
    **For file-based assets**: Provide `file_content` as bytes (uploaded to B2)

    B2 Path Format: `crewai/assets/{department}/{asset_type}/{execution_id}/{filename}`
    """
)
async def store_asset(
    request: AssetStorageRequest,
    service: CrewAIAssetService = Depends(get_service)
) -> AssetResponse:
    """
    Store a new CrewAI generated asset

    **Request Body**:
    - `execution_id` (UUID, required): CrewAI execution ID
    - `department` (enum, required): Department that generated the asset
    - `asset_type` (enum, required): Type of asset (summary, analysis, report, etc.)
    - `asset_name` (str, required): Human-readable asset name
    - `content` (str, optional): Text content (for text-based assets)
    - `content_format` (enum, required): Format (text, markdown, html, json, pdf, etc.)
    - `file_content` (bytes, optional): Binary file content (for file-based assets)
    - `metadata` (dict, optional): Additional metadata
    - `confidence_score` (float, optional): Confidence score (0-1)

    **Response**: AssetResponse with created asset details
    """
    try:
        asset = await service.store_asset(request)
        logger.info(f"Asset stored via API: {asset.id} (type={asset.asset_type})")
        return asset

    except ValueError as e:
        logger.error(f"Invalid asset storage request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Failed to store asset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store asset: {str(e)}"
        )


@router.get(
    "/",
    response_model=AssetListResponse,
    summary="Retrieve Assets with Filters",
    description="""
    Retrieve CrewAI generated assets with optional filtering and pagination

    **Filters**:
    - `execution_id`: Filter by CrewAI execution
    - `department`: Filter by department (marketing, legal, hr, etc.)
    - `asset_type`: Filter by type (summary, analysis, report, etc.)
    - `min_confidence`: Minimum confidence score (0-1)
    - `max_confidence`: Maximum confidence score (0-1)
    - `limit`: Max results (default 100, max 1000)
    - `offset`: Pagination offset (default 0)
    """
)
async def retrieve_assets(
    execution_id: Optional[UUID] = None,
    department: Optional[Department] = None,
    asset_type: Optional[AssetType] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
    service: CrewAIAssetService = Depends(get_service)
) -> AssetListResponse:
    """
    Retrieve assets with optional filtering

    **Query Parameters**:
    - `execution_id` (UUID, optional): Filter by execution ID
    - `department` (enum, optional): Filter by department
    - `asset_type` (enum, optional): Filter by asset type
    - `min_confidence` (float, optional): Minimum confidence score
    - `max_confidence` (float, optional): Maximum confidence score
    - `limit` (int, optional): Max results (default 100, max 1000)
    - `offset` (int, optional): Pagination offset (default 0)

    **Response**: AssetListResponse with filtered assets and applied filters
    """
    try:
        filters = AssetRetrievalFilters(
            execution_id=execution_id,
            department=department,
            asset_type=asset_type,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            limit=limit,
            offset=offset
        )

        result = await service.retrieve_assets(filters)
        logger.info(
            f"Retrieved {result.total} assets via API with filters: {result.filters_applied}"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to retrieve assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve assets: {str(e)}"
        )


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Get Single Asset by ID",
    description="Retrieve a specific asset by its UUID"
)
async def get_asset(
    asset_id: UUID,
    service: CrewAIAssetService = Depends(get_service)
) -> AssetResponse:
    """
    Get a single asset by ID

    **Path Parameters**:
    - `asset_id` (UUID): Asset ID

    **Response**: AssetResponse with asset details

    **Errors**:
    - 404: Asset not found
    """
    try:
        asset = await service.get_asset_by_id(asset_id)

        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset not found: {asset_id}"
            )

        logger.info(f"Retrieved asset via API: {asset_id}")
        return asset

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get asset {asset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get asset: {str(e)}"
        )


@router.patch(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Update Asset Confidence/Metadata",
    description="""
    Update an asset's confidence score and/or metadata

    **Metadata Merge Behavior**: New metadata is merged with existing metadata
    (existing keys are preserved unless explicitly overwritten)
    """
)
async def update_asset(
    asset_id: UUID,
    update: AssetUpdateRequest,
    service: CrewAIAssetService = Depends(get_service)
) -> AssetResponse:
    """
    Update asset confidence score and/or metadata

    **Path Parameters**:
    - `asset_id` (UUID): Asset ID

    **Request Body**:
    - `confidence_score` (float, optional): New confidence score (0-1)
    - `metadata` (dict, optional): Metadata to merge (existing keys preserved)

    **Response**: Updated AssetResponse

    **Errors**:
    - 404: Asset not found
    - 400: Invalid update request
    """
    try:
        asset = await service.update_asset(asset_id, update)
        logger.info(f"Updated asset via API: {asset_id}")
        return asset

    except ValueError as e:
        logger.error(f"Invalid update for asset {asset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Failed to update asset {asset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update asset: {str(e)}"
        )


@router.get(
    "/execution/{execution_id}",
    response_model=AssetListResponse,
    summary="Get All Assets for Execution",
    description="Convenience endpoint to get all assets for a specific CrewAI execution"
)
async def get_execution_assets(
    execution_id: UUID,
    service: CrewAIAssetService = Depends(get_service)
) -> AssetListResponse:
    """
    Get all assets for a specific execution

    **Path Parameters**:
    - `execution_id` (UUID): CrewAI execution ID

    **Response**: AssetListResponse with all assets for the execution
    """
    try:
        filters = AssetRetrievalFilters(
            execution_id=execution_id,
            limit=1000  # Get all assets for execution
        )

        result = await service.retrieve_assets(filters)
        logger.info(
            f"Retrieved {result.total} assets for execution {execution_id} via API"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to get assets for execution {execution_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve execution assets: {str(e)}"
        )


@router.get(
    "/{asset_id}/download-url",
    summary="Get Signed Download URL",
    description="""
    Generate a time-limited signed download URL for a file-based asset

    **Only applicable for file-based assets** stored in B2 (PDF, DOCX, images, etc.)
    Text-based assets (stored in database) will return null.

    Default expiration: 1 hour (3600 seconds)
    Maximum expiration: 1 week (604800 seconds)
    """
)
async def get_asset_download_url(
    asset_id: UUID,
    valid_duration_seconds: int = 3600,
    service: CrewAIAssetService = Depends(get_service)
):
    """
    Get a signed download URL for a file-based asset

    **Path Parameters**:
    - `asset_id` (UUID): Asset ID

    **Query Parameters**:
    - `valid_duration_seconds` (int, optional): URL validity in seconds (default: 3600, max: 604800)

    **Response**: Object with signed_url, expires_at, and asset metadata

    **Errors**:
    - 404: Asset not found
    - 400: Invalid duration or text-based asset
    """
    try:
        # Validate duration
        if valid_duration_seconds < 60:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="valid_duration_seconds must be at least 60 seconds"
            )

        if valid_duration_seconds > 604800:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="valid_duration_seconds cannot exceed 604800 (1 week)"
            )

        signed_url_info = await service.get_signed_download_url(
            asset_id=asset_id,
            valid_duration_seconds=valid_duration_seconds
        )

        if signed_url_info is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Asset is text-based and does not have a downloadable file. Use GET /{asset_id} to retrieve content."
            )

        logger.info(f"Generated signed URL for asset {asset_id} via API")
        return signed_url_info

    except ValueError as e:
        logger.error(f"Asset not found: {asset_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to generate signed URL for asset {asset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )
