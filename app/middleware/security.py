"""
Empire v7.3 - Security Headers Middleware
Task 41.1: JWT Authentication hardening with security headers

Implements HTTP security headers to prevent common web vulnerabilities:
- HSTS (HTTP Strict Transport Security)
- X-Content-Type-Options (prevent MIME sniffing)
- X-Frame-Options (prevent clickjacking)
- X-XSS-Protection (XSS attack prevention)
- Referrer-Policy (control referrer information)
- Permissions-Policy (disable unnecessary browser features)
- Content-Security-Policy (CSP)
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import os


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses

    Security headers help protect against:
    - Man-in-the-middle attacks (HSTS)
    - Clickjacking (X-Frame-Options)
    - MIME type confusion (X-Content-Type-Options)
    - XSS attacks (X-XSS-Protection, CSP)
    - Information leakage (Referrer-Policy)
    - Unwanted browser features (Permissions-Policy)
    """

    def __init__(self, app, enable_hsts: bool = True, enable_csp: bool = True):
        """
        Initialize security headers middleware

        Args:
            app: FastAPI application
            enable_hsts: Enable HSTS header (should be False in development)
            enable_csp: Enable Content-Security-Policy header
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.enable_csp = enable_csp

        # Get environment
        self.is_production = os.getenv("ENVIRONMENT", "development") == "production"

        # Only enable HSTS in production by default
        if self.enable_hsts and not self.is_production:
            print("⚠️  HSTS disabled in development environment")
            self.enable_hsts = False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response

        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain

        Returns:
            Response with security headers added
        """
        # Process the request
        response = await call_next(request)

        # Strict Transport Security (HSTS)
        # Forces HTTPS for 1 year and includes all subdomains
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Prevent MIME type sniffing
        # Browsers must respect the Content-Type header
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking attacks
        # Don't allow this site to be embedded in iframes
        response.headers["X-Frame-Options"] = "DENY"

        # XSS Protection (legacy but still useful for older browsers)
        # Block page if XSS attack detected
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information sent to external sites
        # Only send origin for cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable unnecessary browser features
        # Prevent access to geolocation, microphone, camera
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
            "magnetometer=(), gyroscope=(), accelerometer=()"
        )

        # Content Security Policy (CSP)
        # Define allowed sources for content
        if self.enable_csp:
            # Restrictive CSP for API endpoints
            # Allow same origin for most content, block inline scripts
            csp_directives = [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",  # 'unsafe-inline' for FastAPI docs
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'"
            ]

            # Relax CSP for /docs and /redoc endpoints (FastAPI docs need inline scripts)
            if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
                csp_directives = [
                    "default-src 'self'",
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # FastAPI docs need eval
                    "style-src 'self' 'unsafe-inline'",
                    "img-src 'self' data: https:",
                    "font-src 'self' data:",
                    "connect-src 'self'"
                ]

            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Additional security headers
        # Remove server identification
        response.headers["Server"] = "Empire"

        # Cache control for sensitive data
        if "/api/" in request.url.path and request.url.path not in ["/api/health", "/health"]:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response


def get_security_headers_middleware(enable_hsts: bool = None, enable_csp: bool = True):
    """
    Factory function to create security headers middleware

    Args:
        enable_hsts: Enable HSTS header (defaults to True in production, False in dev)
        enable_csp: Enable Content-Security-Policy header

    Returns:
        SecurityHeadersMiddleware instance
    """
    # Auto-detect HSTS based on environment if not specified
    if enable_hsts is None:
        enable_hsts = os.getenv("ENVIRONMENT", "development") == "production"

    return lambda app: SecurityHeadersMiddleware(app, enable_hsts=enable_hsts, enable_csp=enable_csp)
