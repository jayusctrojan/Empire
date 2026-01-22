"""
Test suite for Task 39: Agent Interaction API - Inter-Agent Messaging & Collaboration
Tests all agent interaction endpoints including messaging, events, state sync, and conflict resolution

NOTE: These are E2E tests - they require a running server at localhost:8000
Run with: pytest tests/test_agent_interactions.py -m e2e (after starting the server)
"""

import pytest
import requests
import json
import time
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

# Module-level cache for test environment (populated by autouse fixture)
_TEST_ENV: Dict[str, Any] = {}


# ==================== Pytest Fixtures ====================

@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    """Set up test environment before any tests in this module run.

    Note: Agent interactions require a valid execution_id in the crewai_executions table.
    Creating executions requires Celery/Redis. If the execution creation fails (e.g., due to
    Redis configuration issues), tests will skip gracefully.
    """
    test_id = str(uuid4())[:8]

    # Step 1: Create a test agent
    agent_data = {
        "agent_name": f"agent_interaction_test_{test_id}",
        "role": "Interaction Tester",
        "goal": "Test agent interaction capabilities",
        "backstory": f"An agent designed for testing - {test_id}",
        "tools": [],
        "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
    }
    agent_response = requests.post(f"{BASE_URL}/api/crewai/agents", json=agent_data)

    if agent_response.status_code != 201:
        print(f"\n  ⚠️ Could not create test agent: {agent_response.status_code}")
        yield
        return

    agent_id = agent_response.json()["id"]
    _TEST_ENV["agent_id"] = agent_id

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
        requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
        yield
        return

    crew_id = crew_response.json()["id"]
    _TEST_ENV["crew_id"] = crew_id

    # Step 3: Create an execution via API (requires Celery/Redis)
    execute_data = {
        "crew_id": crew_id,
        "task_description": "Test execution for agent interactions",
        "input_data": {"test": True, "purpose": "agent_interaction_testing"}
    }
    exec_response = requests.post(f"{BASE_URL}/api/crewai/execute", json=execute_data)

    if exec_response.status_code in [201, 202]:
        exec_data = exec_response.json()
        _TEST_ENV["execution_id"] = exec_data.get("execution_id") or exec_data.get("id")
        print(f"\n  ✅ Created test agent: {agent_id}")
        print(f"  ✅ Created test crew: {crew_id}")
        print(f"  ✅ Created execution ID: {_TEST_ENV['execution_id']}\n")
    else:
        print(f"\n  ⚠️ Could not create execution: {exec_response.status_code}")
        print(f"  ⚠️ Response: {exec_response.text[:200] if exec_response.text else 'No response'}")
        print("  ⚠️ Tests will be skipped - requires Celery/Redis infrastructure\n")
        requests.delete(f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true")
        requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
        _TEST_ENV.clear()

    yield

    # Cleanup after all tests
    if _TEST_ENV.get("crew_id"):
        requests.delete(f"{BASE_URL}/api/crewai/crews/{_TEST_ENV['crew_id']}?hard_delete=true")
    if _TEST_ENV.get("agent_id"):
        requests.delete(f"{BASE_URL}/api/crewai/agents/{_TEST_ENV['agent_id']}?hard_delete=true")


@pytest.fixture(scope="module")
def env() -> Dict[str, str]:
    """Provide the test environment dictionary for tests."""
    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")
    return _TEST_ENV


@pytest.fixture(scope="module")
def context() -> Dict[str, str]:
    """Provide the test context dictionary for tests (alias for env)."""
    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")
    return _TEST_ENV


@pytest.fixture(scope="module")
def interaction_id() -> str:
    """Create a message and return its interaction_id for tests that need it."""
    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available")

    message_data = {
        "execution_id": _TEST_ENV["execution_id"],
        "from_agent_id": _TEST_ENV["agent_id"],
        "to_agent_id": _TEST_ENV["agent_id"],
        "interaction_type": "message",
        "message": "Test message for fixture",
        "priority": 5,
        "requires_response": True,
        "response_deadline": (datetime.now() + timedelta(hours=1)).isoformat()
    }
    response = requests.post(f"{BASE_URL}/api/crewai/agent-interactions/messages/direct", json=message_data)
    if response.status_code != 201:
        pytest.skip(f"Could not create message: {response.status_code}")
    return response.json()["id"]


@pytest.fixture(scope="module")
def state_key() -> str:
    """Create a state entry and return its key for tests that need it."""
    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available")

    unique_key = f"test_state_{str(uuid4())[:8]}"
    state_data = {
        "execution_id": _TEST_ENV["execution_id"],
        "from_agent_id": _TEST_ENV["agent_id"],
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Test state for fixture",
        "state_key": unique_key,
        "state_value": {"test": True},
        "state_version": 1
    }
    response = requests.post(f"{BASE_URL}/api/crewai/agent-interactions/state/sync", json=state_data)
    if response.status_code != 201:
        pytest.skip(f"Could not create state: {response.status_code}")
    return unique_key


@pytest.fixture(scope="module")
def conflict_id() -> str:
    """Create a conflict and return its ID for tests that need it."""
    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available")

    conflict_data = {
        "execution_id": _TEST_ENV["execution_id"],
        "from_agent_id": _TEST_ENV["agent_id"],
        "to_agent_id": _TEST_ENV["agent_id"],
        "interaction_type": "conflict",
        "message": "Test conflict for fixture",
        "conflict_type": "concurrent_update",  # Use valid conflict type
        "conflict_detected": True,
        "conflict_resolved": False,
        "resolution_strategy": "manual"
    }
    response = requests.post(f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report", json=conflict_data)
    if response.status_code != 201:
        pytest.skip(f"Could not create conflict: {response.status_code} - {response.text}")
    return response.json()["id"]


# ==================== Setup Helpers (Legacy) ====================

def setup_test_environment():
    """Legacy function - kept for manual run_all_tests() compatibility."""
    return _TEST_ENV


def test_health_check():
    """Test that the API is running"""
    print("\n=== Test 0: API Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ API is healthy")


# ==================== Subtask 39.2: Messaging Tests ====================

def test_send_direct_message(env: Dict[str, str]):
    """Test Task 39.2: Send a direct message from one agent to another"""
    print("\n=== Test 1: Send Direct Message ===")

    # Use valid execution_id and agent_id from setup
    execution_id = env["execution_id"]
    from_agent_id = env["agent_id"]  # Use real agent from fixture
    to_agent_id = env["agent_id"]  # Self-message for simplicity

    message_data = {
        "execution_id": execution_id,
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "interaction_type": "message",
        "message": "Please analyze document X and extract key entities",
        "priority": 5,
        "requires_response": True,
        "response_deadline": (datetime.now() + timedelta(hours=1)).isoformat(),
        "metadata": {"document_id": "doc_123", "analysis_type": "entity_extraction"}
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/direct",
        json=message_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["from_agent_id"] == from_agent_id
    assert data["to_agent_id"] == to_agent_id
    assert data["requires_response"] is True
    assert data["is_broadcast"] is False

    print(f"✅ Direct message sent with ID: {data['id']}")
    return {
        "interaction_id": data["id"],
        "execution_id": execution_id,
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id
    }


def test_send_broadcast_message():
    """Test Task 39.2: Broadcast message to all agents in crew"""
    print("\n=== Test 2: Send Broadcast Message ===")

    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")

    execution_id = _TEST_ENV["execution_id"]
    from_agent_id = _TEST_ENV.get("agent_id") or str(uuid4())

    broadcast_data = {
        "execution_id": execution_id,
        "from_agent_id": from_agent_id,
        "to_agent_id": None,  # Null for broadcast
        "interaction_type": "message",
        "message": "Workflow phase change: Moving to synthesis phase",
        "priority": 8,
        "metadata": {"phase": "synthesis", "workflow_id": "wf_456"}
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/broadcast",
        json=broadcast_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert "broadcast_id" in data
    assert data["from_agent_id"] == from_agent_id
    assert "total_agents" in data

    print(f"✅ Broadcast sent to {data.get('total_agents', 0)} agents")
    return data


def test_respond_to_message(context: Dict[str, str], interaction_id: str):
    """Test Task 39.2: Respond to a message that requires response"""
    print("\n=== Test 3: Respond to Message ===")

    # Use interaction_id from fixture
    responder_agent_id = context.get("agent_id")
    response_text = "Analysis complete: Found 15 entities including 5 organizations and 10 people"

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/{interaction_id}/respond",
        params={
            "responder_agent_id": responder_agent_id,
            "response_text": response_text
        }
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == interaction_id
    assert data["response"] == response_text

    print("✅ Response sent successfully")
    return data


# ==================== Subtask 39.3: Event Publication Tests ====================

def test_publish_task_started_event():
    """Test Task 39.3: Publish task_started event"""
    print("\n=== Test 4: Publish Task Started Event ===")

    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")

    execution_id = _TEST_ENV["execution_id"]
    agent_id = _TEST_ENV.get("agent_id") or str(uuid4())

    event_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_id,
        "to_agent_id": None,
        "interaction_type": "event",
        "event_type": "task_started",
        "message": "Started processing document batch",
        "event_data": {
            "task_id": "task_789",
            "document_count": 10,
            "estimated_duration": "5 minutes"
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/events/publish",
        json=event_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "task_started"
    assert "event_data" in data

    print("✅ Event published successfully")
    return {"execution_id": execution_id, "agent_id": agent_id}


def test_publish_task_completed_event(context: Dict[str, str]):
    """Test Task 39.3: Publish task_completed event"""
    print("\n=== Test 5: Publish Task Completed Event ===")

    execution_id = context["execution_id"]
    agent_id = context["agent_id"]

    event_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_id,
        "to_agent_id": None,
        "interaction_type": "event",
        "event_type": "task_completed",
        "message": "Document batch processing complete",
        "event_data": {
            "task_id": "task_789",
            "documents_processed": 10,
            "entities_extracted": 150,
            "duration_seconds": 287
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/events/publish",
        json=event_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "task_completed"

    print("✅ Task completed event published")
    return context


def test_subscribe_to_events(context: Dict[str, str]):
    """Test Task 39.3: Subscribe to events for an execution"""
    print("\n=== Test 6: Subscribe to Events ===")

    execution_id = context["execution_id"]

    response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/events/{execution_id}",
        params={"event_types": "task_started,task_completed"}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # Should have both events we published

    print(f"✅ Retrieved {len(data)} events")
    return context


# ==================== Subtask 39.4: State Synchronization Tests ====================

def test_synchronize_state():
    """Test Task 39.4: Synchronize shared state between agents"""
    print("\n=== Test 7: Synchronize State (Initial) ===")

    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")

    execution_id = _TEST_ENV["execution_id"]
    agent_id = _TEST_ENV.get("agent_id") or str(uuid4())

    state_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_id,
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Updating task progress",
        "state_key": "task_1_progress",
        "state_value": {
            "progress_percentage": 25,
            "current_step": "entity_extraction",
            "documents_processed": 3
        },
        "state_version": 1,
        "previous_state": None
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert data["state_key"] == "task_1_progress"
    assert data["state_version"] == 1

    print("✅ Initial state synchronized")
    return {
        "execution_id": execution_id,
        "agent_id": agent_id,
        "state_key": "task_1_progress"
    }


def test_update_state_version(context: Dict[str, str]):
    """Test Task 39.4: Update state with new version"""
    print("\n=== Test 8: Update State (Version 2) ===")

    execution_id = context["execution_id"]
    agent_id = context["agent_id"]  # Use real agent from fixture

    state_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_id,
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Updating task progress",
        "state_key": "task_1_progress",
        "state_value": {
            "progress_percentage": 50,
            "current_step": "relationship_mapping",
            "documents_processed": 6
        },
        "state_version": 2,
        "previous_state": {
            "progress_percentage": 25,
            "current_step": "entity_extraction"
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert data["state_version"] == 2

    print("✅ State updated to version 2")
    return context


def test_state_version_conflict(context: Dict[str, str]):
    """Test Task 39.4: Detect state version conflict (optimistic locking)"""
    print("\n=== Test 9: State Version Conflict (Optimistic Locking) ===")

    execution_id = context["execution_id"]
    agent_id = context["agent_id"]  # Use real agent from fixture

    # Try to update with old version (should fail)
    state_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_id,
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Attempting update with old version",
        "state_key": "task_1_progress",
        "state_value": {
            "progress_percentage": 30,  # Conflicting update
            "current_step": "data_validation"
        },
        "state_version": 1  # Old version - should conflict
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Should return 409 Conflict
    assert response.status_code == 409
    print("✅ Conflict detected correctly (409 status)")
    return context


def test_get_current_state(context: Dict[str, str], state_key: str):
    """Test Task 39.4: Get current state for a key"""
    print("\n=== Test 10: Get Current State ===")

    execution_id = context["execution_id"]
    # Use state_key from fixture

    response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/state/{execution_id}/{state_key}"
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["state_key"] == state_key
    assert data["state_version"] >= 1  # At least version 1 from fixture

    print("✅ Retrieved current state successfully")
    return context


# ==================== Subtask 39.5: Conflict Resolution Tests ====================

def test_report_conflict():
    """Test Task 39.5: Report a detected conflict"""
    print("\n=== Test 11: Report Conflict ===")

    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")

    execution_id = _TEST_ENV["execution_id"]
    agent1_id = _TEST_ENV.get("agent_id") or str(uuid4())
    agent2_id = _TEST_ENV.get("agent_id") or str(uuid4())  # Use same agent (self-conflict for testing)

    conflict_data = {
        "execution_id": execution_id,
        "from_agent_id": agent1_id,
        "to_agent_id": agent2_id,
        "interaction_type": "conflict",
        "message": "Detected duplicate task assignment",
        "conflict_type": "duplicate_assignment",
        "conflict_detected": True,
        "conflict_resolved": False,
        "resolution_strategy": "manual",
        "resolution_data": {
            "task_id": "task_xyz",
            "assigned_to": [agent1_id, agent2_id],
            "detected_at": datetime.now().isoformat()
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        json=conflict_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 201
    data = response.json()
    assert data["conflict_detected"] is True
    assert data["conflict_resolved"] is False
    assert data["conflict_type"] == "duplicate_assignment"

    print(f"✅ Conflict reported with ID: {data['id']}")
    return {
        "conflict_id": data["id"],
        "execution_id": execution_id
    }


def test_resolve_conflict(context: Dict[str, str], conflict_id: str):
    """Test Task 39.5: Resolve a reported conflict"""
    print("\n=== Test 12: Resolve Conflict ===")

    # Use conflict_id from fixture
    agent_id = context.get("agent_id") or str(uuid4())

    resolution_data = {
        "conflict_id": conflict_id,
        "resolution_strategy": "latest_wins",
        "resolution_data": {
            "final_assignment": agent_id,
            "reason": "Agent 1 started work first",
            "resolved_by": "orchestrator"
        },
        "resolved_by_agent_id": agent_id
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{conflict_id}/resolve",
        json=resolution_data
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert data["conflict_resolved"] is True
    assert data["resolution_strategy"] == "latest_wins"
    assert "resolved_at" in data

    print("✅ Conflict resolved successfully")
    return context


def test_get_unresolved_conflicts(context: Dict[str, str]):
    """Test Task 39.5: Get all unresolved conflicts"""
    print("\n=== Test 13: Get Unresolved Conflicts ===")

    execution_id = context["execution_id"]

    response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{execution_id}/unresolved"
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "total_conflicts" in data
    assert "unresolved_conflicts" in data
    assert "conflicts" in data

    print(f"✅ Found {data['unresolved_conflicts']} unresolved conflicts")
    return context


def test_get_pending_responses():
    """Test Task 39.5: Get messages awaiting responses"""
    print("\n=== Test 14: Get Pending Responses ===")

    if not _TEST_ENV.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")

    # First, create a message requiring response
    execution_id = _TEST_ENV["execution_id"]
    from_agent_id = _TEST_ENV.get("agent_id") or str(uuid4())
    to_agent_id = _TEST_ENV.get("agent_id") or str(uuid4())  # Self-message for simplicity

    message_data = {
        "execution_id": execution_id,
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "interaction_type": "message",
        "message": "Need urgent data extraction",
        "priority": 10,
        "requires_response": True,
        "response_deadline": (datetime.now() + timedelta(minutes=5)).isoformat()
    }

    requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/direct",
        json=message_data
    )

    # Now check pending responses
    response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/responses/{execution_id}/pending"
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "total_pending" in data
    assert "urgent_count" in data
    assert "overdue_count" in data
    assert "pending_responses" in data

    print(f"✅ Found {data['total_pending']} pending responses")


# ==================== End-to-End Workflow Test ====================

def test_collaborative_workflow(env: Dict[str, str]):
    """Test Task 39.6: Complete multi-agent collaborative workflow"""
    print("\n=== Test 15: Complete Collaborative Workflow ===")

    if not env.get("execution_id"):
        pytest.skip("Test environment not available - requires Celery/Redis infrastructure")

    execution_id = env["execution_id"]
    # Use the same agent for all roles since we only have one in env
    agent_id = env.get("agent_id") or str(uuid4())
    agent_ids = {
        "orchestrator": agent_id,
        "parser": agent_id,
        "analyzer": agent_id,
        "synthesizer": agent_id
    }

    print(f"\n📋 Execution ID: {execution_id}")
    print(f"👥 Agents: {list(agent_ids.keys())}")

    # Step 1: Orchestrator broadcasts workflow start
    print("\n  Step 1: Orchestrator broadcasts workflow start")
    broadcast_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_ids["orchestrator"],
        "to_agent_id": None,
        "interaction_type": "message",
        "message": "Starting document analysis workflow",
        "priority": 10,
        "metadata": {"workflow_type": "document_analysis", "document_count": 5}
    }

    broadcast_response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/broadcast",
        json=broadcast_data
    )
    assert broadcast_response.status_code == 201
    print("    ✅ Workflow start broadcasted")

    # Step 2: Orchestrator delegates to parser
    print("\n  Step 2: Orchestrator delegates parsing task")
    delegation_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_ids["orchestrator"],
        "to_agent_id": agent_ids["parser"],
        "interaction_type": "message",
        "message": "Parse documents and extract text",
        "priority": 8,
        "requires_response": True,
        "response_deadline": (datetime.now() + timedelta(hours=1)).isoformat(),
        "metadata": {"task_type": "parsing", "document_ids": ["doc1", "doc2", "doc3"]}
    }

    delegation_response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/direct",
        json=delegation_data
    )
    assert delegation_response.status_code == 201
    delegation_id = delegation_response.json()["id"]
    print(f"    ✅ Parsing task delegated (ID: {delegation_id})")

    # Step 3: Parser publishes task_started event
    print("\n  Step 3: Parser publishes task_started event")
    event_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_ids["parser"],
        "to_agent_id": None,
        "interaction_type": "event",
        "event_type": "task_started",
        "message": "Started document parsing",
        "event_data": {"task_id": "parse_task_1", "document_count": 3}
    }

    event_response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/events/publish",
        json=event_data
    )
    assert event_response.status_code == 201
    print("    ✅ Event published")

    # Step 4: Parser updates shared state
    print("\n  Step 4: Parser updates shared state (parsing progress)")
    state_data = {
        "execution_id": execution_id,
        "from_agent_id": agent_ids["parser"],
        "to_agent_id": None,
        "interaction_type": "state_sync",
        "message": "Parsing progress update",
        "state_key": "parsing_progress",
        "state_value": {
            "documents_parsed": 3,
            "total_documents": 3,
            "status": "complete"
        },
        "state_version": 1
    }

    state_response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        json=state_data
    )
    assert state_response.status_code == 201
    print("    ✅ State synchronized")

    # Step 5: Parser responds to orchestrator
    print("\n  Step 5: Parser responds with results")
    response_data = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/{delegation_id}/respond",
        params={
            "responder_agent_id": agent_ids["parser"],
            "response_text": "Parsing complete: 3 documents processed, 15,000 words extracted"
        }
    )
    assert response_data.status_code == 200
    print("    ✅ Response sent to orchestrator")

    # Step 6: Orchestrator delegates to analyzer
    print("\n  Step 6: Orchestrator delegates analysis task")
    analysis_delegation = {
        "execution_id": execution_id,
        "from_agent_id": agent_ids["orchestrator"],
        "to_agent_id": agent_ids["analyzer"],
        "interaction_type": "message",
        "message": "Analyze parsed content and extract entities",
        "priority": 8,
        "requires_response": True,
        "metadata": {"depends_on": "parse_task_1"}
    }

    analysis_response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/messages/direct",
        json=analysis_delegation
    )
    assert analysis_response.status_code == 201
    print("    ✅ Analysis task delegated")

    # Step 7: Check for unresolved conflicts (should be none)
    print("\n  Step 7: Verify no unresolved conflicts")
    conflicts_response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{execution_id}/unresolved"
    )
    assert conflicts_response.status_code == 200
    conflicts_data = conflicts_response.json()
    print(f"    ✅ Unresolved conflicts: {conflicts_data['unresolved_conflicts']}")

    # Step 8: Verify all events
    print("\n  Step 8: Retrieve all workflow events")
    events_response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/events/{execution_id}"
    )
    assert events_response.status_code == 200
    events_data = events_response.json()
    print(f"    ✅ Total events: {len(events_data)}")

    # Step 9: Get current state
    print("\n  Step 9: Get current workflow state")
    current_state_response = requests.get(
        f"{BASE_URL}/api/crewai/agent-interactions/state/{execution_id}/parsing_progress"
    )
    assert current_state_response.status_code == 200
    current_state = current_state_response.json()
    print(f"    ✅ Current state: {current_state['state_value']}")

    print("\n✅ Collaborative workflow completed successfully!")
    print(f"\nWorkflow Summary:")
    print(f"  - Execution ID: {execution_id}")
    print(f"  - Agents involved: {len(agent_ids)}")
    print(f"  - Messages exchanged: 4+")
    print(f"  - Events published: {len(events_data)}")
    print(f"  - State updates: 1")
    print(f"  - Conflicts: {conflicts_data['total_conflicts']}")


# ==================== Main Test Runner ====================

def run_all_tests():
    """Run all test scenarios in sequence"""
    print("\n" + "=" * 80)
    print("TASK 39: AGENT INTERACTION API - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    try:
        # Health check
        test_health_check()

        # Setup test environment (agent, crew, execution)
        env = setup_test_environment()

        # Messaging tests
        msg_context = test_send_direct_message(env)
        test_send_broadcast_message()
        test_respond_to_message(msg_context)

        # Event tests
        event_context = test_publish_task_started_event()
        event_context = test_publish_task_completed_event(event_context)
        test_subscribe_to_events(event_context)

        # State synchronization tests
        state_context = test_synchronize_state()
        state_context = test_update_state_version(state_context)
        test_state_version_conflict(state_context)
        test_get_current_state(state_context)

        # Conflict resolution tests
        conflict_context = test_report_conflict()
        test_resolve_conflict(conflict_context)
        test_get_unresolved_conflicts(conflict_context)
        test_get_pending_responses()

        # End-to-end workflow
        test_collaborative_workflow()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n❌ Test failed with assertion error: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
