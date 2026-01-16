"""
Empire v7.3 - LlamaIndex API Routes (Task 156)

API endpoints for LlamaIndex service integration including:
- Health check endpoint
- Service status and statistics
- Document parsing proxy

Author: Claude Code
Date: 2025-01-15
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.llama_index_service import (
    get_llama_index_service,
    ResilientLlamaIndexService,
    LlamaIndexConfig,
    OperationType,
)

router = APIRouter(
    prefix="/api/llama-index",
    tags=["LlamaIndex"],
    responses={
        503: {"description": "Service unavailable"},
        504: {"description": "Gateway timeout"}
    }
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: str = Field(description="Overall health status: healthy, unhealthy, or degraded")
    service_url: str = Field(description="LlamaIndex service URL")
    response_time_ms: float = Field(description="Response time in milliseconds")
    components: Dict[str, str] = Field(description="Component-level health status")
    timestamp: str = Field(description="ISO timestamp of health check")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service_url": "https://jb-llamaindex.onrender.com",
                "response_time_ms": 150.5,
                "components": {
                    "connection": "healthy",
                    "api": "healthy"
                },
                "timestamp": "2025-01-15T12:00:00.000000",
                "details": {}
            }
        }


class DeepHealthCheckResponse(HealthCheckResponse):
    """Extended health check response with deep check results"""
    deep_check: Dict[str, Any] = Field(default_factory=dict, description="Deep health check results")


class ServiceStatsResponse(BaseModel):
    """Service statistics response"""
    service_name: str
    requests_total: int
    requests_successful: int
    requests_failed: int
    retries_total: int
    health_checks_total: int
    last_health_check: Optional[str]
    last_health_status: Optional[str]
    config: Dict[str, Any]
    client_initialized: bool


class ServiceConfigResponse(BaseModel):
    """Service configuration response"""
    service_url: str
    max_connections: int
    max_keepalive_connections: int
    max_retries: int
    timeouts: Dict[str, float]
    default_timeout: float


class ParseDocumentRequest(BaseModel):
    """Document parsing request"""
    file_content_base64: str = Field(description="Base64 encoded file content")
    filename: str = Field(description="Original filename")
    content_type: str = Field(default="application/pdf", description="MIME type")
    parsing_instructions: Optional[str] = Field(default=None, description="Optional parsing instructions")


class ParseDocumentResponse(BaseModel):
    """Document parsing response"""
    success: bool
    content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# =============================================================================
# DEPENDENCY
# =============================================================================

def get_service() -> ResilientLlamaIndexService:
    """Dependency to get LlamaIndex service instance"""
    return get_llama_index_service()


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="LlamaIndex Health Check",
    description="Check the health of the LlamaIndex service connection and API."
)
async def health_check(
    service: ResilientLlamaIndexService = Depends(get_service)
) -> HealthCheckResponse:
    """
    Perform a health check on the LlamaIndex service.

    Returns:
        Health check results including status, response time, and component health.
    """
    result = await service.check_health()
    return HealthCheckResponse(**result)


@router.get(
    "/health/deep",
    response_model=DeepHealthCheckResponse,
    summary="Deep LlamaIndex Health Check",
    description="Perform a comprehensive health check including test operations."
)
async def deep_health_check(
    service: ResilientLlamaIndexService = Depends(get_service)
) -> DeepHealthCheckResponse:
    """
    Perform a deep health check on the LlamaIndex service.

    This includes:
    - Basic connectivity check
    - API health verification
    - Test operation execution

    Returns:
        Extended health check results with test operation outcomes.
    """
    result = await service.check_deep_health()
    return DeepHealthCheckResponse(**result)


# =============================================================================
# STATUS AND STATISTICS ENDPOINTS
# =============================================================================

@router.get(
    "/stats",
    response_model=ServiceStatsResponse,
    summary="Service Statistics",
    description="Get statistics about the LlamaIndex service usage."
)
async def get_stats(
    service: ResilientLlamaIndexService = Depends(get_service)
) -> ServiceStatsResponse:
    """
    Get statistics about LlamaIndex service operations.

    Returns:
        Service statistics including request counts, retries, and health check history.
    """
    stats = service.get_stats()
    return ServiceStatsResponse(**stats)


@router.get(
    "/config",
    response_model=ServiceConfigResponse,
    summary="Service Configuration",
    description="Get the current LlamaIndex service configuration."
)
async def get_config(
    service: ResilientLlamaIndexService = Depends(get_service)
) -> ServiceConfigResponse:
    """
    Get the current configuration for the LlamaIndex service.

    Returns:
        Service configuration including timeouts, connection limits, and retry settings.
    """
    config = service.config
    return ServiceConfigResponse(
        service_url=config.service_url,
        max_connections=config.max_connections,
        max_keepalive_connections=config.max_keepalive_connections,
        max_retries=config.max_retries,
        timeouts=config.timeouts,
        default_timeout=config.default_timeout
    )


@router.get(
    "/timeouts",
    response_model=Dict[str, float],
    summary="Operation Timeouts",
    description="Get configured timeouts for different operation types."
)
async def get_timeouts(
    service: ResilientLlamaIndexService = Depends(get_service)
) -> Dict[str, float]:
    """
    Get the configured timeouts for each operation type.

    Returns:
        Dictionary mapping operation types to their timeout values in seconds.
    """
    return service.config.timeouts


# =============================================================================
# DOCUMENT OPERATIONS (PROXY)
# =============================================================================

@router.post(
    "/parse",
    response_model=ParseDocumentResponse,
    summary="Parse Document",
    description="Parse a document using the LlamaIndex service."
)
async def parse_document(
    request: ParseDocumentRequest,
    service: ResilientLlamaIndexService = Depends(get_service)
) -> ParseDocumentResponse:
    """
    Parse a document through the LlamaIndex service.

    This endpoint proxies document parsing requests to the LlamaIndex service
    with full retry logic and timeout handling.

    Args:
        request: Document parsing request with base64-encoded content

    Returns:
        Parsed document content and metadata
    """
    import base64

    try:
        # Decode file content
        file_content = base64.b64decode(request.file_content_base64)

        # Call service
        result = await service.parse_document(
            file_content=file_content,
            filename=request.filename,
            content_type=request.content_type,
            parsing_instructions=request.parsing_instructions
        )

        return ParseDocumentResponse(
            success=True,
            content=result.get("content"),
            metadata=result.get("metadata", {})
        )

    except Exception as e:
        return ParseDocumentResponse(
            success=False,
            error=str(e)
        )


# =============================================================================
# INDEX OPERATIONS
# =============================================================================

@router.get(
    "/indices",
    summary="List Indices",
    description="List all available indices in the LlamaIndex service."
)
async def list_indices(
    service: ResilientLlamaIndexService = Depends(get_service)
) -> List[Dict[str, Any]]:
    """
    List all available indices.

    Returns:
        List of index metadata
    """
    try:
        return await service.list_indices()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.delete(
    "/index/{index_id}",
    summary="Delete Index",
    description="Delete an index from the LlamaIndex service."
)
async def delete_index(
    index_id: str,
    service: ResilientLlamaIndexService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Delete an index.

    Args:
        index_id: ID of the index to delete

    Returns:
        Deletion result
    """
    try:
        success = await service.delete_index(index_id)
        return {
            "success": success,
            "index_id": index_id,
            "message": "Index deleted successfully" if success else "Failed to delete index"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# =============================================================================
# QUERY OPERATIONS
# =============================================================================

class QueryIndexRequest(BaseModel):
    """Index query request"""
    query: str = Field(description="Query string")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filters")


@router.post(
    "/index/{index_id}/query",
    summary="Query Index",
    description="Query an existing index."
)
async def query_index(
    index_id: str,
    request: QueryIndexRequest,
    service: ResilientLlamaIndexService = Depends(get_service)
) -> Dict[str, Any]:
    """
    Query an existing index.

    Args:
        index_id: ID of the index to query
        request: Query parameters

    Returns:
        Query results
    """
    try:
        return await service.query_index(
            index_id=index_id,
            query=request.query,
            top_k=request.top_k,
            filters=request.filters
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
