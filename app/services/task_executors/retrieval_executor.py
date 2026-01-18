"""
Empire v7.3 - Retrieval Executor (Task 95 + T017/T018/T019)

Executes retrieval tasks for the Research Projects feature:
- RAG retrieval using hybrid search (vector + BM25 + fuzzy)
- NLQ retrieval using natural language queries with Cypher generation
- Graph retrieval using Neo4j knowledge graph traversal
- API retrieval for external data sources

Features:
- Quality gates with automatic retry
- Query expansion for improved recall
- Artifact storage for retrieved chunks
- Configurable thresholds and limits
- NLQ-to-Cypher translation (T017)
- Neo4j graph context retrieval (T018)
- External API integration with httpx (T019)

Author: Claude Code
Date: 2025-01-10
Updated: 2025-01-17 (T017/T018/T019 integrations)
"""

import os
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from dataclasses import dataclass, field

import structlog
import httpx
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.services.task_harness import TaskExecutor
from app.models.research_project import TaskType, ArtifactType

logger = structlog.get_logger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class RetrievalConfig:
    """Configuration for retrieval operations"""
    # RAG parameters
    default_limit: int = 10
    max_limit: int = 50
    min_score: float = 0.5
    retry_min_score: float = 0.4  # Lower threshold for retry

    # Quality gate thresholds
    min_results: int = 3
    retry_min_results: int = 2
    max_retries: int = 2

    # Query expansion
    expand_on_retry: bool = True
    expansion_variations: int = 3

    # Artifact storage
    store_chunks: bool = True
    max_chunk_length: int = 2000


class QualityGateError(Exception):
    """Raised when quality gate fails after all retries"""
    pass


# ==============================================================================
# Retrieval Executor
# ==============================================================================

class RetrievalExecutor(TaskExecutor):
    """
    Executor for retrieval tasks (RAG, NLQ, Graph, API).

    Integrates with Empire's existing search infrastructure:
    - HybridSearchService for RAG retrieval
    - QueryExpansionService for query refinement
    - Neo4j for graph-based retrieval
    """

    def __init__(
        self,
        supabase: Client,
        config: Optional[RetrievalConfig] = None
    ):
        self.supabase = supabase
        self.config = config or RetrievalConfig()
        self._hybrid_search = None
        self._query_expansion = None

    @property
    def supported_types(self) -> List[str]:
        """Task types this executor supports"""
        return [
            TaskType.RETRIEVAL_RAG.value,
            TaskType.RETRIEVAL_NLQ.value,
            TaskType.RETRIEVAL_GRAPH.value,
            TaskType.RETRIEVAL_API.value,
        ]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a retrieval task based on its type.

        Args:
            task: Task data from plan_tasks table

        Returns:
            Dict with success, summary, data, and artifacts
        """
        task_type = task["task_type"]

        logger.info(
            "Executing retrieval task",
            task_id=task["id"],
            task_type=task_type,
            task_key=task["task_key"]
        )

        try:
            if task_type == TaskType.RETRIEVAL_RAG.value:
                return await self.execute_rag(task)
            elif task_type == TaskType.RETRIEVAL_NLQ.value:
                return await self.execute_nlq(task)
            elif task_type == TaskType.RETRIEVAL_GRAPH.value:
                return await self.execute_graph(task)
            elif task_type == TaskType.RETRIEVAL_API.value:
                return await self.execute_api(task)
            else:
                raise ValueError(f"Unsupported retrieval type: {task_type}")

        except Exception as e:
            logger.error(
                "Retrieval task failed",
                task_id=task["id"],
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "summary": f"Retrieval failed: {str(e)}",
                "data": {},
                "artifacts": []
            }

    # ==========================================================================
    # RAG Retrieval
    # ==========================================================================

    async def execute_rag(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute RAG retrieval using hybrid search.

        Uses Empire's HybridSearchService for:
        - Dense vector search (pgvector)
        - Sparse BM25 search
        - Fuzzy matching
        - Reciprocal Rank Fusion

        Args:
            task: Task data with query and config

        Returns:
            Dict with retrieved chunks and artifacts
        """
        query = task["query"]
        config = task.get("config", {})
        job_id = task["job_id"]
        task_id = task["id"]

        # Get search parameters from config
        limit = config.get("limit", self.config.default_limit)
        min_score = config.get("min_score", self.config.min_score)
        namespace = config.get("namespace")
        metadata_filter = config.get("metadata_filter")

        logger.info(
            "Executing RAG retrieval",
            query=query[:100],
            limit=limit,
            min_score=min_score
        )

        # Perform initial search
        results = await self._perform_hybrid_search(
            query=query,
            limit=limit,
            min_score=min_score,
            namespace=namespace,
            metadata_filter=metadata_filter
        )

        # Apply quality gate
        passed, filtered_results = self._apply_quality_gate(
            results,
            min_results=config.get("min_results", self.config.min_results)
        )

        # Retry with expanded query if needed
        retry_count = 0
        while not passed and retry_count < self.config.max_retries:
            retry_count += 1

            logger.info(
                "Quality gate failed, retrying with expansion",
                retry=retry_count,
                current_count=len(filtered_results)
            )

            # Expand query for better recall
            if self.config.expand_on_retry:
                expanded_query = await self._expand_query(query)
            else:
                expanded_query = query

            # Retry with relaxed parameters
            results = await self._perform_hybrid_search(
                query=expanded_query,
                limit=min(limit + 10, self.config.max_limit),
                min_score=self.config.retry_min_score,
                namespace=namespace,
                metadata_filter=metadata_filter
            )

            passed, filtered_results = self._apply_quality_gate(
                results,
                min_results=self.config.retry_min_results
            )

        if not passed:
            raise QualityGateError(
                f"Failed to retrieve sufficient results after {retry_count} retries. "
                f"Got {len(filtered_results)} results, needed {self.config.retry_min_results}"
            )

        # Prepare artifacts from results
        artifacts = self._prepare_artifacts(
            filtered_results,
            artifact_type=ArtifactType.RETRIEVED_CHUNK.value
        )

        # Calculate metrics
        avg_score = (
            sum(r.get("score", 0) for r in filtered_results) / len(filtered_results)
            if filtered_results else 0
        )

        return {
            "success": True,
            "summary": f"Retrieved {len(filtered_results)} chunks with avg score {avg_score:.2f}",
            "data": {
                "result_count": len(filtered_results),
                "average_score": round(avg_score, 3),
                "query": query,
                "retries": retry_count,
                "chunks": [
                    {
                        "chunk_id": r.get("chunk_id"),
                        "score": r.get("score"),
                        "content_preview": r.get("content", "")[:200]
                    }
                    for r in filtered_results[:5]  # Include preview of top 5
                ]
            },
            "artifacts": artifacts
        }

    async def _perform_hybrid_search(
        self,
        query: str,
        limit: int,
        min_score: float,
        namespace: Optional[str] = None,
        metadata_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using existing Empire infrastructure.

        Falls back to direct vector search if hybrid service unavailable.
        """
        try:
            # Try to use HybridSearchService
            search_service = await self._get_hybrid_search_service()
            if search_service:
                from app.services.hybrid_search_service import SearchMethod, HybridSearchConfig

                custom_config = HybridSearchConfig(
                    top_k=limit,
                    min_dense_score=min_score,
                )

                results = await search_service.search(
                    query=query,
                    method=SearchMethod.HYBRID,
                    namespace=namespace,
                    metadata_filter=metadata_filter,
                    custom_config=custom_config
                )

                return [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]

        except Exception as e:
            logger.warning(f"Hybrid search unavailable, using fallback: {e}")

        # Fallback: Direct vector search via Supabase RPC
        return await self._fallback_vector_search(
            query=query,
            limit=limit,
            min_score=min_score,
            namespace=namespace
        )

    async def _fallback_vector_search(
        self,
        query: str,
        limit: int,
        min_score: float,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fallback vector search using Supabase RPC.

        Used when HybridSearchService is not available.
        """
        try:
            # Get embedding for query
            embedding = await self._get_query_embedding(query)

            # Call Supabase RPC function for vector search
            result = self.supabase.rpc(
                "match_documents",
                {
                    "query_embedding": embedding,
                    "match_count": limit,
                    "filter_namespace": namespace
                }
            ).execute()

            if result.data:
                # Filter by minimum score
                filtered = [
                    {
                        "chunk_id": r.get("id"),
                        "content": r.get("content", ""),
                        "score": r.get("similarity", 0),
                        "metadata": r.get("metadata", {}),
                        "method": "vector"
                    }
                    for r in result.data
                    if r.get("similarity", 0) >= min_score
                ]
                return filtered

            return []

        except Exception as e:
            logger.error(f"Fallback vector search failed: {e}")
            return []

    async def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query using EmbeddingService"""
        try:
            from app.services.embedding_service import get_embedding_service

            service = get_embedding_service()
            result = await service.generate_embedding(query)
            return result.embedding

        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            raise

    # ==========================================================================
    # NLQ Retrieval
    # ==========================================================================

    async def execute_nlq(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Natural Language Query retrieval.

        Converts natural language to structured database queries
        and retrieves matching records.
        """
        query = task["query"]
        config = task.get("config", {})

        logger.info("Executing NLQ retrieval", query=query[:100])

        try:
            # Use existing NLQ infrastructure if available
            results = await self._perform_nlq_search(query, config)

            artifacts = self._prepare_artifacts(
                results,
                artifact_type=ArtifactType.QUERY_RESULT.value
            )

            return {
                "success": True,
                "summary": f"NLQ returned {len(results)} results",
                "data": {
                    "result_count": len(results),
                    "query": query,
                    "results_preview": results[:5] if results else []
                },
                "artifacts": artifacts
            }

        except Exception as e:
            logger.error(f"NLQ retrieval failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": f"NLQ retrieval failed: {str(e)}",
                "data": {},
                "artifacts": []
            }

    async def _perform_nlq_search(
        self,
        query: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Perform NLQ search using CypherGenerationService and Neo4j.

        T017: Integrated NLQ service implementation.

        Steps:
        1. Convert natural language query to Cypher using CypherGenerationService
        2. Execute the generated Cypher query against Neo4j
        3. Format and return results

        Args:
            query: Natural language query
            config: Configuration with optional parameters:
                - max_results: Maximum results to return (default: 20)
                - context: Additional context for query generation
                - min_confidence: Minimum confidence for query execution (default: 0.5)

        Returns:
            List of query results as dictionaries
        """
        try:
            # Get configuration parameters
            max_results = config.get("max_results", 20)
            context = config.get("context")
            min_confidence = config.get("min_confidence", 0.5)

            # Step 1: Generate Cypher query from natural language
            from app.services.cypher_generation_service import get_cypher_generation_service

            cypher_service = get_cypher_generation_service()
            generation_result = await cypher_service.generate_cypher(
                question=query,
                max_results=max_results,
                context=context
            )

            cypher_query = generation_result.get("cypher", "")
            confidence = generation_result.get("confidence", 0.0)
            explanation = generation_result.get("explanation", "")

            # Check if query was generated successfully
            if not cypher_query:
                logger.warning(
                    "NLQ: Could not generate Cypher query",
                    query=query[:100],
                    explanation=explanation
                )
                return []

            # Check confidence threshold
            if confidence < min_confidence:
                logger.warning(
                    "NLQ: Query confidence below threshold",
                    confidence=confidence,
                    threshold=min_confidence,
                    query=query[:100]
                )
                return []

            logger.info(
                "NLQ: Generated Cypher query",
                confidence=confidence,
                cypher=cypher_query[:200]
            )

            # Step 2: Execute the Cypher query against Neo4j
            from app.services.neo4j_http_client import get_neo4j_http_client

            neo4j_client = get_neo4j_http_client()
            results = await neo4j_client.execute_query(cypher_query)

            logger.info(
                "NLQ: Query executed successfully",
                result_count=len(results),
                query=query[:100]
            )

            # Step 3: Format results with metadata
            formatted_results = []
            for i, row in enumerate(results):
                formatted_results.append({
                    "content": str(row),
                    "score": confidence,
                    "method": "nlq",
                    "chunk_id": f"nlq_result_{i}",
                    "metadata": {
                        "cypher_query": cypher_query,
                        "explanation": explanation,
                        "confidence": confidence,
                        "row_data": row
                    }
                })

            return formatted_results

        except ImportError as e:
            logger.error(f"NLQ: Required service not available: {e}")
            return []
        except Exception as e:
            logger.error(f"NLQ search failed: {e}", exc_info=True)
            raise

    # ==========================================================================
    # Graph Retrieval
    # ==========================================================================

    async def execute_graph(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute graph-based retrieval using Neo4j.

        Traverses the knowledge graph to find related entities
        and documents.
        """
        query = task["query"]
        config = task.get("config", {})

        logger.info("Executing graph retrieval", query=query[:100])

        try:
            results = await self._perform_graph_search(query, config)

            artifacts = self._prepare_artifacts(
                results,
                artifact_type=ArtifactType.GRAPH_PATH.value
            )

            return {
                "success": True,
                "summary": f"Graph traversal found {len(results)} paths",
                "data": {
                    "result_count": len(results),
                    "query": query,
                    "paths_preview": results[:5] if results else []
                },
                "artifacts": artifacts
            }

        except Exception as e:
            logger.error(f"Graph retrieval failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": f"Graph retrieval failed: {str(e)}",
                "data": {},
                "artifacts": []
            }

    async def _perform_graph_search(
        self,
        query: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Perform Neo4j graph search using Neo4jGraphQueryService.

        T018: Integrated Neo4j service implementation.

        Steps:
        1. Extract entity IDs or document IDs from config/query
        2. Query graph context (entities, related documents, paths)
        3. Format and return results with relationship metadata

        Args:
            query: Natural language query or search term
            config: Configuration with optional parameters:
                - doc_id: Document ID to search from
                - entity_id: Entity ID to search from
                - max_depth: Maximum traversal depth (default: 2)
                - include_entities: Include linked entities (default: True)
                - include_related_docs: Include related documents (default: True)
                - entity_types: Filter by entity types (optional)

        Returns:
            List of graph results (entities, documents, paths)
        """
        try:
            # Get configuration parameters
            doc_id = config.get("doc_id")
            entity_id = config.get("entity_id")
            max_depth = config.get("max_depth", 2)
            include_entities = config.get("include_entities", True)
            include_related_docs = config.get("include_related_docs", True)
            entity_types = config.get("entity_types")

            # Import Neo4j services
            from app.services.neo4j_graph_queries import get_neo4j_graph_query_service

            graph_service = get_neo4j_graph_query_service()
            results = []

            # Strategy 1: If doc_id is provided, get document context
            if doc_id:
                logger.info(
                    "Graph: Retrieving document context",
                    doc_id=doc_id,
                    max_depth=max_depth
                )

                context = graph_service.get_document_context(
                    doc_id=doc_id,
                    include_entities=include_entities,
                    include_related_docs=include_related_docs,
                    max_depth=max_depth
                )

                # Add entities to results
                for entity in context.get("entities", []):
                    results.append({
                        "content": f"Entity: {entity.get('name')} ({entity.get('entity_type')})",
                        "score": 1.0 - (entity.get("hops", 0) * 0.1),  # Score decreases with distance
                        "method": "graph_entity",
                        "chunk_id": entity.get("entity_id"),
                        "metadata": {
                            "node_type": "entity",
                            "entity_type": entity.get("entity_type"),
                            "hops": entity.get("hops"),
                            "source_doc_id": doc_id
                        }
                    })

                # Add related documents to results
                for doc in context.get("related_docs", []):
                    results.append({
                        "content": f"Related Document: {doc.get('title', doc.get('doc_id'))}",
                        "score": 1.0 - (doc.get("distance", 0) * 0.15),
                        "method": "graph_document",
                        "chunk_id": doc.get("doc_id"),
                        "metadata": {
                            "node_type": "document",
                            "title": doc.get("title"),
                            "distance": doc.get("distance"),
                            "source_doc_id": doc_id
                        }
                    })

            # Strategy 2: If entity_id is provided, get entity context
            elif entity_id:
                logger.info(
                    "Graph: Retrieving entity context",
                    entity_id=entity_id,
                    max_depth=max_depth
                )

                context = graph_service.get_entity_context(
                    entity_id=entity_id,
                    max_depth=max_depth
                )

                # Add documents mentioning this entity
                for doc in context.get("documents", []):
                    results.append({
                        "content": f"Document: {doc.get('title', doc.get('doc_id'))} ({doc.get('doc_type', 'unknown')})",
                        "score": 0.9,
                        "method": "graph_document",
                        "chunk_id": doc.get("doc_id"),
                        "metadata": {
                            "node_type": "document",
                            "title": doc.get("title"),
                            "doc_type": doc.get("doc_type"),
                            "source_entity_id": entity_id
                        }
                    })

                # Add related entities
                for entity in context.get("related_entities", []):
                    results.append({
                        "content": f"Related Entity: {entity.get('name')}",
                        "score": 1.0 - (entity.get("distance", 0) * 0.1),
                        "method": "graph_entity",
                        "chunk_id": entity.get("entity_id"),
                        "metadata": {
                            "node_type": "entity",
                            "distance": entity.get("distance"),
                            "source_entity_id": entity_id
                        }
                    })

            # Strategy 3: Fall back to Cypher generation if no ID provided
            else:
                logger.info(
                    "Graph: Using NLQ-based graph search",
                    query=query[:100]
                )

                # Use CypherGenerationService to convert query to Cypher
                from app.services.cypher_generation_service import get_cypher_generation_service
                from app.services.neo4j_http_client import get_neo4j_http_client

                cypher_service = get_cypher_generation_service()
                generation_result = await cypher_service.generate_cypher(
                    question=query,
                    max_results=config.get("max_results", 20),
                    context="Focus on graph relationships and entity connections."
                )

                cypher_query = generation_result.get("cypher", "")
                confidence = generation_result.get("confidence", 0.0)

                if cypher_query and confidence >= 0.4:
                    neo4j_client = get_neo4j_http_client()
                    query_results = await neo4j_client.execute_query(cypher_query)

                    for i, row in enumerate(query_results):
                        results.append({
                            "content": str(row),
                            "score": confidence,
                            "method": "graph_cypher",
                            "chunk_id": f"graph_result_{i}",
                            "metadata": {
                                "cypher_query": cypher_query,
                                "confidence": confidence,
                                "row_data": row
                            }
                        })

            logger.info(
                "Graph: Search completed",
                result_count=len(results),
                query=query[:100]
            )

            return results

        except ImportError as e:
            logger.error(f"Graph: Required service not available: {e}")
            return []
        except Exception as e:
            logger.error(f"Graph search failed: {e}", exc_info=True)
            raise

    # ==========================================================================
    # API Retrieval
    # ==========================================================================

    async def execute_api(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute external API retrieval.

        Calls external APIs to gather supplementary data
        for the research task.
        """
        query = task["query"]
        config = task.get("config", {})
        api_endpoint = config.get("api_endpoint")

        logger.info(
            "Executing API retrieval",
            query=query[:100],
            endpoint=api_endpoint
        )

        try:
            results = await self._perform_api_call(query, config)

            artifacts = self._prepare_artifacts(
                results,
                artifact_type=ArtifactType.API_RESPONSE.value
            )

            return {
                "success": True,
                "summary": f"API returned {len(results)} results",
                "data": {
                    "result_count": len(results),
                    "query": query,
                    "api_endpoint": api_endpoint,
                    "results_preview": results[:5] if results else []
                },
                "artifacts": artifacts
            }

        except Exception as e:
            logger.error(f"API retrieval failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": f"API retrieval failed: {str(e)}",
                "data": {},
                "artifacts": []
            }

    async def _perform_api_call(
        self,
        query: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Perform external API call using httpx with retry logic.

        T019: Integrated external API implementation.

        Steps:
        1. Determine API endpoint and method from config
        2. Format request with authentication and parameters
        3. Execute with retry logic and timeout handling
        4. Parse and return results in standardized format

        Args:
            query: Search query or request data
            config: Configuration with parameters:
                - api_endpoint: Full URL to call (required)
                - method: HTTP method (default: GET)
                - headers: Additional headers (optional)
                - api_key_header: Header name for API key (optional)
                - api_key_env_var: Environment variable for API key (optional)
                - timeout: Request timeout in seconds (default: 30)
                - max_retries: Maximum retry attempts (default: 3)
                - params: Query parameters (optional)
                - body: Request body for POST/PUT (optional)
                - response_path: JSONPath to extract results (optional)

        Returns:
            List of API results as dictionaries
        """
        try:
            # Get configuration parameters
            api_endpoint = config.get("api_endpoint")
            if not api_endpoint:
                logger.warning("API: No endpoint specified")
                return []

            method = config.get("method", "GET").upper()
            headers = config.get("headers", {})
            timeout = config.get("timeout", 30)
            max_retries = config.get("max_retries", 3)
            params = config.get("params", {})
            body = config.get("body")
            response_path = config.get("response_path")

            # Handle API key authentication
            api_key_header = config.get("api_key_header")
            api_key_env_var = config.get("api_key_env_var")
            if api_key_header and api_key_env_var:
                api_key = os.getenv(api_key_env_var)
                if api_key:
                    headers[api_key_header] = api_key
                else:
                    logger.warning(f"API: API key not found in {api_key_env_var}")

            # Add query to params or body if not already present
            if method == "GET" and "query" not in params and "q" not in params:
                params["q"] = query
            elif method in ("POST", "PUT") and body is None:
                body = {"query": query}

            logger.info(
                "API: Making request",
                endpoint=api_endpoint,
                method=method,
                timeout=timeout
            )

            # Execute request with retry logic
            results = []
            last_error = None

            async with httpx.AsyncClient(timeout=timeout) as client:
                for attempt in range(max_retries):
                    try:
                        if method == "GET":
                            response = await client.get(
                                api_endpoint,
                                params=params,
                                headers=headers
                            )
                        elif method == "POST":
                            response = await client.post(
                                api_endpoint,
                                json=body,
                                params=params,
                                headers=headers
                            )
                        elif method == "PUT":
                            response = await client.put(
                                api_endpoint,
                                json=body,
                                params=params,
                                headers=headers
                            )
                        elif method == "DELETE":
                            response = await client.delete(
                                api_endpoint,
                                params=params,
                                headers=headers
                            )
                        else:
                            raise ValueError(f"Unsupported HTTP method: {method}")

                        # Check for success
                        response.raise_for_status()

                        # Parse response
                        data = response.json()

                        # Extract results using response_path if specified
                        if response_path:
                            data = self._extract_json_path(data, response_path)

                        # Normalize to list
                        if isinstance(data, dict):
                            data = [data]
                        elif not isinstance(data, list):
                            data = [{"value": data}]

                        # Format results
                        for i, item in enumerate(data):
                            results.append({
                                "content": str(item),
                                "score": 1.0,  # API results don't have scores
                                "method": "api",
                                "chunk_id": f"api_result_{i}",
                                "metadata": {
                                    "api_endpoint": api_endpoint,
                                    "method": method,
                                    "status_code": response.status_code,
                                    "item_data": item if isinstance(item, dict) else {"value": item}
                                }
                            })

                        logger.info(
                            "API: Request successful",
                            result_count=len(results),
                            status_code=response.status_code,
                            attempt=attempt + 1
                        )

                        return results

                    except httpx.HTTPStatusError as e:
                        last_error = e
                        logger.warning(
                            f"API: HTTP error on attempt {attempt + 1}",
                            status_code=e.response.status_code,
                            detail=str(e)
                        )
                        # Don't retry on 4xx errors (except 429)
                        if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                            break

                    except httpx.RequestError as e:
                        last_error = e
                        logger.warning(
                            f"API: Request error on attempt {attempt + 1}",
                            error=str(e)
                        )

                    # Wait before retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + (0.5 * attempt)
                        await asyncio.sleep(wait_time)

            # All retries failed
            if last_error:
                logger.error(
                    f"API: All {max_retries} attempts failed",
                    endpoint=api_endpoint,
                    last_error=str(last_error)
                )
                raise last_error

            return results

        except Exception as e:
            logger.error(f"API call failed: {e}", exc_info=True)
            raise

    def _extract_json_path(self, data: Any, path: str) -> Any:
        """
        Extract value from nested JSON using dot notation path.

        Args:
            data: JSON data (dict or list)
            path: Dot notation path (e.g., "data.results" or "items[0].value")

        Returns:
            Extracted value or original data if path not found
        """
        try:
            parts = path.split(".")
            result = data

            for part in parts:
                # Handle array index notation
                if "[" in part and "]" in part:
                    key = part[:part.index("[")]
                    index = int(part[part.index("[") + 1:part.index("]")])
                    if key:
                        result = result[key]
                    result = result[index]
                else:
                    result = result[part]

            return result

        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Could not extract path '{path}': {e}")
            return data

    # ==========================================================================
    # Quality Gates
    # ==========================================================================

    def _apply_quality_gate(
        self,
        results: List[Dict[str, Any]],
        min_results: int
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Apply quality gate to results.

        Args:
            results: Search results
            min_results: Minimum number of results required

        Returns:
            Tuple of (passed, filtered_results)
        """
        # Filter by minimum score (already done in search)
        filtered = results

        # Check minimum number of results
        if len(filtered) >= min_results:
            return True, filtered
        else:
            logger.warning(
                "Quality gate failed",
                got=len(filtered),
                needed=min_results
            )
            return False, filtered

    # ==========================================================================
    # Query Expansion
    # ==========================================================================

    async def _expand_query(self, query: str) -> str:
        """
        Expand query using QueryExpansionService.

        Returns the best expanded variation or original query.
        """
        try:
            from app.services.query_expansion_service import get_query_expansion_service

            service = get_query_expansion_service()
            result = await service.expand_query(
                query,
                num_variations=self.config.expansion_variations,
                strategy="balanced"
            )

            if result.variations:
                # Use first variation (most relevant)
                expanded = result.variations[0]
                logger.info(
                    "Query expanded",
                    original=query[:50],
                    expanded=expanded[:50]
                )
                return expanded

            return query

        except Exception as e:
            logger.warning(f"Query expansion failed, using original: {e}")
            return query

    # ==========================================================================
    # Artifact Preparation
    # ==========================================================================

    def _prepare_artifacts(
        self,
        results: List[Dict[str, Any]],
        artifact_type: str
    ) -> List[Dict[str, Any]]:
        """
        Prepare results as artifacts for storage.

        Args:
            results: Search/retrieval results
            artifact_type: Type of artifact

        Returns:
            List of artifact dictionaries ready for storage
        """
        if not self.config.store_chunks:
            return []

        artifacts = []
        for i, result in enumerate(results):
            content = result.get("content", "")

            # Truncate if too long
            if len(content) > self.config.max_chunk_length:
                content = content[:self.config.max_chunk_length] + "..."

            artifacts.append({
                "type": artifact_type,
                "title": f"Result {i + 1}: {result.get('chunk_id', 'unknown')}",
                "content": content,
                "metadata": {
                    "score": result.get("score"),
                    "method": result.get("method"),
                    "chunk_id": result.get("chunk_id"),
                    "file_id": result.get("file_id"),
                    "rank": i + 1
                },
                "source": result.get("file_id") or result.get("chunk_id"),
                "confidence": result.get("score")
            })

        return artifacts

    # ==========================================================================
    # Service Initialization
    # ==========================================================================

    async def _get_hybrid_search_service(self):
        """Get or initialize HybridSearchService"""
        if self._hybrid_search is None:
            try:
                from app.services.hybrid_search_service import HybridSearchService
                from app.services.vector_storage_service import get_vector_storage_service
                from app.services.embedding_service import get_embedding_service
                from app.core.connections import get_supabase_storage

                self._hybrid_search = HybridSearchService(
                    supabase_storage=get_supabase_storage(),
                    vector_storage_service=get_vector_storage_service(),
                    embedding_service=get_embedding_service()
                )
            except Exception as e:
                logger.warning(f"Could not initialize HybridSearchService: {e}")
                return None

        return self._hybrid_search


# ==============================================================================
# Service Factory
# ==============================================================================

_executor_instance: Optional[RetrievalExecutor] = None


def get_retrieval_executor() -> RetrievalExecutor:
    """Get or create retrieval executor singleton"""
    global _executor_instance
    if _executor_instance is None:
        supabase = get_supabase_client()
        _executor_instance = RetrievalExecutor(supabase)
    return _executor_instance
