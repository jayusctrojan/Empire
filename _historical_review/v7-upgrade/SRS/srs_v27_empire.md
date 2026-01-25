# AI Empire File Processing System - Software Requirements Specification (SRS)

**Document Version:** 2.7  
**Date:** December 20, 2024  
**Project:** AI Empire Organizational Intelligence Platform  
**System:** File Processing Workflow V2.7 with Hybrid RAG Integration  

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for the AI Empire File Processing System, an automated workflow that processes course materials, documents, and media files to generate organizational intelligence and AI agent recommendations for business optimization. **Version 2.7 adds hybrid RAG capabilities with SQL-based record management, enhanced session correlation, contextual embeddings, and metadata enrichment while maintaining Airtable integration for human-readable audit trails.**

### 1.2 Scope
The AI Empire File Processing System encompasses:
- Multi-format file processing and conversion
- **Hash-based change detection and record management**
- **SQL-backed session correlation with validation**
- Parallel image extraction and vision analysis with session correlation
- Enhanced video processing with vision analysis
- Audio-only transcription for pure audio files
- **Contextual embeddings for improved retrieval accuracy**
- **Dynamic metadata enrichment and filtering**
- Content analysis and chunking via LlamaIndex + LangExtract
- Vector storage in Pinecone for retrieval
- **Hybrid search orchestration (vector + graph)**
- Multi-agent organizational intelligence analysis via CrewAI
- Comprehensive course documentation generation
- Automated storage and audit trail management
- Enterprise security with Lakera Guard prompt injection protection
- Comprehensive Prometheus monitoring and alerting
- Real-time observability with Arize Phoenix
- Systematic testing with DeepEval framework

### 1.3 Document Conventions
- **Functional Requirements** are prefixed with FR-
- **Non-Functional Requirements** are prefixed with NFR-
- **Business Rules** are prefixed with BR-
- **Technical Constraints** are prefixed with TC-
- **Observability Requirements** are prefixed with OR-
- **Testing Requirements** are prefixed with TR-
- **Security Requirements** are prefixed with SR-
- **Monitoring Requirements** are prefixed with MR-
- **Hybrid RAG Requirements** are prefixed with HR-

### 1.4 Intended Audience
- Development Team
- Product Managers
- System Administrators
- Business Stakeholders
- QA Engineers
- Security Teams
- DevOps Engineers
- Data Engineers

---

## 2. Overall Description

### 2.1 Product Perspective
The AI Empire File Processing System is a comprehensive workflow automation platform built on n8n that orchestrates multiple AI services to transform raw course materials into actionable organizational intelligence. **Version 2.7 introduces a hybrid approach combining SQL (Supabase) for performance-critical operations with Airtable for human-readable audit trails, implementing key features from state-of-the-art RAG architectures for improved retrieval accuracy and processing efficiency.**

### 2.2 Product Functions
- **Dual Input Processing:** HTML interface uploads and Backblaze file monitoring
- **Change Detection:** Hash-based record management to skip unchanged documents
- **Format Detection & Conversion:** Support for 40+ file formats including PDF, Office documents, audio, video, and images
- **Parallel Processing Architecture:** Simultaneous text and image extraction with SQL-backed session correlation
- **Contextual Processing:** Context-aware embeddings for 30-40% better retrieval
- **Metadata Enrichment:** AI-powered document classification and tagging
- **Hybrid Search:** Combined vector and graph search with reranking
- **Comprehensive Image Processing:** Vision analysis for documents, articles, and video content
- **Advanced Video Processing:** Frame extraction and vision analysis for educational content
- **Audio-Only Processing:** Dedicated Soniox transcription for pure audio files
- **Content Processing:** LlamaIndex + LangExtract for chunking, embedding generation, and structured extraction
- **Vector Storage:** Immediate Pinecone storage with metadata for advanced filtering
- **AI Analysis:** CrewAI multi-agent analysis for organizational recommendations
- **Documentation Generation:** Automated creation of comprehensive reports with visual content timelines
- **Audit & Compliance:** Dual-storage audit trail (SQL + Airtable) and notification system

### 2.3 User Classes and Characteristics
- **Content Processors:** Upload and monitor course materials with rich multimedia content
- **Business Analysts:** Review generated reports including comprehensive visual content analysis
- **Executives:** Receive notifications and approve implementation plans
- **System Administrators:** Monitor workflow performance and troubleshoot issues using Phoenix dashboards and Prometheus metrics
- **Security Teams:** Monitor security threats and prompt injection attempts
- **DevOps Engineers:** Configure alerts, dashboards, and monitoring systems
- **QA Engineers:** Create and maintain DeepEval test suites for system validation
- **Data Engineers:** Manage hybrid data architecture and optimize queries

### 2.4 Operating Environment
- **Orchestration Platform:** n8n (https://jb-n8n.onrender.com)
- **Cloud Infrastructure:** Render.com services
- **Storage:** Backblaze B2 cloud storage, Airtable for audit trails
- **SQL Database:** Supabase (PostgreSQL) for record management and session correlation
- **Vector Database:** Pinecone with enhanced metadata support
- **Processing Services:** LlamaIndex (with hybrid features), CrewAI, Soniox, MarkItDown MCP, Hyperbolic Vision AI
- **Security:** Lakera Guard (integrated across all services)
- **Monitoring:** Prometheus metrics (integrated across all services)
- **Observability:** Arize Phoenix (embedded in LlamaIndex service)
- **Testing Framework:** DeepEval with Confident AI integration
- **Reranking:** Cohere API for hybrid search optimization

---

## 3. System Features

### 3.1 Hybrid Record Management System (NEW IN V2.7)

#### 3.1.1 Hash-Based Change Detection (Node HR-1)
**HR-001:** The system SHALL compute SHA-256 hash for all document content  
**HR-002:** The system SHALL check existing document hash before processing  
**HR-003:** The system SHALL skip processing if hash matches existing record  
**HR-004:** The system SHALL update vectors only when hash changes  
**HR-005:** The system SHALL maintain hash history in SQL database  
**HR-006:** The system SHALL sync record changes to Airtable for audit  

#### 3.1.2 Record Manager API (Node HR-2)
**HR-007:** The system SHALL expose REST endpoint `/hybrid/record/check` for hash comparison  
**HR-008:** The system SHALL expose REST endpoint `/hybrid/record/create` for new records  
**HR-009:** The system SHALL expose REST endpoint `/hybrid/record/update` for record updates  
**HR-010:** The system SHALL return action directive: "skip", "new", or "update"  
**HR-011:** The system SHALL handle concurrent record operations safely  
**HR-012:** The system SHALL maintain referential integrity with vector storage  

#### 3.1.3 Vector Cleanup Management
**HR-013:** The system SHALL delete orphaned vectors when documents are updated  
**HR-014:** The system SHALL track vector IDs associated with each document  
**HR-015:** The system SHALL perform batch vector deletion for efficiency  
**HR-016:** The system SHALL verify vector deletion before creating new ones  
**HR-017:** The system SHALL log all vector operations for debugging  

### 3.2 Enhanced Session Correlation System (ENHANCED IN V2.7)

#### 3.2.1 SQL-Backed Session Management (Node HR-3)
**HR-018:** The system SHALL create sessions in PostgreSQL for reliability  
**HR-019:** The system SHALL track multiple processing paths per session  
**HR-020:** The system SHALL validate path completion before merging  
**HR-021:** The system SHALL store correlation data as JSONB for flexibility  
**HR-022:** The system SHALL implement session timeout handling  
**HR-023:** The system SHALL provide session status API endpoints  

#### 3.2.2 Parallel Path Validation (Node HR-4)
**HR-024:** The system SHALL expose REST endpoint `/hybrid/session/create`  
**HR-025:** The system SHALL expose REST endpoint `/hybrid/session/update`  
**HR-026:** The system SHALL expose REST endpoint `/hybrid/session/validate`  
**HR-027:** The system SHALL reject merges with incomplete paths  
**HR-028:** The system SHALL maintain path execution order  
**HR-029:** The system SHALL handle partial failures gracefully  

### 3.3 Contextual Embeddings System (NEW IN V2.7)

#### 3.3.1 Context Generation (Node HR-5)
**HR-030:** The system SHALL generate contextual descriptions for each chunk  
**HR-031:** The system SHALL use LLM to create 2-3 sentence contexts  
**HR-032:** The system SHALL combine context with chunk before embedding  
**HR-033:** The system SHALL preserve original chunks for reference  
**HR-034:** The system SHALL process contexts in parallel for efficiency  
**HR-035:** The system SHALL make contextual embeddings configurable  

#### 3.3.2 Enhanced Embedding API (Node HR-6)
**HR-036:** The system SHALL expose REST endpoint `/hybrid/embeddings/contextual`  
**HR-037:** The system SHALL support batch chunk processing  
**HR-038:** The system SHALL return both enhanced and original text  
**HR-039:** The system SHALL track context generation metrics  
**HR-040:** The system SHALL cache contexts for repeated chunks  

### 3.4 Metadata Enrichment System (NEW IN V2.7)

#### 3.4.1 Dynamic Metadata Configuration (Node HR-7)
**HR-041:** The system SHALL store metadata field configurations in SQL  
**HR-042:** The system SHALL support custom metadata fields per deployment  
**HR-043:** The system SHALL validate metadata values against allowed lists  
**HR-044:** The system SHALL expose REST endpoint `/hybrid/metadata/fields`  
**HR-045:** The system SHALL cache metadata configurations for performance  

#### 3.4.2 AI-Powered Classification (Node HR-8)
**HR-046:** The system SHALL classify documents using configured metadata fields  
**HR-047:** The system SHALL generate document summaries automatically  
**HR-048:** The system SHALL expose REST endpoint `/hybrid/metadata/enrich`  
**HR-049:** The system SHALL store metadata in both SQL and vector store  
**HR-050:** The system SHALL support metadata-based filtering in searches  

### 3.5 Hybrid Search Orchestration (NEW IN V2.7)

#### 3.5.1 Multi-Source Search (Node HR-9)
**HR-051:** The system SHALL support vector similarity search via Pinecone  
**HR-052:** The system SHALL support knowledge graph search (when configured)  
**HR-053:** The system SHALL combine results from multiple sources  
**HR-054:** The system SHALL expose REST endpoint `/hybrid/search`  
**HR-055:** The system SHALL support search type selection: "vector", "graph", or "hybrid"  

#### 3.5.2 Result Reranking (Node HR-10)
**HR-056:** The system SHALL integrate with Cohere reranking API  
**HR-057:** The system SHALL deduplicate results by content hash  
**HR-058:** The system SHALL preserve source attribution  
**HR-059:** The system SHALL return top-k results after reranking  
**HR-060:** The system SHALL track reranking performance metrics  

### 3.6 Dual Storage Architecture (NEW IN V2.7)

#### 3.6.1 SQL Performance Layer
**HR-061:** The system SHALL use PostgreSQL for record management  
**HR-062:** The system SHALL use PostgreSQL for session correlation  
**HR-063:** The system SHALL use PostgreSQL for metadata storage  
**HR-064:** The system SHALL implement connection pooling for efficiency  
**HR-065:** The system SHALL use JSONB for flexible data structures  

#### 3.6.2 Airtable Audit Layer
**HR-066:** The system SHALL sync all operations to Airtable  
**HR-067:** The system SHALL maintain human-readable audit logs  
**HR-068:** The system SHALL store processing statistics in Airtable  
**HR-069:** The system SHALL link SQL records to Airtable records  
**HR-070:** The system SHALL handle Airtable API failures gracefully  

### 3.7 Dual Input Processing System (EXISTING - ENHANCED)

#### 3.7.1 HTML Interface Webhook (Node 1a)
**FR-001:** The system SHALL accept file uploads via HTTP POST requests to `/content-upload` endpoint  
**FR-002:** The system SHALL validate uploaded content type (URL or file)  
**FR-003:** The system SHALL return immediate acknowledgment with processing ID and timestamp  
**FR-004:** The system SHALL support course and module metadata specification  
**FR-005:** The system SHALL generate unique session IDs for correlation tracking  
**HR-071:** The system SHALL check document hash before processing (NEW)  
**SR-001:** The system SHALL scan all uploaded content with Lakera Guard before processing  
**MR-001:** The system SHALL track upload metrics and security scan results  

#### 3.7.2 Backblaze File Monitor (Node 1b)
**FR-006:** The system SHALL monitor Backblaze B2 `pending/` folder every 5 minutes  
**FR-007:** The system SHALL detect new files modified within the last 5 minutes  
**FR-008:** The system SHALL extract course/module information from file path structure  
**FR-009:** The system SHALL handle B2 API authentication and error responses  
**FR-010:** The system SHALL generate unique session IDs for monitored files  
**HR-072:** The system SHALL check file hash against records before processing (NEW)  
**MR-002:** The system SHALL monitor file detection rates and processing queue metrics  

### 3.8 Content Type Processing (EXISTING)

#### 3.8.1 Input Type Classification (Node 2)
**FR-011:** The system SHALL distinguish between HTML interface and Backblaze monitor inputs  
**FR-012:** The system SHALL classify URLs as YouTube, Google Workspace, or general articles  
**FR-013:** The system SHALL validate URL formats and reject invalid URLs  
**FR-014:** The system SHALL maintain session correlation throughout classification  
**FR-015:** The system SHALL preserve source metadata in session context  
**SR-002:** The system SHALL validate URLs for security threats before processing  
**MR-003:** The system SHALL track classification accuracy and processing routes  

### 3.9 Enhanced Content Processing and Storage (EXISTING - ENHANCED)

#### 3.9.1 LlamaIndex + LangExtract Processing (Node 7)
**FR-107:** The system SHALL chunk content using configurable chunk sizes (1000 chars, 200 overlap)  
**FR-108:** The system SHALL generate embeddings using text-embedding-3-small model  
**HR-073:** The system SHALL optionally generate contextual embeddings (NEW)  
**FR-109:** The system SHALL extract keywords, entities, topics, and questions  
**FR-110:** The system SHALL generate content summaries  
**HR-074:** The system SHALL enrich documents with AI-generated metadata (NEW)  
**FR-111:** The system SHALL respect content boundaries (paragraphs, sections, tables)  
**FR-112:** The system SHALL perform structured data extraction with source grounding using LangExtract  

#### 3.9.2 Enhanced Pinecone Vector Storage (Node 8a)
**FR-116:** The system SHALL store vectors in Pinecone immediately after processing  
**FR-117:** The system SHALL use "course_vectors" namespace for organization  
**HR-075:** The system SHALL include enriched metadata in vector storage (NEW)  
**FR-118:** The system SHALL batch vector uploads (100 vectors per batch)  
**FR-119:** The system SHALL implement retry logic for storage failures  
**HR-076:** The system SHALL track vector IDs for cleanup management (NEW)  

---

## 4. API Specifications (NEW IN V2.7)

### 4.1 Record Management API

```
POST /hybrid/record/check
Request: { doc_id, content_hash, document_title?, data_type? }
Response: { exists, action, existing_record?, message }

POST /hybrid/record/create
Request: { doc_id, content_hash, document_title?, data_type? }
Response: { status, record, message }

POST /hybrid/record/update
Request: { doc_id, content_hash, graph_id? }
Response: { status, record, message }
```

### 4.2 Session Management API

```
POST /hybrid/session/create
Request: { source_file, source_type, processing_paths[], course_name?, module_number? }
Response: { status, session_id, session, message }

POST /hybrid/session/update
Request: { session_id, path, status, data? }
Response: { status, session_id, path, path_status, message }

POST /hybrid/session/validate
Request: { session_id, required_paths[] }
Response: { status, valid, correlation_data, session_id, message }

GET /hybrid/session/{session_id}
Response: { status, session, active }
```

### 4.3 Enhancement API

```
POST /hybrid/embeddings/contextual
Request: { chunks[], document, metadata?, enable_contextual }
Response: { status, chunks[], contextual, chunk_count }

POST /hybrid/metadata/enrich
Request: { document_content, document_name, doc_id }
Response: { status, doc_id, metadata, enriched }

GET /hybrid/metadata/fields
Response: { status, fields[], count }
```

### 4.4 Search API

```
POST /hybrid/search
Request: { query, search_type?, metadata_filter?, top_k? }
Response: { status, query, search_type, results[], count }
```

---

## 5. Database Schema Requirements (NEW IN V2.7)

### 5.1 SQL Tables

#### 5.1.1 Record Manager Table
```sql
CREATE TABLE record_manager_v2 (
    id SERIAL PRIMARY KEY,
    doc_id TEXT UNIQUE NOT NULL,
    hash TEXT NOT NULL,
    graph_id TEXT,
    data_type TEXT CHECK (data_type IN ('unstructured', 'tabular')),
    schema JSONB,
    document_title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    airtable_record_id TEXT
);
```

#### 5.1.2 Session Correlation Table
```sql
CREATE TABLE session_correlation (
    session_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    processing_paths JSONB NOT NULL,
    correlation_data JSONB,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

#### 5.1.3 Metadata Fields Table
```sql
CREATE TABLE metadata_fields (
    id SERIAL PRIMARY KEY,
    metadata_name TEXT UNIQUE NOT NULL,
    allowed_values TEXT,
    data_type TEXT,
    is_required BOOLEAN DEFAULT FALSE
);
```

#### 5.1.4 Vector Metadata Table
```sql
CREATE TABLE vector_metadata (
    id SERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 Database Performance
**HR-077:** The system SHALL implement appropriate indexes for query optimization  
**HR-078:** The system SHALL use connection pooling with 2-10 connections  
**HR-079:** The system SHALL implement database query timeout of 60 seconds  
**HR-080:** The system SHALL use GIN indexes for JSONB columns  

---

## 6. Non-Functional Requirements (ENHANCED)

### 6.1 Performance Requirements

**NFR-001:** The system SHALL process files up to 300MB within 30 minutes  
**NFR-002:** The system SHALL handle concurrent processing of up to 5 files  
**NFR-003:** The system SHALL maintain 99% uptime during business hours  
**NFR-043:** The system SHALL complete hash checking within 500ms (NEW)  
**NFR-044:** The system SHALL validate session merge readiness within 1 second (NEW)  
**NFR-045:** The system SHALL generate contextual embeddings at 10+ chunks/second (NEW)  
**NFR-046:** The system SHALL complete metadata enrichment within 5 seconds (NEW)  
**NFR-047:** The system SHALL return hybrid search results within 3 seconds (NEW)  

### 6.2 Scalability Requirements

**NFR-012:** The system SHALL support processing 100+ files per day  
**NFR-013:** The system SHALL handle vector storage of 10,000+ chunks per file  
**NFR-048:** The system SHALL handle 10,000+ documents in record manager (NEW)  
**NFR-049:** The system SHALL support 100+ concurrent sessions (NEW)  
**NFR-050:** The system SHALL scale to 1M+ vectors with metadata filtering (NEW)  

### 6.3 Reliability Requirements

**NFR-020:** The system SHALL implement retry logic for all external API calls  
**NFR-021:** The system SHALL gracefully handle service timeouts and failures  
**NFR-051:** The system SHALL maintain data consistency between SQL and Airtable (NEW)  
**NFR-052:** The system SHALL recover from database connection failures (NEW)  
**NFR-053:** The system SHALL handle partial sync failures gracefully (NEW)  

---

## 7. Business Rules (ENHANCED)

**BR-001:** Files must be processed in order of upload/detection timestamp  
**BR-002:** Vector storage must complete before analysis can proceed  
**BR-026:** Documents with matching hash SHALL always skip processing (NEW)  
**BR-027:** Vector deletion SHALL complete before new vector creation (NEW)  
**BR-028:** Session merge SHALL require all paths to be completed (NEW)  
**BR-029:** Metadata enrichment SHALL occur before vector storage (NEW)  
**BR-030:** Contextual embeddings SHALL be optional per request (NEW)  
**BR-031:** SQL SHALL be source of truth for record state (NEW)  
**BR-032:** Airtable SHALL maintain complete audit history (NEW)  

---

## 8. Technical Constraints (ENHANCED)

**TC-001:** The system must operate within Render.com service limitations  
**TC-002:** Node.js execution environment for n8n workflow processing  
**TC-019:** Supabase free tier limited to 500MB database (NEW)  
**TC-020:** Supabase connection limit of 60 concurrent connections (NEW)  
**TC-021:** Airtable API rate limit of 5 requests per second (NEW)  
**TC-022:** Cohere reranking limited to 1000 documents per request (NEW)  
**TC-023:** PostgreSQL JSONB queries must be optimized for performance (NEW)  

---

## 9. Migration Plan (NEW IN V2.7)

### 9.1 Database Setup
1. Create Supabase project
2. Run migration script `001_hybrid_rag_schema.sql`
3. Configure environment variables
4. Test database connectivity

### 9.2 Service Updates
1. Deploy hybrid-rag-integration branch
2. Initialize hybrid components on startup
3. Verify API endpoints are accessible
4. Test with sample documents

### 9.3 Workflow Updates
1. Add record checking nodes before processing
2. Implement session management for parallel paths
3. Add validation before merge operations
4. Enable contextual embeddings (optional)
5. Configure metadata enrichment (optional)

### 9.4 Rollback Plan
1. Revert to main branch if issues arise
2. Hybrid endpoints return 503 when not initialized
3. Existing endpoints continue functioning
4. No data loss as Airtable maintains full history

---

## 10. Acceptance Criteria (ENHANCED)

### 10.1 Functional Acceptance
- ✅ Successfully detects unchanged documents and skips processing
- ✅ Maintains hash-based records in PostgreSQL
- ✅ Syncs all operations to Airtable for audit
- ✅ Validates session completion before merging
- ✅ Generates contextual embeddings when enabled
- ✅ Enriches documents with configured metadata
- ✅ Performs hybrid search with reranking

### 10.2 Performance Acceptance
- ✅ Hash checking completes in under 500ms
- ✅ Reduces processing by 40-60% through change detection
- ✅ Improves retrieval accuracy by 30-40% with contextual embeddings
- ✅ Handles 100+ documents per hour with full features

### 10.3 Integration Acceptance
- ✅ n8n workflow successfully calls hybrid endpoints
- ✅ SQL and Airtable remain synchronized
- ✅ Existing functionality continues without modification
- ✅ Gradual feature adoption possible

---

## 11. Future Enhancements (V3 Scope)

- **LightRAG Integration:** Full knowledge graph implementation
- **Advanced Reranking:** Multi-stage reranking with learned models
- **Incremental Processing:** Process only changed document sections
- **Distributed SQL:** Scale beyond single PostgreSQL instance
- **Real-time Sync:** Event-driven SQL-Airtable synchronization
- **Custom Embeddings:** Fine-tuned embedding models
- **Query Optimization:** Automatic query plan optimization
- **Archon Integration:** Automated agent deployment and testing
- **Real-time Monitoring:** Agent performance tracking and optimization
- **Advanced Analytics:** Predictive analysis and ROI measurement

---

## 12. Glossary

**Agent:** AI-powered automation system designed to perform specific organizational tasks  
**asyncpg:** High-performance PostgreSQL client for Python with async support  
**Change Detection:** Process of identifying modified documents using hash comparison  
**Chunking:** Process of dividing content into smaller, semantically meaningful segments  
**Cohere Reranking:** ML-based result reordering for improved relevance  
**Contextual Embedding:** Vector representation that includes surrounding context  
**DeepEval:** Open-source LLM evaluation framework for systematic testing and validation  
**Embedding:** Vector representation of text content for semantic similarity matching  
**Frame Extraction:** Process of extracting individual frames from video content for analysis  
**Hybrid RAG:** Retrieval system combining multiple search strategies  
**Hybrid Search:** Search combining vector similarity and graph relationships  
**Lakera Guard:** AI security platform for detecting prompt injection and content threats  
**LangExtract:** Structured data extraction service using LLM capabilities  
**MarkItDown MCP:** Microsoft's format conversion tool for document processing  
**Metadata Enrichment:** Automatic extraction and assignment of document properties  
**Parallel Processing:** Simultaneous execution of multiple processing paths with correlation tracking  
**Phoenix (Arize):** Open-source observability platform for LLM applications and workflows  
**Pinecone:** Vector database service for storing and querying embeddings  
**Prometheus:** Open-source monitoring and alerting toolkit  
**Prompt Injection:** Security attack that manipulates AI model behavior through crafted inputs  
**Record Manager:** System tracking document versions and processing history  
**Reranking:** Re-ordering search results based on relevance scoring  
**Session Correlation:** Data integrity mechanism ensuring content from same source stays together  
**Soniox:** Advanced speech-to-text service with speaker diarization  
**Supabase:** Open-source Firebase alternative providing PostgreSQL database  
**Vector Storage:** Database system optimized for similarity search using vector embeddings  
**Vision Analysis:** AI-powered analysis of visual content in images and video frames  
**Hyperbolic Vision AI:** Llama-3.2-11B-Vision-Instruct model for educational content analysis  

---

**Document Control:**  
- **Author:** AI Empire Development Team  
- **Reviewer:** Product Management, Security Team, DevOps Team, Data Engineering  
- **Approval:** Technical Architecture Committee  
- **Distribution:** Development Team, QA Team, Business Stakeholders, Security Team, Operations Team  
- **Next Review Date:** February 15, 2025  

**Version 2.7 Change Summary:**
- Added comprehensive hybrid RAG integration with SQL-based record management
- Implemented hash-based change detection to prevent redundant processing
- Enhanced session correlation with SQL backing for reliability
- Added contextual embeddings for 30-40% retrieval improvement
- Introduced dynamic metadata enrichment and filtering
- Implemented hybrid search orchestration with reranking
- Maintained full backward compatibility with existing system
- Preserved Airtable integration for human-readable audit trails
- Added detailed API specifications for n8n integration
- Included migration plan and rollback procedures
- Enhanced monitoring to track hybrid system performance
- Added database schema requirements and performance specifications
- Expanded glossary with hybrid RAG terminology
- Updated all sections to reflect dual storage architecture benefits