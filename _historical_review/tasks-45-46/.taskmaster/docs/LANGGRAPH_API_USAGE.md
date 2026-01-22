# LangGraph + Arcade.dev API Usage Guide (Task 46)

## Overview

Empire v7.3 includes adaptive query processing with three-layer orchestration:
- **Layer 1 (CrewAI)**: Sequential multi-agent workflows
- **Layer 2 (LangGraph)**: Adaptive branching with iterative refinement
- **Layer 3 (Arcade.dev)**: External tool integration (Google Search, Slack, etc.)

## Base URL

**Production**: `https://jb-empire-api.onrender.com`

---

## Endpoints

### 1. Health Check

**GET** `/api/query/health`

Check if LangGraph + Arcade.dev services are available.

**Response**:
```json
{
  "status": "healthy",
  "langgraph_enabled": true,
  "arcade_enabled": true,
  "workflow_router_enabled": true,
  "available_workflows": ["langgraph", "crewai", "simple"],
  "async_processing": true,
  "celery_enabled": true
}
```

---

### 2. List Available Tools

**GET** `/api/query/tools`

Get list of all available tools (internal + external via Arcade.dev).

**Response**:
```json
{
  "internal_tools": ["VectorSearch", "GraphQuery", "HybridSearch"],
  "external_tools": ["Google.Search", "Slack.SendMessage"],
  "total_count": 5,
  "arcade_enabled": true
}
```

---

### 3. Synchronous Adaptive Query

**POST** `/api/query/adaptive`

Execute adaptive query with LangGraph workflow synchronously (blocks until complete).

**Use for**:
- Quick queries (< 30 seconds)
- When you need immediate results
- Testing and development

**Request**:
```json
{
  "query": "What are California insurance regulations?",
  "max_iterations": 3,
  "use_external_tools": true,
  "use_graph_context": true
}
```

**Response**:
```json
{
  "answer": "Based on research, California insurance regulations...",
  "refined_queries": [
    "California insurance regulatory framework",
    "CA insurance compliance requirements"
  ],
  "sources": [
    {"type": "vector", "content": "..."},
    {"type": "graph", "content": "..."}
  ],
  "tool_calls": [
    {"tool": "VectorSearch", "result": "..."}
  ],
  "iterations": 2,
  "workflow_type": "langgraph",
  "processing_time_ms": 15420
}
```

---

### 4. Synchronous Auto-Routed Query

**POST** `/api/query/auto`

Automatically route query to optimal framework (LangGraph/CrewAI/Simple RAG).

**Use for**:
- General queries where framework choice doesn't matter
- Letting the system optimize routing
- Production queries with mixed complexity

**Request**:
```json
{
  "query": "What is our vacation policy?",
  "max_iterations": 2
}
```

**Response**: Same as adaptive query, plus `workflow_type` shows which framework was used.

---

### 5. Asynchronous Adaptive Query

**POST** `/api/query/adaptive/async`

Submit adaptive query for background processing via Celery.

**Use for**:
- Long-running queries (30+ seconds)
- Queries requiring external web search
- Non-blocking API responses
- Batch operations

**Request**:
```json
{
  "query": "Research California insurance regulations and compare with Texas",
  "max_iterations": 3,
  "use_external_tools": true
}
```

**Response**:
```json
{
  "task_id": "abc123-def456-789...",
  "status": "PENDING",
  "message": "Query submitted for async processing. Poll /query/status/{task_id} for results.",
  "estimated_time_seconds": 90
}
```

---

### 6. Asynchronous Auto-Routed Query

**POST** `/api/query/auto/async`

Submit auto-routed query for background processing.

**Request**:
```json
{
  "query": "What are our vacation policies?",
  "max_iterations": 2
}
```

**Response**: Same as async adaptive query.

---

### 7. Batch Query Processing

**POST** `/api/query/batch`

Process multiple queries in batch via Celery (up to 50 queries).

**Use for**:
- Processing multiple related queries
- Bulk data extraction
- Scheduled query refreshes

**Request**:
```json
{
  "queries": [
    "What is our vacation policy?",
    "What are health insurance options?",
    "How do I submit expenses?"
  ],
  "max_iterations": 2,
  "use_auto_routing": true
}
```

**Response**:
```json
{
  "task_id": "batch-xyz789...",
  "status": "PENDING",
  "message": "Batch of 3 queries submitted for processing.",
  "estimated_time_seconds": 120
}
```

---

### 8. Check Task Status

**GET** `/api/query/status/{task_id}`

Poll for results of async query processing.

**Statuses**:
- `PENDING`: Task waiting to start
- `STARTED`: Task currently processing
- `SUCCESS`: Task completed (result available)
- `FAILURE`: Task failed (error available)

**Response (in progress)**:
```json
{
  "task_id": "abc123...",
  "status": "STARTED",
  "result": null,
  "error": null,
  "progress": {
    "iteration": 2,
    "max_iterations": 3
  }
}
```

**Response (completed)**:
```json
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "result": {
    "answer": "Based on research...",
    "iterations": 3,
    "sources": [...],
    "tool_calls": [...],
    "status": "completed"
  },
  "error": null
}
```

**Response (failed)**:
```json
{
  "task_id": "abc123...",
  "status": "FAILURE",
  "result": null,
  "error": "Query processing failed: Connection timeout"
}
```

---

## Python Examples

### Example 1: Synchronous Adaptive Query

```python
import requests

response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/adaptive",
    json={
        "query": "What are California insurance regulations?",
        "max_iterations": 2,
        "use_external_tools": False
    }
)

data = response.json()
print(f"Answer: {data['answer']}")
print(f"Iterations: {data['iterations']}")
```

### Example 2: Asynchronous Query with Polling

```python
import requests
import time

# Submit query
submit_response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/adaptive/async",
    json={
        "query": "Research insurance regulations across states",
        "max_iterations": 3
    }
)

task_id = submit_response.json()['task_id']
print(f"Task submitted: {task_id}")

# Poll for results
while True:
    time.sleep(5)  # Poll every 5 seconds

    status_response = requests.get(
        f"https://jb-empire-api.onrender.com/api/query/status/{task_id}"
    )

    status_data = status_response.json()

    if status_data['status'] == 'SUCCESS':
        result = status_data['result']
        print(f"Answer: {result['answer']}")
        break
    elif status_data['status'] == 'FAILURE':
        print(f"Failed: {status_data['error']}")
        break
    else:
        print(f"Status: {status_data['status']}")
```

### Example 3: Batch Processing

```python
import requests

response = requests.post(
    "https://jb-empire-api.onrender.com/api/query/batch",
    json={
        "queries": [
            "What is our vacation policy?",
            "What are health insurance options?",
            "How do I submit expenses?"
        ],
        "max_iterations": 2,
        "use_auto_routing": True
    }
)

batch_task_id = response.json()['task_id']
print(f"Batch submitted: {batch_task_id}")

# Poll batch status (same as single query)
```

---

## JavaScript Examples

### Example 1: Synchronous Query

```javascript
const response = await fetch('https://jb-empire-api.onrender.com/api/query/adaptive', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'What are California insurance regulations?',
    max_iterations: 2
  })
});

const data = await response.json();
console.log('Answer:', data.answer);
console.log('Iterations:', data.iterations);
```

### Example 2: Async with Polling

```javascript
// Submit query
const submitResponse = await fetch('https://jb-empire-api.onrender.com/api/query/adaptive/async', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'Research insurance regulations',
    max_iterations: 3
  })
});

const { task_id } = await submitResponse.json();
console.log('Task ID:', task_id);

// Poll for results
const pollInterval = setInterval(async () => {
  const statusResponse = await fetch(`https://jb-empire-api.onrender.com/api/query/status/${task_id}`);
  const statusData = await statusResponse.json();

  if (statusData.status === 'SUCCESS') {
    console.log('Answer:', statusData.result.answer);
    clearInterval(pollInterval);
  } else if (statusData.status === 'FAILURE') {
    console.error('Failed:', statusData.error);
    clearInterval(pollInterval);
  } else {
    console.log('Status:', statusData.status);
  }
}, 5000); // Poll every 5 seconds
```

---

## curl Examples

### Health Check
```bash
curl https://jb-empire-api.onrender.com/api/query/health
```

### List Tools
```bash
curl https://jb-empire-api.onrender.com/api/query/tools
```

### Synchronous Query
```bash
curl -X POST https://jb-empire-api.onrender.com/api/query/adaptive \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are California insurance regulations?",
    "max_iterations": 2
  }'
```

### Asynchronous Query
```bash
# Submit
curl -X POST https://jb-empire-api.onrender.com/api/query/adaptive/async \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Research insurance regulations",
    "max_iterations": 3
  }'

# Check status (replace TASK_ID)
curl https://jb-empire-api.onrender.com/api/query/status/TASK_ID
```

---

## Best Practices

### 1. Choose the Right Endpoint

- **Sync adaptive** (`/adaptive`): Quick queries, testing
- **Sync auto** (`/auto`): Let system choose framework
- **Async adaptive** (`/adaptive/async`): Long-running, external tools
- **Async auto** (`/auto/async`): Long-running, auto-routed
- **Batch** (`/batch`): Multiple related queries

### 2. Set Appropriate Iterations

- **Simple queries**: 1-2 iterations
- **Complex queries**: 2-3 iterations
- **Research queries**: 3+ iterations (use async)

### 3. Handle Async Queries

- Store `task_id` for tracking
- Poll every 5-10 seconds
- Set timeout (e.g., 5 minutes)
- Handle FAILURE status gracefully

### 4. Monitor Usage

- Check `/health` before bulk operations
- Use `/tools` to verify Arcade.dev availability
- Monitor Celery via Flower dashboard (port 5555)

---

## Troubleshooting

### Query Returns Empty Answer
- Check if `max_iterations` is sufficient
- Verify tool availability with `/tools`
- Increase iteration count for complex queries

### Async Query Times Out
- Check Celery worker status
- Verify Redis connection
- Check Flower dashboard for task errors

### External Tools Not Working
- Verify `arcade_enabled: true` in `/health`
- Check `ARCADE_API_KEY` in environment
- Review Arcade.dev rate limits

---

## Related Documentation

- **Implementation Plan**: `.taskmaster/docs/LANGGRAPH_ARCADE_INTEGRATION_PLAN.md`
- **Langfuse Observability**: `.taskmaster/docs/LANGFUSE_INTEGRATION_PLAN.md`
- **Test Script**: `tests/test_langgraph_endpoints.py`

---

**Version**: 1.0
**Last Updated**: 2025-11-07
**Task**: #46 - LangGraph + Arcade.dev Integration
