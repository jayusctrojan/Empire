"""
Empire v7.3 - Knowledge Graph API Routes (Task 31)

REST API endpoints for Neo4j knowledge graph operations.
Includes entity queries, graph traversal, and Cypher generation via Claude Sonnet.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.services.neo4j_entity_service import (
    Neo4jEntityService,
    get_neo4j_entity_service,
    DocumentNode,
    EntityNode,
    RelationshipType
)
from app.services.neo4j_graph_queries import (
    Neo4jGraphQueryService,
    get_neo4j_graph_query_service,
    GraphTraversalConfig
)
from app.services.cypher_generation_service import (
    CypherGenerationService,
    get_cypher_generation_service
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["Knowledge Graph"])


# =============================================================================
# Pydantic Models
# =============================================================================

class EntityQueryRequest(BaseModel):
    """Request for entity-centric search"""
    entity_id: str = Field(..., description="Entity ID to query")
    max_depth: int = Field(2, ge=1, le=5, description="Maximum traversal depth")
    include_documents: bool = Field(True, description="Include related documents")
    include_entities: bool = Field(True, description="Include related entities")


class EntityQueryResponse(BaseModel):
    """Response from entity query"""
    entity_id: str
    documents: List[Dict[str, Any]]
    related_entities: List[Dict[str, Any]]
    query_time_ms: float


class DocumentContextRequest(BaseModel):
    """Request for document context"""
    doc_id: str = Field(..., description="Document ID")
    max_depth: int = Field(2, ge=1, le=5, description="Maximum traversal depth")
    include_entities: bool = Field(True, description="Include linked entities")
    include_related_docs: bool = Field(True, description="Include related documents")


class DocumentContextResponse(BaseModel):
    """Response with document context"""
    doc_id: str
    entities: List[Dict[str, Any]]
    related_docs: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    query_time_ms: float


class TraversalRequest(BaseModel):
    """Request for graph traversal"""
    start_id: str = Field(..., description="Starting node ID")
    max_depth: int = Field(3, ge=1, le=5, description="Maximum traversal depth")
    relationship_types: Optional[List[str]] = Field(
        None, description="Filter by relationship types"
    )
    direction: str = Field("both", description="Traversal direction: both, outgoing, incoming")


class TraversalResponse(BaseModel):
    """Response from graph traversal"""
    start_id: str
    nodes: List[Dict[str, Any]]
    total_nodes: int
    max_depth_reached: int
    query_time_ms: float


class NaturalLanguageQueryRequest(BaseModel):
    """Request for natural language graph query"""
    question: str = Field(..., description="Natural language question about the knowledge graph")
    execute: bool = Field(True, description="Execute the generated Cypher query")
    max_results: int = Field(20, ge=1, le=100, description="Maximum results to return")


class NaturalLanguageQueryResponse(BaseModel):
    """Response from natural language query"""
    question: str
    generated_cypher: str
    explanation: str
    results: Optional[List[Dict[str, Any]]] = None
    executed: bool
    query_time_ms: float


class PathFindingRequest(BaseModel):
    """Request to find path between nodes"""
    from_id: str = Field(..., description="Source node ID")
    to_id: str = Field(..., description="Target node ID")
    max_length: int = Field(5, ge=1, le=10, description="Maximum path length")


class PathFindingResponse(BaseModel):
    """Response with path information"""
    from_id: str
    to_id: str
    path: Optional[List[Dict[str, Any]]] = None
    path_length: Optional[int] = None
    found: bool
    query_time_ms: float


class CommonEntitiesRequest(BaseModel):
    """Request to find common entities across documents"""
    doc_ids: List[str] = Field(..., description="List of document IDs")
    min_doc_count: int = Field(2, ge=2, description="Minimum documents entity must appear in")


class CommonEntitiesResponse(BaseModel):
    """Response with common entities"""
    doc_ids: List[str]
    common_entities: List[Dict[str, Any]]
    total_common: int
    query_time_ms: float


class GraphEnhancedContextRequest(BaseModel):
    """Request for graph-enhanced search context"""
    query: str = Field(..., description="Search query")
    doc_ids: List[str] = Field(..., description="Document IDs from initial search")
    expansion_depth: int = Field(2, ge=1, le=3, description="Graph expansion depth")


class GraphEnhancedContextResponse(BaseModel):
    """Response with graph-enhanced context"""
    original_docs: List[str]
    expanded_docs: List[Dict[str, Any]]
    related_entities: List[Dict[str, Any]]
    graph_context: str
    query_time_ms: float


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/entity/query", response_model=EntityQueryResponse)
async def query_entity(request: EntityQueryRequest):
    """
    Query entity and retrieve related documents and entities.

    Performs entity-centric search with configurable depth.
    Returns documents mentioning the entity and related entities via graph traversal.

    **Example:**
    ```json
    {
        "entity_id": "ent-california-insurance",
        "max_depth": 2,
        "include_documents": true,
        "include_entities": true
    }
    ```
    """
    start_time = time.time()

    try:
        graph_service = get_neo4j_graph_query_service()
        context = graph_service.get_entity_context(
            entity_id=request.entity_id,
            max_depth=request.max_depth
        )

        query_time_ms = (time.time() - start_time) * 1000

        return EntityQueryResponse(
            entity_id=request.entity_id,
            documents=context.get("documents", []) if request.include_documents else [],
            related_entities=context.get("related_entities", []) if request.include_entities else [],
            query_time_ms=query_time_ms
        )

    except Exception as e:
        logger.error(f"Entity query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Entity query failed: {str(e)}")


@router.post("/document/context", response_model=DocumentContextResponse)
async def get_document_context(request: DocumentContextRequest):
    """
    Get full context around a document.

    Retrieves entities linked to the document, related documents via shared entities,
    and relationship statistics.

    **Example:**
    ```json
    {
        "doc_id": "doc-12345",
        "max_depth": 2,
        "include_entities": true,
        "include_related_docs": true
    }
    ```
    """
    start_time = time.time()

    try:
        graph_service = get_neo4j_graph_query_service()
        context = graph_service.get_document_context(
            doc_id=request.doc_id,
            include_entities=request.include_entities,
            include_related_docs=request.include_related_docs,
            max_depth=request.max_depth
        )

        query_time_ms = (time.time() - start_time) * 1000

        return DocumentContextResponse(
            doc_id=request.doc_id,
            entities=context.get("entities", []),
            related_docs=context.get("related_docs", []),
            relationships=context.get("relationships", []),
            query_time_ms=query_time_ms
        )

    except Exception as e:
        logger.error(f"Document context query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Document context query failed: {str(e)}")


@router.post("/traverse", response_model=TraversalResponse)
async def traverse_graph(request: TraversalRequest):
    """
    Traverse the knowledge graph from a starting node.

    Supports configurable depth (1-5 hops), relationship type filtering,
    and direction control.

    **Example:**
    ```json
    {
        "start_id": "doc-12345",
        "max_depth": 3,
        "relationship_types": ["MENTIONS", "REFERENCES"],
        "direction": "both"
    }
    ```
    """
    start_time = time.time()

    try:
        graph_service = get_neo4j_graph_query_service()

        config = GraphTraversalConfig(
            max_depth=request.max_depth,
            relationship_types=request.relationship_types or ["MENTIONS", "REFERENCES", "RELATED_TO"],
            direction=request.direction
        )

        nodes = graph_service.traverse_relationships(
            start_id=request.start_id,
            config=config
        )

        # Calculate max depth reached
        max_depth_reached = max([n.get("depth", 0) for n in nodes]) if nodes else 0

        query_time_ms = (time.time() - start_time) * 1000

        return TraversalResponse(
            start_id=request.start_id,
            nodes=nodes,
            total_nodes=len(nodes),
            max_depth_reached=max_depth_reached,
            query_time_ms=query_time_ms
        )

    except Exception as e:
        logger.error(f"Graph traversal failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph traversal failed: {str(e)}")


@router.post("/query/natural", response_model=NaturalLanguageQueryResponse)
async def natural_language_query(request: NaturalLanguageQueryRequest):
    """
    Query the knowledge graph using natural language.

    Uses Claude Sonnet to translate natural language questions into Cypher queries,
    then optionally executes them against Neo4j.

    **Example:**
    ```json
    {
        "question": "Find all documents mentioning California insurance regulations",
        "execute": true,
        "max_results": 20
    }
    ```

    **Returns:**
    Generated Cypher query, explanation, and optionally the query results.
    """
    start_time = time.time()

    try:
        cypher_service = get_cypher_generation_service()

        # Generate Cypher from natural language
        generation_result = await cypher_service.generate_cypher(
            question=request.question,
            max_results=request.max_results
        )

        results = None
        if request.execute and generation_result.get("cypher"):
            # Execute the generated query
            graph_service = get_neo4j_graph_query_service()
            results = graph_service.connection.execute_query(
                generation_result["cypher"],
                {}
            )

        query_time_ms = (time.time() - start_time) * 1000

        return NaturalLanguageQueryResponse(
            question=request.question,
            generated_cypher=generation_result.get("cypher", ""),
            explanation=generation_result.get("explanation", ""),
            results=results,
            executed=request.execute and results is not None,
            query_time_ms=query_time_ms
        )

    except Exception as e:
        logger.error(f"Natural language query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Natural language query failed: {str(e)}")


@router.post("/path/find", response_model=PathFindingResponse)
async def find_path(request: PathFindingRequest):
    """
    Find the shortest path between two nodes.

    Uses Neo4j's shortestPath algorithm to find connections between
    documents or entities in the knowledge graph.

    **Example:**
    ```json
    {
        "from_id": "doc-12345",
        "to_id": "doc-67890",
        "max_length": 5
    }
    ```
    """
    start_time = time.time()

    try:
        graph_service = get_neo4j_graph_query_service()

        path_result = graph_service.find_shortest_path(
            from_id=request.from_id,
            to_id=request.to_id
        )

        query_time_ms = (time.time() - start_time) * 1000

        if path_result:
            return PathFindingResponse(
                from_id=request.from_id,
                to_id=request.to_id,
                path=path_result.get("path", []),
                path_length=path_result.get("length"),
                found=True,
                query_time_ms=query_time_ms
            )
        else:
            return PathFindingResponse(
                from_id=request.from_id,
                to_id=request.to_id,
                path=None,
                path_length=None,
                found=False,
                query_time_ms=query_time_ms
            )

    except Exception as e:
        logger.error(f"Path finding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Path finding failed: {str(e)}")


@router.post("/entities/common", response_model=CommonEntitiesResponse)
async def find_common_entities(request: CommonEntitiesRequest):
    """
    Find entities common to multiple documents.

    Useful for identifying shared themes or topics across a set of documents.

    **Example:**
    ```json
    {
        "doc_ids": ["doc-123", "doc-456", "doc-789"],
        "min_doc_count": 2
    }
    ```
    """
    start_time = time.time()

    try:
        graph_service = get_neo4j_graph_query_service()

        common = graph_service.find_common_entities(
            doc_ids=request.doc_ids,
            min_doc_count=request.min_doc_count
        )

        query_time_ms = (time.time() - start_time) * 1000

        return CommonEntitiesResponse(
            doc_ids=request.doc_ids,
            common_entities=common,
            total_common=len(common),
            query_time_ms=query_time_ms
        )

    except Exception as e:
        logger.error(f"Common entities query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Common entities query failed: {str(e)}")


@router.post("/context/enhanced", response_model=GraphEnhancedContextResponse)
async def get_graph_enhanced_context(request: GraphEnhancedContextRequest):
    """
    Get graph-enhanced context for search results.

    Takes initial search results and expands them using the knowledge graph
    to find additional relevant documents and entities.

    **Example:**
    ```json
    {
        "query": "California insurance requirements",
        "doc_ids": ["doc-123", "doc-456"],
        "expansion_depth": 2
    }
    ```

    **Returns:**
    Expanded document set, related entities, and assembled graph context.
    """
    start_time = time.time()

    try:
        graph_service = get_neo4j_graph_query_service()

        # Expand context from initial documents
        expanded_nodes = graph_service.expand_context_incrementally(
            start_ids=request.doc_ids,
            max_depth=request.expansion_depth
        )

        # Get related documents (filter for Document nodes)
        expanded_docs = [
            node for node in expanded_nodes
            if node.get("node_id", "").startswith("doc-")
        ]

        # Find common entities across documents
        related_entities = graph_service.find_common_entities(
            doc_ids=request.doc_ids,
            min_doc_count=1
        )

        # Assemble graph context as text
        entity_names = [e.get("name", "") for e in related_entities[:10]]
        graph_context = f"Related entities: {', '.join(entity_names)}" if entity_names else ""

        query_time_ms = (time.time() - start_time) * 1000

        return GraphEnhancedContextResponse(
            original_docs=request.doc_ids,
            expanded_docs=expanded_docs,
            related_entities=related_entities[:20],
            graph_context=graph_context,
            query_time_ms=query_time_ms
        )

    except Exception as e:
        logger.error(f"Graph-enhanced context failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph-enhanced context failed: {str(e)}")


@router.get("/health")
async def graph_health():
    """
    Check knowledge graph service health.

    Verifies Neo4j connectivity and returns service status.
    """
    try:
        from app.services.neo4j_connection import get_neo4j_connection

        connection = get_neo4j_connection()
        connected = connection.verify_connectivity()

        # Get basic stats
        stats = {}
        if connected:
            try:
                result = connection.execute_query(
                    "MATCH (n) RETURN labels(n)[0] as label, count(n) as count",
                    {}
                )
                stats = {r["label"]: r["count"] for r in result if r.get("label")}
            except Exception:
                pass

        return {
            "status": "healthy" if connected else "unhealthy",
            "neo4j_connected": connected,
            "node_counts": stats
        }

    except Exception as e:
        logger.error(f"Graph health check failed: {e}")
        return {
            "status": "unhealthy",
            "neo4j_connected": False,
            "error": str(e)
        }


@router.get("/stats")
async def graph_stats():
    """
    Get knowledge graph statistics.

    Returns node counts, relationship counts, and other graph metrics.
    """
    try:
        from app.services.neo4j_connection import get_neo4j_connection

        connection = get_neo4j_connection()

        # Get node counts by label
        node_stats = connection.execute_query(
            "MATCH (n) RETURN labels(n)[0] as label, count(n) as count",
            {}
        )

        # Get relationship counts by type
        rel_stats = connection.execute_query(
            "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count",
            {}
        )

        total_nodes = sum(s.get("count", 0) for s in node_stats)
        total_rels = sum(s.get("count", 0) for s in rel_stats)

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "nodes_by_label": {s["label"]: s["count"] for s in node_stats if s.get("label")},
            "relationships_by_type": {s["type"]: s["count"] for s in rel_stats if s.get("type")}
        }

    except Exception as e:
        logger.error(f"Graph stats query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get graph stats: {str(e)}")
