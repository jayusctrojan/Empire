"""
Test script for LangGraph + Arcade.dev endpoints (Task 46)

Tests both synchronous and asynchronous query processing endpoints.

NOTE: These are INTEGRATION tests - require local or production API
Tests will use localhost:8000 if available, otherwise skip.
"""
import pytest
import requests
import time
import json
from typing import Dict, Any

# Server URLs - prefer localhost for testing
LOCAL_URL = "http://localhost:8000"
PRODUCTION_URL = "https://jb-empire-api.onrender.com"


def _get_available_base_url() -> str:
    """Get the first available API server URL (prefer localhost)."""
    # Try localhost first - check basic health first, then query health
    try:
        # Check if server is up at all
        response = requests.get(f"{LOCAL_URL}/health", timeout=3)
        if response.status_code == 200:
            # Server is up, check if query health exists (may fail but that's ok for some tests)
            try:
                query_response = requests.get(f"{LOCAL_URL}/api/query/health", timeout=3)
                if query_response.status_code == 200:
                    return LOCAL_URL
            except:
                pass
            # Server is up but query endpoints may not be fully configured
            # Still return localhost for tests that don't need query health
            return LOCAL_URL
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        pass

    # Fall back to production
    try:
        response = requests.get(f"{PRODUCTION_URL}/api/query/health", timeout=5)
        if response.status_code == 200:
            return PRODUCTION_URL
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        pass

    return None


# Mark all tests in this module as integration tests that require live API
pytestmark = [
    pytest.mark.integration,
    pytest.mark.live_api,
]


@pytest.fixture(autouse=True)
def check_server_available():
    """Check if any API server is available at test runtime."""
    import time
    # Retry a few times for localhost
    for attempt in range(3):
        base_url = _get_available_base_url()
        if base_url:
            break
        time.sleep(0.5)
    else:
        pytest.skip("No API server available (tried localhost:8000 and production)")


@pytest.fixture
def base_url():
    """Get the base URL for tests."""
    url = _get_available_base_url()
    if not url:
        pytest.skip("No API server available")
    return url

def test_health_check(base_url):
    """Test /api/query/health endpoint."""
    print(f"\n=== Testing Health Check ({base_url}) ===")
    response = requests.get(f"{base_url}/api/query/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert data["langgraph_enabled"] == True
    print("✅ Health check passed")


def test_list_tools(base_url):
    """Test /api/query/tools endpoint."""
    print(f"\n=== Testing List Tools ({base_url}) ===")
    response = requests.get(f"{base_url}/api/query/tools")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Internal tools: {data['internal_tools']}")
    print(f"External tools: {data['external_tools']}")
    print(f"Total: {data['total_count']}")
    print(f"Arcade enabled: {data['arcade_enabled']}")
    assert response.status_code == 200
    assert len(data['internal_tools']) >= 3
    print("✅ List tools passed")


def test_sync_adaptive_query(base_url):
    """Test synchronous /api/query/adaptive endpoint."""
    print(f"\n=== Testing Sync Adaptive Query ({base_url}) ===")

    query_data = {
        "query": "What are the key features of California insurance regulations?",
        "max_iterations": 2,
        "use_external_tools": False  # Don't use external tools for now
    }

    print(f"Query: {query_data['query']}")
    start = time.time()
    response = requests.post(f"{base_url}/api/query/adaptive", json=query_data)
    elapsed = time.time() - start

    print(f"Status: {response.status_code}")
    print(f"Time: {elapsed:.2f}s")

    if response.status_code == 200:
        data = response.json()
        print(f"Answer: {data['answer'][:200]}...")
        print(f"Iterations: {data['iterations']}")
        print(f"Workflow: {data['workflow_type']}")
        print(f"Processing time: {data['processing_time_ms']}ms")
        print("✅ Sync adaptive query passed")
    else:
        print(f"❌ Failed: {response.text}")


def test_sync_auto_routed_query(base_url):
    """Test synchronous /api/query/auto endpoint."""
    print(f"\n=== Testing Sync Auto-Routed Query ({base_url}) ===")

    query_data = {
        "query": "What is our vacation policy?",  # Simple query
        "max_iterations": 2
    }

    print(f"Query: {query_data['query']}")
    start = time.time()
    response = requests.post(f"{base_url}/api/query/auto", json=query_data)
    elapsed = time.time() - start

    print(f"Status: {response.status_code}")
    print(f"Time: {elapsed:.2f}s")

    if response.status_code == 200:
        data = response.json()
        print(f"Answer: {data['answer'][:200]}...")
        print(f"Workflow: {data['workflow_type']}")
        print(f"Iterations: {data['iterations']}")
        print("✅ Sync auto-routed query passed")
    else:
        print(f"❌ Failed: {response.text}")


def test_async_adaptive_query(base_url):
    """Test asynchronous /api/query/adaptive/async endpoint."""
    print(f"\n=== Testing Async Adaptive Query ({base_url}) ===")

    query_data = {
        "query": "Compare insurance policies across different states",
        "max_iterations": 3,
        "use_external_tools": False
    }

    print(f"Query: {query_data['query']}")

    # Submit query
    response = requests.post(f"{base_url}/api/query/adaptive/async", json=query_data)
    print(f"Submit Status: {response.status_code}")

    if response.status_code != 200:
        print(f"❌ Failed to submit: {response.text}")
        return

    data = response.json()
    task_id = data['task_id']
    print(f"Task ID: {task_id}")
    print(f"Estimated time: {data['estimated_time_seconds']}s")

    # Poll for results
    max_polls = 30
    poll_interval = 2

    for i in range(max_polls):
        time.sleep(poll_interval)
        status_response = requests.get(f"{base_url}/api/query/status/{task_id}")

        if status_response.status_code != 200:
            print(f"❌ Failed to get status: {status_response.text}")
            return

        status_data = status_response.json()
        print(f"Poll {i+1}: Status = {status_data['status']}")

        if status_data['status'] == 'SUCCESS':
            result = status_data['result']
            print(f"\n✅ Query completed!")
            print(f"Answer: {result['answer'][:200]}...")
            print(f"Iterations: {result['iterations']}")
            print(f"Status: {result['status']}")
            return

        elif status_data['status'] == 'FAILURE':
            print(f"❌ Query failed: {status_data.get('error')}")
            return

    print(f"⚠️  Timeout after {max_polls * poll_interval}s")


def test_batch_query(base_url):
    """Test batch query processing."""
    print(f"\n=== Testing Batch Query Processing ({base_url}) ===")

    batch_data = {
        "queries": [
            "What is our vacation policy?",
            "What are the health insurance options?",
            "How do I submit an expense report?"
        ],
        "max_iterations": 2,
        "use_auto_routing": True
    }

    print(f"Submitting {len(batch_data['queries'])} queries...")
    response = requests.post(f"{base_url}/api/query/batch", json=batch_data)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Batch task ID: {data['task_id']}")
        print(f"Status: {data.get('status', 'N/A')}")
        print(f"Message: {data.get('message', 'N/A')}")
        # Check that we have a task_id and message indicating batch was submitted
        assert 'task_id' in data, "Response should contain task_id"
        assert 'message' in data, "Response should contain message"
        assert str(len(batch_data['queries'])) in data.get('message', ''), "Message should indicate query count"
        print("✅ Batch query submitted")
    else:
        print(f"❌ Failed: {response.text}")
        assert False, f"Batch query failed with status {response.status_code}"


if __name__ == "__main__":
    print("=" * 60)
    print("LangGraph + Arcade.dev Endpoint Tests (Task 46)")
    print("=" * 60)

    try:
        # Test basic endpoints
        test_health_check()
        test_list_tools()

        # Test synchronous endpoints
        test_sync_adaptive_query()
        test_sync_auto_routed_query()

        # Test asynchronous endpoints
        test_async_adaptive_query()
        test_batch_query()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
