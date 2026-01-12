# Task ID: 111

**Title:** Implement Integration Tests for Graph Agent

**Status:** pending

**Dependencies:** 107, 108, 109, 110

**Priority:** medium

**Description:** Create comprehensive integration tests for the Graph Agent components to ensure they work together correctly and meet performance requirements.

**Details:**

Implement integration tests in tests/integration/test_graph_agent.py that verify the correct functioning of the Graph Agent components together:

1. Test setup:
   - Create test fixtures for Neo4j with sample data
   - Set up test instances of all services
   - Configure test client for API endpoints

2. Customer 360 integration tests:
   - Test end-to-end customer queries
   - Verify correct data retrieval and formatting
   - Test performance against SLAs

3. Document Structure integration tests:
   - Test document structure extraction
   - Test smart retrieval with cross-references
   - Verify correct handling of complex documents

4. Graph-Enhanced RAG integration tests:
   - Test query expansion with graph context
   - Verify improved results compared to standard RAG
   - Test performance impact

5. End-to-end CKO Chat integration:
   - Test query intent detection
   - Verify correct routing to graph agents
   - Test response formatting for UI

Implement test utilities for loading test data, measuring performance, and comparing results:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.neo4j_http_client import Neo4jHTTPClient
from app.services.customer360_service import Customer360Service
# Import other services

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def neo4j_client():
    # Create test Neo4j client with test database
    client = Neo4jHTTPClient(test_uri, test_user, test_password)
    # Load test data
    yield client
    # Clean up test data

@pytest.fixture
def customer360_service(neo4j_client):
    return Customer360Service(neo4j_client)

# Test cases
def test_customer360_query(test_client, neo4j_client):
    # Test customer query endpoint
    response = test_client.post(
        "/api/graph/customer360/query",
        json={"query": "Show me everything about Test Corp"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["customer"]["name"] == "Test Corp"
    # Additional assertions

# Additional test cases for other components
```

Include performance tests that verify the system meets the SLAs defined in the PRD.

**Test Strategy:**

1. Test with realistic test data that mimics production
2. Measure response times against SLAs
3. Test with various query patterns
4. Test error handling and edge cases
5. Test concurrent access patterns
6. Compare results with expected outputs
7. Test integration with existing Empire components
