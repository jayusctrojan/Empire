"""
Empire v7.3 - Project Models
Pydantic models for project CRUD operations

Enables persistent project storage in Supabase for the NotebookLM-style feature.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class ProjectSortField(str, Enum):
    """Fields available for sorting projects"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    SOURCE_COUNT = "source_count"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


# ==============================================================================
# Request Models
# ==============================================================================

class CreateProjectRequest(BaseModel):
    """Request model for creating a new project"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Project description"
    )
    department: Optional[str] = Field(
        None,
        max_length=100,
        description="Department or category"
    )
    instructions: Optional[str] = Field(
        None,
        max_length=5000,
        description="Custom instructions for the project's AI assistant"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Q1 2025 Research",
                "description": "Research project for quarterly planning",
                "department": "Strategy",
                "instructions": "Focus on market trends and competitor analysis"
            }
        }
    }


class UpdateProjectRequest(BaseModel):
    """Request model for updating a project"""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Project name"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Project description"
    )
    department: Optional[str] = Field(
        None,
        max_length=100,
        description="Department or category"
    )
    instructions: Optional[str] = Field(
        None,
        max_length=5000,
        description="Custom instructions for the project's AI assistant"
    )
    memory_context: Optional[str] = Field(
        None,
        description="Conversation memory context"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Updated Project Name",
                "description": "Updated description"
            }
        }
    }


# ==============================================================================
# Response Models
# ==============================================================================

class Project(BaseModel):
    """Project model matching the Supabase 'projects' table schema"""
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    department: Optional[str] = None
    instructions: Optional[str] = None
    memory_context: Optional[str] = None
    source_count: int = 0
    ready_source_count: int = 0
    total_source_size: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class ProjectSummary(BaseModel):
    """Lightweight project summary for list views"""
    id: str
    name: str
    description: Optional[str] = None
    department: Optional[str] = None
    source_count: int = 0
    ready_source_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class CreateProjectResponse(BaseModel):
    """Response model for project creation"""
    success: bool
    project: Optional[Project] = None
    message: str
    error: Optional[str] = None


class GetProjectResponse(BaseModel):
    """Response model for getting a single project"""
    success: bool
    project: Optional[Project] = None
    error: Optional[str] = None


class ListProjectsResponse(BaseModel):
    """Response model for listing projects"""
    success: bool
    projects: List[ProjectSummary] = []
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class UpdateProjectResponse(BaseModel):
    """Response model for project update"""
    success: bool
    project: Optional[Project] = None
    message: str
    error: Optional[str] = None


class DeleteProjectResponse(BaseModel):
    """Response model for project deletion"""
    success: bool
    project_id: Optional[str] = None
    message: str
    deleted_sources_count: int = 0
    error: Optional[str] = None
