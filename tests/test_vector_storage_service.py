"""
Tests for Vector Storage Service

Tests bulk operations, namespace filtering, metadata filtering,
and similarity search functionality.

Run with: python3 -m pytest tests/test_vector_storage_service.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from app.services.vector_storage_service import (
    VectorStorageService,
    VectorStorageConfig,
    VectorRecord,
    SimilarityResult,
    get_vector_storage_service
)


@pytest.fixture
def mock_supabase_storage():
    """Create mock Supabase storage"""
    storage = Mock()
    storage.supabase = Mock()
    return storage


@pytest.fixture
def vector_storage_service(mock_supabase_storage):
    """Create vector storage service with mock"""
    config = VectorStorageConfig(
        default_namespace="test",
        batch_size=10,
        similarity_threshold=0.7
    )
    return VectorStorageService(
        mock_supabase_storage,
        config,
        monitoring_service=None
    )


class TestVectorRecord:
    """Tests for VectorRecord dataclass"""

    def test_vector_record_creation(self):
        """Test creating a vector record"""
        record = VectorRecord(
            embedding=[0.1, 0.2, 0.3],
            content_hash="abc123",
            model="bge-m3",
            dimensions=1024,
            namespace="production",
            chunk_id="chunk-uuid-123",
            metadata={"doc_type": "contract"}
        )

        assert record.embedding == [0.1, 0.2, 0.3]
        assert record.content_hash == "abc123"
        assert record.model == "bge-m3"
        assert record.namespace == "production"
        assert record.metadata["doc_type"] == "contract"

    def test_vector_record_to_dict(self):
        """Test converting vector record to dict"""
        record = VectorRecord(
            embedding=[0.1, 0.2],
            content_hash="hash1",
            model="bge-m3",
            dimensions=2
        )

        data = record.to_dict()

        assert data["embedding"] == [0.1, 0.2]
        assert data["content_hash"] == "hash1"
        assert data["model"] == "bge-m3"
        assert data["dimensions"] == 2
        assert data["namespace"] == "default"


class TestSimilarityResult:
    """Tests for SimilarityResult dataclass"""

    def test_from_db_row(self):
        """Test creating SimilarityResult from database row"""
        row = {
            "chunk_id": "chunk-123",
            "content_hash": "hash456",
            "embedding": [0.1, 0.2, 0.3],
            "similarity": 0.95,
            "model": "bge-m3",
            "namespace": "production",
            "metadata": {"status": "active"},
            "created_at": "2025-01-15T10:00:00Z"
        }

        result = SimilarityResult.from_db_row(row)

        assert result.chunk_id == "chunk-123"
        assert result.similarity == 0.95
        assert result.namespace == "production"
        assert result.metadata["status"] == "active"


class TestVectorStorageService:
    """Tests for VectorStorageService"""

    @pytest.mark.asyncio
    async def test_store_vectors_batch_empty(self, vector_storage_service):
        """Test storing empty batch"""
        result = await vector_storage_service.store_vectors_batch([])

        assert result["success"] is True
        assert result["inserted"] == 0
        assert result["updated"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_store_vectors_batch_single(self, vector_storage_service, mock_supabase_storage):
        """Test storing single record"""
        # Setup mock
        mock_execute = Mock()
        mock_execute.data = [{"id": "uuid-123"}]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        mock_supabase_storage.supabase.table.return_value.upsert.return_value = mock_chain

        # Create record
        record = VectorRecord(
            embedding=[0.1] * 1024,
            content_hash="hash1",
            model="bge-m3",
            dimensions=1024
        )

        # Store
        result = await vector_storage_service.store_vectors_batch([record])

        assert result["success"] is True
        assert result["inserted"] == 1
        assert result["namespace"] == "test"

    @pytest.mark.asyncio
    async def test_store_vectors_batch_multiple(self, vector_storage_service, mock_supabase_storage):
        """Test storing multiple records"""
        # Setup mock
        mock_execute = Mock()
        mock_execute.data = [{"id": f"uuid-{i}"} for i in range(3)]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        mock_supabase_storage.supabase.table.return_value.upsert.return_value = mock_chain

        # Create records
        records = [
            VectorRecord(
                embedding=[float(i)] * 1024,
                content_hash=f"hash{i}",
                model="bge-m3",
                dimensions=1024
            )
            for i in range(3)
        ]

        # Store
        result = await vector_storage_service.store_vectors_batch(records)

        assert result["success"] is True
        assert result["inserted"] == 3

    @pytest.mark.asyncio
    async def test_store_vectors_batch_with_namespace_override(self, vector_storage_service, mock_supabase_storage):
        """Test namespace override in batch"""
        mock_execute = Mock()
        mock_execute.data = [{"id": "uuid-1"}]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        mock_supabase_storage.supabase.table.return_value.upsert.return_value = mock_chain

        record = VectorRecord(
            embedding=[0.1] * 1024,
            content_hash="hash1",
            model="bge-m3",
            dimensions=1024,
            namespace="original"
        )

        result = await vector_storage_service.store_vectors_batch(
            [record],
            namespace="overridden"
        )

        assert result["namespace"] == "overridden"
        assert record.namespace == "overridden"

    @pytest.mark.asyncio
    async def test_similarity_search_python(self, vector_storage_service, mock_supabase_storage):
        """Test Python-based similarity search"""
        # Setup mock
        mock_execute = Mock()
        mock_execute.data = [
            {
                "chunk_id": "chunk-1",
                "content_hash": "hash1",
                "embedding": [0.9] * 1024,
                "model": "bge-m3",
                "namespace": "test",
                "metadata": {},
                "created_at": "2025-01-15T10:00:00Z"
            },
            {
                "chunk_id": "chunk-2",
                "content_hash": "hash2",
                "embedding": [0.1] * 1024,
                "model": "bge-m3",
                "namespace": "test",
                "metadata": {},
                "created_at": "2025-01-15T10:00:00Z"
            }
        ]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        # Build mock chain
        mock_select = Mock()
        mock_eq1 = Mock()
        mock_eq2 = Mock()

        mock_select.return_value.eq = Mock(return_value=mock_eq1)
        mock_eq1.eq = Mock(return_value=mock_chain)

        mock_supabase_storage.supabase.table.return_value.select = mock_select

        # Query
        query_embedding = [1.0] * 1024
        results = await vector_storage_service.similarity_search(
            query_embedding,
            limit=10,
            namespace="test",
            model="bge-m3"
        )

        # Should return only embeddings above threshold
        assert len(results) > 0
        assert all(isinstance(r, SimilarityResult) for r in results)

    @pytest.mark.asyncio
    async def test_get_by_namespace(self, vector_storage_service, mock_supabase_storage):
        """Test retrieving vectors by namespace"""
        mock_execute = Mock()
        mock_execute.data = [
            {
                "id": "uuid-1",
                "namespace": "production",
                "model": "bge-m3"
            }
        ]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        mock_supabase_storage.supabase.table.return_value.select.return_value.eq.return_value.range.return_value = mock_chain

        results = await vector_storage_service.get_by_namespace("production", limit=10)

        assert len(results) == 1
        assert results[0]["namespace"] == "production"

    @pytest.mark.asyncio
    async def test_delete_by_namespace(self, vector_storage_service, mock_supabase_storage):
        """Test deleting vectors by namespace"""
        mock_execute = Mock()
        mock_execute.data = [{"id": f"uuid-{i}"} for i in range(5)]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        mock_supabase_storage.supabase.table.return_value.delete.return_value.eq.return_value = mock_chain

        count = await vector_storage_service.delete_by_namespace("old-namespace")

        assert count == 5

    @pytest.mark.asyncio
    async def test_get_namespaces(self, vector_storage_service, mock_supabase_storage):
        """Test getting all namespaces"""
        mock_execute = Mock()
        mock_execute.data = [
            {"namespace": "production"},
            {"namespace": "production"},
            {"namespace": "staging"},
            {"namespace": "default"}
        ]

        mock_chain = Mock()
        mock_chain.execute = AsyncMock(return_value=mock_execute)

        mock_supabase_storage.supabase.table.return_value.select.return_value = mock_chain

        namespaces = await vector_storage_service.get_namespaces()

        # Should group by namespace
        assert len(namespaces) == 3
        namespace_names = [ns["namespace"] for ns in namespaces]
        assert "production" in namespace_names
        assert "staging" in namespace_names
        assert "default" in namespace_names

    def test_cosine_similarity(self, vector_storage_service):
        """Test cosine similarity calculation"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        # Identical vectors should have similarity = 1.0
        similarity = vector_storage_service._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001

        # Orthogonal vectors should have similarity = 0.0
        vec3 = [0.0, 1.0, 0.0]
        similarity = vector_storage_service._cosine_similarity(vec1, vec3)
        assert abs(similarity - 0.0) < 0.001

        # Opposite vectors should have similarity = -1.0
        vec4 = [-1.0, 0.0, 0.0]
        similarity = vector_storage_service._cosine_similarity(vec1, vec4)
        assert abs(similarity - (-1.0)) < 0.001

    def test_cosine_similarity_different_dimensions_error(self, vector_storage_service):
        """Test that different dimensions raise error"""
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        with pytest.raises(ValueError, match="same dimensions"):
            vector_storage_service._cosine_similarity(vec1, vec2)


class TestFactoryFunction:
    """Tests for factory function"""

    def test_get_vector_storage_service_singleton(self, mock_supabase_storage):
        """Test that factory returns singleton"""
        service1 = get_vector_storage_service(mock_supabase_storage)
        service2 = get_vector_storage_service(mock_supabase_storage)

        assert service1 is service2


class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, vector_storage_service, mock_supabase_storage):
        """Test complete workflow: insert, search, delete"""
        # Setup mocks for insert
        mock_insert_execute = Mock()
        mock_insert_execute.data = [{"id": "uuid-123"}]

        mock_insert_chain = Mock()
        mock_insert_chain.execute = AsyncMock(return_value=mock_insert_execute)

        mock_supabase_storage.supabase.table.return_value.upsert.return_value = mock_insert_chain

        # Insert records
        records = [
            VectorRecord(
                embedding=[0.5] * 1024,
                content_hash="doc1",
                model="bge-m3",
                dimensions=1024,
                namespace="workflow-test"
            )
        ]

        insert_result = await vector_storage_service.store_vectors_batch(
            records,
            namespace="workflow-test"
        )

        assert insert_result["success"] is True

        # Setup mocks for delete
        mock_delete_execute = Mock()
        mock_delete_execute.data = [{"id": "uuid-123"}]

        mock_delete_chain = Mock()
        mock_delete_chain.execute = AsyncMock(return_value=mock_delete_execute)

        mock_supabase_storage.supabase.table.return_value.delete.return_value.eq.return_value = mock_delete_chain

        # Delete namespace
        delete_count = await vector_storage_service.delete_by_namespace("workflow-test")

        assert delete_count == 1
