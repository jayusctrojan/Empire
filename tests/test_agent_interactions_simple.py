"""
Simplified Test Suite for Task 39: Agent Interaction API
Tests core inter-agent messaging, events, state sync, and conflict resolution functionality

NOTE: These are E2E tests - they require a running server at localhost:8000
Run with: pytest tests/test_agent_interactions_simple.py -m e2e (after starting the server)
"""

import pytest
import requests
import json
from typing import Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

def _local_server_is_available() -> bool:
    """Check if the local FastAPI server is available."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        return False


# Mark all tests in this module as e2e tests that need a running server
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.skipif(
        not _local_server_is_available(),
        reason="Local FastAPI server not running on port 8000"
    ),
]

BASE_URL = "http://localhost:8000"

# Shared test environment
TEST_ENV = {
    "execution_id": None,
    "agent_ids": [],
    "crew_id": None
}


# ==================== Pytest Fixtures ====================

@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    """Set up test environment before any tests in this module run.

    Note: Agent interactions require a valid execution_id in the crewai_executions table.
    Creating executions requires Celery/Redis. If the execution creation fails (e.g., due to
    Redis configuration issues), TEST_ENV will be left empty and tests will skip gracefully.
    """
    test_id = str(uuid4())[:8]

    # Step 1: Create a test agent
    agent_data = {
        "agent_name": f"interaction_test_agent_{test_id}",
        "role": "Test Agent for Interactions",
        "goal": "Test agent interaction API",
        "backstory": f"Created for interaction testing - {test_id}",
        "tools": ["web_search"],
        "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
    }
    agent_response = requests.post(f"{BASE_URL}/api/crewai/agents", json=agent_data)

    if agent_response.status_code != 201:
        print(f"\n  ⚠️ Could not create test agent: {agent_response.status_code}")
        yield
        return

    agent_id = agent_response.json()["id"]
    TEST_ENV["agent_ids"] = [agent_id]

    # Step 2: Create a test crew
    crew_data = {
        "crew_name": f"interaction_test_crew_{test_id}",
        "description": f"Test crew for interactions - {test_id}",
        "agent_ids": [agent_id],
        "process_type": "sequential",
        "memory_enabled": False,
        "verbose": False
    }
    crew_response = requests.post(f"{BASE_URL}/api/crewai/crews", json=crew_data)

    if crew_response.status_code != 201:
        print(f"\n  ⚠️ Could not create test crew: {crew_response.status_code}")
        # Cleanup agent
        requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
        TEST_ENV["agent_ids"] = []
        yield
        return

    crew_id = crew_response.json()["id"]
    TEST_ENV["crew_id"] = crew_id

    # Step 3: Create an execution via API (requires Celery/Redis)
    execute_data = {
        "crew_id": crew_id,
        "task_description": "Test execution for agent interactions",
        "input_data": {"test": True, "purpose": "agent_interaction_testing"}
    }
    exec_response = requests.post(f"{BASE_URL}/api/crewai/execute", json=execute_data)

    if exec_response.status_code == 201 or exec_response.status_code == 202:
        # Execution created successfully
        exec_data = exec_response.json()
        TEST_ENV["execution_id"] = exec_data.get("execution_id") or exec_data.get("id")
        print(f"\n  ✅ Created test agent: {agent_id}")
        print(f"  ✅ Created test crew: {crew_id}")
        print(f"  ✅ Created execution ID: {TEST_ENV['execution_id']}\n")
    else:
        # Execution creation failed (likely Redis/Celery issue)
        # Clear TEST_ENV so tests skip gracefully
        print(f"\n  ⚠️ Could not create execution: {exec_response.status_code}")
        print(f"  ⚠️ Response: {exec_response.text[:200] if exec_response.text else 'No response'}")
        print("  ⚠️ Tests will be skipped - requires Celery/Redis infrastructure\n")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true")
        requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
        TEST_ENV["crew_id"] = None
        TEST_ENV["agent_ids"] = []

    yield

    # Cleanup after all tests
    if TEST_ENV["crew_id"]:
        requests.delete(f"{BASE_URL}/api/crewai/crews/{TEST_ENV['crew_id']}?hard_delete=true")
    if TEST_ENV["agent_ids"]:
        for aid in TEST_ENV["agent_ids"]:
            requests.delete(f"{BASE_URL}/api/crewai/agents/{aid}?hard_delete=true")


@pytest.fixture(scope="module")
def state_key():
    """Create a state key by running the synchronize state test."""
    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up")

    unique_key = f"task_1_progress_{str(uuid4())[:8]}"

    state_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": TEST_ENV["agent_ids"][0],
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Updating task progress",
        "state_key": unique_key,
        "state_value": {
            "progress_percentage": 25,
            "current_step": "entity_extraction",
            "documents_processed": 3
        },
        "state_version": 1
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )

    if response.status_code != 201:
        pytest.skip(f"Could not create state for conflict test: {response.status_code}")

    return unique_key


@pytest.fixture(scope="module")
def conflict_id():
    """Create a conflict by running the report conflict test."""
    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up")

    conflict_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": TEST_ENV["agent_ids"][0],
        "to_agent_id": TEST_ENV["agent_ids"][0],
        "interaction_type": "conflict",
        "message": "Detected duplicate task assignment",
        "conflict_type": "duplicate_assignment",
        "conflict_detected": True,
        "conflict_resolved": False,
        "resolution_strategy": "manual"
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        json=conflict_data
    )

    if response.status_code != 201:
        pytest.skip(f"Could not create conflict: {response.status_code}")

    return response.json()["id"]


def setup_test_environment():
    """Legacy function - kept for manual run_all_tests() compatibility."""
    print("\n=== Setting Up Test Environment ===")

    # Use pre-created execution record (bypass Redis/Celery requirement)
    # This execution was created directly in the database for testing
    TEST_ENV["execution_id"] = "450f4ead-0ae9-4746-8bfe-cda26b1d7014"
    TEST_ENV["crew_id"] = "de94019d-8f2b-402f-bca4-8a5b449d0357"
    TEST_ENV["agent_ids"] = ["f2ccafc9-ef34-4112-bef5-b572d58d4b0f"]

    print(f"  ✅ Using test execution: {TEST_ENV['execution_id']}")
    print(f"  ✅ Using test crew: {TEST_ENV['crew_id']}")
    print(f"  ✅ Using test agent: {TEST_ENV['agent_ids'][0]}\n")


def test_1_send_direct_message():
    """Test 1: Send a direct message from one agent to another"""
    print("=== Test 1: Send Direct Message ===")

    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up - no agents available")

    # Use the same agent for both from/to (simulating self-messaging or using same agent)
    agent_id = TEST_ENV["agent_ids"][0]

    message_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": agent_id,
        "to_agent_id": agent_id,  # Using same agent for simplicity
        "interaction_type": "message",
        "message": "Please analyze document X and extract key entities",
        "priority": 5,
        "requires_response": True,
        "response_deadline": (datetime.now() + timedelta(hours=1)).isoformat()
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/direct",
        json=message_data
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.json()}"

    data = response.json()
    assert data["requires_response"] is True
    assert data["is_broadcast"] is False

    print(f"✅ Direct message sent with ID: {data['id']}\n")
    return data["id"]


def test_2_send_broadcast_message():
    """Test 2: Broadcast message to all agents in crew"""
    print("=== Test 2: Send Broadcast Message ===")

    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up - no agents available")

    agent_id = TEST_ENV["agent_ids"][0]

    broadcast_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": agent_id,
        "to_agent_id": None,
        "interaction_type": "message",
        "message": "Workflow phase change: Moving to synthesis phase",
        "priority": 8
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/broadcast",
        json=broadcast_data
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.json()}"

    data = response.json()
    print(f"✅ Broadcast sent to {data.get('total_agents', 0)} agents\n")


def test_3_publish_event():
    """Test 3: Publish task_started event"""
    print("=== Test 3: Publish Event ===")

    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up - no agents available")

    event_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": TEST_ENV["agent_ids"][0],
        "to_agent_id": None,
        "interaction_type": "event",
        "event_type": "task_started",
        "message": "Started processing document batch",
        "event_data": {"task_id": "task_789", "document_count": 10}
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/events/publish",
        json=event_data
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.json()}"

    data = response.json()
    assert data["event_type"] == "task_started"
    print(f"✅ Event published successfully\n")


def test_4_synchronize_state():
    """Test 4: Synchronize shared state between agents"""
    print("=== Test 4: Synchronize State ===")

    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up - no agents available")

    # Use unique state key for each test run to avoid conflicts
    unique_key = f"task_1_progress_{str(uuid4())[:8]}"

    state_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": TEST_ENV["agent_ids"][0],
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Updating task progress",
        "state_key": unique_key,
        "state_value": {
            "progress_percentage": 25,
            "current_step": "entity_extraction",
            "documents_processed": 3
        },
        "state_version": 1
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.json()}"

    data = response.json()
    assert data["state_key"] == unique_key
    assert data["state_version"] == 1
    print(f"✅ State synchronized successfully\n")
    return unique_key  # Return for use in Test 5


def test_5_state_version_conflict(state_key):
    """Test 5: Detect state version conflict (optimistic locking)"""
    print("=== Test 5: State Version Conflict ===")

    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up - no agents available")

    # Try to update with old version (should fail with 409)
    state_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": TEST_ENV["agent_ids"][0],
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Attempting update with old version",
        "state_key": state_key,  # Use the same key from Test 4
        "state_value": {"progress_percentage": 30},
        "state_version": 1  # Old version - should conflict
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 409, f"Expected 409 Conflict, got {response.status_code}"
    print(f"✅ Conflict detected correctly (409 status)\n")


def test_6_report_conflict():
    """Test 6: Report a detected conflict"""
    print("=== Test 6: Report Conflict ===")

    if not TEST_ENV["agent_ids"]:
        pytest.skip("Test environment not set up - no agents available")

    conflict_data = {
        "execution_id": TEST_ENV["execution_id"],
        "from_agent_id": TEST_ENV["agent_ids"][0],
        "to_agent_id": TEST_ENV["agent_ids"][0],
        "interaction_type": "conflict",
        "message": "Detected duplicate task assignment",
        "conflict_type": "duplicate_assignment",
        "conflict_detected": True,
        "conflict_resolved": False,
        "resolution_strategy": "manual"
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        json=conflict_data
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.json()}"

    data = response.json()
    assert data["conflict_detected"] is True
    assert data["conflict_resolved"] is False
    print(f"✅ Conflict reported with ID: {data['id']}\n")
    return data["id"]


def test_7_get_unresolved_conflicts(conflict_id):
    """Test 7: Get all unresolved conflicts"""
    print("=== Test 7: Get Unresolved Conflicts ===")

    if not TEST_ENV["execution_id"]:
        pytest.skip("Test environment not set up - no execution_id available")

    response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{TEST_ENV['execution_id']}/unresolved"
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Failed: {response.json()}"

    data = response.json()
    assert "total_conflicts" in data
    assert "unresolved_conflicts" in data
    print(f"✅ Found {data['unresolved_conflicts']} unresolved conflicts\n")


def test_8_subscribe_to_events():
    """Test 8: Subscribe to events for an execution"""
    print("=== Test 8: Subscribe to Events ===")

    if not TEST_ENV["execution_id"]:
        pytest.skip("Test environment not set up - no execution_id available")

    response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/events/{TEST_ENV['execution_id']}",
        params={"event_types": "task_started,task_completed"}
    )

    print(f"Status: {response.status_code}")
    assert response.status_code == 200, f"Failed: {response.json()}"

    data = response.json()
    assert isinstance(data, list)
    print(f"✅ Retrieved {len(data)} events\n")


def run_all_tests():
    """Run all test scenarios in sequence"""
    print("\n" + "=" * 80)
    print("TASK 39: AGENT INTERACTION API - SIMPLIFIED TEST SUITE")
    print("=" * 80)

    try:
        # Setup
        setup_test_environment()

        # Run tests
        test_1_send_direct_message()
        test_2_send_broadcast_message()
        test_3_publish_event()
        state_key = test_4_synchronize_state()
        test_5_state_version_conflict(state_key)
        conflict_id = test_6_report_conflict()
        test_7_get_unresolved_conflicts(conflict_id)
        test_8_subscribe_to_events()

        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
