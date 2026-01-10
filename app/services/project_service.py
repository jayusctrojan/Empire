"""
Empire v7.3 - Project Service
Service layer for managing projects with Supabase persistence

Provides CRUD operations for the NotebookLM-style project feature,
ensuring projects persist across app restarts.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
import structlog

from app.core.supabase_client import get_supabase_client
from app.models.projects import (
    Project,
    ProjectSummary,
    ProjectSortField,
    SortOrder,
    CreateProjectRequest,
    UpdateProjectRequest,
    CreateProjectResponse,
    GetProjectResponse,
    ListProjectsResponse,
    UpdateProjectResponse,
    DeleteProjectResponse,
)

logger = structlog.get_logger(__name__)


class ProjectService:
    """
    Service for managing projects with Supabase persistence.

    This service handles all CRUD operations for projects, ensuring
    data persists in the database across app restarts.
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        logger.info("ProjectService initialized")

    # ==========================================================================
    # Project Creation
    # ==========================================================================

    async def create_project(
        self,
        user_id: str,
        request: CreateProjectRequest,
    ) -> CreateProjectResponse:
        """
        Create a new project for a user.

        Args:
            user_id: The user's ID
            request: Project creation request with name, description, etc.

        Returns:
            CreateProjectResponse with the created project
        """
        try:
            project_id = str(uuid4())
            now = datetime.utcnow().isoformat()

            project_data = {
                "id": project_id,
                "user_id": user_id,
                "name": request.name.strip(),
                "description": request.description.strip() if request.description else None,
                "department": request.department.strip() if request.department else None,
                "instructions": request.instructions.strip() if request.instructions else None,
                "memory_context": None,
                "source_count": 0,
                "ready_source_count": 0,
                "total_source_size": 0,
                "created_at": now,
                "updated_at": now,
            }

            result = self.supabase.table("projects").insert(project_data).execute()

            if not result.data:
                logger.error("Failed to create project - no data returned")
                return CreateProjectResponse(
                    success=False,
                    message="Failed to create project",
                    error="Database returned no data"
                )

            project = self._to_project(result.data[0])

            logger.info(
                "Project created successfully",
                project_id=project_id,
                user_id=user_id,
                name=request.name
            )

            return CreateProjectResponse(
                success=True,
                project=project,
                message="Project created successfully"
            )

        except Exception as e:
            logger.error("Failed to create project", error=str(e), user_id=user_id)
            return CreateProjectResponse(
                success=False,
                message="Failed to create project",
                error=str(e)
            )

    # ==========================================================================
    # Project Retrieval
    # ==========================================================================

    async def get_project(
        self,
        project_id: str,
        user_id: str,
    ) -> GetProjectResponse:
        """
        Get a single project by ID.

        Args:
            project_id: The project's ID
            user_id: The user's ID (for ownership validation)

        Returns:
            GetProjectResponse with the project data
        """
        try:
            result = self.supabase.table("projects").select("*").eq(
                "id", project_id
            ).eq("user_id", user_id).execute()

            if not result.data:
                return GetProjectResponse(
                    success=False,
                    error="Project not found"
                )

            project = self._to_project(result.data[0])

            return GetProjectResponse(
                success=True,
                project=project
            )

        except Exception as e:
            logger.error(
                "Failed to get project",
                error=str(e),
                project_id=project_id,
                user_id=user_id
            )
            return GetProjectResponse(
                success=False,
                error=str(e)
            )

    async def list_projects(
        self,
        user_id: str,
        search: Optional[str] = None,
        department: Optional[str] = None,
        sort_by: ProjectSortField = ProjectSortField.UPDATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        limit: int = 50,
        offset: int = 0,
    ) -> ListProjectsResponse:
        """
        List all projects for a user with optional filtering.

        Args:
            user_id: The user's ID
            search: Optional search term for name/description
            department: Optional department filter
            sort_by: Field to sort by
            sort_order: Sort direction
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            ListProjectsResponse with projects list
        """
        try:
            # Build query
            query = self.supabase.table("projects").select(
                "id, name, description, department, source_count, ready_source_count, created_at, updated_at",
                count="exact"
            ).eq("user_id", user_id)

            # Apply filters
            if search:
                query = query.or_(f"name.ilike.%{search}%,description.ilike.%{search}%")

            if department:
                query = query.eq("department", department)

            # Apply sorting
            desc = sort_order == SortOrder.DESC
            query = query.order(sort_by.value, desc=desc)

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            result = query.execute()

            projects = [self._to_project_summary(p) for p in result.data]
            total = result.count or 0

            return ListProjectsResponse(
                success=True,
                projects=projects,
                total=total,
                limit=limit,
                offset=offset,
                has_more=(offset + len(projects)) < total
            )

        except Exception as e:
            logger.error("Failed to list projects", error=str(e), user_id=user_id)
            return ListProjectsResponse(
                success=False,
                projects=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

    # ==========================================================================
    # Project Updates
    # ==========================================================================

    async def update_project(
        self,
        project_id: str,
        user_id: str,
        request: UpdateProjectRequest,
    ) -> UpdateProjectResponse:
        """
        Update an existing project.

        Args:
            project_id: The project's ID
            user_id: The user's ID (for ownership validation)
            request: Update request with fields to change

        Returns:
            UpdateProjectResponse with the updated project
        """
        try:
            # Build update data (only include non-None fields)
            update_data: Dict[str, Any] = {
                "updated_at": datetime.utcnow().isoformat()
            }

            if request.name is not None:
                update_data["name"] = request.name.strip()

            if request.description is not None:
                update_data["description"] = request.description.strip() if request.description else None

            if request.department is not None:
                update_data["department"] = request.department.strip() if request.department else None

            if request.instructions is not None:
                update_data["instructions"] = request.instructions.strip() if request.instructions else None

            if request.memory_context is not None:
                update_data["memory_context"] = request.memory_context

            # Update the project
            result = self.supabase.table("projects").update(update_data).eq(
                "id", project_id
            ).eq("user_id", user_id).execute()

            if not result.data:
                return UpdateProjectResponse(
                    success=False,
                    message="Project not found or not authorized",
                    error="No project found with the given ID"
                )

            project = self._to_project(result.data[0])

            logger.info(
                "Project updated successfully",
                project_id=project_id,
                user_id=user_id,
                updated_fields=list(update_data.keys())
            )

            return UpdateProjectResponse(
                success=True,
                project=project,
                message="Project updated successfully"
            )

        except Exception as e:
            logger.error(
                "Failed to update project",
                error=str(e),
                project_id=project_id,
                user_id=user_id
            )
            return UpdateProjectResponse(
                success=False,
                message="Failed to update project",
                error=str(e)
            )

    async def update_source_counts(
        self,
        project_id: str,
        user_id: str,
        source_count: int,
        ready_source_count: int,
        total_source_size: int,
    ) -> bool:
        """
        Update the source counts for a project.
        Called by the project_sources service when sources are added/removed.

        Args:
            project_id: The project's ID
            user_id: The user's ID
            source_count: Total number of sources
            ready_source_count: Number of processed sources
            total_source_size: Total size of all sources in bytes

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            self.supabase.table("projects").update({
                "source_count": source_count,
                "ready_source_count": ready_source_count,
                "total_source_size": total_source_size,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", project_id).eq("user_id", user_id).execute()

            return True

        except Exception as e:
            logger.error(
                "Failed to update source counts",
                error=str(e),
                project_id=project_id
            )
            return False

    # ==========================================================================
    # Project Deletion
    # ==========================================================================

    async def delete_project(
        self,
        project_id: str,
        user_id: str,
    ) -> DeleteProjectResponse:
        """
        Delete a project and all its associated sources.

        Args:
            project_id: The project's ID
            user_id: The user's ID (for ownership validation)

        Returns:
            DeleteProjectResponse with deletion details
        """
        try:
            # First, verify the project exists and belongs to the user
            check = self.supabase.table("projects").select("id").eq(
                "id", project_id
            ).eq("user_id", user_id).execute()

            if not check.data:
                return DeleteProjectResponse(
                    success=False,
                    message="Project not found or not authorized",
                    error="No project found with the given ID"
                )

            # Count sources before deletion
            sources = self.supabase.table("project_sources").select(
                "id", count="exact"
            ).eq("project_id", project_id).execute()
            sources_count = sources.count or 0

            # Delete all sources for this project first
            if sources_count > 0:
                self.supabase.table("project_sources").delete().eq(
                    "project_id", project_id
                ).execute()

            # Delete the project
            self.supabase.table("projects").delete().eq(
                "id", project_id
            ).eq("user_id", user_id).execute()

            logger.info(
                "Project deleted successfully",
                project_id=project_id,
                user_id=user_id,
                deleted_sources=sources_count
            )

            return DeleteProjectResponse(
                success=True,
                project_id=project_id,
                message="Project deleted successfully",
                deleted_sources_count=sources_count
            )

        except Exception as e:
            logger.error(
                "Failed to delete project",
                error=str(e),
                project_id=project_id,
                user_id=user_id
            )
            return DeleteProjectResponse(
                success=False,
                message="Failed to delete project",
                error=str(e)
            )

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    def _to_project(self, data: Dict[str, Any]) -> Project:
        """Convert database row to Project model"""
        return Project(
            id=data["id"],
            user_id=data["user_id"],
            name=data["name"],
            description=data.get("description"),
            department=data.get("department"),
            instructions=data.get("instructions"),
            memory_context=data.get("memory_context"),
            source_count=data.get("source_count", 0) or 0,
            ready_source_count=data.get("ready_source_count", 0) or 0,
            total_source_size=data.get("total_source_size", 0) or 0,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if isinstance(data["created_at"], str) else data["created_at"],
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if isinstance(data["updated_at"], str) else data["updated_at"],
        )

    def _to_project_summary(self, data: Dict[str, Any]) -> ProjectSummary:
        """Convert database row to ProjectSummary model"""
        return ProjectSummary(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            department=data.get("department"),
            source_count=data.get("source_count", 0) or 0,
            ready_source_count=data.get("ready_source_count", 0) or 0,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if isinstance(data["created_at"], str) else data["created_at"],
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if isinstance(data["updated_at"], str) else data["updated_at"],
        )


# ==============================================================================
# Singleton Instance
# ==============================================================================

_service_instance: Optional[ProjectService] = None


def get_project_service() -> ProjectService:
    """Get or create the ProjectService singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ProjectService()
    return _service_instance
