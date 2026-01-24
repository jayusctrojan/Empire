#!/usr/bin/env python3
"""
Empire v7.2 - Complete CrewAI Configuration
Main orchestrator and specialized agents for content analysis and asset generation.
"""

from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from typing import Dict, List, Any, Type
from pydantic import BaseModel, Field
import os
from datetime import datetime


# =============================================================================
# TOOL DEFINITIONS
# CrewAI requires actual Tool objects, not string names.
# These are placeholder implementations that should be enhanced for production.
# =============================================================================

class ContentAnalyzerInput(BaseModel):
    """Input schema for content analyzer tool."""
    content: str = Field(description="The content to analyze")


class ContentAnalyzerTool(BaseTool):
    """Tool for analyzing content structure and extracting key information."""
    name: str = "content_analyzer"
    description: str = "Analyzes content to extract structure, key topics, and metadata"
    args_schema: Type[BaseModel] = ContentAnalyzerInput

    def _run(self, content: str) -> str:
        """Analyze content and return structured analysis."""
        # Placeholder implementation - enhance for production
        word_count = len(content.split())
        return f"Content analyzed: {word_count} words. Key topics extracted."


class DepartmentClassifierInput(BaseModel):
    """Input schema for department classifier tool."""
    content: str = Field(description="The content to classify")


class DepartmentClassifierTool(BaseTool):
    """Tool for classifying content into business departments."""
    name: str = "department_classifier"
    description: str = "Classifies content into one of 10 business departments"
    args_schema: Type[BaseModel] = DepartmentClassifierInput

    def _run(self, content: str) -> str:
        """Classify content into a department."""
        # Placeholder implementation - enhance for production
        return "Department classification completed."


class YamlGeneratorInput(BaseModel):
    """Input schema for YAML generator tool."""
    data: str = Field(description="The data to convert to YAML format")


class YamlGeneratorTool(BaseTool):
    """Tool for generating YAML output."""
    name: str = "yaml_generator"
    description: str = "Generates properly formatted YAML output"
    args_schema: Type[BaseModel] = YamlGeneratorInput

    def _run(self, data: str) -> str:
        """Generate YAML from data."""
        return f"YAML generated from input data."


class MarkdownGeneratorInput(BaseModel):
    """Input schema for Markdown generator tool."""
    content: str = Field(description="The content to format as Markdown")


class MarkdownGeneratorTool(BaseTool):
    """Tool for generating Markdown output."""
    name: str = "markdown_generator"
    description: str = "Generates properly formatted Markdown output"
    args_schema: Type[BaseModel] = MarkdownGeneratorInput

    def _run(self, content: str) -> str:
        """Generate Markdown from content."""
        return f"Markdown generated from input content."


class JsonGeneratorInput(BaseModel):
    """Input schema for JSON generator tool."""
    data: str = Field(description="The data to convert to JSON format")


class JsonGeneratorTool(BaseTool):
    """Tool for generating JSON output."""
    name: str = "json_generator"
    description: str = "Generates properly formatted JSON output"
    args_schema: Type[BaseModel] = JsonGeneratorInput

    def _run(self, data: str) -> str:
        """Generate JSON from data."""
        return f"JSON generated from input data."


# Instantiate tool objects for use in agents
content_analyzer_tool = ContentAnalyzerTool()
department_classifier_tool = DepartmentClassifierTool()
yaml_generator_tool = YamlGeneratorTool()
markdown_generator_tool = MarkdownGeneratorTool()
json_generator_tool = JsonGeneratorTool()

# Department codes for classification
DEPARTMENTS = [
    "it-engineering",
    "sales-marketing",
    "customer-support",
    "operations-hr-supply",
    "finance-accounting",
    "project-management",
    "real-estate",
    "private-equity-ma",
    "consulting",
    "personal-continuing-ed",
    "_global"
]

# Asset type definitions
ASSET_TYPES = {
    "claude-skills": {
        "extension": ".yaml",
        "folder": "claude-skills",
        "description": "Reusable automation tasks with complex logic"
    },
    "claude-commands": {
        "extension": ".md",
        "folder": "claude-commands",
        "description": "Quick actions and simple one-liner commands"
    },
    "agents": {
        "extension": ".yaml",
        "folder": "agents",
        "description": "Multi-step role-based intelligent agents"
    },
    "prompts": {
        "extension": ".md",
        "folder": "prompts",
        "description": "Reusable AI prompt templates"
    },
    "workflows": {
        "extension": ".json",
        "folder": "workflows",
        "description": "Multi-system automation sequences"
    }
}


class EmpireCrewAgents:
    """Factory for all Empire CrewAI agents"""

    def __init__(self):
        # Load knowledge sources
        self.output_guidelines = self._load_file('CREWAI_OUTPUT_GUIDELINES.md')
        self.department_taxonomy = self._load_file('B2_FOLDER_STRUCTURE.md')
        self.quick_reference = self._load_file('CREWAI_QUICK_REFERENCE.md')

    def _load_file(self, filename: str) -> str:
        """Load knowledge source file"""
        try:
            with open(filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return f"[File {filename} not found - agent will use default knowledge]"

    def create_main_orchestrator(self) -> Agent:
        """
        Main orchestrator agent that analyzes content and decides:
        1. Which department it belongs to
        2. What type of assets to generate (skill, command, agent, prompt, workflow)
        3. Which specialized agents to delegate to
        """
        return Agent(
            role="Master Content Analyzer & Asset Orchestrator",
            goal="""
            Analyze incoming content and make intelligent decisions about:
            1. Department classification
            2. Asset type selection (skill vs command vs agent vs prompt vs workflow)
            3. Content summary requirements (detailed PDF with visuals)
            4. Delegation to appropriate specialized agents
            """,
            backstory=f"""
            You are the master orchestrator for Empire v7.2. You have deep knowledge of:

            DECISION LOGIC FOR ASSET TYPES:
            - claude-skill: Complex reusable automation with parameters
            - claude-command: Quick one-liner actions (/command format)
            - agent: Multi-step role-based analysis tasks
            - prompt: Template for consistent AI interactions
            - workflow: Multi-system sequential automation

            DEPARTMENT CODES:
            {', '.join(DEPARTMENTS)}

            CRITICAL RULES:
            1. ALWAYS classify content into correct department
            2. ALWAYS decide appropriate asset type(s) to generate
            3. ALWAYS consider if content needs detailed PDF summary
            4. ALWAYS use filename format: {{department}}_{{name}}.{{ext}}

            KNOWLEDGE BASE:
            {self.quick_reference[:2000]}
            """,
            tools=[
                content_analyzer_tool,
                department_classifier_tool,
            ],
            allow_delegation=True,
            max_iterations=3,
            verbose=True
        )

    def create_content_summarizer(self) -> Agent:
        """
        Content Summarizer Agent - Creates detailed PDFs with images, tables, frameworks
        Output: processed/crewai-summaries/{department}/
        """
        return Agent(
            role="Content Deep-Dive Summarizer & Visual Extractor",
            goal="""
            Create comprehensive PDF summaries of content with:
            1. Detailed module/section breakdowns
            2. Extracted tables and data structures
            3. Important frameworks and models
            4. Key images and diagrams
            5. Implementation guides
            6. Quick reference sheets
            """,
            backstory="""
            You are an expert at analyzing all types of content (courses, documents, videos,
            articles, whitepapers) and creating comprehensive visual summaries. You excel at:

            EXTRACTION CAPABILITIES:
            - Module/chapter structure with learning objectives
            - Data tables and comparison matrices
            - Business frameworks (SWOT, Porter's 5 Forces, etc.)
            - Technical architectures and diagrams
            - Step-by-step processes and workflows
            - Key metrics and KPIs
            - Implementation checklists
            - Quick reference guides

            OUTPUT FORMAT:
            - PDF with professional formatting
            - Clear section headers and navigation
            - Visual elements (tables, charts, diagrams)
            - Color-coded by importance/type
            - Executive summary on first page
            - Detailed breakdowns in subsequent pages

            OUTPUT LOCATION:
            processed/crewai-summaries/{department}/{department}_content_summary_YYYYMMDD.pdf

            IMPORTANT: Not all content needs a detailed summary. Focus on:
            - Educational/training materials
            - Complex technical documentation
            - Strategic frameworks
            - Implementation guides
            - Materials with rich visual content
            """,
            tools=[
                content_analyzer_tool,
                markdown_generator_tool,
            ],
            allow_delegation=False,
            max_iterations=5,
            verbose=True
        )

    def create_skill_generator(self) -> Agent:
        """
        Claude Skills Generator - Creates YAML skill definitions
        Output: processed/crewai-suggestions/claude-skills/drafts/
        """
        return Agent(
            role="Claude Skills Architect",
            goal="Generate production-ready YAML skill definitions for Claude Code automation",
            backstory=f"""
            You specialize in creating Claude Code skills. You understand:

            WHEN TO CREATE A SKILL:
            - Complex reusable automation tasks
            - Operations requiring parameters and logic
            - Multi-step processes with decision points
            - Tasks that save significant time when automated

            SKILL STRUCTURE:
            {self.output_guidelines[2000:4000] if len(self.output_guidelines) > 4000 else 'Use standard YAML skill template'}

            NAMING CONVENTION: {{department}}_{{skill-name}}.yaml

            QUALITY STANDARDS:
            - Include parameter validation
            - Provide usage examples
            - Handle edge cases
            - Clear documentation
            - Production-ready (no placeholders)
            """,
            tools=[yaml_generator_tool],
            allow_delegation=False,
            verbose=True
        )

    def create_command_generator(self) -> Agent:
        """
        Claude Commands Generator - Creates Markdown slash commands
        Output: processed/crewai-suggestions/claude-commands/drafts/
        """
        return Agent(
            role="Claude Commands Designer",
            goal="Generate concise Markdown slash commands for quick Claude Desktop actions",
            backstory="""
            You create slash commands for Claude Desktop. You understand:

            WHEN TO CREATE A COMMAND:
            - Quick one-liner actions
            - Simple queries or lookups
            - Frequently used shortcuts
            - Actions that don't need complex logic

            COMMAND FORMAT:
            - Starts with / (slash)
            - Short, memorable name
            - Clear usage instructions
            - Examples included

            NAMING: {department}_command-name.md

            Keep commands simple and fast to execute.
            """,
            tools=[markdown_generator_tool],
            allow_delegation=False,
            verbose=True
        )

    def create_agent_generator(self) -> Agent:
        """
        CrewAI Agent Generator - Creates YAML agent configurations
        Output: processed/crewai-suggestions/agents/drafts/
        """
        return Agent(
            role="CrewAI Agent Designer",
            goal="Generate specialized CrewAI agent configurations for multi-step intelligent tasks",
            backstory="""
            You design CrewAI agents for complex role-based tasks. You understand:

            WHEN TO CREATE AN AGENT:
            - Multi-step analysis requiring intelligence
            - Role-based tasks (analyst, coach, advisor)
            - Tasks requiring collaboration between agents
            - Complex decision-making processes

            AGENT COMPONENTS:
            - Clear role and goal
            - Detailed backstory
            - Required tools
            - Delegation capabilities
            - Output specifications

            NAMING: {department}_agent-name.yaml

            Agents should be autonomous and goal-oriented.
            """,
            tools=[yaml_generator_tool],
            allow_delegation=False,
            verbose=True
        )

    def create_prompt_generator(self) -> Agent:
        """
        AI Prompt Template Generator - Creates reusable prompt templates
        Output: processed/crewai-suggestions/prompts/drafts/
        """
        return Agent(
            role="AI Prompt Engineer",
            goal="Generate reusable prompt templates for consistent AI interactions",
            backstory="""
            You are an expert prompt engineer. You understand:

            WHEN TO CREATE A PROMPT:
            - Reusable templates for common tasks
            - Standardized formats for consistency
            - Complex prompts with variables
            - Templates that improve AI output quality
            - Default choice when unsure of asset type

            PROMPT STRUCTURE:
            - Clear context section
            - Variable placeholders {{var}}
            - Expected output format
            - Examples when helpful
            - Quality criteria

            NAMING: {department}_prompt-name.md

            Focus on clarity, reusability, and consistent high-quality outputs.
            """,
            tools=[markdown_generator_tool],
            allow_delegation=False,
            verbose=True
        )

    def create_workflow_generator(self) -> Agent:
        """
        n8n Workflow Generator - Creates JSON workflow definitions
        Output: processed/crewai-suggestions/workflows/drafts/
        """
        return Agent(
            role="n8n Workflow Architect",
            goal="Generate n8n workflow definitions for multi-system automation",
            backstory="""
            You design n8n workflows for complex automation. You understand:

            WHEN TO CREATE A WORKFLOW:
            - Multi-system integrations
            - Sequential processing pipelines
            - Scheduled automations
            - Event-driven processes
            - Data transformation flows

            WORKFLOW COMPONENTS:
            - Trigger nodes
            - Processing nodes
            - Integration nodes
            - Error handling
            - Data routing

            NAMING: {department}_workflow-name.json

            Workflows should be robust with proper error handling.
            """,
            tools=[json_generator_tool],
            allow_delegation=False,
            verbose=True
        )

    def create_department_classifier(self) -> Agent:
        """
        Department Classification Specialist
        """
        return Agent(
            role="Department Classification Specialist",
            goal="Accurately classify content into one of 10 business departments",
            backstory=f"""
            You are an expert at departmental classification. You know:

            DEPARTMENTS AND KEYWORDS:
            {self.department_taxonomy[:3000] if self.department_taxonomy else 'Use department list'}

            CLASSIFICATION RULES:
            1. Analyze content keywords and context
            2. Match to most relevant department
            3. Use _global for cross-department content
            4. Consider primary audience and use case

            You ensure content is routed to the correct department every time.
            """,
            tools=[content_analyzer_tool, department_classifier_tool],
            allow_delegation=False,
            verbose=True
        )


class EmpireCrewOrchestrator:
    """Main orchestrator for Empire CrewAI operations"""

    def __init__(self):
        self.agent_factory = EmpireCrewAgents()

        # Create all agents
        self.orchestrator = self.agent_factory.create_main_orchestrator()
        self.content_summarizer = self.agent_factory.create_content_summarizer()
        self.skill_generator = self.agent_factory.create_skill_generator()
        self.command_generator = self.agent_factory.create_command_generator()
        self.agent_generator = self.agent_factory.create_agent_generator()
        self.prompt_generator = self.agent_factory.create_prompt_generator()
        self.workflow_generator = self.agent_factory.create_workflow_generator()
        self.department_classifier = self.agent_factory.create_department_classifier()

    def analyze_content(self, content: str, filename: str = None) -> Dict[str, Any]:
        """
        Main entry point for content analysis

        Returns:
            {
                "department": "sales-marketing",
                "assets_to_generate": ["skill", "prompt", "summary"],
                "outputs": {
                    "skill": "path/to/skill.yaml",
                    "prompt": "path/to/prompt.md",
                    "summary": "path/to/summary.pdf"
                }
            }
        """

        # Task 1: Analyze and classify
        classification_task = Task(
            description=f"""
            Analyze this content and determine:
            1. Which department it belongs to
            2. What types of assets should be generated
            3. Whether it needs a detailed PDF summary

            Content: {content[:5000]}
            Filename: {filename}

            Return a structured decision including:
            - department: one of {DEPARTMENTS}
            - asset_types: list of types to generate
            - needs_summary: boolean for PDF summary
            - reasoning: explanation of decisions
            """,
            agent=self.orchestrator,
            expected_output="Structured classification and asset type decisions"
        )

        # Task 2: Generate detailed summary if needed
        summary_task = Task(
            description="""
            IF content needs a detailed summary:
            Create a comprehensive PDF with:
            - Module/section breakdowns
            - Extracted tables and data
            - Important frameworks
            - Visual elements
            - Implementation guides

            Save to: processed/crewai-summaries/{department}/
            """,
            agent=self.content_summarizer,
            expected_output="PDF summary with visuals (if applicable)"
        )

        # Task 3: Generate appropriate assets based on decisions
        asset_generation_task = Task(
            description="""
            Based on the orchestrator's decisions, generate the appropriate assets:
            - If skill needed → Generate YAML skill definition
            - If command needed → Generate Markdown command
            - If agent needed → Generate agent configuration
            - If prompt needed → Generate prompt template
            - If workflow needed → Generate n8n workflow

            Use correct filename format: {department}_{name}.{ext}
            Save to: processed/crewai-suggestions/{asset-type}/drafts/
            """,
            agent=self.orchestrator,  # Orchestrator delegates to specialists
            expected_output="Generated assets in appropriate formats"
        )

        # Create crew with all agents
        crew = Crew(
            agents=[
                self.orchestrator,
                self.department_classifier,
                self.content_summarizer,
                self.skill_generator,
                self.command_generator,
                self.agent_generator,
                self.prompt_generator,
                self.workflow_generator
            ],
            tasks=[
                classification_task,
                summary_task,
                asset_generation_task
            ],
            verbose=True,
            process="sequential"
        )

        # Execute analysis
        result = crew.kickoff()

        return self._format_results(result)

    def _format_results(self, raw_result: Any) -> Dict[str, Any]:
        """Format crew results into structured output"""
        return {
            "timestamp": datetime.now().isoformat(),
            "department": raw_result.get("department", "unknown"),
            "assets_generated": raw_result.get("assets", []),
            "summary_created": raw_result.get("summary_path", None),
            "outputs": {
                "drafts": f"processed/crewai-suggestions/*/drafts/",
                "summary": f"processed/crewai-summaries/{raw_result.get('department', 'unknown')}/",
            },
            "next_steps": [
                "Review generated assets in drafts/",
                "Move approved assets to approved/",
                "Run promotion script to deploy to production"
            ]
        }


# Example usage
if __name__ == "__main__":
    # Initialize orchestrator
    orchestrator = EmpireCrewOrchestrator()

    # Example content analysis
    sample_content = """
    Sales Pipeline Management Course - Module 3

    This module covers advanced techniques for managing B2B sales pipelines,
    including lead scoring, opportunity management, and closing strategies.

    Topics covered:
    - Pipeline stages and conversion rates
    - Lead qualification frameworks (BANT, MEDDIC)
    - Forecasting accuracy improvement
    - CRM optimization for sales teams
    """

    # Analyze content
    results = orchestrator.analyze_content(
        content=sample_content,
        filename="sales_pipeline_course_module3.pdf"
    )

    # Print results
    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"Department: {results['department']}")
    print(f"Assets Generated: {', '.join(results['assets_generated'])}")
    print(f"Summary Location: {results['summary_created']}")
    print(f"\nNext Steps:")
    for step in results['next_steps']:
        print(f"  - {step}")