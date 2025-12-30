"""
Empire v7.3 - Hybrid Search Service (Task 27)

Implements hybrid search combining multiple retrieval methods:
- Dense vector search (pgvector similarity via RPC)
- Sparse BM25 search (PostgreSQL full-text search with ts_rank_cd)
- Fuzzy matching (PostgreSQL trigram similarity + ILIKE)
- Reciprocal Rank Fusion (RRF) for result combination

Features:
- Server-side PostgreSQL RPC functions for optimal performance
- Python fallback for development/testing
- Configurable weights and thresholds
- Target: +40-60% improvement vs vector-only search

Author: Empire AI Team
Date: January 2025
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import math
import json

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class SearchMethod(Enum):
    """Available search methods"""
    DENSE = "dense"  # Vector similarity (pgvector)
    SPARSE = "sparse"  # BM25 full-text search (ts_rank_cd)
    FUZZY = "fuzzy"  # Trigram similarity + ILIKE pattern matching
    ILIKE = "ilike"  # Simple pattern matching only
    HYBRID = "hybrid"  # All methods combined with RRF
    HYBRID_RPC = "hybrid_rpc"  # Server-side hybrid search (recommended)


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
    file_id: Optional[str] = None

    # Additional fields for hybrid search
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    fuzzy_score: Optional[float] = None
    rrf_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "rank": self.rank,
            "method": self.method,
            "metadata": self.metadata,
            "file_id": self.file_id,
            "dense_score": self.dense_score,
            "sparse_score": self.sparse_score,
            "fuzzy_score": self.fuzzy_score,
            "rrf_score": self.rrf_score
        }


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
    min_sparse_score: float = 0.0  # BM25 relevance threshold (ts_rank_cd)
    min_fuzzy_score: float = 0.3  # Trigram similarity threshold (0-1)

    # Search behavior
    enable_dense: bool = True
    enable_sparse: bool = True
    enable_fuzzy: bool = True

    # Use server-side RPC functions (recommended for production)
    use_rpc: bool = True

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
        start_time = time.time()

        try:
            if method == SearchMethod.DENSE:
                results = await self._dense_search(query, config, namespace, metadata_filter)
            elif method == SearchMethod.SPARSE:
                results = await self._sparse_search_rpc(query, config, namespace, metadata_filter) \
                    if config.use_rpc else await self._sparse_search(query, config, namespace, metadata_filter)
            elif method == SearchMethod.FUZZY:
                results = await self._fuzzy_search_rpc(query, config, namespace, metadata_filter) \
                    if config.use_rpc else await self._fuzzy_search(query, config, namespace, metadata_filter)
            elif method == SearchMethod.ILIKE:
                results = await self._ilike_search(query, config, namespace, metadata_filter)
            elif method == SearchMethod.HYBRID_RPC:
                results = await self._hybrid_search_rpc(query, config, namespace, metadata_filter)
            else:  # HYBRID (default)
                results = await self._hybrid_search(query, config, namespace, metadata_filter)

            duration = time.time() - start_time
            logger.info(
                f"Search completed: method={method.value}, query='{query[:50]}...', "
                f"results={len(results)}, duration={duration:.3f}s"
            )

            return results

        except Exception as e:
            logger.error(f"Search failed: method={method.value}, error={e}")
            raise

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

    # =========================================================================
    # PostgreSQL RPC-based search methods (Task 27 - recommended for production)
    # =========================================================================

    async def _hybrid_search_rpc(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Server-side hybrid search using PostgreSQL RPC function

        This is the recommended approach for production as it:
        - Performs all computation on the database server
        - Leverages database indexes (HNSW, GIN, trigram)
        - Returns fused results in a single query
        - Significantly reduces latency

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            Fused and ranked search results
        """
        try:
            # Generate query embedding for dense search component
            embedding_result = await self.embedding_service.generate_embedding(query)
            query_embedding = embedding_result.embedding

            # Call the hybrid_search RPC function
            result = await self.storage.supabase.rpc(
                "hybrid_search",
                {
                    "search_query": query,
                    "query_embedding": query_embedding,
                    "match_limit": config.top_k,
                    "dense_weight": config.dense_weight,
                    "dense_threshold": config.min_dense_score,
                    "dense_count": config.dense_top_k,
                    "sparse_weight": config.sparse_weight,
                    "sparse_threshold": config.min_sparse_score,
                    "sparse_count": config.sparse_top_k,
                    "fuzzy_weight": config.fuzzy_weight,
                    "fuzzy_threshold": config.min_fuzzy_score,
                    "fuzzy_count": config.fuzzy_top_k,
                    "rrf_k": config.rrf_k,
                    "filter_namespace": namespace,
                    "filter_metadata": json.dumps(metadata_filter) if metadata_filter else None
                }
            ).execute()

            if not result.data:
                return []

            # Convert to SearchResult objects
            search_results = []
            for rank, row in enumerate(result.data, 1):
                search_results.append(SearchResult(
                    chunk_id=str(row["chunk_id"]),
                    content=row.get("content", ""),
                    score=row.get("rrf_score", 0.0),
                    rank=rank,
                    method="hybrid_rpc",
                    metadata=row.get("metadata", {}),
                    file_id=str(row["file_id"]) if row.get("file_id") else None,
                    dense_score=row.get("dense_score"),
                    sparse_score=row.get("sparse_score"),
                    fuzzy_score=row.get("fuzzy_score"),
                    rrf_score=row.get("rrf_score")
                ))

            return search_results

        except Exception as e:
            logger.warning(f"RPC hybrid search failed, falling back to Python: {e}")
            # Fallback to Python-based hybrid search
            return await self._hybrid_search(query, config, namespace, metadata_filter)

    async def _sparse_search_rpc(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        BM25 full-text search using PostgreSQL RPC function

        Uses ts_rank_cd for BM25-like scoring with proper document length normalization.

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            List of results from BM25 search
        """
        try:
            result = await self.storage.supabase.rpc(
                "search_chunks_bm25",
                {
                    "search_query": query,
                    "match_limit": config.sparse_top_k,
                    "min_rank": config.min_sparse_score,
                    "filter_namespace": namespace,
                    "filter_metadata": json.dumps(metadata_filter) if metadata_filter else None
                }
            ).execute()

            if not result.data:
                return []

            # Convert to SearchResult objects
            search_results = []
            for rank, row in enumerate(result.data, 1):
                search_results.append(SearchResult(
                    chunk_id=str(row["chunk_id"]),
                    content=row.get("content", ""),
                    score=row.get("rank", 0.0),
                    rank=rank,
                    method="sparse",
                    metadata=row.get("metadata", {}),
                    file_id=str(row["file_id"]) if row.get("file_id") else None,
                    sparse_score=row.get("rank")
                ))

            return search_results

        except Exception as e:
            logger.warning(f"RPC sparse search failed, falling back to Python: {e}")
            return await self._sparse_search(query, config, namespace, metadata_filter)

    async def _fuzzy_search_rpc(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Fuzzy search using PostgreSQL trigram similarity

        Uses pg_trgm extension for efficient fuzzy matching.

        Args:
            query: Search query
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            List of results from fuzzy search
        """
        try:
            result = await self.storage.supabase.rpc(
                "search_chunks_fuzzy",
                {
                    "search_query": query,
                    "match_limit": config.fuzzy_top_k,
                    "min_similarity": config.min_fuzzy_score,
                    "filter_namespace": namespace,
                    "filter_metadata": json.dumps(metadata_filter) if metadata_filter else None
                }
            ).execute()

            if not result.data:
                return []

            # Convert to SearchResult objects
            search_results = []
            for rank, row in enumerate(result.data, 1):
                search_results.append(SearchResult(
                    chunk_id=str(row["chunk_id"]),
                    content=row.get("content", ""),
                    score=row.get("similarity", 0.0),
                    rank=rank,
                    method="fuzzy",
                    metadata=row.get("metadata", {}),
                    file_id=str(row["file_id"]) if row.get("file_id") else None,
                    fuzzy_score=row.get("similarity")
                ))

            return search_results

        except Exception as e:
            logger.warning(f"RPC fuzzy search failed, falling back to Python: {e}")
            return await self._fuzzy_search(query, config, namespace, metadata_filter)

    async def _ilike_search(
        self,
        query: str,
        config: HybridSearchConfig,
        namespace: Optional[str],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Simple ILIKE pattern search

        Fast case-insensitive pattern matching without fuzzy scoring.

        Args:
            query: Search pattern
            config: Search configuration
            namespace: Filter by namespace
            metadata_filter: Filter by metadata

        Returns:
            List of matching results
        """
        try:
            result = await self.storage.supabase.rpc(
                "search_chunks_ilike",
                {
                    "search_pattern": query,
                    "match_limit": config.top_k,
                    "filter_namespace": namespace,
                    "filter_metadata": json.dumps(metadata_filter) if metadata_filter else None
                }
            ).execute()

            if not result.data:
                return []

            # Convert to SearchResult objects
            search_results = []
            for rank, row in enumerate(result.data, 1):
                search_results.append(SearchResult(
                    chunk_id=str(row["chunk_id"]),
                    content=row.get("content", ""),
                    score=1.0,  # ILIKE doesn't provide a score
                    rank=rank,
                    method="ilike",
                    metadata=row.get("metadata", {}),
                    file_id=str(row["file_id"]) if row.get("file_id") else None
                ))

            return search_results

        except Exception as e:
            logger.error(f"ILIKE search failed: {e}")
            return []

    async def get_search_stats(self) -> Dict[str, Any]:
        """
        Get statistics about searchable content

        Returns:
            Dictionary with search statistics
        """
        try:
            result = await self.storage.supabase.rpc(
                "get_search_stats"
            ).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return {}

        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {
                "error": str(e),
                "total_chunks": 0,
                "chunks_with_tsv": 0,
                "total_embeddings": 0
            }

    async def search_with_reranking(
        self,
        query: str,
        method: SearchMethod = SearchMethod.HYBRID,
        namespace: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        custom_config: Optional[HybridSearchConfig] = None,
        reranking_config: Optional[Any] = None
    ) -> Tuple[List[SearchResult], Dict[str, Any]]:
        """
        Perform hybrid search with optional reranking for improved precision

        This method combines hybrid search with BGE-Reranker-v2 or Cohere
        for +15-25% precision improvement.

        Args:
            query: Search query
            method: Search method to use
            namespace: Filter by namespace
            metadata_filter: Filter by metadata
            custom_config: Override default configuration
            reranking_config: Optional reranking configuration

        Returns:
            Tuple of (reranked results, metrics dict with reranking stats)
        """
        from app.services.reranking_service import (
            RerankingService, RerankingConfig, RerankingProvider
        )

        config = custom_config or self.config
        start_time = time.time()
        metrics = {
            "search_method": method.value,
            "search_time_ms": 0,
            "reranking_time_ms": 0,
            "total_time_ms": 0,
            "initial_results": 0,
            "reranked_results": 0,
            "reranking_provider": None,
            "ndcg": None
        }

        # Step 1: Perform initial search (get more results for reranking)
        search_config = custom_config or HybridSearchConfig(
            top_k=config.top_k * 3,  # Get 3x results for reranking
            dense_top_k=config.dense_top_k,
            sparse_top_k=config.sparse_top_k,
            fuzzy_top_k=config.fuzzy_top_k,
            dense_weight=config.dense_weight,
            sparse_weight=config.sparse_weight,
            fuzzy_weight=config.fuzzy_weight,
            rrf_k=config.rrf_k,
            min_dense_score=config.min_dense_score,
            min_sparse_score=config.min_sparse_score,
            min_fuzzy_score=config.min_fuzzy_score,
            use_rpc=config.use_rpc
        )

        initial_results = await self.search(
            query=query,
            method=method,
            namespace=namespace,
            metadata_filter=metadata_filter,
            custom_config=search_config
        )

        search_time = time.time()
        metrics["search_time_ms"] = (search_time - start_time) * 1000
        metrics["initial_results"] = len(initial_results)

        # Step 2: Rerank if we have results
        if not initial_results:
            metrics["total_time_ms"] = metrics["search_time_ms"]
            return [], metrics

        # Create reranking service with config
        rerank_config = reranking_config or RerankingConfig(
            provider=RerankingProvider.OLLAMA,
            top_k=config.top_k,
            max_input_results=len(initial_results),
            score_threshold=0.3,
            enable_metrics=True
        )

        reranking_service = RerankingService(config=rerank_config)

        try:
            reranking_result = await reranking_service.rerank(
                query=query,
                results=initial_results
            )

            # Update metrics
            if reranking_result.metrics:
                metrics["reranking_time_ms"] = reranking_result.metrics.reranking_time_ms
                metrics["reranking_provider"] = reranking_result.metrics.provider.value if reranking_result.metrics.provider else None
                metrics["ndcg"] = reranking_result.metrics.ndcg

            metrics["reranked_results"] = len(reranking_result.reranked_results)
            metrics["total_time_ms"] = (time.time() - start_time) * 1000

            # Update ranks based on new order
            final_results = []
            for i, result in enumerate(reranking_result.reranked_results, 1):
                result.rank = i
                final_results.append(result)

            return final_results, metrics

        except Exception as e:
            logger.error(f"Reranking failed, returning initial results: {e}")
            metrics["error"] = str(e)
            metrics["total_time_ms"] = (time.time() - start_time) * 1000
            metrics["reranked_results"] = len(initial_results)

            # Return top_k of initial results
            return initial_results[:config.top_k], metrics

        finally:
            await reranking_service.close()


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
