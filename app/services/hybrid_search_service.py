"""
Empire v7.3 - Hybrid Search Service

Implements hybrid search combining multiple retrieval methods:
- Dense vector search (pgvector similarity)
- Sparse BM25 search (PostgreSQL full-text search)
- Fuzzy matching (ILIKE pattern matching + rapidfuzz)
- Reciprocal Rank Fusion (RRF) for result combination

Author: Empire AI Team
Date: January 2025
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import math

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class SearchMethod(Enum):
    """Available search methods"""
    DENSE = "dense"  # Vector similarity
    SPARSE = "sparse"  # BM25 full-text search
    FUZZY = "fuzzy"  # Pattern matching + fuzzy string matching
    HYBRID = "hybrid"  # All methods combined with RRF


@dataclass
class SearchResult:
    """
    Single search result with metadata
    """
    chunk_id: str
    content: str
    score: float
    rank: int
    method: str  # Which search method found this result
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Additional fields for hybrid search
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    fuzzy_score: Optional[float] = None
    rrf_score: Optional[float] = None


@dataclass
class HybridSearchConfig:
    """
    Configuration for hybrid search
    """
    # Method weights for RRF fusion (must sum to 1.0)
    dense_weight: float = 0.5  # Vector similarity weight
    sparse_weight: float = 0.3  # BM25 weight
    fuzzy_weight: float = 0.2  # Fuzzy matching weight

    # Search parameters
    top_k: int = 10  # Number of results to return
    dense_top_k: int = 20  # Results from dense search
    sparse_top_k: int = 20  # Results from sparse search
    fuzzy_top_k: int = 20  # Results from fuzzy search

    # RRF parameter (controls rank decay)
    rrf_k: int = 60  # Higher = slower rank decay

    # Minimum scores to include results
    min_dense_score: float = 0.5  # Cosine similarity threshold
    min_sparse_score: float = 0.1  # BM25 relevance threshold
    min_fuzzy_score: float = 60.0  # Fuzzy match percentage

    # Search behavior
    enable_dense: bool = True
    enable_sparse: bool = True
    enable_fuzzy: bool = True

    def validate(self):
        """Validate configuration"""
        total_weight = self.dense_weight + self.sparse_weight + self.fuzzy_weight
        if not math.isclose(total_weight, 1.0, rel_tol=1e-5):
            raise ValueError(
                f"Method weights must sum to 1.0, got {total_weight}"
            )


class HybridSearchService:
    """
    Service for hybrid search combining dense, sparse, and fuzzy retrieval

    Features:
    - Dense vector search using pgvector
    - Sparse BM25 search using PostgreSQL full-text search
    - Fuzzy matching using ILIKE and rapidfuzz
    - Reciprocal Rank Fusion (RRF) for result combination
    - Configurable weights and thresholds
    """

    def __init__(
        self,
        supabase_storage,
        vector_storage_service,
        embedding_service,
        config: Optional[HybridSearchConfig] = None,
        monitoring_service=None
    ):
        """
        Initialize hybrid search service

        Args:
            supabase_storage: Supabase storage client
            vector_storage_service: Vector storage service for dense search
            embedding_service: Embedding service to generate query embeddings
            config: Search configuration
            monitoring_service: Optional monitoring service
        """
        self.storage = supabase_storage
        self.vector_service = vector_storage_service
        self.embedding_service = embedding_service
        self.config = config or HybridSearchConfig()
        self.monitoring = monitoring_service

        self.config.validate()

        logger.info(
            f"Hybrid search service initialized "
            f"(dense={self.config.dense_weight}, "
            f"sparse={self.config.sparse_weight}, "
            f"fuzzy={self.config.fuzzy_weight})"
        )

    async def search(
        self,
        query: str,
        method: SearchMethod = SearchMethod.HYBRID,
        namespace: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        custom_config: Optional[HybridSearchConfig] = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search

        Args:
            query: Search query
            method: Search method to use
            namespace: Filter by namespace
            metadata_filter: Filter by metadata
            custom_config: Override default configuration

        Returns:
            List of SearchResult objects ranked by relevance
        """
        config = custom_config or self.config

        if method == SearchMethod.DENSE:
            return await self._dense_search(query, config, namespace, metadata_filter)
        elif method == SearchMethod.SPARSE:
            return await self._sparse_search(query, config, namespace, metadata_filter)
        elif method == SearchMethod.FUZZY:
            return await self._fuzzy_search(query, config, namespace, metadata_filter)
        else:  # HYBRID
            return await self._hybrid_search(query, config, namespace, metadata_filter)

    async def _hybrid_search(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining all methods with RRF

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            Fused and ranked search results
        """
        # Run all search methods in parallel
        tasks = []

        if config.enable_dense:
            tasks.append(self._dense_search(query, config, namespace, metadata_filter))
        if config.enable_sparse:
            tasks.append(self._sparse_search(query, config, namespace, metadata_filter))
        if config.enable_fuzzy:
            tasks.append(self._fuzzy_search(query, config, namespace, metadata_filter))

        # Execute all searches concurrently
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results_lists):
            if isinstance(result, Exception):
                logger.error(f"Search method {i} failed: {result}")
            else:
                valid_results.append(result)

        if not valid_results:
            return []

        # Apply Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            valid_results,
            config
        )

        # Sort by RRF score and limit to top_k
        fused_results.sort(key=lambda x: x.rrf_score, reverse=True)
        return fused_results[:config.top_k]

    async def _dense_search(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Dense vector similarity search

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            List of results from vector similarity search
        """
        # Generate query embedding
        embedding_result = await self.embedding_service.generate_embedding(query)
        query_embedding = embedding_result.embedding

        # Perform similarity search
        similarity_results = await self.vector_service.similarity_search(
            query_embedding,
            limit=config.dense_top_k,
            namespace=namespace,
            metadata_filter=metadata_filter,
            similarity_threshold=config.min_dense_score
        )

        # Convert to SearchResult
        search_results = []
        for rank, sim_result in enumerate(similarity_results, 1):
            # Fetch actual content from chunks table
            content = await self._get_chunk_content(sim_result.chunk_id)

            search_results.append(SearchResult(
                chunk_id=sim_result.chunk_id,
                content=content,
                score=sim_result.similarity,
                rank=rank,
                method="dense",
                metadata=sim_result.metadata,
                dense_score=sim_result.similarity
            ))

        return search_results

    async def _sparse_search(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Sparse BM25 full-text search using PostgreSQL

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            List of results from BM25 search
        """
        # Use PostgreSQL ts_rank for BM25-like scoring
        # This requires a tsvector column on the chunks table

        try:
            # Build query
            query_builder = self.storage.supabase.table("chunks")\
                .select("id, content, metadata, file_id")

            # Apply namespace filter (if chunks table has namespace)
            # For now, we'll search all chunks

            # Apply metadata filter
            if metadata_filter:
                for key, value in metadata_filter.items():
                    query_builder = query_builder.eq(f"metadata->>{key}", value)

            # Execute query to get all chunks (we'll filter by text match in Python)
            # In production, use PostgreSQL full-text search with ts_rank
            result = await query_builder.limit(config.sparse_top_k * 3).execute()

            if not result.data:
                return []

            # Perform BM25-like scoring in Python
            # In production, this should be done in PostgreSQL with proper indexes
            scored_results = []
            for chunk in result.data:
                content = chunk.get("content", "")
                score = self._bm25_score(query, content)

                if score >= config.min_sparse_score:
                    scored_results.append({
                        "chunk_id": chunk["id"],
                        "content": content,
                        "score": score,
                        "metadata": chunk.get("metadata", {})
                    })

            # Sort by score and limit
            scored_results.sort(key=lambda x: x["score"], reverse=True)
            scored_results = scored_results[:config.sparse_top_k]

            # Convert to SearchResult
            search_results = []
            for rank, result in enumerate(scored_results, 1):
                search_results.append(SearchResult(
                    chunk_id=result["chunk_id"],
                    content=result["content"],
                    score=result["score"],
                    rank=rank,
                    method="sparse",
                    metadata=result["metadata"],
                    sparse_score=result["score"]
                ))

            return search_results

        except Exception as e:
            logger.error(f"Sparse search failed: {e}")
            return []

    async def _fuzzy_search(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Fuzzy matching search using ILIKE and rapidfuzz

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            List of results from fuzzy matching
        """
        try:
            # Step 1: Pattern matching with ILIKE (fast initial filter)
            query_builder = self.storage.supabase.table("chunks")\
                .select("id, content, metadata, file_id")\
                .ilike("content", f"%{query}%")

            # Apply metadata filter
            if metadata_filter:
                for key, value in metadata_filter.items():
                    query_builder = query_builder.eq(f"metadata->>{key}", value)

            result = await query_builder.limit(config.fuzzy_top_k * 3).execute()

            if not result.data:
                return []

            # Step 2: Fuzzy string matching with rapidfuzz
            candidates = [
                {
                    "id": chunk["id"],
                    "content": chunk.get("content", ""),
                    "metadata": chunk.get("metadata", {})
                }
                for chunk in result.data
            ]

            # Compute fuzzy scores
            scored_results = []
            for candidate in candidates:
                # Use token_sort_ratio for better matching
                score = fuzz.token_sort_ratio(
                    query.lower(),
                    candidate["content"].lower()
                )

                if score >= config.min_fuzzy_score:
                    scored_results.append({
                        "chunk_id": candidate["id"],
                        "content": candidate["content"],
                        "score": score / 100.0,  # Normalize to 0-1
                        "metadata": candidate["metadata"]
                    })

            # Sort by score and limit
            scored_results.sort(key=lambda x: x["score"], reverse=True)
            scored_results = scored_results[:config.fuzzy_top_k]

            # Convert to SearchResult
            search_results = []
            for rank, result in enumerate(scored_results, 1):
                search_results.append(SearchResult(
                    chunk_id=result["chunk_id"],
                    content=result["content"],
                    score=result["score"],
                    rank=rank,
                    method="fuzzy",
                    metadata=result["metadata"],
                    fuzzy_score=result["score"]
                ))

            return search_results

        except Exception as e:
            logger.error(f"Fuzzy search failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        results_lists: List[List[SearchResult]],
        config: HybridSearchConfig
    ) -> List[SearchResult]:
        """
        Combine multiple ranked lists using Reciprocal Rank Fusion (RRF)

        RRF formula: score = Σ (weight_i / (k + rank_i))

        Args:
            results_lists: List of result lists from different methods
            config: Search configuration with weights and k parameter

        Returns:
            Fused list of unique results with RRF scores
        """
        # Map chunk_id to SearchResult with combined scores
        chunk_scores: Dict[str, SearchResult] = {}

        # Determine which method each list represents
        method_weights = {
            "dense": config.dense_weight,
            "sparse": config.sparse_weight,
            "fuzzy": config.fuzzy_weight
        }

        for results in results_lists:
            if not results:
                continue

            method = results[0].method
            weight = method_weights.get(method, 0.0)

            for result in results:
                chunk_id = result.chunk_id

                # RRF score contribution from this method
                rrf_contribution = weight / (config.rrf_k + result.rank)

                if chunk_id in chunk_scores:
                    # Update existing result
                    existing = chunk_scores[chunk_id]
                    existing.rrf_score = (existing.rrf_score or 0.0) + rrf_contribution

                    # Update method-specific scores
                    if method == "dense" and result.dense_score:
                        existing.dense_score = result.dense_score
                    elif method == "sparse" and result.sparse_score:
                        existing.sparse_score = result.sparse_score
                    elif method == "fuzzy" and result.fuzzy_score:
                        existing.fuzzy_score = result.fuzzy_score
                else:
                    # Add new result
                    result.rrf_score = rrf_contribution
                    result.method = "hybrid"  # Mark as hybrid result
                    chunk_scores[chunk_id] = result

        return list(chunk_scores.values())

    def _bm25_score(self, query: str, document: str) -> float:
        """
        Simple BM25 scoring (simplified version)

        In production, use PostgreSQL ts_rank_cd with proper BM25 parameters

        Args:
            query: Search query
            document: Document text

        Returns:
            BM25 relevance score
        """
        # Tokenize
        query_terms = set(query.lower().split())
        doc_terms = document.lower().split()
        doc_length = len(doc_terms)

        if doc_length == 0:
            return 0.0

        # Count term frequencies
        term_freq = {}
        for term in doc_terms:
            term_freq[term] = term_freq.get(term, 0) + 1

        # Simplified BM25 (missing IDF and collection stats)
        k1 = 1.5  # Term frequency saturation
        b = 0.75  # Length normalization
        avg_doc_length = 500  # Assumed average

        score = 0.0
        for term in query_terms:
            if term in term_freq:
                tf = term_freq[term]
                # Simplified BM25 term score
                term_score = (tf * (k1 + 1)) / (
                    tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
                )
                score += term_score

        # Normalize by query length
        return score / max(len(query_terms), 1)

    async def _get_chunk_content(self, chunk_id: str) -> str:
        """
        Retrieve chunk content from database

        Args:
            chunk_id: Chunk UUID

        Returns:
            Chunk content text
        """
        try:
            result = await self.storage.supabase.table("chunks")\
                .select("content")\
                .eq("id", chunk_id)\
                .limit(1)\
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0].get("content", "")
            return ""

        except Exception as e:
            logger.error(f"Failed to get chunk content: {e}")
            return ""


# Singleton instance
_hybrid_search_service = None


def get_hybrid_search_service(
    supabase_storage=None,
    vector_storage_service=None,
    embedding_service=None,
    monitoring_service=None,
    config: Optional[HybridSearchConfig] = None
) -> HybridSearchService:
    """
    Get singleton hybrid search service instance

    Args:
        supabase_storage: Supabase storage client
        vector_storage_service: Vector storage service
        embedding_service: Embedding service
        monitoring_service: Optional monitoring service
        config: Optional configuration

    Returns:
        HybridSearchService instance
    """
    global _hybrid_search_service

    if _hybrid_search_service is None:
        if supabase_storage is None:
            from app.services.supabase_storage import get_supabase_storage
            supabase_storage = get_supabase_storage()

        if vector_storage_service is None:
            from app.services.vector_storage_service import get_vector_storage_service
            vector_storage_service = get_vector_storage_service(supabase_storage)

        if embedding_service is None:
            from app.services.embedding_service import get_embedding_service
            embedding_service = get_embedding_service(supabase_storage, monitoring_service)

        _hybrid_search_service = HybridSearchService(
            supabase_storage,
            vector_storage_service,
            embedding_service,
            config,
            monitoring_service
        )

    return _hybrid_search_service
