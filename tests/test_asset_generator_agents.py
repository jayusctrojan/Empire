"""
Tests for Empire v7.3 Asset Generator Agents (Task 43)

Tests AGENT-003 to AGENT-007:
- AGENT-003: Skill Generator (YAML)
- AGENT-004: Command Generator (Markdown)
- AGENT-005: Agent Generator (CrewAI YAML)
- AGENT-006: Prompt Generator (YAML)
- AGENT-007: Workflow Generator (n8n JSON)
"""

import pytest
import json
import yaml
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Import the modules under test
from app.services.asset_generator_agents import (
    AssetType,
    Department,
    AssetGenerationRequest,
    AssetGenerationResult,
    SkillSpec,
    CommandSpec,
    AgentSpec,
    PromptSpec,
    WorkflowSpec,
    BaseAssetGenerator,
    SkillGeneratorAgent,
    CommandGeneratorAgent,
    AgentGeneratorAgent,
    PromptGeneratorAgent,
    WorkflowGeneratorAgent,
    AssetGeneratorService,
    get_asset_generator_service
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_request():
    """Create a sample asset generation request."""
    return AssetGenerationRequest(
        name="test-asset",
        description="A test asset for unit testing purposes",
        department="it-engineering",
        context="This is additional context for testing",
        metadata={"version": "1.0.0", "author": "test"}
    )


@pytest.fixture
def skill_generator(temp_output_dir):
    """Create a skill generator with temporary output directory."""
    return SkillGeneratorAgent(output_base_path=temp_output_dir)


@pytest.fixture
def command_generator(temp_output_dir):
    """Create a command generator with temporary output directory."""
    return CommandGeneratorAgent(output_base_path=temp_output_dir)


@pytest.fixture
def agent_generator(temp_output_dir):
    """Create an agent generator with temporary output directory."""
    return AgentGeneratorAgent(output_base_path=temp_output_dir)


@pytest.fixture
def prompt_generator(temp_output_dir):
    """Create a prompt generator with temporary output directory."""
    return PromptGeneratorAgent(output_base_path=temp_output_dir)


@pytest.fixture
def workflow_generator(temp_output_dir):
    """Create a workflow generator with temporary output directory."""
    return WorkflowGeneratorAgent(output_base_path=temp_output_dir)


@pytest.fixture
def asset_generator_service(temp_output_dir):
    """Create an asset generator service with temporary output directory."""
    return AssetGeneratorService(output_base_path=temp_output_dir)


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestEnums:
    """Test enum definitions."""

    def test_asset_type_values(self):
        """Test AssetType enum values."""
        assert AssetType.SKILL.value == "skill"
        assert AssetType.COMMAND.value == "command"
        assert AssetType.AGENT.value == "agent"
        assert AssetType.PROMPT.value == "prompt"
        assert AssetType.WORKFLOW.value == "workflow"

    def test_department_values(self):
        """Test Department enum values."""
        assert Department.IT_ENGINEERING.value == "it-engineering"
        assert Department.SALES_MARKETING.value == "sales-marketing"
        assert Department.CUSTOMER_SUPPORT.value == "customer-support"
        assert len(Department) == 10


# =============================================================================
# PYDANTIC MODEL TESTS
# =============================================================================

class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_asset_generation_request_valid(self):
        """Test valid AssetGenerationRequest."""
        request = AssetGenerationRequest(
            name="test-skill",
            description="This is a test skill for testing",
            department="it-engineering"
        )
        assert request.name == "test-skill"
        assert request.department == "it-engineering"

    def test_asset_generation_request_with_optional_fields(self):
        """Test AssetGenerationRequest with optional fields."""
        request = AssetGenerationRequest(
            name="test-skill",
            description="This is a test skill for testing",
            department="it-engineering",
            context="Additional context",
            metadata={"key": "value"}
        )
        assert request.context == "Additional context"
        assert request.metadata == {"key": "value"}

    def test_asset_generation_result(self):
        """Test AssetGenerationResult model."""
        result = AssetGenerationResult(
            success=True,
            asset_type="skill",
            asset_name="test-skill",
            file_path="/path/to/file.yaml",
            department="it-engineering"
        )
        assert result.success is True
        assert result.asset_type == "skill"

    def test_skill_spec(self):
        """Test SkillSpec model."""
        spec = SkillSpec(
            name="test-skill",
            description="A test skill",
            tools=["Read", "Write"],
            instructions="Do the thing",
            tags=["test"]
        )
        assert spec.version == "1.0.0"
        assert "Read" in spec.tools

    def test_command_spec(self):
        """Test CommandSpec model."""
        spec = CommandSpec(
            name="test-command",
            description="A test command",
            steps=["Step 1", "Step 2"]
        )
        assert len(spec.steps) == 2

    def test_agent_spec(self):
        """Test AgentSpec model."""
        spec = AgentSpec(
            name="test-agent",
            role="Test Role",
            goal="Achieve testing",
            backstory="A test agent"
        )
        assert spec.verbose is True
        assert spec.allow_delegation is False

    def test_prompt_spec(self):
        """Test PromptSpec model."""
        spec = PromptSpec(
            name="test-prompt",
            description="A test prompt",
            template="Hello {{name}}"
        )
        assert "{{name}}" in spec.template

    def test_workflow_spec(self):
        """Test WorkflowSpec model."""
        spec = WorkflowSpec(
            name="test-workflow",
            description="A test workflow",
            nodes=[{"name": "Start"}]
        )
        assert len(spec.nodes) == 1


# =============================================================================
# SKILL GENERATOR TESTS (AGENT-003)
# =============================================================================

class TestSkillGenerator:
    """Tests for AGENT-003: Skill Generator."""

    def test_agent_properties(self, skill_generator):
        """Test skill generator properties."""
        assert skill_generator.agent_id == "AGENT-003"
        assert skill_generator.agent_name == "Skill Generator"
        assert skill_generator.asset_type == AssetType.SKILL
        assert skill_generator.file_extension == ".yaml"

    @pytest.mark.asyncio
    async def test_generate_skill_without_llm(self, skill_generator, sample_request):
        """Test skill generation without LLM (fallback)."""
        # Ensure no LLM is available
        skill_generator.llm = None

        result = await skill_generator.generate(sample_request)

        assert result.success is True
        assert result.asset_type == "skill"
        assert result.file_path is not None
        assert result.file_path.endswith(".yaml")

        # Verify file exists and is valid YAML
        assert Path(result.file_path).exists()
        with open(result.file_path) as f:
            content = yaml.safe_load(f)
        assert "name" in content
        assert "description" in content

    @pytest.mark.asyncio
    async def test_generate_skill_with_mock_llm(self, skill_generator, sample_request):
        """Test skill generation with mocked LLM."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""
name: test-skill
description: "A test skill"
version: "1.0.0"
tools:
  - Read
  - Write
instructions: |
  Test instructions
tags:
  - test
""")]
        # Add usage attribute to avoid MagicMock comparison errors
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        skill_generator.llm = AsyncMock()
        skill_generator.llm.messages.create = AsyncMock(return_value=mock_response)

        result = await skill_generator.generate(sample_request)

        assert result.success is True
        assert result.content is not None
        assert "test-skill" in result.content

    def test_get_output_path(self, skill_generator):
        """Test output path generation."""
        path = skill_generator._get_output_path("it-engineering", "test-skill")
        assert "skill" in str(path)
        assert "drafts" in str(path)
        assert "it-engineering" in str(path)
        assert path.suffix == ".yaml"

    def test_stats_tracking(self, skill_generator):
        """Test statistics tracking."""
        skill_generator._update_stats("it-engineering")
        skill_generator._update_stats("it-engineering")
        skill_generator._update_stats("sales-marketing")

        stats = skill_generator.get_stats()
        assert stats["assets_generated"] == 3
        assert stats["by_department"]["it-engineering"] == 2
        assert stats["by_department"]["sales-marketing"] == 1


# =============================================================================
# COMMAND GENERATOR TESTS (AGENT-004)
# =============================================================================

class TestCommandGenerator:
    """Tests for AGENT-004: Command Generator."""

    def test_agent_properties(self, command_generator):
        """Test command generator properties."""
        assert command_generator.agent_id == "AGENT-004"
        assert command_generator.agent_name == "Command Generator"
        assert command_generator.asset_type == AssetType.COMMAND
        assert command_generator.file_extension == ".md"

    @pytest.mark.asyncio
    async def test_generate_command_without_llm(self, command_generator, sample_request):
        """Test command generation without LLM (fallback)."""
        command_generator.llm = None

        result = await command_generator.generate(sample_request)

        assert result.success is True
        assert result.asset_type == "command"
        assert result.file_path.endswith(".md")

        # Verify file exists and has markdown content
        assert Path(result.file_path).exists()
        with open(result.file_path) as f:
            content = f.read()
        assert "# " in content  # Has a heading
        assert "## " in content  # Has subheadings
        assert sample_request.description in content

    @pytest.mark.asyncio
    async def test_generate_command_with_mock_llm(self, command_generator, sample_request):
        """Test command generation with mocked LLM."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""
# Test Command

A test command for testing.

## Steps

1. Do step one
2. Do step two

## Examples

```
/test-command
```
""")]
        # Add usage attribute to avoid MagicMock comparison errors
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        command_generator.llm = MagicMock()
        command_generator.llm.messages = MagicMock()
        command_generator.llm.messages.create = AsyncMock(return_value=mock_response)

        result = await command_generator.generate(sample_request)

        assert result.success is True
        assert "# Test Command" in result.content


# =============================================================================
# AGENT GENERATOR TESTS (AGENT-005)
# =============================================================================

class TestAgentGenerator:
    """Tests for AGENT-005: Agent Generator."""

    def test_agent_properties(self, agent_generator):
        """Test agent generator properties."""
        assert agent_generator.agent_id == "AGENT-005"
        assert agent_generator.agent_name == "Agent Generator"
        assert agent_generator.asset_type == AssetType.AGENT
        assert agent_generator.file_extension == ".yaml"

    @pytest.mark.asyncio
    async def test_generate_agent_without_llm(self, agent_generator, sample_request):
        """Test agent generation without LLM (fallback)."""
        agent_generator.llm = None

        result = await agent_generator.generate(sample_request)

        assert result.success is True
        assert result.asset_type == "agent"
        assert result.file_path.endswith(".yaml")

        # Verify valid YAML with required fields
        with open(result.file_path) as f:
            content = yaml.safe_load(f)
        assert "name" in content
        assert "role" in content
        assert "goal" in content
        assert "backstory" in content

    @pytest.mark.asyncio
    async def test_generate_agent_with_mock_llm(self, agent_generator, sample_request):
        """Test agent generation with mocked LLM."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""
name: test-agent
role: "Test Agent"
goal: "Achieve testing excellence"
backstory: |
  A dedicated test agent with years of experience.
tools:
  - search
  - analyze
llm: claude-sonnet-4-5-20250514
verbose: true
allow_delegation: false
""")]
        # Add usage attribute to avoid MagicMock comparison errors
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        agent_generator.llm = AsyncMock()
        agent_generator.llm.messages.create = AsyncMock(return_value=mock_response)

        result = await agent_generator.generate(sample_request)

        assert result.success is True
        content = yaml.safe_load(result.content)
        assert content["name"] == "test-agent"


# =============================================================================
# PROMPT GENERATOR TESTS (AGENT-006)
# =============================================================================

class TestPromptGenerator:
    """Tests for AGENT-006: Prompt Generator."""

    def test_agent_properties(self, prompt_generator):
        """Test prompt generator properties."""
        assert prompt_generator.agent_id == "AGENT-006"
        assert prompt_generator.agent_name == "Prompt Generator"
        assert prompt_generator.asset_type == AssetType.PROMPT
        assert prompt_generator.file_extension == ".yaml"

    @pytest.mark.asyncio
    async def test_generate_prompt_without_llm(self, prompt_generator, sample_request):
        """Test prompt generation without LLM (fallback)."""
        prompt_generator.llm = None

        result = await prompt_generator.generate(sample_request)

        assert result.success is True
        assert result.asset_type == "prompt"
        assert result.file_path.endswith(".yaml")

        # Verify valid YAML with template
        with open(result.file_path) as f:
            content = yaml.safe_load(f)
        assert "name" in content
        assert "template" in content
        assert "variables" in content
        assert "{{" in content["template"]  # Has variables

    @pytest.mark.asyncio
    async def test_generate_prompt_with_mock_llm(self, prompt_generator, sample_request):
        """Test prompt generation with mocked LLM."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""
name: test-prompt
description: "A test prompt template"
version: "1.0.0"
template: |
  You are a {{role}}. Your task is {{task}}.

  Context: {{context}}

  Please provide a detailed response.
variables:
  - name: role
    type: string
    description: "The role to assume"
    required: true
  - name: task
    type: string
    description: "The task to complete"
    required: true
  - name: context
    type: string
    description: "Additional context"
    required: false
    default: "General context"
examples:
  - variables:
      role: "analyst"
      task: "analyze data"
    result: "Expected output..."
tags:
  - test
  - template
""")]

        prompt_generator.llm = AsyncMock()
        prompt_generator.llm.messages.create = AsyncMock(return_value=mock_response)

        result = await prompt_generator.generate(sample_request)

        assert result.success is True
        content = yaml.safe_load(result.content)
        assert "template" in content
        assert "variables" in content


# =============================================================================
# WORKFLOW GENERATOR TESTS (AGENT-007)
# =============================================================================

class TestWorkflowGenerator:
    """Tests for AGENT-007: Workflow Generator."""

    def test_agent_properties(self, workflow_generator):
        """Test workflow generator properties."""
        assert workflow_generator.agent_id == "AGENT-007"
        assert workflow_generator.agent_name == "Workflow Generator"
        assert workflow_generator.asset_type == AssetType.WORKFLOW
        assert workflow_generator.file_extension == ".json"

    @pytest.mark.asyncio
    async def test_generate_workflow_without_llm(self, workflow_generator, sample_request):
        """Test workflow generation without LLM (fallback)."""
        workflow_generator.llm = None

        result = await workflow_generator.generate(sample_request)

        assert result.success is True
        assert result.asset_type == "workflow"
        assert result.file_path.endswith(".json")

        # Verify valid JSON with n8n structure
        with open(result.file_path) as f:
            content = json.load(f)
        assert "name" in content
        assert "nodes" in content
        assert "connections" in content
        assert len(content["nodes"]) > 0

    @pytest.mark.asyncio
    async def test_generate_workflow_with_mock_llm(self, workflow_generator, sample_request):
        """Test workflow generation with mocked LLM."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "name": "test-workflow",
            "nodes": [
                {
                    "parameters": {},
                    "name": "Start",
                    "type": "n8n-nodes-base.manualTrigger",
                    "position": [250, 300]
                },
                {
                    "parameters": {"message": "Hello"},
                    "name": "Log",
                    "type": "n8n-nodes-base.noOp",
                    "position": [450, 300]
                }
            ],
            "connections": {
                "Start": {
                    "main": [[{"node": "Log", "type": "main", "index": 0}]]
                }
            },
            "settings": {"executionOrder": "v1"}
        }))]
        # Add usage attribute to avoid MagicMock comparison errors
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

        workflow_generator.llm = AsyncMock()
        workflow_generator.llm.messages.create = AsyncMock(return_value=mock_response)

        result = await workflow_generator.generate(sample_request)

        assert result.success is True
        content = json.loads(result.content)
        assert content["name"] == "test-workflow"
        assert len(content["nodes"]) == 2


# =============================================================================
# ASSET GENERATOR SERVICE TESTS
# =============================================================================

class TestAssetGeneratorService:
    """Tests for the unified AssetGeneratorService."""

    def test_initialization(self, asset_generator_service):
        """Test service initialization."""
        assert len(asset_generator_service.generators) == 5
        assert AssetType.SKILL in asset_generator_service.generators
        assert AssetType.COMMAND in asset_generator_service.generators
        assert AssetType.AGENT in asset_generator_service.generators
        assert AssetType.PROMPT in asset_generator_service.generators
        assert AssetType.WORKFLOW in asset_generator_service.generators

    def test_list_generators(self, asset_generator_service):
        """Test listing all generators."""
        generators = asset_generator_service.list_generators()
        assert len(generators) == 5

        agent_ids = [g["agent_id"] for g in generators]
        assert "AGENT-003" in agent_ids
        assert "AGENT-004" in agent_ids
        assert "AGENT-005" in agent_ids
        assert "AGENT-006" in agent_ids
        assert "AGENT-007" in agent_ids

    def test_get_generator(self, asset_generator_service):
        """Test getting a specific generator."""
        skill_gen = asset_generator_service.get_generator(AssetType.SKILL)
        assert skill_gen is not None
        assert skill_gen.agent_id == "AGENT-003"

        workflow_gen = asset_generator_service.get_generator(AssetType.WORKFLOW)
        assert workflow_gen is not None
        assert workflow_gen.agent_id == "AGENT-007"

    @pytest.mark.asyncio
    async def test_generate_skill(self, asset_generator_service, sample_request):
        """Test generating a skill through the service."""
        # Disable LLM for predictable testing
        asset_generator_service.generators[AssetType.SKILL].llm = None

        result = await asset_generator_service.generate_skill(sample_request)
        assert result.success is True
        assert result.asset_type == "skill"

    @pytest.mark.asyncio
    async def test_generate_command(self, asset_generator_service, sample_request):
        """Test generating a command through the service."""
        asset_generator_service.generators[AssetType.COMMAND].llm = None

        result = await asset_generator_service.generate_command(sample_request)
        assert result.success is True
        assert result.asset_type == "command"

    @pytest.mark.asyncio
    async def test_generate_agent(self, asset_generator_service, sample_request):
        """Test generating an agent through the service."""
        asset_generator_service.generators[AssetType.AGENT].llm = None

        result = await asset_generator_service.generate_agent(sample_request)
        assert result.success is True
        assert result.asset_type == "agent"

    @pytest.mark.asyncio
    async def test_generate_prompt(self, asset_generator_service, sample_request):
        """Test generating a prompt through the service."""
        asset_generator_service.generators[AssetType.PROMPT].llm = None

        result = await asset_generator_service.generate_prompt(sample_request)
        assert result.success is True
        assert result.asset_type == "prompt"

    @pytest.mark.asyncio
    async def test_generate_workflow(self, asset_generator_service, sample_request):
        """Test generating a workflow through the service."""
        asset_generator_service.generators[AssetType.WORKFLOW].llm = None

        result = await asset_generator_service.generate_workflow(sample_request)
        assert result.success is True
        assert result.asset_type == "workflow"

    @pytest.mark.asyncio
    async def test_generate_generic(self, asset_generator_service, sample_request):
        """Test generating via generic method."""
        asset_generator_service.generators[AssetType.SKILL].llm = None

        result = await asset_generator_service.generate(AssetType.SKILL, sample_request)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_generate_invalid_type(self, asset_generator_service, sample_request):
        """Test generating with invalid type."""
        # Create a mock invalid type
        result = await asset_generator_service.generate(
            MagicMock(value="invalid"),  # Invalid asset type
            sample_request
        )
        assert result.success is False
        assert "Unknown asset type" in result.error

    def test_get_all_stats(self, asset_generator_service):
        """Test getting all stats."""
        # Generate some stats
        for gen in asset_generator_service.generators.values():
            gen._update_stats("it-engineering")

        all_stats = asset_generator_service.get_all_stats()
        assert len(all_stats) == 5
        assert "AGENT-003" in all_stats
        assert all_stats["AGENT-003"]["assets_generated"] == 1


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Test singleton pattern for service."""

    def test_singleton_instance(self):
        """Test that get_asset_generator_service returns same instance."""
        # Reset singleton for test
        import app.services.asset_generator_agents as module
        module._asset_generator_service = None

        service1 = get_asset_generator_service()
        service2 = get_asset_generator_service()

        assert service1 is service2


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling in generators."""

    @pytest.mark.asyncio
    async def test_generation_error_handling(self, skill_generator, sample_request):
        """Test that errors are properly caught and returned."""
        # Force an error by making _generate_content raise
        skill_generator._generate_content = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await skill_generator.generate(sample_request)

        assert result.success is False
        assert "Test error" in result.error

    @pytest.mark.asyncio
    async def test_llm_error_fallback(self, skill_generator, sample_request):
        """Test that LLM errors fall back to static generation."""
        # Set up LLM that will fail
        skill_generator.llm = AsyncMock()
        skill_generator.llm.messages.create = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        result = await skill_generator.generate(sample_request)

        # Should succeed with fallback
        assert result.success is True
        assert result.content is not None


# =============================================================================
# OUTPUT FILE TESTS
# =============================================================================

class TestOutputFiles:
    """Test output file creation and structure."""

    @pytest.mark.asyncio
    async def test_skill_yaml_structure(self, skill_generator, sample_request):
        """Test that generated skill YAML has correct structure."""
        skill_generator.llm = None
        result = await skill_generator.generate(sample_request)

        with open(result.file_path) as f:
            content = yaml.safe_load(f)

        # Required fields
        assert "name" in content
        assert "description" in content
        assert "tools" in content
        assert "instructions" in content
        assert "tags" in content

    @pytest.mark.asyncio
    async def test_workflow_json_structure(self, workflow_generator, sample_request):
        """Test that generated workflow JSON has correct n8n structure."""
        workflow_generator.llm = None
        result = await workflow_generator.generate(sample_request)

        with open(result.file_path) as f:
            content = json.load(f)

        # Required n8n fields
        assert "name" in content
        assert "nodes" in content
        assert "connections" in content
        assert "settings" in content

        # Verify node structure
        for node in content["nodes"]:
            assert "name" in node
            assert "type" in node
            assert "position" in node

    @pytest.mark.asyncio
    async def test_output_directory_structure(self, asset_generator_service, sample_request):
        """Test that output files are created in correct directory structure."""
        # Disable all LLMs
        for gen in asset_generator_service.generators.values():
            gen.llm = None

        # Generate all types
        skill_result = await asset_generator_service.generate_skill(sample_request)
        command_result = await asset_generator_service.generate_command(sample_request)

        # Check directory structure
        skill_path = Path(skill_result.file_path)
        assert "skill" in str(skill_path)
        assert "drafts" in str(skill_path)
        assert "it-engineering" in str(skill_path)

        command_path = Path(command_result.file_path)
        assert "command" in str(command_path)
        assert "drafts" in str(command_path)


# =============================================================================
# DEPARTMENT TESTS
# =============================================================================

class TestDepartments:
    """Test department handling."""

    @pytest.mark.asyncio
    async def test_all_departments(self, skill_generator):
        """Test generation for all departments."""
        skill_generator.llm = None

        for dept in Department:
            request = AssetGenerationRequest(
                name=f"test-{dept.value}",
                description="Test skill for department testing",
                department=dept.value
            )

            result = await skill_generator.generate(request)
            assert result.success is True
            assert dept.value in result.file_path

    @pytest.mark.asyncio
    async def test_stats_by_department(self, skill_generator):
        """Test stats tracking by department."""
        skill_generator.llm = None

        departments = ["it-engineering", "sales-marketing", "it-engineering"]
        for dept in departments:
            request = AssetGenerationRequest(
                name=f"test-{dept}",
                description="Test skill for stats testing",
                department=dept
            )
            await skill_generator.generate(request)

        stats = skill_generator.get_stats()
        assert stats["by_department"]["it-engineering"] == 2
        assert stats["by_department"]["sales-marketing"] == 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the complete asset generation flow."""

    @pytest.mark.asyncio
    async def test_full_generation_flow(self, asset_generator_service, sample_request):
        """Test complete generation flow for all asset types."""
        # Disable all LLMs
        for gen in asset_generator_service.generators.values():
            gen.llm = None

        results = []
        for asset_type in AssetType:
            result = await asset_generator_service.generate(asset_type, sample_request)
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)

        # Each should have unique file path
        file_paths = [r.file_path for r in results]
        assert len(file_paths) == len(set(file_paths))

        # Verify all files exist
        for result in results:
            assert Path(result.file_path).exists()

    @pytest.mark.asyncio
    async def test_batch_generation(self, asset_generator_service):
        """Test generating multiple assets of the same type."""
        # Disable LLM
        asset_generator_service.generators[AssetType.SKILL].llm = None

        requests = [
            AssetGenerationRequest(
                name=f"skill-{i}",
                description=f"Test skill number {i}",
                department="it-engineering"
            )
            for i in range(3)
        ]

        results = []
        for req in requests:
            result = await asset_generator_service.generate_skill(req)
            results.append(result)

        assert all(r.success for r in results)
        assert len(set(r.file_path for r in results)) == 3


# =============================================================================
# API ROUTE TESTS
# =============================================================================

class TestAPIRoutes:
    """Test API route functionality."""

    def test_routes_import(self):
        """Test that routes can be imported."""
        from app.routes.asset_generators import router
        assert router is not None
        assert router.prefix == "/api/assets"

    def test_route_count(self):
        """Test that all expected routes are defined."""
        from app.routes.asset_generators import router

        routes = [route.path for route in router.routes]

        # Routes include prefix, check for expected patterns
        assert any("/skill" in r for r in routes)
        assert any("/command" in r for r in routes)
        assert any("/agent" in r for r in routes)
        assert any("/prompt" in r for r in routes)
        assert any("/workflow" in r for r in routes)
        assert any("/generate/" in r for r in routes)
        assert any("/batch" in r for r in routes)
        assert any("/generators" in r for r in routes)
        assert any("/types" in r for r in routes)
        assert any("/departments" in r for r in routes)
        assert any("/stats" in r for r in routes)
        assert any("/health" in r for r in routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
