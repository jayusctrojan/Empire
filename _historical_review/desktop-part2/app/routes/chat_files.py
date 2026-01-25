"""
Empire v7.3 - Chat File Upload Routes
Handles file and image uploads in chat for context-aware Q&A

Task 21: Enable File and Image Upload in Chat
Subtask 21.3: Create Chat File Upload Backend Endpoint
"""

import os
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import structlog

from app.services.chat_file_handler import (
    get_chat_file_handler,
    ChatFileHandler,
    ChatFileType,
    ChatFileMetadata,
    FileUploadResult
)
from app.services.vision_service import (
    get_vision_service,
    VisionService,
    VisionAnalysisType,
    VisionAnalysisResult
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat Files"])


# ============================================================================
# Request/Response Models
# ============================================================================

class FileUploadResponse(BaseModel):
    """Response for file upload"""
    success: bool
    file_id: Optional[str] = None
    filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    extracted_text: Optional[str] = None
    error: Optional[str] = None
    message: str = ""


class FileListResponse(BaseModel):
    """Response for listing session files"""
    session_id: str
    files: List[dict]
    total_count: int


class AnalyzeImageRequest(BaseModel):
    """Request for image analysis"""
    file_id: str = Field(..., description="ID of the uploaded file")
    analysis_type: VisionAnalysisType = Field(
        default=VisionAnalysisType.GENERAL,
        description="Type of analysis to perform"
    )
    custom_prompt: Optional[str] = Field(
        None,
        description="Custom prompt for analysis"
    )


class AnalyzeImageResponse(BaseModel):
    """Response for image analysis"""
    success: bool
    file_id: str
    analysis_type: str
    description: Optional[str] = None
    extracted_text: Optional[str] = None
    processing_time_ms: Optional[float] = None
    error: Optional[str] = None


class AskAboutImageRequest(BaseModel):
    """Request for asking about an image"""
    file_id: str = Field(..., description="ID of the uploaded file")
    question: str = Field(..., description="Question about the image")


class MultiImageAnalysisRequest(BaseModel):
    """Request for multi-image analysis"""
    file_ids: List[str] = Field(..., description="List of file IDs to analyze")
    prompt: str = Field(..., description="Analysis prompt")
    compare: bool = Field(default=False, description="Whether to compare images")


class CleanupResponse(BaseModel):
    """Response for cleanup operations"""
    success: bool
    files_deleted: int
    message: str


# ============================================================================
# Dependencies
# ============================================================================

def get_file_handler() -> ChatFileHandler:
    """Dependency for file handler"""
    return get_chat_file_handler()


def get_vision() -> VisionService:
    """Dependency for vision service"""
    return get_vision_service()


# ============================================================================
# File Upload Endpoints
# ============================================================================

@router.post("/upload", response_model=FileUploadResponse)
async def upload_chat_file(
    file: UploadFile = File(..., description="File to upload"),
    session_id: str = Form(..., description="Chat session ID"),
    user_id: Optional[str] = Form(None, description="User ID"),
    extract_text: bool = Form(True, description="Extract text from documents"),
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> FileUploadResponse:
    """
    Upload a file or image to a chat session

    Supported file types:
    - Images: JPEG, PNG, GIF, WebP, BMP
    - Documents: PDF, DOC, DOCX, TXT, MD, RTF

    Features:
    - Automatic MIME type detection
    - File validation and size limits
    - Text extraction for documents
    - Image dimension detection
    """
    try:
        logger.info(
            "Chat file upload request",
            filename=file.filename,
            session_id=session_id,
            content_type=file.content_type
        )

        # Read file content
        content = await file.read()

        # Process upload
        result = await file_handler.process_upload(
            file_data=content,
            filename=file.filename,
            session_id=session_id,
            user_id=user_id,
            extract_text=extract_text
        )

        if not result.success:
            logger.warning(
                "File upload failed",
                filename=file.filename,
                error=result.error
            )
            return FileUploadResponse(
                success=False,
                error=result.error,
                message="File upload failed"
            )

        metadata = result.metadata
        return FileUploadResponse(
            success=True,
            file_id=metadata.file_id,
            filename=metadata.original_filename,
            file_type=metadata.file_type.value,
            file_size=metadata.file_size,
            mime_type=metadata.mime_type,
            width=metadata.width,
            height=metadata.height,
            extracted_text=metadata.extracted_text[:500] if metadata.extracted_text else None,
            message="File uploaded successfully"
        )

    except Exception as e:
        logger.error(
            "File upload error",
            filename=file.filename if file else "unknown",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/multiple", response_model=List[FileUploadResponse])
async def upload_multiple_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    session_id: str = Form(..., description="Chat session ID"),
    user_id: Optional[str] = Form(None, description="User ID"),
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> List[FileUploadResponse]:
    """
    Upload multiple files to a chat session

    Maximum 10 files per request.
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files per upload request"
        )

    results = []
    for file in files:
        try:
            content = await file.read()
            result = await file_handler.process_upload(
                file_data=content,
                filename=file.filename,
                session_id=session_id,
                user_id=user_id,
                extract_text=True
            )

            if result.success:
                metadata = result.metadata
                results.append(FileUploadResponse(
                    success=True,
                    file_id=metadata.file_id,
                    filename=metadata.original_filename,
                    file_type=metadata.file_type.value,
                    file_size=metadata.file_size,
                    mime_type=metadata.mime_type,
                    message="File uploaded successfully"
                ))
            else:
                results.append(FileUploadResponse(
                    success=False,
                    filename=file.filename,
                    error=result.error,
                    message="File upload failed"
                ))

        except Exception as e:
            results.append(FileUploadResponse(
                success=False,
                filename=file.filename,
                error=str(e),
                message="File upload failed"
            ))

    return results


# ============================================================================
# File Management Endpoints
# ============================================================================

@router.get("/files/{session_id}", response_model=FileListResponse)
async def list_session_files(
    session_id: str,
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> FileListResponse:
    """List all files uploaded to a chat session"""
    files = file_handler.get_session_files(session_id)
    return FileListResponse(
        session_id=session_id,
        files=[f.to_dict() for f in files],
        total_count=len(files)
    )


@router.get("/file/{file_id}")
async def get_file_metadata(
    file_id: str,
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> dict:
    """Get metadata for a specific file"""
    metadata = file_handler.get_file_by_id(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
    return metadata.to_dict()


@router.get("/file/{file_id}/content")
async def get_file_content(
    file_id: str,
    as_base64: bool = Query(False, description="Return as base64 string"),
    file_handler: ChatFileHandler = Depends(get_file_handler)
):
    """Get file content by ID"""
    metadata = file_handler.get_file_by_id(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")

    if as_base64:
        content = file_handler.get_file_as_base64(file_id)
        if content:
            return {"base64": content, "mime_type": metadata.mime_type}
        raise HTTPException(status_code=404, detail="File content not found")

    from fastapi.responses import FileResponse
    if metadata.storage_path and os.path.exists(metadata.storage_path):
        return FileResponse(
            path=metadata.storage_path,
            filename=metadata.original_filename,
            media_type=metadata.mime_type
        )

    raise HTTPException(status_code=404, detail="File content not found")


@router.delete("/file/{file_id}")
async def delete_file(
    file_id: str,
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> dict:
    """Delete a specific file"""
    success = file_handler.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found or deletion failed")
    return {"success": True, "message": "File deleted"}


@router.delete("/files/{session_id}", response_model=CleanupResponse)
async def cleanup_session_files(
    session_id: str,
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> CleanupResponse:
    """Delete all files for a chat session"""
    deleted_count = file_handler.cleanup_session(session_id)
    return CleanupResponse(
        success=True,
        files_deleted=deleted_count,
        message=f"Deleted {deleted_count} files from session"
    )


# ============================================================================
# Vision Analysis Endpoints
# ============================================================================

@router.post("/analyze", response_model=AnalyzeImageResponse)
async def analyze_image(
    request: AnalyzeImageRequest,
    vision_service: VisionService = Depends(get_vision)
) -> AnalyzeImageResponse:
    """
    Analyze an uploaded image using Claude Vision API

    Analysis types:
    - general: General description of the image
    - document: Extract text from document images
    - diagram: Analyze charts and diagrams
    - code: Analyze code screenshots
    - detailed: Highly detailed analysis
    """
    try:
        logger.info(
            "Image analysis request",
            file_id=request.file_id,
            analysis_type=request.analysis_type.value
        )

        result = await vision_service.analyze_image(
            file_id=request.file_id,
            analysis_type=request.analysis_type,
            custom_prompt=request.custom_prompt
        )

        return AnalyzeImageResponse(
            success=result.success,
            file_id=result.file_id,
            analysis_type=result.analysis_type.value,
            description=result.description if result.success else None,
            extracted_text=result.extracted_text,
            processing_time_ms=result.processing_time_ms,
            error=result.error
        )

    except Exception as e:
        logger.error(
            "Image analysis error",
            file_id=request.file_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=dict)
async def ask_about_image(
    request: AskAboutImageRequest,
    vision_service: VisionService = Depends(get_vision)
) -> dict:
    """
    Ask a specific question about an uploaded image

    Useful for interactive Q&A about image content.
    """
    try:
        answer = await vision_service.answer_question_about_image(
            file_id=request.file_id,
            question=request.question
        )

        return {
            "success": True,
            "file_id": request.file_id,
            "question": request.question,
            "answer": answer
        }

    except Exception as e:
        logger.error(
            "Ask about image error",
            file_id=request.file_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/multiple", response_model=dict)
async def analyze_multiple_images(
    request: MultiImageAnalysisRequest,
    vision_service: VisionService = Depends(get_vision)
) -> dict:
    """
    Analyze multiple images together

    Useful for comparing images or analyzing image sequences.
    """
    try:
        result = await vision_service.analyze_multiple_images(
            file_ids=request.file_ids,
            prompt=request.prompt,
            compare=request.compare
        )

        return result

    except Exception as e:
        logger.error(
            "Multi-image analysis error",
            file_ids=request.file_ids,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/describe/{file_id}")
async def describe_for_chat(
    file_id: str,
    query: Optional[str] = Query(None, description="Optional user query about the image"),
    vision_service: VisionService = Depends(get_vision)
) -> dict:
    """
    Get a concise description of an image for chat context

    Returns a brief description suitable for including in chat conversation.
    """
    try:
        description = await vision_service.describe_for_chat(
            file_id=file_id,
            user_query=query
        )

        return {
            "success": True,
            "file_id": file_id,
            "description": description
        }

    except Exception as e:
        logger.error(
            "Describe for chat error",
            file_id=file_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Utility Endpoints
# ============================================================================

@router.get("/supported-types")
async def get_supported_types(
    file_handler: ChatFileHandler = Depends(get_file_handler)
) -> dict:
    """Get list of supported file types and extensions"""
    return {
        "supported_types": file_handler.get_supported_types(),
        "max_file_size_mb": file_handler.max_file_size / (1024 * 1024),
        "max_files_per_session": file_handler.max_files_per_session
    }


@router.get("/health")
async def chat_files_health() -> dict:
    """Health check for chat file service"""
    return {
        "status": "healthy",
        "service": "chat_files",
        "features": {
            "file_upload": True,
            "image_analysis": True,
            "text_extraction": True,
            "multi_image_analysis": True
        }
    }
