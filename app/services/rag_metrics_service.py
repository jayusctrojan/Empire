"""
RAG Metrics Service - Task 149

Provides aggregated RAG quality metrics for the dashboard.
Supports real-time monitoring, trend analysis, and drill-down capabilities.

Features:
- Real-time RAGAS scores (Context Relevance, Answer Relevance, Faithfulness, Coverage)
- Drill-down by query type, time period, and agent
- Trend analysis and optimization opportunities
- Performance-optimized queries for 30-day data
"""

import os
import structlog
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum
from supabase import create_client, Client

logger = structlog.get_logger(__name__)


class TimeRange(str, Enum):
    """Time range options for metrics queries."""
    LAST_HOUR = "1h"
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    CUSTOM = "custom"


class AggregationType(str, Enum):
    """Aggregation methods for metrics."""
    AVERAGE = "avg"
    MEDIAN = "median"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"
    MIN = "min"
    MAX = "max"


class RAGASSummary(BaseModel):
    """Summary of RAGAS metrics."""
    context_relevance: float = 0.0
    answer_relevance: float = 0.0
    faithfulness: float = 0.0
    coverage: float = 0.0
    overall_score: float = 0.0
    sample_count: int = 0


class TrendPoint(BaseModel):
    """Single data point in a trend."""
    timestamp: datetime
    value: float
    sample_count: int = 0


class MetricTrend(BaseModel):
    """Trend data for a metric."""
    metric_name: str
    time_range: TimeRange
    data_points: List[TrendPoint] = Field(default_factory=list)
    trend_direction: str = "stable"  # up, down, stable
    trend_percentage: float = 0.0


class AgentPerformanceSummary(BaseModel):
    """Performance summary for an agent."""
    agent_id: str
    agent_name: str
    total_executions: int = 0
    success_rate: float = 0.0
    avg_quality_score: float = 0.0
    avg_latency_ms: float = 0.0
    task_types: List[str] = Field(default_factory=list)


class QueryTypeBreakdown(BaseModel):
    """Metrics broken down by query type."""
    query_type: str
    query_count: int = 0
    avg_quality_score: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0


class OptimizationOpportunity(BaseModel):
    """Identified optimization opportunity."""
    area: str
    severity: str  # high, medium, low
    description: str
    recommendation: str
    potential_improvement: float = 0.0  # Estimated % improvement


class DashboardData(BaseModel):
    """Complete dashboard data response."""
    summary: RAGASSummary
    trends: List[MetricTrend] = Field(default_factory=list)
    agent_performance: List[AgentPerformanceSummary] = Field(default_factory=list)
    query_breakdown: List[QueryTypeBreakdown] = Field(default_factory=list)
    optimization_opportunities: List[OptimizationOpportunity] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_freshness_seconds: float = 0.0


class RAGMetricsService:
    """
    Service for aggregating and analyzing RAG quality metrics.

    Provides:
    - Real-time RAGAS score summaries
    - Historical trend analysis
    - Agent performance breakdowns
    - Query type analysis
    - Optimization recommendations
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        cache_ttl_seconds: int = 60
    ):
        """
        Initialize metrics service.

        Args:
            supabase_url: Supabase URL.
            supabase_key: Supabase service key.
            cache_ttl_seconds: Cache time-to-live for aggregated data.
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Initialize Supabase client
        url = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")

        if url and key:
            self.supabase: Optional[Client] = create_client(url, key)
        else:
            self.supabase = None
            logger.warning("rag_metrics_no_supabase",
                          message="Supabase not configured")

    def _get_time_bounds(
        self,
        time_range: TimeRange,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> tuple[datetime, datetime]:
        """Calculate time bounds for queries."""
        now = datetime.now(timezone.utc)

        if time_range == TimeRange.CUSTOM and start_time and end_time:
            return start_time, end_time

        time_deltas = {
            TimeRange.LAST_HOUR: timedelta(hours=1),
            TimeRange.LAST_24_HOURS: timedelta(hours=24),
            TimeRange.LAST_7_DAYS: timedelta(days=7),
            TimeRange.LAST_30_DAYS: timedelta(days=30),
        }

        delta = time_deltas.get(time_range, timedelta(days=30))
        return now - delta, now

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache_timestamps:
            return False

        age = (datetime.now(timezone.utc) - self._cache_timestamps[cache_key]).total_seconds()
        return age < self.cache_ttl_seconds

    async def get_ragas_summary(
        self,
        time_range: TimeRange = TimeRange.LAST_24_HOURS,
        query_type: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> RAGASSummary:
        """
        Get RAGAS metrics summary.

        Args:
            time_range: Time range to aggregate.
            query_type: Optional filter by query type.
            agent_id: Optional filter by agent.

        Returns:
            RAGASSummary with aggregated metrics.
        """
        cache_key = f"ragas_summary:{time_range}:{query_type}:{agent_id}"

        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        start_time, end_time = self._get_time_bounds(time_range)

        if not self.supabase:
            return RAGASSummary()

        try:
            # Use the database function for efficient aggregation
            result = self.supabase.rpc(
                "get_avg_rag_metrics",
                {
                    "start_ts": start_time.isoformat(),
                    "end_ts": end_time.isoformat()
                }
            ).execute()

            if result.data and len(result.data) > 0:
                row = result.data[0]
                summary = RAGASSummary(
                    context_relevance=row.get("avg_context_relevance", 0) or 0,
                    answer_relevance=row.get("avg_answer_relevance", 0) or 0,
                    faithfulness=row.get("avg_faithfulness", 0) or 0,
                    coverage=row.get("avg_coverage", 0) or 0,
                    overall_score=row.get("avg_overall_score", 0) or 0,
                    sample_count=row.get("sample_count", 0) or 0
                )
            else:
                summary = RAGASSummary()

            self._cache[cache_key] = summary
            self._cache_timestamps[cache_key] = datetime.now(timezone.utc)

            return summary

        except Exception as e:
            logger.error("get_ragas_summary_error", error=str(e))
            return RAGASSummary()

    async def get_metric_trend(
        self,
        metric_name: str,
        time_range: TimeRange = TimeRange.LAST_7_DAYS,
        granularity: str = "hour"  # hour, day
    ) -> MetricTrend:
        """
        Get trend data for a specific metric.

        Args:
            metric_name: Name of the metric (context_relevance, answer_relevance, etc.)
            time_range: Time range for the trend.
            granularity: Data point granularity (hour or day).

        Returns:
            MetricTrend with data points.
        """
        start_time, end_time = self._get_time_bounds(time_range)

        if not self.supabase:
            return MetricTrend(metric_name=metric_name, time_range=time_range)

        try:
            # Query metrics grouped by time bucket
            _interval = "1 hour" if granularity == "hour" else "1 day"  # noqa: F841

            query = f"""
                SELECT
                    date_trunc('{granularity}', created_at) as time_bucket,
                    AVG({metric_name}) as avg_value,
                    COUNT(*) as sample_count
                FROM rag_quality_metrics
                WHERE created_at >= '{start_time.isoformat()}'
                  AND created_at <= '{end_time.isoformat()}'
                GROUP BY time_bucket
                ORDER BY time_bucket ASC
            """

            result = self.supabase.rpc("execute_sql", {"query": query}).execute()

            data_points = []
            if result.data:
                for row in result.data:
                    data_points.append(TrendPoint(
                        timestamp=row["time_bucket"],
                        value=row["avg_value"] or 0,
                        sample_count=row["sample_count"] or 0
                    ))

            # Calculate trend direction
            trend_direction = "stable"
            trend_percentage = 0.0

            if len(data_points) >= 2:
                first_half = data_points[:len(data_points) // 2]
                second_half = data_points[len(data_points) // 2:]

                first_avg = sum(p.value for p in first_half) / len(first_half) if first_half else 0
                second_avg = sum(p.value for p in second_half) / len(second_half) if second_half else 0

                if first_avg > 0:
                    trend_percentage = ((second_avg - first_avg) / first_avg) * 100

                    if trend_percentage > 5:
                        trend_direction = "up"
                    elif trend_percentage < -5:
                        trend_direction = "down"

            return MetricTrend(
                metric_name=metric_name,
                time_range=time_range,
                data_points=data_points,
                trend_direction=trend_direction,
                trend_percentage=trend_percentage
            )

        except Exception as e:
            logger.error("get_metric_trend_error", metric=metric_name, error=str(e))
            return MetricTrend(metric_name=metric_name, time_range=time_range)

    async def get_agent_performance(
        self,
        time_range: TimeRange = TimeRange.LAST_7_DAYS
    ) -> List[AgentPerformanceSummary]:
        """
        Get performance summary for all agents.

        Args:
            time_range: Time range to analyze.

        Returns:
            List of agent performance summaries.
        """
        if not self.supabase:
            return []

        try:
            # Query agent performance
            result = self.supabase.table("agent_performance_history").select(
                "agent_id, task_type, success, quality_score, latency_ms"
            ).execute()

            # Aggregate by agent
            agent_data: Dict[str, Dict[str, Any]] = {}

            for row in result.data or []:
                agent_id = row["agent_id"]

                if agent_id not in agent_data:
                    agent_data[agent_id] = {
                        "total": 0,
                        "successes": 0,
                        "quality_sum": 0,
                        "latency_sum": 0,
                        "task_types": set()
                    }

                agent_data[agent_id]["total"] += 1
                if row.get("success"):
                    agent_data[agent_id]["successes"] += 1
                agent_data[agent_id]["quality_sum"] += row.get("quality_score", 0) or 0
                agent_data[agent_id]["latency_sum"] += row.get("latency_ms", 0) or 0
                if row.get("task_type"):
                    agent_data[agent_id]["task_types"].add(row["task_type"])

            # Build summaries
            summaries = []
            for agent_id, data in agent_data.items():
                total = data["total"]
                summaries.append(AgentPerformanceSummary(
                    agent_id=agent_id,
                    agent_name=self._get_agent_name(agent_id),
                    total_executions=total,
                    success_rate=data["successes"] / total if total > 0 else 0,
                    avg_quality_score=data["quality_sum"] / total if total > 0 else 0,
                    avg_latency_ms=data["latency_sum"] / total if total > 0 else 0,
                    task_types=list(data["task_types"])
                ))

            # Sort by total executions
            summaries.sort(key=lambda x: x.total_executions, reverse=True)

            return summaries

        except Exception as e:
            logger.error("get_agent_performance_error", error=str(e))
            return []

    async def get_query_breakdown(
        self,
        time_range: TimeRange = TimeRange.LAST_7_DAYS
    ) -> List[QueryTypeBreakdown]:
        """
        Get metrics breakdown by query type.

        Args:
            time_range: Time range to analyze.

        Returns:
            List of query type breakdowns.
        """
        start_time, end_time = self._get_time_bounds(time_range)

        if not self.supabase:
            return []

        try:
            result = self.supabase.table("rag_quality_metrics").select(
                "query_type, overall_score, latency_ms"
            ).gte("created_at", start_time.isoformat()).lte(
                "created_at", end_time.isoformat()
            ).execute()

            # Aggregate by query type
            type_data: Dict[str, Dict[str, Any]] = {}

            for row in result.data or []:
                query_type = row.get("query_type", "unknown")

                if query_type not in type_data:
                    type_data[query_type] = {
                        "count": 0,
                        "quality_sum": 0,
                        "latency_sum": 0,
                        "successes": 0
                    }

                type_data[query_type]["count"] += 1
                quality = row.get("overall_score", 0) or 0
                type_data[query_type]["quality_sum"] += quality
                type_data[query_type]["latency_sum"] += row.get("latency_ms", 0) or 0

                # Consider quality > 0.5 as success
                if quality > 0.5:
                    type_data[query_type]["successes"] += 1

            # Build breakdowns
            breakdowns = []
            for query_type, data in type_data.items():
                count = data["count"]
                breakdowns.append(QueryTypeBreakdown(
                    query_type=query_type,
                    query_count=count,
                    avg_quality_score=data["quality_sum"] / count if count > 0 else 0,
                    avg_latency_ms=data["latency_sum"] / count if count > 0 else 0,
                    success_rate=data["successes"] / count if count > 0 else 0
                ))

            # Sort by query count
            breakdowns.sort(key=lambda x: x.query_count, reverse=True)

            return breakdowns

        except Exception as e:
            logger.error("get_query_breakdown_error", error=str(e))
            return []

    async def get_optimization_opportunities(
        self,
        summary: RAGASSummary,
        agent_performance: List[AgentPerformanceSummary],
        query_breakdown: List[QueryTypeBreakdown]
    ) -> List[OptimizationOpportunity]:
        """
        Identify optimization opportunities based on current metrics.

        Args:
            summary: Current RAGAS summary.
            agent_performance: Agent performance data.
            query_breakdown: Query type breakdown.

        Returns:
            List of optimization opportunities.
        """
        opportunities = []

        # Check context relevance
        if summary.context_relevance < 0.7:
            opportunities.append(OptimizationOpportunity(
                area="Context Retrieval",
                severity="high" if summary.context_relevance < 0.5 else "medium",
                description=f"Context relevance score is {summary.context_relevance:.2f}",
                recommendation="Consider adjusting retrieval parameters, expanding query terms, or increasing top_k",
                potential_improvement=(0.7 - summary.context_relevance) * 100
            ))

        # Check answer relevance
        if summary.answer_relevance < 0.7:
            opportunities.append(OptimizationOpportunity(
                area="Answer Generation",
                severity="high" if summary.answer_relevance < 0.5 else "medium",
                description=f"Answer relevance score is {summary.answer_relevance:.2f}",
                recommendation="Review prompt templates and consider using more specific generation instructions",
                potential_improvement=(0.7 - summary.answer_relevance) * 100
            ))

        # Check faithfulness
        if summary.faithfulness < 0.8:
            opportunities.append(OptimizationOpportunity(
                area="Hallucination Prevention",
                severity="high" if summary.faithfulness < 0.6 else "medium",
                description=f"Faithfulness score is {summary.faithfulness:.2f}",
                recommendation="Strengthen grounding constraints and add citation requirements",
                potential_improvement=(0.8 - summary.faithfulness) * 100
            ))

        # Check agent performance
        for agent in agent_performance:
            if agent.success_rate < 0.8 and agent.total_executions > 10:
                opportunities.append(OptimizationOpportunity(
                    area=f"Agent: {agent.agent_name}",
                    severity="medium",
                    description=f"Agent {agent.agent_id} has {agent.success_rate:.1%} success rate",
                    recommendation="Review agent prompts and consider retraining or adjusting task routing",
                    potential_improvement=(0.8 - agent.success_rate) * 100
                ))

        # Check slow query types
        for breakdown in query_breakdown:
            if breakdown.avg_latency_ms > 5000 and breakdown.query_count > 5:
                opportunities.append(OptimizationOpportunity(
                    area=f"Query Type: {breakdown.query_type}",
                    severity="low",
                    description=f"{breakdown.query_type} queries average {breakdown.avg_latency_ms:.0f}ms",
                    recommendation="Consider caching, query optimization, or specialized agents for this type",
                    potential_improvement=((breakdown.avg_latency_ms - 2000) / breakdown.avg_latency_ms) * 100
                ))

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        opportunities.sort(key=lambda x: severity_order.get(x.severity, 3))

        return opportunities

    async def get_dashboard_data(
        self,
        time_range: TimeRange = TimeRange.LAST_24_HOURS
    ) -> DashboardData:
        """
        Get complete dashboard data in a single call.

        Optimized for performance with parallel queries and caching.

        Args:
            time_range: Time range for the dashboard.

        Returns:
            Complete DashboardData object.
        """
        import asyncio
        start_time = datetime.now(timezone.utc)

        # Run all queries in parallel
        summary_task = self.get_ragas_summary(time_range)
        agent_task = self.get_agent_performance(time_range)
        query_task = self.get_query_breakdown(time_range)

        # Get trends for main metrics
        trend_tasks = [
            self.get_metric_trend("context_relevance", time_range),
            self.get_metric_trend("answer_relevance", time_range),
            self.get_metric_trend("faithfulness", time_range),
            self.get_metric_trend("overall_score", time_range),
        ]

        # Await all results
        summary, agents, queries = await asyncio.gather(
            summary_task, agent_task, query_task
        )
        trends = await asyncio.gather(*trend_tasks)

        # Get optimization opportunities
        opportunities = await self.get_optimization_opportunities(
            summary, agents, queries
        )

        data_freshness = (datetime.now(timezone.utc) - start_time).total_seconds()

        return DashboardData(
            summary=summary,
            trends=list(trends),
            agent_performance=agents,
            query_breakdown=queries,
            optimization_opportunities=opportunities,
            last_updated=datetime.now(timezone.utc),
            data_freshness_seconds=data_freshness
        )

    def _get_agent_name(self, agent_id: str) -> str:
        """Get human-readable agent name."""
        agent_names = {
            "AGENT-001": "Query Router",
            "AGENT-002": "Content Summarizer",
            "AGENT-003": "Entity Extractor",
            "AGENT-004": "Relationship Mapper",
            "AGENT-005": "Context Synthesizer",
            "AGENT-006": "Answer Generator",
            "AGENT-007": "Citation Validator",
            "AGENT-008": "Department Classifier",
            "AGENT-009": "Senior Research Analyst",
            "AGENT-010": "Content Strategist",
            "AGENT-011": "Fact Checker",
            "AGENT-012": "Research Agent",
            "AGENT-013": "Analysis Agent",
            "AGENT-014": "Writing Agent",
            "AGENT-015": "Review Agent",
            "AGENT-016": "Memory Agent",
            "AGENT-017": "Graph Query Agent",
        }
        return agent_names.get(agent_id, agent_id)


# Singleton instance
_metrics_service_instance: Optional[RAGMetricsService] = None


def get_rag_metrics_service() -> RAGMetricsService:
    """Get or create the RAG metrics service singleton."""
    global _metrics_service_instance

    if _metrics_service_instance is None:
        _metrics_service_instance = RAGMetricsService()

    return _metrics_service_instance
