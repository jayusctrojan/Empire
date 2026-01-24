# Task ID: 187

**Title:** Implement Research Project Celery Integration

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Complete the Research Project Service by implementing Celery task integration for project initialization and task revocation on project cancellation.

**Details:**

In `app/services/research_project_service.py`, implement the following TODOs:

```python
def create_project(self, name, description, owner_id, settings=None):
    """Create a new research project."""
    project_id = str(uuid.uuid4())
    
    # Create project record
    project = {
        "id": project_id,
        "name": name,
        "description": description,
        "owner_id": owner_id,
        "members": [],
        "settings": settings or {},
        "status": "initializing",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    # Insert into database
    self.db.insert("research_projects", project)
    
    # Trigger Celery task for project initialization
    task = initialize_research_project.delay(
        project_id=project_id,
        owner_id=owner_id,
        settings=settings or {}
    )
    
    # Store task ID in project record
    self.db.update("research_projects", project_id, {
        "initialization_task_id": task.id
    })
    
    return project

def cancel_project(self, project_id):
    """Cancel a research project and clean up resources."""
    # Get project
    project = self.db.get("research_projects", project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")
    
    # Check if project can be cancelled
    if project.get("status") in ["completed", "cancelled", "failed"]:
        raise ValueError(f"Project cannot be cancelled in status: {project.get('status')}")
    
    # Implement task revocation on project cancellation
    # Revoke initialization task if still running
    if project.get("initialization_task_id"):
        try:
            app.control.revoke(
                project["initialization_task_id"],
                terminate=True,
                signal="SIGTERM"
            )
        except Exception as e:
            logger.error(f"Error revoking initialization task: {str(e)}")
    
    # Revoke all running tasks for this project
    running_tasks = self.db.query(
        "task_queue",
        {"project_id": project_id, "status": "running"}
    )
    
    for task in running_tasks:
        if task.get("celery_task_id"):
            try:
                app.control.revoke(
                    task["celery_task_id"],
                    terminate=True,
                    signal="SIGTERM"
                )
            except Exception as e:
                logger.error(f"Error revoking task {task['id']}: {str(e)}")
            
            # Update task status
            self.db.update("task_queue", task["id"], {
                "status": "cancelled",
                "updated_at": datetime.now().isoformat()
            })
    
    # Update project status
    self.db.update("research_projects", project_id, {
        "status": "cancelled",
        "updated_at": datetime.now().isoformat(),
        "cancelled_at": datetime.now().isoformat()
    })
    
    # Log the cancellation
    self.db.insert("project_logs", {
        "project_id": project_id,
        "action": "project_cancelled",
        "details": {
            "cancelled_tasks": len(running_tasks)
        },
        "timestamp": datetime.now().isoformat()
    })
    
    return {"success": True, "message": f"Project {project_id} cancelled"}
```

**Test Strategy:**

1. Unit tests:
   - Test project creation with task initialization
   - Test project cancellation with task revocation
   - Test error handling for various scenarios

2. Integration tests:
   - Test end-to-end project lifecycle
   - Test Celery task creation and execution
   - Test task revocation behavior

3. Functional tests:
   - Test with actual Celery worker
   - Verify database state after operations
   - Test concurrent operations
