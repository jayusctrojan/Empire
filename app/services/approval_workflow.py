"""
Approval Workflow State Machine - Task 32.2
Handles document approval workflow state transitions and validation
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import structlog

from app.core.supabase_client import get_supabase_client
from app.models.documents import ApprovalStatus

logger = structlog.get_logger(__name__)


class ApprovalEvent(str, Enum):
    """Events that trigger state transitions"""
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    ARCHIVE = "archive"
    REOPEN = "reopen"


def _map_event_to_audit_type(event: ApprovalEvent) -> str:
    """
    Map ApprovalEvent enum values to database-compliant event_type strings.

    Database constraint expects: ['created', 'status_changed', 'submitted',
    'approved', 'rejected', 'archived', 'notes_added', 'version_updated']
    """
    mapping = {
        ApprovalEvent.SUBMIT: "submitted",
        ApprovalEvent.APPROVE: "approved",
        ApprovalEvent.REJECT: "rejected",
        ApprovalEvent.ARCHIVE: "archived",
        ApprovalEvent.REOPEN: "status_changed"
    }
    return mapping.get(event, "status_changed")


# State Machine Definition
# Format: {current_state: {event: next_state}}
STATE_TRANSITIONS = {
    ApprovalStatus.DRAFT: {
        ApprovalEvent.SUBMIT: ApprovalStatus.PENDING_REVIEW,
        ApprovalEvent.ARCHIVE: ApprovalStatus.ARCHIVED,
    },
    ApprovalStatus.PENDING_REVIEW: {
        ApprovalEvent.APPROVE: ApprovalStatus.APPROVED,
        ApprovalEvent.REJECT: ApprovalStatus.REJECTED,
        ApprovalEvent.ARCHIVE: ApprovalStatus.ARCHIVED,
    },
    ApprovalStatus.APPROVED: {
        ApprovalEvent.ARCHIVE: ApprovalStatus.ARCHIVED,
        ApprovalEvent.REOPEN: ApprovalStatus.DRAFT,  # Allow reopening for new version
    },
    ApprovalStatus.REJECTED: {
        ApprovalEvent.REOPEN: ApprovalStatus.DRAFT,  # Allow fixing and resubmitting
        ApprovalEvent.ARCHIVE: ApprovalStatus.ARCHIVED,
    },
    ApprovalStatus.ARCHIVED: {
        # Archived is terminal state (no transitions)
    },
}


class ApprovalWorkflowService:
    """Service for managing document approval workflow"""

    def __init__(self):
        self.supabase = get_supabase_client()

    def is_valid_transition(
        self,
        current_status: ApprovalStatus,
        event: ApprovalEvent
    ) -> bool:
        """
        Check if a state transition is valid

        Args:
            current_status: Current approval status
            event: Event triggering the transition

        Returns:
            True if transition is valid, False otherwise
        """
        if current_status not in STATE_TRANSITIONS:
            return False

        allowed_events = STATE_TRANSITIONS[current_status]
        return event in allowed_events

    def get_next_status(
        self,
        current_status: ApprovalStatus,
        event: ApprovalEvent
    ) -> Optional[ApprovalStatus]:
        """
        Get the next status given current status and event

        Args:
            current_status: Current approval status
            event: Event triggering the transition

        Returns:
            Next approval status, or None if invalid transition
        """
        if not self.is_valid_transition(current_status, event):
            return None

        return STATE_TRANSITIONS[current_status][event]

    async def create_approval(
        self,
        document_id: str,
        version_id: Optional[str],
        user_id: str,
        initial_status: ApprovalStatus = ApprovalStatus.DRAFT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new approval record for a document

        Args:
            document_id: Document ID
            version_id: Optional specific version ID
            user_id: User creating the approval
            initial_status: Initial approval status (default: DRAFT)
            metadata: Additional metadata

        Returns:
            Created approval record
        """
        approval_id = str(uuid.uuid4())

        approval_data = {
            "id": approval_id,
            "document_id": document_id,
            "version_id": version_id,
            "approval_status": initial_status,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = self.supabase.table("document_approvals").insert(approval_data).execute()

        if not result.data:
            raise Exception("Failed to create approval record")

        logger.info(
            "Approval created",
            approval_id=approval_id,
            document_id=document_id,
            status=initial_status,
            user_id=user_id
        )

        return result.data[0]

    async def transition_status(
        self,
        approval_id: str,
        event: ApprovalEvent,
        user_id: str,
        notes: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Perform a state transition on an approval

        Args:
            approval_id: Approval ID
            event: Event triggering the transition
            user_id: User performing the action
            notes: Optional notes for the transition
            rejection_reason: Required for REJECT event
            ip_address: Optional IP address for audit
            user_agent: Optional user agent for audit

        Returns:
            Tuple of (success, message, updated_approval)
        """
        # Fetch current approval
        result = self.supabase.table("document_approvals").select("*").eq("id", approval_id).execute()

        if not result.data:
            return False, f"Approval {approval_id} not found", None

        approval = result.data[0]
        current_status = ApprovalStatus(approval["approval_status"])

        # Check if transition is valid
        if not self.is_valid_transition(current_status, event):
            return False, f"Invalid transition from {current_status} with event {event}", None

        # Validate rejection reason for REJECT event
        if event == ApprovalEvent.REJECT and not rejection_reason:
            return False, "Rejection reason is required for REJECT event", None

        # Get next status
        next_status = self.get_next_status(current_status, event)

        # Prepare update data
        update_data = {
            "approval_status": next_status,
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Update specific fields based on event
        if event == ApprovalEvent.SUBMIT:
            update_data["submitted_by"] = user_id
            update_data["submitted_at"] = datetime.utcnow().isoformat()

        elif event == ApprovalEvent.APPROVE:
            update_data["reviewed_by"] = user_id
            update_data["reviewed_at"] = datetime.utcnow().isoformat()
            if notes:
                update_data["approval_notes"] = notes

        elif event == ApprovalEvent.REJECT:
            update_data["reviewed_by"] = user_id
            update_data["reviewed_at"] = datetime.utcnow().isoformat()
            update_data["rejection_reason"] = rejection_reason
            if notes:
                update_data["approval_notes"] = notes

        # Update approval record
        result = self.supabase.table("document_approvals").update(update_data).eq("id", approval_id).execute()

        if not result.data:
            return False, "Failed to update approval status", None

        # Create audit log entry
        await self._create_audit_log(
            approval_id=approval_id,
            event_type=_map_event_to_audit_type(event),
            previous_status=current_status,
            new_status=next_status,
            changed_by=user_id,
            change_reason=notes or rejection_reason,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Update document approval_status if needed
        await self._update_document_approval_status(approval["document_id"], next_status)

        logger.info(
            "Approval status transitioned",
            approval_id=approval_id,
            previous_status=current_status,
            new_status=next_status,
            approval_event=event.value,
            user_id=user_id
        )

        return True, f"Successfully transitioned from {current_status} to {next_status}", result.data[0]

    async def _create_audit_log(
        self,
        approval_id: str,
        event_type: str,
        previous_status: ApprovalStatus,
        new_status: ApprovalStatus,
        changed_by: str,
        change_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Create an audit log entry"""
        audit_data = {
            "approval_id": approval_id,
            "event_type": event_type,
            "previous_status": previous_status,
            "new_status": new_status,
            "changed_by": changed_by,
            "change_reason": change_reason,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat(),
        }

        self.supabase.table("approval_audit_log").insert(audit_data).execute()

    async def _update_document_approval_status(
        self,
        document_id: str,
        approval_status: ApprovalStatus
    ):
        """Update the document's approval_status field"""
        self.supabase.table("documents").update({
            "approval_status": approval_status,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("document_id", document_id).execute()

    async def get_approval_history(
        self,
        approval_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get the complete audit history for an approval

        Args:
            approval_id: Approval ID

        Returns:
            List of audit log entries
        """
        result = self.supabase.table("approval_audit_log").select("*").eq(
            "approval_id", approval_id
        ).order("created_at", desc=False).execute()

        return result.data if result.data else []

    async def get_pending_approvals(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get all pending approvals

        Args:
            limit: Maximum number of approvals to return
            offset: Number of approvals to skip

        Returns:
            Tuple of (approvals, total_count)
        """
        # Get pending approvals
        result = self.supabase.table("document_approvals").select("*").eq(
            "approval_status", ApprovalStatus.PENDING_REVIEW
        ).order("submitted_at", desc=True).range(offset, offset + limit - 1).execute()

        approvals = result.data if result.data else []

        # Get total count
        count_result = self.supabase.table("document_approvals").select(
            "id", count="exact"
        ).eq("approval_status", ApprovalStatus.PENDING_REVIEW).execute()

        total_count = count_result.count if count_result.count else 0

        return approvals, total_count

    async def bulk_transition(
        self,
        approval_ids: List[str],
        event: ApprovalEvent,
        user_id: str,
        notes: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform bulk state transitions on multiple approvals

        Args:
            approval_ids: List of approval IDs
            event: Event to trigger for all approvals
            user_id: User performing the actions
            notes: Optional notes for all transitions
            rejection_reason: Required for REJECT event
            ip_address: Optional IP address for audit
            user_agent: Optional user agent for audit

        Returns:
            Dict with success/failure counts and details
        """
        results = {
            "total": len(approval_ids),
            "successful": 0,
            "failed": 0,
            "details": []
        }

        for approval_id in approval_ids:
            success, message, approval = await self.transition_status(
                approval_id=approval_id,
                event=event,
                user_id=user_id,
                notes=notes,
                rejection_reason=rejection_reason,
                ip_address=ip_address,
                user_agent=user_agent
            )

            if success:
                results["successful"] += 1
                results["details"].append({
                    "approval_id": approval_id,
                    "status": "success",
                    "message": message
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "approval_id": approval_id,
                    "status": "failed",
                    "error": message
                })

        logger.info(
            "Bulk approval transition completed",
            total=results["total"],
            successful=results["successful"],
            failed=results["failed"],
            event=event,
            user_id=user_id
        )

        return results
