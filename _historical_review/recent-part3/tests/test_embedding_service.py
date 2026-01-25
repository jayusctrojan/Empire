"""
Tests for Embedding Service
Tests BGE-M3 (Ollama), OpenAI embeddings, caching, and batch processing
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List

from app.services.embedding_service import (
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingModel,
    EmbeddingCacheManager,
    EmbeddingResult,
    create_embedding_service,
    get_embedding_service
)


# ============================================================================
# Test Configuration
# ============================================================================

class TestEmbeddingConfig:
    """Test embedding configuration"""

    def test_config_ollama_default(self):
        """Test default Ollama configuration"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3
        )

        assert config.provider == EmbeddingProvider.OLLAMA
        assert config.model == EmbeddingModel.BGE_M3
        assert config.dimensions == 1024
        assert config.batch_size == 100
        assert config.cache_enabled is True

    def test_config_openai(self):
        """Test OpenAI configuration"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=EmbeddingModel.OPENAI_SMALL,
            dimensions=1536,
            batch_size=50,
            openai_api_key="test-key"
        )

        assert config.provider == EmbeddingProvider.OPENAI
        assert config.model == EmbeddingModel.OPENAI_SMALL
        assert config.dimensions == 1536
        assert config.batch_size == 50
        assert config.openai_api_key == "test-key"


# ============================================================================
# Test Cache Manager
# ============================================================================

class TestEmbeddingCacheManager:
    """Test embedding cache manager"""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Test retrieving cached embedding"""
        mock_storage = Mock()

        # Create a proper mock chain for Supabase query
        mock_execute = Mock()
        mock_execute.data = [{
            "embedding": [0.1] * 1024,
            "model": "bge-m3",
            "created_at": "2025-01-15T10:00:00Z"
        }]

        mock_chain = Mock()
        mock_chain.execute.return_value = mock_execute

        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = mock_chain

        cache_manager = EmbeddingCacheManager(mock_storage)
        cached = await cache_manager.get_cached_embedding("test content", "bge-m3")

        assert cached is not None
        assert len(cached) == 1024
        assert cached[0] == 0.1

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss for new content"""
        mock_storage = Mock()

        # Create mock chain for empty result
        mock_execute = Mock()
        mock_execute.data = []

        mock_chain = Mock()
        mock_chain.execute.return_value = mock_execute

        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = mock_chain

        cache_manager = EmbeddingCacheManager(mock_storage)
        cached = await cache_manager.get_cached_embedding("new content", "bge-m3")

        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_embedding(self):
        """Test caching an embedding"""
        mock_storage = AsyncMock()
        mock_storage.supabase.table.return_value.upsert.return_value.execute = AsyncMock()

        cache_manager = EmbeddingCacheManager(mock_storage)
        await cache_manager.cache_embedding(
            "test content",
            [0.1] * 1024,
            "bge-m3",
            chunk_id="chunk-123"
        )

        # Verify upsert was called
        assert mock_storage.supabase.table.return_value.upsert.called

    @pytest.mark.asyncio
    async def test_batch_cache_embeddings(self):
        """Test batch caching multiple embeddings"""
        mock_storage = AsyncMock()
        mock_storage.supabase.table.return_value.upsert.return_value.execute = AsyncMock()

        cache_manager = EmbeddingCacheManager(mock_storage)
        contents = ["content 1", "content 2", "content 3"]
        embeddings = [[0.1] * 1024, [0.2] * 1024, [0.3] * 1024]

        await cache_manager.batch_cache_embeddings(
            contents,
            embeddings,
            "bge-m3"
        )

        # Verify batch upsert was called with 3 entries
        assert mock_storage.supabase.table.return_value.upsert.called

    @pytest.mark.asyncio
    async def test_invalidate_cache(self):
        """Test cache invalidation for a chunk"""
        mock_storage = AsyncMock()
        mock_storage.supabase.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock()

        cache_manager = EmbeddingCacheManager(mock_storage)
        await cache_manager.invalidate_cache("chunk-123")

        # Verify delete was called
        assert mock_storage.supabase.table.return_value.delete.called

    def test_content_hash_consistency(self):
        """Test that same content produces same hash"""
        mock_storage = Mock()
        cache_manager = EmbeddingCacheManager(mock_storage)

        hash1 = cache_manager._hash_content("test content")
        hash2 = cache_manager._hash_content("test content")
        hash3 = cache_manager._hash_content("different content")

        assert hash1 == hash2
        assert hash1 != hash3


# ============================================================================
# Test Embedding Service - Ollama
# ============================================================================

class TestEmbeddingServiceOllama:
    """Test embedding service with Ollama provider"""

    @pytest.mark.asyncio
    async def test_ollama_initialization(self):
        """Test Ollama client initialization"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                service = EmbeddingService(config)
                assert service.ollama_client is not None

    @pytest.mark.asyncio
    async def test_generate_single_embedding_ollama(self):
        """Test generating single embedding with Ollama"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=False
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                # Mock embedder
                mock_embedder = Mock()
                mock_embedder.embed_documents = Mock(return_value=[[0.1] * 1024])
                mock_ollama.return_value = mock_embedder

                service = EmbeddingService(config)

                result = await service.generate_embedding("test content")

                assert isinstance(result, EmbeddingResult)
                assert len(result.embedding) == 1024
                assert result.provider == "ollama"
                assert result.model == "bge-m3"
                assert result.cost == 0.0  # Free for Ollama
                assert result.cached is False

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_ollama(self):
        """Test generating batch embeddings with Ollama"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=False,
            batch_size=10
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                # Mock embedder
                mock_embedder = Mock()
                mock_embedder.embed_documents = Mock(return_value=[[0.1 * i] * 1024 for i in range(25)])
                mock_ollama.return_value = mock_embedder

                service = EmbeddingService(config)

                texts = [f"content {i}" for i in range(25)]
                results = await service.generate_embeddings_batch(texts)

                assert len(results) == 25
                assert all(isinstance(r, EmbeddingResult) for r in results)
                assert all(len(r.embedding) == 1024 for r in results)


# ============================================================================
# Test Embedding Service - OpenAI
# ============================================================================

class TestEmbeddingServiceOpenAI:
    """Test embedding service with OpenAI provider"""

    @pytest.mark.asyncio
    async def test_openai_initialization(self):
        """Test OpenAI client initialization"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=EmbeddingModel.OPENAI_SMALL,
            openai_api_key="test-key"
        )

        with patch('app.services.embedding_service.OPENAI_AVAILABLE', True):
            with patch('app.services.embedding_service.AsyncOpenAI') as mock_openai:
                service = EmbeddingService(config)
                assert service.openai_client is not None

    @pytest.mark.asyncio
    async def test_generate_single_embedding_openai(self):
        """Test generating single embedding with OpenAI"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=EmbeddingModel.OPENAI_SMALL,
            openai_api_key="test-key",
            cache_enabled=False
        )

        with patch('app.services.embedding_service.OPENAI_AVAILABLE', True):
            with patch('app.services.embedding_service.AsyncOpenAI') as mock_openai:
                # Mock OpenAI response
                mock_client = AsyncMock()
                mock_response = Mock()
                mock_response.data = [Mock(embedding=[0.2] * 1536)]
                mock_client.embeddings.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                service = EmbeddingService(config)

                result = await service.generate_embedding("test content")

                assert isinstance(result, EmbeddingResult)
                assert len(result.embedding) == 1536
                assert result.provider == "openai"
                assert result.model == "text-embedding-3-small"
                assert result.cost > 0.0  # OpenAI has cost
                assert result.cached is False

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings_openai(self):
        """Test generating batch embeddings with OpenAI"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=EmbeddingModel.OPENAI_SMALL,
            openai_api_key="test-key",
            cache_enabled=False,
            batch_size=10
        )

        with patch('app.services.embedding_service.OPENAI_AVAILABLE', True):
            with patch('app.services.embedding_service.AsyncOpenAI') as mock_openai:
                # Mock OpenAI response
                mock_client = AsyncMock()
                mock_response = Mock()
                mock_response.data = [Mock(embedding=[0.2 * i] * 1536) for i in range(15)]
                mock_client.embeddings.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                service = EmbeddingService(config)

                texts = [f"content {i}" for i in range(15)]
                results = await service.generate_embeddings_batch(texts)

                assert len(results) == 15
                assert all(isinstance(r, EmbeddingResult) for r in results)
                assert all(len(r.embedding) == 1536 for r in results)


# ============================================================================
# Test Caching Integration
# ============================================================================

class TestCachingIntegration:
    """Test caching integration with embedding service"""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_generation(self):
        """Test that cache hit skips embedding generation"""
        mock_storage = AsyncMock()
        # Mock cache hit
        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"embedding": [0.5] * 1024}]
        )

        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=True
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings'):
                service = EmbeddingService(config, supabase_storage=mock_storage)

                result = await service.generate_embedding("cached content")

                assert result.cached is True
                assert len(result.embedding) == 1024
                assert result.cost == 0.0  # No cost for cached

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_generation(self):
        """Test that cache miss triggers embedding generation"""
        mock_storage = AsyncMock()
        # Mock cache miss
        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        # Mock cache insert
        mock_storage.supabase.table.return_value.upsert.return_value.execute = AsyncMock()

        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=True
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                mock_embedder = Mock()
                mock_embedder.embed_documents = Mock(return_value=[[0.3] * 1024])
                mock_ollama.return_value = mock_embedder

                service = EmbeddingService(config, supabase_storage=mock_storage)

                result = await service.generate_embedding("new content")

                assert result.cached is False
                assert len(result.embedding) == 1024

    @pytest.mark.asyncio
    async def test_batch_with_mixed_cache_hits(self):
        """Test batch processing with some cache hits and misses"""
        mock_storage = AsyncMock()

        # Mock cache: hit for first and third, miss for second
        call_count = [0]

        def mock_cache_response(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] in [1, 3]:  # Cache hits
                return MagicMock(data=[{"embedding": [0.5] * 1024}])
            else:  # Cache miss
                return MagicMock(data=[])

        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute = mock_cache_response
        mock_storage.supabase.table.return_value.upsert.return_value.execute = AsyncMock()

        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=True,
            batch_size=10
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                mock_embedder = Mock()
                mock_embedder.embed_documents = Mock(return_value=[[0.3] * 1024])
                mock_ollama.return_value = mock_embedder

                service = EmbeddingService(config, supabase_storage=mock_storage)

                texts = ["content 1", "content 2", "content 3"]
                results = await service.generate_embeddings_batch(texts)

                assert len(results) == 3
                # First and third should be cached
                assert results[0].cached is True
                assert results[1].cached is False  # Generated
                assert results[2].cached is True


# ============================================================================
# Test Monitoring Integration
# ============================================================================

class TestMonitoringIntegration:
    """Test monitoring integration with embedding service"""

    @pytest.mark.asyncio
    async def test_monitoring_records_generation(self):
        """Test that monitoring service records embedding generation"""
        mock_monitoring = AsyncMock()
        mock_monitoring.record_embedding_generation = AsyncMock()

        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=False
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                mock_embedder = Mock()
                mock_embedder.embed_documents = Mock(return_value=[[0.1] * 1024])
                mock_ollama.return_value = mock_embedder

                service = EmbeddingService(config, monitoring_service=mock_monitoring)

                await service.generate_embedding("test content")

                # Verify monitoring was called
                assert mock_monitoring.record_embedding_generation.called
                call_args = mock_monitoring.record_embedding_generation.call_args
                assert call_args[1]["provider"] == "ollama"
                assert call_args[1]["model"] == "bge-m3"

    @pytest.mark.asyncio
    async def test_monitoring_not_called_for_cached(self):
        """Test that monitoring is not called for cached embeddings"""
        mock_storage = AsyncMock()
        # Mock cache hit
        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"embedding": [0.5] * 1024}]
        )

        mock_monitoring = AsyncMock()
        mock_monitoring.record_embedding_generation = AsyncMock()

        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=True
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings'):
                service = EmbeddingService(
                    config,
                    supabase_storage=mock_storage,
                    monitoring_service=mock_monitoring
                )

                await service.generate_embedding("cached content")

                # Monitoring should NOT be called for cached embeddings
                assert not mock_monitoring.record_embedding_generation.called


# ============================================================================
# Test Factory Functions
# ============================================================================

class TestFactoryFunctions:
    """Test factory functions for creating embedding services"""

    def test_create_embedding_service_ollama(self):
        """Test creating Ollama embedding service"""
        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings'):
                service = create_embedding_service(provider="ollama")

                assert isinstance(service, EmbeddingService)
                assert service.config.provider == EmbeddingProvider.OLLAMA
                assert service.config.model == EmbeddingModel.BGE_M3
                assert service.config.dimensions == 1024

    def test_create_embedding_service_openai(self):
        """Test creating OpenAI embedding service"""
        with patch('app.services.embedding_service.OPENAI_AVAILABLE', True):
            with patch('app.services.embedding_service.AsyncOpenAI'):
                service = create_embedding_service(
                    provider="openai",
                    openai_api_key="test-key"
                )

                assert isinstance(service, EmbeddingService)
                assert service.config.provider == EmbeddingProvider.OPENAI
                assert service.config.model == EmbeddingModel.OPENAI_SMALL
                assert service.config.dimensions == 1536

    def test_create_embedding_service_with_custom_batch_size(self):
        """Test creating service with custom batch size"""
        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings'):
                service = create_embedding_service(
                    provider="ollama",
                    batch_size=50
                )

                assert service.config.batch_size == 50

    def test_get_embedding_service_singleton(self):
        """Test singleton pattern for embedding service"""
        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings'):
                # Reset singleton
                import app.services.embedding_service as embed_module
                embed_module._embedding_service = None

                service1 = get_embedding_service(provider="ollama")
                service2 = get_embedding_service()

                assert service1 is service2


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in embedding service"""

    def test_initialization_without_ollama_library(self):
        """Test error when langchain-ollama not installed"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', False):
            with pytest.raises(ImportError, match="langchain-ollama not installed"):
                service = EmbeddingService(config)

    def test_initialization_without_openai_library(self):
        """Test error when openai not installed"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=EmbeddingModel.OPENAI_SMALL,
            openai_api_key="test-key"
        )

        with patch('app.services.embedding_service.OPENAI_AVAILABLE', False):
            with pytest.raises(ImportError, match="openai not installed"):
                service = EmbeddingService(config)

    def test_openai_without_api_key(self):
        """Test error when OpenAI API key not provided"""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=EmbeddingModel.OPENAI_SMALL
        )

        with patch('app.services.embedding_service.OPENAI_AVAILABLE', True):
            with patch('os.getenv', return_value=None):
                with pytest.raises(ValueError, match="OpenAI API key not provided"):
                    service = EmbeddingService(config)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete embedding workflow"""

    @pytest.mark.asyncio
    async def test_end_to_end_ollama_workflow(self):
        """Test complete workflow with Ollama"""
        mock_storage = AsyncMock()
        mock_monitoring = AsyncMock()

        # Mock cache miss then cache insert
        mock_storage.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mock_storage.supabase.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_monitoring.record_embedding_generation = AsyncMock()

        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model=EmbeddingModel.BGE_M3,
            cache_enabled=True,
            batch_size=50
        )

        with patch('app.services.embedding_service.OLLAMA_AVAILABLE', True):
            with patch('app.services.embedding_service.OllamaEmbeddings') as mock_ollama:
                mock_embedder = Mock()
                mock_embedder.embed_documents = Mock(
                    side_effect=lambda texts: [[0.1 * i] * 1024 for i in range(len(texts))]
                )
                mock_ollama.return_value = mock_embedder

                service = EmbeddingService(
                    config,
                    supabase_storage=mock_storage,
                    monitoring_service=mock_monitoring
                )

                # Generate embeddings for 100 chunks
                texts = [f"chunk {i}" for i in range(100)]
                chunk_ids = [f"chunk-{i}" for i in range(100)]

                results = await service.generate_embeddings_batch(
                    texts,
                    chunk_ids=chunk_ids
                )

                # Verify results
                assert len(results) == 100
                assert all(r.dimensions == 1024 for r in results)
                assert all(r.provider == "ollama" for r in results)
                assert all(r.cost == 0.0 for r in results)

                # Verify caching was called
                assert mock_storage.supabase.table.return_value.upsert.called

                # Verify monitoring was called
                assert mock_monitoring.record_embedding_generation.called
