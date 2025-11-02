# Web Service Orchestration Documentation - Python/FastAPI Implementation
## Empire v7.2 - Complete Implementation Guide

This directory contains the complete Python/FastAPI web service implementation organized into manageable, focused files. This replaces the n8n workflow implementation with production-ready Python services.

## File Organization

### Core Overview & Configuration
- **00_overview.md** - Architecture overview, technology stack, FastAPI structure, and implementation philosophy

### Milestone-Based Implementation Files

- **milestone_1_document_intake.md** - Document intake and classification
  - FastAPI endpoints for upload
  - Hash-based deduplication
  - Backblaze B2 storage integration
  - Supabase database schemas
  - File validation and security

- **milestone_2_universal_processing.md** - Text extraction and chunking
  - Multi-format text extraction (PDF, Word, Excel, etc.)
  - OCR with Mistral Pixtral
  - Intelligent chunking strategies
  - Celery async task processing
  - Supabase schemas for chunks

- **milestone_3_advanced_rag.md** - Embeddings and vector storage
  - Ollama BGE-M3 local embeddings (free)
  - OpenAI embeddings fallback
  - pgvector integration
  - Batch embedding generation
  - Vector index optimization

- **milestone_4_query_processing.md** - Hybrid RAG search implementation
  - Vector similarity search
  - Full-text keyword search
  - Hybrid search combining both
  - BGE-Reranker-v2 (local Mac Studio, zero cost)
  - Context expansion
  - Search caching with Redis

- **milestone_5_chat_ui.md** - Chat interface and memory management
  - FastAPI WebSocket implementation
  - Chat session management
  - Message history storage
  - User memory system (mem-agent MCP integration)
  - Streaming responses
  - Chat context management

- **milestone_6_monitoring.md** - Monitoring and observability
  - Prometheus metrics
  - Logging configuration
  - Health check endpoints
  - Performance monitoring
  - Error tracking

- **milestone_7_admin_tools.md** - Admin tools and management
  - Admin API endpoints
  - Document management
  - User management
  - System statistics
  - Batch operations

### Specialized Reference Files

- **database_setup.md** - Complete Supabase/PostgreSQL schemas
  - All CREATE TABLE statements
  - PostgreSQL functions
  - Indexes and constraints
  - pgvector configuration
  - Migration scripts

- **service_patterns.md** - Python service implementation patterns
  - FastAPI best practices
  - Service layer architecture
  - Error handling patterns
  - Async/await patterns
  - Pydantic models

- **integration_services.md** - External service integrations
  - Ollama configuration
  - OpenAI API integration
  - BGE-Reranker-v2 (local reranking)
  - Mistral Pixtral OCR
  - CrewAI multi-agent system
  - Backblaze B2 SDK
  - Supabase client
  - Redis caching
  - mem-agent MCP server

### Operational Files

- **deployment_configuration.md** - Production deployment
  - Docker Compose configuration
  - Environment variables
  - Nginx reverse proxy
  - SSL/TLS setup
  - Celery worker configuration
  - Redis setup

- **testing_validation.md** - Testing procedures
  - Unit tests with pytest
  - Integration tests
  - API endpoint testing
  - Load testing
  - Validation procedures

## Technology Stack

**Backend Framework**: FastAPI (Python 3.11+)
**Database**: Supabase (PostgreSQL with pgvector)
**Object Storage**: Backblaze B2
**Task Queue**: Celery
**Message Broker**: Redis
**Vector Search**: pgvector
**Embeddings**: Ollama (BGE-M3, local, free) + OpenAI (fallback)
**OCR**: Mistral Pixtral-12B API
**Reranking**: BGE-Reranker-v2 (local Mac Studio, zero cost)
**Memory**: mem-agent MCP server
**Multi-Agent**: CrewAI framework

## Key Features

1. **Document Processing Pipeline**
   - Multi-format upload and validation
   - Hash-based deduplication
   - Automatic text extraction
   - Intelligent chunking

2. **Advanced Search & Retrieval**
   - Hybrid search (keyword + semantic)
   - RAG with context expansion
   - Optional reranking
   - Search result caching

3. **Conversational Interface**
   - WebSocket-based chat
   - Persistent memory with mem-agent
   - Session management
   - Streaming responses

4. **Production-Ready Features**
   - Async task processing
   - Comprehensive error handling
   - Monitoring and metrics
   - Admin API
   - Complete test coverage

## Implementation Approach

### Cost Optimization
- **Primary**: Local Ollama embeddings (BGE-M3) - $0 cost
- **Fallback**: OpenAI Ada-002 - only when Ollama fails
- **Storage**: Backblaze B2 - 10GB free tier, then very affordable
- **Database**: Supabase free tier (500MB, 2GB bandwidth)

### Performance Optimization
- Celery for async long-running tasks
- Redis caching for search results
- Vector indexes for fast similarity search
- Connection pooling
- Batch processing

### Security
- File validation and scanning
- Size limits
- MIME type verification
- Hash-based duplicate detection
- API authentication
- CORS configuration

## Quick Start

1. **Setup Environment**
   ```bash
   cd empire-web-service
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Services**
   - Copy `.env.example` to `.env`
   - Add Supabase credentials
   - Add Backblaze B2 keys
   - Configure Ollama URL

3. **Run Database Migrations**
   ```bash
   psql $SUPABASE_DB_URL -f migrations/01_milestone1.sql
   # ... run all migrations
   ```

4. **Start Services**
   ```bash
   docker-compose up -d
   ```

5. **Access API Documentation**
   - FastAPI Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## File Structure Summary

| File | Purpose | Size Estimate |
|------|---------|---------------|
| INDEX.md | This file | ~300 lines |
| 00_overview.md | Architecture & philosophy | ~400 lines |
| milestone_1_document_intake.md | Upload & intake | ~600 lines |
| milestone_2_universal_processing.md | Text extraction | ~700 lines |
| milestone_3_advanced_rag.md | Embeddings | ~600 lines |
| milestone_4_query_processing.md | Search implementation | ~800 lines |
| milestone_5_chat_ui.md | Chat interface | ~900 lines |
| milestone_6_monitoring.md | Monitoring setup | ~400 lines |
| milestone_7_admin_tools.md | Admin APIs | ~500 lines |
| database_setup.md | SQL schemas | ~1200 lines |
| service_patterns.md | Code patterns | ~500 lines |
| integration_services.md | External services | ~800 lines |
| deployment_configuration.md | Docker & deploy | ~500 lines |
| testing_validation.md | Testing procedures | ~600 lines |

**Total**: ~8,800 lines across 14 focused files (vs 10,231 lines in single n8n file)

## Navigation Guide

| Need | File |
|------|------|
| Start here | 00_overview.md |
| Upload API | milestone_1_document_intake.md |
| Text processing | milestone_2_universal_processing.md |
| Vector embeddings | milestone_3_advanced_rag.md |
| Search API | milestone_4_query_processing.md |
| Chat WebSocket | milestone_5_chat_ui.md |
| Monitoring | milestone_6_monitoring.md |
| Admin API | milestone_7_admin_tools.md |
| Database schemas | database_setup.md |
| Code patterns | service_patterns.md |
| Integrations | integration_services.md |
| Deploy to production | deployment_configuration.md |
| Test suite | testing_validation.md |

## Version Information

- **Document Version**: v7.2 (Python/FastAPI implementation)
- **Python Version**: 3.11+
- **FastAPI Version**: 0.104+
- **Database**: Supabase (PostgreSQL 15+ with pgvector)
- **Vector DB**: pgvector extension
- **Task Queue**: Celery 5.3+
- **Cache**: Redis 7+

## Migration from n8n

This implementation replaces all n8n workflows with Python/FastAPI services:
- **n8n HTTP nodes** → FastAPI endpoints
- **n8n workflows** → Python service classes
- **n8n scheduled triggers** → Celery beat tasks
- **n8n manual triggers** → API endpoints
- **n8n error handling** → Python try/except with logging

## Development Workflow

1. Read milestone files in order (1-7)
2. Implement services following patterns in `service_patterns.md`
3. Set up database using `database_setup.md`
4. Configure integrations from `integration_services.md`
5. Deploy using `deployment_configuration.md`
6. Validate using `testing_validation.md`

---

**Ready to build?** Start with `00_overview.md` to understand the architecture, then proceed through milestones 1-7 in sequence.
