"""
Script to create 8 Asset Generation Agents for Task 36
Implements the agent specifications from the PRD
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Agent configurations from PRD
ASSET_GENERATION_AGENTS = [
    {
        "agent_name": "main_orchestrator",
        "role": "Master Content Analyzer & Asset Orchestrator",
        "goal": "Analyze incoming content and make intelligent decisions about: 1) Department classification (12 departments including R&D), 2) Asset type selection (skill vs command vs agent vs prompt vs workflow), 3) Content summary requirements, 4) Delegation to appropriate specialized agents",
        "backstory": "Expert orchestrator with deep knowledge of asset type decision logic, department taxonomy (12 departments including research-development), and output guidelines. Skilled at analyzing content patterns and delegating to specialized agents.",
        "tools": ["document_search", "pattern_analyzer", "department_classifier"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.7,
            "max_tokens": 4096
        }
    },
    {
        "agent_name": "content_summarizer",
        "role": "Content Summary & Visualization Expert",
        "goal": "Generate comprehensive PDF summaries with: 1) Visual diagrams and flowcharts, 2) Key concepts and frameworks, 3) Implementation guides, 4) Quick reference sections, 5) Interactive tables and charts",
        "backstory": "Expert at synthesizing complex content into visual summaries. Skilled at creating diagrams, charts, and comprehensive PDF documents. Output files go to processed/crewai-summaries/{department}/ with pattern {department}_summary_{timestamp}.pdf",
        "tools": ["pdf_generator", "diagram_creator", "chart_builder"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.5,
            "max_tokens": 8192
        }
    },
    {
        "agent_name": "skill_generator",
        "role": "Claude Skills Generator",
        "goal": "Generate YAML skill definitions for Claude Code automation. Criteria: Complex reusable automation with parameters, multi-step processes. Output pattern: {department}_skill-name.yaml",
        "backstory": "Expert at extracting actionable skills from course content and creating YAML configurations for Claude Code. Skilled at identifying complex reusable automation patterns and multi-step processes that benefit from parameterization.",
        "tools": ["yaml_generator", "skill_validator"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.3,
            "max_tokens": 4096
        }
    },
    {
        "agent_name": "command_generator",
        "role": "Claude Commands Generator",
        "goal": "Generate Markdown slash commands for quick one-liner actions. Criteria: Quick one-liner actions, /command format. Output pattern: {department}_command-name.md",
        "backstory": "Expert at creating concise, executable commands for Claude Code. Specializes in identifying quick one-liner actions that users execute frequently. Masters the /command format for efficient automation.",
        "tools": ["markdown_generator", "command_validator"],
        "llm_config": {
            "model": "claude-3-5-haiku-20241022",
            "temperature": 0.2,
            "max_tokens": 2048
        }
    },
    {
        "agent_name": "agent_generator",
        "role": "CrewAI Agent Configuration Specialist",
        "goal": "Generate agent YAML configurations for role-based analysis tasks. Criteria: Multi-step role-based analysis tasks, intelligence required. Output pattern: {department}_agent-name.yaml",
        "backstory": "Expert at designing intelligent agent configurations for CrewAI. Skilled at identifying tasks that require role-based analysis, multi-step reasoning, and agent intelligence. Creates comprehensive YAML configurations with roles, goals, backstories, and tools.",
        "tools": ["agent_config_generator", "role_analyzer"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.4,
            "max_tokens": 4096
        }
    },
    {
        "agent_name": "prompt_generator",
        "role": "AI Prompt Template Generator",
        "goal": "Extract reusable prompt patterns for consistent AI interactions. Criteria: Template for consistent AI interactions, DEFAULT when unsure. Output pattern: {department}_prompt-name.md",
        "backstory": "Expert at identifying reusable prompt structures and creating templates for consistent AI interactions. Skilled at pattern recognition in prompts and extracting generalizable templates. This is the DEFAULT generator when asset type is unclear.",
        "tools": ["prompt_pattern_extractor", "template_generator"],
        "llm_config": {
            "model": "claude-3-5-haiku-20241022",
            "temperature": 0.3,
            "max_tokens": 2048
        }
    },
    {
        "agent_name": "workflow_generator",
        "role": "n8n Workflow Automation Specialist",
        "goal": "Design multi-system sequential automation workflows. Criteria: Multi-system integration, sequential pipelines. Output pattern: {department}_workflow-name.json in n8n format",
        "backstory": "Expert at orchestrating multi-system workflows using n8n. Skilled at designing sequential pipelines, integration mappings, and complex workflow automation. Creates JSON configurations that connect multiple systems and services.",
        "tools": ["workflow_designer", "integration_mapper"],
        "llm_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.5,
            "max_tokens": 8192
        }
    },
    {
        "agent_name": "department_classifier",
        "role": "Department Classification Specialist",
        "goal": "Accurately classify content into correct departments with confidence scores. Departments: it-engineering, sales-marketing, customer-support, operations-hr-supply, finance-accounting, project-management, real-estate, private-equity-ma, consulting, personal-continuing-ed",
        "backstory": "Expert at analyzing course content and classification keywords. Skilled at the 10-department taxonomy with deep knowledge of departmental keywords, themes, and content patterns. Provides confidence scores (0-1) for classifications.",
        "tools": ["file_reader", "department_classifier", "keyword_extractor"],
        "llm_config": {
            "model": "claude-3-5-haiku-20241022",
            "temperature": 0.1,
            "max_tokens": 1024
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
    print("Task 36.1: Creating 8 Asset Generation Agents")
    print("="*70)

    created_agents = []

    for i, agent_config in enumerate(ASSET_GENERATION_AGENTS, 1):
        print(f"\n[{i}/8] Creating {agent_config['agent_name']}...")
        agent = create_agent(agent_config)
        if agent:
            created_agents.append(agent)

    print("\n" + "="*70)
    print(f"✅ Successfully created {len(created_agents)}/8 agents")
    print("="*70)

    # List all agents to verify
    print("\nVerifying agents in database...")
    response = requests.get(f"{BASE_URL}/api/crewai/agents?active_only=true")
    if response.status_code == 200:
        data = response.json()
        print(f"Total active agents in database: {data['count']}")
        print("\nAgent names:")
        for agent in data['agents']:
            print(f"  - {agent['agent_name']}: {agent['role']}")

    return created_agents


if __name__ == "__main__":
    main()
