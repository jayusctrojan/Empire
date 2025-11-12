"""
Script to create Document Analysis Crew for Task 37.2
Creates a crew that orchestrates the 3 document analysis agents
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def get_agent_id_by_name(agent_name):
    """Get agent ID by name"""
    response = requests.get(f"{BASE_URL}/api/crewai/agents/by-name/{agent_name}")
    if response.status_code == 200:
        return response.json()["id"]
    return None


def create_crew(crew_config):
    """Create a crew via API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/crewai/crews",
            json=crew_config,
            timeout=30
        )

        if response.status_code == 201:
            data = response.json()
            print(f"✅ Created crew: {crew_config['crew_name']} (ID: {data['id']})")
            return data
        else:
            print(f"❌ Failed to create {crew_config['crew_name']}: {response.status_code}")
            print(f"   Error: {response.json()}")
            return None

    except Exception as e:
        print(f"❌ Error creating {crew_config['crew_name']}: {e}")
        return None


def main():
    print("="*70)
    print("Task 37.2: Creating Document Analysis Crew")
    print("="*70)

    # Get agent IDs
    print("\nFetching agent IDs...")
    agent_ids = {}
    agent_names = [
        "research_analyst",
        "content_strategist",
        "fact_checker"
    ]

    for name in agent_names:
        agent_id = get_agent_id_by_name(name)
        if agent_id:
            agent_ids[name] = agent_id
            print(f"  ✅ {name}: {agent_id}")
        else:
            print(f"  ❌ Failed to get ID for {name}")
            return

    # Define document analysis crew
    crew_config = {
        "crew_name": "document_analysis_workflow",
        "description": "Comprehensive document analysis workflow: Extract insights and entities (research_analyst), synthesize actionable findings (content_strategist), verify claims and accuracy (fact_checker)",
        "agent_ids": [
            agent_ids["research_analyst"],
            agent_ids["content_strategist"],
            agent_ids["fact_checker"]
        ],
        "process_type": "sequential",
        "memory_enabled": True,
        "verbose": False
    }

    print(f"\nCreating document analysis crew...")
    crew = create_crew(crew_config)

    if crew:
        print("\n" + "="*70)
        print("✅ Document Analysis Crew Created Successfully!")
        print("="*70)

        # Verify crew
        print("\nVerifying crew in database...")
        response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true")
        if response.status_code == 200:
            data = response.json()
            print(f"Total active crews in database: {data['count']}")

            # Find our crew
            for c in data['crews']:
                if c['crew_name'] == 'document_analysis_workflow':
                    print(f"\nCrew Details:")
                    print(f"  Name: {c['crew_name']}")
                    print(f"  Description: {c['description']}")
                    print(f"  Agents: {len(c['agent_ids'])}")
                    print(f"  Process: {c['process_type']}")
                    print(f"  Memory Enabled: {c['memory_enabled']}")

    return crew


if __name__ == "__main__":
    main()
