"""
Empire v7.3 - Project-Scoped RAG API Routes
Task 64: Implement project-scoped hybrid RAG query endpoint

Endpoints:
- POST /api/projects/{project_id}/rag/query - Query with project sources + global KB
- POST /api/projects/{project_id}/rag/query/sources-only - Query project sources only
- GET /api/projects/{project_id}/rag/health - Health check
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
import structlog

from app.middleware.auth import get_current_user
from app.services.project_rag_service import (
    ProjectRAGService,
    ProjectRAGConfig,
    RAGResponse,
    RAGSource,
    Citation,
    get_project_rag_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Project RAG"])


# ============================================================================
# Request/Response Models
# ============================================================================

class RAGQueryRequest(BaseModel):
    """Request for project-scoped RAG query"""
    query: str = Field(..., min_length=1, max_length=4000, description="The query to answer")

    # Optional configuration overrides
    project_source_limit: int = Field(8, ge=1, le=20, description="Max project sources to retrieve")
    global_kb_limit: int = Field(5, ge=0, le=15, description="Max global KB sources to retrieve")
    project_weight: float = Field(1.0, ge=0.0, le=2.0, description="Weight for project sources in RRF")
    global_weight: float = Field(0.7, ge=0.0, le=2.0, description="Weight for global KB sources in RRF")
    min_similarity: float = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity threshold")
    include_global_kb: bool = Field(True, description="Whether to include global KB in search")

    # Query Expansion settings (Claude Haiku)
    enable_query_expansion: bool = Field(True, description="Use Claude Haiku to generate query variations")
    num_query_variations: int = Field(5, ge=1, le=10, description="Number of query variations to generate")
    expansion_strategy: str = Field("balanced", description="Expansion strategy: synonyms, reformulate, specific, broad, balanced, question")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the key points about insurance claims?",
                "project_source_limit": 8,
                "global_kb_limit": 5,
                "include_global_kb": True,
                "enable_query_expansion": True,
                "num_query_variations": 5,
                "expansion_strategy": "balanced"
            }
        }


class SourceResponse(BaseModel):
    """A source used in the RAG response"""
    id: str
    source_type: str  # 'project' or 'global'
    title: str
    content: str
    chunk_index: int
    similarity: float
    rank: int
    source_id: Optional[str] = None
    document_id: Optional[str] = None
    file_type: Optional[str] = None
    department: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CitationResponse(BaseModel):
    """A citation linking response text to a source (Task 66: Enhanced with clickable link info)"""
    source_id: str
    source_type: str
    title: str
    excerpt: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    confidence: float
    # Task 66: Enhanced fields for clickable links
    file_type: Optional[str] = None  # pdf, docx, youtube, website, etc.
    url: Optional[str] = None  # Direct URL for websites/YouTube
    youtube_timestamp: Optional[int] = None  # Seconds for YouTube seeking
    project_source_id: Optional[str] = None  # Link to project_sources table
    citation_marker: Optional[str] = None  # [1], [G1], etc.
    link_url: Optional[str] = None  # Pre-computed clickable URL


class RAGQueryResponse(BaseModel):
    """Response from project-scoped RAG query"""
    success: bool = True
    answer: str
    citations: List[CitationResponse]
    sources: List[SourceResponse]

    # Metadata
    project_sources_count: int
    global_sources_count: int
    total_sources: int
    query_time_ms: float
    model: str

    # Query Expansion metadata
    query_variations: List[str] = []
    expansion_time_ms: float = 0.0
    expansion_strategy: str = "balanced"

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "answer": "Based on the project sources [1] and global knowledge [G1], insurance claims...",
                "citations": [
                    {
                        "source_id": "abc123",
                        "source_type": "project",
                        "title": "Insurance Policy Guide.pdf",
                        "excerpt": "Claims must be filed within 30 days...",
                        "chunk_index": 2,
                        "confidence": 0.89
                    }
                ],
                "sources": [],
                "project_sources_count": 5,
                "global_sources_count": 3,
                "total_sources": 8,
                "query_time_ms": 1250.5,
                "model": "claude-sonnet-4-20250514",
                "query_variations": [
                    "What are the key points about insurance claims?",
                    "Insurance claim requirements and process",
                    "How to file an insurance claim",
                    "Important insurance claim information",
                    "Insurance claims documentation needed"
                ],
                "expansion_time_ms": 150.2,
                "expansion_strategy": "balanced"
            }
        }


class RAGHealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    project_sources_enabled: bool
    global_kb_enabled: bool
    embedding_model: str
    llm_model: str


# ============================================================================
# Dependencies
# ============================================================================

def get_service() -> ProjectRAGService:
    """Dependency for project RAG service"""
    return get_project_rag_service()


# ============================================================================
# Query Endpoints
# ============================================================================

@router.post("/{project_id}/rag/query", response_model=RAGQueryResponse)
async def query_project_rag(
    project_id: str,
    request: RAGQueryRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectRAGService = Depends(get_service)
) -> RAGQueryResponse:
    """
    Execute a project-scoped RAG query with Query Expansion.

    **Pipeline:**
    1. **Query Expansion** (Claude Haiku): Generate 5 query variations for better recall
    2. **Parallel Search**: Search project sources + global KB for all variations
    3. **RRF Fusion**: Combine results with weighted ranking
    4. **Response Generation** (Claude Sonnet): Answer with inline citations

    **Source Types:**
    - **Project Sources** (weight 1.0): Files, URLs, YouTube added to this project
    - **Global Knowledge Base** (weight 0.7): Organization-wide documents

    **Citation Format:**
    - `[1]`, `[2]`, etc. - References project-specific sources
    - `[G1]`, `[G2]`, etc. - References global knowledge base sources
    """
    try:
        logger.info(
            "Project RAG query received",
            project_id=project_id,
            user_id=user_id,
            query_length=len(request.query),
            include_global=request.include_global_kb,
            query_expansion=request.enable_query_expansion
        )

        # Build config from request
        config = ProjectRAGConfig(
            project_source_limit=request.project_source_limit,
            global_kb_limit=request.global_kb_limit if request.include_global_kb else 0,
            project_weight=request.project_weight,
            global_weight=request.global_weight if request.include_global_kb else 0,
            min_similarity=request.min_similarity,
            include_project_sources=True,
            include_global_kb=request.include_global_kb,
            # Query Expansion settings
            enable_query_expansion=request.enable_query_expansion,
            num_query_variations=request.num_query_variations,
            expansion_strategy=request.expansion_strategy
        )

        # Execute query
        result: RAGResponse = await service.query(
            project_id=project_id,
            user_id=user_id,
            query=request.query,
            config=config
        )

        # Convert to response models
        sources = [
            SourceResponse(
                id=s.id,
                source_type=s.source_type,
                title=s.title,
                content=s.content[:500] + "..." if len(s.content) > 500 else s.content,
                chunk_index=s.chunk_index,
                similarity=s.similarity,
                rank=s.rank,
                source_id=s.source_id,
                document_id=s.document_id,
                file_type=s.file_type,
                department=s.department,
                metadata=s.metadata
            )
            for s in result.sources_used
        ]

        # Task 66: Convert citations with enhanced clickable link metadata
        citations = [
            CitationResponse(
                source_id=c.source_id,
                source_type=c.source_type,
                title=c.title,
                excerpt=c.excerpt,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                confidence=c.confidence,
                # Enhanced fields for clickable links
                file_type=c.file_type,
                url=c.url,
                youtube_timestamp=c.youtube_timestamp,
                project_source_id=c.project_source_id,
                citation_marker=c.citation_marker,
                link_url=c.get_link_url() if hasattr(c, 'get_link_url') else None,
            )
            for c in result.citations
        ]

        return RAGQueryResponse(
            success=True,
            answer=result.answer,
            citations=citations,
            sources=sources,
            project_sources_count=result.project_sources_count,
            global_sources_count=result.global_sources_count,
            total_sources=result.total_sources,
            query_time_ms=result.query_time_ms,
            model=result.model,
            # Query Expansion metadata
            query_variations=result.query_variations,
            expansion_time_ms=result.expansion_time_ms,
            expansion_strategy=result.expansion_strategy
        )

    except Exception as e:
        logger.error(
            "Project RAG query failed",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/{project_id}/rag/query/sources-only", response_model=RAGQueryResponse)
async def query_project_sources_only(
    project_id: str,
    request: RAGQueryRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectRAGService = Depends(get_service)
) -> RAGQueryResponse:
    """
    Execute a RAG query using ONLY project sources (no global KB).

    **Pipeline:**
    1. **Query Expansion** (Claude Haiku): Generate query variations
    2. **Parallel Search**: Search project sources only for all variations
    3. **RRF Fusion**: Combine results
    4. **Response Generation** (Claude Sonnet): Answer with citations

    This is useful when you want answers strictly from the project's
    uploaded files, URLs, and YouTube content without any organization-wide
    knowledge base influence.

    All citations will be in the format [1], [2], etc.
    """
    try:
        logger.info(
            "Project sources-only RAG query",
            project_id=project_id,
            user_id=user_id,
            query_length=len(request.query),
            query_expansion=request.enable_query_expansion
        )

        # Override config to exclude global KB but include query expansion
        config = ProjectRAGConfig(
            project_source_limit=request.project_source_limit,
            global_kb_limit=0,  # Disable global KB
            project_weight=1.0,
            global_weight=0.0,
            min_similarity=request.min_similarity,
            include_project_sources=True,
            include_global_kb=False,
            # Query Expansion settings
            enable_query_expansion=request.enable_query_expansion,
            num_query_variations=request.num_query_variations,
            expansion_strategy=request.expansion_strategy
        )

        # Execute query
        result: RAGResponse = await service.query(
            project_id=project_id,
            user_id=user_id,
            query=request.query,
            config=config
        )

        # Convert to response models
        sources = [
            SourceResponse(
                id=s.id,
                source_type=s.source_type,
                title=s.title,
                content=s.content[:500] + "..." if len(s.content) > 500 else s.content,
                chunk_index=s.chunk_index,
                similarity=s.similarity,
                rank=s.rank,
                source_id=s.source_id,
                document_id=s.document_id,
                file_type=s.file_type,
                department=s.department,
                metadata=s.metadata
            )
            for s in result.sources_used
        ]

        # Task 66: Convert citations with enhanced clickable link metadata
        citations = [
            CitationResponse(
                source_id=c.source_id,
                source_type=c.source_type,
                title=c.title,
                excerpt=c.excerpt,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                confidence=c.confidence,
                # Enhanced fields for clickable links
                file_type=c.file_type,
                url=c.url,
                youtube_timestamp=c.youtube_timestamp,
                project_source_id=c.project_source_id,
                citation_marker=c.citation_marker,
                link_url=c.get_link_url() if hasattr(c, 'get_link_url') else None,
            )
            for c in result.citations
        ]

        return RAGQueryResponse(
            success=True,
            answer=result.answer,
            citations=citations,
            sources=sources,
            project_sources_count=result.project_sources_count,
            global_sources_count=0,
            total_sources=result.total_sources,
            query_time_ms=result.query_time_ms,
            model=result.model,
            # Query Expansion metadata
            query_variations=result.query_variations,
            expansion_time_ms=result.expansion_time_ms,
            expansion_strategy=result.expansion_strategy
        )

    except Exception as e:
        logger.error(
            "Project sources-only RAG query failed",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query failed: {str(e)}"
        )


# ============================================================================
# Streaming Endpoint (SSE-based streaming)
# ============================================================================

from fastapi.responses import StreamingResponse
import asyncio
import json


@router.post("/{project_id}/rag/query/stream")
async def stream_project_rag_query(
    project_id: str,
    request: RAGQueryRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectRAGService = Depends(get_service)
):
    """
    Stream a project-scoped RAG response using Server-Sent Events (SSE).

    Returns SSE stream with events:
    - 'sources' event: Retrieved sources for the query
    - 'token' events: Response tokens as they're generated
    - 'citations' event: Extracted citations from response
    - 'done' event: Completion signal with metadata
    - 'error' event: Error information if streaming fails

    The stream allows the client to receive partial results as they become
    available, improving perceived latency for long-running queries.
    """
    async def generate_sse():
        """SSE generator for streaming RAG response"""
        try:
            # Build config from request
            config = ProjectRAGConfig(
                project_source_limit=request.project_source_limit,
                global_kb_limit=request.global_kb_limit if request.include_global_kb else 0,
                project_weight=request.project_weight,
                global_weight=request.global_weight,
                min_similarity=request.min_similarity,
                include_project_sources=True,
                include_global_kb=request.include_global_kb,
                enable_query_expansion=request.enable_query_expansion,
                num_query_variations=request.num_query_variations,
                expansion_strategy=request.expansion_strategy
            )

            # First, retrieve and emit sources
            logger.info(
                "stream_rag_query_started",
                project_id=project_id,
                query_length=len(request.query)
            )

            # Get sources first (non-streaming retrieval)
            result = await service.query(
                project_id=project_id,
                user_id=user_id,
                query=request.query,
                config=config
            )

            # Emit sources event
            sources_data = [
                {
                    "id": s.source_id,
                    "title": s.title,
                    "content_preview": s.content[:200] if s.content else "",
                    "similarity_score": s.similarity,
                    "source_type": s.source_type
                }
                for s in result.sources_used
            ]
            yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"
            await asyncio.sleep(0)  # Allow event to flush

            # Stream the response tokens
            # For now, chunk the response into smaller pieces for streaming effect
            response_text = result.answer
            chunk_size = 20  # Characters per chunk for smooth streaming

            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield f"event: token\ndata: {json.dumps({'text': chunk, 'index': i})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for streaming effect

            # Emit citations event
            if result.citations:
                citations_data = [
                    {
                        "source_id": c.source_id,
                        "text": c.excerpt
                    }
                    for c in result.citations
                ]
                yield f"event: citations\ndata: {json.dumps(citations_data)}\n\n"

            # Emit done event with metadata
            done_data = {
                "total_sources": result.total_sources,
                "project_sources_count": result.project_sources_count,
                "query_time_ms": result.query_time_ms,
                "model": result.model,
                "expansion_strategy": result.expansion_strategy
            }
            yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

            logger.info(
                "stream_rag_query_completed",
                project_id=project_id,
                total_sources=result.total_sources
            )

        except Exception as e:
            logger.exception(
                "stream_rag_query_failed",
                project_id=project_id,
                error=str(e)
            )
            error_data = {"error": "An internal error occurred", "type": "InternalError"}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/{project_id}/rag/health", response_model=RAGHealthResponse)
async def project_rag_health(
    project_id: str,
    user_id: str = Depends(get_current_user)
) -> RAGHealthResponse:
    """
    Health check for project RAG service.

    Returns service status and configuration.
    """
    return RAGHealthResponse(
        status="healthy",
        service="project_rag",
        project_sources_enabled=True,
        global_kb_enabled=True,
        embedding_model="bge-m3",
        llm_model="claude-sonnet-4-20250514"
    )


# ============================================================================
# Source Preview Endpoint
# ============================================================================

class SourcePreviewRequest(BaseModel):
    """Request for source preview"""
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(5, ge=1, le=20)
    include_global_kb: bool = Field(True)


class SourcePreviewResponse(BaseModel):
    """Preview of sources that would be used for a query"""
    project_sources: List[SourceResponse]
    global_sources: List[SourceResponse]
    total_project: int
    total_global: int


@router.post("/{project_id}/rag/preview-sources", response_model=SourcePreviewResponse)
async def preview_sources(
    project_id: str,
    request: SourcePreviewRequest,
    user_id: str = Depends(get_current_user),
    service: ProjectRAGService = Depends(get_service)
) -> SourcePreviewResponse:
    """
    Preview which sources would be used for a query WITHOUT generating a response.

    This is useful for:
    - Debugging source retrieval
    - Showing users what sources are relevant
    - Testing source configuration
    """
    try:
        # Generate query embedding
        query_embedding = await service._generate_embedding(request.query)

        # Search sources
        project_sources = await service._search_project_sources(
            project_id=project_id,
            user_id=user_id,
            query_embedding=query_embedding,
            limit=request.limit,
            min_similarity=0.5
        )

        global_sources = []
        if request.include_global_kb:
            global_sources = await service._search_global_kb(
                query_embedding=query_embedding,
                limit=request.limit,
                min_similarity=0.5
            )

        # Convert to response format
        project_response = [
            SourceResponse(
                id=s.id,
                source_type=s.source_type,
                title=s.title,
                content=s.content[:300] + "..." if len(s.content) > 300 else s.content,
                chunk_index=s.chunk_index,
                similarity=s.similarity,
                rank=s.rank,
                source_id=s.source_id,
                document_id=s.document_id,
                file_type=s.file_type,
                metadata=s.metadata
            )
            for s in project_sources
        ]

        global_response = [
            SourceResponse(
                id=s.id,
                source_type=s.source_type,
                title=s.title,
                content=s.content[:300] + "..." if len(s.content) > 300 else s.content,
                chunk_index=s.chunk_index,
                similarity=s.similarity,
                rank=s.rank,
                document_id=s.document_id,
                department=s.department,
                metadata=s.metadata
            )
            for s in global_sources
        ]

        return SourcePreviewResponse(
            project_sources=project_response,
            global_sources=global_response,
            total_project=len(project_sources),
            total_global=len(global_sources)
        )

    except Exception as e:
        logger.error(
            "Source preview failed",
            project_id=project_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Source preview failed: {str(e)}"
        )
