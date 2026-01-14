"""
Empire v7.3 - Integration Test Configuration and Fixtures
Task 139: Create Integration Tests for Agent API Routes

Provides shared fixtures for integration testing of agent API routes.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime
from typing import Dict, Any, List, Optional

# Pytest markers
pytestmark = [pytest.mark.integration]


# =============================================================================
# APP FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def test_client():
    """
    Create a FastAPI TestClient for integration testing.

    Uses module scope for efficiency - the client is reused across tests
    in the same module.
    """
    # Import here to avoid circular imports and allow mocking
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(test_client):
    """Alias for test_client for convenience."""
    return test_client


# =============================================================================
# MOCK SERVICE FIXTURES
# =============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic Claude client for LLM calls."""
    mock_client = MagicMock()

    # Mock message response
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "This is a mock LLM response for testing purposes."
    mock_response.content = [mock_content]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for database operations."""
    mock_client = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[], count=0)

    mock_client.table.return_value = mock_table

    return mock_client


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for graph database operations."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.data.return_value = []
    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    return mock_driver


@pytest.fixture
def mock_b2_storage():
    """Mock B2 storage client."""
    mock_storage = MagicMock()
    mock_storage.upload_file = AsyncMock(return_value={
        "file_id": "test_file_id",
        "file_name": "test_file.pdf",
        "size": 1024,
        "url": "https://example.com/test_file.pdf"
    })
    mock_storage.download_file = AsyncMock(return_value=b"file content")
    mock_storage.list_files = AsyncMock(return_value=[])

    return mock_storage


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching."""
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=True)
    mock_redis.exists = AsyncMock(return_value=False)

    return mock_redis


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_document_content():
    """Sample document content for testing summarization and analysis."""
    return """
    Annual Business Strategy Report 2024

    Executive Summary

    This comprehensive report outlines the key strategic initiatives
    for our organization in 2024. The focus areas include digital
    transformation, customer experience enhancement, and sustainable
    growth strategies.

    1. Market Analysis

    The global market continues to evolve with increasing emphasis on
    digital solutions. Our analysis indicates a 15% year-over-year
    growth in the digital services sector, presenting significant
    opportunities for expansion.

    2. Strategic Initiatives

    2.1 Digital Transformation
    Investment in cloud infrastructure and AI-powered automation
    will drive operational efficiency. Expected ROI: 25% over 3 years.

    2.2 Customer Experience
    Implementation of omnichannel support and personalization engines
    to improve customer satisfaction scores by 20%.

    2.3 Sustainability
    Commitment to carbon neutrality by 2030 through renewable energy
    adoption and supply chain optimization.

    3. Financial Projections

    Revenue growth forecast: 18% annually
    Cost reduction target: 10% through automation
    Market share goal: Increase from 12% to 15%

    4. Conclusion

    The strategic roadmap positions our organization for sustainable
    growth while maintaining competitive advantage in key markets.
    """


@pytest.fixture
def sample_technical_content():
    """Sample technical content for IT/Engineering classification."""
    return """
    Kubernetes Deployment Guide for Microservices

    This document outlines the best practices for deploying
    microservices to a Kubernetes cluster. Topics covered include:

    - Container orchestration with Kubernetes
    - Service mesh implementation with Istio
    - CI/CD pipeline integration
    - Monitoring with Prometheus and Grafana
    - Horizontal pod autoscaling
    - ConfigMaps and Secrets management

    Prerequisites:
    - Docker and kubectl installed
    - Access to a Kubernetes cluster
    - Helm 3.x for package management

    The deployment process involves creating deployment manifests,
    configuring service endpoints, and setting up ingress rules
    for external access.
    """


@pytest.fixture
def sample_sales_content():
    """Sample sales content for Sales/Marketing classification."""
    return """
    Q4 Sales Performance Review

    Regional Sales Summary:
    - North America: $2.5M (115% of target)
    - Europe: $1.8M (102% of target)
    - APAC: $1.2M (98% of target)

    Top Performing Products:
    1. Enterprise Suite - 45% of revenue
    2. Professional Plan - 30% of revenue
    3. Starter Package - 25% of revenue

    Key Wins:
    - Fortune 500 contract worth $500K ARR
    - Partnership with major systems integrator
    - 25% increase in lead generation

    Next Quarter Focus:
    - Expand into Latin America market
    - Launch new pricing tier
    - Implement sales enablement tools
    """


@pytest.fixture
def sample_hr_content():
    """Sample HR content for Operations/HR classification."""
    return """
    Employee Onboarding Process Manual

    Purpose: This manual provides guidelines for onboarding
    new employees to ensure a smooth transition into the organization.

    Day 1 Checklist:
    - HR orientation and paperwork completion
    - IT equipment setup and access provisioning
    - Benefits enrollment walkthrough
    - Office tour and introductions

    Week 1 Goals:
    - Complete mandatory training modules
    - Meet with direct manager for role expectations
    - Access team resources and documentation
    - Set up 1:1 meetings with key stakeholders

    Probation Period:
    - 90-day evaluation with milestones
    - Regular check-ins with HR and manager
    - Performance review at 30, 60, and 90 days
    """


@pytest.fixture
def sample_finance_content():
    """Sample finance content for Finance/Accounting classification."""
    return """
    Quarterly Financial Report - Q3 2024

    Balance Sheet Summary:
    Total Assets: $15.2M
    Total Liabilities: $8.5M
    Shareholders' Equity: $6.7M

    Income Statement:
    Revenue: $4.5M
    Cost of Goods Sold: $2.1M
    Gross Profit: $2.4M
    Operating Expenses: $1.5M
    Net Income: $0.9M

    Key Financial Ratios:
    - Current Ratio: 2.1
    - Debt-to-Equity: 1.27
    - ROE: 13.4%
    - ROA: 5.9%

    Audit Findings:
    No material misstatements identified.
    Recommendation: Improve accounts receivable collection.
    """


@pytest.fixture
def sample_batch_items():
    """Sample batch of items for batch classification testing."""
    return [
        {"content": "Python API development with FastAPI and PostgreSQL", "filename": "dev_guide.md"},
        {"content": "Marketing campaign performance analysis and ROI metrics", "filename": "campaign_report.docx"},
        {"content": "Employee benefits enrollment and 401k contribution guide", "filename": "benefits_guide.pdf"},
        {"content": "Q4 budget forecast and expense allocation planning", "filename": "budget_q4.xlsx"},
        {"content": "Project timeline and milestone tracking for product launch", "filename": "project_plan.mpp"},
    ]


# =============================================================================
# RESPONSE VALIDATION HELPERS
# =============================================================================

@pytest.fixture
def validate_error_response():
    """Helper fixture to validate error response structure."""
    def _validate(response_json: Dict[str, Any], expected_code: Optional[str] = None):
        """Validate that response has proper error structure."""
        assert "error_code" in response_json or "error" in response_json or "detail" in response_json
        if expected_code and "error_code" in response_json:
            assert response_json["error_code"] == expected_code
        return True
    return _validate


@pytest.fixture
def validate_health_response():
    """Helper fixture to validate health check response structure."""
    def _validate(response_json: Dict[str, Any]):
        """Validate that response has proper health check structure."""
        assert "status" in response_json
        assert response_json["status"] in ["healthy", "degraded", "unhealthy"]
        return True
    return _validate


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def mock_environment_variables(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_PASSWORD", "test-password")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
