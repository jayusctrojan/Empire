"""
Analytics Dashboard Service

Provides dashboard data aggregation and visualization for query analytics.

Features:
- Query volume metrics and time-series data
- Latency statistics and distribution
- CTR aggregation and trends
- Filtering by date range, search type, and department
- Widget configuration and layout management

Usage:
    from app.services.analytics_dashboard_service import get_analytics_dashboard_service

    service = get_analytics_dashboard_service()

    # Get comprehensive dashboard metrics
    metrics = await service.get_dashboard_metrics(
        start_date=start_date,
        end_date=end_date
    )

    # Get time-series data
    time_series = await service.get_query_volume_time_series(
        start_date=start_date,
        end_date=end_date,
        interval="1d"
    )
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from collections import defaultdict

from app.services.query_analytics_service import QueryAnalyticsService, get_query_analytics_service

logger = logging.getLogger(__name__)


class WidgetType(Enum):
    """Available widget types for dashboard"""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    METRIC_CARD = "metric_card"
    TABLE = "table"
    HEATMAP = "heatmap"


@dataclass
class DashboardConfig:
    """Configuration for analytics dashboard"""
    refresh_interval: int = 60  # seconds
    default_date_range_days: int = 7
    enable_real_time_updates: bool = True
    max_time_series_points: int = 100

    # Widget settings
    default_chart_height: int = 300
    default_chart_width: int = 600


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget"""
    widget_type: WidgetType
    title: str
    data_source: str
    refresh_interval: int = 60
    position: Dict[str, int] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "widget_type": self.widget_type.value,
            "title": self.title,
            "data_source": self.data_source,
            "refresh_interval": self.refresh_interval,
            "position": self.position,
            "config": self.config
        }


@dataclass
class TimeSeriesData:
    """Time-series data for charts"""
    timestamps: List[datetime]
    values: List[float]
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamps": [t.isoformat() for t in self.timestamps],
            "values": self.values,
            "label": self.label,
            "metadata": self.metadata
        }


@dataclass
class DashboardMetrics:
    """Comprehensive dashboard metrics"""
    query_volume: Dict[str, Any]
    latency_stats: Dict[str, Any]
    ctr_stats: Dict[str, Any]
    time_range_start: datetime
    time_range_end: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query_volume": self.query_volume,
            "latency_stats": self.latency_stats,
            "ctr_stats": self.ctr_stats,
            "time_range_start": self.time_range_start.isoformat(),
            "time_range_end": self.time_range_end.isoformat(),
            "metadata": self.metadata
        }


class AnalyticsDashboardService:
    """
    Service for analytics dashboard data aggregation

    Provides:
    - Query volume metrics and time-series
    - Latency statistics and distribution
    - CTR aggregation and trends
    - Filtering capabilities
    - Widget configuration
    """

    def __init__(
        self,
        storage,
        analytics_service: Optional[QueryAnalyticsService] = None,
        config: Optional[DashboardConfig] = None
    ):
        """
        Initialize analytics dashboard service

        Args:
            storage: Supabase storage client
            analytics_service: Query analytics service
            config: Dashboard configuration
        """
        self.storage = storage
        self.analytics_service = analytics_service or get_query_analytics_service()
        self.config = config or DashboardConfig()

        logger.info("Initialized AnalyticsDashboardService")

    async def get_query_volume_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_type: Optional[str] = None,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get query volume metrics

        Args:
            start_date: Start of date range
            end_date: End of date range
            search_type: Filter by search type
            department: Filter by department

        Returns:
            Dictionary with query volume metrics
        """
        # Default date range
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=self.config.default_date_range_days)

        # Validate date range
        if end_date < start_date:
            raise ValueError("end_date must be after start_date")

        # Get queries
        if search_type or department:
            # Use storage for filtered queries
            queries = await self._get_filtered_queries(
                start_date=start_date,
                end_date=end_date,
                search_type=search_type,
                department=department
            )
        else:
            # Use analytics service
            queries = await self.analytics_service.get_queries_by_date_range(
                start_date=start_date,
                end_date=end_date
            )

        total_queries = len(queries)
        days = max(1, (end_date - start_date).days)
        avg_queries_per_day = total_queries / days if days > 0 else 0

        # Generate time series data
        time_series = self._aggregate_by_time(queries, start_date, end_date)

        return {
            "total_queries": total_queries,
            "avg_queries_per_day": avg_queries_per_day,
            "time_series": time_series,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }

    async def get_latency_metrics(self) -> Dict[str, Any]:
        """
        Get latency metrics

        Returns:
            Dictionary with latency statistics
        """
        stats = await self.analytics_service.get_latency_statistics()

        # Return defaults if stats are empty
        if not stats:
            return {
                "avg_latency": 0.0,
                "p50_latency": 0.0,
                "p95_latency": 0.0,
                "p99_latency": 0.0,
                "max_latency": 0.0
            }

        return stats

    async def get_ctr_metrics(self) -> Dict[str, Any]:
        """
        Get CTR metrics

        Returns:
            Dictionary with CTR statistics
        """
        overall_ctr = await self.analytics_service.calculate_overall_ctr()
        popular_queries = await self.analytics_service.get_popular_queries(limit=10)

        return {
            "overall_ctr": overall_ctr,
            "top_queries_by_ctr": popular_queries
        }

    async def get_dashboard_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_type: Optional[str] = None,
        department: Optional[str] = None
    ) -> DashboardMetrics:
        """
        Get comprehensive dashboard metrics

        Args:
            start_date: Start of date range
            end_date: End of date range
            search_type: Filter by search type
            department: Filter by department

        Returns:
            DashboardMetrics with all metrics
        """
        # Default date range
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=self.config.default_date_range_days)

        # Get all metrics
        query_volume = await self.get_query_volume_metrics(
            start_date=start_date,
            end_date=end_date,
            search_type=search_type,
            department=department
        )

        latency_stats = await self.get_latency_metrics()
        ctr_stats = await self.get_ctr_metrics()

        return DashboardMetrics(
            query_volume=query_volume,
            latency_stats=latency_stats,
            ctr_stats=ctr_stats,
            time_range_start=start_date,
            time_range_end=end_date
        )

    async def get_query_volume_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> TimeSeriesData:
        """
        Get time-series data for query volume

        Args:
            start_date: Start of date range
            end_date: End of date range
            interval: Time interval (1h, 1d, 1w)

        Returns:
            TimeSeriesData for query volume
        """
        queries = await self.analytics_service.get_queries_by_date_range(
            start_date=start_date,
            end_date=end_date
        )

        # Parse interval
        interval_delta = self._parse_interval(interval)

        # Aggregate queries by interval
        aggregated = defaultdict(int)
        current = start_date

        # Create buckets
        timestamps = []
        while current <= end_date:
            timestamps.append(current)
            current += interval_delta

        # Count queries per bucket
        for query in queries:
            query_time = datetime.fromisoformat(query["created_at"].replace("Z", "+00:00"))

            # Find the bucket for this query
            for i, ts in enumerate(timestamps):
                next_ts = timestamps[i + 1] if i + 1 < len(timestamps) else end_date + interval_delta
                if ts <= query_time < next_ts:
                    aggregated[ts] += 1
                    break

        # Build values list
        values = [aggregated.get(ts, 0) for ts in timestamps]

        return TimeSeriesData(
            timestamps=timestamps,
            values=values,
            label="Query Volume"
        )

    async def get_latency_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> TimeSeriesData:
        """
        Get time-series data for latency

        Args:
            start_date: Start of date range
            end_date: End of date range
            interval: Time interval

        Returns:
            TimeSeriesData for latency
        """
        # Query aggregated latency data from storage
        mock_result = await self.storage.table("query_logs_aggregated")\
            .select("date, avg_latency")\
            .gte("date", start_date.isoformat())\
            .lte("date", end_date.isoformat())\
            .execute()

        if not mock_result.data:
            return TimeSeriesData(timestamps=[], values=[], label="Latency")

        timestamps = [datetime.fromisoformat(r["date"]) for r in mock_result.data]
        values = [r["avg_latency"] for r in mock_result.data]

        return TimeSeriesData(
            timestamps=timestamps,
            values=values,
            label="Average Latency (ms)"
        )

    async def get_ctr_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d"
    ) -> TimeSeriesData:
        """
        Get time-series data for CTR

        Args:
            start_date: Start of date range
            end_date: End of date range
            interval: Time interval

        Returns:
            TimeSeriesData for CTR
        """
        # Query aggregated CTR data from storage
        mock_result = await self.storage.table("ctr_aggregated")\
            .select("date, ctr")\
            .gte("date", start_date.isoformat())\
            .lte("date", end_date.isoformat())\
            .execute()

        if not mock_result.data:
            return TimeSeriesData(timestamps=[], values=[], label="CTR")

        timestamps = [datetime.fromisoformat(r["date"]) for r in mock_result.data]
        values = [r["ctr"] for r in mock_result.data]

        return TimeSeriesData(
            timestamps=timestamps,
            values=values,
            label="Click-Through Rate"
        )

    def get_default_layout(self) -> List[WidgetConfig]:
        """
        Get default dashboard layout

        Returns:
            List of widget configurations
        """
        return [
            WidgetConfig(
                widget_type=WidgetType.METRIC_CARD,
                title="Total Queries",
                data_source="query_volume",
                position={"row": 0, "col": 0}
            ),
            WidgetConfig(
                widget_type=WidgetType.METRIC_CARD,
                title="Average Latency",
                data_source="latency_stats",
                position={"row": 0, "col": 1}
            ),
            WidgetConfig(
                widget_type=WidgetType.METRIC_CARD,
                title="Overall CTR",
                data_source="ctr_stats",
                position={"row": 0, "col": 2}
            ),
            WidgetConfig(
                widget_type=WidgetType.LINE_CHART,
                title="Query Volume Over Time",
                data_source="query_volume_time_series",
                position={"row": 1, "col": 0}
            ),
            WidgetConfig(
                widget_type=WidgetType.LINE_CHART,
                title="Latency Trends",
                data_source="latency_time_series",
                position={"row": 1, "col": 1}
            ),
            WidgetConfig(
                widget_type=WidgetType.LINE_CHART,
                title="CTR Trends",
                data_source="ctr_time_series",
                position={"row": 1, "col": 2}
            )
        ]

    async def _get_filtered_queries(
        self,
        start_date: datetime,
        end_date: datetime,
        search_type: Optional[str] = None,
        department: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get filtered queries from storage

        Args:
            start_date: Start of date range
            end_date: End of date range
            search_type: Filter by search type
            department: Filter by department

        Returns:
            List of query records
        """
        query = self.storage.table("query_logs").select("*")

        if search_type:
            query = query.eq("search_type", search_type)

        if department:
            query = query.eq("department", department)

        if start_date:
            query = query.gte("created_at", start_date.isoformat())

        if end_date:
            query = query.lte("created_at", end_date.isoformat())

        result = await query.execute()
        return result.data if result.data else []

    def _aggregate_by_time(
        self,
        queries: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Aggregate queries by time buckets

        Args:
            queries: List of query records
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of time-series data points
        """
        # Simple daily aggregation
        daily_counts = defaultdict(int)

        for query in queries:
            if "created_at" in query:
                created_at = datetime.fromisoformat(query["created_at"].replace("Z", "+00:00"))
                date_key = created_at.date().isoformat()
                daily_counts[date_key] += 1

        # Build time series
        time_series = []
        current = start_date.date()
        end = end_date.date()

        while current <= end:
            date_key = current.isoformat()
            time_series.append({
                "date": date_key,
                "count": daily_counts.get(date_key, 0)
            })
            current += timedelta(days=1)

        return time_series

    def _parse_interval(self, interval: str) -> timedelta:
        """
        Parse interval string to timedelta

        Args:
            interval: Interval string (1h, 1d, 1w)

        Returns:
            timedelta object
        """
        if interval == "1h":
            return timedelta(hours=1)
        elif interval == "1d":
            return timedelta(days=1)
        elif interval == "1w":
            return timedelta(weeks=1)
        else:
            return timedelta(days=1)  # Default to 1 day


# Singleton instance
_analytics_dashboard_service: Optional[AnalyticsDashboardService] = None


def get_analytics_dashboard_service(
    storage=None,
    analytics_service: Optional[QueryAnalyticsService] = None,
    config: Optional[DashboardConfig] = None
) -> AnalyticsDashboardService:
    """
    Get or create singleton analytics dashboard service instance

    Args:
        storage: Optional Supabase storage client
        analytics_service: Optional query analytics service
        config: Optional dashboard configuration

    Returns:
        AnalyticsDashboardService instance
    """
    global _analytics_dashboard_service

    if _analytics_dashboard_service is None:
        _analytics_dashboard_service = AnalyticsDashboardService(
            storage=storage,
            analytics_service=analytics_service,
            config=config
        )

    return _analytics_dashboard_service
