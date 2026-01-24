# Task ID: 194

**Title:** Implement Upload API B2 Verification

**Status:** cancelled

**Dependencies:** 191 ✗

**Priority:** high

**Description:** Enhance the upload API endpoint to verify file existence in B2 before returning success and check processing status from the database.

**Details:**

This task involves completing 2 TODOs in app/api/upload.py:

1. Verify file exists in B2 before returning success:
```python
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    metadata: str = Form("{}"),
    current_user: User = Depends(get_current_user)
):
    try:
        # Parse metadata JSON
        metadata_dict = json.loads(metadata)
        
        # Upload document using service
        document_service = DocumentManagementService()
        document = document_service.upload_document(file, metadata_dict, project_id)
        
        # Verify file exists in B2
        b2_storage = B2StorageService()
        file_exists = b2_storage.verify_file_exists(document["file_path"])
        
        if not file_exists:
            # If verification fails, delete the document record and raise error
            db.table("documents").delete().eq("id", document["id"]).execute()
            raise HTTPException(
                status_code=500,
                detail="File upload to B2 failed verification"
            )
        
        return {
            "success": True,
            "document_id": document["id"],
            "status": document["status"],
            "message": "File uploaded successfully and processing started"
        }
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid metadata JSON format"
        )
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )
```

2. Check processing status from database:
```python
@router.get("/upload/{document_id}/status")
async def get_upload_status(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        # Get document record
        document = db.table("documents").select("*").eq("id", document_id).single().execute()
        
        if not document.data:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )
        
        # Check if user has access to this document
        project_id = document.data["project_id"]
        project_access = db.table("project_members")\
            .select("*")\
            .eq("project_id", project_id)\
            .eq("user_id", current_user.id)\
            .execute()
            
        if not project_access.data and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this document"
            )
        
        # Get processing status
        status = document.data["status"]
        processing_details = {}
        
        # Get additional processing details if available
        if status == "processing":
            task_status = db.table("document_processing_tasks")\
                .select("*")\
                .eq("document_id", document_id)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
                
            if task_status.data:
                processing_details = {
                    "current_step": task_status.data[0]["current_step"],
                    "progress": task_status.data[0]["progress"],
                    "started_at": task_status.data[0]["created_at"],
                }
        
        return {
            "document_id": document_id,
            "status": status,
            "filename": document.data["filename"],
            "processing_details": processing_details,
            "last_updated": document.data["updated_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get upload status: {str(e)}"
        )
```

Add the verify_file_exists method to B2StorageService if it doesn't exist:
```python
def verify_file_exists(self, file_path):
    """Verify a file exists in B2"""
    try:
        # Get file info from B2
        file_info = self.b2_api.get_file_info_by_name(
            self.bucket_name,
            file_path
        )
        return True
    except Exception as e:
        logger.error(f"B2 file verification failed: {str(e)}")
        return False
```

**Test Strategy:**

1. Unit tests for upload endpoint with mocked B2StorageService
2. Unit tests for status endpoint with mocked database responses
3. Integration tests with actual B2 storage in test environment
4. Test cases:
   - Successful upload with B2 verification
   - Failed B2 verification (should clean up database record)
   - Status check for various document states (uploaded, processing, completed, failed)
   - Authorization checks for status endpoint
5. Error handling tests:
   - Invalid document IDs
   - B2 service failures
   - Database errors
