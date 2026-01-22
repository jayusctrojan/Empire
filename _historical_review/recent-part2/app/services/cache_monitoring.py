"""
Cache Monitoring and Effectiveness Tracking Service

Provides comprehensive monitoring, metrics aggregation, and effectiveness analysis
for the tiered cache system (L1: Redis, L2: PostgreSQL).

Features:
- Real-time cache hit rate tracking
- L1/L2 metrics aggregation
- Cache effectiveness scoring
- Performance gain estimation
- Memory usage monitoring
- Health checks
- Prometheus metrics export
- Recommendations based on metrics
- Historical metrics tracking

Usage:
    from app.services.cache_monitoring import get_cache_monitoring_service

    monitor = get_cache_monitoring_service()

    # Get current metrics
    metrics = monitor.get_current_metrics()

    # Analyze effectiveness
    effectiveness = monitor.analyze_cache_effectiveness()

    # Get performance report
    report = monitor.get_cache_performance_report()
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.services.tiered_cache_service import (
    TieredCacheService,
    get_tiered_cache_service
)

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Cache metrics for a single cache level"""
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    timestamp: Optional[datetime] = None

    @property
    def total_requests(self) -> int:
        """Total cache requests"""
        return self.hits + self.misses

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "total_requests": self.total_requests,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class CacheStats:
    """Aggregated cache statistics"""
    l1_metrics: CacheMetrics
    l2_metrics: CacheMetrics
    overall_hit_rate: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "l1_stats": self.l1_metrics.to_dict(),
            "l2_stats": self.l2_metrics.to_dict(),
            "overall_hit_rate": self.overall_hit_rate,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CacheEffectiveness:
    """Cache effectiveness analysis"""
    hit_rate: float
    l1_hit_percentage: float
    l2_hit_percentage: float
    memory_usage_mb: float
    avg_response_time_ms: float
    estimated_speedup: float
    effectiveness_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hit_rate": self.hit_rate,
            "l1_hit_percentage": self.l1_hit_percentage,
            "l2_hit_percentage": self.l2_hit_percentage,
            "memory_usage_mb": self.memory_usage_mb,
            "avg_response_time_ms": self.avg_response_time_ms,
            "estimated_speedup": self.estimated_speedup,
            "effectiveness_score": self.effectiveness_score
        }


class CacheMonitoringService:
    """
    Service for monitoring and analyzing cache performance

    Tracks metrics, calculates effectiveness, and provides recommendations
    for optimizing the tiered cache system.
    """

    def __init__(self, tiered_cache: Optional[TieredCacheService] = None):
        """
        Initialize cache monitoring service

        Args:
            tiered_cache: Optional tiered cache service
        """
        self.tiered_cache = tiered_cache or get_tiered_cache_service()
        self.operations_history: List[Dict[str, Any]] = []
        self.metrics_history: List[Dict[str, Any]] = []

        logger.info("Initialized CacheMonitoringService")

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current cache metrics from tiered cache

        Returns:
            Metrics dictionary with L1 and L2 stats
        """
        try:
            metrics = self.tiered_cache.get_metrics()
            metrics["timestamp"] = datetime.utcnow().isoformat()
            return metrics
        except Exception as e:
            logger.error(f"Failed to get current metrics: {e}")
            return {
                "l1": {"hits": 0, "misses": 0, "hit_rate": 0.0},
                "l2": {"hits": 0, "misses": 0, "hit_rate": 0.0},
                "timestamp": datetime.utcnow().isoformat()
            }

    def calculate_overall_hit_rate(
        self,
        l1_metrics: Dict[str, int],
        l2_metrics: Dict[str, int]
    ) -> float:
        """
        Calculate overall hit rate across L1 and L2

        Args:
            l1_metrics: L1 cache metrics
            l2_metrics: L2 cache metrics

        Returns:
            Combined hit rate (0.0 to 1.0)
        """
        total_hits = l1_metrics.get("hits", 0) + l2_metrics.get("hits", 0)
        total_misses = l1_metrics.get("misses", 0) + l2_metrics.get("misses", 0)
        total_requests = total_hits + total_misses

        if total_requests == 0:
            return 0.0

        return total_hits / total_requests

    def get_l1_cache_info(self) -> Dict[str, Any]:
        """
        Get L1 (Redis) cache information

        Returns:
            Cache info including memory usage and connection status
        """
        try:
            if self.tiered_cache.redis_cache:
                return self.tiered_cache.redis_cache.get_cache_info()
            return {"connected": False}
        except Exception as e:
            logger.error(f"Failed to get L1 cache info: {e}")
            return {"connected": False, "error": str(e)}

    def analyze_cache_effectiveness(self) -> CacheEffectiveness:
        """
        Analyze cache effectiveness

        Returns:
            CacheEffectiveness with scores and analysis
        """
        try:
            metrics = self.get_current_metrics()
            l1 = metrics.get("l1", {})
            l2 = metrics.get("l2", {})

            l1_hits = l1.get("hits", 0)
            l2_hits = l2.get("hits", 0)
            l1_misses = l1.get("misses", 0)
            l2_misses = l2.get("misses", 0)

            total_requests = l1_hits + l1_misses + l2_hits + l2_misses

            if total_requests == 0:
                return CacheEffectiveness(
                    hit_rate=0.0,
                    l1_hit_percentage=0.0,
                    l2_hit_percentage=0.0,
                    memory_usage_mb=0.0,
                    avg_response_time_ms=0.0,
                    estimated_speedup=1.0,
                    effectiveness_score=0.0
                )

            overall_hit_rate = (l1_hits + l2_hits) / total_requests
            l1_hit_percentage = l1_hits / total_requests
            l2_hit_percentage = l2_hits / total_requests

            # Get memory usage
            cache_info = self.get_l1_cache_info()
            memory_str = cache_info.get("used_memory_human", "0M")
            memory_mb = self._parse_memory_string(memory_str)

            # Estimate performance
            l1_hit_rate = l1_hits / (l1_hits + l1_misses) if (l1_hits + l1_misses) > 0 else 0
            l2_hit_rate = l2_hits / (l2_hits + l2_misses) if (l2_hits + l2_misses) > 0 else 0
            estimated_speedup = self.estimate_performance_gain(l1_hit_rate, l2_hit_rate)

            # Calculate effectiveness score
            effectiveness_score = self.calculate_effectiveness_score(
                l1_hits=l1_hits,
                l2_hits=l2_hits,
                total_requests=total_requests
            )

            return CacheEffectiveness(
                hit_rate=overall_hit_rate,
                l1_hit_percentage=l1_hit_percentage,
                l2_hit_percentage=l2_hit_percentage,
                memory_usage_mb=memory_mb,
                avg_response_time_ms=15.0,  # Mock value
                estimated_speedup=estimated_speedup,
                effectiveness_score=effectiveness_score
            )

        except Exception as e:
            logger.error(f"Failed to analyze cache effectiveness: {e}")
            return CacheEffectiveness(
                hit_rate=0.0,
                l1_hit_percentage=0.0,
                l2_hit_percentage=0.0,
                memory_usage_mb=0.0,
                avg_response_time_ms=0.0,
                estimated_speedup=1.0,
                effectiveness_score=0.0
            )

    def calculate_effectiveness_score(
        self,
        l1_hits: int,
        l2_hits: int,
        total_requests: int
    ) -> float:
        """
        Calculate cache effectiveness score

        L1 hits are weighted more heavily than L2 hits since L1 is faster.

        Args:
            l1_hits: Number of L1 hits
            l2_hits: Number of L2 hits
            total_requests: Total requests

        Returns:
            Effectiveness score (0.0 to 1.0)
        """
        if total_requests == 0:
            return 0.0

        # Weight L1 hits 1.0, L2 hits 0.7 (since L2 is slower)
        weighted_hits = (l1_hits * 1.0) + (l2_hits * 0.7)
        score = weighted_hits / total_requests

        # Cap at 1.0
        return min(score, 1.0)

    def estimate_performance_gain(
        self,
        l1_hit_rate: float,
        l2_hit_rate: float
    ) -> float:
        """
        Estimate performance gain from caching

        Args:
            l1_hit_rate: L1 cache hit rate
            l2_hit_rate: L2 cache hit rate

        Returns:
            Estimated speedup factor
        """
        # Assume:
        # - L1 cache hit: 2ms
        # - L2 cache hit: 20ms
        # - Database query: 100ms

        l1_time = 2.0
        l2_time = 20.0
        db_time = 100.0

        # Weighted average response time
        avg_time = (
            l1_hit_rate * l1_time +
            l2_hit_rate * l2_time +
            (1 - l1_hit_rate - l2_hit_rate) * db_time
        )

        if avg_time == 0:
            return 1.0

        # Speedup compared to no cache
        speedup = db_time / avg_time
        return speedup

    def _parse_memory_string(self, memory_str: str) -> float:
        """Parse memory string like '10M' to MB"""
        if not memory_str:
            return 0.0

        try:
            if memory_str.endswith("M"):
                return float(memory_str[:-1])
            elif memory_str.endswith("G"):
                return float(memory_str[:-1]) * 1024
            elif memory_str.endswith("K"):
                return float(memory_str[:-1]) / 1024
            else:
                # Assume bytes
                return float(memory_str) / (1024 * 1024)
        except:
            return 0.0

    async def trigger_l2_cleanup(self) -> int:
        """
        Trigger L2 cache cleanup

        Returns:
            Count of cleaned entries
        """
        try:
            return await self.tiered_cache.cleanup_expired_l2_entries()
        except Exception as e:
            logger.error(f"Failed to trigger L2 cleanup: {e}")
            return 0

    def get_cache_stats_summary(self) -> Dict[str, Any]:
        """
        Get cache statistics summary

        Returns:
            Summary dictionary
        """
        metrics = self.get_current_metrics()
        l1 = metrics.get("l1", {})
        l2 = metrics.get("l2", {})

        overall_hit_rate = self.calculate_overall_hit_rate(l1, l2)

        return {
            "l1_stats": l1,
            "l2_stats": l2,
            "overall_hit_rate": overall_hit_rate,
            "timestamp": metrics.get("timestamp")
        }

    def track_cache_operation(
        self,
        operation: str,
        cache_hit: bool,
        cache_level: str,
        latency_ms: float
    ):
        """
        Track individual cache operation

        Args:
            operation: Operation name
            cache_hit: Whether operation resulted in hit
            cache_level: Cache level (L1, L2, NONE)
            latency_ms: Operation latency
        """
        self.operations_history.append({
            "operation": operation,
            "cache_hit": cache_hit,
            "cache_level": cache_level,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep only last 1000 operations
        if len(self.operations_history) > 1000:
            self.operations_history = self.operations_history[-1000:]

    def get_cache_performance_report(self) -> Dict[str, Any]:
        """
        Generate cache performance report

        Returns:
            Comprehensive performance report
        """
        metrics = self.get_current_metrics()
        effectiveness = self.analyze_cache_effectiveness()
        recommendations = self.generate_recommendations()

        return {
            "metrics": metrics,
            "effectiveness": effectiveness.to_dict(),
            "analysis": {
                "hit_rate": effectiveness.hit_rate,
                "estimated_speedup": effectiveness.estimated_speedup,
                "effectiveness_score": effectiveness.effectiveness_score
            },
            "recommendations": recommendations,
            "timestamp": datetime.utcnow().isoformat()
        }

    def check_cache_health(self) -> Dict[str, Any]:
        """
        Check cache health

        Returns:
            Health status dictionary
        """
        cache_info = self.get_l1_cache_info()
        l1_healthy = cache_info.get("connected", False)

        metrics = self.get_current_metrics()
        overall_hit_rate = self.calculate_overall_hit_rate(
            metrics.get("l1", {}),
            metrics.get("l2", {})
        )

        # Consider healthy if L1 connected and hit rate > 0.3
        overall_healthy = l1_healthy and overall_hit_rate > 0.3

        return {
            "redis_healthy": l1_healthy,
            "l1_healthy": l1_healthy,
            "overall_healthy": overall_healthy,
            "hit_rate": overall_hit_rate,
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_metrics_history(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get historical metrics

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of historical metrics
        """
        # Filter metrics history by time range
        filtered = [
            m for m in self.metrics_history
            if start_time <= datetime.fromisoformat(m["timestamp"]) <= end_time
        ]

        return filtered

    def calculate_cost_savings(
        self,
        hit_count: int,
        avg_db_query_cost_ms: float,
        avg_cache_query_cost_ms: float
    ) -> Dict[str, Any]:
        """
        Calculate cache cost savings

        Args:
            hit_count: Number of cache hits
            avg_db_query_cost_ms: Average database query time
            avg_cache_query_cost_ms: Average cache query time

        Returns:
            Cost savings dictionary
        """
        time_saved_ms = hit_count * (avg_db_query_cost_ms - avg_cache_query_cost_ms)

        return {
            "queries_avoided": hit_count,
            "time_saved_ms": time_saved_ms,
            "time_saved_seconds": time_saved_ms / 1000,
            "avg_speedup": avg_db_query_cost_ms / avg_cache_query_cost_ms if avg_cache_query_cost_ms > 0 else 1.0
        }

    def generate_recommendations(self) -> List[str]:
        """
        Generate recommendations based on current metrics

        Returns:
            List of recommendation strings
        """
        recommendations = []
        metrics = self.get_current_metrics()
        l1 = metrics.get("l1", {})
        l2 = metrics.get("l2", {})

        overall_hit_rate = self.calculate_overall_hit_rate(l1, l2)

        # Check hit rate
        if overall_hit_rate < 0.5:
            recommendations.append(
                "Low cache hit rate detected. Consider increasing cache TTL or "
                "reviewing query patterns."
            )

        # Check L1 hit rate
        l1_hit_rate = l1.get("hit_rate", 0.0)
        if l1_hit_rate < 0.6 and overall_hit_rate > 0.7:
            recommendations.append(
                "L1 hit rate is lower than expected. Consider increasing L1 TTL "
                "or promoting more L2 hits to L1."
            )

        # Check memory
        cache_info = self.get_l1_cache_info()
        memory_str = cache_info.get("used_memory_human", "0M")
        memory_mb = self._parse_memory_string(memory_str)

        if memory_mb > 100:
            recommendations.append(
                f"L1 memory usage is high ({memory_mb:.1f}MB). Consider reducing TTL "
                "or implementing eviction policies."
            )

        if not recommendations:
            recommendations.append("Cache performance is healthy. No immediate actions needed.")

        return recommendations

    def check_hit_rate_threshold(
        self,
        metrics: Dict[str, Any],
        threshold: float
    ) -> bool:
        """
        Check if hit rate is below threshold

        Args:
            metrics: Cache metrics
            threshold: Hit rate threshold

        Returns:
            True if alert should be triggered
        """
        overall_hit_rate = self.calculate_overall_hit_rate(
            metrics.get("l1", {}),
            metrics.get("l2", {})
        )

        return overall_hit_rate < threshold

    def get_memory_status(self) -> Dict[str, Any]:
        """
        Get memory usage status

        Returns:
            Memory status dictionary
        """
        cache_info = self.get_l1_cache_info()
        memory_str = cache_info.get("used_memory_human", "0M")
        memory_mb = self._parse_memory_string(memory_str)

        return {
            "l1_memory": cache_info.get("used_memory"),
            "used_memory": cache_info.get("used_memory_human"),
            "memory_mb": memory_mb,
            "high_usage": memory_mb > 100
        }

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format

        Returns:
            Prometheus-formatted metrics string
        """
        metrics = self.get_current_metrics()
        l1 = metrics.get("l1", {})
        l2 = metrics.get("l2", {})

        overall_hit_rate = self.calculate_overall_hit_rate(l1, l2)

        prometheus_output = f"""# HELP cache_hit_rate Cache hit rate (0.0 to 1.0)
# TYPE cache_hit_rate gauge
cache_hit_rate{{level="overall"}} {overall_hit_rate}
cache_hit_rate{{level="l1"}} {l1.get('hit_rate', 0.0)}
cache_hit_rate{{level="l2"}} {l2.get('hit_rate', 0.0)}

# HELP cache_operations_total Total cache operations
# TYPE cache_operations_total counter
cache_operations_total{{level="l1",result="hit"}} {l1.get('hits', 0)}
cache_operations_total{{level="l1",result="miss"}} {l1.get('misses', 0)}
cache_operations_total{{level="l2",result="hit"}} {l2.get('hits', 0)}
cache_operations_total{{level="l2",result="miss"}} {l2.get('misses', 0)}
"""

        return prometheus_output


# Singleton instance
_cache_monitoring_service: Optional[CacheMonitoringService] = None


def get_cache_monitoring_service(
    tiered_cache: Optional[TieredCacheService] = None
) -> CacheMonitoringService:
    """
    Get or create singleton cache monitoring service instance

    Args:
        tiered_cache: Optional tiered cache service

    Returns:
        CacheMonitoringService instance
    """
    global _cache_monitoring_service

    if _cache_monitoring_service is None:
        _cache_monitoring_service = CacheMonitoringService(tiered_cache=tiered_cache)

    return _cache_monitoring_service
