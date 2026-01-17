"""
Empire v7.3 - Research Project Service
Business logic for the Research Projects (Agent Harness) feature.
"""

import secrets
from typing import Optional, List
from datetime import datetime, timedelta
import structlog
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.models.research_project import (
    ResearchType,
    JobStatus,
    TaskStatus,
    CreateResearchProjectRequest,
    ResearchProjectSummary,
    ResearchProjectDetail,
    ProjectStatusResponse,
    TaskResponse,
    ReportResponse,
    FindingsResponse,
    ShareResponse,
    PublicReportResponse,
    CreateProjectResponse,
    ListProjectsResponse,
    CancelProjectResponse,
    CreateShareResponse,
    ListSharesResponse,
    RevokeShareResponse,
)

logger = structlog.get_logger(__name__)


class ResearchProjectService:
    """Service for managing research projects"""

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.base_url = "https://jb-empire-api.onrender.com"  # Configure via env

    # ==========================================================================
    # Project CRUD Operations
    # ==========================================================================

    async def create_project(
        self,
        user_id: str,
        customer_id: str,
        request: CreateResearchProjectRequest
    ) -> CreateProjectResponse:
        """Create a new research project"""
        try:
            # Insert into research_jobs table
            result = self.supabase.table("research_jobs").insert({
                "user_id": user_id,
                "customer_id": customer_id,
                "query": request.query,
                "context": request.context,
                "research_type": request.research_type.value,
                "notify_email": request.notify_email,
                "status": JobStatus.INITIALIZING.value,
            }).execute()

            if not result.data:
                logger.error("Failed to create research project", user_id=user_id)
                return CreateProjectResponse(
                    success=False,
                    job_id=0,
                    status=JobStatus.FAILED,
                    message="Failed to create research project"
                )

            job = result.data[0]
            logger.info(
                "Research project created",
                job_id=job["id"],
                user_id=user_id,
                research_type=request.research_type.value
            )

            # Task 187: Trigger Celery task for initialization
            from app.tasks.research_tasks import initialize_research_job
            celery_task = initialize_research_job.delay(job["id"])

            # Store Celery task ID for potential cancellation
            self.supabase.table("research_jobs").update({
                "celery_task_id": celery_task.id
            }).eq("id", job["id"]).execute()

            logger.info(
                "Research job initialization task queued",
                job_id=job["id"],
                celery_task_id=celery_task.id
            )

            return CreateProjectResponse(
                success=True,
                job_id=job["id"],
                status=JobStatus.INITIALIZING,
                message="Research project created. Task planning will begin shortly."
            )

        except Exception as e:
            logger.error("Error creating research project", error=str(e), user_id=user_id)
            # Check for concurrent limit violation
            if "Maximum concurrent projects limit" in str(e):
                return CreateProjectResponse(
                    success=False,
                    job_id=0,
                    status=JobStatus.FAILED,
                    message="Maximum concurrent projects limit (3) reached. Please wait for existing projects to complete."
                )
            raise

    async def list_projects(
        self,
        user_id: str,
        status_filter: Optional[JobStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> ListProjectsResponse:
        """List research projects for a user"""
        try:
            query = self.supabase.table("research_jobs").select(
                "id, query, research_type, status, progress_percentage, "
                "total_tasks, completed_tasks, created_at, updated_at, completed_at"
            ).eq("user_id", user_id)

            if status_filter:
                query = query.eq("status", status_filter.value)

            # Get total count
            count_result = query.execute()
            total = len(count_result.data) if count_result.data else 0

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)
            result = query.execute()

            projects = [
                ResearchProjectSummary(
                    id=row["id"],
                    query=row["query"][:100] + "..." if len(row["query"]) > 100 else row["query"],
                    research_type=ResearchType(row["research_type"]),
                    status=JobStatus(row["status"]),
                    progress_percentage=float(row["progress_percentage"] or 0),
                    total_tasks=row["total_tasks"] or 0,
                    completed_tasks=row["completed_tasks"] or 0,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row["completed_at"],
                )
                for row in (result.data or [])
            ]

            return ListProjectsResponse(
                success=True,
                projects=projects,
                total=total,
                page=page,
                page_size=page_size
            )

        except Exception as e:
            logger.error("Error listing projects", error=str(e), user_id=user_id)
            raise

    async def get_project(self, user_id: str, job_id: int) -> Optional[ResearchProjectDetail]:
        """Get detailed project information including tasks"""
        try:
            # Get job details
            job_result = self.supabase.table("research_jobs").select("*").eq(
                "id", job_id
            ).eq("user_id", user_id).single().execute()

            if not job_result.data:
                return None

            job = job_result.data

            # Get tasks for this job
            tasks_result = self.supabase.table("plan_tasks").select("*").eq(
                "job_id", job_id
            ).order("sequence_order").execute()

            tasks = [
                TaskResponse(
                    id=t["id"],
                    task_key=t["task_key"],
                    task_type=t["task_type"],
                    task_title=t.get("task_title"),
                    task_description=t.get("task_description"),
                    status=TaskStatus(t["status"]),
                    sequence_order=t["sequence_order"],
                    depends_on=t.get("depends_on"),
                    result_summary=t.get("result_summary"),
                    artifacts_count=t.get("artifacts_count", 0),
                    started_at=t.get("started_at"),
                    completed_at=t.get("completed_at"),
                    duration_seconds=t.get("duration_seconds"),
                    error_message=t.get("error_message"),
                )
                for t in (tasks_result.data or [])
            ]

            return ResearchProjectDetail(
                id=job["id"],
                query=job["query"],
                context=job.get("context"),
                research_type=ResearchType(job["research_type"]),
                status=JobStatus(job["status"]),
                progress_percentage=float(job["progress_percentage"] or 0),
                total_tasks=job["total_tasks"] or 0,
                completed_tasks=job["completed_tasks"] or 0,
                current_task_key=job.get("current_task_key"),
                tasks=tasks,
                summary=job.get("summary"),
                key_findings=job.get("key_findings"),
                report_url=job.get("report_url"),
                error_message=job.get("error_message"),
                created_at=job["created_at"],
                updated_at=job["updated_at"],
                started_at=job.get("started_at"),
                completed_at=job.get("completed_at"),
            )

        except Exception as e:
            logger.error("Error getting project", error=str(e), job_id=job_id)
            raise

    async def get_project_status(self, user_id: str, job_id: int) -> Optional[ProjectStatusResponse]:
        """Get lightweight project status for polling"""
        try:
            result = self.supabase.table("research_jobs").select(
                "id, status, progress_percentage, total_tasks, completed_tasks, "
                "current_task_key, error_message"
            ).eq("id", job_id).eq("user_id", user_id).single().execute()

            if not result.data:
                return None

            job = result.data
            return ProjectStatusResponse(
                id=job["id"],
                status=JobStatus(job["status"]),
                progress_percentage=float(job["progress_percentage"] or 0),
                total_tasks=job["total_tasks"] or 0,
                completed_tasks=job["completed_tasks"] or 0,
                current_task_key=job.get("current_task_key"),
                error_message=job.get("error_message"),
            )

        except Exception as e:
            logger.error("Error getting project status", error=str(e), job_id=job_id)
            raise

    async def cancel_project(self, user_id: str, job_id: int) -> CancelProjectResponse:
        """Cancel an active research project"""
        try:
            # Get current status and celery task ID
            job_result = self.supabase.table("research_jobs").select(
                "id, status, celery_task_id"
            ).eq("id", job_id).eq("user_id", user_id).single().execute()

            if not job_result.data:
                return CancelProjectResponse(
                    success=False,
                    job_id=job_id,
                    message="Project not found"
                )

            job = job_result.data
            current_status = job["status"]
            if current_status in ["complete", "failed", "cancelled"]:
                return CancelProjectResponse(
                    success=False,
                    job_id=job_id,
                    status=JobStatus(current_status),
                    message=f"Cannot cancel project with status: {current_status}"
                )

            # Task 187: Revoke Celery tasks
            revoked_tasks = 0
            from app.celery_app import celery_app

            # Revoke the main initialization/execution task if exists
            if job.get("celery_task_id"):
                try:
                    celery_app.control.revoke(
                        job["celery_task_id"],
                        terminate=True,
                        signal="SIGTERM"
                    )
                    revoked_tasks += 1
                    logger.info(
                        "Revoked main Celery task",
                        job_id=job_id,
                        celery_task_id=job["celery_task_id"]
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to revoke main Celery task",
                        job_id=job_id,
                        celery_task_id=job["celery_task_id"],
                        error=str(e)
                    )

            # Revoke any running plan tasks with celery_task_id
            running_tasks_result = self.supabase.table("plan_tasks").select(
                "id, celery_task_id"
            ).eq("job_id", job_id).in_(
                "status", [TaskStatus.RUNNING.value, TaskStatus.QUEUED.value]
            ).execute()

            running_tasks = running_tasks_result.data or []
            for task in running_tasks:
                if task.get("celery_task_id"):
                    try:
                        celery_app.control.revoke(
                            task["celery_task_id"],
                            terminate=True,
                            signal="SIGTERM"
                        )
                        revoked_tasks += 1
                        logger.info(
                            "Revoked plan task",
                            task_id=task["id"],
                            celery_task_id=task["celery_task_id"]
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to revoke plan task",
                            task_id=task["id"],
                            error=str(e)
                        )

            # Update job status
            self.supabase.table("research_jobs").update({
                "status": JobStatus.CANCELLED.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", job_id).execute()

            # Cancel pending/queued/running tasks
            self.supabase.table("plan_tasks").update({
                "status": TaskStatus.CANCELLED.value
            }).eq("job_id", job_id).in_(
                "status", [
                    TaskStatus.PENDING.value,
                    TaskStatus.QUEUED.value,
                    TaskStatus.RUNNING.value
                ]
            ).execute()

            logger.info(
                "Project cancelled",
                job_id=job_id,
                user_id=user_id,
                revoked_tasks=revoked_tasks
            )

            return CancelProjectResponse(
                success=True,
                job_id=job_id,
                status=JobStatus.CANCELLED,
                message=f"Project cancelled successfully. Revoked {revoked_tasks} Celery task(s)."
            )

        except Exception as e:
            logger.error("Error cancelling project", error=str(e), job_id=job_id)
            raise

    async def get_report(self, user_id: str, job_id: int) -> Optional[ReportResponse]:
        """Get the final research report"""
        try:
            result = self.supabase.table("research_jobs").select(
                "id, status, summary, key_findings, report_content, report_url, completed_at"
            ).eq("id", job_id).eq("user_id", user_id).single().execute()

            if not result.data:
                return None

            job = result.data
            return ReportResponse(
                id=job["id"],
                status=JobStatus(job["status"]),
                summary=job.get("summary"),
                key_findings=job.get("key_findings"),
                report_content=job.get("report_content"),
                report_url=job.get("report_url"),
                completed_at=job.get("completed_at"),
            )

        except Exception as e:
            logger.error("Error getting report", error=str(e), job_id=job_id)
            raise

    # ==========================================================================
    # Partial Findings (FR-009)
    # ==========================================================================

    async def get_partial_findings(self, user_id: str, job_id: int) -> Optional[FindingsResponse]:
        """Get findings from completed tasks before full report"""
        try:
            # Verify user owns the project
            job_result = self.supabase.table("research_jobs").select(
                "id, status, progress_percentage"
            ).eq("id", job_id).eq("user_id", user_id).single().execute()

            if not job_result.data:
                return None

            job = job_result.data

            # Get completed tasks with their artifacts
            tasks_result = self.supabase.table("plan_tasks").select(
                "id, task_key, task_type, result_summary, completed_at"
            ).eq("job_id", job_id).eq("status", TaskStatus.COMPLETE.value).execute()

            completed_findings = []
            for task in (tasks_result.data or []):
                # Get artifacts for this task
                artifacts_result = self.supabase.table("research_artifacts").select(
                    "artifact_type, processed_content, relevance_score, source, created_at"
                ).eq("task_id", task["id"]).execute()

                completed_findings.append({
                    "task_key": task["task_key"],
                    "task_type": task["task_type"],
                    "completed_at": task["completed_at"],
                    "result_summary": task.get("result_summary"),
                    "artifacts": [
                        {
                            "artifact_type": a["artifact_type"],
                            "processed_content": a.get("processed_content", "")[:500],  # Truncate
                            "relevance_score": a.get("relevance_score"),
                            "source": a.get("source"),
                        }
                        for a in (artifacts_result.data or [])
                    ]
                })

            return FindingsResponse(
                job_id=job_id,
                status=JobStatus(job["status"]),
                progress_percentage=float(job["progress_percentage"] or 0),
                completed_findings=completed_findings
            )

        except Exception as e:
            logger.error("Error getting partial findings", error=str(e), job_id=job_id)
            raise

    # ==========================================================================
    # Share Link Management (FR-005, FR-005a)
    # ==========================================================================

    async def create_share(
        self,
        user_id: str,
        job_id: int,
        expires_in_days: Optional[int] = None
    ) -> CreateShareResponse:
        """Create a shareable public link for a report"""
        try:
            # Verify user owns the project and it's complete
            job_result = self.supabase.table("research_jobs").select(
                "id, status"
            ).eq("id", job_id).eq("user_id", user_id).single().execute()

            if not job_result.data:
                return CreateShareResponse(
                    success=False,
                    share=None,
                    message="Project not found"
                )

            if job_result.data["status"] != JobStatus.COMPLETE.value:
                return CreateShareResponse(
                    success=False,
                    share=None,
                    message="Can only share completed projects"
                )

            # Generate secure token
            share_token = secrets.token_urlsafe(32)
            expires_at = None
            if expires_in_days:
                expires_at = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()

            # Create share record
            result = self.supabase.table("shared_reports").insert({
                "job_id": job_id,
                "share_token": share_token,
                "created_by": user_id,
                "expires_at": expires_at,
            }).execute()

            if not result.data:
                return CreateShareResponse(
                    success=False,
                    share=None,
                    message="Failed to create share link"
                )

            share_data = result.data[0]
            share_url = f"{self.base_url}/api/research-projects/shared/{share_token}"

            share = ShareResponse(
                id=share_data["id"],
                share_token=share_token,
                share_url=share_url,
                created_at=share_data["created_at"],
                expires_at=share_data.get("expires_at"),
                view_count=0,
            )

            logger.info("Share link created", job_id=job_id, share_id=share.id)

            return CreateShareResponse(
                success=True,
                share=share,
                message="Share link created successfully"
            )

        except Exception as e:
            logger.error("Error creating share", error=str(e), job_id=job_id)
            raise

    async def list_shares(self, user_id: str, job_id: int) -> ListSharesResponse:
        """List all share links for a project"""
        try:
            # Verify user owns the project
            job_result = self.supabase.table("research_jobs").select("id").eq(
                "id", job_id
            ).eq("user_id", user_id).single().execute()

            if not job_result.data:
                return ListSharesResponse(success=False, shares=[], total=0)

            # Get shares
            result = self.supabase.table("shared_reports").select("*").eq(
                "job_id", job_id
            ).order("created_at", desc=True).execute()

            shares = [
                ShareResponse(
                    id=s["id"],
                    share_token=s["share_token"],
                    share_url=f"{self.base_url}/api/research-projects/shared/{s['share_token']}",
                    created_at=s["created_at"],
                    expires_at=s.get("expires_at"),
                    revoked_at=s.get("revoked_at"),
                    view_count=s.get("view_count", 0),
                    last_viewed_at=s.get("last_viewed_at"),
                )
                for s in (result.data or [])
            ]

            return ListSharesResponse(
                success=True,
                shares=shares,
                total=len(shares)
            )

        except Exception as e:
            logger.error("Error listing shares", error=str(e), job_id=job_id)
            raise

    async def revoke_share(self, user_id: str, job_id: int, share_id: int) -> RevokeShareResponse:
        """Revoke a share link"""
        try:
            # Verify user owns the share (via created_by)
            share_result = self.supabase.table("shared_reports").select(
                "id, created_by"
            ).eq("id", share_id).eq("job_id", job_id).single().execute()

            if not share_result.data:
                return RevokeShareResponse(
                    success=False,
                    share_id=share_id,
                    message="Share link not found"
                )

            if share_result.data["created_by"] != user_id:
                return RevokeShareResponse(
                    success=False,
                    share_id=share_id,
                    message="Not authorized to revoke this share"
                )

            # Revoke (set revoked_at)
            self.supabase.table("shared_reports").update({
                "revoked_at": datetime.utcnow().isoformat(),
                "revoked_by": user_id,
            }).eq("id", share_id).execute()

            logger.info("Share link revoked", share_id=share_id, user_id=user_id)

            return RevokeShareResponse(
                success=True,
                share_id=share_id,
                message="Share link revoked successfully"
            )

        except Exception as e:
            logger.error("Error revoking share", error=str(e), share_id=share_id)
            raise

    async def get_public_report(self, share_token: str) -> Optional[PublicReportResponse]:
        """Get report via public share token (no auth required)"""
        try:
            # Use the database function to validate and increment view count
            result = self.supabase.rpc(
                "increment_share_view",
                {"p_token": share_token}
            ).execute()

            if not result.data or not result.data[0].get("is_valid"):
                return None

            data = result.data[0]

            # Get full report details
            job_result = self.supabase.table("research_jobs").select(
                "id, query, research_type, completed_at, summary, key_findings, "
                "report_content, report_url"
            ).eq("id", data["job_id"]).single().execute()

            if not job_result.data:
                return None

            job = job_result.data
            return PublicReportResponse(
                job_id=job["id"],
                query=job["query"],
                research_type=ResearchType(job["research_type"]),
                completed_at=job.get("completed_at"),
                summary=job.get("summary"),
                key_findings=job.get("key_findings"),
                report_content=job.get("report_content"),
                report_url=job.get("report_url"),
            )

        except Exception as e:
            logger.error("Error getting public report", error=str(e))
            return None


# ==============================================================================
# Service Factory
# ==============================================================================

_service_instance: Optional[ResearchProjectService] = None


def get_research_project_service() -> ResearchProjectService:
    """Get or create research project service singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ResearchProjectService(get_supabase_client())
    return _service_instance
