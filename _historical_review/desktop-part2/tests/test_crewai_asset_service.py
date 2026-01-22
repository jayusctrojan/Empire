"""
Empire v7.3 - CrewAI Asset Service Tests (Task 47)
Comprehensive pytest tests for CrewAI asset storage and B2 integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime
import base64

from app.models.crewai_asset import (
    AssetStorageRequest,
    AssetUpdateRequest,
    AssetResponse,
    AssetListResponse,
    AssetRetrievalFilters,
    AssetType,
    Department,
    ContentFormat
)
from app.services.crewai_asset_service import CrewAIAssetService, get_asset_service


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    with patch('app.services.crewai_asset_service.get_supabase_client') as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_b2_service():
    """Mock B2 storage service"""
    with patch('app.services.crewai_asset_service.get_b2_service') as mock:
        mock_service = MagicMock()
        mock_service.upload_file = AsyncMock()
        mock_service.get_signed_url_for_asset = AsyncMock()
        mock.return_value = mock_service
        yield mock_service


@pytest.fixture
def asset_service(mock_supabase, mock_b2_service):
    """Create asset service with mocked dependencies"""
    # Reset singleton
    import app.services.crewai_asset_service as module
    module._asset_service = None

    service = CrewAIAssetService()
    service.supabase = mock_supabase
    service.b2_service = mock_b2_service
    return service


@pytest.fixture
def sample_text_asset_request():
    """Sample text-based asset storage request"""
    return AssetStorageRequest(
        execution_id=uuid4(),
        document_id="doc-123",
        department=Department.MARKETING,
        asset_type=AssetType.SUMMARY,
        asset_name="Q4 Campaign Summary",
        content="# Q4 Marketing Campaign\n\nKey findings...",
        content_format=ContentFormat.MARKDOWN,
        metadata={"campaign": "Q4", "year": 2025},
        confidence_score=0.95
    )


@pytest.fixture
def sample_file_asset_request():
    """Sample file-based asset storage request"""
    return AssetStorageRequest(
        execution_id=uuid4(),
        department=Department.LEGAL,
        asset_type=AssetType.CONTRACT_REVIEW,
        asset_name="Contract_Analysis_Report",
        file_content=b"PDF content here...",
        content_format=ContentFormat.PDF,
        metadata={"contract_id": "CON-456"},
        confidence_score=0.88
    )


@pytest.fixture
def sample_asset_response():
    """Sample asset response from database"""
    return {
        "id": str(uuid4()),
        "execution_id": str(uuid4()),
        "document_id": "doc-123",
        "department": "marketing",
        "asset_type": "summary",
        "asset_name": "Q4 Campaign Summary",
        "content": "# Q4 Marketing Campaign\n\nKey findings...",
        "content_format": "markdown",
        "b2_path": None,
        "file_size": None,
        "mime_type": "text/markdown",
        "metadata": {"campaign": "Q4"},
        "confidence_score": 0.95,
        "created_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# PYDANTIC MODEL TESTS
# =============================================================================

class TestAssetModels:
    """Test Pydantic models for CrewAI assets"""

    def test_asset_type_enum_values(self):
        """Test AssetType enum has all expected values"""
        assert AssetType.SUMMARY == "summary"
        assert AssetType.ANALYSIS == "analysis"
        assert AssetType.REPORT == "report"
        assert AssetType.CHART == "chart"
        assert AssetType.CONTRACT_REVIEW == "contract_review"
        assert AssetType.CUSTOM == "custom"

    def test_department_enum_values(self):
        """Test Department enum has all expected values"""
        assert Department.MARKETING == "marketing"
        assert Department.LEGAL == "legal"
        assert Department.HR == "hr"
        assert Department.FINANCE == "finance"
        assert Department.ENGINEERING == "engineering"

    def test_content_format_enum_values(self):
        """Test ContentFormat enum has all expected values"""
        assert ContentFormat.TEXT == "text"
        assert ContentFormat.MARKDOWN == "markdown"
        assert ContentFormat.HTML == "html"
        assert ContentFormat.JSON == "json"
        assert ContentFormat.PDF == "pdf"
        assert ContentFormat.PNG == "png"

    def test_asset_storage_request_text_content(self, sample_text_asset_request):
        """Test AssetStorageRequest with text content"""
        assert sample_text_asset_request.content is not None
        assert sample_text_asset_request.file_content is None
        assert sample_text_asset_request.content_format == ContentFormat.MARKDOWN

    def test_asset_storage_request_file_content(self, sample_file_asset_request):
        """Test AssetStorageRequest with file content"""
        assert sample_file_asset_request.content is None
        assert sample_file_asset_request.file_content is not None
        assert sample_file_asset_request.content_format == ContentFormat.PDF

    def test_asset_storage_request_base64_decoding(self):
        """Test base64 decoding of file_content in JSON"""
        original_bytes = b"Test PDF content"
        encoded = base64.b64encode(original_bytes).decode()

        request = AssetStorageRequest(
            execution_id=uuid4(),
            department=Department.MARKETING,
            asset_type=AssetType.SUMMARY,
            asset_name="Test",
            file_content=encoded,  # Pass as string (base64)
            content_format=ContentFormat.PDF
        )

        assert request.file_content == original_bytes

    def test_confidence_score_validation(self):
        """Test confidence_score must be between 0 and 1"""
        with pytest.raises(ValueError):
            AssetStorageRequest(
                execution_id=uuid4(),
                department=Department.MARKETING,
                asset_type=AssetType.SUMMARY,
                asset_name="Test",
                content="Test",
                confidence_score=1.5  # Invalid: > 1.0
            )

    def test_asset_update_request(self):
        """Test AssetUpdateRequest model"""
        update = AssetUpdateRequest(
            confidence_score=0.98,
            metadata={"reviewed_by": "John"}
        )
        assert update.confidence_score == 0.98
        assert update.metadata["reviewed_by"] == "John"

    def test_asset_retrieval_filters_defaults(self):
        """Test AssetRetrievalFilters default values"""
        filters = AssetRetrievalFilters()
        assert filters.limit == 100
        assert filters.offset == 0
        assert filters.execution_id is None
        assert filters.department is None

    def test_asset_retrieval_filters_validation(self):
        """Test AssetRetrievalFilters limit validation"""
        with pytest.raises(ValueError):
            AssetRetrievalFilters(limit=2000)  # > max 1000


# =============================================================================
# ASSET SERVICE TESTS - STORE ASSET
# =============================================================================

class TestStoreAsset:
    """Test storing assets to database and B2"""

    @pytest.mark.asyncio
    async def test_store_text_asset_success(self, asset_service, mock_supabase, sample_text_asset_request, sample_asset_response):
        """Test storing text-based asset (stored in database)"""
        # Setup mock
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [sample_asset_response]

        result = await asset_service.store_asset(sample_text_asset_request)

        # Verify database insert was called
        mock_supabase.table.assert_called_with("crewai_generated_assets")

        # Verify result
        assert result.asset_name == "Q4 Campaign Summary"
        assert result.department == "marketing"
        assert result.b2_path is None  # Text assets don't have B2 path

    @pytest.mark.asyncio
    async def test_store_file_asset_success(self, asset_service, mock_supabase, mock_b2_service, sample_file_asset_request):
        """Test storing file-based asset (uploaded to B2)"""
        # Setup mocks
        mock_b2_service.upload_file.return_value = {
            "file_name": "crewai/assets/legal/contract_review/uuid/Contract_Analysis_Report.pdf",
            "size": 1234,
            "content_type": "application/pdf"
        }

        db_response = {
            "id": str(uuid4()),
            "execution_id": str(sample_file_asset_request.execution_id),
            "document_id": None,
            "department": "legal",
            "asset_type": "contract_review",
            "asset_name": "Contract_Analysis_Report",
            "content": None,
            "content_format": "pdf",
            "b2_path": "crewai/assets/legal/contract_review/uuid/Contract_Analysis_Report.pdf",
            "file_size": 1234,
            "mime_type": "application/pdf",
            "metadata": {"contract_id": "CON-456"},
            "confidence_score": 0.88,
            "created_at": datetime.utcnow().isoformat()
        }
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [db_response]

        result = await asset_service.store_asset(sample_file_asset_request)

        # Verify B2 upload was called
        mock_b2_service.upload_file.assert_called_once()

        # Verify result
        assert result.asset_name == "Contract_Analysis_Report"
        assert result.b2_path is not None
        assert result.file_size == 1234

    @pytest.mark.asyncio
    async def test_store_asset_both_content_types_error(self, asset_service):
        """Test error when both content and file_content provided"""
        request = AssetStorageRequest(
            execution_id=uuid4(),
            department=Department.MARKETING,
            asset_type=AssetType.SUMMARY,
            asset_name="Test",
            content="text content",
            file_content=b"binary content",
            content_format=ContentFormat.TEXT
        )

        with pytest.raises(ValueError, match="Cannot provide both content and file_content"):
            await asset_service.store_asset(request)

    @pytest.mark.asyncio
    async def test_store_asset_no_content_error(self, asset_service):
        """Test error when neither content nor file_content provided"""
        request = AssetStorageRequest(
            execution_id=uuid4(),
            department=Department.MARKETING,
            asset_type=AssetType.SUMMARY,
            asset_name="Test",
            content_format=ContentFormat.TEXT
        )

        with pytest.raises(ValueError, match="Must provide either content or file_content"):
            await asset_service.store_asset(request)

    @pytest.mark.asyncio
    async def test_store_asset_database_error(self, asset_service, mock_supabase, sample_text_asset_request):
        """Test handling of database insert error"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = []

        with pytest.raises(Exception, match="Failed to insert asset"):
            await asset_service.store_asset(sample_text_asset_request)


# =============================================================================
# ASSET SERVICE TESTS - RETRIEVE ASSETS
# =============================================================================

class TestRetrieveAssets:
    """Test retrieving assets with filters"""

    @pytest.mark.asyncio
    async def test_retrieve_assets_no_filters(self, asset_service, mock_supabase, sample_asset_response):
        """Test retrieving all assets without filters"""
        mock_supabase.table.return_value.select.return_value.range.return_value.order.return_value.execute.return_value.data = [sample_asset_response]

        filters = AssetRetrievalFilters()
        result = await asset_service.retrieve_assets(filters)

        assert result.total == 1
        assert len(result.assets) == 1
        assert result.filters_applied == {}

    @pytest.mark.asyncio
    async def test_retrieve_assets_with_department_filter(self, asset_service, mock_supabase, sample_asset_response):
        """Test retrieving assets filtered by department"""
        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value.data = [sample_asset_response]
        mock_supabase.table.return_value.select.return_value = mock_query

        filters = AssetRetrievalFilters(department=Department.MARKETING)
        result = await asset_service.retrieve_assets(filters)

        assert "department" in result.filters_applied
        assert result.filters_applied["department"] == "marketing"

    @pytest.mark.asyncio
    async def test_retrieve_assets_with_confidence_filter(self, asset_service, mock_supabase, sample_asset_response):
        """Test retrieving assets filtered by confidence score"""
        mock_query = MagicMock()
        mock_query.gte.return_value = mock_query
        mock_query.lte.return_value = mock_query
        mock_query.range.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value.data = [sample_asset_response]
        mock_supabase.table.return_value.select.return_value = mock_query

        filters = AssetRetrievalFilters(min_confidence=0.8, max_confidence=1.0)
        result = await asset_service.retrieve_assets(filters)

        assert "min_confidence" in result.filters_applied
        assert "max_confidence" in result.filters_applied

    @pytest.mark.asyncio
    async def test_retrieve_assets_pagination(self, asset_service, mock_supabase, sample_asset_response):
        """Test pagination with offset and limit"""
        mock_query = MagicMock()
        mock_query.range.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value.data = [sample_asset_response]
        mock_supabase.table.return_value.select.return_value = mock_query

        filters = AssetRetrievalFilters(limit=10, offset=20)
        await asset_service.retrieve_assets(filters)

        # Verify range was called with correct offset
        mock_query.range.assert_called_with(20, 29)


# =============================================================================
# ASSET SERVICE TESTS - GET SINGLE ASSET
# =============================================================================

class TestGetAssetById:
    """Test getting a single asset by ID"""

    @pytest.mark.asyncio
    async def test_get_asset_by_id_success(self, asset_service, mock_supabase, sample_asset_response):
        """Test successfully getting asset by ID"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_asset_response]

        asset_id = UUID(sample_asset_response["id"])
        result = await asset_service.get_asset_by_id(asset_id)

        assert result is not None
        assert result.asset_name == "Q4 Campaign Summary"

    @pytest.mark.asyncio
    async def test_get_asset_by_id_not_found(self, asset_service, mock_supabase):
        """Test getting non-existent asset returns None"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        result = await asset_service.get_asset_by_id(uuid4())

        assert result is None


# =============================================================================
# ASSET SERVICE TESTS - UPDATE ASSET
# =============================================================================

class TestUpdateAsset:
    """Test updating asset metadata and confidence"""

    @pytest.mark.asyncio
    async def test_update_asset_confidence(self, asset_service, mock_supabase, sample_asset_response):
        """Test updating asset confidence score"""
        # Mock get_asset_by_id
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_asset_response]

        # Mock update
        updated_response = {**sample_asset_response, "confidence_score": 0.99}
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [updated_response]

        asset_id = UUID(sample_asset_response["id"])
        update = AssetUpdateRequest(confidence_score=0.99)
        result = await asset_service.update_asset(asset_id, update)

        assert result.confidence_score == 0.99

    @pytest.mark.asyncio
    async def test_update_asset_metadata_merge(self, asset_service, mock_supabase, sample_asset_response):
        """Test metadata is merged, not replaced"""
        # Mock get_asset_by_id
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_asset_response]

        # Mock update with merged metadata
        merged_metadata = {**sample_asset_response["metadata"], "reviewed_by": "John"}
        updated_response = {**sample_asset_response, "metadata": merged_metadata}
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [updated_response]

        asset_id = UUID(sample_asset_response["id"])
        update = AssetUpdateRequest(metadata={"reviewed_by": "John"})
        result = await asset_service.update_asset(asset_id, update)

        assert "campaign" in result.metadata  # Original key preserved
        assert result.metadata["reviewed_by"] == "John"  # New key added

    @pytest.mark.asyncio
    async def test_update_asset_not_found(self, asset_service, mock_supabase):
        """Test updating non-existent asset raises error"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Asset not found"):
            await asset_service.update_asset(uuid4(), AssetUpdateRequest(confidence_score=0.9))


# =============================================================================
# ASSET SERVICE TESTS - SIGNED URL
# =============================================================================

class TestSignedUrl:
    """Test signed URL generation for file-based assets"""

    @pytest.mark.asyncio
    async def test_get_signed_url_for_file_asset(self, asset_service, mock_supabase, mock_b2_service):
        """Test generating signed URL for file-based asset"""
        # Setup file-based asset response (has b2_path)
        file_asset_response = {
            "id": str(uuid4()),
            "execution_id": str(uuid4()),
            "document_id": None,
            "department": "legal",
            "asset_type": "contract_review",
            "asset_name": "Contract_Analysis",
            "content": None,
            "content_format": "pdf",
            "b2_path": "crewai/assets/legal/contract_review/uuid/file.pdf",
            "file_size": 1234,
            "mime_type": "application/pdf",
            "metadata": {},
            "confidence_score": 0.9,
            "created_at": datetime.utcnow().isoformat()
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [file_asset_response]

        # Mock B2 signed URL
        mock_b2_service.get_signed_url_for_asset.return_value = {
            "signed_url": "https://b2.example.com/file?auth=token",
            "expires_at": datetime.utcnow().isoformat(),
            "valid_duration_seconds": 3600,
            "file_path": file_asset_response["b2_path"]
        }

        asset_id = UUID(file_asset_response["id"])
        result = await asset_service.get_signed_download_url(asset_id)

        assert result is not None
        assert "signed_url" in result
        assert result["asset_id"] == str(asset_id)
        assert result["asset_name"] == "Contract_Analysis"

    @pytest.mark.asyncio
    async def test_get_signed_url_for_text_asset_returns_none(self, asset_service, mock_supabase, sample_asset_response):
        """Test text-based assets return None for signed URL"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_asset_response]

        asset_id = UUID(sample_asset_response["id"])
        result = await asset_service.get_signed_download_url(asset_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_signed_url_asset_not_found(self, asset_service, mock_supabase):
        """Test signed URL for non-existent asset raises error"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Asset not found"):
            await asset_service.get_signed_download_url(uuid4())


# =============================================================================
# MIME TYPE TESTS
# =============================================================================

class TestMimeTypes:
    """Test MIME type mapping"""

    def test_mime_type_text(self, asset_service):
        """Test text MIME type"""
        assert asset_service._get_mime_type(ContentFormat.TEXT) == "text/plain"

    def test_mime_type_markdown(self, asset_service):
        """Test markdown MIME type"""
        assert asset_service._get_mime_type(ContentFormat.MARKDOWN) == "text/markdown"

    def test_mime_type_pdf(self, asset_service):
        """Test PDF MIME type"""
        assert asset_service._get_mime_type(ContentFormat.PDF) == "application/pdf"

    def test_mime_type_docx(self, asset_service):
        """Test DOCX MIME type"""
        mime = asset_service._get_mime_type(ContentFormat.DOCX)
        assert "openxmlformats" in mime

    def test_mime_type_png(self, asset_service):
        """Test PNG MIME type"""
        assert asset_service._get_mime_type(ContentFormat.PNG) == "image/png"


# =============================================================================
# SINGLETON TESTS
# =============================================================================

class TestSingleton:
    """Test singleton pattern for asset service"""

    def test_get_asset_service_returns_singleton(self):
        """Test get_asset_service returns same instance"""
        with patch('app.services.crewai_asset_service.get_supabase_client'), \
             patch('app.services.crewai_asset_service.get_b2_service'):

            # Reset singleton
            import app.services.crewai_asset_service as module
            module._asset_service = None

            service1 = get_asset_service()
            service2 = get_asset_service()

            assert service1 is service2
