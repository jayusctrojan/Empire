# Task ID: 167

**Title:** Implement Query Parameter Validation

**Status:** cancelled

**Dependencies:** 165 ✗

**Priority:** medium

**Description:** Add Pydantic models for all query parameters to ensure proper validation and sanitization of user input.

**Details:**

Implement Pydantic models for query parameter validation across all endpoints:

1. Create base validation models in `app/models/validators.py`:
```python
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = Field(default=None)

    @validator("query")
    def sanitize_query(cls, v):
        # Remove potential injection patterns
        dangerous_patterns = ["--", ";", "DROP", "DELETE", "INSERT"]
        for pattern in dangerous_patterns:
            if pattern.upper() in v.upper():
                raise ValueError(f"Query contains disallowed pattern: {pattern}")
        return v.strip()

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class DocumentQueryParams(PaginationParams):
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc")
    filter_tag: Optional[str] = None
    
    @validator("sort_by")
    def validate_sort_field(cls, v):
        allowed_fields = ["created_at", "updated_at", "title", "size"]
        if v not in allowed_fields:
            raise ValueError(f"Invalid sort field. Must be one of: {', '.join(allowed_fields)}")
        return v
        
    @validator("sort_order")
    def validate_sort_order(cls, v):
        if v.lower() not in ["asc", "desc"]:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v.lower()

class GraphQueryParams(BaseModel):
    entity_id: str = Field(..., min_length=1, max_length=100)
    depth: int = Field(default=2, ge=1, le=5)
    relationship_types: Optional[List[str]] = None
    
    @validator("entity_id")
    def validate_entity_id(cls, v):
        if not v.isalnum() and not "-" in v:
            raise ValueError("Entity ID must contain only alphanumeric characters and hyphens")
        return v

class SearchParams(BaseModel):
    term: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    
    @validator("term")
    def sanitize_term(cls, v):
        return v.strip()
```

2. Apply these validators in route handlers:
```python
from fastapi import Depends
from app.models.validators import QueryRequest, DocumentQueryParams

@router.post("/query")
async def query_endpoint(query_params: QueryRequest):
    # Use validated parameters
    result = await query_service.process_query(
        query=query_params.query,
        top_k=query_params.top_k,
        filters=query_params.filters
    )
    return result

@router.get("/documents")
async def list_documents(params: DocumentQueryParams = Depends()):
    # Use validated parameters
    documents = await document_service.list_documents(
        page=params.page,
        page_size=params.page_size,
        sort_by=params.sort_by,
        sort_order=params.sort_order,
        filter_tag=params.filter_tag
    )
    return documents
```

3. Update all API endpoints to use appropriate validators:
   - `/api/query/*` endpoints
   - `/api/documents/*` endpoints
   - `/api/graph/*` endpoints
   - `/api/search/*` endpoints

**Test Strategy:**

1. Create unit tests that verify:
   - Valid parameters are accepted
   - Invalid parameters are rejected with appropriate errors
   - Validators correctly sanitize and transform input
   - Default values are applied correctly

2. Create integration tests that:
   - Test each endpoint with valid and invalid parameters
   - Verify error responses for validation failures
   - Check that sanitized values are used correctly
   - Test edge cases for each parameter type

3. Create security tests that attempt to inject malicious patterns and verify they are caught by validators
