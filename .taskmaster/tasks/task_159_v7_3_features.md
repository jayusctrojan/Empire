# Task ID: 159

**Title:** Implement Circuit Breaker Pattern for External API Services

**Status:** done

**Dependencies:** 137 ✓, 101 ✓, 110 ✓

**Priority:** medium

**Description:** Implement a comprehensive circuit breaker pattern for all external API calls including Anthropic, Neo4j, and Supabase with configurable thresholds, fallback responses, and monitoring capabilities.

**Details:**

Extend the existing circuit breaker implementation to cover all external API services with enhanced functionality:

1. Refactor the existing `app/services/api_resilience.py` module to support multiple API services:
   - Create a configurable CircuitBreaker class that can be instantiated for different services
   - Implement service-specific configuration profiles for Anthropic, Neo4j, and Supabase
   - Add support for per-service configurable thresholds:
     ```python
     class CircuitBreakerConfig:
         def __init__(self, 
                     failure_threshold: int = 5,
                     recovery_timeout: int = 30,
                     retry_max_attempts: int = 3,
                     retry_backoff_factor: float = 2.0,
                     timeout: int = 10):
             self.failure_threshold = failure_threshold
             self.recovery_timeout = recovery_timeout
             self.retry_max_attempts = retry_max_attempts
             self.retry_backoff_factor = retry_backoff_factor
             self.timeout = timeout
     
     class CircuitBreaker:
         def __init__(self, service_name: str, config: CircuitBreakerConfig = None):
             self.service_name = service_name
             self.config = config or CircuitBreakerConfig()
             self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
             self.failure_count = 0
             self.last_failure_time = None
             # Additional state tracking
     ```

2. Implement fallback response mechanisms:
   - Create a FallbackRegistry to store and retrieve fallback handlers
   - Implement default fallback responses for each service type
   - Allow custom fallback handlers to be registered per operation
   - Example implementation:
     ```python
     class FallbackRegistry:
         def __init__(self):
             self.fallbacks = {}
         
         def register(self, service_name: str, operation: str, handler: Callable):
             if service_name not in self.fallbacks:
                 self.fallbacks[service_name] = {}
             self.fallbacks[service_name][operation] = handler
         
         def get_fallback(self, service_name: str, operation: str) -> Optional[Callable]:
             return self.fallbacks.get(service_name, {}).get(operation)
     ```

3. Add circuit state monitoring and metrics:
   - Implement Prometheus metrics for circuit state changes
   - Track success/failure rates, response times, and circuit open duration
   - Create a dashboard endpoint for current circuit states
   - Log all circuit state transitions with context
   - Example metrics:
     ```python
     # In app/monitoring/metrics.py
     from prometheus_client import Counter, Gauge, Histogram
     
     # Counters
     circuit_state_changes = Counter('circuit_breaker_state_changes_total', 
                                    'Circuit breaker state transitions',
                                    ['service', 'from_state', 'to_state'])
     circuit_requests = Counter('circuit_breaker_requests_total',
                               'Requests through circuit breaker',
                               ['service', 'result'])
     
     # Gauges
     circuit_state = Gauge('circuit_breaker_state',
                          'Current circuit breaker state (0=closed, 1=half-open, 2=open)',
                          ['service'])
     
     # Histograms
     circuit_response_time = Histogram('circuit_breaker_response_time_seconds',
                                      'Response time for requests through circuit breaker',
                                      ['service'])
     ```

4. Create service-specific circuit breaker wrappers:
   - Implement AnthropicCircuitBreaker (extending existing implementation)
   - Implement Neo4jCircuitBreaker for database operations
   - Implement SupabaseCircuitBreaker for storage operations
   - Example wrapper:
     ```python
     class Neo4jCircuitBreaker:
         def __init__(self, client, config=None):
             self.client = client
             self.circuit = CircuitBreaker("neo4j", config)
             self.fallback_registry = FallbackRegistry()
             
             # Register default fallbacks
             self.fallback_registry.register("neo4j", "query", self._default_query_fallback)
         
         async def query(self, cypher, params=None):
             try:
                 return await self.circuit.execute(
                     lambda: self.client.query(cypher, params),
                     operation="query"
                 )
             except CircuitOpenError:
                 fallback = self.fallback_registry.get_fallback("neo4j", "query")
                 return await fallback(cypher, params)
         
         async def _default_query_fallback(self, cypher, params=None):
             # Return cached results or empty response
             return {"results": [], "from_fallback": True}
     ```

5. Update service initialization to use circuit breakers:
   - Modify service factory methods to wrap clients with circuit breakers
   - Update dependency injection to provide circuit-protected clients
   - Add configuration loading from environment variables

6. Implement a circuit breaker management API:
   - Create endpoints to view circuit states
   - Allow manual reset of circuits
   - Provide configuration update capabilities
   - Example API routes:
     ```python
     @router.get("/api/system/circuit-breakers")
     async def get_circuit_states():
         # Return states of all circuit breakers
     
     @router.post("/api/system/circuit-breakers/{service}/reset")
     async def reset_circuit(service: str):
         # Reset specified circuit breaker
     ```

**Test Strategy:**

1. Unit tests for the CircuitBreaker class:
   - Test state transitions (closed → open → half-open → closed)
   - Test configurable thresholds for different services
   - Test failure counting and reset behavior
   - Test timeout handling and recovery periods
   - Test metrics recording

2. Unit tests for fallback mechanisms:
   - Test fallback registry registration and retrieval
   - Test default fallbacks for each service
   - Test custom fallback handlers
   - Test fallback context preservation

3. Integration tests for each service-specific circuit breaker:
   - Test AnthropicCircuitBreaker with mocked API responses
   - Test Neo4jCircuitBreaker with mocked database responses
   - Test SupabaseCircuitBreaker with mocked storage responses
   - Test circuit opening on consecutive failures
   - Test circuit recovery after timeout period

4. Failure scenario testing:
   - Simulate API timeouts and verify circuit behavior
   - Simulate connection errors and verify fallback responses
   - Test partial failures (some endpoints working, others failing)
   - Verify correct fallback content is returned

5. Performance testing:
   - Measure overhead of circuit breaker implementation
   - Test under high concurrency to verify thread safety
   - Verify no memory leaks during extended operation

6. Monitoring tests:
   - Verify metrics are correctly recorded and exposed
   - Test dashboard endpoint for accurate state reporting
   - Verify logs contain appropriate context for debugging

7. End-to-end tests:
   - Test complete request flow with circuit breakers in place
   - Verify application resilience during simulated outages
   - Test recovery behavior when services come back online
