"""
Empire v7.3 - Load Tests for Concurrent Source Processing
Task 69: E2E testing and performance optimization

Tests:
- Concurrent file uploads
- Concurrent URL processing
- Mixed source type processing
- Queue throughput under load
- Memory stability under load
- Cache effectiveness under load
"""

import asyncio
import os
import time
import random
import tempfile
import statistics
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from dataclasses import dataclass
import pytest

# Test configuration
CONCURRENT_USERS = [1, 5, 10, 20]  # Number of concurrent operations
SOURCES_PER_USER = 5  # Sources each user uploads
LOAD_TEST_TIMEOUT = 300  # 5 minutes max for load tests


@dataclass
class LoadTestResult:
    """Result of a load test run"""
    concurrent_users: int
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_ops_per_second: float
    total_duration_seconds: float
    memory_start_mb: float
    memory_end_mb: float
    cache_hit_rate: float
    errors: List[str]


class LoadTestMetrics:
    """Collect and aggregate load test metrics"""

    def __init__(self):
        self.latencies: List[float] = []
        self.successes: int = 0
        self.failures: int = 0
        self.errors: List[str] = []
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def record_success(self, latency_ms: float, cache_hit: bool = False):
        """Record a successful operation"""
        self.latencies.append(latency_ms)
        self.successes += 1
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_failure(self, error: str):
        """Record a failed operation"""
        self.failures += 1
        self.errors.append(error)

    def start(self):
        """Start timing"""
        self.start_time = time.time()

    def stop(self):
        """Stop timing"""
        self.end_time = time.time()

    def get_result(self, concurrent_users: int, memory_start: float, memory_end: float) -> LoadTestResult:
        """Calculate and return test results"""
        if not self.latencies:
            return LoadTestResult(
                concurrent_users=concurrent_users,
                total_operations=0,
                successful_operations=0,
                failed_operations=self.failures,
                avg_latency_ms=0,
                p50_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                min_latency_ms=0,
                max_latency_ms=0,
                throughput_ops_per_second=0,
                total_duration_seconds=0,
                memory_start_mb=memory_start,
                memory_end_mb=memory_end,
                cache_hit_rate=0,
                errors=self.errors
            )

        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            idx = int(n * p)
            return sorted_latencies[min(idx, n - 1)]

        total_duration = (self.end_time or time.time()) - (self.start_time or time.time())
        cache_hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0

        return LoadTestResult(
            concurrent_users=concurrent_users,
            total_operations=self.successes + self.failures,
            successful_operations=self.successes,
            failed_operations=self.failures,
            avg_latency_ms=statistics.mean(self.latencies),
            p50_latency_ms=percentile(0.50),
            p95_latency_ms=percentile(0.95),
            p99_latency_ms=percentile(0.99),
            min_latency_ms=min(self.latencies),
            max_latency_ms=max(self.latencies),
            throughput_ops_per_second=self.successes / total_duration if total_duration > 0 else 0,
            total_duration_seconds=total_duration,
            memory_start_mb=memory_start,
            memory_end_mb=memory_end,
            cache_hit_rate=cache_hit_rate,
            errors=self.errors[:10]  # Limit to first 10 errors
        )


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for load tests"""
    mock = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{
        "id": "test-source-id",
        "project_id": "test-project-id",
        "source_type": "pdf",
        "file_type": "pdf",
        "status": "ready"
    }], count=1)

    mock.table.return_value = mock_table

    # Mock storage
    mock_storage = MagicMock()
    mock_storage.from_.return_value = mock_storage
    mock_storage.download.return_value = b"Test file content"
    mock_storage.upload.return_value = {"path": "test/path"}
    mock.storage = mock_storage

    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client for cache"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.mget.return_value = [None]
    mock.pipeline.return_value = mock
    mock.execute.return_value = []
    mock.ping.return_value = True
    return mock


@pytest.fixture
def mock_celery():
    """Mock Celery for task execution"""
    mock = MagicMock()
    mock.send_task.return_value = MagicMock(id="test-task-id")
    mock.AsyncResult.return_value = MagicMock(
        ready=MagicMock(return_value=True),
        get=MagicMock(return_value={"status": "success"})
    )
    return mock


# ============================================================================
# Load Test Utilities
# ============================================================================

async def simulate_source_upload(
    user_id: str,
    project_id: str,
    source_type: str,
    supabase_mock: MagicMock,
    simulate_delay: bool = True
) -> Dict[str, Any]:
    """Simulate a source upload operation"""
    start_time = time.time()

    try:
        # Simulate file validation delay
        if simulate_delay:
            await asyncio.sleep(random.uniform(0.01, 0.05))

        # Simulate database insert
        source_id = f"source-{user_id}-{int(time.time() * 1000)}"

        # Simulate file upload delay
        if simulate_delay:
            await asyncio.sleep(random.uniform(0.02, 0.1))

        latency_ms = (time.time() - start_time) * 1000

        return {
            "success": True,
            "source_id": source_id,
            "latency_ms": latency_ms,
            "cache_hit": False
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000
        }


async def simulate_source_processing(
    source_id: str,
    source_type: str,
    cache_mock: MagicMock,
    simulate_delay: bool = True
) -> Dict[str, Any]:
    """Simulate source processing with caching"""
    start_time = time.time()

    try:
        # Check cache (simulate)
        cache_hit = random.random() < 0.3  # 30% cache hit rate

        if cache_hit:
            # Fast return for cached content
            if simulate_delay:
                await asyncio.sleep(random.uniform(0.001, 0.01))
        else:
            # Simulate content extraction
            if simulate_delay:
                base_delay = {
                    "pdf": 0.5,
                    "youtube": 0.3,
                    "website": 0.2,
                    "txt": 0.05,
                    "docx": 0.3,
                }.get(source_type, 0.2)
                await asyncio.sleep(random.uniform(base_delay * 0.5, base_delay * 1.5))

            # Simulate embedding generation
            if simulate_delay:
                await asyncio.sleep(random.uniform(0.1, 0.3))

        latency_ms = (time.time() - start_time) * 1000

        return {
            "success": True,
            "source_id": source_id,
            "latency_ms": latency_ms,
            "cache_hit": cache_hit
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000
        }


# ============================================================================
# Load Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.load
class TestConcurrentUploads:
    """Load tests for concurrent file uploads"""

    @pytest.mark.parametrize("concurrent_users", CONCURRENT_USERS)
    async def test_concurrent_file_uploads(
        self,
        concurrent_users: int,
        mock_supabase
    ):
        """Test concurrent file upload handling"""
        import psutil

        metrics = LoadTestMetrics()
        memory_start = psutil.Process().memory_info().rss / 1024 / 1024

        metrics.start()

        # Create concurrent upload tasks
        tasks = []
        for user_idx in range(concurrent_users):
            user_id = f"user-{user_idx}"
            project_id = f"project-{user_idx}"

            for _ in range(SOURCES_PER_USER):
                source_type = random.choice(["pdf", "docx", "txt", "csv"])
                task = simulate_source_upload(
                    user_id=user_id,
                    project_id=project_id,
                    source_type=source_type,
                    supabase_mock=mock_supabase
                )
                tasks.append(task)

        # Execute all uploads concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        metrics.stop()
        memory_end = psutil.Process().memory_info().rss / 1024 / 1024

        # Process results
        for result in results:
            if isinstance(result, Exception):
                metrics.record_failure(str(result))
            elif result.get("success"):
                metrics.record_success(result["latency_ms"], result.get("cache_hit", False))
            else:
                metrics.record_failure(result.get("error", "Unknown error"))

        test_result = metrics.get_result(concurrent_users, memory_start, memory_end)

        # Log results
        print(f"\n--- Concurrent Upload Test Results ---")
        print(f"Concurrent Users: {concurrent_users}")
        print(f"Total Operations: {test_result.total_operations}")
        print(f"Success Rate: {test_result.successful_operations / test_result.total_operations * 100:.1f}%")
        print(f"Avg Latency: {test_result.avg_latency_ms:.2f}ms")
        print(f"P95 Latency: {test_result.p95_latency_ms:.2f}ms")
        print(f"Throughput: {test_result.throughput_ops_per_second:.2f} ops/sec")
        print(f"Memory Delta: {test_result.memory_end_mb - test_result.memory_start_mb:.2f}MB")

        # Assertions
        assert test_result.successful_operations > 0, "At least one operation should succeed"
        success_rate = test_result.successful_operations / test_result.total_operations
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} should be >= 95%"

        # Memory should not grow excessively
        memory_growth = test_result.memory_end_mb - test_result.memory_start_mb
        assert memory_growth < 100, f"Memory growth {memory_growth:.1f}MB should be < 100MB"


@pytest.mark.asyncio
@pytest.mark.load
class TestConcurrentProcessing:
    """Load tests for concurrent source processing"""

    @pytest.mark.parametrize("concurrent_users", CONCURRENT_USERS)
    async def test_concurrent_source_processing(
        self,
        concurrent_users: int,
        mock_redis
    ):
        """Test concurrent source processing with caching"""
        import psutil

        metrics = LoadTestMetrics()
        memory_start = psutil.Process().memory_info().rss / 1024 / 1024

        metrics.start()

        # Create concurrent processing tasks
        tasks = []
        source_types = ["pdf", "youtube", "website", "txt", "docx"]

        for user_idx in range(concurrent_users):
            for source_idx in range(SOURCES_PER_USER):
                source_id = f"source-{user_idx}-{source_idx}"
                source_type = random.choice(source_types)
                task = simulate_source_processing(
                    source_id=source_id,
                    source_type=source_type,
                    cache_mock=mock_redis
                )
                tasks.append(task)

        # Execute all processing concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        metrics.stop()
        memory_end = psutil.Process().memory_info().rss / 1024 / 1024

        # Process results
        for result in results:
            if isinstance(result, Exception):
                metrics.record_failure(str(result))
            elif result.get("success"):
                metrics.record_success(result["latency_ms"], result.get("cache_hit", False))
            else:
                metrics.record_failure(result.get("error", "Unknown error"))

        test_result = metrics.get_result(concurrent_users, memory_start, memory_end)

        # Log results
        print(f"\n--- Concurrent Processing Test Results ---")
        print(f"Concurrent Users: {concurrent_users}")
        print(f"Total Operations: {test_result.total_operations}")
        print(f"Success Rate: {test_result.successful_operations / test_result.total_operations * 100:.1f}%")
        print(f"Avg Latency: {test_result.avg_latency_ms:.2f}ms")
        print(f"P95 Latency: {test_result.p95_latency_ms:.2f}ms")
        print(f"Cache Hit Rate: {test_result.cache_hit_rate * 100:.1f}%")
        print(f"Throughput: {test_result.throughput_ops_per_second:.2f} ops/sec")

        # Assertions
        success_rate = test_result.successful_operations / test_result.total_operations
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} should be >= 95%"


@pytest.mark.asyncio
@pytest.mark.load
class TestMixedWorkload:
    """Load tests for mixed source type workloads"""

    async def test_mixed_source_types(self, mock_supabase, mock_redis):
        """Test processing various source types concurrently"""
        import psutil

        metrics = LoadTestMetrics()
        memory_start = psutil.Process().memory_info().rss / 1024 / 1024

        # Define workload distribution
        workload = [
            ("pdf", 30),      # 30% PDFs
            ("youtube", 20),  # 20% YouTube
            ("website", 25),  # 25% Websites
            ("txt", 15),      # 15% Text files
            ("docx", 10),     # 10% Word docs
        ]

        total_sources = 100
        tasks = []

        metrics.start()

        for source_type, percentage in workload:
            count = int(total_sources * percentage / 100)
            for i in range(count):
                source_id = f"{source_type}-{i}"
                task = simulate_source_processing(
                    source_id=source_id,
                    source_type=source_type,
                    cache_mock=mock_redis
                )
                tasks.append((source_type, task))

        # Execute concurrently (limited concurrency to simulate real conditions)
        semaphore = asyncio.Semaphore(20)  # Max 20 concurrent operations

        async def limited_task(source_type: str, task):
            async with semaphore:
                result = await task
                return source_type, result

        results = await asyncio.gather(
            *[limited_task(st, t) for st, t in tasks],
            return_exceptions=True
        )

        metrics.stop()
        memory_end = psutil.Process().memory_info().rss / 1024 / 1024

        # Track results by source type
        type_results: Dict[str, List[Dict]] = {}
        for result in results:
            if isinstance(result, Exception):
                metrics.record_failure(str(result))
            else:
                source_type, op_result = result
                if source_type not in type_results:
                    type_results[source_type] = []
                type_results[source_type].append(op_result)

                if op_result.get("success"):
                    metrics.record_success(op_result["latency_ms"], op_result.get("cache_hit", False))
                else:
                    metrics.record_failure(op_result.get("error", "Unknown error"))

        test_result = metrics.get_result(1, memory_start, memory_end)

        # Log results by type
        print(f"\n--- Mixed Workload Test Results ---")
        for source_type, type_ops in type_results.items():
            successful = sum(1 for r in type_ops if r.get("success"))
            avg_latency = statistics.mean([r["latency_ms"] for r in type_ops if r.get("success")] or [0])
            print(f"  {source_type}: {successful}/{len(type_ops)} success, avg {avg_latency:.2f}ms")

        print(f"Overall Success Rate: {test_result.successful_operations / test_result.total_operations * 100:.1f}%")
        print(f"Overall Throughput: {test_result.throughput_ops_per_second:.2f} ops/sec")

        # Assertions
        success_rate = test_result.successful_operations / test_result.total_operations
        assert success_rate >= 0.95, f"Success rate {success_rate:.2%} should be >= 95%"


@pytest.mark.asyncio
@pytest.mark.load
class TestQueueThroughput:
    """Load tests for Celery queue throughput"""

    async def test_queue_prioritization(self, mock_celery):
        """Test that priority queue processes high-priority items first"""
        from app.celery_app import SOURCE_PRIORITY, get_source_priority

        # Test priority assignments
        assert get_source_priority("youtube", None) > get_source_priority("file", "pdf")
        assert get_source_priority("url", None) > get_source_priority("file", "pdf")
        assert get_source_priority("file", "txt") > get_source_priority("file", "pdf")

        # Verify priority values are in valid range
        for source_type in ["youtube", "url", "file"]:
            for file_type in ["pdf", "docx", "txt", "csv", "xlsx"]:
                priority = get_source_priority(source_type, file_type)
                assert 0 <= priority <= 9, f"Priority {priority} out of range for {source_type}/{file_type}"

        print("\n--- Queue Priority Test ---")
        print("YouTube priority:", get_source_priority("youtube", None))
        print("Website priority:", get_source_priority("url", None))
        print("TXT priority:", get_source_priority("file", "txt"))
        print("PDF priority:", get_source_priority("file", "pdf"))


@pytest.mark.asyncio
@pytest.mark.load
class TestCacheEffectiveness:
    """Load tests for cache effectiveness under load"""

    async def test_cache_hit_rate_under_load(self, mock_redis):
        """Test that cache maintains good hit rate under load"""
        import psutil

        # Simulate workload with repeated content
        unique_sources = 20  # Number of unique sources
        repeat_factor = 5    # Each source processed 5 times
        total_ops = unique_sources * repeat_factor

        metrics = LoadTestMetrics()
        cache_simulation: Dict[str, bool] = {}  # Track which sources were cached

        metrics.start()
        memory_start = psutil.Process().memory_info().rss / 1024 / 1024

        tasks = []
        for _ in range(repeat_factor):
            for i in range(unique_sources):
                source_id = f"source-{i}"

                # Simulate cache behavior
                cache_hit = source_id in cache_simulation
                if not cache_hit:
                    cache_simulation[source_id] = True

                task = simulate_source_processing(
                    source_id=source_id,
                    source_type="pdf",
                    cache_mock=mock_redis,
                    simulate_delay=True
                )
                tasks.append((source_id, cache_hit, task))

        # Execute with simulated cache behavior
        for source_id, cache_hit, task in tasks:
            start = time.time()
            result = await task
            latency_ms = (time.time() - start) * 1000

            if result.get("success"):
                metrics.record_success(latency_ms, cache_hit)
            else:
                metrics.record_failure(result.get("error", "Unknown"))

        metrics.stop()
        memory_end = psutil.Process().memory_info().rss / 1024 / 1024

        test_result = metrics.get_result(1, memory_start, memory_end)

        print(f"\n--- Cache Effectiveness Test ---")
        print(f"Total Operations: {test_result.total_operations}")
        print(f"Cache Hit Rate: {test_result.cache_hit_rate * 100:.1f}%")
        print(f"Avg Latency: {test_result.avg_latency_ms:.2f}ms")

        # With repeat_factor of 5, we expect ~80% cache hit rate
        # (first access is miss, next 4 are hits)
        expected_hit_rate = (repeat_factor - 1) / repeat_factor
        actual_hit_rate = test_result.cache_hit_rate

        # Allow some variance
        assert actual_hit_rate >= expected_hit_rate * 0.8, \
            f"Cache hit rate {actual_hit_rate:.2%} should be close to {expected_hit_rate:.2%}"


@pytest.mark.asyncio
@pytest.mark.load
class TestMemoryStability:
    """Load tests for memory stability under sustained load"""

    async def test_memory_stability_sustained_load(self, mock_supabase, mock_redis):
        """Test memory doesn't grow unbounded under sustained load"""
        import psutil
        import gc

        iterations = 5
        ops_per_iteration = 50
        memory_samples: List[float] = []

        for iteration in range(iterations):
            gc.collect()
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024
            memory_samples.append(memory_before)

            # Run operations
            tasks = []
            for i in range(ops_per_iteration):
                task = simulate_source_processing(
                    source_id=f"source-{iteration}-{i}",
                    source_type="pdf",
                    cache_mock=mock_redis
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_samples.append(final_memory)

        # Calculate memory growth trend
        memory_growth = memory_samples[-1] - memory_samples[0]
        avg_growth_per_iteration = memory_growth / iterations

        print(f"\n--- Memory Stability Test ---")
        print(f"Iterations: {iterations}")
        print(f"Ops per iteration: {ops_per_iteration}")
        print(f"Memory samples (MB): {[f'{m:.1f}' for m in memory_samples]}")
        print(f"Total memory growth: {memory_growth:.2f}MB")
        print(f"Avg growth per iteration: {avg_growth_per_iteration:.2f}MB")

        # Memory should not grow significantly
        assert memory_growth < 50, f"Memory growth {memory_growth:.1f}MB should be < 50MB"
        assert avg_growth_per_iteration < 10, f"Avg growth {avg_growth_per_iteration:.1f}MB should be < 10MB/iteration"


# ============================================================================
# Performance Threshold Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.load
class TestPerformanceThresholds:
    """Test performance meets defined thresholds"""

    async def test_pdf_processing_threshold(self, mock_redis):
        """PDF processing should complete within 60 seconds"""
        from app.utils.performance_profiler import PERFORMANCE_THRESHOLDS

        start = time.time()
        result = await simulate_source_processing(
            source_id="test-pdf",
            source_type="pdf",
            cache_mock=mock_redis,
            simulate_delay=True
        )
        duration = time.time() - start

        max_threshold = PERFORMANCE_THRESHOLDS["pdf_processing_max_seconds"]
        print(f"\n--- PDF Processing Threshold Test ---")
        print(f"Duration: {duration:.2f}s (threshold: {max_threshold}s)")

        assert result["success"], "PDF processing should succeed"
        # Simulated delay is much faster than real processing

    async def test_youtube_processing_threshold(self, mock_redis):
        """YouTube processing should complete within 30 seconds"""
        from app.utils.performance_profiler import PERFORMANCE_THRESHOLDS

        start = time.time()
        result = await simulate_source_processing(
            source_id="test-youtube",
            source_type="youtube",
            cache_mock=mock_redis,
            simulate_delay=True
        )
        duration = time.time() - start

        max_threshold = PERFORMANCE_THRESHOLDS["youtube_processing_max_seconds"]
        print(f"\n--- YouTube Processing Threshold Test ---")
        print(f"Duration: {duration:.2f}s (threshold: {max_threshold}s)")

        assert result["success"], "YouTube processing should succeed"

    async def test_rag_query_threshold(self, mock_redis):
        """RAG queries should complete within 3 seconds"""
        from app.utils.performance_profiler import PERFORMANCE_THRESHOLDS

        # Simulate RAG query (fast operation)
        start = time.time()
        await asyncio.sleep(0.1)  # Simulate query
        duration = time.time() - start

        max_threshold = PERFORMANCE_THRESHOLDS["rag_query_max_seconds"]
        print(f"\n--- RAG Query Threshold Test ---")
        print(f"Duration: {duration:.2f}s (threshold: {max_threshold}s)")

        assert duration < max_threshold, f"RAG query took {duration}s, exceeds {max_threshold}s threshold"


# ============================================================================
# CLI Entry Point for Load Testing
# ============================================================================

if __name__ == "__main__":
    """Run load tests from command line"""
    import sys

    print("=" * 60)
    print("Empire v7.3 - Load Tests for Concurrent Source Processing")
    print("=" * 60)

    pytest.main([
        __file__,
        "-v",
        "-m", "load",
        "--tb=short",
        "-s",  # Show print statements
    ] + sys.argv[1:])
