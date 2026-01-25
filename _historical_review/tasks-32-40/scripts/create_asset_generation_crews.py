"""
Script to create Asset Generation Crews for Task 36.2
Creates specialized crews that orchestrate the 8 asset generation agents
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
    print("Task 36.2: Creating Asset Generation Crews")
    print("="*70)

    # Get agent IDs
    print("\nFetching agent IDs...")
    agent_ids = {}
    agent_names = [
        "main_orchestrator",
        "content_summarizer",
        "skill_generator",
        "command_generator",
        "agent_generator",
        "prompt_generator",
        "workflow_generator",
        "department_classifier"
    ]

    for name in agent_names:
        agent_id = get_agent_id_by_name(name)
        if agent_id:
            agent_ids[name] = agent_id
            print(f"  ✅ {name}: {agent_id}")
        else:
            print(f"  ❌ Failed to get ID for {name}")
            return

    # Define crews for asset generation workflows
    crews = [
        {
            "crew_name": "asset_generation_full_workflow",
            "description": "Full asset generation workflow: classify department, analyze content, generate all asset types (skills, commands, agents, prompts, workflows, summaries)",
            "agent_ids": [
                agent_ids["main_orchestrator"],
                agent_ids["department_classifier"],
                agent_ids["content_summarizer"],
                agent_ids["skill_generator"],
                agent_ids["command_generator"],
                agent_ids["agent_generator"],
                agent_ids["prompt_generator"],
                agent_ids["workflow_generator"]
            ],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        },
        {
            "crew_name": "quick_classification_and_summary",
            "description": "Quick workflow for department classification and content summarization only",
            "agent_ids": [
                agent_ids["department_classifier"],
                agent_ids["content_summarizer"]
            ],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        },
        {
            "crew_name": "skill_command_generation",
            "description": "Generate Claude Code skills and slash commands from course content",
            "agent_ids": [
                agent_ids["main_orchestrator"],
                agent_ids["skill_generator"],
                agent_ids["command_generator"]
            ],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        },
        {
            "crew_name": "agent_workflow_generation",
            "description": "Generate CrewAI agent configs and n8n workflow automation",
            "agent_ids": [
                agent_ids["main_orchestrator"],
                agent_ids["agent_generator"],
                agent_ids["workflow_generator"]
            ],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        },
        {
            "crew_name": "prompt_template_extraction",
            "description": "Extract reusable AI prompt templates from content",
            "agent_ids": [
                agent_ids["main_orchestrator"],
                agent_ids["prompt_generator"]
            ],
            "process_type": "sequential",
            "memory_enabled": True,
            "verbose": False
        }
    ]

    print(f"\nCreating {len(crews)} specialized crews...")
    created_crews = []

    for i, crew_config in enumerate(crews, 1):
        print(f"\n[{i}/{len(crews)}] Creating {crew_config['crew_name']}...")
        crew = create_crew(crew_config)
        if crew:
            created_crews.append(crew)

    print("\n" + "="*70)
    print(f"✅ Successfully created {len(created_crews)}/{len(crews)} crews")
    print("="*70)

    # Verify crews
    print("\nVerifying crews in database...")
    response = requests.get(f"{BASE_URL}/api/crewai/crews?active_only=true")
    if response.status_code == 200:
        data = response.json()
        print(f"Total active crews in database: {data['count']}")
        print("\nCrew details:")
        for crew in data['crews']:
            print(f"  - {crew['crew_name']}")
            print(f"    Agents: {len(crew['agent_ids'])}")
            print(f"    Process: {crew['process_type']}")

    return created_crews


if __name__ == "__main__":
    main()
