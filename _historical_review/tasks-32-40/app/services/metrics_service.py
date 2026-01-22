"""
Analytics metrics service for Empire v7.2
Collects and aggregates metrics from Supabase for Grafana dashboards
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog
from supabase import Client

logger = structlog.get_logger(__name__)


class MetricsService:
    """Service for collecting and aggregating analytics metrics"""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_document_stats(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """
        Get document statistics

        Args:
            time_range_hours: Time range in hours (default: 24)

        Returns:
            Dictionary with document statistics
        """
        try:
            # Total documents
            total_result = self.supabase.table("documents").select("id", count="exact").execute()
            total_count = total_result.count if total_result.count else 0

            # Recent documents (within time range)
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)
            recent_result = self.supabase.table("documents").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            recent_count = recent_result.count if recent_result.count else 0

            # Documents by type
            type_result = self.supabase.table("documents").select("file_type").execute()
            type_counts = {}
            if type_result.data:
                for doc in type_result.data:
                    file_type = doc.get("file_type", "unknown")
                    type_counts[file_type] = type_counts.get(file_type, 0) + 1

            # Processing status
            status_result = self.supabase.table("processing_tasks").select("status").execute()
            status_counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
            if status_result.data:
                for task in status_result.data:
                    status = task.get("status", "unknown")
                    if status in status_counts:
                        status_counts[status] += 1

            # Storage size (sum of file_size_bytes)
            size_result = self.supabase.table("documents").select("file_size_bytes").execute()
            total_size_bytes = 0
            if size_result.data:
                for doc in size_result.data:
                    size_bytes = doc.get("file_size_bytes", 0)
                    if size_bytes:
                        total_size_bytes += size_bytes

            return {
                "total_documents": total_count,
                "recent_documents": recent_count,
                "documents_by_type": type_counts,
                "processing_status": status_counts,
                "total_storage_bytes": total_size_bytes,
                "total_storage_gb": round(total_size_bytes / (1024**3), 2)
            }

        except Exception as e:
            logger.error("Failed to get document stats", error=str(e))
            raise

    async def get_query_metrics(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """
        Get query performance metrics

        Args:
            time_range_hours: Time range in hours (default: 24)

        Returns:
            Dictionary with query metrics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)

            # Total queries
            total_result = self.supabase.table("search_queries").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            total_queries = total_result.count if total_result.count else 0

            # Queries by type
            type_result = self.supabase.table("search_queries").select(
                "search_type"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            type_counts = {}
            if type_result.data:
                for query in type_result.data:
                    search_type = query.get("search_type", "unknown")
                    type_counts[search_type] = type_counts.get(search_type, 0) + 1

            # Average latency (if latency_ms field exists)
            latency_result = self.supabase.table("search_queries").select(
                "latency_ms"
            ).gte("created_at", cutoff_time.isoformat()).execute()

            total_latency = 0
            latency_count = 0
            min_latency = float('inf')
            max_latency = 0

            if latency_result.data:
                for query in latency_result.data:
                    latency = query.get("latency_ms")
                    if latency is not None:
                        total_latency += latency
                        latency_count += 1
                        min_latency = min(min_latency, latency)
                        max_latency = max(max_latency, latency)

            avg_latency = round(total_latency / latency_count, 2) if latency_count > 0 else 0
            min_latency = min_latency if min_latency != float('inf') else 0

            # Cache hit rate (if available)
            cache_result = self.supabase.table("search_cache").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            cache_hits = cache_result.count if cache_result.count else 0
            cache_hit_rate = round((cache_hits / total_queries * 100), 2) if total_queries > 0 else 0

            return {
                "total_queries": total_queries,
                "queries_by_type": type_counts,
                "avg_latency_ms": avg_latency,
                "min_latency_ms": min_latency,
                "max_latency_ms": max_latency,
                "cache_hits": cache_hits,
                "cache_hit_rate_percent": cache_hit_rate
            }

        except Exception as e:
            logger.error("Failed to get query metrics", error=str(e))
            raise

    async def get_user_activity_metrics(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """
        Get user activity metrics

        Args:
            time_range_hours: Time range in hours (default: 24)

        Returns:
            Dictionary with user activity metrics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)

            # Total active users
            user_result = self.supabase.table("admin_users").select(
                "id", count="exact"
            ).eq("is_active", True).execute()
            active_users = user_result.count if user_result.count else 0

            # Recent logins
            login_result = self.supabase.table("admin_sessions").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            recent_logins = login_result.count if login_result.count else 0

            # User actions (from activity log)
            action_result = self.supabase.table("admin_activity_log").select(
                "action_type"
            ).gte("created_at", cutoff_time.isoformat()).execute()

            action_counts = {}
            if action_result.data:
                for action in action_result.data:
                    action_type = action.get("action_type", "unknown")
                    action_counts[action_type] = action_counts.get(action_type, 0) + 1

            # Active sessions
            session_result = self.supabase.table("admin_sessions").select(
                "id", count="exact"
            ).gt("expires_at", datetime.utcnow().isoformat()).execute()
            active_sessions = session_result.count if session_result.count else 0

            return {
                "active_users": active_users,
                "recent_logins": recent_logins,
                "active_sessions": active_sessions,
                "actions_by_type": action_counts,
                "total_actions": sum(action_counts.values())
            }

        except Exception as e:
            logger.error("Failed to get user activity metrics", error=str(e))
            raise

    async def get_storage_usage(self) -> Dict[str, Any]:
        """
        Get storage usage across different components

        Returns:
            Dictionary with storage usage metrics
        """
        try:
            # Document storage (from documents table)
            doc_result = self.supabase.table("documents").select("file_size_bytes").execute()
            total_doc_size = 0
            doc_count = 0
            if doc_result.data:
                for doc in doc_result.data:
                    size = doc.get("file_size_bytes", 0)
                    if size:
                        total_doc_size += size
                        doc_count += 1

            # Chunk storage estimate (chunks * avg chunk size)
            chunk_result = self.supabase.table("document_chunks").select(
                "content_length", count="exact"
            ).execute()
            total_chunk_size = 0
            chunk_count = chunk_result.count if chunk_result.count else 0

            if chunk_result.data:
                for chunk in chunk_result.data:
                    length = chunk.get("content_length", 0)
                    if length:
                        total_chunk_size += length

            # Embedding storage estimate (vector dimensions * 4 bytes * count)
            embedding_result = self.supabase.table("embedding_generations").select(
                "id", count="exact"
            ).execute()
            embedding_count = embedding_result.count if embedding_result.count else 0
            # Assuming 1024 dimensions * 4 bytes per float
            embedding_size = embedding_count * 1024 * 4

            # Total storage
            total_storage = total_doc_size + total_chunk_size + embedding_size

            return {
                "documents": {
                    "count": doc_count,
                    "size_bytes": total_doc_size,
                    "size_gb": round(total_doc_size / (1024**3), 2)
                },
                "chunks": {
                    "count": chunk_count,
                    "size_bytes": total_chunk_size,
                    "size_gb": round(total_chunk_size / (1024**3), 2)
                },
                "embeddings": {
                    "count": embedding_count,
                    "size_bytes": embedding_size,
                    "size_gb": round(embedding_size / (1024**3), 2)
                },
                "total": {
                    "size_bytes": total_storage,
                    "size_gb": round(total_storage / (1024**3), 2)
                }
            }

        except Exception as e:
            logger.error("Failed to get storage usage", error=str(e))
            raise

    async def get_api_endpoint_metrics(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """
        Get API endpoint usage metrics

        Args:
            time_range_hours: Time range in hours (default: 24)

        Returns:
            Dictionary with API endpoint metrics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)

            # Get query endpoint usage
            query_result = self.supabase.table("search_queries").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            query_count = query_result.count if query_result.count else 0

            # Get document endpoint usage (uploads)
            doc_result = self.supabase.table("documents").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            doc_count = doc_result.count if doc_result.count else 0

            # Get user actions (represents API calls to user management endpoints)
            action_result = self.supabase.table("admin_activity_log").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            action_count = action_result.count if action_result.count else 0

            # Session operations
            session_result = self.supabase.table("admin_sessions").select(
                "id", count="exact"
            ).gte("created_at", cutoff_time.isoformat()).execute()
            session_count = session_result.count if session_result.count else 0

            total_requests = query_count + doc_count + action_count + session_count

            return {
                "total_requests": total_requests,
                "requests_per_hour": round(total_requests / time_range_hours, 2),
                "endpoints": {
                    "query": query_count,
                    "documents": doc_count,
                    "users": action_count,
                    "sessions": session_count
                }
            }

        except Exception as e:
            logger.error("Failed to get API endpoint metrics", error=str(e))
            raise

    async def get_all_metrics(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """
        Get all metrics in one call

        Args:
            time_range_hours: Time range in hours (default: 24)

        Returns:
            Dictionary with all metrics categories
        """
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "time_range_hours": time_range_hours,
                "documents": await self.get_document_stats(time_range_hours),
                "queries": await self.get_query_metrics(time_range_hours),
                "users": await self.get_user_activity_metrics(time_range_hours),
                "storage": await self.get_storage_usage(),
                "api_endpoints": await self.get_api_endpoint_metrics(time_range_hours)
            }
        except Exception as e:
            logger.error("Failed to get all metrics", error=str(e))
            raise
