# Task ID: 107

**Title:** Implement Graph Agent Router

**Status:** pending

**Dependencies:** 103, 104, 105, 106

**Priority:** high

**Description:** Create the Graph Agent Router that extends existing /api/graph routes with new capabilities for Customer 360, Document Structure, and Graph-Enhanced RAG.

**Details:**

Implement the Graph Agent Router in app/routes/graph_agent.py to handle the new graph agent endpoints:

1. Customer 360 endpoints:
   - POST /api/graph/customer360/query
   - GET /api/graph/customer360/{customer_id}
   - GET /api/graph/customer360/similar/{customer_id}

2. Document Structure endpoints:
   - POST /api/graph/document-structure/extract
   - GET /api/graph/document-structure/{doc_id}
   - POST /api/graph/document-structure/query
   - GET /api/graph/document-structure/{doc_id}/cross-refs
   - POST /api/graph/document-structure/smart-retrieve

3. Graph-Enhanced RAG endpoints:
   - POST /api/graph/enhanced-rag/query
   - POST /api/graph/enhanced-rag/expand
   - GET /api/graph/enhanced-rag/entities/{entity_id}/related
   - POST /api/graph/enhanced-rag/context

Implement the router using FastAPI with dependency injection for services:

```python
from fastapi import APIRouter, Depends, HTTPException
from app.services.customer360_service import Customer360Service
from app.services.document_structure_service import DocumentStructureService
from app.services.graph_enhanced_rag_service import GraphEnhancedRAGService
from app.models.graph_agent import *

router = APIRouter(prefix="/api/graph", tags=["graph-agent"])

# Customer 360 endpoints
@router.post("/customer360/query", response_model=Customer360Response)
async def query_customer(request: Customer360Request, 
                       service: Customer360Service = Depends()):
    return await service.process_customer_query(request)

@router.get("/customer360/{customer_id}", response_model=Customer360Response)
async def get_customer(customer_id: str, include_documents: bool = True,
                     include_tickets: bool = True, include_orders: bool = True,
                     include_interactions: bool = True,
                     service: Customer360Service = Depends()):
    return await service.get_customer_by_id(
        customer_id, include_documents, include_tickets, 
        include_orders, include_interactions
    )

# Document Structure endpoints
# ...

# Graph-Enhanced RAG endpoints
# ...
```

Integrate the router with the main FastAPI application and ensure proper error handling and validation.

**Test Strategy:**

1. Unit tests for each endpoint with mocked service responses
2. Integration tests with actual services
3. Test request validation with valid and invalid inputs
4. Test error handling with various error conditions
5. Test authentication and authorization if applicable
6. Load testing for concurrent requests
