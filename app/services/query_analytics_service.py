"""
Query Analytics Service

Provides query logging, metric tracking, and CTR calculation for search analytics.

Features:
- Log all search queries with latency and result counts
- Track click events with position and metadata
- Calculate click-through rates (CTR)
- Aggregate metrics and statistics
- Support for date-range queries

Usage:
    from app.services.query_analytics_service import get_query_analytics_service

    service = get_query_analytics_service()

    # Log a query
    query_log = await service.log_query(
        query_text="California insurance",
        latency_ms=125.5,
        result_count=10,
        user_session_id=session_id
    )

    # Log a click
    click_event = await service.log_click(
        query_id=query_log.query_id,
        result_id="chunk123",
        result_rank=1,
        user_session_id=session_id
    )

    # Get metrics
    metrics = await service.get_query_metrics(query_id=query_log.query_id)
    print(f"CTR: {metrics.ctr}")
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsConfig:
    """Configuration for query analytics"""
    enable_query_logging: bool = True
    enable_click_tracking: bool = True
    log_latency: bool = True
    log_metadata: bool = True
    retention_days: int = 90  # How long to keep analytics data

    # CTR calculation settings
    min_impressions_for_ctr: int = 1

    # Batch processing
    batch_size: int = 100
    flush_interval_seconds: int = 60


@dataclass
class QueryLog:
    """Log entry for a search query"""
    query_id: str
    query_text: str
    user_session_id: str
    created_at: datetime
    latency_ms: float
    result_count: int
    search_type: str = "hybrid"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "user_session_id": self.user_session_id,
            "created_at": self.created_at.isoformat(),
            "latency_ms": self.latency_ms,
            "result_count": self.result_count,
            "search_type": self.search_type,
            "metadata": self.metadata
        }


@dataclass
class ClickEvent:
    """Log entry for a result click"""
    click_id: str
    query_id: str
    result_id: str
    result_rank: int
    clicked_at: datetime
    user_session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "click_id": self.click_id,
            "query_id": self.query_id,
            "result_id": self.result_id,
            "result_rank": self.result_rank,
            "clicked_at": self.clicked_at.isoformat(),
            "user_session_id": self.user_session_id,
            "metadata": self.metadata
        }


@dataclass
class QueryMetrics:
    """Aggregated metrics for a query"""
    query_id: str
    query_text: str
    impression_count: int
    click_count: int
    ctr: float
    avg_latency_ms: float
    result_count: int
    unique_users: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "impression_count": self.impression_count,
            "click_count": self.click_count,
            "ctr": self.ctr,
            "avg_latency_ms": self.avg_latency_ms,
            "result_count": self.result_count,
            "unique_users": self.unique_users,
            "metadata": self.metadata
        }


class QueryAnalyticsService:
    """
    Service for query analytics and logging

    Provides:
    - Query logging with latency tracking
    - Click event tracking
    - CTR calculation
    - Metric aggregation
    - Analytics reporting
    """

    def __init__(
        self,
        storage,
        config: Optional[AnalyticsConfig] = None
    ):
        """
        Initialize query analytics service

        Args:
            storage: Supabase storage client
            config: Analytics configuration
        """
        self.storage = storage
        self.config = config or AnalyticsConfig()

        logger.info("Initialized QueryAnalyticsService")

    async def log_query(
        self,
        query_text: str,
        latency_ms: float,
        result_count: int,
        user_session_id: str,
        search_type: str = "hybrid",
        metadata: Optional[Dict[str, Any]] = None
    ) -> QueryLog:
        """
        Log a search query with metrics

        Args:
            query_text: The search query text
            latency_ms: Query execution latency in milliseconds
            result_count: Number of results returned
            user_session_id: User session identifier
            search_type: Type of search (hybrid, vector, keyword)
            metadata: Additional metadata to log

        Returns:
            QueryLog instance

        Raises:
            ValueError: If query_text is empty or latency is negative
        """
        # Validation
        if not query_text or query_text.strip() == "":
            raise ValueError("query_text cannot be empty")

        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")

        # Create query log
        query_log = QueryLog(
            query_id=str(uuid4()),
            query_text=query_text,
            user_session_id=user_session_id,
            created_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            result_count=result_count,
            search_type=search_type,
            metadata=metadata or {}
        )

        # Store in Supabase
        if self.config.enable_query_logging:
            try:
                await self._store_query_log(query_log)
                logger.debug(f"Logged query: {query_log.query_id}")
            except Exception as e:
                logger.error(f"Failed to store query log: {e}")
                # Don't fail the query if logging fails

        return query_log

    async def log_click(
        self,
        query_id: str,
        result_id: str,
        result_rank: int,
        user_session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ClickEvent:
        """
        Log a click event on a search result

        Args:
            query_id: Query that led to this result
            result_id: ID of the clicked result
            result_rank: Position/rank of the result (1-indexed)
            user_session_id: User session identifier
            metadata: Additional metadata about the result

        Returns:
            ClickEvent instance

        Raises:
            ValueError: If result_rank is < 1
        """
        # Validation
        if result_rank < 1:
            raise ValueError("result_rank must be >= 1")

        # Create click event
        click_event = ClickEvent(
            click_id=str(uuid4()),
            query_id=query_id,
            result_id=result_id,
            result_rank=result_rank,
            clicked_at=datetime.now(timezone.utc),
            user_session_id=user_session_id,
            metadata=metadata or {}
        )

        # Store in Supabase
        if self.config.enable_click_tracking:
            try:
                await self._store_click_event(click_event)
                logger.debug(f"Logged click: {click_event.click_id}")
            except Exception as e:
                logger.error(f"Failed to store click event: {e}")
                # Don't fail the request if logging fails

        return click_event

    async def calculate_ctr(
        self,
        query_id: str
    ) -> float:
        """
        Calculate click-through rate for a specific query

        Args:
            query_id: Query to calculate CTR for

        Returns:
            CTR as a float (0.0 to 1.0)
        """
        try:
            # Get impression and click counts
            result = await self.storage.table("query_analytics")\
                .select("impression_count, click_count")\
                .eq("query_id", query_id)\
                .execute()

            if not result.data:
                return 0.0

            data = result.data[0]
            impressions = data.get("impression_count", 0)
            clicks = data.get("click_count", 0)

            if impressions == 0:
                return 0.0

            return clicks / impressions

        except Exception as e:
            logger.error(f"Failed to calculate CTR for query {query_id}: {e}")
            return 0.0

    async def calculate_overall_ctr(self) -> float:
        """
        Calculate overall CTR across all queries

        Returns:
            Overall CTR as a float (0.0 to 1.0)
        """
        try:
            # Get all impression and click counts
            result = await self.storage.table("query_analytics")\
                .select("impression_count, click_count")\
                .execute()

            if not result.data:
                return 0.0

            total_impressions = sum(r.get("impression_count", 0) for r in result.data)
            total_clicks = sum(r.get("click_count", 0) for r in result.data)

            if total_impressions == 0:
                return 0.0

            return total_clicks / total_impressions

        except Exception as e:
            logger.error(f"Failed to calculate overall CTR: {e}")
            return 0.0

    async def get_query_metrics(
        self,
        query_id: str
    ) -> Optional[QueryMetrics]:
        """
        Get aggregated metrics for a specific query

        Args:
            query_id: Query to get metrics for

        Returns:
            QueryMetrics instance or None if query not found
        """
        try:
            # Get query log
            query_result = await self.storage.table("query_logs")\
                .select("*")\
                .eq("query_id", query_id)\
                .execute()

            if not query_result.data:
                return None

            query_data = query_result.data[0]

            # Get click events
            click_result = await self.storage.table("click_events")\
                .select("*")\
                .eq("query_id", query_id)\
                .execute()

            click_count = len(click_result.data) if click_result.data else 0

            # Calculate CTR
            ctr = await self.calculate_ctr(query_id)

            # Build metrics
            metrics = QueryMetrics(
                query_id=query_id,
                query_text=query_data.get("query_text", ""),
                impression_count=1,  # Simplified - would aggregate in production
                click_count=click_count,
                ctr=ctr,
                avg_latency_ms=query_data.get("latency_ms", 0.0),
                result_count=query_data.get("result_count", 0),
                unique_users=1,  # Simplified
                metadata=query_data.get("metadata", {})
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to get metrics for query {query_id}: {e}")
            return None

    async def get_popular_queries(
        self,
        limit: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get most popular queries by frequency

        Args:
            limit: Maximum number of queries to return
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of query statistics sorted by frequency
        """
        try:
            # Get query frequency data
            result = await self.storage.table("query_analytics")\
                .select("query_text, count")\
                .execute()

            if not result.data:
                return []

            # Sort by count descending
            sorted_queries = sorted(
                result.data,
                key=lambda x: x.get("count", 0),
                reverse=True
            )

            return sorted_queries[:limit]

        except Exception as e:
            logger.error(f"Failed to get popular queries: {e}")
            return []

    async def get_latency_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Get latency statistics (avg, p50, p95, p99)

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with latency statistics
        """
        try:
            # Call Supabase RPC function for percentile calculation
            result = await self.storage.rpc("get_latency_stats").execute()

            if not result.data or len(result.data) == 0:
                return {
                    "avg_latency": 0.0,
                    "p50_latency": 0.0,
                    "p95_latency": 0.0,
                    "p99_latency": 0.0,
                    "max_latency": 0.0
                }

            return result.data[0]

        except Exception as e:
            logger.error(f"Failed to get latency statistics: {e}")
            return {
                "avg_latency": 0.0,
                "p50_latency": 0.0,
                "p95_latency": 0.0,
                "p99_latency": 0.0,
                "max_latency": 0.0
            }

    async def get_queries_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get all queries within a date range

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of query logs
        """
        try:
            result = await self.storage.table("query_logs")\
                .select("*")\
                .gte("created_at", start_date.isoformat())\
                .lte("created_at", end_date.isoformat())\
                .execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Failed to get queries by date range: {e}")
            return []

    async def _store_query_log(self, query_log: QueryLog) -> None:
        """
        Store query log in Supabase

        Args:
            query_log: QueryLog to store
        """
        data = query_log.to_dict()

        await self.storage.table("query_logs")\
            .insert(data)\
            .execute()

    async def _store_click_event(self, click_event: ClickEvent) -> None:
        """
        Store click event in Supabase

        Args:
            click_event: ClickEvent to store
        """
        data = click_event.to_dict()

        await self.storage.table("click_events")\
            .insert(data)\
            .execute()


# Singleton instance
_query_analytics_service: Optional[QueryAnalyticsService] = None


def get_query_analytics_service(
    storage=None,
    config: Optional[AnalyticsConfig] = None
) -> QueryAnalyticsService:
    """
    Get or create singleton query analytics service instance

    Args:
        storage: Optional Supabase storage client
        config: Optional analytics configuration

    Returns:
        QueryAnalyticsService instance
    """
    global _query_analytics_service

    if _query_analytics_service is None:
        _query_analytics_service = QueryAnalyticsService(
            storage=storage,
            config=config
        )

    return _query_analytics_service
