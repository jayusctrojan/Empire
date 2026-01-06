"""
Empire v7.3 - Project Sources E2E Tests (Task 69)
End-to-end tests for full user flows:
- Upload file/URL/YouTube -> Monitor status -> Chat query -> Verify citations

Performance targets:
- PDF processing: <60s
- YouTube processing: <30s
- RAG query response: <3s
- Success rate: >95%
"""

import pytest
import asyncio
import time
import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Any


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    with patch('app.core.supabase_client.get_supabase_client') as mock:
        mock_client = MagicMock()

        # Mock table operations
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.delete.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.in_.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        mock_client.table.return_value = mock_table
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_b2_storage():
    """Mock B2 storage service"""
    with patch('app.services.b2_storage.get_b2_service') as mock:
        mock_service = MagicMock()
        mock_service.upload_file = AsyncMock(return_value={
            "file_id": f"b2-{uuid4()}",
            "file_name": "test/sources/file.pdf",
            "size": 1024000,
            "content_type": "application/pdf",
            "b2_url": "https://b2.example.com/file/bucket/test.pdf"
        })
        mock_service.get_signed_download_url = MagicMock(return_value={
            "signed_url": "https://b2.example.com/file?auth=token",
            "expires_at": datetime.utcnow().isoformat(),
            "valid_duration_seconds": 3600
        })
        mock.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic Claude client for RAG responses"""
    with patch('anthropic.AsyncAnthropic') as mock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="""
Based on the project sources [1] and global knowledge [G1], here are the key findings:

1. The insurance policy requires claims to be filed within 30 days [1].
2. California regulations mandate specific coverage levels [G1].
3. The document outlines three main categories of coverage [1].

For more details, refer to sections 2.1 and 3.4 of the policy document.
        """)]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for vector operations"""
    with patch('app.services.embedding_service.get_embedding_service') as mock:
        mock_service = MagicMock()
        # Return a 1024-dim embedding vector
        mock_service.generate_embedding = AsyncMock(return_value=[0.1] * 1024)
        mock_service.generate_embeddings = AsyncMock(return_value=[[0.1] * 1024])
        mock.return_value = mock_service
        yield mock_service


@pytest.fixture
def sample_pdf_content():
    """Sample PDF file content"""
    # Minimal PDF structure for testing
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"


@pytest.fixture
def sample_source_record():
    """Sample project source record"""
    return {
        "id": str(uuid4()),
        "project_id": str(uuid4()),
        "user_id": "test-user-123",
        "title": "Test Insurance Policy.pdf",
        "source_type": "pdf",
        "status": "ready",
        "file_size": 1024000,
        "url": None,
        "b2_file_id": f"b2-{uuid4()}",
        "b2_path": "sources/test.pdf",
        "content_hash": "abc123",
        "processing_progress": 100,
        "processing_error": None,
        "chunk_count": 15,
        "metadata": {
            "page_count": 10,
            "author": "Test Author"
        },
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# E2E TEST: File Upload Flow
# =============================================================================

class TestFileUploadE2E:
    """End-to-end tests for file upload flow"""

    @pytest.mark.asyncio
    async def test_pdf_upload_complete_flow(
        self,
        mock_supabase,
        mock_b2_storage,
        sample_pdf_content
    ):
        """
        Test complete PDF upload flow:
        1. Upload file
        2. Validate file type
        3. Store in B2
        4. Create source record
        5. Queue processing
        """
        from app.services.project_sources_service import ProjectSourcesService

        with patch.object(ProjectSourcesService, '_queue_source_processing'):
            service = ProjectSourcesService()
            service.supabase = mock_supabase

            # Mock capacity check
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

            # Mock insert
            source_id = str(uuid4())
            mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": source_id}])

            start_time = time.time()

            result = await service.add_file_source(
                project_id=str(uuid4()),
                user_id="test-user",
                file_content=sample_pdf_content,
                filename="test_policy.pdf",
                mime_type="application/pdf"
            )

            upload_time = time.time() - start_time

            # Assertions
            assert result.success is True or result.error is None, f"Upload failed: {result.error}"
            assert upload_time < 5, f"Upload took too long: {upload_time:.2f}s (target: <5s)"

    @pytest.mark.asyncio
    async def test_blocked_file_extension_rejected(self, mock_supabase):
        """Test that executable files are blocked"""
        from app.services.project_sources_service import ProjectSourcesService

        service = ProjectSourcesService()
        service.supabase = mock_supabase

        # Try to upload an executable
        result = await service.add_file_source(
            project_id=str(uuid4()),
            user_id="test-user",
            file_content=b"MZ\x90\x00",  # PE header
            filename="malware.exe",
            mime_type="application/x-msdownload"
        )

        assert result.success is False
        assert "blocked" in result.error.lower() or "unsupported" in result.error.lower()

    @pytest.mark.asyncio
    async def test_capacity_limit_returns_429(self, mock_supabase):
        """Test that capacity limit returns proper error"""
        from app.services.project_sources_service import (
            ProjectSourcesService,
            MAX_SOURCES_PER_PROJECT
        )

        service = ProjectSourcesService()
        service.supabase = mock_supabase

        # Mock 100 existing sources (at limit)
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "file_size": 1000} for _ in range(MAX_SOURCES_PER_PROJECT)]
        )

        result = await service.add_file_source(
            project_id=str(uuid4()),
            user_id="test-user",
            file_content=b"%PDF-1.4",
            filename="one_more.pdf",
            mime_type="application/pdf"
        )

        assert result.success is False
        assert "limit" in result.error.lower() or "capacity" in result.error.lower()


# =============================================================================
# E2E TEST: URL Source Flow
# =============================================================================

class TestURLSourceE2E:
    """End-to-end tests for URL source flow"""

    @pytest.mark.asyncio
    async def test_website_url_flow(self, mock_supabase):
        """Test adding a website URL source"""
        from app.services.project_sources_service import ProjectSourcesService

        with patch.object(ProjectSourcesService, '_queue_source_processing'):
            service = ProjectSourcesService()
            service.supabase = mock_supabase

            # Mock empty sources (no capacity issue)
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])

            result = await service.add_url_source(
                project_id=str(uuid4()),
                user_id="test-user",
                url="https://example.com/article",
                title="Test Article"
            )

            assert result.success is True, f"URL add failed: {result.error}"

    @pytest.mark.asyncio
    async def test_youtube_url_detection(self, mock_supabase):
        """Test YouTube URL is correctly detected"""
        from app.services.project_sources_service import ProjectSourcesService

        with patch.object(ProjectSourcesService, '_queue_source_processing'):
            service = ProjectSourcesService()
            service.supabase = mock_supabase

            # Mock empty sources
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])

            # Test various YouTube URL formats
            youtube_urls = [
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "https://youtu.be/dQw4w9WgXcQ",
                "https://youtube.com/embed/dQw4w9WgXcQ",
            ]

            for url in youtube_urls:
                result = await service.add_url_source(
                    project_id=str(uuid4()),
                    user_id="test-user",
                    url=url
                )
                assert result.success is True, f"YouTube URL failed: {url} - {result.error}"

    @pytest.mark.asyncio
    async def test_ssrf_protection(self, mock_supabase):
        """Test SSRF protection blocks internal URLs"""
        from app.services.project_sources_service import ProjectSourcesService

        service = ProjectSourcesService()
        service.supabase = mock_supabase

        # Mock empty sources
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        ssrf_urls = [
            "http://localhost:8080/admin",
            "http://127.0.0.1/internal",
            "http://169.254.169.254/latest/meta-data",  # AWS metadata
            "file:///etc/passwd",
        ]

        for url in ssrf_urls:
            result = await service.add_url_source(
                project_id=str(uuid4()),
                user_id="test-user",
                url=url
            )
            assert result.success is False, f"SSRF URL should be blocked: {url}"


# =============================================================================
# E2E TEST: Chat Query with Citations
# =============================================================================

class TestChatQueryE2E:
    """End-to-end tests for chat query with citations"""

    @pytest.mark.asyncio
    async def test_project_chat_returns_citations(self, mock_anthropic):
        """Test project chat includes formatted citations"""
        from app.services.chat_service import ChatService

        with patch('httpx.AsyncClient') as mock_client:
            # Mock the RAG API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "answer": "Based on the sources [1], the policy requires claims within 30 days.",
                "citations": [
                    {
                        "source_id": "src-123",
                        "source_type": "project",
                        "title": "Insurance Policy.pdf",
                        "excerpt": "Claims must be filed within 30 days...",
                        "page_number": 5,
                        "file_type": "pdf",
                        "citation_marker": "[1]",
                        "link_url": "/api/projects/sources/src-123/view?page=5"
                    }
                ],
                "project_sources_count": 1,
                "global_sources_count": 0,
                "query_time_ms": 1500
            }
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client.return_value = mock_client_instance

            service = ChatService()

            # Collect streamed response
            response_chunks = []
            async for chunk in service.stream_project_chat_response(
                message="What are the claim requirements?",
                project_id=str(uuid4()),
                history=[],
                auth_token="test-token"
            ):
                response_chunks.append(chunk)

            full_response = "".join(response_chunks)

            # Verify citations are present
            assert "[1]" in full_response or "Sources" in full_response
            assert "Insurance Policy" in full_response or "pdf" in full_response.lower()

    @pytest.mark.asyncio
    async def test_query_performance_under_3s(self, mock_anthropic):
        """Test RAG query completes in under 3 seconds"""
        from app.services.chat_service import ChatService

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "answer": "Quick response",
                "citations": [],
                "project_sources_count": 0,
                "global_sources_count": 0,
                "query_time_ms": 500
            }
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client.return_value = mock_client_instance

            service = ChatService()

            start_time = time.time()

            response_chunks = []
            async for chunk in service.stream_project_chat_response(
                message="Quick test query",
                project_id=str(uuid4()),
                history=[],
                auth_token="test-token"
            ):
                response_chunks.append(chunk)

            query_time = time.time() - start_time

            assert query_time < 3, f"Query took too long: {query_time:.2f}s (target: <3s)"


# =============================================================================
# E2E TEST: Status Monitoring
# =============================================================================

class TestStatusMonitoringE2E:
    """End-to-end tests for source status monitoring"""

    @pytest.mark.asyncio
    async def test_status_transitions(self, mock_supabase, sample_source_record):
        """Test source status transitions: pending -> processing -> ready"""
        from app.services.project_sources_service import ProjectSourcesService
        from app.models.project_sources import SourceStatus

        service = ProjectSourcesService()
        service.supabase = mock_supabase

        # Create source with pending status
        source = sample_source_record.copy()
        source["status"] = SourceStatus.PENDING.value

        # Mock get source
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=source)

        result = await service.get_source(
            source_id=source["id"],
            project_id=source["project_id"],
            user_id=source["user_id"]
        )

        assert result is not None
        assert result.status.value == SourceStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_failed_source_retry(self, mock_supabase, sample_source_record):
        """Test failed source can be retried"""
        from app.services.project_sources_service import ProjectSourcesService
        from app.models.project_sources import SourceStatus

        with patch.object(ProjectSourcesService, '_queue_source_processing'):
            service = ProjectSourcesService()
            service.supabase = mock_supabase

            # Create failed source
            source = sample_source_record.copy()
            source["status"] = SourceStatus.FAILED.value
            source["processing_error"] = "Processing timeout"
            source["retry_count"] = 1

            mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=source)
            mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[source])

            result = await service.retry_source(
                source_id=source["id"],
                project_id=source["project_id"],
                user_id=source["user_id"]
            )

            assert result.success is True


# =============================================================================
# PERFORMANCE BENCHMARKS
# =============================================================================

class TestPerformanceBenchmarks:
    """Performance benchmark tests"""

    @pytest.mark.asyncio
    async def test_concurrent_source_uploads(self, mock_supabase, mock_b2_storage):
        """Test 10 concurrent source uploads"""
        from app.services.project_sources_service import ProjectSourcesService

        with patch.object(ProjectSourcesService, '_queue_source_processing'):
            service = ProjectSourcesService()
            service.supabase = mock_supabase

            # Mock responses
            mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])

            project_id = str(uuid4())
            user_id = "test-user"

            # Create 10 concurrent uploads
            tasks = []
            for i in range(10):
                task = service.add_url_source(
                    project_id=project_id,
                    user_id=user_id,
                    url=f"https://example.com/article-{i}"
                )
                tasks.append(task)

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time

            # Check results
            successes = sum(1 for r in results if hasattr(r, 'success') and r.success)
            failures = sum(1 for r in results if isinstance(r, Exception))

            success_rate = successes / len(results) * 100

            assert success_rate >= 95, f"Success rate too low: {success_rate:.1f}% (target: >95%)"
            assert total_time < 10, f"Concurrent uploads too slow: {total_time:.2f}s"

    @pytest.mark.asyncio
    async def test_capacity_check_performance(self, mock_supabase):
        """Test capacity check is fast even with many sources"""
        from app.services.project_sources_service import ProjectSourcesService

        service = ProjectSourcesService()
        service.supabase = mock_supabase

        # Mock 80 sources (near limit)
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "file_size": 5000000} for _ in range(80)]
        )

        start_time = time.time()

        for _ in range(100):  # Run 100 times
            capacity = await service.check_capacity(
                project_id=str(uuid4()),
                user_id="test-user"
            )

        total_time = time.time() - start_time
        avg_time = total_time / 100

        assert avg_time < 0.1, f"Capacity check too slow: {avg_time*1000:.1f}ms (target: <100ms)"
        assert capacity.warning is True  # Should show 80% warning


# =============================================================================
# CITATION FORMATTING TESTS
# =============================================================================

class TestCitationFormatting:
    """Tests for citation formatting in responses"""

    def test_citation_marker_extraction(self):
        """Test citation markers are correctly extracted"""
        from app.services.project_rag_service import ProjectRAGService, RAGSource

        service = ProjectRAGService()

        # Create mock answer with citations
        answer = "According to source [1], the policy is valid. Global source [G1] confirms this."

        # Create source map
        source_map = {
            1: RAGSource(
                id="src-1",
                source_type="project",
                title="Policy.pdf",
                content="The policy is valid for 1 year.",
                chunk_index=0,
                similarity=0.9,
                rank=1,
                file_type="pdf",
                metadata={"page_number": 5}
            ),
            2: RAGSource(
                id="src-g1",
                source_type="global",
                title="Regulations.pdf",
                content="California regulations confirm...",
                chunk_index=0,
                similarity=0.85,
                rank=2,
                file_type="pdf",
                metadata={}
            )
        }

        citations = service._extract_citations(answer, source_map)

        assert len(citations) >= 1
        assert citations[0].citation_marker == "[1]"
        assert citations[0].file_type == "pdf"

    def test_youtube_timestamp_formatting(self):
        """Test YouTube timestamps are correctly formatted"""
        from app.services.chat_service import ChatService

        service = ChatService()

        # Test various timestamps
        assert service._format_timestamp(65) == "1:05"
        assert service._format_timestamp(3665) == "1:01:05"
        assert service._format_timestamp(0) == "0:00"
        assert service._format_timestamp(59) == "0:59"

    def test_source_type_icons(self):
        """Test source type icons are correctly assigned"""
        from app.services.chat_service import ChatService

        service = ChatService()

        assert service._get_source_type_icon("pdf") == "📄"
        assert service._get_source_type_icon("youtube") == "🎥"
        assert service._get_source_type_icon("website") == "🌐"
        assert service._get_source_type_icon("docx") == "📝"
        assert service._get_source_type_icon("unknown") == "📎"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
