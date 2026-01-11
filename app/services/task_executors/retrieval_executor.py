"""
Empire v7.3 - Retrieval Executor (Task 95)

Executes retrieval tasks for the Research Projects feature:
- RAG retrieval using hybrid search (vector + BM25 + fuzzy)
- NLQ retrieval using natural language queries
- Graph retrieval using Neo4j knowledge graph
- API retrieval for external data sources

Features:
- Quality gates with automatic retry
- Query expansion for improved recall
- Artifact storage for retrieved chunks
- Configurable thresholds and limits

Author: Claude Code
Date: 2025-01-10
"""

import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

import structlog
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
        Perform NLQ search - placeholder for full implementation.

        In production, this would:
        1. Parse natural language query
        2. Convert to SQL/structured query
        3. Execute against database
        4. Return formatted results
        """
        # Placeholder - return empty results
        # TODO: Integrate with NLQ service when available
        return []

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
        Perform Neo4j graph search - placeholder for full implementation.

        In production, this would:
        1. Extract entities from query
        2. Build Cypher query
        3. Execute against Neo4j
        4. Return paths and related entities
        """
        # Placeholder - return empty results
        # TODO: Integrate with Neo4j service
        return []

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
        Perform external API call - placeholder for full implementation.

        In production, this would:
        1. Determine appropriate API endpoint
        2. Format request
        3. Execute with retry logic
        4. Parse and return results
        """
        # Placeholder - return empty results
        # TODO: Implement API integration
        return []

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
