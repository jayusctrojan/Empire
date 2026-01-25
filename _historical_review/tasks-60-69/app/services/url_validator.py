"""
Empire v7.3 - URL Validation and Sanitization Service
Task 67: File type validation and security scanning

Features:
- Scheme whitelisting (http, https only)
- SSRF protection (block private IPs, localhost, metadata endpoints)
- Domain validation and normalization
- URL structure validation
- Malicious pattern detection
"""

import re
import socket
import ipaddress
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional, Tuple, List, Set, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class URLRiskLevel(Enum):
    """Risk classification for URLs"""
    SAFE = "safe"
    MODERATE = "moderate"  # External URLs
    HIGH = "high"          # Unusual patterns
    BLOCKED = "blocked"    # Blocked for security


# Allowed URL schemes - ONLY these are permitted
ALLOWED_SCHEMES: Set[str] = {'http', 'https'}

# Blocked schemes - Explicitly dangerous
BLOCKED_SCHEMES: Set[str] = {
    'javascript',
    'vbscript',
    'data',
    'file',
    'ftp',
    'sftp',
    'ssh',
    'telnet',
    'ldap',
    'ldaps',
    'gopher',
    'dict',
    'jar',
    'netdoc',
}

# Private/internal IP ranges (SSRF protection)
PRIVATE_IP_RANGES: List[str] = [
    '10.0.0.0/8',       # Class A private
    '172.16.0.0/12',    # Class B private
    '192.168.0.0/16',   # Class C private
    '127.0.0.0/8',      # Loopback
    '169.254.0.0/16',   # Link-local
    '0.0.0.0/8',        # Current network
    '100.64.0.0/10',    # Carrier-grade NAT
    '192.0.0.0/24',     # IETF Protocol assignments
    '192.0.2.0/24',     # TEST-NET-1
    '198.51.100.0/24',  # TEST-NET-2
    '203.0.113.0/24',   # TEST-NET-3
    '224.0.0.0/4',      # Multicast
    '240.0.0.0/4',      # Reserved
    '255.255.255.255/32',  # Broadcast
]

# IPv6 private ranges
PRIVATE_IPV6_RANGES: List[str] = [
    '::1/128',          # Loopback
    'fc00::/7',         # Unique local
    'fe80::/10',        # Link-local
    'ff00::/8',         # Multicast
    '::ffff:0:0/96',    # IPv4-mapped
]

# Blocked hostnames (SSRF protection)
BLOCKED_HOSTNAMES: Set[str] = {
    'localhost',
    'localhost.localdomain',
    '127.0.0.1',
    '::1',
    '0.0.0.0',
    '[::1]',
    '[::ffff:127.0.0.1]',
}

# Cloud metadata endpoints (SSRF protection)
METADATA_HOSTNAMES: Set[str] = {
    '169.254.169.254',           # AWS, GCP, Azure
    'metadata.google.internal',   # GCP
    'metadata.gcp.internal',      # GCP
    'metadata',                   # Generic
    'instance-data',              # EC2 internal
}

# Suspicious TLDs often used in attacks
SUSPICIOUS_TLDS: Set[str] = {
    '.tk', '.ml', '.ga', '.cf', '.gq',  # Free domains often abused
    '.top', '.xyz', '.work', '.click',   # Common in spam/phishing
    '.zip', '.mov',  # New TLDs that can be confused with files
}

# Patterns that indicate potentially malicious URLs
SUSPICIOUS_PATTERNS: List[Tuple[str, str]] = [
    (r'@', 'URL contains @ symbol (potential credential injection)'),
    (r'\x00', 'URL contains null byte'),
    (r'%00', 'URL contains encoded null byte'),
    (r'[\x01-\x1f]', 'URL contains control characters'),
    (r'\\\\', 'URL contains backslashes'),
    (r'\.\./', 'URL contains directory traversal'),
    (r'%2e%2e%2f', 'URL contains encoded directory traversal'),
    (r'(?i)javascript:', 'URL contains javascript protocol'),
    (r'(?i)data:', 'URL contains data protocol'),
    (r'(?i)vbscript:', 'URL contains vbscript protocol'),
]

# Maximum URL length (prevents DoS with extremely long URLs)
MAX_URL_LENGTH = 8192

# Maximum domain length
MAX_DOMAIN_LENGTH = 253

# Maximum path depth
MAX_PATH_DEPTH = 20


# ============================================================================
# Validation Result
# ============================================================================

@dataclass
class URLValidationResult:
    """Result of URL validation"""
    is_valid: bool
    error_message: Optional[str] = None
    risk_level: URLRiskLevel = URLRiskLevel.SAFE
    sanitized_url: Optional[str] = None
    original_url: Optional[str] = None
    parsed_scheme: Optional[str] = None
    parsed_host: Optional[str] = None
    parsed_path: Optional[str] = None
    warnings: List[str] = None
    resolved_ip: Optional[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# ============================================================================
# URL Validator Service
# ============================================================================

class URLValidator:
    """
    URL validation and sanitization service with security focus.

    Features:
    - Scheme whitelisting (http/https only)
    - SSRF protection (blocks internal IPs)
    - Malicious pattern detection
    - URL normalization
    """

    def __init__(
        self,
        allow_private_ips: bool = False,
        allow_metadata_endpoints: bool = False,
        resolve_dns: bool = True,
        strict_mode: bool = True
    ):
        """
        Initialize URL validator.

        Args:
            allow_private_ips: If True, allow private/internal IP addresses
            allow_metadata_endpoints: If True, allow cloud metadata endpoints
            resolve_dns: If True, resolve DNS to check for private IPs
            strict_mode: If True, block URLs with warnings; if False, allow with warnings
        """
        self.allow_private_ips = allow_private_ips
        self.allow_metadata_endpoints = allow_metadata_endpoints
        self.resolve_dns = resolve_dns
        self.strict_mode = strict_mode

        # Compile regex patterns
        self._compiled_patterns = [
            (re.compile(pattern), message)
            for pattern, message in SUSPICIOUS_PATTERNS
        ]

        # Parse IP networks for fast lookup
        self._private_networks = [
            ipaddress.ip_network(net) for net in PRIVATE_IP_RANGES
        ]
        self._private_v6_networks = [
            ipaddress.ip_network(net) for net in PRIVATE_IPV6_RANGES
        ]

        logger.info(
            "URL validator initialized",
            extra={
                "allow_private_ips": allow_private_ips,
                "resolve_dns": resolve_dns,
                "strict_mode": strict_mode
            }
        )

    def validate_url(self, url: str) -> URLValidationResult:
        """
        Validate and sanitize a URL.

        Args:
            url: The URL to validate

        Returns:
            URLValidationResult with validation status and details
        """
        warnings: List[str] = []

        try:
            # ===== BASIC VALIDATION =====
            if not url or not isinstance(url, str):
                return URLValidationResult(
                    is_valid=False,
                    error_message="URL is empty or not a string",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=str(url) if url else None
                )

            # Trim whitespace
            url = url.strip()

            # Check length
            if len(url) > MAX_URL_LENGTH:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"URL exceeds maximum length ({MAX_URL_LENGTH} characters)",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url[:100] + "..."
                )

            # ===== SUSPICIOUS PATTERN CHECK =====
            pattern_issues = self._check_suspicious_patterns(url)
            if pattern_issues:
                if self.strict_mode:
                    return URLValidationResult(
                        is_valid=False,
                        error_message=f"URL contains suspicious pattern: {pattern_issues[0]}",
                        risk_level=URLRiskLevel.BLOCKED,
                        original_url=url
                    )
                else:
                    warnings.extend(pattern_issues)

            # ===== PARSE URL =====
            try:
                parsed = urlparse(url)
            except Exception as e:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"Invalid URL format: {str(e)}",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url
                )

            # ===== SCHEME VALIDATION =====
            scheme = parsed.scheme.lower()

            if not scheme:
                # No scheme - assume https
                url = f"https://{url}"
                parsed = urlparse(url)
                scheme = 'https'
                warnings.append("URL had no scheme, defaulted to https")

            if scheme in BLOCKED_SCHEMES:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"URL scheme '{scheme}' is blocked for security reasons",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url,
                    parsed_scheme=scheme
                )

            if scheme not in ALLOWED_SCHEMES:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"URL scheme '{scheme}' is not allowed (use http or https)",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url,
                    parsed_scheme=scheme
                )

            # ===== HOST VALIDATION =====
            host = parsed.hostname
            if not host:
                return URLValidationResult(
                    is_valid=False,
                    error_message="URL has no hostname",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url,
                    parsed_scheme=scheme
                )

            host_lower = host.lower()

            # Check hostname length
            if len(host) > MAX_DOMAIN_LENGTH:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"Hostname exceeds maximum length ({MAX_DOMAIN_LENGTH} characters)",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url,
                    parsed_host=host[:50] + "..."
                )

            # Check blocked hostnames
            if host_lower in BLOCKED_HOSTNAMES:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"Hostname '{host}' is blocked (localhost/internal)",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url,
                    parsed_host=host
                )

            # Check metadata endpoints
            if not self.allow_metadata_endpoints and host_lower in METADATA_HOSTNAMES:
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"Hostname '{host}' is a cloud metadata endpoint (SSRF protection)",
                    risk_level=URLRiskLevel.BLOCKED,
                    original_url=url,
                    parsed_host=host
                )

            # ===== IP ADDRESS CHECK =====
            resolved_ip = None

            # Check if host is an IP address
            is_ip, ip_obj = self._parse_ip_address(host)
            if is_ip and ip_obj:
                if not self.allow_private_ips and self._is_private_ip(ip_obj):
                    return URLValidationResult(
                        is_valid=False,
                        error_message=f"IP address '{host}' is a private/internal address (SSRF protection)",
                        risk_level=URLRiskLevel.BLOCKED,
                        original_url=url,
                        parsed_host=host,
                        resolved_ip=str(ip_obj)
                    )
                resolved_ip = str(ip_obj)

            # DNS resolution check (to catch DNS rebinding attacks)
            elif self.resolve_dns and not self.allow_private_ips:
                try:
                    resolved_ips = socket.getaddrinfo(host, None, socket.AF_UNSPEC)
                    for result in resolved_ips:
                        ip_str = result[4][0]
                        is_ip, ip_obj = self._parse_ip_address(ip_str)
                        if is_ip and ip_obj and self._is_private_ip(ip_obj):
                            return URLValidationResult(
                                is_valid=False,
                                error_message=f"Hostname '{host}' resolves to private IP '{ip_str}' (SSRF protection)",
                                risk_level=URLRiskLevel.BLOCKED,
                                original_url=url,
                                parsed_host=host,
                                resolved_ip=ip_str
                            )
                    if resolved_ips:
                        resolved_ip = resolved_ips[0][4][0]
                except socket.gaierror:
                    # DNS resolution failed - might be intentional for testing
                    warnings.append(f"Could not resolve hostname '{host}'")

            # ===== PATH VALIDATION =====
            path = parsed.path
            if path:
                # Check path depth
                path_parts = [p for p in path.split('/') if p]
                if len(path_parts) > MAX_PATH_DEPTH:
                    return URLValidationResult(
                        is_valid=False,
                        error_message=f"URL path is too deep ({len(path_parts)} levels, max {MAX_PATH_DEPTH})",
                        risk_level=URLRiskLevel.HIGH,
                        original_url=url,
                        parsed_path=path[:100] + "..."
                    )

            # ===== SUSPICIOUS TLD CHECK =====
            for tld in SUSPICIOUS_TLDS:
                if host_lower.endswith(tld):
                    warnings.append(f"URL uses suspicious TLD '{tld}'")
                    break

            # ===== SANITIZE AND NORMALIZE =====
            sanitized_url = self._sanitize_url(parsed)

            # ===== DETERMINE RISK LEVEL =====
            risk_level = URLRiskLevel.SAFE
            if warnings:
                risk_level = URLRiskLevel.MODERATE
            if resolved_ip:
                # External URL with resolved IP
                risk_level = URLRiskLevel.MODERATE

            logger.info(
                "URL validation passed",
                extra={
                    "original_url": url[:100],
                    "sanitized_url": sanitized_url[:100],
                    "host": host,
                    "risk_level": risk_level.value
                }
            )

            return URLValidationResult(
                is_valid=True,
                risk_level=risk_level,
                sanitized_url=sanitized_url,
                original_url=url,
                parsed_scheme=scheme,
                parsed_host=host,
                parsed_path=parsed.path,
                warnings=warnings,
                resolved_ip=resolved_ip
            )

        except Exception as e:
            logger.error(f"URL validation error: {e}", extra={"url": url[:100] if url else None})
            return URLValidationResult(
                is_valid=False,
                error_message=f"URL validation error: {str(e)}",
                risk_level=URLRiskLevel.BLOCKED,
                original_url=url[:100] if url else None
            )

    def validate_url_simple(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Simple validation returning tuple (backwards compatible).

        Args:
            url: The URL to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        result = self.validate_url(url)
        return result.is_valid, result.error_message

    def _check_suspicious_patterns(self, url: str) -> List[str]:
        """Check URL for suspicious patterns"""
        issues = []
        for pattern, message in self._compiled_patterns:
            if pattern.search(url):
                issues.append(message)
        return issues

    def _parse_ip_address(self, host: str) -> Tuple[bool, Optional[ipaddress.ip_address]]:
        """
        Try to parse host as IP address.

        Returns:
            tuple: (is_ip, ip_object or None)
        """
        # Remove IPv6 brackets if present
        if host.startswith('[') and host.endswith(']'):
            host = host[1:-1]

        try:
            ip = ipaddress.ip_address(host)
            return True, ip
        except ValueError:
            return False, None

    def _is_private_ip(self, ip: ipaddress.ip_address) -> bool:
        """Check if IP address is private/internal"""
        # Check IPv4
        if isinstance(ip, ipaddress.IPv4Address):
            for network in self._private_networks:
                if ip in network:
                    return True

        # Check IPv6
        elif isinstance(ip, ipaddress.IPv6Address):
            for network in self._private_v6_networks:
                if ip in network:
                    return True

            # Also check mapped IPv4
            if ip.ipv4_mapped:
                return self._is_private_ip(ip.ipv4_mapped)

        return False

    def _sanitize_url(self, parsed) -> str:
        """
        Sanitize and normalize a parsed URL.

        Args:
            parsed: urllib.parse.ParseResult

        Returns:
            Sanitized URL string
        """
        # Normalize scheme to lowercase
        scheme = parsed.scheme.lower()

        # Normalize host to lowercase
        netloc = parsed.netloc.lower()

        # Remove default ports
        if parsed.port:
            if (scheme == 'http' and parsed.port == 80) or \
               (scheme == 'https' and parsed.port == 443):
                # Remove default port from netloc
                if ':' in netloc:
                    netloc = netloc.rsplit(':', 1)[0]

        # Normalize path (remove trailing slashes except for root)
        path = parsed.path
        if path and path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        # Sort query parameters for consistency
        query = parsed.query
        if query:
            try:
                params = parse_qs(query, keep_blank_values=True)
                sorted_params = sorted(params.items())
                query = urlencode([(k, v[0] if len(v) == 1 else v) for k, v in sorted_params], doseq=True)
            except Exception:
                pass  # Keep original query if parsing fails

        # Reconstruct URL
        sanitized = urlunparse((
            scheme,
            netloc,
            path,
            '',  # params (deprecated)
            query,
            ''   # fragment (not relevant for server)
        ))

        return sanitized

    def is_youtube_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Check if URL is a valid YouTube video URL.

        Returns:
            tuple: (is_youtube, video_id or None)
        """
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return True, match.group(1)

        return False, None

    def get_allowed_schemes(self) -> List[str]:
        """Get list of allowed URL schemes"""
        return sorted(list(ALLOWED_SCHEMES))

    def get_blocked_schemes(self) -> List[str]:
        """Get list of blocked URL schemes"""
        return sorted(list(BLOCKED_SCHEMES))


# ============================================================================
# Global Instance
# ============================================================================

_url_validator = None


def get_url_validator(
    allow_private_ips: bool = False,
    resolve_dns: bool = True,
    strict_mode: bool = True
) -> URLValidator:
    """
    Get or create URL validator singleton.

    Returns:
        URLValidator instance
    """
    global _url_validator

    if _url_validator is None:
        _url_validator = URLValidator(
            allow_private_ips=allow_private_ips,
            resolve_dns=resolve_dns,
            strict_mode=strict_mode
        )

    return _url_validator
