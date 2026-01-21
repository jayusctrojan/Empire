# Task ID: 199

**Title:** Implement OpenTelemetry Integration for Distributed Tracing

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Add distributed tracing with OpenTelemetry across all services, including trace propagation through Celery tasks and export to a configured backend.

**Details:**

This task involves creating app/core/tracing.py with OpenTelemetry setup and integrating it throughout the application:

```python
# app/core/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.context.context import Context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Global propagator for trace context
propagator = TraceContextTextMapPropagator()

def setup_tracing(service_name="empire-api"):
    """Setup OpenTelemetry tracing"""
    try:
        # Create a resource with service info
        resource = Resource.create({
            "service.name": service_name,
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT
        })
        
        # Create a tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Configure the exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTLP_ENDPOINT,
            insecure=settings.ENVIRONMENT != "production"
        )
        
        # Add span processor to the tracer provider
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set the tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Get a tracer
        tracer = trace.get_tracer(service_name)
        
        # Instrument libraries
        RequestsInstrumentor().instrument()
        CeleryInstrumentor().instrument()
        RedisInstrumentor().instrument()
        
        logger.info(f"OpenTelemetry tracing initialized for {service_name}")
        
        return tracer
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {str(e)}")
        # Return a no-op tracer that won't break the application if tracing fails
        return trace.get_tracer(service_name)

def instrument_fastapi(app):
    """Instrument FastAPI application"""
    try:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {str(e)}")

def instrument_sqlalchemy(engine):
    """Instrument SQLAlchemy engine"""
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {str(e)}")

# Celery task tracing
def get_celery_carrier(task_id, parent_span=None):
    """Create carrier for Celery task with trace context"""
    carrier = {}
    if parent_span:
        ctx = trace.set_span_in_context(parent_span)
    else:
        ctx = Context()
    propagator.inject(carrier=carrier, context=ctx)
    return carrier

def extract_celery_context(headers):
    """Extract trace context from Celery task headers"""
    return propagator.extract(carrier=headers)

# Trace decorator for functions
def traced(name=None):
    """Decorator to add tracing to a function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get the tracer
            tracer = trace.get_tracer("empire-api")
            # Start a span
            span_name = name or func.__name__
            with tracer.start_as_current_span(span_name) as span:
                # Add attributes to the span
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.args_length", len(args))
                span.set_attribute("function.kwargs_length", len(kwargs))
                
                # Execute the function
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    # Record exception in span
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        return wrapper
    return decorator
```

Integrate OpenTelemetry in the main FastAPI application (app/main.py):

```python
from fastapi import FastAPI, Request, Response
from app.core.tracing import setup_tracing, instrument_fastapi
from app.core.config import settings
import time
import logging

logger = logging.getLogger(__name__)

# Initialize tracing
tracer = setup_tracing("empire-api")

app = FastAPI(
    title="Empire API",
    description="Empire v7.3 API",
    version=settings.VERSION
)

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)

# Add middleware for request logging with trace IDs
@app.middleware("http")
async def add_trace_id_to_response(request: Request, call_next):
    start_time = time.time()
    
    # Get current span and trace ID
    current_span = trace.get_current_span()
    trace_id = current_span.get_span_context().trace_id if current_span else None
    
    # Convert trace ID to hex string if it exists
    trace_id_hex = format(trace_id, '032x') if trace_id else None
    
    # Add trace context to logs
    if trace_id_hex:
        logger.info(f"Request started: {request.method} {request.url.path} [trace_id={trace_id_hex}]")
    else:
        logger.info(f"Request started: {request.method} {request.url.path}")
    
    # Process the request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Add trace ID to response headers
    if trace_id_hex:
        response.headers["X-Trace-ID"] = trace_id_hex
        logger.info(f"Request completed: {request.method} {request.url.path} {response.status_code} in {duration:.3f}s [trace_id={trace_id_hex}]")
    else:
        logger.info(f"Request completed: {request.method} {request.url.path} {response.status_code} in {duration:.3f}s")
    
    return response
```

Integrate OpenTelemetry in Celery tasks (app/celery_app.py):

```python
from celery import Celery, Task
from app.core.config import settings
from app.core.tracing import setup_tracing, extract_celery_context
from opentelemetry import trace
import logging

logger = logging.getLogger(__name__)

# Initialize tracing
tracer = setup_tracing("empire-celery")

class TracedTask(Task):
    """Custom Celery Task class with tracing"""
    def __call__(self, *args, **kwargs):
        # Extract trace context from headers if available
        headers = self.request.headers or {}
        context = extract_celery_context(headers)
        
        # Start a new span with the extracted context
        with tracer.start_as_current_span(
            f"celery.task.{self.name}",
            context=context
        ) as span:
            # Add task info to span
            span.set_attribute("celery.task.id", self.request.id)
            span.set_attribute("celery.task.name", self.name)
            span.set_attribute("celery.task.args_length", len(args))
            span.set_attribute("celery.task.kwargs_length", len(kwargs))
            
            # Get trace ID for logging
            trace_id = span.get_span_context().trace_id
            trace_id_hex = format(trace_id, '032x') if trace_id else None
            
            # Log task execution with trace ID
            if trace_id_hex:
                logger.info(f"Executing task {self.name}[{self.request.id}] [trace_id={trace_id_hex}]")
            else:
                logger.info(f"Executing task {self.name}[{self.request.id}]")
            
            try:
                # Execute the task
                return super().__call__(*args, **kwargs)
            except Exception as e:
                # Record exception in span
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

# Initialize Celery app with tracing
celery_app = Celery(
    "empire",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_send_sent_event=True,
    task_default_rate_limit="100/m",
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    task_routes={
        "app.tasks.document_processing.*": {"queue": "documents"},
        "app.tasks.research_tasks.*": {"queue": "research"},
        "app.tasks.graph_sync.*": {"queue": "graph"}
    }
)

# Set default task base class to TracedTask
celery_app.Task = TracedTask
```

Add OpenTelemetry configuration to app/core/config.py:

```python
# Add to existing settings
class Settings:
    # ... existing settings ...
    
    # OpenTelemetry settings
    OTLP_ENDPOINT: str = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
    
    # Celery settings
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
    CELERY_WORKER_CONCURRENCY: int = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
```

**Test Strategy:**

1. Unit tests for tracing functionality
   - Test span creation and propagation
   - Test context extraction and injection
   - Test traced decorator
2. Integration tests for tracing across services
   - Test trace propagation from API to Celery tasks
   - Test trace propagation through multiple services
3. Test cases:
   - API request with trace context
   - Celery task with trace context
   - Error handling and exception recording
   - Trace ID in response headers
4. Verify traces in configured backend (Jaeger, etc.)
5. Performance impact testing
   - Measure overhead of tracing
   - Test with different sampling rates
