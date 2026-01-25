"""
Empire v7.3 - Performance Profiler for Project Sources
Task 69: E2E testing and performance optimization

Provides profiling utilities for:
- Source upload/processing benchmarks
- RAG query performance tracking
- Memory and CPU profiling
- Percentile latency tracking
"""

import time
import asyncio
import functools
import statistics
import psutil
import sys
from typing import Dict, Any, Optional, List, Callable, TypeVar

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from collections import defaultdict
from prometheus_client import Histogram, Counter, Gauge, Summary
import structlog

logger = structlog.get_logger(__name__)

# Type variables for decorators
P = ParamSpec('P')
T = TypeVar('T')


# ============================================================================
# Prometheus Metrics for Project Sources
# ============================================================================

# Source processing metrics
SOURCE_PROCESSING_DURATION = Histogram(
    'empire_source_processing_duration_seconds',
    'Time to process a project source',
    ['source_type', 'file_type', 'status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
)

SOURCE_PROCESSING_STAGES = Histogram(
    'empire_source_processing_stage_duration_seconds',
    'Time for each processing stage',
    ['stage', 'source_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

SOURCE_UPLOAD_SIZE = Histogram(
    'empire_source_upload_size_bytes',
    'Size of uploaded sources',
    ['source_type'],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 52428800, 104857600]
)

SOURCE_QUEUE_TIME = Histogram(
    'empire_source_queue_time_seconds',
    'Time sources spend in Celery queue before processing',
    ['priority', 'queue'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

RAG_QUERY_DURATION = Histogram(
    'empire_rag_query_duration_seconds',
    'Time to execute a project RAG query',
    ['include_global', 'has_citations'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
)

RAG_RETRIEVAL_COUNT = Summary(
    'empire_rag_retrieval_count',
    'Number of chunks retrieved per query',
    ['source_type']
)

# Resource usage metrics
PROCESSING_MEMORY_USAGE = Gauge(
    'empire_source_processing_memory_mb',
    'Memory usage during source processing',
    ['process_type']
)

CONCURRENT_PROCESSING = Gauge(
    'empire_concurrent_source_processing',
    'Number of sources being processed concurrently'
)


# ============================================================================
# Performance Data Classes
# ============================================================================

@dataclass
class StageProfile:
    """Profile data for a single processing stage"""
    stage_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    memory_start_mb: Optional[float] = None
    memory_end_mb: Optional[float] = None
    memory_delta_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    success: bool = True

    def complete(self) -> 'StageProfile':
        """Mark stage as complete and calculate metrics"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

        if self.memory_start_mb is not None:
            self.memory_end_mb = psutil.Process().memory_info().rss / 1024 / 1024
            self.memory_delta_mb = self.memory_end_mb - self.memory_start_mb

        return self


@dataclass
class SourceProcessingProfile:
    """Complete profile for source processing"""
    source_id: str
    source_type: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    queue_time_ms: Optional[float] = None
    stages: List[StageProfile] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self) -> 'SourceProcessingProfile':
        """Mark processing as complete"""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": self.total_duration_ms,
            "queue_time_ms": self.queue_time_ms,
            "stages": [
                {
                    "name": s.stage_name,
                    "duration_ms": s.duration_ms,
                    "memory_delta_mb": s.memory_delta_mb,
                    "success": s.success,
                    "error": s.error
                }
                for s in self.stages
            ],
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class PerformanceReport:
    """Aggregated performance report"""
    period_start: datetime
    period_end: datetime
    total_sources_processed: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    avg_queue_time_ms: float = 0.0
    by_source_type: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_file_type: Dict[str, Dict[str, float]] = field(default_factory=dict)
    stage_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)


# ============================================================================
# Performance Profiler Service
# ============================================================================

class PerformanceProfiler:
    """
    Performance profiling service for project sources.

    Provides:
    - Decorator-based function profiling
    - Context managers for stage profiling
    - Aggregated performance reports
    - Prometheus metric recording
    """

    def __init__(self):
        self._profiles: Dict[str, SourceProcessingProfile] = {}
        self._completed_profiles: List[SourceProcessingProfile] = []
        self._max_completed_profiles = 1000  # Keep last 1000 for reporting
        self._stage_durations: Dict[str, List[float]] = defaultdict(list)

    def start_source_profile(
        self,
        source_id: str,
        source_type: str,
        file_type: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        queue_start_time: Optional[float] = None
    ) -> SourceProcessingProfile:
        """Start profiling a source processing operation"""
        profile = SourceProcessingProfile(
            source_id=source_id,
            source_type=source_type,
            file_type=file_type,
            file_size_bytes=file_size_bytes
        )

        # Calculate queue time if provided
        if queue_start_time:
            profile.queue_time_ms = (profile.start_time - queue_start_time) * 1000

        self._profiles[source_id] = profile

        # Record metrics
        CONCURRENT_PROCESSING.inc()
        if file_size_bytes:
            SOURCE_UPLOAD_SIZE.labels(source_type=source_type).observe(file_size_bytes)

        logger.debug(
            "Started source profiling",
            source_id=source_id,
            source_type=source_type,
            file_type=file_type
        )

        return profile

    def complete_source_profile(
        self,
        source_id: str,
        success: bool = True,
        error: Optional[str] = None
    ) -> Optional[SourceProcessingProfile]:
        """Complete profiling a source processing operation"""
        profile = self._profiles.pop(source_id, None)
        if not profile:
            logger.warning("No profile found for source", source_id=source_id)
            return None

        profile.success = success
        profile.error = error
        profile.complete()

        # Store completed profile
        self._completed_profiles.append(profile)
        if len(self._completed_profiles) > self._max_completed_profiles:
            self._completed_profiles = self._completed_profiles[-self._max_completed_profiles:]

        # Record metrics
        CONCURRENT_PROCESSING.dec()
        SOURCE_PROCESSING_DURATION.labels(
            source_type=profile.source_type,
            file_type=profile.file_type or "unknown",
            status="success" if success else "failure"
        ).observe(profile.total_duration_ms / 1000)

        if profile.queue_time_ms:
            SOURCE_QUEUE_TIME.labels(
                priority="normal",
                queue="sources"
            ).observe(profile.queue_time_ms / 1000)

        logger.info(
            "Completed source profiling",
            source_id=source_id,
            duration_ms=profile.total_duration_ms,
            success=success,
            stages=len(profile.stages)
        )

        return profile

    @asynccontextmanager
    async def profile_stage(
        self,
        source_id: str,
        stage_name: str,
        track_memory: bool = True
    ):
        """
        Context manager for profiling a processing stage.

        Usage:
            async with profiler.profile_stage(source_id, "parsing"):
                await parse_document()
        """
        profile = self._profiles.get(source_id)

        stage = StageProfile(
            stage_name=stage_name,
            start_time=time.time(),
            memory_start_mb=psutil.Process().memory_info().rss / 1024 / 1024 if track_memory else None
        )

        try:
            yield stage
            stage.complete()
        except Exception as e:
            stage.end_time = time.time()
            stage.duration_ms = (stage.end_time - stage.start_time) * 1000
            stage.success = False
            stage.error = str(e)
            raise
        finally:
            if profile:
                profile.stages.append(stage)

            # Track stage duration
            self._stage_durations[stage_name].append(stage.duration_ms)

            # Record Prometheus metric
            if profile:
                SOURCE_PROCESSING_STAGES.labels(
                    stage=stage_name,
                    source_type=profile.source_type
                ).observe(stage.duration_ms / 1000)

            logger.debug(
                "Stage completed",
                stage=stage_name,
                duration_ms=stage.duration_ms,
                success=stage.success
            )

    @asynccontextmanager
    async def profile_rag_query(
        self,
        project_id: str,
        include_global: bool = True
    ):
        """
        Context manager for profiling RAG queries.

        Usage:
            async with profiler.profile_rag_query(project_id) as ctx:
                results = await rag_service.query(...)
                ctx.set_results(results)
        """
        start_time = time.time()
        context = {"chunks_retrieved": 0, "has_citations": False}

        class QueryContext:
            def set_results(self, results: Dict[str, Any]):
                context["chunks_retrieved"] = results.get("chunks_count", 0)
                context["has_citations"] = bool(results.get("citations"))

        ctx = QueryContext()

        try:
            yield ctx
        finally:
            duration_seconds = time.time() - start_time

            RAG_QUERY_DURATION.labels(
                include_global=str(include_global).lower(),
                has_citations=str(context["has_citations"]).lower()
            ).observe(duration_seconds)

            if context["chunks_retrieved"] > 0:
                RAG_RETRIEVAL_COUNT.labels(source_type="project").observe(context["chunks_retrieved"])

            logger.debug(
                "RAG query completed",
                project_id=project_id,
                duration_s=round(duration_seconds, 3),
                chunks_retrieved=context["chunks_retrieved"]
            )

    def get_performance_report(
        self,
        period_hours: int = 24
    ) -> PerformanceReport:
        """Generate aggregated performance report"""
        now = datetime.utcnow()
        period_start = now - timedelta(hours=period_hours)

        # Filter profiles within period
        relevant_profiles = [
            p for p in self._completed_profiles
            if p.end_time and datetime.fromtimestamp(p.end_time) >= period_start
        ]

        if not relevant_profiles:
            return PerformanceReport(
                period_start=period_start,
                period_end=now
            )

        durations = [p.total_duration_ms for p in relevant_profiles if p.total_duration_ms]
        queue_times = [p.queue_time_ms for p in relevant_profiles if p.queue_time_ms]

        # Calculate percentiles
        sorted_durations = sorted(durations)
        _n = len(sorted_durations)  # noqa: F841

        def percentile(data: List[float], p: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * p)
            return data[min(idx, len(data) - 1)]

        # Group by source type
        by_source_type: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "avg_ms": 0.0, "success_rate": 0.0})
        for p in relevant_profiles:
            st = p.source_type
            by_source_type[st]["count"] += 1
            if p.success:
                by_source_type[st]["success_rate"] = (
                    by_source_type[st].get("success_count", 0) + 1
                ) / by_source_type[st]["count"]

        # Calculate source type averages
        for st, stats in by_source_type.items():
            st_durations = [
                p.total_duration_ms for p in relevant_profiles
                if p.source_type == st and p.total_duration_ms
            ]
            stats["avg_ms"] = statistics.mean(st_durations) if st_durations else 0.0

        # Stage breakdown
        stage_breakdown: Dict[str, Dict[str, float]] = {}
        for stage_name, stage_durations in self._stage_durations.items():
            if stage_durations:
                stage_breakdown[stage_name] = {
                    "avg_ms": statistics.mean(stage_durations),
                    "p95_ms": percentile(sorted(stage_durations), 0.95),
                    "count": len(stage_durations)
                }

        return PerformanceReport(
            period_start=period_start,
            period_end=now,
            total_sources_processed=len(relevant_profiles),
            success_count=sum(1 for p in relevant_profiles if p.success),
            failure_count=sum(1 for p in relevant_profiles if not p.success),
            avg_duration_ms=statistics.mean(durations) if durations else 0.0,
            p50_duration_ms=percentile(sorted_durations, 0.50),
            p95_duration_ms=percentile(sorted_durations, 0.95),
            p99_duration_ms=percentile(sorted_durations, 0.99),
            max_duration_ms=max(durations) if durations else 0.0,
            min_duration_ms=min(durations) if durations else 0.0,
            avg_queue_time_ms=statistics.mean(queue_times) if queue_times else 0.0,
            by_source_type=dict(by_source_type),
            stage_breakdown=stage_breakdown
        )

    def profile_function(self, stage_name: str):
        """
        Decorator for profiling async functions.

        Usage:
            @profiler.profile_function("embedding_generation")
            async def generate_embeddings(text: str):
                ...
        """
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                start_time = time.time()
                memory_start = psutil.Process().memory_info().rss / 1024 / 1024

                try:
                    result = await func(*args, **kwargs)
                    success = True
                except Exception:
                    success = False
                    raise
                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    memory_delta = (psutil.Process().memory_info().rss / 1024 / 1024) - memory_start

                    self._stage_durations[stage_name].append(duration_ms)

                    logger.debug(
                        "Function profiled",
                        function=func.__name__,
                        stage=stage_name,
                        duration_ms=round(duration_ms, 2),
                        memory_delta_mb=round(memory_delta, 2),
                        success=success
                    )

                return result
            return wrapper
        return decorator


# ============================================================================
# Singleton Instance
# ============================================================================

_profiler: Optional[PerformanceProfiler] = None


def get_performance_profiler() -> PerformanceProfiler:
    """Get or create singleton PerformanceProfiler instance"""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
    return _profiler


# ============================================================================
# Benchmark Utilities
# ============================================================================

class Benchmark:
    """
    Simple benchmark utility for timing operations.

    Usage:
        bench = Benchmark("PDF processing")
        with bench.section("parsing"):
            parse_pdf()
        with bench.section("chunking"):
            chunk_text()
        logger.info("benchmark_complete", **bench.report())
    """

    def __init__(self, name: str):
        self.name = name
        self.sections: Dict[str, float] = {}
        self.start_time = time.time()
        self._current_section: Optional[str] = None
        self._section_start: Optional[float] = None

    @asynccontextmanager
    async def section(self, name: str):
        """Time a section of code"""
        start = time.time()
        try:
            yield
        finally:
            self.sections[name] = (time.time() - start) * 1000

    def report(self) -> Dict[str, Any]:
        """Generate benchmark report"""
        total_ms = (time.time() - self.start_time) * 1000
        return {
            "benchmark": self.name,
            "total_ms": round(total_ms, 2),
            "sections": {k: round(v, 2) for k, v in self.sections.items()},
            "overhead_ms": round(total_ms - sum(self.sections.values()), 2)
        }


# ============================================================================
# Performance Thresholds
# ============================================================================

# Target performance thresholds (Task 69)
PERFORMANCE_THRESHOLDS = {
    "pdf_processing_max_seconds": 60,
    "youtube_processing_max_seconds": 30,
    "rag_query_max_seconds": 3,
    "success_rate_min_percent": 95,
    "queue_time_max_seconds": 10,
    "embedding_generation_max_seconds": 5,
}


def check_performance_thresholds(report: PerformanceReport) -> Dict[str, bool]:
    """Check if performance metrics meet thresholds"""
    checks = {}

    # Success rate check
    if report.total_sources_processed > 0:
        success_rate = (report.success_count / report.total_sources_processed) * 100
        checks["success_rate"] = success_rate >= PERFORMANCE_THRESHOLDS["success_rate_min_percent"]

    # Queue time check
    checks["queue_time"] = (
        report.avg_queue_time_ms / 1000 <= PERFORMANCE_THRESHOLDS["queue_time_max_seconds"]
    )

    # P95 latency check (using RAG threshold as general benchmark)
    checks["p95_latency"] = (
        report.p95_duration_ms / 1000 <= PERFORMANCE_THRESHOLDS["pdf_processing_max_seconds"]
    )

    return checks
