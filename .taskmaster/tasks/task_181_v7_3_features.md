# Task ID: 181

**Title:** Implement Research Tasks Report Generation

**Status:** done

**Dependencies:** 180 ✓

**Priority:** high

**Description:** Complete the report generation functionality in the research tasks module by implementing the ReportExecutor integration and B2 storage for reports.

**Details:**

In `app/tasks/research_tasks.py`, implement the following TODOs:

1. Implement report generation using ReportExecutor:
```python
def generate_research_report(project_id, task_ids=None):
    """Generate a comprehensive research report for a project."""
    # Get project details
    project = db.get("research_projects", project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")
    
    # Get tasks for this project
    if task_ids:
        tasks = [db.get("research_tasks", task_id) for task_id in task_ids]
        tasks = [t for t in tasks if t]  # Filter out None values
    else:
        tasks = db.query("research_tasks", {"project_id": project_id})
    
    # Get task results
    task_results = []
    for task in tasks:
        results = db.query("task_results", {"task_id": task["id"]})
        task_results.append({
            "task": task,
            "results": results
        })
    
    # Initialize ReportExecutor
    executor = ReportExecutor(
        model="claude-3-opus-20240229",
        temperature=0.2,
        max_tokens=12000
    )
    
    # Generate report content
    report_content = executor.generate_report(
        project_name=project["name"],
        project_description=project["description"],
        task_results=task_results,
        format="markdown"
    )
    
    # Generate a PDF version
    pdf_content = executor.convert_to_pdf(report_content)
    
    # Save report to B2
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"report_{project_id}_{timestamp}.md"
    pdf_filename = f"report_{project_id}_{timestamp}.pdf"
    
    b2_path_md = f"reports/{project_id}/{report_filename}"
    b2_path_pdf = f"reports/{project_id}/{pdf_filename}"
    
    # Save markdown to temp file
    md_temp_path = f"/tmp/{report_filename}"
    with open(md_temp_path, "w") as f:
        f.write(report_content)
    
    # Save PDF to temp file
    pdf_temp_path = f"/tmp/{pdf_filename}"
    with open(pdf_temp_path, "wb") as f:
        f.write(pdf_content)
    
    # Upload to B2
    b2_service = B2StorageService()
    md_url = b2_service.upload_file(md_temp_path, b2_path_md)
    pdf_url = b2_service.upload_file(pdf_temp_path, b2_path_pdf)
    
    # Store report metadata in database
    report_record = {
        "project_id": project_id,
        "title": f"Research Report: {project['name']}",
        "description": f"Generated report for project {project['name']}",
        "md_path": b2_path_md,
        "md_url": md_url,
        "pdf_path": b2_path_pdf,
        "pdf_url": pdf_url,
        "task_ids": task_ids or [t["id"] for t in tasks],
        "created_at": datetime.now().isoformat()
    }
    
    report_id = db.insert("research_reports", report_record).get("id")
    
    # Clean up temp files
    os.remove(md_temp_path)
    os.remove(pdf_temp_path)
    
    return {"report_id": report_id, "md_url": md_url, "pdf_url": pdf_url}
```

**Test Strategy:**

1. Unit tests:
   - Test report generation with mock task data
   - Test PDF conversion functionality
   - Test B2 upload with mock B2StorageService
   - Test database record creation

2. Integration tests:
   - Test end-to-end report generation with sample project data
   - Verify B2 storage structure and accessibility of reports
   - Test with various project sizes (small, medium, large number of tasks)

3. Error handling tests:
   - Test behavior when ReportExecutor fails
   - Test behavior when B2 upload fails
   - Test with missing project or task data
