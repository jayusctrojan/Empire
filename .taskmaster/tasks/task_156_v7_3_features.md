# Task ID: 156

**Title:** LlamaIndex Integration Hardening

**Status:** done

**Dependencies:** 143 ✓, 145 ✓, 147 ✓

**Priority:** medium

**Description:** Implement reliability improvements for the LlamaIndex service including connection pooling, request timeout handling, retry logic for transient failures, and a health check endpoint.

**Details:**

Enhance the LlamaIndex integration with the following reliability improvements:

1. Connection Pooling:
   - Implement a connection pool for LlamaIndex service to efficiently manage and reuse connections
   - Create a `LlamaIndexConnectionPool` class in `app/services/llama_index/connection_pool.py`
   - Configure pool size based on expected load (default: min=5, max=20)
   - Implement connection lifecycle management (creation, validation, recycling)
   - Add monitoring for pool statistics

2. Request Timeout Handling:
   - Add configurable timeout parameters for all LlamaIndex operations
   - Implement graceful timeout handling with appropriate error messages
   - Create a timeout configuration in `app/config/llama_index_config.py`
   - Add logging for timeout events with context information

3. Retry Logic:
   - Implement exponential backoff retry mechanism for transient failures
   - Define retry policies for different types of operations (queries, indexing, etc.)
   - Create a `RetryHandler` class in `app/services/llama_index/retry_handler.py`
   - Configure max retry attempts, backoff factor, and jitter
   - Add detailed logging of retry attempts and outcomes

4. Health Check Endpoint:
   - Create a `/api/llama-index/health` endpoint in `app/api/routes/llama_index.py`
   - Implement comprehensive health checks that verify:
     - Connection to LlamaIndex service
     - Index availability and status
     - Query functionality with a simple test query
     - Resource availability (memory, storage)
   - Return detailed health status with component-level information
   - Add integration with the application's overall health monitoring system

5. Error Handling Improvements:
   - Create standardized error responses for different failure scenarios
   - Implement detailed logging with context information
   - Add error classification to distinguish between transient and permanent failures

Sample code for connection pool implementation:
```python
# app/services/llama_index/connection_pool.py
from typing import List, Optional
import time
import threading
from llama_index import ServiceContext, StorageContext, load_index_from_storage

class LlamaIndexConnection:
    def __init__(self, index_id: str):
        self.index_id = index_id
        self.last_used = time.time()
        self.created_at = time.time()
        self.service_context = ServiceContext.from_defaults()
        self.storage_context = StorageContext.from_defaults()
        self.index = load_index_from_storage(self.storage_context)
        
    def is_valid(self) -> bool:
        # Implement validation logic
        return True
        
    def refresh(self) -> None:
        # Implement refresh logic
        self.last_used = time.time()

class LlamaIndexConnectionPool:
    def __init__(self, min_connections: int = 5, max_connections: int = 20):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connections: List[LlamaIndexConnection] = []
        self.lock = threading.RLock()
        self.initialize_pool()
        
    def initialize_pool(self) -> None:
        with self.lock:
            for _ in range(self.min_connections):
                self.connections.append(LlamaIndexConnection("default"))
                
    def get_connection(self) -> LlamaIndexConnection:
        with self.lock:
            if not self.connections:
                if len(self.connections) < self.max_connections:
                    return LlamaIndexConnection("default")
                else:
                    # Wait for a connection to become available
                    # Implement waiting logic
                    pass
            
            connection = self.connections.pop(0)
            if not connection.is_valid():
                connection = LlamaIndexConnection("default")
            
            return connection
            
    def release_connection(self, connection: LlamaIndexConnection) -> None:
        with self.lock:
            connection.refresh()
            self.connections.append(connection)
```

**Test Strategy:**

1. Connection Pool Testing:
   - Unit test the `LlamaIndexConnectionPool` class with various pool sizes
   - Verify connections are properly created, managed, and recycled
   - Test concurrent access patterns with multiple threads
   - Validate connection validation logic works correctly
   - Measure performance improvements with and without connection pooling

2. Timeout Handling Testing:
   - Create test cases with deliberately slow operations
   - Verify timeout configuration is correctly applied
   - Test different timeout values and their effects
   - Ensure proper error messages are returned on timeout
   - Validate that resources are properly cleaned up after timeout

3. Retry Logic Testing:
   - Create mock LlamaIndex service that fails intermittently
   - Test retry behavior with various failure patterns
   - Verify exponential backoff works as expected
   - Test different retry configurations
   - Ensure maximum retry limit is respected
   - Validate that permanent failures are handled correctly

4. Health Check Endpoint Testing:
   - Test the endpoint returns correct status when all systems are operational
   - Simulate various failure conditions and verify correct reporting
   - Test response format and content
   - Verify integration with monitoring systems
   - Test performance impact of health checks

5. Integration Testing:
   - Create end-to-end tests that verify all components work together
   - Test under load to ensure stability
   - Verify error propagation and handling
   - Test recovery scenarios after simulated failures
   - Validate logging and monitoring integration

6. Performance Testing:
   - Measure throughput with and without the improvements
   - Test under various load conditions
   - Measure resource utilization (CPU, memory)
   - Identify and address any bottlenecks
