"""
Empire v7.3 - CrewAI Asset Storage & Retrieval Service
Handles storage of CrewAI generated assets in database and B2 storage
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
import io

from app.core.supabase_client import get_supabase_client
from app.services.b2_storage import get_b2_service, B2Folder
from app.models.crewai_asset import (
    AssetStorageRequest,
    AssetUpdateRequest,
    AssetResponse,
    AssetListResponse,
    AssetRetrievalFilters,
    ContentFormat
)

logger = logging.getLogger(__name__)


class CrewAIAssetService:
    """Service for storing and retrieving CrewAI generated assets"""

    def __init__(self):
        self.supabase = get_supabase_client()
        self.b2_service = get_b2_service()

    async def store_asset(self, request: AssetStorageRequest) -> AssetResponse:
        """
        Store a CrewAI generated asset

        For text-based assets (text, markdown, html, json):
        - Content stored in database 'content' column
        - b2_path is None

        For file-based assets (pdf, docx, images):
        - Binary content uploaded to B2
        - b2_path contains B2 file path
        - Database content is None

        Path format: crewai/assets/{department}/{asset_type}/{execution_id}/{filename}

        Args:
            request: Asset storage request with content or file data

        Returns:
            AssetResponse with created asset details

        Raises:
            ValueError: If both content and file_content provided
            Exception: If storage fails
        """
        try:
            # Validate request
            if request.content and request.file_content:
                raise ValueError("Cannot provide both content and file_content")

            if not request.content and not request.file_content:
                raise ValueError("Must provide either content or file_content")

            # Prepare asset record
            b2_path = None
            file_size = None
            mime_type = None
            content_to_store = request.content

            # Handle file-based assets (upload to B2)
            if request.file_content:
                logger.info(
                    f"Uploading file-based asset to B2: {request.asset_name} "
                    f"(department={request.department.value}, type={request.asset_type.value})"
                )

                # Construct B2 path: crewai/assets/{department}/{asset_type}/{execution_id}/{filename}
                filename = f"{request.asset_name}.{request.content_format.value}"
                folder_path = f"{B2Folder.CREWAI_ASSETS.value}/{request.department.value}/{request.asset_type.value}/{request.execution_id}"

                # Upload to B2
                file_data = io.BytesIO(request.file_content)

                # Prepare metadata - B2 requires all values to be strings
                b2_metadata = {
                    "execution_id": str(request.execution_id),
                    "department": request.department.value,
                    "asset_type": request.asset_type.value,
                    "asset_name": request.asset_name
                }

                # Stringify user metadata values (B2 doesn't support bool/int/etc)
                for key, value in request.metadata.items():
                    b2_metadata[key] = str(value) if value is not None else ""

                upload_result = await self.b2_service.upload_file(
                    file_data=file_data,
                    filename=filename,
                    folder=folder_path,  # Pass folder path as string
                    content_type=self._get_mime_type(request.content_format),
                    metadata=b2_metadata
                )

                b2_path = upload_result["file_name"]
                file_size = upload_result["size"]
                mime_type = upload_result["content_type"]
                content_to_store = None  # Don't store binary content in DB

                logger.info(f"File uploaded to B2: {b2_path} ({file_size} bytes)")

            # Insert into database
            asset_data = {
                "execution_id": str(request.execution_id),
                "document_id": request.document_id,
                "department": request.department.value,
                "asset_type": request.asset_type.value,
                "asset_name": request.asset_name,
                "content": content_to_store,
                "content_format": request.content_format.value,
                "b2_path": b2_path,
                "file_size": file_size,
                "mime_type": mime_type or self._get_mime_type(request.content_format),
                "metadata": request.metadata,
                "confidence_score": request.confidence_score
            }

            response = self.supabase.table("crewai_generated_assets").insert(asset_data).execute()

            if not response.data:
                raise Exception("Failed to insert asset into database")

            asset_record = response.data[0]

            logger.info(
                f"Asset stored successfully: {asset_record['id']} "
                f"(type={request.asset_type.value}, b2_path={b2_path})"
            )

            # Return AssetResponse
            return AssetResponse(**asset_record)

        except Exception as e:
            logger.error(f"Failed to store asset: {e}")
            raise

    async def retrieve_assets(self, filters: AssetRetrievalFilters) -> AssetListResponse:
        """
        Retrieve assets with optional filtering

        Args:
            filters: Filter criteria and pagination params

        Returns:
            AssetListResponse with filtered assets

        Raises:
            Exception: If retrieval fails
        """
        try:
            # Start query
            query = self.supabase.table("crewai_generated_assets").select("*")

            # Apply filters
            filters_applied = {}

            if filters.execution_id:
                query = query.eq("execution_id", str(filters.execution_id))
                filters_applied["execution_id"] = str(filters.execution_id)

            if filters.department:
                query = query.eq("department", filters.department.value)
                filters_applied["department"] = filters.department.value

            if filters.asset_type:
                query = query.eq("asset_type", filters.asset_type.value)
                filters_applied["asset_type"] = filters.asset_type.value

            if filters.min_confidence is not None:
                query = query.gte("confidence_score", filters.min_confidence)
                filters_applied["min_confidence"] = filters.min_confidence

            if filters.max_confidence is not None:
                query = query.lte("confidence_score", filters.max_confidence)
                filters_applied["max_confidence"] = filters.max_confidence

            # Apply pagination (offset-based)
            query = query.range(filters.offset, filters.offset + filters.limit - 1)

            # Order by created_at descending (most recent first)
            query = query.order("created_at", desc=True)

            # Execute query
            response = query.execute()

            assets = [AssetResponse(**asset) for asset in response.data]
            total = len(response.data)  # Note: This is count for current page, not total across all pages

            logger.info(
                f"Retrieved {total} assets with filters: {filters_applied}"
            )

            return AssetListResponse(
                total=total,
                assets=assets,
                filters_applied=filters_applied
            )

        except Exception as e:
            logger.error(f"Failed to retrieve assets: {e}")
            raise

    async def get_asset_by_id(self, asset_id: UUID) -> Optional[AssetResponse]:
        """
        Get a single asset by ID

        Args:
            asset_id: Asset UUID

        Returns:
            AssetResponse or None if not found

        Raises:
            Exception: If retrieval fails
        """
        try:
            response = self.supabase.table("crewai_generated_assets")\
                .select("*")\
                .eq("id", str(asset_id))\
                .execute()

            if not response.data:
                logger.warning(f"Asset not found: {asset_id}")
                return None

            logger.info(f"Retrieved asset: {asset_id}")
            return AssetResponse(**response.data[0])

        except Exception as e:
            logger.error(f"Failed to get asset {asset_id}: {e}")
            raise

    async def update_asset(
        self,
        asset_id: UUID,
        update: AssetUpdateRequest
    ) -> AssetResponse:
        """
        Update asset confidence score and/or metadata

        Metadata is merged (not replaced) with existing metadata

        Args:
            asset_id: Asset UUID
            update: Update request with confidence/metadata

        Returns:
            Updated AssetResponse

        Raises:
            ValueError: If asset not found
            Exception: If update fails
        """
        try:
            # Get existing asset
            existing = await self.get_asset_by_id(asset_id)
            if not existing:
                raise ValueError(f"Asset not found: {asset_id}")

            # Prepare update data
            update_data = {}

            if update.confidence_score is not None:
                update_data["confidence_score"] = update.confidence_score

            if update.metadata is not None:
                # Merge metadata (preserve existing keys not in update)
                merged_metadata = {**existing.metadata, **update.metadata}
                update_data["metadata"] = merged_metadata

            if not update_data:
                logger.info(f"No updates provided for asset {asset_id}")
                return existing

            # Update database
            response = self.supabase.table("crewai_generated_assets")\
                .update(update_data)\
                .eq("id", str(asset_id))\
                .execute()

            if not response.data:
                raise Exception(f"Failed to update asset {asset_id}")

            logger.info(
                f"Asset updated: {asset_id} "
                f"(confidence={update.confidence_score}, metadata_keys={list(update.metadata.keys()) if update.metadata else []})"
            )

            return AssetResponse(**response.data[0])

        except Exception as e:
            logger.error(f"Failed to update asset {asset_id}: {e}")
            raise

    def _get_mime_type(self, format: ContentFormat) -> str:
        """Get MIME type for content format"""
        mime_types = {
            ContentFormat.TEXT: "text/plain",
            ContentFormat.MARKDOWN: "text/markdown",
            ContentFormat.HTML: "text/html",
            ContentFormat.JSON: "application/json",
            ContentFormat.PDF: "application/pdf",
            ContentFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ContentFormat.PNG: "image/png",
            ContentFormat.JPEG: "image/jpeg",
            ContentFormat.SVG: "image/svg+xml"
        }
        return mime_types.get(format, "application/octet-stream")

    async def get_signed_download_url(
        self,
        asset_id: UUID,
        valid_duration_seconds: int = 3600
    ) -> Optional[Dict[str, Any]]:
        """
        Get a signed download URL for a file-based asset

        For assets stored in B2 (file-based), generates a time-limited
        signed URL for secure download. Text-based assets (stored in DB)
        do not have signed URLs.

        Args:
            asset_id: Asset UUID
            valid_duration_seconds: How long the URL should be valid (default: 1 hour)

        Returns:
            dict with signed_url, expires_at, and asset metadata, or None if text-based

        Raises:
            ValueError: If asset not found
            Exception: If URL generation fails
        """
        try:
            # Get asset
            asset = await self.get_asset_by_id(asset_id)
            if not asset:
                raise ValueError(f"Asset not found: {asset_id}")

            # Text-based assets don't have B2 paths
            if not asset.b2_path:
                logger.info(
                    f"Asset {asset_id} is text-based (no B2 path), "
                    "signed URL not applicable"
                )
                return None

            # Generate signed URL from B2 service
            signed_url_info = await self.b2_service.get_signed_url_for_asset(
                b2_path=asset.b2_path,
                valid_duration_seconds=valid_duration_seconds
            )

            if signed_url_info:
                signed_url_info["asset_id"] = str(asset_id)
                signed_url_info["asset_name"] = asset.asset_name
                signed_url_info["mime_type"] = asset.mime_type
                signed_url_info["file_size"] = asset.file_size

            logger.info(
                f"Generated signed URL for asset {asset_id}, "
                f"expires at {signed_url_info['expires_at']}"
            )

            return signed_url_info

        except Exception as e:
            logger.error(f"Failed to get signed URL for asset {asset_id}: {e}")
            raise


# Singleton instance
_asset_service = None


def get_asset_service() -> CrewAIAssetService:
    """Get or create asset service singleton"""
    global _asset_service
    if _asset_service is None:
        _asset_service = CrewAIAssetService()
    return _asset_service
