"""
Empire v7.3 - Graph Agent API Routes (Task 107)

REST API endpoints for the Graph Agent capabilities:
- Customer 360: Unified customer views across multiple data sources
- Document Structure: Document hierarchy extraction and smart retrieval
- Graph-Enhanced RAG: Vector search augmented with graph context

These endpoints extend the existing /api/graph routes with new intelligent
graph traversal capabilities for the CKO Chat interface.
"""

import structlog
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Body, Depends, status

from app.models.graph_agent import (
    # Customer 360
    Customer360Request,
    Customer360Response,
    CustomerNode,
    # Document Structure
    DocumentStructureRequest,
    DocumentStructureResponse,
    SmartRetrievalRequest,
    SmartRetrievalResponse,
    SectionNode,
    DefinedTermNode,
    CrossReference,
    # Graph-Enhanced RAG
    GraphEnhancedRAGRequest,
    GraphEnhancedRAGResponse,
    GraphExpansionResult,
    TraversalDepth,
    # Common
    QueryType,
)

from app.services.customer360_service import (
    Customer360Service,
    get_customer360_service,
    CustomerNotFoundError,
)
from app.services.document_structure_service import (
    DocumentStructureService,
    get_document_structure_service,
)
from app.services.graph_enhanced_rag_service import (
    GraphEnhancedRAGService,
    get_graph_enhanced_rag_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/graph", tags=["Graph Agent"])


# =============================================================================
# DEPENDENCY INJECTION HELPERS
# =============================================================================

async def get_customer360() -> Customer360Service:
    """Get Customer360Service instance."""
    return get_customer360_service()


async def get_document_structure() -> DocumentStructureService:
    """Get DocumentStructureService instance."""
    return get_document_structure_service()


async def get_graph_rag() -> GraphEnhancedRAGService:
    """Get GraphEnhancedRAGService instance."""
    return get_graph_enhanced_rag_service()


# =============================================================================
# CUSTOMER 360 ENDPOINTS
# =============================================================================

@router.post(
    "/customer360/query",
    response_model=Customer360Response,
    summary="Query Customer 360 View",
    description="Process a natural language query about a customer and return "
                "unified customer data from multiple sources.",
)
async def query_customer(
    request: Customer360Request,
    service: Customer360Service = Depends(get_customer360),
) -> Customer360Response:
    """
    Query the Customer 360 view using natural language.

    This endpoint processes natural language queries like:
    - "Show me everything about Acme Corp"
    - "What are the recent support tickets for customer X?"
    - "Give me a 360 view of Company ABC"

    Returns unified customer data including documents, tickets, orders,
    and interactions.
    """
    start_time = time.time()
    logger.info("Customer 360 query", query=request.query[:100])

    try:
        response = await service.process_customer_query(request)

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Customer 360 query complete",
            query=request.query[:50],
            customer_found=response.customer is not None,
            latency_ms=latency_ms,
        )

        return response

    except Exception as e:
        logger.error("Customer 360 query failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Customer 360 query failed: {str(e)}",
        )


@router.get(
    "/customer360/{customer_id}",
    response_model=Customer360Response,
    summary="Get Customer 360 by ID",
    description="Retrieve unified customer view by customer ID.",
)
async def get_customer(
    customer_id: str,
    include_documents: bool = Query(True, description="Include related documents"),
    include_tickets: bool = Query(True, description="Include support tickets"),
    include_orders: bool = Query(True, description="Include orders"),
    include_interactions: bool = Query(True, description="Include interactions"),
    max_items: int = Query(50, ge=1, le=200, description="Max items per category"),
    service: Customer360Service = Depends(get_customer360),
) -> Customer360Response:
    """
    Get Customer 360 view by customer ID.

    Returns comprehensive customer data including:
    - Customer profile information
    - Related documents
    - Support tickets
    - Orders history
    - Interaction timeline
    """
    start_time = time.time()
    logger.info("Getting Customer 360", customer_id=customer_id)

    try:
        response = await service.get_customer_360(
            customer_id=customer_id,
            include_documents=include_documents,
            include_tickets=include_tickets,
            include_orders=include_orders,
            include_interactions=include_interactions,
            max_items=max_items,
        )

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Customer 360 retrieved",
            customer_id=customer_id,
            latency_ms=latency_ms,
        )

        return response

    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer not found: {customer_id}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get customer failed", customer_id=customer_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer: {str(e)}",
        )


@router.get(
    "/customer360/similar/{customer_id}",
    response_model=List[CustomerNode],
    summary="Find Similar Customers",
    description="Find customers with similar profiles or behaviors.",
)
async def find_similar_customers(
    customer_id: str,
    limit: int = Query(5, ge=1, le=20, description="Maximum similar customers to return"),
    service: Customer360Service = Depends(get_customer360),
) -> List[CustomerNode]:
    """
    Find customers similar to the specified customer.

    Uses graph-based similarity to find customers with:
    - Similar industries
    - Similar document types
    - Similar interaction patterns
    """
    logger.info("Finding similar customers", customer_id=customer_id, limit=limit)

    try:
        similar = await service.find_similar_customers(customer_id, limit=limit)

        logger.info(
            "Similar customers found",
            customer_id=customer_id,
            count=len(similar),
        )

        return similar

    except Exception as e:
        logger.error("Find similar customers failed", customer_id=customer_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar customers: {str(e)}",
        )


# =============================================================================
# DOCUMENT STRUCTURE ENDPOINTS
# =============================================================================

@router.post(
    "/document-structure/extract",
    response_model=DocumentStructureResponse,
    summary="Extract Document Structure",
    description="Extract hierarchical structure from a document including sections, "
                "definitions, cross-references, and citations.",
)
async def extract_document_structure(
    request: DocumentStructureRequest,
    service: DocumentStructureService = Depends(get_document_structure),
) -> DocumentStructureResponse:
    """
    Extract and store document structure.

    This endpoint analyzes a document and extracts:
    - Section hierarchy (chapters, sections, subsections)
    - Defined terms and definitions
    - Cross-references between sections
    - External citations

    The extracted structure is stored in Neo4j for later retrieval
    and smart querying.
    """
    start_time = time.time()
    logger.info("Extracting document structure", document_id=request.document_id)

    try:
        response = await service.extract_document_structure(
            document_id=request.document_id,
            extract_cross_refs=request.extract_cross_refs,
            extract_definitions=request.extract_definitions,
        )

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Document structure extracted",
            document_id=request.document_id,
            sections=len(response.sections),
            latency_ms=latency_ms,
        )

        return response

    except Exception as e:
        logger.error(
            "Document structure extraction failed",
            document_id=request.document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract document structure: {str(e)}",
        )


@router.post(
    "/document-structure/smart-retrieve",
    response_model=SmartRetrievalResponse,
    summary="Smart Document Retrieval",
    description="Context-aware retrieval that follows cross-references and "
                "expands results with related sections.",
)
async def smart_retrieve(
    request: SmartRetrievalRequest,
    service: DocumentStructureService = Depends(get_document_structure),
) -> SmartRetrievalResponse:
    """
    Perform smart retrieval within a document.

    This endpoint:
    1. Retrieves relevant sections based on the query
    2. Follows cross-references to get related content
    3. Expands context with parent/sibling sections
    4. Resolves defined terms automatically

    Returns sections with their full context for better understanding.
    """
    start_time = time.time()
    logger.info(
        "Smart document retrieval",
        document_id=request.document_id,
        query=request.query[:100],
    )

    try:
        response = await service.smart_retrieve(request)

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Smart retrieval complete",
            document_id=request.document_id,
            sections=len(response.sections),
            latency_ms=latency_ms,
        )

        return response

    except Exception as e:
        logger.error(
            "Smart retrieval failed",
            document_id=request.document_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Smart retrieval failed: {str(e)}",
        )


@router.get(
    "/document-structure/{doc_id}",
    response_model=DocumentStructureResponse,
    summary="Get Document Structure",
    description="Retrieve the extracted structure of a document.",
)
async def get_document_structure_by_id(
    doc_id: str,
    include_definitions: bool = Query(True, description="Include defined terms"),
    include_cross_refs: bool = Query(True, description="Include cross-references"),
    service: DocumentStructureService = Depends(get_document_structure),
) -> DocumentStructureResponse:
    """
    Get the previously extracted structure of a document.

    Returns the hierarchical structure including sections,
    definitions, and cross-references.
    """
    logger.info("Getting document structure", doc_id=doc_id)

    try:
        response = await service.get_document_structure(
            document_id=doc_id,
            include_definitions=include_definitions,
            include_cross_refs=include_cross_refs,
        )

        logger.info(
            "Document structure retrieved",
            doc_id=doc_id,
            sections=len(response.sections),
        )

        return response

    except Exception as e:
        logger.error("Get document structure failed", doc_id=doc_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document structure: {str(e)}",
        )


@router.get(
    "/document-structure/{doc_id}/cross-refs",
    response_model=List[CrossReference],
    summary="Get Cross-References",
    description="Get all cross-references for a document or specific section.",
)
async def get_cross_references(
    doc_id: str,
    section_id: Optional[str] = Query(None, description="Filter by section ID"),
    service: DocumentStructureService = Depends(get_document_structure),
) -> List[CrossReference]:
    """
    Get cross-references for a document.

    Returns all cross-references, optionally filtered by section.
    Useful for understanding document interconnections.
    """
    logger.info("Getting cross-references", doc_id=doc_id, section_id=section_id)

    try:
        refs = await service.get_cross_references(
            document_id=doc_id,
            section_id=section_id,
        )

        logger.info(
            "Cross-references retrieved",
            doc_id=doc_id,
            count=len(refs),
        )

        return refs

    except Exception as e:
        logger.error("Get cross-references failed", doc_id=doc_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cross-references: {str(e)}",
        )


# =============================================================================
# GRAPH-ENHANCED RAG ENDPOINTS
# =============================================================================

@router.post(
    "/enhanced-rag/query",
    response_model=GraphEnhancedRAGResponse,
    summary="Graph-Enhanced RAG Query",
    description="Perform RAG with graph context expansion for richer results.",
)
async def graph_enhanced_query(
    request: GraphEnhancedRAGRequest,
    service: GraphEnhancedRAGService = Depends(get_graph_rag),
) -> GraphEnhancedRAGResponse:
    """
    Perform a graph-enhanced RAG query.

    This endpoint:
    1. Executes vector search for initial results
    2. Extracts entities from the query and results
    3. Expands context using graph relationships
    4. Re-ranks results based on graph relevance

    Returns enriched results with related entities and documents.
    """
    start_time = time.time()
    logger.info(
        "Graph-enhanced RAG query",
        query=request.query[:100],
        depth=request.expansion_depth,
    )

    try:
        response = await service.query(request)

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Graph-enhanced RAG complete",
            query=request.query[:50],
            chunks=len(response.original_chunks),
            latency_ms=latency_ms,
        )

        return response

    except Exception as e:
        logger.error("Graph-enhanced RAG query failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph-enhanced RAG query failed: {str(e)}",
        )


@router.post(
    "/enhanced-rag/expand",
    response_model=GraphExpansionResult,
    summary="Expand Results with Graph Context",
    description="Take existing search results and expand them with graph context.",
)
async def expand_results(
    chunks: List[Dict[str, Any]] = Body(..., description="Search result chunks to expand"),
    expansion_depth: TraversalDepth = Query(
        TraversalDepth.MEDIUM,
        description="Depth of graph expansion",
    ),
    service: GraphEnhancedRAGService = Depends(get_graph_rag),
) -> GraphExpansionResult:
    """
    Expand existing search results with graph context.

    Takes chunks from any search and enriches them with:
    - Related entities from the graph
    - Connected documents
    - Relationship paths

    Useful for post-processing results from other search systems.
    """
    start_time = time.time()
    logger.info("Expanding results", chunk_count=len(chunks), depth=expansion_depth)

    try:
        # Convert dicts to ChunkNode objects if needed
        from app.models.graph_agent import ChunkNode

        chunk_objects = []
        for i, chunk in enumerate(chunks):
            if isinstance(chunk, dict):
                # Map incoming fields to ChunkNode fields
                # Support both legacy (text, source) and new (content, document_id) formats
                chunk_data = {
                    "id": chunk.get("id", f"chunk_{i}"),
                    "document_id": chunk.get("document_id") or chunk.get("source", "unknown"),
                    "content": chunk.get("content") or chunk.get("text", ""),
                    "position": chunk.get("position", i),
                }
                # Include optional fields if present
                if chunk.get("embedding_id"):
                    chunk_data["embedding_id"] = chunk["embedding_id"]
                if chunk.get("section_id"):
                    chunk_data["section_id"] = chunk["section_id"]
                chunk_objects.append(ChunkNode(**chunk_data))
            else:
                chunk_objects.append(chunk)

        result = await service.expand_results(
            chunks=chunk_objects,
            expansion_depth=expansion_depth,
        )

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "Results expanded",
            expanded_chunks=len(result.expanded_chunks),
            entities=len(result.extracted_entities),
            latency_ms=latency_ms,
        )

        return result

    except Exception as e:
        logger.error("Result expansion failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Result expansion failed: {str(e)}",
        )


@router.get(
    "/enhanced-rag/entities/{entity_id}/related",
    response_model=Dict[str, Any],
    summary="Get Related Entity Context",
    description="Get graph context for a specific entity.",
)
async def get_entity_related(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3, description="Traversal depth"),
    service: GraphEnhancedRAGService = Depends(get_graph_rag),
) -> Dict[str, Any]:
    """
    Get context for a specific entity.

    Returns:
    - Entity details
    - Neighboring entities
    - Related chunks/documents
    - Relationship information
    """
    logger.info("Getting entity context", entity_id=entity_id, depth=depth)

    try:
        context = await service.get_entity_context(entity_id, depth=depth)

        if context is None or context.get("entity") is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity not found: {entity_id}",
            )

        logger.info(
            "Entity context retrieved",
            entity_id=entity_id,
            neighbors=len(context.get("neighbors", [])),
        )

        return context

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get entity context failed", entity_id=entity_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve entity context: {str(e)}",
        )


@router.post(
    "/enhanced-rag/context",
    response_model=GraphExpansionResult,
    summary="Get Graph Context for Query",
    description="Get graph context for a text query without performing RAG.",
)
async def get_query_context(
    query: str = Body(..., description="Text query to analyze"),
    depth: TraversalDepth = Body(
        TraversalDepth.MEDIUM,
        description="Expansion depth",
    ),
    service: GraphEnhancedRAGService = Depends(get_graph_rag),
) -> GraphExpansionResult:
    """
    Get graph context for a query without full RAG.

    Useful for:
    - Understanding what entities are in the knowledge graph
    - Exploring relationships before querying
    - Building context for downstream processing
    """
    logger.info("Getting query context", query=query[:100], depth=depth)

    try:
        # Extract entities from query and expand
        from app.models.graph_agent import ChunkNode

        # Create a mock chunk with the query text
        query_chunk = ChunkNode(
            id="query_context",
            document_id="user_query",
            content=query,
            position=0,
        )

        result = await service.expand_results(
            chunks=[query_chunk],
            expansion_depth=depth,
        )

        logger.info(
            "Query context retrieved",
            entities=len(result.extracted_entities),
        )

        return result

    except Exception as e:
        logger.error("Get query context failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get query context: {str(e)}",
        )


# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@router.get(
    "/agent/health",
    summary="Graph Agent Health Check",
    description="Check health of all Graph Agent services.",
)
async def graph_agent_health() -> Dict[str, Any]:
    """
    Health check for Graph Agent services.

    Returns status of:
    - Customer 360 Service
    - Document Structure Service
    - Graph-Enhanced RAG Service
    - Neo4j connection
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
    }

    # Check Customer 360 Service
    try:
        service = get_customer360_service()
        health_status["services"]["customer360"] = {
            "status": "healthy" if service else "unavailable",
        }
    except Exception as e:
        health_status["services"]["customer360"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"

    # Check Document Structure Service
    try:
        service = get_document_structure_service()
        health_status["services"]["document_structure"] = {
            "status": "healthy" if service else "unavailable",
        }
    except Exception as e:
        health_status["services"]["document_structure"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"

    # Check Graph-Enhanced RAG Service
    try:
        service = get_graph_enhanced_rag_service()
        health_status["services"]["graph_enhanced_rag"] = {
            "status": "healthy" if service else "unavailable",
        }
    except Exception as e:
        health_status["services"]["graph_enhanced_rag"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"

    return health_status
