"""
Empire v7.3 - Embedding Generation Service
Generate and cache embeddings using BGE-M3 (Ollama) or Mistral with Supabase pgvector caching

Primary: BGE-M3 via Ollama (1024 dims, free, local)
Fallback: Mistral Embed (1024 dims, $0.1/1M tokens, cloud)

Both use 1024 dimensions for compatibility - no schema changes needed when switching.
"""

import os
import time
import hashlib
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# Langchain for Ollama embeddings
try:
    from langchain_ollama import OllamaEmbeddings
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("langchain-ollama not available - install with: pip install langchain-ollama")

# Mistral AI for production embeddings (fallback)
try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    logging.warning("mistralai not available - install with: pip install mistralai")

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker_sync,
)

logger = logging.getLogger(__name__)

# Circuit breaker for Ollama embedding service
_ollama_embedding_circuit_breaker: Optional[CircuitBreaker] = None


def get_ollama_embedding_circuit_breaker() -> CircuitBreaker:
    """Get or create Ollama embedding circuit breaker with appropriate settings"""
    global _ollama_embedding_circuit_breaker
    if _ollama_embedding_circuit_breaker is None:
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=2,
            success_threshold=2,
        )
        _ollama_embedding_circuit_breaker = get_circuit_breaker_sync("ollama_embeddings", config)
    return _ollama_embedding_circuit_breaker


# ============================================================================
# Configuration and Enums
# ============================================================================

class EmbeddingProvider(str, Enum):
    """Available embedding providers"""
    OLLAMA = "ollama"  # BGE-M3 via Ollama for development (free, local)
    MISTRAL = "mistral"  # Mistral Embed for production fallback ($0.1/1M tokens)


class EmbeddingModel(str, Enum):
    """Available embedding models"""
    BGE_M3 = "bge-m3"  # Ollama BGE-M3 (1024 dimensions, free)
    MISTRAL_EMBED = "mistral-embed"  # Mistral Embed (1024 dimensions with output_dimension param)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""
    provider: EmbeddingProvider
    model: EmbeddingModel
    batch_size: int = 100
    dimensions: int = 1024  # Both BGE-M3 and Mistral use 1024 dims
    ollama_base_url: str = "http://localhost:11434"
    mistral_api_key: Optional[str] = None
    cache_enabled: bool = True
    regenerate_on_update: bool = True


@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    chunk_id: str
    embedding: List[float]
    provider: str
    model: str
    dimensions: int
    generation_time: float
    cached: bool = False
    cost: float = 0.0


# ============================================================================
# Embedding Cache Manager
# ============================================================================

class EmbeddingCacheManager:
    """
    Manage embedding cache in Supabase pgvector

    Features:
    - Content hash-based caching
    - Cache invalidation on content updates
    - Efficient batch operations
    - Metadata tracking
    """

    def __init__(self, supabase_storage):
        """
        Initialize cache manager

        Args:
            supabase_storage: Supabase storage service for database access
        """
        self.storage = supabase_storage

    async def get_cached_embedding(
        self,
        content: str,
        model: str
    ) -> Optional[List[float]]:
        """
        Retrieve cached embedding for content

        Args:
            content: Text content
            model: Embedding model name

        Returns:
            Cached embedding vector or None if not found
        """
        try:
            # Generate content hash
            content_hash = self._hash_content(content)

            # Query cache
            result = await self.storage.supabase.table("embeddings_cache")\
                .select("embedding, model, created_at")\
                .eq("content_hash", content_hash)\
                .eq("model", model)\
                .limit(1)\
                .execute()

            if result.data and len(result.data) > 0:
                logger.debug(f"Cache hit for content hash {content_hash[:16]}...")
                return result.data[0]["embedding"]

            logger.debug(f"Cache miss for content hash {content_hash[:16]}...")
            return None

        except Exception as e:
            logger.error(f"Error retrieving cached embedding: {e}")
            return None

    async def cache_embedding(
        self,
        content: str,
        embedding: List[float],
        model: str,
        chunk_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Cache embedding for content

        Args:
            content: Text content
            embedding: Embedding vector
            model: Embedding model name
            chunk_id: Optional chunk ID
            metadata: Optional additional metadata
        """
        try:
            content_hash = self._hash_content(content)

            # Prepare cache entry
            cache_entry = {
                "content_hash": content_hash,
                "embedding": embedding,
                "model": model,
                "chunk_id": chunk_id,
                "dimensions": len(embedding),
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }

            # Upsert (insert or update)
            await self.storage.supabase.table("embeddings_cache")\
                .upsert(cache_entry, on_conflict="content_hash,model")\
                .execute()

            logger.debug(f"Cached embedding for content hash {content_hash[:16]}...")

        except Exception as e:
            logger.error(f"Error caching embedding: {e}")

    async def batch_cache_embeddings(
        self,
        contents: List[str],
        embeddings: List[List[float]],
        model: str,
        chunk_ids: Optional[List[str]] = None,
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Cache multiple embeddings in batch

        Args:
            contents: List of text contents
            embeddings: List of embedding vectors
            model: Embedding model name
            chunk_ids: Optional list of chunk IDs
            metadata_list: Optional list of metadata dicts
        """
        try:
            cache_entries = []

            for i, (content, embedding) in enumerate(zip(contents, embeddings)):
                content_hash = self._hash_content(content)
                chunk_id = chunk_ids[i] if chunk_ids else None
                metadata = metadata_list[i] if metadata_list else {}

                cache_entries.append({
                    "content_hash": content_hash,
                    "embedding": embedding,
                    "model": model,
                    "chunk_id": chunk_id,
                    "dimensions": len(embedding),
                    "metadata": metadata,
                    "created_at": datetime.utcnow().isoformat()
                })

            # Batch upsert
            await self.storage.supabase.table("embeddings_cache")\
                .upsert(cache_entries, on_conflict="content_hash,model")\
                .execute()

            logger.info(f"Cached {len(cache_entries)} embeddings in batch")

        except Exception as e:
            logger.error(f"Error batch caching embeddings: {e}")

    async def invalidate_cache(self, chunk_id: str):
        """Invalidate cached embeddings for a chunk"""
        try:
            await self.storage.supabase.table("embeddings_cache")\
                .delete()\
                .eq("chunk_id", chunk_id)\
                .execute()

            logger.info(f"Invalidated cache for chunk {chunk_id}")

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")

    def _hash_content(self, content: str) -> str:
        """Generate SHA-256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


# ============================================================================
# Embedding Service
# ============================================================================

class EmbeddingService:
    """
    Unified embedding generation service with caching and monitoring

    Features:
    - BGE-M3 via Ollama for development (free, local, 1024 dims)
    - Mistral Embed for production fallback ($0.1/1M tokens, 1024 dims)
    - Automatic caching in Supabase pgvector
    - Batch processing (100 chunks default)
    - Cost tracking and monitoring
    - Error handling and retries

    Both providers use 1024 dimensions for seamless switching.
    """

    def __init__(
        self,
        config: EmbeddingConfig,
        supabase_storage=None,
        monitoring_service=None
    ):
        """
        Initialize embedding service

        Args:
            config: Embedding configuration
            supabase_storage: Optional Supabase storage for caching
            monitoring_service: Optional monitoring service for metrics
        """
        self.config = config
        self.supabase_storage = supabase_storage
        self.monitoring = monitoring_service

        # Initialize cache manager
        if config.cache_enabled and supabase_storage:
            self.cache_manager = EmbeddingCacheManager(supabase_storage)
        else:
            self.cache_manager = None

        # Initialize embedding providers
        self.ollama_client = None
        self.mistral_client = None

        if config.provider == EmbeddingProvider.OLLAMA:
            self._init_ollama()
        elif config.provider == EmbeddingProvider.MISTRAL:
            self._init_mistral()

    def _init_ollama(self):
        """Initialize Ollama embedding client"""
        if not OLLAMA_AVAILABLE:
            raise ImportError("langchain-ollama not installed. Install with: pip install langchain-ollama")

        try:
            self.ollama_client = OllamaEmbeddings(
                base_url=self.config.ollama_base_url,
                model=self.config.model.value
            )
            logger.info(f"Initialized Ollama embeddings with model: {self.config.model.value}")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")
            raise

    def _init_mistral(self):
        """Initialize Mistral embedding client"""
        if not MISTRAL_AVAILABLE:
            raise ImportError("mistralai not installed. Install with: pip install mistralai")

        api_key = self.config.mistral_api_key or os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("Mistral API key not provided and MISTRAL_API_KEY not in environment")

        try:
            self.mistral_client = Mistral(api_key=api_key)
            logger.info(f"Initialized Mistral embeddings with model: {self.config.model.value}")
        except Exception as e:
            logger.error(f"Failed to initialize Mistral client: {e}")
            raise

    async def generate_embedding(
        self,
        text: str,
        chunk_id: Optional[str] = None,
        use_cache: bool = True
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text

        Args:
            text: Input text
            chunk_id: Optional chunk identifier
            use_cache: Whether to use cached embeddings

        Returns:
            EmbeddingResult with embedding vector and metadata
        """
        start_time = time.time()

        # Check cache
        cached_embedding = None
        if use_cache and self.cache_manager:
            cached_embedding = await self.cache_manager.get_cached_embedding(
                text,
                self.config.model.value
            )

        if cached_embedding:
            return EmbeddingResult(
                chunk_id=chunk_id or "unknown",
                embedding=cached_embedding,
                provider=self.config.provider.value,
                model=self.config.model.value,
                dimensions=len(cached_embedding),
                generation_time=time.time() - start_time,
                cached=True,
                cost=0.0
            )

        # Generate new embedding
        if self.config.provider == EmbeddingProvider.OLLAMA:
            embedding = await self._generate_ollama_embedding(text)
            cost = 0.0  # Free
        elif self.config.provider == EmbeddingProvider.MISTRAL:
            embedding, cost = await self._generate_mistral_embedding(text)
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

        generation_time = time.time() - start_time

        # Cache embedding
        if self.cache_manager:
            await self.cache_manager.cache_embedding(
                text,
                embedding,
                self.config.model.value,
                chunk_id=chunk_id
            )

        # Record metrics
        if self.monitoring:
            await self.monitoring.record_embedding_generation(
                provider=self.config.provider.value,
                model=self.config.model.value,
                num_embeddings=1,
                tokens=len(text.split()),  # Rough estimate
                duration=generation_time,
                status="success"
            )

        return EmbeddingResult(
            chunk_id=chunk_id or "unknown",
            embedding=embedding,
            provider=self.config.provider.value,
            model=self.config.model.value,
            dimensions=len(embedding),
            generation_time=generation_time,
            cached=False,
            cost=cost
        )

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        chunk_ids: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts in batch

        Args:
            texts: List of input texts
            chunk_ids: Optional list of chunk identifiers
            use_cache: Whether to use cached embeddings

        Returns:
            List of EmbeddingResult objects
        """
        if chunk_ids and len(chunk_ids) != len(texts):
            raise ValueError("Number of chunk_ids must match number of texts")

        results = []
        batch_size = self.config.batch_size

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_chunk_ids = chunk_ids[i:i + batch_size] if chunk_ids else None

            batch_results = await self._process_batch(
                batch_texts,
                batch_chunk_ids,
                use_cache
            )
            results.extend(batch_results)

            logger.info(f"Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

        return results

    async def _process_batch(
        self,
        texts: List[str],
        chunk_ids: Optional[List[str]],
        use_cache: bool
    ) -> List[EmbeddingResult]:
        """Process a single batch of texts"""
        start_time = time.time()

        # Check cache for all texts
        uncached_indices = []
        cached_embeddings = []

        if use_cache and self.cache_manager:
            for idx, text in enumerate(texts):
                cached = await self.cache_manager.get_cached_embedding(
                    text,
                    self.config.model.value
                )
                if cached:
                    cached_embeddings.append((idx, cached))
                else:
                    uncached_indices.append(idx)
        else:
            uncached_indices = list(range(len(texts)))

        # Generate embeddings for uncached texts
        new_embeddings = []
        total_cost = 0.0

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]

            if self.config.provider == EmbeddingProvider.OLLAMA:
                new_emb = await self._generate_ollama_embeddings_batch(uncached_texts)
                new_embeddings = [(uncached_indices[i], emb) for i, emb in enumerate(new_emb)]
                cost = 0.0
            elif self.config.provider == EmbeddingProvider.MISTRAL:
                new_emb, cost = await self._generate_mistral_embeddings_batch(uncached_texts)
                new_embeddings = [(uncached_indices[i], emb) for i, emb in enumerate(new_emb)]
                total_cost = cost

            # Cache new embeddings
            if self.cache_manager:
                await self.cache_manager.batch_cache_embeddings(
                    uncached_texts,
                    new_emb,
                    self.config.model.value,
                    chunk_ids=[chunk_ids[i] for i in uncached_indices] if chunk_ids else None
                )

        generation_time = time.time() - start_time

        # Record metrics
        if self.monitoring and uncached_indices:
            await self.monitoring.record_embedding_generation(
                provider=self.config.provider.value,
                model=self.config.model.value,
                num_embeddings=len(uncached_indices),
                tokens=sum(len(texts[i].split()) for i in uncached_indices),
                duration=generation_time,
                status="success"
            )

        # Combine cached and new embeddings in correct order
        all_embeddings = [None] * len(texts)
        for idx, emb in cached_embeddings:
            all_embeddings[idx] = (emb, True, 0.0)
        for idx, emb in new_embeddings:
            all_embeddings[idx] = (emb, False, total_cost / len(uncached_indices) if uncached_indices else 0.0)

        # Create results
        results = []
        for i, (embedding, cached, cost) in enumerate(all_embeddings):
            results.append(EmbeddingResult(
                chunk_id=chunk_ids[i] if chunk_ids else f"batch_{i}",
                embedding=embedding,
                provider=self.config.provider.value,
                model=self.config.model.value,
                dimensions=len(embedding),
                generation_time=generation_time / len(texts),
                cached=cached,
                cost=cost
            ))

        return results

    async def _generate_ollama_embedding(self, text: str) -> List[float]:
        """Generate single embedding using Ollama (with circuit breaker protection)"""
        if not self.ollama_client:
            raise ValueError("Ollama client not initialized")

        circuit = get_ollama_embedding_circuit_breaker()

        try:
            # Ollama embed_documents expects a list
            async def ollama_embed():
                return await asyncio.to_thread(
                    self.ollama_client.embed_documents,
                    [text]
                )

            embeddings = await circuit.call(ollama_embed, operation="embed_single")
            return embeddings[0]
        except Exception as e:
            logger.error(f"Ollama embedding generation failed: {e}")
            raise

    async def _generate_ollama_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using Ollama (with circuit breaker protection)"""
        if not self.ollama_client:
            raise ValueError("Ollama client not initialized")

        circuit = get_ollama_embedding_circuit_breaker()

        try:
            async def ollama_embed_batch():
                return await asyncio.to_thread(
                    self.ollama_client.embed_documents,
                    texts
                )

            embeddings = await circuit.call(ollama_embed_batch, operation="embed_batch")
            return embeddings
        except Exception as e:
            logger.error(f"Ollama batch embedding generation failed: {e}")
            raise

    async def _generate_mistral_embedding(self, text: str) -> Tuple[List[float], float]:
        """Generate single embedding using Mistral AI"""
        if not self.mistral_client:
            raise ValueError("Mistral client not initialized")

        try:
            # Use async method with output_dimension=1024 to match BGE-M3
            response = await self.mistral_client.embeddings.create_async(
                model=self.config.model.value,
                inputs=[text],
                output_dimension=1024  # Match BGE-M3 dimensions
            )

            embedding = response.data[0].embedding

            # Calculate cost: $0.1 per 1M tokens
            # Rough token estimate: ~1.3 tokens per word
            tokens = len(text.split()) * 1.3
            cost = (tokens / 1_000_000) * 0.1

            return embedding, cost

        except Exception as e:
            logger.error(f"Mistral embedding generation failed: {e}")
            raise

    async def _generate_mistral_embeddings_batch(
        self,
        texts: List[str]
    ) -> Tuple[List[List[float]], float]:
        """Generate batch embeddings using Mistral AI"""
        if not self.mistral_client:
            raise ValueError("Mistral client not initialized")

        try:
            # Use async method with output_dimension=1024 to match BGE-M3
            response = await self.mistral_client.embeddings.create_async(
                model=self.config.model.value,
                inputs=texts,
                output_dimension=1024  # Match BGE-M3 dimensions
            )

            # Extract embeddings maintaining order (sorted by index)
            sorted_data = sorted(response.data, key=lambda x: x.index)
            embeddings = [item.embedding for item in sorted_data]

            # Calculate total cost: $0.1 per 1M tokens
            total_tokens = sum(len(text.split()) * 1.3 for text in texts)
            cost = (total_tokens / 1_000_000) * 0.1

            return embeddings, cost

        except Exception as e:
            logger.error(f"Mistral batch embedding generation failed: {e}")
            raise

    async def invalidate_chunk_cache(self, chunk_id: str):
        """Invalidate cached embeddings for a chunk"""
        if self.cache_manager:
            await self.cache_manager.invalidate_cache(chunk_id)


# ============================================================================
# Factory Functions
# ============================================================================

def create_embedding_service(
    provider: str = "ollama",
    model: Optional[str] = None,
    supabase_storage=None,
    monitoring_service=None,
    **kwargs
) -> EmbeddingService:
    """
    Factory function to create an embedding service

    Args:
        provider: "ollama" or "mistral"
        model: Model name (defaults based on provider)
        supabase_storage: Supabase storage service
        monitoring_service: Monitoring service
        **kwargs: Additional configuration options

    Returns:
        Configured EmbeddingService instance

    Note:
        Both providers use 1024 dimensions for compatibility:
        - ollama: BGE-M3 (free, local)
        - mistral: mistral-embed with output_dimension=1024 ($0.1/1M tokens)
    """
    # Determine provider - both use 1024 dimensions
    if provider == "ollama":
        embedding_provider = EmbeddingProvider.OLLAMA
        embedding_model = EmbeddingModel.BGE_M3 if not model else EmbeddingModel(model)
        dimensions = 1024
    elif provider == "mistral":
        embedding_provider = EmbeddingProvider.MISTRAL
        embedding_model = EmbeddingModel.MISTRAL_EMBED if not model else EmbeddingModel(model)
        dimensions = 1024  # Set via output_dimension parameter in API call
    else:
        raise ValueError(f"Unsupported provider: {provider}. Use 'ollama' or 'mistral'.")

    # Create configuration
    config = EmbeddingConfig(
        provider=embedding_provider,
        model=embedding_model,
        dimensions=dimensions,
        batch_size=kwargs.get("batch_size", 100),
        ollama_base_url=kwargs.get("ollama_base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")),
        mistral_api_key=kwargs.get("mistral_api_key", os.getenv("MISTRAL_API_KEY")),
        cache_enabled=kwargs.get("cache_enabled", True),
        regenerate_on_update=kwargs.get("regenerate_on_update", True)
    )

    return EmbeddingService(config, supabase_storage, monitoring_service)


# ============================================================================
# Singleton Instance
# ============================================================================

_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(
    provider: Optional[str] = None,
    supabase_storage=None,
    monitoring_service=None
) -> EmbeddingService:
    """
    Get or create singleton EmbeddingService instance

    Args:
        provider: Optional provider override
        supabase_storage: Supabase storage service
        monitoring_service: Monitoring service

    Returns:
        EmbeddingService instance
    """
    global _embedding_service

    if _embedding_service is None:
        # Use environment variable or default to Ollama
        provider = provider or os.getenv("EMBEDDING_PROVIDER", "ollama")
        _embedding_service = create_embedding_service(
            provider=provider,
            supabase_storage=supabase_storage,
            monitoring_service=monitoring_service
        )

    return _embedding_service
