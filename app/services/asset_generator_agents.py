"""
Empire v7.3 - Asset Generator Agents (Task 43)

AGENT-003 to AGENT-007: Specialized agents for generating different asset types.

- AGENT-003: Skill Generator (YAML for Claude Code skills)
- AGENT-004: Command Generator (Markdown slash commands)
- AGENT-005: Agent Generator (CrewAI YAML configs)
- AGENT-006: Prompt Generator (reusable prompt templates)
- AGENT-007: Workflow Generator (n8n JSON workflows)

Output: processed/crewai-suggestions/{asset-type}/drafts/
LLM: Claude Sonnet 4.5

Author: Claude Code
Date: 2025-12-29
"""

import os
import re
import json
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError
from app.services.agent_metrics import (
    AgentMetricsContext,
    AgentID,
    track_agent_request,
    track_agent_error,
    track_llm_call,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AssetType(str, Enum):
    """Types of assets that can be generated"""
    SKILL = "skill"
    COMMAND = "command"
    AGENT = "agent"
    PROMPT = "prompt"
    WORKFLOW = "workflow"


class Department(str, Enum):
    """Business departments for asset organization"""
    IT_ENGINEERING = "it-engineering"
    SALES_MARKETING = "sales-marketing"
    CUSTOMER_SUPPORT = "customer-support"
    OPERATIONS_HR_SUPPLY = "operations-hr-supply"
    FINANCE_ACCOUNTING = "finance-accounting"
    PROJECT_MANAGEMENT = "project-management"
    REAL_ESTATE = "real-estate"
    PRIVATE_EQUITY_MA = "private-equity-ma"
    CONSULTING = "consulting"
    PERSONAL_CONTINUING_ED = "personal-continuing-ed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AssetGenerationRequest(BaseModel):
    """Request for generating an asset"""
    name: str = Field(..., min_length=1, max_length=100, description="Asset name")
    description: str = Field(..., min_length=10, description="What the asset should do")
    department: str = Field(..., description="Target department")
    context: Optional[str] = Field(None, description="Additional context or requirements")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssetGenerationResult(BaseModel):
    """Result of asset generation"""
    success: bool
    asset_type: str
    asset_name: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    department: str
    error: Optional[str] = None
    processing_time_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillSpec(BaseModel):
    """Specification for a Claude Code skill"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Empire AI"
    tools: List[str] = Field(default_factory=list)
    instructions: str = ""
    examples: List[Dict[str, str]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class CommandSpec(BaseModel):
    """Specification for a slash command"""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    """Specification for a CrewAI agent"""
    name: str
    role: str
    goal: str
    backstory: str
    tools: List[str] = Field(default_factory=list)
    llm: str = "claude-sonnet-4-5-20250929"
    verbose: bool = True
    allow_delegation: bool = False


class PromptSpec(BaseModel):
    """Specification for a reusable prompt template"""
    name: str
    description: str
    template: str
    variables: List[Dict[str, Any]] = Field(default_factory=list)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class WorkflowSpec(BaseModel):
    """Specification for an n8n workflow"""
    name: str
    description: str
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# BASE ASSET GENERATOR
# =============================================================================

class BaseAssetGenerator(ABC):
    """Base class for all asset generators"""

    def __init__(self, output_base_path: str = "processed/crewai-suggestions"):
        self.output_base_path = output_base_path
        self.stats = {
            "assets_generated": 0,
            "by_department": {}
        }

        # Initialize LLM
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm = ResilientAnthropicClient(
            api_key=api_key,
            service_name="asset_generator",
            failure_threshold=5,
            recovery_timeout=60.0,
        ) if api_key else None

        logger.info(
            f"{self.agent_id} initialized",
            output_path=output_base_path,
            llm_available=self.llm is not None
        )

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Agent identifier (e.g., AGENT-003)"""
        pass

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable agent name"""
        pass

    @property
    @abstractmethod
    def asset_type(self) -> AssetType:
        """Type of asset this generator creates"""
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension for output files"""
        pass

    @abstractmethod
    async def _generate_content(self, request: AssetGenerationRequest) -> str:
        """Generate the asset content"""
        pass

    def _get_output_path(self, department: str, name: str) -> Path:
        """Get the output file path"""
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_name}_{timestamp}{self.file_extension}"

        output_dir = Path(self.output_base_path) / self.asset_type.value / "drafts" / department
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir / filename

    async def generate(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        """Generate an asset from the request"""
        async with AgentMetricsContext(
            self.agent_id,
            "generate",
            model="claude-sonnet-4-5-20250929"
        ) as metrics_ctx:
            start_time = datetime.now()

            logger.info(
                f"{self.agent_id} generation started",
                asset_type=self.asset_type.value,
                name=request.name,
                department=request.department
            )

            try:
                # Generate content
                content = await self._generate_content(request)

                # Save to file
                output_path = self._get_output_path(request.department, request.name)
                with open(output_path, 'w') as f:
                    f.write(content)

                # Update stats
                processing_time = (datetime.now() - start_time).total_seconds()
                self._update_stats(request.department)

                result = AssetGenerationResult(
                    success=True,
                    asset_type=self.asset_type.value,
                    asset_name=request.name,
                    file_path=str(output_path),
                    content=content,
                    department=request.department,
                    processing_time_seconds=processing_time,
                    metadata={
                        "agent_id": self.agent_id,
                        "agent_name": self.agent_name,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                logger.info(
                    f"{self.agent_id} generation complete",
                    file_path=str(output_path),
                    processing_time=f"{processing_time:.2f}s"
                )

                metrics_ctx.set_success()
                return result

            except Exception as e:
                logger.error(f"{self.agent_id} generation failed", error=str(e))
                metrics_ctx.set_failure(type(e).__name__)
                return AssetGenerationResult(
                    success=False,
                    asset_type=self.asset_type.value,
                    asset_name=request.name,
                    department=request.department,
                    error=str(e),
                    processing_time_seconds=(datetime.now() - start_time).total_seconds()
                )

    def _update_stats(self, department: str):
        """Update generation statistics"""
        self.stats["assets_generated"] += 1
        if department not in self.stats["by_department"]:
            self.stats["by_department"][department] = 0
        self.stats["by_department"][department] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics"""
        return {
            **self.stats,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "asset_type": self.asset_type.value
        }


# =============================================================================
# AGENT-003: SKILL GENERATOR
# =============================================================================

class SkillGeneratorAgent(BaseAssetGenerator):
    """
    AGENT-003: Skill Generator

    Generates YAML skill files for Claude Code with:
    - Tool definitions
    - Instructions
    - Usage examples
    - Tags for organization
    """

    @property
    def agent_id(self) -> str:
        return "AGENT-003"

    @property
    def agent_name(self) -> str:
        return "Skill Generator"

    @property
    def asset_type(self) -> AssetType:
        return AssetType.SKILL

    @property
    def file_extension(self) -> str:
        return ".yaml"

    async def _generate_content(self, request: AssetGenerationRequest) -> str:
        """Generate YAML skill definition"""

        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate a Claude Code skill YAML file for:

Name: {request.name}
Description: {request.description}
Department: {request.department}
Additional Context: {request.context or 'None'}

Create a comprehensive skill with:
1. Clear name and description
2. Relevant tools (Read, Write, Edit, Bash, Glob, Grep, etc.)
3. Detailed instructions for the AI
4. 2-3 usage examples
5. Relevant tags

Output ONLY valid YAML (no markdown code blocks, no explanation):

name: skill-name
description: "Brief description"
version: "1.0.0"
author: "Empire AI"
tools:
  - Read
  - Write
instructions: |
  Detailed instructions here...
examples:
  - input: "Example input"
    output: "Expected output"
tags:
  - tag1
  - tag2"""
                    }]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                track_llm_call(
                    AgentID.SKILL_GENERATOR,
                    "claude-sonnet-4-5-20250929",
                    "success",
                    input_tokens,
                    output_tokens
                )

                content = response.content[0].text.strip()
                # Remove any markdown code blocks if present
                if content.startswith("```"):
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```$', '', content)

                # Validate YAML
                yaml.safe_load(content)
                return content

            except Exception as e:
                logger.warning("LLM skill generation failed", error=str(e))
                track_llm_call(AgentID.SKILL_GENERATOR, "claude-sonnet-4-5-20250929", "failure")

        # Fallback: Generate basic skill
        skill = SkillSpec(
            name=re.sub(r'[^a-z0-9-]', '-', request.name.lower()),
            description=request.description,
            tools=["Read", "Write", "Edit", "Glob", "Grep"],
            instructions=f"Help the user with {request.description}. Follow best practices for {request.department}.",
            examples=[
                {"input": f"Help me with {request.name}", "output": "I'll help you with that..."}
            ],
            tags=[request.department, "auto-generated"]
        )

        return yaml.dump(skill.model_dump(), default_flow_style=False, sort_keys=False)


# =============================================================================
# AGENT-004: COMMAND GENERATOR
# =============================================================================

class CommandGeneratorAgent(BaseAssetGenerator):
    """
    AGENT-004: Command Generator

    Generates Markdown slash command files for Claude Code with:
    - Command description
    - Arguments with types
    - Step-by-step instructions
    - Usage examples
    """

    @property
    def agent_id(self) -> str:
        return "AGENT-004"

    @property
    def agent_name(self) -> str:
        return "Command Generator"

    @property
    def asset_type(self) -> AssetType:
        return AssetType.COMMAND

    @property
    def file_extension(self) -> str:
        return ".md"

    async def _generate_content(self, request: AssetGenerationRequest) -> str:
        """Generate Markdown slash command"""

        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1500,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate a Claude Code slash command Markdown file for:

Name: {request.name}
Description: {request.description}
Department: {request.department}
Additional Context: {request.context or 'None'}

Create a command with:
1. Clear description at the top
2. Arguments section if needed (use $ARGUMENTS for user input)
3. Step-by-step instructions (numbered list)
4. 1-2 usage examples

The command will be invoked as /{request.name} and the file goes in .claude/commands/

Output ONLY the Markdown content (no code blocks, no explanation):"""
                    }]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                track_llm_call(
                    AgentID.COMMAND_GENERATOR,
                    "claude-sonnet-4-5-20250929",
                    "success",
                    input_tokens,
                    output_tokens
                )

                content = response.content[0].text.strip()
                # Remove any markdown code blocks if present
                if content.startswith("```"):
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```$', '', content)
                return content

            except Exception as e:
                logger.warning("LLM command generation failed", error=str(e))
                track_llm_call(AgentID.COMMAND_GENERATOR, "claude-sonnet-4-5-20250929", "failure")

        # Fallback: Generate basic command
        command_name = re.sub(r'[^a-z0-9-]', '-', request.name.lower())
        return f"""# {request.name}

{request.description}

## Arguments

This command accepts optional arguments via $ARGUMENTS.

## Steps

1. Analyze the current context and requirements
2. Execute the main task: {request.description}
3. Verify the results
4. Report completion status

## Examples

```
/{command_name}
/{command_name} with specific options
```

---
Generated by Empire v7.3 Command Generator (AGENT-004)
Department: {request.department}
"""


# =============================================================================
# AGENT-005: AGENT GENERATOR
# =============================================================================

class AgentGeneratorAgent(BaseAssetGenerator):
    """
    AGENT-005: Agent Generator

    Generates CrewAI agent YAML configuration files with:
    - Role definition
    - Goals and backstory
    - Tool assignments
    - LLM configuration
    """

    @property
    def agent_id(self) -> str:
        return "AGENT-005"

    @property
    def agent_name(self) -> str:
        return "Agent Generator"

    @property
    def asset_type(self) -> AssetType:
        return AssetType.AGENT

    @property
    def file_extension(self) -> str:
        return ".yaml"

    async def _generate_content(self, request: AssetGenerationRequest) -> str:
        """Generate CrewAI agent YAML configuration"""

        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate a CrewAI agent YAML configuration for:

Name: {request.name}
Description: {request.description}
Department: {request.department}
Additional Context: {request.context or 'None'}

Create an agent with:
1. Clear role title
2. Specific, measurable goal
3. Compelling backstory (2-3 sentences)
4. Relevant tools list
5. LLM configuration

Output ONLY valid YAML (no markdown code blocks, no explanation):

name: agent-name
role: "Role Title"
goal: "Specific goal the agent aims to achieve"
backstory: |
  Compelling backstory explaining the agent's expertise...
tools:
  - tool_name_1
  - tool_name_2
llm: claude-sonnet-4-5-20250929
verbose: true
allow_delegation: false
max_iterations: 10
memory: true"""
                    }]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                track_llm_call(
                    AgentID.AGENT_GENERATOR,
                    "claude-sonnet-4-5-20250929",
                    "success",
                    input_tokens,
                    output_tokens
                )

                content = response.content[0].text.strip()
                if content.startswith("```"):
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```$', '', content)

                # Validate YAML
                yaml.safe_load(content)
                return content

            except Exception as e:
                logger.warning("LLM agent generation failed", error=str(e))
                track_llm_call(AgentID.AGENT_GENERATOR, "claude-sonnet-4-5-20250929", "failure")

        # Fallback: Generate basic agent config
        agent = AgentSpec(
            name=re.sub(r'[^a-z0-9_]', '_', request.name.lower()),
            role=f"{request.name} Specialist",
            goal=request.description,
            backstory=f"An expert in {request.department} with deep knowledge of {request.name}. Dedicated to delivering high-quality results.",
            tools=["search", "analyze", "report"],
            llm="claude-sonnet-4-5-20250929"
        )

        return yaml.dump(agent.model_dump(), default_flow_style=False, sort_keys=False)


# =============================================================================
# AGENT-006: PROMPT GENERATOR
# =============================================================================

class PromptGeneratorAgent(BaseAssetGenerator):
    """
    AGENT-006: Prompt Generator

    Generates reusable prompt templates with:
    - Template with variable placeholders
    - Variable definitions
    - Usage examples
    - Tags for organization
    """

    @property
    def agent_id(self) -> str:
        return "AGENT-006"

    @property
    def agent_name(self) -> str:
        return "Prompt Generator"

    @property
    def asset_type(self) -> AssetType:
        return AssetType.PROMPT

    @property
    def file_extension(self) -> str:
        return ".yaml"

    async def _generate_content(self, request: AssetGenerationRequest) -> str:
        """Generate prompt template YAML"""

        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate a reusable prompt template YAML for:

Name: {request.name}
Description: {request.description}
Department: {request.department}
Additional Context: {request.context or 'None'}

Create a prompt template with:
1. Clear name and description
2. Template with {{{{variable}}}} placeholders
3. Variable definitions (name, type, description, required)
4. 1-2 usage examples with filled variables
5. Relevant tags

Output ONLY valid YAML (no markdown code blocks, no explanation):

name: prompt-name
description: "What this prompt does"
version: "1.0.0"
template: |
  Your prompt template here with {{{{variable1}}}} and {{{{variable2}}}}...
variables:
  - name: variable1
    type: string
    description: "What this variable is for"
    required: true
  - name: variable2
    type: string
    description: "Another variable"
    required: false
    default: "default value"
examples:
  - variables:
      variable1: "example value"
      variable2: "another value"
    result: "Expected output..."
tags:
  - tag1
  - tag2"""
                    }]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                track_llm_call(
                    AgentID.PROMPT_GENERATOR,
                    "claude-sonnet-4-5-20250929",
                    "success",
                    input_tokens,
                    output_tokens
                )

                content = response.content[0].text.strip()
                if content.startswith("```"):
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```$', '', content)

                # Validate YAML
                yaml.safe_load(content)
                return content

            except Exception as e:
                logger.warning("LLM prompt generation failed", error=str(e))
                track_llm_call(AgentID.PROMPT_GENERATOR, "claude-sonnet-4-5-20250929", "failure")

        # Fallback: Generate basic prompt template
        prompt = PromptSpec(
            name=re.sub(r'[^a-z0-9-]', '-', request.name.lower()),
            description=request.description,
            template=f"You are an expert in {request.department}.\n\nTask: {{{{task}}}}\n\nContext: {{{{context}}}}\n\nProvide a detailed response.",
            variables=[
                {"name": "task", "type": "string", "description": "The main task to complete", "required": True},
                {"name": "context", "type": "string", "description": "Additional context", "required": False, "default": ""}
            ],
            examples=[
                {
                    "variables": {"task": request.name, "context": "Standard scenario"},
                    "result": "Example response..."
                }
            ],
            tags=[request.department, "auto-generated"]
        )

        return yaml.dump(prompt.model_dump(), default_flow_style=False, sort_keys=False)


# =============================================================================
# AGENT-007: WORKFLOW GENERATOR
# =============================================================================

class WorkflowGeneratorAgent(BaseAssetGenerator):
    """
    AGENT-007: Workflow Generator

    Generates n8n workflow JSON files with:
    - Node definitions
    - Connection mappings
    - Workflow settings
    - Trigger configurations
    """

    @property
    def agent_id(self) -> str:
        return "AGENT-007"

    @property
    def agent_name(self) -> str:
        return "Workflow Generator"

    @property
    def asset_type(self) -> AssetType:
        return AssetType.WORKFLOW

    @property
    def file_extension(self) -> str:
        return ".json"

    async def _generate_content(self, request: AssetGenerationRequest) -> str:
        """Generate n8n workflow JSON"""

        if self.llm:
            try:
                response = await self.llm.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=3000,
                    messages=[{
                        "role": "user",
                        "content": f"""Generate an n8n workflow JSON for:

Name: {request.name}
Description: {request.description}
Department: {request.department}
Additional Context: {request.context or 'None'}

Create a workflow with:
1. Appropriate trigger node (webhook, schedule, or manual)
2. 3-5 processing nodes relevant to the task
3. Proper connections between nodes
4. Error handling where appropriate
5. Output/response node

Output ONLY valid JSON (no markdown code blocks, no explanation). Use this structure:

{{
  "name": "workflow-name",
  "nodes": [
    {{
      "parameters": {{}},
      "name": "Node Name",
      "type": "n8n-nodes-base.nodeType",
      "position": [x, y],
      "typeVersion": 1
    }}
  ],
  "connections": {{
    "Node Name": {{
      "main": [[{{"node": "Next Node", "type": "main", "index": 0}}]]
    }}
  }},
  "settings": {{
    "executionOrder": "v1"
  }}
}}"""
                    }]
                )

                # Track LLM call metrics
                input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
                output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
                track_llm_call(
                    AgentID.WORKFLOW_GENERATOR,
                    "claude-sonnet-4-5-20250929",
                    "success",
                    input_tokens,
                    output_tokens
                )

                content = response.content[0].text.strip()
                if content.startswith("```"):
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```$', '', content)

                # Validate JSON
                json.loads(content)
                return content

            except Exception as e:
                logger.warning("LLM workflow generation failed", error=str(e))
                track_llm_call(AgentID.WORKFLOW_GENERATOR, "claude-sonnet-4-5-20250929", "failure")

        # Fallback: Generate basic workflow
        workflow_name = re.sub(r'[^a-z0-9_]', '_', request.name.lower())
        workflow = {
            "name": workflow_name,
            "nodes": [
                {
                    "parameters": {},
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "position": [250, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "values": {
                            "string": [
                                {"name": "task", "value": request.description},
                                {"name": "department", "value": request.department}
                            ]
                        }
                    },
                    "name": "Set Variables",
                    "type": "n8n-nodes-base.set",
                    "position": [450, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "conditions": {
                            "string": [
                                {"value1": "={{$json.task}}", "operation": "isNotEmpty"}
                            ]
                        }
                    },
                    "name": "Validate Input",
                    "type": "n8n-nodes-base.if",
                    "position": [650, 300],
                    "typeVersion": 1
                },
                {
                    "parameters": {},
                    "name": "Process Task",
                    "type": "n8n-nodes-base.noOp",
                    "position": [850, 250],
                    "typeVersion": 1
                },
                {
                    "parameters": {
                        "values": {
                            "string": [
                                {"name": "status", "value": "completed"},
                                {"name": "result", "value": f"Processed {request.name}"}
                            ]
                        }
                    },
                    "name": "Output Result",
                    "type": "n8n-nodes-base.set",
                    "position": [1050, 250],
                    "typeVersion": 1
                }
            ],
            "connections": {
                "Manual Trigger": {
                    "main": [[{"node": "Set Variables", "type": "main", "index": 0}]]
                },
                "Set Variables": {
                    "main": [[{"node": "Validate Input", "type": "main", "index": 0}]]
                },
                "Validate Input": {
                    "main": [
                        [{"node": "Process Task", "type": "main", "index": 0}],
                        []
                    ]
                },
                "Process Task": {
                    "main": [[{"node": "Output Result", "type": "main", "index": 0}]]
                }
            },
            "settings": {
                "executionOrder": "v1"
            },
            "meta": {
                "description": request.description,
                "department": request.department,
                "generated_by": "AGENT-007",
                "generated_at": datetime.now().isoformat()
            }
        }

        return json.dumps(workflow, indent=2)


# =============================================================================
# UNIFIED ASSET GENERATOR SERVICE
# =============================================================================

class AssetGeneratorService:
    """
    Unified service for all asset generators (AGENT-003 to AGENT-007).

    Provides a single interface to generate any asset type.
    """

    def __init__(self, output_base_path: str = "processed/crewai-suggestions"):
        self.output_base_path = output_base_path

        # Initialize all generators
        self.generators: Dict[AssetType, BaseAssetGenerator] = {
            AssetType.SKILL: SkillGeneratorAgent(output_base_path),
            AssetType.COMMAND: CommandGeneratorAgent(output_base_path),
            AssetType.AGENT: AgentGeneratorAgent(output_base_path),
            AssetType.PROMPT: PromptGeneratorAgent(output_base_path),
            AssetType.WORKFLOW: WorkflowGeneratorAgent(output_base_path),
        }

        logger.info(
            "AssetGeneratorService initialized",
            output_path=output_base_path,
            generators=list(self.generators.keys())
        )

    async def generate(
        self,
        asset_type: AssetType,
        request: AssetGenerationRequest
    ) -> AssetGenerationResult:
        """
        Generate an asset of the specified type.

        Args:
            asset_type: Type of asset to generate
            request: Generation request with name, description, etc.

        Returns:
            AssetGenerationResult with file path and content
        """
        generator = self.generators.get(asset_type)
        if not generator:
            return AssetGenerationResult(
                success=False,
                asset_type=asset_type.value,
                asset_name=request.name,
                department=request.department,
                error=f"Unknown asset type: {asset_type}"
            )

        return await generator.generate(request)

    async def generate_skill(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        """Generate a Claude Code skill (AGENT-003)"""
        return await self.generate(AssetType.SKILL, request)

    async def generate_command(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        """Generate a slash command (AGENT-004)"""
        return await self.generate(AssetType.COMMAND, request)

    async def generate_agent(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        """Generate a CrewAI agent (AGENT-005)"""
        return await self.generate(AssetType.AGENT, request)

    async def generate_prompt(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        """Generate a prompt template (AGENT-006)"""
        return await self.generate(AssetType.PROMPT, request)

    async def generate_workflow(self, request: AssetGenerationRequest) -> AssetGenerationResult:
        """Generate an n8n workflow (AGENT-007)"""
        return await self.generate(AssetType.WORKFLOW, request)

    def get_generator(self, asset_type: AssetType) -> Optional[BaseAssetGenerator]:
        """Get a specific generator"""
        return self.generators.get(asset_type)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all generators"""
        return {
            generator.agent_id: generator.get_stats()
            for generator in self.generators.values()
        }

    def list_generators(self) -> List[Dict[str, str]]:
        """List all available generators"""
        return [
            {
                "agent_id": gen.agent_id,
                "agent_name": gen.agent_name,
                "asset_type": gen.asset_type.value,
                "file_extension": gen.file_extension
            }
            for gen in self.generators.values()
        ]


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_asset_generator_service: Optional[AssetGeneratorService] = None


def get_asset_generator_service() -> AssetGeneratorService:
    """Get singleton instance of AssetGeneratorService"""
    global _asset_generator_service
    if _asset_generator_service is None:
        _asset_generator_service = AssetGeneratorService()
    return _asset_generator_service


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        """Test all asset generators"""
        service = AssetGeneratorService()

        logger.info("asset_generator_test_started", agents="AGENT-003 to AGENT-007")

        # Test each generator
        test_cases = [
            (AssetType.SKILL, "code-reviewer", "Review Python code for best practices and security issues"),
            (AssetType.COMMAND, "deploy-staging", "Deploy the current branch to the staging environment"),
            (AssetType.AGENT, "data-analyst", "Analyze sales data and generate insights reports"),
            (AssetType.PROMPT, "email-writer", "Write professional business emails based on context"),
            (AssetType.WORKFLOW, "document-processor", "Process uploaded documents and extract key information"),
        ]

        for asset_type, name, description in test_cases:
            logger.info("testing_generator", asset_type=asset_type.value.upper())

            request = AssetGenerationRequest(
                name=name,
                description=description,
                department="it-engineering"
            )

            result = await service.generate(asset_type, request)

            logger.info(
                "generator_result",
                success=result.success,
                file_path=result.file_path,
                processing_time_seconds=round(result.processing_time_seconds, 2)
            )

            if result.error:
                logger.error("generator_error", error=result.error)

        # Log all stats
        logger.info("asset_generator_test_completed", stats=service.get_all_stats())

    asyncio.run(test())
