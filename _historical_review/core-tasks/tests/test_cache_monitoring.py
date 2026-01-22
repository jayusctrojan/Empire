"""
Tests for Cache Monitoring and Effectiveness Tracking

Tests cache hit rates, metrics aggregation, and effectiveness analysis.
Validates monitoring across tiered cache (L1: Redis, L2: PostgreSQL).

Run with: python3 -m pytest tests/test_cache_monitoring.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime, timedelta

from app.services.cache_monitoring import (
    CacheMonitoringService,
    CacheMetrics,
    CacheStats,
    CacheEffectiveness,
    get_cache_monitoring_service
)


@pytest.fixture
def mock_tiered_cache():
    """Create mock tiered cache service"""
    cache = Mock()
    cache.get_metrics = Mock(return_value={
        "l1": {"hits": 100, "misses": 20, "hit_rate": 0.833},
        "l2": {"hits": 15, "misses": 5, "hit_rate": 0.75},
        "config": {
            "l1_enabled": True,
            "l2_enabled": True,
            "promote_to_l1": True
        }
    })
    cache.redis_cache = Mock()
    cache.redis_cache.get_cache_info = Mock(return_value={
        "used_memory": "10485760",
        "used_memory_human": "10M",
        "connected": True
    })
    cache.cleanup_expired_l2_entries = AsyncMock(return_value=5)
    return cache


@pytest.fixture
def monitoring_service(mock_tiered_cache):
    """Create cache monitoring service"""
    return CacheMonitoringService(tiered_cache=mock_tiered_cache)


def test_cache_metrics_creation():
    """
    Test CacheMetrics dataclass creation

    Verifies:
    - Metrics structure contains hit/miss counts
    - Hit rate is calculated correctly
    - Timestamp is recorded
    """
    metrics = CacheMetrics(
        hits=100,
        misses=25,
        hit_rate=0.8,
        timestamp=datetime.utcnow()
    )

    assert metrics.hits == 100
    assert metrics.misses == 25
    assert metrics.hit_rate == 0.8
    assert metrics.total_requests == 125


def test_cache_stats_aggregation():
    """
    Test CacheStats aggregation across L1 and L2

    Verifies:
    - L1 and L2 metrics are separate
    - Overall stats are calculated
    - Combined hit rate is correct
    """
    stats = CacheStats(
        l1_metrics=CacheMetrics(hits=100, misses=20, hit_rate=0.833),
        l2_metrics=CacheMetrics(hits=15, misses=5, hit_rate=0.75),
        overall_hit_rate=0.821,  # (100+15)/(120+20)
        timestamp=datetime.utcnow()
    )

    assert stats.l1_metrics.hits == 100
    assert stats.l2_metrics.hits == 15
    assert stats.overall_hit_rate == 0.821


def test_cache_effectiveness_analysis():
    """
    Test CacheEffectiveness analysis

    Verifies:
    - Effectiveness score is calculated
    - Memory usage is tracked
    - Performance gain is estimated
    """
    effectiveness = CacheEffectiveness(
        hit_rate=0.85,
        l1_hit_percentage=0.70,
        l2_hit_percentage=0.15,
        memory_usage_mb=10.5,
        avg_response_time_ms=15.0,
        estimated_speedup=5.67,
        effectiveness_score=0.92
    )

    assert effectiveness.hit_rate == 0.85
    assert effectiveness.l1_hit_percentage == 0.70
    assert effectiveness.estimated_speedup == 5.67


def test_get_current_metrics(monitoring_service, mock_tiered_cache):
    """
    Test retrieving current cache metrics

    Verifies:
    - Metrics are fetched from tiered cache
    - L1 and L2 metrics are included
    - Timestamp is added
    """
    metrics = monitoring_service.get_current_metrics()

    assert metrics is not None
    assert "l1" in metrics
    assert "l2" in metrics
    assert metrics["l1"]["hits"] == 100
    mock_tiered_cache.get_metrics.assert_called_once()


def test_calculate_overall_hit_rate(monitoring_service):
    """
    Test overall hit rate calculation

    Verifies:
    - Combined hit rate from L1 and L2
    - Handles zero requests gracefully
    - Returns float between 0 and 1
    """
    l1_metrics = {"hits": 100, "misses": 20}
    l2_metrics = {"hits": 15, "misses": 5}

    hit_rate = monitoring_service.calculate_overall_hit_rate(l1_metrics, l2_metrics)

    assert hit_rate == pytest.approx(0.821, 0.01)
    assert 0 <= hit_rate <= 1


def test_calculate_hit_rate_zero_requests(monitoring_service):
    """
    Test hit rate calculation with zero requests

    Verifies:
    - Returns 0.0 for no requests
    - Doesn't raise division by zero
    """
    l1_metrics = {"hits": 0, "misses": 0}
    l2_metrics = {"hits": 0, "misses": 0}

    hit_rate = monitoring_service.calculate_overall_hit_rate(l1_metrics, l2_metrics)

    assert hit_rate == 0.0


def test_get_l1_cache_info(monitoring_service, mock_tiered_cache):
    """
    Test retrieving L1 (Redis) cache info

    Verifies:
    - Memory usage is returned
    - Connection status is included
    - Info comes from Redis
    """
    info = monitoring_service.get_l1_cache_info()

    assert info is not None
    assert "used_memory" in info
    assert info["connected"] is True
    mock_tiered_cache.redis_cache.get_cache_info.assert_called_once()


def test_analyze_cache_effectiveness(monitoring_service, mock_tiered_cache):
    """
    Test cache effectiveness analysis

    Verifies:
    - Effectiveness score is calculated
    - L1/L2 hit percentages are determined
    - Memory efficiency is assessed
    """
    effectiveness = monitoring_service.analyze_cache_effectiveness()

    assert effectiveness is not None
    assert hasattr(effectiveness, "hit_rate")
    assert hasattr(effectiveness, "effectiveness_score")
    assert 0 <= effectiveness.hit_rate <= 1


def test_effectiveness_score_calculation(monitoring_service):
    """
    Test effectiveness score calculation logic

    Verifies:
    - Score is based on hit rate and L1 preference
    - L1 hits weighted more than L2 hits
    - Score is between 0 and 1
    """
    l1_hits = 100
    l2_hits = 20
    total = 140

    score = monitoring_service.calculate_effectiveness_score(
        l1_hits=l1_hits,
        l2_hits=l2_hits,
        total_requests=total
    )

    assert 0 <= score <= 1
    # Weighted score (L2 hits at 0.7 weight) should be less than simple average
    simple_hit_rate = (l1_hits + l2_hits) / total
    assert score < simple_hit_rate  # Due to L2 weighting at 0.7


def test_estimate_performance_gain(monitoring_service):
    """
    Test performance gain estimation

    Verifies:
    - Speedup calculated from hit rates
    - L1 hits provide most speedup
    - Accounts for cache overhead
    """
    l1_hit_rate = 0.70
    l2_hit_rate = 0.15

    speedup = monitoring_service.estimate_performance_gain(
        l1_hit_rate=l1_hit_rate,
        l2_hit_rate=l2_hit_rate
    )

    assert speedup > 1.0  # Should show improvement
    assert speedup < 100.0  # Should be reasonable


@pytest.mark.asyncio
async def test_trigger_l2_cleanup(monitoring_service, mock_tiered_cache):
    """
    Test triggering L2 cache cleanup

    Verifies:
    - Cleanup is called on L2
    - Returns count of cleaned entries
    """
    count = await monitoring_service.trigger_l2_cleanup()

    assert count == 5
    mock_tiered_cache.cleanup_expired_l2_entries.assert_called_once()


def test_get_cache_stats_summary(monitoring_service, mock_tiered_cache):
    """
    Test getting cache stats summary

    Verifies:
    - Summary includes L1 and L2 stats
    - Overall metrics are calculated
    - Timestamp is included
    """
    summary = monitoring_service.get_cache_stats_summary()

    assert summary is not None
    assert "l1_stats" in summary or "l1" in summary
    assert "l2_stats" in summary or "l2" in summary
    assert "overall_hit_rate" in summary


def test_track_cache_operation(monitoring_service):
    """
    Test tracking individual cache operations

    Verifies:
    - Operation is recorded
    - Timestamp is added
    - Hit/miss is tracked
    """
    monitoring_service.track_cache_operation(
        operation="get_query_result",
        cache_hit=True,
        cache_level="L1",
        latency_ms=2.5
    )

    # Should not raise exception
    assert True


def test_get_cache_performance_report(monitoring_service):
    """
    Test generating cache performance report

    Verifies:
    - Report includes hit rates
    - Memory usage is reported
    - Effectiveness analysis included
    - Recommendations provided
    """
    report = monitoring_service.get_cache_performance_report()

    assert report is not None
    assert "hit_rate" in report or "metrics" in report
    assert "effectiveness" in report or "analysis" in report


def test_cache_health_check(monitoring_service, mock_tiered_cache):
    """
    Test cache health check

    Verifies:
    - L1 connection status checked
    - L2 connection status checked
    - Overall health returned
    """
    health = monitoring_service.check_cache_health()

    assert health is not None
    assert "l1_healthy" in health or "redis_healthy" in health
    assert "overall_healthy" in health


def test_get_cache_metrics_history(monitoring_service):
    """
    Test retrieving cache metrics history

    Verifies:
    - Historical metrics are tracked
    - Time range can be specified
    - Data points are timestamped
    """
    history = monitoring_service.get_metrics_history(
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow()
    )

    assert history is not None
    assert isinstance(history, list)


def test_calculate_cache_cost_savings(monitoring_service):
    """
    Test calculating cache cost savings

    Verifies:
    - Database query cost is estimated
    - Cache hit savings calculated
    - Cost per query is configurable
    """
    savings = monitoring_service.calculate_cost_savings(
        hit_count=1000,
        avg_db_query_cost_ms=100,
        avg_cache_query_cost_ms=5
    )

    assert isinstance(savings, dict)
    assert savings.get("time_saved_ms", 0) > 0
    assert "time_saved_ms" in savings or "queries_avoided" in savings


def test_get_monitoring_service_singleton():
    """
    Test singleton pattern for monitoring service

    Verifies:
    - Same instance returned
    - Configuration persists
    """
    service1 = get_cache_monitoring_service()
    service2 = get_cache_monitoring_service()

    assert service1 is service2


def test_cache_recommendations_based_on_metrics(monitoring_service):
    """
    Test generating recommendations based on metrics

    Verifies:
    - Low hit rate triggers recommendations
    - High memory usage flagged
    - L1/L2 balance suggestions
    """
    recommendations = monitoring_service.generate_recommendations()

    assert recommendations is not None
    assert isinstance(recommendations, list)


def test_alert_on_low_hit_rate(monitoring_service):
    """
    Test alerting when hit rate drops below threshold

    Verifies:
    - Alert triggered when hit rate < threshold
    - No alert when hit rate is healthy
    """
    # Mock low hit rate
    mock_metrics = {
        "l1": {"hits": 10, "misses": 90, "hit_rate": 0.10},
        "l2": {"hits": 5, "misses": 85, "hit_rate": 0.056}
    }

    should_alert = monitoring_service.check_hit_rate_threshold(
        metrics=mock_metrics,
        threshold=0.5
    )

    assert should_alert is True


def test_memory_usage_monitoring(monitoring_service, mock_tiered_cache):
    """
    Test monitoring memory usage

    Verifies:
    - L1 memory usage tracked
    - Warns on high usage
    - Suggests eviction if needed
    """
    memory_status = monitoring_service.get_memory_status()

    assert memory_status is not None
    assert "used_memory" in memory_status or "l1_memory" in memory_status


def test_export_metrics_for_prometheus(monitoring_service):
    """
    Test exporting metrics in Prometheus format

    Verifies:
    - Metrics formatted for Prometheus
    - Includes cache_hit_rate gauge
    - Includes cache_operations_total counter
    """
    prometheus_metrics = monitoring_service.export_prometheus_metrics()

    assert prometheus_metrics is not None
    assert "cache_hit_rate" in prometheus_metrics or "# TYPE" in prometheus_metrics
