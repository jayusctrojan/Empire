"""
Pydantic models for document management operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class BatchOperationStatus(str, Enum):
    """Batch operation status"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """Document metadata"""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class BulkUploadItem(BaseModel):
    """Single document for bulk upload"""
    file_path: str = Field(..., description="Path to the file in B2 or local storage")
    filename: str = Field(..., description="Original filename")
    metadata: Optional[DocumentMetadata] = None
    user_id: Optional[str] = None


class BulkUploadRequest(BaseModel):
    """Request model for bulk document upload"""
    documents: List[BulkUploadItem] = Field(..., min_items=1, max_items=100)
    auto_process: bool = Field(default=True, description="Automatically process documents after upload")
    notification_email: Optional[str] = Field(None, description="Email to notify when batch completes")


class BulkDeleteRequest(BaseModel):
    """Request model for bulk document deletion"""
    document_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of document IDs to delete")
    soft_delete: bool = Field(default=True, description="Soft delete (mark as deleted) vs hard delete (remove from storage)")


class ReprocessingOptions(BaseModel):
    """Options for document reprocessing"""
    force_reparse: bool = Field(default=False, description="Force reparsing even if already processed")
    update_embeddings: bool = Field(default=True, description="Regenerate vector embeddings")
    preserve_metadata: bool = Field(default=True, description="Preserve existing metadata")


class BulkReprocessRequest(BaseModel):
    """Request model for bulk document reprocessing"""
    document_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of document IDs to reprocess")
    options: Optional[ReprocessingOptions] = ReprocessingOptions()
    priority: int = Field(default=5, ge=1, le=10, description="Processing priority (1=lowest, 10=highest)")


class MetadataUpdateItem(BaseModel):
    """Single metadata update operation"""
    document_id: str
    metadata: DocumentMetadata


class BulkMetadataUpdateRequest(BaseModel):
    """Request model for bulk metadata updates"""
    updates: List[MetadataUpdateItem] = Field(..., min_items=1, max_items=100)


class DocumentOperationResult(BaseModel):
    """Result of a single document operation"""
    document_id: Optional[str] = None
    filename: Optional[str] = None
    status: str  # success, failed, skipped
    message: Optional[str] = None
    error: Optional[str] = None


class BatchOperationResponse(BaseModel):
    """Response model for batch operations"""
    operation_id: str = Field(..., description="Unique operation ID for tracking")
    operation_type: str = Field(..., description="Type of operation (upload, delete, reprocess, metadata_update)")
    status: BatchOperationStatus
    total_items: int
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    results: List[DocumentOperationResult] = []
    created_at: datetime
    updated_at: datetime
    estimated_completion_time: Optional[datetime] = None
    message: str = "Operation queued for processing"


class BatchOperationStatusResponse(BaseModel):
    """Response model for checking batch operation status"""
    operation_id: str
    operation_type: str
    status: BatchOperationStatus
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    progress_percentage: float
    results: List[DocumentOperationResult] = []
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class DocumentListItem(BaseModel):
    """Single document in list view"""
    id: str
    filename: str
    status: DocumentStatus
    metadata: Optional[DocumentMetadata] = None
    created_at: datetime
    updated_at: datetime
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    user_id: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response model for listing documents"""
    documents: List[DocumentListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


# ============================================================================
# Task 32.2: Document Versioning and Approval Workflow Models
# ============================================================================

class ApprovalStatus(str, Enum):
    """Document approval status enumeration"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class DocumentVersion(BaseModel):
    """Document version information"""
    id: str
    document_id: str
    version_number: int
    file_hash: str
    b2_file_id: Optional[str] = None
    b2_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_type: Optional[str] = None
    created_by: str
    change_description: Optional[str] = None
    is_current: bool = False
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentApproval(BaseModel):
    """Document approval workflow state"""
    id: str
    document_id: str
    version_id: Optional[str] = None
    approval_status: ApprovalStatus
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    approval_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ApprovalAuditLogEntry(BaseModel):
    """Approval audit log entry"""
    id: str
    approval_id: str
    event_type: str
    previous_status: Optional[str] = None
    new_status: str
    changed_by: str
    change_reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ============================================================================
# Request/Response Models for Versioning API
# ============================================================================

class CreateVersionRequest(BaseModel):
    """Request to create a new document version"""
    document_id: str = Field(..., description="Document ID to create version for")
    file_path: str = Field(..., description="Path to the new version file")
    change_description: Optional[str] = Field(None, description="Description of changes in this version")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CreateVersionResponse(BaseModel):
    """Response after creating a new version"""
    version_id: str
    document_id: str
    version_number: int
    message: str = "Version created successfully"


class GetVersionHistoryResponse(BaseModel):
    """Response for version history query"""
    document_id: str
    total_versions: int
    current_version: Optional[DocumentVersion] = None
    versions: List[DocumentVersion] = Field(default_factory=list)


class RollbackVersionRequest(BaseModel):
    """Request to rollback to a previous version"""
    document_id: str = Field(..., description="Document ID")
    version_number: int = Field(..., description="Version number to rollback to", gt=0)
    reason: Optional[str] = Field(None, description="Reason for rollback")


# ============================================================================
# Request/Response Models for Approval Workflow API
# ============================================================================

class SubmitForApprovalRequest(BaseModel):
    """Request to submit document for approval"""
    document_id: str = Field(..., description="Document ID to submit")
    version_id: Optional[str] = Field(None, description="Specific version to submit (defaults to current)")
    notes: Optional[str] = Field(None, description="Submission notes")


class SubmitForApprovalResponse(BaseModel):
    """Response after submitting for approval"""
    approval_id: str
    document_id: str
    version_id: Optional[str] = None
    approval_status: ApprovalStatus
    message: str = "Document submitted for approval"


class ApproveDocumentRequest(BaseModel):
    """Request to approve a document"""
    approval_id: str = Field(..., description="Approval ID")
    approval_notes: Optional[str] = Field(None, description="Approval notes")


class RejectDocumentRequest(BaseModel):
    """Request to reject a document"""
    approval_id: str = Field(..., description="Approval ID")
    rejection_reason: str = Field(..., description="Reason for rejection")
    rejection_notes: Optional[str] = Field(None, description="Additional rejection notes")


class ApprovalActionResponse(BaseModel):
    """Response for approval/rejection actions"""
    approval_id: str
    document_id: str
    approval_status: ApprovalStatus
    message: str


class GetApprovalStatusResponse(BaseModel):
    """Response for approval status query"""
    approval: DocumentApproval
    version: Optional[DocumentVersion] = None
    audit_trail: List[ApprovalAuditLogEntry] = Field(default_factory=list)


class ListApprovalsRequest(BaseModel):
    """Request to list approvals with filters"""
    status_filter: Optional[ApprovalStatus] = Field(None, description="Filter by approval status")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of approvals to return")
    offset: int = Field(0, ge=0, description="Number of approvals to skip")


class ListApprovalsResponse(BaseModel):
    """Response for listing approvals"""
    approvals: List[DocumentApproval] = Field(default_factory=list)
    total_count: int
    limit: int
    offset: int


# ============================================================================
# Batch Versioning and Approval Models
# ============================================================================

class BulkVersionUpdateItem(BaseModel):
    """Single item for bulk version creation"""
    document_id: str
    file_path: str
    change_description: Optional[str] = None


class BulkVersionUpdateRequest(BaseModel):
    """Request for bulk version creation"""
    updates: List[BulkVersionUpdateItem] = Field(..., min_items=1, max_items=100)


class BulkApprovalActionRequest(BaseModel):
    """Request for bulk approval/rejection"""
    approval_ids: List[str] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., description="Action to perform: 'approve' or 'reject'")
    notes: Optional[str] = Field(None, description="Notes for all approvals")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason (required if action is 'reject')")
