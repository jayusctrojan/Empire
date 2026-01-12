# app/services/graph_enhanced_rag_service.py
"""
Graph-Enhanced RAG Service for context expansion.

Task 106: Graph Agent - Graph-Enhanced RAG Service
Feature: 005-graph-agent

Augments vector search results with graph context by:
- Entity extraction from retrieved chunks
- Graph expansion strategies (neighbor expansion, parent context)
- Context enrichment for retrieved results
- Result re-ranking based on graph relevance

Reference: AI Automators Graph-Based Context Expansion Blueprint
"""

from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
import re
import time
import structlog

from app.services.neo4j_http_client import (
    Neo4jHTTPClient,
    get_neo4j_http_client,
    Neo4jQueryError,
    Neo4jConnectionError,
)
from app.models.graph_agent import (
    GraphEnhancedRAGRequest,
    GraphEnhancedRAGResponse,
    GraphExpansionResult,
    ChunkNode,
    EntityNode,
    EntityRelationship,
    EntityType,
    TraversalDepth,
)

logger = structlog.get_logger()


class GraphRAGError(Exception):
    """Raised when graph-enhanced RAG operations fail."""
    pass


class EntityExtractionError(Exception):
    """Raised when entity extraction fails."""
    pass


# Type alias for entity extractor callable
EntityExtractor = Callable[[str], List[Dict[str, Any]]]


class GraphEnhancedRAGService:
    """
    Augments vector search results with graph context.

    Provides:
    - Entity extraction from retrieved chunks
    - Graph expansion (neighbor expansion, parent context)
    - Context enrichment for retrieved results
    - Re-ranking based on graph relevance

    Reference: AI Automators Graph-Based Context Expansion pattern
    """

    CACHE_TTL = 300  # 5 minutes

    # Traversal depth configurations
    DEPTH_CONFIG = {
        TraversalDepth.SHALLOW: {"entity_depth": 1, "chunk_depth": 1, "max_entities": 5},
        TraversalDepth.MEDIUM: {"entity_depth": 2, "chunk_depth": 2, "max_entities": 10},
        TraversalDepth.DEEP: {"entity_depth": 3, "chunk_depth": 3, "max_entities": 20},
    }

    def __init__(
        self,
        neo4j_client: Optional[Neo4jHTTPClient] = None,
        vector_search_service: Optional[Any] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        cache_service: Optional[Any] = None,
    ):
        """
        Initialize Graph-Enhanced RAG Service.

        Args:
            neo4j_client: Neo4j HTTP client instance.
            vector_search_service: Optional vector search service for initial retrieval.
            entity_extractor: Optional callable for entity extraction.
            cache_service: Optional cache service for result caching.
        """
        self.neo4j = neo4j_client or get_neo4j_http_client()
        self.vector_search = vector_search_service
        self.entity_extractor = entity_extractor or self._default_entity_extractor
        self.cache = cache_service

        logger.info("GraphEnhancedRAGService initialized")

    async def query(
        self, request: GraphEnhancedRAGRequest
    ) -> GraphEnhancedRAGResponse:
        """
        Perform graph-enhanced RAG query.

        1. Retrieves initial chunks (from vector search or provided)
        2. Extracts entities from chunks
        3. Expands context using graph traversal
        4. Re-ranks results based on graph relevance

        Args:
            request: GraphEnhancedRAGRequest with query and options

        Returns:
            GraphEnhancedRAGResponse with enhanced results
        """
        start_time = time.time()
        query = request.query

        logger.info(
            "Graph-enhanced RAG query",
            query=query[:50],
            depth=request.expansion_depth.value,
        )

        try:
            # Step 1: Get initial chunks (from provided IDs or vector search)
            if request.chunk_ids:
                original_chunks = await self._get_chunks_by_ids(request.chunk_ids)
            elif self.vector_search:
                original_chunks = await self._perform_vector_search(query)
            else:
                # Use graph-based text search as fallback
                original_chunks = await self._search_chunks_by_text(query)

            # Step 2: Expand results with graph context
            graph_context = await self.expand_results(
                chunks=original_chunks,
                expansion_depth=request.expansion_depth,
                max_expanded=request.max_expanded_chunks,
                include_entities=request.include_entity_context,
                include_relationships=request.include_relationship_paths,
            )

            # Step 3: Re-rank if requested
            if request.rerank_by_graph_relevance:
                all_chunks = original_chunks + graph_context.expanded_chunks
                all_chunks = await self._rerank_results(
                    query=query,
                    original_results=original_chunks,
                    expanded_results=graph_context.expanded_chunks,
                )
                graph_context.expanded_chunks = all_chunks[len(original_chunks):]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            response = GraphEnhancedRAGResponse(
                query=query,
                answer=None,  # Answer generation handled by caller
                original_chunks=original_chunks,
                graph_context=graph_context,
                sources=self._build_sources(original_chunks, graph_context),
                graph_enhanced=len(graph_context.expanded_chunks) > 0,
                latency_ms=latency_ms,
            )

            logger.info(
                "Graph-enhanced RAG complete",
                original_count=len(original_chunks),
                expanded_count=len(graph_context.expanded_chunks),
                entity_count=len(graph_context.extracted_entities),
                latency_ms=round(latency_ms, 2),
            )

            return response

        except Exception as e:
            logger.error("Graph-enhanced RAG failed", error=str(e))
            raise GraphRAGError(f"Graph-enhanced RAG failed: {e}")

    async def expand_results(
        self,
        chunks: List[ChunkNode],
        expansion_depth: TraversalDepth = TraversalDepth.MEDIUM,
        max_expanded: int = 10,
        include_entities: bool = True,
        include_relationships: bool = True,
    ) -> GraphExpansionResult:
        """
        Expand vector search results with graph context.

        Args:
            chunks: Original retrieved chunks
            expansion_depth: How deep to traverse the graph
            max_expanded: Maximum number of expanded chunks
            include_entities: Whether to include entity context
            include_relationships: Whether to include relationship paths

        Returns:
            GraphExpansionResult with expanded context
        """
        config = self.DEPTH_CONFIG[expansion_depth]

        # Extract entities from chunks
        extracted_entities = []
        if include_entities:
            for chunk in chunks:
                entities = await self._extract_entities(chunk.content)
                extracted_entities.extend(entities)

        # Deduplicate entities
        seen_ids = set()
        unique_entities = []
        for entity in extracted_entities:
            if entity.id not in seen_ids:
                seen_ids.add(entity.id)
                unique_entities.append(entity)
        extracted_entities = unique_entities[:config["max_entities"]]

        # Get related entities from graph
        related_entities = []
        entity_relationships = []
        relationship_paths = []

        if extracted_entities:
            entity_ids = [e.id for e in extracted_entities]

            # Expand by entity neighbors
            related_entities = await self._expand_by_neighbors(
                entity_ids,
                depth=config["entity_depth"],
            )

            # Get relationships
            if include_relationships:
                entity_relationships = await self._get_entity_relationships(entity_ids)
                relationship_paths = self._build_relationship_paths(entity_relationships)

        # Expand chunks by graph proximity
        expanded_chunks = await self._expand_chunks_by_graph(
            chunk_ids=[c.id for c in chunks],
            entity_ids=[e.id for e in extracted_entities],
            depth=config["chunk_depth"],
            max_chunks=max_expanded,
        )

        return GraphExpansionResult(
            original_chunks=chunks,
            expanded_chunks=expanded_chunks,
            extracted_entities=extracted_entities,
            related_entities=related_entities,
            entity_relationships=entity_relationships,
            relationship_paths=relationship_paths,
            expansion_method="entity_neighbor_expansion",
        )

    async def get_entity_context(
        self, entity_id: str, depth: int = 1
    ) -> Dict[str, Any]:
        """
        Get context for a specific entity.

        Args:
            entity_id: Entity ID to get context for
            depth: Traversal depth

        Returns:
            Dictionary with entity context
        """
        try:
            # Get entity details
            entity = await self._get_entity_by_id(entity_id)
            if not entity:
                return {"entity": None, "neighbors": [], "chunks": []}

            # Get neighboring entities
            neighbors = await self._expand_by_neighbors([entity_id], depth=depth)

            # Get chunks mentioning this entity
            chunks = await self._get_chunks_mentioning_entity(entity_id)

            return {
                "entity": entity.model_dump() if entity else None,
                "neighbors": [n.model_dump() for n in neighbors],
                "chunks": [c.model_dump() for c in chunks],
                "relationship_count": len(neighbors),
            }

        except Exception as e:
            logger.error("Failed to get entity context", entity_id=entity_id, error=str(e))
            raise GraphRAGError(f"Failed to get entity context: {e}")

    # =========================================================================
    # ENTITY EXTRACTION
    # =========================================================================

    async def _extract_entities(self, text: str) -> List[EntityNode]:
        """
        Extract entities from text.

        Uses the configured entity extractor or default pattern-based extraction.
        """
        if not text:
            return []

        try:
            # Use injected extractor if available
            if self.entity_extractor != self._default_entity_extractor:
                raw_entities = self.entity_extractor(text)
                return [
                    EntityNode(
                        id=e.get("id", f"entity_{hash(e.get('name', ''))}"),
                        name=e["name"],
                        type=EntityType(e.get("type", "OTHER")),
                        normalized_name=e.get("name", "").lower(),
                        confidence=e.get("confidence", 0.8),
                    )
                    for e in raw_entities
                    if e.get("name")
                ]

            # Default pattern-based extraction
            return self._default_entity_extractor(text)

        except Exception as e:
            logger.warning("Entity extraction failed", error=str(e))
            return []

    def _default_entity_extractor(self, text: str) -> List[EntityNode]:
        """
        Default pattern-based entity extraction.

        Extracts:
        - Capitalized multi-word phrases (potential organizations/people)
        - Quoted terms
        - Common entity patterns
        """
        entities = []

        # Pattern: Capitalized multi-word phrases (e.g., "Acme Corporation")
        org_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
        for match in org_pattern.finditer(text):
            name = match.group(1)
            entities.append(EntityNode(
                id=f"entity_{hash(name) % 1000000}",
                name=name,
                type=EntityType.ORGANIZATION,
                normalized_name=name.lower(),
                confidence=0.7,
            ))

        # Pattern: Quoted terms (potential defined terms or products)
        quoted_pattern = re.compile(r'"([^"]+)"')
        for match in quoted_pattern.finditer(text):
            term = match.group(1)
            if len(term) > 2:
                entities.append(EntityNode(
                    id=f"term_{hash(term) % 1000000}",
                    name=term,
                    type=EntityType.CONCEPT,
                    normalized_name=term.lower(),
                    confidence=0.6,
                ))

        # Deduplicate by normalized name
        seen = set()
        unique = []
        for e in entities:
            if e.normalized_name not in seen:
                seen.add(e.normalized_name)
                unique.append(e)

        return unique[:20]  # Limit to prevent over-extraction

    # =========================================================================
    # GRAPH EXPANSION
    # =========================================================================

    async def _expand_by_neighbors(
        self, entity_ids: List[str], depth: int = 1
    ) -> List[EntityNode]:
        """
        Expand by traversing entity neighbors in the graph.
        """
        if not entity_ids:
            return []

        try:
            query = """
            UNWIND $entity_ids as eid
            MATCH (e:Entity {id: eid})-[r]-(neighbor:Entity)
            WHERE neighbor.id NOT IN $entity_ids
            RETURN DISTINCT
                neighbor.id as id,
                neighbor.name as name,
                neighbor.type as type,
                neighbor.normalized_name as normalized_name,
                neighbor.description as description,
                neighbor.confidence as confidence
            LIMIT $limit
            """
            results = await self.neo4j.execute_query(
                query,
                {
                    "entity_ids": entity_ids,
                    "limit": depth * 10,
                }
            )

            return [
                EntityNode(
                    id=r["id"],
                    name=r["name"],
                    type=EntityType(r.get("type", "OTHER")),
                    normalized_name=r.get("normalized_name"),
                    description=r.get("description"),
                    confidence=r.get("confidence", 0.5),
                )
                for r in results
            ]

        except Exception as e:
            logger.warning("Failed to expand by neighbors", error=str(e))
            return []

    async def _expand_chunks_by_graph(
        self,
        chunk_ids: List[str],
        entity_ids: List[str],
        depth: int = 1,
        max_chunks: int = 10,
    ) -> List[ChunkNode]:
        """
        Expand chunks using graph relationships.

        Finds related chunks through:
        - Neighboring chunks (NEXT_CHUNK, PREV_CHUNK)
        - Chunks mentioning related entities
        - Chunks in same section
        """
        if not chunk_ids and not entity_ids:
            return []

        try:
            expanded = []

            # Get neighboring chunks
            if chunk_ids:
                neighbor_query = """
                UNWIND $chunk_ids as cid
                MATCH (c:Chunk {id: cid})-[:NEXT_CHUNK|PREV_CHUNK|IN_SECTION]-(neighbor:Chunk)
                WHERE neighbor.id NOT IN $chunk_ids
                RETURN DISTINCT
                    neighbor.id as id,
                    neighbor.document_id as document_id,
                    neighbor.content as content,
                    neighbor.position as position,
                    neighbor.embedding_id as embedding_id,
                    neighbor.section_id as section_id
                LIMIT $limit
                """
                neighbor_results = await self.neo4j.execute_query(
                    neighbor_query,
                    {"chunk_ids": chunk_ids, "limit": max_chunks}
                )
                for r in neighbor_results:
                    expanded.append(ChunkNode(
                        id=r["id"],
                        document_id=r["document_id"],
                        content=r.get("content", ""),
                        position=r.get("position", 0),
                        embedding_id=r.get("embedding_id"),
                        section_id=r.get("section_id"),
                    ))

            # Get chunks mentioning related entities
            if entity_ids and len(expanded) < max_chunks:
                entity_query = """
                UNWIND $entity_ids as eid
                MATCH (e:Entity {id: eid})<-[:MENTIONS]-(c:Chunk)
                WHERE c.id NOT IN $existing_ids
                RETURN DISTINCT
                    c.id as id,
                    c.document_id as document_id,
                    c.content as content,
                    c.position as position,
                    c.embedding_id as embedding_id,
                    c.section_id as section_id
                LIMIT $limit
                """
                existing_ids = chunk_ids + [c.id for c in expanded]
                entity_results = await self.neo4j.execute_query(
                    entity_query,
                    {
                        "entity_ids": entity_ids,
                        "existing_ids": existing_ids,
                        "limit": max_chunks - len(expanded),
                    }
                )
                for r in entity_results:
                    expanded.append(ChunkNode(
                        id=r["id"],
                        document_id=r["document_id"],
                        content=r.get("content", ""),
                        position=r.get("position", 0),
                        embedding_id=r.get("embedding_id"),
                        section_id=r.get("section_id"),
                    ))

            return expanded[:max_chunks]

        except Exception as e:
            logger.warning("Failed to expand chunks", error=str(e))
            return []

    async def _get_entity_relationships(
        self, entity_ids: List[str]
    ) -> List[EntityRelationship]:
        """
        Get relationships between entities.
        """
        if not entity_ids:
            return []

        try:
            query = """
            UNWIND $entity_ids as eid
            MATCH (e:Entity {id: eid})-[r]->(target:Entity)
            RETURN
                e.id as from_id,
                target.id as to_id,
                type(r) as rel_type,
                r.confidence as confidence,
                r.source_chunk_id as source_chunk_id
            LIMIT 50
            """
            results = await self.neo4j.execute_query(query, {"entity_ids": entity_ids})

            return [
                EntityRelationship(
                    from_entity_id=r["from_id"],
                    to_entity_id=r["to_id"],
                    relationship_type=r["rel_type"],
                    confidence=r.get("confidence", 0.5),
                    source_chunk_id=r.get("source_chunk_id"),
                )
                for r in results
            ]

        except Exception as e:
            logger.warning("Failed to get entity relationships", error=str(e))
            return []

    def _build_relationship_paths(
        self, relationships: List[EntityRelationship]
    ) -> List[List[str]]:
        """
        Build human-readable relationship paths.
        """
        paths = []
        for rel in relationships:
            path = [
                rel.from_entity_id,
                f"--[{rel.relationship_type}]-->",
                rel.to_entity_id,
            ]
            paths.append(path)
        return paths

    # =========================================================================
    # CHUNK RETRIEVAL
    # =========================================================================

    async def _get_chunks_by_ids(self, chunk_ids: List[str]) -> List[ChunkNode]:
        """
        Get chunks by their IDs from Neo4j.
        """
        if not chunk_ids:
            return []

        try:
            query = """
            UNWIND $chunk_ids as cid
            MATCH (c:Chunk {id: cid})
            RETURN
                c.id as id,
                c.document_id as document_id,
                c.content as content,
                c.position as position,
                c.embedding_id as embedding_id,
                c.section_id as section_id
            """
            results = await self.neo4j.execute_query(query, {"chunk_ids": chunk_ids})

            return [
                ChunkNode(
                    id=r["id"],
                    document_id=r["document_id"],
                    content=r.get("content", ""),
                    position=r.get("position", 0),
                    embedding_id=r.get("embedding_id"),
                    section_id=r.get("section_id"),
                )
                for r in results
            ]

        except Exception as e:
            logger.warning("Failed to get chunks by IDs", error=str(e))
            return []

    async def _search_chunks_by_text(
        self, query: str, limit: int = 10
    ) -> List[ChunkNode]:
        """
        Search chunks by text content (fallback when vector search unavailable).
        """
        try:
            cypher = """
            MATCH (c:Chunk)
            WHERE c.content CONTAINS $query
            RETURN
                c.id as id,
                c.document_id as document_id,
                c.content as content,
                c.position as position,
                c.embedding_id as embedding_id,
                c.section_id as section_id
            LIMIT $limit
            """
            results = await self.neo4j.execute_query(
                cypher,
                {"query": query, "limit": limit}
            )

            return [
                ChunkNode(
                    id=r["id"],
                    document_id=r["document_id"],
                    content=r.get("content", ""),
                    position=r.get("position", 0),
                    embedding_id=r.get("embedding_id"),
                    section_id=r.get("section_id"),
                )
                for r in results
            ]

        except Exception as e:
            logger.warning("Failed to search chunks", error=str(e))
            return []

    async def _perform_vector_search(
        self, query: str, limit: int = 10
    ) -> List[ChunkNode]:
        """
        Perform vector search using injected service.
        """
        if not self.vector_search:
            return []

        try:
            results = await self.vector_search.search(query, limit=limit)
            return [
                ChunkNode(
                    id=r.get("id", ""),
                    document_id=r.get("document_id", ""),
                    content=r.get("content", ""),
                    position=r.get("position", 0),
                    embedding_id=r.get("embedding_id"),
                    section_id=r.get("section_id"),
                )
                for r in results
            ]

        except Exception as e:
            logger.warning("Vector search failed", error=str(e))
            return []

    async def _get_chunks_mentioning_entity(
        self, entity_id: str, limit: int = 10
    ) -> List[ChunkNode]:
        """
        Get chunks that mention a specific entity.
        """
        try:
            query = """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {id: $entity_id})
            RETURN
                c.id as id,
                c.document_id as document_id,
                c.content as content,
                c.position as position,
                c.embedding_id as embedding_id,
                c.section_id as section_id
            LIMIT $limit
            """
            results = await self.neo4j.execute_query(
                query,
                {"entity_id": entity_id, "limit": limit}
            )

            return [
                ChunkNode(
                    id=r["id"],
                    document_id=r["document_id"],
                    content=r.get("content", ""),
                    position=r.get("position", 0),
                    embedding_id=r.get("embedding_id"),
                    section_id=r.get("section_id"),
                )
                for r in results
            ]

        except Exception as e:
            logger.warning("Failed to get chunks for entity", error=str(e))
            return []

    async def _get_entity_by_id(self, entity_id: str) -> Optional[EntityNode]:
        """
        Get entity by ID from Neo4j.
        """
        try:
            query = """
            MATCH (e:Entity {id: $entity_id})
            RETURN
                e.id as id,
                e.name as name,
                e.type as type,
                e.normalized_name as normalized_name,
                e.description as description,
                e.confidence as confidence
            """
            results = await self.neo4j.execute_query(query, {"entity_id": entity_id})

            if results:
                r = results[0]
                return EntityNode(
                    id=r["id"],
                    name=r["name"],
                    type=EntityType(r.get("type", "OTHER")),
                    normalized_name=r.get("normalized_name"),
                    description=r.get("description"),
                    confidence=r.get("confidence", 1.0),
                )

            return None

        except Exception as e:
            logger.warning("Failed to get entity", entity_id=entity_id, error=str(e))
            return None

    # =========================================================================
    # RE-RANKING
    # =========================================================================

    async def _rerank_results(
        self,
        query: str,
        original_results: List[ChunkNode],
        expanded_results: List[ChunkNode],
    ) -> List[ChunkNode]:
        """
        Re-rank results based on graph relevance.

        Scoring factors:
        - Entity overlap with query
        - Graph connectivity (number of relationships)
        - Document coherence (same document as original results)
        """
        all_results = original_results + expanded_results

        # Extract entities from query for comparison
        query_entities = await self._extract_entities(query)
        query_entity_names = {e.normalized_name for e in query_entities}

        # Score each result
        scored_results = []
        for chunk in all_results:
            score = await self._calculate_relevance_score(
                chunk,
                query_entity_names,
                is_original=chunk in original_results,
            )
            scored_results.append((score, chunk))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)

        return [chunk for _, chunk in scored_results]

    async def _calculate_relevance_score(
        self,
        chunk: ChunkNode,
        query_entities: set,
        is_original: bool,
    ) -> float:
        """
        Calculate relevance score for a chunk.
        """
        score = 0.0

        # Base score for original vs expanded
        if is_original:
            score += 0.5

        # Entity overlap score
        chunk_entities = await self._extract_entities(chunk.content)
        chunk_entity_names = {e.normalized_name for e in chunk_entities}
        overlap = len(query_entities & chunk_entity_names)
        if overlap > 0:
            score += 0.3 * min(overlap / max(len(query_entities), 1), 1.0)

        # Check graph connectivity
        try:
            connectivity_query = """
            MATCH (c:Chunk {id: $chunk_id})-[r]-()
            RETURN count(r) as rel_count
            """
            results = await self.neo4j.execute_query(
                connectivity_query,
                {"chunk_id": chunk.id}
            )
            if results:
                rel_count = results[0].get("rel_count", 0)
                score += 0.2 * min(rel_count / 10, 1.0)
        except Exception:
            pass

        return score

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _build_sources(
        self,
        original_chunks: List[ChunkNode],
        graph_context: GraphExpansionResult,
    ) -> List[Dict[str, Any]]:
        """
        Build source citations from chunks.
        """
        sources = []
        seen_docs = set()

        for chunk in original_chunks + graph_context.expanded_chunks:
            if chunk.document_id and chunk.document_id not in seen_docs:
                seen_docs.add(chunk.document_id)
                sources.append({
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "section_id": chunk.section_id,
                    "is_expanded": chunk in graph_context.expanded_chunks,
                })

        return sources


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_graph_rag_service: Optional[GraphEnhancedRAGService] = None


def get_graph_enhanced_rag_service() -> GraphEnhancedRAGService:
    """Get or create singleton GraphEnhancedRAGService instance."""
    global _graph_rag_service
    if _graph_rag_service is None:
        _graph_rag_service = GraphEnhancedRAGService()
    return _graph_rag_service


async def close_graph_enhanced_rag_service() -> None:
    """Close the singleton GraphEnhancedRAGService instance."""
    global _graph_rag_service
    if _graph_rag_service is not None:
        _graph_rag_service = None
