# Empire v7.3 - Embedding Service Guide

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Provider Setup](#provider-setup)
- [Usage Examples](#usage-examples)
- [Caching System](#caching-system)
- [Batch Processing](#batch-processing)
- [Cost Tracking](#cost-tracking)
- [Monitoring Integration](#monitoring-integration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

The Empire Embedding Service provides a unified interface for generating vector embeddings from text chunks. It supports multiple embedding providers and includes automatic caching, batch processing, and cost tracking.

### Key Features

- **Dual Provider Support**: BGE-M3 (Ollama) for development, OpenAI for production
- **Automatic Caching**: Content hash-based deduplication in Supabase pgvector
- **Batch Processing**: Efficient processing of large document sets (100 chunks default)
- **Cost Tracking**: Automatic cost calculation and monitoring integration
- **Vector Search**: HNSW-indexed similarity search in Supabase
- **Cache Invalidation**: Automatic cache updates on content changes

### Supported Models

| Provider | Model | Dimensions | Cost | Use Case |
|----------|-------|------------|------|----------|
| Ollama | BGE-M3 | 1024 | Free | Development, local testing |
| OpenAI | text-embedding-3-small | 1536 | $0.00002/1K tokens | Production (standard) |
| OpenAI | text-embedding-3-large | 3072 | $0.00013/1K tokens | Production (high quality) |

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    EmbeddingService                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Provider Selection                       │  │
│  │  - Ollama (BGE-M3) for development                   │  │
│  │  - OpenAI for production                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          EmbeddingCacheManager                        │  │
│  │  - Content hash calculation (SHA-256)                │  │
│  │  - Cache lookup in Supabase pgvector                 │  │
│  │  - Cache storage with metadata                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Batch Processing Engine                     │  │
│  │  - Configurable batch size (default: 100)            │  │
│  │  - Parallel processing support                       │  │
│  │  - Error handling per batch                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Cost Tracking & Monitoring                    │  │
│  │  - Per-operation cost calculation                    │  │
│  │  - Prometheus metrics integration                    │  │
│  │  - Cache hit/miss tracking                           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌───────────────────────┐
              │  Supabase pgvector    │
              │  - embeddings_cache   │
              │  - HNSW indexes       │
              │  - Vector search      │
              └───────────────────────┘
```

### Data Flow

1. **Input**: Text chunks from document processing pipeline
2. **Cache Check**: SHA-256 hash lookup in Supabase
3. **Generation**: If not cached, generate via Ollama or OpenAI
4. **Storage**: Store embedding with metadata in cache
5. **Output**: Return embedding vector with metadata

## Quick Start

### Basic Usage

```python
from app.services.embedding_service import get_embedding_service
from app.services.supabase_storage import get_supabase_storage
from app.services.monitoring_service import get_monitoring_service

# Initialize services
storage = get_supabase_storage()
monitoring = get_monitoring_service(storage)
embedding_service = get_embedding_service(storage, monitoring)

# Generate single embedding
result = await embedding_service.generate_embedding(
    text="Your text content here",
    chunk_id="chunk-uuid-123"
)

print(f"Embedding: {result.embedding}")
print(f"Dimensions: {result.dimensions}")
print(f"Cached: {result.from_cache}")
print(f"Cost: ${result.cost:.6f}")
```

### Batch Processing

```python
# Generate embeddings for multiple chunks
texts = [
    "First document chunk",
    "Second document chunk",
    "Third document chunk"
]
chunk_ids = ["chunk-1", "chunk-2", "chunk-3"]

results = await embedding_service.generate_embeddings_batch(
    texts=texts,
    chunk_ids=chunk_ids,
    use_cache=True
)

for result in results:
    print(f"Chunk {result.chunk_id}: {len(result.embedding)} dims, "
          f"cached={result.from_cache}, cost=${result.cost:.6f}")
```

## Configuration

### Environment Variables

```bash
# .env file

# Provider Selection
EMBEDDING_PROVIDER=ollama  # or "openai"

# Ollama Configuration (Development)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3  # 1024 dimensions

# OpenAI Configuration (Production)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small  # or text-embedding-3-large

# Cache Configuration
EMBEDDING_CACHE_ENABLED=true
EMBEDDING_CACHE_TTL=2592000  # 30 days in seconds

# Batch Processing
EMBEDDING_BATCH_SIZE=100
EMBEDDING_MAX_RETRIES=3
EMBEDDING_RETRY_DELAY=1.0  # seconds
```

### Programmatic Configuration

```python
from app.services.embedding_service import EmbeddingConfig, EmbeddingService

# Custom configuration
config = EmbeddingConfig(
    provider="openai",
    model="text-embedding-3-large",
    dimensions=3072,
    batch_size=50,
    cache_enabled=True,
    cache_ttl=86400,  # 1 day
    max_retries=5,
    retry_delay=2.0,
    openai_api_key="sk-your-key"
)

# Create service with custom config
embedding_service = EmbeddingService(
    config=config,
    supabase_storage=storage,
    monitoring_service=monitoring
)
```

## Provider Setup

### Ollama (Development)

#### Installation

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

#### Pull BGE-M3 Model

```bash
ollama pull bge-m3
```

#### Verify Installation

```bash
ollama list
# Should show: bge-m3

# Test embedding generation
curl http://localhost:11434/api/embeddings -d '{
  "model": "bge-m3",
  "prompt": "Test text"
}'
```

#### Usage in Code

```python
from app.services.embedding_service import get_ollama_embedding_service

# Automatically uses OLLAMA_BASE_URL and OLLAMA_EMBEDDING_MODEL from env
embedding_service = get_ollama_embedding_service(storage, monitoring)

result = await embedding_service.generate_embedding("Sample text")
# result.dimensions = 1024 (BGE-M3)
# result.cost = 0.0 (free)
```

### OpenAI (Production)

#### API Key Setup

```bash
# Set environment variable
export OPENAI_API_KEY=sk-your-api-key-here

# Or add to .env file
echo "OPENAI_API_KEY=sk-your-api-key-here" >> .env
```

#### Model Selection

```python
from app.services.embedding_service import get_openai_embedding_service

# text-embedding-3-small (recommended for most use cases)
embedding_service = get_openai_embedding_service(
    storage,
    monitoring,
    model="text-embedding-3-small"  # 1536 dims, $0.00002/1K tokens
)

# text-embedding-3-large (for highest quality)
embedding_service = get_openai_embedding_service(
    storage,
    monitoring,
    model="text-embedding-3-large"  # 3072 dims, $0.00013/1K tokens
)
```

## Usage Examples

### 1. Single Document Processing

```python
async def process_document_embeddings(file_id: str):
    """Generate embeddings for all chunks of a document"""

    # Get chunks from database
    chunks = await storage.supabase.table("chunks")\
        .select("id, content")\
        .eq("file_id", file_id)\
        .execute()

    # Prepare batch
    texts = [chunk["content"] for chunk in chunks.data]
    chunk_ids = [chunk["id"] for chunk in chunks.data]

    # Generate embeddings
    results = await embedding_service.generate_embeddings_batch(
        texts=texts,
        chunk_ids=chunk_ids
    )

    # Update chunks with embeddings
    for result in results:
        await storage.supabase.table("chunks")\
            .update({"embedding": result.embedding})\
            .eq("id", result.chunk_id)\
            .execute()

    return results
```

### 2. Similarity Search

```python
async def find_similar_chunks(query: str, limit: int = 10):
    """Find chunks similar to query using vector search"""

    # Generate query embedding
    query_result = await embedding_service.generate_embedding(query)

    # Perform similarity search in Supabase
    # Using cosine similarity (<=> operator)
    results = await storage.supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_result.embedding,
            "match_threshold": 0.7,
            "match_count": limit
        }
    ).execute()

    return results.data
```

### 3. Cache Management

```python
async def refresh_document_embeddings(file_id: str):
    """Regenerate embeddings for a document, bypassing cache"""

    chunks = await storage.supabase.table("chunks")\
        .select("id, content")\
        .eq("file_id", file_id)\
        .execute()

    texts = [chunk["content"] for chunk in chunks.data]
    chunk_ids = [chunk["id"] for chunk in chunks.data]

    # Disable cache for this operation
    results = await embedding_service.generate_embeddings_batch(
        texts=texts,
        chunk_ids=chunk_ids,
        use_cache=False  # Force regeneration
    )

    return results
```

### 4. Cost Estimation

```python
async def estimate_embedding_cost(file_id: str):
    """Estimate cost to embed all chunks of a document"""

    chunks = await storage.supabase.table("chunks")\
        .select("content")\
        .eq("file_id", file_id)\
        .execute()

    total_tokens = sum(
        len(chunk["content"]) // 4  # Rough token estimate
        for chunk in chunks.data
    )

    # Cost per 1K tokens
    if embedding_service.config.provider == "openai":
        if embedding_service.config.model == "text-embedding-3-small":
            cost_per_1k = 0.00002
        elif embedding_service.config.model == "text-embedding-3-large":
            cost_per_1k = 0.00013
        else:
            cost_per_1k = 0.0
    else:
        cost_per_1k = 0.0  # Ollama is free

    estimated_cost = (total_tokens / 1000) * cost_per_1k

    return {
        "total_chunks": len(chunks.data),
        "estimated_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost,
        "provider": embedding_service.config.provider,
        "model": embedding_service.config.model
    }
```

## Caching System

### How Caching Works

1. **Content Hashing**: SHA-256 hash generated from text content
2. **Cache Lookup**: Check `embeddings_cache` table for hash + model combination
3. **Cache Hit**: Return cached embedding, update `last_accessed_at`
4. **Cache Miss**: Generate new embedding, store in cache
5. **Deduplication**: Same content + model = same cache entry

### Cache Schema

```sql
CREATE TABLE embeddings_cache (
    id UUID PRIMARY KEY,
    content_hash VARCHAR(64) NOT NULL,  -- SHA-256 of content
    chunk_id UUID REFERENCES chunks(id),
    embedding vector(1024),  -- Adjusts based on model
    model VARCHAR(100) NOT NULL,
    dimensions INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (content_hash, model)
);
```

### Cache Statistics

```python
async def get_cache_stats():
    """Get embedding cache statistics"""

    result = await storage.supabase.rpc(
        "get_embeddings_cache_stats"
    ).execute()

    stats = result.data[0]
    return {
        "total_embeddings": stats["total_embeddings"],
        "total_size_mb": stats["total_size_mb"],
        "models_count": stats["models_count"],
        "oldest_entry": stats["oldest_entry"],
        "newest_entry": stats["newest_entry"],
        "avg_dimension": stats["avg_dimension"]
    }
```

### Cache Cleanup

```python
async def cleanup_old_cache(days: int = 90):
    """Remove cache entries older than specified days"""

    result = await storage.supabase.rpc(
        "cleanup_old_embeddings_cache",
        {"days_old": days}
    ).execute()

    deleted_count = result.data
    return f"Deleted {deleted_count} old cache entries"
```

## Batch Processing

### Batch Configuration

```python
# Configure batch size based on available memory
config = EmbeddingConfig(
    batch_size=100,  # Process 100 chunks at a time
    provider="openai"
)

embedding_service = EmbeddingService(config, storage, monitoring)
```

### Processing Large Documents

```python
async def process_large_document(file_id: str):
    """Process a large document in batches with progress tracking"""

    # Get total chunk count
    count_result = await storage.supabase.table("chunks")\
        .select("id", count="exact")\
        .eq("file_id", file_id)\
        .execute()

    total_chunks = count_result.count
    batch_size = 100
    processed = 0

    for offset in range(0, total_chunks, batch_size):
        # Fetch batch
        chunks = await storage.supabase.table("chunks")\
            .select("id, content")\
            .eq("file_id", file_id)\
            .range(offset, offset + batch_size - 1)\
            .execute()

        # Generate embeddings
        texts = [c["content"] for c in chunks.data]
        chunk_ids = [c["id"] for c in chunks.data]

        results = await embedding_service.generate_embeddings_batch(
            texts=texts,
            chunk_ids=chunk_ids
        )

        processed += len(results)
        progress = (processed / total_chunks) * 100

        print(f"Progress: {processed}/{total_chunks} chunks ({progress:.1f}%)")

        # Update database
        for result in results:
            await storage.supabase.table("chunks")\
                .update({"embedding": result.embedding})\
                .eq("id", result.chunk_id)\
                .execute()

    return {"processed": processed, "total": total_chunks}
```

## Cost Tracking

### Model Costs

| Model | Provider | Input Cost (per 1K tokens) | Dimensions |
|-------|----------|----------------------------|------------|
| BGE-M3 | Ollama | $0.00000 | 1024 |
| text-embedding-3-small | OpenAI | $0.00002 | 1536 |
| text-embedding-3-large | OpenAI | $0.00013 | 3072 |

### Cost Calculation

```python
async def calculate_embedding_costs(file_id: str):
    """Calculate actual costs for embedded document"""

    results = await embedding_service.generate_embeddings_batch(
        texts=texts,
        chunk_ids=chunk_ids
    )

    total_cost = sum(r.cost for r in results)
    cached_count = sum(1 for r in results if r.from_cache)
    generated_count = len(results) - cached_count

    return {
        "total_chunks": len(results),
        "cached_chunks": cached_count,
        "generated_chunks": generated_count,
        "total_cost_usd": total_cost,
        "cache_savings_usd": cached_count * (total_cost / max(generated_count, 1))
    }
```

### Monitoring Cost Metrics

```python
from app.services.monitoring_service import get_monitoring_service

monitoring = get_monitoring_service(storage)

# Costs are automatically tracked via monitoring integration
async with monitoring.track_embedding_generation(
    model="text-embedding-3-small",
    num_embeddings=100
) as stage:
    results = await embedding_service.generate_embeddings_batch(texts)
    stage.cost = sum(r.cost for r in results)

# Query cost metrics from Prometheus
# embeddings_generated_total{model="text-embedding-3-small"}
# embeddings_cache_hits_total
# embeddings_generation_cost_total
```

## Monitoring Integration

### Prometheus Metrics

The embedding service exposes the following metrics:

```python
# Counter: Total embeddings generated
embeddings_generated_total{model="bge-m3",provider="ollama"}

# Counter: Cache hits
embeddings_cache_hits_total{model="bge-m3"}

# Counter: Cache misses
embeddings_cache_misses_total{model="bge-m3"}

# Histogram: Generation duration
embeddings_generation_duration_seconds{model="text-embedding-3-small"}

# Counter: Total generation cost
embeddings_generation_cost_total{model="text-embedding-3-small"}

# Gauge: Batch size
embeddings_batch_size{model="bge-m3"}
```

### Querying Metrics

```python
# Get cache hit rate
cache_hit_rate = """
rate(embeddings_cache_hits_total[5m]) /
(rate(embeddings_cache_hits_total[5m]) + rate(embeddings_cache_misses_total[5m]))
"""

# Get average generation time
avg_generation_time = """
rate(embeddings_generation_duration_seconds_sum[5m]) /
rate(embeddings_generation_duration_seconds_count[5m])
"""

# Get total cost over time
total_cost = """
increase(embeddings_generation_cost_total[1h])
"""
```

## Best Practices

### 1. Provider Selection

- **Development/Testing**: Use Ollama (BGE-M3)
  - Free, runs locally
  - Good quality (1024 dimensions)
  - No API rate limits

- **Production**: Use OpenAI
  - `text-embedding-3-small` for most use cases (cost-effective)
  - `text-embedding-3-large` for maximum quality (scientific/legal documents)

### 2. Caching Strategy

- **Always enable caching** for production workloads
- Set appropriate cache TTL based on content volatility
  - Static documents: 90 days
  - Frequently updated: 7 days
- Monitor cache hit rates (target: >70%)

### 3. Batch Sizing

- **Small batches (50-100)**: Lower memory, better error recovery
- **Large batches (200-500)**: Faster processing, higher throughput
- Monitor memory usage and adjust accordingly

### 4. Error Handling

```python
from app.services.embedding_service import EmbeddingGenerationError

try:
    results = await embedding_service.generate_embeddings_batch(texts)
except EmbeddingGenerationError as e:
    # Log error
    logger.error(f"Embedding generation failed: {e}")

    # Retry with smaller batch
    if len(texts) > 10:
        # Split into smaller batches
        mid = len(texts) // 2
        results1 = await embedding_service.generate_embeddings_batch(texts[:mid])
        results2 = await embedding_service.generate_embeddings_batch(texts[mid:])
        results = results1 + results2
    else:
        raise
```

### 5. Cost Optimization

- Enable caching to reduce duplicate computations
- Use `text-embedding-3-small` unless you need maximum quality
- Process in batches to reduce API overhead
- Monitor costs via Prometheus metrics
- Set up cost alerts

```python
# Example: Stop processing if cost exceeds budget
MAX_COST = 10.0  # $10 budget
current_cost = 0.0

for batch in batches:
    results = await embedding_service.generate_embeddings_batch(batch)
    batch_cost = sum(r.cost for r in results)
    current_cost += batch_cost

    if current_cost > MAX_COST:
        raise ValueError(f"Cost exceeded budget: ${current_cost:.2f}")
```

## Troubleshooting

### Ollama Connection Issues

**Problem**: `Failed to connect to Ollama at http://localhost:11434`

**Solutions**:
```bash
# 1. Check if Ollama is running
curl http://localhost:11434/api/tags

# 2. Start Ollama if not running
ollama serve

# 3. Verify BGE-M3 model is installed
ollama list | grep bge-m3

# 4. Pull model if missing
ollama pull bge-m3

# 5. Check environment variable
echo $OLLAMA_BASE_URL
```

### OpenAI API Errors

**Problem**: `401 Unauthorized` or `Invalid API key`

**Solutions**:
```bash
# 1. Verify API key is set
echo $OPENAI_API_KEY

# 2. Check API key validity
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 3. Ensure key has embeddings permissions
# Visit https://platform.openai.com/api-keys

# 4. Check for rate limits
# Visit https://platform.openai.com/account/limits
```

### Cache Not Working

**Problem**: Cache hit rate is 0% or cache entries not found

**Solutions**:
```sql
-- 1. Verify cache table exists
SELECT COUNT(*) FROM embeddings_cache;

-- 2. Check for unique constraint violations
SELECT content_hash, model, COUNT(*)
FROM embeddings_cache
GROUP BY content_hash, model
HAVING COUNT(*) > 1;

-- 3. Verify indexes exist
SELECT indexname FROM pg_indexes WHERE tablename = 'embeddings_cache';

-- 4. Check RLS policies
SELECT * FROM pg_policies WHERE tablename = 'embeddings_cache';
```

```python
# 5. Enable debug logging
import logging
logging.getLogger("app.services.embedding_service").setLevel(logging.DEBUG)

# 6. Manually test cache
cache_manager = embedding_service.cache_manager
cached = await cache_manager.get_cached_embedding("test content", "bge-m3")
print(f"Cached result: {cached}")
```

### High Memory Usage

**Problem**: Memory usage spikes during batch processing

**Solutions**:
```python
# 1. Reduce batch size
config.batch_size = 50  # Down from 100

# 2. Process in smaller chunks
async def process_with_memory_limit(texts, max_memory_mb=500):
    results = []
    current_memory = psutil.Process().memory_info().rss / 1024 / 1024

    for i in range(0, len(texts), config.batch_size):
        batch = texts[i:i + config.batch_size]
        batch_results = await embedding_service.generate_embeddings_batch(batch)
        results.extend(batch_results)

        # Check memory
        new_memory = psutil.Process().memory_info().rss / 1024 / 1024
        if new_memory > max_memory_mb:
            # Clear some cache or wait
            import gc
            gc.collect()

    return results

# 3. Monitor memory via Prometheus
# process_resident_memory_bytes
```

### Slow Performance

**Problem**: Embedding generation takes too long

**Solutions**:
```python
# 1. Enable caching
config.cache_enabled = True

# 2. Increase batch size (if memory allows)
config.batch_size = 200

# 3. Use faster model
config.provider = "ollama"  # Local, no network latency
config.model = "bge-m3"

# 4. Parallelize across files
import asyncio

async def process_multiple_files(file_ids):
    tasks = [
        process_document_embeddings(file_id)
        for file_id in file_ids
    ]
    results = await asyncio.gather(*tasks)
    return results

# 5. Check network latency (OpenAI)
import time
start = time.time()
result = await embedding_service.generate_embedding("test")
latency = time.time() - start
print(f"API latency: {latency:.2f}s")
```

## API Reference

### EmbeddingConfig

```python
@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation"""

    provider: str = "ollama"  # "ollama" or "openai"
    model: str = "bge-m3"  # Model name
    dimensions: int = 1024  # Embedding dimensions
    batch_size: int = 100  # Batch processing size
    cache_enabled: bool = True  # Enable caching
    cache_ttl: int = 2592000  # Cache TTL (30 days)
    max_retries: int = 3  # Max retry attempts
    retry_delay: float = 1.0  # Retry delay (seconds)

    # Provider-specific
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: Optional[str] = None
```

### EmbeddingResult

```python
@dataclass
class EmbeddingResult:
    """Result of embedding generation"""

    embedding: List[float]  # The embedding vector
    dimensions: int  # Vector dimensions
    model: str  # Model used
    chunk_id: Optional[str] = None  # Associated chunk ID
    content_hash: Optional[str] = None  # Content hash
    from_cache: bool = False  # Was retrieved from cache
    cost: float = 0.0  # Generation cost (USD)
    generation_time: float = 0.0  # Time taken (seconds)
```

### EmbeddingService Methods

```python
class EmbeddingService:
    """Main embedding service"""

    async def generate_embedding(
        self,
        text: str,
        chunk_id: Optional[str] = None,
        use_cache: bool = True
    ) -> EmbeddingResult:
        """Generate embedding for a single text"""

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        chunk_ids: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts"""

    async def invalidate_cache(
        self,
        chunk_id: str
    ) -> bool:
        """Invalidate cached embedding for a chunk"""
```

### EmbeddingCacheManager Methods

```python
class EmbeddingCacheManager:
    """Manages embedding cache in Supabase"""

    async def get_cached_embedding(
        self,
        content: str,
        model: str
    ) -> Optional[List[float]]:
        """Retrieve cached embedding"""

    async def store_embedding(
        self,
        content: str,
        embedding: List[float],
        model: str,
        chunk_id: Optional[str] = None,
        dimensions: int = 1024,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Store embedding in cache"""

    async def invalidate_cache(
        self,
        chunk_id: str
    ) -> bool:
        """Invalidate cache for a chunk"""
```

### Factory Functions

```python
def get_embedding_service(
    supabase_storage=None,
    monitoring_service=None
) -> EmbeddingService:
    """Get singleton embedding service (auto-configured from env)"""

def get_ollama_embedding_service(
    supabase_storage=None,
    monitoring_service=None,
    model: str = "bge-m3"
) -> EmbeddingService:
    """Get Ollama-configured embedding service"""

def get_openai_embedding_service(
    supabase_storage=None,
    monitoring_service=None,
    model: str = "text-embedding-3-small"
) -> EmbeddingService:
    """Get OpenAI-configured embedding service"""
```

---

## Additional Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [BGE-M3 Model Card](https://huggingface.co/BAAI/bge-m3)
- [Supabase pgvector Guide](https://supabase.com/docs/guides/ai/vector-columns)
- [Empire Monitoring Guide](./MONITORING_GUIDE.md)

---

**Last Updated**: January 2025
**Version**: Empire v7.3
