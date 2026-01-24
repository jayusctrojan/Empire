# Task ID: 163

**Title:** Add Configurable Timeouts to External Service Calls

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Implement configurable timeouts for all external HTTP calls to prevent indefinite hanging when external services are slow or unresponsive.

**Details:**

Create a new file `app/core/service_timeouts.py` to define timeout constants and modify service client implementations:

1. Define timeout constants for each service:
```python
SERVICE_TIMEOUTS = {
    "llama_index": 60.0,  # 60 seconds for document parsing
    "crewai": 120.0,     # 120 seconds for multi-agent workflows
    "ollama": 30.0,      # 30 seconds for embeddings
    "neo4j": 15.0,       # 15 seconds for graph database
    "supabase": 10.0,    # 10 seconds for database operations
    "default": 30.0      # Default timeout
}
```

2. Create a base ExternalServiceClient class as specified in the PRD:
```python
import httpx
from app.services.circuit_breaker import circuit_breaker
from app.core.service_timeouts import SERVICE_TIMEOUTS

class ExternalServiceClient:
    def __init__(self, service_name: str, base_url: str, timeout: float = None):
        self.service_name = service_name
        timeout = timeout or SERVICE_TIMEOUTS.get(service_name, SERVICE_TIMEOUTS["default"])
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )

    @circuit_breaker()
    async def call(self, endpoint: str, **kwargs):
        return await self.client.post(endpoint, **kwargs)
```

3. Modify each service client to use this base class or implement similar timeout logic:
   - `app/services/llama_index_service.py`
   - `app/services/crewai_service.py`
   - `app/services/embedding_service.py`
   - `app/services/neo4j_service.py`
   - Any other services making external calls

**Test Strategy:**

1. Create unit tests that verify:
   - Timeout values are correctly applied from configuration
   - Default timeout is used for undefined services
   - Custom timeout overrides work correctly

2. Create integration tests that:
   - Mock slow responses and verify timeout behavior
   - Test timeout exceptions are properly handled
   - Verify timeout settings for each service type

3. Create a test utility that simulates slow responses to verify timeout behavior across all service clients
