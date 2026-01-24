# Task ID: 133

**Title:** Implement Orchestrator API Routes

**Status:** done

**Dependencies:** 103 ✓, 122 ✓, 124 ✓

**Priority:** medium

**Description:** Create API routes for the Master Orchestrator (AGENT-001) to expose its functionality, including coordination, agent listing, health checks, and statistics endpoints.

**Details:**

Create the file `app/routes/orchestrator.py` with the following FastAPI routes:

1. POST /api/orchestrator/coordinate - Main endpoint for orchestrating agent workflows
   - Implement request validation using Pydantic models
   - Parse incoming requests and delegate to the Orchestrator service
   - Handle response formatting and error cases

2. GET /api/orchestrator/agents - Endpoint to list all available agents
   - Return metadata about registered agents including capabilities and status
   - Support filtering by agent type, status, or capability

3. GET /api/orchestrator/health - Health check endpoint
   - Verify Orchestrator service is running properly
   - Check connections to dependent services
   - Return appropriate health status codes

4. GET /api/orchestrator/stats - Statistics endpoint
   - Collect and return performance metrics
   - Include agent usage statistics, response times, and success rates
   - Support time-range filtering

Register the router in main.py by adding:
```python
from app.routes import orchestrator

app.include_router(orchestrator.router, tags=["orchestrator"])
```

Create Pydantic models in `app/models/orchestrator.py`:
```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum

class AgentType(str, Enum):
    CONTENT_PREP = "content_prep"
    GRAPH = "graph"
    RETRIEVAL = "retrieval"
    # Add other agent types

class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"

class OrchestrationRequest(BaseModel):
    workflow_id: Optional[str] = Field(None, description="Optional workflow identifier")
    task: str = Field(..., description="Task description for orchestration")
    agents: List[str] = Field(default=[], description="Specific agents to include")
    parameters: Dict[str, Any] = Field(default={}, description="Task parameters")
    
class AgentInfo(BaseModel):
    id: str
    name: str
    type: AgentType
    status: AgentStatus
    capabilities: List[str]
    
class OrchestrationResponse(BaseModel):
    workflow_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    
class HealthStatus(BaseModel):
    status: str
    version: str
    dependencies: Dict[str, str]
    
class StatsResponse(BaseModel):
    total_requests: int
    success_rate: float
    average_response_time: float
    agent_usage: Dict[str, int]
    recent_workflows: List[Dict[str, Any]]
```

Ensure proper error handling and validation throughout the implementation.

**Test Strategy:**

1. Create unit tests in `tests/routes/test_orchestrator.py` for each endpoint:
   - Test POST /api/orchestrator/coordinate with valid and invalid payloads
   - Test GET /api/orchestrator/agents with various filter parameters
   - Test GET /api/orchestrator/health in normal and degraded states
   - Test GET /api/orchestrator/stats with different time ranges

2. Create integration tests that verify:
   - Router registration works correctly in main.py
   - Endpoints interact properly with the Orchestrator service
   - Authentication and authorization are enforced correctly

3. Test error handling:
   - Verify appropriate status codes for various error conditions
   - Test validation errors with malformed requests
   - Test service unavailable scenarios

4. Test Pydantic models:
   - Verify model validation works as expected
   - Test serialization/deserialization
   - Ensure OpenAPI schema generation is correct

5. Performance testing:
   - Test response times under load
   - Verify endpoints can handle concurrent requests
   - Check memory usage during extended operation

6. Documentation verification:
   - Ensure API documentation is generated correctly
   - Verify examples in documentation match implementation
