# Quickstart: Production Readiness Testing

**Branch**: `009-production-readiness` | **Date**: 2025-01-15

## Overview

This guide provides quick tests to verify each production readiness improvement.

---

## Test 1: Environment Variable Validation (US1)

### Test: Missing Critical Variable

```bash
# Unset a critical variable and start the app
unset SUPABASE_URL
python -m uvicorn app.main:app --port 8000

# Expected: Exit code 1 with message:
# "Cannot start: Missing critical env vars: SUPABASE_URL"
```

### Test: Missing Recommended Variable

```bash
# Unset a recommended variable and start the app
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_KEY="xxx"
export REDIS_URL="redis://localhost:6379"
export ANTHROPIC_API_KEY="sk-xxx"
export ENVIRONMENT="development"
unset NEO4J_URI

python -m uvicorn app.main:app --port 8000

# Expected: Warning logged, app starts successfully
# Log: "Missing recommended env vars: NEO4J_URI - some features may be unavailable"
```

### Test: Empty String Variable

```bash
# Set a critical variable to empty string
export SUPABASE_URL=""
python -m uvicorn app.main:app --port 8000

# Expected: Treated as missing, exit code 1
# "Cannot start: Missing critical env vars: SUPABASE_URL"
```

---

## Test 2: CORS Production Hardening (US2)

### Test: Wildcard CORS in Production

```bash
# Set production with wildcard CORS
export ENVIRONMENT="production"
export CORS_ORIGINS="*"
python -m uvicorn app.main:app --port 8000

# Expected: Exit code 1
# "CORS_ORIGINS cannot be '*' in production"
```

### Test: Missing CORS in Production

```bash
# Set production without CORS
export ENVIRONMENT="production"
unset CORS_ORIGINS
python -m uvicorn app.main:app --port 8000

# Expected: Exit code 1
# "CORS_ORIGINS must be explicitly set in production"
```

### Test: Wildcard CORS in Development

```bash
# Set development without CORS (should default to *)
export ENVIRONMENT="development"
unset CORS_ORIGINS
python -m uvicorn app.main:app --port 8000

# Expected: Warning logged, app starts
# "CORS defaulting to '*' in development mode"
```

---

## Test 3: Sensitive Endpoint Rate Limiting (US3)

### Test: Login Rate Limit

```bash
# Send 6 login requests within 1 minute
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/users/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"test"}'
  echo ""
done

# Expected: First 5 return normal response
# 6th returns HTTP 429 with Retry-After header
```

### Test: Upload Rate Limit

```bash
# Send 11 upload requests within 1 minute
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test.pdf"
  echo ""
done

# Expected: First 10 succeed, 11th returns HTTP 429
```

---

## Test 4: External Service Timeouts (US4)

### Test: LlamaIndex Timeout

```bash
# Start a mock slow server on port 9000 that delays 70s
# Configure LLAMAINDEX_SERVICE_URL to point to mock

curl -X POST http://localhost:8000/api/documents/parse \
  -H "Content-Type: application/json" \
  -d '{"document_url":"https://example.com/doc.pdf"}'

# Expected: Timeout after 60s with error:
# {"error":{"code":"EXTERNAL_SERVICE_ERROR","message":"LlamaIndex service timeout"}}
```

---

## Test 5: Circuit Breaker Protection (US5)

### Test: Circuit Opens After Failures

```bash
# Shut down LlamaIndex service, send 6 requests
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/documents/parse \
    -H "Content-Type: application/json" \
    -d '{"document_url":"https://example.com/doc.pdf"}'
  sleep 1
done

# Expected: First 5 fail with service error
# 6th fails immediately with "Circuit breaker open"
```

### Test: Circuit Breaker State Endpoint

```bash
curl http://localhost:8000/api/system/circuit-breakers

# Expected JSON response:
# {
#   "llama_index": {"state": "OPEN", "failure_count": 5},
#   "crewai": {"state": "CLOSED", "failure_count": 0},
#   ...
# }
```

---

## Test 6: Standardized Error Responses (US6)

### Test: Validation Error Format

```bash
curl -X POST http://localhost:8000/api/query/auto \
  -H "Content-Type: application/json" \
  -d '{}'

# Expected response format:
# {
#   "error": {
#     "code": "VALIDATION_ERROR",
#     "message": "Request validation failed",
#     "details": {"query": "field required"},
#     "request_id": "uuid-string",
#     "timestamp": "2025-01-15T12:00:00Z"
#   }
# }
```

### Test: Rate Limit Error Format

```bash
# Exceed rate limit and check response format
# (after hitting 429)

# Expected:
# {
#   "error": {
#     "code": "RATE_LIMITED",
#     "message": "Rate limit exceeded",
#     "details": {"retry_after": 60},
#     "request_id": "uuid-string",
#     "timestamp": "2025-01-15T12:00:00Z"
#   }
# }
```

---

## Automated Test Suite

Run all production readiness tests:

```bash
# Run unit tests
pytest tests/test_startup_validation.py -v
pytest tests/test_rate_limiting.py -v
pytest tests/test_circuit_breakers.py -v
pytest tests/test_error_responses.py -v

# Run all production readiness tests
pytest tests/ -k "production_readiness" -v
```

---

## Success Verification Checklist

- [ ] App fails to start with missing critical env var
- [ ] App logs warning for missing recommended env var
- [ ] App fails to start with wildcard CORS in production
- [ ] Login endpoint returns 429 after 5 requests/minute
- [ ] Upload endpoint returns 429 after 10 requests/minute
- [ ] External service calls timeout as configured
- [ ] Circuit breaker opens after threshold failures
- [ ] Circuit breaker exposes state via API
- [ ] All errors follow standardized format
- [ ] All errors include request_id and timestamp
