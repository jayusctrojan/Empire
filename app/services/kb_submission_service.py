"""
KB Submission Service

Manages the submission pipeline for agent content submissions to the knowledge base.
CKO reviews and processes submissions with full audit trail and duplicate detection.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

import structlog

from app.services.supabase_storage import get_supabase_storage

logger = structlog.get_logger(__name__)

VALID_TYPES = {"url", "document", "work", "auto-synthesis"}
VALID_STATUSES = {"pending", "processing", "accepted", "rejected"}
VALID_DECISIONS = {"accepted", "rejected", "deferred"}


@dataclass
class KBSubmission:
    id: str
    agent_id: str
    submission_type: str
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    submitted_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    cko_decision: Optional[str] = None
    cko_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agentId": self.agent_id,
            "submissionType": self.submission_type,
            "contentUrl": self.content_url,
            "contentText": self.content_text[:200] + "..." if self.content_text and len(self.content_text) > 200 else self.content_text,
            "metadata": self.metadata,
            "status": self.status,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "processedAt": self.processed_at.isoformat() if self.processed_at else None,
            "ckoDecision": self.cko_decision,
            "ckoNotes": self.cko_notes,
        }


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    return datetime.fromisoformat(val.replace("Z", "+00:00"))


def _row_to_submission(row: Dict[str, Any]) -> KBSubmission:
    return KBSubmission(
        id=row["id"],
        agent_id=row["agent_id"],
        submission_type=row["submission_type"],
        content_url=row.get("content_url"),
        content_text=row.get("content_text"),
        metadata=row.get("metadata") or {},
        status=row["status"],
        submitted_at=_parse_dt(row.get("submitted_at")),
        processed_at=_parse_dt(row.get("processed_at")),
        cko_decision=row.get("cko_decision"),
        cko_notes=row.get("cko_notes"),
        created_at=_parse_dt(row.get("created_at")),
        updated_at=_parse_dt(row.get("updated_at")),
    )


class KBSubmissionService:
    def __init__(self):
        self.supabase = get_supabase_storage()

    async def create_submission(
        self,
        agent_id: str,
        submission_type: str,
        content_url: Optional[str] = None,
        content_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KBSubmission:
        """Create a new KB submission."""
        if submission_type not in VALID_TYPES:
            raise ValueError(f"Invalid submission_type: {submission_type}. Must be one of {VALID_TYPES}")

        if not content_url and not content_text:
            raise ValueError("Either content_url or content_text is required")

        # Duplicate detection: same URL within 24h
        if content_url:
            is_dup = await self._check_duplicate_url(content_url)
            if is_dup:
                raise ValueError(f"Duplicate submission: URL '{content_url}' was submitted within the last 24 hours")

        now = datetime.now(timezone.utc)
        insert_data = {
            "agent_id": agent_id,
            "submission_type": submission_type,
            "content_url": content_url,
            "content_text": content_text,
            "metadata": metadata or {},
            "status": "pending",
            "submitted_at": now.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("kb_submissions")
                .insert(insert_data)
                .execute()
        )

        if not result.data:
            raise Exception("Failed to create submission")

        submission = _row_to_submission(result.data[0])
        logger.info("kb_submission_created",
                     submission_id=submission.id,
                     agent_id=agent_id,
                     type=submission_type)
        return submission

    async def list_submissions(
        self,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[KBSubmission]:
        """List submissions, optionally filtered by status or agent."""
        def _query():
            q = self.supabase.supabase.table("kb_submissions").select("*")
            if status:
                q = q.eq("status", status)
            if agent_id:
                q = q.eq("agent_id", agent_id)
            return q.order("submitted_at", desc=True).limit(limit).execute()

        result = await asyncio.to_thread(_query)
        return [_row_to_submission(row) for row in (result.data or [])]

    async def get_submission(self, submission_id: str) -> Optional[KBSubmission]:
        """Get a single submission by ID."""
        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("kb_submissions")
                .select("*")
                .eq("id", submission_id)
                .limit(1)
                .execute()
        )
        if result.data:
            return _row_to_submission(result.data[0])
        return None

    async def process_submission(
        self,
        submission_id: str,
        decision: str,
        notes: Optional[str] = None,
    ) -> Optional[KBSubmission]:
        """Process a submission: accept, reject, or defer."""
        if decision not in VALID_DECISIONS:
            raise ValueError(f"Invalid decision: {decision}. Must be one of {VALID_DECISIONS}")

        now = datetime.now(timezone.utc)
        status = "accepted" if decision == "accepted" else "rejected" if decision == "rejected" else "pending"

        update_data = {
            "cko_decision": decision,
            "cko_notes": notes,
            "status": status,
            "processed_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("kb_submissions")
                .update(update_data)
                .eq("id", submission_id)
                .execute()
        )

        if not result.data:
            return None

        submission = _row_to_submission(result.data[0])
        logger.info("kb_submission_processed",
                     submission_id=submission_id,
                     decision=decision)
        return submission

    async def _check_duplicate_url(self, url: str) -> bool:
        """Check if the same URL was submitted within the last 24 hours."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("kb_submissions")
                .select("id")
                .eq("content_url", url)
                .gte("submitted_at", cutoff)
                .limit(1)
                .execute()
        )
        return bool(result.data)


_service: Optional[KBSubmissionService] = None


def get_kb_submission_service() -> KBSubmissionService:
    global _service
    if _service is None:
        _service = KBSubmissionService()
    return _service
