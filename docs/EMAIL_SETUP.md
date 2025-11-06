# Email Notifications Setup Guide

Empire v7.3 includes email notifications for task events and long-running task alerts. This guide explains how to configure email notifications.

## Overview

Email notifications are sent for:
- ✅ **Task Completed** - When a task finishes successfully
- ❌ **Task Failed** - When a task fails after all retries
- 🔄 **Task Retry** - When a task is retried (first retry only)
- ⏰ **Long-Running Task Alert** - When a task exceeds the threshold time

## Configuration Options

Empire supports two email providers:

1. **SMTP** - Use any SMTP server (Gmail, Outlook, custom server)
2. **SendGrid** - Use SendGrid's API for reliable delivery

## Option 1: SMTP Configuration

### Gmail Setup

1. **Enable 2-Factor Authentication** on your Gmail account

2. **Create an App Password**:
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Security → 2-Step Verification → App passwords
   - Select "Mail" and "Other (Custom name)"
   - Name it "Empire v7.3"
   - Copy the 16-character password

3. **Configure .env**:
   ```bash
   EMAIL_NOTIFICATIONS_ENABLED=true
   EMAIL_PROVIDER=smtp

   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-16-char-app-password
   SMTP_USE_TLS=true

   EMAIL_FROM=your-email@gmail.com
   EMAIL_FROM_NAME=Empire v7.3
   ```

### Outlook/Hotmail Setup

1. **Configure .env**:
   ```bash
   EMAIL_NOTIFICATIONS_ENABLED=true
   EMAIL_PROVIDER=smtp

   SMTP_HOST=smtp.office365.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@outlook.com
   SMTP_PASSWORD=your-password
   SMTP_USE_TLS=true

   EMAIL_FROM=your-email@outlook.com
   EMAIL_FROM_NAME=Empire v7.3
   ```

### Custom SMTP Server

```bash
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_PROVIDER=smtp

SMTP_HOST=smtp.your-domain.com
SMTP_PORT=587  # or 465 for SSL
SMTP_USERNAME=noreply@your-domain.com
SMTP_PASSWORD=your-smtp-password
SMTP_USE_TLS=true  # or false for SSL on port 465

EMAIL_FROM=noreply@your-domain.com
EMAIL_FROM_NAME=Empire v7.3
```

## Option 2: SendGrid Configuration

SendGrid is recommended for production deployments due to higher reliability and deliverability.

### Setup Steps

1. **Create SendGrid Account**: Sign up at [SendGrid](https://sendgrid.com/)

2. **Create API Key**:
   - Dashboard → Settings → API Keys
   - Create API Key with "Mail Send" permission
   - Copy the API key (starts with `SG.`)

3. **Verify Sender Identity**:
   - Dashboard → Settings → Sender Authentication
   - Verify a single sender email address

4. **Install SendGrid Python Library**:
   ```bash
   pip install sendgrid
   ```

5. **Configure .env**:
   ```bash
   EMAIL_NOTIFICATIONS_ENABLED=true
   EMAIL_PROVIDER=sendgrid

   SENDGRID_API_KEY=SG.your-api-key-here

   EMAIL_FROM=verified-sender@your-domain.com
   EMAIL_FROM_NAME=Empire v7.3
   ```

## Long-Running Task Alerts

Configure the threshold for long-running task alerts:

```bash
# Time in seconds before sending long-running alert (default: 300 = 5 minutes)
LONG_RUNNING_TASK_THRESHOLD=300
```

Example thresholds:
- `60` - 1 minute
- `180` - 3 minutes
- `300` - 5 minutes (default)
- `600` - 10 minutes
- `1800` - 30 minutes

## Testing Email Configuration

Create a test script `test_email.py`:

```python
import os
from dotenv import load_dotenv
from app.services.email_service import get_email_service

load_dotenv()

# Initialize email service
email_service = get_email_service()

if not email_service.enabled:
    print("❌ Email notifications are disabled in .env")
    print("Set EMAIL_NOTIFICATIONS_ENABLED=true")
    exit(1)

# Test email
success = email_service.send_email(
    to_emails=["your-test-email@example.com"],
    subject="🧪 Empire v7.3 - Test Email",
    html_content="<h1>Email is working!</h1><p>Your Empire email notifications are configured correctly.</p>"
)

if success:
    print("✅ Test email sent successfully!")
else:
    print("❌ Failed to send test email. Check logs for details.")
```

Run the test:
```bash
python3 test_email.py
```

## Email Templates

Email templates are located in `app/templates/email/`:

- `task_completed.html` - Success notification
- `task_failed.html` - Failure notification
- `task_retry.html` - Retry notification
- `task_long_running.html` - Long-running task alert

Templates use simple variable substitution with `{{variable_name}}` syntax.

## Troubleshooting

### Gmail "Less Secure Apps" Error

**Solution**: Use App Password (see Gmail Setup above). Never enable "Less secure app access" - it's deprecated and insecure.

### SendGrid "Sender Identity Not Verified"

**Solution**: Verify your sender email in SendGrid dashboard before sending emails.

### SMTP Connection Timeout

**Possible causes**:
1. Firewall blocking port 587/465
2. Incorrect SMTP host/port
3. Corporate network restrictions

**Solution**: Try alternative ports or contact network admin.

### Emails Going to Spam

**Solutions**:
1. Use SendGrid instead of SMTP for better deliverability
2. Set up SPF/DKIM records for your domain
3. Avoid spam trigger words in subject lines
4. Send from verified domain email

### "Authentication Failed" Error

**Possible causes**:
1. Incorrect username/password
2. Account security blocks (Gmail)
3. 2FA not configured properly

**Solution**: Double-check credentials, enable 2FA, use App Password.

## Security Best Practices

1. **Never commit .env file** - It's in `.gitignore` by default
2. **Use App Passwords** - Don't use actual account passwords
3. **Rotate credentials** - Change API keys/passwords periodically
4. **Limit email recipients** - Only send to necessary users
5. **Monitor sending volume** - Avoid hitting rate limits

## Rate Limits

### Gmail SMTP
- 500 emails/day for free accounts
- 2,000 emails/day for Google Workspace

### SendGrid
- 100 emails/day (free tier)
- 40,000-100,000+/day (paid tiers)

## Production Recommendations

For production deployments:

1. ✅ **Use SendGrid** - Better deliverability and monitoring
2. ✅ **Set up domain authentication** - SPF, DKIM, DMARC records
3. ✅ **Monitor email quotas** - Track sending volume
4. ✅ **Configure retry logic** - Email service has built-in retries
5. ✅ **Test email templates** - Verify rendering in different clients
6. ✅ **Set appropriate thresholds** - Adjust long-running alerts per task type

## Integration with Celery Tasks

Add email notifications to your Celery tasks:

```python
from app.services.notification_dispatcher import get_notification_dispatcher

dispatcher = get_notification_dispatcher()

@celery_app.task(bind=True)
def my_task(self, user_email: str):
    # Notify task started
    dispatcher.notify_task_started(
        task_id=self.request.id,
        task_type="my_task",
        filename="example.pdf",
        user_emails=[user_email]  # Enable email notifications
    )

    # Do work...

    # Notify task completed
    dispatcher.notify_task_completed(
        task_id=self.request.id,
        task_type="my_task",
        filename="example.pdf",
        user_emails=[user_email],
        result={"status": "success"}
    )
```

## Support

For issues or questions:
1. Check logs: `tail -f logs/empire.log`
2. Verify environment variables are loaded
3. Test with simple script first
4. Review email provider documentation

## References

- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [SendGrid Documentation](https://docs.sendgrid.com/)
- [SMTP Port Reference](https://www.mailgun.com/blog/which-smtp-port-understanding-ports-25-465-587/)
