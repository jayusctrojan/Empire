"""
Empire v7.3 - Vector Storage Service

Handles storage and retrieval of vector embeddings in Supabase pgvector.

Features:
- Bulk insert/upsert operations for efficient batch processing
- Namespace-based organization for multi-tenant storage
- Metadata filtering for targeted similarity search
- HNSW index-based fast approximate nearest neighbor search
- Integration with monitoring service

Author: Empire AI Team
Date: January 2025
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class VectorRecord:
    """
    Represents a single vector embedding record
    """
    embedding: List[float]
    content_hash: str
    model: str
    dimensions: int
    namespace: str = "default"
    chunk_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            "embedding": self.embedding,
            "content_hash": self.content_hash,
            "model": self.model,
            "dimensions": self.dimensions,
            "namespace": self.namespace,
            "chunk_id": self.chunk_id,
            "metadata": self.metadata
        }


@dataclass
class SimilarityResult:
    """
    Result of a similarity search query
    """
    chunk_id: Optional[str]
    content_hash: str
    embedding: List[float]
    similarity: float  # 0.0 (dissimilar) to 1.0 (identical)
    model: str
    namespace: str
    metadata: Dict[str, Any]
    created_at: str

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SimilarityResult":
        """Create from database row"""
        return cls(
            chunk_id=row.get("chunk_id"),
            content_hash=row["content_hash"],
            embedding=row["embedding"],
            similarity=row["similarity"],
            model=row["model"],
            namespace=row.get("namespace", "default"),
            metadata=row.get("metadata", {}),
            created_at=row.get("created_at", "")
        )


@dataclass
class VectorStorageConfig:
    """
    Configuration for vector storage service
    """
    default_namespace: str = "default"
    batch_size: int = 100  # Max records per bulk operation
    similarity_threshold: float = 0.7  # Minimum similarity for search results
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds


class VectorStorageService:
    """
    Service for storing and retrieving vector embeddings in Supabase pgvector

    Features:
    - Bulk insert/upsert with automatic batching
    - Namespace-based isolation
    - Metadata filtering
    - Fast similarity search with HNSW indexes
    - Monitoring integration
    """

    def __init__(
        self,
        supabase_storage,
        config: Optional[VectorStorageConfig] = None,
        monitoring_service=None
    ):
        """
        Initialize vector storage service

        Args:
            supabase_storage: Supabase storage client
            config: Service configuration
            monitoring_service: Optional monitoring service for metrics
        """
        self.storage = supabase_storage
        self.config = config or VectorStorageConfig()
        self.monitoring = monitoring_service

        logger.info(
            f"Vector storage service initialized "
            f"(batch_size={self.config.batch_size}, "
            f"default_namespace={self.config.default_namespace})"
        )

    async def store_vectors_batch(
        self,
        records: List[VectorRecord],
        namespace: Optional[str] = None,
        on_conflict: str = "update"  # "update", "ignore", or "error"
    ) -> Dict[str, Any]:
        """
        Store multiple vector records in a single batch operation

        Args:
            records: List of VectorRecord objects to store
            namespace: Override namespace for all records
            on_conflict: How to handle conflicts ("update", "ignore", "error")

        Returns:
            Dict with insertion results and stats
        """
        if not records:
            return {"success": True, "inserted": 0, "updated": 0, "errors": 0}

        start_time = time.time()
        namespace = namespace or self.config.default_namespace

        # Override namespace if provided
        for record in records:
            if namespace:
                record.namespace = namespace

        # Process in batches
        batch_size = self.config.batch_size
        total_inserted = 0
        total_updated = 0
        total_errors = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            try:
                result = await self._insert_batch(batch, on_conflict)
                total_inserted += result.get("inserted", 0)
                total_updated += result.get("updated", 0)
                total_errors += result.get("errors", 0)

            except Exception as e:
                logger.error(f"Error inserting batch {i//batch_size + 1}: {e}")
                total_errors += len(batch)

        duration = time.time() - start_time

        # Track metrics
        if self.monitoring:
            # This would use monitoring service metrics
            pass

        logger.info(
            f"Batch insert completed: {total_inserted} inserted, "
            f"{total_updated} updated, {total_errors} errors "
            f"in {duration:.2f}s"
        )

        return {
            "success": total_errors == 0,
            "inserted": total_inserted,
            "updated": total_updated,
            "errors": total_errors,
            "duration": duration,
            "namespace": namespace
        }

    async def _insert_batch(
        self,
        batch: List[VectorRecord],
        on_conflict: str
    ) -> Dict[str, int]:
        """
        Insert a single batch using Supabase upsert

        Args:
            batch: Records to insert
            on_conflict: Conflict resolution strategy

        Returns:
            Dict with counts of inserted/updated/error records
        """
        data = [record.to_dict() for record in batch]

        try:
            if on_conflict == "update":
                # Upsert: insert or update on conflict
                result = await self.storage.supabase.table("embeddings_cache")\
                    .upsert(data)\
                    .execute()

                return {
                    "inserted": len(result.data) if result.data else 0,
                    "updated": 0,  # Supabase doesn't distinguish
                    "errors": 0
                }

            elif on_conflict == "ignore":
                # Insert only, ignore conflicts
                result = await self.storage.supabase.table("embeddings_cache")\
                    .insert(data, on_conflict="ignore")\
                    .execute()

                return {
                    "inserted": len(result.data) if result.data else 0,
                    "updated": 0,
                    "errors": 0
                }

            else:  # "error"
                # Insert only, raise error on conflict
                result = await self.storage.supabase.table("embeddings_cache")\
                    .insert(data)\
                    .execute()

                return {
                    "inserted": len(result.data) if result.data else 0,
                    "updated": 0,
                    "errors": 0
                }

        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            return {
                "inserted": 0,
                "updated": 0,
                "errors": len(batch)
            }

    async def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        namespace: Optional[str] = None,
        model: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[SimilarityResult]:
        """
        Find similar vectors using cosine similarity

        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            namespace: Filter by namespace
            model: Filter by embedding model
            metadata_filter: Filter by metadata fields
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of SimilarityResult objects ordered by similarity
        """
        threshold = similarity_threshold or self.config.similarity_threshold
        namespace = namespace or self.config.default_namespace

        start_time = time.time()

        try:
            # Build query
            query = self.storage.supabase.table("embeddings_cache")\
                .select(
                    "chunk_id, content_hash, embedding, model, namespace, "
                    "metadata, created_at"
                )

            # Apply namespace filter
            if namespace:
                query = query.eq("namespace", namespace)

            # Apply model filter
            if model:
                query = query.eq("model", model)

            # Apply metadata filters
            if metadata_filter:
                for key, value in metadata_filter.items():
                    query = query.eq(f"metadata->>{key}", value)

            # Execute query
            # Note: Supabase Python client doesn't support vector operations directly yet
            # We need to use RPC or raw SQL for vector similarity

            # For now, we'll fetch all matching records and compute similarity in Python
            # In production, use Supabase RPC function for server-side vector search
            result = await query.execute()

            if not result.data:
                return []

            # Compute cosine similarity for each result
            results = []
            for row in result.data:
                embedding = row["embedding"]
                similarity = self._cosine_similarity(query_embedding, embedding)

                if similarity >= threshold:
                    results.append({
                        **row,
                        "similarity": similarity
                    })

            # Sort by similarity (descending) and limit
            results.sort(key=lambda x: x["similarity"], reverse=True)
            results = results[:limit]

            # Convert to SimilarityResult objects
            similarity_results = [
                SimilarityResult.from_db_row(row)
                for row in results
            ]

            duration = time.time() - start_time

            logger.info(
                f"Similarity search completed: {len(similarity_results)} results "
                f"in {duration:.2f}s (namespace={namespace}, model={model})"
            )

            return similarity_results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []

    async def similarity_search_rpc(
        self,
        query_embedding: List[float],
        limit: int = 10,
        namespace: Optional[str] = None,
        model: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[SimilarityResult]:
        """
        Find similar vectors using Supabase RPC function (server-side)

        This is the recommended approach for production as it leverages
        the HNSW index and performs computation on the database server.

        Requires a Supabase function like:

        CREATE OR REPLACE FUNCTION match_embeddings(
            query_embedding vector(1024),
            match_threshold float,
            match_count int,
            filter_namespace text DEFAULT NULL,
            filter_model text DEFAULT NULL
        )
        RETURNS TABLE (
            chunk_id uuid,
            content_hash varchar,
            embedding vector(1024),
            model varchar,
            namespace varchar,
            metadata jsonb,
            created_at timestamptz,
            similarity float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                e.chunk_id,
                e.content_hash,
                e.embedding,
                e.model,
                e.namespace,
                e.metadata,
                e.created_at,
                1 - (e.embedding <=> query_embedding) as similarity
            FROM embeddings_cache e
            WHERE (filter_namespace IS NULL OR e.namespace = filter_namespace)
              AND (filter_model IS NULL OR e.model = filter_model)
              AND 1 - (e.embedding <=> query_embedding) >= match_threshold
            ORDER BY e.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;

        Args:
            query_embedding: Query vector
            limit: Maximum number of results
            namespace: Filter by namespace
            model: Filter by embedding model
            metadata_filter: Filter by metadata (requires additional RPC parameters)
            similarity_threshold: Minimum similarity score

        Returns:
            List of SimilarityResult objects
        """
        threshold = similarity_threshold or self.config.similarity_threshold
        namespace = namespace or self.config.default_namespace

        try:
            result = await self.storage.supabase.rpc(
                "match_embeddings",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "filter_namespace": namespace,
                    "filter_model": model
                }
            ).execute()

            if not result.data:
                return []

            return [
                SimilarityResult.from_db_row(row)
                for row in result.data
            ]

        except Exception as e:
            logger.error(f"RPC similarity search failed: {e}")
            # Fallback to Python-based search
            return await self.similarity_search(
                query_embedding,
                limit,
                namespace,
                model,
                metadata_filter,
                similarity_threshold
            )

    async def get_by_namespace(
        self,
        namespace: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all vectors from a specific namespace

        Args:
            namespace: Namespace to query
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of vector records
        """
        try:
            query = self.storage.supabase.table("embeddings_cache")\
                .select("*")\
                .eq("namespace", namespace)\
                .range(offset, offset + limit - 1 if limit else 999999)

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Get by namespace failed: {e}")
            return []

    async def delete_by_namespace(
        self,
        namespace: str
    ) -> int:
        """
        Delete all vectors in a namespace

        Args:
            namespace: Namespace to delete

        Returns:
            Number of records deleted
        """
        try:
            result = await self.storage.supabase.table("embeddings_cache")\
                .delete()\
                .eq("namespace", namespace)\
                .execute()

            count = len(result.data) if result.data else 0
            logger.info(f"Deleted {count} vectors from namespace '{namespace}'")
            return count

        except Exception as e:
            logger.error(f"Delete by namespace failed: {e}")
            return 0

    async def get_namespaces(self) -> List[Dict[str, Any]]:
        """
        Get all namespaces and their record counts

        Returns:
            List of dicts with namespace stats
        """
        try:
            # Use RPC or raw SQL for aggregation
            # For now, fetch all records and count in Python
            result = await self.storage.supabase.table("embeddings_cache")\
                .select("namespace")\
                .execute()

            if not result.data:
                return []

            # Count by namespace
            namespace_counts = {}
            for row in result.data:
                ns = row.get("namespace", "default")
                namespace_counts[ns] = namespace_counts.get(ns, 0) + 1

            return [
                {"namespace": ns, "count": count}
                for ns, count in namespace_counts.items()
            ]

        except Exception as e:
            logger.error(f"Get namespaces failed: {e}")
            return []

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two vectors

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        import math

        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimensions")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


# Singleton instance
_vector_storage_service = None


def get_vector_storage_service(
    supabase_storage=None,
    monitoring_service=None,
    config: Optional[VectorStorageConfig] = None
) -> VectorStorageService:
    """
    Get singleton vector storage service instance

    Args:
        supabase_storage: Supabase storage client
        monitoring_service: Optional monitoring service
        config: Optional configuration

    Returns:
        VectorStorageService instance
    """
    global _vector_storage_service

    if _vector_storage_service is None:
        if supabase_storage is None:
            from app.services.supabase_storage import get_supabase_storage
            supabase_storage = get_supabase_storage()

        if monitoring_service is None:
            try:
                from app.services.monitoring_service import get_monitoring_service
                monitoring_service = get_monitoring_service(supabase_storage)
            except ImportError:
                logger.warning("Monitoring service not available")
                monitoring_service = None

        _vector_storage_service = VectorStorageService(
            supabase_storage,
            config,
            monitoring_service
        )

    return _vector_storage_service
