# Error Handling & Graceful Degradation Guide

## Overview

Empire v7.3 includes a comprehensive error handling framework that provides:
- Automatic error classification and categorization
- Intelligent retry logic with exponential backoff
- Graceful degradation with fallback mechanisms
- Detailed error logging to database and Python logger
- Celery task integration

## Components

### 1. Error Handler Service (`app/services/error_handler.py`)
- **ErrorClassifier**: Classifies errors into categories and determines retry strategies
- **ErrorHandler**: Centralized error handling with logging and recovery
- **Decorators**: `@handle_errors` and `@with_fallback` for easy integration

### 2. Celery Retry Utilities (`app/utils/celery_retry.py`)
- **task_with_retry**: Enhanced Celery task decorator
- **RetryContext**: Manual retry context manager
- **with_graceful_degradation**: Decorator for fallback logic

### 3. Processing Logs Model (`app/models/processing_logs.py`)
- Database schema for storing error logs
- Pydantic models for validation

### 4. Supabase Storage Updates (`app/services/supabase_storage.py`)
- `insert_processing_log()`: Save errors to database
- `get_processing_logs()`: Query error logs

## Error Classification

Errors are automatically classified into categories:

| Category | Examples | Retry Strategy |
|----------|----------|----------------|
| NETWORK | ConnectionError, HTTPError | Exponential backoff |
| TIMEOUT | TimeoutError, Request timeout | Exponential backoff |
| SERVICE_UNAVAILABLE | 503 errors | Exponential backoff |
| DATABASE | Database locks, connection issues | Linear/Exponential |
| STORAGE | File not found, S3 errors | Exponential/None |
| VALIDATION | ValueError, TypeError | No retry |
| PARSING | JSON/XML parse errors | No retry |
| AUTHENTICATION | Auth failures | No retry |

## Usage Examples

### Basic Error Handling with Decorator

```python
from app.services.error_handler import handle_errors

@handle_errors(fallback_value=[], log_errors=True)
async def fetch_data():
    # If this fails, returns [] instead of raising
    response = await api_client.get("/data")
    return response.json()
```

### With Fallback Function

```python
from app.services.error_handler import with_fallback

async def simple_processing(document):
    """Fallback: simpler processing when primary fails"""
    return {"status": "partial", "method": "simple"}

@with_fallback(simple_processing)
async def advanced_processing(document):
    """Primary: complex processing with ML models"""
    result = await ml_model.process(document)
    return {"status": "complete", "method": "advanced", "result": result}
```

### Celery Tasks with Auto-Retry

```python
from app.celery_app import celery_app
from app.utils.celery_retry import task_with_retry

@celery_app.task(**task_with_retry(max_retries=5))
def process_document(file_id: str):
    """Task with automatic retry on transient errors"""
    # Network errors, timeouts automatically retried
    result = external_service.process(file_id)
    return result
```

### Manual Error Handling

```python
from app.services.error_handler import get_error_handler, ErrorContext

async def my_function(file_id: str):
    error_handler = get_error_handler()

    context = ErrorContext(
        task_id="custom-task-123",
        task_type="custom_processing",
        file_id=file_id,
        retry_count=0,
        max_retries=3
    )

    try:
        # Your code here
        result = await risky_operation()
        return result

    except Exception as e:
        # Log error and get classification
        log_entry = await error_handler.handle_error(e, context)

        # Check if we should retry
        from app.services.error_handler import ErrorClassifier
        if ErrorClassifier.is_retryable(e):
            # Retry logic
            pass
        else:
            # Permanent failure handling
            raise
```

### Celery Task with Custom Retry Logic

```python
from app.celery_app import celery_app
from app.utils.celery_retry import RetryContext
from app.services.error_handler import get_error_handler, ErrorContext

@celery_app.task(bind=True)
def complex_task(self, file_id: str):
    error_handler = get_error_handler()
    retry_ctx = RetryContext(self, max_retries=5, base_countdown=120)

    try:
        # Your processing code
        result = process_file(file_id)
        return result

    except Exception as e:
        # Log to database
        context = ErrorContext(
            task_id=self.request.id,
            task_type="complex_task",
            file_id=file_id,
            retry_count=retry_ctx.retry_count
        )
        await error_handler.handle_error(e, context)

        # Retry if appropriate
        if retry_ctx.should_retry(e):
            retry_ctx.retry(e)
        else:
            raise
```

### Using Graceful Degradation

```python
from app.utils.celery_retry import with_graceful_degradation

def simple_parser(file_path):
    """Simple fallback parser"""
    with open(file_path) as f:
        return {"text": f.read(), "method": "simple"}

@with_graceful_degradation(fallback_fn=simple_parser)
def advanced_parser(file_path):
    """Advanced parser with ML"""
    # Try complex parsing first
    result = llama_parse.parse(file_path)
    return {"text": result.text, "method": "advanced"}
```

### Registering Custom Fallbacks

```python
from app.services.error_handler import get_error_handler

async def s3_fallback(exception, context):
    """Fallback to B2 storage if S3 fails"""
    await b2_storage.upload(context.file_id)

error_handler = get_error_handler()
error_handler.register_fallback(ConnectionError, s3_fallback)
```

## Database Schema

The `processing_logs` table stores all error information:

```sql
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    severity TEXT NOT NULL,  -- critical, error, warning, info
    category TEXT NOT NULL,  -- network, timeout, validation, etc.
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,

    -- Context
    task_id TEXT,
    task_type TEXT,
    file_id TEXT,
    filename TEXT,
    user_id UUID,
    document_id UUID,

    -- Retry info
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Recovery
    recovery_action TEXT,
    resolution_status TEXT,  -- unresolved, retrying, resolved, failed

    -- Metadata
    additional_context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Querying Error Logs

```python
from app.services.supabase_storage import get_supabase_storage

storage = get_supabase_storage()

# Get recent critical errors
logs = await storage.get_processing_logs(
    filters={"severity": "critical"},
    limit=50,
    order_by="timestamp",
    descending=True
)

# Get errors for specific task
logs = await storage.get_processing_logs(
    filters={"task_id": "celery-task-123"}
)

# Get unresolved errors
logs = await storage.get_processing_logs(
    filters={"resolution_status": "unresolved"}
)
```

## Best Practices

### 1. Use Appropriate Retry Strategies
- **Network/Service errors**: Use exponential backoff
- **Database locks**: Use linear backoff
- **Validation errors**: Don't retry, fix the data
- **Parsing errors**: Don't retry, improve parser

### 2. Set Reasonable Retry Limits
```python
# For critical operations
@celery_app.task(**task_with_retry(max_retries=5, retry_backoff=120))

# For less critical operations
@celery_app.task(**task_with_retry(max_retries=3, retry_backoff=60))

# For external APIs with rate limits
@celery_app.task(**task_with_retry(max_retries=10, retry_backoff=300))
```

### 3. Always Log Context
```python
context = ErrorContext(
    task_id=self.request.id,
    task_type="document_processing",
    file_id=file_id,
    filename=filename,
    user_id=user_id,
    additional_context={
        "step": "parsing",
        "parser_version": "2.0"
    }
)
```

### 4. Implement Fallbacks for Critical Paths
```python
# Always have a simpler fallback for critical operations
@with_fallback(simple_processing)
async def complex_processing(data):
    return await advanced_algorithm(data)
```

### 5. Monitor Error Logs
- Set up alerts for critical errors
- Review unresolved errors daily
- Track retry patterns
- Monitor error categories

## Common Patterns

### Pattern 1: API Integration with Retry
```python
from app.utils.celery_retry import task_with_retry

@celery_app.task(**task_with_retry(
    max_retries=5,
    retry_backoff=60,
    retry_backoff_max=3600
))
def call_external_api(data):
    response = requests.post("https://api.example.com", json=data)
    response.raise_for_status()
    return response.json()
```

### Pattern 2: Partial Processing
```python
@celery_app.task(bind=True)
def process_batch(self, items):
    results = []
    errors = []

    for item in items:
        try:
            result = process_item(item)
            results.append(result)
        except Exception as e:
            # Log but continue processing
            context = ErrorContext(
                task_id=self.request.id,
                additional_context={"item_id": item["id"]}
            )
            await error_handler.handle_error(e, context)
            errors.append({"item": item, "error": str(e)})

    return {"results": results, "errors": errors}
```

### Pattern 3: Multi-Stage Pipeline with Checkpoints
```python
@celery_app.task(bind=True)
def multi_stage_pipeline(self, file_id):
    error_handler = get_error_handler()
    context = ErrorContext(task_id=self.request.id, file_id=file_id)

    # Stage 1: Parse (save checkpoint)
    try:
        parsed = parse_document(file_id)
        save_checkpoint(file_id, "parsed", parsed)
    except Exception as e:
        await error_handler.handle_error(e, context)
        # Try to load from checkpoint if available
        parsed = load_checkpoint(file_id, "parsed")
        if not parsed:
            raise

    # Stage 2: Extract (save checkpoint)
    try:
        extracted = extract_metadata(parsed)
        save_checkpoint(file_id, "extracted", extracted)
    except Exception as e:
        await error_handler.handle_error(e, context)
        raise

    return extracted
```

## Metrics and Monitoring

Key metrics to track:
- **Error rate by category**: Identify systemic issues
- **Retry success rate**: Measure retry effectiveness
- **Average retries per task**: Optimize retry counts
- **Unresolved error count**: Identify stuck tasks
- **Error severity distribution**: Prioritize fixes

Query examples:
```sql
-- Error rate by category (last 24 hours)
SELECT category, COUNT(*) as count
FROM processing_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY category
ORDER BY count DESC;

-- Tasks with most retries
SELECT task_type, AVG(retry_count) as avg_retries
FROM processing_logs
WHERE retry_count > 0
GROUP BY task_type
ORDER BY avg_retries DESC;

-- Critical unresolved errors
SELECT *
FROM processing_logs
WHERE severity = 'critical'
  AND resolution_status = 'unresolved'
ORDER BY created_at DESC;
```

## Troubleshooting

### Issue: Tasks retrying infinitely
**Solution**: Check retry configuration, ensure max_retries is set

### Issue: Errors not logged to database
**Solution**: Verify Supabase storage is enabled and processing_logs table exists

### Issue: Too many retries for permanent errors
**Solution**: Update ErrorClassifier to properly categorize the error type

### Issue: Fallback not being called
**Solution**: Ensure decorator is applied correctly and fallback function signature matches

---

**Last Updated**: 2025-01-05
**Empire Version**: v7.3
**Task**: 14 - Error Handling & Graceful Degradation
