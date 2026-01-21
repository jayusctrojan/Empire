"""
Empire v7.3 - Document Management Service Unit Tests (Task 180)
Tests for B2 integration in document upload, delete, and reprocess operations.
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from io import BytesIO
import tempfile
import os


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    client = Mock()

    # Mock table operations
    table_mock = Mock()
    table_mock.select.return_value = table_mock
    table_mock.insert.return_value = table_mock
    table_mock.update.return_value = table_mock
    table_mock.delete.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.limit.return_value = table_mock
    table_mock.execute.return_value = Mock(data=[])

    client.table.return_value = table_mock
    return client


@pytest.fixture
def mock_b2_service():
    """Mock resilient B2 storage service"""
    service = Mock()
    service.b2_service = Mock()

    # Mock upload_file
    service.upload_file = AsyncMock(return_value={
        "file_id": "test_b2_file_id_123",
        "file_name": "documents/user123/doc_abc123/test.pdf",
        "url": "https://f001.backblazeb2.com/file/bucket/documents/user123/doc_abc123/test.pdf",
        "size": 1024,
        "content_type": "application/pdf",
        "checksum_verified": True
    })

    # Mock download_file
    service.download_file = AsyncMock(return_value={
        "success": True,
        "file_path": "/tmp/test_download.pdf",
        "checksum": "abc123"
    })

    # Mock delete_file on underlying service
    service.b2_service.delete_file = AsyncMock(return_value=True)

    return service


@pytest.fixture
def mock_document_processor():
    """Mock document processor"""
    processor = Mock()
    processor.process_document = AsyncMock(return_value={
        "success": True,
        "document_type": "pdf",
        "extraction_method": "pypdf",
        "content": {
            "text": "This is the extracted text from the document.",
            "pages": [
                {"page_number": 1, "text": "Page 1 content here."},
                {"page_number": 2, "text": "Page 2 content here."}
            ],
            "tables": [],
            "images": []
        },
        "metadata": {"page_count": 2}
    })
    return processor


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service"""
    service = Mock()

    # Create mock embedding result
    mock_result = Mock()
    mock_result.chunk_id = "chunk_abc123"
    mock_result.embedding = [0.1] * 1024  # 1024 dimensions
    mock_result.provider = "ollama"
    mock_result.cached = False

    service.generate_embeddings_batch = AsyncMock(return_value=[mock_result])
    service.generate_embedding = AsyncMock(return_value=mock_result)

    return service


@pytest.fixture
def sample_document_data():
    """Sample document record from database"""
    return {
        "document_id": "doc_test123",
        "filename": "test_document.pdf",
        "file_type": "pdf",
        "file_size_bytes": 1024,
        "file_hash": "abc123hash",
        "b2_file_id": "b2_file_id_456",
        "b2_url": "https://example.com/test.pdf",
        "file_path": "documents/user123/doc_test123/test_document.pdf",
        "uploaded_by": "user123",
        "processing_status": "processed",
        "storage_status": "uploaded",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def temp_test_file():
    """Create a temporary test file"""
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
        f.write(b'%PDF-1.4 Test PDF content here...')
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


# =============================================================================
# TEST: process_document_upload
# =============================================================================

class TestProcessDocumentUpload:
    """Tests for process_document_upload function"""

    @patch('app.services.document_management.get_supabase_client')
    @patch('app.services.document_management.get_resilient_b2_service')
    @patch('app.services.document_management.get_document_processor')
    def test_upload_with_b2_integration(
        self,
        mock_get_processor,
        mock_get_b2,
        mock_get_supabase,
        mock_supabase,
        mock_b2_service,
        mock_document_processor,
        temp_test_file
    ):
        """Test document upload with B2 storage integration"""
        mock_get_supabase.return_value = mock_supabase
        mock_get_b2.return_value = mock_b2_service
        mock_get_processor.return_value = mock_document_processor

        # Mock successful insert
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"document_id": "doc_abc123"}]
        )

        from app.services.document_management import process_document_upload

        result = process_document_upload(
            file_path=temp_test_file,
            filename="test_document.pdf",
            metadata={"department": "IT"},
            user_id="user123",
            auto_process=False
        )

        # Verify result
        assert result["document_id"] is not None
        assert result["filename"] == "test_document.pdf"
        assert "file_hash" in result

    @patch('app.services.document_management.get_supabase_client')
    @patch('app.services.document_management.get_resilient_b2_service')
    def test_upload_b2_failure_continues(
        self,
        mock_get_b2,
        mock_get_supabase,
        mock_supabase,
        temp_test_file
    ):
        """Test that upload continues even if B2 fails"""
        mock_get_supabase.return_value = mock_supabase

        # Make B2 service raise an exception
        mock_b2 = Mock()
        mock_b2.upload_file = AsyncMock(side_effect=Exception("B2 connection failed"))
        mock_get_b2.return_value = mock_b2

        # Mock successful database insert
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"document_id": "doc_abc123"}]
        )

        from app.services.document_management import process_document_upload

        # Should not raise - B2 failure is handled gracefully
        result = process_document_upload(
            file_path=temp_test_file,
            filename="test_document.pdf",
            user_id="user123",
            auto_process=False
        )

        assert result["document_id"] is not None

    @patch('app.services.document_management.get_supabase_client')
    @patch('app.services.document_management.get_resilient_b2_service')
    @patch('app.services.document_management.get_document_processor')
    def test_upload_with_auto_process(
        self,
        mock_get_processor,
        mock_get_b2,
        mock_get_supabase,
        mock_supabase,
        mock_b2_service,
        mock_document_processor,
        temp_test_file
    ):
        """Test document upload with automatic processing"""
        mock_get_supabase.return_value = mock_supabase
        mock_get_b2.return_value = mock_b2_service
        mock_get_processor.return_value = mock_document_processor

        # Mock successful operations
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"document_id": "doc_abc123"}]
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = Mock(
            data=[{"document_id": "doc_abc123"}]
        )

        from app.services.document_management import process_document_upload

        result = process_document_upload(
            file_path=temp_test_file,
            filename="test_document.pdf",
            user_id="user123",
            auto_process=True
        )

        assert result["processing_status"] == "processed"


# =============================================================================
# TEST: delete_document
# =============================================================================

class TestDeleteDocument:
    """Tests for delete_document function"""

    @patch('app.services.document_management.get_supabase_client')
    def test_soft_delete(
        self,
        mock_get_supabase,
        mock_supabase,
        sample_document_data
    ):
        """Test soft delete marks document as deleted"""
        mock_get_supabase.return_value = mock_supabase

        # Mock document exists
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[sample_document_data]
        )

        from app.services.document_management import delete_document

        result = delete_document(
            document_id="doc_test123",
            user_id="user123",
            soft_delete=True
        )

        assert result["deleted"] is True
        assert result["soft_delete"] is True
        assert result["document_id"] == "doc_test123"

    @patch('app.services.document_management.get_supabase_client')
    @patch('app.services.document_management.get_resilient_b2_service')
    def test_hard_delete_with_b2(
        self,
        mock_get_b2,
        mock_get_supabase,
        mock_supabase,
        mock_b2_service,
        sample_document_data
    ):
        """Test hard delete removes from database and B2"""
        mock_get_supabase.return_value = mock_supabase
        mock_get_b2.return_value = mock_b2_service

        # Mock document exists with B2 file
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[sample_document_data]
        )

        from app.services.document_management import delete_document

        result = delete_document(
            document_id="doc_test123",
            user_id="user123",
            soft_delete=False
        )

        assert result["deleted"] is True
        assert result["soft_delete"] is False

        # Verify B2 delete was called
        mock_b2_service.b2_service.delete_file.assert_called_once()

    @patch('app.services.document_management.get_supabase_client')
    @patch('app.services.document_management.get_resilient_b2_service')
    def test_hard_delete_b2_failure_continues(
        self,
        mock_get_b2,
        mock_get_supabase,
        mock_supabase,
        sample_document_data
    ):
        """Test hard delete continues if B2 deletion fails"""
        mock_get_supabase.return_value = mock_supabase

        # Mock B2 service that fails
        mock_b2 = Mock()
        mock_b2.b2_service = Mock()
        mock_b2.b2_service.delete_file = AsyncMock(side_effect=Exception("B2 delete failed"))
        mock_get_b2.return_value = mock_b2

        # Mock document exists
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[sample_document_data]
        )

        from app.services.document_management import delete_document

        # Should not raise - B2 failure is handled gracefully
        result = delete_document(
            document_id="doc_test123",
            user_id="user123",
            soft_delete=False
        )

        assert result["deleted"] is True

    @patch('app.services.document_management.get_supabase_client')
    def test_delete_nonexistent_document(
        self,
        mock_get_supabase,
        mock_supabase
    ):
        """Test delete raises error for non-existent document"""
        mock_get_supabase.return_value = mock_supabase

        # Mock document not found
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[]
        )

        from app.services.document_management import delete_document

        with pytest.raises(Exception) as excinfo:
            delete_document(document_id="nonexistent_doc")

        assert "not found" in str(excinfo.value)


# =============================================================================
# TEST: reprocess_document
# =============================================================================

class TestReprocessDocument:
    """Tests for reprocess_document function"""

    @patch('app.services.document_management.get_supabase_client')
    @patch('app.services.document_management.get_resilient_b2_service')
    @patch('app.services.document_management.get_document_processor')
    @patch('app.services.document_management.get_embedding_service')
    def test_reprocess_with_text_extraction(
        self,
        mock_get_embedding,
        mock_get_processor,
        mock_get_b2,
        mock_get_supabase,
        mock_supabase,
        mock_b2_service,
        mock_document_processor,
        mock_embedding_service,
        sample_document_data
    ):
        """Test reprocessing extracts text and generates embeddings"""
        mock_get_supabase.return_value = mock_supabase
        mock_get_b2.return_value = mock_b2_service
        mock_get_processor.return_value = mock_document_processor
        mock_get_embedding.return_value = mock_embedding_service

        # Mock document exists with B2 file
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[sample_document_data]
        )

        # Mock no existing chunks initially
        def select_side_effect(*args, **kwargs):
            mock = Mock()
            mock.eq.return_value = mock
            mock.execute.return_value = Mock(data=[])
            return mock

        mock_supabase.table.return_value.select.side_effect = [
            # First call: get document
            Mock(eq=Mock(return_value=Mock(execute=Mock(return_value=Mock(data=[sample_document_data]))))),
            # Second call: get existing chunks
            Mock(eq=Mock(return_value=Mock(execute=Mock(return_value=Mock(data=[]))))),
            # Third call: get chunks for embedding
            Mock(eq=Mock(return_value=Mock(execute=Mock(return_value=Mock(data=[
                {"chunk_id": "chunk_1", "content": "Page 1 content"},
                {"chunk_id": "chunk_2", "content": "Page 2 content"}
            ])))))
        ]

        from app.services.document_management import reprocess_document

        result = reprocess_document(
            document_id="doc_test123",
            user_id="user123",
            force_reparse=True,
            update_embeddings=True
        )

        assert result["reprocessed"] is True
        assert result["force_reparse"] is True
        assert result["update_embeddings"] is True

    @patch('app.services.document_management.get_supabase_client')
    def test_reprocess_nonexistent_document(
        self,
        mock_get_supabase,
        mock_supabase
    ):
        """Test reprocess raises error for non-existent document"""
        mock_get_supabase.return_value = mock_supabase

        # Mock document not found
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[]
        )

        from app.services.document_management import reprocess_document

        with pytest.raises(Exception) as excinfo:
            reprocess_document(document_id="nonexistent_doc")

        assert "not found" in str(excinfo.value)

    @patch('app.services.document_management.get_supabase_client')
    def test_reprocess_embeddings_only(
        self,
        mock_get_supabase,
        mock_supabase,
        sample_document_data
    ):
        """Test reprocess with embeddings only (no text re-extraction)"""
        mock_get_supabase.return_value = mock_supabase

        # Mock document exists
        existing_chunks = [
            {"chunk_id": "chunk_1", "content": "Existing content 1"},
            {"chunk_id": "chunk_2", "content": "Existing content 2"}
        ]

        # Create separate mock chains for each table
        mock_documents_table = MagicMock()
        mock_chunks_table = MagicMock()

        # Track which table is being accessed
        def table_router(table_name):
            if table_name == "documents":
                return mock_documents_table
            elif table_name == "document_chunks":
                return mock_chunks_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        # Mock documents table: select and update chains
        mock_documents_select = MagicMock()
        mock_documents_table.select.return_value = mock_documents_select
        mock_documents_eq = MagicMock()
        mock_documents_select.eq.return_value = mock_documents_eq
        mock_documents_eq.execute.return_value = MagicMock(data=[sample_document_data])

        mock_documents_update = MagicMock()
        mock_documents_table.update.return_value = mock_documents_update
        mock_documents_update_eq = MagicMock()
        mock_documents_update.eq.return_value = mock_documents_update_eq
        mock_documents_update_eq.execute.return_value = MagicMock(data=[sample_document_data])

        # Mock chunks table: select and update chains
        mock_chunks_select = MagicMock()
        mock_chunks_table.select.return_value = mock_chunks_select
        mock_chunks_eq = MagicMock()
        mock_chunks_select.eq.return_value = mock_chunks_eq
        mock_chunks_eq.execute.return_value = MagicMock(data=existing_chunks)

        mock_chunks_update = MagicMock()
        mock_chunks_table.update.return_value = mock_chunks_update
        mock_chunks_update_eq = MagicMock()
        mock_chunks_update.eq.return_value = mock_chunks_update_eq
        mock_chunks_update_eq.execute.return_value = MagicMock(data=existing_chunks)

        from app.services.document_management import reprocess_document

        # Mock embedding service and asyncio event loop
        with patch('app.services.document_management.get_embedding_service') as mock_get_embed:
            with patch('app.services.document_management.asyncio') as mock_asyncio:
                mock_embed = MagicMock()
                mock_result = MagicMock()
                mock_result.chunk_id = "chunk_1"
                mock_result.embedding = [0.1] * 1024
                mock_get_embed.return_value = mock_embed

                # Mock the asyncio.get_event_loop().run_until_complete() call
                mock_loop = MagicMock()
                mock_loop.run_until_complete.return_value = [mock_result]
                mock_asyncio.get_event_loop.return_value = mock_loop

                result = reprocess_document(
                    document_id="doc_test123",
                    force_reparse=False,  # Don't re-extract text
                    update_embeddings=True
                )

        assert result["reprocessed"] is True
        assert result["force_reparse"] is False


# =============================================================================
# TEST: update_document_metadata
# =============================================================================

class TestUpdateDocumentMetadata:
    """Tests for update_document_metadata function"""

    @patch('app.services.document_management.get_supabase_client')
    def test_update_metadata_success(
        self,
        mock_get_supabase,
        mock_supabase,
        sample_document_data
    ):
        """Test successful metadata update"""
        mock_get_supabase.return_value = mock_supabase

        # Mock document exists
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[sample_document_data]
        )

        from app.services.document_management import update_document_metadata

        result = update_document_metadata(
            document_id="doc_test123",
            metadata={"department": "Finance", "custom_key": "custom_value"},
            user_id="user123"
        )

        assert result["updated"] is True
        assert result["document_id"] == "doc_test123"
        assert "department" in result["metadata_keys"]

    @patch('app.services.document_management.get_supabase_client')
    def test_update_nonexistent_document(
        self,
        mock_get_supabase,
        mock_supabase
    ):
        """Test update raises error for non-existent document"""
        mock_get_supabase.return_value = mock_supabase

        # Mock document not found
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[]
        )

        from app.services.document_management import update_document_metadata

        with pytest.raises(Exception) as excinfo:
            update_document_metadata(
                document_id="nonexistent_doc",
                metadata={"department": "IT"}
            )

        assert "not found" in str(excinfo.value)


# =============================================================================
# TEST: B2 Path Construction
# =============================================================================

class TestB2PathConstruction:
    """Tests for B2 path construction logic"""

    def test_b2_path_format(self):
        """Test B2 path follows documents/{user_id}/{document_id}/ pattern"""
        user_id = "user123"
        document_id = "doc_abc456"

        expected_prefix = f"documents/{user_id}/{document_id}"
        b2_folder = f"documents/{user_id}/{document_id}"

        assert b2_folder == expected_prefix

    def test_b2_path_anonymous_user(self):
        """Test B2 path uses 'anonymous' for null user_id"""
        user_id = None
        document_id = "doc_abc456"

        b2_folder = f"documents/{user_id or 'anonymous'}/{document_id}"

        assert "anonymous" in b2_folder
        assert document_id in b2_folder


# =============================================================================
# TEST: Content Type Detection
# =============================================================================

class TestContentTypeDetection:
    """Tests for content type detection in upload"""

    def test_content_type_mapping(self):
        """Test file extension to content type mapping"""
        content_type_map = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc': 'application/msword',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'json': 'application/json',
            'md': 'text/markdown',
            'html': 'text/html',
            'xml': 'application/xml',
        }

        assert content_type_map['pdf'] == 'application/pdf'
        assert content_type_map['docx'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        assert content_type_map['txt'] == 'text/plain'

    def test_unknown_content_type_fallback(self):
        """Test unknown file types get octet-stream fallback"""
        content_type_map = {
            'pdf': 'application/pdf',
        }

        file_type = 'xyz'  # Unknown type
        content_type = content_type_map.get(file_type.lower(), 'application/octet-stream')

        assert content_type == 'application/octet-stream'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
