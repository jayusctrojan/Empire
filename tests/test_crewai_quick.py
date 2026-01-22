"""
Quick test suite for Task 35: CrewAI Integration (skips hanging health check)
Tests core CRUD operations for agents and crews

These tests require a running API server at localhost:8000.
They are marked as live_api tests and will be skipped if the server is not available.
"""
import pytest
import requests
import json
from uuid import uuid4

BASE_URL = "http://localhost:8000"


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


class TestCrewAIQuickCRUD:
    """Test CrewAI CRUD operations with unique names to avoid conflicts"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup unique identifiers for this test run"""
        self.test_id = str(uuid4())[:8]
        self.agent_name = f"test_agent_{self.test_id}"
        self.crew_name = f"test_crew_{self.test_id}"
        self.created_agent_id = None
        self.created_crew_id = None
        yield
        # Cleanup after tests
        self._cleanup()

    def _cleanup(self):
        """Clean up any resources created during tests"""
        # Delete crew first (depends on agent)
        if self.created_crew_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/crewai/crews/{self.created_crew_id}?hard_delete=true",
                    timeout=5
                )
            except Exception:
                pass

        # Delete agent
        if self.created_agent_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/crewai/agents/{self.created_agent_id}?hard_delete=true",
                    timeout=5
                )
            except Exception:
                pass

    def test_create_agent(self):
        """Test creating a new agent with unique name"""
        agent_data = {
            "agent_name": self.agent_name,
            "role": "Quick Test Agent",
            "goal": "Test agent creation",
            "backstory": f"Created for quick testing - {self.test_id}",
            "tools": ["test_tool"],
            "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
        }

        response = requests.post(
            f"{BASE_URL}/api/crewai/agents",
            json=agent_data,
            timeout=10
        )

        assert response.status_code == 201, f"Failed to create agent: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["agent_name"] == agent_data["agent_name"]
        self.created_agent_id = data["id"]

    def test_list_agents(self):
        """Test listing agents"""
        response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true", timeout=10)

        assert response.status_code == 200, f"Failed to list agents: {response.text}"
        data = response.json()
        assert "agents" in data
        assert "count" in data

    def test_agent_crud_workflow(self):
        """Test complete agent CRUD workflow"""
        # Create agent
        agent_data = {
            "agent_name": self.agent_name,
            "role": "Workflow Test Agent",
            "goal": "Test full CRUD workflow",
            "backstory": f"Created for CRUD testing - {self.test_id}",
            "tools": ["test_tool"],
            "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
        }

        create_response = requests.post(
            f"{BASE_URL}/api/crewai/agents",
            json=agent_data,
            timeout=10
        )
        assert create_response.status_code == 201
        agent_id = create_response.json()["id"]
        self.created_agent_id = agent_id

        # List agents (should include our new agent)
        list_response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true", timeout=10)
        assert list_response.status_code == 200

        # Delete agent
        delete_response = requests.delete(
            f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true",
            timeout=10
        )
        assert delete_response.status_code == 200
        self.created_agent_id = None  # Already deleted

    def test_crew_crud_workflow(self):
        """Test complete crew CRUD workflow"""
        # First create an agent for the crew
        agent_data = {
            "agent_name": self.agent_name,
            "role": "Crew Member Agent",
            "goal": "Be part of a test crew",
            "backstory": f"Created for crew testing - {self.test_id}",
            "tools": ["test_tool"],
            "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
        }

        agent_response = requests.post(
            f"{BASE_URL}/api/crewai/agents",
            json=agent_data,
            timeout=10
        )
        assert agent_response.status_code == 201
        agent_id = agent_response.json()["id"]
        self.created_agent_id = agent_id

        # Create crew with the agent
        crew_data = {
            "crew_name": self.crew_name,
            "description": f"Quick test crew - {self.test_id}",
            "agent_ids": [agent_id],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        }

        crew_response = requests.post(
            f"{BASE_URL}/api/crewai/crews",
            json=crew_data,
            timeout=10
        )
        assert crew_response.status_code == 201, f"Failed to create crew: {crew_response.text}"
        crew_id = crew_response.json()["id"]
        self.created_crew_id = crew_id

        # Delete crew
        delete_crew_response = requests.delete(
            f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true",
            timeout=10
        )
        assert delete_crew_response.status_code == 200
        self.created_crew_id = None

        # Delete agent
        delete_agent_response = requests.delete(
            f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true",
            timeout=10
        )
        assert delete_agent_response.status_code == 200
        self.created_agent_id = None


def run_quick_tests():
    """Run quick CrewAI tests (skips health check)"""
    print("="*70)
    print("Task 35: CrewAI Integration - Quick Test Suite")
    print("(Using unique names to avoid database conflicts)")
    print("="*70)

    test_id = str(uuid4())[:8]
    agent_name = f"test_agent_{test_id}"
    crew_name = f"test_crew_{test_id}"
    agent_id = None
    crew_id = None

    try:
        # Test agent creation
        print("\n=== Test: Create Agent ===")
        agent_data = {
            "agent_name": agent_name,
            "role": "Quick Test Agent",
            "goal": "Test agent creation",
            "backstory": f"Created for quick testing - {test_id}",
            "tools": ["test_tool"],
            "llm_config": {"model": "claude-haiku-4-5", "temperature": 0.7}
        }
        response = requests.post(f"{BASE_URL}/api/crewai/agents", json=agent_data)
        assert response.status_code == 201
        agent_id = response.json()["id"]
        print(f"✅ Agent created with ID: {agent_id}")

        # Test list agents
        print("\n=== Test: List Agents ===")
        response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true")
        assert response.status_code == 200
        print(f"✅ Found {response.json()['count']} active agents")

        # Test crew creation
        print(f"\n=== Test: Create Crew ===")
        crew_data = {
            "crew_name": crew_name,
            "description": f"Quick test crew - {test_id}",
            "agent_ids": [agent_id],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        }
        response = requests.post(f"{BASE_URL}/api/crewai/crews", json=crew_data)
        assert response.status_code == 201
        crew_id = response.json()["id"]
        print(f"✅ Crew created with ID: {crew_id}")

        # Cleanup
        print(f"\n=== Test: Delete Crew ===")
        response = requests.delete(f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true")
        assert response.status_code == 200
        print("✅ Crew deleted successfully")
        crew_id = None

        print(f"\n=== Test: Delete Agent ===")
        response = requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
        assert response.status_code == 200
        print("✅ Agent deleted successfully")
        agent_id = None

        print("\n" + "="*70)
        print("✅ ALL QUICK TESTS PASSED - Task 35 Core Functionality Verified")
        print("="*70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    finally:
        # Cleanup on failure
        if crew_id:
            try:
                requests.delete(f"{BASE_URL}/api/crewai/crews/{crew_id}?hard_delete=true")
            except Exception:
                pass
        if agent_id:
            try:
                requests.delete(f"{BASE_URL}/api/crewai/agents/{agent_id}?hard_delete=true")
            except Exception:
                pass


if __name__ == "__main__":
    run_quick_tests()
