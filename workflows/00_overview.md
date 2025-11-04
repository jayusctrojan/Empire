# Empire v7.2 - Web Service Orchestration Overview
## Python/FastAPI Implementation Architecture

---

## 1. Introduction

This document provides a comprehensive overview of the Empire v7.2 web service orchestration system - a complete Python/FastAPI implementation that replaces n8n workflows with production-ready microservices.

### What is Empire v7.2?

Empire v7.2 is a document processing and knowledge management system that:
- Ingests documents in multiple formats
- Extracts and chunks text intelligently
- Generates embeddings for semantic search
- Provides hybrid RAG (Retrieval Augmented Generation) search
- Offers a chat interface with persistent memory
- Integrates with CrewAI for multi-agent asset generation

### Why Python/FastAPI vs n8n?

**Advantages of Python/FastAPI Implementation:**
- ✅ Better performance and scalability
- ✅ Easier debugging and testing
- ✅ More flexible error handling
- ✅ Better IDE support and type checking
- ✅ Easier to version control
- ✅ Standard Python ecosystem libraries
- ✅ Better async support
- ✅ Professional API documentation (auto-generated)
- ✅ Easier to deploy and containerize
- ✅ More maintainable codebase

---

## 2. Architecture Overview

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│   (Web UI, Mobile Apps, API Clients, Chat, Neo4j MCP/Claude)   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              API Router Layer                             │  │
│  │  /docs  /upload  /search  /chat  /embeddings  /admin     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Service Layer                                │  │
│  │  • DocumentProcessor  • TextExtractor  • EmbeddingService │  │
│  │  • RAGSearch         • ChatManager     • CrewAIOrchestrator│ │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼──────────────────────┐
        ▼                    ▼                      ▼
┌──────────────┐   ┌──────────────────┐   ┌─────────────────┐
│   Supabase   │   │  Neo4j Docker    │   │  Backblaze B2   │
│  PostgreSQL  │   │  (Mac Studio)    │   │ Object Storage  │
│  + pgvector  │   │  Knowledge Graph │   │                 │
│  User Memory │   │  + Neo4j MCP     │   │                 │
└──────────────┘   └──────────────────┘   └─────────────────┘
        │                    │                      │
        └────────────────────┼──────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬─────────────────────┐
        ▼                    ▼                    ▼                     ▼
┌──────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│    Redis     │   │     Ollama       │   │  BGE-Reranker-v2     │
│   Cache +    │   │    BGE-M3        │   │   (Mac Studio)       │
│   Celery     │   │   (Local/$$)     │   │  Local Reranking     │
└──────────────┘   └──────────────────┘   └──────────────────────┘
```

### 2.2 Data Flow

**Document Upload Flow:**
```
Client → FastAPI → Validate → B2 Upload → Supabase → Queue → Celery Worker
```

**Text Processing Flow:**
```
Celery → Download from B2 → Extract Text → Chunk → Store in Supabase
```

**Embedding Generation Flow:**
```
Celery → Get Chunks → Ollama (BGE-M3) → Store Vectors → Update Status
```

**Search Flow:**
```
Client → FastAPI → Generate Query Embedding → Hybrid Search → Rerank → Return Results
```

**Chat Flow:**
```
Client WebSocket → FastAPI → Search Context → LLM → Stream Response → Save History
```

---

## 3. Technology Stack

### 3.1 Core Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI 0.104+ | REST API endpoints, WebSocket support |
| **Language** | Python 3.11+ | Main programming language |
| **Database** | Supabase (PostgreSQL 15+) | Primary data store |
| **Vector DB** | pgvector | Vector similarity search |
| **Object Storage** | Backblaze B2 | Document file storage |
| **Task Queue** | Celery 5.3+ | Async background processing |
| **Message Broker** | Redis 7+ | Celery broker + caching |
| **Embeddings** | Ollama (BGE-M3) | Local, free embeddings |
| **Embeddings Fallback** | OpenAI (Ada-002) | Cloud fallback |
| **OCR** | Mistral Pixtral-12B | Image text extraction |
| **Reranking** | BGE-Reranker-v2 (Local) | Search result improvement |
| **Memory** | mem-agent MCP | Persistent user memory |
| **Multi-Agent** | CrewAI | Asset generation |

### 3.2 Python Libraries

**Core Dependencies:**
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
python-multipart==0.0.6
websockets==12.0

# Database & Storage
supabase==2.3.0
psycopg2-binary==2.9.9
redis==5.0.1
boto3==1.34.10  # For B2 S3-compatible API

# Task Queue
celery==5.3.4
celery[redis]==5.3.4

# AI & ML
httpx==0.25.2  # For Ollama API calls
openai==1.6.1
# BGE-Reranker-v2 via Ollama (local)

# Document Processing
PyPDF2==3.0.1
python-docx==1.1.0
pandas==2.1.4
openpyxl==3.1.2
python-pptx==0.6.23
pillow==10.1.0

# Utilities
python-magic==0.4.27
hashlib  # Built-in
```

### 3.3 External Services

**Required:**
- Supabase account (free tier available)
- Backblaze B2 account (10GB free)
- Ollama running locally

**Optional:**
- OpenAI API key (fallback embeddings)
- Mistral API key (OCR)

**Local (Mac Studio):**
- BGE-Reranker-v2 via Ollama (local reranking, zero cost)

---

## 4. Project Structure

```
empire-web-service/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entry point
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── documents.py         # Document upload endpoints
│   │       ├── search.py            # Search endpoints
│   │       ├── embeddings.py        # Embedding endpoints
│   │       ├── chat.py              # Chat WebSocket endpoints
│   │       └── admin.py             # Admin endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_processor.py   # Document intake logic
│   │   ├── text_extractor.py       # Text extraction
│   │   ├── chunking.py              # Chunking strategies
│   │   ├── embedding_service.py    # Embedding generation
│   │   ├── rag_search.py            # Hybrid search
│   │   ├── chat_manager.py          # Chat session management
│   │   └── crewai_orchestrator.py  # CrewAI integration
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── document.py              # Pydantic models for documents
│   │   ├── chunk.py                 # Chunk models
│   │   ├── search.py                # Search request/response models
│   │   └── chat.py                  # Chat models
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase_client.py       # Supabase connection
│   │   └── redis_client.py          # Redis connection
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Settings/configuration
│   │   ├── security.py              # Authentication
│   │   └── exceptions.py            # Custom exceptions
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── celery_tasks.py          # Async Celery tasks
│   │
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py            # File handling utilities
│       └── logging_config.py        # Logging setup
│
├── migrations/
│   ├── 01_milestone1_document_intake.sql
│   ├── 02_milestone2_text_extraction.sql
│   ├── 03_milestone3_embeddings.sql
│   ├── 04_milestone4_search.sql
│   ├── 05_milestone5_chat.sql
│   ├── 06_milestone6_monitoring.sql
│   └── 07_milestone7_admin.sql
│
├── tests/
│   ├── __init__.py
│   ├── test_documents.py
│   ├── test_search.py
│   ├── test_embeddings.py
│   └── test_chat.py
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 5. Core Design Principles

### 5.1 Service-Oriented Architecture

Each major feature is implemented as a service class:
- **DocumentProcessor**: Handles file upload and validation
- **TextExtractor**: Extracts text from various formats
- **ChunkingService**: Creates intelligent chunks
- **EmbeddingService**: Generates vector embeddings
- **RAGSearchService**: Performs hybrid search
- **ChatManager**: Manages chat sessions
- **CrewAIOrchestrator**: Coordinates multi-agent workflows

### 5.2 Async-First Design

- All I/O operations use `async/await`
- Long-running tasks delegated to Celery workers
- FastAPI handles concurrent requests efficiently
- WebSocket support for real-time chat

### 5.3 Error Handling Strategy

```python
# Consistent error handling pattern
try:
    result = await service.process()
    return {"success": True, "data": result}
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except ExternalServiceError as e:
    logger.error(f"External service failed: {e}")
    raise HTTPException(status_code=503, detail="Service temporarily unavailable")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

### 5.4 Configuration Management

All configuration via environment variables using Pydantic Settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str

    # B2
    b2_application_key_id: str
    b2_application_key: str
    b2_bucket_name: str

    # Redis
    redis_url: str

    # Ollama
    ollama_api_url: str = "http://localhost:11434"

    class Config:
        env_file = ".env"
```

---

## 6. Key Features

### 6.1 Document Processing

**Supported Formats:**
- PDF (with OCR fallback)
- Microsoft Office (Word, Excel, PowerPoint)
- Text files (TXT, MD, CSV)
- Structured data (JSON, XML)
- Images (PNG, JPG with OCR)
- Audio/Video (transcription via Whisper)

**Processing Pipeline:**
1. Upload validation (size, type, malware check)
2. Hash-based deduplication
3. Store in Backblaze B2
4. Queue for async processing
5. Extract text based on format
6. Create intelligent chunks
7. Generate embeddings
8. Store in Supabase with vectors

### 6.2 Intelligent Chunking

**Strategies:**
- **Default**: 1000 chars, 200 overlap
- **Technical**: 1500 chars, 300 overlap (for code, APIs)
- **Narrative**: 2000 chars, 400 overlap (for articles, books)
- **Structured**: 800 chars, 100 overlap (for tables, lists)

**Auto-Detection:**
- Code blocks → Technical
- Paragraphs → Narrative
- Lists/tables → Structured

### 6.3 Hybrid Search

**Three Search Modes:**
1. **Vector Search**: Pure semantic similarity using embeddings
2. **Keyword Search**: Full-text search using PostgreSQL
3. **Hybrid Search**: Combines both with configurable weights

**Built-In Enhancements:**
- BGE-Reranker-v2 (local) for better relevance
- Context expansion (surrounding chunks)
- Search result caching

### 6.4 Chat Interface

**Features:**
- WebSocket-based streaming responses
- Persistent session management
- User memory with mem-agent MCP
- Context-aware responses using RAG
- Multi-turn conversation support

---

## 7. Cost Optimization

### 7.1 Embedding Strategy

**Primary: Ollama (Local, FREE)**
- BGE-M3 model (1024 dimensions)
- Runs on Mac Studio or local GPU
- Zero API costs
- Fast inference

**Fallback: OpenAI ($)**
- Ada-002 embeddings
- Only used when Ollama unavailable
- $0.0001 per 1K tokens
- Automatic failover

### 7.2 Storage Costs

**Backblaze B2:**
- First 10GB: FREE
- Additional: $0.005/GB/month
- Bandwidth: First 1GB/day free

**Supabase:**
- Free tier: 500MB database, 2GB bandwidth
- Pro: $25/month for 8GB database

**Redis:**
- Self-hosted: FREE
- Or use Redis Cloud free tier (30MB)

### 7.3 Estimated Monthly Costs

For moderate usage (1000 documents/month, 10K searches):
- Embeddings (Ollama BGE-M3): $0
- Reranking (BGE-Reranker-v2): $0
- Storage (B2): $0-5
- Database (Supabase): $0-25
- OCR (Mistral): ~$5
- **Total: $5-35/month** (saves $3-30/month vs Cohere)

---

## 8. Performance Characteristics

### 8.1 Throughput

- **Document Upload**: 50-100 requests/sec
- **Text Extraction**: 10-20 docs/sec (Celery workers)
- **Embedding Generation**: 100-200 chunks/sec (Ollama)
- **Search Queries**: 200-500 requests/sec (with caching)
- **Chat Messages**: 100+ concurrent WebSocket connections

### 8.2 Latency

- **Upload API**: <100ms
- **Search API**: 50-200ms (depending on result count)
- **Embedding Generation**: 50-100ms per chunk (Ollama)
- **Chat Response**: 200ms first token, streaming thereafter

### 8.3 Scalability

**Horizontal Scaling:**
- Add more FastAPI workers (via Docker)
- Add more Celery workers for processing
- Redis clustering for high availability
- Supabase automatically scales

**Vertical Scaling:**
- Increase Ollama GPU memory for faster embeddings
- Larger Redis cache for more search results
- More powerful database instance

---

## 9. Security Considerations

### 9.1 API Security

- API key authentication
- Rate limiting per client
- CORS configuration
- Input validation (Pydantic)

### 9.2 File Security

- File size limits (default 100MB)
- MIME type validation
- Malware scanning (optional)
- Hash-based deduplication prevents storage abuse

### 9.3 Data Security

- PostgreSQL row-level security (RLS)
- Encrypted storage (B2, Supabase)
- Redis password protection
- Environment variable secrets management

---

## 10. Monitoring & Observability

### 10.1 Logging

- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request/response logging
- Performance metrics logging

### 10.2 Metrics

- Prometheus-compatible metrics endpoint
- Request count, latency, error rates
- Document processing statistics
- Search performance metrics

### 10.3 Health Checks

- `/health` - Basic health check
- `/health/ready` - Readiness probe (for K8s)
- `/health/live` - Liveness probe
- Checks: Database, Redis, Ollama connectivity

---

## 11. Development Workflow

### 11.1 Local Development

```bash
# 1. Clone repository
git clone <repo>
cd empire-web-service

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Start dependencies
docker-compose up -d redis  # Start Redis

# 6. Run migrations
psql $SUPABASE_DB_URL -f migrations/01_milestone1_document_intake.sql
# ... run all migrations

# 7. Start Ollama (in separate terminal)
ollama serve
ollama pull bge-m3

# 8. Start Celery worker (in separate terminal)
celery -A app.tasks.celery_tasks worker --loglevel=info

# 9. Start FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 11.2 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_documents.py

# Run integration tests
pytest tests/integration/
```

### 11.3 Production Deployment

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f web
docker-compose logs -f celery_worker

# Scale workers
docker-compose up -d --scale celery_worker=5
```

---

## 12. Migration from n8n

### 12.1 Mapping n8n to FastAPI

| n8n Component | FastAPI Equivalent |
|---------------|-------------------|
| HTTP Trigger Node | FastAPI endpoint decorator |
| Webhook Node | FastAPI POST endpoint |
| Function Node | Python function |
| Set Node | Variable assignment |
| IF Node | Python if/else |
| Switch Node | Python match/case |
| Loop Node | Python for/while loop |
| Execute Workflow | Service method call |
| HTTP Request Node | httpx async HTTP call |
| Postgres Node | Supabase client call |
| Redis Node | Redis client call |
| Schedule Trigger | Celery beat scheduled task |

### 12.2 Benefits of Migration

✅ **Better Performance**: Native Python is faster than n8n interpretation
✅ **Better Debugging**: Python debuggers, stack traces, IDE support
✅ **Better Testing**: pytest, unittest, integration tests
✅ **Better Type Safety**: Pydantic models, type hints
✅ **Better Version Control**: Git-friendly Python code vs large JSON
✅ **Better Deployment**: Standard Docker containers
✅ **Better Monitoring**: Native Python logging, metrics
✅ **Better Documentation**: Auto-generated FastAPI docs

---

## 13. Next Steps

1. **Read the Milestone Files**: Start with milestone_1_document_intake.md and proceed through milestone_7_admin_tools.md in sequence

2. **Set Up Development Environment**: Follow the local development workflow above

3. **Run Database Migrations**: Use the SQL files in migrations/ directory

4. **Configure External Services**: Set up Supabase, B2, Ollama, etc.

5. **Start Building**: Begin with Milestone 1 and work through each milestone

6. **Test Thoroughly**: Use the testing_validation.md guide

7. **Deploy**: Use deployment_configuration.md for production deployment

---

**Ready to dive deeper?** Continue to `milestone_1_document_intake.md` to start implementation.
