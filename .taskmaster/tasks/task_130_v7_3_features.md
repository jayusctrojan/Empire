# Task ID: 130

**Title:** Implement Retention Policy and Cleanup

**Status:** done

**Dependencies:** 123 ✓

**Priority:** low

**Description:** Implement the 90-day retention policy for content set metadata and create a scheduled cleanup task.

**Details:**

Create a scheduled task to enforce the 90-day retention policy for content set metadata. This includes:

1. Creating a Celery periodic task for cleanup
2. Implementing the database cleanup logic
3. Adding logging and monitoring

Pseudo-code:

```python
# In app/tasks/scheduled_tasks.py

from celery import shared_task
from celery.schedules import crontab
from app.db.supabase import get_supabase_client
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Register as a periodic task to run daily at 3 AM
@shared_task
def cleanup_content_sets():
    """Clean up content sets older than 90 days"""
    logger.info("Starting content set cleanup task")
    
    try:
        # Calculate cutoff date (90 days ago)
        cutoff_date = datetime.now() - timedelta(days=90)
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Find completed content sets older than 90 days
        response = supabase.table("content_sets") \
            .select("id") \
            .eq("processing_status", "complete") \
            .lt("updated_at", cutoff_date.isoformat()) \
            .execute()
        
        if response.data:
            content_set_ids = [item["id"] for item in response.data]
            count = len(content_set_ids)
            logger.info(f"Found {count} content sets to clean up")
            
            # Delete in batches to avoid timeout
            batch_size = 50
            for i in range(0, count, batch_size):
                batch = content_set_ids[i:i+batch_size]
                
                # Delete content set files first (due to foreign key constraint)
                supabase.table("content_set_files") \
                    .delete() \
                    .in_("content_set_id", batch) \
                    .execute()
                
                # Delete content sets
                supabase.table("content_sets") \
                    .delete() \
                    .in_("id", batch) \
                    .execute()
                
                logger.info(f"Deleted batch {i//batch_size + 1} ({len(batch)} content sets)")
            
            return {"status": "success", "deleted_count": count}
        else:
            logger.info("No content sets to clean up")
            return {"status": "success", "deleted_count": 0}
    
    except Exception as e:
        logger.error(f"Error in content set cleanup: {str(e)}")
        return {"status": "error", "error": str(e)}
```

Register the periodic task in Celery beat schedule:

```python
# In app/celery_app.py

app.conf.beat_schedule = {
    # ... existing scheduled tasks ...
    
    'cleanup-content-sets-daily': {
        'task': 'app.tasks.scheduled_tasks.cleanup_content_sets',
        'schedule': crontab(hour=3, minute=0),  # Run at 3:00 AM
    },
}
```

Add monitoring and metrics:

```python
# In app/monitoring/metrics.py

from prometheus_client import Counter, Gauge

# Counters for content set operations
content_sets_created = Counter('content_sets_created', 'Number of content sets created')
content_sets_processed = Counter('content_sets_processed', 'Number of content sets processed')
content_sets_deleted = Counter('content_sets_deleted', 'Number of content sets deleted by retention policy')

# Gauges for current state
content_sets_pending = Gauge('content_sets_pending', 'Number of pending content sets')
content_sets_processing = Gauge('content_sets_processing', 'Number of processing content sets')
content_sets_complete = Gauge('content_sets_complete', 'Number of complete content sets')
```

**Test Strategy:**

1. Unit tests for cleanup logic
2. Test with mock database responses
3. Test date calculation and filtering
4. Test batch processing
5. Test error handling
6. Integration test with test database
7. Verify metrics are updated correctly
