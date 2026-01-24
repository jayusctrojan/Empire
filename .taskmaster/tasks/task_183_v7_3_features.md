# Task ID: 183

**Title:** Implement Upload API B2 Verification

**Status:** done

**Dependencies:** 180 ✓

**Priority:** high

**Description:** Enhance the Upload API to verify file existence in B2 before returning success and check processing status from the database.

**Details:**

In `app/api/upload.py`, implement the following TODOs:

1. Verify file exists in B2 before returning success:
```python
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    document_type: str = Form(...),
    metadata: str = Form("{}"),
    current_user: User = Depends(get_current_user)
):
    """Upload a file to B2 storage and start processing."""
    # Parse metadata JSON
    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    
    # Save file to temporary location
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        # Upload to B2 using document service
        document_service = DocumentManagementService()
        document = document_service.upload_document(
            file_path=temp_file_path,
            project_id=project_id,
            document_type=document_type,
            metadata=metadata_dict
        )
        
        # Verify file exists in B2
        b2_service = B2StorageService()
        file_exists = b2_service.check_file_exists(document["b2_path"])
        
        if not file_exists:
            raise HTTPException(
                status_code=500,
                detail="File upload to B2 failed verification"
            )
        
        # Start processing task
        task = process_document.delay(document["id"])
        
        # Update document with task ID
        db = Database()
        db.update("documents", document["id"], {
            "processing_task_id": task.id,
            "status": "processing"
        })
        
        # Return document info with task ID
        return {
            "success": True,
            "document_id": document["id"],
            "task_id": task.id,
            "status": "processing"
        }
    except Exception as e:
        # Log the error
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
```

2. Check processing status from database:
```python
@router.get("/upload/{document_id}/status")
async def check_upload_status(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Check the status of an uploaded document."""
    db = Database()
    document = db.get("documents", document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if user has access to this document
    if not has_document_access(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get processing task status if available
    task_status = None
    if document.get("processing_task_id"):
        try:
            # Get task status from Celery
            task = AsyncResult(document["processing_task_id"])
            task_status = task.status
        except Exception as e:
            logger.error(f"Error getting task status: {str(e)}")
    
    # Check B2 file existence
    b2_service = B2StorageService()
    file_exists = b2_service.check_file_exists(document["b2_path"])
    
    return {
        "document_id": document_id,
        "status": document.get("status", "unknown"),
        "task_status": task_status,
        "file_exists": file_exists,
        "filename": document.get("filename"),
        "document_type": document.get("document_type"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at")
    }

def has_document_access(user, document):
    """Check if user has access to the document."""
    # Admin users have access to all documents
    if user.get("role") == "admin":
        return True
    
    # Check if document belongs to a project the user has access to
    db = Database()
    project = db.get("research_projects", document.get("project_id"))
    
    if not project:
        return False
    
    # Check if user is project owner or member
    if project.get("owner_id") == user.get("id"):
        return True
    
    # Check project members
    members = project.get("members", [])
    if user.get("id") in members:
        return True
    
    return False
```

**Test Strategy:**

1. Unit tests:
   - Test file upload with mock B2 service
   - Test B2 verification logic
   - Test status checking with various document states
   - Test access control logic

2. Integration tests:
   - Test actual file uploads to B2
   - Test status checking with actual Celery tasks
   - Test error handling for various failure scenarios

3. Security tests:
   - Test access control for documents across different users
   - Test handling of invalid document IDs
   - Test handling of unauthorized access attempts
