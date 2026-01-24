# Task ID: 127

**Title:** Integrate with B2 Workflow Service

**Status:** done

**Dependencies:** 122 ✓, 125 ✓, 126 ✓

**Priority:** high

**Description:** Integrate the Content Prep Agent with the B2 Workflow Service to intercept file uploads and trigger content preparation.

**Details:**

Modify the existing B2 Workflow Service to hook into the Content Prep Agent. This involves:

1. Intercepting new file uploads to the `pending/` folder
2. Triggering content set detection and analysis
3. Moving files to `processing/` in the correct order based on the manifest

Pseudo-code for the integration:

```python
# In app/services/b2_workflow.py

from app.services.content_prep_agent import ContentPrepAgent

class B2WorkflowService:
    # ... existing code ...
    
    def __init__(self):
        # ... existing init ...
        self.content_prep_agent = ContentPrepAgent()
    
    async def process_pending_folder(self):
        """Process files in the pending folder"""
        # Get files from pending folder
        pending_files = await self.list_pending_files()
        
        if not pending_files:
            return
        
        # Check if we need content preparation
        if len(pending_files) > 1:
            # Detect content sets
            content_sets, standalone_files = self.content_prep_agent.detect_content_sets(pending_files)
            
            # Process standalone files immediately
            for file in standalone_files:
                await self.move_to_processing(file['path'])
                await self.trigger_processing(file['path'])
            
            # Process content sets
            for content_set in content_sets:
                # Store content set in database
                await self.store_content_set(content_set)
                
                # Check completeness
                if not content_set.is_complete:
                    # Log warning about incomplete set
                    self.logger.warning(f"Incomplete content set detected: {content_set.name}")
                    # Send notification to user (implementation depends on notification system)
                    await self.notify_incomplete_set(content_set)
                    # Skip processing until user acknowledges
                    continue
                
                # Generate manifest
                manifest = self.content_prep_agent.generate_manifest(content_set)
                
                # Process files in order
                for file in manifest.ordered_files:
                    await self.move_to_processing(file.b2_path)
                    # Pass content set context to processing task
                    await self.trigger_processing(file.b2_path, context=manifest.context)
        else:
            # Single file - process immediately
            file = pending_files[0]
            await self.move_to_processing(file['path'])
            await self.trigger_processing(file['path'])
    
    async def store_content_set(self, content_set):
        """Store content set in database"""
        # Implementation depends on database access method
        pass
    
    async def notify_incomplete_set(self, content_set):
        """Notify user about incomplete content set"""
        # Implementation depends on notification system
        pass
    
    async def trigger_processing(self, file_path, context=None):
        """Trigger processing task for a file"""
        # ... existing code ...
        
        # Add content set context if available
        task_data = {
            "file_path": file_path,
            # ... existing task data ...
        }
        
        if context:
            task_data["content_set_context"] = context
        
        # Trigger Celery task
        # ... existing code ...
```

Also create a Celery task for content set detection and processing:

```python
# In app/tasks/content_prep_tasks.py

from celery import shared_task
from app.services.content_prep_agent import ContentPrepAgent

@shared_task
def detect_content_sets(b2_folder):
    """Detect content sets in a B2 folder"""
    agent = ContentPrepAgent()
    
    # List files in folder
    # Detect content sets
    # Store in database
    
    return {"content_sets": [], "standalone_files": []}

@shared_task
def process_content_set(content_set_id, proceed_incomplete=False):
    """Process a content set"""
    agent = ContentPrepAgent()
    
    # Get content set from database
    # Generate manifest
    # Trigger processing for each file in order
    
    return {"status": "processing", "files_count": 0}
```

**Test Strategy:**

1. Integration tests with mocked B2 service
2. Test single file pass-through
3. Test multi-file content set detection
4. Test incomplete set handling and notification
5. Verify correct processing order
6. Test with various file naming patterns
7. Test error handling and recovery
