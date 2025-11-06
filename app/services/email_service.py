"""
Empire v7.3 - Email Service
Send email notifications for long-running tasks
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service for sending notifications about long-running tasks

    Supports both SMTP and SendGrid for email delivery.
    Includes retry logic and HTML template rendering.
    """

    def __init__(self):
        """Initialize email service with configuration from environment"""
        # Email configuration
        self.enabled = os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "false").lower() == "true"
        self.provider = os.getenv("EMAIL_PROVIDER", "smtp")  # smtp or sendgrid

        # SMTP configuration
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

        # SendGrid configuration
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")

        # Sender configuration
        self.from_email = os.getenv("EMAIL_FROM", "noreply@empire.ai")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "Empire v7.3")

        # Template directory
        self.template_dir = Path(__file__).parent.parent / "templates" / "email"

        # Validation
        if self.enabled:
            if self.provider == "smtp" and not (self.smtp_username and self.smtp_password):
                logger.warning("Email enabled but SMTP credentials not configured")
                self.enabled = False
            elif self.provider == "sendgrid" and not self.sendgrid_api_key:
                logger.warning("Email enabled but SendGrid API key not configured")
                self.enabled = False

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        max_retries: int = 3
    ) -> bool:
        """
        Send email with retry logic

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject line
            html_content: HTML email body
            text_content: Plain text fallback (auto-generated if not provided)
            max_retries: Maximum number of retry attempts

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Email notifications disabled, skipping: {subject}")
            return False

        if not to_emails:
            logger.warning("No recipient emails provided")
            return False

        # Try sending with retries
        for attempt in range(max_retries):
            try:
                if self.provider == "smtp":
                    return self._send_via_smtp(to_emails, subject, html_content, text_content)
                elif self.provider == "sendgrid":
                    return self._send_via_sendgrid(to_emails, subject, html_content, text_content)
                else:
                    logger.error(f"Unknown email provider: {self.provider}")
                    return False

            except Exception as e:
                logger.error(f"Email send attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All email send attempts failed for: {subject}")
                    return False

        return False

    def _send_via_smtp(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email via SMTP

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body

        Returns:
            True if successful
        """
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{self.from_name} <{self.from_email}>"
        msg['To'] = ", ".join(to_emails)

        # Add plain text part (auto-strip HTML tags if not provided)
        if text_content is None:
            import re
            text_content = re.sub('<[^<]+?>', '', html_content)

        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')

        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.smtp_use_tls:
                server.starttls()

            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)

            server.sendmail(self.from_email, to_emails, msg.as_string())

        logger.info(f"Email sent via SMTP to {len(to_emails)} recipients: {subject}")
        return True

    def _send_via_sendgrid(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email via SendGrid API

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body

        Returns:
            True if successful
        """
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content
        except ImportError:
            logger.error("SendGrid library not installed. Install with: pip install sendgrid")
            return False

        # Auto-generate text content if not provided
        if text_content is None:
            import re
            text_content = re.sub('<[^<]+?>', '', html_content)

        # Create message
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=[To(email) for email in to_emails],
            subject=subject,
            plain_text_content=Content("text/plain", text_content),
            html_content=Content("text/html", html_content)
        )

        # Send via SendGrid
        sg = SendGridAPIClient(self.sendgrid_api_key)
        response = sg.send(message)

        if response.status_code in [200, 201, 202]:
            logger.info(f"Email sent via SendGrid to {len(to_emails)} recipients: {subject}")
            return True
        else:
            logger.error(f"SendGrid send failed with status {response.status_code}")
            return False

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render email template with context variables

        Args:
            template_name: Template filename (e.g., "task_completed.html")
            context: Template context variables

        Returns:
            Rendered HTML content
        """
        template_path = self.template_dir / template_name

        if not template_path.exists():
            logger.warning(f"Email template not found: {template_path}")
            return self._generate_fallback_template(context)

        try:
            with open(template_path, 'r') as f:
                template = f.read()

            # Simple template variable substitution
            for key, value in context.items():
                template = template.replace(f"{{{{{key}}}}}", str(value))

            return template

        except Exception as e:
            logger.error(f"Error rendering email template {template_name}: {e}")
            return self._generate_fallback_template(context)

    def _generate_fallback_template(self, context: Dict[str, Any]) -> str:
        """
        Generate simple fallback HTML template

        Args:
            context: Template context

        Returns:
            Basic HTML email
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #667eea; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f7fafc; }}
                .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Empire v7.3</h1>
                </div>
                <div class="content">
                    <h2>{context.get('title', 'Notification')}</h2>
                    <p>{context.get('message', 'Task notification from Empire')}</p>
                    <ul>
                        {''.join(f'<li><strong>{k}:</strong> {v}</li>' for k, v in context.items() if k not in ['title', 'message'])}
                    </ul>
                </div>
                <div class="footer">
                    <p>Empire v7.3 - AI File Processing System</p>
                    <p>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """

    def send_task_notification(
        self,
        to_emails: List[str],
        task_id: str,
        task_type: str,
        status: str,
        filename: Optional[str] = None,
        error: Optional[str] = None,
        duration: Optional[float] = None
    ) -> bool:
        """
        Send task notification email

        Args:
            to_emails: Recipient email addresses
            task_id: Celery task ID
            task_type: Type of task (document_processing, embedding, etc.)
            status: Task status (completed, failed, retry)
            filename: Optional filename being processed
            error: Optional error message
            duration: Optional task duration in seconds

        Returns:
            True if sent successfully
        """
        # Build email subject
        status_emoji = {
            "completed": "✅",
            "failed": "❌",
            "retry": "🔄",
            "processing": "⏳"
        }

        emoji = status_emoji.get(status, "📋")
        subject = f"{emoji} Empire Task {status.title()}"
        if filename:
            subject += f": {filename}"

        # Build template context
        context = {
            "title": f"Task {status.title()}",
            "message": f"Your {task_type} task has {status}",
            "task_id": task_id,
            "task_type": task_type,
            "status": status,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        }

        if filename:
            context["filename"] = filename

        if error:
            context["error"] = error

        if duration:
            context["duration"] = f"{duration:.2f} seconds"

        # Render template
        html_content = self.render_template(f"task_{status}.html", context)

        # Send email
        return self.send_email(
            to_emails=to_emails,
            subject=subject,
            html_content=html_content
        )

    def send_long_running_task_alert(
        self,
        to_emails: List[str],
        task_id: str,
        task_type: str,
        filename: Optional[str] = None,
        elapsed_time: float = 0,
        estimated_remaining: Optional[float] = None
    ) -> bool:
        """
        Send alert for long-running task

        Args:
            to_emails: Recipient email addresses
            task_id: Celery task ID
            task_type: Type of task
            filename: Optional filename
            elapsed_time: Time elapsed in seconds
            estimated_remaining: Optional estimated time remaining in seconds

        Returns:
            True if sent successfully
        """
        subject = f"⏰ Long-Running Task Alert"
        if filename:
            subject += f": {filename}"

        context = {
            "title": "Long-Running Task Alert",
            "message": f"Your {task_type} task is taking longer than expected",
            "task_id": task_id,
            "task_type": task_type,
            "filename": filename or "N/A",
            "elapsed_time": f"{elapsed_time:.0f} seconds ({elapsed_time/60:.1f} minutes)",
            "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        }

        if estimated_remaining:
            context["estimated_remaining"] = f"{estimated_remaining:.0f} seconds ({estimated_remaining/60:.1f} minutes)"

        html_content = self.render_template("task_long_running.html", context)

        return self.send_email(
            to_emails=to_emails,
            subject=subject,
            html_content=html_content
        )


# Global singleton instance
_email_service = None


def get_email_service() -> EmailService:
    """
    Get singleton instance of EmailService

    Returns:
        EmailService instance
    """
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
