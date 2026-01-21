# Task ID: 173

**Title:** Implement External Service Timeouts

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Add configurable timeouts to all external HTTP calls to prevent indefinite hanging when external services are slow or unresponsive.

**Details:**

1. Create a new file `app/core/service_timeouts.py` to define timeout constants:
```python
SERVICE_TIMEOUTS = {
    "llama_index": 60.0,  # 60 seconds (document parsing can be slow)
    "crewai": 120.0,     # 120 seconds (multi-agent workflows)
    "ollama": 30.0,      # 30 seconds (embeddings)
    "neo4j": 15.0,       # 15 seconds
    "supabase": 10.0,    # 10 seconds
    "default": 30.0      # Default timeout
}
```

2. Create a base client class that implements timeouts:
```python
class ExternalServiceClient:
    def __init__(self, base_url: str, service_name: str):
        timeout = SERVICE_TIMEOUTS.get(service_name, SERVICE_TIMEOUTS["default"])
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        self.service_name = service_name

    async def call(self, endpoint: str, **kwargs):
        try:
            return await self.client.post(endpoint, **kwargs)
        except httpx.TimeoutException:
            logger.error(f"{self.service_name} request timed out", endpoint=endpoint)
            raise ServiceTimeoutError(f"{self.service_name} request timed out")
```

3. Modify the following service files to use the timeout-enabled client:
   - `app/services/llama_index_service.py`
   - `app/services/crewai_service.py`
   - `app/services/embedding_service.py`
   - `app/services/neo4j_service.py`
   - `app/services/b2_storage.py`

**Test Strategy:**

1. Create unit tests that verify:
   - Timeout values are correctly applied from configuration
   - TimeoutException is properly caught and converted to ServiceTimeoutError

2. Create integration tests that:
   - Use a mock server that delays responses beyond timeout threshold
   - Verify requests actually timeout after the configured duration
   - Test different timeout values for different services

3. Create tests for timeout error handling and reporting

## Subtasks

### 173.1. Create test_service_timeouts.py with httpx mock fixtures

**Status:** pending  
**Dependencies:** None  

Set up the test file with necessary fixtures for mocking httpx responses and timeouts

**Details:**

Create tests/test_service_timeouts.py with httpx mock fixtures for simulating timeouts. Include setup for mocked responses, delayed responses, and timeout exceptions. Set up pytest fixtures that can be reused across all timeout tests.

### 173.2. Test LlamaIndex service timeout after 60s

**Status:** pending  
**Dependencies:** 173.1  

Implement test case to verify LlamaIndex service times out correctly after 60 seconds

**Details:**

Create a test that verifies the LlamaIndex service correctly applies a 60-second timeout. Use the httpx mock to simulate a response that takes longer than 60 seconds and verify that a ServiceTimeoutError is raised with the appropriate message.

### 173.3. Test CrewAI service timeout after 120s

**Status:** pending  
**Dependencies:** 173.1  

Implement test case to verify CrewAI service times out correctly after 120 seconds

**Details:**

Create a test that verifies the CrewAI service correctly applies a 120-second timeout. Use the httpx mock to simulate a response that takes longer than 120 seconds and verify that a ServiceTimeoutError is raised with the appropriate message.

### 173.4. Test Ollama service timeout after 30s

**Status:** pending  
**Dependencies:** 173.1  

Implement test case to verify Ollama service times out correctly after 30 seconds

**Details:**

Create a test that verifies the Ollama service correctly applies a 30-second timeout. Use the httpx mock to simulate a response that takes longer than 30 seconds and verify that a ServiceTimeoutError is raised with the appropriate message.

### 173.5. Test Neo4j service timeout after 15s

**Status:** pending  
**Dependencies:** 173.1  

Implement test case to verify Neo4j service times out correctly after 15 seconds

**Details:**

Create a test that verifies the Neo4j service correctly applies a 15-second timeout. Use the httpx mock to simulate a response that takes longer than 15 seconds and verify that a ServiceTimeoutError is raised with the appropriate message.

### 173.6. Create service_timeouts.py with timeout constants

**Status:** pending  
**Dependencies:** None  

Implement the core timeout configuration file with constants for all services

**Details:**

Create app/core/service_timeouts.py with the SERVICE_TIMEOUTS dictionary containing timeout values for all external services. Implement the ExternalServiceClient class that uses these timeout values to create httpx clients with appropriate timeout settings.

### 173.7. Add timeout configuration to llama_index_service.py

**Status:** pending  
**Dependencies:** 173.6  

Modify the LlamaIndex service to use the timeout-enabled client

**Details:**

Update app/services/llama_index_service.py to use the ExternalServiceClient with the 'llama_index' service name. Replace direct httpx calls with the timeout-enabled client. Ensure proper error handling for timeout exceptions.

### 173.8. Add timeout configuration to crewai_service.py

**Status:** pending  
**Dependencies:** 173.6  

Modify the CrewAI service to use the timeout-enabled client

**Details:**

Update app/services/crewai_service.py to use the ExternalServiceClient with the 'crewai' service name. Replace direct httpx calls with the timeout-enabled client. Ensure proper error handling for timeout exceptions.

### 173.9. Add timeout configuration to embedding_service.py

**Status:** pending  
**Dependencies:** 173.6  

Modify the embedding service to use the timeout-enabled client for Ollama

**Details:**

Update app/services/embedding_service.py to use the ExternalServiceClient with the 'ollama' service name. Replace direct httpx calls with the timeout-enabled client. Ensure proper error handling for timeout exceptions.

### 173.10. Add timeout configuration to neo4j_service.py

**Status:** pending  
**Dependencies:** 173.6  

Modify the Neo4j service to use the timeout-enabled client

**Details:**

Update app/services/neo4j_service.py to use the ExternalServiceClient with the 'neo4j' service name. Replace direct httpx calls with the timeout-enabled client. Ensure proper error handling for timeout exceptions.

### 173.11. Add timeout error handling with EXTERNAL_SERVICE_ERROR response

**Status:** pending  
**Dependencies:** 173.7, 173.8, 173.9, 173.10  

Implement standardized error handling for service timeouts across the application

**Details:**

Create a ServiceTimeoutError exception class and implement error handling that returns a standardized EXTERNAL_SERVICE_ERROR response when timeouts occur. Update all service files to catch timeout exceptions and convert them to ServiceTimeoutError with appropriate logging.
