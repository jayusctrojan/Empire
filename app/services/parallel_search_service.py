"""
Parallel Search Service with Query Expansion

Orchestrates query expansion and parallel hybrid searches to improve recall.
Executes multiple searches concurrently and aggregates/deduplicates results.

Features:
- Query expansion integration
- Parallel hybrid search execution
- Result aggregation and deduplication
- Configurable concurrency limits
- Performance metrics tracking

Usage:
    from app.services.parallel_search_service import get_parallel_search_service

    service = get_parallel_search_service()
    results = await service.search(
        "California insurance policy",
        expand_queries=True,
        num_variations=5
    )
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import time

from app.services.query_expansion_service import (
    QueryExpansionService,
    QueryExpansionConfig,
    ExpansionStrategy,
    get_query_expansion_service
)
from app.services.hybrid_search_service import (
    HybridSearchService,
    HybridSearchConfig,
    SearchResult,
    SearchMethod,
    get_hybrid_search_service
)

logger = logging.getLogger(__name__)


@dataclass
class ParallelSearchConfig:
    """Configuration for parallel search service"""
    # Query expansion
    enable_expansion: bool = True
    num_query_variations: int = 5
    expansion_strategy: str = "balanced"

    # Parallel execution
    max_concurrent_searches: int = 10
    search_timeout_seconds: float = 30.0

    # Result processing
    enable_deduplication: bool = True
    max_results: int = 100
    min_similarity_score: float = 0.7

    # Aggregation strategy
    aggregation_method: str = "score_weighted"  # "score_weighted", "frequency", "max_score"

    # Performance
    cache_expanded_queries: bool = True


@dataclass
class ParallelSearchResult:
    """Result of parallel search operation"""
    original_query: str
    expanded_queries: List[str]
    aggregated_results: List[SearchResult]
    total_results_found: int
    unique_results_count: int
    queries_executed: int
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ParallelSearchService:
    """Service for executing parallel searches with query expansion"""

    def __init__(
        self,
        query_expansion_service: Optional[QueryExpansionService] = None,
        hybrid_search_service: Optional[HybridSearchService] = None,
        config: Optional[ParallelSearchConfig] = None,
        monitoring_service: Optional[Any] = None
    ):
        self.config = config or ParallelSearchConfig()
        self.monitoring = monitoring_service

        # Initialize services
        self.query_expander = query_expansion_service or get_query_expansion_service()
        self.hybrid_searcher = hybrid_search_service or get_hybrid_search_service()

        logger.info("ParallelSearchService initialized")

    async def search(
        self,
        query: str,
        expand_queries: Optional[bool] = None,
        num_variations: Optional[int] = None,
        expansion_strategy: Optional[ExpansionStrategy] = None,
        search_method: SearchMethod = SearchMethod.HYBRID,
        namespace: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        custom_search_config: Optional[HybridSearchConfig] = None
    ) -> ParallelSearchResult:
        """
        Execute parallel searches with optional query expansion

        Args:
            query: Original search query
            expand_queries: Enable query expansion (default: config.enable_expansion)
            num_variations: Number of query variations (default: config.num_query_variations)
            expansion_strategy: Strategy for expansion (default: config.expansion_strategy)
            search_method: Search method to use (DENSE, SPARSE, FUZZY, HYBRID)
            namespace: Namespace filter
            metadata_filter: Metadata filter
            max_results: Maximum results to return (default: config.max_results)
            custom_search_config: Custom hybrid search configuration

        Returns:
            ParallelSearchResult with aggregated results
        """
        start_time = time.time()

        expand_queries = expand_queries if expand_queries is not None else self.config.enable_expansion
        num_variations = num_variations or self.config.num_query_variations
        max_results = max_results or self.config.max_results

        # Convert string strategy to enum if needed
        if isinstance(expansion_strategy, str):
            expansion_strategy = ExpansionStrategy(expansion_strategy)
        elif expansion_strategy is None:
            expansion_strategy = ExpansionStrategy(self.config.expansion_strategy)

        # Step 1: Expand query if enabled
        queries_to_search = [query]
        if expand_queries:
            try:
                expansion_result = await self.query_expander.expand_query(
                    query,
                    num_variations=num_variations,
                    strategy=expansion_strategy,
                    include_original=True
                )
                queries_to_search = expansion_result.expanded_queries
                logger.info(
                    f"Expanded '{query[:50]}...' into {len(queries_to_search)} queries"
                )
            except Exception as e:
                logger.error(f"Query expansion failed: {e}. Using original query only.")
                queries_to_search = [query]

        # Step 2: Execute parallel searches
        all_results = await self._execute_parallel_searches(
            queries_to_search,
            search_method,
            namespace,
            metadata_filter,
            custom_search_config
        )

        # Step 3: Aggregate and deduplicate results
        aggregated = self._aggregate_results(
            all_results,
            queries_to_search
        )

        # Step 4: Sort and limit results
        aggregated = self._sort_and_limit_results(aggregated, max_results)

        duration_ms = (time.time() - start_time) * 1000

        # Create result
        result = ParallelSearchResult(
            original_query=query,
            expanded_queries=queries_to_search,
            aggregated_results=aggregated,
            total_results_found=sum(len(r) for r in all_results),
            unique_results_count=len(aggregated),
            queries_executed=len(queries_to_search),
            duration_ms=duration_ms,
            metadata={
                "expansion_enabled": expand_queries,
                "search_method": search_method.value,
                "aggregation_method": self.config.aggregation_method
            }
        )

        # Log metrics
        if self.monitoring:
            self.monitoring.track_event("parallel_search", {
                "queries_executed": result.queries_executed,
                "total_results": result.total_results_found,
                "unique_results": result.unique_results_count,
                "duration_ms": duration_ms
            })

        logger.info(
            f"Parallel search complete: {result.queries_executed} queries, "
            f"{result.total_results_found} total results, "
            f"{result.unique_results_count} unique ({duration_ms:.2f}ms)"
        )

        return result

    async def _execute_parallel_searches(
        self,
        queries: List[str],
        search_method: SearchMethod,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]],
        custom_config: Optional[HybridSearchConfig]
    ) -> List[List[SearchResult]]:
        """Execute searches for all queries in parallel"""

        semaphore = asyncio.Semaphore(self.config.max_concurrent_searches)

        async def search_with_semaphore(query: str) -> List[SearchResult]:
            async with semaphore:
                try:
                    results = await asyncio.wait_for(
                        self.hybrid_searcher.search(
                            query,
                            method=search_method,
                            namespace=namespace,
                            metadata_filter=metadata_filter,
                            custom_config=custom_config
                        ),
                        timeout=self.config.search_timeout_seconds
                    )
                    logger.debug(f"Search for '{query[:50]}...' returned {len(results)} results")
                    return results
                except asyncio.TimeoutError:
                    logger.warning(f"Search timeout for query: '{query[:50]}...'")
                    return []
                except Exception as e:
                    logger.error(f"Search failed for '{query[:50]}...': {e}")
                    return []

        # Execute all searches in parallel
        tasks = [search_with_semaphore(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.error(f"Search exception for '{query[:50]}...': {result}")
                final_results.append([])
            else:
                final_results.append(result)

        return final_results

    def _aggregate_results(
        self,
        all_results: List[List[SearchResult]],
        queries: List[str]
    ) -> List[SearchResult]:
        """
        Aggregate and deduplicate results from multiple searches

        Aggregation methods:
        - score_weighted: Weight scores by query position and combine
        - frequency: Rank by how many queries returned the result
        - max_score: Use the maximum score across all queries
        """

        if not self.config.enable_deduplication:
            # Simple concatenation without deduplication
            combined = []
            for results in all_results:
                combined.extend(results)
            return combined

        # Track results by chunk_id
        result_map: Dict[str, List[SearchResult]] = defaultdict(list)

        for query_idx, results in enumerate(all_results):
            for result in results:
                result_map[result.chunk_id].append((query_idx, result))

        # Aggregate based on method
        aggregated = []

        for chunk_id, result_instances in result_map.items():
            if not result_instances:
                continue

            # Use the first instance as base
            _, base_result = result_instances[0]

            if self.config.aggregation_method == "score_weighted":
                # Weight by query position (earlier queries get higher weight)
                weighted_score = 0.0
                total_weight = 0.0

                for query_idx, result in result_instances:
                    # Query position weight (decays exponentially)
                    position_weight = 1.0 / (1.0 + query_idx * 0.5)
                    weighted_score += result.score * position_weight
                    total_weight += position_weight

                final_score = weighted_score / total_weight if total_weight > 0 else base_result.score

            elif self.config.aggregation_method == "frequency":
                # Score based on frequency of appearance
                final_score = len(result_instances) / len(queries)

            elif self.config.aggregation_method == "max_score":
                # Use maximum score
                final_score = max(r.score for _, r in result_instances)

            else:
                # Default: average score
                final_score = sum(r.score for _, r in result_instances) / len(result_instances)

            # Create aggregated result
            aggregated_result = SearchResult(
                chunk_id=chunk_id,
                content=base_result.content,
                score=final_score,
                rank=0,  # Will be set during sorting
                method="parallel_aggregated",
                metadata=base_result.metadata,
                dense_score=base_result.dense_score,
                sparse_score=base_result.sparse_score,
                fuzzy_score=base_result.fuzzy_score,
                rrf_score=base_result.rrf_score
            )

            # Add aggregation metadata
            aggregated_result.metadata = {
                **base_result.metadata,
                "appearances": len(result_instances),
                "query_indices": [idx for idx, _ in result_instances],
                "original_scores": [r.score for _, r in result_instances],
                "aggregation_method": self.config.aggregation_method
            }

            aggregated.append(aggregated_result)

        logger.debug(
            f"Aggregated {sum(len(r) for r in all_results)} results "
            f"into {len(aggregated)} unique results"
        )

        return aggregated

    def _sort_and_limit_results(
        self,
        results: List[SearchResult],
        max_results: int
    ) -> List[SearchResult]:
        """Sort results by score and limit to max_results"""

        # Filter by minimum score if configured
        if self.config.min_similarity_score > 0:
            results = [
                r for r in results
                if r.score >= self.config.min_similarity_score
            ]

        # Sort by score (descending)
        results.sort(key=lambda x: x.score, reverse=True)

        # Update ranks
        for idx, result in enumerate(results):
            result.rank = idx + 1

        # Limit results
        return results[:max_results]

    async def batch_search(
        self,
        queries: List[str],
        expand_queries: bool = True,
        num_variations: int = 3,
        search_method: SearchMethod = SearchMethod.HYBRID,
        max_concurrent: int = 5
    ) -> List[ParallelSearchResult]:
        """
        Execute parallel searches for multiple original queries

        Args:
            queries: List of original queries
            expand_queries: Enable expansion for each query
            num_variations: Variations per query
            search_method: Search method to use
            max_concurrent: Maximum concurrent batch searches

        Returns:
            List of ParallelSearchResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def search_with_semaphore(query: str) -> ParallelSearchResult:
            async with semaphore:
                return await self.search(
                    query,
                    expand_queries=expand_queries,
                    num_variations=num_variations,
                    search_method=search_method
                )

        tasks = [search_with_semaphore(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.error(f"Batch search failed for '{query[:50]}...': {result}")
                final_results.append(ParallelSearchResult(
                    original_query=query,
                    expanded_queries=[query],
                    aggregated_results=[],
                    total_results_found=0,
                    unique_results_count=0,
                    queries_executed=0,
                    duration_ms=0.0,
                    metadata={"error": str(result)}
                ))
            else:
                final_results.append(result)

        return final_results

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "config": {
                "enable_expansion": self.config.enable_expansion,
                "num_query_variations": self.config.num_query_variations,
                "max_concurrent_searches": self.config.max_concurrent_searches,
                "aggregation_method": self.config.aggregation_method
            },
            "query_expander_cache": self.query_expander.get_cache_stats()
        }


# Singleton instance
_parallel_search_service: Optional[ParallelSearchService] = None


def get_parallel_search_service(
    query_expansion_service: Optional[QueryExpansionService] = None,
    hybrid_search_service: Optional[HybridSearchService] = None,
    config: Optional[ParallelSearchConfig] = None,
    monitoring_service: Optional[Any] = None
) -> ParallelSearchService:
    """Get or create the singleton ParallelSearchService instance"""
    global _parallel_search_service

    if _parallel_search_service is None:
        _parallel_search_service = ParallelSearchService(
            query_expansion_service,
            hybrid_search_service,
            config,
            monitoring_service
        )

    return _parallel_search_service
