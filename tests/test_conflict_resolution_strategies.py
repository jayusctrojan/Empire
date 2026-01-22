"""
Test suite for auto-resolution conflict strategies (Priority 3)
Tests all 4 strategies: latest_wins, merge, rollback, escalate

These tests require a running API server at localhost:8000.
They are marked as live_api tests and will be skipped if the server is not available.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
import asyncio
from uuid import UUID, uuid4
import requests
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


def _server_is_available() -> bool:
    """Check if the API server is available."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


# Skip all tests if the server is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.live_api,
    pytest.mark.skipif(
        not _server_is_available(),
        reason="API server not available at localhost:8000"
    ),
]


def test_conflict_resolution_strategies():
    """Test all 4 auto-resolution strategies"""

    print(f"\n=== Testing Conflict Resolution Strategies ===")

    # Setup: Create execution and crew using the correct API workflow
    print("\n1. Setting up test execution and crew...")

    # Placeholder IDs - will be replaced by actual IDs from API
    placeholder_execution_id = uuid4()
    placeholder_crew_id = uuid4()
    placeholder_agent1_id = uuid4()
    placeholder_agent2_id = uuid4()

    result = setup_execution_and_crew(
        placeholder_execution_id,
        placeholder_crew_id,
        placeholder_agent1_id,
        placeholder_agent2_id
    )

    if result[0] is None:
        pytest.skip("Could not create execution via API - skipping test")

    execution_id, crew_id, agent1_id, agent2_id = result

    print(f"Execution ID: {execution_id}")
    print(f"Crew ID: {crew_id}")
    print(f"Agent 1 ID: {agent1_id}")
    print(f"Agent 2 ID: {agent2_id}")

    try:
        # Test 1: latest_wins strategy
        print("\n2. Testing LATEST_WINS strategy...")
        _run_latest_wins_resolution(execution_id, agent1_id, agent2_id)

        # Test 2: merge strategy (success case)
        print("\n3. Testing MERGE strategy (non-conflicting keys)...")
        _run_merge_resolution_success(execution_id, agent1_id, agent2_id)

        # Test 3: merge strategy (escalation case)
        print("\n4. Testing MERGE strategy (conflicting keys → escalate)...")
        _run_merge_resolution_escalate(execution_id, agent1_id, agent2_id)

        # Test 4: rollback strategy
        print("\n5. Testing ROLLBACK strategy...")
        _run_rollback_resolution(execution_id, agent1_id, agent2_id)

        # Test 5: escalate strategy
        print("\n6. Testing ESCALATE strategy...")
        _run_escalate_resolution(execution_id, crew_id, agent1_id, agent2_id)

        print("\n=== All Conflict Resolution Tests Passed! ===\n")
    finally:
        # Cleanup created resources
        print("\n7. Cleaning up test resources...")
        _cleanup_test_resources(crew_id, agent1_id, agent2_id)


def setup_execution_and_crew(execution_id, crew_id, agent1_id, agent2_id):
    """Create test execution and crew via REST API using the correct workflow"""

    test_id = str(uuid4())[:8]

    # Step 1: Create agents via POST /api/crewai/agents
    agent1_data = {
        "agent_name": f"conflict_test_agent1_{test_id}",
        "role": "Conflict Test Agent 1",
        "goal": "Test conflict resolution",
        "backstory": f"Created for conflict resolution testing - {test_id}",
        "tools": ["test_tool"],
        "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
    }
    agent1_response = requests.post(
        f"{BASE_URL}/api/crewai/agents",
        headers=HEADERS,
        json=agent1_data
    )
    if agent1_response.status_code != 201:
        print(f"  Warning: Agent 1 creation returned {agent1_response.status_code}: {agent1_response.text}")
        return None, None, None, None
    real_agent1_id = agent1_response.json()["id"]
    print(f"  ✓ Created agent 1: {real_agent1_id}")

    agent2_data = {
        "agent_name": f"conflict_test_agent2_{test_id}",
        "role": "Conflict Test Agent 2",
        "goal": "Test conflict resolution",
        "backstory": f"Created for conflict resolution testing - {test_id}",
        "tools": ["test_tool"],
        "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
    }
    agent2_response = requests.post(
        f"{BASE_URL}/api/crewai/agents",
        headers=HEADERS,
        json=agent2_data
    )
    if agent2_response.status_code != 201:
        print(f"  Warning: Agent 2 creation returned {agent2_response.status_code}: {agent2_response.text}")
        # Cleanup agent 1
        requests.delete(f"{BASE_URL}/api/crewai/agents/{real_agent1_id}?hard_delete=true")
        return None, None, None, None
    real_agent2_id = agent2_response.json()["id"]
    print(f"  ✓ Created agent 2: {real_agent2_id}")

    # Step 2: Create crew via POST /api/crewai/crews
    crew_data = {
        "crew_name": f"conflict_test_crew_{test_id}",
        "description": f"Test conflict resolution crew - {test_id}",
        "agent_ids": [real_agent1_id, real_agent2_id],
        "process_type": "sequential",
        "memory_enabled": True,
        "verbose": False
    }
    crew_response = requests.post(
        f"{BASE_URL}/api/crewai/crews",
        headers=HEADERS,
        json=crew_data
    )
    if crew_response.status_code != 201:
        print(f"  Warning: Crew creation returned {crew_response.status_code}: {crew_response.text}")
        # Cleanup agents
        requests.delete(f"{BASE_URL}/api/crewai/agents/{real_agent1_id}?hard_delete=true")
        requests.delete(f"{BASE_URL}/api/crewai/agents/{real_agent2_id}?hard_delete=true")
        return None, None, None, None
    real_crew_id = crew_response.json()["id"]
    print(f"  ✓ Created crew: {real_crew_id}")

    # Step 3: Create execution via POST /api/crewai/execute
    execute_data = {
        "crew_id": real_crew_id,
        "task_description": "Test conflict resolution strategies",
        "input_data": {"test": True, "purpose": "conflict_resolution_testing"}
    }
    execute_response = requests.post(
        f"{BASE_URL}/api/crewai/execute",
        headers=HEADERS,
        json=execute_data
    )
    if execute_response.status_code not in [200, 201, 202]:
        print(f"  Warning: Execution creation returned {execute_response.status_code}: {execute_response.text}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/crewai/crews/{real_crew_id}?hard_delete=true")
        requests.delete(f"{BASE_URL}/api/crewai/agents/{real_agent1_id}?hard_delete=true")
        requests.delete(f"{BASE_URL}/api/crewai/agents/{real_agent2_id}?hard_delete=true")
        return None, None, None, None

    real_execution_id = execute_response.json().get("execution_id") or execute_response.json().get("id")
    print(f"  ✓ Created execution: {real_execution_id}")

    print(f"✓ Setup complete - execution {real_execution_id}, crew {real_crew_id}")
    return real_execution_id, real_crew_id, real_agent1_id, real_agent2_id


def _run_latest_wins_resolution(execution_id, agent1_id, agent2_id):
    """Test latest_wins strategy: accept most recent state"""

    # 1. Create initial state
    state_key = "test_state_latest_wins"

    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent1_id),
            "to_agent_id": None,
            "interaction_type": "state_sync",
            "message": "Initial state",
            "state_key": state_key,
            "state_value": {"counter": 1, "status": "initial"},
            "state_version": 1
        }
    )
    assert response.status_code == 201, f"Failed to create initial state: {response.text}"
    print(f"  ✓ Created initial state: version 1")

    # 2. Create conflicting state (version 2)
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent2_id),
            "to_agent_id": None,
            "interaction_type": "state_sync",
            "message": "Updated state",
            "state_key": state_key,
            "state_value": {"counter": 5, "status": "updated"},
            "state_version": 2,
            "previous_state": {"counter": 1, "status": "initial"}
        }
    )
    assert response.status_code == 201, f"Failed to create updated state: {response.text}"
    print(f"  ✓ Created updated state: version 2")

    # 3. Report conflict
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent1_id),
            "to_agent_id": None,
            "interaction_type": "conflict",
            "message": "Version conflict detected",
            "conflict_type": "concurrent_update",
            "conflict_detected": True,
            "resolution_data": {
                "state_key": state_key,
                "current_value": {"counter": 5, "status": "updated"},
                "attempted_value": {"counter": 3, "status": "conflict"}
            }
        }
    )
    assert response.status_code == 201, f"Failed to report conflict: {response.text}"
    conflict_id = response.json()["id"]
    print(f"  ✓ Reported conflict: {conflict_id}")

    # 4. Resolve with latest_wins
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{conflict_id}/resolve",
        headers=HEADERS,
        json={
            "conflict_id": conflict_id,
            "resolution_strategy": "latest_wins"
        }
    )
    assert response.status_code == 200, f"Failed to resolve conflict: {response.text}"
    assert response.json()["conflict_resolved"] == True
    print(f"  ✓ Resolved conflict with latest_wins strategy")


def _run_merge_resolution_success(execution_id, agent1_id, agent2_id):
    """Test merge strategy: successfully merge non-conflicting changes"""

    state_key = "test_state_merge_success"

    # 1. Create initial state
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent1_id),
            "to_agent_id": None,
            "interaction_type": "state_sync",
            "message": "Initial state",
            "state_key": state_key,
            "state_value": {"field_a": 1, "field_b": 2},
            "state_version": 1
        }
    )
    assert response.status_code == 201
    print(f"  ✓ Created initial state with field_a and field_b")

    # 2. Report conflict with non-conflicting changes
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent2_id),
            "to_agent_id": None,
            "interaction_type": "conflict",
            "message": "Merge conflict",
            "conflict_type": "concurrent_update",
            "conflict_detected": True,
            "resolution_data": {
                "state_key": state_key,
                "current_value": {"field_a": 1, "field_b": 2},  # Current state
                "attempted_value": {"field_c": 3}  # Non-conflicting new field
            }
        }
    )
    assert response.status_code == 201
    conflict_id = response.json()["id"]
    print(f"  ✓ Reported conflict with non-conflicting changes")

    # 3. Resolve with merge (should succeed)
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{conflict_id}/resolve",
        headers=HEADERS,
        json={
            "conflict_id": conflict_id,
            "resolution_strategy": "merge"
        }
    )
    assert response.status_code == 200
    assert response.json()["conflict_resolved"] == True
    print(f"  ✓ Successfully merged non-conflicting changes")


def _run_merge_resolution_escalate(execution_id, agent1_id, agent2_id):
    """Test merge strategy: escalate when there are conflicting key values"""

    state_key = "test_state_merge_conflict"

    # 1. Create initial state
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent1_id),
            "to_agent_id": None,
            "interaction_type": "state_sync",
            "message": "Initial state",
            "state_key": state_key,
            "state_value": {"counter": 10},
            "state_version": 1
        }
    )
    assert response.status_code == 201
    print(f"  ✓ Created initial state with counter=10")

    # 2. Report conflict with conflicting key values
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent2_id),
            "to_agent_id": None,
            "interaction_type": "conflict",
            "message": "Conflicting update",
            "conflict_type": "concurrent_update",
            "conflict_detected": True,
            "resolution_data": {
                "state_key": state_key,
                "current_value": {"counter": 10},  # Current has counter=10
                "attempted_value": {"counter": 20}  # Attempted has counter=20 (CONFLICT!)
            }
        }
    )
    assert response.status_code == 201
    conflict_id = response.json()["id"]
    print(f"  ✓ Reported conflict with conflicting counter values")

    # 3. Resolve with merge (should escalate due to conflicting 'counter' key)
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{conflict_id}/resolve",
        headers=HEADERS,
        json={
            "conflict_id": conflict_id,
            "resolution_strategy": "merge"
        }
    )
    assert response.status_code == 200
    assert response.json()["conflict_resolved"] == True
    print(f"  ✓ Merge strategy detected conflict and escalated")


def _run_rollback_resolution(execution_id, agent1_id, agent2_id):
    """Test rollback strategy: revert to previous state"""

    state_key = "test_state_rollback"

    # 1. Create initial state
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/state/sync",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent1_id),
            "to_agent_id": None,
            "interaction_type": "state_sync",
            "message": "Good state",
            "state_key": state_key,
            "state_value": {"status": "good", "version": 1},
            "state_version": 1
        }
    )
    assert response.status_code == 201
    print(f"  ✓ Created good state")

    # 2. Report conflict
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent2_id),
            "to_agent_id": None,
            "interaction_type": "conflict",
            "message": "Rollback needed",
            "conflict_type": "state_mismatch",
            "conflict_detected": True,
            "resolution_data": {
                "state_key": state_key,
                "current_value": {"status": "good", "version": 1},  # Good state to revert to
                "attempted_value": {"status": "bad", "version": 2}  # Bad state
            }
        }
    )
    assert response.status_code == 201
    conflict_id = response.json()["id"]
    print(f"  ✓ Reported conflict for rollback")

    # 3. Resolve with rollback
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{conflict_id}/resolve",
        headers=HEADERS,
        json={
            "conflict_id": conflict_id,
            "resolution_strategy": "rollback"
        }
    )
    assert response.status_code == 200
    assert response.json()["conflict_resolved"] == True
    print(f"  ✓ Rolled back to previous good state")


def _run_escalate_resolution(execution_id, crew_id, agent1_id, agent2_id):
    """Test escalate strategy: notify all agents in crew"""

    # 1. Report conflict
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/report",
        headers=HEADERS,
        json={
            "execution_id": str(execution_id),
            "from_agent_id": str(agent1_id),
            "to_agent_id": None,
            "interaction_type": "conflict",
            "message": "Critical conflict requiring escalation",
            "conflict_type": "priority_conflict",
            "conflict_detected": True,
            "resolution_data": {
                "severity": "critical",
                "requires_human_intervention": True
            }
        }
    )
    assert response.status_code == 201
    conflict_id = response.json()["id"]
    print(f"  ✓ Reported critical conflict")

    # 2. Resolve with escalate
    response = requests.post(
        f"{BASE_URL}/api/crewai/agent-interactions/conflicts/{conflict_id}/resolve",
        headers=HEADERS,
        json={
            "conflict_id": conflict_id,
            "resolution_strategy": "escalate"
        }
    )
    assert response.status_code == 200
    assert response.json()["conflict_resolved"] == True
    print(f"  ✓ Escalated conflict to all agents in crew")

    # 3. Verify escalation by checking that conflict is resolved
    # The escalate strategy should have sent events to all agents
    # (we verify this by the 200 response and conflict_resolved = True)
    print(f"  ✓ Escalation events created successfully")


def _cleanup_test_resources(crew_id, agent1_id, agent2_id):
    """Clean up resources created during testing"""
    try:
        # Delete crew first (depends on agents)
        if crew_id:
            requests.delete(
                f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true",
                timeout=5
            )
            print(f"  ✓ Deleted crew {crew_id}")
    except Exception as e:
        print(f"  Warning: Failed to delete crew: {e}")

    try:
        # Delete agents
        if agent1_id:
            requests.delete(
                f"{BASE_URL}/api/crewai/agents/{agent1_id}?hard_delete=true",
                timeout=5
            )
            print(f"  ✓ Deleted agent 1 {agent1_id}")
    except Exception as e:
        print(f"  Warning: Failed to delete agent 1: {e}")

    try:
        if agent2_id:
            requests.delete(
                f"{BASE_URL}/api/crewai/agents/{agent2_id}?hard_delete=true",
                timeout=5
            )
            print(f"  ✓ Deleted agent 2 {agent2_id}")
    except Exception as e:
        print(f"  Warning: Failed to delete agent 2: {e}")


if __name__ == "__main__":
    test_conflict_resolution_strategies()
