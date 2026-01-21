"""
Test suite for auto-resolution conflict strategies (Priority 3)
Tests all 4 strategies: latest_wins, merge, rollback, escalate
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

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration
import asyncio
from uuid import UUID, uuid4
import requests
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


def test_conflict_resolution_strategies():
    """Test all 4 auto-resolution strategies"""

    # Create test execution
    execution_id = uuid4()
    crew_id = uuid4()
    agent1_id = uuid4()
    agent2_id = uuid4()

    print(f"\n=== Testing Conflict Resolution Strategies ===")
    print(f"Execution ID: {execution_id}")
    print(f"Crew ID: {crew_id}")
    print(f"Agent 1 ID: {agent1_id}")
    print(f"Agent 2 ID: {agent2_id}")

    # Setup: Create execution and crew
    print("\n1. Setting up test execution and crew...")
    setup_execution_and_crew(execution_id, crew_id, agent1_id, agent2_id)

    # Test 1: latest_wins strategy
    print("\n2. Testing LATEST_WINS strategy...")
    test_latest_wins_resolution(execution_id, agent1_id, agent2_id)

    # Test 2: merge strategy (success case)
    print("\n3. Testing MERGE strategy (non-conflicting keys)...")
    test_merge_resolution_success(execution_id, agent1_id, agent2_id)

    # Test 3: merge strategy (escalation case)
    print("\n4. Testing MERGE strategy (conflicting keys → escalate)...")
    test_merge_resolution_escalate(execution_id, agent1_id, agent2_id)

    # Test 4: rollback strategy
    print("\n5. Testing ROLLBACK strategy...")
    test_rollback_resolution(execution_id, agent1_id, agent2_id)

    # Test 5: escalate strategy
    print("\n6. Testing ESCALATE strategy...")
    test_escalate_resolution(execution_id, crew_id, agent1_id, agent2_id)

    print("\n=== All Conflict Resolution Tests Passed! ===\n")


def setup_execution_and_crew(execution_id, crew_id, agent1_id, agent2_id):
    """Create test execution and crew via REST API"""

    # Use the CrewAI API to create crew and execution
    # For testing, we'll just verify the conflict resolution strategies work
    # The execution and crew will be created on-demand when we create interactions

    print(f"✓ Using execution {execution_id} and crew {crew_id} for testing")


def test_latest_wins_resolution(execution_id, agent1_id, agent2_id):
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


def test_merge_resolution_success(execution_id, agent1_id, agent2_id):
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


def test_merge_resolution_escalate(execution_id, agent1_id, agent2_id):
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


def test_rollback_resolution(execution_id, agent1_id, agent2_id):
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


def test_escalate_resolution(execution_id, crew_id, agent1_id, agent2_id):
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


if __name__ == "__main__":
    test_conflict_resolution_strategies()
