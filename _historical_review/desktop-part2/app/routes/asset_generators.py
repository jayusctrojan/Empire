"""
Empire v7.3 - Asset Generator API Routes (Task 43)

REST API endpoints for asset generation (AGENT-003 to AGENT-007):
- AGENT-003: Skill Generator (YAML for Claude Code)
- AGENT-004: Command Generator (Markdown slash commands)
- AGENT-005: Agent Generator (CrewAI YAML configs)
- AGENT-006: Prompt Generator (reusable prompt templates)
- AGENT-007: Workflow Generator (n8n JSON workflows)
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import structlog

from app.services.asset_generator_agents import (
    get_asset_generator_service,
    AssetGeneratorService,
    AssetType,
    AssetGenerationRequest,
    AssetGenerationResult,
    Department
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/assets", tags=["Asset Generators"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GenerateAssetRequest(BaseModel):
    """Request model for asset generation"""
    name: str = Field(..., min_length=1, max_length=100, description="Asset name")
    description: str = Field(..., min_length=10, description="What the asset should do")
    department: str = Field(..., description="Target department")
    context: Optional[str] = Field(None, description="Additional context or requirements")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerateAssetResponse(BaseModel):
    """Response model for asset generation"""
    success: bool
    asset_type: str
    asset_name: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    department: str
    error: Optional[str] = None
    processing_time_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchGenerateRequest(BaseModel):
    """Request for generating multiple assets"""
    assets: List[GenerateAssetRequest] = Field(..., min_length=1, max_length=10)
    asset_type: str = Field(..., description="Type of assets to generate")


class BatchGenerateResponse(BaseModel):
    """Response for batch generation"""
    success: bool
    total_requested: int
    total_generated: int
    results: List[GenerateAssetResponse]
    errors: List[str] = []


class GeneratorInfo(BaseModel):
    """Information about an asset generator"""
    agent_id: str
    agent_name: str
    asset_type: str
    file_extension: str


class GeneratorStatsResponse(BaseModel):
    """Response model for generator statistics"""
    agent_id: str
    agent_name: str
    asset_type: str
    assets_generated: int
    by_department: Dict[str, int]


class AllStatsResponse(BaseModel):
    """Response model for all generator statistics"""
    generators: Dict[str, GeneratorStatsResponse]


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_generator_service() -> AssetGeneratorService:
    """Dependency for asset generator service"""
    return get_asset_generator_service()


# =============================================================================
# SKILL GENERATOR ENDPOINTS (AGENT-003)
# =============================================================================

@router.post("/skill", response_model=GenerateAssetResponse)
async def generate_skill(
    request: GenerateAssetRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GenerateAssetResponse:
    """
    Generate a Claude Code skill (AGENT-003).

    Creates a YAML skill file with:
    - Tool definitions
    - Instructions
    - Usage examples
    - Tags for organization

    Output: processed/crewai-suggestions/skill/drafts/{department}/
    """
    try:
        logger.info(
            "Skill generation request",
            name=request.name,
            department=request.department
        )

        gen_request = AssetGenerationRequest(
            name=request.name,
            description=request.description,
            department=request.department,
            context=request.context,
            metadata=request.metadata
        )

        result = await service.generate_skill(gen_request)

        return GenerateAssetResponse(
            success=result.success,
            asset_type=result.asset_type,
            asset_name=result.asset_name,
            file_path=result.file_path,
            content=result.content,
            department=result.department,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error("Skill generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# COMMAND GENERATOR ENDPOINTS (AGENT-004)
# =============================================================================

@router.post("/command", response_model=GenerateAssetResponse)
async def generate_command(
    request: GenerateAssetRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GenerateAssetResponse:
    """
    Generate a slash command (AGENT-004).

    Creates a Markdown command file with:
    - Command description
    - Arguments with types
    - Step-by-step instructions
    - Usage examples

    Output: processed/crewai-suggestions/command/drafts/{department}/
    """
    try:
        logger.info(
            "Command generation request",
            name=request.name,
            department=request.department
        )

        gen_request = AssetGenerationRequest(
            name=request.name,
            description=request.description,
            department=request.department,
            context=request.context,
            metadata=request.metadata
        )

        result = await service.generate_command(gen_request)

        return GenerateAssetResponse(
            success=result.success,
            asset_type=result.asset_type,
            asset_name=result.asset_name,
            file_path=result.file_path,
            content=result.content,
            department=result.department,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error("Command generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# AGENT GENERATOR ENDPOINTS (AGENT-005)
# =============================================================================

@router.post("/agent", response_model=GenerateAssetResponse)
async def generate_agent(
    request: GenerateAssetRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GenerateAssetResponse:
    """
    Generate a CrewAI agent configuration (AGENT-005).

    Creates a YAML agent config with:
    - Role definition
    - Goals and backstory
    - Tool assignments
    - LLM configuration

    Output: processed/crewai-suggestions/agent/drafts/{department}/
    """
    try:
        logger.info(
            "Agent generation request",
            name=request.name,
            department=request.department
        )

        gen_request = AssetGenerationRequest(
            name=request.name,
            description=request.description,
            department=request.department,
            context=request.context,
            metadata=request.metadata
        )

        result = await service.generate_agent(gen_request)

        return GenerateAssetResponse(
            success=result.success,
            asset_type=result.asset_type,
            asset_name=result.asset_name,
            file_path=result.file_path,
            content=result.content,
            department=result.department,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error("Agent generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PROMPT GENERATOR ENDPOINTS (AGENT-006)
# =============================================================================

@router.post("/prompt", response_model=GenerateAssetResponse)
async def generate_prompt(
    request: GenerateAssetRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GenerateAssetResponse:
    """
    Generate a prompt template (AGENT-006).

    Creates a YAML prompt template with:
    - Template with variable placeholders
    - Variable definitions
    - Usage examples
    - Tags for organization

    Output: processed/crewai-suggestions/prompt/drafts/{department}/
    """
    try:
        logger.info(
            "Prompt generation request",
            name=request.name,
            department=request.department
        )

        gen_request = AssetGenerationRequest(
            name=request.name,
            description=request.description,
            department=request.department,
            context=request.context,
            metadata=request.metadata
        )

        result = await service.generate_prompt(gen_request)

        return GenerateAssetResponse(
            success=result.success,
            asset_type=result.asset_type,
            asset_name=result.asset_name,
            file_path=result.file_path,
            content=result.content,
            department=result.department,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error("Prompt generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WORKFLOW GENERATOR ENDPOINTS (AGENT-007)
# =============================================================================

@router.post("/workflow", response_model=GenerateAssetResponse)
async def generate_workflow(
    request: GenerateAssetRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GenerateAssetResponse:
    """
    Generate an n8n workflow (AGENT-007).

    Creates a JSON workflow with:
    - Node definitions
    - Connection mappings
    - Workflow settings
    - Trigger configurations

    Output: processed/crewai-suggestions/workflow/drafts/{department}/
    """
    try:
        logger.info(
            "Workflow generation request",
            name=request.name,
            department=request.department
        )

        gen_request = AssetGenerationRequest(
            name=request.name,
            description=request.description,
            department=request.department,
            context=request.context,
            metadata=request.metadata
        )

        result = await service.generate_workflow(gen_request)

        return GenerateAssetResponse(
            success=result.success,
            asset_type=result.asset_type,
            asset_name=result.asset_name,
            file_path=result.file_path,
            content=result.content,
            department=result.department,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error("Workflow generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GENERIC GENERATION ENDPOINT
# =============================================================================

@router.post("/generate/{asset_type}", response_model=GenerateAssetResponse)
async def generate_asset(
    asset_type: str,
    request: GenerateAssetRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GenerateAssetResponse:
    """
    Generate any asset type by specifying the type in the URL.

    Supported types: skill, command, agent, prompt, workflow
    """
    try:
        # Validate asset type
        try:
            asset_type_enum = AssetType(asset_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset type: {asset_type}. Valid types: {[t.value for t in AssetType]}"
            )

        logger.info(
            "Asset generation request",
            asset_type=asset_type,
            name=request.name,
            department=request.department
        )

        gen_request = AssetGenerationRequest(
            name=request.name,
            description=request.description,
            department=request.department,
            context=request.context,
            metadata=request.metadata
        )

        result = await service.generate(asset_type_enum, gen_request)

        return GenerateAssetResponse(
            success=result.success,
            asset_type=result.asset_type,
            asset_name=result.asset_name,
            file_path=result.file_path,
            content=result.content,
            department=result.department,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Asset generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# BATCH GENERATION ENDPOINT
# =============================================================================

@router.post("/batch", response_model=BatchGenerateResponse)
async def batch_generate_assets(
    request: BatchGenerateRequest,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> BatchGenerateResponse:
    """
    Generate multiple assets of the same type in batch.

    Maximum 10 assets per batch request.
    """
    try:
        # Validate asset type
        try:
            asset_type_enum = AssetType(request.asset_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset type: {request.asset_type}. Valid types: {[t.value for t in AssetType]}"
            )

        logger.info(
            "Batch generation request",
            asset_type=request.asset_type,
            count=len(request.assets)
        )

        results = []
        errors = []
        total_generated = 0

        for asset_request in request.assets:
            try:
                gen_request = AssetGenerationRequest(
                    name=asset_request.name,
                    description=asset_request.description,
                    department=asset_request.department,
                    context=asset_request.context,
                    metadata=asset_request.metadata
                )

                result = await service.generate(asset_type_enum, gen_request)

                results.append(GenerateAssetResponse(
                    success=result.success,
                    asset_type=result.asset_type,
                    asset_name=result.asset_name,
                    file_path=result.file_path,
                    content=result.content,
                    department=result.department,
                    error=result.error,
                    processing_time_seconds=result.processing_time_seconds,
                    metadata=result.metadata
                ))

                if result.success:
                    total_generated += 1
                else:
                    errors.append(f"{asset_request.name}: {result.error}")

            except Exception as e:
                errors.append(f"{asset_request.name}: {str(e)}")
                results.append(GenerateAssetResponse(
                    success=False,
                    asset_type=request.asset_type,
                    asset_name=asset_request.name,
                    department=asset_request.department,
                    error=str(e)
                ))

        return BatchGenerateResponse(
            success=total_generated > 0,
            total_requested=len(request.assets),
            total_generated=total_generated,
            results=results,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# METADATA ENDPOINTS
# =============================================================================

@router.get("/generators", response_model=List[GeneratorInfo])
async def list_generators(
    service: AssetGeneratorService = Depends(get_generator_service)
) -> List[GeneratorInfo]:
    """List all available asset generators."""
    generators = service.list_generators()
    return [GeneratorInfo(**g) for g in generators]


@router.get("/types")
async def get_asset_types() -> Dict[str, List[str]]:
    """Get all supported asset types and departments."""
    return {
        "asset_types": [t.value for t in AssetType],
        "departments": [d.value for d in Department],
        "file_extensions": {
            "skill": ".yaml",
            "command": ".md",
            "agent": ".yaml",
            "prompt": ".yaml",
            "workflow": ".json"
        }
    }


@router.get("/departments")
async def get_departments() -> Dict[str, Any]:
    """Get list of supported departments with descriptions."""
    return {
        "departments": [
            {"code": "it-engineering", "name": "IT & Engineering"},
            {"code": "sales-marketing", "name": "Sales & Marketing"},
            {"code": "customer-support", "name": "Customer Support"},
            {"code": "operations-hr-supply", "name": "Operations, HR & Supply Chain"},
            {"code": "finance-accounting", "name": "Finance & Accounting"},
            {"code": "project-management", "name": "Project Management"},
            {"code": "real-estate", "name": "Real Estate"},
            {"code": "private-equity-ma", "name": "Private Equity & M&A"},
            {"code": "consulting", "name": "Consulting"},
            {"code": "personal-continuing-ed", "name": "Personal & Continuing Education"}
        ]
    }


# =============================================================================
# STATISTICS ENDPOINTS
# =============================================================================

@router.get("/stats/{asset_type}", response_model=GeneratorStatsResponse)
async def get_generator_stats(
    asset_type: str,
    service: AssetGeneratorService = Depends(get_generator_service)
) -> GeneratorStatsResponse:
    """Get statistics for a specific generator."""
    try:
        asset_type_enum = AssetType(asset_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset type: {asset_type}"
        )

    generator = service.get_generator(asset_type_enum)
    if not generator:
        raise HTTPException(
            status_code=404,
            detail=f"Generator not found for type: {asset_type}"
        )

    stats = generator.get_stats()
    return GeneratorStatsResponse(
        agent_id=stats["agent_id"],
        agent_name=stats["agent_name"],
        asset_type=stats["asset_type"],
        assets_generated=stats["assets_generated"],
        by_department=stats["by_department"]
    )


@router.get("/stats", response_model=AllStatsResponse)
async def get_all_stats(
    service: AssetGeneratorService = Depends(get_generator_service)
) -> AllStatsResponse:
    """Get statistics for all generators."""
    all_stats = service.get_all_stats()
    return AllStatsResponse(
        generators={
            agent_id: GeneratorStatsResponse(
                agent_id=stats["agent_id"],
                agent_name=stats["agent_name"],
                asset_type=stats["asset_type"],
                assets_generated=stats["assets_generated"],
                by_department=stats["by_department"]
            )
            for agent_id, stats in all_stats.items()
        }
    )


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/health")
async def asset_generators_health() -> Dict[str, Any]:
    """Health check for Asset Generator agents."""
    service = get_asset_generator_service()
    generators = service.list_generators()

    return {
        "status": "healthy",
        "agents": {
            "AGENT-003": "Skill Generator",
            "AGENT-004": "Command Generator",
            "AGENT-005": "Agent Generator",
            "AGENT-006": "Prompt Generator",
            "AGENT-007": "Workflow Generator"
        },
        "generators_available": len(generators),
        "llm_available": bool(os.getenv("ANTHROPIC_API_KEY")),
        "output_path": service.output_base_path,
        "capabilities": {
            "skill_generation": True,
            "command_generation": True,
            "agent_generation": True,
            "prompt_generation": True,
            "workflow_generation": True,
            "batch_generation": True
        }
    }
