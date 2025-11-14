#!/usr/bin/env python3
"""
Update document analysis agents to use Claude Sonnet 4.5
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Agent IDs and their temperature settings
AGENTS = [
    {
        "id": "57ac031d-e2d2-4c97-86e8-89fac2a4b0a8",
        "name": "research_analyst",
        "temperature": 0.5
    },
    {
        "id": "000a2cc5-e549-436d-98bf-11c46cd643cf",
        "name": "content_strategist",
        "temperature": 0.7
    },
    {
        "id": "b41a8338-e0ea-4a1d-943f-8267c2534b55",
        "name": "fact_checker",
        "temperature": 0.3
    }
]

def update_agent_model(agent_id, agent_name, temperature):
    """Update agent to use Sonnet 4.5"""
    update_data = {
        "llm_config": {
            "model": "claude-sonnet-4-5-20250929",
            "temperature": temperature,
            "max_tokens": 4096
        }
    }

    try:
        response = requests.patch(
            f"{BASE_URL}/api/crewai/agents/{agent_id}",
            json=update_data,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Updated {agent_name}")
            print(f"   Model: {data['llm_config']['model']}")
            print(f"   Temperature: {data['llm_config']['temperature']}")
            return True
        else:
            print(f"❌ Failed to update {agent_name}: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error updating {agent_name}: {e}")
        return False

def main():
    print("="*70)
    print("Updating Document Analysis Agents to Claude Sonnet 4.5")
    print("="*70)
    print()

    success_count = 0

    for agent in AGENTS:
        print(f"Updating {agent['name']}...")
        if update_agent_model(agent['id'], agent['name'], agent['temperature']):
            success_count += 1
        print()

    print("="*70)
    print(f"✅ Successfully updated {success_count}/3 agents to Sonnet 4.5")
    print("="*70)

    # Verify updates
    print("\nVerifying updates via API...")
    response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true")
    if response.status_code == 200:
        data = response.json()
        analysis_agents = [
            a for a in data['agents']
            if a['agent_name'] in ['research_analyst', 'content_strategist', 'fact_checker']
        ]

        print(f"\nDocument Analysis Agents ({len(analysis_agents)}):")
        for agent in analysis_agents:
            model = agent['llm_config'].get('model', 'N/A')
            temp = agent['llm_config'].get('temperature', 'N/A')
            print(f"  - {agent['agent_name']}: {model} @ temp={temp}")

if __name__ == "__main__":
    main()
