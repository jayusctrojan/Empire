"""
Empire v7.3 - Research Projects API Routes
Endpoints for the Research Projects (Agent Harness) feature.

Provides autonomous research capability with task decomposition,
concurrent execution, and comprehensive report generation.

T185: WebSocket authentication implemented for secure real-time communication.
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import structlog
import jwt

from app.middleware.auth import get_current_user
from app.services.research_project_service import (
    ResearchProjectService,
    get_research_project_service,
)
from app.services.rbac_service import get_rbac_service
from app.models.research_project import (
    JobStatus,
    CreateResearchProjectRequest,
    CreateShareRequest,
    ResearchProjectDetail,
    ProjectStatusResponse,
    ReportResponse,
    FindingsResponse,
    PublicReportResponse,
    CreateProjectResponse,
    ListProjectsResponse,
    CancelProjectResponse,
    CreateShareResponse,
    ListSharesResponse,
    RevokeShareResponse,
)

logger = structlog.get_logger(__name__)

# JWT secret for token validation
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

router = APIRouter(prefix="/api/research-projects", tags=["Research Projects"])


# ==============================================================================
# Dependencies
# ==============================================================================

def get_service() -> ResearchProjectService:
    """Dependency for research project service"""
    return get_research_project_service()


# ==============================================================================
# Project CRUD Endpoints (Subtask 92.1, 92.2, 92.3)
# ==============================================================================

@router.post(
    "",
    response_model=CreateProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new research project",
    description="Submit a research query to initiate autonomous research."
)
async def create_project(
    request: CreateResearchProjectRequest,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> CreateProjectResponse:
    """
    Create a new research project.

    - **query**: The research question to investigate (10-2000 chars)
    - **context**: Optional constraints or focus areas
    - **research_type**: Type of research (general, compliance, competitive, technical, financial)
    - **notify_email**: Email for completion notification
    """
    logger.info(
        "Create research project request",
        user_id=user_id,
        research_type=request.research_type.value
    )

    # Use user_id as customer_id for now (could be separate in multi-tenant setup)
    response = await service.create_project(user_id, user_id, request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    return response


@router.get(
    "",
    response_model=ListProjectsResponse,
    summary="List research projects",
    description="List all research projects for the authenticated user."
)
async def list_projects(
    status_filter: Optional[JobStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> ListProjectsResponse:
    """
    List all research projects with optional filtering and pagination.
    """
    return await service.list_projects(user_id, status_filter, page, page_size)


@router.get(
    "/{job_id}",
    response_model=ResearchProjectDetail,
    summary="Get project details",
    description="Get detailed information about a research project including tasks."
)
async def get_project(
    job_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> ResearchProjectDetail:
    """
    Get full project details including all tasks and progress.
    """
    project = await service.get_project(user_id, job_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found"
        )

    return project


@router.get(
    "/{job_id}/status",
    response_model=ProjectStatusResponse,
    summary="Get project status",
    description="Lightweight endpoint for polling project progress."
)
async def get_project_status(
    job_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> ProjectStatusResponse:
    """
    Get lightweight status for efficient polling.
    """
    status_response = await service.get_project_status(user_id, job_id)

    if not status_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found"
        )

    return status_response


@router.delete(
    "/{job_id}",
    response_model=CancelProjectResponse,
    summary="Cancel project",
    description="Cancel an active research project."
)
async def cancel_project(
    job_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> CancelProjectResponse:
    """
    Cancel a research project. Running tasks will complete gracefully.
    """
    response = await service.cancel_project(user_id, job_id)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    return response


@router.get(
    "/{job_id}/report",
    response_model=ReportResponse,
    summary="Get final report",
    description="Get the completed research report."
)
async def get_report(
    job_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> ReportResponse:
    """
    Get the final research report with findings and analysis.
    """
    report = await service.get_report(user_id, job_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found"
        )

    return report


# ==============================================================================
# Partial Findings (FR-009) - Subtask 92.4
# ==============================================================================

@router.get(
    "/{job_id}/findings",
    response_model=FindingsResponse,
    summary="Get partial findings",
    description="Get findings from completed tasks before full report is ready."
)
async def get_partial_findings(
    job_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> FindingsResponse:
    """
    Get partial findings from completed tasks.
    Useful for monitoring progress and seeing early results.
    """
    findings = await service.get_partial_findings(user_id, job_id)

    if not findings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found"
        )

    return findings


# ==============================================================================
# Share Management (FR-005, FR-005a) - Subtasks 92.4, 92.5
# ==============================================================================

@router.post(
    "/{job_id}/share",
    response_model=CreateShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create share link",
    description="Create a public shareable link for a completed report."
)
async def create_share(
    job_id: int,
    request: Optional[CreateShareRequest] = None,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> CreateShareResponse:
    """
    Create a shareable public link for a completed research report.
    Only completed projects can be shared.
    """
    expires_in_days = request.expires_in_days if request else None
    response = await service.create_share(user_id, job_id, expires_in_days)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    return response


@router.get(
    "/{job_id}/shares",
    response_model=ListSharesResponse,
    summary="List share links",
    description="List all share links for a project (active and revoked)."
)
async def list_shares(
    job_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> ListSharesResponse:
    """
    List all share links for a project including revoked ones.
    """
    return await service.list_shares(user_id, job_id)


@router.delete(
    "/{job_id}/share/{share_id}",
    response_model=RevokeShareResponse,
    summary="Revoke share link",
    description="Revoke a share link to disable public access."
)
async def revoke_share(
    job_id: int,
    share_id: int,
    user_id: str = Depends(get_current_user),
    service: ResearchProjectService = Depends(get_service),
) -> RevokeShareResponse:
    """
    Revoke a share link. The link will no longer provide access.
    """
    response = await service.revoke_share(user_id, job_id, share_id)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    return response


# ==============================================================================
# Public Share Access (No Auth Required) - Subtask 92.5
# ==============================================================================

@router.get(
    "/shared/{share_token}",
    response_model=PublicReportResponse,
    summary="Access shared report",
    description="Access a research report via public share token (no authentication required)."
)
async def get_shared_report(
    share_token: str,
    service: ResearchProjectService = Depends(get_service),
) -> PublicReportResponse:
    """
    Access a shared research report without authentication.
    View count is tracked automatically.
    """
    report = await service.get_public_report(share_token)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found, expired, or revoked"
        )

    return report


# ==============================================================================
# WebSocket for Real-time Updates - Subtask 92.3, T185 (Authentication)
# ==============================================================================

async def _authenticate_websocket(
    websocket: WebSocket,
    job_id: int,
    service: ResearchProjectService
) -> Optional[str]:
    """
    Authenticate WebSocket connection using token or API key.

    T185: WebSocket authentication implementation.

    Supports:
    - Bearer JWT token via query param: ?token=xxx
    - API key via query param: ?api_key=emp_xxx

    Args:
        websocket: WebSocket connection
        job_id: Research project ID
        service: Research project service

    Returns:
        user_id if authenticated, None if authentication fails
    """
    # Get token from query parameters
    token = websocket.query_params.get("token")
    api_key = websocket.query_params.get("api_key")

    user_id = None

    # Strategy 1: JWT Token authentication
    if token:
        try:
            if not CLERK_SECRET_KEY:
                logger.error("WebSocket auth: CLERK_SECRET_KEY not configured")
                await websocket.send_json({
                    "type": "error",
                    "error": "Server authentication not configured"
                })
                await websocket.close(code=1011)  # Internal error
                return None

            # Decode and verify the JWT token
            payload = jwt.decode(
                token,
                CLERK_SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_signature": True, "verify_exp": True}
            )

            user_id = payload.get("sub")
            if not user_id:
                logger.warning("WebSocket auth: Token missing user ID", job_id=job_id)
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid token: missing user ID"
                })
                await websocket.close(code=1008)  # Policy violation
                return None

            logger.debug("WebSocket JWT auth success", user_id=user_id, job_id=job_id)

        except jwt.ExpiredSignatureError:
            logger.warning("WebSocket auth: Token expired", job_id=job_id)
            await websocket.send_json({
                "type": "error",
                "error": "Token has expired"
            })
            await websocket.close(code=1008)  # Policy violation
            return None

        except jwt.InvalidTokenError as e:
            logger.warning("WebSocket auth: Invalid token", job_id=job_id, error=str(e))
            await websocket.send_json({
                "type": "error",
                "error": f"Invalid token: {str(e)}"
            })
            await websocket.close(code=1008)  # Policy violation
            return None

    # Strategy 2: API Key authentication
    elif api_key and api_key.startswith("emp_"):
        try:
            rbac_service = get_rbac_service()
            key_record = await rbac_service.validate_api_key(api_key)

            if not key_record:
                logger.warning(
                    "WebSocket auth: Invalid API key",
                    job_id=job_id,
                    key_prefix=api_key[:12]
                )
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid or expired API key"
                })
                await websocket.close(code=1008)  # Policy violation
                return None

            user_id = key_record["user_id"]
            logger.debug("WebSocket API key auth success", user_id=user_id, job_id=job_id)

        except Exception as e:
            logger.error("WebSocket auth: API key validation error", error=str(e))
            await websocket.send_json({
                "type": "error",
                "error": "Authentication failed"
            })
            await websocket.close(code=1011)  # Internal error
            return None

    # No authentication provided
    else:
        logger.warning("WebSocket auth: No credentials provided", job_id=job_id)
        await websocket.send_json({
            "type": "error",
            "error": "Authentication required. Provide token or api_key query parameter."
        })
        await websocket.close(code=1008)  # Policy violation
        return None

    # Verify user has access to the project
    try:
        project = await service.get_project(user_id, job_id)

        if not project:
            logger.warning(
                "WebSocket auth: Project access denied",
                user_id=user_id,
                job_id=job_id
            )
            await websocket.send_json({
                "type": "error",
                "error": "Project not found or access denied"
            })
            await websocket.close(code=1008)  # Policy violation
            return None

    except Exception as e:
        logger.error(
            "WebSocket auth: Project access check failed",
            user_id=user_id,
            job_id=job_id,
            error=str(e)
        )
        await websocket.send_json({
            "type": "error",
            "error": "Failed to verify project access"
        })
        await websocket.close(code=1011)  # Internal error
        return None

    return user_id


@router.websocket("/ws/{job_id}")
async def websocket_project_updates(
    websocket: WebSocket,
    job_id: int,
    service: ResearchProjectService = Depends(get_service),
):
    """
    WebSocket endpoint for real-time project updates.

    T185: Secure WebSocket with proper authentication.

    Authentication options:
    - JWT token: ws://host/ws/{job_id}?token=<jwt_token>
    - API key: ws://host/ws/{job_id}?api_key=emp_xxx

    Messages sent when:
    - Task status changes
    - Progress updates
    - Project completes or fails

    WebSocket Close Codes:
    - 1000: Normal closure
    - 1008: Policy violation (authentication/authorization failed)
    - 1011: Internal server error
    """
    await websocket.accept()

    # Authenticate the connection
    user_id = await _authenticate_websocket(websocket, job_id, service)
    if not user_id:
        # Connection already closed in _authenticate_websocket
        return

    logger.info(
        "WebSocket connected",
        user_id=user_id,
        job_id=job_id
    )

    try:
        # Send initial status
        initial_message = {
            "type": "connected",
            "job_id": job_id,
            "user_id": user_id,
            "message": "Connected to project updates"
        }
        await websocket.send_json(initial_message)

        # Send current project status
        try:
            status_response = await service.get_project_status(user_id, job_id)
            if status_response:
                await websocket.send_json({
                    "type": "status",
                    "job_id": job_id,
                    "status": status_response.status.value if hasattr(status_response.status, 'value') else str(status_response.status),
                    "progress": status_response.progress if hasattr(status_response, 'progress') else 0,
                    "tasks_completed": status_response.tasks_completed if hasattr(status_response, 'tasks_completed') else 0,
                    "tasks_total": status_response.tasks_total if hasattr(status_response, 'tasks_total') else 0,
                })
        except Exception as e:
            logger.warning("Failed to send initial status", error=str(e), job_id=job_id)

        # Keep connection alive and wait for updates
        while True:
            # In production: subscribe to Redis pub/sub channel for this job_id
            # and forward messages to WebSocket

            # Wait for client messages (ping/pong, commands)
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "status":
                # Client requesting status update
                try:
                    status_response = await service.get_project_status(user_id, job_id)
                    if status_response:
                        await websocket.send_json({
                            "type": "status",
                            "job_id": job_id,
                            "status": status_response.status.value if hasattr(status_response.status, 'value') else str(status_response.status),
                            "progress": status_response.progress if hasattr(status_response, 'progress') else 0,
                            "tasks_completed": status_response.tasks_completed if hasattr(status_response, 'tasks_completed') else 0,
                            "tasks_total": status_response.tasks_total if hasattr(status_response, 'tasks_total') else 0,
                        })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Failed to get status: {str(e)}"
                    })
            elif data == "findings":
                # Client requesting partial findings
                try:
                    findings = await service.get_partial_findings(user_id, job_id)
                    if findings:
                        await websocket.send_json({
                            "type": "findings",
                            "job_id": job_id,
                            "findings": findings.model_dump() if hasattr(findings, 'model_dump') else findings
                        })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Failed to get findings: {str(e)}"
                    })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", user_id=user_id, job_id=job_id)
    except Exception as e:
        logger.error("WebSocket error", user_id=user_id, job_id=job_id, error=str(e))
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
            await websocket.close(code=1011)  # Internal error
        except Exception:
            pass  # Connection may already be closed


# ==============================================================================
# Health Check
# ==============================================================================

@router.get(
    "/health",
    summary="Health check",
    description="Check if the Research Projects service is healthy."
)
async def health_check():
    """Health check endpoint for the Research Projects service."""
    return {
        "status": "healthy",
        "service": "research-projects",
        "version": "1.0.0"
    }
