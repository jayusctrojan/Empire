"""
Empire v7.3 - Artifact API Routes
Phase 3: Document artifact management

Endpoints:
- GET /api/studio/artifacts - List user's artifacts
- GET /api/studio/artifacts/{id} - Get artifact metadata
- GET /api/studio/artifacts/{id}/download - Download artifact file
- DELETE /api/studio/artifacts/{id} - Delete artifact
"""

import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog
from io import BytesIO
from datetime import datetime

from app.middleware.auth import get_current_user
from app.services.supabase_storage import get_supabase_storage
from app.services.b2_storage import get_b2_service, B2Folder

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/studio/artifacts", tags=["AI Studio Artifacts"])


# ============================================================================
# Response Models
# ============================================================================

class ArtifactResponse(BaseModel):
    id: str
    messageId: Optional[str] = None
    sessionId: str
    title: str
    format: str
    mimeType: str
    sizeBytes: int
    storageUrl: Optional[str] = None
    previewMarkdown: Optional[str] = None
    summary: Optional[str] = None
    intent: Optional[str] = None
    contentBlockCount: int = 0
    createdAt: str
    updatedAt: str


class ArtifactListResponse(BaseModel):
    artifacts: List[ArtifactResponse]
    total: int


# ============================================================================
# Helper
# ============================================================================

def _get_supabase():
    return get_supabase_storage()


def _row_to_response(row: dict) -> ArtifactResponse:
    return ArtifactResponse(
        id=row["id"],
        messageId=row.get("message_id"),
        sessionId=row["session_id"],
        title=row["title"],
        format=row["format"],
        mimeType=row["mime_type"],
        sizeBytes=row.get("size_bytes", 0),
        storageUrl=row.get("storage_url"),
        previewMarkdown=row.get("preview_markdown"),
        summary=row.get("summary"),
        intent=row.get("intent"),
        contentBlockCount=row.get("content_block_count", 0),
        createdAt=row.get("created_at", ""),
        updatedAt=row.get("updated_at", ""),
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    session_id: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
):
    """List user's artifacts, optionally filtered by session or format."""
    try:
        supabase = _get_supabase()
        query = (
            supabase.supabase.table("studio_cko_artifacts")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )

        if session_id:
            query = query.eq("session_id", session_id)
        if format:
            query = query.eq("format", format)

        result = await asyncio.to_thread(
            lambda: query.range(offset, offset + limit - 1).execute()
        )

        artifacts = [_row_to_response(row) for row in (result.data or [])]
        total = result.count or len(artifacts)

        return ArtifactListResponse(artifacts=artifacts, total=total)

    except Exception as e:
        logger.error("Failed to list artifacts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list artifacts",
        ) from e


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get artifact metadata."""
    try:
        supabase = _get_supabase()
        result = await asyncio.to_thread(
            lambda: supabase.supabase.table("studio_cko_artifacts")
            .select("*")
            .eq("id", artifact_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        return _row_to_response(result.data[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get artifact", artifact_id=artifact_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get artifact",
        ) from e


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    user_id: str = Depends(get_current_user),
):
    """Download artifact file from B2 storage."""
    try:
        supabase = _get_supabase()
        result = await asyncio.to_thread(
            lambda: supabase.supabase.table("studio_cko_artifacts")
            .select("storage_path, mime_type, title, format")
            .eq("id", artifact_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        row = result.data[0]
        storage_path = row.get("storage_path")

        if not storage_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact file not available",
            )

        # Download from B2
        b2 = get_b2_service()
        file_data = await asyncio.to_thread(
            lambda: b2.download_file(storage_path)
        )

        import re as _re
        safe_title = _re.sub(r'[^\w\s\-.]', '', row['title'])[:100].strip() or "artifact"
        filename = f"{safe_title}.{row['format']}"

        return StreamingResponse(
            BytesIO(file_data),
            media_type=row["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_data)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download artifact", artifact_id=artifact_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download artifact",
        ) from e


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(
    artifact_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete an artifact and its B2 file."""
    try:
        supabase = _get_supabase()

        # Get artifact first for storage cleanup
        result = await asyncio.to_thread(
            lambda: supabase.supabase.table("studio_cko_artifacts")
            .select("storage_path")
            .eq("id", artifact_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        storage_path = result.data[0].get("storage_path")

        # Delete from DB
        await asyncio.to_thread(
            lambda: supabase.supabase.table("studio_cko_artifacts")
            .delete()
            .eq("id", artifact_id)
            .eq("user_id", user_id)
            .execute()
        )

        # Clean up B2 storage (best-effort)
        if storage_path:
            try:
                b2 = get_b2_service()
                await asyncio.to_thread(lambda: b2.delete_file(storage_path))
            except Exception as e:
                logger.warning(
                    "Failed to delete artifact from B2 (orphaned)",
                    storage_path=storage_path,
                    error=str(e),
                )

        logger.info("Artifact deleted", artifact_id=artifact_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete artifact", artifact_id=artifact_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete artifact",
        ) from e
