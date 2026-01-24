# Task ID: 137

**Title:** Implement Circuit Breaker for Anthropic API Calls

**Status:** done

**Dependencies:** 110 ✓

**Priority:** medium

**Description:** Implement a circuit breaker pattern for Anthropic API calls across all agent services to improve resilience and prevent cascading failures during API outages.

**Details:**

Create a robust circuit breaker implementation for Anthropic API calls that will be used across all agent services:

1. Create a new module `app/services/api_resilience.py` to implement the circuit breaker pattern:
   - Use the `tenacity` or `circuit-breaker` library for implementation
   - Configure exponential backoff with a maximum of 3 retries
   - Implement proper circuit state tracking (closed/open/half-open)
   - Set appropriate thresholds for opening the circuit (e.g., 5 failures in 30 seconds)
   - Implement half-open state with test requests to check if service is restored

2. Create a wrapper class for Anthropic API calls:
```python
from tenacity import retry, stop_after_attempt, wait_exponential
from prometheus_client import Counter, Gauge
import logging

logger = logging.getLogger(__name__)

# Metrics for circuit breaker state
anthropic_circuit_state = Gauge(
    'anthropic_circuit_state',
    'Current state of Anthropic API circuit breaker (0=closed, 1=half-open, 2=open)',
    ['service']
)

anthropic_api_failures = Counter(
    'anthropic_api_failures',
    'Number of Anthropic API call failures',
    ['service', 'endpoint']
)

class AnthropicCircuitBreaker:
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2
    
    def __init__(self, service_name, failure_threshold=5, recovery_timeout=60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = self.CLOSED
        self._update_state_metric()
    
    def _update_state_metric(self):
        anthropic_circuit_state.labels(service=self.service_name).set(self.state)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry_error_callback=lambda retry_state: retry_state.outcome.result()
    )
    async def call_api(self, func, *args, **kwargs):
        """Wrapper for Anthropic API calls with circuit breaker pattern"""
        # Check if circuit is open
        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed to transition to half-open
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = self.HALF_OPEN
                self._update_state_metric()
                logger.info(f"Circuit for {self.service_name} transitioned to HALF-OPEN state")
            else:
                # Fail fast when circuit is open
                logger.warning(f"Circuit for {self.service_name} is OPEN, failing fast")
                raise CircuitOpenError(f"Circuit for {self.service_name} is open")
        
        try:
            result = await func(*args, **kwargs)
            
            # If we're in half-open and call succeeded, close the circuit
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
                self.failure_count = 0
                self._update_state_metric()
                logger.info(f"Circuit for {self.service_name} restored to CLOSED state")
            
            return result
            
        except Exception as e:
            endpoint = kwargs.get('endpoint', 'unknown')
            anthropic_api_failures.labels(service=self.service_name, endpoint=endpoint).inc()
            
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            # Check if we need to open the circuit
            if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                self._update_state_metric()
                logger.error(f"Circuit for {self.service_name} transitioned to OPEN state after {self.failure_count} failures")
            
            # Re-raise the exception for retry handling
            raise
```

3. Apply the circuit breaker to all agent services that call Anthropic API:
   - content_summarizer
   - department_classifier
   - document_analysis
   - multi_agent_orchestration
   - asset_generators

4. Update each service to use the circuit breaker wrapper:
```python
# Example integration in content_summarizer
from app.services.api_resilience import AnthropicCircuitBreaker

class ContentSummarizerAgent:
    def __init__(self):
        # Initialize circuit breaker
        self.circuit_breaker = AnthropicCircuitBreaker(service_name="content_summarizer")
        # Other initialization...
    
    async def summarize_content(self, content):
        try:
            # Use circuit breaker to call Anthropic API
            summary = await self.circuit_breaker.call_api(
                self._call_anthropic_api,
                content=content,
                endpoint="completion"
            )
            return summary
        except CircuitOpenError:
            # Handle circuit open case - return cached response or fallback
            return self._generate_fallback_summary(content)
```

5. Implement appropriate fallback mechanisms for each service when the circuit is open:
   - Return cached responses when available
   - Use simpler models or rules-based approaches as fallbacks
   - Provide clear error messages to users about temporary service limitations

6. Add comprehensive logging for circuit state changes and API failures to aid in debugging and monitoring.

**Test Strategy:**

1. Unit tests for the circuit breaker implementation:
   - Test state transitions (closed → open → half-open → closed)
   - Test failure counting and threshold behavior
   - Test exponential backoff retry logic
   - Test timeout handling and recovery

2. Integration tests with mocked Anthropic API responses:
   - Test successful API calls
   - Test handling of different error types (rate limits, server errors, etc.)
   - Test retry behavior with temporary failures
   - Test circuit opening after threshold failures

3. Test each agent service with the circuit breaker:
   - Verify circuit breaker is properly integrated in each service
   - Test fallback mechanisms when circuit is open
   - Verify metrics are correctly updated for each service

4. Load testing:
   - Simulate high load scenarios to verify circuit breaker prevents cascading failures
   - Test recovery behavior under load

5. Monitoring tests:
   - Verify circuit state metrics are correctly exposed to Prometheus
   - Test dashboard alerts for circuit open states
   - Verify logging provides sufficient information for troubleshooting

6. End-to-end tests:
   - Test the complete flow from API call through circuit breaker to response
   - Verify correct behavior during simulated Anthropic API outages

7. Test fallback quality:
   - Evaluate the quality of fallback responses compared to normal operation
   - Ensure degraded service is still usable when circuit is open
