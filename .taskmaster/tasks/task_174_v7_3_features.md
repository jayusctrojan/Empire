# Task ID: 174

**Title:** Implement Circuit Breaker Pattern for External Services

**Status:** done

**Dependencies:** 173 ✓

**Priority:** high

**Description:** Apply circuit breakers to all external service calls to prevent cascading failures when external services are down or degraded.

**Details:**

1. Create a circuit breaker implementation in `app/services/circuit_breaker.py`:
```python
import functools
import time
from typing import Dict, Any, Callable, TypeVar, Awaitable
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')

CIRCUIT_BREAKER_CONFIG = {
    "llama_index": {"failure_threshold": 5, "recovery_timeout": 30},
    "crewai": {"failure_threshold": 3, "recovery_timeout": 60},
    "ollama": {"failure_threshold": 5, "recovery_timeout": 15},
    "neo4j": {"failure_threshold": 3, "recovery_timeout": 30},
    "b2": {"failure_threshold": 5, "recovery_timeout": 60},
    "default": {"failure_threshold": 3, "recovery_timeout": 30},
}

class CircuitBreaker:
    _instances: Dict[str, 'CircuitBreaker'] = {}
    
    @classmethod
    def get_instance(cls, service_name: str) -> 'CircuitBreaker':
        if service_name not in cls._instances:
            config = CIRCUIT_BREAKER_CONFIG.get(
                service_name, CIRCUIT_BREAKER_CONFIG["default"]
            )
            cls._instances[service_name] = CircuitBreaker(
                service_name=service_name,
                failure_threshold=config["failure_threshold"],
                recovery_timeout=config["recovery_timeout"]
            )
        return cls._instances[service_name]
    
    def __init__(self, service_name: str, failure_threshold: int, recovery_timeout: int):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.open = False
        
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            if not self.open:
                logger.warning(
                    f"Circuit breaker opened for {self.service_name}",
                    service=self.service_name,
                    failures=self.failure_count,
                    threshold=self.failure_threshold
                )
            self.open = True
    
    def record_success(self):
        self.failure_count = 0
        if self.open:
            logger.info(
                f"Circuit breaker closed for {self.service_name}",
                service=self.service_name
            )
            self.open = False
    
    def is_open(self) -> bool:
        if not self.open:
            return False
            
        # Check if recovery timeout has elapsed
        if time.time() - self.last_failure_time > self.recovery_timeout:
            logger.info(
                f"Circuit breaker recovery timeout elapsed for {self.service_name}",
                service=self.service_name
            )
            return False
            
        return True

def circuit_breaker(service_name: str):
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            breaker = CircuitBreaker.get_instance(service_name)
            
            if breaker.is_open():
                raise ServiceUnavailableError(
                    f"{service_name} circuit breaker is open"
                )
                
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                logger.error(
                    f"Circuit breaker recorded failure for {service_name}",
                    service=service_name,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
                
        return wrapper
    return decorator
```

2. Apply the circuit breaker decorator to all external service methods in:
   - `app/services/llama_index_service.py`
   - `app/services/crewai_service.py`
   - `app/services/embedding_service.py`
   - `app/services/neo4j_service.py`
   - `app/services/b2_storage.py`

3. Create a `ServiceUnavailableError` class in `app/models/errors.py` that returns a 503 status code

**Test Strategy:**

1. Create unit tests that verify:
   - Circuit breaker opens after threshold failures
   - Circuit breaker stays open during recovery timeout
   - Circuit breaker closes after recovery timeout
   - Circuit breaker closes after successful call

2. Create integration tests that:
   - Test circuit breaker with mock services that fail
   - Verify circuit breaker prevents calls to failed services
   - Test recovery behavior

3. Test different configuration values for different services

## Subtasks

### 174.1. Create tests/test_circuit_breakers.py with mock service fixtures

**Status:** pending  
**Dependencies:** None  

Set up a test file with mock service fixtures to test the circuit breaker functionality

**Details:**

Create a new test file at tests/test_circuit_breakers.py that includes pytest fixtures for mocking external services. Include setup for simulating failures and successes, and configure the test environment with appropriate timeouts for testing recovery periods.

### 174.2. Test LlamaIndex circuit opens after 5 failures

**Status:** pending  
**Dependencies:** 174.1  

Implement a test case to verify that the circuit breaker for LlamaIndex opens after 5 consecutive failures

**Details:**

Create a test function that simulates 5 consecutive failures when calling LlamaIndex service. Verify that after the 5th failure, the circuit breaker transitions to the open state and logs the appropriate warning message.

### 174.3. Test circuit in open state fails immediately

**Status:** pending  
**Dependencies:** 174.1, 174.2  

Verify that when a circuit is in the open state, subsequent requests fail immediately without attempting to call the service

**Details:**

Create a test function that first puts a circuit breaker into the open state, then attempts to make additional service calls. Verify that these calls immediately raise a ServiceUnavailableError without attempting to call the underlying service.

### 174.4. Test circuit transitions to half-open after recovery timeout

**Status:** pending  
**Dependencies:** 174.1, 174.3  

Implement a test to verify that a circuit breaker transitions from open to half-open state after the recovery timeout period

**Details:**

Create a test function that puts a circuit breaker into the open state, then advances the mock time beyond the recovery timeout period. Verify that the next call attempt is allowed through (half-open state) rather than failing immediately.

### 174.5. Test successful request in half-open closes circuit

**Status:** pending  
**Dependencies:** 174.1, 174.4  

Verify that a successful service call when the circuit is in half-open state causes it to transition back to closed

**Details:**

Create a test function that puts a circuit breaker into the half-open state, then simulates a successful service call. Verify that the circuit breaker transitions back to the closed state and resets its failure counter.

### 174.6. Apply circuit breaker decorator to app/services/llama_index_service.py

**Status:** pending  
**Dependencies:** 174.1, 174.5  

Apply the circuit breaker decorator to all external service methods in the LlamaIndex service

**Details:**

Modify app/services/llama_index_service.py to apply the @circuit_breaker('llama_index') decorator to all methods that make external API calls. Ensure the configuration uses 5 failures threshold and 30s recovery timeout as specified in the CIRCUIT_BREAKER_CONFIG.

### 174.7. Apply circuit breaker decorator to app/services/crewai_service.py

**Status:** pending  
**Dependencies:** 174.1, 174.5  

Apply the circuit breaker decorator to all external service methods in the CrewAI service

**Details:**

Modify app/services/crewai_service.py to apply the @circuit_breaker('crewai') decorator to all methods that make external API calls. Ensure the configuration uses 3 failures threshold and 60s recovery timeout as specified in the CIRCUIT_BREAKER_CONFIG.

### 174.8. Apply circuit breaker decorator to app/services/embedding_service.py

**Status:** pending  
**Dependencies:** 174.1, 174.5  

Apply the circuit breaker decorator to all external service methods in the Embedding service

**Details:**

Modify app/services/embedding_service.py to apply the @circuit_breaker('ollama') decorator to all methods that make external API calls. Ensure the configuration uses 5 failures threshold and 15s recovery timeout as specified in the CIRCUIT_BREAKER_CONFIG.

### 174.9. Apply circuit breaker decorator to app/services/neo4j_service.py

**Status:** pending  
**Dependencies:** 174.1, 174.5  

Apply the circuit breaker decorator to all external service methods in the Neo4j service

**Details:**

Modify app/services/neo4j_service.py to apply the @circuit_breaker('neo4j') decorator to all methods that make external API calls. Ensure the configuration uses 3 failures threshold and 30s recovery timeout as specified in the CIRCUIT_BREAKER_CONFIG.

### 174.10. Apply circuit breaker decorator to app/services/b2_storage.py

**Status:** pending  
**Dependencies:** 174.1, 174.5  

Apply the circuit breaker decorator to all external service methods in the B2 Storage service

**Details:**

Modify app/services/b2_storage.py to apply the @circuit_breaker('b2') decorator to all methods that make external API calls. Ensure the configuration uses 5 failures threshold and 60s recovery timeout as specified in the CIRCUIT_BREAKER_CONFIG.

### 174.11. Implement /api/system/circuit-breakers endpoint

**Status:** pending  
**Dependencies:** 174.6, 174.7, 174.8, 174.9, 174.10  

Create an API endpoint that exposes the current state of all circuit breakers in the system

**Details:**

Create a new endpoint at /api/system/circuit-breakers that returns the current state of all circuit breakers, including their service name, current state (open/closed), failure count, and last failure time. This will be used for monitoring and debugging purposes.
