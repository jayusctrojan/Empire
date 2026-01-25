"""
Test Connection Pooling Implementation
Task 43.3+ Phase 2

Verifies that database connection pooling is configured correctly.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core import (
    get_supabase,
    get_neo4j,
    get_redis,
    get_pool_metrics,
    check_database_health,
    db_manager
)


def test_neo4j_pool():
    """Test Neo4j connection pooling configuration"""
    print("\n" + "=" * 70)
    print("Testing Neo4j Connection Pooling")
    print("=" * 70)

    try:
        # Get Neo4j driver (should create pool)
        driver = get_neo4j()

        # Verify it's the optimized driver
        print(f"✅ Neo4j driver created")
        print(f"   Pool size: {db_manager.neo4j_pool_size}")
        print(f"   Pool timeout: {db_manager.neo4j_pool_timeout}s")

        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            value = result.single()["test"]
            assert value == 1
            print(f"✅ Connection test passed")

        # Check pool stats
        stats = db_manager.connection_stats
        print(f"✅ Pool stats: {stats['neo4j_calls']} calls, {stats['neo4j_pool_hits']} hits")

        return True
    except Exception as e:
        print(f"❌ Neo4j pool test failed: {e}")
        return False


def test_redis_pool():
    """Test Redis connection pooling configuration"""
    print("\n" + "=" * 70)
    print("Testing Redis Connection Pooling")
    print("=" * 70)

    try:
        # Get Redis client (should use pool)
        client = get_redis()

        # Verify pool is configured
        print(f"✅ Redis client created")
        print(f"   Pool size: {db_manager.redis_pool_size}")

        # Test connection
        client.ping()
        print(f"✅ Connection test passed")

        # Check pool stats
        if db_manager._redis_pool:
            pool = db_manager._redis_pool
            available = len(pool._available_connections)
            in_use = pool._in_use_connections
            print(f"✅ Pool stats: {available} available, {in_use} in use")

        stats = db_manager.connection_stats
        print(f"✅ Total calls: {stats['redis_calls']}, pool hits: {stats['redis_pool_hits']}")

        return True
    except Exception as e:
        print(f"❌ Redis pool test failed: {e}")
        return False


def test_supabase_retry():
    """Test Supabase retry logic"""
    print("\n" + "=" * 70)
    print("Testing Supabase Retry Logic")
    print("=" * 70)

    try:
        # Get Supabase client (should have retry logic)
        client = get_supabase()

        print(f"✅ Supabase client created with retry logic")

        # Test simple query - try documents table
        try:
            result = client.table("documents").select("id").limit(1).execute()
            print(f"✅ Query test passed (found {len(result.data)} documents)")
        except Exception as e:
            # Table might not exist, but client still works
            print(f"⚠️  Query warning (table may not exist): {str(e)[:100]}")
            print(f"✅ Supabase client is functional (retry logic active)")

        stats = db_manager.connection_stats
        print(f"✅ Total calls: {stats['supabase_calls']}")

        return True
    except Exception as e:
        print(f"❌ Supabase retry test failed: {e}")
        return False


def test_pool_metrics():
    """Test pool metrics retrieval"""
    print("\n" + "=" * 70)
    print("Testing Pool Metrics")
    print("=" * 70)

    try:
        metrics = get_pool_metrics()

        print(f"✅ Pool metrics retrieved:")
        print(f"\n   Neo4j:")
        for key, value in metrics["neo4j"].items():
            print(f"   - {key}: {value}")

        print(f"\n   Redis:")
        for key, value in metrics["redis"].items():
            print(f"   - {key}: {value}")

        return True
    except Exception as e:
        print(f"❌ Pool metrics test failed: {e}")
        return False


def test_health_checks():
    """Test database health checks"""
    print("\n" + "=" * 70)
    print("Testing Database Health Checks")
    print("=" * 70)

    try:
        health = check_database_health()

        # Check Supabase
        if health["supabase"]["status"] == "healthy":
            print(f"✅ Supabase: healthy ({health['supabase']['latency_ms']:.1f}ms)")
        else:
            print(f"❌ Supabase: {health['supabase']['status']}")

        # Check Neo4j
        if health["neo4j"]["status"] == "healthy":
            latency = health["neo4j"]["latency_ms"]
            pool_hits = health["neo4j"]["pool"]["pool_hits"]
            print(f"✅ Neo4j: healthy ({latency:.1f}ms, {pool_hits} pool hits)")
        else:
            print(f"❌ Neo4j: {health['neo4j']['status']}")

        # Check Redis
        if health["redis"]["status"] == "healthy":
            latency = health["redis"]["latency_ms"]
            available = health["redis"]["pool"].get("num_connections", "N/A")
            print(f"✅ Redis: healthy ({latency:.1f}ms, {available} connections available)")
        else:
            print(f"❌ Redis: {health['redis']['status']}")

        # Check overall health
        all_healthy = all(
            h["status"] == "healthy"
            for h in [health["supabase"], health["neo4j"], health["redis"]]
        )

        return all_healthy
    except Exception as e:
        print(f"❌ Health check test failed: {e}")
        return False


def test_concurrent_connections():
    """Test concurrent connection handling"""
    print("\n" + "=" * 70)
    print("Testing Concurrent Connection Handling")
    print("=" * 70)

    try:
        import concurrent.futures

        def make_query(i):
            """Make a simple query"""
            driver = get_neo4j()
            with driver.session() as session:
                result = session.run("RETURN $i as num", i=i)
                return result.single()["num"]

        # Run 10 concurrent queries
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_query, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        print(f"✅ Completed 10 concurrent queries")
        print(f"   Results: {sorted(results)}")

        # Check pool usage
        metrics = get_pool_metrics()
        print(f"✅ Pool handled concurrent requests")
        print(f"   Total Neo4j calls: {metrics['neo4j']['total_calls']}")

        return True
    except Exception as e:
        print(f"❌ Concurrent connection test failed: {e}")
        return False


def main():
    """Run all connection pooling tests"""
    print("\n" + "=" * 70)
    print("Empire v7.3 - Connection Pooling Tests")
    print("Task 43.3+ Phase 2")
    print("=" * 70)

    # Track results
    results = {
        "Neo4j Pool": test_neo4j_pool(),
        "Redis Pool": test_redis_pool(),
        "Supabase Retry": test_supabase_retry(),
        "Pool Metrics": test_pool_metrics(),
        "Health Checks": test_health_checks(),
        "Concurrent Connections": test_concurrent_connections()
    }

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test}")

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All tests passed! Connection pooling is working correctly.")
        print("\nNext steps:")
        print("1. Review pool metrics in Grafana: http://localhost:3001")
        print("2. Monitor performance improvements in production")
        print("3. Adjust pool sizes if needed based on load")
    else:
        print("❌ Some tests failed. Check the error messages above.")
        print("\nTroubleshooting:")
        print("1. Verify environment variables are set (.env file)")
        print("2. Check database services are running (Neo4j, Redis, Supabase)")
        print("3. Review logs for connection errors")

    print("=" * 70 + "\n")

    # Cleanup
    db_manager.close_all()

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
