# OWASP ZAP Dynamic Security Scan Guide

**Task 8.2**: Dynamic Application Security Testing (DAST)

## Overview

OWASP ZAP (Zed Attack Proxy) is the world's most widely used web application security scanner. This guide documents how to run a dynamic security scan against the Empire v7.3 API.

## Prerequisites

1. **OWASP ZAP Installation**:
   ```bash
   # macOS (Homebrew)
   brew install --cask owasp-zap

   # Docker
   docker pull ghcr.io/zaproxy/zaproxy:stable
   ```

2. **API Access**:
   - Production API: `https://jb-empire-api.onrender.com`
   - Local Development: `http://localhost:8000`

3. **Authentication Token**: Clerk JWT for authenticated endpoint scanning

## Scan Types

### 1. Baseline Scan (Quick - ~5 minutes)
Passive scan that doesn't actively attack the application.

```bash
# Docker command
docker run -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
  -t https://jb-empire-api.onrender.com \
  -r zap_baseline_report.html \
  -I
```

### 2. API Scan (Recommended - ~15 minutes)
Targeted scan for REST APIs using OpenAPI specification.

```bash
# First, export OpenAPI spec
curl https://jb-empire-api.onrender.com/openapi.json > openapi.json

# Run API scan
docker run -v $(pwd):/zap/wrk:rw -t ghcr.io/zaproxy/zaproxy:stable zap-api-scan.py \
  -t openapi.json \
  -f openapi \
  -r zap_api_report.html \
  -J zap_api_report.json
```

### 3. Full Active Scan (Comprehensive - ~60 minutes)
Active scanning with attack payloads. **Run only in staging/test environments.**

```bash
docker run -v $(pwd):/zap/wrk:rw -t ghcr.io/zaproxy/zaproxy:stable zap-full-scan.py \
  -t https://jb-empire-api.onrender.com \
  -r zap_full_report.html \
  -J zap_full_report.json
```

## Authenticated Scanning

For endpoints requiring authentication, create a ZAP context with Clerk JWT:

### Option 1: Environment Variable
```bash
docker run -e ZAP_AUTH_HEADER="Authorization: Bearer $CLERK_JWT" \
  -t ghcr.io/zaproxy/zaproxy:stable zap-api-scan.py \
  -t openapi.json \
  -f openapi \
  -r zap_authenticated_report.html
```

### Option 2: Custom Script
Create `zap_auth.py`:
```python
# Script to add Clerk JWT to all requests
def zap_started(zap, target):
    zap.replacer.add_rule(
        description="Add Clerk JWT",
        enabled=True,
        matchtype="REQ_HEADER",
        matchregex=False,
        matchstring="Authorization",
        replacement="Bearer YOUR_JWT_HERE",
        initiators=""
    )
```

## Endpoints to Scan

### High Priority (Authentication/Authorization)
- `POST /api/query/auto` - Query processing
- `POST /api/documents/upload` - File uploads
- `POST /api/rbac/roles` - Role management
- `GET /api/users/me` - User data access
- `POST /api/crewai/execute` - CrewAI execution

### Medium Priority (Data Access)
- `GET /api/documents` - Document listing
- `GET /api/sessions` - Session management
- `POST /api/audit/query` - Audit log access

### Low Priority (Public/Health)
- `GET /health` - Health check
- `GET /docs` - API documentation
- `GET /monitoring/metrics` - Prometheus metrics

## Expected Findings & Mitigations

### Already Mitigated in Task 41

| Finding | Mitigation | Status |
|---------|------------|--------|
| Missing Security Headers | SecurityHeadersMiddleware | ✅ Done |
| Rate Limiting | slowapi + Redis | ✅ Done |
| CORS Misconfiguration | Hardened CORS policy | ✅ Done |
| SQL Injection | Parameterized queries | ✅ Done |
| Input Validation | Pydantic validators | ✅ Done |

### Common ZAP Findings to Review

1. **Cross-Site Scripting (XSS)**: Should be mitigated by CSP headers
2. **SQL Injection**: Should be mitigated by ORM/parameterized queries
3. **CSRF**: Should be mitigated by SameSite cookies
4. **Information Disclosure**: Review error messages
5. **Authentication Bypass**: Review Clerk JWT validation

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Security Scan
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  zap_scan:
    runs-on: ubuntu-latest
    steps:
      - name: OWASP ZAP Scan
        uses: zaproxy/action-api-scan@v0.7.0
        with:
          target: 'https://jb-empire-api.onrender.com/openapi.json'
          format: openapi

      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: zap-report
          path: report_html.html
```

## Running the Scan

### Recommended Approach

1. **Development Phase**: Run baseline scan locally
   ```bash
   uvicorn app.main:app --port 8000 &
   docker run -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
     -t http://host.docker.internal:8000 -I
   ```

2. **Pre-Production**: Run API scan in staging
   ```bash
   docker run -v $(pwd):/zap/wrk:rw -t ghcr.io/zaproxy/zaproxy:stable zap-api-scan.py \
     -t https://staging-api.example.com/openapi.json -f openapi
   ```

3. **Production**: Weekly scheduled baseline scans only
   - Do NOT run active scans against production
   - Use CI/CD for automated baseline scanning

## Interpreting Results

### Risk Levels
- **High**: Immediate remediation required
- **Medium**: Remediate within sprint
- **Low**: Backlog for future sprint
- **Informational**: Document and monitor

### False Positive Handling
Common false positives for Empire:
- `X-Content-Type-Options` - Already set in SecurityHeadersMiddleware
- `Strict-Transport-Security` - Set in production only
- `Content-Security-Policy` - Configured for API responses

## Report Location

After running scans, reports are saved to:
```
reports/
├── zap_baseline_report.html
├── zap_api_report.html
├── zap_api_report.json
└── zap_full_report.html
```

## Manual Testing Checklist

While ZAP automates most tests, manually verify:

- [ ] JWT token expiration is enforced
- [ ] Invalid JWT tokens are rejected
- [ ] Rate limiting triggers at configured thresholds
- [ ] CORS blocks unauthorized origins
- [ ] File upload accepts only allowed types
- [ ] User can only access their own data (RLS)
- [ ] Admin endpoints require admin role

## Contact

For questions about security scanning:
- Security Report: `docs/SECURITY_AUDIT_REPORT.md`
- Rate Limiting: `app/middleware/rate_limit.py`
- Security Headers: `app/middleware/security.py`

---

**Last Updated**: 2025-11-26
**Task**: 8.2 - OWASP ZAP Dynamic Security Scan
