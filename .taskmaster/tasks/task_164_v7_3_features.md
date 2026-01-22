# Task ID: 164

**Title:** Implement Circuit Breaker Pattern for All External Services

**Status:** cancelled

**Dependencies:** 163 ✗

**Priority:** high

**Description:** Apply circuit breakers to all external service calls to prevent cascading failures when external services are down or degraded.

**Details:**

Extend the existing circuit breaker implementation to cover all external services:

1. Define circuit breaker configuration in a central location:
```python
# app/core/circuit_breaker_config.py
CIRCUIT_BREAKER_CONFIG = {
    "llama_index": {"failure_threshold": 5, "recovery_timeout": 30},
    "crewai": {"failure_threshold": 3, "recovery_timeout": 60},
    "ollama": {"failure_threshold": 5, "recovery_timeout": 15},
    "neo4j": {"failure_threshold": 3, "recovery_timeout": 30},
    "b2": {"failure_threshold": 5, "recovery_timeout": 60},
    "default": {"failure_threshold": 3, "recovery_timeout": 30},
}
```

2. Enhance the circuit breaker decorator to use this configuration:
```python
# app/services/circuit_breaker.py
import functools
import time
from typing import Dict, Any, Callable, Optional
import structlog
from app.core.circuit_breaker_config import CIRCUIT_BREAKER_CONFIG

logger = structlog.get_logger(__name__)

class CircuitBreaker:
    _instances: Dict[str, "CircuitBreaker"] = {}
    
    @classmethod
    def get_instance(cls, service_name: str) -> "CircuitBreaker":
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
            self.open = True
            logger.warning(
                "Circuit breaker opened",
                service=self.service_name,
                failures=self.failure_count
            )
    
    def record_success(self):
        self.failure_count = 0
        if self.open:
            self.open = False
            logger.info(
                "Circuit breaker closed",
                service=self.service_name
            )
    
    def is_open(self) -> bool:
        if not self.open:
            return False
            
        # Check if recovery timeout has elapsed
        if time.time() - self.last_failure_time > self.recovery_timeout:
            logger.info(
                "Circuit breaker recovery timeout elapsed, allowing request",
                service=self.service_name
            )
            return False
            
        return True

def circuit_breaker(service_name: Optional[str] = None):
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get service name from instance or parameter
            svc_name = service_name or getattr(self, "service_name", "default")
            breaker = CircuitBreaker.get_instance(svc_name)
            
            if breaker.is_open():
                logger.warning(
                    "Circuit breaker open, rejecting request",
                    service=svc_name
                )
                raise ServiceUnavailableError(f"{svc_name} service is currently unavailable")
                
            try:
                result = await func(self, *args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                logger.exception(
                    "External service call failed",
                    service=svc_name,
                    error=str(e)
                )
                raise
                
        return wrapper
    return decorator
```

3. Apply the circuit breaker decorator to all external service calls in:
   - `app/services/llama_index_service.py`
   - `app/services/crewai_service.py`
   - `app/services/embedding_service.py`
   - `app/services/arcade_service.py`
   - `app/services/neo4j_service.py`
   - `app/services/b2_storage.py`

4. Create a ServiceUnavailableError class that returns appropriate 503 responses

**Test Strategy:**

1. Create unit tests that verify:
   - Circuit breaker opens after threshold failures
   - Circuit breaker rejects requests when open
   - Circuit breaker allows requests after recovery timeout
   - Circuit breaker resets on successful calls

2. Create integration tests that:
   - Simulate service failures to trigger circuit breaker
   - Verify correct error responses when circuit is open
   - Test recovery behavior after timeout
   - Confirm circuit breaker state is maintained between requests

3. Test with various failure scenarios to ensure all services are properly protected
