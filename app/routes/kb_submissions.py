"""
KB Submissions API Routes

REST API for the knowledge base submission pipeline.
Agents submit content via POST, CKO reviews via GET/PATCH.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.services.kb_submission_service import get_kb_submission_service

router = APIRouter(prefix="/api/kb", tags=["KB Submissions"])


# ---------------------------------------------------------------------------
# Auth — internal API, accessed by agents via the gateway service role.
# ---------------------------------------------------------------------------

async def verify_internal_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Validate requests come from authorized internal services (gateway/agents)."""
    import os
    expected = os.getenv("EMPIRE_INTERNAL_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class SubmitRequest(BaseModel):
    agent_id: str
    submission_type: str = Field(default="url", pattern="^(url|document|work|auto-synthesis)$")
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    metadata: Optional[dict] = None

    @model_validator(mode="after")
    def check_content_provided(self):
        if not self.content_url and not self.content_text:
            raise ValueError("At least one of content_url or content_text must be provided")
        return self


class ProcessRequest(BaseModel):
    decision: str = Field(pattern="^(accepted|rejected|deferred)$")
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/submit", dependencies=[Depends(verify_internal_api_key)])
async def submit_content(req: SubmitRequest):
    """Submit content for CKO review. Called by agents via kb-query skill."""
    service = get_kb_submission_service()
    try:
        submission = await service.create_submission(
            agent_id=req.agent_id,
            submission_type=req.submission_type,
            content_url=req.content_url,
            content_text=req.content_text,
            metadata=req.metadata,
        )
        return {"submission": submission.to_dict(), "status": "created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/submissions", dependencies=[Depends(verify_internal_api_key)])
async def list_submissions(
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 20,
):
    """List submissions. CKO uses this to poll for pending items."""
    service = get_kb_submission_service()
    submissions = await service.list_submissions(
        status=status,
        agent_id=agent_id,
        limit=limit,
    )
    return {
        "submissions": [s.to_dict() for s in submissions],
        "count": len(submissions),
    }


@router.get("/submissions/{submission_id}", dependencies=[Depends(verify_internal_api_key)])
async def get_submission(submission_id: str):
    """Get a single submission by ID."""
    service = get_kb_submission_service()
    submission = await service.get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"submission": submission.to_dict()}


@router.patch("/submissions/{submission_id}", dependencies=[Depends(verify_internal_api_key)])
async def process_submission(submission_id: str, req: ProcessRequest):
    """Process a submission (accept/reject/defer). CKO only."""
    service = get_kb_submission_service()
    try:
        submission = await service.process_submission(
            submission_id=submission_id,
            decision=req.decision,
            notes=req.notes,
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        return {"submission": submission.to_dict(), "status": "processed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
