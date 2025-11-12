"""
Query processing endpoints with LangGraph + Arcade.dev support for Empire v7.3
Provides adaptive query processing with intelligent routing
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import structlog
import time

from app.workflows.langgraph_workflows import LangGraphWorkflows, QueryState
from app.workflows.workflow_router import workflow_router, WorkflowType
from app.services.arcade_service import arcade_service
from app.services.crewai_service import crewai_service
from app.tasks.query_tasks import (
    process_adaptive_query,
    process_auto_routed_query,
    batch_process_queries
)
from app.middleware.clerk_auth import verify_clerk_token

router = APIRouter(prefix="/api/query", tags=["query"])
logger = structlog.get_logger(__name__)


class AdaptiveQueryRequest(BaseModel):
    """Request for adaptive query processing."""
    query: str = Field(..., description="User query to process", min_length=1)
    max_iterations: int = Field(3, ge=1, le=5, description="Max refinement iterations")
    use_external_tools: bool = Field(True, description="Allow external API calls via Arcade")
    use_graph_context: bool = Field(True, description="Include Neo4j graph context")


class AdaptiveQueryResponse(BaseModel):
    """Response from adaptive query processing."""
    answer: str
    refined_queries: List[str] = []
    sources: List[dict] = []
    tool_calls: List[dict] = []
    iterations: int
    workflow_type: str
    processing_time_ms: int


class ToolListResponse(BaseModel):
    """Available tools information."""
    internal_tools: List[str]
    external_tools: List[str]
    total_count: int
    arcade_enabled: bool


class AsyncTaskResponse(BaseModel):
    """Response for async task submission."""
    task_id: str
    status: str
    message: str
    estimated_time_seconds: int


class TaskStatusResponse(BaseModel):
    """Response for task status check."""
    task_id: str
    status: str  # PENDING, STARTED, SUCCESS, FAILURE
    result: Optional[dict] = None
    error: Optional[str] = None
    progress: Optional[dict] = None


class BatchQueryRequest(BaseModel):
    """Request for batch query processing."""
    queries: List[str] = Field(..., description="List of queries to process", min_items=1, max_items=50)
    max_iterations: int = Field(2, ge=1, le=3, description="Max iterations per query")
    use_auto_routing: bool = Field(True, description="Auto-route vs direct LangGraph")


@router.get("/tools", response_model=ToolListResponse)
async def list_available_tools():
    """
    List all available tools (internal + Arcade.dev).

    Useful for debugging and understanding what capabilities are available.

    Returns:
        ToolListResponse with internal tools, external tools, and counts
    """
    try:
        internal = ["VectorSearch", "GraphQuery", "HybridSearch"]
        external = arcade_service.get_available_tools() if arcade_service.enabled else []

        logger.info(
            "Tools listed",
            internal_count=len(internal),
            external_count=len(external)
        )

        return ToolListResponse(
            internal_tools=internal,
            external_tools=external,
            total_count=len(internal) + len(external),
            arcade_enabled=arcade_service.enabled
        )

    except Exception as e:
        logger.error("Failed to list tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adaptive", response_model=AdaptiveQueryResponse)
async def adaptive_query_endpoint(
    request: AdaptiveQueryRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_clerk_token)
):
    """
    Execute adaptive query using LangGraph workflow with tool support.
    
    **Authentication Required**: Must provide valid Clerk JWT token.

    This endpoint provides:
    - Iterative query refinement
    - Conditional branching logic
    - Internal tool access (vector, graph search)
    - External tool access via Arcade.dev (when enabled and needed)
    - Quality evaluation and retry logic

    Use this for:
    - Research queries needing external context
    - Complex questions requiring refinement
    - Queries that might need web search

    Args:
        request: AdaptiveQueryRequest with query and configuration
        background_tasks: FastAPI background tasks

    Returns:
        AdaptiveQueryResponse with answer, sources, and metadata

    Example:
        ```json
        {
            "query": "Compare our policies with current California regulations",
            "max_iterations": 3,
            "use_external_tools": true
        }
        ```
    """
    start_time = time.time()

    try:
        logger.info(
            "Adaptive query started",
            query=request.query[:50],
            max_iterations=request.max_iterations,
            user_id=user["user_id"]
        )

        # Initialize workflow
        workflows = LangGraphWorkflows()
        graph = workflows.build_adaptive_research_graph()

        # Set initial state
        initial_state: QueryState = {
            "query": request.query,
            "messages": [],
            "refined_queries": [],
            "search_results": [],
            "tool_calls": [],
            "final_answer": "",
            "iteration_count": 0,
            "max_iterations": request.max_iterations,
            "needs_external_data": False
        }

        # Execute graph
        result = await graph.ainvoke(initial_state)

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "Adaptive query completed",
            iterations=result["iteration_count"],
            processing_time_ms=processing_time,
            tool_calls=len(result.get("tool_calls", []))
        )

        return AdaptiveQueryResponse(
            answer=result.get("final_answer", ""),
            refined_queries=result.get("refined_queries", []),
            sources=result.get("search_results", []),
            tool_calls=result.get("tool_calls", []),
            iterations=result["iteration_count"],
            workflow_type="langgraph",
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error("Adaptive query failed", error=str(e), query=request.query[:50])
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@router.post("/auto", response_model=AdaptiveQueryResponse)
async def auto_routed_query(
    request: AdaptiveQueryRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_clerk_token)
):
    """
    Automatically route query to optimal framework (CrewAI, LangGraph, or Simple RAG).
    
    **Authentication Required**: Must provide valid Clerk JWT token.

    The router analyzes the query and decides:
    - LangGraph: For adaptive queries needing refinement/external data
    - CrewAI: For multi-agent document processing workflows
    - Simple: For direct knowledge base lookups

    This is the recommended endpoint for most use cases.

    Args:
        request: AdaptiveQueryRequest with query and configuration
        background_tasks: FastAPI background tasks

    Returns:
        AdaptiveQueryResponse with answer, sources, and metadata

    Example:
        ```json
        {
            "query": "What are California insurance requirements?",
            "max_iterations": 2
        }
        ```
    """
    start_time = time.time()

    try:
        # Classify query
        classification = await workflow_router.classify_query(request.query)

        logger.info(
            "Query routed",
            workflow=classification.workflow_type.value,
            confidence=classification.confidence,
            query=request.query[:50],
            user_id=user["user_id"]
        )

        # Route to appropriate handler
        if classification.workflow_type == WorkflowType.LANGGRAPH:
            # Use LangGraph for adaptive processing
            return await adaptive_query_endpoint(request, background_tasks)

        elif classification.workflow_type == WorkflowType.CREWAI:
            # Route to CrewAI multi-agent service
            try:
                logger.info("Routing to CrewAI multi-agent workflow")

                # Call CrewAI service
                crewai_result = crewai_service.process_query(
                    query=request.query,
                    workflow_type="document_analysis",
                    max_iterations=request.max_iterations
                )

                processing_time = int((time.time() - start_time) * 1000)

                return AdaptiveQueryResponse(
                    answer=crewai_result.get("answer", ""),
                    refined_queries=crewai_result.get("refined_queries", []),
                    sources=crewai_result.get("sources", []),
                    tool_calls=crewai_result.get("agents_used", []),
                    iterations=len(crewai_result.get("steps", [])),
                    workflow_type="crewai",
                    processing_time_ms=processing_time
                )

            except Exception as e:
                logger.error("CrewAI processing failed", error=str(e))
                # Fallback to simple RAG on CrewAI failure
                processing_time = int((time.time() - start_time) * 1000)
                return AdaptiveQueryResponse(
                    answer=f"CrewAI service error (falling back to simple): {str(e)}",
                    workflow_type="simple",
                    processing_time_ms=processing_time,
                    iterations=0,
                    refined_queries=[],
                    sources=[],
                    tool_calls=[]
                )

        else:  # SIMPLE
            # Direct RAG pipeline (stub for now)
            processing_time = int((time.time() - start_time) * 1000)

            logger.info("Simple RAG query", query=request.query[:50])

            return AdaptiveQueryResponse(
                answer=f"Simple RAG result for: {request.query}",
                sources=[{"type": "vector", "content": "Stub result"}],
                workflow_type="simple",
                processing_time_ms=processing_time,
                iterations=0,
                refined_queries=[],
                tool_calls=[]
            )

    except Exception as e:
        logger.error("Auto-routed query failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Query routing failed: {str(e)}")


@router.post("/adaptive/async", response_model=AsyncTaskResponse)
async def adaptive_query_async(
    request: AdaptiveQueryRequest,
    user: dict = Depends(verify_clerk_token)
):
    """
    Submit adaptive query for async processing via Celery.
    
    **Authentication Required**: Must provide valid Clerk JWT token.

    Use this for:
    - Long-running queries (30+ seconds)
    - Queries requiring external web search
    - Batch processing workflows
    - Non-blocking API responses

    Returns task_id to poll for results via /query/status/{task_id}

    Args:
        request: AdaptiveQueryRequest with query and configuration

    Returns:
        AsyncTaskResponse with task_id for polling

    Example:
        ```json
        POST /api/query/adaptive/async
        {
            "query": "Research California insurance regulations",
            "max_iterations": 3
        }

        Response:
        {
            "task_id": "abc123...",
            "status": "PENDING",
            "message": "Query submitted for processing",
            "estimated_time_seconds": 60
        }
        ```
    """
    try:
        logger.info(
            "Async adaptive query submitted",
            query=request.query[:50],
            max_iterations=request.max_iterations,
            user_id=user["user_id"]
        )

        # Submit to Celery
        task = process_adaptive_query.apply_async(
            args=[request.query],
            kwargs={
                "max_iterations": request.max_iterations,
                "use_external_tools": request.use_external_tools
            }
        )

        logger.info("Celery task created", task_id=task.id)

        return AsyncTaskResponse(
            task_id=task.id,
            status="PENDING",
            message="Query submitted for async processing. Poll /query/status/{task_id} for results.",
            estimated_time_seconds=request.max_iterations * 30  # Rough estimate
        )

    except Exception as e:
        logger.error("Async query submission failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to submit async query: {str(e)}")


@router.post("/auto/async", response_model=AsyncTaskResponse)
async def auto_routed_query_async(
    request: AdaptiveQueryRequest,
    user: dict = Depends(verify_clerk_token)
):
    """
    Submit auto-routed query for async processing via Celery.
    
    **Authentication Required**: Must provide valid Clerk JWT token.

    Automatically routes to LangGraph, CrewAI, or Simple RAG based on query analysis.
    Returns task_id to poll for results.

    Args:
        request: AdaptiveQueryRequest with query and configuration

    Returns:
        AsyncTaskResponse with task_id for polling

    Example:
        ```json
        POST /api/query/auto/async
        {
            "query": "What are our vacation policies?"
        }

        Response:
        {
            "task_id": "xyz789...",
            "status": "PENDING",
            "message": "Query submitted for processing",
            "estimated_time_seconds": 30
        }
        ```
    """
    try:
        logger.info(
            "Async auto-routed query submitted",
            query=request.query[:50],
            user_id=user["user_id"]
        )

        # Submit to Celery with auto-routing
        task = process_auto_routed_query.apply_async(
            args=[request.query],
            kwargs={"max_iterations": request.max_iterations}
        )

        logger.info("Celery auto-routed task created", task_id=task.id)

        return AsyncTaskResponse(
            task_id=task.id,
            status="PENDING",
            message="Query submitted for auto-routed async processing. Poll /query/status/{task_id} for results.",
            estimated_time_seconds=30
        )

    except Exception as e:
        logger.error("Async auto-routed query submission failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to submit async query: {str(e)}")


@router.post("/batch", response_model=AsyncTaskResponse)
async def batch_query_processing(request: BatchQueryRequest):
    """
    Process multiple queries in batch via Celery.

    Submits all queries as async tasks and returns parent task_id.
    Use /query/status/{task_id} to check progress.

    Args:
        request: BatchQueryRequest with list of queries and configuration

    Returns:
        AsyncTaskResponse with parent task_id

    Example:
        ```json
        POST /api/query/batch
        {
            "queries": [
                "What are CA insurance laws?",
                "Compare with TX regulations",
                "Show compliance gaps"
            ],
            "max_iterations": 2,
            "use_auto_routing": true
        }
        ```
    """
    try:
        logger.info("Batch query processing started", query_count=len(request.queries))

        # Submit batch to Celery
        task = batch_process_queries.apply_async(
            args=[request.queries],
            kwargs={
                "max_iterations": request.max_iterations,
                "use_auto_routing": request.use_auto_routing
            }
        )

        logger.info("Celery batch task created", task_id=task.id)

        return AsyncTaskResponse(
            task_id=task.id,
            status="PENDING",
            message=f"Batch of {len(request.queries)} queries submitted for processing.",
            estimated_time_seconds=len(request.queries) * request.max_iterations * 20
        )

    except Exception as e:
        logger.error("Batch query submission failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to submit batch: {str(e)}")


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Check status of async query task.

    Poll this endpoint to get results from async query processing.

    Args:
        task_id: Celery task ID from async query submission

    Returns:
        TaskStatusResponse with status and result (if completed)

    Status Values:
    - PENDING: Task waiting to start
    - STARTED: Task currently processing
    - SUCCESS: Task completed successfully (result available)
    - FAILURE: Task failed (error available)

    Example:
        ```
        GET /api/query/status/abc123...

        Response (in progress):
        {
            "task_id": "abc123...",
            "status": "STARTED",
            "result": null,
            "error": null,
            "progress": {"iteration": 2, "max_iterations": 3}
        }

        Response (completed):
        {
            "task_id": "abc123...",
            "status": "SUCCESS",
            "result": {
                "answer": "Based on research...",
                "iterations": 3,
                "sources": [...]
            },
            "error": null
        }
        ```
    """
    try:
        from celery.result import AsyncResult

        # Get task result
        task = AsyncResult(task_id, app=process_adaptive_query.app)

        response = TaskStatusResponse(
            task_id=task_id,
            status=task.state,
            result=task.result if task.successful() else None,
            error=str(task.result) if task.failed() else None,
            progress=task.info if task.state == "STARTED" else None
        )

        logger.info(
            "Task status checked",
            task_id=task_id,
            status=task.state
        )

        return response

    except Exception as e:
        logger.error("Failed to check task status", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to check task status: {str(e)}")


@router.post("/search/faceted")
async def faceted_search(
    query: str = Query(..., description="Search query"),
    departments: Optional[List[str]] = Query(None, description="Filter by departments"),
    file_types: Optional[List[str]] = Query(None, description="Filter by file types"),
    date_from: Optional[str] = Query(None, description="Start date filter"),
    date_to: Optional[str] = Query(None, description="End date filter"),
    entities: Optional[List[str]] = Query(None, description="Filter by entities"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    user: dict = Depends(verify_clerk_token)
):
    """
    Faceted search with filtering and result presentation.

    **Authentication Required**: Must provide valid Clerk JWT token.

    Features:
    - Multi-select faceted filtering (department, file type, date, entities)
    - Snippet generation with keyword highlighting
    - Relevance scores and metadata
    - B2 URL links
    - Pagination

    Args:
        query: Search query text
        departments: Filter by departments (multi-select)
        file_types: Filter by file types (multi-select)
        date_from: Filter by date from (ISO format)
        date_to: Filter by date to (ISO format)
        entities: Filter by entities (multi-select)
        page: Page number (1-indexed)
        page_size: Results per page (1-100)

    Returns:
        Search results with facets, snippets, highlights, and metadata

    Example:
        ```json
        POST /api/query/search/faceted
        {
            "query": "California insurance policy",
            "departments": ["legal", "hr"],
            "file_types": ["pdf"],
            "page": 1,
            "page_size": 20
        }

        Response:
        {
            "results": [
                {
                    "chunk_id": "uuid",
                    "snippet": "...California <mark>insurance</mark> policy...",
                    "relevance_score": 0.95,
                    "source_file": "policy.pdf",
                    "department": "legal",
                    "b2_url": "https://..."
                }
            ],
            "facets": [
                {
                    "facet_type": "department",
                    "display_name": "Department",
                    "values": [
                        {"value": "legal", "display_name": "Legal", "count": 45, "selected": true}
                    ]
                }
            ],
            "total_results": 156,
            "page": 1,
            "page_size": 20,
            "total_pages": 8
        }
        ```
    """
    try:
        from app.services.faceted_search_service import get_faceted_search_service, FacetFilters
        from app.services.hybrid_search_service import get_hybrid_search_service
        from datetime import datetime

        logger.info(
            "Faceted search request",
            query=query[:50],
            departments=departments,
            file_types=file_types,
            user_id=user["user_id"]
        )

        # Build facet filters
        filters = FacetFilters(
            departments=departments or [],
            file_types=file_types or [],
            date_from=datetime.fromisoformat(date_from) if date_from else None,
            date_to=datetime.fromisoformat(date_to) if date_to else None,
            entities=entities or []
        )

        # Get services
        faceted_service = get_faceted_search_service()
        search_service = get_hybrid_search_service()

        # Perform hybrid search with filters
        # TODO: Integrate filters with actual search service
        # For now, using mock data

        # Mock search results
        mock_results = [
            {
                "chunk_id": "test-1",
                "document_id": "doc-1",
                "content": "California insurance policy requires minimum coverage...",
                "score": 0.95,
                "rank": 1,
                "metadata": {
                    "filename": "ca_insurance_policy.pdf",
                    "department": "legal",
                    "file_type": "pdf",
                    "created_at": "2024-01-15",
                    "b2_url": "https://b2.example.com/ca_insurance_policy.pdf"
                }
            }
        ]

        # Extract keywords from query for highlighting
        keywords = query.split()

        # Format results with snippets and highlights
        formatted_results = []
        document_ids = []

        for result in mock_results:
            formatted = faceted_service.format_search_result(
                chunk_id=result["chunk_id"],
                document_id=result["document_id"],
                content=result["content"],
                score=result["score"],
                rank=result["rank"],
                query_keywords=keywords,
                document_metadata=result["metadata"]
            )

            formatted_results.append({
                "chunk_id": formatted.chunk_id,
                "document_id": formatted.document_id,
                "snippet": formatted.highlighted_snippet,
                "relevance_score": formatted.relevance_score,
                "source_file": formatted.source_file,
                "department": formatted.department,
                "file_type": formatted.file_type,
                "created_at": formatted.created_at,
                "b2_url": formatted.b2_url,
                "rank": formatted.rank
            })

            document_ids.append(result["document_id"])

        # Extract facets from results
        facets = await faceted_service.extract_facets(document_ids, filters)

        # Format facets for response
        facets_data = [
            {
                "facet_type": facet.facet_type.value,
                "display_name": facet.display_name,
                "multi_select": facet.multi_select,
                "values": [
                    {
                        "value": val.value,
                        "display_name": val.display_name,
                        "count": val.count,
                        "selected": val.selected
                    }
                    for val in facet.values
                ]
            }
            for facet in facets
        ]

        # Calculate pagination
        total_results = len(formatted_results)  # Mock - should be actual count
        total_pages = (total_results + page_size - 1) // page_size

        logger.info(
            "Faceted search completed",
            results_count=len(formatted_results),
            facets_count=len(facets)
        )

        return {
            "results": formatted_results,
            "facets": facets_data,
            "total_results": total_results,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "query": query,
            "filters_applied": not filters.is_empty()
        }

    except Exception as e:
        logger.error("Faceted search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Faceted search failed: {str(e)}")


@router.get("/health")
async def query_health():
    """
    Health check for query processing system.

    Returns:
        Health status with component availability
    """
    return {
        "status": "healthy",
        "langgraph_enabled": True,
        "arcade_enabled": arcade_service.enabled,
        "crewai_enabled": crewai_service.enabled,
        "crewai_healthy": crewai_service.health_check() if crewai_service.enabled else False,
        "workflow_router_enabled": True,
        "available_workflows": ["langgraph", "crewai", "simple"],
        "async_processing": True,
        "celery_enabled": True,
        "faceted_search_enabled": True
    }
