"""
Query Router

Routes classified queries to appropriate search pipelines based on query type.
Integrates query classifier with vector, graph, metadata, and hybrid search services.

Features:
- Automatic routing based on query classification
- Fallback to hybrid search on errors
- Low confidence handling
- Batch query routing
- Comprehensive logging

Usage:
    from app.services.query_router import get_query_router

    router = get_query_router()
    result = await router.route_and_search("What is insurance?")

    print(f"Pipeline: {result.pipeline}")
    print(f"Results: {result.results}")
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from app.services.query_taxonomy import QueryType
from app.services.query_classifier import (
    QueryClassifier,
    get_query_classifier,
    ClassificationResult
)

logger = logging.getLogger(__name__)


@dataclass
class QueryRouterConfig:
    """Configuration for query router"""
    enable_routing: bool = True
    fallback_to_hybrid: bool = True
    confidence_threshold: float = 0.7
    log_routing_decisions: bool = True

    @classmethod
    def from_env(cls) -> "QueryRouterConfig":
        """Create config from environment variables"""
        import os
        return cls(
            enable_routing=os.getenv("ROUTER_ENABLE_ROUTING", "true").lower() == "true",
            fallback_to_hybrid=os.getenv("ROUTER_FALLBACK_HYBRID", "true").lower() == "true",
            confidence_threshold=float(os.getenv("ROUTER_CONFIDENCE_THRESHOLD", "0.7")),
            log_routing_decisions=os.getenv("ROUTER_LOG_DECISIONS", "true").lower() == "true"
        )


@dataclass
class RouteResult:
    """Result of query routing and search"""
    pipeline: str
    query_type: QueryType
    confidence: float
    results: List[Dict[str, Any]]
    fallback_used: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pipeline": self.pipeline,
            "query_type": self.query_type.value,
            "confidence": self.confidence,
            "results": self.results,
            "fallback_used": self.fallback_used,
            "error": self.error
        }


class QueryRouter:
    """
    Routes queries to appropriate search pipelines based on classification

    Maps query types to search pipelines:
    - SEMANTIC -> Vector search
    - RELATIONAL -> Graph search (Neo4j)
    - METADATA -> Metadata/filter search
    - HYBRID -> Hybrid search (RRF fusion)
    """

    def __init__(
        self,
        classifier: Optional[QueryClassifier] = None,
        vector_search: Optional[Any] = None,
        graph_search: Optional[Any] = None,
        metadata_search: Optional[Any] = None,
        hybrid_search: Optional[Any] = None,
        config: Optional[QueryRouterConfig] = None
    ):
        """
        Initialize query router

        Args:
            classifier: Query classifier instance
            vector_search: Vector search service
            graph_search: Graph search service (Neo4j)
            metadata_search: Metadata search service
            hybrid_search: Hybrid search service
            config: Router configuration
        """
        self.classifier = classifier or get_query_classifier()
        self.config = config or QueryRouterConfig.from_env()

        # Search services
        self.vector_search = vector_search
        self.graph_search = graph_search
        self.metadata_search = metadata_search
        self.hybrid_search = hybrid_search

        # Pipeline mapping
        self.pipeline_map = {
            QueryType.SEMANTIC: ("vector", self.vector_search),
            QueryType.RELATIONAL: ("graph", self.graph_search),
            QueryType.METADATA: ("metadata", self.metadata_search),
            QueryType.HYBRID: ("hybrid", self.hybrid_search)
        }

        logger.info(
            f"Initialized QueryRouter "
            f"(routing: {self.config.enable_routing}, "
            f"fallback: {self.config.fallback_to_hybrid})"
        )

    async def route_and_search(
        self,
        query: str,
        top_k: int = 10,
        **search_params
    ) -> RouteResult:
        """
        Route query to appropriate search pipeline and execute search

        Args:
            query: Query text
            top_k: Number of results to return
            **search_params: Additional parameters for search

        Returns:
            RouteResult with pipeline, classification, and results
        """
        # If routing disabled, use hybrid search
        if not self.config.enable_routing:
            logger.debug("Routing disabled, using hybrid search")
            return await self._search_hybrid(
                query=query,
                query_type=QueryType.HYBRID,
                confidence=1.0,
                top_k=top_k,
                **search_params
            )

        # Classify query
        try:
            classification = await self.classifier.classify_async(query)

            if self.config.log_routing_decisions:
                logger.info(
                    f"Routing query: '{query[:50]}...' -> "
                    f"{classification.query_type.value} "
                    f"(confidence: {classification.confidence:.2f})"
                )

            # Check confidence threshold
            if classification.confidence < self.config.confidence_threshold:
                logger.warning(
                    f"Low confidence {classification.confidence:.2f} "
                    f"< {self.config.confidence_threshold}, using hybrid"
                )
                return await self._search_hybrid(
                    query=query,
                    query_type=classification.query_type,
                    confidence=classification.confidence,
                    top_k=top_k,
                    **search_params
                )

            # Route to appropriate pipeline
            return await self._route_to_pipeline(
                query=query,
                classification=classification,
                top_k=top_k,
                **search_params
            )

        except Exception as e:
            logger.error(f"Classification failed: {e}")

            # Fallback to hybrid if enabled
            if self.config.fallback_to_hybrid:
                return await self._search_hybrid(
                    query=query,
                    query_type=QueryType.HYBRID,
                    confidence=0.0,
                    fallback_used=True,
                    error=str(e),
                    top_k=top_k,
                    **search_params
                )
            else:
                raise

    async def _route_to_pipeline(
        self,
        query: str,
        classification: ClassificationResult,
        top_k: int = 10,
        **search_params
    ) -> RouteResult:
        """
        Route to specific search pipeline based on classification

        Args:
            query: Query text
            classification: Classification result
            top_k: Number of results
            **search_params: Additional search parameters

        Returns:
            RouteResult
        """
        pipeline_name, search_service = self.pipeline_map[classification.query_type]

        if search_service is None:
            logger.warning(
                f"Search service '{pipeline_name}' not available, "
                f"falling back to hybrid"
            )
            return await self._search_hybrid(
                query=query,
                query_type=classification.query_type,
                confidence=classification.confidence,
                fallback_used=True,
                top_k=top_k,
                **search_params
            )

        # Execute search on appropriate pipeline
        try:
            results = await search_service.search(
                query=query,
                top_k=top_k,
                **search_params
            )

            return RouteResult(
                pipeline=pipeline_name,
                query_type=classification.query_type,
                confidence=classification.confidence,
                results=results,
                fallback_used=False
            )

        except Exception as e:
            logger.error(f"Search failed on {pipeline_name} pipeline: {e}")

            # Fallback to hybrid
            if self.config.fallback_to_hybrid:
                return await self._search_hybrid(
                    query=query,
                    query_type=classification.query_type,
                    confidence=classification.confidence,
                    fallback_used=True,
                    error=str(e),
                    top_k=top_k,
                    **search_params
                )
            else:
                raise

    async def _search_hybrid(
        self,
        query: str,
        query_type: QueryType,
        confidence: float,
        fallback_used: bool = False,
        error: Optional[str] = None,
        top_k: int = 10,
        **search_params
    ) -> RouteResult:
        """
        Execute hybrid search (fallback or intentional)

        Args:
            query: Query text
            query_type: Original query type
            confidence: Classification confidence
            fallback_used: Whether this is a fallback
            error: Error message if fallback
            top_k: Number of results
            **search_params: Additional search parameters

        Returns:
            RouteResult
        """
        if self.hybrid_search is None:
            raise RuntimeError("Hybrid search service not available")

        try:
            results = await self.hybrid_search.search(
                query=query,
                top_k=top_k,
                **search_params
            )

            return RouteResult(
                pipeline="hybrid",
                query_type=query_type,
                confidence=confidence,
                results=results,
                fallback_used=fallback_used,
                error=error
            )

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return RouteResult(
                pipeline="hybrid",
                query_type=query_type,
                confidence=confidence,
                results=[],
                fallback_used=True,
                error=f"Hybrid search failed: {str(e)}"
            )

    async def route_batch(
        self,
        queries: List[str],
        top_k: int = 10,
        **search_params
    ) -> List[RouteResult]:
        """
        Route and search multiple queries in batch

        Args:
            queries: List of query texts
            top_k: Number of results per query
            **search_params: Additional search parameters

        Returns:
            List of RouteResults
        """
        tasks = [
            self.route_and_search(query, top_k=top_k, **search_params)
            for query in queries
        ]
        return await asyncio.gather(*tasks)

    def _get_pipeline_name(self, query_type: QueryType) -> str:
        """
        Get pipeline name for query type

        Args:
            query_type: Query type

        Returns:
            Pipeline name
        """
        pipeline_name, _ = self.pipeline_map[query_type]
        return pipeline_name


# Singleton instance
_query_router: Optional[QueryRouter] = None


def get_query_router(
    config: Optional[QueryRouterConfig] = None,
    classifier: Optional[QueryClassifier] = None,
    vector_search: Optional[Any] = None,
    graph_search: Optional[Any] = None,
    metadata_search: Optional[Any] = None,
    hybrid_search: Optional[Any] = None
) -> QueryRouter:
    """
    Get or create singleton query router instance

    Args:
        config: Optional router configuration
        classifier: Optional query classifier
        vector_search: Optional vector search service
        graph_search: Optional graph search service
        metadata_search: Optional metadata search service
        hybrid_search: Optional hybrid search service

    Returns:
        QueryRouter instance
    """
    global _query_router

    if _query_router is None:
        _query_router = QueryRouter(
            classifier=classifier,
            vector_search=vector_search,
            graph_search=graph_search,
            metadata_search=metadata_search,
            hybrid_search=hybrid_search,
            config=config
        )

    return _query_router
