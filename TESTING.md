# Empire v7.3 - Celery Priority Queue Testing Guide

## Overview

This guide covers end-to-end testing of the Celery priority queue system, including priority ordering, status tracking, retry logic, and Dead Letter Queue functionality.

## Quick Start

```bash
# 1. Start test environment
./start_celery_test_env.sh

# 2. Run tests
python3 test_celery_priority_queue.py

# 3. Stop environment
./stop_celery_test_env.sh
```

## Prerequisites

### Required Software
- **Python 3.9+** with dependencies installed (`pip install -r requirements.txt`)
- **Redis** (message broker for Celery)
  - macOS: `brew install redis`
  - Ubuntu: `sudo apt install redis-server`
- **Celery** (installed via requirements.txt)

### Optional Services
- **Supabase** - For testing status tracking integration
- **Flower** - Web UI for monitoring Celery tasks (auto-started by test environment)

## Test Environment Scripts

### `start_celery_test_env.sh`
Automated script that:
1. Checks if Redis is running (starts it if needed)
2. Stops existing Celery workers (ensures clean state)
3. Starts new Celery worker in background
4. Starts Flower monitoring UI on port 5555
5. Creates logs directory for worker output

**Usage:**
```bash
./start_celery_test_env.sh
```

**Output:**
```
==========================================
Starting Celery Test Environment
==========================================

✅ Redis is already running on port 6379
✅ Celery worker started successfully
   Log file: logs/celery_worker.log
✅ Flower started on http://localhost:5555

==========================================
✅ Celery Test Environment Ready
==========================================

Services running:
  • Redis: localhost:6379
  • Celery Worker: Running (see logs/celery_worker.log)
  • Flower UI: http://localhost:5555
```

### `stop_celery_test_env.sh`
Stops Celery workers and Flower (leaves Redis running for other services).

**Usage:**
```bash
./stop_celery_test_env.sh
```

## Test Suite

### `test_celery_priority_queue.py`

Comprehensive test suite covering all aspects of the priority queue system.

#### Test 1: Priority Queue Ordering
- **Purpose**: Verify tasks are processed in correct priority order
- **Method**: Submit 4 tasks with different priorities in random order
- **Validation**: High-priority tasks should complete before low-priority tasks
- **Expected Result**: Processing order matches priority (URGENT → HIGH → NORMAL → LOW → BACKGROUND)

#### Test 2: Supabase Status Tracking
- **Purpose**: Verify status updates are correctly written to Supabase
- **Method**: Submit a task and check status transitions
- **Validation**: Status updates work correctly (uploaded → processing → processed)
- **Expected Result**: Status update function returns True

#### Test 3: Retry Logic with Exponential Backoff
- **Purpose**: Validate retry configuration and behavior
- **Method**: Check task retry settings and configuration
- **Validation**: Tasks have correct retry setup (max 3 retries, exponential backoff)
- **Expected Result**: Retry configuration matches spec (60s → 120s → 240s)

#### Test 4: Dead Letter Queue (DLQ)
- **Purpose**: Verify DLQ tasks are available and functional
- **Method**: Check DLQ task registration and run inspection task
- **Validation**: All 3 DLQ tasks are registered and inspection works
- **Expected Result**: DLQ inspection task executes successfully

## Monitoring During Tests

### Real-Time Log Monitoring
```bash
# Watch Celery worker logs
tail -f logs/celery_worker.log

# Watch Flower logs
tail -f logs/flower.log
```

### Flower Web UI
Open http://localhost:5555 in your browser to view:
- Active tasks
- Task history
- Worker status
- Task priority distribution
- Task timing and performance

**Credentials:**
- Username: `admin`
- Password: `empireflower123`

### Celery CLI Inspection
```bash
# View active tasks
celery -A app.celery_app inspect active

# View registered tasks
celery -A app.celery_app inspect registered

# View worker stats
celery -A app.celery_app inspect stats

# View scheduled tasks
celery -A app.celery_app inspect scheduled
```

## Manual Testing Scenarios

### Scenario 1: Priority Queue Ordering

**Objective**: Manually verify priority ordering works correctly.

```bash
# Terminal 1: Start worker with debug logging
celery -A app.celery_app worker --loglevel=debug

# Terminal 2: Submit tasks
python3 << EOF
from app.tasks.document_processing import submit_document_processing
from app.celery_app import PRIORITY_URGENT, PRIORITY_BACKGROUND

# Submit low priority first
submit_document_processing('file1', 'low.pdf', 'path1', priority=PRIORITY_BACKGROUND)

# Submit high priority second
submit_document_processing('file2', 'high.pdf', 'path2', priority=PRIORITY_URGENT)
EOF

# Expected: high.pdf processes before low.pdf (check worker logs)
```

### Scenario 2: Retry Logic

**Objective**: Trigger retry logic and observe exponential backoff.

```python
# Create failing_task_test.py
from app.celery_app import celery_app

@celery_app.task(bind=True)
def failing_task(self):
    print(f"Attempt {self.request.retries + 1}")
    raise Exception("Test failure")

# Run it
failing_task.delay()

# Watch logs for:
# - Retry attempt 1/3 - waiting 60s
# - Retry attempt 2/3 - waiting 120s
# - Retry attempt 3/3 - waiting 240s
# - All retry attempts exhausted
```

### Scenario 3: Dead Letter Queue

**Objective**: Verify failed tasks route to DLQ after retry exhaustion.

```python
# After running Scenario 2 (which exhausts retries)
from app.celery_app import inspect_dead_letter_queue

# Inspect DLQ for failed task
result = inspect_dead_letter_queue.delay()
print(result.get())

# Expected: See DLQ entry for failing_task
```

### Scenario 4: Status Tracking

**Objective**: Verify Supabase status updates throughout task lifecycle.

```python
from app.tasks.document_processing import submit_document_processing
from app.celery_app import PRIORITY_HIGH
from app.services.supabase_storage import get_supabase_storage
import asyncio

# Submit a task
result = submit_document_processing(
    file_id="test_123",
    filename="test.pdf",
    b2_path="test/test.pdf",
    priority=PRIORITY_HIGH
)

# Check status in Supabase
supabase = get_supabase_storage()
asyncio.run(supabase.update_document_status(
    b2_file_id="test_123",
    status="processing"
))

# Expected: Status updates successfully in Supabase
```

## Troubleshooting

### Redis Not Running
```bash
# Check if Redis is running
lsof -Pi :6379 -sTCP:LISTEN

# Start Redis manually
redis-server --daemonize yes

# Or use brew (macOS)
brew services start redis
```

### Celery Worker Not Starting
```bash
# Check logs
cat logs/celery_worker.log

# Try starting manually with debug logging
celery -A app.celery_app worker --loglevel=debug

# Common issues:
# - Missing dependencies: pip install -r requirements.txt
# - Import errors: Check PYTHONPATH
# - Redis not running: Start Redis first
```

### Tests Failing
```bash
# Check Redis connection
redis-cli ping  # Should return "PONG"

# Check Celery worker is running
ps aux | grep celery | grep -v grep

# Check Supabase credentials (if status tracking test fails)
# Verify .env file has SUPABASE_URL and SUPABASE_SERVICE_KEY

# Run tests with verbose output
python3 test_celery_priority_queue.py -v
```

### Flower Not Accessible
```bash
# Check if Flower is running
lsof -Pi :5555 -sTCP:LISTEN

# Start Flower manually
celery -A app.celery_app flower --port=5555

# Access at http://localhost:5555
```

## Expected Test Output

### Successful Test Run

```
============================================================
CELERY PRIORITY QUEUE - END-TO-END TESTS
============================================================

Starting tests at: 2025-01-05T10:30:00

============================================================
TEST: Priority Queue Ordering
============================================================

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

⏳ Waiting 5 seconds for tasks to process...

📊 Completed 4 out of 4 tasks
  1. urgent.pdf (priority 9) - SUCCESS
  2. high.pdf (priority 7) - SUCCESS
  3. normal.pdf (priority 5) - SUCCESS
  4. background.pdf (priority 1) - SUCCESS

✅ PASSED: Priority Ordering

============================================================
TEST: Supabase Status Tracking
============================================================

Testing status tracking workflow...
  → Submitted task: xyz-789
  → File ID: test_status_1234567890

⏳ Waiting for task to process...

🔍 Checking Supabase status updates...
✅ PASSED: Status Tracking

============================================================
TEST: Retry Logic & Exponential Backoff
============================================================

Testing retry logic requires a task that fails...
This test validates the retry configuration is correct.

📋 Retry Configuration:
  → Max retries: 3
  → Countdown formula: base_delay * (2 ** retry_count)
  → Base delay: 60s
  → Expected delays: [60, 120, 240]

✅ Task found: app.tasks.document_processing.process_document
  → Task is bound: True
  → Task has retry method: True

✅ PASSED: Retry Configuration

============================================================
TEST: Dead Letter Queue (DLQ)
============================================================

Testing DLQ task availability...
  ✅ Found: app.tasks.send_to_dead_letter_queue
  ✅ Found: app.tasks.inspect_dead_letter_queue
  ✅ Found: app.tasks.retry_from_dead_letter_queue

✅ PASSED: DLQ Tasks Available

🔍 Testing DLQ inspection...
  → DLQ inspection result: success

✅ PASSED: DLQ Inspection

============================================================
TEST SUMMARY
============================================================

Total Tests: 8
  ✅ Passed: 8
  ❌ Failed: 0

Test Breakdown:
  ✅ priority_test: 1 passed, 0 failed
  ✅ status_tracking_test: 1 passed, 0 failed
  ✅ retry_test: 1 passed, 0 failed
  ✅ dlq_test: 2 passed, 0 failed

============================================================
🎉 ALL TESTS PASSED!
============================================================
```

## Continuous Integration

### GitHub Actions (Future)

```yaml
# .github/workflows/celery-tests.yml
name: Celery Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Start Celery worker
        run: celery -A app.celery_app worker --detach
      - name: Run tests
        run: python3 test_celery_priority_queue.py
```

## Additional Resources

- **Celery Documentation**: https://docs.celeryq.dev/
- **Redis Documentation**: https://redis.io/docs/
- **Flower Documentation**: https://flower.readthedocs.io/
- **Empire Celery Configuration**: `docs/celery-priority-queue.md`

## Support

For issues or questions:
1. Check logs: `logs/celery_worker.log`
2. Review documentation: `docs/celery-priority-queue.md`
3. Inspect Celery state: `celery -A app.celery_app inspect [command]`
4. Monitor in Flower: http://localhost:5555
