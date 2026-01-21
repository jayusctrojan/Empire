# Task ID: 124

**Title:** Implement Content Prep API Routes

**Status:** done

**Dependencies:** 122 ✓, 123 ✓

**Priority:** high

**Description:** Create the API routes for the Content Prep Agent as specified in the PRD, including endpoints for analyzing files, validating content sets, and generating processing manifests.

**Details:**

Create the file `app/routes/content_prep.py` with FastAPI routes for the Content Prep Agent. Implement all the endpoints specified in the PRD:

1. POST /api/content-prep/analyze - Analyze pending files, detect sets
2. POST /api/content-prep/validate - Validate completeness of content set
3. POST /api/content-prep/order - Generate processing order
4. GET /api/content-prep/sets - List detected content sets
5. GET /api/content-prep/sets/{set_id} - Get content set details
6. POST /api/content-prep/manifest - Generate processing manifest
7. GET /api/content-prep/health - Service health check

Pseudo-code:
```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
from app.models.content_sets import ContentSet, ContentSetCreate, ProcessingManifest
from app.services.content_prep_agent import ContentPrepAgent
from app.db.supabase import get_supabase_client

router = APIRouter(prefix="/api/content-prep", tags=["content-prep"])
content_prep_agent = ContentPrepAgent()

@router.post("/analyze", response_model=dict)
async def analyze_pending_files(data: dict):
    """Analyze pending files and detect content sets"""
    b2_folder = data.get("b2_folder", "pending/")
    detection_mode = data.get("detection_mode", "auto")
    
    # Get files from B2
    # Detect content sets
    # Return results
    
    return {
        "content_sets": [],  # List of detected sets
        "standalone_files": []  # List of files not in sets
    }

@router.post("/validate", response_model=dict)
async def validate_content_set(data: dict):
    """Validate completeness of a content set"""
    content_set_id = data.get("content_set_id")
    
    # Get content set
    # Validate completeness
    # Return validation results
    
    return {
        "is_complete": True,
        "missing_files": [],
        "warnings": []
    }

@router.post("/order", response_model=dict)
async def generate_processing_order(data: dict):
    """Generate processing order for a content set"""
    content_set_id = data.get("content_set_id")
    
    # Get content set
    # Generate order
    # Return ordered files
    
    return {
        "ordered_files": []
    }

@router.get("/sets", response_model=List[ContentSet])
async def list_content_sets(status: Optional[str] = None):
    """List detected content sets"""
    # Query database for content sets
    # Filter by status if provided
    # Return list
    
    return []

@router.get("/sets/{set_id}", response_model=ContentSet)
async def get_content_set(set_id: str):
    """Get content set details"""
    # Query database for content set
    # Return details or 404
    
    return {}

@router.post("/manifest", response_model=ProcessingManifest)
async def generate_processing_manifest(data: dict):
    """Generate processing manifest for a content set"""
    content_set_id = data.get("content_set_id")
    proceed_incomplete = data.get("proceed_incomplete", False)
    add_context = data.get("add_context", True)
    
    # Get content set
    # Generate manifest
    # Return manifest
    
    return {}

@router.get("/health")
async def health_check():
    """Service health check"""
    return {"status": "healthy"}
```

Also update the main FastAPI app to include these routes:

```python
# In app/main.py
from app.routes import content_prep

app.include_router(content_prep.router)
```

**Test Strategy:**

1. Unit tests for each API endpoint
2. Test with valid and invalid request data
3. Test error handling and edge cases
4. Integration tests with mocked B2 service
5. Test response formats match API specifications
6. Load testing with multiple concurrent requests
