"""
Empire v7.3 - Celery Configuration
Background task processing for document parsing, embedding generation, and graph synchronization

Task 12: Enhanced with unified StatusBroadcaster for:
- Redis Pub/Sub broadcasting
- Database status persistence
- Standardized TaskStatusMessage schema
"""

import os
import time
import traceback
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_success, task_retry
from prometheus_client import Counter, Histogram
from dotenv import load_dotenv

load_dotenv()

# Prometheus metrics for Celery tasks (basic tracking)
CELERY_TASKS = Counter('empire_celery_tasks_total', 'Total Celery tasks', ['task_name', 'status'])
CELERY_TASK_DURATION = Histogram('empire_celery_task_duration_seconds', 'Celery task duration', ['task_name'])

# Note: Business metrics for task processing are defined in monitoring_service.py
# Import monitoring service for detailed metrics
from app.services.monitoring_service import get_monitoring_service
from app.services.supabase_storage import get_supabase_storage

# Task 12: Import StatusBroadcaster for unified status broadcasting
from app.services.status_broadcaster import (
    get_sync_status_broadcaster,
    get_task_type_from_name
)
from app.models.task_status import TaskType

# Initialize monitoring service
_supabase_storage = get_supabase_storage()
_monitoring_service = get_monitoring_service(_supabase_storage)

# Task timing storage (to calculate duration)
_task_start_times = {}

# Task 12: Get sync broadcaster for signal handlers
_status_broadcaster = None

def _get_status_broadcaster():
    """Lazy load the status broadcaster"""
    global _status_broadcaster
    if _status_broadcaster is None:
        _status_broadcaster = get_sync_status_broadcaster()
    return _status_broadcaster

# Redis broker URL
# Clean URL to remove invalid SSL parameters
_raw_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_URL = _raw_redis_url.split("?")[0] if "?" in _raw_redis_url else _raw_redis_url

_raw_result_backend = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_RESULT_BACKEND = _raw_result_backend.split("?")[0] if "?" in _raw_result_backend else _raw_result_backend

# Create Celery app
celery_app = Celery(
    "empire",
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.document_processing',
        'app.tasks.embedding_generation',
        'app.tasks.graph_sync',
        'app.tasks.crewai_workflows'
    ]
)

# Celery configuration with priority queue support
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Prefetch 1 task at a time (required for priority)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    result_expires=86400,  # Results expire after 24 hours

    # Priority queue configuration
    broker_transport_options={
        'priority_steps': list(range(10)),  # Support priority 0-9
        'queue_order_strategy': 'priority',  # Process by priority
    },

    # Task routing - default queues by task type
    task_routes={
        'app.tasks.document_processing.*': {'queue': 'documents'},
        'app.tasks.embedding_generation.*': {'queue': 'embeddings'},
        'app.tasks.graph_sync.*': {'queue': 'graph'},
        'app.tasks.crewai_workflows.*': {'queue': 'crewai'},
        'app.tasks.send_to_dead_letter_queue': {'queue': 'dead_letter'},
        'app.tasks.inspect_dead_letter_queue': {'queue': 'dead_letter'},
        'app.tasks.retry_from_dead_letter_queue': {'queue': 'dead_letter'}
    },

    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
    task_default_priority=5,  # Default priority (middle of 0-9 scale)
)

# Priority levels (0-9 scale, 9 is highest)
PRIORITY_URGENT = 9
PRIORITY_HIGH = 7
PRIORITY_NORMAL = 5
PRIORITY_LOW = 3
PRIORITY_BACKGROUND = 1


# Task signals for monitoring
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """
    Track task start and broadcast status - Task 12 Enhanced
    Uses unified StatusBroadcaster for Redis Pub/Sub and database persistence.
    """
    _task_start_times[task_id] = time.time()
    print(f"📋 Task started: {task.name} [{task_id}]")

    # Task 12: Use unified StatusBroadcaster
    try:
        broadcaster = _get_status_broadcaster()

        # Extract resource IDs from task kwargs if available
        task_kwargs = kwargs.get('kwargs', {})
        document_id = task_kwargs.get('document_id')
        query_id = task_kwargs.get('query_id') or task_kwargs.get('task_id')
        user_id = task_kwargs.get('user_id')
        session_id = task_kwargs.get('session_id')

        # Determine task type from task name
        task_type = get_task_type_from_name(task.name)

        # Build metadata
        metadata = {}
        if task_kwargs.get('filename'):
            metadata['filename'] = task_kwargs.get('filename')
        if task_kwargs.get('file_size'):
            metadata['file_size'] = task_kwargs.get('file_size')

        # Broadcast started status via Redis Pub/Sub + database
        broadcaster.broadcast_started(
            task_id=task_id,
            task_name=task.name,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata if metadata else None
        )
    except Exception as e:
        # Don't let broadcast errors break task execution
        print(f"⚠️  Status broadcast failed for task start: {e}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, retval=None, state=None, **kwargs):
    """
    Track task completion and broadcast status - Task 12 Enhanced
    Uses unified StatusBroadcaster for Redis Pub/Sub and database persistence.
    """
    # Calculate duration
    duration = None
    if task_id in _task_start_times:
        duration = time.time() - _task_start_times[task_id]
        CELERY_TASK_DURATION.labels(task_name=task.name).observe(duration)
        del _task_start_times[task_id]

    print(f"✅ Task completed: {task.name} [{task_id}]")
    CELERY_TASKS.labels(task_name=task.name, status='success').inc()

    # Task 12: Use unified StatusBroadcaster
    try:
        broadcaster = _get_status_broadcaster()

        # Extract resource IDs from task kwargs if available
        task_kwargs = kwargs.get('kwargs', {})
        document_id = task_kwargs.get('document_id')
        query_id = task_kwargs.get('query_id') or task_kwargs.get('task_id')
        user_id = task_kwargs.get('user_id')
        session_id = task_kwargs.get('session_id')

        # Determine task type from task name
        task_type = get_task_type_from_name(task.name)

        # Build metadata
        metadata = {}
        if duration is not None:
            metadata['duration_seconds'] = round(duration, 2)

        # Prepare result (sanitize for JSON serialization)
        result_data = None
        if retval is not None and isinstance(retval, dict):
            result_data = retval

        # Broadcast success status via Redis Pub/Sub + database
        broadcaster.broadcast_success(
            task_id=task_id,
            task_name=task.name,
            result=result_data,
            runtime_seconds=duration,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=metadata if metadata else None
        )
    except Exception as e:
        # Don't let broadcast errors break task execution
        print(f"⚠️  Status broadcast failed for task completion: {e}")


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Track successful task completion"""
    # Additional success tracking can be added here
    pass


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, einfo=None, **kw):
    """
    Track task failure and broadcast status - Task 12 Enhanced
    Uses unified StatusBroadcaster for Redis Pub/Sub and database persistence.
    Also routes to Dead Letter Queue if all retries exhausted.
    """
    print(f"❌ Task failed: {sender.name} [{task_id}]: {exception}")
    CELERY_TASKS.labels(task_name=sender.name, status='failure').inc()

    # Calculate duration if available
    duration = None
    if task_id in _task_start_times:
        duration = time.time() - _task_start_times[task_id]
        del _task_start_times[task_id]

    # Get retry info
    from celery import current_app
    task_state = current_app.backend.get_task_meta(task_id)
    retry_count = task_state.get('retries', 0) if task_state else 0
    max_retries = sender.max_retries if hasattr(sender, 'max_retries') else 3

    # Task 12: Use unified StatusBroadcaster
    try:
        broadcaster = _get_status_broadcaster()

        # Extract resource IDs from task kwargs if available
        task_kwargs = kwargs or {}
        document_id = task_kwargs.get('document_id')
        query_id = task_kwargs.get('query_id') or task_kwargs.get('task_id')
        user_id = task_kwargs.get('user_id')
        session_id = task_kwargs.get('session_id')

        # Determine task type from task name
        task_type = get_task_type_from_name(sender.name)

        # Get stack trace if available
        stack_trace = None
        if einfo:
            stack_trace = str(einfo.traceback) if hasattr(einfo, 'traceback') else str(einfo)

        # Broadcast failure status via Redis Pub/Sub + database
        broadcaster.broadcast_failure(
            task_id=task_id,
            task_name=sender.name,
            error_type=type(exception).__name__,
            error_message=str(exception),
            retry_count=retry_count,
            max_retries=max_retries,
            stack_trace=stack_trace,
            runtime_seconds=duration,
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata={"args": str(args)[:500] if args else None}
        )
    except Exception as e:
        # Don't let broadcast errors break task execution
        print(f"⚠️  Status broadcast failed for task failure: {e}")

    # If task has no more retries, send to Dead Letter Queue
    if task_state and retry_count >= max_retries:
        print(f"💀 Task {task_id} exhausted all retries - routing to Dead Letter Queue")

        # Route to DLQ by applying to dead_letter queue
        send_to_dead_letter_queue.apply_async(
            args=[{
                'task_id': task_id,
                'task_name': sender.name,
                'exception': str(exception),
                'args': args,
                'kwargs': kwargs,
                'retries': retry_count,
                'max_retries': max_retries
            }],
            queue='dead_letter'
        )


@task_retry.connect
def task_retry_handler(sender=None, request=None, reason=None, einfo=None, **kwargs):
    """
    Track task retry and broadcast status - Task 12
    Uses unified StatusBroadcaster for Redis Pub/Sub and database persistence.
    """
    task_id = request.id if request else None
    print(f"🔄 Task retrying: {sender.name} [{task_id}]: {reason}")
    CELERY_TASKS.labels(task_name=sender.name, status='retry').inc()

    # Task 12: Use unified StatusBroadcaster
    try:
        broadcaster = _get_status_broadcaster()

        # Extract resource IDs from task kwargs if available
        task_kwargs = request.kwargs if request else {}
        document_id = task_kwargs.get('document_id')
        query_id = task_kwargs.get('query_id') or task_kwargs.get('task_id')
        user_id = task_kwargs.get('user_id')
        session_id = task_kwargs.get('session_id')

        # Determine task type from task name
        task_type = get_task_type_from_name(sender.name)

        # Get retry count and countdown
        retry_count = request.retries if request else 0
        max_retries = sender.max_retries if hasattr(sender, 'max_retries') else 3
        countdown = getattr(request, 'countdown', 60) or 60

        # Broadcast retry status via Redis Pub/Sub + database
        broadcaster.broadcast_retry(
            task_id=task_id,
            task_name=sender.name,
            retry_count=retry_count,
            max_retries=max_retries,
            error_message=str(reason),
            countdown_seconds=int(countdown),
            task_type=task_type,
            document_id=document_id,
            query_id=query_id,
            user_id=user_id,
            metadata=None
        )
    except Exception as e:
        # Don't let broadcast errors break task execution
        print(f"⚠️  Status broadcast failed for task retry: {e}")


# Health check task
@celery_app.task(name='app.tasks.health_check')
def health_check():
    """Simple health check task"""
    return {
        'status': 'healthy',
        'service': 'Empire Celery Worker',
        'version': '7.3.0'
    }


# Dead Letter Queue handler
@celery_app.task(name='app.tasks.send_to_dead_letter_queue', queue='dead_letter')
def send_to_dead_letter_queue(failed_task_info: dict):
    """
    Store failed task information in the Dead Letter Queue

    This task runs in the 'dead_letter' queue and stores information about
    tasks that have exhausted all retry attempts for manual inspection.

    Args:
        failed_task_info: Dictionary containing failed task metadata
    """
    import json
    from datetime import datetime

    print(f"💀 Dead Letter Queue: Processing failed task {failed_task_info.get('task_name')}")

    # Log to console (in production, this would go to a database or monitoring system)
    dlq_entry = {
        'task_id': failed_task_info.get('task_id'),
        'task_name': failed_task_info.get('task_name'),
        'exception': failed_task_info.get('exception'),
        'args': failed_task_info.get('args'),
        'kwargs': failed_task_info.get('kwargs'),
        'retries': failed_task_info.get('retries'),
        'max_retries': failed_task_info.get('max_retries'),
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'dead_letter'
    }

    # TODO: Store in database for permanent tracking
    # For now, log to console
    print(f"💀 DLQ Entry: {json.dumps(dlq_entry, indent=2)}")

    return dlq_entry


# Task to inspect Dead Letter Queue
@celery_app.task(name='app.tasks.inspect_dead_letter_queue')
def inspect_dead_letter_queue():
    """
    Inspect and return Dead Letter Queue entries

    Returns:
        List of failed task entries (currently from logs, should be from DB)
    """
    # TODO: Query database for DLQ entries
    # For now, return placeholder
    return {
        'status': 'success',
        'message': 'Dead Letter Queue inspection placeholder',
        'note': 'In production, this would query a database for failed tasks'
    }


# Task to retry a failed task from DLQ
@celery_app.task(name='app.tasks.retry_from_dead_letter_queue')
def retry_from_dead_letter_queue(task_id: str, task_name: str, args: list, kwargs: dict):
    """
    Retry a failed task from the Dead Letter Queue

    Args:
        task_id: Original task ID
        task_name: Task name to retry
        args: Original task arguments
        kwargs: Original task keyword arguments

    Returns:
        New task ID
    """
    print(f"🔄 Retrying task from DLQ: {task_name} (original ID: {task_id})")

    # Get the task by name
    task = celery_app.tasks.get(task_name)

    if task:
        # Re-submit the task with original arguments
        result = task.apply_async(args=args, kwargs=kwargs)
        print(f"✅ Task resubmitted with new ID: {result.id}")
        return {
            'status': 'success',
            'original_task_id': task_id,
            'new_task_id': result.id,
            'task_name': task_name
        }
    else:
        print(f"❌ Task {task_name} not found")
        return {
            'status': 'error',
            'message': f'Task {task_name} not found',
            'task_id': task_id
        }


if __name__ == '__main__':
    celery_app.start()
