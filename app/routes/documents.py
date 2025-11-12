"""
Document Management API Routes - Bulk Operations
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
import structlog

from app.models.documents import (
    BulkUploadRequest,
    BulkDeleteRequest,
    BulkReprocessRequest,
    BulkMetadataUpdateRequest,
    BatchOperationResponse,
    BatchOperationStatusResponse,
    BatchOperationStatus,
    DocumentOperationResult,
    # Task 32.2: Versioning and Approval models
    CreateVersionRequest,
    CreateVersionResponse,
    GetVersionHistoryResponse,
    RollbackVersionRequest,
    SubmitForApprovalRequest,
    SubmitForApprovalResponse,
    ApproveDocumentRequest,
    RejectDocumentRequest,
    ApprovalActionResponse,
    GetApprovalStatusResponse,
    ListApprovalsResponse,
    BulkVersionUpdateRequest,
    BulkApprovalActionRequest,
    ApprovalStatus,
    DocumentVersion,
    DocumentApproval,
    ApprovalAuditLogEntry
)
from app.tasks.bulk_operations import (
    bulk_upload_documents,
    bulk_delete_documents,
    bulk_reprocess_documents,
    bulk_update_metadata
)
from app.middleware.auth import get_current_user
from app.core.supabase_client import get_supabase_client
# Task 32.2: Import versioning and approval services
from app.services.versioning_service import VersioningService
from app.services.approval_workflow import ApprovalWorkflowService, ApprovalEvent

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/bulk-upload", response_model=BatchOperationResponse)
async def create_bulk_upload(
    request: BulkUploadRequest,
    user=Depends(get_current_user)
):
    """
    Bulk upload documents

    Requires: documents:write permission

    Args:
        request: Bulk upload request with list of documents
        user: Current authenticated user

    Returns:
        BatchOperationResponse with operation ID and status
    """
    try:
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())

        # Create operation record in database
        supabase = get_supabase_client()
        operation_data = {
            "id": operation_id,
            "operation_type": "bulk_upload",
            "user_id": user,
            "status": BatchOperationStatus.QUEUED,
            "total_items": len(request.documents),
            "processed_items": 0,
            "successful_items": 0,
            "failed_items": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        supabase.table("batch_operations").insert(operation_data).execute()

        # Queue Celery task
        documents_data = [
            {
                "file_path": doc.file_path,
                "filename": doc.filename,
                "metadata": doc.metadata.dict() if doc.metadata else None,
                "user_id": doc.user_id or user
            }
            for doc in request.documents
        ]

        bulk_upload_documents.delay(
            operation_id=operation_id,
            documents=documents_data,
            user_id=user,
            auto_process=request.auto_process
        )

        logger.info(
            "Bulk upload operation queued",
            operation_id=operation_id,
            document_count=len(request.documents),
            user_id=user
        )

        return BatchOperationResponse(
            operation_id=operation_id,
            operation_type="bulk_upload",
            status=BatchOperationStatus.QUEUED,
            total_items=len(request.documents),
            processed_items=0,
            successful_items=0,
            failed_items=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message=f"Bulk upload queued for {len(request.documents)} documents"
        )

    except Exception as e:
        logger.error("Failed to queue bulk upload", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue bulk upload: {str(e)}"
        )


@router.post("/bulk-delete", response_model=BatchOperationResponse)
async def create_bulk_delete(
    request: BulkDeleteRequest,
    user=Depends(get_current_user)
):
    """
    Bulk delete documents

    Requires: documents:delete permission

    Args:
        request: Bulk delete request with list of document IDs
        user: Current authenticated user

    Returns:
        BatchOperationResponse with operation ID and status
    """
    try:
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())

        # Create operation record in database
        supabase = get_supabase_client()
        operation_data = {
            "id": operation_id,
            "operation_type": "bulk_delete",
            "user_id": user,
            "status": BatchOperationStatus.QUEUED,
            "total_items": len(request.document_ids),
            "processed_items": 0,
            "successful_items": 0,
            "failed_items": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        supabase.table("batch_operations").insert(operation_data).execute()

        # Queue Celery task
        bulk_delete_documents.delay(
            operation_id=operation_id,
            document_ids=request.document_ids,
            user_id=user,
            soft_delete=request.soft_delete
        )

        logger.info(
            "Bulk delete operation queued",
            operation_id=operation_id,
            document_count=len(request.document_ids),
            user_id=user,
            soft_delete=request.soft_delete
        )

        return BatchOperationResponse(
            operation_id=operation_id,
            operation_type="bulk_delete",
            status=BatchOperationStatus.QUEUED,
            total_items=len(request.document_ids),
            processed_items=0,
            successful_items=0,
            failed_items=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message=f"Bulk delete queued for {len(request.document_ids)} documents"
        )

    except Exception as e:
        logger.error("Failed to queue bulk delete", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue bulk delete: {str(e)}"
        )


@router.post("/bulk-reprocess", response_model=BatchOperationResponse)
async def create_bulk_reprocess(
    request: BulkReprocessRequest,
    user=Depends(get_current_user)
):
    """
    Bulk reprocess documents

    Requires: documents:write permission

    Args:
        request: Bulk reprocess request with list of document IDs and options
        user: Current authenticated user

    Returns:
        BatchOperationResponse with operation ID and status
    """
    try:
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())

        # Create operation record in database
        supabase = get_supabase_client()
        operation_data = {
            "id": operation_id,
            "operation_type": "bulk_reprocess",
            "user_id": user,
            "status": BatchOperationStatus.QUEUED,
            "total_items": len(request.document_ids),
            "processed_items": 0,
            "successful_items": 0,
            "failed_items": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        supabase.table("batch_operations").insert(operation_data).execute()

        # Queue Celery task
        bulk_reprocess_documents.delay(
            operation_id=operation_id,
            document_ids=request.document_ids,
            user_id=user,
            options=request.options.dict() if request.options else None
        )

        logger.info(
            "Bulk reprocess operation queued",
            operation_id=operation_id,
            document_count=len(request.document_ids),
            user_id=user
        )

        return BatchOperationResponse(
            operation_id=operation_id,
            operation_type="bulk_reprocess",
            status=BatchOperationStatus.QUEUED,
            total_items=len(request.document_ids),
            processed_items=0,
            successful_items=0,
            failed_items=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message=f"Bulk reprocess queued for {len(request.document_ids)} documents"
        )

    except Exception as e:
        logger.error("Failed to queue bulk reprocess", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue bulk reprocess: {str(e)}"
        )


@router.patch("/bulk-metadata", response_model=BatchOperationResponse)
async def create_bulk_metadata_update(
    request: BulkMetadataUpdateRequest,
    user=Depends(get_current_user)
):
    """
    Bulk update document metadata

    Requires: documents:write permission

    Args:
        request: Bulk metadata update request with list of updates
        user: Current authenticated user

    Returns:
        BatchOperationResponse with operation ID and status
    """
    try:
        # Generate unique operation ID
        operation_id = str(uuid.uuid4())

        # Create operation record in database
        supabase = get_supabase_client()
        operation_data = {
            "id": operation_id,
            "operation_type": "bulk_metadata_update",
            "user_id": user,
            "status": BatchOperationStatus.QUEUED,
            "total_items": len(request.updates),
            "processed_items": 0,
            "successful_items": 0,
            "failed_items": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        supabase.table("batch_operations").insert(operation_data).execute()

        # Queue Celery task
        updates_data = [
            {
                "document_id": update.document_id,
                "metadata": update.metadata.dict()
            }
            for update in request.updates
        ]

        bulk_update_metadata.delay(
            operation_id=operation_id,
            updates=updates_data,
            user_id=user
        )

        logger.info(
            "Bulk metadata update operation queued",
            operation_id=operation_id,
            update_count=len(request.updates),
            user_id=user
        )

        return BatchOperationResponse(
            operation_id=operation_id,
            operation_type="bulk_metadata_update",
            status=BatchOperationStatus.QUEUED,
            total_items=len(request.updates),
            processed_items=0,
            successful_items=0,
            failed_items=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message=f"Bulk metadata update queued for {len(request.updates)} documents"
        )

    except Exception as e:
        logger.error("Failed to queue bulk metadata update", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue bulk metadata update: {str(e)}"
        )


@router.get("/batch-operations/{operation_id}", response_model=BatchOperationStatusResponse)
async def get_batch_operation_status(
    operation_id: str,
    user=Depends(get_current_user)
):
    """
    Get status of a batch operation

    Requires: Authentication (no specific permission)

    Args:
        operation_id: Unique operation ID
        user: Current authenticated user

    Returns:
        BatchOperationStatusResponse with current status
    """
    try:
        supabase = get_supabase_client()

        # Fetch operation from database
        result = supabase.table("batch_operations").select("*").eq("id", operation_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch operation {operation_id} not found"
            )

        operation = result.data[0]

        # Check if user has access to this operation
        if operation["user_id"] != user:
            # Check if user has admin permission
            user_permissions = user.get("permissions", [])
            if "admin:all" not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view this operation"
                )

        # Calculate progress percentage
        progress = 0
        if operation["total_items"] > 0:
            progress = (operation["processed_items"] / operation["total_items"]) * 100

        return BatchOperationStatusResponse(
            operation_id=operation["id"],
            operation_type=operation["operation_type"],
            status=operation["status"],
            total_items=operation["total_items"],
            processed_items=operation["processed_items"],
            successful_items=operation["successful_items"],
            failed_items=operation["failed_items"],
            progress_percentage=progress,
            results=operation.get("results", []),
            created_at=datetime.fromisoformat(operation["created_at"]),
            updated_at=datetime.fromisoformat(operation["updated_at"]),
            completed_at=datetime.fromisoformat(operation["completed_at"]) if operation.get("completed_at") else None,
            error_message=operation.get("error_message")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get batch operation status", operation_id=operation_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get operation status: {str(e)}"
        )


@router.get("/batch-operations", response_model=list[BatchOperationStatusResponse])
async def list_batch_operations(
    user=Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None
):
    """
    List batch operations for current user

    Requires: Authentication (no specific permission)

    Args:
        user: Current authenticated user
        limit: Maximum number of operations to return
        offset: Number of operations to skip
        status_filter: Optional status filter

    Returns:
        List of BatchOperationStatusResponse
    """
    try:
        supabase = get_supabase_client()

        # Build query
        query = supabase.table("batch_operations").select("*").eq("user_id", user)

        if status_filter:
            query = query.eq("status", status_filter)

        # Execute query with pagination
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        operations = []
        for operation in result.data:
            progress = 0
            if operation["total_items"] > 0:
                progress = (operation["processed_items"] / operation["total_items"]) * 100

            operations.append(BatchOperationStatusResponse(
                operation_id=operation["id"],
                operation_type=operation["operation_type"],
                status=operation["status"],
                total_items=operation["total_items"],
                processed_items=operation["processed_items"],
                successful_items=operation["successful_items"],
                failed_items=operation["failed_items"],
                progress_percentage=progress,
                results=operation.get("results", []),
                created_at=datetime.fromisoformat(operation["created_at"]),
                updated_at=datetime.fromisoformat(operation["updated_at"]),
                completed_at=datetime.fromisoformat(operation["completed_at"]) if operation.get("completed_at") else None,
                error_message=operation.get("error_message")
            ))

        return operations

    except Exception as e:
        logger.error("Failed to list batch operations", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list operations: {str(e)}"
        )


# ============================================================================
# Task 32.2: Document Versioning Endpoints
# ============================================================================

@router.post("/versions/create", response_model=CreateVersionResponse)
async def create_document_version(
    request: CreateVersionRequest,
    user=Depends(get_current_user)
):
    """
    Create a new version of a document

    Requires: documents:write permission

    Args:
        request: Version creation request
        user: Current authenticated user

    Returns:
        CreateVersionResponse with version details
    """
    try:
        versioning_service = VersioningService()

        # TODO: Calculate file hash from file_path
        # For now, using a placeholder hash
        file_hash = "placeholder_hash"

        version = await versioning_service.create_version(
            document_id=request.document_id,
            file_path=request.file_path,
            file_hash=file_hash,
            created_by=user,  # user is a string (user_id)
            change_description=request.change_description,
            metadata=request.metadata
        )

        logger.info(
            "Document version created",
            document_id=request.document_id,
            version_id=version["id"],
            version_number=version["version_number"],
            user_id=user
        )

        return CreateVersionResponse(
            version_id=version["id"],
            document_id=version["document_id"],
            version_number=version["version_number"]
        )

    except Exception as e:
        logger.error("Failed to create version", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create version: {str(e)}"
        )


@router.get("/versions/{document_id}", response_model=GetVersionHistoryResponse)
async def get_version_history(
    document_id: str,
    user=Depends(get_current_user),
    limit: int = 100,
    offset: int = 0
):
    """
    Get version history for a document

    Requires: documents:read permission

    Args:
        document_id: Document ID
        user: Current authenticated user
        limit: Maximum number of versions to return
        offset: Number of versions to skip

    Returns:
        GetVersionHistoryResponse with version history
    """
    try:
        versioning_service = VersioningService()

        versions, total_count, current_version = await versioning_service.get_version_history(
            document_id=document_id,
            limit=limit,
            offset=offset
        )

        # Convert to Pydantic models
        version_models = [
            DocumentVersion(**version) for version in versions
        ]

        current_version_model = DocumentVersion(**current_version) if current_version else None

        return GetVersionHistoryResponse(
            document_id=document_id,
            total_versions=total_count,
            current_version=current_version_model,
            versions=version_models
        )

    except Exception as e:
        logger.error("Failed to get version history", error=str(e), document_id=document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get version history: {str(e)}"
        )


@router.post("/versions/rollback")
async def rollback_version(
    request: RollbackVersionRequest,
    user=Depends(get_current_user)
):
    """
    Rollback document to a previous version

    Requires: documents:write permission

    Args:
        request: Rollback request
        user: Current authenticated user

    Returns:
        Success message with version details
    """
    try:
        versioning_service = VersioningService()

        success, message, version = await versioning_service.rollback_to_version(
            document_id=request.document_id,
            version_number=request.version_number,
            user_id=user,
            reason=request.reason
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        logger.info(
            "Document rolled back",
            document_id=request.document_id,
            version_number=request.version_number,
            user_id=user
        )

        return {
            "success": True,
            "message": message,
            "version": DocumentVersion(**version)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to rollback version", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback version: {str(e)}"
        )


@router.post("/versions/bulk-create", response_model=BatchOperationResponse)
async def bulk_create_versions(
    request: BulkVersionUpdateRequest,
    user=Depends(get_current_user)
):
    """
    Create multiple document versions in bulk

    Requires: documents:write permission

    Args:
        request: Bulk version update request
        user: Current authenticated user

    Returns:
        BatchOperationResponse with operation details
    """
    try:
        versioning_service = VersioningService()

        updates_data = [
            {
                "document_id": update.document_id,
                "file_path": update.file_path,
                "change_description": update.change_description,
                "file_hash": "placeholder_hash"  # TODO: Calculate actual hash
            }
            for update in request.updates
        ]

        results = await versioning_service.bulk_create_versions(
            updates=updates_data,
            user_id=user
        )

        logger.info(
            "Bulk version creation completed",
            total=results["total"],
            successful=results["successful"],
            failed=results["failed"],
            user_id=user
        )

        return BatchOperationResponse(
            operation_id=str(uuid.uuid4()),
            operation_type="bulk_version_create",
            status=BatchOperationStatus.COMPLETED if results["failed"] == 0 else BatchOperationStatus.PARTIAL_SUCCESS,
            total_items=results["total"],
            processed_items=results["total"],
            successful_items=results["successful"],
            failed_items=results["failed"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message=f"Bulk version creation completed: {results['successful']}/{results['total']} successful"
        )

    except Exception as e:
        logger.error("Failed to create bulk versions", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bulk versions: {str(e)}"
        )


# ============================================================================
# Task 32.2: Document Approval Workflow Endpoints
# ============================================================================

@router.post("/approvals/submit", response_model=SubmitForApprovalResponse)
async def submit_for_approval(
    request: SubmitForApprovalRequest,
    user=Depends(get_current_user)
):
    """
    Submit a document for approval

    Requires: documents:write permission

    Args:
        request: Submit for approval request
        user: Current authenticated user

    Returns:
        SubmitForApprovalResponse with approval details
    """
    try:
        workflow_service = ApprovalWorkflowService()

        # Check if approval record already exists
        supabase = get_supabase_client()
        existing = supabase.table("document_approvals").select("*").eq(
            "document_id", request.document_id
        ).eq("approval_status", ApprovalStatus.DRAFT).execute()

        if existing.data:
            # Use existing approval record and transition to PENDING_REVIEW
            approval = existing.data[0]
            success, message, updated_approval = await workflow_service.transition_status(
                approval_id=approval["id"],
                event=ApprovalEvent.SUBMIT,
                user_id=user,
                notes=request.notes
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )

            approval_id = approval["id"]
        else:
            # Create new approval record in DRAFT state, then submit
            approval = await workflow_service.create_approval(
                document_id=request.document_id,
                version_id=request.version_id,
                user_id=user,
                initial_status=ApprovalStatus.DRAFT
            )

            # Transition to PENDING_REVIEW
            success, message, updated_approval = await workflow_service.transition_status(
                approval_id=approval["id"],
                event=ApprovalEvent.SUBMIT,
                user_id=user,
                notes=request.notes
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )

            approval_id = approval["id"]

        logger.info(
            "Document submitted for approval",
            document_id=request.document_id,
            approval_id=approval_id,
            user_id=user
        )

        return SubmitForApprovalResponse(
            approval_id=approval_id,
            document_id=request.document_id,
            version_id=request.version_id,
            approval_status=ApprovalStatus.PENDING_REVIEW
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit for approval", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit for approval: {str(e)}"
        )


@router.post("/approvals/approve", response_model=ApprovalActionResponse)
async def approve_document(
    request: ApproveDocumentRequest,
    user=Depends(get_current_user)
):
    """
    Approve a document

    Requires: documents:approve permission (or admin role)

    Args:
        request: Approve document request
        user: Current authenticated user

    Returns:
        ApprovalActionResponse with approval details
    """
    try:
        workflow_service = ApprovalWorkflowService()

        success, message, approval = await workflow_service.transition_status(
            approval_id=request.approval_id,
            event=ApprovalEvent.APPROVE,
            user_id=user,
            notes=request.approval_notes
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        logger.info(
            "Document approved",
            approval_id=request.approval_id,
            document_id=approval["document_id"],
            user_id=user
        )

        return ApprovalActionResponse(
            approval_id=request.approval_id,
            document_id=approval["document_id"],
            approval_status=ApprovalStatus.APPROVED,
            message="Document approved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve document", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve document: {str(e)}"
        )


@router.post("/approvals/reject", response_model=ApprovalActionResponse)
async def reject_document(
    request: RejectDocumentRequest,
    user=Depends(get_current_user)
):
    """
    Reject a document

    Requires: documents:approve permission (or admin role)

    Args:
        request: Reject document request
        user: Current authenticated user

    Returns:
        ApprovalActionResponse with rejection details
    """
    try:
        workflow_service = ApprovalWorkflowService()

        success, message, approval = await workflow_service.transition_status(
            approval_id=request.approval_id,
            event=ApprovalEvent.REJECT,
            user_id=user,
            notes=request.rejection_notes,
            rejection_reason=request.rejection_reason
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        logger.info(
            "Document rejected",
            approval_id=request.approval_id,
            document_id=approval["document_id"],
            user_id=user,
            reason=request.rejection_reason
        )

        return ApprovalActionResponse(
            approval_id=request.approval_id,
            document_id=approval["document_id"],
            approval_status=ApprovalStatus.REJECTED,
            message="Document rejected"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reject document", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject document: {str(e)}"
        )


@router.get("/approvals/{approval_id}", response_model=GetApprovalStatusResponse)
async def get_approval_status(
    approval_id: str,
    user=Depends(get_current_user)
):
    """
    Get approval status and audit trail

    Requires: Authentication

    Args:
        approval_id: Approval ID
        user: Current authenticated user

    Returns:
        GetApprovalStatusResponse with approval details and audit trail
    """
    try:
        supabase = get_supabase_client()
        workflow_service = ApprovalWorkflowService()

        # Get approval record
        result = supabase.table("document_approvals").select("*").eq("id", approval_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval {approval_id} not found"
            )

        approval = result.data[0]

        # Get version if exists
        version = None
        if approval["version_id"]:
            version_result = supabase.table("document_versions").select("*").eq(
                "id", approval["version_id"]
            ).execute()
            if version_result.data:
                version = DocumentVersion(**version_result.data[0])

        # Get audit trail
        audit_trail_data = await workflow_service.get_approval_history(approval_id)
        audit_trail = [ApprovalAuditLogEntry(**entry) for entry in audit_trail_data]

        return GetApprovalStatusResponse(
            approval=DocumentApproval(**approval),
            version=version,
            audit_trail=audit_trail
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get approval status", error=str(e), approval_id=approval_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get approval status: {str(e)}"
        )


@router.get("/approvals", response_model=ListApprovalsResponse)
async def list_approvals(
    user=Depends(get_current_user),
    status_filter: Optional[ApprovalStatus] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List approvals for the current user (or all if admin)

    Requires: Authentication

    Args:
        user: Current authenticated user
        status_filter: Optional filter by approval status
        limit: Maximum number of approvals to return
        offset: Number of approvals to skip

    Returns:
        ListApprovalsResponse with list of approvals
    """
    try:
        supabase = get_supabase_client()

        # Build query
        query = supabase.table("document_approvals").select("*")

        # Filter by status if provided
        if status_filter:
            query = query.eq("approval_status", status_filter)

        # TODO: Check if user is admin, if not filter by user_id
        # For now, show all approvals for the user

        # Execute query with pagination
        result = query.order("updated_at", desc=True).range(offset, offset + limit - 1).execute()

        approvals = [DocumentApproval(**approval) for approval in result.data]

        # Get total count
        count_query = supabase.table("document_approvals").select("id", count="exact")
        if status_filter:
            count_query = count_query.eq("approval_status", status_filter)

        count_result = count_query.execute()
        total_count = count_result.count if count_result.count else 0

        return ListApprovalsResponse(
            approvals=approvals,
            total_count=total_count,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error("Failed to list approvals", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list approvals: {str(e)}"
        )


@router.post("/approvals/bulk-action", response_model=BatchOperationResponse)
async def bulk_approval_action(
    request: BulkApprovalActionRequest,
    user=Depends(get_current_user)
):
    """
    Perform bulk approval/rejection actions

    Requires: documents:approve permission (or admin role)

    Args:
        request: Bulk approval action request
        user: Current authenticated user

    Returns:
        BatchOperationResponse with results
    """
    try:
        workflow_service = ApprovalWorkflowService()

        # Validate action
        if request.action not in ["approve", "reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'approve' or 'reject'"
            )

        # Validate rejection reason for reject action
        if request.action == "reject" and not request.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required for reject action"
            )

        # Perform bulk transition
        event = ApprovalEvent.APPROVE if request.action == "approve" else ApprovalEvent.REJECT

        results = await workflow_service.bulk_transition(
            approval_ids=request.approval_ids,
            event=event,
            user_id=user,
            notes=request.notes,
            rejection_reason=request.rejection_reason if request.action == "reject" else None
        )

        logger.info(
            "Bulk approval action completed",
            action=request.action,
            total=results["total"],
            successful=results["successful"],
            failed=results["failed"],
            user_id=user
        )

        return BatchOperationResponse(
            operation_id=str(uuid.uuid4()),
            operation_type=f"bulk_approval_{request.action}",
            status=BatchOperationStatus.COMPLETED if results["failed"] == 0 else BatchOperationStatus.PARTIAL_SUCCESS,
            total_items=results["total"],
            processed_items=results["total"],
            successful_items=results["successful"],
            failed_items=results["failed"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message=f"Bulk {request.action} completed: {results['successful']}/{results['total']} successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to perform bulk approval action", error=str(e), user_id=user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk approval action: {str(e)}"
        )
