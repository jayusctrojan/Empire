"""
Empire v7.3 - Research Project Notification Service (Task 99)

Notification service for sending emails to users at key points in the research process.
Builds on top of the existing EmailService infrastructure.

Author: Claude Code
Date: 2025-01-10
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

import structlog
from supabase import Client

from app.core.supabase_client import get_supabase_client
from app.services.email_service import get_email_service, EmailService

logger = structlog.get_logger(__name__)


# ==============================================================================
# Email Templates
# ==============================================================================

class ResearchEmailTemplates:
    """HTML email templates for research project notifications."""

    # Common styles
    COMMON_STYLES = """
        body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; font-weight: 600; }
        .header p { margin: 10px 0 0; opacity: 0.9; font-size: 14px; }
        .content { padding: 30px; }
        .content h2 { color: #333; font-size: 20px; margin-top: 0; }
        .query-box { background: #f8f9fa; border-left: 4px solid #667eea; padding: 15px; margin: 20px 0; font-style: italic; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }
        .stat-item { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 12px; color: #666; text-transform: uppercase; }
        .button { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 15px 0; }
        .button:hover { opacity: 0.9; }
        .findings-list { list-style: none; padding: 0; margin: 20px 0; }
        .findings-list li { padding: 10px 0; border-bottom: 1px solid #eee; }
        .findings-list li:last-child { border-bottom: none; }
        .findings-list li::before { content: "\\2022"; color: #667eea; font-weight: bold; display: inline-block; width: 1em; }
        .progress-bar { background: #e9ecef; border-radius: 10px; height: 20px; overflow: hidden; margin: 20px 0; }
        .progress-fill { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100%; transition: width 0.3s; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; border-top: 1px solid #eee; }
        .footer a { color: #667eea; text-decoration: none; }
        .error-box { background: #fee; border-left: 4px solid #e74c3c; padding: 15px; margin: 20px 0; }
        .error-box h3 { color: #e74c3c; margin: 0 0 10px; }
    """

    @classmethod
    def get_project_started_template(
        cls,
        query: str,
        estimated_tasks: int,
        research_type: str,
        project_url: str,
        estimated_time: str
    ) -> Dict[str, str]:
        """Generate project started email template."""
        return {
            "subject": f"Research Project Started: {query[:50]}{'...' if len(query) > 50 else ''}",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>{cls.COMMON_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Research Project Started</h1>
            <p>Empire v7.3 Research Assistant</p>
        </div>
        <div class="content">
            <h2>Your research is underway!</h2>

            <p>Our AI research assistant has started working on your query:</p>

            <div class="query-box">
                {query}
            </div>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{estimated_tasks}</div>
                    <div class="stat-label">Research Tasks</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{research_type.replace('_', ' ').title()}</div>
                    <div class="stat-label">Research Type</div>
                </div>
            </div>

            <p><strong>Estimated completion time:</strong> {estimated_time}</p>

            <p>We'll notify you when the research is complete. You can also check progress anytime:</p>

            <p style="text-align: center;">
                <a href="{project_url}" class="button">View Project Progress</a>
            </p>

            <p style="color: #666; font-size: 14px;">
                Our AI will search through your knowledge base, analyze relevant documents,
                synthesize findings, and generate a comprehensive research report.
            </p>
        </div>
        <div class="footer">
            <p>Empire v7.3 - AI Research Assistant</p>
            <p>You're receiving this because you started a research project.</p>
        </div>
    </div>
</body>
</html>
"""
        }

    @classmethod
    def get_progress_update_template(
        cls,
        query: str,
        progress_percent: float,
        completed_tasks: int,
        total_tasks: int,
        current_phase: str,
        project_url: str
    ) -> Dict[str, str]:
        """Generate progress update email template."""
        milestone = int(progress_percent // 25 * 25)  # 25, 50, 75

        return {
            "subject": f"Research {milestone}% Complete: {query[:40]}{'...' if len(query) > 40 else ''}",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>{cls.COMMON_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Progress Update</h1>
            <p>Your research is {milestone}% complete</p>
        </div>
        <div class="content">
            <h2>Making great progress!</h2>

            <p>Your research project is progressing well:</p>

            <div class="query-box">
                {query}
            </div>

            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress_percent}%;"></div>
            </div>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{completed_tasks}/{total_tasks}</div>
                    <div class="stat-label">Tasks Completed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{current_phase}</div>
                    <div class="stat-label">Current Phase</div>
                </div>
            </div>

            <p style="text-align: center;">
                <a href="{project_url}" class="button">View Live Progress</a>
            </p>
        </div>
        <div class="footer">
            <p>Empire v7.3 - AI Research Assistant</p>
            <p>We'll send another update when your research is complete.</p>
        </div>
    </div>
</body>
</html>
"""
        }

    @classmethod
    def get_project_completed_template(
        cls,
        query: str,
        key_findings: List[str],
        total_sources: int,
        research_duration: str,
        report_url: str,
        dashboard_url: str
    ) -> Dict[str, str]:
        """Generate project completed email template."""
        findings_html = "\n".join([f"<li>{finding}</li>" for finding in key_findings[:5]])

        return {
            "subject": f"Research Complete: {query[:50]}{'...' if len(query) > 50 else ''}",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>{cls.COMMON_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);">
            <h1>Research Complete!</h1>
            <p>Your comprehensive report is ready</p>
        </div>
        <div class="content">
            <h2>Great news! Your research is finished.</h2>

            <div class="query-box">
                {query}
            </div>

            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{total_sources}</div>
                    <div class="stat-label">Sources Analyzed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{research_duration}</div>
                    <div class="stat-label">Research Time</div>
                </div>
            </div>

            <h3>Key Findings:</h3>
            <ul class="findings-list">
                {findings_html}
            </ul>

            <p style="text-align: center;">
                <a href="{report_url}" class="button">View Full Report</a>
            </p>

            <p style="color: #666; font-size: 14px; text-align: center;">
                You can also access this and all your research projects from
                <a href="{dashboard_url}">your dashboard</a>.
            </p>
        </div>
        <div class="footer">
            <p>Empire v7.3 - AI Research Assistant</p>
            <p>Thank you for using Empire!</p>
        </div>
    </div>
</body>
</html>
"""
        }

    @classmethod
    def get_project_failed_template(
        cls,
        query: str,
        error_message: str,
        failed_task: Optional[str],
        support_url: str,
        retry_url: str
    ) -> Dict[str, str]:
        """Generate project failed email template."""
        return {
            "subject": f"Research Project Issue: {query[:50]}{'...' if len(query) > 50 else ''}",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>{cls.COMMON_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header" style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);">
            <h1>Research Project Issue</h1>
            <p>We encountered a problem</p>
        </div>
        <div class="content">
            <h2>We're sorry, but your research project encountered an issue.</h2>

            <div class="query-box">
                {query}
            </div>

            <div class="error-box">
                <h3>Error Details</h3>
                <p>{error_message}</p>
                {f'<p><strong>Failed task:</strong> {failed_task}</p>' if failed_task else ''}
            </div>

            <p>You can try running your research again, or contact support if the issue persists:</p>

            <p style="text-align: center;">
                <a href="{retry_url}" class="button">Retry Research</a>
            </p>

            <p style="color: #666; font-size: 14px; text-align: center;">
                Need help? <a href="{support_url}">Contact Support</a>
            </p>
        </div>
        <div class="footer">
            <p>Empire v7.3 - AI Research Assistant</p>
            <p>We apologize for the inconvenience.</p>
        </div>
    </div>
</body>
</html>
"""
        }


# ==============================================================================
# Research Notification Service
# ==============================================================================

class ResearchNotificationService:
    """
    Notification service for research projects.

    Sends emails to users at key points in the research process:
    - Project started
    - Progress milestones (25%, 50%, 75%)
    - Project completed
    - Project failed
    """

    # Progress milestones that trigger notifications
    PROGRESS_MILESTONES = [25, 50, 75]

    def __init__(
        self,
        supabase: Optional[Client] = None,
        email_service: Optional[EmailService] = None
    ):
        """Initialize notification service."""
        self.supabase = supabase or get_supabase_client()
        self.email_service = email_service or get_email_service()

        # Base URLs from environment
        self.app_base_url = os.getenv("APP_BASE_URL", "https://empire.ai")
        self.support_url = os.getenv("SUPPORT_URL", "https://empire.ai/support")

        # Track which milestones have been sent for each job
        self._sent_milestones: Dict[int, set] = {}

    def _get_job_details(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Fetch job details from database."""
        try:
            result = self.supabase.table("research_jobs").select(
                "*"
            ).eq("id", job_id).single().execute()
            return result.data
        except Exception as e:
            logger.error("Failed to fetch job details", job_id=job_id, error=str(e))
            return None

    def _get_user_email(self, user_id: str) -> Optional[str]:
        """Get user's email address from user_id."""
        # For now, assume user_id is the email or fetch from auth table
        # In production, this would query the user table
        if "@" in user_id:
            return user_id

        try:
            # Try to get from profiles table
            result = self.supabase.table("profiles").select(
                "email"
            ).eq("id", user_id).single().execute()

            if result.data:
                return result.data.get("email")
        except Exception:
            pass

        return None

    def _get_project_url(self, job_id: int) -> str:
        """Get URL for project page."""
        return f"{self.app_base_url}/research/projects/{job_id}"

    def _get_report_url(self, job_id: int) -> str:
        """Get URL for report page."""
        return f"{self.app_base_url}/research/reports/{job_id}"

    def _get_dashboard_url(self) -> str:
        """Get URL for user dashboard."""
        return f"{self.app_base_url}/research/dashboard"

    def _get_retry_url(self, job_id: int) -> str:
        """Get URL to retry research."""
        return f"{self.app_base_url}/research/projects/{job_id}/retry"

    def _estimate_completion_time(self, total_tasks: int) -> str:
        """Estimate completion time based on task count."""
        # Rough estimate: 30 seconds per retrieval, 1 min per synthesis, 2 min for report
        estimated_minutes = (total_tasks * 0.5) + 5  # Base estimate

        if estimated_minutes < 5:
            return "A few minutes"
        elif estimated_minutes < 15:
            return "10-15 minutes"
        elif estimated_minutes < 30:
            return "15-30 minutes"
        elif estimated_minutes < 60:
            return "30-60 minutes"
        else:
            hours = estimated_minutes / 60
            return f"About {hours:.1f} hours"

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable form."""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"

    def _get_current_phase(self, progress: float) -> str:
        """Determine current phase based on progress."""
        if progress < 30:
            return "Data Retrieval"
        elif progress < 60:
            return "Analysis"
        elif progress < 85:
            return "Synthesis"
        else:
            return "Report Generation"

    def _extract_key_findings(self, job: Dict[str, Any]) -> List[str]:
        """Extract key findings from completed job."""
        findings = []

        # Try to get from result_data
        result_data = job.get("result_data", {})
        if isinstance(result_data, dict):
            if "key_findings" in result_data:
                findings = result_data["key_findings"][:5]
            elif "findings" in result_data:
                findings = result_data["findings"][:5]
            elif "summary" in result_data:
                # Use summary as a single finding
                findings = [result_data["summary"]]

        # Fallback to generic findings
        if not findings:
            findings = [
                "Research analysis completed successfully",
                f"Processed {job.get('completed_tasks', 0)} research tasks",
                "Full report is available for review"
            ]

        return findings

    def send_project_started(self, job_id: int) -> bool:
        """
        Send notification that research project has started.

        Args:
            job_id: Research job ID

        Returns:
            True if email sent successfully
        """
        job = self._get_job_details(job_id)
        if not job:
            logger.warning("Cannot send started notification - job not found", job_id=job_id)
            return False

        user_email = self._get_user_email(job.get("user_id", ""))
        if not user_email:
            logger.warning("No email for user", job_id=job_id, user_id=job.get("user_id"))
            return False

        # Get task count
        task_result = self.supabase.table("plan_tasks").select(
            "id", count="exact"
        ).eq("job_id", job_id).execute()
        estimated_tasks = task_result.count or job.get("estimated_tasks", 10)

        # Generate template
        template = ResearchEmailTemplates.get_project_started_template(
            query=job.get("query", "Research query"),
            estimated_tasks=estimated_tasks,
            research_type=job.get("research_type", "general"),
            project_url=self._get_project_url(job_id),
            estimated_time=self._estimate_completion_time(estimated_tasks)
        )

        # Send email
        success = self.email_service.send_email(
            to_emails=[user_email],
            subject=template["subject"],
            html_content=template["html"]
        )

        if success:
            logger.info("Sent project started notification", job_id=job_id, email=user_email)
            # Initialize milestone tracking
            self._sent_milestones[job_id] = set()
        else:
            logger.error("Failed to send project started notification", job_id=job_id)

        return success

    def send_progress_update(self, job_id: int, progress: float) -> bool:
        """
        Send progress milestone notification.

        Only sends at 25%, 50%, 75% milestones (once each).

        Args:
            job_id: Research job ID
            progress: Current progress percentage (0-100)

        Returns:
            True if email sent (or no notification needed)
        """
        # Determine milestone
        milestone = None
        for m in self.PROGRESS_MILESTONES:
            if progress >= m:
                milestone = m

        if milestone is None:
            return True  # No milestone reached yet

        # Check if already sent
        if job_id not in self._sent_milestones:
            self._sent_milestones[job_id] = set()

        if milestone in self._sent_milestones[job_id]:
            return True  # Already sent this milestone

        # Get job details
        job = self._get_job_details(job_id)
        if not job:
            return False

        user_email = self._get_user_email(job.get("user_id", ""))
        if not user_email:
            return False

        # Get task counts
        task_result = self.supabase.table("plan_tasks").select(
            "id, status"
        ).eq("job_id", job_id).execute()

        tasks = task_result.data or []
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "complete")

        # Generate template
        template = ResearchEmailTemplates.get_progress_update_template(
            query=job.get("query", "Research query"),
            progress_percent=progress,
            completed_tasks=completed_tasks,
            total_tasks=total_tasks,
            current_phase=self._get_current_phase(progress),
            project_url=self._get_project_url(job_id)
        )

        # Send email
        success = self.email_service.send_email(
            to_emails=[user_email],
            subject=template["subject"],
            html_content=template["html"]
        )

        if success:
            self._sent_milestones[job_id].add(milestone)
            logger.info(
                "Sent progress notification",
                job_id=job_id,
                milestone=milestone,
                email=user_email
            )

        return success

    def send_project_completed(
        self,
        job_id: int,
        report_url: Optional[str] = None
    ) -> bool:
        """
        Send notification that research project is complete.

        Args:
            job_id: Research job ID
            report_url: Optional custom report URL

        Returns:
            True if email sent successfully
        """
        job = self._get_job_details(job_id)
        if not job:
            logger.warning("Cannot send completed notification - job not found", job_id=job_id)
            return False

        user_email = self._get_user_email(job.get("user_id", ""))
        if not user_email:
            return False

        # Calculate duration
        started_at = job.get("started_at")
        completed_at = job.get("completed_at") or datetime.utcnow().isoformat()

        duration = "Unknown"
        if started_at:
            try:
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                duration = self._format_duration((end - start).total_seconds())
            except Exception:
                pass

        # Get artifact count
        artifact_result = self.supabase.table("research_artifacts").select(
            "id", count="exact"
        ).eq("job_id", job_id).execute()
        total_sources = artifact_result.count or 0

        # Generate template
        template = ResearchEmailTemplates.get_project_completed_template(
            query=job.get("query", "Research query"),
            key_findings=self._extract_key_findings(job),
            total_sources=total_sources,
            research_duration=duration,
            report_url=report_url or self._get_report_url(job_id),
            dashboard_url=self._get_dashboard_url()
        )

        # Send email
        success = self.email_service.send_email(
            to_emails=[user_email],
            subject=template["subject"],
            html_content=template["html"]
        )

        if success:
            logger.info("Sent project completed notification", job_id=job_id, email=user_email)
            # Clean up milestone tracking
            self._sent_milestones.pop(job_id, None)

        return success

    def send_project_failed(
        self,
        job_id: int,
        error: str,
        failed_task: Optional[str] = None
    ) -> bool:
        """
        Send notification that research project failed.

        Args:
            job_id: Research job ID
            error: Error message
            failed_task: Optional name of failed task

        Returns:
            True if email sent successfully
        """
        job = self._get_job_details(job_id)
        if not job:
            logger.warning("Cannot send failed notification - job not found", job_id=job_id)
            return False

        user_email = self._get_user_email(job.get("user_id", ""))
        if not user_email:
            return False

        # Sanitize error message for email
        sanitized_error = error[:500] if len(error) > 500 else error

        # Generate template
        template = ResearchEmailTemplates.get_project_failed_template(
            query=job.get("query", "Research query"),
            error_message=sanitized_error,
            failed_task=failed_task,
            support_url=self.support_url,
            retry_url=self._get_retry_url(job_id)
        )

        # Send email
        success = self.email_service.send_email(
            to_emails=[user_email],
            subject=template["subject"],
            html_content=template["html"]
        )

        if success:
            logger.info("Sent project failed notification", job_id=job_id, email=user_email)
            # Clean up milestone tracking
            self._sent_milestones.pop(job_id, None)

        return success


# ==============================================================================
# Service Factory
# ==============================================================================

_notification_service: Optional[ResearchNotificationService] = None


def get_research_notification_service() -> ResearchNotificationService:
    """Get singleton instance of ResearchNotificationService."""
    global _notification_service
    if _notification_service is None:
        _notification_service = ResearchNotificationService()
    return _notification_service


# ==============================================================================
# Celery Signal Handlers
# ==============================================================================

def register_research_notification_hooks():
    """
    Register notification hooks for research task events.

    Call this once during application startup to enable automatic notifications.
    """
    try:
        from celery.signals import task_success, task_failure
        from app.tasks.research_tasks import (
            initialize_research_job,
            execute_single_task,
            execute_research_tasks_concurrent
        )

        @task_success.connect(sender=initialize_research_job)
        def on_project_initialized(sender=None, result=None, **kwargs):
            """Send notification when project is initialized."""
            if result and isinstance(result, dict):
                job_id = result.get("job_id")
                if job_id:
                    service = get_research_notification_service()
                    service.send_project_started(job_id)

        @task_success.connect(sender=execute_research_tasks_concurrent)
        def on_concurrent_execution_complete(sender=None, result=None, **kwargs):
            """Send notification when concurrent execution completes."""
            if result and isinstance(result, dict):
                job_id = result.get("job_id")
                if job_id and result.get("status") == "complete":
                    service = get_research_notification_service()
                    service.send_project_completed(job_id)

        @task_failure.connect
        def on_research_task_failure(sender=None, task_id=None, exception=None, **kwargs):
            """Send notification when a research task fails."""
            # Only notify for research-related tasks
            if sender and hasattr(sender, 'name'):
                if 'research' in sender.name.lower():
                    args = kwargs.get('args', [])
                    if args:
                        job_id = args[0]
                        service = get_research_notification_service()
                        service.send_project_failed(
                            job_id=job_id,
                            error=str(exception),
                            failed_task=sender.name
                        )

        logger.info("Registered research notification hooks")

    except ImportError as e:
        logger.warning(f"Could not register notification hooks: {e}")
