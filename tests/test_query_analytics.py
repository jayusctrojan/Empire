"""
Tests for Query Analytics and Logging Service

Tests query logging, metric tracking, and CTR calculation:
- Query logging with latency tracking
- Click tracking and position recording
- CTR calculation and aggregation
- Metric retrieval and analysis
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.query_analytics_service import (
    QueryAnalyticsService,
    QueryLog,
    ClickEvent,
    QueryMetrics,
    AnalyticsConfig
)


@pytest.fixture
def mock_storage():
    """Mock Supabase storage"""
    storage = MagicMock()
    # table() returns a chainable mock
    storage.table = MagicMock(return_value=MagicMock())
    # rpc() returns a chainable mock
    storage.rpc = MagicMock(return_value=MagicMock())
    return storage


@pytest.fixture
def analytics_service(mock_storage):
    """Analytics service instance"""
    return QueryAnalyticsService(storage=mock_storage)


@pytest.fixture
def sample_query_log():
    """Sample query log data"""
    return QueryLog(
        query_id=str(uuid4()),
        query_text="California insurance policy",
        user_session_id=str(uuid4()),
        created_at=datetime.now(timezone.utc),
        latency_ms=125.5,
        result_count=10,
        search_type="hybrid",
        metadata={
            "filters_applied": ["department:Legal"],
            "top_k": 10
        }
    )


@pytest.fixture
def sample_click_event():
    """Sample click event data"""
    return ClickEvent(
        click_id=str(uuid4()),
        query_id=str(uuid4()),
        result_id="chunk123",
        result_rank=1,
        clicked_at=datetime.now(timezone.utc),
        user_session_id=str(uuid4()),
        metadata={
            "department": "Legal",
            "file_type": "pdf"
        }
    )


class TestQueryLogging:
    """Test query logging functionality"""

    @pytest.mark.asyncio
    async def test_log_query_basic(self, analytics_service, mock_storage):
        """Test logging a basic query"""
        query_log = await analytics_service.log_query(
            query_text="California insurance",
            latency_ms=100.0,
            result_count=5,
            user_session_id=str(uuid4())
        )

        assert query_log.query_id is not None
        assert query_log.query_text == "California insurance"
        assert query_log.latency_ms == 100.0
        assert query_log.result_count == 5
        assert query_log.created_at is not None

        # Verify storage was called
        mock_storage.table.assert_called()

    @pytest.mark.asyncio
    async def test_log_query_with_metadata(self, analytics_service, mock_storage):
        """Test logging query with additional metadata"""
        metadata = {
            "filters": ["department:Legal"],
            "search_type": "hybrid",
            "top_k": 10
        }

        query_log = await analytics_service.log_query(
            query_text="contract review",
            latency_ms=150.0,
            result_count=8,
            user_session_id=str(uuid4()),
            metadata=metadata
        )

        assert query_log.metadata == metadata
        assert query_log.search_type == "hybrid"

    @pytest.mark.asyncio
    async def test_log_query_timestamps(self, analytics_service, mock_storage):
        """Test query timestamps are recorded correctly"""
        before = datetime.now(timezone.utc)
        query_log = await analytics_service.log_query(
            query_text="test query",
            latency_ms=50.0,
            result_count=3,
            user_session_id=str(uuid4())
        )
        after = datetime.now(timezone.utc)

        assert before <= query_log.created_at <= after

    @pytest.mark.asyncio
    async def test_log_query_generates_unique_ids(self, analytics_service, mock_storage):
        """Test each query gets a unique ID"""
        log1 = await analytics_service.log_query(
            query_text="query 1",
            latency_ms=100.0,
            result_count=5,
            user_session_id=str(uuid4())
        )

        log2 = await analytics_service.log_query(
            query_text="query 2",
            latency_ms=100.0,
            result_count=5,
            user_session_id=str(uuid4())
        )

        assert log1.query_id != log2.query_id


class TestClickTracking:
    """Test click event tracking"""

    @pytest.mark.asyncio
    async def test_log_click_event(self, analytics_service, mock_storage):
        """Test logging a click event"""
        query_id = str(uuid4())

        click_event = await analytics_service.log_click(
            query_id=query_id,
            result_id="chunk123",
            result_rank=1,
            user_session_id=str(uuid4())
        )

        assert click_event.click_id is not None
        assert click_event.query_id == query_id
        assert click_event.result_id == "chunk123"
        assert click_event.result_rank == 1
        assert click_event.clicked_at is not None

        # Verify storage was called
        mock_storage.table.assert_called()

    @pytest.mark.asyncio
    async def test_log_click_with_metadata(self, analytics_service, mock_storage):
        """Test logging click with result metadata"""
        metadata = {
            "department": "Legal",
            "file_type": "pdf",
            "filename": "contract.pdf"
        }

        click_event = await analytics_service.log_click(
            query_id=str(uuid4()),
            result_id="chunk456",
            result_rank=3,
            user_session_id=str(uuid4()),
            metadata=metadata
        )

        assert click_event.metadata == metadata

    @pytest.mark.asyncio
    async def test_log_multiple_clicks_same_query(self, analytics_service, mock_storage):
        """Test logging multiple clicks for same query"""
        query_id = str(uuid4())
        user_session_id = str(uuid4())

        click1 = await analytics_service.log_click(
            query_id=query_id,
            result_id="chunk1",
            result_rank=1,
            user_session_id=user_session_id
        )

        click2 = await analytics_service.log_click(
            query_id=query_id,
            result_id="chunk2",
            result_rank=2,
            user_session_id=user_session_id
        )

        # Should have different click IDs
        assert click1.click_id != click2.click_id
        # But same query ID
        assert click1.query_id == click2.query_id


class TestCTRCalculation:
    """Test click-through rate calculation"""

    @pytest.mark.asyncio
    async def test_calculate_ctr_for_query(self, analytics_service, mock_storage):
        """Test CTR calculation for a specific query"""
        query_id = str(uuid4())

        # Mock: query was shown 10 times, clicked 3 times
        mock_result = MagicMock()
        mock_result.data = [
            {"query_id": query_id, "impression_count": 10, "click_count": 3}
        ]

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        ctr = await analytics_service.calculate_ctr(query_id=query_id)

        assert ctr == 0.3  # 3/10 = 30%

    @pytest.mark.asyncio
    async def test_calculate_ctr_no_clicks(self, analytics_service, mock_storage):
        """Test CTR when query has no clicks"""
        query_id = str(uuid4())

        # Mock: query was shown but never clicked
        mock_result = MagicMock()
        mock_result.data = [
            {"query_id": query_id, "impression_count": 5, "click_count": 0}
        ]

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        ctr = await analytics_service.calculate_ctr(query_id=query_id)

        assert ctr == 0.0

    @pytest.mark.asyncio
    async def test_calculate_ctr_no_impressions(self, analytics_service, mock_storage):
        """Test CTR when query has no impressions"""
        query_id = str(uuid4())

        # Mock: no data for this query
        mock_result = MagicMock()
        mock_result.data = []

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        ctr = await analytics_service.calculate_ctr(query_id=query_id)

        assert ctr == 0.0

    @pytest.mark.asyncio
    async def test_calculate_overall_ctr(self, analytics_service, mock_storage):
        """Test overall CTR across all queries"""
        # Mock: multiple queries with different CTRs
        mock_result = MagicMock()
        mock_result.data = [
            {"impression_count": 10, "click_count": 3},
            {"impression_count": 20, "click_count": 10},
            {"impression_count": 5, "click_count": 1}
        ]

        mock_storage.table.return_value.select.return_value.execute = AsyncMock(return_value=mock_result)

        overall_ctr = await analytics_service.calculate_overall_ctr()

        # Total: 35 impressions, 14 clicks = 0.4
        assert overall_ctr == pytest.approx(0.4, rel=0.01)


class TestMetricRetrieval:
    """Test metric retrieval and aggregation"""

    @pytest.mark.asyncio
    async def test_get_query_metrics(self, analytics_service, mock_storage):
        """Test retrieving metrics for a specific query"""
        query_id = str(uuid4())

        # Mock query log data
        mock_query_result = MagicMock()
        mock_query_result.data = [{
            "query_id": query_id,
            "query_text": "insurance policy",
            "latency_ms": 125.5,
            "result_count": 10,
            "created_at": datetime.now(timezone.utc).isoformat()
        }]

        # Mock click data
        mock_click_result = MagicMock()
        mock_click_result.data = [
            {"result_rank": 1},
            {"result_rank": 3}
        ]

        # Mock CTR result
        mock_ctr_result = MagicMock()
        mock_ctr_result.data = [
            {"query_id": query_id, "impression_count": 1, "click_count": 2}
        ]

        # Use side_effect to return different results for each call
        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
            side_effect=[mock_query_result, mock_click_result, mock_ctr_result]
        )

        metrics = await analytics_service.get_query_metrics(query_id=query_id)

        assert isinstance(metrics, QueryMetrics)
        assert metrics.query_id == query_id
        assert metrics.query_text == "insurance policy"
        assert metrics.avg_latency_ms == 125.5
        assert metrics.click_count == 2
        assert metrics.ctr > 0

    @pytest.mark.asyncio
    async def test_get_popular_queries(self, analytics_service, mock_storage):
        """Test retrieving most popular queries"""
        # Mock query frequency data
        mock_result = MagicMock()
        mock_result.data = [
            {"query_text": "insurance", "count": 50},
            {"query_text": "contract", "count": 30},
            {"query_text": "policy", "count": 20}
        ]

        mock_storage.table.return_value.select.return_value.execute = AsyncMock(return_value=mock_result)

        popular = await analytics_service.get_popular_queries(limit=3)

        assert len(popular) == 3
        assert popular[0]["query_text"] == "insurance"
        assert popular[0]["count"] == 50

    @pytest.mark.asyncio
    async def test_get_latency_statistics(self, analytics_service, mock_storage):
        """Test retrieving latency statistics"""
        # Mock latency data
        mock_result = MagicMock()
        mock_result.data = [{
            "avg_latency": 150.0,
            "p50_latency": 125.0,
            "p95_latency": 250.0,
            "p99_latency": 400.0,
            "max_latency": 500.0
        }]

        mock_storage.rpc.return_value.execute = AsyncMock(return_value=mock_result)

        stats = await analytics_service.get_latency_statistics()

        assert stats["avg_latency"] == 150.0
        assert stats["p50_latency"] == 125.0
        assert stats["p95_latency"] == 250.0
        assert stats["p99_latency"] == 400.0

    @pytest.mark.asyncio
    async def test_get_queries_by_date_range(self, analytics_service, mock_storage):
        """Test retrieving queries within a date range"""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        # Mock query data
        mock_result = MagicMock()
        mock_result.data = [
            {"query_id": str(uuid4()), "query_text": "test1"},
            {"query_id": str(uuid4()), "query_text": "test2"}
        ]

        mock_storage.table.return_value.select.return_value.gte.return_value.lte.return_value.execute = AsyncMock(return_value=mock_result)

        queries = await analytics_service.get_queries_by_date_range(
            start_date=start_date,
            end_date=end_date
        )

        assert len(queries) == 2


class TestAnalyticsConfig:
    """Test analytics configuration"""

    def test_default_config(self):
        """Test default analytics configuration"""
        config = AnalyticsConfig()

        assert config.enable_query_logging is True
        assert config.enable_click_tracking is True
        assert config.log_latency is True
        assert config.retention_days > 0

    def test_custom_config(self):
        """Test custom analytics configuration"""
        config = AnalyticsConfig(
            enable_query_logging=True,
            enable_click_tracking=False,
            retention_days=90
        )

        assert config.enable_query_logging is True
        assert config.enable_click_tracking is False
        assert config.retention_days == 90


class TestDataModels:
    """Test data model validation"""

    def test_query_log_model(self, sample_query_log):
        """Test QueryLog data model"""
        assert sample_query_log.query_id is not None
        assert sample_query_log.query_text is not None
        assert sample_query_log.latency_ms >= 0
        assert sample_query_log.result_count >= 0

    def test_query_log_to_dict(self, sample_query_log):
        """Test QueryLog serialization"""
        log_dict = sample_query_log.to_dict()

        assert "query_id" in log_dict
        assert "query_text" in log_dict
        assert "latency_ms" in log_dict
        assert "created_at" in log_dict

    def test_click_event_model(self, sample_click_event):
        """Test ClickEvent data model"""
        assert sample_click_event.click_id is not None
        assert sample_click_event.query_id is not None
        assert sample_click_event.result_id is not None
        assert sample_click_event.result_rank > 0

    def test_click_event_to_dict(self, sample_click_event):
        """Test ClickEvent serialization"""
        click_dict = sample_click_event.to_dict()

        assert "click_id" in click_dict
        assert "query_id" in click_dict
        assert "result_id" in click_dict
        assert "result_rank" in click_dict


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_log_query_empty_text(self, analytics_service):
        """Test logging query with empty text"""
        with pytest.raises(ValueError):
            await analytics_service.log_query(
                query_text="",
                latency_ms=100.0,
                result_count=0,
                user_session_id=str(uuid4())
            )

    @pytest.mark.asyncio
    async def test_log_query_negative_latency(self, analytics_service):
        """Test logging query with negative latency"""
        with pytest.raises(ValueError):
            await analytics_service.log_query(
                query_text="test",
                latency_ms=-10.0,
                result_count=5,
                user_session_id=str(uuid4())
            )

    @pytest.mark.asyncio
    async def test_log_click_invalid_rank(self, analytics_service):
        """Test logging click with invalid rank"""
        with pytest.raises(ValueError):
            await analytics_service.log_click(
                query_id=str(uuid4()),
                result_id="chunk123",
                result_rank=0,  # Rank must be >= 1
                user_session_id=str(uuid4())
            )

    @pytest.mark.asyncio
    async def test_get_metrics_nonexistent_query(self, analytics_service, mock_storage):
        """Test getting metrics for non-existent query"""
        mock_result = MagicMock()
        mock_result.data = []

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        metrics = await analytics_service.get_query_metrics(
            query_id=str(uuid4())
        )

        assert metrics is None
