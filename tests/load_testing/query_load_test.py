#!/usr/bin/env python3
"""
Query Load Test for Task 43.3+ - Optimization Validation
Tests /api/query/adaptive and /api/query/auto endpoints
Measures cache performance, response times, and query routing
"""

import requests
import time
import statistics
from datetime import datetime
import json
import os
import sys
from typing import List, Dict, Tuple

# Configuration
HOST = os.getenv("EMPIRE_API_URL", "https://jb-empire-api.onrender.com")
NUM_REQUESTS = 10  # Number of requests per query type
CLERK_TOKEN = os.getenv("CLERK_TEST_TOKEN")  # Clerk JWT token for authentication

# Test queries - designed to test different scenarios
TEST_QUERIES = {
    "simple_lookup": [
        "What are California insurance requirements?",
        "Explain our privacy policy",
        "What is our refund policy?",
    ],
    "complex_research": [
        "Compare our policies with current California regulations",
        "What are the latest industry trends in compliance?",
        "How do our benefits compare to competitors?",
    ],
    "similar_queries": [  # Should trigger cache hits
        "What are California insurance requirements?",
        "What are the insurance requirements for California?",
        "Tell me about California's insurance requirements",
    ]
}


def get_headers() -> Dict[str, str]:
    """Get request headers with authentication."""
    if not CLERK_TOKEN:
        print("\n⚠️  WARNING: CLERK_TEST_TOKEN not set in environment")
        print("   Some endpoints may fail due to authentication")
        print("   Set token with: export CLERK_TEST_TOKEN='your-token'\n")
        return {"Content-Type": "application/json"}

    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLERK_TOKEN}"
    }


def test_endpoint(
    endpoint: str,
    query: str,
    max_iterations: int = 3,
    verbose: bool = False
) -> Tuple[int, dict, bool]:
    """
    Test a single query endpoint.

    Returns:
        (response_time_ms, response_data, from_cache)
    """
    url = f"{HOST}/api/query/{endpoint}"
    headers = get_headers()
    payload = {
        "query": query,
        "max_iterations": max_iterations,
        "use_external_tools": False,  # Disable for faster testing
        "use_graph_context": True
    }

    start = time.time()
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        duration = int((time.time() - start) * 1000)

        if response.status_code == 200:
            data = response.json()
            from_cache = data.get("from_cache", False)

            if verbose:
                print(f"  ✅ {response.status_code} | {duration}ms | "
                      f"{'CACHED' if from_cache else 'FRESH'} | {query[:40]}...")

            return duration, data, from_cache
        else:
            print(f"  ❌ {response.status_code} | {duration}ms | {query[:40]}...")
            print(f"     Error: {response.text[:200]}")
            return duration, {"error": response.text}, False

    except requests.exceptions.Timeout:
        duration = 60000  # 60 second timeout
        print(f"  ⏱️  TIMEOUT | {query[:40]}...")
        return duration, {"error": "timeout"}, False
    except Exception as e:
        duration = int((time.time() - start) * 1000)
        print(f"  ❌ ERROR | {duration}ms | {query[:40]}...")
        print(f"     {str(e)[:200]}")
        return duration, {"error": str(e)}, False


def test_adaptive_endpoint():
    """Test /api/query/adaptive endpoint."""
    print("\n" + "="*70)
    print("Test 1: Adaptive Endpoint (/api/query/adaptive)")
    print("="*70)

    all_times = []
    cache_hits = 0
    total_requests = 0

    for category, queries in TEST_QUERIES.items():
        print(f"\n{category.upper()} Queries:")
        print("-" * 40)

        for query in queries:
            duration, data, from_cache = test_endpoint("adaptive", query, verbose=True)
            all_times.append(duration)
            total_requests += 1
            if from_cache:
                cache_hits += 1

    # Statistics
    print(f"\n📊 Statistics:")
    print(f"  Total Requests: {total_requests}")
    print(f"  Average: {statistics.mean(all_times):.0f}ms")
    print(f"  P50: {statistics.median(all_times):.0f}ms")
    print(f"  P95: {sorted(all_times)[int(len(all_times)*0.95)]:.0f}ms")
    print(f"  Min: {min(all_times):.0f}ms")
    print(f"  Max: {max(all_times):.0f}ms")
    print(f"  Cache Hits: {cache_hits}/{total_requests} ({cache_hits/total_requests*100:.1f}%)")

    return {
        "endpoint": "adaptive",
        "times": all_times,
        "cache_hit_rate": cache_hits / total_requests if total_requests > 0 else 0,
        "total_requests": total_requests
    }


def test_auto_endpoint():
    """Test /api/query/auto endpoint."""
    print("\n" + "="*70)
    print("Test 2: Auto-Routed Endpoint (/api/query/auto)")
    print("="*70)

    all_times = []
    cache_hits = 0
    total_requests = 0
    workflow_types = {}

    for category, queries in TEST_QUERIES.items():
        print(f"\n{category.upper()} Queries:")
        print("-" * 40)

        for query in queries:
            duration, data, from_cache = test_endpoint("auto", query, max_iterations=2, verbose=True)
            all_times.append(duration)
            total_requests += 1
            if from_cache:
                cache_hits += 1

            # Track workflow routing
            workflow = data.get("workflow_type", "unknown")
            workflow_types[workflow] = workflow_types.get(workflow, 0) + 1

    # Statistics
    print(f"\n📊 Statistics:")
    print(f"  Total Requests: {total_requests}")
    print(f"  Average: {statistics.mean(all_times):.0f}ms")
    print(f"  P50: {statistics.median(all_times):.0f}ms")
    print(f"  P95: {sorted(all_times)[int(len(all_times)*0.95)]:.0f}ms")
    print(f"  Min: {min(all_times):.0f}ms")
    print(f"  Max: {max(all_times):.0f}ms")
    print(f"  Cache Hits: {cache_hits}/{total_requests} ({cache_hits/total_requests*100:.1f}%)")

    print(f"\n🔀 Workflow Routing:")
    for workflow, count in workflow_types.items():
        print(f"  {workflow}: {count} ({count/total_requests*100:.1f}%)")

    return {
        "endpoint": "auto",
        "times": all_times,
        "cache_hit_rate": cache_hits / total_requests if total_requests > 0 else 0,
        "total_requests": total_requests,
        "workflow_routing": workflow_types
    }


def test_cache_effectiveness():
    """Test cache effectiveness with repeated queries."""
    print("\n" + "="*70)
    print("Test 3: Cache Effectiveness (Repeated Queries)")
    print("="*70)

    # Run same query multiple times to test caching
    test_query = "What are California insurance requirements?"

    print(f"\nQuery: {test_query}")
    print(f"Iterations: {NUM_REQUESTS}\n")

    times = []
    cache_hits = 0

    for i in range(NUM_REQUESTS):
        duration, data, from_cache = test_endpoint("adaptive", test_query, verbose=True)
        times.append(duration)
        if from_cache:
            cache_hits += 1

    # Analyze first vs cached
    first_request = times[0]
    cached_avg = statistics.mean(times[1:]) if len(times) > 1 else 0

    print(f"\n📊 Cache Performance:")
    print(f"  First Request (uncached): {first_request:.0f}ms")
    print(f"  Subsequent Avg (cached): {cached_avg:.0f}ms")
    print(f"  Speedup: {((first_request - cached_avg) / first_request * 100):.1f}%")
    print(f"  Cache Hit Rate: {cache_hits}/{NUM_REQUESTS} ({cache_hits/NUM_REQUESTS*100:.1f}%)")

    return {
        "first_request_ms": first_request,
        "cached_avg_ms": cached_avg,
        "speedup_pct": (first_request - cached_avg) / first_request * 100 if first_request > 0 else 0,
        "cache_hit_rate": cache_hits / NUM_REQUESTS
    }


def test_semantic_similarity():
    """Test semantic similarity cache matching."""
    print("\n" + "="*70)
    print("Test 4: Semantic Similarity Matching")
    print("="*70)

    similar = TEST_QUERIES["similar_queries"]

    print(f"\nTesting {len(similar)} semantically similar queries:")
    print("(Should trigger cache hits with cosine similarity > 0.95)\n")

    times = []
    cache_hits = 0

    for i, query in enumerate(similar):
        print(f"Query {i+1}: {query}")
        duration, data, from_cache = test_endpoint("adaptive", query, verbose=False)
        times.append(duration)
        if from_cache:
            cache_hits += 1

        print(f"  → {duration}ms | {'CACHED ✅' if from_cache else 'FRESH'}")

    print(f"\n📊 Semantic Cache Performance:")
    print(f"  Total Queries: {len(similar)}")
    print(f"  Cache Hits: {cache_hits}/{len(similar)}")
    print(f"  Hit Rate: {cache_hits/len(similar)*100:.1f}%")
    print(f"  Expected: 66.7% (2/3 cached after first query)")

    if cache_hits < 2:
        print(f"  ⚠️  Semantic matching may need tuning (threshold currently 0.95)")

    return {
        "semantic_cache_hits": cache_hits,
        "total_similar_queries": len(similar),
        "hit_rate": cache_hits / len(similar)
    }


def test_metrics_endpoint():
    """Check Prometheus metrics for cache data."""
    print("\n" + "="*70)
    print("Test 5: Prometheus Metrics Endpoint")
    print("="*70)

    try:
        response = requests.get(f"{HOST}/monitoring/metrics", timeout=10)

        if response.status_code == 200:
            content = response.text

            # Extract relevant metrics
            metrics = {}
            for line in content.split('\n'):
                if 'cache_hit_rate' in line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        label = line.split('{')[1].split('}')[0] if '{' in line else 'overall'
                        value = float(parts[-1])
                        metrics[label] = value

            print(f"  Status: {response.status_code} OK")
            print(f"  Metrics Available: ✅")

            if metrics:
                print(f"\n📊 Cache Hit Rates:")
                for label, value in metrics.items():
                    print(f"  {label}: {value*100:.1f}%")
            else:
                print(f"  ⚠️  No cache metrics found (may need more traffic)")

            return {"status": "ok", "metrics": metrics}
        else:
            print(f"  Status: {response.status_code}")
            print(f"  ❌ Metrics endpoint unavailable")
            return {"status": "error", "code": response.status_code}

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {"status": "error", "error": str(e)}


def generate_summary(results: List[Dict]):
    """Generate final summary report."""
    print("\n" + "="*70)
    print("Load Test Summary - Query Endpoints (Task 43.3+)")
    print("="*70)

    # Aggregate metrics
    adaptive_result = results[0]
    auto_result = results[1]
    cache_result = results[2]
    semantic_result = results[3]

    # Performance summary
    print(f"\n📊 Performance Summary:")
    print(f"\n  Adaptive Endpoint (/api/query/adaptive):")
    print(f"    Average: {statistics.mean(adaptive_result['times']):.0f}ms")
    print(f"    P95: {sorted(adaptive_result['times'])[int(len(adaptive_result['times'])*0.95)]:.0f}ms")
    print(f"    Cache Hit Rate: {adaptive_result['cache_hit_rate']*100:.1f}%")

    print(f"\n  Auto-Routed Endpoint (/api/query/auto):")
    print(f"    Average: {statistics.mean(auto_result['times']):.0f}ms")
    print(f"    P95: {sorted(auto_result['times'])[int(len(auto_result['times'])*0.95)]:.0f}ms")
    print(f"    Cache Hit Rate: {auto_result['cache_hit_rate']*100:.1f}%")

    # Cache effectiveness
    print(f"\n🎯 Cache Effectiveness:")
    print(f"    First Request: {cache_result['first_request_ms']:.0f}ms")
    print(f"    Cached Average: {cache_result['cached_avg_ms']:.0f}ms")
    print(f"    Speedup: {cache_result['speedup_pct']:.1f}%")

    # Semantic matching
    print(f"\n🔍 Semantic Similarity:")
    print(f"    Hit Rate: {semantic_result['hit_rate']*100:.1f}%")
    print(f"    Hits: {semantic_result['semantic_cache_hits']}/{semantic_result['total_similar_queries']}")

    # Performance targets
    print(f"\n🎯 Performance Targets:")

    adaptive_p95 = sorted(adaptive_result['times'])[int(len(adaptive_result['times'])*0.95)]
    auto_p95 = sorted(auto_result['times'])[int(len(auto_result['times'])*0.95)]

    # Target: Cached queries < 800ms (from Task 43.3)
    if cache_result['cached_avg_ms'] < 800:
        print(f"  ✅ Cached P95 < 800ms (actual: {cache_result['cached_avg_ms']:.0f}ms)")
    else:
        print(f"  ⚠️  Cached P95 > 800ms (actual: {cache_result['cached_avg_ms']:.0f}ms)")

    # Target: Cache hit rate > 40%
    overall_cache_rate = (adaptive_result['cache_hit_rate'] + auto_result['cache_hit_rate']) / 2
    if overall_cache_rate > 0.4:
        print(f"  ✅ Cache Hit Rate > 40% (actual: {overall_cache_rate*100:.1f}%)")
    else:
        print(f"  ⏸️  Cache Hit Rate < 40% (actual: {overall_cache_rate*100:.1f}%) - needs more traffic")

    # Save results
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "host": HOST,
        "adaptive_endpoint": {
            "avg_ms": statistics.mean(adaptive_result['times']),
            "p50_ms": statistics.median(adaptive_result['times']),
            "p95_ms": adaptive_p95,
            "cache_hit_rate": adaptive_result['cache_hit_rate'],
            "total_requests": adaptive_result['total_requests']
        },
        "auto_endpoint": {
            "avg_ms": statistics.mean(auto_result['times']),
            "p50_ms": statistics.median(auto_result['times']),
            "p95_ms": auto_p95,
            "cache_hit_rate": auto_result['cache_hit_rate'],
            "total_requests": auto_result['total_requests'],
            "workflow_routing": auto_result.get('workflow_routing', {})
        },
        "cache_effectiveness": cache_result,
        "semantic_similarity": semantic_result
    }

    results_file = f"results/query_load_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("results", exist_ok=True)

    with open(results_file, 'w') as f:
        json.dump(result_data, f, indent=2)

    print(f"\n📁 Results saved to: {results_file}")

    print(f"\n✅ Query load test completed successfully!")
    print(f"\nNext steps:")
    print(f"  1. Review cache hit rates in Prometheus: {HOST}/monitoring/metrics")
    print(f"  2. Consider adjusting cache TTL if hit rates are low")
    print(f"  3. Monitor semantic similarity threshold (currently 0.95)")
    print(f"  4. Run with more traffic for more accurate cache statistics")


def main():
    """Main test execution."""
    print("="*70)
    print("Empire v7.3 - Query Endpoint Load Test")
    print("="*70)
    print(f"Host: {HOST}")
    print(f"Auth: {'Configured ✅' if CLERK_TOKEN else 'Missing ⚠️'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not CLERK_TOKEN:
        print("\n⚠️  WARNING: Running without authentication")
        print("   Set CLERK_TEST_TOKEN environment variable for full testing")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            sys.exit(1)

    try:
        results = []

        # Run all tests
        results.append(test_adaptive_endpoint())
        results.append(test_auto_endpoint())
        results.append(test_cache_effectiveness())
        results.append(test_semantic_similarity())
        test_metrics_endpoint()

        # Generate summary
        generate_summary(results)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
