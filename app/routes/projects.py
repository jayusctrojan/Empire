"""
Empire v7.3 - Projects API Routes
CRUD endpoints for project management

Provides persistent project storage for the NotebookLM-style feature.
Projects are saved to Supabase and persist across app restarts.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
import structlog

from app.middleware.auth import get_current_user
from app.services.project_service import (
    ProjectService,
    get_project_service,
)
from app.models.projects import (
    ProjectSortField,
    SortOrder,
    CreateProjectRequest,
    UpdateProjectRequest,
    Project,
    ProjectSummary,
    CreateProjectResponse,
    GetProjectResponse,
    ListProjectsResponse,
    UpdateProjectResponse,
    DeleteProjectResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# ==============================================================================
# Dependencies
# ==============================================================================

def get_service() -> ProjectService:
    """Dependency for project service"""
    return get_project_service()


# ==============================================================================
# Project CRUD Endpoints
# ==============================================================================

@router.post(
    "",
    response_model=CreateProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    description="Creates a new project for the authenticated user."
)
async def create_project(
    request: CreateProjectRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectService = Depends(get_service),
) -> CreateProjectResponse:
    """
    Create a new project.

    - **name**: Project name (required, 1-255 characters)
    - **description**: Optional description (max 2000 characters)
    - **department**: Optional department/category (max 100 characters)
    - **instructions**: Optional AI instructions (max 5000 characters)
    """
    logger.info(
        "Create project request",
        user_id=user_id,
        name=request.name
    )

    response = await service.create_project(user_id, request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.error
        )

    return response


@router.get(
    "",
    response_model=ListProjectsResponse,
    summary="List all projects",
    description="Lists all projects for the authenticated user with optional filtering."
)
async def list_projects(
    search: Optional[str] = Query(None, description="Search term for name/description"),
    department: Optional[str] = Query(None, description="Filter by department"),
    sort_by: ProjectSortField = Query(
        ProjectSortField.UPDATED_AT,
        description="Field to sort by"
    ),
    sort_order: SortOrder = Query(
        SortOrder.DESC,
        description="Sort direction"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    user_id: str = Depends(get_current_user),
    service: ProjectService = Depends(get_service),
) -> ListProjectsResponse:
    """
    List all projects for the current user.

    Supports:
    - Search by name or description
    - Filter by department
    - Sorting by various fields
    - Pagination with limit/offset
    """
    logger.info(
        "List projects request",
        user_id=user_id,
        search=search,
        department=department
    )

    return await service.list_projects(
        user_id=user_id,
        search=search,
        department=department,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}",
    response_model=GetProjectResponse,
    summary="Get a project",
    description="Get detailed information about a specific project."
)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectService = Depends(get_service),
) -> GetProjectResponse:
    """
    Get a project by ID.

    Returns full project details including:
    - Basic info (name, description, department)
    - Custom AI instructions
    - Source counts and storage usage
    - Timestamps
    """
    logger.info(
        "Get project request",
        user_id=user_id,
        project_id=project_id
    )

    response = await service.get_project(project_id, user_id)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=response.error
        )

    return response


@router.put(
    "/{project_id}",
    response_model=UpdateProjectResponse,
    summary="Update a project",
    description="Update an existing project's properties."
)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectService = Depends(get_service),
) -> UpdateProjectResponse:
    """
    Update a project.

    Only provided fields will be updated. All fields are optional.
    """
    logger.info(
        "Update project request",
        user_id=user_id,
        project_id=project_id
    )

    response = await service.update_project(project_id, user_id, request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in (response.error or "").lower() else status.HTTP_400_BAD_REQUEST,
            detail=response.error
        )

    return response


@router.delete(
    "/{project_id}",
    response_model=DeleteProjectResponse,
    summary="Delete a project",
    description="Delete a project and all its associated sources."
)
async def delete_project(
    project_id: str,
    user_id: str = Depends(get_current_user),
    service: ProjectService = Depends(get_service),
) -> DeleteProjectResponse:
    """
    Delete a project.

    This will also delete all sources associated with the project.
    This action cannot be undone.
    """
    logger.info(
        "Delete project request",
        user_id=user_id,
        project_id=project_id
    )

    response = await service.delete_project(project_id, user_id)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in (response.error or "").lower() else status.HTTP_400_BAD_REQUEST,
            detail=response.error
        )

    return response


# ==============================================================================
# Health Check
# ==============================================================================

@router.get(
    "/health",
    summary="Health check",
    description="Check if the projects service is healthy."
)
async def health_check():
    """Health check endpoint for the projects service."""
    return {"status": "healthy", "service": "projects"}
