# Task ID: 192

**Title:** Implement Research Tasks Report Generation

**Status:** cancelled

**Dependencies:** 191 ✗

**Priority:** high

**Description:** Complete the report generation functionality in the research tasks module by implementing the actual report generation using ReportExecutor and connecting to B2 for report storage.

**Details:**

This task involves completing 2 TODOs in app/tasks/research_tasks.py:

1. Implement actual report generation using ReportExecutor:
```python
def generate_research_report(project_id, task_id, report_type="summary"):
    # Get project and task data
    project = db.table("research_projects").select("*").eq("id", project_id).single().execute()
    task = db.table("research_tasks").select("*").eq("id", task_id).single().execute()
    
    if not project or not task:
        raise ValueError(f"Project or task not found: {project_id}, {task_id}")
    
    # Get relevant documents and data
    documents = db.table("documents")\
        .select("*")\
        .eq("project_id", project_id)\
        .eq("status", "processed")\
        .execute()
    
    # Initialize report executor
    report_executor = ReportExecutor(
        model="claude-3-opus-20240229",  # Use latest Claude model
        max_tokens=100000
    )
    
    # Generate report based on type
    if report_type == "summary":
        report_content = report_executor.generate_summary_report(
            project=project,
            task=task,
            documents=documents
        )
    elif report_type == "detailed":
        report_content = report_executor.generate_detailed_report(
            project=project,
            task=task,
            documents=documents
        )
    else:
        raise ValueError(f"Unknown report type: {report_type}")
    
    # Format report as markdown
    formatted_report = f"# {task['title']} Report\n\n{report_content}"
    
    return formatted_report
```

2. Connect to B2 for report storage:
```python
def store_report(project_id, task_id, report_content, report_type="summary"):
    # Generate filename and path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_report_{timestamp}.md"
    file_path = f"reports/{project_id}/{task_id}/{filename}"
    
    # Convert report content to bytes
    report_bytes = report_content.encode('utf-8')
    content_stream = io.BytesIO(report_bytes)
    
    # Upload to B2
    b2_storage = B2StorageService()
    b2_url = b2_storage.upload_file(
        content_stream, 
        file_path, 
        content_type="text/markdown"
    )
    
    # Store metadata in Supabase
    report_record = {
        "project_id": project_id,
        "task_id": task_id,
        "report_type": report_type,
        "filename": filename,
        "file_path": file_path,
        "b2_url": b2_url,
        "created_at": datetime.now()
    }
    db.table("research_reports").insert(report_record).execute()
    
    return report_record
```

Update the main task function to use these new functions:
```python
@celery_app.task
def generate_and_store_report(project_id, task_id, report_type="summary"):
    try:
        # Generate report content
        report_content = generate_research_report(project_id, task_id, report_type)
        
        # Store report in B2
        report_record = store_report(project_id, task_id, report_content, report_type)
        
        # Update task status
        db.table("research_tasks")\
            .update({"report_status": "completed", "report_id": report_record["id"]})\
            .eq("id", task_id)\
            .execute()
            
        return {"success": True, "report_id": report_record["id"]}
    except Exception as e:
        # Update task status on failure
        db.table("research_tasks")\
            .update({"report_status": "failed", "report_error": str(e)})\
            .eq("id", task_id)\
            .execute()
        raise
```

**Test Strategy:**

1. Unit tests for each function with mocked ReportExecutor and B2StorageService
2. Integration tests with actual services in a test environment
3. Test cases:
   - Report generation: Test with different report types
   - B2 storage: Verify reports stored in correct location with proper naming
   - Error handling: Test with invalid project/task IDs, service failures
4. Verify proper folder structure in B2: reports/{project_id}/{task_id}/{filename}
5. Test Celery task execution and error handling
6. Verify report metadata stored correctly in database
