# Task ID: 178

**Title:** Create Service Timeout Configuration Module

**Status:** done

**Dependencies:** 173 ✓

**Priority:** medium

**Description:** Create a central configuration module for service timeouts to ensure consistent timeout settings across the application.

**Details:**

1. Create a new file `app/core/service_timeouts.py` to define timeout constants and configuration:

```python
from typing import Dict, Any
import os

# Default timeout values in seconds
DEFAULT_TIMEOUTS = {
    "llama_index": 60.0,  # 60 seconds (document parsing can be slow)
    "crewai": 120.0,     # 120 seconds (multi-agent workflows)
    "ollama": 30.0,      # 30 seconds (embeddings)
    "neo4j": 15.0,       # 15 seconds
    "supabase": 10.0,    # 10 seconds
    "arcade": 30.0,      # 30 seconds
    "b2": 45.0,          # 45 seconds
    "default": 30.0      # Default timeout
}

# Environment variable prefix for overriding timeouts
ENV_PREFIX = "TIMEOUT_"

def get_timeout(service_name: str) -> float:
    """Get timeout for a service, allowing environment variable override."""
    # Check for environment variable override (e.g., TIMEOUT_LLAMA_INDEX=90)
    env_var = f"{ENV_PREFIX}{service_name.upper()}"
    env_value = os.getenv(env_var)
    
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            # Log warning about invalid timeout value
            pass
    
    # Fall back to default timeout
    return DEFAULT_TIMEOUTS.get(service_name, DEFAULT_TIMEOUTS["default"])

def get_connect_timeout(service_name: str) -> float:
    """Get connection timeout, which is typically shorter than request timeout."""
    # Connection timeouts are usually shorter
    return min(5.0, get_timeout(service_name) / 4)

def get_all_timeouts() -> Dict[str, Any]:
    """Get all timeout configurations for monitoring/logging."""
    result = {}
    
    # Include defaults
    for service, timeout in DEFAULT_TIMEOUTS.items():
        result[service] = {
            "default": timeout,
            "current": get_timeout(service),
            "connect": get_connect_timeout(service)
        }
    
    return result
```

2. Create a utility function to configure httpx clients with proper timeouts:

```python
# app/utils/http_client.py
import httpx
from app.core.service_timeouts import get_timeout, get_connect_timeout

def create_http_client(service_name: str, base_url: str = None) -> httpx.AsyncClient:
    """Create an httpx client with appropriate timeouts for the service."""
    timeout = get_timeout(service_name)
    connect_timeout = get_connect_timeout(service_name)
    
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout, connect=connect_timeout),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )
```

3. Add a startup event handler to log all timeout configurations:

```python
# In app/main.py
from app.core.service_timeouts import get_all_timeouts
import structlog

logger = structlog.get_logger(__name__)

@app.on_event("startup")
async def log_timeout_configuration():
    timeouts = get_all_timeouts()
    logger.info("Service timeout configuration", timeouts=timeouts)
```

**Test Strategy:**

1. Create unit tests in `tests/test_service_timeouts.py` that verify:
   - Default timeouts are correctly defined
   - Environment variable overrides work correctly
   - Invalid environment values are handled gracefully
   - Connection timeouts are calculated correctly

2. Create integration tests that:
   - Verify HTTP clients are created with correct timeout values
   - Test that timeouts actually trigger after the specified duration
   - Check that timeout configurations are properly logged at startup

3. Test with various environment variable configurations
