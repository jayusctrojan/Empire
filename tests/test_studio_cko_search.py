"""
Tests for CKO KB Search endpoint
Empire v7.3 - GET /api/studio/cko/search
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.studio_cko_conversation_service import (
    StudioCKOConversationService,
    CKOConfig,
    CKOSource,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_supabase_storage():
    """Mock Supabase storage"""
    mock = Mock()
    mock.supabase = Mock()
    mock.supabase.rpc.return_value = Mock()
    mock.supabase.rpc.return_value.execute.return_value = Mock(data=[])
    return mock


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service"""
    mock = AsyncMock()
    mock.generate_embedding.return_value = Mock(embedding=[0.1] * 768)
    return mock


@pytest.fixture
def mock_query_expansion():
    """Mock query expansion service"""
    mock = AsyncMock()
    mock.expand_query.return_value = Mock(
        expanded_queries=["test query", "test search", "test lookup"]
    )
    return mock


@pytest.fixture
def cko_service(mock_supabase_storage, mock_embedding_service, mock_query_expansion):
    """Create a CKO service with mocked dependencies"""
    with patch("app.services.studio_cko_conversation_service.get_supabase_storage", return_value=mock_supabase_storage), \
         patch("app.services.studio_cko_conversation_service.get_embedding_service", return_value=mock_embedding_service), \
         patch("app.services.studio_cko_conversation_service.get_query_expansion_service", return_value=mock_query_expansion), \
         patch("app.services.studio_cko_conversation_service.get_llm_client"):
        service = StudioCKOConversationService()
    return service


# =============================================================================
# Test search() method
# =============================================================================

class TestCKOSearch:
    """Test CKO search endpoint logic"""

    @pytest.mark.asyncio
    async def test_search_returns_sources(self, cko_service, mock_supabase_storage):
        """Test that search returns a list of CKOSource objects"""
        # Mock vector_search RPC to return results
        mock_supabase_storage.supabase.rpc.return_value.execute.return_value = Mock(data=[
            {
                "document_id": "doc-1",
                "content": "Revenue grew 15% year over year",
                "similarity": 0.85,
                "metadata": {
                    "title": "Q4 Financial Report",
                    "department": "finance",
                    "file_type": "pdf",
                    "page_number": 3,
                },
                "chunk_index": 0,
            },
            {
                "document_id": "doc-2",
                "content": "Market analysis shows strong growth",
                "similarity": 0.72,
                "metadata": {
                    "title": "Market Analysis 2025",
                    "department": "research",
                    "file_type": "pdf",
                },
                "chunk_index": 1,
            },
        ])

        results = await cko_service.search("quarterly revenue report")

        assert len(results) > 0
        assert all(isinstance(s, CKOSource) for s in results)
        assert results[0].relevance_score >= results[-1].relevance_score

    @pytest.mark.asyncio
    async def test_search_empty_results(self, cko_service, mock_supabase_storage):
        """Test that search returns empty list when no matches"""
        mock_supabase_storage.supabase.rpc.return_value.execute.return_value = Mock(data=[])

        results = await cko_service.search("completely unrelated gibberish query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, cko_service, mock_supabase_storage):
        """Test that search respects the limit parameter"""
        # Return many results
        many_results = [
            {
                "document_id": f"doc-{i}",
                "content": f"Content {i}",
                "similarity": 0.9 - (i * 0.05),
                "metadata": {"title": f"Doc {i}"},
                "chunk_index": 0,
            }
            for i in range(20)
        ]
        mock_supabase_storage.supabase.rpc.return_value.execute.return_value = Mock(data=many_results)

        results = await cko_service.search("test query", limit=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_uses_query_expansion(self, cko_service, mock_query_expansion, mock_supabase_storage):
        """Test that search uses query expansion when enabled"""
        mock_supabase_storage.supabase.rpc.return_value.execute.return_value = Mock(data=[])

        await cko_service.search("test query")

        mock_query_expansion.expand_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_fallback_on_expansion_failure(self, cko_service, mock_query_expansion, mock_supabase_storage, mock_embedding_service):
        """Test that search falls back to original query if expansion fails"""
        mock_query_expansion.expand_query.side_effect = Exception("expansion failed")
        mock_supabase_storage.supabase.rpc.return_value.execute.return_value = Mock(data=[])

        # Should not raise — falls back gracefully
        results = await cko_service.search("test query")

        assert results == []
        # Embedding was still called with the original query
        mock_embedding_service.generate_embedding.assert_called()

    @pytest.mark.asyncio
    async def test_search_source_fields(self, cko_service, mock_supabase_storage):
        """Test that source fields are populated correctly"""
        mock_supabase_storage.supabase.rpc.return_value.execute.return_value = Mock(data=[
            {
                "document_id": "doc-abc",
                "content": "Test content snippet here",
                "similarity": 0.91,
                "metadata": {
                    "title": "Test Document",
                    "department": "legal",
                    "file_type": "docx",
                    "page_number": 7,
                },
                "chunk_index": 2,
            },
        ])

        results = await cko_service.search("test")

        assert len(results) == 1
        src = results[0]
        assert src.doc_id == "doc-abc"
        assert src.title == "Test Document"
        assert src.department == "legal"
        assert src.document_type == "docx"
        assert src.page_number == 7
        assert src.chunk_index == 2
        assert src.relevance_score == 0.91
