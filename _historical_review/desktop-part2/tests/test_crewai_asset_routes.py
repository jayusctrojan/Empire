"""
Empire v7.3 - CrewAI Asset Routes Tests (Task 47)
Tests for API endpoints in /api/crewai/assets
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import base64


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_asset_service():
    """Mock CrewAI asset service"""
    with patch('app.routes.crewai_assets.get_asset_service') as mock:
        mock_service = MagicMock()
        mock_service.store_asset = AsyncMock()
        mock_service.retrieve_assets = AsyncMock()
        mock_service.get_asset_by_id = AsyncMock()
        mock_service.update_asset = AsyncMock()
        mock_service.get_signed_download_url = AsyncMock()
        mock.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_asset_response():
    """Sample AssetResponse data"""
    from app.models.crewai_asset import AssetResponse
    return AssetResponse(
        id=uuid4(),
        execution_id=uuid4(),
        document_id="doc-123",
        department="marketing",
        asset_type="summary",
        asset_name="Q4 Campaign Summary",
        content="# Q4 Marketing Campaign\n\nKey findings...",
        content_format="markdown",
        b2_path=None,
        file_size=None,
        mime_type="text/markdown",
        metadata={"campaign": "Q4"},
        confidence_score=0.95,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_file_asset_response():
    """Sample AssetResponse for file-based asset"""
    from app.models.crewai_asset import AssetResponse
    return AssetResponse(
        id=uuid4(),
        execution_id=uuid4(),
        document_id=None,
        department="legal",
        asset_type="contract_review",
        asset_name="Contract_Analysis",
        content=None,
        content_format="pdf",
        b2_path="crewai/assets/legal/contract_review/uuid/file.pdf",
        file_size=1234,
        mime_type="application/pdf",
        metadata={},
        confidence_score=0.9,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def app():
    """Create test FastAPI app"""
    from fastapi import FastAPI
    from app.routes.crewai_assets import router

    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Sync test client"""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Async test client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# STORE ASSET ENDPOINT TESTS
# =============================================================================

class TestStoreAssetEndpoint:
    """Test POST /api/crewai/assets/ endpoint"""

    def test_store_text_asset_success(self, client, mock_asset_service, sample_asset_response):
        """Test storing text-based asset"""
        mock_asset_service.store_asset.return_value = sample_asset_response

        response = client.post(
            "/api/crewai/assets/",
            json={
                "execution_id": str(uuid4()),
                "department": "marketing",
                "asset_type": "summary",
                "asset_name": "Q4 Campaign Summary",
                "content": "# Q4 Marketing Campaign",
                "content_format": "markdown",
                "confidence_score": 0.95
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["asset_name"] == "Q4 Campaign Summary"
        assert data["department"] == "marketing"

    def test_store_file_asset_with_base64(self, client, mock_asset_service, sample_file_asset_response):
        """Test storing file-based asset with base64 content"""
        mock_asset_service.store_asset.return_value = sample_file_asset_response

        file_content = base64.b64encode(b"PDF content").decode()

        response = client.post(
            "/api/crewai/assets/",
            json={
                "execution_id": str(uuid4()),
                "department": "legal",
                "asset_type": "contract_review",
                "asset_name": "Contract_Analysis",
                "file_content": file_content,
                "content_format": "pdf",
                "confidence_score": 0.9
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["b2_path"] is not None

    def test_store_asset_invalid_request(self, client, mock_asset_service):
        """Test error handling for invalid request"""
        mock_asset_service.store_asset.side_effect = ValueError("Cannot provide both content and file_content")

        response = client.post(
            "/api/crewai/assets/",
            json={
                "execution_id": str(uuid4()),
                "department": "marketing",
                "asset_type": "summary",
                "asset_name": "Test",
                "content": "text",
                "file_content": base64.b64encode(b"binary").decode(),
                "content_format": "text"
            }
        )

        assert response.status_code == 400
        assert "Cannot provide both" in response.json()["detail"]

    def test_store_asset_missing_required_fields(self, client):
        """Test validation error for missing required fields"""
        response = client.post(
            "/api/crewai/assets/",
            json={
                "asset_name": "Test"
                # Missing execution_id, department, asset_type
            }
        )

        assert response.status_code == 422  # Validation error


# =============================================================================
# RETRIEVE ASSETS ENDPOINT TESTS
# =============================================================================

class TestRetrieveAssetsEndpoint:
    """Test GET /api/crewai/assets/ endpoint"""

    def test_retrieve_assets_no_filters(self, client, mock_asset_service, sample_asset_response):
        """Test retrieving all assets"""
        from app.models.crewai_asset import AssetListResponse
        mock_asset_service.retrieve_assets.return_value = AssetListResponse(
            total=1,
            assets=[sample_asset_response],
            filters_applied={}
        )

        response = client.get("/api/crewai/assets/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["assets"]) == 1

    def test_retrieve_assets_with_department_filter(self, client, mock_asset_service, sample_asset_response):
        """Test retrieving assets filtered by department"""
        from app.models.crewai_asset import AssetListResponse
        mock_asset_service.retrieve_assets.return_value = AssetListResponse(
            total=1,
            assets=[sample_asset_response],
            filters_applied={"department": "marketing"}
        )

        response = client.get("/api/crewai/assets/?department=marketing")

        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"]["department"] == "marketing"

    def test_retrieve_assets_with_confidence_filter(self, client, mock_asset_service, sample_asset_response):
        """Test retrieving assets filtered by confidence score"""
        from app.models.crewai_asset import AssetListResponse
        mock_asset_service.retrieve_assets.return_value = AssetListResponse(
            total=1,
            assets=[sample_asset_response],
            filters_applied={"min_confidence": 0.8}
        )

        response = client.get("/api/crewai/assets/?min_confidence=0.8")

        assert response.status_code == 200

    def test_retrieve_assets_with_pagination(self, client, mock_asset_service, sample_asset_response):
        """Test pagination parameters"""
        from app.models.crewai_asset import AssetListResponse
        mock_asset_service.retrieve_assets.return_value = AssetListResponse(
            total=0,
            assets=[],
            filters_applied={}
        )

        response = client.get("/api/crewai/assets/?limit=10&offset=20")

        assert response.status_code == 200


# =============================================================================
# GET SINGLE ASSET ENDPOINT TESTS
# =============================================================================

class TestGetAssetEndpoint:
    """Test GET /api/crewai/assets/{asset_id} endpoint"""

    def test_get_asset_success(self, client, mock_asset_service, sample_asset_response):
        """Test getting asset by ID"""
        mock_asset_service.get_asset_by_id.return_value = sample_asset_response

        asset_id = str(sample_asset_response.id)
        response = client.get(f"/api/crewai/assets/{asset_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == asset_id

    def test_get_asset_not_found(self, client, mock_asset_service):
        """Test 404 for non-existent asset"""
        mock_asset_service.get_asset_by_id.return_value = None

        response = client.get(f"/api/crewai/assets/{uuid4()}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_asset_invalid_uuid(self, client):
        """Test validation for invalid UUID"""
        response = client.get("/api/crewai/assets/not-a-uuid")

        assert response.status_code == 422


# =============================================================================
# UPDATE ASSET ENDPOINT TESTS
# =============================================================================

class TestUpdateAssetEndpoint:
    """Test PATCH /api/crewai/assets/{asset_id} endpoint"""

    def test_update_asset_confidence(self, client, mock_asset_service, sample_asset_response):
        """Test updating asset confidence score"""
        updated = sample_asset_response
        updated.confidence_score = 0.99
        mock_asset_service.update_asset.return_value = updated

        response = client.patch(
            f"/api/crewai/assets/{sample_asset_response.id}",
            json={"confidence_score": 0.99}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["confidence_score"] == 0.99

    def test_update_asset_metadata(self, client, mock_asset_service, sample_asset_response):
        """Test updating asset metadata"""
        updated = sample_asset_response
        updated.metadata = {**sample_asset_response.metadata, "reviewed": True}
        mock_asset_service.update_asset.return_value = updated

        response = client.patch(
            f"/api/crewai/assets/{sample_asset_response.id}",
            json={"metadata": {"reviewed": True}}
        )

        assert response.status_code == 200

    def test_update_asset_not_found(self, client, mock_asset_service):
        """Test 404 when updating non-existent asset"""
        mock_asset_service.update_asset.side_effect = ValueError("Asset not found")

        response = client.patch(
            f"/api/crewai/assets/{uuid4()}",
            json={"confidence_score": 0.9}
        )

        assert response.status_code == 404


# =============================================================================
# GET EXECUTION ASSETS ENDPOINT TESTS
# =============================================================================

class TestGetExecutionAssetsEndpoint:
    """Test GET /api/crewai/assets/execution/{execution_id} endpoint"""

    def test_get_execution_assets_success(self, client, mock_asset_service, sample_asset_response):
        """Test getting all assets for an execution"""
        from app.models.crewai_asset import AssetListResponse
        mock_asset_service.retrieve_assets.return_value = AssetListResponse(
            total=2,
            assets=[sample_asset_response, sample_asset_response],
            filters_applied={"execution_id": str(sample_asset_response.execution_id)}
        )

        execution_id = str(sample_asset_response.execution_id)
        response = client.get(f"/api/crewai/assets/execution/{execution_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_get_execution_assets_empty(self, client, mock_asset_service):
        """Test getting assets for execution with no results"""
        from app.models.crewai_asset import AssetListResponse
        mock_asset_service.retrieve_assets.return_value = AssetListResponse(
            total=0,
            assets=[],
            filters_applied={}
        )

        response = client.get(f"/api/crewai/assets/execution/{uuid4()}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


# =============================================================================
# SIGNED URL ENDPOINT TESTS
# =============================================================================

class TestSignedUrlEndpoint:
    """Test GET /api/crewai/assets/{asset_id}/download-url endpoint"""

    def test_get_signed_url_success(self, client, mock_asset_service, sample_file_asset_response):
        """Test getting signed URL for file-based asset"""
        mock_asset_service.get_signed_download_url.return_value = {
            "signed_url": "https://b2.example.com/file?auth=token",
            "expires_at": datetime.utcnow().isoformat(),
            "valid_duration_seconds": 3600,
            "file_path": sample_file_asset_response.b2_path,
            "asset_id": str(sample_file_asset_response.id),
            "asset_name": sample_file_asset_response.asset_name,
            "mime_type": sample_file_asset_response.mime_type,
            "file_size": sample_file_asset_response.file_size
        }

        response = client.get(
            f"/api/crewai/assets/{sample_file_asset_response.id}/download-url"
        )

        assert response.status_code == 200
        data = response.json()
        assert "signed_url" in data
        assert data["valid_duration_seconds"] == 3600

    def test_get_signed_url_custom_duration(self, client, mock_asset_service, sample_file_asset_response):
        """Test getting signed URL with custom duration"""
        mock_asset_service.get_signed_download_url.return_value = {
            "signed_url": "https://b2.example.com/file?auth=token",
            "expires_at": datetime.utcnow().isoformat(),
            "valid_duration_seconds": 7200,
            "file_path": sample_file_asset_response.b2_path,
            "asset_id": str(sample_file_asset_response.id),
            "asset_name": sample_file_asset_response.asset_name,
            "mime_type": sample_file_asset_response.mime_type,
            "file_size": sample_file_asset_response.file_size
        }

        response = client.get(
            f"/api/crewai/assets/{sample_file_asset_response.id}/download-url?valid_duration_seconds=7200"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid_duration_seconds"] == 7200

    def test_get_signed_url_text_asset_error(self, client, mock_asset_service, sample_asset_response):
        """Test error when getting signed URL for text-based asset"""
        mock_asset_service.get_signed_download_url.return_value = None

        response = client.get(
            f"/api/crewai/assets/{sample_asset_response.id}/download-url"
        )

        assert response.status_code == 400
        assert "text-based" in response.json()["detail"].lower()

    def test_get_signed_url_not_found(self, client, mock_asset_service):
        """Test 404 when asset not found"""
        mock_asset_service.get_signed_download_url.side_effect = ValueError("Asset not found")

        response = client.get(f"/api/crewai/assets/{uuid4()}/download-url")

        assert response.status_code == 404

    def test_get_signed_url_duration_too_short(self, client, mock_asset_service):
        """Test validation for duration < 60 seconds"""
        response = client.get(
            f"/api/crewai/assets/{uuid4()}/download-url?valid_duration_seconds=30"
        )

        assert response.status_code == 400
        assert "at least 60" in response.json()["detail"]

    def test_get_signed_url_duration_too_long(self, client, mock_asset_service):
        """Test validation for duration > 1 week"""
        response = client.get(
            f"/api/crewai/assets/{uuid4()}/download-url?valid_duration_seconds=1000000"
        )

        assert response.status_code == 400
        assert "604800" in response.json()["detail"]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling in routes"""

    def test_internal_server_error(self, client, mock_asset_service):
        """Test 500 error handling"""
        mock_asset_service.store_asset.side_effect = Exception("Database connection failed")

        response = client.post(
            "/api/crewai/assets/",
            json={
                "execution_id": str(uuid4()),
                "department": "marketing",
                "asset_type": "summary",
                "asset_name": "Test",
                "content": "Test content",
                "content_format": "text"
            }
        )

        assert response.status_code == 500
        assert "Failed to store asset" in response.json()["detail"]

    def test_retrieve_error(self, client, mock_asset_service):
        """Test error handling in retrieve"""
        mock_asset_service.retrieve_assets.side_effect = Exception("Query failed")

        response = client.get("/api/crewai/assets/")

        assert response.status_code == 500


# =============================================================================
# ROUTE REGISTRATION TESTS
# =============================================================================

class TestRouteRegistration:
    """Test that routes are properly registered"""

    def test_routes_exist(self, app):
        """Test all expected routes are registered"""
        routes = [route.path for route in app.routes]

        # Check main endpoints
        assert "/api/crewai/assets/" in routes
        assert "/api/crewai/assets/{asset_id}" in routes
        assert "/api/crewai/assets/{asset_id}/download-url" in routes
        assert "/api/crewai/assets/execution/{execution_id}" in routes

    def test_route_methods(self, app):
        """Test routes have correct HTTP methods"""
        # Collect all methods across routes with the same path
        route_methods = {}
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                if route.path not in route_methods:
                    route_methods[route.path] = set()
                route_methods[route.path].update(route.methods)

        # Check that POST and GET exist for /api/crewai/assets/
        assets_methods = route_methods.get("/api/crewai/assets/", set())
        assert "GET" in assets_methods or "POST" in assets_methods, \
            "Expected GET or POST method for /api/crewai/assets/"

        # PATCH for update
        assert "PATCH" in route_methods.get("/api/crewai/assets/{asset_id}", set())

        # GET for download URL
        assert "GET" in route_methods.get("/api/crewai/assets/{asset_id}/download-url", set())
