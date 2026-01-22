"""
Security Validators - Task 41.4
Custom validators for preventing common security vulnerabilities
"""

import re
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
import structlog

logger = structlog.get_logger(__name__)


class SecurityValidationError(Exception):
    """Custom exception for security validation failures"""
    pass


# Dangerous patterns for path traversal
PATH_TRAVERSAL_PATTERNS = [
    r'\.\.',  # Parent directory (..)
    r'\./',   # Current directory (./)
    r'~/',    # Home directory
    r'\x00',  # Null byte
    r'%00',   # URL-encoded null byte
    r'%2e%2e', # URL-encoded ..
    r'%252e',  # Double URL-encoded .
    r'\\',    # Backslash (Windows path separator)
]

# SQL injection patterns (basic detection)
SQL_INJECTION_PATTERNS = [
    r'(\bunion\b.*\bselect\b)',
    r'(\bselect\b.*\bfrom\b)',
    r'(\binsert\b.*\binto\b)',
    r'(\bupdate\b.*\bset\b)',
    r'(\bdelete\b.*\bfrom\b)',
    r'(\bdrop\b.*\btable\b)',
    r'(;.*\b(select|insert|update|delete|drop)\b)',
    r'(--|\#|/\*)',  # SQL comments
    r'(\bor\b.*=.*)',  # OR 1=1 patterns
    r'(\band\b.*=.*)',
]

# XSS patterns
XSS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'on\w+\s*=',  # Event handlers (onclick, onload, etc.)
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',
    r'<applet[^>]*>',
    r'<meta[^>]*>',
    r'<link[^>]*>',
    r'<img[^>]*onerror',
    r'<svg[^>]*onload',
    r'eval\s*\(',
    r'expression\s*\(',
]


def validate_path_traversal(path: str, field_name: str = "path") -> str:
    """
    Validate that a path does not contain path traversal attempts

    Args:
        path: Path string to validate
        field_name: Name of the field (for error messages)

    Returns:
        The original path if valid

    Raises:
        HTTPException: If path traversal attempt detected
    """
    if not path:
        return path

    # Check for dangerous patterns
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, path, re.IGNORECASE):
            logger.warning(
                "path_traversal_attempt",
                field=field_name,
                path=path,
                pattern=pattern
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid path",
                    "field": field_name,
                    "message": f"Path contains forbidden pattern: {pattern}"
                }
            )

    # Check for null bytes
    if '\x00' in path or '%00' in path:
        logger.warning(
            "null_byte_detected",
            field=field_name,
            path=path
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid path",
                "field": field_name,
                "message": "Path contains null byte"
            }
        )

    return path


def validate_sql_injection(value: str, field_name: str = "value") -> str:
    """
    Basic SQL injection pattern detection

    Note: This is defense in depth. Always use parameterized queries as primary defense.

    Args:
        value: String to validate
        field_name: Name of the field (for error messages)

    Returns:
        The original value if no patterns detected

    Raises:
        HTTPException: If SQL injection pattern detected
    """
    if not value:
        return value

    # Check for SQL injection patterns
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(
                "sql_injection_attempt",
                field=field_name,
                value=value[:100],  # Log first 100 chars only
                pattern=pattern
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid input",
                    "field": field_name,
                    "message": "Input contains forbidden SQL patterns"
                }
            )

    return value


def validate_xss(value: str, field_name: str = "value", strict: bool = True) -> str:
    """
    Validate that a string does not contain XSS attack vectors

    Args:
        value: String to validate
        field_name: Name of the field (for error messages)
        strict: If True, raises exception. If False, sanitizes instead.

    Returns:
        The original value if valid (or sanitized value if strict=False)

    Raises:
        HTTPException: If XSS pattern detected and strict=True
    """
    if not value:
        return value

    # Check for XSS patterns
    for pattern in XSS_PATTERNS:
        match = re.search(pattern, value, re.IGNORECASE | re.DOTALL)
        if match:
            logger.warning(
                "xss_attempt",
                field=field_name,
                value=value[:100],  # Log first 100 chars only
                pattern=pattern,
                matched=match.group(0)[:50]
            )

            if strict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid input",
                        "field": field_name,
                        "message": "Input contains forbidden HTML/JavaScript patterns"
                    }
                )
            else:
                # Sanitize by removing the pattern
                value = re.sub(pattern, '', value, flags=re.IGNORECASE | re.DOTALL)

    return value


def sanitize_metadata(metadata: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """
    Sanitize metadata dictionary to prevent XSS in user-generated content

    Args:
        metadata: Metadata dictionary to sanitize
        strict: If True, raises exception on XSS. If False, sanitizes.

    Returns:
        Sanitized metadata dictionary

    Raises:
        HTTPException: If XSS detected and strict=True
    """
    if not metadata:
        return metadata

    sanitized = {}

    for key, value in metadata.items():
        # Validate key for path traversal and SQL injection
        key = validate_path_traversal(key, field_name=f"metadata.{key}")
        key = validate_sql_injection(key, field_name=f"metadata.{key}")

        # Sanitize value based on type
        if isinstance(value, str):
            # Check for XSS in string values
            value = validate_xss(value, field_name=f"metadata.{key}", strict=strict)
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            value = sanitize_metadata(value, strict=strict)
        elif isinstance(value, list):
            # Sanitize list items
            value = [
                validate_xss(item, field_name=f"metadata.{key}[]", strict=strict)
                if isinstance(item, str)
                else sanitize_metadata(item, strict=strict)
                if isinstance(item, dict)
                else item
                for item in value
            ]

        sanitized[key] = value

    return sanitized


def validate_filename(filename: str) -> str:
    """
    Validate filename to prevent path traversal and other attacks

    Args:
        filename: Filename to validate

    Returns:
        Validated filename

    Raises:
        HTTPException: If filename is invalid
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Filename cannot be empty"}
        )

    # Check for path traversal
    filename = validate_path_traversal(filename, field_name="filename")

    # Check for forbidden characters
    forbidden_chars = ['<', '>', ':', '"', '|', '?', '*']
    for char in forbidden_chars:
        if char in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid filename",
                    "message": f"Filename contains forbidden character: {char}"
                }
            )

    # Check filename length
    if len(filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid filename",
                "message": "Filename exceeds maximum length of 255 characters"
            }
        )

    return filename


def validate_email_domain(email: str, allowed_domains: Optional[list[str]] = None) -> bool:
    """
    Validate email domain against allowlist

    Args:
        email: Email address to validate
        allowed_domains: List of allowed domains (e.g., ["example.com", "company.com"])

    Returns:
        True if domain is allowed (or no allowlist provided)

    Raises:
        HTTPException: If email domain is not in allowlist
    """
    if not allowed_domains:
        return True

    domain = email.split('@')[-1].lower()

    if domain not in [d.lower() for d in allowed_domains]:
        logger.warning(
            "email_domain_not_allowed",
            email=email,
            domain=domain,
            allowed_domains=allowed_domains
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Email domain not allowed",
                "message": f"Email domain '{domain}' is not in the allowed list"
            }
        )

    return True
