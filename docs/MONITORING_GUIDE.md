# Empire v7.3 - Monitoring & Metrics Guide

**Complete guide to monitoring, metrics collection, and cost tracking**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Processing Pipeline Monitoring](#processing-pipeline-monitoring)
5. [Cost Tracking](#cost-tracking)
6. [Resource Monitoring](#resource-monitoring)
7. [Prometheus Metrics](#prometheus-metrics)
8. [Database Logging](#database-logging)
9. [Celery Task Monitoring](#celery-task-monitoring)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Empire's monitoring system provides comprehensive observability across the entire document processing pipeline:

- **25+ Prometheus metrics** for real-time monitoring
- **Stage-wise processing tracking** with automatic timing and resource usage
- **Cost tracking** for LLM API calls, embeddings, and storage
- **Database logging** for historical analysis
- **Resource monitoring** (CPU, memory) per processing stage
- **Celery task metrics** for background job monitoring

### Key Features

✅ **Automatic Context Managers** - Zero-overhead metric collection
✅ **Cost Calculation** - Real-time tracking of LLM, embedding, and storage costs
✅ **Resource Tracking** - CPU and memory usage per stage
✅ **Database Integration** - All metrics logged to `processing_logs` table
✅ **Prometheus Export** - Standard `/monitoring/metrics` endpoint
✅ **Error Tracking** - Automatic failure detection and logging

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         MonitoringService (Singleton)                  │ │
│  │  - track_processing()   Context Manager                │ │
│  │  - track_stage()        Context Manager                │ │
│  │  - record_llm_call()    Cost Tracking                  │ │
│  │  - record_embedding()   Cost Tracking                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│        ┌──────────────────┼──────────────────┐              │
│        │                  │                  │              │
│        ▼                  ▼                  ▼              │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐          │
│  │Prometheus│      │ Database │      │ psutil   │          │
│  │ Metrics  │      │ Logging  │      │Resource  │          │
│  └──────────┘      └──────────┘      └──────────┘          │
└─────────────────────────────────────────────────────────────┘
         │                   │                   │
         ▼                   ▼                   ▼
    /metrics          processing_logs       CPU/Memory
   Endpoint              Table               Usage
```

### Components

1. **MonitoringService** - Central service for all metrics collection
2. **ProcessingStage** - Enum defining 10 pipeline stages
3. **CostCalculator** - Calculates costs for LLM, embeddings, storage
4. **Prometheus Metrics** - 25+ metrics exported at `/monitoring/metrics`
5. **Database Logger** - Stores metrics in `processing_logs` table

---

## Quick Start

### Basic Usage

```python
from app.services.monitoring_service import get_monitoring_service, ProcessingStage

# Get singleton monitoring service
monitor = get_monitoring_service()

# Track entire document processing
async with monitor.track_processing(
    file_id="doc-123",
    filename="contract.pdf",
    file_type="pdf"
) as metrics:

    # Track individual stages
    async with monitor.track_stage("doc-123", ProcessingStage.PARSING):
        result = await parse_document("doc-123")

    async with monitor.track_stage("doc-123", ProcessingStage.EMBEDDING_GENERATION) as stage:
        embeddings = await generate_embeddings(chunks)

        # Record cost
        stage.cost = await monitor.record_embedding_generation(
            provider="ollama",
            model="bge-m3",
            num_embeddings=len(embeddings),
            tokens=total_tokens,
            duration=embedding_time
        )

# Metrics automatically recorded to Prometheus and database
```

### Accessing in FastAPI

```python
from fastapi import Request

@app.post("/api/v1/documents/process")
async def process_document(request: Request, file_id: str):
    monitor = request.app.state.monitoring

    async with monitor.track_processing(file_id, filename, file_type) as metrics:
        # Processing code
        pass

    return {"file_id": file_id, "cost": metrics.total_cost}
```

---

## Processing Pipeline Monitoring

### Available Processing Stages

```python
class ProcessingStage(str, Enum):
    UPLOAD = "upload"                          # File upload
    VALIDATION = "validation"                  # File validation
    PARSING = "parsing"                        # Document parsing
    METADATA_EXTRACTION = "metadata_extraction"  # Metadata extraction
    CHUNKING = "chunking"                      # Text chunking
    EMBEDDING_GENERATION = "embedding_generation"  # Embedding creation
    CLASSIFICATION = "classification"          # Document classification
    STORAGE = "storage"                        # Cloud storage
    GRAPH_SYNC = "graph_sync"                  # Neo4j synchronization
    INDEXING = "indexing"                      # Search indexing
```

### Complete Pipeline Example

```python
async def process_document_pipeline(file_id: str, filename: str):
    monitor = get_monitoring_service()

    async with monitor.track_processing(file_id, filename, "pdf") as metrics:

        # 1. Upload
        async with monitor.track_stage(file_id, ProcessingStage.UPLOAD):
            await upload_to_storage(file_id)

        # 2. Validation
        async with monitor.track_stage(file_id, ProcessingStage.VALIDATION):
            await validate_file(file_id)

        # 3. Parsing (with metadata)
        async with monitor.track_stage(
            file_id,
            ProcessingStage.PARSING,
            metadata={"parser": "llama_parse", "pages": 25}
        ) as parsing:
            result = await parse_with_llama(file_id)
            parsing.cost = 0.01  # LlamaParse cost

        # 4. Metadata Extraction
        async with monitor.track_stage(file_id, ProcessingStage.METADATA_EXTRACTION):
            metadata = await extract_metadata(file_id)

        # 5. Chunking
        async with monitor.track_stage(
            file_id,
            ProcessingStage.CHUNKING,
            metadata={"chunks": 150, "avg_size": 512}
        ):
            chunks = await chunk_document(file_id)

        # 6. Embedding Generation
        async with monitor.track_stage(file_id, ProcessingStage.EMBEDDING_GENERATION) as embed:
            embeddings = await generate_embeddings(chunks)
            embed.cost = await monitor.record_embedding_generation(
                provider="ollama",
                model="bge-m3",
                num_embeddings=len(embeddings),
                tokens=len(chunks) * 512,
                duration=embed_time
            )

        # 7. Classification
        async with monitor.track_stage(file_id, ProcessingStage.CLASSIFICATION) as classify:
            category = await classify_document(file_id)
            classify.cost = await monitor.record_llm_call(
                provider="anthropic",
                model="claude-3-5-haiku-20241022",
                operation="classification",
                input_tokens=1000,
                output_tokens=200,
                duration=llm_time
            )

        # 8. Storage
        async with monitor.track_stage(file_id, ProcessingStage.STORAGE):
            await monitor.record_storage_operation(
                operation="upload",
                backend="b2",
                bytes_transferred=5 * 1024 * 1024,  # 5 MB
                duration=storage_time
            )

        # 9. Graph Sync
        async with monitor.track_stage(file_id, ProcessingStage.GRAPH_SYNC):
            await monitor.record_graph_sync(
                operation="create",
                duration=graph_time
            )

    # Total cost automatically calculated
    print(f"Total processing cost: ${metrics.total_cost:.4f}")
    print(f"Total duration: {metrics.total_duration:.2f}s")
```

### Stage Metrics

Each stage automatically tracks:

- **Duration** - Start to end time
- **CPU Usage** - Average CPU % during stage
- **Memory Usage** - Memory delta (bytes)
- **Status** - `success` or `failure`
- **Error** - Exception message if failed
- **Cost** - Optional cost if applicable
- **Metadata** - Custom stage-specific data

---

## Cost Tracking

### Supported Cost Models

#### LLM API Costs (per 1K tokens)

```python
LLM_COSTS = {
    "claude-3-5-sonnet-20241022": {"input": $0.003, "output": $0.015},
    "claude-3-5-haiku-20241022": {"input": $0.001, "output": $0.005},
    "claude-3-opus-20240229": {"input": $0.015, "output": $0.075},
    "gpt-4o": {"input": $0.005, "output": $0.015},
    "gpt-4o-mini": {"input": $0.00015, "output": $0.0006},
}
```

#### Embedding Costs (per 1K tokens)

```python
EMBEDDING_COSTS = {
    "openai-text-embedding-3-small": $0.00002,
    "openai-text-embedding-3-large": $0.00013,
    "bge-m3": $0.00  # Free via Ollama
}
```

#### Storage Costs

```python
STORAGE_COST_PER_GB_MONTH = $0.005  # Backblaze B2
```

### Recording LLM Calls

```python
# Record LLM API call with automatic cost calculation
cost = await monitor.record_llm_call(
    provider="anthropic",
    model="claude-3-5-haiku-20241022",
    operation="query_expansion",
    input_tokens=1000,
    output_tokens=500,
    duration=2.5,
    status="success"
)

# Returns: $0.0035
# Calculation: (1000/1000 * $0.001) + (500/1000 * $0.005) = $0.0035
```

### Recording Embedding Generation

```python
# Record embedding generation with cost
cost = await monitor.record_embedding_generation(
    provider="ollama",
    model="bge-m3",
    num_embeddings=150,
    tokens=76800,  # 150 chunks * 512 tokens
    duration=2.5,
    status="success"
)

# Returns: $0.00 (BGE-M3 is free via Ollama)
```

### Manual Cost Calculation

```python
from app.services.monitoring_service import CostCalculator

# LLM cost
llm_cost = CostCalculator.calculate_llm_cost(
    model="claude-3-5-sonnet-20241022",
    input_tokens=5000,
    output_tokens=1000
)
# Returns: $0.03

# Embedding cost
embed_cost = CostCalculator.calculate_embedding_cost(
    model="openai-text-embedding-3-small",
    tokens=100000
)
# Returns: $0.002

# Storage cost (1 GB for 30 days)
storage_cost = CostCalculator.calculate_storage_cost(
    bytes_stored=1024**3,  # 1 GB
    days=30
)
# Returns: $0.005
```

### Cost Aggregation

```python
async with monitor.track_processing(file_id, filename, file_type) as metrics:
    # Stage 1
    async with monitor.track_stage(file_id, ProcessingStage.PARSING) as stage:
        stage.cost = 0.01

    # Stage 2
    async with monitor.track_stage(file_id, ProcessingStage.EMBEDDING_GENERATION) as stage:
        stage.cost = await monitor.record_embedding_generation(...)

    # Stage 3
    async with monitor.track_stage(file_id, ProcessingStage.CLASSIFICATION) as stage:
        stage.cost = await monitor.record_llm_call(...)

# Total cost automatically calculated
print(f"Total: ${metrics.total_cost:.4f}")
```

---

## Resource Monitoring

### CPU and Memory Tracking

Each stage automatically tracks:

```python
async with monitor.track_stage(file_id, ProcessingStage.PARSING) as stage:
    # Heavy processing
    result = await parse_large_document(file_id)

# After stage completes:
print(f"CPU Usage: {stage.cpu_usage:.2f}%")
print(f"Memory Delta: {stage.memory_usage / 1024**2:.2f} MB")
```

### How It Works

```python
# Before stage starts
process = psutil.Process()
cpu_start = process.cpu_percent(interval=0.1)
memory_start = process.memory_info().rss

# ... stage execution ...

# After stage completes
cpu_end = process.cpu_percent(interval=0.1)
memory_end = process.memory_info().rss

# Calculate averages/deltas
stage.cpu_usage = (cpu_start + cpu_end) / 2
stage.memory_usage = memory_end - memory_start
```

### Prometheus Gauges

Resource metrics are exported to Prometheus:

```python
PROCESSING_CPU_USAGE.labels(stage="parsing").set(45.2)
PROCESSING_MEMORY_USAGE.labels(stage="parsing").set(524288000)  # bytes
```

---

## Prometheus Metrics

### Available Metrics

#### Document Processing

```
# Total documents processed
empire_document_processing_total{stage, status, file_type}

# Processing duration histogram
empire_document_processing_duration_seconds{stage, file_type}

# Processing errors
empire_document_processing_errors_total{stage, error_type}
```

#### Resource Usage

```
# CPU usage gauge
empire_processing_cpu_usage_percent{stage}

# Memory usage gauge
empire_processing_memory_usage_bytes{stage}
```

#### Cost Tracking

```
# Cumulative cost counter
empire_processing_cost_dollars{service, operation}

# Per-document cost summary
empire_document_cost_dollars{operation}
```

#### LLM API Calls

```
# API call counter
empire_llm_api_calls_total{provider, model, operation, status}

# API duration histogram
empire_llm_api_duration_seconds{provider, model, operation}

# Token usage counter
empire_llm_api_tokens_total{provider, model, token_type}
```

#### Embedding Generation

```
# Embedding counter
empire_embedding_generation_total{provider, model, status}

# Embedding duration
empire_embedding_generation_duration_seconds{provider, model}

# Token counter
empire_embedding_tokens_total{provider, model}
```

#### Storage Operations

```
# Storage operations
empire_storage_operations_total{operation, backend, status}

# Bytes transferred
empire_storage_bytes_total{operation, backend}
```

#### Graph Sync

```
# Graph operations
empire_graph_sync_operations_total{operation, status}

# Graph sync duration
empire_graph_sync_duration_seconds{operation}
```

#### Queue Metrics

```
# Queue size gauge
empire_queue_size{queue_name}

# Queue latency histogram
empire_queue_latency_seconds{queue_name}
```

#### Celery Tasks

```
# Celery task counter
empire_celery_tasks_total{task_name, status}

# Celery task duration
empire_celery_task_duration_seconds{task_name}
```

### Accessing Metrics

```bash
# FastAPI metrics endpoint
curl http://localhost:8000/monitoring/metrics

# Example output:
# empire_document_processing_total{stage="parsing",status="success",file_type="pdf"} 42.0
# empire_document_processing_duration_seconds_sum{stage="parsing",file_type="pdf"} 125.4
# empire_llm_api_calls_total{provider="anthropic",model="claude-3-5-haiku-20241022",operation="classification",status="success"} 15.0
# empire_processing_cost_dollars_total{service="anthropic",operation="classification"} 0.0525
```

### Prometheus Queries

```promql
# Average processing time per stage
rate(empire_document_processing_duration_seconds_sum[5m]) /
rate(empire_document_processing_total[5m])

# Total cost per hour
rate(empire_processing_cost_dollars_total[1h]) * 3600

# Success rate by stage
sum(rate(empire_document_processing_total{status="success"}[5m])) /
sum(rate(empire_document_processing_total[5m]))

# P95 LLM API latency
histogram_quantile(0.95,
  rate(empire_llm_api_duration_seconds_bucket[5m])
)
```

---

## Database Logging

### Processing Logs Table

All metrics are logged to the `processing_logs` table:

```sql
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    severity TEXT CHECK (severity IN ('info', 'warning', 'error')),
    category TEXT CHECK (category IN ('processing', 'validation', 'storage', 'system')),
    error_type TEXT,
    error_message TEXT,
    file_id UUID REFERENCES files(id),
    filename TEXT,
    task_type TEXT,
    resolution_status TEXT,
    additional_context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Log Entry Format

```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "severity": "info",
  "category": "processing",
  "error_type": null,
  "error_message": "Processing stage: parsing",
  "file_id": "doc-123",
  "filename": "contract.pdf",
  "task_type": "processing_parsing",
  "resolution_status": "success",
  "additional_context": {
    "stage": "parsing",
    "duration": 2.45,
    "cpu_usage": 45.2,
    "memory_usage": 524288000,
    "cost": 0.01,
    "metadata": {
      "parser": "llama_parse",
      "pages": 25
    }
  }
}
```

### Querying Logs

```python
from app.services.supabase_storage import get_supabase_storage

storage = get_supabase_storage()

# Query logs for a specific file
logs = await storage.supabase.table("processing_logs")\
    .select("*")\
    .eq("file_id", "doc-123")\
    .order("timestamp", desc=True)\
    .execute()

# Query failed processing stages
failed_logs = await storage.supabase.table("processing_logs")\
    .select("*")\
    .eq("category", "processing")\
    .eq("resolution_status", "failure")\
    .gte("timestamp", "2025-01-15T00:00:00Z")\
    .execute()

# Calculate average cost per file type
cost_by_type = await storage.supabase.rpc("calculate_avg_cost_by_type").execute()
```

### SQL Analytics

```sql
-- Average processing time by stage
SELECT
    additional_context->>'stage' as stage,
    AVG((additional_context->>'duration')::float) as avg_duration,
    COUNT(*) as count
FROM processing_logs
WHERE category = 'processing'
    AND resolution_status = 'success'
GROUP BY stage
ORDER BY avg_duration DESC;

-- Total cost by file type
SELECT
    SUBSTRING(filename FROM '\\.([^.]+)$') as file_type,
    SUM((additional_context->>'cost')::float) as total_cost,
    COUNT(DISTINCT file_id) as num_files
FROM processing_logs
WHERE category = 'processing'
    AND additional_context->>'cost' IS NOT NULL
GROUP BY file_type;

-- Failure rate by stage
SELECT
    additional_context->>'stage' as stage,
    COUNT(*) FILTER (WHERE resolution_status = 'failure') as failures,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_status = 'failure') / COUNT(*), 2) as failure_rate
FROM processing_logs
WHERE category = 'processing'
GROUP BY stage
ORDER BY failure_rate DESC;
```

---

## Celery Task Monitoring

### Automatic Task Tracking

Celery tasks are automatically tracked via signals:

```python
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    _task_start_times[task_id] = time.time()
    print(f"📋 Task started: {task.name} [{task_id}]")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    if task_id in _task_start_times:
        duration = time.time() - _task_start_times[task_id]
        CELERY_TASK_DURATION.labels(task_name=task.name).observe(duration)

    CELERY_TASKS.labels(task_name=task.name, status='success').inc()

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    CELERY_TASKS.labels(task_name=sender.name, status='failure').inc()
```

### Task Metrics

```
# Total tasks by name and status
empire_celery_tasks_total{task_name, status}

# Task duration histogram
empire_celery_task_duration_seconds{task_name}
```

### Queue Monitoring

```python
# Update queue metrics
await monitor.update_queue_metrics(
    queue_name="documents",
    size=42,
    avg_latency=5.5
)
```

---

## Best Practices

### 1. Always Use Context Managers

✅ **Recommended:**
```python
async with monitor.track_processing(file_id, filename, file_type) as metrics:
    async with monitor.track_stage(file_id, ProcessingStage.PARSING):
        await parse_document(file_id)
```

❌ **Avoid:**
```python
# Manual tracking is error-prone
metrics = ProcessingMetrics(...)
stage = StageMetrics(...)
# ... lots of manual timing and error handling
```

### 2. Record All Costs

Always record costs for billable operations:

```python
async with monitor.track_stage(file_id, ProcessingStage.CLASSIFICATION) as stage:
    result = await classify_document(file_id)

    # Record cost
    stage.cost = await monitor.record_llm_call(
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
        operation="classification",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        duration=result.duration
    )
```

### 3. Add Stage Metadata

Include relevant metadata for debugging:

```python
async with monitor.track_stage(
    file_id,
    ProcessingStage.PARSING,
    metadata={
        "parser": "llama_parse",
        "pages": num_pages,
        "file_size_mb": file_size / 1024**2,
        "detected_language": language
    }
):
    result = await parse_document(file_id)
```

### 4. Handle Errors Gracefully

Context managers automatically track failures:

```python
try:
    async with monitor.track_stage(file_id, ProcessingStage.EMBEDDING_GENERATION) as stage:
        embeddings = await generate_embeddings(chunks)
except EmbeddingGenerationError as e:
    # Error is automatically recorded in stage metrics
    # Handle error appropriately
    logger.error(f"Embedding generation failed: {e}")
    raise
```

### 5. Use Singleton Access

Always use the singleton getter:

```python
from app.services.monitoring_service import get_monitoring_service

monitor = get_monitoring_service()  # ✅ Correct
# monitor = MonitoringService()  # ❌ Avoid - creates new instance
```

### 6. Monitor Resource Usage

For resource-intensive stages, check metrics:

```python
async with monitor.track_stage(file_id, ProcessingStage.PARSING) as stage:
    result = await parse_large_document(file_id)

# Log if resource usage is high
if stage.memory_usage > 1024**3:  # > 1 GB
    logger.warning(f"High memory usage: {stage.memory_usage / 1024**3:.2f} GB")
```

---

## Troubleshooting

### Issue: Metrics Not Appearing in Prometheus

**Symptoms:**
- `/monitoring/metrics` endpoint returns no data
- Grafana dashboards are empty

**Causes & Solutions:**

1. **Monitoring service not initialized**
   ```python
   # Check FastAPI lifespan
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       monitoring = get_monitoring_service(get_supabase_storage())
       app.state.monitoring = monitoring  # ✅ Must set
       yield
   ```

2. **No processing activity**
   ```bash
   # Trigger some processing to generate metrics
   curl -X POST http://localhost:8000/api/v1/upload/file \
     -F "file=@test.pdf"
   ```

3. **Prometheus not scraping**
   ```yaml
   # prometheus.yml
   scrape_configs:
     - job_name: 'empire'
       static_configs:
         - targets: ['localhost:8000']
       metrics_path: '/monitoring/metrics'
   ```

### Issue: Database Logs Not Being Written

**Symptoms:**
- `processing_logs` table is empty
- No errors in logs

**Causes & Solutions:**

1. **Supabase storage not configured**
   ```python
   # Ensure storage is passed to monitoring service
   storage = get_supabase_storage()
   monitor = get_monitoring_service(storage)  # ✅ Pass storage
   ```

2. **Database connection failed**
   ```python
   # Check Supabase connection
   try:
       result = await storage.supabase.table("processing_logs").select("id").limit(1).execute()
       print("✅ Database connected")
   except Exception as e:
       print(f"❌ Database error: {e}")
   ```

3. **Missing table**
   ```sql
   -- Create processing_logs table
   -- See ERROR_HANDLING_GUIDE.md for schema
   ```

### Issue: High Memory Usage

**Symptoms:**
- `memory_usage` metrics show large values
- Application crashes with OOM errors

**Causes & Solutions:**

1. **Large file processing**
   ```python
   # Stream large files instead of loading into memory
   async with monitor.track_stage(file_id, ProcessingStage.PARSING) as stage:
       async for chunk in stream_parse_document(file_id):  # ✅ Stream
           process_chunk(chunk)
   ```

2. **Metrics accumulation**
   ```python
   # Monitor active tracking dict size
   if len(monitor.active_tracking) > 100:
       logger.warning("Too many active tracking sessions")
   ```

### Issue: Cost Calculations Incorrect

**Symptoms:**
- Costs don't match expected values
- Negative or zero costs

**Causes & Solutions:**

1. **Wrong model name**
   ```python
   # Use exact model names from CostCalculator
   cost = await monitor.record_llm_call(
       model="claude-3-5-haiku-20241022",  # ✅ Exact name
       # model="claude-haiku",  # ❌ Won't match
       ...
   )
   ```

2. **Missing cost recording**
   ```python
   # Always record costs for billable operations
   async with monitor.track_stage(file_id, stage) as s:
       result = await expensive_operation()
       s.cost = await monitor.record_llm_call(...)  # ✅ Record
   ```

3. **Cost model outdated**
   ```python
   # Update CostCalculator.LLM_COSTS with current pricing
   # Check provider documentation for latest rates
   ```

### Issue: Celery Task Metrics Missing

**Symptoms:**
- `empire_celery_tasks_total` shows 0
- Task duration not recorded

**Causes & Solutions:**

1. **Signals not connected**
   ```python
   # Ensure signals are imported in celery_app.py
   from celery.signals import task_prerun, task_postrun, task_failure

   @task_prerun.connect
   def task_prerun_handler(...):  # ✅ Must be defined
       ...
   ```

2. **Task start time not tracked**
   ```python
   # Check _task_start_times dict
   _task_start_times = {}  # ✅ Must exist at module level
   ```

### Issue: Stage Context Manager Not Recording

**Symptoms:**
- Stage metrics not added to processing metrics
- Duration shows as None

**Causes & Solutions:**

1. **File not being tracked**
   ```python
   # Must wrap with track_processing first
   async with monitor.track_processing(file_id, ...) as metrics:  # ✅ Required
       async with monitor.track_stage(file_id, stage):
           ...
   ```

2. **Exception in finally block**
   ```python
   # Check for exceptions in stage cleanup
   # Add logging to debug
   try:
       # stage cleanup
   except Exception as e:
       logger.error(f"Stage cleanup failed: {e}")
   ```

---

## Summary

Empire's monitoring system provides:

✅ **Automatic Tracking** - Context managers handle all metric collection
✅ **Comprehensive Metrics** - 25+ Prometheus metrics covering all aspects
✅ **Cost Visibility** - Real-time tracking of LLM, embedding, and storage costs
✅ **Resource Monitoring** - CPU and memory usage per stage
✅ **Database Logging** - Historical analysis via `processing_logs` table
✅ **Error Tracking** - Automatic failure detection and logging
✅ **Production-Ready** - Integrated with FastAPI, Celery, and Prometheus

For more information:
- **Implementation**: `app/services/monitoring_service.py`
- **Tests**: `tests/test_monitoring_service.py`
- **Error Handling**: `docs/ERROR_HANDLING_GUIDE.md`
- **Architecture**: `ARCHITECTURE.md`
