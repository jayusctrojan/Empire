# Architecture Specification: Empire Project Sources

**Version:** 1.0
**Date:** January 4, 2026
**Author:** Claude Code
**Status:** Draft

---

## 1. System Overview

This document describes the technical architecture for enhancing Empire's Projects feature with NotebookLM-style source management. The implementation leverages Empire's existing infrastructure while adding project-scoped source processing and RAG queries.

### 1.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EMPIRE DESKTOP (Tauri/React)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Sidebar   │  │  Projects   │  │   Sources   │  │    Chat     │        │
│  │   (Nav)     │  │    List     │  │   Manager   │  │    View     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                            │                │               │               │
│                            └────────────────┴───────────────┘               │
│                                           │                                  │
│                                    REST API / WebSocket                      │
└───────────────────────────────────────────┼─────────────────────────────────┘
                                            │
┌───────────────────────────────────────────┼─────────────────────────────────┐
│                              EMPIRE API (FastAPI)                            │
├───────────────────────────────────────────┼─────────────────────────────────┤
│                                           │                                  │
│  ┌─────────────────┐  ┌─────────────────┐ │ ┌─────────────────┐             │
│  │  /api/projects  │  │ /api/sources    │ │ │ /api/query      │             │
│  │  CRUD projects  │  │ CRUD sources    │ │ │ Project-scoped  │             │
│  └─────────────────┘  └────────┬────────┘ │ └────────┬────────┘             │
│                                │          │          │                       │
│                       ┌────────▼────────┐ │ ┌────────▼────────┐             │
│                       │  Celery Tasks   │ │ │   RAG Pipeline  │             │
│                       │  (Processing)   │ │ │  (Retrieval)    │             │
│                       └────────┬────────┘ │ └────────┬────────┘             │
│                                │          │          │                       │
└────────────────────────────────┼──────────┼──────────┼───────────────────────┘
                                 │          │          │
┌────────────────────────────────┼──────────┼──────────┼───────────────────────┐
│                           PROCESSING LAYER                                    │
├────────────────────────────────┼──────────┼──────────┼───────────────────────┤
│  ┌─────────────┐  ┌────────────┴───┐  ┌───┴──────────┴───┐  ┌─────────────┐ │
│  │  LlamaParse │  │   yt-dlp       │  │   BeautifulSoup  │  │   Soniox    │ │
│  │  (PDFs)     │  │   (YouTube)    │  │   (Web Scrape)   │  │   (Audio)   │ │
│  └─────────────┘  └────────────────┘  └──────────────────┘  └─────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    BGE-M3 Embeddings (Ollama)                           ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────┼─────────────────────────────────────────────┐
│                           DATA LAYER                                          │
├────────────────────────────────┼─────────────────────────────────────────────┤
│                                │                                              │
│  ┌─────────────────────────────┴─────────────────────────────┐              │
│  │                     SUPABASE (PostgreSQL)                  │              │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│              │
│  │  │  projects   │  │   sources   │  │  source_embeddings  ││              │
│  │  │             │──│             │──│  (pgvector)         ││              │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘│              │
│  └───────────────────────────────────────────────────────────┘              │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Redis (Upstash) │  │  Backblaze B2    │  │  Ollama (Local)  │          │
│  │  Celery Broker   │  │  File Storage    │  │  Embeddings      │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Database Schema

### 2.1 New Tables

#### `project_sources` Table

```sql
-- Migration: create_project_sources_table
CREATE TABLE project_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Source identification
    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN (
        'pdf', 'docx', 'xlsx', 'pptx', 'txt', 'md', 'csv', 'rtf',
        'image', 'audio', 'video', 'youtube', 'website', 'archive'
    )),

    -- Source location
    url TEXT,                          -- For URLs/YouTube
    file_path TEXT,                    -- B2 storage path
    file_name VARCHAR(500),            -- Original filename
    file_size BIGINT,                  -- Size in bytes
    mime_type VARCHAR(100),

    -- Extracted content
    content TEXT,                      -- Extracted text content
    summary TEXT,                      -- AI-generated summary
    metadata JSONB DEFAULT '{}',       -- Additional metadata (pages, duration, etc.)

    -- Processing status
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'ready', 'failed'
    )),
    processing_progress INTEGER DEFAULT 0 CHECK (processing_progress >= 0 AND processing_progress <= 100),
    processing_error TEXT,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_project_sources_project_id ON project_sources(project_id);
CREATE INDEX idx_project_sources_user_id ON project_sources(user_id);
CREATE INDEX idx_project_sources_status ON project_sources(status);
CREATE INDEX idx_project_sources_type ON project_sources(source_type);
CREATE INDEX idx_project_sources_created_at ON project_sources(created_at DESC);

-- Composite index for project + status queries
CREATE INDEX idx_project_sources_project_status ON project_sources(project_id, status);

-- RLS Policies
ALTER TABLE project_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own project sources"
    ON project_sources FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own project sources"
    ON project_sources FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own project sources"
    ON project_sources FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own project sources"
    ON project_sources FOR DELETE
    USING (auth.uid() = user_id);

-- Updated_at trigger
CREATE TRIGGER update_project_sources_updated_at
    BEFORE UPDATE ON project_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

#### `source_embeddings` Table

```sql
-- Migration: create_source_embeddings_table
CREATE TABLE source_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES project_sources(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Chunk information
    chunk_index INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    chunk_metadata JSONB DEFAULT '{}',  -- page number, timestamp, section, etc.

    -- Vector embedding (1024 dimensions for BGE-M3)
    embedding vector(1024) NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_source_embeddings_source_id ON source_embeddings(source_id);
CREATE INDEX idx_source_embeddings_project_id ON source_embeddings(project_id);
CREATE INDEX idx_source_embeddings_user_id ON source_embeddings(user_id);

-- HNSW index for fast vector similarity search
CREATE INDEX idx_source_embeddings_vector ON source_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- RLS Policies
ALTER TABLE source_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own source embeddings"
    ON source_embeddings FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own source embeddings"
    ON source_embeddings FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own source embeddings"
    ON source_embeddings FOR DELETE
    USING (auth.uid() = user_id);
```

### 2.2 Modified Tables

#### Update `projects` Table

```sql
-- Add source-related columns to existing projects table
ALTER TABLE projects ADD COLUMN IF NOT EXISTS
    source_count INTEGER DEFAULT 0;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS
    ready_source_count INTEGER DEFAULT 0;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS
    total_source_size BIGINT DEFAULT 0;

-- Function to update project source stats
CREATE OR REPLACE FUNCTION update_project_source_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE projects SET
        source_count = (
            SELECT COUNT(*) FROM project_sources WHERE project_id = COALESCE(NEW.project_id, OLD.project_id)
        ),
        ready_source_count = (
            SELECT COUNT(*) FROM project_sources
            WHERE project_id = COALESCE(NEW.project_id, OLD.project_id) AND status = 'ready'
        ),
        total_source_size = (
            SELECT COALESCE(SUM(file_size), 0) FROM project_sources
            WHERE project_id = COALESCE(NEW.project_id, OLD.project_id)
        ),
        updated_at = NOW()
    WHERE id = COALESCE(NEW.project_id, OLD.project_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to maintain stats
CREATE TRIGGER update_project_stats_on_source_change
    AFTER INSERT OR UPDATE OR DELETE ON project_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_project_source_stats();
```

---

## 3. API Endpoints

### 3.1 Source Management Endpoints

#### `POST /api/projects/{project_id}/sources`
Create a new source (file upload or URL).

**Request (File Upload - multipart/form-data):**
```
files: File[] (multiple files)
```

**Request (URL - JSON):**
```json
{
    "urls": [
        "https://youtube.com/watch?v=xxx",
        "https://example.com/article"
    ]
}
```

**Response:**
```json
{
    "sources": [
        {
            "id": "uuid",
            "title": "Document.pdf",
            "source_type": "pdf",
            "status": "pending",
            "created_at": "2026-01-04T12:00:00Z"
        }
    ],
    "errors": []
}
```

#### `GET /api/projects/{project_id}/sources`
List all sources for a project.

**Query Parameters:**
- `status`: Filter by status (pending, processing, ready, failed)
- `type`: Filter by source type
- `limit`: Pagination limit (default 50)
- `offset`: Pagination offset

**Response:**
```json
{
    "sources": [
        {
            "id": "uuid",
            "title": "Company Policy.pdf",
            "source_type": "pdf",
            "file_size": 2456789,
            "status": "ready",
            "summary": "This document outlines...",
            "metadata": {
                "pages": 45,
                "word_count": 12500
            },
            "created_at": "2026-01-04T12:00:00Z",
            "processing_completed_at": "2026-01-04T12:01:30Z"
        },
        {
            "id": "uuid",
            "title": "How to Build RAG Systems",
            "source_type": "youtube",
            "url": "https://youtube.com/watch?v=xxx",
            "status": "processing",
            "processing_progress": 45,
            "metadata": {
                "duration": "15:32",
                "channel": "TechChannel",
                "thumbnail": "https://..."
            },
            "created_at": "2026-01-04T12:05:00Z"
        }
    ],
    "total": 4,
    "ready_count": 2,
    "processing_count": 1,
    "failed_count": 1
}
```

#### `GET /api/projects/{project_id}/sources/{source_id}`
Get detailed information about a specific source.

**Response:**
```json
{
    "id": "uuid",
    "title": "Company Policy.pdf",
    "source_type": "pdf",
    "file_path": "projects/xxx/sources/yyy/Company Policy.pdf",
    "file_size": 2456789,
    "mime_type": "application/pdf",
    "content": "Full extracted text...",
    "summary": "AI-generated summary...",
    "status": "ready",
    "metadata": {
        "pages": 45,
        "word_count": 12500,
        "author": "HR Department",
        "created_date": "2025-06-15"
    },
    "chunk_count": 23,
    "created_at": "2026-01-04T12:00:00Z",
    "processing_completed_at": "2026-01-04T12:01:30Z"
}
```

#### `DELETE /api/projects/{project_id}/sources/{source_id}`
Delete a source and its embeddings.

**Response:**
```json
{
    "success": true,
    "message": "Source deleted successfully"
}
```

#### `POST /api/projects/{project_id}/sources/{source_id}/retry`
Retry processing a failed source.

**Response:**
```json
{
    "id": "uuid",
    "status": "pending",
    "retry_count": 1
}
```

### 3.2 Project-Scoped Query Endpoint

#### `POST /api/projects/{project_id}/query`
Query only sources within the specified project.

**Request:**
```json
{
    "query": "What is the PTO policy?",
    "max_results": 10,
    "include_citations": true
}
```

**Response:**
```json
{
    "answer": "According to the Company Policy Manual, employees are entitled to 15 days of PTO per year...",
    "citations": [
        {
            "source_id": "uuid",
            "source_title": "Company Policy Manual.pdf",
            "source_type": "pdf",
            "excerpt": "...employees shall receive fifteen (15) days of paid time off...",
            "metadata": {
                "page": 23,
                "section": "Benefits"
            },
            "relevance_score": 0.94
        },
        {
            "source_id": "uuid",
            "source_title": "Employee Handbook.pdf",
            "source_type": "pdf",
            "excerpt": "...PTO accrues at a rate of 1.25 days per month...",
            "metadata": {
                "page": 8
            },
            "relevance_score": 0.87
        }
    ],
    "sources_searched": 4,
    "processing_time_ms": 1250
}
```

### 3.3 WebSocket Events (Real-time Updates)

```typescript
// Client subscribes to source updates
ws.send({
    type: "subscribe",
    channel: "project_sources",
    project_id: "uuid"
});

// Server sends status updates
{
    type: "source_update",
    source_id: "uuid",
    status: "processing",
    progress: 45,
    message: "Extracting text..."
}

{
    type: "source_update",
    source_id: "uuid",
    status: "ready",
    progress: 100,
    summary: "This document covers..."
}

{
    type: "source_update",
    source_id: "uuid",
    status: "failed",
    error: "Could not extract text from PDF"
}
```

---

## 4. Celery Task Architecture

### 4.1 Task Definitions

```python
# app/tasks/source_processing.py

from celery import shared_task
from app.services.source_processor import SourceProcessor

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def process_source(self, source_id: str):
    """
    Main task to process a source (file or URL).
    Updates status throughout processing.
    """
    processor = SourceProcessor(source_id)

    try:
        # Update status to processing
        processor.update_status("processing", progress=0)

        # Step 1: Extract content (type-specific)
        processor.update_status("processing", progress=20, message="Extracting content...")
        content = processor.extract_content()

        # Step 2: Generate summary
        processor.update_status("processing", progress=50, message="Generating summary...")
        summary = processor.generate_summary(content)

        # Step 3: Chunk content
        processor.update_status("processing", progress=70, message="Chunking content...")
        chunks = processor.chunk_content(content)

        # Step 4: Generate embeddings
        processor.update_status("processing", progress=85, message="Creating embeddings...")
        processor.create_embeddings(chunks)

        # Step 5: Mark as ready
        processor.update_status("ready", progress=100, summary=summary)

        return {"status": "success", "source_id": source_id}

    except Exception as e:
        processor.update_status("failed", error=str(e))
        raise


@shared_task
def process_source_batch(source_ids: list[str]):
    """Process multiple sources in parallel."""
    from celery import group
    job = group(process_source.s(sid) for sid in source_ids)
    return job.apply_async()


@shared_task
def cleanup_failed_sources():
    """Periodic task to clean up stuck processing jobs."""
    # Find sources stuck in 'processing' for > 30 minutes
    # Reset to 'pending' for retry or mark as 'failed'
    pass
```

### 4.2 Source Processor Service

```python
# app/services/source_processor.py

from typing import Optional
from app.services.document_processor import DocumentProcessor
from app.services.url_processing import URLProcessor
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

class SourceProcessor:
    def __init__(self, source_id: str):
        self.source_id = source_id
        self.source = self._load_source()
        self.doc_processor = DocumentProcessor()
        self.url_processor = URLProcessor()
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()

    def extract_content(self) -> str:
        """Extract text content based on source type."""
        source_type = self.source.source_type

        if source_type == "youtube":
            return self.url_processor.extract_youtube_transcript(self.source.url)
        elif source_type == "website":
            return self.url_processor.extract_web_content(self.source.url)
        elif source_type in ["pdf", "docx", "xlsx", "pptx", "txt"]:
            return self.doc_processor.extract_text(
                self.source.file_path,
                source_type
            )
        elif source_type == "image":
            return self.doc_processor.extract_image_text(self.source.file_path)
        elif source_type in ["audio", "video"]:
            return self.doc_processor.transcribe_media(self.source.file_path)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def generate_summary(self, content: str) -> str:
        """Generate AI summary of content."""
        return self.llm_service.summarize(
            content,
            max_length=500,
            style="concise"
        )

    def chunk_content(self, content: str) -> list[dict]:
        """Split content into chunks for embedding."""
        return self.doc_processor.chunk_text(
            content,
            chunk_size=1000,
            overlap=200,
            metadata={"source_id": self.source_id}
        )

    def create_embeddings(self, chunks: list[dict]):
        """Generate and store embeddings for chunks."""
        for i, chunk in enumerate(chunks):
            embedding = self.embedding_service.embed(chunk["content"])
            self._store_embedding(
                chunk_index=i,
                chunk_content=chunk["content"],
                chunk_metadata=chunk.get("metadata", {}),
                embedding=embedding
            )

    def update_status(
        self,
        status: str,
        progress: int = 0,
        message: str = None,
        summary: str = None,
        error: str = None
    ):
        """Update source status and notify via WebSocket."""
        # Update database
        update_data = {
            "status": status,
            "processing_progress": progress
        }
        if status == "processing" and not self.source.processing_started_at:
            update_data["processing_started_at"] = "NOW()"
        if status in ["ready", "failed"]:
            update_data["processing_completed_at"] = "NOW()"
        if summary:
            update_data["summary"] = summary
        if error:
            update_data["processing_error"] = error

        self._update_source(update_data)

        # Send WebSocket notification
        self._notify_status_change(status, progress, message, error)
```

### 4.3 Celery Configuration

```python
# app/core/celery_config.py

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "empire",
    broker=os.getenv("CELERY_BROKER_URL"),
    backend=os.getenv("CELERY_RESULT_BACKEND")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "app.tasks.source_processing.*": {"queue": "source_processing"},
    },

    # Rate limiting
    task_annotations={
        "app.tasks.source_processing.process_source": {
            "rate_limit": "10/m"  # Max 10 sources per minute
        }
    },

    # Periodic tasks
    beat_schedule={
        "cleanup-failed-sources": {
            "task": "app.tasks.source_processing.cleanup_failed_sources",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
        },
    }
)
```

---

## 5. Hybrid RAG Implementation (Project Sources + Global KB)

### 5.1 Query Service

The query service implements a **hybrid approach** that searches both project-specific sources AND the global knowledge base, then intelligently merges results with appropriate weighting.

```python
# app/services/project_query_service.py

from typing import Optional
import asyncio
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.db.supabase import supabase_client

# Weighting for result merging
PROJECT_SOURCE_WEIGHT = 1.0    # Primary - full weight
GLOBAL_KB_WEIGHT = 0.7         # Secondary - reduced weight

class ProjectQueryService:
    def __init__(self, project_id: str, user_id: str):
        self.project_id = project_id
        self.user_id = user_id
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()

    async def query(
        self,
        query: str,
        project_source_limit: int = 8,
        global_kb_limit: int = 5,
        include_citations: bool = True
    ) -> dict:
        """
        Execute a HYBRID RAG query combining:
        1. Project sources (primary) - specific context for this project
        2. Global knowledge base (secondary) - expert frameworks and methodology
        """
        # Step 1: Generate query embedding
        query_embedding = self.embedding_service.embed(query)

        # Step 2: PARALLEL search - project sources AND global KB
        project_chunks, global_chunks = await asyncio.gather(
            self._search_project_sources(query_embedding, project_source_limit),
            self._search_global_kb(query_embedding, global_kb_limit)
        )

        # Step 3: Merge and rerank results with weighting
        merged_chunks = self._merge_and_rerank(
            project_chunks,
            global_chunks
        )

        # Step 4: Build context with source type indicators
        context = self._build_hybrid_context(merged_chunks)

        # Step 5: Generate response with citations from both sources
        response = await self._generate_response(
            query,
            context,
            merged_chunks if include_citations else []
        )

        return response

    async def _search_project_sources(
        self,
        query_embedding: list[float],
        limit: int
    ) -> list[dict]:
        """
        Search embeddings from PROJECT SOURCES only.
        These are the files/URLs specifically attached to this project.
        """
        result = await supabase_client.rpc(
            "match_source_embeddings",
            {
                "query_embedding": query_embedding,
                "match_project_id": self.project_id,
                "match_user_id": self.user_id,
                "match_count": limit,
                "match_threshold": 0.7
            }
        ).execute()

        # Tag results as project sources
        chunks = result.data or []
        for chunk in chunks:
            chunk["source_category"] = "project"
            chunk["weight"] = PROJECT_SOURCE_WEIGHT

        return chunks

    async def _search_global_kb(
        self,
        query_embedding: list[float],
        limit: int
    ) -> list[dict]:
        """
        Search embeddings from GLOBAL KNOWLEDGE BASE.
        This is the existing Empire document repository with domain expertise.
        """
        result = await supabase_client.rpc(
            "match_documents",  # Existing Empire KB search function
            {
                "query_embedding": query_embedding,
                "match_user_id": self.user_id,
                "match_count": limit,
                "match_threshold": 0.7
            }
        ).execute()

        # Tag results as global KB and apply weight penalty
        chunks = result.data or []
        for chunk in chunks:
            chunk["source_category"] = "global_kb"
            chunk["weight"] = GLOBAL_KB_WEIGHT

        return chunks

    def _merge_and_rerank(
        self,
        project_chunks: list[dict],
        global_chunks: list[dict]
    ) -> list[dict]:
        """
        Merge project sources and global KB results with intelligent weighting.
        Project sources are prioritized but global KB fills knowledge gaps.
        """
        # Combine all chunks
        all_chunks = project_chunks + global_chunks

        # Apply weight to similarity scores
        for chunk in all_chunks:
            original_score = chunk.get("similarity", 0)
            weight = chunk.get("weight", 1.0)
            chunk["weighted_score"] = original_score * weight

        # Sort by weighted score (project sources naturally rank higher)
        all_chunks.sort(key=lambda x: x["weighted_score"], reverse=True)

        # Deduplicate similar content (keep highest scoring)
        seen_content_hashes = set()
        deduplicated = []
        for chunk in all_chunks:
            content_hash = hash(chunk.get("chunk_content", "")[:200])
            if content_hash not in seen_content_hashes:
                seen_content_hashes.add(content_hash)
                deduplicated.append(chunk)

        return deduplicated[:13]  # Return top 13 (8 project + 5 global max)

    def _build_hybrid_context(self, chunks: list[dict]) -> str:
        """
        Build context string with clear source type indicators.
        """
        context_parts = []

        # Group by source category for clarity
        project_chunks = [c for c in chunks if c.get("source_category") == "project"]
        global_chunks = [c for c in chunks if c.get("source_category") == "global_kb"]

        if project_chunks:
            context_parts.append("=== PROJECT-SPECIFIC SOURCES ===")
            for chunk in project_chunks:
                source_title = chunk.get("source_title", "Unknown")
                content = chunk.get("chunk_content", "")
                context_parts.append(f"[Project Source: {source_title}]\n{content}")

        if global_chunks:
            context_parts.append("\n=== KNOWLEDGE BASE (Expert Frameworks) ===")
            for chunk in global_chunks:
                source_title = chunk.get("source_title", "Unknown")
                content = chunk.get("chunk_content", "")
                context_parts.append(f"[Knowledge Base: {source_title}]\n{content}")

        return "\n\n---\n\n".join(context_parts)

    def _build_context(self, chunks: list[dict]) -> str:
        """Build context string from relevant chunks."""
        context_parts = []
        for chunk in chunks:
            source_title = chunk.get("source_title", "Unknown")
            content = chunk.get("chunk_content", "")
            context_parts.append(f"[Source: {source_title}]\n{content}")

        return "\n\n---\n\n".join(context_parts)

    async def _generate_response(
        self,
        query: str,
        context: str,
        chunks: list[dict]
    ) -> dict:
        """Generate LLM response with citations."""

        system_prompt = """You are a helpful assistant that answers questions based solely on the provided context.
        Always cite your sources when providing information.
        If the context doesn't contain relevant information, say so clearly."""

        user_prompt = f"""Context:
{context}

Question: {query}

Please answer the question based only on the provided context. Cite specific sources when possible."""

        # Generate response
        answer = await self.llm_service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Build citations
        citations = self._build_citations(chunks)

        return {
            "answer": answer,
            "citations": citations,
            "sources_searched": len(chunks)
        }

    def _build_citations(self, chunks: list[dict]) -> list[dict]:
        """Format chunks as citations."""
        citations = []
        seen_sources = set()

        for chunk in chunks:
            source_id = chunk.get("source_id")
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)

            citations.append({
                "source_id": source_id,
                "source_title": chunk.get("source_title"),
                "source_type": chunk.get("source_type"),
                "excerpt": chunk.get("chunk_content", "")[:200] + "...",
                "metadata": chunk.get("chunk_metadata", {}),
                "relevance_score": chunk.get("similarity", 0)
            })

        return citations
```

### 5.2 Supabase RPC Function

```sql
-- Migration: create_match_source_embeddings_function

CREATE OR REPLACE FUNCTION match_source_embeddings(
    query_embedding vector(1024),
    match_project_id UUID,
    match_user_id UUID,
    match_count INT DEFAULT 10,
    match_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    source_id UUID,
    source_title TEXT,
    source_type TEXT,
    chunk_index INT,
    chunk_content TEXT,
    chunk_metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        se.id,
        se.source_id,
        ps.title AS source_title,
        ps.source_type,
        se.chunk_index,
        se.chunk_content,
        se.chunk_metadata,
        1 - (se.embedding <=> query_embedding) AS similarity
    FROM source_embeddings se
    JOIN project_sources ps ON se.source_id = ps.id
    WHERE
        se.project_id = match_project_id
        AND se.user_id = match_user_id
        AND ps.status = 'ready'
        AND 1 - (se.embedding <=> query_embedding) > match_threshold
    ORDER BY se.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

---

## 6. Frontend Components

### 6.1 Component Structure

```
src/components/
├── projects/
│   ├── ProjectDetailView.tsx      # Main project view (existing, enhanced)
│   ├── SourcesSection.tsx         # New: Sources panel
│   ├── SourceCard.tsx             # New: Individual source display
│   ├── AddSourcesModal.tsx        # New: File/URL input modal
│   ├── SourceStatusBadge.tsx      # New: Status indicator
│   └── CitationsList.tsx          # New: Chat citations display
```

### 6.2 State Management

```typescript
// src/stores/sources.ts

import { create } from 'zustand'

interface Source {
    id: string
    projectId: string
    title: string
    sourceType: SourceType
    url?: string
    filePath?: string
    fileSize?: number
    status: 'pending' | 'processing' | 'ready' | 'failed'
    processingProgress: number
    processingError?: string
    summary?: string
    metadata: Record<string, unknown>
    createdAt: string
}

type SourceType =
    | 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' | 'md' | 'csv'
    | 'image' | 'audio' | 'video' | 'youtube' | 'website'

interface SourcesState {
    sources: Record<string, Source[]>  // projectId -> sources
    isLoading: boolean
    error: string | null

    // Actions
    loadSources: (projectId: string) => Promise<void>
    addSources: (projectId: string, files?: File[], urls?: string[]) => Promise<void>
    deleteSource: (projectId: string, sourceId: string) => Promise<void>
    retrySource: (projectId: string, sourceId: string) => Promise<void>
    updateSourceStatus: (sourceId: string, update: Partial<Source>) => void
}

export const useSourcesStore = create<SourcesState>((set, get) => ({
    sources: {},
    isLoading: false,
    error: null,

    loadSources: async (projectId) => {
        set({ isLoading: true, error: null })
        try {
            const response = await get(`/api/projects/${projectId}/sources`)
            set((state) => ({
                sources: {
                    ...state.sources,
                    [projectId]: response.sources
                },
                isLoading: false
            }))
        } catch (error) {
            set({ error: error.message, isLoading: false })
        }
    },

    addSources: async (projectId, files, urls) => {
        // Implementation
    },

    deleteSource: async (projectId, sourceId) => {
        // Implementation
    },

    retrySource: async (projectId, sourceId) => {
        // Implementation
    },

    updateSourceStatus: (sourceId, update) => {
        // Called from WebSocket handler
        set((state) => {
            // Find and update source across all projects
            const newSources = { ...state.sources }
            for (const projectId in newSources) {
                newSources[projectId] = newSources[projectId].map((s) =>
                    s.id === sourceId ? { ...s, ...update } : s
                )
            }
            return { sources: newSources }
        })
    }
}))
```

### 6.3 WebSocket Integration

```typescript
// src/hooks/useSourceUpdates.ts

import { useEffect } from 'react'
import { useSourcesStore } from '@/stores/sources'
import { getChatClient } from '@/lib/api'

export function useSourceUpdates(projectId: string) {
    const updateSourceStatus = useSourcesStore((s) => s.updateSourceStatus)

    useEffect(() => {
        const client = getChatClient()

        // Subscribe to source updates for this project
        client.send({
            type: 'subscribe',
            channel: 'project_sources',
            project_id: projectId
        })

        // Handle incoming updates
        const handleMessage = (event: MessageEvent) => {
            const data = JSON.parse(event.data)
            if (data.type === 'source_update') {
                updateSourceStatus(data.source_id, {
                    status: data.status,
                    processingProgress: data.progress,
                    processingError: data.error,
                    summary: data.summary
                })
            }
        }

        client.addEventListener('message', handleMessage)

        return () => {
            client.send({
                type: 'unsubscribe',
                channel: 'project_sources',
                project_id: projectId
            })
            client.removeEventListener('message', handleMessage)
        }
    }, [projectId, updateSourceStatus])
}
```

---

## 7. File Storage Structure

### 7.1 Backblaze B2 Organization

```
empire-storage/
├── users/
│   └── {user_id}/
│       └── projects/
│           └── {project_id}/
│               └── sources/
│                   ├── {source_id}/
│                   │   ├── original/
│                   │   │   └── document.pdf
│                   │   └── processed/
│                   │       ├── content.txt
│                   │       └── metadata.json
│                   └── {source_id}/
│                       └── ...
```

---

## 8. Security Considerations

### 8.1 Access Control
- All source operations require authentication
- RLS policies ensure users can only access their own sources
- Project membership validated before source operations
- File uploads scanned for malware

### 8.2 Input Validation
- URL sanitization before processing
- File type validation (magic bytes)
- File size limits enforced
- Content scanning for sensitive data

### 8.3 Rate Limiting
- Source upload: 10 per minute per user
- Processing queue: 10 concurrent per user
- Query API: 60 per minute per user

---

## 9. Monitoring & Observability

### 9.1 Metrics to Track
- Source processing time (by type)
- Processing success/failure rates
- Queue depth and wait times
- Embedding generation time
- Query latency (project-scoped vs global)
- Storage usage per project

### 9.2 Alerts
- Processing queue backup (>100 pending)
- High failure rate (>10% in 1 hour)
- Long processing time (>5 min for single source)
- Storage quota exceeded

---

## 10. Migration Strategy

### Phase 1: Database Setup
1. Create `project_sources` table
2. Create `source_embeddings` table
3. Add columns to `projects` table
4. Create RPC functions

### Phase 2: Backend Services
1. Implement SourceProcessor service
2. Create Celery tasks
3. Add API endpoints
4. Implement WebSocket notifications

### Phase 3: Frontend Integration
1. Create SourcesSection component
2. Add to ProjectDetailView
3. Implement real-time status updates
4. Add project-scoped chat

### Phase 4: Testing & Polish
1. E2E testing
2. Performance optimization
3. Error handling refinement
4. Documentation

---

## Appendix A: API Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Source created |
| 400 | Invalid input (bad URL, unsupported file type) |
| 401 | Unauthorized |
| 403 | Forbidden (not project owner) |
| 404 | Project or source not found |
| 413 | File too large |
| 429 | Rate limit exceeded |
| 500 | Processing error |

---

## Appendix B: Source Type Detection

```python
# app/utils/source_type_detector.py

import magic
from urllib.parse import urlparse

YOUTUBE_PATTERNS = [
    r'youtube\.com/watch',
    r'youtu\.be/',
    r'youtube\.com/shorts',
    r'youtube\.com/embed'
]

MIME_TO_SOURCE_TYPE = {
    'application/pdf': 'pdf',
    'application/msword': 'docx',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.ms-excel': 'xlsx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-powerpoint': 'pptx',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'text/plain': 'txt',
    'text/markdown': 'md',
    'text/csv': 'csv',
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/gif': 'image',
    'audio/mpeg': 'audio',
    'audio/wav': 'audio',
    'video/mp4': 'video',
    'video/quicktime': 'video',
}

def detect_source_type(file: bytes = None, url: str = None) -> str:
    if url:
        for pattern in YOUTUBE_PATTERNS:
            if re.search(pattern, url):
                return 'youtube'
        return 'website'

    if file:
        mime = magic.from_buffer(file, mime=True)
        return MIME_TO_SOURCE_TYPE.get(mime, 'unknown')

    return 'unknown'
```
