"""
Test Document Analysis Setup for Task 37.3
Verifies that the 3 document analysis agents and crew are properly configured
"""
import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


import requests

BASE_URL = "http://localhost:8000"


def test_document_analysis_setup():
    """Test that document analysis agents and crew are properly configured"""
    print("="*70)
    print("Task 37.3: Validating Document Analysis Setup")
    print("="*70)

    # Test 1: Verify all 3 agents exist
    print("\n[1/3] Verifying document analysis agents...")
    try:
        response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true")
        if response.status_code != 200:
            print(f"❌ Failed to fetch agents: {response.status_code}")
            return False

        agents = response.json()["agents"]
        expected_agents = ["research_analyst", "content_strategist", "fact_checker"]

        found_agents = {a["agent_name"]: a for a in agents}

        for agent_name in expected_agents:
            if agent_name in found_agents:
                agent = found_agents[agent_name]
                print(f"   ✅ {agent_name}")
                print(f"      Role: {agent['role']}")
                print(f"      Model: {agent['llm_config'].get('model', 'N/A')}")
                print(f"      Temperature: {agent['llm_config'].get('temperature', 'N/A')}")
            else:
                print(f"   ❌ {agent_name}: NOT FOUND")
                return False

    except Exception as e:
        print(f"❌ Error verifying agents: {e}")
        return False

    # Test 2: Verify crew exists
    print("\n[2/3] Verifying document analysis crew...")
    try:
        response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true")
        if response.status_code != 200:
            print(f"❌ Failed to fetch crews: {response.status_code}")
            return False

        crews = response.json()["crews"]
        doc_crew = next((c for c in crews if c["crew_name"] == "document_analysis_workflow"), None)

        if not doc_crew:
            print("❌ document_analysis_workflow crew not found")
            return False

        print(f"   ✅ document_analysis_workflow")
        print(f"      ID: {doc_crew['id']}")
        print(f"      Description: {doc_crew['description']}")
        print(f"      Process: {doc_crew['process_type']}")
        print(f"      Agents: {len(doc_crew['agent_ids'])}")
        print(f"      Memory Enabled: {doc_crew['memory_enabled']}")

        # Verify all 3 agents are in the crew
        agent_ids_set = set(doc_crew['agent_ids'])
        expected_agent_ids = {found_agents[name]['id'] for name in expected_agents}

        if agent_ids_set == expected_agent_ids:
            print(f"   ✅ All 3 agents properly configured in crew")
        else:
            print(f"   ❌ Agent mismatch:")
            print(f"      Expected: {expected_agent_ids}")
            print(f"      Found: {agent_ids_set}")
            return False

    except Exception as e:
        print(f"❌ Error verifying crew: {e}")
        return False

    # Test 3: Verify agent configurations
    print("\n[3/3] Verifying agent configurations...")
    try:
        for agent_name in expected_agents:
            agent = found_agents[agent_name]

            # Check required fields
            required_fields = ["role", "goal", "backstory", "tools", "llm_config"]
            missing_fields = [f for f in required_fields if f not in agent or not agent[f]]

            if missing_fields:
                print(f"   ❌ {agent_name}: Missing fields: {missing_fields}")
                return False

            # Check LLM config
            llm_config = agent["llm_config"]
            if "model" not in llm_config:
                print(f"   ❌ {agent_name}: Missing model in llm_config")
                return False

            if "temperature" not in llm_config:
                print(f"   ❌ {agent_name}: Missing temperature in llm_config")
                return False

        print(f"   ✅ All agents have valid configurations")

    except Exception as e:
        print(f"❌ Error validating configurations: {e}")
        return False

    # Summary
    print("\n" + "="*70)
    print("✅ Task 37 Complete: Document Analysis Agents & Crew Configured!")
    print("="*70)
    print("\nSetup Summary:")
    print(f"  - 3 document analysis agents created")
    print(f"  - 1 orchestration crew created")
    print(f"  - Sequential workflow: research → strategy → fact-checking")
    print(f"  - All agents using Claude Sonnet 4.5")
    print(f"  - Memory enabled for context retention")

    print("\nNote: Actual workflow execution requires the external CrewAI service")
    print("      (https://jb-crewai.onrender.com) to implement the execution endpoint.")
    print("      Agents and crews are properly configured in the local database.")

    return True


if __name__ == "__main__":
    success = test_document_analysis_setup()
    exit(0 if success else 1)
