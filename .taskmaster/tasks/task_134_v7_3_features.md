# Task ID: 134

**Title:** Implement Health Endpoint for Asset Generators

**Status:** done

**Dependencies:** 107 ✓, 132 ✓, 133 ✓

**Priority:** medium

**Description:** Add a health endpoint to Asset Generators (AGENT-003 through AGENT-007) that returns status information and capabilities for all five generators: Skill, Command, Agent, Prompt, and Workflow.

**Details:**

Create a new health endpoint in the asset_generators.py routes file to provide status information for all five Asset Generator agents:

1. Add the following route to app/routes/asset_generators.py:
```python
@router.get("/health", response_model=AssetGeneratorsHealthResponse)
async def get_health():
    """
    Get health status for all Asset Generator agents.
    
    Returns:
        AssetGeneratorsHealthResponse: Status and capabilities for all five generators
    """
    health_service = AssetGeneratorsHealthService()
    return await health_service.get_health_status()
```

2. Create a Pydantic model for the health response in app/models/asset_generators.py:
```python
class GeneratorHealth(BaseModel):
    status: str  # "healthy", "degraded", or "offline"
    capabilities: List[str]
    last_check: datetime
    error_message: Optional[str] = None

class AssetGeneratorsHealthResponse(BaseModel):
    skill_generator: GeneratorHealth
    command_generator: GeneratorHealth
    agent_generator: GeneratorHealth
    prompt_generator: GeneratorHealth
    workflow_generator: GeneratorHealth
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

3. Implement the health service in app/services/asset_generators_health.py:
```python
from datetime import datetime
from app.models.asset_generators import AssetGeneratorsHealthResponse, GeneratorHealth
from app.services.skill_generator import SkillGeneratorService
from app.services.command_generator import CommandGeneratorService
from app.services.agent_generator import AgentGeneratorService
from app.services.prompt_generator import PromptGeneratorService
from app.services.workflow_generator import WorkflowGeneratorService

class AssetGeneratorsHealthService:
    async def get_health_status(self) -> AssetGeneratorsHealthResponse:
        """Get health status for all Asset Generator agents."""
        
        # Get health status from each generator service
        skill_health = await self._check_skill_generator()
        command_health = await self._check_command_generator()
        agent_health = await self._check_agent_generator()
        prompt_health = await self._check_prompt_generator()
        workflow_health = await self._check_workflow_generator()
        
        return AssetGeneratorsHealthResponse(
            skill_generator=skill_health,
            command_generator=command_health,
            agent_generator=agent_health,
            prompt_generator=prompt_health,
            workflow_generator=workflow_health
        )
    
    async def _check_skill_generator(self) -> GeneratorHealth:
        try:
            service = SkillGeneratorService()
            capabilities = await service.get_capabilities()
            return GeneratorHealth(
                status="healthy",
                capabilities=capabilities,
                last_check=datetime.utcnow()
            )
        except Exception as e:
            return GeneratorHealth(
                status="offline",
                capabilities=[],
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    # Implement similar _check methods for other generators
    # _check_command_generator, _check_agent_generator, etc.
```

4. Update each generator service to implement a get_capabilities() method that returns a list of capabilities specific to that generator.

5. Ensure proper error handling and timeouts for health checks to prevent cascading failures.

6. Add appropriate logging for health check operations.

7. Update API documentation to include the new health endpoint.

**Test Strategy:**

1. Create unit tests in tests/routes/test_asset_generators.py:
   ```python
   async def test_health_endpoint_returns_correct_structure():
       # Arrange
       client = TestClient(app)
       
       # Act
       response = client.get("/api/asset-generators/health")
       
       # Assert
       assert response.status_code == 200
       data = response.json()
       assert "skill_generator" in data
       assert "command_generator" in data
       assert "agent_generator" in data
       assert "prompt_generator" in data
       assert "workflow_generator" in data
       assert "timestamp" in data
       
       # Check structure of each generator's health data
       for generator in ["skill_generator", "command_generator", "agent_generator", 
                         "prompt_generator", "workflow_generator"]:
           assert "status" in data[generator]
           assert "capabilities" in data[generator]
           assert "last_check" in data[generator]
   ```

2. Create unit tests for the AssetGeneratorsHealthService:
   - Test successful health checks for all generators
   - Test scenarios where one or more generators are offline
   - Test error handling when exceptions occur

3. Create integration tests that verify the health endpoint with mocked generator services:
   ```python
   @patch("app.services.skill_generator.SkillGeneratorService")
   @patch("app.services.command_generator.CommandGeneratorService")
   # ... patches for other services
   async def test_health_endpoint_with_mocked_services(mock_skill, mock_command, ...):
       # Configure mocks
       mock_skill.return_value.get_capabilities.return_value = ["create_skill", "update_skill"]
       # ... configure other mocks
       
       # Make request
       response = client.get("/api/asset-generators/health")
       
       # Verify response
       # ...
   ```

4. Test error scenarios:
   - Test when one generator is down but others are up
   - Test timeout handling
   - Test with various error conditions

5. Performance testing:
   - Measure response time under normal conditions
   - Test with simulated slow responses from generators

6. Manual testing:
   - Verify the endpoint in development environment
   - Check that all capabilities are correctly listed
   - Verify status values are accurate

7. Update API documentation tests to include the new endpoint.
