# Research: Production Excellence - 100/100 Readiness

**Date**: 2026-01-17
**Feature Branch**: `010-production-excellence`

## Technology Decisions

### 1. Distributed Tracing Framework

**Decision**: OpenTelemetry Python SDK

**Rationale**:
- Vendor-neutral standard with wide ecosystem support
- Native FastAPI instrumentation available (opentelemetry-instrumentation-fastapi)
- Celery instrumentation available for background task tracing
- Can export to multiple backends (Jaeger, Zipkin, OTLP, console)
- Minimal code changes required with auto-instrumentation

**Alternatives Considered**:
- Jaeger client directly: Vendor lock-in, no Celery support
- DataDog APM: Expensive, proprietary
- AWS X-Ray: AWS-specific, limited Python support

**Implementation Pattern**:
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
```

### 2. Database Migration Framework

**Decision**: Alembic

**Rationale**:
- Official SQLAlchemy migration tool
- Version control for schema changes
- Rollback capability with downgrade migrations
- Integration with existing Supabase PostgreSQL
- Well-documented, mature project

**Alternatives Considered**:
- Manual SQL scripts: No version tracking, no rollback
- Flyway: Java-based, less Python integration
- Django migrations: Requires Django, not compatible with FastAPI

**Implementation Pattern**:
```
migrations/
├── alembic.ini
├── env.py
└── versions/
    ├── 001_initial.py
    └── 002_agent_feedback.py
```

### 3. Health Check Pattern

**Decision**: Custom health check endpoints with dependency probes

**Rationale**:
- FastAPI doesn't have built-in health check conventions
- Need to check multiple dependencies (Supabase, Neo4j, Redis, B2)
- Kubernetes/Render need distinct liveness and readiness probes
- Timeout handling critical for production reliability

**Alternatives Considered**:
- fastapi-health: Limited dependency checking
- health-check: Minimal async support

**Implementation Pattern**:
- `/health/live` - Returns 200 if process running (liveness)
- `/health/ready` - Checks all dependencies (readiness)
- `/health/deep` - Detailed status of each component

### 4. Test Framework Configuration

**Decision**: pytest + pytest-cov + pytest-asyncio + httpx

**Rationale**:
- pytest is standard Python testing framework
- pytest-cov provides coverage reporting
- pytest-asyncio handles async FastAPI tests
- httpx provides async test client for FastAPI

**Coverage Targets**:
- Overall: 80%
- Critical paths (auth, security): 100%
- Services: 80%
- API routes: 80%

### 5. WebSocket Authentication

**Decision**: JWT validation on WebSocket connection

**Rationale**:
- Consistent with existing REST API authentication
- JWT can be passed in connection query parameters
- Token validation before accepting connection
- Supabase JWT tokens already in use

**Implementation Pattern**:
```python
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = await validate_jwt(token)
    if not user:
        await websocket.close(code=4001)
        return
    await websocket.accept()
```

## Best Practices Research

### OpenTelemetry for Python

1. **Context Propagation**: Use `TraceContextTextMapPropagator` for W3C trace context
2. **Sampling**: Use `ParentBasedTraceIdRatio` sampler to reduce overhead
3. **Resource Attributes**: Include service.name, service.version, deployment.environment
4. **Span Naming**: Use `{method} {route}` pattern for HTTP spans
5. **Error Recording**: Use `span.record_exception()` for error traces

### Celery Task Tracing

1. **Context Injection**: Inject trace context into task headers
2. **Task Spans**: Create new spans for task execution
3. **Parent Linking**: Link task spans to request spans
4. **Signal Handlers**: Use Celery signals for instrumentation

### Alembic Best Practices

1. **Naming Convention**: Use sequential numbering with descriptive names
2. **Atomic Migrations**: Each migration should be atomic and reversible
3. **Online Migrations**: Support online schema changes for zero-downtime
4. **Data Migrations**: Separate schema and data migrations

## Resolved Clarifications

All technical decisions have been made. No NEEDS CLARIFICATION items remain.

## References

- OpenTelemetry Python SDK: https://opentelemetry.io/docs/instrumentation/python/
- Alembic Tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- FastAPI Testing: https://fastapi.tiangolo.com/advanced/testing/
- WebSocket Security: https://fastapi.tiangolo.com/advanced/websockets/
