# Task ID: 197

**Title:** Implement Admin Authorization Check

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Implement the admin authorization check in the documents route to ensure that non-admin users can only see their own pending approvals while admin users can see all pending approvals.

**Details:**

This task involves completing 1 TODO in app/routes/documents.py to implement the admin authorization check:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.core.auth import get_current_user
from app.models.user import User
from app.services.document_management import DocumentManagementService

router = APIRouter()

@router.get("/documents/pending-approval")
async def get_pending_approvals(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """Get documents pending approval"""
    try:
        # Initialize service
        doc_service = DocumentManagementService()
        
        # Implement admin check for approval listings
        if current_user.is_admin:
            # Admin users can see all pending approvals
            pending_docs = doc_service.get_all_pending_approvals(limit, offset)
        else:
            # Non-admin users can only see their own pending approvals
            pending_docs = doc_service.get_user_pending_approvals(current_user.id, limit, offset)
        
        return {
            "success": True,
            "documents": pending_docs,
            "count": len(pending_docs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pending approvals: {str(e)}"
        )

# Add the following methods to DocumentManagementService if they don't exist
"""
def get_all_pending_approvals(self, limit: int = 10, offset: int = 0):
    """Get all documents pending approval (admin only)"""
    result = self.db.table("documents")\
        .select("*")\
        .eq("status", "pending_approval")\
        .order("created_at", desc=True)\
        .range(offset, offset + limit - 1)\
        .execute()
        
    return result.data

def get_user_pending_approvals(self, user_id: str, limit: int = 10, offset: int = 0):
    """Get documents pending approval for a specific user"""
    # Get projects where user is a member
    user_projects = self.db.table("project_members")\
        .select("project_id")\
        .eq("user_id", user_id)\
        .execute()
        
    project_ids = [item["project_id"] for item in user_projects.data]
    
    # Also include projects owned by the user
    owned_projects = self.db.table("research_projects")\
        .select("id")\
        .eq("owner_id", user_id)\
        .execute()
        
    project_ids.extend([item["id"] for item in owned_projects.data])
    
    # Remove duplicates
    project_ids = list(set(project_ids))
    
    if not project_ids:
        return []
    
    # Get pending documents for these projects
    result = self.db.table("documents")\
        .select("*")\
        .eq("status", "pending_approval")\
        .in_("project_id", project_ids)\
        .order("created_at", desc=True)\
        .range(offset, offset + limit - 1)\
        .execute()
        
    return result.data
"""

@router.post("/documents/{document_id}/approve")
async def approve_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Approve a document pending approval"""
    try:
        # Check if user is admin or has rights to approve
        doc_service = DocumentManagementService()
        document = doc_service.get_document(document_id)
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )
        
        # Only admins or project owners can approve documents
        if not current_user.is_admin:
            # Check if user is project owner
            project = doc_service.db.table("research_projects")\
                .select("owner_id")\
                .eq("id", document["project_id"])\
                .single()\
                .execute()
                
            if not project.data or project.data["owner_id"] != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to approve this document"
                )
        
        # Approve the document
        result = doc_service.approve_document(document_id, current_user.id)
        
        return {
            "success": True,
            "document_id": document_id,
            "message": "Document approved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve document: {str(e)}"
        )
```

**Test Strategy:**

1. Unit tests for authorization logic
   - Test admin user access to all pending approvals
   - Test non-admin user access to only their approvals
   - Test document approval permissions
2. Integration tests with database
3. Test cases:
   - Admin user retrieves all pending approvals
   - Regular user retrieves only their pending approvals
   - Admin approves any document
   - Project owner approves their document
   - Non-admin tries to approve document they don't own
4. Security testing:
   - Attempt to bypass authorization checks
   - Test with manipulated user roles
5. Database query testing to ensure correct filtering
