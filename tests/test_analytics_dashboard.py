"""
Tests for Analytics Dashboard Service

Tests dashboard data aggregation and visualization:
- Query volume metrics and time-series data
- Latency statistics and distribution
- CTR aggregation and trends
- Filtering by date range and algorithm version
- Dashboard widget configuration
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.analytics_dashboard_service import (
    AnalyticsDashboardService,
    DashboardConfig,
    DashboardMetrics,
    TimeSeriesData,
    WidgetConfig,
    WidgetType
)


@pytest.fixture
def mock_analytics_service():
    """Mock query analytics service"""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_storage():
    """Mock Supabase storage"""
    storage = MagicMock()
    storage.table = MagicMock(return_value=MagicMock())
    return storage


@pytest.fixture
def dashboard_service(mock_storage, mock_analytics_service):
    """Dashboard service instance"""
    return AnalyticsDashboardService(
        storage=mock_storage,
        analytics_service=mock_analytics_service
    )


class TestDashboardMetrics:
    """Test dashboard metrics aggregation"""

    @pytest.mark.asyncio
    async def test_get_query_volume_metrics(self, dashboard_service, mock_analytics_service):
        """Test retrieving query volume metrics"""
        # Mock query data
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        mock_analytics_service.get_queries_by_date_range.return_value = [
            {"query_id": str(uuid4()), "created_at": (start_date + timedelta(days=i)).isoformat()}
            for i in range(7)
        ]

        metrics = await dashboard_service.get_query_volume_metrics(
            start_date=start_date,
            end_date=end_date
        )

        assert metrics["total_queries"] == 7
        assert metrics["avg_queries_per_day"] > 0
        assert "time_series" in metrics

    @pytest.mark.asyncio
    async def test_get_latency_metrics(self, dashboard_service, mock_analytics_service):
        """Test retrieving latency metrics"""
        # Mock latency stats
        mock_analytics_service.get_latency_statistics.return_value = {
            "avg_latency": 150.0,
            "p50_latency": 125.0,
            "p95_latency": 250.0,
            "p99_latency": 400.0,
            "max_latency": 500.0
        }

        metrics = await dashboard_service.get_latency_metrics()

        assert metrics["avg_latency"] == 150.0
        assert metrics["p50_latency"] == 125.0
        assert metrics["p95_latency"] == 250.0
        assert metrics["p99_latency"] == 400.0

    @pytest.mark.asyncio
    async def test_get_ctr_metrics(self, dashboard_service, mock_analytics_service):
        """Test retrieving CTR metrics"""
        # Mock CTR data
        mock_analytics_service.calculate_overall_ctr.return_value = 0.35

        # Mock popular queries with CTR
        mock_analytics_service.get_popular_queries.return_value = [
            {"query_text": "insurance", "count": 50, "ctr": 0.4},
            {"query_text": "contract", "count": 30, "ctr": 0.3},
        ]

        metrics = await dashboard_service.get_ctr_metrics()

        assert metrics["overall_ctr"] == 0.35
        assert len(metrics["top_queries_by_ctr"]) == 2

    @pytest.mark.asyncio
    async def test_get_comprehensive_metrics(self, dashboard_service):
        """Test getting all dashboard metrics at once"""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        metrics = await dashboard_service.get_dashboard_metrics(
            start_date=start_date,
            end_date=end_date
        )

        assert isinstance(metrics, DashboardMetrics)
        assert metrics.query_volume is not None
        assert metrics.latency_stats is not None
        assert metrics.ctr_stats is not None
        assert metrics.time_range_start == start_date
        assert metrics.time_range_end == end_date


class TestTimeSeriesData:
    """Test time-series data generation"""

    @pytest.mark.asyncio
    async def test_generate_query_volume_time_series(self, dashboard_service, mock_analytics_service):
        """Test generating time-series data for query volume"""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Mock queries spread across 7 days - use Z suffix for timezone
        mock_analytics_service.get_queries_by_date_range.return_value = [
            {"query_id": str(uuid4()), "created_at": (start_date + timedelta(days=i % 7)).isoformat().replace("+00:00", "Z")}
            for i in range(70)  # 10 queries per day
        ]

        time_series = await dashboard_service.get_query_volume_time_series(
            start_date=start_date,
            end_date=end_date,
            interval="1d"  # 1 day intervals
        )

        assert isinstance(time_series, TimeSeriesData)
        assert len(time_series.timestamps) == 8  # 7 days ago + today = 8 timestamps
        assert len(time_series.values) == 8
        # First 7 buckets have 10 queries each, last bucket has 0
        assert sum(time_series.values) == 70

    @pytest.mark.asyncio
    async def test_generate_latency_time_series(self, dashboard_service, mock_storage):
        """Test generating time-series data for latency"""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Mock latency data
        mock_result = MagicMock()
        mock_result.data = [
            {
                "date": (start_date + timedelta(days=i)).isoformat(),
                "avg_latency": 100 + (i * 10)
            }
            for i in range(7)
        ]

        mock_storage.table.return_value.select.return_value.gte.return_value.lte.return_value.execute = AsyncMock(return_value=mock_result)

        time_series = await dashboard_service.get_latency_time_series(
            start_date=start_date,
            end_date=end_date,
            interval="1d"
        )

        assert isinstance(time_series, TimeSeriesData)
        assert len(time_series.timestamps) == 7
        assert time_series.values[0] == 100
        assert time_series.values[6] == 160

    @pytest.mark.asyncio
    async def test_generate_ctr_time_series(self, dashboard_service, mock_storage):
        """Test generating time-series data for CTR"""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Mock CTR data over time
        mock_result = MagicMock()
        mock_result.data = [
            {
                "date": (start_date + timedelta(days=i)).isoformat(),
                "ctr": 0.3 + (i * 0.01)
            }
            for i in range(7)
        ]

        mock_storage.table.return_value.select.return_value.gte.return_value.lte.return_value.execute = AsyncMock(return_value=mock_result)

        time_series = await dashboard_service.get_ctr_time_series(
            start_date=start_date,
            end_date=end_date,
            interval="1d"
        )

        assert isinstance(time_series, TimeSeriesData)
        assert len(time_series.timestamps) == 7
        assert time_series.values[0] == pytest.approx(0.3)
        assert time_series.values[6] == pytest.approx(0.36)


class TestFiltering:
    """Test dashboard filtering capabilities"""

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, dashboard_service, mock_analytics_service):
        """Test filtering metrics by date range"""
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc) - timedelta(days=7)

        mock_analytics_service.get_queries_by_date_range.return_value = [
            {"query_id": str(uuid4()), "created_at": (start_date + timedelta(days=i)).isoformat()}
            for i in range(23)  # 23 days of data
        ]

        metrics = await dashboard_service.get_query_volume_metrics(
            start_date=start_date,
            end_date=end_date
        )

        # Verify date range was applied
        mock_analytics_service.get_queries_by_date_range.assert_called_with(
            start_date=start_date,
            end_date=end_date
        )
        assert metrics["total_queries"] == 23

    @pytest.mark.asyncio
    async def test_filter_by_search_type(self, dashboard_service, mock_storage):
        """Test filtering metrics by search type (algorithm version)"""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Mock filtered query data
        mock_result = MagicMock()
        mock_result.data = [
            {"query_id": str(uuid4()), "search_type": "hybrid"}
            for _ in range(10)
        ]

        mock_storage.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute = AsyncMock(return_value=mock_result)

        metrics = await dashboard_service.get_query_volume_metrics(
            start_date=start_date,
            end_date=end_date,
            search_type="hybrid"
        )

        assert metrics["total_queries"] == 10

    @pytest.mark.asyncio
    async def test_filter_by_department(self, dashboard_service, mock_storage):
        """Test filtering metrics by department"""
        # Mock queries filtered by department
        mock_result = MagicMock()
        mock_result.data = [
            {"query_id": str(uuid4()), "department": "Legal", "created_at": datetime.now(timezone.utc).isoformat()}
            for _ in range(5)
        ]

        # Need to mock the full chain: table().select().eq().gte().lte().execute()
        mock_storage.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute = AsyncMock(return_value=mock_result)

        metrics = await dashboard_service.get_query_volume_metrics(
            department="Legal"
        )

        assert metrics["total_queries"] == 5


class TestWidgetConfiguration:
    """Test dashboard widget configuration"""

    def test_create_widget_config(self):
        """Test creating widget configuration"""
        widget = WidgetConfig(
            widget_type=WidgetType.LINE_CHART,
            title="Query Volume Over Time",
            data_source="query_volume_time_series",
            refresh_interval=60
        )

        assert widget.widget_type == WidgetType.LINE_CHART
        assert widget.title == "Query Volume Over Time"
        assert widget.refresh_interval == 60

    def test_dashboard_layout_config(self, dashboard_service):
        """Test dashboard layout configuration"""
        layout = dashboard_service.get_default_layout()

        assert isinstance(layout, list)
        assert len(layout) > 0
        assert all(isinstance(w, WidgetConfig) for w in layout)

    def test_widget_data_binding(self, dashboard_service):
        """Test widget data source binding"""
        widgets = dashboard_service.get_default_layout()

        # Check that widgets have proper data sources
        data_sources = {w.data_source for w in widgets}
        assert "query_volume" in data_sources
        assert "latency_stats" in data_sources
        assert "ctr_stats" in data_sources


class TestDashboardConfig:
    """Test dashboard configuration"""

    def test_default_config(self):
        """Test default dashboard configuration"""
        config = DashboardConfig()

        assert config.refresh_interval > 0
        assert config.default_date_range_days > 0
        assert config.enable_real_time_updates is True

    def test_custom_config(self):
        """Test custom dashboard configuration"""
        config = DashboardConfig(
            refresh_interval=30,
            default_date_range_days=14,
            enable_real_time_updates=False
        )

        assert config.refresh_interval == 30
        assert config.default_date_range_days == 14
        assert config.enable_real_time_updates is False


class TestDataModels:
    """Test dashboard data models"""

    def test_dashboard_metrics_model(self):
        """Test DashboardMetrics data model"""
        metrics = DashboardMetrics(
            query_volume={"total": 100},
            latency_stats={"avg": 150.0},
            ctr_stats={"overall": 0.35},
            time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
            time_range_end=datetime.now(timezone.utc)
        )

        assert metrics.query_volume["total"] == 100
        assert metrics.latency_stats["avg"] == 150.0
        assert metrics.ctr_stats["overall"] == 0.35

    def test_dashboard_metrics_to_dict(self):
        """Test DashboardMetrics serialization"""
        metrics = DashboardMetrics(
            query_volume={"total": 100},
            latency_stats={"avg": 150.0},
            ctr_stats={"overall": 0.35},
            time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
            time_range_end=datetime.now(timezone.utc)
        )

        metrics_dict = metrics.to_dict()

        assert "query_volume" in metrics_dict
        assert "latency_stats" in metrics_dict
        assert "ctr_stats" in metrics_dict
        assert "time_range_start" in metrics_dict
        assert "time_range_end" in metrics_dict

    def test_time_series_data_model(self):
        """Test TimeSeriesData data model"""
        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(hours=i) for i in range(5)]
        values = [10, 15, 20, 18, 22]

        time_series = TimeSeriesData(
            timestamps=timestamps,
            values=values,
            label="Query Volume"
        )

        assert len(time_series.timestamps) == 5
        assert len(time_series.values) == 5
        assert time_series.label == "Query Volume"

    def test_time_series_to_dict(self):
        """Test TimeSeriesData serialization"""
        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(hours=i) for i in range(3)]
        values = [10, 15, 20]

        time_series = TimeSeriesData(
            timestamps=timestamps,
            values=values,
            label="Test Series"
        )

        series_dict = time_series.to_dict()

        assert "timestamps" in series_dict
        assert "values" in series_dict
        assert "label" in series_dict
        assert len(series_dict["timestamps"]) == 3


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_date_range(self, dashboard_service, mock_analytics_service):
        """Test handling empty date range"""
        start_date = datetime.now(timezone.utc)
        end_date = datetime.now(timezone.utc)

        mock_analytics_service.get_queries_by_date_range.return_value = []

        metrics = await dashboard_service.get_query_volume_metrics(
            start_date=start_date,
            end_date=end_date
        )

        assert metrics["total_queries"] == 0
        assert metrics["avg_queries_per_day"] == 0

    @pytest.mark.asyncio
    async def test_invalid_date_range(self, dashboard_service):
        """Test handling invalid date range (end before start)"""
        start_date = datetime.now(timezone.utc)
        end_date = datetime.now(timezone.utc) - timedelta(days=7)

        with pytest.raises(ValueError):
            await dashboard_service.get_query_volume_metrics(
                start_date=start_date,
                end_date=end_date
            )

    @pytest.mark.asyncio
    async def test_missing_data_graceful_handling(self, dashboard_service, mock_analytics_service):
        """Test graceful handling of missing data"""
        mock_analytics_service.get_latency_statistics.return_value = {}

        metrics = await dashboard_service.get_latency_metrics()

        # Should return defaults or empty values
        assert metrics is not None
