#!/usr/bin/env python3
"""
Example FastAPI app with full monitoring integration
This is a working example you can run immediately to test the monitoring stack

Run with: python example_app_with_monitoring.py
Or: uvicorn example_app_with_monitoring:app --reload --port 8000
"""

from fastapi import FastAPI, Response, UploadFile, File, HTTPException
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import random
import asyncio
from datetime import datetime

# Create FastAPI app
app = FastAPI(
    title="Empire API - Example with Monitoring",
    description="Example FastAPI app with Prometheus monitoring integration",
    version="1.0.0"
)

# ==========================================
# PROMETHEUS METRICS DEFINITION
# ==========================================

# Document metrics
DOCUMENT_UPLOADS = Counter(
    'empire_document_uploads_total',
    'Total number of document uploads',
    ['status', 'file_type']
)

DOCUMENT_PROCESSING_TIME = Histogram(
    'empire_document_processing_seconds',
    'Time spent processing documents',
    ['operation_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Embedding metrics
EMBEDDING_GENERATION_TIME = Histogram(
    'empire_embedding_generation_seconds',
    'Time spent generating embeddings',
    ['provider'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# Search metrics
SEARCH_QUERIES = Counter(
    'empire_search_queries_total',
    'Total number of search queries',
    ['search_type', 'status']
)

SEARCH_LATENCY = Histogram(
    'empire_search_latency_seconds',
    'Search query latency',
    ['search_type'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# Chat metrics
CHAT_MESSAGES = Counter(
    'empire_chat_messages_total',
    'Total number of chat messages',
    ['role', 'has_memory']
)

LLM_RESPONSE_TIME = Histogram(
    'empire_llm_response_seconds',
    'LLM response generation time',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
)

# System metrics
ACTIVE_WEBSOCKETS = Gauge(
    'empire_active_websockets',
    'Number of active WebSocket connections'
)

QUEUE_SIZE = Gauge(
    'empire_celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue_name']
)

ERROR_COUNT = Counter(
    'empire_errors_total',
    'Total number of errors',
    ['error_type', 'component']
)

# Request tracking
REQUEST_COUNT = Counter(
    'empire_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'empire_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# ==========================================
# MIDDLEWARE FOR REQUEST TRACKING
# ==========================================

@app.middleware("http")
async def track_requests(request, call_next):
    """Track all HTTP requests automatically"""
    start_time = time.time()

    # Process the request
    response = await call_next(request)

    # Record metrics
    duration = time.time() - start_time
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response

# ==========================================
# MONITORING ENDPOINTS
# ==========================================

@app.get("/monitoring/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/monitoring/health", tags=["Monitoring"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "empire-api"
    }

@app.get("/monitoring/ready", tags=["Monitoring"])
async def readiness_check():
    """Readiness check - verify all dependencies are available"""
    checks = {
        "database": True,  # In real app, check database connection
        "redis": True,     # In real app, check Redis connection
        "storage": True    # In real app, check storage access
    }

    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail={"status": "not ready", "checks": checks})

@app.get("/monitoring/live", tags=["Monitoring"])
async def liveness_check():
    """Liveness check - verify the service is responsive"""
    return {"status": "alive"}

# ==========================================
# EXAMPLE API ENDPOINTS
# ==========================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Empire API with Monitoring",
        "endpoints": {
            "monitoring": "/monitoring/metrics",
            "health": "/monitoring/health",
            "docs": "/docs"
        }
    }

@app.post("/documents/upload", tags=["Documents"])
async def upload_document(file: UploadFile = File(None)):
    """Simulated document upload with metrics"""
    start_time = time.time()

    try:
        # Simulate processing delay
        await asyncio.sleep(random.uniform(0.5, 2.0))

        # Record success metrics
        file_type = file.content_type if file else "unknown"
        DOCUMENT_UPLOADS.labels(status="success", file_type=file_type).inc()

        # Record processing time
        duration = time.time() - start_time
        DOCUMENT_PROCESSING_TIME.labels(operation_type="upload").observe(duration)

        return {
            "status": "success",
            "message": "Document uploaded successfully",
            "processing_time": f"{duration:.2f}s"
        }

    except Exception as e:
        # Record failure metrics
        DOCUMENT_UPLOADS.labels(status="failure", file_type="unknown").inc()
        ERROR_COUNT.labels(error_type=type(e).__name__, component="upload").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/process", tags=["Documents"])
async def process_document(document_id: str):
    """Simulated document processing with metrics"""
    start_time = time.time()

    # Simulate different processing stages
    stages = ["extraction", "embedding", "indexing"]

    for stage in stages:
        stage_start = time.time()
        await asyncio.sleep(random.uniform(0.2, 1.0))
        stage_duration = time.time() - stage_start
        DOCUMENT_PROCESSING_TIME.labels(operation_type=stage).observe(stage_duration)

    # Simulate embedding generation
    embedding_start = time.time()
    await asyncio.sleep(random.uniform(0.1, 0.5))
    EMBEDDING_GENERATION_TIME.labels(provider="bge-m3").observe(time.time() - embedding_start)

    total_duration = time.time() - start_time

    return {
        "status": "processed",
        "document_id": document_id,
        "total_time": f"{total_duration:.2f}s"
    }

@app.post("/search", tags=["Search"])
async def search_documents(query: str, search_type: str = "semantic"):
    """Simulated search with metrics"""
    start_time = time.time()

    try:
        # Simulate search delay
        await asyncio.sleep(random.uniform(0.1, 0.8))

        # Record search metrics
        SEARCH_QUERIES.labels(search_type=search_type, status="success").inc()
        duration = time.time() - start_time
        SEARCH_LATENCY.labels(search_type=search_type).observe(duration)

        # Return mock results
        return {
            "query": query,
            "search_type": search_type,
            "results": [
                {"id": "doc1", "score": 0.95, "title": "Sample Document 1"},
                {"id": "doc2", "score": 0.87, "title": "Sample Document 2"},
                {"id": "doc3", "score": 0.73, "title": "Sample Document 3"}
            ],
            "search_time": f"{duration:.3f}s"
        }

    except Exception as e:
        SEARCH_QUERIES.labels(search_type=search_type, status="failure").inc()
        ERROR_COUNT.labels(error_type=type(e).__name__, component="search").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", tags=["Chat"])
async def chat_completion(message: str, use_memory: bool = False):
    """Simulated chat with metrics"""
    start_time = time.time()

    # Record chat message
    CHAT_MESSAGES.labels(role="user", has_memory=str(use_memory).lower()).inc()

    # Simulate LLM processing
    await asyncio.sleep(random.uniform(1.0, 3.0))

    # Record LLM response time
    duration = time.time() - start_time
    LLM_RESPONSE_TIME.labels(model="claude-3-haiku").observe(duration)

    # Record assistant message
    CHAT_MESSAGES.labels(role="assistant", has_memory=str(use_memory).lower()).inc()

    return {
        "response": f"This is a simulated response to: {message}",
        "model": "claude-3-haiku",
        "response_time": f"{duration:.2f}s",
        "memory_used": use_memory
    }

@app.get("/test/generate-metrics", tags=["Testing"])
async def generate_test_metrics():
    """Generate various metrics for testing dashboards"""

    # Generate some document uploads
    for _ in range(5):
        DOCUMENT_UPLOADS.labels(
            status=random.choice(["success", "failure"]),
            file_type=random.choice(["pdf", "docx", "txt"])
        ).inc()

    # Generate search queries
    for _ in range(10):
        search_type = random.choice(["semantic", "keyword", "hybrid"])
        SEARCH_QUERIES.labels(search_type=search_type, status="success").inc()
        SEARCH_LATENCY.labels(search_type=search_type).observe(random.uniform(0.1, 2.0))

    # Generate some errors
    for _ in range(3):
        ERROR_COUNT.labels(
            error_type=random.choice(["ValueError", "TimeoutError", "ConnectionError"]),
            component=random.choice(["upload", "search", "chat"])
        ).inc()

    # Update queue size
    QUEUE_SIZE.labels(queue_name="default").set(random.randint(0, 50))

    # Simulate WebSocket connections
    ACTIVE_WEBSOCKETS.set(random.randint(5, 25))

    return {
        "message": "Test metrics generated",
        "note": "Check Prometheus and Grafana dashboards"
    }

@app.get("/test/trigger-alert", tags=["Testing"])
async def trigger_test_alert():
    """Trigger high error rate to test alerting"""

    # Generate many errors quickly to trigger alert
    for _ in range(20):
        ERROR_COUNT.labels(error_type="TestAlert", component="test").inc()

    return {
        "message": "Alert triggered",
        "note": "Check Alertmanager in ~5 minutes at http://localhost:9093"
    }

# ==========================================
# BACKGROUND TASKS SIMULATION
# ==========================================

async def update_queue_metrics():
    """Periodically update queue size metrics"""
    while True:
        # Simulate varying queue size
        size = random.randint(0, 100)
        QUEUE_SIZE.labels(queue_name="default").set(size)
        await asyncio.sleep(30)  # Update every 30 seconds

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    # Start background metric updates
    asyncio.create_task(update_queue_metrics())
    print("✓ Monitoring metrics initialized")
    print("✓ Access metrics at: http://localhost:8000/monitoring/metrics")
    print("✓ API documentation at: http://localhost:8000/docs")

# ==========================================
# RUN THE APP
# ==========================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("EMPIRE API - Example with Monitoring")
    print("=" * 60)
    print()
    print("Starting server...")
    print("• API Docs: http://localhost:8000/docs")
    print("• Metrics: http://localhost:8000/monitoring/metrics")
    print("• Health: http://localhost:8000/monitoring/health")
    print()
    print("Generate test metrics: http://localhost:8000/test/generate-metrics")
    print("Trigger test alert: http://localhost:8000/test/trigger-alert")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)