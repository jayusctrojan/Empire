# Empire v7.3 API Reference

**Version**: 7.3
**Base URL (Production)**: https://jb-empire-api.onrender.com
**Base URL (Local)**: http://localhost:8000
**Documentation**: /docs (Interactive Swagger UI)

---

## Table of Contents

1. [Overview & Authentication](#overview--authentication)
2. [Query Endpoints](#query-endpoints)
3. [Document Endpoints](#document-endpoints)
4. [CrewAI Endpoints](#crewai-endpoints)
5. [CrewAI Assets](#crewai-assets)
6. [Monitoring Endpoints](#monitoring-endpoints)
7. [RBAC Endpoints](#rbac-endpoints)
8. [User Endpoints](#user-endpoints)
9. [Session Endpoints](#session-endpoints)
10. [Audit Endpoints](#audit-endpoints)
11. [Preference Endpoints](#preference-endpoints)
12. [Cost Endpoints](#cost-endpoints)
13. [Agent Interaction Endpoints](#agent-interaction-endpoints)
14. [Error Codes Reference](#error-codes-reference)

---

## Overview & Authentication

### Base Information

**Production URL**: `https://jb-empire-api.onrender.com`
**Local Development**: `http://localhost:8000`
**Interactive Docs**: `/docs` (Swagger UI)
**OpenAPI Schema**: `/openapi.json`

### Authentication

Empire v7.3 uses **Clerk** for JWT-based authentication. All API endpoints require a valid JWT token in the `Authorization` header.

#### Getting an Access Token

1. **Via Clerk SDK** (Recommended for production):
```javascript
import Clerk from '@clerk/clerk-js';

const clerk = new Clerk('<your-publishable-key>');
await clerk.load();

if (clerk.user) {
  const token = await clerk.session.getToken();
  // Use token in Authorization header
}
```

2. **Via Chat UI** (Development/Testing):
- Login to https://jb-empire-chat.onrender.com
- Token is automatically included in requests

#### Making Authenticated Requests

**HTTP Header Format**:
```
Authorization: Bearer <jwt-token>
```

**Example with curl**:
```bash
curl https://jb-empire-api.onrender.com/api/query/adaptive \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{"query": "What are California insurance requirements?"}'
```

**Example with Python**:
```python
import requests

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Content-Type": "application/json"
}

response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/adaptive",
    headers=headers,
    json={"query": "What are California insurance requirements?"}
)
```

#### Authentication Errors

| Status Code | Error | Description |
|-------------|-------|-------------|
| 401 | Unauthorized | Missing or invalid JWT token |
| 403 | Forbidden | Valid token but insufficient permissions |

---

## Query Endpoints

**Base Path**: `/api/query`
**Authentication**: Required (Clerk JWT)
**Rate Limit**: 100 requests/minute per IP

### Overview

Query endpoints leverage **LangGraph** for adaptive workflows and **Arcade.dev** for external tool integration. All endpoints support semantic caching for improved performance (Task 43.3).

### 1. GET /api/query/tools

**Description**: List all available internal and external tools.

**Authentication**: Required

**Response**:
```json
{
  "tools": {
    "internal": [
      {
        "name": "vector_search",
        "description": "Search documents using semantic similarity",
        "category": "retrieval"
      },
      {
        "name": "graph_traversal",
        "description": "Explore entity relationships in knowledge graph",
        "category": "retrieval"
      }
    ],
    "external": [
      {
        "name": "Google.Search",
        "description": "Search the web using Google",
        "provider": "arcade.dev",
        "enabled": true
      },
      {
        "name": "Slack.SendMessage",
        "description": "Send messages to Slack channels",
        "provider": "arcade.dev",
        "enabled": false
      }
    ]
  },
  "total_count": 52
}
```

**Example**:
```bash
curl https://jb-empire-api.onrender.com/api/query/tools \
  -H "Authorization: Bearer <token>"
```

---

### 2. POST /api/query/adaptive

**Description**: Execute adaptive query using LangGraph 5-node workflow with iterative refinement and external tool support.

**Authentication**: Required
**Cache TTL**: 30 minutes (Task 43.3)
**Average Response Time**: ~11 seconds (uncached), ~360ms (cached)

**Request Body**:
```json
{
  "query": "What are California insurance requirements?",
  "max_iterations": 3,
  "enable_tools": true,
  "user_context": {
    "location": "California",
    "industry": "automotive"
  }
}
```

**Request Schema**:
- `query` (string, required): User query text
- `max_iterations` (integer, optional): Maximum refinement iterations (default: 3, max: 5)
- `enable_tools` (boolean, optional): Enable external tools via Arcade.dev (default: true)
- `user_context` (object, optional): Additional context for query processing

**Response**:
```json
{
  "answer": "California requires minimum liability insurance coverage...",
  "sources": [
    {
      "document_id": "doc_123",
      "title": "California Insurance Requirements 2025",
      "relevance_score": 0.95,
      "chunk": "California drivers must maintain..."
    }
  ],
  "iterations": 2,
  "workflow_path": ["retrieve", "refine", "verify"],
  "tools_used": ["vector_search", "Google.Search"],
  "from_cache": false,
  "cache_namespace": "adaptive",
  "processing_time_ms": 11223,
  "model_used": "claude-3-5-haiku-20241022"
}
```

**Response Schema**:
- `answer` (string): Final synthesized answer
- `sources` (array): Retrieved document sources with relevance scores
- `iterations` (integer): Number of refinement iterations performed
- `workflow_path` (array): Sequence of workflow nodes executed
- `tools_used` (array): List of tools invoked during processing
- `from_cache` (boolean): Whether result was served from cache
- `cache_namespace` (string): Cache namespace used
- `processing_time_ms` (integer): Total processing time in milliseconds
- `model_used` (string): LLM model used for generation

**Example**:
```python
import requests

response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/adaptive",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "What are California insurance requirements?",
        "max_iterations": 3,
        "enable_tools": True
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])}")
print(f"Cached: {result['from_cache']}")
```

**Error Responses**:
- `400`: Invalid request (missing query, invalid max_iterations)
- `401`: Unauthorized (missing/invalid token)
- `429`: Rate limit exceeded
- `500`: Internal server error

---

### 3. POST /api/query/auto

**Description**: Auto-routed query that intelligently selects the best workflow (LangGraph/CrewAI/Simple RAG) based on query complexity.

**Authentication**: Required
**Cache TTL**: 30 minutes
**Average Response Time**: ~5.6 seconds (uncached), ~360ms (cached)

**Request Body**:
```json
{
  "query": "Compare our policies with California regulations",
  "max_iterations": 3,
  "enable_tools": true
}
```

**Response**:
```json
{
  "answer": "Your policies align with California requirements in the following ways...",
  "sources": [...],
  "workflow_type": "langgraph",
  "routing_reason": "Complex query requiring external data and iterative refinement",
  "processing_time_ms": 5581,
  "from_cache": false
}
```

**Response Schema**:
- All fields from `/adaptive` endpoint, plus:
- `workflow_type` (string): Selected workflow ("langgraph", "crewai", "simple")
- `routing_reason` (string): Explanation for workflow selection

**Workflow Selection Logic**:
- **LangGraph**: Complex queries needing refinement, external data, iterative research
- **CrewAI**: Multi-agent document processing, complex analysis workflows
- **Simple RAG**: Direct knowledge base lookups, straightforward queries

**Example**:
```bash
curl https://jb-empire-api.onrender.com/api/query/auto \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest industry trends?",
    "enable_tools": true
  }'
```

---

### 4. POST /api/query/adaptive/async

**Description**: Submit adaptive query for asynchronous processing via Celery. Returns immediately with task ID for polling.

**Authentication**: Required

**Request Body**: Same as `/api/query/adaptive`

**Response** (202 Accepted):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Query submitted for async processing",
  "status_url": "/api/query/status/550e8400-e29b-41d4-a716-446655440000"
}
```

**Example**:
```python
# Submit async query
response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/adaptive/async",
    headers={"Authorization": f"Bearer {token}"},
    json={"query": "Complex research task", "max_iterations": 5}
)

task_id = response.json()["task_id"]

# Poll for results (see /api/query/status below)
```

---

### 5. POST /api/query/auto/async

**Description**: Submit auto-routed query for asynchronous processing.

**Authentication**: Required

**Request Body**: Same as `/api/query/auto`

**Response**: Same as `/api/query/adaptive/async`

---

### 6. POST /api/query/batch

**Description**: Process multiple queries in parallel with intelligent batching.

**Authentication**: Required
**Max Batch Size**: 10 queries

**Request Body**:
```json
{
  "queries": [
    {
      "id": "q1",
      "query": "What are California insurance requirements?",
      "max_iterations": 3
    },
    {
      "id": "q2",
      "query": "Explain our privacy policy",
      "max_iterations": 2
    }
  ],
  "enable_tools": true
}
```

**Response**:
```json
{
  "results": [
    {
      "id": "q1",
      "status": "success",
      "answer": "California requires...",
      "processing_time_ms": 8234
    },
    {
      "id": "q2",
      "status": "success",
      "answer": "Our privacy policy states...",
      "processing_time_ms": 5421
    }
  ],
  "total_processing_time_ms": 8421,
  "cache_hits": 0,
  "cache_misses": 2
}
```

**Example**:
```python
batch_queries = {
    "queries": [
        {"id": "q1", "query": "What is our refund policy?"},
        {"id": "q2", "query": "What are California insurance requirements?"}
    ]
}

response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/batch",
    headers={"Authorization": f"Bearer {token}"},
    json=batch_queries
)
```

---

### 7. GET /api/query/status/{task_id}

**Description**: Check status of asynchronous query task.

**Authentication**: Required

**Path Parameters**:
- `task_id` (string, required): Task ID from async query submission

**Response (Pending)**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "progress": 0,
  "message": "Task queued for processing"
}
```

**Response (In Progress)**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "progress": 50,
  "message": "Iteration 2/3 complete",
  "current_step": "refine"
}
```

**Response (Completed)**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "progress": 100,
  "result": {
    "answer": "...",
    "sources": [...],
    "iterations": 3
  }
}
```

**Response (Failed)**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "FAILURE",
  "progress": 75,
  "error": "External tool timeout",
  "message": "Task failed during external tool invocation"
}
```

**Example**:
```python
import time

# Poll until complete
while True:
    status_response = requests.get(
        f"https://jb-empire-api.onrender.com/api/query/status/{task_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    status_data = status_response.json()

    if status_data["status"] in ["SUCCESS", "FAILURE"]:
        break

    print(f"Progress: {status_data['progress']}%")
    time.sleep(2)

if status_data["status"] == "SUCCESS":
    result = status_data["result"]
```

---

### 8. POST /api/query/search/faceted

**Description**: Perform faceted search with advanced filtering on documents.

**Authentication**: Required

**Request Body**:
```json
{
  "query": "insurance policy",
  "filters": {
    "document_type": ["policy", "contract"],
    "date_range": {
      "start": "2024-01-01",
      "end": "2025-01-01"
    },
    "tags": ["california", "automotive"]
  },
  "top_k": 10,
  "enable_reranking": true
}
```

**Response**:
```json
{
  "results": [
    {
      "document_id": "doc_123",
      "title": "California Auto Insurance Policy",
      "score": 0.95,
      "document_type": "policy",
      "tags": ["california", "automotive"],
      "created_at": "2024-06-15T10:30:00Z"
    }
  ],
  "facets": {
    "document_type": {
      "policy": 25,
      "contract": 12,
      "report": 5
    },
    "tags": {
      "california": 30,
      "automotive": 22,
      "insurance": 42
    }
  },
  "total_results": 42,
  "reranked": true
}
```

---

### 9. GET /api/query/health

**Description**: Health check for query services (LangGraph, Arcade.dev, embedding service).

**Authentication**: Not required

**Response**:
```json
{
  "status": "healthy",
  "services": {
    "langgraph": {
      "status": "healthy",
      "model": "claude-3-5-haiku-20241022"
    },
    "arcade": {
      "status": "healthy",
      "enabled_tools": ["Google.Search"],
      "total_tools": 52
    },
    "embedding_service": {
      "status": "healthy",
      "model": "bge-m3",
      "backend": "ollama"
    },
    "cache": {
      "status": "healthy",
      "backend": "redis",
      "hit_rate": 0.667
    }
  },
  "timestamp": "2025-01-17T12:00:00Z"
}
```

**Example**:
```bash
curl https://jb-empire-api.onrender.com/api/query/health
```

---

## Document Endpoints

**Base Path**: `/api/documents`
**Authentication**: Required
**Rate Limit**: 20 requests/minute for upload, 50 requests/minute for other operations

### 1. POST /api/documents/bulk-upload

**Description**: Upload multiple documents in a single request. Processing is handled asynchronously via Celery.

**Authentication**: Required

**Request Body** (multipart/form-data):
```
files: [File, File, File]
metadata: {
  "tags": ["california", "policies"],
  "department": "legal",
  "auto_process": true
}
```

**Response** (202 Accepted):
```json
{
  "operation_id": "bulk_upload_20250117_120000",
  "status": "queued",
  "file_count": 3,
  "files": [
    {
      "filename": "policy_a.pdf",
      "size_bytes": 1048576,
      "status": "queued"
    }
  ],
  "status_url": "/api/documents/bulk-upload/status/bulk_upload_20250117_120000"
}
```

**Example**:
```python
import requests

files = [
    ('files', open('policy_a.pdf', 'rb')),
    ('files', open('contract_b.docx', 'rb'))
]

metadata = {
    "tags": ["california"],
    "auto_process": True
}

response = requests.post(
    "https://jb-empire-api.onrender.com/api/documents/bulk-upload",
    headers={"Authorization": f"Bearer {token}"},
    files=files,
    data={"metadata": json.dumps(metadata)}
)
```

---

### 2. POST /api/documents/bulk-delete

**Description**: Delete multiple documents (soft delete or permanent).

**Authentication**: Required

**Request Body**:
```json
{
  "document_ids": ["doc_123", "doc_456", "doc_789"],
  "hard_delete": false,
  "reason": "Outdated policies from 2020"
}
```

**Response**:
```json
{
  "operation_id": "bulk_delete_20250117_120500",
  "status": "completed",
  "deleted_count": 3,
  "failed_count": 0,
  "results": [
    {
      "document_id": "doc_123",
      "status": "deleted",
      "deleted_at": "2025-01-17T12:05:00Z"
    }
  ]
}
```

---

### 3. POST /api/documents/bulk-reprocess

**Description**: Reprocess multiple documents (re-chunk, re-embed, re-index).

**Authentication**: Required

**Request Body**:
```json
{
  "document_ids": ["doc_123", "doc_456"],
  "options": {
    "regenerate_embeddings": true,
    "update_graph": true,
    "parsing_instructions": "Focus on structured data"
  }
}
```

**Response**:
```json
{
  "operation_id": "bulk_reprocess_20250117_121000",
  "status": "processing",
  "queued_count": 2,
  "status_url": "/api/documents/bulk-reprocess/status/bulk_reprocess_20250117_121000"
}
```

---

### 4. POST /api/documents/bulk-metadata-update

**Description**: Update metadata for multiple documents.

**Authentication**: Required

**Request Body**:
```json
{
  "document_ids": ["doc_123", "doc_456"],
  "metadata_updates": {
    "tags": ["updated", "california"],
    "department": "compliance",
    "review_status": "approved"
  }
}
```

**Response**:
```json
{
  "operation_id": "bulk_metadata_20250117_121500",
  "status": "completed",
  "updated_count": 2,
  "failed_count": 0
}
```

---

## CrewAI Endpoints

**Base Path**: `/api/crewai`
**Authentication**: Required
**Rate Limit**: 50 requests/minute

### 1. GET /api/crewai/health

**Description**: Health check for CrewAI orchestration service.

**Authentication**: Not required

**Response**:
```json
{
  "status": "healthy",
  "service_url": "https://jb-crewai.onrender.com",
  "version": "1.0.0",
  "active_agents": 5,
  "active_crews": 2,
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

### 2. GET /api/crewai/workflows

**Description**: List available CrewAI workflow templates.

**Authentication**: Required

**Response**:
```json
{
  "workflows": [
    {
      "id": "multi_doc_analysis",
      "name": "Multi-Document Analysis",
      "description": "Analyze multiple documents and extract insights",
      "agents": ["parser", "entity_extractor", "synthesizer"],
      "estimated_duration_minutes": 5
    },
    {
      "id": "research_workflow",
      "name": "Research & Synthesis",
      "description": "Deep research with external tools",
      "agents": ["researcher", "fact_checker", "writer"],
      "estimated_duration_minutes": 10
    }
  ]
}
```

---

### 3. POST /api/crewai/agents

**Description**: Create a new CrewAI agent.

**Authentication**: Required

**Request Body**:
```json
{
  "name": "policy_analyzer",
  "role": "Insurance Policy Analyst",
  "goal": "Extract key terms and conditions from insurance policies",
  "tools": ["llamaindex", "neo4j"],
  "backstory": "Expert insurance analyst with 10 years of experience",
  "max_iterations": 3,
  "verbose": true
}
```

**Response** (201 Created):
```json
{
  "agent_id": "agent_abc123",
  "name": "policy_analyzer",
  "role": "Insurance Policy Analyst",
  "status": "active",
  "created_at": "2025-01-17T12:00:00Z"
}
```

---

### 4. GET /api/crewai/agents

**Description**: List all CrewAI agents.

**Authentication**: Required

**Query Parameters**:
- `status` (optional): Filter by status ("active", "inactive")
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Pagination offset

**Response**:
```json
{
  "agents": [
    {
      "agent_id": "agent_abc123",
      "name": "policy_analyzer",
      "role": "Insurance Policy Analyst",
      "status": "active",
      "tasks_completed": 42
    }
  ],
  "total_count": 5,
  "limit": 50,
  "offset": 0
}
```

---

### 5. GET /api/crewai/agents/{agent_id}

**Description**: Get detailed information about a specific agent.

**Authentication**: Required

**Response**:
```json
{
  "agent_id": "agent_abc123",
  "name": "policy_analyzer",
  "role": "Insurance Policy Analyst",
  "goal": "Extract key terms and conditions from insurance policies",
  "tools": ["llamaindex", "neo4j"],
  "status": "active",
  "metrics": {
    "tasks_completed": 42,
    "success_rate": 0.95,
    "avg_duration_seconds": 120
  },
  "created_at": "2025-01-17T12:00:00Z",
  "last_active": "2025-01-17T15:30:00Z"
}
```

---

### 6. GET /api/crewai/agents/by-name/{agent_name}

**Description**: Get agent by name instead of ID.

**Authentication**: Required

**Response**: Same as `/api/crewai/agents/{agent_id}`

---

### 7. PATCH /api/crewai/agents/{agent_id}

**Description**: Update an existing agent's configuration.

**Authentication**: Required

**Request Body**:
```json
{
  "goal": "Updated goal for the agent",
  "tools": ["llamaindex", "neo4j", "Google.Search"],
  "max_iterations": 5
}
```

**Response**:
```json
{
  "agent_id": "agent_abc123",
  "message": "Agent updated successfully",
  "updated_fields": ["goal", "tools", "max_iterations"]
}
```

---

## CrewAI Assets

**Base Path**: `/api/crewai/assets`
**Authentication**: Required
**Rate Limit**: 50 requests/minute

**Purpose**: Store and retrieve CrewAI-generated assets (reports, analyses, visualizations) organized by department and type (Task 40).

### Asset Organization

**B2 Storage Path**: `crewai/assets/{department}/{asset_type}/{execution_id}/{filename}`

**Departments** (10 total):
- `it-engineering`
- `sales-marketing`
- `customer-support`
- `operations-hr-supply`
- `finance-accounting`
- `project-management`
- `real-estate`
- `private-equity-ma`
- `consulting`
- `personal-continuing-ed`

**Asset Types** (5 total):
- `reports` - Final reports and summaries
- `analysis` - Analytical outputs
- `visualizations` - Charts, graphs, diagrams
- `structured_data` - JSON, CSV, Excel files
- `raw_outputs` - Unprocessed agent outputs

---

### 1. POST /api/crewai/assets

**Description**: Store a new CrewAI-generated asset.

**Authentication**: Required

**Request Body** (Text-based asset):
```json
{
  "execution_id": "exec_20250117_120000",
  "department": "finance-accounting",
  "asset_type": "reports",
  "content": "# Financial Analysis Report\n\n## Summary\n...",
  "metadata": {
    "title": "Q4 2024 Financial Analysis",
    "generated_by": "finance_analyst_agent",
    "format": "markdown"
  },
  "confidence_score": 0.92
}
```

**Request Body** (File-based asset):
```json
{
  "execution_id": "exec_20250117_120000",
  "department": "sales-marketing",
  "asset_type": "visualizations",
  "file_content": "<base64-encoded-bytes>",
  "filename": "sales_chart.png",
  "metadata": {
    "title": "Q4 Sales Performance",
    "generated_by": "visualization_agent",
    "format": "png"
  },
  "confidence_score": 0.88
}
```

**Response** (201 Created):
```json
{
  "asset_id": "asset_xyz789",
  "execution_id": "exec_20250117_120000",
  "department": "finance-accounting",
  "asset_type": "reports",
  "storage_path": "crewai/assets/finance-accounting/reports/exec_20250117_120000/financial_analysis.md",
  "storage_url": "https://s3.amazonaws.com/jb-course-kb/crewai/assets/...",
  "confidence_score": 0.92,
  "created_at": "2025-01-17T12:00:00Z"
}
```

**Example**:
```python
import requests
import base64

# Store text-based asset
text_asset = {
    "execution_id": "exec_001",
    "department": "finance-accounting",
    "asset_type": "reports",
    "content": "# Financial Report\n\nTotal Revenue: $1.2M",
    "metadata": {"title": "Q4 Report"},
    "confidence_score": 0.95
}

response = requests.post(
    "https://jb-empire-api.onrender.com/api/crewai/assets",
    headers={"Authorization": f"Bearer {token}"},
    json=text_asset
)

# Store file-based asset
with open("chart.png", "rb") as f:
    file_bytes = base64.b64encode(f.read()).decode()

file_asset = {
    "execution_id": "exec_001",
    "department": "sales-marketing",
    "asset_type": "visualizations",
    "file_content": file_bytes,
    "filename": "sales_chart.png",
    "metadata": {"title": "Sales Chart"},
    "confidence_score": 0.90
}

response = requests.post(
    "https://jb-empire-api.onrender.com/api/crewai/assets",
    headers={"Authorization": f"Bearer {token}"},
    json=file_asset
)
```

---

### 2. GET /api/crewai/assets

**Description**: Retrieve assets with filtering options.

**Authentication**: Required

**Query Parameters**:
- `execution_id` (optional): Filter by execution ID
- `department` (optional): Filter by department
- `asset_type` (optional): Filter by asset type
- `min_confidence` (optional): Minimum confidence score (0.0-1.0)
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Pagination offset

**Response**:
```json
{
  "assets": [
    {
      "asset_id": "asset_xyz789",
      "execution_id": "exec_20250117_120000",
      "department": "finance-accounting",
      "asset_type": "reports",
      "confidence_score": 0.92,
      "storage_url": "https://s3.amazonaws.com/...",
      "metadata": {
        "title": "Q4 2024 Financial Analysis"
      },
      "created_at": "2025-01-17T12:00:00Z"
    }
  ],
  "total_count": 42,
  "limit": 50,
  "offset": 0
}
```

**Example**:
```python
# Get all reports for finance department
response = requests.get(
    "https://jb-empire-api.onrender.com/api/crewai/assets",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "department": "finance-accounting",
        "asset_type": "reports",
        "min_confidence": 0.9
    }
)
```

---

### 3. GET /api/crewai/assets/{asset_id}

**Description**: Retrieve a specific asset by ID.

**Authentication**: Required

**Response**:
```json
{
  "asset_id": "asset_xyz789",
  "execution_id": "exec_20250117_120000",
  "department": "finance-accounting",
  "asset_type": "reports",
  "content": "# Financial Analysis Report\n\n## Summary\n...",
  "storage_url": "https://s3.amazonaws.com/...",
  "storage_path": "crewai/assets/finance-accounting/reports/...",
  "confidence_score": 0.92,
  "metadata": {
    "title": "Q4 2024 Financial Analysis",
    "generated_by": "finance_analyst_agent",
    "format": "markdown"
  },
  "created_at": "2025-01-17T12:00:00Z",
  "updated_at": "2025-01-17T12:00:00Z"
}
```

---

### 4. PATCH /api/crewai/assets/{asset_id}

**Description**: Update asset confidence score or metadata.

**Authentication**: Required

**Request Body**:
```json
{
  "confidence_score": 0.95,
  "metadata": {
    "reviewed_by": "john_smith",
    "review_status": "approved"
  }
}
```

**Response**:
```json
{
  "asset_id": "asset_xyz789",
  "message": "Asset updated successfully",
  "updated_fields": ["confidence_score", "metadata"]
}
```

---

## Monitoring Endpoints

**Base Path**: `/api/monitoring`
**Authentication**: Not required (public metrics)
**Rate Limit**: 200 requests/minute

### 1. GET /api/monitoring/health

**Description**: Overall system health check.

**Response**:
```json
{
  "status": "healthy",
  "version": "7.3.0",
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "celery": "healthy"
  },
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

### 2. GET /api/monitoring/metrics

**Description**: Prometheus-format metrics for scraping.

**Response** (text/plain):
```
# HELP empire_query_requests_total Total number of query requests
# TYPE empire_query_requests_total counter
empire_query_requests_total{endpoint="adaptive"} 1523

# HELP empire_query_latency_seconds Query latency in seconds
# TYPE empire_query_latency_seconds histogram
empire_query_latency_seconds_bucket{endpoint="adaptive",le="0.5"} 342
empire_query_latency_seconds_bucket{endpoint="adaptive",le="1.0"} 856
empire_query_latency_seconds_bucket{endpoint="adaptive",le="5.0"} 1421
empire_query_latency_seconds_bucket{endpoint="adaptive",le="+Inf"} 1523
empire_query_latency_seconds_sum{endpoint="adaptive"} 6891.234
empire_query_latency_seconds_count{endpoint="adaptive"} 1523

# HELP empire_cache_hits_total Total number of cache hits
# TYPE empire_cache_hits_total counter
empire_cache_hits_total{namespace="adaptive"} 1015

# HELP empire_cache_misses_total Total number of cache misses
# TYPE empire_cache_misses_total counter
empire_cache_misses_total{namespace="adaptive"} 508
```

---

### 3. GET /api/monitoring/metrics/json

**Description**: JSON-format metrics for Grafana datasource.

**Response**:
```json
{
  "query_metrics": {
    "total_requests": 1523,
    "avg_latency_ms": 4524,
    "p50_latency_ms": 3200,
    "p95_latency_ms": 11000,
    "p99_latency_ms": 19000
  },
  "cache_metrics": {
    "hit_rate": 0.667,
    "total_hits": 1015,
    "total_misses": 508
  },
  "document_metrics": {
    "total_documents": 4532,
    "processed_documents": 4500,
    "failed_documents": 32
  }
}
```

---

### 4. GET /api/monitoring/metrics/documents

**Description**: Document processing statistics.

**Response**:
```json
{
  "total_documents": 4532,
  "processed": 4500,
  "processing": 10,
  "failed": 32,
  "by_type": {
    "pdf": 2500,
    "docx": 1200,
    "txt": 832
  },
  "avg_processing_time_ms": 5234
}
```

---

### 5. GET /api/monitoring/metrics/queries

**Description**: Query performance metrics.

**Response**:
```json
{
  "total_queries": 1523,
  "by_endpoint": {
    "adaptive": 856,
    "auto": 567,
    "faceted": 100
  },
  "avg_latency_ms": 4524,
  "cache_hit_rate": 0.667,
  "workflow_distribution": {
    "langgraph": 856,
    "crewai": 234,
    "simple": 433
  }
}
```

---

## RBAC Endpoints

**Base Path**: `/api/rbac`
**Authentication**: Required (admin only)
**Rate Limit**: 50 requests/minute

**Purpose**: Role-Based Access Control and API key lifecycle management (Task 41.1).

### 1. POST /api/rbac/keys

**Description**: Create a new API key. Returns full key ONLY ONCE (never stored in plaintext).

**Authentication**: Required (admin only)

**Request Body**:
```json
{
  "name": "Production API Key",
  "description": "API key for production deployment",
  "permissions": ["query:read", "document:write"],
  "expires_at": "2026-01-01T00:00:00Z",
  "rate_limit": 1000
}
```

**Response** (201 Created):
```json
{
  "key_id": "key_abc123",
  "api_key": "emp_live_EXAMPLE1234567890abcdefghijklmnopqrstuvwxyz",
  "name": "Production API Key",
  "prefix": "sk_live_a1b2",
  "permissions": ["query:read", "document:write"],
  "rate_limit": 1000,
  "expires_at": "2026-01-01T00:00:00Z",
  "created_at": "2025-01-17T12:00:00Z",
  "warning": "Save this key now. You won't be able to see it again."
}
```

**Security Note**: The `api_key` field is shown ONLY in the creation response. It's hashed with bcrypt before storage and cannot be retrieved later.

---

### 2. GET /api/rbac/keys

**Description**: List all API keys (prefix only for security).

**Authentication**: Required (admin only)

**Query Parameters**:
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Pagination offset
- `active_only` (optional): Filter to active keys only

**Response**:
```json
{
  "keys": [
    {
      "key_id": "key_abc123",
      "name": "Production API Key",
      "prefix": "sk_live_a1b2",
      "permissions": ["query:read", "document:write"],
      "rate_limit": 1000,
      "status": "active",
      "last_used": "2025-01-17T11:30:00Z",
      "expires_at": "2026-01-01T00:00:00Z",
      "created_at": "2025-01-17T12:00:00Z"
    }
  ],
  "total_count": 5
}
```

---

### 3. POST /api/rbac/keys/rotate

**Description**: Rotate an API key (generate new key, revoke old one).

**Authentication**: Required (admin only)

**Request Body**:
```json
{
  "key_id": "key_abc123",
  "reason": "Regular rotation per security policy"
}
```

**Response**:
```json
{
  "old_key_id": "key_abc123",
  "new_key_id": "key_xyz789",
  "new_api_key": "emp_live_EXAMPLE0987654321zyxwvutsrqponmlkjihgfedcba",
  "prefix": "sk_live_z9y8",
  "message": "Key rotated successfully. Old key will be valid for 24 hours.",
  "grace_period_ends": "2025-01-18T12:00:00Z"
}
```

---

### 4. DELETE /api/rbac/keys/{key_id}

**Description**: Revoke an API key immediately.

**Authentication**: Required (admin only)

**Response**:
```json
{
  "key_id": "key_abc123",
  "status": "revoked",
  "revoked_at": "2025-01-17T12:00:00Z",
  "message": "API key revoked successfully"
}
```

---

## User Endpoints

**Base Path**: `/api/users`
**Authentication**: Required
**Rate Limit**: 50 requests/minute

### 1. POST /api/users

**Description**: Create a new user (admin only).

**Authentication**: Required (admin only)

**Request Body**:
```json
{
  "email": "john.smith@example.com",
  "full_name": "John Smith",
  "password": "SecurePassword123!",
  "role": "user",
  "department": "finance"
}
```

**Response** (201 Created):
```json
{
  "user_id": "user_abc123",
  "email": "john.smith@example.com",
  "full_name": "John Smith",
  "role": "user",
  "status": "active",
  "created_at": "2025-01-17T12:00:00Z"
}
```

---

### 2. GET /api/users

**Description**: List users with pagination (admin only).

**Authentication**: Required (admin only)

**Query Parameters**:
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Pagination offset
- `role` (optional): Filter by role
- `status` (optional): Filter by status

**Response**:
```json
{
  "users": [
    {
      "user_id": "user_abc123",
      "email": "john.smith@example.com",
      "full_name": "John Smith",
      "role": "user",
      "status": "active",
      "last_login": "2025-01-17T11:30:00Z",
      "created_at": "2025-01-17T12:00:00Z"
    }
  ],
  "total_count": 42,
  "limit": 50,
  "offset": 0
}
```

---

### 3. GET /api/users/{user_id}

**Description**: Get user details.

**Authentication**: Required (self or admin)

**Response**:
```json
{
  "user_id": "user_abc123",
  "email": "john.smith@example.com",
  "full_name": "John Smith",
  "role": "user",
  "status": "active",
  "department": "finance",
  "preferences": {
    "theme": "dark",
    "notifications": true
  },
  "created_at": "2025-01-17T12:00:00Z",
  "last_login": "2025-01-17T11:30:00Z"
}
```

---

### 4. PATCH /api/users/{user_id}

**Description**: Update user profile.

**Authentication**: Required (self or admin)

**Request Body**:
```json
{
  "full_name": "John A. Smith",
  "department": "operations",
  "preferences": {
    "theme": "light"
  }
}
```

**Response**:
```json
{
  "user_id": "user_abc123",
  "message": "User updated successfully",
  "updated_fields": ["full_name", "department", "preferences"]
}
```

---

### 5. POST /api/users/password/change

**Description**: Change user password.

**Authentication**: Required (self only)

**Request Body**:
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePassword456!"
}
```

**Response**:
```json
{
  "message": "Password changed successfully",
  "user_id": "user_abc123"
}
```

---

### 6. POST /api/users/password/admin-reset

**Description**: Admin password reset (admin only).

**Authentication**: Required (admin only)

**Request Body**:
```json
{
  "user_id": "user_abc123",
  "new_password": "TemporaryPassword789!",
  "require_change": true
}
```

**Response**:
```json
{
  "message": "Password reset successfully",
  "user_id": "user_abc123",
  "require_change_on_login": true
}
```

---

### 7. POST /api/users/{user_id}/suspend

**Description**: Suspend user account (admin only).

**Authentication**: Required (admin only)

**Request Body**:
```json
{
  "reason": "Policy violation",
  "duration_days": 30
}
```

**Response**:
```json
{
  "user_id": "user_abc123",
  "status": "suspended",
  "suspended_until": "2025-02-16T12:00:00Z",
  "reason": "Policy violation"
}
```

---

### 8. POST /api/users/{user_id}/activate

**Description**: Activate suspended user account (admin only).

**Authentication**: Required (admin only)

**Response**:
```json
{
  "user_id": "user_abc123",
  "status": "active",
  "activated_at": "2025-01-17T12:00:00Z"
}
```

---

## Session Endpoints

**Base Path**: `/sessions`
**Authentication**: Required
**Rate Limit**: 100 requests/minute

**Purpose**: Manage user chat sessions with Redis-backed caching (Task 28).

### 1. POST /sessions

**Description**: Create a new session.

**Authentication**: Required

**Request Body**:
```json
{
  "user_id": "user_abc123",
  "metadata": {
    "client": "web",
    "browser": "Chrome",
    "platform": "macOS"
  }
}
```

**Response** (201 Created):
```json
{
  "session_id": "session_xyz789",
  "user_id": "user_abc123",
  "status": "active",
  "created_at": "2025-01-17T12:00:00Z",
  "expires_at": "2025-01-17T18:00:00Z"
}
```

---

### 2. GET /sessions/{session_id}

**Description**: Get session details.

**Authentication**: Required

**Response**:
```json
{
  "session_id": "session_xyz789",
  "user_id": "user_abc123",
  "status": "active",
  "message_count": 15,
  "created_at": "2025-01-17T12:00:00Z",
  "last_activity": "2025-01-17T12:30:00Z",
  "expires_at": "2025-01-17T18:00:00Z",
  "metadata": {
    "client": "web",
    "browser": "Chrome"
  }
}
```

---

### 3. GET /sessions/user/{user_id}

**Description**: List all sessions for a user.

**Authentication**: Required

**Query Parameters**:
- `status` (optional): Filter by status ("active", "expired")
- `limit` (optional): Max results (default: 50)

**Response**:
```json
{
  "sessions": [
    {
      "session_id": "session_xyz789",
      "status": "active",
      "message_count": 15,
      "created_at": "2025-01-17T12:00:00Z",
      "last_activity": "2025-01-17T12:30:00Z"
    }
  ],
  "total_count": 5
}
```

---

### 4. PATCH /sessions/{session_id}/activity

**Description**: Update session last activity timestamp.

**Authentication**: Required

**Response**:
```json
{
  "session_id": "session_xyz789",
  "last_activity": "2025-01-17T12:35:00Z",
  "expires_at": "2025-01-17T18:35:00Z"
}
```

---

### 5. PATCH /sessions/{session_id}/metadata

**Description**: Update session metadata.

**Authentication**: Required

**Request Body**:
```json
{
  "metadata": {
    "current_page": "/dashboard",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Response**:
```json
{
  "session_id": "session_xyz789",
  "message": "Metadata updated successfully"
}
```

---

### 6. DELETE /sessions/{session_id}

**Description**: Delete/end a session.

**Authentication**: Required

**Response**:
```json
{
  "session_id": "session_xyz789",
  "status": "deleted",
  "deleted_at": "2025-01-17T12:40:00Z"
}
```

---

## Audit Endpoints

**Base Path**: `/api/audit`
**Authentication**: Required (admin only)
**Rate Limit**: 50 requests/minute

**Purpose**: Security audit logging for compliance (Task 41.5).

### 1. GET /api/audit/logs

**Description**: Retrieve audit logs with filtering.

**Authentication**: Required (admin only)

**Query Parameters**:
- `user_id` (optional): Filter by user
- `event_type` (optional): Filter by event type
- `start_date` (optional): Start date (ISO 8601)
- `end_date` (optional): End date (ISO 8601)
- `limit` (optional): Max results (default: 100)
- `offset` (optional): Pagination offset

**Event Types**:
- `document_upload`
- `document_delete`
- `user_login`
- `user_logout`
- `policy_violation`
- `system_error`
- `config_change`
- `data_export`

**Response**:
```json
{
  "logs": [
    {
      "log_id": "log_abc123",
      "user_id": "user_xyz789",
      "event_type": "document_upload",
      "details": {
        "document_id": "doc_123",
        "filename": "policy_a.pdf",
        "size_bytes": 1048576
      },
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "timestamp": "2025-01-17T12:00:00Z"
    }
  ],
  "total_count": 1523,
  "limit": 100,
  "offset": 0
}
```

---

### 2. GET /api/audit/logs/{log_id}

**Description**: Get detailed audit log entry.

**Authentication**: Required (admin only)

**Response**:
```json
{
  "log_id": "log_abc123",
  "user_id": "user_xyz789",
  "event_type": "document_upload",
  "details": {
    "document_id": "doc_123",
    "filename": "policy_a.pdf",
    "size_bytes": 1048576,
    "processing_status": "success"
  },
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "request_id": "req_abc123",
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

### 3. GET /api/audit/stats

**Description**: Get audit log statistics.

**Authentication**: Required (admin only)

**Query Parameters**:
- `start_date` (optional): Start date
- `end_date` (optional): End date

**Response**:
```json
{
  "total_events": 15234,
  "by_event_type": {
    "document_upload": 5234,
    "user_login": 4532,
    "document_delete": 234
  },
  "by_user": {
    "user_abc123": 1234,
    "user_xyz789": 856
  },
  "policy_violations": 12,
  "system_errors": 45,
  "time_range": {
    "start": "2025-01-01T00:00:00Z",
    "end": "2025-01-17T12:00:00Z"
  }
}
```

---

## Preference Endpoints

**Base Path**: `/preferences`
**Authentication**: Required
**Rate Limit**: 100 requests/minute

**Purpose**: User preference management (Task 28).

### 1. POST /preferences

**Description**: Set user preferences.

**Authentication**: Required

**Request Body**:
```json
{
  "user_id": "user_abc123",
  "preferences": {
    "theme": "dark",
    "notifications": {
      "email": true,
      "push": false
    },
    "language": "en",
    "timezone": "America/Los_Angeles"
  }
}
```

**Response**:
```json
{
  "user_id": "user_abc123",
  "message": "Preferences saved successfully",
  "updated_at": "2025-01-17T12:00:00Z"
}
```

---

### 2. GET /preferences/{user_id}

**Description**: Get user preferences.

**Authentication**: Required

**Response**:
```json
{
  "user_id": "user_abc123",
  "preferences": {
    "theme": "dark",
    "notifications": {
      "email": true,
      "push": false
    },
    "language": "en",
    "timezone": "America/Los_Angeles"
  },
  "updated_at": "2025-01-17T12:00:00Z"
}
```

---

### 3. DELETE /preferences/{user_id}

**Description**: Delete user preferences (reset to defaults).

**Authentication**: Required

**Response**:
```json
{
  "user_id": "user_abc123",
  "message": "Preferences reset to defaults"
}
```

---

## Cost Endpoints

**Base Path**: `/costs`
**Authentication**: Required
**Rate Limit**: 50 requests/minute

**Purpose**: Cost tracking and budget management (Task 30).

### 1. POST /costs

**Description**: Record a cost entry.

**Authentication**: Required

**Request Body**:
```json
{
  "user_id": "user_abc123",
  "service": "anthropic",
  "cost_type": "llm_api",
  "amount_usd": 0.025,
  "details": {
    "model": "claude-3-5-haiku-20241022",
    "input_tokens": 1500,
    "output_tokens": 500
  }
}
```

**Response** (201 Created):
```json
{
  "cost_id": "cost_abc123",
  "user_id": "user_abc123",
  "service": "anthropic",
  "amount_usd": 0.025,
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

### 2. GET /costs/monthly

**Description**: Get monthly cost report.

**Authentication**: Required

**Query Parameters**:
- `year` (required): Year (e.g., 2025)
- `month` (required): Month (1-12)
- `user_id` (optional): Filter by user

**Response**:
```json
{
  "year": 2025,
  "month": 1,
  "total_cost_usd": 423.56,
  "by_service": {
    "anthropic": 250.00,
    "supabase": 100.00,
    "upstash": 50.00,
    "backblaze": 23.56
  },
  "by_cost_type": {
    "llm_api": 250.00,
    "database": 100.00,
    "cache": 50.00,
    "storage": 23.56
  },
  "budget_limit_usd": 500.00,
  "budget_remaining_usd": 76.44,
  "budget_utilization": 0.847
}
```

---

### 3. GET /costs/alerts

**Description**: Get budget alerts and warnings.

**Authentication**: Required

**Response**:
```json
{
  "alerts": [
    {
      "alert_id": "alert_abc123",
      "severity": "warning",
      "message": "Monthly budget at 85% utilization",
      "threshold": 0.85,
      "current_utilization": 0.847,
      "triggered_at": "2025-01-17T12:00:00Z"
    }
  ],
  "total_alerts": 1
}
```

---

## Agent Interaction Endpoints

**Base Path**: `/api/crewai/agent-interactions`
**Authentication**: Required
**Rate Limit**: 100 requests/minute

**Purpose**: Inter-agent messaging and coordination (Task 39).

### 1. POST /api/crewai/agent-interactions/message

**Description**: Send direct message from one agent to another.

**Authentication**: Required

**Request Body**:
```json
{
  "from_agent": "agent_abc123",
  "to_agent": "agent_xyz789",
  "message_type": "data_request",
  "content": {
    "request": "Need entity extraction results for document doc_456",
    "priority": "high"
  }
}
```

**Response** (201 Created):
```json
{
  "message_id": "msg_abc123",
  "from_agent": "agent_abc123",
  "to_agent": "agent_xyz789",
  "status": "sent",
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

### 2. POST /api/crewai/agent-interactions/broadcast

**Description**: Broadcast message to multiple agents.

**Authentication**: Required

**Request Body**:
```json
{
  "from_agent": "agent_abc123",
  "message_type": "system_notification",
  "content": {
    "event": "New documents available for processing",
    "document_ids": ["doc_123", "doc_456"]
  },
  "recipient_filter": {
    "role": "document_processor"
  }
}
```

**Response**:
```json
{
  "broadcast_id": "broadcast_abc123",
  "recipients_count": 5,
  "status": "sent",
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

### 3. POST /api/crewai/agent-interactions/event

**Description**: Publish event to event bus for agent subscriptions.

**Authentication**: Required

**Request Body**:
```json
{
  "event_type": "document_processed",
  "source_agent": "agent_abc123",
  "payload": {
    "document_id": "doc_123",
    "status": "completed",
    "entities_extracted": 42
  }
}
```

**Response**:
```json
{
  "event_id": "event_abc123",
  "event_type": "document_processed",
  "published_at": "2025-01-17T12:00:00Z",
  "subscribers_notified": 3
}
```

---

### 4. GET /api/crewai/agent-interactions/messages/{agent_id}

**Description**: Get messages for a specific agent.

**Authentication**: Required

**Query Parameters**:
- `status` (optional): Filter by status ("unread", "read")
- `limit` (optional): Max results (default: 50)

**Response**:
```json
{
  "messages": [
    {
      "message_id": "msg_abc123",
      "from_agent": "agent_xyz789",
      "to_agent": "agent_abc123",
      "message_type": "data_response",
      "content": {
        "entities": [...]
      },
      "status": "unread",
      "timestamp": "2025-01-17T12:00:00Z"
    }
  ],
  "total_count": 5,
  "unread_count": 2
}
```

---

### 5. WebSocket: /api/crewai/agent-interactions/ws/{agent_id}

**Description**: WebSocket connection for real-time agent communication.

**Authentication**: Required (via query parameter: `?token=<jwt>`)

**Connection**:
```javascript
const ws = new WebSocket(
  'wss://jb-empire-api.onrender.com/api/crewai/agent-interactions/ws/agent_abc123?token=<jwt>'
);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};

// Send message
ws.send(JSON.stringify({
  type: 'message',
  to_agent: 'agent_xyz789',
  content: { request: '...' }
}));
```

**Message Format**:
```json
{
  "type": "message",
  "message_id": "msg_abc123",
  "from_agent": "agent_xyz789",
  "content": {
    "response": "..."
  },
  "timestamp": "2025-01-17T12:00:00Z"
}
```

---

## Error Codes Reference

### HTTP Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Request accepted for async processing |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict (e.g., duplicate) |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

---

### Application Error Codes

**Query Errors** (QRY-xxx):
- `QRY-001`: Invalid query format
- `QRY-002`: Query too long (max 10,000 chars)
- `QRY-003`: Max iterations exceeded
- `QRY-004`: External tool timeout
- `QRY-005`: LLM API error

**Document Errors** (DOC-xxx):
- `DOC-001`: Invalid file type
- `DOC-002`: File too large (max 100MB)
- `DOC-003`: Parsing failed
- `DOC-004`: Embedding generation failed
- `DOC-005`: Document not found

**Authentication Errors** (AUTH-xxx):
- `AUTH-001`: Invalid JWT token
- `AUTH-002`: Token expired
- `AUTH-003`: Invalid credentials
- `AUTH-004`: Account suspended

**Rate Limit Errors** (RATE-xxx):
- `RATE-001`: Rate limit exceeded for endpoint
- `RATE-002`: Daily quota exceeded
- `RATE-003`: Concurrent request limit exceeded

**Cache Errors** (CACHE-xxx):
- `CACHE-001`: Redis connection failed
- `CACHE-002`: Cache key not found
- `CACHE-003`: Cache serialization error

---

### Error Response Format

All errors follow this consistent format:

```json
{
  "error": {
    "code": "QRY-001",
    "message": "Invalid query format: query field is required",
    "details": {
      "field": "query",
      "reason": "missing_required_field"
    },
    "request_id": "req_abc123",
    "timestamp": "2025-01-17T12:00:00Z"
  }
}
```

**Error Response Fields**:
- `code` (string): Application error code (e.g., "QRY-001")
- `message` (string): Human-readable error message
- `details` (object, optional): Additional error context
- `request_id` (string): Unique request ID for tracking
- `timestamp` (string): Error timestamp (ISO 8601)

---

### Rate Limit Headers

All responses include rate limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1705502400
```

**Header Descriptions**:
- `X-RateLimit-Limit`: Max requests per time window
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Best Practices

### Caching

1. **Leverage Semantic Caching**: Identical or similar queries are cached for 30 minutes. Check `from_cache` field in responses.

2. **Cache Headers**: Respect cache-related response headers:
   - `Cache-Control: public, max-age=1800`
   - `X-Cache-Status: HIT` or `MISS`

3. **Cache Invalidation**: Contact admin if you need to invalidate specific cached results.

### Performance

1. **Use Async Endpoints**: For long-running queries (>10 seconds), use `/async` endpoints and poll for results.

2. **Batch Requests**: Use `/api/query/batch` for multiple related queries instead of sequential requests.

3. **Filter Early**: Use faceted search with filters to reduce result set size.

### Security

1. **Rotate API Keys**: Rotate API keys every 90 days using `/api/rbac/keys/rotate`.

2. **Use HTTPS**: Always use HTTPS in production. HTTP requests are automatically redirected.

3. **Token Expiration**: JWT tokens expire after 24 hours. Refresh tokens before expiration.

4. **Audit Logs**: Monitor `/api/audit/logs` for suspicious activity.

### Error Handling

1. **Retry Logic**: Implement exponential backoff for 5xx errors (max 3 retries).

2. **Rate Limiting**: Handle 429 errors by respecting `Retry-After` header.

3. **Timeouts**: Set client timeouts to 60 seconds for sync endpoints, 300 seconds for async.

---

## Code Examples

### Python Client Example

```python
import requests
import time
from typing import Optional

class EmpireClient:
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }

    def adaptive_query(self, query: str, max_iterations: int = 3) -> dict:
        """Execute adaptive query with caching"""
        response = requests.post(
            f"{self.base_url}/api/query/adaptive",
            headers=self.headers,
            json={
                "query": query,
                "max_iterations": max_iterations,
                "enable_tools": True
            }
        )
        response.raise_for_status()
        return response.json()

    def adaptive_query_async(self, query: str) -> str:
        """Submit async query and return task ID"""
        response = requests.post(
            f"{self.base_url}/api/query/adaptive/async",
            headers=self.headers,
            json={"query": query}
        )
        response.raise_for_status()
        return response.json()["task_id"]

    def poll_task_status(self, task_id: str, timeout: int = 300) -> dict:
        """Poll for async task completion"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.base_url}/api/query/status/{task_id}",
                headers=self.headers
            )
            response.raise_for_status()

            data = response.json()

            if data["status"] in ["SUCCESS", "FAILURE"]:
                return data

            print(f"Progress: {data['progress']}%")
            time.sleep(2)

        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")

# Usage
client = EmpireClient(
    base_url="https://jb-empire-api.onrender.com",
    jwt_token="your-jwt-token"
)

# Sync query
result = client.adaptive_query("What are California insurance requirements?")
print(f"Answer: {result['answer']}")
print(f"Cached: {result['from_cache']}")

# Async query
task_id = client.adaptive_query_async("Complex research task")
result = client.poll_task_status(task_id)
print(f"Result: {result['result']['answer']}")
```

### JavaScript/TypeScript Client Example

```typescript
class EmpireClient {
  constructor(
    private baseUrl: string,
    private jwtToken: string
  ) {}

  private async request(endpoint: string, options: RequestInit = {}) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.jwtToken}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error.message);
    }

    return response.json();
  }

  async adaptiveQuery(query: string, maxIterations: number = 3) {
    return this.request('/api/query/adaptive', {
      method: 'POST',
      body: JSON.stringify({
        query,
        max_iterations: maxIterations,
        enable_tools: true,
      }),
    });
  }

  async adaptiveQueryAsync(query: string): Promise<string> {
    const response = await this.request('/api/query/adaptive/async', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
    return response.task_id;
  }

  async pollTaskStatus(taskId: string, timeout: number = 300000): Promise<any> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const data = await this.request(`/api/query/status/${taskId}`);

      if (data.status === 'SUCCESS' || data.status === 'FAILURE') {
        return data;
      }

      console.log(`Progress: ${data.progress}%`);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    throw new Error(`Task ${taskId} timed out after ${timeout}ms`);
  }
}

// Usage
const client = new EmpireClient(
  'https://jb-empire-api.onrender.com',
  'your-jwt-token'
);

// Sync query
const result = await client.adaptiveQuery('What are California insurance requirements?');
console.log(`Answer: ${result.answer}`);
console.log(`Cached: ${result.from_cache}`);

// Async query
const taskId = await client.adaptiveQueryAsync('Complex research task');
const asyncResult = await client.pollTaskStatus(taskId);
console.log(`Result: ${asyncResult.result.answer}`);
```

---

## Additional Resources

### Official Documentation
- **Interactive API Docs**: https://jb-empire-api.onrender.com/docs
- **OpenAPI Schema**: https://jb-empire-api.onrender.com/openapi.json
- **GitHub Repository**: (Contact admin for access)

### Related Documentation
- [WORKFLOW_DIAGRAMS.md](./WORKFLOW_DIAGRAMS.md) - Service interaction diagrams
- [ONBOARDING.md](./onboarding/) - Quick start guides
- [SECURITY.md](./SECURITY.md) - Security best practices

### Support
- **Email**: support@empire.ai
- **Slack**: #empire-api-support
- **Office Hours**: Monday-Friday, 9AM-5PM PST

### Changelog
- **v7.3.0** (2025-01-17): Added LangGraph + Arcade.dev integration, semantic caching (Task 43.3), CrewAI asset storage (Task 40)
- **v7.2.0** (2025-01-10): Added security hardening (Task 41), monitoring endpoints (Milestone 6)
- **v7.1.0** (2024-12-15): Initial release with dual-database architecture

---

**Last Updated**: 2025-01-17
**API Version**: 7.3.0
**Documentation Version**: 1.0
