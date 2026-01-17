# Quickstart: Production Excellence - 100/100 Readiness

**Date**: 2026-01-17
**Feature Branch**: `010-production-excellence`

## Overview

This quickstart guide provides test scenarios for validating the production excellence features. Each scenario maps to a user story from the specification.

## Prerequisites

```bash
# Ensure virtual environment is active
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-cov pytest-asyncio httpx

# Set up test environment
export TESTING=true
export SUPABASE_URL="your-test-supabase-url"
export NEO4J_URI="bolt://localhost:7687"
export REDIS_URL="redis://localhost:6379/0"
```

## Test Scenarios

### US1: Complete Service Integration

**Scenario 1.1: Document Upload to B2**
```bash
# Test document upload flow
pytest tests/integration/test_b2_integration.py::test_document_upload -v

# Expected: Document stored in B2 with proper folder structure
# Verify: B2 path follows documents/{user_id}/{document_id}/ pattern
```

**Scenario 1.2: Document Deletion**
```bash
# Test document deletion flow
pytest tests/integration/test_b2_integration.py::test_document_deletion -v

# Expected: Document removed from B2 and Supabase
# Verify: No orphaned files in B2, no database records remain
```

**Scenario 1.3: Document Reprocessing**
```bash
# Test reprocessing with force_reparse
pytest tests/integration/test_document_processing.py::test_reprocess_force_reparse -v

# Expected: Text re-extracted, embeddings regenerated
# Verify: New embeddings differ from original
```

### US2: Reliable Task Processing

**Scenario 2.1: Project Initialization Task**
```bash
# Test project creation triggers Celery task
pytest tests/integration/test_celery_integration.py::test_project_init_task -v

# Expected: Background task triggered for project setup
# Verify: Celery task ID stored in project record
```

**Scenario 2.2: Project Cancellation Task Revocation**
```bash
# Test project cancellation revokes pending tasks
pytest tests/integration/test_celery_integration.py::test_project_cancel_revokes -v

# Expected: Pending tasks revoked, status updated
# Verify: Task state shows REVOKED
```

**Scenario 2.3: Dead Letter Queue Recording**
```bash
# Test failed task goes to DLQ
pytest tests/integration/test_dlq.py::test_failed_task_dlq -v

# Expected: Failed task recorded in DLQ with exception
# Verify: DLQ entry contains task_id, exception, retries
```

### US3: System Observability

**Scenario 3.1: Trace ID Generation**
```bash
# Test trace ID in request/response
curl -v http://localhost:8000/api/documents \
  -H "Authorization: Bearer $TOKEN"

# Expected: X-Trace-ID header in response
# Verify: Trace ID appears in logs
```

**Scenario 3.2: Health Check Endpoints**
```bash
# Test liveness probe
curl http://localhost:8000/health/live
# Expected: {"status": "ok"}

# Test readiness probe
curl http://localhost:8000/health/ready
# Expected: {"status": "ok", "dependencies": {...}}

# Test deep health check
curl http://localhost:8000/health/deep
# Expected: Detailed status for each component
```

**Scenario 3.3: Dependency Health Reporting**
```bash
# Test with unhealthy dependency (stop Neo4j)
docker stop empire-neo4j
curl http://localhost:8000/health/ready
# Expected: {"status": "unhealthy", "dependencies": {"neo4j": {"status": "unhealthy", ...}}}

# Restart Neo4j
docker start empire-neo4j
```

### US4: Secure Authentication

**Scenario 4.1: WebSocket Authentication**
```python
# Test WebSocket with valid token
import websockets
async with websockets.connect(
    f"ws://localhost:8000/ws/projects/{project_id}?token={valid_jwt}"
) as ws:
    # Expected: Connection accepted
    data = await ws.recv()
```

```python
# Test WebSocket without token
async with websockets.connect(
    f"ws://localhost:8000/ws/projects/{project_id}"
) as ws:
    # Expected: Connection closed with code 4001
```

**Scenario 4.2: Admin Authorization**
```bash
# Test non-admin approval listing
curl http://localhost:8000/api/documents/pending-approvals \
  -H "Authorization: Bearer $NON_ADMIN_TOKEN"
# Expected: Only own pending approvals

# Test admin approval listing
curl http://localhost:8000/api/documents/pending-approvals \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Expected: All pending approvals
```

### US5: Test Coverage

**Scenario 5.1: Coverage Report**
```bash
# Run full test suite with coverage
pytest --cov=app --cov-report=html tests/

# Expected: Coverage report generated in htmlcov/
# Verify: Overall coverage >= 80%
```

**Scenario 5.2: Critical Path Coverage**
```bash
# Check auth module coverage
pytest --cov=app/auth --cov-fail-under=100 tests/

# Expected: 100% coverage on auth paths
```

### US6: Database Migrations

**Scenario 6.1: Apply Migration**
```bash
# Apply all pending migrations
alembic upgrade head

# Expected: Schema updated to latest version
# Verify: Tables created (dead_letter_queue, agent_feedback)
```

**Scenario 6.2: Migration Rollback**
```bash
# Rollback last migration
alembic downgrade -1

# Expected: Previous schema state restored
# Verify: Last migration tables removed
```

## Running All Tests

```bash
# Full test suite
pytest tests/ -v --cov=app --cov-report=term-missing

# Integration tests only
pytest tests/integration/ -v

# Unit tests only
pytest tests/unit/ -v

# Production readiness tests
pytest tests/test_production_readiness.py -v
```

## Validation Checklist

- [ ] All 26 production readiness tests pass
- [ ] Coverage report shows >= 80% overall
- [ ] Health endpoints return correct status
- [ ] Trace IDs present in logs
- [ ] DLQ captures failed tasks
- [ ] WebSocket authentication enforced
- [ ] Migrations apply and rollback cleanly
