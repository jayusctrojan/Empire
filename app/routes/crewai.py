"""
CrewAI multi-agent orchestration routes for Empire v7.3
Provides REST API for agent pool management and crew orchestration
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import structlog

from app.services.crewai_service import CrewAIService
from app.core.connections import get_supabase
from supabase import Client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/crewai", tags=["crewai"])


# ==================== Request/Response Models ====================

class AgentCreateRequest(BaseModel):
    agent_name: str = Field(..., description="Unique name for the agent")
    role: str = Field(..., description="Role/job title of the agent")
    goal: str = Field(..., description="Primary objective of the agent")
    backstory: str = Field(..., description="Background/context for the agent")
    tools: Optional[List[str]] = Field(default=None, description="List of tool names the agent can use")
    llm_config: Optional[Dict[str, Any]] = Field(default=None, description="LLM configuration")


class AgentUpdateRequest(BaseModel):
    role: Optional[str] = Field(default=None, description="New role")
    goal: Optional[str] = Field(default=None, description="New goal")
    backstory: Optional[str] = Field(default=None, description="New backstory")
    tools: Optional[List[str]] = Field(default=None, description="New tools list")
    llm_config: Optional[Dict[str, Any]] = Field(default=None, description="New LLM config")
    is_active: Optional[bool] = Field(default=None, description="Active status")


class CrewCreateRequest(BaseModel):
    crew_name: str = Field(..., description="Unique name for the crew")
    description: str = Field(..., description="Description of crew's purpose")
    agent_ids: List[str] = Field(..., description="List of agent UUIDs")
    process_type: str = Field(default="sequential", description="Process type (sequential, hierarchical)")
    memory_enabled: bool = Field(default=True, description="Enable crew memory")
    verbose: bool = Field(default=False, description="Enable verbose logging")


class CrewUpdateRequest(BaseModel):
    description: Optional[str] = Field(default=None, description="New description")
    agent_ids: Optional[List[str]] = Field(default=None, description="New agent IDs list")
    process_type: Optional[str] = Field(default=None, description="New process type")
    is_active: Optional[bool] = Field(default=None, description="Active status")


# ==================== Dependency Injection ====================

def get_crewai_service(supabase: Client = Depends(get_supabase)) -> CrewAIService:
    """Dependency to get CrewAIService instance with Supabase client"""
    return CrewAIService(supabase=supabase)


# ==================== Health & Status Endpoints ====================

@router.get("/health", summary="Health Check", description="Check CrewAI service health")
async def health_check(crewai_service: CrewAIService = Depends(get_crewai_service)):
    """Check if CrewAI service is available and healthy"""
    is_healthy = await crewai_service.health_check()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "crewai",
        "enabled": crewai_service.enabled
    }


@router.get("/workflows", summary="List Available Workflows", description="Get available CrewAI workflow types")
async def list_workflows(crewai_service: CrewAIService = Depends(get_crewai_service)):
    """Get list of available CrewAI workflow types"""
    try:
        workflows = crewai_service.get_available_workflows()
        return {"workflows": workflows, "count": len(workflows)}
    except Exception as e:
        logger.error("Failed to list workflows", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Agent Management Endpoints ====================

@router.post(
    "/agents",
    summary="Create Agent",
    description="Create a new agent in the agent pool",
    status_code=status.HTTP_201_CREATED
)
async def create_agent(
    request: AgentCreateRequest,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Create a new agent with specified configuration"""
    try:
        agent = crewai_service.create_agent(
            agent_name=request.agent_name,
            role=request.role,
            goal=request.goal,
            backstory=request.backstory,
            tools=request.tools,
            llm_config=request.llm_config
        )
        return agent
    except Exception as e:
        logger.error("Failed to create agent", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agents",
    summary="List Agents",
    description="Get all agents in the agent pool"
)
async def list_agents(
    active_only: bool = True,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """List all agents, optionally filtering by active status"""
    try:
        agents = crewai_service.get_agents(active_only=active_only)
        return {"agents": agents, "count": len(agents)}
    except Exception as e:
        logger.error("Failed to list agents", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agents/{agent_id}",
    summary="Get Agent",
    description="Retrieve a specific agent by ID"
)
async def get_agent(
    agent_id: str,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Get agent details by ID"""
    try:
        agent = crewai_service.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/agents/by-name/{agent_name}",
    summary="Get Agent by Name",
    description="Retrieve a specific agent by name"
)
async def get_agent_by_name(
    agent_name: str,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Get agent details by name"""
    try:
        agent = crewai_service.get_agent(agent_name=agent_name)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", agent_name=agent_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/agents/{agent_id}",
    summary="Update Agent",
    description="Update an existing agent's configuration"
)
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Update agent configuration"""
    try:
        agent = crewai_service.update_agent(
            agent_id=agent_id,
            role=request.role,
            goal=request.goal,
            backstory=request.backstory,
            tools=request.tools,
            llm_config=request.llm_config,
            is_active=request.is_active
        )
        return agent
    except Exception as e:
        logger.error("Failed to update agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/agents/{agent_id}",
    summary="Delete Agent",
    description="Delete an agent (soft delete by default)"
)
async def delete_agent(
    agent_id: str,
    hard_delete: bool = False,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Delete an agent (soft or hard delete)"""
    try:
        success = crewai_service.delete_agent(agent_id=agent_id, soft_delete=not hard_delete)
        return {
            "success": success,
            "agent_id": agent_id,
            "deleted_type": "hard" if hard_delete else "soft"
        }
    except Exception as e:
        logger.error("Failed to delete agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Crew Management Endpoints ====================

@router.post(
    "/crews",
    summary="Create Crew",
    description="Create a new crew (team of agents)",
    status_code=status.HTTP_201_CREATED
)
async def create_crew(
    request: CrewCreateRequest,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Create a new crew with specified agents"""
    try:
        crew = crewai_service.create_crew(
            crew_name=request.crew_name,
            description=request.description,
            agent_ids=request.agent_ids,
            process_type=request.process_type,
            memory_enabled=request.memory_enabled,
            verbose=request.verbose
        )
        return crew
    except Exception as e:
        logger.error("Failed to create crew", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/crews",
    summary="List Crews",
    description="Get all crews"
)
async def list_crews(
    active_only: bool = True,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """List all crews, optionally filtering by active status"""
    try:
        crews = crewai_service.get_crews(active_only=active_only)
        return {"crews": crews, "count": len(crews)}
    except Exception as e:
        logger.error("Failed to list crews", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/crews/{crew_id}",
    summary="Get Crew",
    description="Retrieve a specific crew by ID"
)
async def get_crew(
    crew_id: str,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Get crew details by ID"""
    try:
        crew = crewai_service.get_crew(crew_id=crew_id)
        if not crew:
            raise HTTPException(status_code=404, detail=f"Crew {crew_id} not found")
        return crew
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get crew", crew_id=crew_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/crews/by-name/{crew_name}",
    summary="Get Crew by Name",
    description="Retrieve a specific crew by name"
)
async def get_crew_by_name(
    crew_name: str,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Get crew details by name"""
    try:
        crew = crewai_service.get_crew(crew_name=crew_name)
        if not crew:
            raise HTTPException(status_code=404, detail=f"Crew '{crew_name}' not found")
        return crew
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get crew", crew_name=crew_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/crews/{crew_id}",
    summary="Update Crew",
    description="Update an existing crew's configuration"
)
async def update_crew(
    crew_id: str,
    request: CrewUpdateRequest,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Update crew configuration"""
    try:
        crew = crewai_service.update_crew(
            crew_id=crew_id,
            description=request.description,
            agent_ids=request.agent_ids,
            process_type=request.process_type,
            is_active=request.is_active
        )
        return crew
    except Exception as e:
        logger.error("Failed to update crew", crew_id=crew_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/crews/{crew_id}",
    summary="Delete Crew",
    description="Delete a crew (soft delete by default)"
)
async def delete_crew(
    crew_id: str,
    hard_delete: bool = False,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Delete a crew (soft or hard delete)"""
    try:
        success = crewai_service.delete_crew(crew_id=crew_id, soft_delete=not hard_delete)
        return {
            "success": success,
            "crew_id": crew_id,
            "deleted_type": "hard" if hard_delete else "soft"
        }
    except Exception as e:
        logger.error("Failed to delete crew", crew_id=crew_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Workflow Execution Endpoints ====================

class CrewExecutionRequest(BaseModel):
    crew_id: str = Field(..., description="UUID of the crew to execute")
    input_data: Dict[str, Any] = Field(..., description="Input data for the workflow")
    document_id: Optional[str] = Field(default=None, description="Optional document ID")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")
    execution_type: str = Field(default="manual", description="Type of execution")


@router.post(
    "/execute",
    summary="Execute Crew Workflow (Async)",
    description="Queue a crew workflow for async execution via Celery. Returns immediately with execution ID.",
    status_code=status.HTTP_202_ACCEPTED
)
async def execute_crew(
    request: CrewExecutionRequest,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """
    Queue a crew workflow for async execution.

    Returns HTTP 202 immediately with execution ID.
    Use GET /executions/{execution_id} to poll for status and results.
    """
    from app.tasks.crewai_workflows import execute_crew_async
    from datetime import datetime

    try:
        # Get crew details to validate and get agent_ids
        crew = crewai_service.get_crew(crew_id=request.crew_id)
        if not crew:
            raise HTTPException(status_code=404, detail=f"Crew {request.crew_id} not found")

        if not crew.get("is_active", False):
            raise HTTPException(status_code=400, detail=f"Crew {request.crew_id} is not active")

        agent_ids = crew.get("agent_ids", [])
        if not agent_ids:
            raise HTTPException(status_code=400, detail=f"Crew {request.crew_id} has no agents")

        # Create execution record immediately
        execution_data = {
            "crew_id": request.crew_id,
            "document_id": request.document_id,
            "user_id": request.user_id,
            "execution_type": request.execution_type,
            "input_data": request.input_data,
            "status": "pending",
            "total_tasks": len(agent_ids),
            "completed_tasks": 0,
            "failed_tasks": 0,
            "started_at": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }

        result = crewai_service.supabase.table("crewai_executions").insert(execution_data).execute()
        execution_id = result.data[0]["id"]

        # Queue Celery task for async execution
        task = execute_crew_async.apply_async(
            kwargs={
                "execution_id": execution_id,
                "crew_id": request.crew_id,
                "input_data": request.input_data,
                "agent_ids": agent_ids,
                "process_type": crew.get("process_type", "sequential"),
                "memory_enabled": crew.get("memory_enabled", True),
                "verbose": crew.get("verbose_mode", False)
            }
        )

        logger.info(
            "Crew execution queued",
            execution_id=execution_id,
            crew_id=request.crew_id,
            celery_task_id=task.id,
            agent_count=len(agent_ids)
        )

        # Return immediately with HTTP 202
        return {
            "id": execution_id,
            "crew_id": request.crew_id,
            "status": "pending",
            "celery_task_id": task.id,
            "total_tasks": len(agent_ids),
            "message": "Workflow queued for execution. Use GET /executions/{id} to check status.",
            "polling_url": f"/api/crewai/executions/{execution_id}",
            **execution_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to queue crew execution", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/executions/{execution_id}",
    summary="Get Execution",
    description="Get execution details by ID"
)
async def get_execution(
    execution_id: str,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Get execution details by ID"""
    try:
        execution = crewai_service.get_execution(execution_id=execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
        return execution
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get execution", execution_id=execution_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/executions",
    summary="List Executions",
    description="List executions with optional filtering"
)
async def list_executions(
    crew_id: Optional[str] = None,
    document_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """List executions with optional filters"""
    try:
        executions = crewai_service.get_executions(
            crew_id=crew_id,
            document_id=document_id,
            user_id=user_id,
            status=status,
            limit=limit
        )
        return {"executions": executions, "count": len(executions)}
    except Exception as e:
        logger.error("Failed to list executions", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/executions/{execution_id}/cancel",
    summary="Cancel Execution",
    description="Cancel a running execution"
)
async def cancel_execution(
    execution_id: str,
    crewai_service: CrewAIService = Depends(get_crewai_service)
):
    """Cancel a running execution"""
    try:
        success = crewai_service.cancel_execution(execution_id=execution_id)
        return {"success": success, "execution_id": execution_id}
    except Exception as e:
        logger.error("Failed to cancel execution", execution_id=execution_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Statistics & Analytics ====================

@router.get(
    "/stats",
    summary="Agent Pool Statistics",
    description="Get comprehensive statistics about the agent pool"
)
async def get_agent_pool_stats(crewai_service: CrewAIService = Depends(get_crewai_service)):
    """Get agent pool statistics including agents, crews, and executions"""
    try:
        stats = crewai_service.get_agent_pool_stats()
        return stats
    except Exception as e:
        logger.error("Failed to get agent pool stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AGENT-001: Orchestrator Endpoints (Task 41) ====================

from app.services.orchestrator_agent_service import (
    OrchestratorAgentService,
    OrchestratorResult,
    Department,
    AssetType
)


class OrchestratorRequest(BaseModel):
    """Request model for orchestrator content processing"""
    content: str = Field(..., description="Content to analyze and process", min_length=10)
    filename: Optional[str] = Field(default=None, description="Optional filename for context")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional additional metadata")
    user_id: Optional[str] = Field(default=None, description="Optional user ID for tracking")


class OrchestratorResponse(BaseModel):
    """Response model for orchestrator processing"""
    success: bool
    department: str
    department_confidence: float
    primary_asset_type: str
    all_asset_types: List[str]
    needs_summary: bool
    delegation_targets: List[str]
    output_paths: Dict[str, str]
    processing_time_seconds: float
    classification_reasoning: str
    asset_decision_reasoning: str


def get_orchestrator_service(supabase: Client = Depends(get_supabase)) -> OrchestratorAgentService:
    """Dependency to get OrchestratorAgentService instance"""
    return OrchestratorAgentService(supabase_client=supabase)


@router.post(
    "/orchestrator/process",
    summary="Process Content with AGENT-001",
    description="Analyze content using AGENT-001 (Master Content Analyzer & Asset Orchestrator). "
                "Classifies department (12 departments including R&D, >96% accuracy), selects asset types, "
                "and determines delegation targets.",
    response_model=OrchestratorResponse,
    tags=["crewai", "agent-001"]
)
async def orchestrator_process_content(
    request: OrchestratorRequest,
    orchestrator: OrchestratorAgentService = Depends(get_orchestrator_service)
):
    """
    AGENT-001: Master Content Analyzer & Asset Orchestrator

    Analyzes incoming content and makes intelligent decisions about:
    1. Department classification (12 departments including R&D)
    2. Asset type selection (skill/command/agent/prompt/workflow)
    3. Content summary requirements
    4. Delegation to specialized agents

    Target: >96% classification accuracy
    LLM: Claude Sonnet 4.5
    """
    try:
        logger.info(
            "AGENT-001 request received",
            content_length=len(request.content),
            filename=request.filename
        )

        result: OrchestratorResult = await orchestrator.process_content(
            content=request.content,
            filename=request.filename,
            metadata=request.metadata,
            user_id=request.user_id
        )

        return OrchestratorResponse(
            success=True,
            department=result.classification.department.value,
            department_confidence=result.classification.confidence,
            primary_asset_type=result.asset_decision.primary_type.value,
            all_asset_types=[a.value for a in result.asset_decision.asset_types],
            needs_summary=result.asset_decision.needs_summary,
            delegation_targets=result.delegation_targets,
            output_paths=result.output_paths,
            processing_time_seconds=result.processing_metadata.get("processing_time_seconds", 0),
            classification_reasoning=result.classification.reasoning,
            asset_decision_reasoning=result.asset_decision.reasoning
        )

    except Exception as e:
        logger.error("AGENT-001 processing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orchestrator processing failed: {str(e)}"
        )


@router.get(
    "/orchestrator/stats",
    summary="AGENT-001 Statistics",
    description="Get processing statistics for AGENT-001 orchestrator"
)
async def orchestrator_stats(
    orchestrator: OrchestratorAgentService = Depends(get_orchestrator_service)
):
    """Get AGENT-001 processing statistics"""
    try:
        stats = orchestrator.get_stats()
        return {
            "agent_id": "AGENT-001",
            "agent_name": "Master Content Analyzer & Asset Orchestrator",
            "statistics": stats
        }
    except Exception as e:
        logger.error("Failed to get orchestrator stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/orchestrator/departments",
    summary="List Departments",
    description="Get list of all available departments for classification"
)
async def list_departments():
    """Get list of all available departments"""
    departments = [
        {
            "code": d.value,
            "name": d.name.replace("_", " ").title(),
            "description": _get_department_description(d)
        }
        for d in Department
    ]
    return {"departments": departments, "count": len(departments)}


@router.get(
    "/orchestrator/asset-types",
    summary="List Asset Types",
    description="Get list of all available asset types for generation"
)
async def list_asset_types():
    """Get list of all available asset types"""
    asset_types = [
        {
            "code": a.value,
            "name": a.name.replace("_", " ").title(),
            "description": _get_asset_type_description(a),
            "file_extension": _get_asset_extension(a)
        }
        for a in AssetType
    ]
    return {"asset_types": asset_types, "count": len(asset_types)}


def _get_department_description(dept: Department) -> str:
    """Get description for department (12 departments v7.3)"""
    descriptions = {
        Department.IT_ENGINEERING: "Software development, infrastructure, DevOps, technical systems",
        Department.SALES_MARKETING: "Sales processes, marketing campaigns, lead generation, CRM",
        Department.CUSTOMER_SUPPORT: "Customer service, helpdesk, ticketing, issue resolution",
        Department.OPERATIONS_HR_SUPPLY: "HR, operations, supply chain, logistics, workforce management",
        Department.FINANCE_ACCOUNTING: "Financial operations, accounting, budgeting, auditing",
        Department.PROJECT_MANAGEMENT: "Project planning, Agile/Scrum, milestones, resource management",
        Department.REAL_ESTATE: "Property management, leasing, real estate transactions",
        Department.PRIVATE_EQUITY_MA: "Private equity, mergers & acquisitions, valuations, investments",
        Department.CONSULTING: "Strategic consulting, advisory services, frameworks, recommendations",
        Department.PERSONAL_CONTINUING_ED: "Education, training, professional development, courses",
        Department.GLOBAL: "Cross-department or multi-department content",
        Department.RESEARCH_DEVELOPMENT: "R&D, innovation, prototyping, experiments, patents, product development"
    }
    return descriptions.get(dept, "")


def _get_asset_type_description(asset: AssetType) -> str:
    """Get description for asset type"""
    descriptions = {
        AssetType.SKILL: "Complex reusable automation with parameters and logic (YAML)",
        AssetType.COMMAND: "Quick one-liner actions and shortcuts (Markdown)",
        AssetType.AGENT: "Multi-step role-based intelligent tasks (YAML)",
        AssetType.PROMPT: "Reusable AI prompt templates (Markdown) - DEFAULT",
        AssetType.WORKFLOW: "Multi-system automation sequences (JSON)"
    }
    return descriptions.get(asset, "")


def _get_asset_extension(asset: AssetType) -> str:
    """Get file extension for asset type"""
    extensions = {
        AssetType.SKILL: ".yaml",
        AssetType.COMMAND: ".md",
        AssetType.AGENT: ".yaml",
        AssetType.PROMPT: ".md",
        AssetType.WORKFLOW: ".json"
    }
    return extensions.get(asset, "")
