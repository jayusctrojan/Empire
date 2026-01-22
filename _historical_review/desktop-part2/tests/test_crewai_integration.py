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

# Skip all tests in this module when running pytest - they require a live server
pytestmark = pytest.mark.skip(reason="Requires running FastAPI server at localhost:8000")

BASE_URL = "http://localhost:8000"


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
    agent_data = {
        "agent_name": f"test_researcher",
        "role": "Research Specialist",
        "goal": "Research and analyze documents to extract key insights",
        "backstory": "An expert researcher with deep knowledge of information extraction",
        "tools": ["web_search", "document_parser"],
        "llm_config": {
            "model": "claude-3-5-haiku-20241022",
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
    assert data["agent_name"] == agent_data["agent_name"]
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
    crew_data = {
        "crew_name": "test_research_crew",
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
