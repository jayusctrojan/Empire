"""
Empire v7.3 - Content Summarizer Agent API Routes
Task 42: Implement Content Summarizer Agent (AGENT-002)

Provides REST API endpoints for generating PDF summaries with visual diagrams.
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
import structlog

from app.services.content_summarizer_agent import (
    get_content_summarizer_service,
    ContentSummarizerAgentService,
    DiagramType,
    DiagramSpec,
    SummaryGenerationResult
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/summarizer", tags=["Content Summarizer"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GenerateSummaryRequest(BaseModel):
    """Request model for summary generation"""
    content: str = Field(..., min_length=100, description="Content to summarize")
    department: str = Field(..., description="Target department code")
    title: str = Field(..., min_length=1, max_length=200, description="Summary title")
    source_type: str = Field(
        default="document",
        description="Type of source content (document, video, course, article)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )


class GenerateSummaryResponse(BaseModel):
    """Response model for summary generation"""
    success: bool
    pdf_path: Optional[str] = None
    department: str
    title: str
    sections_generated: List[str] = []
    diagrams_generated: int = 0
    tables_generated: int = 0
    error: Optional[str] = None
    processing_time_seconds: float = 0.0
    metadata: Dict[str, Any] = {}


class CreateDiagramRequest(BaseModel):
    """Request model for diagram creation"""
    diagram_type: DiagramType = Field(..., description="Type of diagram to create")
    title: str = Field(..., min_length=1, max_length=100, description="Diagram title")
    department: str = Field(..., description="Department for output path")
    elements: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Elements to include in diagram"
    )
    connections: List[Dict[str, Any]] = Field(
        default=[],
        description="Connections between elements (for flowcharts)"
    )
    style: Dict[str, Any] = Field(
        default={},
        description="Custom styling options"
    )


class CreateDiagramResponse(BaseModel):
    """Response model for diagram creation"""
    success: bool
    diagram_path: Optional[str] = None
    diagram_type: str
    error: Optional[str] = None


class CreateChartRequest(BaseModel):
    """Request model for chart creation"""
    chart_type: str = Field(..., description="Type of chart (bar, pie)")
    title: str = Field(..., description="Chart title")
    department: str = Field(..., description="Department for output path")
    labels: List[str] = Field(..., description="Labels for data points")
    values: List[float] = Field(..., description="Values for data points")
    ylabel: Optional[str] = Field(default="Value", description="Y-axis label (for bar charts)")


class CreateChartResponse(BaseModel):
    """Response model for chart creation"""
    success: bool
    chart_path: Optional[str] = None
    chart_type: str
    error: Optional[str] = None


class SummarizerStatsResponse(BaseModel):
    """Response model for summarizer statistics"""
    agent_id: str
    agent_name: str
    summaries_generated: int
    diagrams_created: int
    charts_created: int
    by_department: Dict[str, int]


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_summarizer_service() -> ContentSummarizerAgentService:
    """Dependency for content summarizer service"""
    return get_content_summarizer_service()


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=GenerateSummaryResponse)
async def generate_summary(
    request: GenerateSummaryRequest,
    summarizer: ContentSummarizerAgentService = Depends(get_summarizer_service)
) -> GenerateSummaryResponse:
    """
    Generate a comprehensive PDF summary from content.

    Creates a professional PDF document with:
    - Executive summary
    - Key concepts
    - Detailed breakdowns
    - Visual diagrams
    - Implementation guides
    - Quick reference sections

    The PDF is saved to: processed/crewai-summaries/{department}/
    """
    try:
        logger.info(
            "Summary generation request",
            department=request.department,
            title=request.title,
            content_length=len(request.content)
        )

        result = await summarizer.generate_summary(
            content=request.content,
            department=request.department,
            title=request.title,
            source_type=request.source_type,
            metadata=request.metadata
        )

        return GenerateSummaryResponse(
            success=result.success,
            pdf_path=result.pdf_path,
            department=result.department,
            title=result.title,
            sections_generated=result.sections_generated,
            diagrams_generated=result.diagrams_generated,
            tables_generated=result.tables_generated,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error("Summary generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/file", response_model=GenerateSummaryResponse)
async def generate_summary_from_file(
    file: UploadFile = File(..., description="Document file to summarize"),
    department: str = Form(..., description="Target department code"),
    title: Optional[str] = Form(None, description="Summary title (defaults to filename)"),
    source_type: str = Form(default="document", description="Source type"),
    summarizer: ContentSummarizerAgentService = Depends(get_summarizer_service)
) -> GenerateSummaryResponse:
    """
    Generate a PDF summary from an uploaded file.

    Supported file types:
    - Text files (.txt, .md)
    - PDF files (.pdf) - text extraction
    - Word documents (.docx) - text extraction
    """
    try:
        # Read file content
        content = await file.read()

        # Decode text content
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            # Try latin-1 for binary-ish text files
            try:
                text_content = content.decode('latin-1')
            except:
                raise HTTPException(
                    status_code=400,
                    detail="Could not decode file content. Please upload a text file."
                )

        # Use filename as title if not provided
        summary_title = title or file.filename or "Untitled Summary"

        logger.info(
            "Summary generation from file",
            filename=file.filename,
            department=department,
            content_length=len(text_content)
        )

        result = await summarizer.generate_summary(
            content=text_content,
            department=department,
            title=summary_title,
            source_type=source_type
        )

        return GenerateSummaryResponse(
            success=result.success,
            pdf_path=result.pdf_path,
            department=result.department,
            title=result.title,
            sections_generated=result.sections_generated,
            diagrams_generated=result.diagrams_generated,
            tables_generated=result.tables_generated,
            error=result.error,
            processing_time_seconds=result.processing_time_seconds,
            metadata=result.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File summary generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagram", response_model=CreateDiagramResponse)
async def create_diagram(
    request: CreateDiagramRequest,
    summarizer: ContentSummarizerAgentService = Depends(get_summarizer_service)
) -> CreateDiagramResponse:
    """
    Create a visual diagram.

    Supported diagram types:
    - flowchart: Vertical flow diagram
    - hierarchy: Tree/hierarchy structure
    - process: Horizontal process steps
    - timeline: Timeline of events
    - comparison: Side-by-side comparison
    """
    try:
        logger.info(
            "Diagram creation request",
            type=request.diagram_type.value,
            department=request.department,
            elements_count=len(request.elements)
        )

        spec = DiagramSpec(
            diagram_type=request.diagram_type,
            title=request.title,
            elements=request.elements,
            connections=request.connections,
            style=request.style
        )

        diagram_path = summarizer.diagram_creator.create_diagram(
            spec=spec,
            department=request.department
        )

        return CreateDiagramResponse(
            success=True,
            diagram_path=diagram_path,
            diagram_type=request.diagram_type.value
        )

    except Exception as e:
        logger.error("Diagram creation failed", error=str(e))
        return CreateDiagramResponse(
            success=False,
            diagram_type=request.diagram_type.value,
            error=str(e)
        )


@router.post("/chart", response_model=CreateChartResponse)
async def create_chart(
    request: CreateChartRequest,
    summarizer: ContentSummarizerAgentService = Depends(get_summarizer_service)
) -> CreateChartResponse:
    """
    Create a chart (bar or pie).

    Chart types:
    - bar: Vertical bar chart
    - pie: Pie chart with percentages
    """
    try:
        logger.info(
            "Chart creation request",
            type=request.chart_type,
            department=request.department,
            data_points=len(request.labels)
        )

        if request.chart_type == "bar":
            chart_path = summarizer.chart_builder.create_bar_chart(
                title=request.title,
                labels=request.labels,
                values=request.values,
                department=request.department,
                ylabel=request.ylabel
            )
        elif request.chart_type == "pie":
            chart_path = summarizer.chart_builder.create_pie_chart(
                title=request.title,
                labels=request.labels,
                values=request.values,
                department=request.department
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported chart type: {request.chart_type}. Use 'bar' or 'pie'."
            )

        return CreateChartResponse(
            success=True,
            chart_path=chart_path,
            chart_type=request.chart_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chart creation failed", error=str(e))
        return CreateChartResponse(
            success=False,
            chart_type=request.chart_type,
            error=str(e)
        )


@router.get("/stats", response_model=SummarizerStatsResponse)
async def get_summarizer_stats(
    summarizer: ContentSummarizerAgentService = Depends(get_summarizer_service)
) -> SummarizerStatsResponse:
    """Get statistics for the Content Summarizer Agent"""
    stats = summarizer.get_stats()
    return SummarizerStatsResponse(
        agent_id=stats.get("agent_id", "AGENT-002"),
        agent_name=stats.get("agent_name", "Content Summarizer Agent"),
        summaries_generated=stats.get("summaries_generated", 0),
        diagrams_created=stats.get("diagrams_created", 0),
        charts_created=stats.get("charts_created", 0),
        by_department=stats.get("by_department", {})
    )


@router.get("/departments")
async def get_supported_departments() -> Dict[str, List[str]]:
    """Get list of supported department codes"""
    return {
        "departments": [
            "it-engineering",
            "sales-marketing",
            "customer-support",
            "operations-hr-supply",
            "finance-accounting",
            "project-management",
            "real-estate",
            "private-equity-ma",
            "consulting",
            "personal-continuing-ed",
            "_global",
            "research-development"
        ],
        "diagram_types": [t.value for t in DiagramType],
        "chart_types": ["bar", "pie"]
    }


@router.get("/health")
async def summarizer_health() -> Dict[str, Any]:
    """Health check for Content Summarizer Agent"""
    return {
        "status": "healthy",
        "agent_id": "AGENT-002",
        "agent_name": "Content Summarizer Agent",
        "capabilities": {
            "pdf_generation": True,
            "diagram_creation": True,
            "chart_creation": True,
            "llm_summarization": bool(os.getenv("ANTHROPIC_API_KEY"))
        }
    }
