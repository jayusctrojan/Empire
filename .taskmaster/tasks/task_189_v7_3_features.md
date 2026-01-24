# Task ID: 189

**Title:** Implement OpenTelemetry Integration for Distributed Tracing

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Add distributed tracing with OpenTelemetry across all services, including trace propagation through Celery tasks and export to configured backend.

**Details:**

1. Create `app/core/tracing.py` with OpenTelemetry setup:

```python
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.context.context import Context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators import set_global_textmap, composite
from fastapi import FastAPI
from app.core.config import settings

def setup_tracing():
    """Configure OpenTelemetry tracing."""
    # Create a resource with service info
    resource = Resource.create({
        "service.name": settings.SERVICE_NAME,
        "service.version": settings.SERVICE_VERSION,
        "deployment.environment": settings.ENVIRONMENT
    })
    
    # Create a tracer provider
    tracer_provider = TracerProvider(resource=resource)
    
    # Configure the exporter
    if settings.OTLP_ENDPOINT:
        # Use OTLP exporter (for Jaeger, Tempo, etc.)
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTLP_ENDPOINT,
            insecure=settings.OTLP_INSECURE
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set the tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    # Set up propagators for distributed tracing
    set_global_textmap(composite.CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator()
    ]))
    
    # Get a tracer
    tracer = trace.get_tracer(settings.SERVICE_NAME, settings.SERVICE_VERSION)
    
    # Instrument libraries
    RequestsInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    
    return tracer

def instrument_fastapi(app: FastAPI):
    """Instrument a FastAPI application."""
    FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())

# Helper functions for Celery task tracing
def inject_trace_info(headers):
    """Inject trace context into Celery task headers."""
    propagator = TraceContextTextMapPropagator()
    propagator.inject(headers)
    return headers

def extract_trace_info(headers):
    """Extract trace context from Celery task headers."""
    propagator = TraceContextTextMapPropagator()
    context = propagator.extract(headers)
    return context

# Context manager for creating spans
class TracingSpan:
    def __init__(self, name, attributes=None, parent_context=None):
        self.name = name
        self.attributes = attributes or {}
        self.parent_context = parent_context
        self.tracer = trace.get_tracer(settings.SERVICE_NAME, settings.SERVICE_VERSION)
        self.span = None
    
    def __enter__(self):
        if self.parent_context:
            self.span = self.tracer.start_span(
                name=self.name,
                attributes=self.attributes,
                context=self.parent_context
            )
        else:
            self.span = self.tracer.start_span(
                name=self.name,
                attributes=self.attributes
            )
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.span.set_status(trace.StatusCode.ERROR, str(exc_val))
            self.span.record_exception(exc_val)
        self.span.end()
```

2. Update `app/main.py` to initialize tracing:

```python
from fastapi import FastAPI
from app.core.tracing import setup_tracing, instrument_fastapi
from app.core.config import settings

# Setup tracing first
tracer = setup_tracing()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.SERVICE_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None
)

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)

# Import and include routers
from app.routes import health, documents, research_projects, upload

app.include_router(health.router, tags=["health"])
app.include_router(documents.router, tags=["documents"])
app.include_router(research_projects.router, tags=["research_projects"])
app.include_router(upload.router, tags=["upload"])
```

3. Update `app/celery_app.py` to add tracing to Celery tasks:

```python
from celery import Celery, Task
from app.core.config import settings
from app.core.tracing import extract_trace_info, TracingSpan
from opentelemetry import trace

app = Celery(
    "empire",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_publish_retry=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_queue_max_priority=10,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    task_default_queue="default"
)

# Define a base task class with tracing
class TracedTask(Task):
    """Base task class that includes OpenTelemetry tracing."""
    
    def apply_async(self, args=None, kwargs=None, **options):
        """Inject trace context when scheduling a task."""
        # Get current headers or initialize empty dict
        headers = options.setdefault("headers", {})
        
        # Inject current trace context into headers
        current_context = trace.get_current_span().get_span_context()
        if current_context.is_valid:
            trace_id = format(current_context.trace_id, "032x")
            span_id = format(current_context.span_id, "016x")
            headers["traceparent"] = f"00-{trace_id}-{span_id}-{int(current_context.trace_flags):02x}"
        
        return super().apply_async(args=args, kwargs=kwargs, **options)
    
    def __call__(self, *args, **kwargs):
        """Extract trace context and create a span for the task execution."""
        # Get the task request
        task_id = self.request.id
        task_name = self.name
        
        # Extract trace context from headers if available
        headers = self.request.get("headers", {})
        parent_context = None
        if "traceparent" in headers:
            parent_context = extract_trace_info(headers)
        
        # Create a span for this task
        with TracingSpan(
            name=f"celery.task.{task_name}",
            attributes={
                "celery.task_id": task_id,
                "celery.task_name": task_name,
                "celery.args": str(args),
                "celery.kwargs": str(kwargs)
            },
            parent_context=parent_context
        ):
            # Execute the task
            return super().__call__(*args, **kwargs)

# Set the base task class
app.Task = TracedTask

# Import tasks to register them
from app.tasks import document_processing, research_tasks, graph_sync
```

4. Add tracing to key services, for example in `app/services/document_management.py`:

```python
from app.core.tracing import TracingSpan

def upload_document(self, file_path, project_id, document_type, metadata=None):
    """Upload a document to B2 storage."""
    with TracingSpan(
        name="document_management.upload_document",
        attributes={
            "project_id": project_id,
            "document_type": document_type,
            "filename": os.path.basename(file_path)
        }
    ) as span:
        # Generate a unique B2 path using project_id and filename
        filename = os.path.basename(file_path)
        b2_path = f"documents/{project_id}/{document_type}/{filename}"
        
        # Use existing B2StorageService to upload the file
        span.add_event("uploading_to_b2")
        b2_url = self.b2_service.upload_file(file_path, b2_path)
        
        # Store metadata in Supabase
        span.add_event("storing_metadata")
        document_record = {
            "project_id": project_id,
            "document_type": document_type,
            "filename": filename,
            "b2_path": b2_path,
            "b2_url": b2_url,
            "metadata": metadata or {},
            "status": "uploaded"
        }
        
        # Insert into documents table
        document_id = self.db.insert("documents", document_record).get("id")
        span.set_attribute("document_id", document_id)
        
        # Return document record with ID
        return {**document_record, "id": document_id}
```

**Test Strategy:**

1. Unit tests:
   - Test trace context injection and extraction
   - Test span creation and attributes
   - Test error handling in spans

2. Integration tests:
   - Test trace propagation across service boundaries
   - Test trace propagation through Celery tasks
   - Test trace export to configured backend

3. Performance tests:
   - Measure overhead of tracing instrumentation
   - Test with different sampling rates
   - Test with high concurrency

## Subtasks

### 189.1. Create OpenTelemetry tracing setup in app/core/tracing.py

**Status:** pending  
**Dependencies:** None  

Implement the core tracing functionality in app/core/tracing.py with OpenTelemetry setup, including tracer provider, span processors, and exporters.

**Details:**

Create the tracing.py module with the following components:
- TracerProvider configuration with service information
- OTLP exporter setup for sending traces to the backend
- Global propagator configuration for distributed tracing
- Helper functions for creating spans
- Context manager for span creation and management
- Error handling and status code setting in spans

### 189.2. Create tracing middleware for FastAPI in app/middleware/tracing.py

**Status:** pending  
**Dependencies:** 189.1  

Implement FastAPI middleware for request tracing and instrumentation of FastAPI applications.

**Details:**

Create middleware/tracing.py with:
- FastAPI instrumentation setup
- Request/response tracing middleware
- Automatic span creation for HTTP requests
- Span attribute population with request details
- Status code tracking
- Error handling for failed requests
- Integration with the core tracing module

### 189.3. Implement trace ID generation and propagation

**Status:** pending  
**Dependencies:** 189.1  

Implement trace ID generation and context propagation across service boundaries using W3C TraceContext.

**Details:**

Implement trace context propagation:
- Configure W3C TraceContext propagator
- Create helper functions for injecting trace context into headers
- Create helper functions for extracting trace context from headers
- Ensure trace IDs are properly formatted and propagated
- Implement baggage propagation for additional metadata
- Update main.py to initialize tracing early in application startup

### 189.4. Implement trace context propagation to Celery tasks

**Status:** pending  
**Dependencies:** 189.1, 189.3  

Extend the tracing system to propagate trace context through Celery tasks for end-to-end tracing.

**Details:**

Update celery_app.py to support tracing:
- Create a TracedTask base class inheriting from Celery's Task
- Override apply_async to inject trace context into task headers
- Override __call__ to extract trace context and create spans
- Add span attributes for task ID, name, and arguments
- Implement error handling for task failures
- Configure Celery instrumentation with OpenTelemetry
- Update task modules to use the traced task base class

### 189.5. Implement trace ID injection in structlog

**Status:** pending  
**Dependencies:** 189.1, 189.3  

Integrate OpenTelemetry trace IDs with structlog for correlated logging across services.

**Details:**

Create logging integration with tracing:
- Configure structlog processor to extract current trace context
- Add trace_id and span_id to log records
- Create helper functions for creating logs with trace context
- Update logging configuration to include trace IDs in log formats
- Ensure trace IDs are consistent between logs and traces
- Add correlation ID support for linking logs to traces
- Document the logging pattern for developers
