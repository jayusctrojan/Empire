"""
Empire v7.3 - Security Event Logging Service
Task 67: File type validation and security scanning

Features:
- Structured security event logging
- Event categorization by severity
- Integration with Supabase audit_logs table
- Rate limiting for log volume
- Sensitive data redaction
"""

import logging
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
from functools import lru_cache
import asyncio
import os

import structlog

# Use structlog if available, fallback to standard logging
try:
    logger = structlog.get_logger(__name__)
except Exception:
    logger = logging.getLogger(__name__)


# ============================================================================
# Security Event Types
# ============================================================================

class SecurityEventType(Enum):
    """Types of security events to log"""
    # File Validation Events
    FILE_BLOCKED_EXTENSION = "file_blocked_extension"
    FILE_BLOCKED_MIME = "file_blocked_mime"
    FILE_BLOCKED_MAGIC_BYTES = "file_blocked_magic_bytes"
    FILE_VALIDATION_FAILED = "file_validation_failed"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"

    # URL Validation Events
    URL_BLOCKED_SCHEME = "url_blocked_scheme"
    URL_BLOCKED_HOST = "url_blocked_host"
    URL_SSRF_ATTEMPT = "url_ssrf_attempt"
    URL_SUSPICIOUS_PATTERN = "url_suspicious_pattern"
    URL_VALIDATION_FAILED = "url_validation_failed"

    # Virus Scanning Events
    VIRUS_DETECTED = "virus_detected"
    VIRUS_SCAN_FAILED = "virus_scan_failed"
    VIRUS_SCAN_CLEAN = "virus_scan_clean"

    # Authentication Events
    AUTH_FAILED = "auth_failed"
    AUTH_SUCCESS = "auth_success"
    AUTH_TOKEN_EXPIRED = "auth_token_expired"
    AUTH_TOKEN_INVALID = "auth_token_invalid"

    # Access Control Events
    ACCESS_DENIED = "access_denied"
    PERMISSION_ESCALATION = "permission_escalation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    # Rate Limiting Events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    RATE_LIMIT_WARNING = "rate_limit_warning"

    # Data Security Events
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    DATA_EXPORT = "data_export"
    BULK_DOWNLOAD = "bulk_download"

    # System Events
    CONFIG_CHANGE = "config_change"
    SYSTEM_ERROR = "system_error"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class SecuritySeverity(Enum):
    """Severity levels for security events"""
    DEBUG = "debug"       # Informational, no action needed
    INFO = "info"         # Normal security events
    WARNING = "warning"   # Potentially suspicious, monitor
    HIGH = "high"         # Security concern, investigate
    CRITICAL = "critical" # Security incident, immediate action


# ============================================================================
# Security Event Data Class
# ============================================================================

@dataclass
class SecurityEvent:
    """Structured security event for logging"""
    event_type: SecurityEventType
    severity: SecuritySeverity
    message: str

    # Context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Event-specific data
    resource_type: Optional[str] = None  # file, url, document, etc.
    resource_id: Optional[str] = None
    action: Optional[str] = None         # upload, download, delete, etc.

    # Additional details
    details: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    # Timestamps
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "details": self.details,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


# ============================================================================
# Security Logger Service
# ============================================================================

class SecurityLogger:
    """
    Security event logging service with structured logging and database persistence.

    Features:
    - Structured event logging
    - Severity-based filtering
    - Rate limiting to prevent log flooding
    - Sensitive data redaction
    - Async database persistence
    """

    # Fields that should be redacted
    SENSITIVE_FIELDS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
        'authorization', 'auth', 'credentials', 'credit_card', 'ssn', 'private_key',
        'access_token', 'refresh_token', 'session_token', 'bearer',
    }

    # Maximum events per minute per user (rate limiting)
    MAX_EVENTS_PER_MINUTE = 100

    def __init__(
        self,
        supabase_client=None,
        min_severity: SecuritySeverity = SecuritySeverity.INFO,
        enable_db_logging: bool = True,
        enable_console_logging: bool = True,
    ):
        """
        Initialize security logger.

        Args:
            supabase_client: Supabase client for database logging
            min_severity: Minimum severity to log
            enable_db_logging: Enable database persistence
            enable_console_logging: Enable console output
        """
        self.supabase = supabase_client
        self.min_severity = min_severity
        self.enable_db_logging = enable_db_logging
        self.enable_console_logging = enable_console_logging

        # Rate limiting state
        self._event_counts: Dict[str, int] = {}
        self._last_reset: datetime = datetime.now(timezone.utc)

        # Severity ordering for filtering
        self._severity_order = {
            SecuritySeverity.DEBUG: 0,
            SecuritySeverity.INFO: 1,
            SecuritySeverity.WARNING: 2,
            SecuritySeverity.HIGH: 3,
            SecuritySeverity.CRITICAL: 4,
        }

        logger.info(
            "Security logger initialized",
            min_severity=min_severity.value,
            db_logging=enable_db_logging
        )

    async def log_event(self, event: SecurityEvent) -> bool:
        """
        Log a security event.

        Args:
            event: SecurityEvent to log

        Returns:
            True if event was logged, False if filtered/rate-limited
        """
        # Check severity filter
        if self._severity_order[event.severity] < self._severity_order[self.min_severity]:
            return False

        # Check rate limiting
        if not self._check_rate_limit(event.user_id or "anonymous"):
            logger.warning(
                "Security event rate limit exceeded",
                user_id=event.user_id,
                event_type=event.event_type.value
            )
            return False

        # Redact sensitive data
        event = self._redact_sensitive_data(event)

        # Console logging
        if self.enable_console_logging:
            self._log_to_console(event)

        # Database logging
        if self.enable_db_logging and self.supabase:
            await self._log_to_database(event)

        return True

    def log_event_sync(self, event: SecurityEvent) -> bool:
        """
        Synchronous version of log_event for non-async contexts.

        Args:
            event: SecurityEvent to log

        Returns:
            True if event was logged
        """
        # Check severity filter
        if self._severity_order[event.severity] < self._severity_order[self.min_severity]:
            return False

        # Check rate limiting
        if not self._check_rate_limit(event.user_id or "anonymous"):
            return False

        # Redact sensitive data
        event = self._redact_sensitive_data(event)

        # Console logging only (no async DB)
        if self.enable_console_logging:
            self._log_to_console(event)

        return True

    # =========================================================================
    # Convenience Methods for Common Events
    # =========================================================================

    async def log_file_blocked(
        self,
        filename: str,
        reason: str,
        extension: Optional[str] = None,
        mime_type: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a blocked file upload"""
        event_type = SecurityEventType.FILE_BLOCKED_EXTENSION
        if "mime" in reason.lower():
            event_type = SecurityEventType.FILE_BLOCKED_MIME
        elif "magic" in reason.lower() or "header" in reason.lower():
            event_type = SecurityEventType.FILE_BLOCKED_MAGIC_BYTES

        event = SecurityEvent(
            event_type=event_type,
            severity=SecuritySeverity.WARNING,
            message=f"File blocked: {reason}",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="file",
            resource_id=self._hash_filename(filename),
            action="upload",
            details={
                "filename": filename,
                "extension": extension,
                "mime_type": mime_type,
                "reason": reason,
            }
        )
        await self.log_event(event)

    async def log_url_blocked(
        self,
        url: str,
        reason: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a blocked URL"""
        # Determine event type
        if "ssrf" in reason.lower() or "private" in reason.lower():
            event_type = SecurityEventType.URL_SSRF_ATTEMPT
        elif "scheme" in reason.lower():
            event_type = SecurityEventType.URL_BLOCKED_SCHEME
        elif "host" in reason.lower():
            event_type = SecurityEventType.URL_BLOCKED_HOST
        else:
            event_type = SecurityEventType.URL_VALIDATION_FAILED

        event = SecurityEvent(
            event_type=event_type,
            severity=SecuritySeverity.WARNING,
            message=f"URL blocked: {reason}",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="url",
            resource_id=self._hash_url(url),
            action="access",
            details={
                "url_preview": url[:100] + ("..." if len(url) > 100 else ""),
                "reason": reason,
            }
        )
        await self.log_event(event)

    async def log_virus_detected(
        self,
        filename: str,
        virus_names: List[str],
        scan_result: Dict[str, Any],
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a virus detection"""
        event = SecurityEvent(
            event_type=SecurityEventType.VIRUS_DETECTED,
            severity=SecuritySeverity.CRITICAL,
            message=f"Virus detected in file: {', '.join(virus_names[:3])}",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="file",
            resource_id=self._hash_filename(filename),
            action="scan",
            details={
                "filename": filename,
                "virus_names": virus_names[:10],  # Limit to first 10
                "detection_count": len(virus_names),
                "scan_summary": {
                    k: v for k, v in scan_result.items()
                    if k in ['positives', 'total', 'scan_date', 'permalink']
                } if scan_result else None,
            }
        )
        await self.log_event(event)

    async def log_rate_limit_exceeded(
        self,
        endpoint: str,
        limit: int,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log rate limit exceeded"""
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SecuritySeverity.WARNING,
            message=f"Rate limit exceeded on {endpoint}",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="endpoint",
            resource_id=endpoint,
            action="request",
            details={
                "endpoint": endpoint,
                "limit": limit,
            }
        )
        await self.log_event(event)

    async def log_auth_failure(
        self,
        reason: str,
        username: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log authentication failure"""
        event = SecurityEvent(
            event_type=SecurityEventType.AUTH_FAILED,
            severity=SecuritySeverity.WARNING,
            message=f"Authentication failed: {reason}",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type="auth",
            action="login",
            details={
                "reason": reason,
                "username_hash": self._hash_string(username) if username else None,
            }
        )
        await self.log_event(event)

    async def log_access_denied(
        self,
        resource: str,
        action: str,
        reason: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log access denied"""
        event = SecurityEvent(
            event_type=SecurityEventType.ACCESS_DENIED,
            severity=SecuritySeverity.WARNING,
            message=f"Access denied to {resource}: {reason}",
            user_id=user_id,
            ip_address=ip_address,
            resource_type=resource,
            action=action,
            details={
                "reason": reason,
            }
        )
        await self.log_event(event)

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit"""
        now = datetime.now(timezone.utc)

        # Reset counts every minute
        if (now - self._last_reset).total_seconds() > 60:
            self._event_counts.clear()
            self._last_reset = now

        # Increment count
        current = self._event_counts.get(user_id, 0)
        if current >= self.MAX_EVENTS_PER_MINUTE:
            return False

        self._event_counts[user_id] = current + 1
        return True

    def _redact_sensitive_data(self, event: SecurityEvent) -> SecurityEvent:
        """Redact sensitive fields from event details"""
        if not event.details:
            return event

        redacted_details = {}
        for key, value in event.details.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                redacted_details[key] = "[REDACTED]"
            elif isinstance(value, dict):
                # Recursively redact nested dicts
                redacted_details[key] = self._redact_dict(value)
            else:
                redacted_details[key] = value

        event.details = redacted_details
        return event

    def _redact_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive fields in a dictionary"""
        redacted = {}
        for key, value in d.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            else:
                redacted[key] = value
        return redacted

    def _log_to_console(self, event: SecurityEvent) -> None:
        """Log event to console with appropriate level"""
        log_data = event.to_dict()

        # Map severity to log level
        if event.severity == SecuritySeverity.CRITICAL:
            logger.critical("SECURITY EVENT", **log_data)
        elif event.severity == SecuritySeverity.HIGH:
            logger.error("SECURITY EVENT", **log_data)
        elif event.severity == SecuritySeverity.WARNING:
            logger.warning("SECURITY EVENT", **log_data)
        elif event.severity == SecuritySeverity.INFO:
            logger.info("SECURITY EVENT", **log_data)
        else:
            logger.debug("SECURITY EVENT", **log_data)

    async def _log_to_database(self, event: SecurityEvent) -> None:
        """Persist event to Supabase audit_logs table"""
        try:
            if not self.supabase:
                return

            # Map to audit_logs schema
            log_entry = {
                "event_type": event.event_type.value,
                "severity": event.severity.value,
                "user_id": event.user_id,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "action": event.action,
                "details": json.dumps(event.details) if event.details else None,
                "metadata": json.dumps(event.metadata) if event.metadata else None,
                "timestamp": event.timestamp,
            }

            # Insert into audit_logs table
            result = self.supabase.table("audit_logs").insert(log_entry).execute()

            if not result.data:
                logger.warning("Failed to insert security event to database")

        except Exception as e:
            logger.error(f"Database logging error: {e}")

    def _hash_filename(self, filename: str) -> str:
        """Hash filename for logging (privacy)"""
        return hashlib.sha256(filename.encode()).hexdigest()[:16]

    def _hash_url(self, url: str) -> str:
        """Hash URL for logging (privacy)"""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _hash_string(self, s: str) -> str:
        """Hash any string for logging (privacy)"""
        return hashlib.sha256(s.encode()).hexdigest()[:16]


# ============================================================================
# Global Instance
# ============================================================================

_security_logger: Optional[SecurityLogger] = None


def get_security_logger(
    supabase_client=None,
    min_severity: SecuritySeverity = SecuritySeverity.INFO,
) -> SecurityLogger:
    """
    Get or create security logger singleton.

    Returns:
        SecurityLogger instance
    """
    global _security_logger

    if _security_logger is None:
        _security_logger = SecurityLogger(
            supabase_client=supabase_client,
            min_severity=min_severity,
        )

    return _security_logger


def init_security_logger(supabase_client=None) -> SecurityLogger:
    """
    Initialize security logger with Supabase client.

    Returns:
        SecurityLogger instance
    """
    global _security_logger
    _security_logger = SecurityLogger(supabase_client=supabase_client)
    return _security_logger
