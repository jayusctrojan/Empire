# Empire v7.3 - REST Status Polling API

**Task 11**: Create REST Status Endpoint and Polling Logic

## Overview

The Status Polling API provides REST endpoints for checking processing status as a fallback to WebSocket connections. This is useful when:

- WebSocket connections are blocked by proxies/firewalls
- Client needs simple HTTP-based polling
- Batch status checks are required
- Debugging or testing without WebSocket client

## Base URL

```
/api/status
```

## Authentication

All endpoints require authentication via Clerk JWT token:

```http
Authorization: Bearer <clerk_jwt_token>
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Individual status (`/task/*`, `/document/*`, `/batch/*`) | 60 requests/minute |
| Batch check (`/batch-check`) | 30 requests/minute |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Endpoints

### 1. Get Task Status

Poll status for Celery async tasks (queries, batch operations, etc.).

**Endpoint**: `GET /api/status/task/{task_id}`

**Request**:
```bash
curl -X GET "https://jb-empire-api.onrender.com/api/status/task/abc123-def456" \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

**Response**:
```json
{
  "resource_id": "abc123-def456",
  "resource_type": "task",
  "status": "processing",
  "status_message": "Task is currently processing",
  "progress": {
    "current": 2,
    "total": 3,
    "percentage": 66.67,
    "message": "Iteration 2 of 3",
    "stage": "search",
    "stage_details": {
      "documents_found": 15
    }
  },
  "created_at": null,
  "updated_at": "2025-01-15T10:30:45Z",
  "completed_at": null,
  "result": null,
  "error": null,
  "poll_interval_ms": 2000,
  "should_continue_polling": true
}
```

**Status Values**:
- `pending` - Task waiting to start
- `started` - Task is currently processing
- `success` - Task completed successfully
- `failure` - Task failed

---

### 2. Get Document Status

Poll status for document upload/processing.

**Endpoint**: `GET /api/status/document/{document_id}`

**Request**:
```bash
curl -X GET "https://jb-empire-api.onrender.com/api/status/document/doc-789" \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

**Response**:
```json
{
  "resource_id": "doc-789",
  "resource_type": "document",
  "status": "processing",
  "status_message": "Processing: text_extraction",
  "progress": {
    "current": 45,
    "total": 100,
    "percentage": 45.0,
    "message": "Page 5 of 11",
    "stage": "text_extraction"
  },
  "created_at": "2025-01-15T10:25:00Z",
  "updated_at": "2025-01-15T10:30:45Z",
  "completed_at": null,
  "metadata": {
    "filename": "report.pdf",
    "size_bytes": 1048576
  },
  "poll_interval_ms": 2000,
  "should_continue_polling": true
}
```

**Document Processing Stages**:
- `uploading` - File being uploaded
- `parsing` - Document being parsed
- `text_extraction` - Text being extracted
- `embedding` - Generating embeddings
- `indexing` - Adding to search index
- `completed` - Processing complete

---

### 3. Get Batch Operation Status

Poll status for bulk operations (bulk upload, bulk delete, etc.).

**Endpoint**: `GET /api/status/batch/{operation_id}`

**Request**:
```bash
curl -X GET "https://jb-empire-api.onrender.com/api/status/batch/op-456" \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

**Response**:
```json
{
  "resource_id": "op-456",
  "resource_type": "batch_operation",
  "status": "processing",
  "status_message": "Batch operation processing",
  "progress": {
    "current": 35,
    "total": 100,
    "percentage": 35.0,
    "message": "Processed 35 of 100 items",
    "stage": "bulk_upload"
  },
  "created_at": "2025-01-15T10:20:00Z",
  "updated_at": "2025-01-15T10:30:45Z",
  "completed_at": null,
  "metadata": {
    "operation_type": "bulk_upload",
    "successful_items": 32,
    "failed_items": 3
  },
  "poll_interval_ms": 2000,
  "should_continue_polling": true
}
```

---

### 4. Batch Status Check

Check status of multiple resources in a single request.

**Endpoint**: `POST /api/status/batch-check`

**Query Parameters**:
- `resource_ids[]` - Array of resource IDs (max 50)
- `resource_type` - Type of resources: `task`, `document`, `batch_operation`

**Request**:
```bash
curl -X POST "https://jb-empire-api.onrender.com/api/status/batch-check?resource_ids=task1&resource_ids=task2&resource_ids=task3&resource_type=task" \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

**Response**:
```json
{
  "statuses": [
    {
      "resource_id": "task1",
      "resource_type": "task",
      "status": "success",
      "status_message": "Task success",
      "result": {"answer": "..."},
      "poll_interval_ms": 0,
      "should_continue_polling": false
    },
    {
      "resource_id": "task2",
      "resource_type": "task",
      "status": "processing",
      "status_message": "Task processing",
      "poll_interval_ms": 2000,
      "should_continue_polling": true
    }
  ],
  "total_count": 3,
  "found_count": 2,
  "timestamp": "2025-01-15T10:30:45Z"
}
```

---

### 5. Health Check

Check status service health.

**Endpoint**: `GET /api/status/health`

**Response**:
```json
{
  "status": "healthy",
  "service": "status_polling",
  "capabilities": [
    "task_status",
    "document_status",
    "batch_operation_status",
    "batch_check"
  ],
  "rate_limits": {
    "individual_status": "60/minute",
    "batch_check": "30/minute"
  },
  "websocket_fallback": true,
  "timestamp": "2025-01-15T10:30:45Z"
}
```

---

## Response Schema

All status endpoints return the `StatusResponse` schema:

```typescript
interface StatusResponse {
  // Resource identification
  resource_id: string;      // ID of the resource
  resource_type: string;    // "task" | "document" | "batch_operation"

  // Status information
  status: string;           // Current processing status
  status_message: string;   // Human-readable message

  // Progress tracking
  progress?: {
    current: number;        // Current progress value
    total: number;          // Total progress value
    percentage: number;     // Progress percentage (0-100)
    message: string;        // Current status message
    stage?: string;         // Current processing stage
    stage_details?: object; // Stage-specific details
  };

  // Timestamps
  created_at?: string;      // ISO 8601 timestamp
  updated_at?: string;      // ISO 8601 timestamp
  completed_at?: string;    // ISO 8601 timestamp

  // Result data (only on completion)
  result?: object;          // Result data when completed
  error?: string;           // Error message when failed
  error_details?: object;   // Detailed error information

  // Metadata
  metadata?: object;        // Additional resource metadata

  // Polling hints
  poll_interval_ms: number;       // Recommended poll interval
  should_continue_polling: boolean; // Whether to continue polling
}
```

---

## Frontend Integration

### Using the JavaScript Polling Utility

Include the status poller script:

```html
<script src="/static/js/status-poller.js"></script>
```

#### Basic Usage

```javascript
// Create a poller instance
const poller = new EmpireStatus.StatusPoller({
  baseUrl: '/api/status',
  wsBaseUrl: 'wss://jb-empire-api.onrender.com/ws'
});

// Start polling for a task
const pollerId = poller.startPolling('task-123', 'task', {
  onStatus: (status) => {
    console.log('Status update:', status);
    updateUI(status);
  },
  onProgress: (progress) => {
    updateProgressBar(progress.percentage);
  },
  onComplete: (data) => {
    console.log('Task completed:', data.result);
    showResults(data.result);
  },
  onError: (error, retryCount) => {
    console.error(`Error (attempt ${retryCount}):`, error);
  }
});

// Stop polling when done
poller.stopPolling(pollerId);
```

#### Poll Once (No Subscription)

```javascript
// Get status once without subscribing
const status = await poller.pollOnce('doc-456', 'document');
console.log('Document status:', status);
```

#### Batch Polling

```javascript
// Check multiple tasks at once
const results = await poller.batchPoll(
  ['task1', 'task2', 'task3'],
  'task'
);

results.statuses.forEach(status => {
  console.log(`${status.resource_id}: ${status.status}`);
});
```

#### Wait for Completion

```javascript
// Wait for a task to complete (with timeout)
try {
  const result = await EmpireStatus.waitForCompletion(
    poller,
    'task-123',
    'task',
    60000  // 60 second timeout
  );
  console.log('Final result:', result);
} catch (error) {
  console.error('Timeout or error:', error);
}
```

#### Progress Bar Helper

```javascript
// Create a progress bar element
const progressBar = EmpireStatus.createProgressBar({
  percentage: 45,
  message: 'Processing page 5 of 11...'
});

document.getElementById('progress-container').appendChild(progressBar);
```

#### Format Status for Display

```javascript
// Get formatted status with icon and color
const formatted = EmpireStatus.formatStatus(statusData);

console.log(formatted.icon);    // '🔄'
console.log(formatted.color);   // '#3b82f6'
console.log(formatted.label);   // 'Processing'
console.log(formatted.message); // 'Processing page 5...'
```

---

## WebSocket vs REST Comparison

| Feature | WebSocket | REST Polling |
|---------|-----------|--------------|
| Real-time updates | Immediate | Depends on poll interval |
| Network efficiency | More efficient | Higher overhead |
| Connection maintenance | Requires keep-alive | Stateless |
| Firewall/proxy support | May be blocked | Usually allowed |
| Load on server | Lower | Higher with frequent polls |
| Complexity | Higher | Lower |

### Recommended Strategy

1. **Try WebSocket first** - Use `/ws/document/{id}` or `/ws/query/{id}`
2. **Fall back to REST** - If WebSocket fails, use `/api/status/*` endpoints
3. **Respect poll_interval_ms** - Server recommends optimal polling frequency
4. **Stop when should_continue_polling is false** - Don't poll after completion

---

## Error Handling

### Rate Limit Exceeded (429)

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": "60 seconds",
  "path": "/api/status/task/abc123"
}
```

### Resource Not Found (404)

```json
{
  "detail": "Document doc-999 not found"
}
```

### Server Error (500)

```json
{
  "detail": "Failed to check task status: Connection error"
}
```

---

## Best Practices

1. **Use batch-check for multiple resources** - More efficient than individual requests
2. **Respect poll_interval_ms** - Server adjusts based on processing state
3. **Handle terminal states** - Stop polling when `should_continue_polling` is `false`
4. **Implement exponential backoff** - On errors, increase poll interval
5. **Set request timeouts** - Don't wait indefinitely for responses
6. **Cache completed statuses** - Don't re-poll completed tasks

---

## Related Documentation

- [WebSocket Real-Time Status](./WEBSOCKET_STATUS.md)
- [Async Query Processing](./ASYNC_QUERIES.md)
- [Bulk Document Operations](./BULK_OPERATIONS.md)
- [API Authentication](./AUTHENTICATION.md)

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-25 | 1.0 | Initial documentation (Task 11) |
