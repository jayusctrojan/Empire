# Research: Production Readiness Improvements

**Branch**: `009-production-readiness` | **Date**: 2025-01-15

## Research Summary

All technical decisions resolved from PRD and existing codebase analysis.

---

## Decision 1: Rate Limiting Library

**Question**: Which library to use for tiered rate limiting?

**Decision**: Use existing slowapi with Redis backend

**Rationale**:
- Already installed and configured in `app/middleware/rate_limit.py`
- Supports Redis backend for multi-instance deployments
- Supports per-endpoint configuration via decorators
- Supports key extraction from request (IP, user ID)

**Alternatives Considered**:
- Custom implementation: Rejected (unnecessary complexity)
- limits library: Rejected (slowapi already wraps it)

**Implementation Notes**:
```python
# Existing pattern to extend
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)

# Add per-endpoint limits via decorator
@limiter.limit("5/minute")
async def login(request: Request): ...
```

---

## Decision 2: Circuit Breaker Pattern

**Question**: Custom implementation vs external library?

**Decision**: Extend existing `app/services/circuit_breaker.py`

**Rationale**:
- Already implemented with states: CLOSED, OPEN, HALF_OPEN
- Already has failure counting and recovery timeout
- Already exposes states via `/api/system/circuit-breakers`
- Just needs to be applied to more services

**Alternatives Considered**:
- pybreaker library: Rejected (would require migration, existing solution works)
- resilience4py: Rejected (Java-inspired, less Pythonic)

**Implementation Notes**:
```python
# Existing decorator pattern
from app.services.circuit_breaker import circuit_breaker

@circuit_breaker("llama_index", failure_threshold=5, recovery_timeout=30)
async def call_llama_index(): ...
```

---

## Decision 3: Environment Validation

**Question**: How to validate environment variables at startup?

**Decision**: Create custom module `app/core/startup_validation.py`

**Rationale**:
- Simple validation logic doesn't need external library
- Need custom categorization (critical vs recommended)
- Need custom error messages
- Integration with structlog for logging

**Alternatives Considered**:
- pydantic-settings: Rejected (overkill, adds dependency)
- python-dotenv validation: Rejected (doesn't support categorization)

**Implementation Notes**:
```python
REQUIRED_ENV_VARS = {
    "critical": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", ...],
    "recommended": ["NEO4J_URI", "NEO4J_PASSWORD", ...]
}

def validate_environment() -> None:
    # Fail fast if critical vars missing
    # Log warning for recommended vars
```

---

## Decision 4: Timeout Implementation

**Question**: How to implement configurable timeouts for external services?

**Decision**: Use httpx.Timeout with per-service configuration

**Rationale**:
- httpx already used for all external HTTP calls
- Native timeout support with connect/read/write/pool options
- Integrates with async context managers
- Type-safe configuration

**Alternatives Considered**:
- asyncio.wait_for: Rejected (less readable, manual exception handling)
- aiohttp timeout: Rejected (would require library change)

**Implementation Notes**:
```python
import httpx

TIMEOUTS = {
    "llama_index": httpx.Timeout(60.0, connect=5.0),
    "crewai": httpx.Timeout(120.0, connect=5.0),
    "ollama": httpx.Timeout(30.0, connect=5.0),
}

async with httpx.AsyncClient(timeout=TIMEOUTS["llama_index"]) as client:
    response = await client.post(url, json=data)
```

---

## Decision 5: Error Response Format

**Question**: How to standardize error responses across all endpoints?

**Decision**: Extend `app/models/errors.py` with standard codes

**Rationale**:
- Pydantic models already used for validation errors
- Type-safe response structures
- Easy to serialize to JSON
- Can use FastAPI exception handlers

**Alternatives Considered**:
- Dict responses: Rejected (no type safety)
- dataclasses: Rejected (Pydantic already used everywhere)

**Implementation Notes**:
```python
class StandardError(BaseModel):
    code: str  # e.g., "VALIDATION_ERROR"
    message: str
    details: Optional[dict] = None
    request_id: str
    timestamp: datetime

class ErrorResponse(BaseModel):
    error: StandardError
```

---

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| How to handle empty env vars? | Treat empty string same as missing (FR-004) |
| Rate limit storage fallback? | Fall back to in-memory if Redis unavailable |
| Circuit breaker state persistence? | In-memory per instance, reset on restart |
| Timeout mid-response handling? | httpx raises ReadTimeout, caught and wrapped |

---

## References

- Empire existing code: `app/middleware/rate_limit.py`, `app/services/circuit_breaker.py`
- FastAPI exception handlers: https://fastapi.tiangolo.com/tutorial/handling-errors/
- httpx timeouts: https://www.python-httpx.org/advanced/#timeout-configuration
- slowapi documentation: https://github.com/laurents/slowapi
