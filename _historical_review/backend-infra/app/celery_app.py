"""
Empire v7.3 - Celery Configuration
Background task processing for document parsing, embedding generation, and graph synchronization
"""

import os
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from prometheus_client import Counter, Histogram
from dotenv import load_dotenv

load_dotenv()

# Prometheus metrics for Celery tasks
CELERY_TASKS = Counter('empire_celery_tasks_total', 'Total Celery tasks', ['task_name', 'status'])
CELERY_TASK_DURATION = Histogram('empire_celery_task_duration_seconds', 'Celery task duration', ['task_name'])

# Redis broker URL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

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

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Prefetch 1 task at a time
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    result_expires=86400,  # Results expire after 24 hours
    task_routes={
        'app.tasks.document_processing.*': {'queue': 'documents'},
        'app.tasks.embedding_generation.*': {'queue': 'embeddings'},
        'app.tasks.graph_sync.*': {'queue': 'graph'},
        'app.tasks.crewai_workflows.*': {'queue': 'crewai'}
    },
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
)


# Task signals for monitoring
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Track task start"""
    print(f"📋 Task started: {task.name} [{task_id}]")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Track task completion"""
    print(f"✅ Task completed: {task.name} [{task_id}]")
    CELERY_TASKS.labels(task_name=task.name, status='success').inc()


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Track task failure"""
    print(f"❌ Task failed: {sender.name} [{task_id}]: {exception}")
    CELERY_TASKS.labels(task_name=sender.name, status='failure').inc()


# Health check task
@celery_app.task(name='app.tasks.health_check')
def health_check():
    """Simple health check task"""
    return {
        'status': 'healthy',
        'service': 'Empire Celery Worker',
        'version': '7.3.0'
    }


if __name__ == '__main__':
    celery_app.start()
