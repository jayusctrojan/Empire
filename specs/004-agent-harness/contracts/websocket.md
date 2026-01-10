# WebSocket Protocol: Research Projects Progress

**Endpoint**: `wss://jb-empire-api.onrender.com/api/research-projects/ws/{projectId}`

## Connection

### Authentication

Include JWT token in connection request:
```javascript
const ws = new WebSocket(
  `wss://api.example.com/api/research-projects/ws/${projectId}`,
  ['authorization', `Bearer ${token}`]
);
```

### Connection Lifecycle

1. Client connects with project ID
2. Server validates JWT and project ownership
3. Server sends current state immediately
4. Server streams updates as they occur
5. Client can disconnect/reconnect anytime

---

## Message Types

### Server → Client Messages

All messages follow this envelope:

```json
{
  "type": "message_type",
  "data": { ... },
  "timestamp": "2025-01-10T12:00:00Z"
}
```

---

### `project_status`

Sent immediately on connection and when project status changes.

```json
{
  "type": "project_status",
  "data": {
    "job_id": 123,
    "status": "executing",
    "total_tasks": 8,
    "completed_tasks": 3,
    "progress_percentage": 37.5,
    "current_task_key": "retrieval_rag_1"
  },
  "timestamp": "2025-01-10T12:00:00Z"
}
```

---

### `task_started`

Sent when a task begins execution.

```json
{
  "type": "task_started",
  "data": {
    "job_id": 123,
    "task_key": "retrieval_rag_1",
    "task_type": "retrieval_rag",
    "task_title": "Search for policy documents",
    "sequence_order": 1
  },
  "timestamp": "2025-01-10T12:00:05Z"
}
```

---

### `task_completed`

Sent when a task finishes successfully.

```json
{
  "type": "task_completed",
  "data": {
    "job_id": 123,
    "task_key": "retrieval_rag_1",
    "task_type": "retrieval_rag",
    "result_summary": "Retrieved 15 relevant document chunks",
    "duration_seconds": 12,
    "artifacts_count": 15,
    "quality_score": 0.85
  },
  "timestamp": "2025-01-10T12:00:17Z"
}
```

---

### `task_failed`

Sent when a task fails.

```json
{
  "type": "task_failed",
  "data": {
    "job_id": 123,
    "task_key": "retrieval_api_1",
    "task_type": "retrieval_api",
    "error_message": "API timeout after 30 seconds",
    "retry_count": 2,
    "will_retry": false
  },
  "timestamp": "2025-01-10T12:01:00Z"
}
```

---

### `wave_completed`

Sent when a parallel execution wave finishes.

```json
{
  "type": "wave_completed",
  "data": {
    "job_id": 123,
    "wave_number": 1,
    "tasks_completed": 3,
    "tasks_failed": 0,
    "wave_duration_seconds": 15,
    "next_wave_tasks": ["synthesis_1", "synthesis_2"]
  },
  "timestamp": "2025-01-10T12:00:20Z"
}
```

---

### `project_complete`

Sent when all tasks finish and report is ready.

```json
{
  "type": "project_complete",
  "data": {
    "job_id": 123,
    "status": "complete",
    "total_duration_seconds": 95,
    "report_url": "https://b2.example.com/reports/123.md",
    "summary": "Research complete. Found 5 key findings.",
    "key_findings": [
      "Finding 1...",
      "Finding 2..."
    ]
  },
  "timestamp": "2025-01-10T12:01:35Z"
}
```

---

### `project_failed`

Sent when project fails unrecoverably.

```json
{
  "type": "project_failed",
  "data": {
    "job_id": 123,
    "status": "failed",
    "error_message": "Critical task failed after 3 retries",
    "partial_results_available": true
  },
  "timestamp": "2025-01-10T12:02:00Z"
}
```

---

### `project_cancelled`

Sent when user cancels the project.

```json
{
  "type": "project_cancelled",
  "data": {
    "job_id": 123,
    "status": "cancelled",
    "tasks_completed": 5,
    "tasks_cancelled": 3
  },
  "timestamp": "2025-01-10T12:02:30Z"
}
```

---

## Client → Server Messages

### `ping`

Keep-alive message (optional, server handles timeouts).

```json
{
  "type": "ping"
}
```

Server responds with:

```json
{
  "type": "pong",
  "timestamp": "2025-01-10T12:03:00Z"
}
```

---

## Error Handling

### Connection Errors

| Code | Reason | Action |
|------|--------|--------|
| 1000 | Normal close | Project complete/cancelled |
| 1008 | Policy violation | Invalid JWT or not project owner |
| 1011 | Server error | Reconnect with backoff |

### Reconnection Strategy

```javascript
const reconnect = (attempt = 1) => {
  const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
  setTimeout(() => {
    connect();
  }, delay);
};
```

---

## Example Client Implementation

```javascript
class ResearchProjectSocket {
  constructor(projectId, token) {
    this.projectId = projectId;
    this.token = token;
    this.ws = null;
    this.handlers = {};
  }

  connect() {
    this.ws = new WebSocket(
      `wss://api.example.com/api/research-projects/ws/${this.projectId}`,
      ['authorization', `Bearer ${this.token}`]
    );

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const handler = this.handlers[message.type];
      if (handler) {
        handler(message.data);
      }
    };

    this.ws.onclose = (event) => {
      if (event.code !== 1000) {
        this.reconnect();
      }
    };
  }

  on(type, handler) {
    this.handlers[type] = handler;
  }

  reconnect(attempt = 1) {
    const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
    setTimeout(() => this.connect(), delay);
  }
}

// Usage
const socket = new ResearchProjectSocket(123, 'jwt-token');

socket.on('project_status', (data) => {
  updateProgressBar(data.progress_percentage);
});

socket.on('task_completed', (data) => {
  addCompletedTask(data);
});

socket.on('project_complete', (data) => {
  showReport(data.report_url);
});

socket.connect();
```
