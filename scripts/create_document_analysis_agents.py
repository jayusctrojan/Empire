"""
Script to create 3 Document Analysis Agents for Task 37
Implements the agent specifications from the PRD
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Document Analysis Agent configurations from PRD
DOCUMENT_ANALYSIS_AGENTS = [
    {
        "agent_name": "research_analyst",
        "role": "Senior Research Analyst",
        "goal": "Analyze documents and extract key insights, entities, and themes including: 1) Main topics and themes, 2) Key entities (people, organizations, locations), 3) Important facts and claims, 4) Document structure and organization, 5) Content quality assessment",
        "backstory": "Expert analyst with 15 years of experience in document analysis, research methodology, and information extraction. Skilled at identifying patterns, extracting structured data, and providing comprehensive analysis of complex documents.",
        "tools": ["document_search", "web_search", "summarizer"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.5,
            "max_tokens": 4096
        }
    },
    {
        "agent_name": "content_strategist",
        "role": "Content Strategy Expert",
        "goal": "Synthesize information and create actionable insights including: 1) Executive summary (3-5 sentences), 2) Key findings and insights, 3) Content categorization and taxonomy, 4) Recommendations for further analysis",
        "backstory": "Seasoned strategist specializing in content organization, taxonomy design, and strategic planning. Expert at synthesizing complex information into clear, actionable insights and creating comprehensive content frameworks.",
        "tools": ["pattern_analyzer", "theme_extractor", "categorizer"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.7,
            "max_tokens": 4096
        }
    },
    {
        "agent_name": "fact_checker",
        "role": "Senior Fact Verification Specialist",
        "goal": "Verify claims and validate information accuracy including: 1) Identify all factual claims, 2) Assess confidence level for each claim (0.0-1.0), 3) Flag potentially inaccurate or unsupported claims, 4) Provide citations or sources where possible",
        "backstory": "Meticulous fact-checker with expertise in verification methodologies and source validation. Skilled at evaluating claim accuracy, assessing confidence levels, and providing detailed fact verification reports with citations.",
        "tools": ["web_search", "database_query", "citation_validator"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.3,
            "max_tokens": 4096
        }
    }
]


def create_agent(agent_config):
    """Create a single agent via API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/crewai/agents",
            json=agent_config,
            timeout=30
        )

        if response.status_code == 201:
            data = response.json()
            print(f"✅ Created agent: {agent_config['agent_name']} (ID: {data['id']})")
            return data
        else:
            print(f"❌ Failed to create {agent_config['agent_name']}: {response.status_code}")
            print(f"   Error: {response.json()}")
            return None

    except Exception as e:
        print(f"❌ Error creating {agent_config['agent_name']}: {e}")
        return None


def main():
    print("="*70)
    print("Task 37.1: Creating 3 Document Analysis Agents")
    print("="*70)

    created_agents = []

    for i, agent_config in enumerate(DOCUMENT_ANALYSIS_AGENTS, 1):
        print(f"\n[{i}/3] Creating {agent_config['agent_name']}...")
        agent = create_agent(agent_config)
        if agent:
            created_agents.append(agent)

    print("\n" + "="*70)
    print(f"✅ Successfully created {len(created_agents)}/3 agents")
    print("="*70)

    # List all agents to verify
    print("\nVerifying agents in database...")
    response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true")
    if response.status_code == 200:
        data = response.json()
        print(f"Total active agents in database: {data['count']}")

        # Filter document analysis agents
        analysis_agents = [a for a in data['agents'] if a['agent_name'] in ['research_analyst', 'content_strategist', 'fact_checker']]
        print(f"\nDocument Analysis Agents ({len(analysis_agents)}):")
        for agent in analysis_agents:
            print(f"  - {agent['agent_name']}: {agent['role']}")

    return created_agents


if __name__ == "__main__":
    main()
