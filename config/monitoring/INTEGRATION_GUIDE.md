# 🔌 Empire Monitoring Integration Guide

## What You Need to Do to Make Monitoring Work

### ✅ What's Already Set Up (by me):
- ✓ Environment variables in `.env`
- ✓ Docker compose configuration
- ✓ Prometheus, Grafana, Alertmanager configs
- ✓ Grafana dashboards
- ✓ Alert rules
- ✓ Startup script

### ⚠️ What YOU Need to Do:

## 1. Install Python Dependencies

Add these to your `requirements.txt`:
```txt
# Monitoring dependencies
prometheus-client==0.19.0
celery==5.3.4
redis==5.0.1
flower==2.0.1
```

Install them:
```bash
pip install prometheus-client celery redis flower
```

## 2. Add Metrics Endpoint to Your FastAPI App

Create or update `app/main.py`:

```python
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
from contextlib import asynccontextmanager

# Create FastAPI app
app = FastAPI(title="Empire API")

# Define Prometheus metrics
DOCUMENT_UPLOADS = Counter(
    'empire_document_uploads_total',
    'Total number of document uploads',
    ['status', 'file_type']
)

DOCUMENT_PROCESSING_TIME = Histogram(
    'empire_document_processing_seconds',
    'Time spent processing documents',
    ['operation_type']
)

SEARCH_QUERIES = Counter(
    'empire_search_queries_total',
    'Total number of search queries',
    ['search_type', 'status']
)

SEARCH_LATENCY = Histogram(
    'empire_search_latency_seconds',
    'Search query latency',
    ['search_type']
)

ACTIVE_WEBSOCKETS = Gauge(
    'empire_active_websockets',
    'Number of active WebSocket connections'
)

ERROR_COUNT = Counter(
    'empire_errors_total',
    'Total number of errors',
    ['error_type', 'component']
)

# CRITICAL: Add metrics endpoint
@app.get("/monitoring/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Health check endpoints
@app.get("/monitoring/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy"}

@app.get("/monitoring/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    # Add checks for your dependencies here
    return {"status": "ready"}

@app.get("/monitoring/live")
async def liveness_check():
    """Liveness check"""
    return {"status": "alive"}
```

## 3. Instrument Your Code with Metrics

### Example: Document Upload Endpoint

```python
@app.post("/upload")
async def upload_document(file: UploadFile):
    start_time = time.time()

    try:
        # Your upload logic here
        result = await process_upload(file)

        # Record success metric
        DOCUMENT_UPLOADS.labels(status="success", file_type=file.content_type).inc()

        # Record processing time
        duration = time.time() - start_time
        DOCUMENT_PROCESSING_TIME.labels(operation_type="upload").observe(duration)

        return result

    except Exception as e:
        # Record error metric
        DOCUMENT_UPLOADS.labels(status="failure", file_type=file.content_type).inc()
        ERROR_COUNT.labels(error_type=type(e).__name__, component="upload").inc()
        raise
```

### Example: Search Endpoint

```python
@app.post("/search")
async def search_documents(query: str):
    start_time = time.time()

    try:
        # Your search logic
        results = await perform_search(query)

        # Record metrics
        SEARCH_QUERIES.labels(search_type="semantic", status="success").inc()
        duration = time.time() - start_time
        SEARCH_LATENCY.labels(search_type="semantic").observe(duration)

        return results

    except Exception as e:
        SEARCH_QUERIES.labels(search_type="semantic", status="failure").inc()
        ERROR_COUNT.labels(error_type=type(e).__name__, component="search").inc()
        raise
```

### Example: WebSocket Connections

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ACTIVE_WEBSOCKETS.inc()  # Increment on connect

    try:
        while True:
            data = await websocket.receive_text()
            # Handle WebSocket messages

    finally:
        ACTIVE_WEBSOCKETS.dec()  # Decrement on disconnect
```

## 4. Set Up Celery (If Using Background Tasks)

Create `app/celery_app.py`:

```python
from celery import Celery
import os
from prometheus_client import Gauge

# Create Celery app
celery_app = Celery(
    'empire',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
)

# Queue size metric
QUEUE_SIZE = Gauge(
    'empire_celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue_name']
)

@celery_app.task
def process_document_async(document_id: str):
    """Example async task"""
    # Your processing logic
    pass

# Update queue metrics periodically
@celery_app.task
def update_queue_metrics():
    """Task to update queue size metrics"""
    inspect = celery_app.control.inspect()
    reserved = inspect.reserved()

    if reserved:
        for worker, tasks in reserved.items():
            QUEUE_SIZE.labels(queue_name='default').set(len(tasks))
```

## 5. Start Services in the Correct Order

### Option A: All-in-One (Development)
```bash
# 1. Start monitoring stack first
./start-monitoring.sh

# 2. Start your FastAPI app
uvicorn app.main:app --reload --port 8000

# 3. Start Celery worker (if using)
celery -A app.celery_app worker --loglevel=info

# 4. Start Celery beat (if using scheduled tasks)
celery -A app.celery_app beat --loglevel=info
```

### Option B: Production Setup
```bash
# 1. Start all services with docker-compose
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

## 6. Verify Everything is Connected

### Check Prometheus is scraping your app:
1. Go to http://localhost:9090/targets
2. Look for `empire_api` target
3. It should show "UP" status

### Check metrics are being collected:
1. Go to http://localhost:9090
2. Search for `empire_` metrics
3. You should see your custom metrics

### Check Grafana dashboard:
1. Go to http://localhost:3001
2. Login (admin/empiregrafana123)
3. Open "Empire Document Processing Dashboard"
4. You should see data flowing

## 7. Test Alert Rules

Trigger a test alert:
```python
# Add this test endpoint to your FastAPI app
@app.get("/test/trigger-alert")
async def trigger_alert():
    """Trigger high error rate for testing"""
    for _ in range(10):
        ERROR_COUNT.labels(error_type="TestError", component="test").inc()
    return {"message": "Triggered test alerts"}
```

Check Alertmanager:
- Go to http://localhost:9093
- You should see the alert after ~5 minutes

## 8. Common Issues and Solutions

### Issue: Metrics endpoint returns 404
**Solution**: Make sure you added the `/monitoring/metrics` endpoint to your FastAPI app

### Issue: Prometheus shows target as DOWN
**Solution**:
- Check your FastAPI app is running on port 8000
- If using Docker, use `host.docker.internal:8000` instead of `localhost:8000`

### Issue: No data in Grafana
**Solution**:
- Verify Prometheus is scraping successfully
- Check that your code is actually incrementing metrics
- Wait 1-2 minutes for data to appear

### Issue: Celery metrics not showing
**Solution**:
- Make sure Celery worker is running
- Check Redis is accessible
- Verify Flower is running on port 5555

## 9. Environment Variables Needed

Make sure these are set in your `.env`:
```bash
# Required for monitoring
PROMETHEUS_ENABLED=true
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Required for your app to expose metrics
APP_PORT=8000
```

## 10. Testing Checklist

- [ ] FastAPI app starts without errors
- [ ] `/monitoring/metrics` endpoint returns Prometheus format
- [ ] Prometheus shows empire_api target as UP
- [ ] Metrics appear in Prometheus query interface
- [ ] Grafana dashboard shows data
- [ ] Test alert triggers and appears in Alertmanager
- [ ] Flower shows Celery workers (if using)
- [ ] Redis is accessible via `redis-cli ping`

## Complete Working Example

Here's a minimal working FastAPI app with monitoring:

```python
# app/main.py
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
import random

app = FastAPI(title="Empire API")

# Metrics
REQUEST_COUNT = Counter('empire_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('empire_request_duration_seconds', 'Request duration')

# Middleware to track all requests
@app.middleware("http")
async def track_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_DURATION.observe(duration)

    return response

# Metrics endpoint
@app.get("/monitoring/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Health checks
@app.get("/monitoring/health")
async def health():
    return {"status": "healthy"}

# Your actual endpoints
@app.get("/")
async def root():
    # Simulate some work
    time.sleep(random.uniform(0.1, 0.5))
    return {"message": "Empire API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 🎯 Quick Start Commands

```bash
# 1. Install dependencies
pip install prometheus-client fastapi uvicorn

# 2. Start monitoring
./start-monitoring.sh

# 3. Run your app
python app/main.py

# 4. Test metrics endpoint
curl http://localhost:8000/monitoring/metrics

# 5. View in Grafana
open http://localhost:3001
```

That's it! Your monitoring should now be fully integrated with your Empire application.