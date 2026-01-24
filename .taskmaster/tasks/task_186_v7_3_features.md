# Task ID: 186

**Title:** Implement Admin Authorization Check

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Implement admin authorization check in the documents route to ensure proper access control for approval listings.

**Details:**

In `app/routes/documents.py`, implement the following TODO:

```python
@router.get("/documents/pending_approval")
async def get_pending_approval_documents(
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """Get documents pending approval."""
    db = Database()
    
    # Implement admin check for approval listings
    is_admin = current_user.get("role") == "admin"
    
    # Build query based on user role
    query = {"status": "pending_approval"}
    
    # If not admin, only show user's own documents
    if not is_admin:
        query["created_by"] = current_user.get("id")
    
    # Get documents with pagination
    documents = db.query(
        "documents",
        query,
        limit=limit,
        offset=skip,
        order_by="created_at",
        order_direction="desc"
    )
    
    # Get total count for pagination
    total_count = db.count("documents", query)
    
    # Enrich documents with user info
    for doc in documents:
        if doc.get("created_by"):
            user = db.get("users", doc["created_by"])
            if user:
                doc["created_by_name"] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                doc["created_by_email"] = user.get("email")
    
    return {
        "documents": documents,
        "total": total_count,
        "skip": skip,
        "limit": limit
    }

@router.post("/documents/{document_id}/approve")
async def approve_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Approve a document pending approval."""
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can approve documents"
        )
    
    db = Database()
    document = db.get("documents", document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.get("status") != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not pending approval (current status: {document.get('status')})"
        )
    
    # Update document status
    db.update("documents", document_id, {
        "status": "approved",
        "approved_by": current_user.get("id"),
        "approved_at": datetime.now().isoformat()
    })
    
    # Trigger post-approval processing
    process_approved_document.delay(document_id)
    
    return {"success": True, "message": "Document approved"}

@router.post("/documents/{document_id}/reject")
async def reject_document(
    document_id: str,
    rejection: DocumentRejection,
    current_user: User = Depends(get_current_user)
):
    """Reject a document pending approval."""
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can reject documents"
        )
    
    db = Database()
    document = db.get("documents", document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.get("status") != "pending_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not pending approval (current status: {document.get('status')})"
        )
    
    # Update document status
    db.update("documents", document_id, {
        "status": "rejected",
        "rejected_by": current_user.get("id"),
        "rejected_at": datetime.now().isoformat(),
        "rejection_reason": rejection.reason
    })
    
    # Notify document owner
    if document.get("created_by"):
        notification_service = NotificationService()
        notification_service.send_notification(
            user_id=document.get("created_by"),
            title="Document Rejected",
            message=f"Your document '{document.get('filename')}' was rejected: {rejection.reason}",
            type="document_rejected",
            data={
                "document_id": document_id,
                "rejection_reason": rejection.reason
            }
        )
    
    return {"success": True, "message": "Document rejected"}
```

**Test Strategy:**

1. Unit tests:
   - Test admin role check logic
   - Test document query filtering based on user role
   - Test approval and rejection logic

2. Integration tests:
   - Test document listing with admin and non-admin users
   - Test approval workflow end-to-end
   - Test rejection workflow with notifications

3. Security tests:
   - Test authorization bypass attempts
   - Test role spoofing prevention
   - Test document ID manipulation protection
