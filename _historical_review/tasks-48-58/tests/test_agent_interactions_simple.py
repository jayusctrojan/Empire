"""
Simplified Test Suite for Task 39: Agent Interaction API
Tests core inter-agent messaging, events, state sync, and conflict resolution functionality

NOTE: These are INTEGRATION tests - they require a running server at localhost:8000
"""

import pytest
import requests
import json
from typing import Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

BASE_URL = "http://localhost:8000"

# Shared test environment
TEST_ENV = {
    "execution_id": None,
    "agent_ids": [],
    "crew_id": None
}


def setup_test_environment():
    """Use existing test execution (created via Supabase)"""
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
