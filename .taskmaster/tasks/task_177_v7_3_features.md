# Task ID: 177

**Title:** Implement Query Parameter Validation

**Status:** done

**Dependencies:** 175 ✓

**Priority:** medium

**Description:** Add Pydantic models for all query parameters to ensure proper validation and sanitization of user input.

**Details:**

1. Create Pydantic models for query parameters in appropriate modules:

```python
# app/models/query.py
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

# app/models/document.py
class DocumentListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
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

# app/models/graph.py
class GraphQueryParams(BaseModel):
    entity_id: str = Field(..., min_length=1, max_length=100)
    traversal_depth: int = Field(default=2, ge=1, le=5)
    relationship_types: Optional[List[str]] = None
    limit: int = Field(default=50, ge=1, le=200)

# app/models/search.py
class SearchParams(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    content_type: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

    @validator("query")
    def sanitize_search_query(cls, v):
        return v.strip()

    @validator("content_type")
    def validate_content_type(cls, v):
        if v is not None:
            allowed_types = ["document", "image", "audio", "video"]
            for t in v:
                if t not in allowed_types:
                    raise ValueError(f"Invalid content type: {t}")
        return v
```

2. Update route handlers to use these models for parameter validation:

```python
# Example for query endpoint
@router.post("/api/query")
async def query_documents(query_params: QueryRequest):
    # Access validated parameters
    query = query_params.query
    top_k = query_params.top_k
    filters = query_params.filters or {}
    
    # Process query...
    
# Example for document listing
@router.get("/api/documents")
async def list_documents(params: DocumentListParams = Depends()):
    # Access validated parameters
    page = params.page
    page_size = params.page_size
    sort_by = params.sort_by
    sort_order = params.sort_order
    
    # Process request...
```

**Test Strategy:**

1. Create unit tests that verify:
   - Valid parameters are accepted
   - Invalid parameters are rejected with appropriate error messages
   - Validators correctly sanitize and transform input

2. Create integration tests that:
   - Test endpoints with various parameter combinations
   - Verify error responses for invalid parameters
   - Check that sanitization is working correctly

3. Test edge cases like minimum/maximum values and special characters
