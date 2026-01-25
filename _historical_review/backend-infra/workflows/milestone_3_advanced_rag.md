## 4. Milestone 3: Embeddings and Vector Storage

### 4.1 Supabase Schema - Embeddings

```sql
-- ============================================================================
-- Milestone 3: Embeddings and Vector Storage Schema
-- ============================================================================

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Update document_chunks table to ensure embedding column exists
-- (Already created in Milestone 2, but adding index here)

-- Create vector similarity index for fast searches
-- Using IVFFlat index for better performance on large datasets
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
ON public.document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Alternative: HNSW index (better for smaller datasets, faster queries)
-- CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
-- ON public.document_chunks
-- USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- Embedding generation tracking
CREATE TABLE IF NOT EXISTS public.embedding_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL,
    provider VARCHAR(50) NOT NULL, -- 'ollama', 'openai', 'cohere'
    model_name VARCHAR(100) NOT NULL, -- 'bge-m3', 'text-embedding-ada-002'
    embedding_dimension INTEGER NOT NULL,
    chunks_total INTEGER NOT NULL,
    chunks_processed INTEGER DEFAULT 0,
    chunks_failed INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    processing_time_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (document_id) REFERENCES public.documents(document_id) ON DELETE CASCADE
);

-- Embedding provider statistics
CREATE TABLE IF NOT EXISTS public.embedding_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_embeddings INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0.00,
    avg_processing_time_ms INTEGER,
    success_rate DECIMAL(5, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, model_name, date)
);

-- Function to update embedding job progress
CREATE OR REPLACE FUNCTION update_embedding_job_progress(
    p_job_id UUID,
    p_chunks_processed INTEGER,
    p_chunks_failed INTEGER DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    UPDATE public.embedding_jobs
    SET
        chunks_processed = p_chunks_processed,
        chunks_failed = p_chunks_failed,
        updated_at = NOW(),
        status = CASE
            WHEN p_chunks_processed + p_chunks_failed >= chunks_total THEN 'completed'
            ELSE 'processing'
        END,
        completed_at = CASE
            WHEN p_chunks_processed + p_chunks_failed >= chunks_total THEN NOW()
            ELSE completed_at
        END,
        processing_time_ms = CASE
            WHEN p_chunks_processed + p_chunks_failed >= chunks_total
            THEN EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000
            ELSE processing_time_ms
        END
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record embedding statistics
CREATE OR REPLACE FUNCTION record_embedding_stats(
    p_provider VARCHAR(50),
    p_model_name VARCHAR(100),
    p_embeddings_count INTEGER,
    p_tokens_count INTEGER,
    p_cost_usd DECIMAL(10, 6),
    p_processing_time_ms INTEGER
) RETURNS VOID AS $$
BEGIN
    INSERT INTO public.embedding_stats (
        provider, model_name, date, total_embeddings, total_tokens,
        total_cost_usd, avg_processing_time_ms
    )
    VALUES (
        p_provider, p_model_name, CURRENT_DATE, p_embeddings_count,
        p_tokens_count, p_cost_usd, p_processing_time_ms
    )
    ON CONFLICT (provider, model_name, date)
    DO UPDATE SET
        total_embeddings = embedding_stats.total_embeddings + p_embeddings_count,
        total_tokens = embedding_stats.total_tokens + p_tokens_count,
        total_cost_usd = embedding_stats.total_cost_usd + p_cost_usd,
        avg_processing_time_ms = (
            embedding_stats.avg_processing_time_ms * embedding_stats.total_embeddings +
            p_processing_time_ms * p_embeddings_count
        ) / (embedding_stats.total_embeddings + p_embeddings_count),
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Create indexes for embedding jobs
CREATE INDEX IF NOT EXISTS idx_embedding_jobs_document ON public.embedding_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_embedding_jobs_status ON public.embedding_jobs(status);
CREATE INDEX IF NOT EXISTS idx_embedding_stats_date ON public.embedding_stats(date DESC);
```

### 4.2 Embedding Generation Service

```python
# app/services/embedding_service.py

from typing import Dict, List, Any, Optional, Tuple
import httpx
import numpy as np
from datetime import datetime
import logging
from app.core.config import settings
from app.db.supabase_client import get_supabase_client
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Handles embedding generation using multiple providers:
    - Primary: Ollama with BGE-M3 (local, free)
    - Fallback: OpenAI Ada-002 (cloud, paid)
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

        # Provider configurations
        self.providers = {
            'ollama': {
                'url': settings.OLLAMA_API_URL,
                'model': 'bge-m3',
                'dimension': 1024,
                'cost_per_1k_tokens': 0.0,  # Free!
                'timeout': 30
            },
            'openai': {
                'model': 'text-embedding-ada-002',
                'dimension': 1536,
                'cost_per_1k_tokens': 0.0001,
                'timeout': 30
            }
        }

        self.primary_provider = 'ollama'
        self.fallback_provider = 'openai'

    async def generate_embedding_ollama(self, text: str) -> Tuple[Optional[List[float]], Dict[str, Any]]:
        """
        Generate embedding using Ollama (local)

        Returns:
            Tuple of (embedding_vector, metadata)
        """
        config = self.providers['ollama']

        try:
            start_time = datetime.now()

            async with httpx.AsyncClient(timeout=config['timeout']) as client:
                response = await client.post(
                    f"{config['url']}/api/embeddings",
                    json={
                        'model': config['model'],
                        'prompt': text
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get('embedding')

                    processing_time = (datetime.now() - start_time).total_seconds() * 1000

                    metadata = {
                        'provider': 'ollama',
                        'model': config['model'],
                        'dimension': len(embedding) if embedding else 0,
                        'processing_time_ms': int(processing_time),
                        'tokens': len(text.split()),  # Rough estimate
                        'cost_usd': 0.0
                    }

                    return embedding, metadata
                else:
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    return None, {'error': f"API error: {response.status_code}"}

        except Exception as e:
            logger.error(f"Ollama embedding generation failed: {str(e)}")
            return None, {'error': str(e)}

    async def generate_embedding_openai(self, text: str) -> Tuple[Optional[List[float]], Dict[str, Any]]:
        """
        Generate embedding using OpenAI (fallback)

        Returns:
            Tuple of (embedding_vector, metadata)
        """
        if not self.openai_client:
            return None, {'error': 'OpenAI client not configured'}

        config = self.providers['openai']

        try:
            start_time = datetime.now()

            response = await self.openai_client.embeddings.create(
                model=config['model'],
                input=text
            )

            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            cost = (tokens_used / 1000) * config['cost_per_1k_tokens']

            metadata = {
                'provider': 'openai',
                'model': config['model'],
                'dimension': len(embedding),
                'processing_time_ms': int(processing_time),
                'tokens': tokens_used,
                'cost_usd': round(cost, 6)
            }

            return embedding, metadata

        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {str(e)}")
            return None, {'error': str(e)}

    async def generate_embedding(self, text: str, provider: Optional[str] = None) -> Tuple[Optional[List[float]], Dict[str, Any]]:
        """
        Generate embedding with automatic fallback

        Args:
            text: Text to embed
            provider: Specific provider to use, or None for auto-fallback

        Returns:
            Tuple of (embedding_vector, metadata)
        """
        if not text or not text.strip():
            return None, {'error': 'Empty text provided'}

        # Truncate text if too long
        max_length = 8000  # Safe limit for most models
        if len(text) > max_length:
            text = text[:max_length]
            logger.warning(f"Text truncated to {max_length} characters")

        # Try specified provider or primary
        target_provider = provider or self.primary_provider

        if target_provider == 'ollama':
            embedding, metadata = await self.generate_embedding_ollama(text)
            if embedding:
                return embedding, metadata

            # Fallback to OpenAI if Ollama fails
            logger.warning("Ollama failed, falling back to OpenAI")
            return await self.generate_embedding_openai(text)

        elif target_provider == 'openai':
            return await self.generate_embedding_openai(text)

        else:
            return None, {'error': f'Unknown provider: {target_provider}'}

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
        provider: Optional[str] = None
    ) -> List[Tuple[Optional[List[float]], Dict[str, Any]]]:
        """
        Generate embeddings for multiple texts in batches

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            provider: Specific provider to use

        Returns:
            List of (embedding_vector, metadata) tuples
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            for text in batch:
                embedding, metadata = await self.generate_embedding(text, provider)
                results.append((embedding, metadata))

            logger.info(f"Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

        return results

    async def embed_document_chunks(self, document_id: str) -> Dict[str, Any]:
        """
        Generate embeddings for all chunks of a document

        Returns:
            Dict with success status and statistics
        """
        try:
            # Get all chunks for this document
            chunks_response = self.supabase.table('document_chunks')\
                .select('id, content, chunk_index')\
                .eq('document_id', document_id)\
                .order('chunk_index')\
                .execute()

            chunks = chunks_response.data

            if not chunks:
                return {'success': False, 'error': 'No chunks found for document'}

            # Create embedding job
            job_response = self.supabase.table('embedding_jobs').insert({
                'document_id': document_id,
                'provider': self.primary_provider,
                'model_name': self.providers[self.primary_provider]['model'],
                'embedding_dimension': self.providers[self.primary_provider]['dimension'],
                'chunks_total': len(chunks),
                'status': 'processing',
                'started_at': datetime.now().isoformat()
            }).execute()

            job_id = job_response.data[0]['id']

            # Process chunks
            chunks_processed = 0
            chunks_failed = 0
            total_tokens = 0
            total_cost = 0.0
            processing_times = []

            for chunk in chunks:
                embedding, metadata = await self.generate_embedding(chunk['content'])

                if embedding:
                    # Save embedding to database
                    self.supabase.table('document_chunks').update({
                        'embedding': embedding
                    }).eq('id', chunk['id']).execute()

                    chunks_processed += 1
                    total_tokens += metadata.get('tokens', 0)
                    total_cost += metadata.get('cost_usd', 0.0)
                    processing_times.append(metadata.get('processing_time_ms', 0))
                else:
                    chunks_failed += 1
                    logger.error(f"Failed to embed chunk {chunk['chunk_index']}: {metadata.get('error')}")

                # Update job progress
                self.supabase.rpc('update_embedding_job_progress', {
                    'p_job_id': job_id,
                    'p_chunks_processed': chunks_processed,
                    'p_chunks_failed': chunks_failed
                }).execute()

            # Record statistics
            avg_processing_time = int(np.mean(processing_times)) if processing_times else 0

            self.supabase.rpc('record_embedding_stats', {
                'p_provider': self.primary_provider,
                'p_model_name': self.providers[self.primary_provider]['model'],
                'p_embeddings_count': chunks_processed,
                'p_tokens_count': total_tokens,
                'p_cost_usd': total_cost,
                'p_processing_time_ms': avg_processing_time
            }).execute()

            # Update document status
            if chunks_failed == 0:
                self.supabase.table('documents').update({
                    'processing_status': 'embeddings_complete',
                    'updated_at': datetime.now().isoformat()
                }).eq('document_id', document_id).execute()

            return {
                'success': True,
                'job_id': job_id,
                'chunks_total': len(chunks),
                'chunks_processed': chunks_processed,
                'chunks_failed': chunks_failed,
                'total_tokens': total_tokens,
                'total_cost_usd': round(total_cost, 6),
                'avg_processing_time_ms': avg_processing_time
            }

        except Exception as e:
            logger.error(f"Error embedding document chunks: {str(e)}")
            return {'success': False, 'error': str(e)}
```

### 4.3 Celery Task for Embedding Generation

```python
# app/tasks/celery_tasks.py (add to existing file)

@celery_app.task(name='generate_document_embeddings', bind=True)
def generate_document_embeddings(self, document_id: str) -> Dict[str, Any]:
    """
    Celery task to generate embeddings for all chunks of a document

    Args:
        document_id: Document identifier

    Returns:
        Dict with embedding generation results
    """
    import asyncio
    from app.services.embedding_service import EmbeddingService

    try:
        # Create event loop for async operations
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Initialize service
        embedding_service = EmbeddingService()

        # Generate embeddings
        result = loop.run_until_complete(
            embedding_service.embed_document_chunks(document_id)
        )

        if result['success']:
            logger.info(f"Successfully generated embeddings for document {document_id}: "
                       f"{result['chunks_processed']}/{result['chunks_total']} chunks")
        else:
            logger.error(f"Failed to generate embeddings for document {document_id}: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Error in generate_document_embeddings task: {str(e)}")

        # Update document status to failed
        try:
            supabase = get_supabase_client()
            supabase.table('documents').update({
                'processing_status': 'embeddings_failed',
                'processing_error': str(e)
            }).eq('document_id', document_id).execute()
        except:
            pass

        return {'success': False, 'error': str(e)}
```

### 4.4 FastAPI Endpoints for Embeddings

```python
# app/api/v1/embeddings.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from app.services.embedding_service import EmbeddingService
from app.tasks.celery_tasks import generate_document_embeddings
from app.db.supabase_client import get_supabase_client

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

class EmbedTextRequest(BaseModel):
    text: str
    provider: Optional[str] = None

class EmbedTextResponse(BaseModel):
    embedding: List[float]
    metadata: dict

class EmbedDocumentRequest(BaseModel):
    document_id: str
    async_processing: bool = True

class EmbedDocumentResponse(BaseModel):
    success: bool
    document_id: str
    job_id: Optional[str] = None
    chunks_total: Optional[int] = None
    message: str

@router.post("/text", response_model=EmbedTextResponse)
async def embed_text(request: EmbedTextRequest):
    """
    Generate embedding for a single text
    """
    embedding_service = EmbeddingService()

    embedding, metadata = await embedding_service.generate_embedding(
        text=request.text,
        provider=request.provider
    )

    if not embedding:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embedding: {metadata.get('error', 'Unknown error')}"
        )

    return EmbedTextResponse(embedding=embedding, metadata=metadata)

@router.post("/document", response_model=EmbedDocumentResponse)
async def embed_document(request: EmbedDocumentRequest, background_tasks: BackgroundTasks):
    """
    Generate embeddings for all chunks of a document

    Args:
        async_processing: If True, process in background (recommended for large documents)
    """
    supabase = get_supabase_client()

    # Verify document exists
    doc_response = supabase.table('documents')\
        .select('document_id, processing_status')\
        .eq('document_id', request.document_id)\
        .execute()

    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Document not found")

    if request.async_processing:
        # Queue background task
        task = generate_document_embeddings.delay(request.document_id)

        return EmbedDocumentResponse(
            success=True,
            document_id=request.document_id,
            job_id=task.id,
            message="Embedding generation queued for background processing"
        )
    else:
        # Process synchronously (not recommended for large documents)
        embedding_service = EmbeddingService()
        result = await embedding_service.embed_document_chunks(request.document_id)

        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Embedding generation failed'))

        return EmbedDocumentResponse(
            success=True,
            document_id=request.document_id,
            job_id=result.get('job_id'),
            chunks_total=result.get('chunks_total'),
            message=f"Successfully embedded {result['chunks_processed']}/{result['chunks_total']} chunks"
        )

@router.get("/document/{document_id}/status")
async def get_embedding_status(document_id: str):
    """
    Get embedding generation status for a document
    """
    supabase = get_supabase_client()

    job_response = supabase.table('embedding_jobs')\
        .select('*')\
        .eq('document_id', document_id)\
        .order('created_at', desc=True)\
        .limit(1)\
        .execute()

    if not job_response.data:
        raise HTTPException(status_code=404, detail="No embedding jobs found for document")

    return job_response.data[0]

@router.get("/stats")
async def get_embedding_stats(days: int = 7):
    """
    Get embedding generation statistics

    Args:
        days: Number of days to include in statistics
    """
    supabase = get_supabase_client()

    stats_response = supabase.table('embedding_stats')\
        .select('*')\
        .gte('date', f'now() - interval \'{days} days\'')\
        .order('date', desc=True)\
        .execute()

    return {
        'days': days,
        'statistics': stats_response.data
    }
```

---

