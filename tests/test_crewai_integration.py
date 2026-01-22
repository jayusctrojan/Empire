"""
Test suite for Task 35: CrewAI Multi-Agent Integration & Orchestration
Tests all CrewAI endpoints including agent management, crew creation, and workflow execution

NOTE: These are integration tests that require a running FastAPI server at localhost:8000.
They should be run manually, not as part of automated pytest runs.

To run manually:
1. Start the server: uvicorn app.main:app --reload
2. Run: python tests/test_crewai_integration.py
"""

import pytest
import requests
import json
from typing import Dict, Any


def _local_server_is_available() -> bool:
    """Check if the local FastAPI server is available."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        return False


# Mark all tests in this module as integration tests that require live server
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _local_server_is_available(),
        reason="Local FastAPI server not running on port 8000"
    ),
]

BASE_URL = "http://localhost:8000"

from uuid import uuid4


# ==================== Pytest Fixtures ====================

@pytest.fixture(scope="module")
def test_id():
    """Generate a unique test ID for this test run."""
    return str(uuid4())[:8]


@pytest.fixture(scope="module")
def agent_id(test_id):
    """Create and return an agent ID for testing."""
    agent_data = {
        "agent_name": f"integration_test_agent_{test_id}",
        "role": "Integration Test Agent",
        "goal": "Test CrewAI integration",
        "backstory": f"Created for integration testing - {test_id}",
        "tools": ["web_search"],
        "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
    }
    response = requests.post(f"{BASE_URL}/api/crewai/agents", json=agent_data)
    if response.status_code == 201:
        yield response.json()["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/crewai/agents/{response.json()['id']}?hard_delete=true")
    else:
        yield None


@pytest.fixture(scope="module")
def agent_ids(test_id):
    """Create and return a list of agent IDs for testing."""
    agent_data = {
        "agent_name": f"integration_test_crew_agent_{test_id}",
        "role": "Integration Test Crew Agent",
        "goal": "Be part of test crew",
        "backstory": f"Created for crew testing - {test_id}",
        "tools": ["web_search"],
        "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
    }
    response = requests.post(f"{BASE_URL}/api/crewai/agents", json=agent_data)
    if response.status_code == 201:
        agent_id = response.json()["id"]
        yield [agent_id]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
    else:
        yield []


@pytest.fixture(scope="module")
def crew_id(agent_ids, test_id):
    """Create and return a crew ID for testing."""
    if not agent_ids:
        yield None
        return

    crew_data = {
        "crew_name": f"integration_test_crew_{test_id}",
        "description": f"Test crew for integration testing - {test_id}",
        "agent_ids": agent_ids,
        "process_type": "sequential",
        "memory_enabled": False,
        "verbose": False
    }
    response = requests.post(f"{BASE_URL}/api/crewai/crews", json=crew_data)
    if response.status_code == 201:
        crew_id = response.json()["id"]
        yield crew_id
        # Cleanup
        requests.delete(f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true")
    else:
        yield None


# ==================== Test Functions ====================

def test_health_check():
    """Test Task 35.1: CrewAI health check endpoint"""
    print("\n=== Test 1: CrewAI Health Check ===")
    response = requests.get(f"{BASE_URL}/api/crewai/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    print("✅ Health check passed")
    return data


def test_list_workflows():
    """Test Task 35.2: List available workflows"""
    print("\n=== Test 2: List Available Workflows ===")
    response = requests.get(f"{BASE_URL}/api/crewai/workflows")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert "workflows" in data
    assert "count" in data
    print(f"✅ Found {data['count']} workflows")
    return data


def test_create_agent():
    """Test Task 35.1: Create a new agent"""
    print("\n=== Test 3: Create Agent ===")
    unique_id = str(uuid4())[:8]
    agent_name = f"test_researcher_{unique_id}"
    agent_data = {
        "agent_name": agent_name,
        "role": "Research Specialist",
        "goal": "Research and analyze documents to extract key insights",
        "backstory": f"An expert researcher - {unique_id}",
        "tools": ["web_search", "document_parser"],
        "llm_config": {
            "model": "claude-haiku-4-5",
            "temperature": 0.7
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/agents",
        json=agent_data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["agent_name"] == agent_name
    # Cleanup
    requests.delete(f"{BASE_URL}/api/crewai/agents/{data['id']}?hard_delete=true")
    print(f"✅ Agent created with ID: {data['id']}")
    return data


def test_list_agents():
    """Test Task 35.1: List all agents"""
    print("\n=== Test 4: List Agents ===")
    response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "count" in data
    print(f"✅ Found {data['count']} active agents")
    return data


def test_get_agent(agent_id: str):
    """Test Task 35.1: Get specific agent"""
    print(f"\n=== Test 5: Get Agent {agent_id} ===")
    response = requests.get(f"{BASE_URL}/api/crewai/agents/{agent_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == agent_id
    print("✅ Agent retrieved successfully")
    return data


def test_update_agent(agent_id: str):
    """Test Task 35.1: Update agent"""
    print(f"\n=== Test 6: Update Agent {agent_id} ===")
    update_data = {
        "goal": "Research and synthesize complex information with enhanced analytical capabilities",
        "is_active": True
    }

    response = requests.patch(
        f"{BASE_URL}/api/crewai/agents/{agent_id}",
        json=update_data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert data["goal"] == update_data["goal"]
    print("✅ Agent updated successfully")
    return data


def test_create_crew(agent_ids: list):
    """Test Task 35.2: Create a crew"""
    print(f"\n=== Test 7: Create Crew with agents: {agent_ids} ===")
    unique_crew_name = f"test_research_crew_{uuid4().hex[:8]}"
    crew_data = {
        "crew_name": unique_crew_name,
        "description": "A test crew for document analysis and research",
        "agent_ids": agent_ids,
        "process_type": "sequential",
        "memory_enabled": True,
        "verbose": False
    }

    response = requests.post(
        f"{BASE_URL}/api/crewai/crews",
        json=crew_data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["crew_name"] == crew_data["crew_name"]
    print(f"✅ Crew created with ID: {data['id']}")
    # Cleanup - delete the crew we just created
    requests.delete(f"{BASE_URL}/api/crewai/crews/{data['id']}?hard_delete=true")
    return data


def test_list_crews():
    """Test Task 35.2: List all crews"""
    print("\n=== Test 8: List Crews ===")
    response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert "crews" in data
    assert "count" in data
    print(f"✅ Found {data['count']} active crews")
    return data


def test_get_crew(crew_id: str):
    """Test Task 35.2: Get specific crew"""
    print(f"\n=== Test 9: Get Crew {crew_id} ===")
    response = requests.get(f"{BASE_URL}/api/crewai/crews/{crew_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == crew_id
    print("✅ Crew retrieved successfully")
    return data


def test_agent_pool_stats():
    """Test Task 35.1: Get agent pool statistics"""
    print("\n=== Test 10: Agent Pool Statistics ===")
    response = requests.get(f"{BASE_URL}/api/crewai/stats")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert "total_agents" in data
    assert "total_crews" in data
    print("✅ Statistics retrieved successfully")
    return data


def test_delete_crew(crew_id: str):
    """Test Task 35.2: Delete crew (soft delete)"""
    print(f"\n=== Test 11: Delete Crew {crew_id} (Soft Delete) ===")
    response = requests.delete(
        f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=false"
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["deleted_type"] == "soft"
    print("✅ Crew soft deleted successfully")
    return data


def test_delete_agent(agent_id: str):
    """Test Task 35.1: Delete agent (soft delete)"""
    print(f"\n=== Test 12: Delete Agent {agent_id} (Soft Delete) ===")
    response = requests.delete(
        f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=false"
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["deleted_type"] == "soft"
    print("✅ Agent soft deleted successfully")
    return data


def run_all_tests():
    """Run all CrewAI integration tests"""
    print("="*70)
    print("Task 35: CrewAI Multi-Agent Integration & Orchestration - Test Suite")
    print("="*70)

    try:
        # Test 1: Health check
        test_health_check()

        # Test 2: List workflows
        test_list_workflows()

        # Test 3-6: Agent Management (Task 35.1)
        agent = test_create_agent()
        agent_id = agent["id"]

        test_list_agents()
        test_get_agent(agent_id)
        test_update_agent(agent_id)

        # Test 7-9: Crew Management (Task 35.2)
        crew = test_create_crew([agent_id])
        crew_id = crew["id"]

        test_list_crews()
        test_get_crew(crew_id)

        # Test 10: Statistics
        test_agent_pool_stats()

        # Test 11-12: Cleanup (soft delete)
        test_delete_crew(crew_id)
        test_delete_agent(agent_id)

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED - Task 35 Implementation Verified")
        print("="*70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"\n❌ REQUEST ERROR: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
