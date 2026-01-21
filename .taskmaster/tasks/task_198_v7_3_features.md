# Task ID: 198

**Title:** Implement Research Project Celery Integration

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Complete the Celery task integration for research projects by implementing task triggering for project initialization and task revocation on project cancellation.

**Details:**

This task involves completing 2 TODOs in app/services/research_project_service.py:

```python
from app.db.supabase import get_supabase_client
from app.celery_app import celery_app
from celery.result import AsyncResult
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ResearchProjectService:
    def __init__(self, db_client=None):
        self.db = db_client or get_supabase_client()
    
    def create_project(self, project_data, user_id):
        """Create a new research project and trigger initialization"""
        try:
            # Set default values
            project_data["owner_id"] = user_id
            project_data["status"] = "initializing"
            project_data["created_at"] = datetime.now()
            
            # Insert project into database
            result = self.db.table("research_projects").insert(project_data).execute()
            
            if not result.data:
                raise Exception("Failed to create project")
                
            project_id = result.data[0]["id"]
            
            # Trigger Celery task for project initialization
            task = celery_app.send_task(
                "app.tasks.research_tasks.initialize_project",
                args=[project_id, user_id],
                kwargs={"project_data": project_data}
            )
            
            # Store task ID in the project record
            self.db.table("research_projects")\
                .update({"initialization_task_id": task.id})\
                .eq("id", project_id)\
                .execute()
            
            logger.info(f"Created project {project_id} with initialization task {task.id}")
            
            return {"id": project_id, "task_id": task.id}
        except Exception as e:
            logger.error(f"Failed to create project: {str(e)}")
            raise
    
    def cancel_project(self, project_id):
        """Cancel a research project and revoke pending tasks"""
        try:
            # Get project details
            project = self.db.table("research_projects")\
                .select("*")\
                .eq("id", project_id)\
                .single()\
                .execute()
                
            if not project.data:
                raise Exception(f"Project {project_id} not found")
                
            # Check if project can be cancelled
            if project.data["status"] in ["completed", "cancelled", "failed"]:
                raise Exception(f"Project {project_id} is already in final state: {project.data['status']}")
            
            # Implement task revocation on project cancellation
            # Revoke initialization task if it exists and is still running
            init_task_id = project.data.get("initialization_task_id")
            if init_task_id:
                # Check task status
                task_result = AsyncResult(init_task_id)
                if not task_result.ready():
                    # Revoke the task
                    celery_app.control.revoke(init_task_id, terminate=True)
                    logger.info(f"Revoked initialization task {init_task_id} for project {project_id}")
            
            # Revoke any other pending tasks for this project
            pending_tasks = self.db.table("research_tasks")\
                .select("id,celery_task_id")\
                .eq("project_id", project_id)\
                .in_("status", ["pending", "running"])\
                .execute()
                
            for task in pending_tasks.data:
                if task.get("celery_task_id"):
                    celery_app.control.revoke(task["celery_task_id"], terminate=True)
                    logger.info(f"Revoked task {task['celery_task_id']} for project {project_id}")
                    
                    # Update task status
                    self.db.table("research_tasks")\
                        .update({"status": "cancelled", "updated_at": datetime.now()})\
                        .eq("id", task["id"])\
                        .execute()
            
            # Update project status
            self.db.table("research_projects")\
                .update({"status": "cancelled", "updated_at": datetime.now()})\
                .eq("id", project_id)\
                .execute()
                
            return {"success": True, "message": f"Project {project_id} cancelled successfully"}
        except Exception as e:
            logger.error(f"Failed to cancel project {project_id}: {str(e)}")
            raise

# Add the initialize_project task to app/tasks/research_tasks.py if it doesn't exist
"""
@celery_app.task(bind=True, max_retries=3)
def initialize_project(self, project_id, user_id, project_data=None):
    """Initialize a research project"""
    try:
        logger.info(f"Initializing project {project_id}")
        db = get_supabase_client()
        
        # Update project status
        db.table("research_projects")\
            .update({"status": "initializing", "updated_at": datetime.now()})\
            .eq("id", project_id)\
            .execute()
        
        # Create default folders
        folders = [
            {"name": "Documents", "project_id": project_id, "parent_id": None},
            {"name": "Research", "project_id": project_id, "parent_id": None},
            {"name": "Reports", "project_id": project_id, "parent_id": None}
        ]
        db.table("project_folders").insert(folders).execute()
        
        # Create default tasks based on project type
        if project_data and project_data.get("project_type"):
            project_type = project_data["project_type"]
            
            # Get task templates for this project type
            templates = db.table("task_templates")\
                .select("*")\
                .eq("project_type", project_type)\
                .execute()
                
            # Create tasks from templates
            for template in templates.data:
                task = {
                    "project_id": project_id,
                    "title": template["title"],
                    "description": template["description"],
                    "status": "pending",
                    "created_by": user_id,
                    "created_at": datetime.now()
                }
                db.table("research_tasks").insert(task).execute()
        
        # Update project status to active
        db.table("research_projects")\
            .update({"status": "active", "updated_at": datetime.now()})\
            .eq("id", project_id)\
            .execute()
            
        logger.info(f"Project {project_id} initialized successfully")
        return {"success": True, "project_id": project_id}
    except Exception as e:
        logger.error(f"Failed to initialize project {project_id}: {str(e)}")
        # Retry up to max_retries
        self.retry(exc=e, countdown=60)  # Retry after 1 minute
"""
```

**Test Strategy:**

1. Unit tests for create_project and cancel_project methods
   - Test project creation with task triggering
   - Test project cancellation with task revocation
2. Integration tests with Celery
3. Test cases:
   - Create project and verify initialization task is triggered
   - Cancel project in different states (initializing, active)
   - Verify task revocation works for different task states
   - Test error handling and retries
4. Mock Celery for unit tests
5. Test with actual Celery worker in integration environment
6. Verify database state after operations
