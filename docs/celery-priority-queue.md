# Celery Priority Queue Configuration

## Overview
Empire v7.3 uses Celery with Redis for background task processing with priority queue support. Tasks can be assigned priorities from 0-9, where 9 is the highest priority.

## Priority Levels
```python
PRIORITY_URGENT = 9      # Critical tasks requiring immediate processing
PRIORITY_HIGH = 7        # User-initiated uploads (default for web UI uploads)
PRIORITY_NORMAL = 5      # Standard background processing (default)
PRIORITY_LOW = 3         # Batch operations
PRIORITY_BACKGROUND = 1  # Low-priority background jobs
```

## Configuration
Celery is configured in `app/celery_app.py` with the following priority queue settings:

```python
celery_app.conf.update(
    worker_prefetch_multiplier=1,  # Required for priority to work correctly

    broker_transport_options={
        'priority_steps': list(range(10)),  # Support priority 0-9
        'queue_order_strategy': 'priority',  # Process by priority
    },

    task_default_priority=5,  # Default priority for tasks without explicit priority
)
```

## Usage

### Submitting Tasks with Priority

Use the helper functions in `app/tasks/document_processing.py`:

```python
from app.tasks.document_processing import submit_document_processing, PRIORITY_HIGH, PRIORITY_BACKGROUND

# High priority (user upload)
submit_document_processing(
    file_id="abc123",
    filename="important.pdf",
    b2_path="pending/courses/important.pdf",
    priority=PRIORITY_HIGH
)

# Background priority (batch import)
submit_document_processing(
    file_id="xyz789",
    filename="batch.pdf",
    b2_path="pending/courses/batch.pdf",
    priority=PRIORITY_BACKGROUND
)
```

### Default Priority Behavior
- **User uploads via web UI**: `PRIORITY_HIGH` (7)
- **API uploads**: `PRIORITY_NORMAL` (5)
- **Batch imports**: `PRIORITY_LOW` (3) or `PRIORITY_BACKGROUND` (1)
- **System tasks**: `PRIORITY_NORMAL` (5)

## Task Queue Routing
Tasks are automatically routed to specialized queues:

```python
task_routes = {
    'app.tasks.document_processing.*': {'queue': 'documents'},
    'app.tasks.embedding_generation.*': {'queue': 'embeddings'},
    'app.tasks.graph_sync.*': {'queue': 'graph'},
    'app.tasks.crewai_workflows.*': {'queue': 'crewai'},
    'app.tasks.send_to_dead_letter_queue': {'queue': 'dead_letter'},
    'app.tasks.inspect_dead_letter_queue': {'queue': 'dead_letter'},
    'app.tasks.retry_from_dead_letter_queue': {'queue': 'dead_letter'}
}
```

## Dead Letter Queue (DLQ)

The Dead Letter Queue captures tasks that have failed after exhausting all retry attempts (3 retries with exponential backoff).

### How It Works

1. **Task fails** after 3 retry attempts
2. **Automatic routing**: Task failure handler detects exhausted retries
3. **DLQ entry created**: Failed task metadata sent to `dead_letter` queue
4. **Manual inspection**: Review failed tasks via `inspect_dead_letter_queue`
5. **Retry if needed**: Manually retry tasks via `retry_from_dead_letter_queue`

### DLQ Tasks

```python
# Inspect Dead Letter Queue
from app.celery_app import inspect_dead_letter_queue
result = inspect_dead_letter_queue.delay()

# Retry a failed task
from app.celery_app import retry_from_dead_letter_queue
result = retry_from_dead_letter_queue.delay(
    task_id='original-task-id',
    task_name='app.tasks.document_processing.process_document',
    args=['file_id', 'filename', 'b2_path'],
    kwargs={}
)
```

### DLQ Worker

Start a dedicated Dead Letter Queue worker:

```bash
celery -A app.celery_app worker --queues=dead_letter --concurrency=1 --loglevel=info
```

### Monitoring DLQ

Failed tasks are logged with the following format:

```json
{
  "task_id": "abc-123",
  "task_name": "app.tasks.document_processing.process_document",
  "exception": "Connection refused",
  "args": ["file_id", "filename", "b2_path"],
  "kwargs": {},
  "retries": 3,
  "max_retries": 3,
  "timestamp": "2025-11-05T22:00:00Z",
  "status": "dead_letter"
}
```

**Note**: In production, DLQ entries should be stored in a database (Supabase) for permanent tracking and analysis.

## Starting Celery Workers

### Development (Single Worker)
```bash
celery -A app.celery_app worker --loglevel=info
```

### Production (Multiple Queues)
```bash
# Document processing worker
celery -A app.celery_app worker --queues=documents --concurrency=4 --loglevel=info

# Embedding generation worker
celery -A app.celery_app worker --queues=embeddings --concurrency=2 --loglevel=info

# Graph sync worker
celery -A app.celery_app worker --queues=graph --concurrency=2 --loglevel=info

# CrewAI workflows worker
celery -A app.celery_app worker --queues=crewai --concurrency=1 --loglevel=info

# Dead Letter Queue worker
celery -A app.celery_app worker --queues=dead_letter --concurrency=1 --loglevel=info
```

### Flower Monitoring
```bash
celery -A app.celery_app flower --port=5555
```

Access at: http://localhost:5555

## Requirements
- **Redis**: Message broker (default: `redis://localhost:6379/0`)
- **Celery**: Background task processing (`celery[redis]>=5.3.6`)
- **Environment Variables**:
  ```bash
  REDIS_URL=redis://localhost:6379/0
  CELERY_RESULT_BACKEND=redis://localhost:6379/0
  ```

## Task Retry Configuration
All tasks have exponential backoff retry logic:

```python
@celery_app.task(bind=True)
def process_document(self, file_id: str, filename: str, b2_path: str):
    try:
        # Task implementation
        pass
    except Exception as e:
        # Retry with 60s delay, max 3 attempts
        self.retry(exc=e, countdown=60, max_retries=3)
```

## Monitoring Tasks

### Via Flower
1. Start Flower: `celery -A app.celery_app flower`
2. Open: http://localhost:5555
3. View:
   - Active tasks
   - Task history
   - Worker status
   - Task priority distribution

### Via Prometheus Metrics
Empire exposes Celery metrics at `/monitoring/metrics`:

```python
# Task counters
empire_celery_tasks_total{task_name="...", status="success|failure"}

# Task duration
empire_celery_task_duration_seconds{task_name="..."}
```

## Testing Priority Queues

### Quick Test (Manual)

```python
# Test script
from app.tasks.document_processing import submit_document_processing, PRIORITY_URGENT, PRIORITY_BACKGROUND

# Submit low priority task
submit_document_processing("file1", "low.pdf", "path1", priority=PRIORITY_BACKGROUND)

# Submit high priority task
submit_document_processing("file2", "high.pdf", "path2", priority=PRIORITY_URGENT)

# High priority task should be processed first
```

### Comprehensive End-to-End Testing

Empire v7.3 includes a comprehensive test suite for validating the entire Celery priority queue system.

#### Prerequisites

Before running tests, ensure the following services are running:
- **Redis** (port 6379) - Message broker
- **Celery Worker** - Background task processor
- **Supabase** (optional) - For status tracking tests

#### Quick Start

```bash
# 1. Start test environment (Redis + Celery + Flower)
./start_celery_test_env.sh

# 2. Run end-to-end tests
python3 test_celery_priority_queue.py

# 3. Monitor tasks in real-time (optional)
tail -f logs/celery_worker.log

# 4. View tasks in Flower UI (optional)
open http://localhost:5555

# 5. Stop test environment when done
./stop_celery_test_env.sh
```

#### Test Coverage

The test suite validates:

1. **Priority Queue Ordering**
   - Submits tasks with varying priorities (URGENT, HIGH, NORMAL, LOW, BACKGROUND)
   - Verifies tasks are processed in correct priority order
   - Confirms high-priority tasks preempt low-priority tasks

2. **Supabase Status Tracking**
   - Tests status updates at key task stages
   - Validates status transitions (uploaded → processing → processed/failed)
   - Confirms database updates are atomic

3. **Retry Logic with Exponential Backoff**
   - Validates retry configuration (3 attempts max)
   - Confirms exponential backoff delays (60s → 120s → 240s)
   - Tests task binding and retry method availability

4. **Dead Letter Queue (DLQ)**
   - Verifies DLQ tasks are registered
   - Tests DLQ inspection functionality
   - Validates failed task routing after retry exhaustion

#### Expected Test Output

```
=============================================================
CELERY PRIORITY QUEUE - END-TO-END TESTS
=============================================================

TEST: Priority Queue Ordering
--------------------------------------------------------------
Submitting tasks with different priorities...
  → Submitted BACKGROUND priority task: abc-123
  → Submitted HIGH priority task: def-456
  → Submitted URGENT priority task: ghi-789
  → Submitted NORMAL priority task: jkl-012

✅ Successfully submitted 4 tasks with varying priorities

Expected processing order (highest priority first):
  1. urgent.pdf (priority 9)
  2. high.pdf (priority 7)
  3. normal.pdf (priority 5)
  4. background.pdf (priority 1)

✅ PASSED: Priority Ordering

=============================================================
TEST SUMMARY
=============================================================

Total Tests: 8
  ✅ Passed: 8
  ❌ Failed: 0

🎉 ALL TESTS PASSED!
=============================================================
```

#### Manual Testing Scenarios

**Test Scenario 1: Priority Ordering**
```bash
# Start worker with debug logging
celery -A app.celery_app worker --loglevel=debug

# In another terminal, submit tasks
python3 -c "
from app.tasks.document_processing import submit_document_processing, PRIORITY_URGENT, PRIORITY_BACKGROUND
submit_document_processing('file1', 'low.pdf', 'path1', priority=1)
submit_document_processing('file2', 'high.pdf', 'path2', priority=9)
"

# Observe logs - high.pdf should process first
```

**Test Scenario 2: Retry Logic**
```python
# Create a task that always fails
from app.celery_app import celery_app

@celery_app.task(bind=True)
def failing_task(self):
    # This will trigger retry logic
    raise Exception("Test failure for retry")

# Submit and watch logs for retry attempts
failing_task.delay()
```

**Test Scenario 3: Dead Letter Queue**
```python
# After a task exhausts all retries (Scenario 2)
from app.celery_app import inspect_dead_letter_queue

# Inspect DLQ for failed task
result = inspect_dead_letter_queue.delay()
print(result.get())
```

## Best Practices

1. **User-facing operations**: Use `PRIORITY_HIGH` (7) or `PRIORITY_URGENT` (9)
2. **Background batch jobs**: Use `PRIORITY_LOW` (3) or `PRIORITY_BACKGROUND` (1)
3. **System maintenance**: Use `PRIORITY_NORMAL` (5)
4. **Avoid overusing URGENT**: Reserve priority 9 for truly critical tasks
5. **Monitor queue depth**: Use Flower to ensure tasks aren't backing up

## Troubleshooting

### Tasks not processing in priority order
- Verify `worker_prefetch_multiplier=1` is set
- Check `broker_transport_options` configuration
- Ensure Redis broker is running

### Worker not picking up tasks
```bash
# Check Redis connection
redis-cli ping

# Check Celery worker logs
celery -A app.celery_app worker --loglevel=debug

# Inspect active tasks
celery -A app.celery_app inspect active
```

### High memory usage
- Adjust `worker_max_tasks_per_child` (default: 100)
- Reduce `concurrency` setting
- Monitor with: `celery -A app.celery_app inspect stats`
