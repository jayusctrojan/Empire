"""
Empire v7.3 - Workflow Management API (Task 158)

API endpoints for managing workflows:
- Workflow CRUD operations
- Task tracking and completion
- Cancellation support
- Metrics and status monitoring

Author: Claude Code
Date: 2025-01-15
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.workflow_management import (
    get_workflow_manager,
    WorkflowState,
    WorkflowStatus,
    StorageBackend,
)

router = APIRouter(
    prefix="/api/workflows",
    tags=["Workflows"],
    responses={
        404: {"description": "Workflow not found"},
        409: {"description": "Workflow conflict"},
    }
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateWorkflowRequest(BaseModel):
    """Request to create a new workflow"""
    workflow_type: str = Field(..., description="Type of workflow (e.g., document_analysis)")
    tasks: List[str] = Field(..., description="List of task names to execute")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional workflow context")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_type": "document_analysis",
                "tasks": ["parse", "extract_entities", "synthesize"],
                "context": {"document_id": "doc-123"},
                "metadata": {"user_id": "user-456"}
            }
        }


class WorkflowResponse(BaseModel):
    """Workflow state response"""
    workflow_id: str
    workflow_type: str
    status: str
    current_task: Optional[str] = None
    completed_tasks: List[str] = []
    pending_tasks: List[str] = []
    progress_percent: float = 0.0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class TaskUpdateRequest(BaseModel):
    """Request to update task status"""
    task_name: str = Field(..., description="Name of the task")
    success: bool = Field(default=True, description="Whether task succeeded")
    result: Optional[Any] = Field(default=None, description="Task result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class CancelWorkflowRequest(BaseModel):
    """Request to cancel a workflow"""
    reason: str = Field(default="User requested cancellation", description="Cancellation reason")


class WorkflowListResponse(BaseModel):
    """Response for listing workflows"""
    workflows: List[WorkflowResponse]
    total: int
    running: int
    completed: int
    failed: int
    cancelled: int


class WorkflowMetricsResponse(BaseModel):
    """Workflow metrics response"""
    total_workflows: int
    completed: int
    failed: int
    cancelled: int
    running: int
    success_rate: float
    average_duration: float
    total_tasks: int
    completed_tasks: int
    failed_tasks: int


class TaskMetricsResponse(BaseModel):
    """Individual task metrics"""
    task_id: str
    task_name: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    status: str


class WorkflowDetailResponse(WorkflowResponse):
    """Detailed workflow response with task metrics"""
    tasks: Dict[str, TaskMetricsResponse] = {}
    duration: Optional[float] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _state_to_response(state: WorkflowState) -> WorkflowResponse:
    """Convert WorkflowState to response model"""
    total_tasks = len(state.completed_tasks) + len(state.pending_tasks)
    if state.current_task:
        total_tasks += 1
    progress = (len(state.completed_tasks) / total_tasks * 100) if total_tasks > 0 else 0

    return WorkflowResponse(
        workflow_id=state.workflow_id,
        workflow_type=state.workflow_type,
        status=state.status.value,
        current_task=state.current_task,
        completed_tasks=state.completed_tasks,
        pending_tasks=state.pending_tasks,
        progress_percent=round(progress, 1),
        started_at=state.started_at,
        updated_at=state.updated_at,
        completed_at=state.completed_at,
        error=state.error,
        metadata=state.metadata,
    )


# =============================================================================
# WORKFLOW CRUD ENDPOINTS
# =============================================================================

@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=201,
    summary="Create Workflow",
    description="Create a new workflow with specified tasks."
)
async def create_workflow(request: CreateWorkflowRequest) -> WorkflowResponse:
    """
    Create a new workflow.

    The workflow will be created in PENDING status.
    Use the /start endpoint to begin execution.
    """
    manager = get_workflow_manager()
    await manager.initialize()

    workflow_id = await manager.create_workflow(
        workflow_type=request.workflow_type,
        tasks=request.tasks,
        context=request.context,
        metadata=request.metadata
    )

    state = await manager.get_workflow_state(workflow_id)
    return _state_to_response(state)


@router.get(
    "",
    response_model=WorkflowListResponse,
    summary="List Workflows",
    description="List all workflows with optional filtering."
)
async def list_workflows(
    status: Optional[str] = Query(None, description="Filter by status"),
    workflow_type: Optional[str] = Query(None, description="Filter by workflow type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> WorkflowListResponse:
    """List all workflows with optional filtering."""
    manager = get_workflow_manager()
    await manager.initialize()

    status_filter = WorkflowStatus(status) if status else None
    workflows = await manager.list_workflows(status=status_filter, workflow_type=workflow_type)

    # Apply limit
    workflows = workflows[:limit]

    # Calculate stats
    running = sum(1 for w in workflows if w.status == WorkflowStatus.RUNNING)
    completed = sum(1 for w in workflows if w.status == WorkflowStatus.COMPLETED)
    failed = sum(1 for w in workflows if w.status == WorkflowStatus.FAILED)
    cancelled = sum(1 for w in workflows if w.status == WorkflowStatus.CANCELLED)

    return WorkflowListResponse(
        workflows=[_state_to_response(w) for w in workflows],
        total=len(workflows),
        running=running,
        completed=completed,
        failed=failed,
        cancelled=cancelled,
    )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDetailResponse,
    summary="Get Workflow",
    description="Get detailed information about a specific workflow."
)
async def get_workflow(workflow_id: str) -> WorkflowDetailResponse:
    """Get detailed workflow information including task metrics."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Get metrics
    metrics = manager.get_metrics(workflow_id)
    task_metrics = {}
    if metrics and "tasks" in metrics:
        for task_id, tm in metrics["tasks"].items():
            task_metrics[task_id] = TaskMetricsResponse(
                task_id=tm["task_id"],
                task_name=tm["task_name"],
                start_time=tm.get("start_time"),
                end_time=tm.get("end_time"),
                duration=tm.get("duration"),
                status=tm.get("status", "unknown")
            )

    base_response = _state_to_response(state)

    return WorkflowDetailResponse(
        **base_response.model_dump(),
        tasks=task_metrics,
        duration=metrics.get("duration") if metrics else None
    )


@router.delete(
    "/{workflow_id}",
    status_code=204,
    summary="Delete Workflow",
    description="Delete a workflow and its state."
)
async def delete_workflow(workflow_id: str) -> None:
    """Delete a workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    if state.status == WorkflowStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete running workflow. Cancel it first."
        )

    await manager.state_manager.delete_state(workflow_id)


# =============================================================================
# WORKFLOW LIFECYCLE ENDPOINTS
# =============================================================================

@router.post(
    "/{workflow_id}/start",
    response_model=WorkflowResponse,
    summary="Start Workflow",
    description="Start executing a workflow."
)
async def start_workflow(workflow_id: str) -> WorkflowResponse:
    """Start workflow execution."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    if state.status not in [WorkflowStatus.PENDING, WorkflowStatus.PAUSED, WorkflowStatus.RECOVERING]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start workflow in {state.status.value} status"
        )

    state = await manager.start_workflow(workflow_id)
    return _state_to_response(state)


@router.post(
    "/{workflow_id}/cancel",
    response_model=WorkflowResponse,
    summary="Cancel Workflow",
    description="Cancel a running workflow."
)
async def cancel_workflow(
    workflow_id: str,
    request: CancelWorkflowRequest = CancelWorkflowRequest()
) -> WorkflowResponse:
    """Cancel a workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    if state.status in [WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED, WorkflowStatus.FAILED]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel workflow in {state.status.value} status"
        )

    await manager.cancel_workflow(workflow_id, reason=request.reason)

    state = await manager.get_workflow_state(workflow_id)
    return _state_to_response(state)


@router.post(
    "/{workflow_id}/recover",
    response_model=WorkflowResponse,
    summary="Recover Workflow",
    description="Recover a workflow from its last checkpoint."
)
async def recover_workflow(workflow_id: str) -> WorkflowResponse:
    """Recover a workflow from checkpoint."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.recover_workflow(workflow_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"No checkpoint found for workflow '{workflow_id}'"
        )

    return _state_to_response(state)


# =============================================================================
# TASK MANAGEMENT ENDPOINTS
# =============================================================================

@router.post(
    "/{workflow_id}/tasks/start",
    response_model=WorkflowResponse,
    summary="Start Task",
    description="Mark a task as started within a workflow."
)
async def start_task(
    workflow_id: str,
    task_name: str = Query(..., description="Name of the task to start")
) -> WorkflowResponse:
    """Start a task within a workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    if state.status != WorkflowStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start task on workflow in {state.status.value} status"
        )

    await manager.start_task(workflow_id, task_name)

    state = await manager.get_workflow_state(workflow_id)
    return _state_to_response(state)


@router.post(
    "/{workflow_id}/tasks/complete",
    response_model=WorkflowResponse,
    summary="Complete Task",
    description="Mark a task as completed within a workflow."
)
async def complete_task(
    workflow_id: str,
    request: TaskUpdateRequest
) -> WorkflowResponse:
    """Complete a task within a workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    await manager.complete_task(
        workflow_id,
        request.task_name,
        result=request.result,
        success=request.success,
        error=request.error
    )

    state = await manager.get_workflow_state(workflow_id)
    return _state_to_response(state)


@router.post(
    "/{workflow_id}/complete",
    response_model=WorkflowResponse,
    summary="Complete Workflow",
    description="Mark an entire workflow as completed."
)
async def complete_workflow_endpoint(
    workflow_id: str,
    success: bool = Query(True, description="Whether workflow succeeded"),
    error: Optional[str] = Query(None, description="Error message if failed")
) -> WorkflowResponse:
    """Complete a workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    state = await manager.get_workflow_state(workflow_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    await manager.complete_workflow(workflow_id, success=success, error=error)

    state = await manager.get_workflow_state(workflow_id)
    return _state_to_response(state)


# =============================================================================
# METRICS AND MONITORING ENDPOINTS
# =============================================================================

@router.get(
    "/metrics/summary",
    response_model=WorkflowMetricsResponse,
    summary="Get Metrics Summary",
    description="Get aggregated metrics across all workflows."
)
async def get_metrics_summary() -> WorkflowMetricsResponse:
    """Get aggregated workflow metrics."""
    manager = get_workflow_manager()
    await manager.initialize()

    metrics = manager.get_metrics()

    return WorkflowMetricsResponse(
        total_workflows=metrics.get("total_workflows", 0),
        completed=metrics.get("completed", 0),
        failed=metrics.get("failed", 0),
        cancelled=metrics.get("cancelled", 0),
        running=metrics.get("running", 0),
        success_rate=metrics.get("success_rate", 0.0),
        average_duration=metrics.get("average_duration", 0.0),
        total_tasks=metrics.get("total_tasks", 0),
        completed_tasks=metrics.get("completed_tasks", 0),
        failed_tasks=metrics.get("failed_tasks", 0),
    )


@router.get(
    "/{workflow_id}/metrics",
    summary="Get Workflow Metrics",
    description="Get detailed metrics for a specific workflow."
)
async def get_workflow_metrics(workflow_id: str) -> Dict[str, Any]:
    """Get metrics for a specific workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    metrics = manager.get_metrics(workflow_id)
    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for workflow '{workflow_id}'"
        )

    return metrics


@router.get(
    "/{workflow_id}/cancellation-status",
    summary="Get Cancellation Status",
    description="Get the cancellation token status for a workflow."
)
async def get_cancellation_status(workflow_id: str) -> Dict[str, Any]:
    """Get cancellation token status for a workflow."""
    manager = get_workflow_manager()
    await manager.initialize()

    token = manager.get_cancellation_token(workflow_id)
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"No cancellation token found for workflow '{workflow_id}'"
        )

    return {
        "workflow_id": workflow_id,
        **token.get_status()
    }


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get(
    "/health",
    summary="Workflow Service Health",
    description="Check workflow management service health."
)
async def health_check() -> Dict[str, Any]:
    """Health check for workflow service."""
    manager = get_workflow_manager()

    try:
        await manager.initialize()
        metrics = manager.get_metrics()

        return {
            "status": "healthy",
            "storage_backend": manager.state_manager.backend.value,
            "active_workflows": metrics.get("running", 0),
            "total_workflows": metrics.get("total_workflows", 0),
            "shutdown_handler_active": manager.shutdown_handler._enable_shutdown_handler if hasattr(manager.shutdown_handler, '_enable_shutdown_handler') else True,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
