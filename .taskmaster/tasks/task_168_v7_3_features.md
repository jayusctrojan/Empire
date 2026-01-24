# Task ID: 168

**Title:** Create Integration Tests for Production Readiness

**Status:** cancelled

**Dependencies:** 160 ✗, 161 ✗, 162 ✗, 163 ✗, 164 ✗, 165 ✗, 166 ✗, 167 ✗

**Priority:** medium

**Description:** Develop comprehensive integration tests to verify all production readiness improvements function correctly together.

**Details:**

Create integration tests that verify the combined functionality of all production readiness improvements:

1. Create a test suite in `tests/integration/test_production_readiness.py`:
```python
import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

# Environment Variable Validation Tests
def test_startup_validation_fails_with_missing_critical_vars():
    with patch.dict(os.environ, {"SUPABASE_URL": "", "REDIS_URL": ""}, clear=True):
        with pytest.raises(RuntimeError, match="Missing critical env vars"):
            from app.core.startup_validation import validate_environment
            validate_environment()

# CORS Tests
def test_cors_rejects_wildcard_in_production():
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "CORS_ORIGINS": "*"}, clear=False):
        with pytest.raises(RuntimeError, match="CORS_ORIGINS cannot be '*' in production"):
            # Import here to trigger CORS validation
            from app.main import setup_cors
            setup_cors()

# Rate Limiting Tests
def test_login_endpoint_rate_limiting(client):
    # Make 6 requests to login endpoint (limit is 5/minute)
    for i in range(6):
        response = client.post("/api/users/login", json={"username": "test", "password": "test"})
        if i < 5:
            assert response.status_code != 429
        else:
            assert response.status_code == 429
            assert "error" in response.json()
            assert response.json()["error"]["code"] == "RATE_LIMITED"

# Timeout Tests
@patch("httpx.AsyncClient.post")
async def test_external_service_timeout(mock_post):
    # Simulate timeout
    mock_post.side_effect = httpx.TimeoutException("Timeout")
    
    from app.services.llama_index_service import LlamaIndexService
    service = LlamaIndexService()
    
    with pytest.raises(httpx.TimeoutException):
        await service.process_document("test.pdf")

# Circuit Breaker Tests
@patch("httpx.AsyncClient.post")
async def test_circuit_breaker_opens_after_failures(mock_post):
    # Simulate multiple failures
    mock_post.side_effect = Exception("Service error")
    
    from app.services.llama_index_service import LlamaIndexService
    service = LlamaIndexService()
    
    # Cause failures to trigger circuit breaker
    for i in range(6):  # Threshold is 5
        try:
            await service.process_document("test.pdf")
        except Exception:
            pass
    
    # Next call should be rejected by circuit breaker
    with pytest.raises(ServiceUnavailableError):
        await service.process_document("test.pdf")

# Error Response Format Tests
def test_error_response_format(client):
    # Test validation error
    response = client.post("/api/query", json={})
    assert response.status_code == 400
    
    error_data = response.json()
    assert "error" in error_data
    assert "code" in error_data["error"]
    assert "message" in error_data["error"]
    assert "details" in error_data["error"]
    assert "request_id" in error_data["error"]
    assert "timestamp" in error_data["error"]
    
    assert error_data["error"]["code"] == "VALIDATION_ERROR"
```

2. Create a test fixture that simulates production environment:
```python
@pytest.fixture
def production_environment():
    original_env = os.environ.copy()
    os.environ.update({
        "ENVIRONMENT": "production",
        "CORS_ORIGINS": "https://app.example.com,https://admin.example.com",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_KEY": "dummy-key",
        "REDIS_URL": "redis://localhost:6379/0",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_PASSWORD": "password",
        "ANTHROPIC_API_KEY": "dummy-key"
    })
    yield
    os.environ.clear()
    os.environ.update(original_env)
```

3. Create tests that verify all components work together in a production-like environment

**Test Strategy:**

1. Run the integration tests in a CI/CD pipeline to verify production readiness
2. Test with various environment configurations to ensure all validation works correctly
3. Verify that all components (validation, CORS, rate limiting, timeouts, circuit breakers, error handling) work together correctly
4. Create a test matrix that covers all possible combinations of failure scenarios
5. Verify that the tests accurately reflect the production environment
