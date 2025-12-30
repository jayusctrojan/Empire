# Empire v7.3 - Feature Flag Configuration Guide

**Task**: 3.3 - Configure Feature Flags for All New Features
**Date**: 2025-01-24
**Status**: ✅ Complete

---

## Overview

This guide explains how to use feature flags in Empire v7.3 for controlling the rollout of new features. All 9 v7.3 feature flags are pre-configured in the database and ready to use.

---

## Feature Flag Inventory

### All 9 v7.3 Feature Flags

| Flag Name | Feature ID | Description | Migration | Default State |
|-----------|------------|-------------|-----------|---------------|
| `feature_department_research_development` | F1 | Research & Development department (12th dept) | 20251124_v73_add_research_development_department.sql | DISABLED |
| `feature_processing_status_details` | F2 | Detailed processing status tracking (JSONB) | 20251124_v73_add_processing_status_details.sql | DISABLED |
| `feature_source_metadata` | F3 | Source metadata and citation management | 20251124_v73_add_source_metadata.sql | DISABLED |
| `feature_agent_router_cache` | F4 | Intelligent agent routing cache | 20251124_v73_create_agent_router_cache.sql | DISABLED |
| `feature_agent_feedback` | F5 | Agent feedback collection system | 20251124_v73_create_agent_feedback.sql | DISABLED |
| `feature_course_management` | F6 | LMS course content addition | 20251124_v73_create_course_structure_tables.sql | DISABLED |
| `feature_enhanced_search` | F7 | Enhanced search with filters | N/A (code-only) | DISABLED |
| `feature_book_processing` | F8 | Book processing (PDF/EPUB/MOBI) | 20251124_v73_create_book_metadata_tables.sql | DISABLED |
| `feature_bulk_embeddings` | F9 | Bulk embedding generation | N/A (code-only) | DISABLED |

---

## Using Feature Flags in Code

### Pattern 1: Simple Enable/Disable Check

```python
from app.core.feature_flags import get_feature_flag_manager
from fastapi import HTTPException

async def some_endpoint():
    """Example endpoint with feature flag check"""
    ff = get_feature_flag_manager()

    # Simple check - is feature enabled globally?
    if not await ff.is_enabled("feature_course_management"):
        raise HTTPException(
            status_code=403,
            detail="Course management feature is not enabled"
        )

    # Feature is enabled - proceed with logic
    return {"message": "Course created successfully"}
```

### Pattern 2: User-Specific Check (Gradual Rollout)

```python
from app.core.feature_flags import get_feature_flag_manager

async def process_book(book_id: str, user_id: str):
    """Example with user-specific rollout"""
    ff = get_feature_flag_manager()

    # Check if enabled for this specific user
    if await ff.is_enabled("feature_book_processing", user_id=user_id):
        # Use new book processing engine
        return await process_book_v2(book_id)
    else:
        # Fall back to old processing
        return await process_book_v1(book_id)
```

### Pattern 3: FastAPI Dependency for Route Protection

```python
from fastapi import Depends, HTTPException
from app.core.feature_flags import get_feature_flag_manager

async def require_feature(flag_name: str):
    """Reusable dependency to check feature flags"""
    ff = get_feature_flag_manager()
    if not await ff.is_enabled(flag_name):
        raise HTTPException(
            status_code=403,
            detail=f"Feature not enabled: {flag_name}"
        )
    return True

# Use in routes
@app.post("/api/courses")
async def create_course(
    course_data: dict,
    _: bool = Depends(lambda: require_feature("feature_course_management"))
):
    """Only accessible if feature_course_management is enabled"""
    return create_course_logic(course_data)
```

### Pattern 4: Conditional Logic with Context

```python
from app.core.feature_flags import get_feature_flag_manager

async def search_documents(query: str, user_id: str):
    """Example showing conditional feature usage"""
    ff = get_feature_flag_manager()

    # Base search
    results = await basic_search(query)

    # Enhanced search if enabled
    if await ff.is_enabled("feature_enhanced_search", user_id=user_id):
        results = await apply_advanced_filters(results)
        results = await add_faceted_search(results)

    return results
```

---

## Integration Examples by Feature

### Feature 1: Research & Development Department

**Flag**: `feature_department_research_development`
**Files to integrate**: `app/api/upload.py`, department validation logic

```python
# In app/api/upload.py or department validator
from app.core.feature_flags import get_feature_flag_manager

VALID_DEPARTMENTS = [
    'it-engineering', 'sales-marketing', 'customer-support',
    'operations-hr-supply', 'finance-accounting', 'project-management',
    'real-estate', 'private-equity-ma', 'consulting',
    'personal-continuing-ed', 'health-wellness'
]

async def get_valid_departments():
    """Get list of valid departments based on feature flags"""
    departments = VALID_DEPARTMENTS.copy()

    ff = get_feature_flag_manager()
    if await ff.is_enabled("feature_department_research_development"):
        departments.append('research-development')

    return departments

async def validate_department(department: str):
    """Validate department with feature flag support"""
    valid_depts = await get_valid_departments()

    if department not in valid_depts:
        raise ValueError(
            f"Invalid department. Valid: {', '.join(valid_depts)}"
        )
```

---

### Feature 2: Processing Status Details

**Flag**: `feature_processing_status_details`
**Files to integrate**: `app/tasks/document_processing.py`, `app/services/document_processor.py`

```python
# In document processing tasks
from app.core.feature_flags import get_feature_flag_manager

async def update_processing_status(doc_id: str, status: str, details: dict = None):
    """Update document processing status with optional details"""
    ff = get_feature_flag_manager()

    # Base status update
    await supabase.table("documents_v2").update({
        "status": status
    }).eq("id", doc_id).execute()

    # Detailed status if feature enabled
    if await ff.is_enabled("feature_processing_status_details") and details:
        await supabase.table("documents_v2").update({
            "processing_status_details": details
        }).eq("id", doc_id).execute()
```

---

### Feature 3: Source Metadata

**Flag**: `feature_source_metadata`
**Files to integrate**: `app/services/document_processor.py`, `app/services/chunking_service.py`

```python
# In document processor
from app.core.feature_flags import get_feature_flag_manager

async def store_document_chunk(chunk_data: dict):
    """Store document chunk with optional source metadata"""
    ff = get_feature_flag_manager()

    chunk_record = {
        "content": chunk_data["content"],
        "embedding": chunk_data["embedding"],
        # ... other fields
    }

    # Add source metadata if feature enabled
    if await ff.is_enabled("feature_source_metadata"):
        chunk_record["source_metadata"] = {
            "page_number": chunk_data.get("page_number"),
            "section": chunk_data.get("section"),
            "confidence_score": chunk_data.get("confidence"),
            "extraction_method": "llama_parse"
        }

    return await supabase.table("document_chunks").insert(chunk_record).execute()
```

---

### Feature 4: Agent Router Cache

**Flag**: `feature_agent_router_cache`
**Files to integrate**: `app/workflows/workflow_router.py`

```python
# In workflow router
from app.core.feature_flags import get_feature_flag_manager

async def route_query(query: str, user_id: str):
    """Route query to appropriate workflow with optional caching"""
    ff = get_feature_flag_manager()

    # Check cache if feature enabled
    if await ff.is_enabled("feature_agent_router_cache"):
        cached_route = await check_router_cache(query, user_id)
        if cached_route:
            logger.info(f"Cache hit for query routing: {query[:50]}")
            return cached_route

    # Determine route via ML model
    route = await determine_route_ml(query)

    # Cache result if feature enabled
    if await ff.is_enabled("feature_agent_router_cache"):
        await cache_router_decision(query, user_id, route)

    return route
```

---

### Feature 5: Agent Feedback

**Flag**: `feature_agent_feedback`
**Files to integrate**: `app/api/routes/query.py`, response handling

```python
# In query response handler
from app.core.feature_flags import get_feature_flag_manager

async def send_query_response(query_id: str, response: dict):
    """Send query response with optional feedback collection"""
    ff = get_feature_flag_manager()

    # Include feedback UI if feature enabled
    if await ff.is_enabled("feature_agent_feedback"):
        response["feedback_enabled"] = True
        response["feedback_endpoint"] = f"/api/agent-feedback/{query_id}"

    return response
```

---

### Feature 6: Course Management

**Flag**: `feature_course_management`
**Files to integrate**: New course API routes (to be created)

```python
# In app/routes/courses.py (new file)
from fastapi import APIRouter, Depends, HTTPException
from app.core.feature_flags import get_feature_flag_manager

router = APIRouter(prefix="/api/courses", tags=["Courses"])

@router.post("")
async def create_course(course_data: dict):
    """Create new course (requires feature flag)"""
    ff = get_feature_flag_manager()

    if not await ff.is_enabled("feature_course_management"):
        raise HTTPException(
            status_code=403,
            detail="Course management feature is not available"
        )

    # Create course logic
    return {"message": "Course created", "id": "..."}
```

---

### Feature 7: Enhanced Search

**Flag**: `feature_enhanced_search`
**Files to integrate**: `app/services/hybrid_search_service.py`

```python
# In search service
from app.core.feature_flags import get_feature_flag_manager

async def search(query: str, user_id: str, filters: dict = None):
    """Search with optional enhanced features"""
    ff = get_feature_flag_manager()

    # Basic search
    results = await vector_search(query)

    # Enhanced features if enabled
    if await ff.is_enabled("feature_enhanced_search", user_id=user_id):
        if filters:
            results = await apply_filters(results, filters)
        results = await add_facets(results)
        results = await add_related_queries(results)

    return results
```

---

### Feature 8: Book Processing

**Flag**: `feature_book_processing`
**Files to integrate**: `app/tasks/document_processing.py`

```python
# In document processor
from app.core.feature_flags import get_feature_flag_manager

async def process_document(doc_id: str, file_type: str):
    """Process document with optional book processing"""
    ff = get_feature_flag_manager()

    # Check if this is a book format
    if file_type in ['pdf', 'epub', 'mobi']:
        if await ff.is_enabled("feature_book_processing"):
            # Use advanced book processor with chapter detection
            return await process_book_advanced(doc_id)

    # Standard document processing
    return await process_document_standard(doc_id)
```

---

### Feature 9: Bulk Embeddings

**Flag**: `feature_bulk_embeddings`
**Files to integrate**: `app/services/embedding_service.py`

```python
# In embedding service
from app.core.feature_flags import get_feature_flag_manager

async def generate_embeddings(texts: list[str]):
    """Generate embeddings with optional bulk processing"""
    ff = get_feature_flag_manager()

    # Bulk processing if enabled (more efficient)
    if await ff.is_enabled("feature_bulk_embeddings") and len(texts) > 10:
        return await generate_embeddings_bulk(texts)

    # Standard one-by-one processing
    return [await generate_embedding(text) for text in texts]
```

---

## Environment-Specific Configuration

### Development Environment

**Recommended approach**: Enable all flags for testing

```bash
# Using API to enable all flags in development
curl -X PUT http://localhost:8000/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "dev_setup"}'

# Or use SQL directly
UPDATE feature_flags SET enabled = TRUE WHERE flag_name LIKE 'feature_%';
```

### Staging Environment

**Recommended approach**: Enable flags gradually, test each feature

```sql
-- Enable specific features for staging testing
UPDATE feature_flags
SET enabled = TRUE, rollout_percentage = 100
WHERE flag_name IN (
    'feature_processing_status_details',
    'feature_source_metadata',
    'feature_agent_router_cache'
);
```

### Production Environment

**Recommended approach**: Gradual rollout with monitoring

```bash
# Step 1: Enable for 10% of users
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -d '{"enabled": true, "rollout_percentage": 10, "updated_by": "production_admin"}'

# Step 2: Monitor metrics for 24 hours

# Step 3: Increase to 50%
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -d '{"enabled": true, "rollout_percentage": 50, "updated_by": "production_admin"}'

# Step 4: Monitor metrics for 24 hours

# Step 5: Full rollout
curl -X PUT https://jb-empire-api.onrender.com/api/feature-flags/feature_course_management \
  -d '{"enabled": true, "rollout_percentage": 100, "updated_by": "production_admin"}'
```

---

## Rollout Strategy Recommendations

### Low-Risk Features (Database Schema Additions)
**Flags**: F1, F2, F3, F4, F5, F6, F8
**Strategy**: Direct 100% rollout after migration

```sql
-- Safe to enable immediately after migration
UPDATE feature_flags
SET enabled = TRUE, rollout_percentage = 100
WHERE flag_name IN (
    'feature_department_research_development',
    'feature_processing_status_details',
    'feature_source_metadata',
    'feature_agent_router_cache',
    'feature_agent_feedback',
    'feature_book_processing'
);
```

### Medium-Risk Features (New User-Facing Functionality)
**Flags**: F6 (Course Management), F7 (Enhanced Search)
**Strategy**: Gradual rollout 10% → 50% → 100%

```bash
# Week 1: 10% rollout
curl -X PUT /api/feature-flags/feature_course_management \
  -d '{"enabled": true, "rollout_percentage": 10}'

# Week 2: If metrics look good, 50% rollout
curl -X PUT /api/feature-flags/feature_course_management \
  -d '{"enabled": true, "rollout_percentage": 50}'

# Week 3: Full rollout
curl -X PUT /api/feature-flags/feature_course_management \
  -d '{"enabled": true, "rollout_percentage": 100}'
```

### Performance-Impacting Features
**Flags**: F9 (Bulk Embeddings)
**Strategy**: Test in dev/staging, then gradual production rollout

```bash
# Start with beta users only
curl -X PUT /api/feature-flags/feature_bulk_embeddings \
  -d '{
    "enabled": true,
    "rollout_percentage": 5,
    "user_segments": ["beta_tester_1", "beta_tester_2"]
  }'

# Monitor performance metrics
# If good: gradual rollout to all users
```

---

## Feature Dependencies

Some features depend on others being enabled:

```
feature_enhanced_search (F7)
  └─ Depends on: feature_source_metadata (F3)

feature_bulk_embeddings (F9)
  └─ Depends on: feature_processing_status_details (F2)
```

**Enforcement in code**:

```python
async def validate_feature_dependencies():
    """Ensure feature dependencies are satisfied"""
    ff = get_feature_flag_manager()

    # Enhanced search requires source metadata
    if await ff.is_enabled("feature_enhanced_search"):
        if not await ff.is_enabled("feature_source_metadata"):
            logger.warning(
                "feature_enhanced_search enabled but feature_source_metadata is disabled. "
                "Some functionality may not work correctly."
            )
```

---

## Monitoring and Observability

### Track Flag Usage

```python
from prometheus_client import Counter

feature_flag_checks = Counter(
    'feature_flag_checks_total',
    'Total feature flag checks',
    ['flag_name', 'enabled']
)

async def is_enabled_with_metrics(flag_name: str, user_id: str = None):
    """Check flag with Prometheus metrics"""
    ff = get_feature_flag_manager()
    enabled = await ff.is_enabled(flag_name, user_id=user_id)

    feature_flag_checks.labels(
        flag_name=flag_name,
        enabled=str(enabled)
    ).inc()

    return enabled
```

### Grafana Dashboard Queries

```promql
# Flag check rate
rate(feature_flag_checks_total[5m])

# Flag enable rate by flag
sum by (flag_name) (feature_flag_checks_total{enabled="True"})
/
sum by (flag_name) (feature_flag_checks_total)

# Cache hit rate for flags
rate(redis_cache_hits_total{key_type="feature_flag"}[5m])
```

---

## Testing Feature Flags

### Unit Tests

```python
import pytest
from app.core.feature_flags import get_feature_flag_manager, reset_feature_flag_manager

@pytest.fixture(autouse=True)
def reset_flags():
    """Reset feature flag manager between tests"""
    yield
    reset_feature_flag_manager()

async def test_course_creation_with_flag_disabled():
    """Test that course creation fails when flag is disabled"""
    ff = get_feature_flag_manager()

    # Ensure flag is disabled
    await ff.update_flag("feature_course_management", enabled=False)

    # Attempt course creation
    with pytest.raises(HTTPException) as exc:
        await create_course({"title": "Test Course"})

    assert exc.value.status_code == 403
    assert "not enabled" in exc.value.detail

async def test_course_creation_with_flag_enabled():
    """Test that course creation succeeds when flag is enabled"""
    ff = get_feature_flag_manager()

    # Enable flag
    await ff.update_flag("feature_course_management", enabled=True)

    # Course creation should succeed
    result = await create_course({"title": "Test Course"})
    assert result["status"] == "success"
```

### Integration Tests

```python
async def test_gradual_rollout():
    """Test that rollout percentage works correctly"""
    ff = get_feature_flag_manager()

    # Set 50% rollout
    await ff.update_flag("feature_book_processing", enabled=True, rollout_percentage=50)

    # Test with 100 different user IDs
    enabled_count = 0
    for i in range(100):
        user_id = f"test_user_{i}"
        if await ff.is_enabled("feature_book_processing", user_id=user_id):
            enabled_count += 1

    # Should be approximately 50% (allow 10% variance)
    assert 40 <= enabled_count <= 60, f"Expected ~50, got {enabled_count}"
```

---

## Troubleshooting

### Flag not taking effect

**Check cache**:
```bash
# Clear Redis cache for flag
redis-cli DEL "feature_flag:feature_course_management*"
```

**Verify database**:
```sql
SELECT * FROM feature_flags WHERE flag_name = 'feature_course_management';
```

### Unexpected rollout behavior

**Check user hash**:
```python
# Test user hash calculation
import hashlib
user_id = "test_user_123"
user_hash = abs(hash(user_id)) % 100
print(f"User {user_id} hash: {user_hash}")
# If hash = 45 and rollout_percentage = 50, user should see the feature
```

---

## Quick Reference

### Enable all flags (development)
```sql
UPDATE feature_flags SET enabled = TRUE, rollout_percentage = 100;
```

### Disable all flags (emergency)
```sql
UPDATE feature_flags SET enabled = FALSE;
```

### Check flag status
```bash
curl http://localhost:8000/api/feature-flags
```

### Enable single flag
```bash
curl -X PUT http://localhost:8000/api/feature-flags/feature_course_management \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "rollout_percentage": 100}'
```

### View audit trail
```bash
curl http://localhost:8000/api/feature-flags/feature_course_management/audit
```

---

## Summary

✅ All 9 v7.3 feature flags are configured and ready to use
✅ Integration patterns documented for each feature
✅ Environment-specific rollout strategies defined
✅ Testing and monitoring guidelines provided
✅ No code changes or redeployment required to toggle flags

**Next Steps**: Implement flag checking in the actual feature code (Tasks 3.4-3.6)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-24
**Task**: 3.3 - Configure Feature Flags for All New Features
