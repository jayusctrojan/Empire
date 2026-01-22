# WebSocket Real-Time Status Guide - Task 10

## Overview

Empire v7.3 includes a comprehensive WebSocket implementation for real-time status updates during document processing and query execution. The system supports distributed broadcasting across multiple server instances using Redis Pub/Sub.

## Features

- **Real-time task updates** - Celery tasks automatically broadcast status changes
- **Distributed broadcasting** - Messages reach clients across all server instances via Redis Pub/Sub
- **Resource-based routing** - Clients can subscribe to specific documents, queries, or users
- **Production monitoring** - Prometheus metrics for all WebSocket operations
- **Graceful degradation** - Works with or without Redis

## Architecture

```
Client (Browser/App)
  ↓ WebSocket Connection
FastAPI WebSocket Endpoint (/ws/*)
  ↓
ConnectionManager
  ↓ Local + Redis Pub/Sub
All Server Instances
  ↓
Connected Clients Receive Updates
```

### Distributed Broadcasting with Redis Pub/Sub

When Redis is available, messages are published to Redis channels, allowing all server instances to receive and forward messages to their local WebSocket connections. This enables horizontal scaling while maintaining real-time updates.

**Channels:**
- `empire:websocket:broadcast` - General broadcast to all connections
- `empire:websocket:document:{document_id}` - Document-specific updates
- `empire:websocket:query:{query_id}` - Query-specific updates

## WebSocket Endpoints

### 1. General Notifications: `WS /ws/notifications`

Connect to receive general real-time notifications.

**URL**: `ws://localhost:8000/ws/notifications`

**Query Parameters:**
- `session_id` (optional) - Session identifier for session-based routing
- `user_id` (optional) - User identifier for user-based routing

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications?session_id=abc123&user_id=user456');

ws.onopen = () => {
    console.log('Connected to notifications');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);

    // Handle different message types
    switch(data.type) {
        case 'task_event':
            handleTaskEvent(data);
            break;
        case 'pong':
            console.log('Keepalive response');
            break;
    }
};

// Send ping for keepalive
setInterval(() => {
    ws.send(JSON.stringify({type: 'ping'}));
}, 30000);
```

### 2. Document Status: `WS /ws/document/{document_id}`

Subscribe to updates for a specific document during processing.

**URL**: `ws://localhost:8000/ws/document/{document_id}`

**Query Parameters:**
- `session_id` (optional)
- `user_id` (optional)

**Example (Python):**
```python
import asyncio
import websockets
import json

async def monitor_document(document_id):
    uri = f"ws://localhost:8000/ws/document/{document_id}"

    async with websockets.connect(uri) as websocket:
        # Receive subscription confirmation
        confirmation = await websocket.recv()
        print(f"Subscribed: {confirmation}")

        # Listen for document updates
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data.get('type') == 'task_event':
                task_name = data.get('task_name')
                status = data.get('status')
                progress = data.get('progress', 0)
                message_text = data.get('message')

                print(f"[{task_name}] {status} - {progress}%: {message_text}")

                if status == 'success':
                    print("Document processing completed!")
                    break

asyncio.run(monitor_document('doc_123'))
```

### 3. Query Status: `WS /ws/query/{query_id}`

Subscribe to updates for a specific query during execution.

**URL**: `ws://localhost:8000/ws/query/{query_id}`

**Query Parameters:**
- `session_id` (optional)
- `user_id` (optional)

**Example (JavaScript with React):**
```javascript
import { useEffect, useState } from 'react';

function QueryMonitor({ queryId }) {
    const [status, setStatus] = useState('connecting');
    const [progress, setProgress] = useState(0);
    const [message, setMessage] = useState('');

    useEffect(() => {
        const ws = new WebSocket(`ws://localhost:8000/ws/query/${queryId}`);

        ws.onopen = () => setStatus('connected');

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'task_event') {
                setProgress(data.progress || 0);
                setMessage(data.message);

                if (data.status === 'success') {
                    setStatus('completed');
                } else if (data.status === 'failure') {
                    setStatus('failed');
                }
            }
        };

        ws.onerror = () => setStatus('error');
        ws.onclose = () => setStatus('disconnected');

        return () => ws.close();
    }, [queryId]);

    return (
        <div>
            <h3>Query Status: {status}</h3>
            <progress value={progress} max="100" />
            <p>{message}</p>
        </div>
    );
}
```

### 4. Connection Statistics: `GET /ws/stats`

Get current WebSocket connection statistics.

**URL**: `http://localhost:8000/ws/stats`

**Response:**
```json
{
    "active_connections": 15,
    "session_count": 8,
    "user_count": 5,
    "document_subscriptions": 3,
    "query_subscriptions": 2,
    "redis_enabled": true
}
```

## Message Format

### Task Event Messages

All task events follow this structure:

```json
{
    "type": "task_event",
    "task_id": "abc-123-def-456",
    "task_name": "process_adaptive_query",
    "status": "progress",
    "message": "Processing query with LangGraph workflow",
    "progress": 30,
    "timestamp": "2025-01-24T10:30:00.000Z",
    "metadata": {
        "stage": "processing",
        "iteration": 2,
        "max_iterations": 3
    }
}
```

**Fields:**
- `type` - Message type (always "task_event" for Celery tasks)
- `task_id` - Celery task identifier
- `task_name` - Task name (e.g., "process_document", "embedding_generation")
- `status` - Task status: `started`, `progress`, `success`, `failure`
- `message` - Human-readable status message
- `progress` - Progress percentage (0-100), optional
- `timestamp` - ISO 8601 timestamp
- `metadata` - Additional task-specific data, optional

### Status Values

- **`started`** - Task has begun execution
- **`progress`** - Task is in progress (may include progress percentage)
- **`success`** - Task completed successfully
- **`failure`** - Task failed (includes error information in metadata)

### Example Messages by Task Type

#### Document Processing

```json
{
    "type": "task_event",
    "task_id": "doc-task-123",
    "task_name": "document_processing",
    "status": "progress",
    "message": "Parsing document",
    "progress": 25,
    "metadata": {
        "stage": "parsing",
        "chunks": 10
    }
}
```

#### Query Processing

```json
{
    "type": "task_event",
    "task_id": "query-task-456",
    "task_name": "query_processing",
    "status": "progress",
    "message": "Iteration 2/3: Searching knowledge base",
    "progress": 66,
    "metadata": {
        "stage": "searching",
        "iteration": 2,
        "max_iterations": 3
    }
}
```

#### Embedding Generation

```json
{
    "type": "task_event",
    "task_id": "embed-task-789",
    "task_name": "embedding_generation",
    "status": "progress",
    "message": "Generating embeddings with BGE-M3",
    "progress": 60,
    "metadata": {
        "chunks_processed": 60,
        "total_chunks": 100,
        "model": "bge-m3"
    }
}
```

## Integration with Celery Tasks

### Automatic Notifications via Signal Handlers

Celery tasks automatically send WebSocket notifications through signal handlers configured in `app/celery_app.py`:

- **`task_prerun`** - Sends "started" notification when task begins
- **`task_postrun`** - Sends "success" notification when task completes
- **`task_failure`** - Sends "failure" notification when task fails

### Manual Notifications from Tasks

Tasks can send custom progress updates using helper functions from `app/utils/websocket_notifications.py`:

```python
from app.celery_app import celery_app
from app.utils.websocket_notifications import send_query_processing_update

@celery_app.task(name="my_custom_query_task", bind=True)
def my_custom_query_task(self, query: str, user_id: str):
    # Send initialization update
    send_query_processing_update(
        task_id=self.request.id,
        query_id=self.request.id,
        stage="initialization",
        status="started",
        message="Starting query processing",
        progress=10,
        user_id=user_id
    )

    # Perform work...
    process_query_step_1()

    # Send progress update
    send_query_processing_update(
        task_id=self.request.id,
        query_id=self.request.id,
        stage="processing",
        status="progress",
        message="Processing query",
        progress=50,
        user_id=user_id
    )

    # More work...
    result = process_query_step_2()

    # Send completion update
    send_query_processing_update(
        task_id=self.request.id,
        query_id=self.request.id,
        stage="completed",
        status="success",
        message="Query processing completed",
        progress=100,
        metadata={"result": result},
        user_id=user_id
    )

    return result
```

### Available Helper Functions

#### 1. Generic Task Notification
```python
from app.utils.websocket_notifications import send_task_notification

send_task_notification(
    task_id="task_123",
    task_name="my_task",
    status="progress",
    message="Task is running",
    progress=50,
    metadata={"custom": "data"},
    document_id="doc_123",  # Optional
    query_id="query_456",   # Optional
    user_id="user_789",     # Optional
    session_id="session_abc" # Optional
)
```

#### 2. Document Processing Update
```python
from app.utils.websocket_notifications import send_document_processing_update

send_document_processing_update(
    task_id="task_123",
    document_id="doc_123",
    stage="embedding",
    status="progress",
    message="Generating embeddings",
    progress=60,
    metadata={"chunks_completed": 60, "total_chunks": 100}
)
```

#### 3. Query Processing Update
```python
from app.utils.websocket_notifications import send_query_processing_update

send_query_processing_update(
    task_id="task_456",
    query_id="query_456",
    stage="searching",
    status="progress",
    message="Searching knowledge base",
    progress=75,
    user_id="user_789"
)
```

#### 4. Embedding Generation Update
```python
from app.utils.websocket_notifications import send_embedding_generation_update

send_embedding_generation_update(
    task_id="task_789",
    document_id="doc_123",
    status="progress",
    message="Generating embeddings with BGE-M3",
    progress=80,
    chunks_processed=80,
    total_chunks=100,
    model="bge-m3"
)
```

#### 5. Graph Sync Update
```python
from app.utils.websocket_notifications import send_graph_sync_update

send_graph_sync_update(
    task_id="task_abc",
    document_id="doc_123",
    status="success",
    message="Graph sync completed",
    progress=100,
    entities_created=15,
    relationships_created=23
)
```

## Redis Pub/Sub Configuration

### Environment Variables

```bash
# Redis connection (required for distributed broadcasting)
REDIS_URL=rediss://default:<token>@enhanced-manatee-37521.upstash.io:6379

# Note: Use 'rediss://' for TLS, 'redis://' for non-TLS
```

### Graceful Fallback

If Redis is unavailable:
- WebSocket system continues to work with local-only broadcasting
- Messages only reach clients connected to the same server instance
- Startup logs will show: "WebSocket manager initialized (local-only broadcasting - Redis unavailable)"

### Testing Redis Connection

```python
from app.services.redis_pubsub_service import RedisPubSubService

async def test_redis():
    service = RedisPubSubService()
    try:
        await service.connect()
        print("✅ Redis Pub/Sub connected")
        await service.disconnect()
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
```

## Monitoring and Metrics

### Prometheus Metrics

All WebSocket operations are tracked with Prometheus metrics:

**Connection Metrics:**
- `empire_websocket_connections_total{connection_type}` - Total connections established
- `empire_websocket_active_connections{connection_type}` - Currently active connections
- `empire_websocket_disconnections_total{reason}` - Total disconnections by reason

**Message Metrics:**
- `empire_websocket_messages_sent_total{message_type}` - Total messages sent
- `empire_websocket_messages_failed_total{error_type}` - Failed message sends
- `empire_websocket_message_latency_seconds{message_type}` - Message send latency

**Redis Pub/Sub Metrics:**
- `empire_pubsub_messages_published_total{channel_type}` - Messages published to Redis
- `empire_pubsub_messages_received_total{channel_type}` - Messages received from Redis
- `empire_pubsub_active_subscriptions` - Active Redis channel subscriptions

### Viewing Metrics

Access metrics at: `http://localhost:8000/monitoring/metrics`

Example Prometheus queries:
```promql
# Connection rate per minute
rate(empire_websocket_connections_total[1m])

# Average message latency
histogram_quantile(0.95, rate(empire_websocket_message_latency_seconds_bucket[5m]))

# Redis pub/sub throughput
rate(empire_pubsub_messages_published_total[1m])
```

## Security Considerations

### Authentication

WebSocket endpoints currently accept optional `user_id` and `session_id` parameters. For production:

1. **Add authentication middleware** to verify user identity
2. **Validate session tokens** before establishing WebSocket connections
3. **Implement RLS checks** to ensure users only receive their own data

### Rate Limiting

Consider implementing WebSocket-specific rate limiting:
- Limit connections per IP address
- Limit message frequency per connection
- Disconnect abusive clients

### Message Filtering

Always filter messages server-side based on user permissions:
```python
# Example: Only send document updates if user has access
if user_has_access(user_id, document_id):
    await manager.send_to_document(message, document_id)
```

## Production Deployment

### Load Balancing

WebSocket connections are sticky - ensure your load balancer uses:
- **Session affinity** (sticky sessions)
- **Source IP hashing**
- **Cookie-based routing**

This ensures clients reconnect to the same server instance.

### Scaling with Redis Pub/Sub

Redis Pub/Sub enables horizontal scaling:
1. Deploy multiple FastAPI instances behind a load balancer
2. All instances connect to the same Redis server
3. Messages published on any instance reach all connected clients
4. Scale up/down server instances as needed

### Health Checks

WebSocket endpoints are monitored through:
- `/health` - Basic health check
- `/health/detailed` - Includes WebSocket manager status
- `/ws/stats` - Real-time connection statistics

### Logging

All WebSocket operations are logged with `structlog`:
```
logger.info(
    "websocket_notifications_connected",
    connection_id=connection_id,
    user_id=user_id
)
```

Filter logs in production:
```bash
# View WebSocket-specific logs
grep "websocket_" empire.log

# Monitor connection events
grep "websocket.*connected\|disconnected" empire.log
```

## Troubleshooting

### WebSocket Connection Fails

**Symptoms**: Client cannot establish WebSocket connection

**Checks**:
1. Verify server is running: `curl http://localhost:8000/health`
2. Test WebSocket endpoint: Use browser DevTools Network tab
3. Check CORS configuration in `app/main.py`
4. Verify firewall/proxy allows WebSocket protocol

### Messages Not Received

**Symptoms**: WebSocket connected but no messages received

**Checks**:
1. Verify client is subscribed to correct resource
2. Check Celery tasks are running: `celery -A app.celery_app inspect active`
3. Confirm Redis connection (if using distributed broadcasting)
4. Review server logs for errors

### Redis Pub/Sub Not Working

**Symptoms**: Messages only received on same server instance

**Checks**:
1. Verify `REDIS_URL` environment variable is set
2. Test Redis connection: `redis-cli -u $REDIS_URL ping`
3. Check startup logs for Redis initialization
4. Review `empire_pubsub_*` Prometheus metrics

### High Latency

**Symptoms**: Delayed message delivery

**Checks**:
1. Check Prometheus message latency metrics
2. Monitor Redis performance
3. Review server CPU/memory usage
4. Consider scaling horizontally

## Examples

### Full Example: Document Upload with Real-Time Status

**Frontend (React):**
```jsx
import { useEffect, useState } from 'react';

function DocumentUpload() {
    const [file, setFile] = useState(null);
    const [documentId, setDocumentId] = useState(null);
    const [status, setStatus] = useState('idle');
    const [progress, setProgress] = useState(0);
    const [message, setMessage] = useState('');

    const handleUpload = async () => {
        // Upload file
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/v1/upload', {
            method: 'POST',
            body: formData
        });

        const { document_id } = await response.json();
        setDocumentId(document_id);
    };

    useEffect(() => {
        if (!documentId) return;

        const ws = new WebSocket(`ws://localhost:8000/ws/document/${documentId}`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'task_event') {
                setStatus(data.status);
                setProgress(data.progress || 0);
                setMessage(data.message);

                if (data.metadata?.stage) {
                    console.log(`Stage: ${data.metadata.stage}`);
                }
            }
        };

        return () => ws.close();
    }, [documentId]);

    return (
        <div>
            <input type="file" onChange={(e) => setFile(e.target.files[0])} />
            <button onClick={handleUpload}>Upload</button>

            {documentId && (
                <div>
                    <h3>Processing: {status}</h3>
                    <progress value={progress} max="100" />
                    <p>{message}</p>
                </div>
            )}
        </div>
    );
}
```

**Backend (Celery Task):**
```python
from app.celery_app import celery_app
from app.utils.websocket_notifications import send_document_processing_update

@celery_app.task(name="process_document_with_updates", bind=True)
def process_document_with_updates(self, document_id: str, file_path: str):
    # Parsing stage
    send_document_processing_update(
        task_id=self.request.id,
        document_id=document_id,
        stage="parsing",
        status="progress",
        message="Parsing document",
        progress=25
    )
    chunks = parse_document(file_path)

    # Embedding stage
    send_document_processing_update(
        task_id=self.request.id,
        document_id=document_id,
        stage="embedding",
        status="progress",
        message="Generating embeddings",
        progress=50
    )
    embeddings = generate_embeddings(chunks)

    # Indexing stage
    send_document_processing_update(
        task_id=self.request.id,
        document_id=document_id,
        stage="indexing",
        status="progress",
        message="Indexing in vector database",
        progress=75
    )
    index_vectors(embeddings)

    # Completion
    send_document_processing_update(
        task_id=self.request.id,
        document_id=document_id,
        stage="completed",
        status="success",
        message="Document processing completed",
        progress=100
    )

    return {"document_id": document_id, "status": "success"}
```

## API Reference

See `app/services/websocket_manager.py` for complete API documentation.

## Support

For issues or questions:
1. Check server logs for errors
2. Review Prometheus metrics
3. Test with provided example code
4. Consult Empire v7.3 documentation

---

**Version**: 1.0
**Last Updated**: 2025-01-24
**Task**: 10 - WebSocket Real-Time Processing Status
