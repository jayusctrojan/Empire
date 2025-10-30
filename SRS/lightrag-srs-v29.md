# Software Requirements Specification for AI Empire File Processing System
## Version 2.9
### Advanced Retrieval-Augmented Generation Platform

**Document Status:** Final Draft  
**Date:** September 26, 2025  
**Classification:** Confidential - Internal Use  
**IEEE Std 830-1998 Compliant**

---

## Document Control

### Revision History

| Version | Date | Author | Description | Approval |
|---------|------|--------|-------------|----------|
| 2.9 | 2025-09-26 | Engineering Team | IEEE 830 standardization with enhanced RAG capabilities, hybrid search, long-term memory | Pending |
| 2.8 | 2025-08-15 | Development Team | Streamlined architecture with MarkItDown MCP | Approved |
| 2.7 | 2025-07-01 | Development Team | Hybrid RAG implementation | Approved |
| 2.6 | 2025-05-15 | Architecture Team | Performance optimization requirements | Approved |

### Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Project Manager | | | |
| Technical Lead | | | |
| QA Lead | | | |
| Product Owner | | | |
| Security Officer | | | |

### Distribution List

- Development Team
- Product Management
- Quality Assurance Team
- System Administrators
- Security Team
- DevOps Engineers
- Business Stakeholders

---

## Table of Contents

1. [Introduction](#1-introduction)
   1.1 [Purpose](#11-purpose)
   1.2 [Scope](#12-scope)
   1.3 [Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)
   1.4 [References](#14-references)
   1.5 [Overview](#15-overview)

2. [Overall Description](#2-overall-description)
   2.1 [Product Perspective](#21-product-perspective)
   2.2 [Product Functions](#22-product-functions)
   2.3 [User Characteristics](#23-user-characteristics)
   2.4 [Constraints](#24-constraints)
   2.5 [Assumptions and Dependencies](#25-assumptions-and-dependencies)

3. [Specific Requirements](#3-specific-requirements)
   3.1 [Functional Requirements](#31-functional-requirements)
   3.2 [Non-Functional Requirements](#32-non-functional-requirements)
   3.3 [External Interface Requirements](#33-external-interface-requirements)
   3.4 [System Features](#34-system-features)
   3.5 [Performance Requirements](#35-performance-requirements)
   3.6 [Design Constraints](#36-design-constraints)
   3.7 [Software System Attributes](#37-software-system-attributes)

4. [Supporting Information](#4-supporting-information)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) document provides a complete description of all functions and specifications for the AI Empire File Processing System, version 2.9. This document is intended for all project stakeholders including developers, system architects, quality assurance teams, project managers, and business stakeholders involved in the development, deployment, and maintenance of the AI Empire intelligent document processing and retrieval-augmented generation platform.

The purpose of this SRS is to:
- Define the functional and non-functional requirements for AI Empire v2.9
- Establish the basis for agreement between customers and contractors
- Reduce development effort and project risks
- Provide a basis for estimating costs and schedules
- Facilitate transfer to new personnel
- Serve as a basis for enhancement

### 1.2 Scope

**Product Name:** AI Empire File Processing System  
**Product Version:** 2.9  
**Product Description:** 

The AI Empire File Processing System is an enterprise-grade automated workflow system that processes diverse document formats, multimedia content, and web resources to generate organizational intelligence through retrieval-augmented generation. The system encompasses:

**Core Capabilities:**
- Unified document processing supporting 40+ file formats via MarkItDown MCP
- Intelligent PDF routing with OCR fallback for complex documents
- YouTube content extraction with transcript and frame analysis
- Audio/video transcription with speaker diarization via Soniox
- Hash-based change detection for efficient reprocessing
- Contextual embeddings using Mistral for enhanced retrieval accuracy
- Dynamic metadata enrichment using AI classification
- Hybrid search with Cohere reranking for optimal relevance
- Vector storage with Pinecone and graph storage with LightRAG API
- SQL querying capabilities for tabular data analysis
- Multi-agent organizational intelligence analysis via CrewAI
- Dual agent architecture with optional long-term memory via Zep
- Web scraping capabilities via Firecrawl
- Dual storage architecture with SQL performance layer and audit trail
- Enterprise security with threat monitoring
- Comprehensive observability and monitoring

**System Objectives:**
- Process and convert diverse document formats to standardized Markdown
- Extract actionable intelligence from unstructured content
- Enable efficient retrieval through hybrid RAG architecture
- Support complex SQL queries on extracted tabular data
- Generate organizational recommendations through AI analysis
- Maintain user-specific long-term memory for personalized interactions
- Automatically ingest and process web content
- Maintain complete audit trail and compliance records
- Ensure enterprise-grade security and performance

**Benefits:**
- 30% reduction in document processing time
- 50% reduction in workflow complexity
- 99% uptime availability
- Support for 100+ documents per day
- Unified processing pipeline for maintainability
- Improved search relevance through hybrid approach and reranking
- Personalized user experiences with long-term memory

### 1.3 Definitions, Acronyms, and Abbreviations

| Term/Acronym | Definition |
|--------------|------------|
| **RAG** | Retrieval-Augmented Generation - AI technique combining retrieval and generation |
| **MCP** | Model Context Protocol - Microsoft's document processing protocol |
| **MarkItDown** | Microsoft's universal document converter supporting 40+ formats |
| **LLM** | Large Language Model - AI models for natural language processing |
| **OCR** | Optical Character Recognition - Technology for extracting text from images |
| **LightRAG** | Third-party API service for knowledge graph storage and retrieval |
| **Zep** | Long-term memory service for user-specific information storage |
| **Firecrawl** | Web scraping service for automated content ingestion |
| **Cohere** | AI service providing advanced reranking capabilities |
| **FAISS** | Facebook AI Similarity Search - Vector similarity search library |
| **HNSW** | Hierarchical Navigable Small World - Graph-based similarity search algorithm |
| **CrewAI** | Multi-agent AI framework for collaborative intelligence |
| **n8n** | Workflow automation platform for orchestration |
| **Pinecone** | Cloud-native vector database for similarity search |
| **Soniox** | Speech-to-text transcription service with diarization |
| **SHA-256** | Secure Hash Algorithm - Cryptographic hash function |
| **JWT** | JSON Web Token - Standard for secure information transmission |
| **RBAC** | Role-Based Access Control - Security access control method |
| **gRPC** | Google Remote Procedure Call - High-performance RPC framework |
| **REST** | Representational State Transfer - Architectural style for APIs |
| **QPS** | Queries Per Second - Performance metric |
| **SLA** | Service Level Agreement - Service performance commitment |
| **B2** | Backblaze B2 - Cloud object storage service |

### 1.4 References

1. **IEEE Std 830-1998:** IEEE Recommended Practice for Software Requirements Specifications
2. **ISO/IEC 25010:2011:** Systems and Software Quality Requirements and Evaluation (SQuaRE)
3. **OpenAPI Specification v3.1.0:** API Documentation Standard
4. **NIST Cybersecurity Framework v1.1:** Security Guidelines
5. **GDPR:** General Data Protection Regulation Compliance Guidelines
6. **SOC 2 Type II:** Service Organization Control Requirements
7. **Microsoft MarkItDown Documentation:** Universal Document Converter Specifications
8. **Pinecone Documentation:** Vector Database Best Practices
9. **CrewAI Framework Guide:** Multi-Agent System Architecture
10. **n8n Workflow Documentation:** Automation Platform Guidelines
11. **Cohere Reranking API:** Advanced Search Result Optimization
12. **Zep Memory API:** Long-term User Memory Management
13. **Firecrawl Documentation:** Web Scraping Best Practices
14. **LightRAG API Documentation:** Knowledge Graph Integration Guide

### 1.5 Overview

This document is organized following IEEE Std 830-1998 structure:

- **Section 1** provides introductory information about the SRS document
- **Section 2** presents the general factors affecting the product and its requirements
- **Section 3** contains all specific requirements organized by category
- **Section 4** provides supporting information including appendices

Each requirement is uniquely identified using the following convention:
- **FR-XXX:** Functional Requirements
- **NFR-XXX:** Non-Functional Requirements
- **STR-XXX:** Streamlined Architecture Requirements (v2.8+)
- **HR-XXX:** Hybrid RAG Requirements
- **SR-XXX:** Security Requirements
- **OR-XXX:** Observability Requirements
- **TR-XXX:** Testing Requirements
- **BR-XXX:** Business Rules
- **TC-XXX:** Technical Constraints

---

## 2. Overall Description

### 2.1 Product Perspective

#### 2.1.1 System Context

The AI Empire File Processing System operates as a comprehensive middleware platform within the enterprise architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Enterprise Ecosystem                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input Sources                    Output Systems            │
│  ┌────────────┐                  ┌────────────────┐       │
│  │ HTML Upload│                  │Business Intel. │       │
│  └────────────┘                  └────────────────┘       │
│  ┌────────────┐     ┌────────┐   ┌────────────────┐       │
│  │Backblaze B2│────▶│AI Empire──▶│Analytics Dash. │       │
│  └────────────┘     └────────┘   └────────────────┘       │
│  ┌────────────┐          │        ┌────────────────┐       │
│  │YouTube URLs│          │        │Executive Reports│       │
│  └────────────┘          │        └────────────────┘       │
│  ┌────────────┐          │        ┌────────────────┐       │
│  │Web Scraping│          │        │User Interactions│       │
│  └────────────┘          │        └────────────────┘       │
│                          │                                  │
│                    ┌──────────┐                            │
│                    │Supporting│                            │
│                    │ Services │                            │
│                    └──────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

#### 2.1.2 System Interfaces

The AI Empire system interfaces with multiple external systems:

**Upstream Systems:**
- Document storage systems (Backblaze B2)
- Web interfaces (HTML upload forms)
- Content platforms (YouTube API)
- Web scraping targets (via Firecrawl)
- File systems (local/network storage)

**Processing Services:**
- MarkItDown MCP Server (primary document processor)
- Mistral OCR API (complex PDF processing)
- Mistral API (contextual embeddings)
- Soniox API (audio/video transcription)
- OpenAI API (embeddings and analysis)
- Cohere API (search result reranking)
- CrewAI Framework (multi-agent intelligence)
- Firecrawl API (web content extraction)

**Storage Systems:**
- PostgreSQL/Supabase (record management, sessions, tabular data)
- Pinecone (vector database with metadata)
- LightRAG API (knowledge graph storage)
- Airtable (audit trail and human-readable logs)
- Backblaze B2 (object storage)
- Zep (user-specific long-term memory)

**Monitoring & Security:**
- Prometheus (metrics collection)
- Arize Phoenix (ML observability)
- Lakera Guard (security monitoring)
- DeepEval (testing framework)

### 2.2 Product Functions

#### 2.2.1 Primary Functions

1. **Unified Document Processing**
   - Convert 40+ file formats to Markdown via MarkItDown MCP
   - Intelligent routing of complex PDFs to OCR services
   - Preserve document structure and formatting
   - Extract embedded content (images, tables, metadata)

2. **Multimedia Processing**
   - YouTube transcript extraction with fallback hierarchy
   - Optional frame extraction and analysis
   - Audio/video transcription with speaker diarization
   - Support for all major audio/video formats

3. **Web Content Ingestion**
   - Automated web scraping via Firecrawl
   - Scheduled crawling capabilities
   - JavaScript-rendered content handling
   - Clean Markdown extraction from web pages

4. **Content Intelligence**
   - Generate contextual embeddings using Mistral for improved retrieval
   - Extract structured data (frameworks, concepts, actions)
   - AI-powered document classification and summarization
   - Multi-agent analysis for organizational recommendations
   - SQL querying for tabular data analysis

5. **Hybrid RAG System**
   - Hash-based change detection to avoid reprocessing
   - Hybrid search combining vector and keyword approaches
   - Cohere reranking for optimal result relevance
   - Knowledge graph integration via LightRAG API
   - SQL-backed record management for performance
   - Vector storage with enriched metadata in Pinecone

6. **Memory and Agent Management**
   - User-specific long-term memory via Zep
   - Dual agent architecture (with/without memory)
   - Session-based correlation tracking
   - Automatic memory updates and retrieval

7. **Workflow Orchestration**
   - Automated file monitoring and processing
   - Error handling and retry mechanisms
   - Parallel processing optimization
   - Progress tracking and notifications

#### 2.2.2 Simplified Processing Architecture (v2.9)

```
Input Layer:
├── HTML Upload Interface
├── Backblaze B2 Monitoring
├── YouTube URL Processing
├── Web Scraping (Firecrawl)
└── Direct API Calls

Processing Layer (Streamlined):
├── Document Router
│   ├── Hash Check (Skip if unchanged)
│   └── Format Detection
├── Primary Processors
│   ├── MarkItDown MCP (40+ formats)
│   ├── Mistral OCR (Complex PDFs only)
│   ├── YouTube API (Transcripts/Frames)
│   ├── Soniox (Audio/Video)
│   └── Firecrawl (Web Content)
└── Unified Markdown Output

Intelligence Layer:
├── LlamaIndex Chunking
├── Contextual Embeddings (Mistral - Optional)
├── Metadata Enrichment (AI Classification)
├── LangExtract (Structured Data)
├── Tabular Data Processing (SQL-ready)
└── CrewAI Multi-Agent Analysis

Search & Retrieval Layer:
├── Hybrid Search (Vector + Keyword)
├── Cohere Reranking
├── LightRAG Graph Queries
├── SQL Tabular Queries
└── Metadata Filtering

Storage Layer:
├── Pinecone (Vectors with Metadata)
├── PostgreSQL (Records/Sessions/Tabular)
├── LightRAG API (Knowledge Graph)
├── Airtable (Audit Trail)
├── Backblaze B2 (Objects)
└── Zep (Long-term Memory)

Agent Layer:
├── Dual Agent Architecture
├── Memory-Enabled Agent (Zep)
├── Session-Only Agent
└── CrewAI Collaboration
```

### 2.3 User Characteristics

#### 2.3.1 User Classes

| User Class | Description | Technical Expertise | Frequency of Use |
|------------|-------------|-------------------|------------------|
| **Content Processors** | Upload and manage course materials | Low-Medium | Daily |
| **Business Analysts** | Review insights and reports | Medium | Weekly |
| **System Administrators** | Monitor system performance | High | Daily |
| **Executives** | Receive strategic recommendations | Low | Monthly |
| **End Users** | Interact with agents for queries | Low | Daily |
| **Developers** | Maintain and enhance system | Very High | Daily |
| **QA Engineers** | Test system functionality | High | Weekly |
| **Security Teams** | Monitor threats and compliance | High | Daily |
| **Data Engineers** | Optimize data pipelines | Very High | Weekly |

#### 2.3.2 User Personas

**Sarah - Content Manager**
- Uploads 20-30 documents daily
- Needs simple drag-and-drop interface
- Requires processing status notifications
- Values accurate content extraction

**Michael - Business Analyst**
- Reviews weekly intelligence reports
- Needs clear visualizations
- Requires export capabilities
- Values actionable insights

**David - System Administrator**
- Monitors system health 24/7
- Needs detailed error logs
- Requires performance metrics
- Values system stability

**Emma - End User**
- Asks questions about documents
- Expects personalized responses
- Needs quick, accurate answers
- Values conversational interface

### 2.4 Constraints

#### 2.4.1 Technical Constraints

**TC-001:** System must operate within Render.com infrastructure limitations  
**TC-002:** Node.js execution environment required for n8n workflow automation  
**TC-003:** MarkItDown MCP server must maintain persistent availability  
**TC-004:** Maximum file size limited to 300MB per document  
**TC-005:** Concurrent processing limited to 5 files simultaneously  

#### 2.4.2 Resource Constraints

**TC-006:** Supabase free tier limited to 500MB database storage  
**TC-007:** Supabase connection limit of 60 concurrent connections  
**TC-008:** Airtable API rate limit of 5 requests per second  
**TC-009:** Mistral OCR API rate limits apply (100 requests/hour)  
**TC-010:** Pinecone vector storage limited to tier specifications  
**TC-011:** Cohere reranking API rate limits (1000 requests/minute)  
**TC-012:** Zep memory API rate limits apply  
**TC-013:** Firecrawl crawling limits per tier  

#### 2.4.3 Regulatory Constraints

**TC-014:** Must comply with GDPR data protection requirements  
**TC-015:** Must maintain SOC 2 Type II compliance  
**TC-016:** Must implement data retention policies per legal requirements  
**TC-017:** Must ensure data residency compliance  

#### 2.4.4 Design Constraints

**TC-018:** Must use existing n8n workflow platform  
**TC-019:** Must integrate with current authentication system  
**TC-020:** Must maintain backward compatibility with v2.8  
**TC-021:** Must use RESTful API design patterns  

### 2.5 Assumptions and Dependencies

#### 2.5.1 Assumptions

1. **Infrastructure Assumptions**
   - Render.com services maintain 99.9% uptime
   - Network bandwidth sufficient for file transfers
   - Cloud services remain within cost budget

2. **Technical Assumptions**
   - MarkItDown MCP continues to support current formats
   - API services maintain backward compatibility
   - Vector similarity search remains effective for retrieval
   - LightRAG API remains available and stable

3. **Business Assumptions**
   - Document volume remains under 100 files/day
   - User base grows at predictable rate
   - Content primarily in English language
   - Users have unique identifiers for memory storage

#### 2.5.2 Dependencies

1. **External Service Dependencies**
   - Microsoft MarkItDown MCP Server
   - Mistral OCR API
   - Mistral Embedding API
   - Soniox Transcription Service
   - OpenAI Embedding API
   - Cohere Reranking API
   - YouTube Data API v3
   - Pinecone Vector Database
   - LightRAG Knowledge Graph API
   - Backblaze B2 Storage
   - Zep Memory Service
   - Firecrawl Web Scraping API

2. **Internal Dependencies**
   - n8n Workflow Engine
   - PostgreSQL Database
   - Authentication Service
   - Monitoring Infrastructure

---

## 3. Specific Requirements

### 3.1 Functional Requirements

#### 3.1.1 Document Processing Requirements

##### 3.1.1.1 Unified MarkItDown Processing

**FR-001:** The system SHALL accept documents in 40+ supported formats  
*Priority: Essential*  
*Source: Product Management*  
*Verification: Integration Testing*

**FR-002:** The system SHALL convert all supported formats to clean Markdown using MarkItDown MCP  
*Priority: Essential*  
*Dependencies: TC-003*

**FR-003:** The system SHALL preserve document structure including headings, lists, and paragraphs  
*Priority: Essential*

**FR-004:** The system SHALL extract and preserve tables with proper formatting  
*Priority: High*

**FR-005:** The system SHALL handle embedded images by extracting and referencing them  
*Priority: High*

**FR-006:** The system SHALL extract document metadata including title, author, creation date  
*Priority: Medium*

**Supported Formats via MarkItDown MCP:**
- **Microsoft Office:** DOCX, XLSX, PPTX, DOC, XLS, PPT
- **Web Formats:** HTML, XML, MHTML, JSON, YAML
- **Archives:** ZIP, EPUB, TAR, GZ
- **Images:** JPG, PNG, GIF, BMP, TIFF, SVG, WEBP
- **Data:** CSV, TSV, JSON, YAML, TOML
- **Text:** TXT, MD, RTF, LOG
- **Simple PDFs:** Text-based PDFs without complex formatting

##### 3.1.1.2 Intelligent PDF Routing

**FR-007:** The system SHALL assess PDF complexity before processing  
*Priority: Essential*

**FR-008:** The system SHALL route simple text-based PDFs to MarkItDown MCP  
*Priority: Essential*

**FR-009:** The system SHALL route complex PDFs to Mistral OCR when:
- Document contains complex tables or layouts
- Document contains diagrams or flowcharts  
- Document contains mathematical formulas
- File size exceeds 10MB
- MarkItDown processing fails  
*Priority: Essential*

**FR-010:** The system SHALL merge OCR output seamlessly with main pipeline  
*Priority: High*

```javascript
// PDF Complexity Assessment Logic
function assessPDFComplexity(file) {
  const criteria = {
    hasComplexTables: checkForComplexTables(file),
    hasDiagrams: checkForDiagrams(file),
    hasFormulas: checkForMathFormulas(file),
    largeFileSize: file.size > 10485760, // 10MB
    hasMultiColumn: checkForMultiColumnLayout(file)
  };
  
  return Object.values(criteria).some(v => v === true);
}
```

##### 3.1.1.3 Mistral OCR Processing

**FR-011:** The system SHALL upload complex PDFs to Mistral OCR API  
*Priority: Essential*

**FR-012:** The system SHALL poll Mistral API for OCR completion status  
*Priority: Essential*

**FR-013:** The system SHALL extract Markdown-formatted text from OCR results  
*Priority: Essential*

**FR-014:** The system SHALL handle OCR timeouts with retry logic (3 attempts)  
*Priority: High*

**FR-015:** The system SHALL fallback to basic text extraction if OCR fails  
*Priority: Medium*

#### 3.1.2 Multimedia Processing Requirements

##### 3.1.2.1 YouTube Content Extraction

**FR-016:** The system SHALL extract YouTube video metadata including:
- Title, description, duration
- Channel information
- Upload date, view count
- Tags and categories  
*Priority: High*

**FR-017:** The system SHALL retrieve video transcripts using three-tier hierarchy:
1. Official YouTube captions (highest priority)
2. Auto-generated captions (medium priority)
3. Soniox transcription of audio (fallback)  
*Priority: Essential*

**FR-018:** The system SHALL extract video frames at configurable intervals (default: 30 seconds)  
*Priority: Medium*

**FR-019:** The system SHALL analyze extracted frames for educational content  
*Priority: Low*

**FR-020:** The system SHALL create timestamped descriptions of visual content  
*Priority: Low*

**FR-021:** The system SHALL output unified Markdown document with transcript and metadata  
*Priority: Essential*

##### 3.1.2.2 Audio/Video Transcription

**FR-022:** The system SHALL transcribe audio/video files using Soniox API  
*Priority: Essential*

**FR-023:** The system SHALL enable speaker diarization for multi-speaker content  
*Priority: High*

**FR-024:** The system SHALL support automatic language detection  
*Priority: Medium*

**FR-025:** The system SHALL handle files up to 300MB  
*Priority: Essential*

**FR-026:** The system SHALL output transcripts as properly formatted Markdown  
*Priority: Essential*

**FR-027:** The system SHALL include speaker labels and timestamps in output  
*Priority: High*

**Supported Audio Formats:** MP3, WAV, FLAC, AAC, OGG, WMA, M4A, OPUS  
**Supported Video Formats:** MP4, AVI, MOV, MKV, WMV, FLV, WEBM, MPG

##### 3.1.2.3 Web Content Ingestion

**FR-028:** The system SHALL integrate Firecrawl for web scraping capabilities  
*Priority: Essential*

**FR-029:** The system SHALL support scheduled crawling of specified URLs  
*Priority: High*

**FR-030:** The system SHALL extract clean Markdown from web pages  
*Priority: Essential*

**FR-031:** The system SHALL handle JavaScript-rendered content  
*Priority: Medium*

**FR-032:** The system SHALL respect robots.txt and rate limiting  
*Priority: Essential*

**FR-033:** The system SHALL support webhook callbacks for crawl completion  
*Priority: Medium*

##### 3.1.2.4 Multimodal RAG Processing

**FR-034:** The system SHALL process mixed content types (text, images, tables)  
*Priority: Essential*

**FR-035:** The system SHALL extract and analyze images from documents  
*Priority: High*

**FR-036:** The system SHALL generate image descriptions for retrieval  
*Priority: High*

**FR-037:** The system SHALL maintain image-text relationships in storage  
*Priority: Essential*

**FR-038:** The system SHALL support image-based search queries  
*Priority: Medium*

##### 3.1.2.5 Visual Content Querying

**FR-039:** The system SHALL enable direct visual querying using Mistral Pixtral-12B  
*Priority: Essential*

**FR-040:** The system SHALL support visual query types including:
- Object identification ("What objects are in this image?")
- Text extraction from images ("What text is visible?")
- Diagram interpretation ("Explain this flowchart")
- Chart analysis ("What trend does this graph show?")
- Technical drawing comprehension ("What components are shown?")  
*Priority: High*

**FR-041:** The system SHALL generate searchable descriptions for all extracted images  
*Priority: Essential*

**FR-042:** The system SHALL store visual analysis results as metadata:
```json
{
  "image_id": "uuid",
  "source_document": "string",
  "visual_description": "string",
  "detected_objects": ["array"],
  "extracted_text": "string",
  "chart_data": {},
  "query_history": []
}
```
*Priority: High*

**FR-043:** The system SHALL cache visual analysis to avoid reprocessing  
*Priority: Medium*

**FR-044:** The system SHALL support batch visual processing (up to 50 images)  
*Priority: Medium*

**FR-045:** The system SHALL fallback to OCR for text-heavy images  
*Priority: High*

#### 3.1.3 Hybrid RAG System Requirements

##### 3.1.3.1 Hash-Based Change Detection

**FR-039:** The system SHALL compute SHA-256 hash for all processed content  
*Priority: Essential*  
*Rationale: Prevents redundant processing*

**FR-040:** The system SHALL check existing hash before initiating processing  
*Priority: Essential*

**FR-041:** The system SHALL skip processing when hash matches existing record  
*Priority: Essential*

**FR-042:** The system SHALL update vectors only when content hash changes  
*Priority: Essential*

**FR-043:** The system SHALL maintain complete hash history in PostgreSQL  
*Priority: High*

**FR-044:** The system SHALL synchronize hash records to Airtable for audit  
*Priority: Medium*

##### 3.1.3.2 Hybrid Search with Reranking

**FR-045:** The system SHALL implement hybrid search combining vector and keyword search  
*Priority: Essential*

**FR-046:** The system SHALL integrate Cohere reranking API for result optimization  
*Priority: Essential*

**FR-047:** The system SHALL support configurable top-k retrieval (default: 30)  
*Priority: High*

**FR-048:** The system SHALL rerank results to top-10 most relevant  
*Priority: Essential*

**FR-049:** The system SHALL maintain original relevance scores for analysis  
*Priority: Medium*

**FR-050:** The system SHALL support fallback to basic search if reranking fails  
*Priority: High*

##### 3.1.3.3 Record Management API

**FR-051:** The system SHALL expose RESTful endpoints for record management:

```http
POST /api/v1/hybrid/record/check
Request: {
  "document_id": "string",
  "content_hash": "string",
  "metadata": {}
}
Response: {
  "action": "skip|new|update",
  "existing_record": {},
  "reason": "string"
}

POST /api/v1/hybrid/record/create
Request: {
  "document_id": "string",
  "content_hash": "string",
  "content_type": "string",
  "metadata": {},
  "vectors": []
}
Response: {
  "record_id": "string",
  "status": "created",
  "timestamp": "ISO8601"
}

POST /api/v1/hybrid/record/update
Request: {
  "record_id": "string",
  "content_hash": "string",
  "vectors": [],
  "metadata_updates": {}
}
Response: {
  "status": "updated",
  "changes": [],
  "timestamp": "ISO8601"
}
```
*Priority: Essential*

**FR-052:** The system SHALL maintain record state consistency across storage layers  
*Priority: Essential*

**FR-053:** The system SHALL support bulk record operations  
*Priority: Medium*

##### 3.1.3.4 Knowledge Graph Integration (LightRAG)

**FR-054:** The system SHALL integrate LightRAG API for graph-based knowledge storage  
*Priority: Essential*

**FR-055:** The system SHALL extract entities and relationships from documents  
*Priority: Essential*

**FR-056:** The system SHALL support hybrid queries (vector + graph)  
*Priority: Essential*

**FR-057:** The system SHALL maintain graph consistency with vector store  
*Priority: High*

**FR-058:** The system SHALL support graph traversal queries  
*Priority: Medium*

**FR-059:** The system SHALL update graph incrementally with new documents  
*Priority: High*

**FR-060:** The system SHALL provide graph visualization endpoints  
*Priority: Low*

#### 3.1.4 Content Intelligence Requirements

##### 3.1.4.1 LlamaIndex Processing

**FR-061:** The system SHALL chunk content using configurable parameters:
- Default chunk size: 1000 characters
- Default overlap: 200 characters
- Sentence boundary respect: enabled  
*Priority: Essential*

**FR-062:** The system SHALL generate embeddings using OpenAI text-embedding-3-small  
*Priority: Essential*

**FR-063:** The system SHALL extract key entities, topics, and concepts  
*Priority: High*

**FR-064:** The system SHALL generate document and chunk-level summaries  
*Priority: Medium*

##### 3.1.4.2 Contextual Embeddings

**FR-065:** The system SHALL optionally generate contextual embeddings using Mistral  
*Priority: High*

**FR-066:** The system SHALL create 2-3 sentence context descriptions for each chunk  
*Priority: High*

**FR-067:** The system SHALL prepend context to chunks before embedding  
*Priority: High*

**FR-068:** The system SHALL make contextual embedding configurable per document  
*Priority: Medium*

**FR-069:** The system SHALL cache contextual descriptions for reuse  
*Priority: Low*

##### 3.1.4.3 Advanced Metadata Filtering

**FR-070:** The system SHALL dynamically extract metadata using AI classification  
*Priority: Essential*

**FR-071:** The system SHALL support configurable metadata fields  
*Priority: High*

**FR-072:** The system SHALL enable complex filter queries including:
- AND/OR logical operators
- Range queries (>, <, >=, <=)
- IN/NOT IN array operations
- Equality and inequality checks  
*Priority: Essential*

**FR-073:** The system SHALL automatically suggest relevant filters based on query  
*Priority: Medium*

**FR-074:** The system SHALL maintain metadata field registry in database  
*Priority: High*

##### 3.1.4.4 Tabular Data Processing

**FR-075:** The system SHALL detect and extract tables from documents  
*Priority: Essential*

**FR-076:** The system SHALL store tabular data in PostgreSQL as JSONB  
*Priority: Essential*

**FR-077:** The system SHALL enable SQL queries against extracted tables  
*Priority: Essential*

**FR-078:** The system SHALL support aggregations (SUM, AVG, MAX, MIN, COUNT)  
*Priority: High*

**FR-079:** The system SHALL support GROUP BY and JOIN operations  
*Priority: Medium*

**FR-080:** The system SHALL integrate SQL results into RAG responses  
*Priority: Essential*

**FR-081:** The system SHALL maintain table schema in record manager  
*Priority: High*

##### 3.1.4.5 LangExtract Structured Extraction

**FR-082:** The system SHALL extract structured data with source grounding  
*Priority: High*

**FR-083:** The system SHALL identify and extract:
- Frameworks and methodologies
- Business processes
- Action items and recommendations
- Key concepts and definitions
- Relationships and dependencies  
*Priority: High*

**FR-084:** The system SHALL maintain bidirectional links between extracted data and source  
*Priority: Medium*

#### 3.1.5 Memory and Agent Architecture Requirements

##### 3.1.5.1 Long-term Memory with Zep

**FR-085:** The system SHALL integrate Zep for user-specific long-term memory  
*Priority: Essential*

**FR-086:** The system SHALL create unique user profiles in Zep  
*Priority: Essential*

**FR-087:** The system SHALL store user facts and preferences as graph edges  
*Priority: High*

**FR-088:** The system SHALL retrieve relevant memories based on query context  
*Priority: Essential*

**FR-089:** The system SHALL update memories asynchronously after interactions  
*Priority: High*

**FR-090:** The system SHALL support memory relevance filtering (min 0.7 score)  
*Priority: Medium*

**FR-091:** The system SHALL maintain memory versioning and history  
*Priority: Low*

##### 3.1.5.2 Dual Agent Architecture

**FR-092:** The system SHALL implement two distinct agent configurations:
- Agent A: With long-term memory (Zep integration)
- Agent B: Without long-term memory (session only)  
*Priority: Essential*

**FR-093:** The system SHALL route users to appropriate agent based on:
- User preferences
- Use case requirements
- Privacy settings  
*Priority: High*

**FR-094:** The system SHALL maintain separate conversation histories  
*Priority: Essential*

**FR-095:** The system SHALL support agent switching within sessions  
*Priority: Medium*

**FR-096:** The system SHALL clearly identify active agent to users  
*Priority: High*

##### 3.1.5.3 Session Management

**FR-097:** The system SHALL create unique session IDs for each interaction  
*Priority: Essential*

**FR-098:** The system SHALL track session state in Airtable  
*Priority: Essential*

**FR-099:** The system SHALL maintain session metadata in Supabase  
*Priority: High*

**FR-100:** The system SHALL support session resumption after interruption  
*Priority: Medium*

**FR-101:** The system SHALL implement session timeout (default: 30 minutes)  
*Priority: High*

**FR-102:** The system SHALL correlate all operations within a session  
*Priority: Essential*

#### 3.1.6 Multi-Agent Analysis Requirements

**FR-103:** The system SHALL execute CrewAI analysis using 1-5 specialized agents  
*Priority: High*

**FR-104:** The system SHALL adapt agent complexity based on content type  
*Priority: Medium*

**FR-105:** The system SHALL generate organizational recommendations including:
- Process improvements
- Knowledge gaps
- Training needs
- Strategic opportunities
- Risk assessments  
*Priority: High*

**FR-106:** The system SHALL handle long-running analysis (up to 30 minutes)  
*Priority: Medium*

**FR-107:** The system SHALL provide progress updates during analysis  
*Priority: Low*

**FR-108:** The system SHALL support custom agent configurations  
*Priority: Medium*

**FR-109:** The system SHALL enable agent collaboration for complex queries  
*Priority: High*

#### 3.1.7 Vector Storage and Retrieval Requirements

**FR-110:** The system SHALL store vectors in Pinecone immediately after processing  
*Priority: Essential*

**FR-111:** The system SHALL use namespace organization (default: "course_vectors")  
*Priority: Essential*

**FR-112:** The system SHALL batch vector uploads (max 100 vectors per batch)  
*Priority: High*

**FR-113:** The system SHALL include enriched metadata with each vector:
```json
{
  "vector_id": "uuid",
  "values": [0.1, 0.2, ...],
  "metadata": {
    "document_id": "string",
    "chunk_index": 0,
    "content": "string",
    "document_type": "string",
    "source_format": "string",
    "topics": ["array"],
    "complexity": "low|medium|high",
    "timestamp": "ISO8601",
    "hash": "sha256",
    "contextual_summary": "string"
  }
}
```
*Priority: Essential*

**FR-114:** The system SHALL support vector updates without full reindexing  
*Priority: High*

**FR-115:** The system SHALL implement vector similarity search with cosine distance  
*Priority: Essential*

**FR-116:** The system SHALL support metadata-filtered vector queries  
*Priority: Essential*

### 3.2 Non-Functional Requirements

#### 3.2.1 Performance Requirements

**NFR-001:** The system SHALL process documents up to 300MB within 30 minutes  
*Measurement: 95th percentile processing time*

**NFR-002:** The system SHALL handle concurrent processing of up to 5 documents  
*Measurement: System stability under load*

**NFR-003:** The system SHALL achieve 30% reduction in processing time vs v2.7  
*Measurement: Comparative benchmark*

**NFR-004:** The system SHALL complete hash checking within 500ms  
*Measurement: 99th percentile response time*

**NFR-005:** The system SHALL complete MarkItDown conversion within 60 seconds for standard documents  
*Measurement: 95th percentile for documents <50MB*

**NFR-006:** The system SHALL maintain sub-100ms vector search latency  
*Measurement: 95th percentile query time*

**NFR-007:** The system SHALL support 100+ documents per day throughput  
*Measurement: Daily processing capacity*

**NFR-008:** The system SHALL complete Cohere reranking within 2 seconds  
*Measurement: 95th percentile reranking time*

**NFR-009:** The system SHALL retrieve user memories from Zep within 500ms  
*Measurement: 95th percentile retrieval time*

**NFR-010:** The system SHALL process visual queries via Pixtral within 3 seconds  
*Measurement: 95th percentile for single image analysis*

#### 3.2.2 Reliability Requirements

**NFR-010:** The system SHALL maintain 99% uptime availability  
*Measurement: Monthly uptime percentage*

**NFR-011:** The system SHALL implement automatic retry logic for all external API calls:
- Initial retry: 1 second
- Exponential backoff: 2x
- Maximum retries: 3
- Maximum delay: 30 seconds  
*Measurement: Retry success rate*

**NFR-012:** The system SHALL gracefully degrade when external services fail  
*Measurement: System stability during outages*

**NFR-013:** The system SHALL maintain data consistency between SQL and Airtable  
*Measurement: Consistency check results*

**NFR-014:** The system SHALL recover from failures without data loss  
*Measurement: Recovery testing results*

#### 3.2.3 Scalability Requirements

**NFR-015:** The system SHALL scale to handle 10,000+ documents in storage  
*Measurement: Storage performance at scale*

**NFR-016:** The system SHALL support up to 1M vectors with maintained performance  
*Measurement: Vector search latency at scale*

**NFR-017:** The system SHALL scale horizontally for increased load  
*Measurement: Performance under distributed deployment*

**NFR-018:** The system SHALL support incremental capacity increases  
*Measurement: Scaling without downtime*

**NFR-019:** The system SHALL support unlimited user memories in Zep  
*Measurement: Memory retrieval performance at scale*

#### 3.2.4 Security Requirements

**SR-001:** The system SHALL authenticate all API requests using JWT tokens  
*Priority: Essential*

**SR-002:** The system SHALL implement role-based access control (RBAC)  
*Priority: Essential*

**SR-003:** The system SHALL encrypt data in transit using TLS 1.3  
*Priority: Essential*

**SR-004:** The system SHALL encrypt sensitive data at rest using AES-256  
*Priority: Essential*

**SR-005:** The system SHALL log all access attempts and modifications  
*Priority: High*

**SR-006:** The system SHALL detect and prevent injection attacks  
*Priority: Essential*

**SR-007:** The system SHALL implement rate limiting on all endpoints  
*Priority: High*

**SR-008:** The system SHALL comply with GDPR data protection requirements  
*Priority: Essential*

**SR-009:** The system SHALL isolate user memories in Zep  
*Priority: Essential*

#### 3.2.5 Usability Requirements

**NFR-020:** The system SHALL provide intuitive drag-and-drop file upload  
*Measurement: User satisfaction score*

**NFR-021:** The system SHALL display clear processing status indicators  
*Measurement: User comprehension rate*

**NFR-022:** The system SHALL provide meaningful error messages  
*Measurement: Error resolution time*

**NFR-023:** The system SHALL support batch operations for efficiency  
*Measurement: Task completion time*

**NFR-024:** The system SHALL provide conversational interface for queries  
*Measurement: User engagement metrics*

#### 3.2.6 Maintainability Requirements

**NFR-025:** The system SHALL achieve 80% code coverage in tests  
*Measurement: Coverage reports*

**NFR-026:** The system SHALL follow consistent coding standards  
*Measurement: Linting compliance*

**NFR-027:** The system SHALL provide comprehensive API documentation  
*Measurement: Documentation completeness*

**NFR-028:** The system SHALL support hot-swappable service updates  
*Measurement: Deployment downtime*

**NFR-029:** The system SHALL maintain backward compatibility for 2 major versions  
*Measurement: Compatibility testing*

### 3.3 External Interface Requirements

#### 3.3.1 User Interfaces

##### 3.3.1.1 Web Upload Interface

**UI-001:** The interface SHALL provide drag-and-drop file upload area  
**UI-002:** The interface SHALL display upload progress with percentage  
**UI-003:** The interface SHALL show processing status for each file  
**UI-004:** The interface SHALL provide download links for results  
**UI-005:** The interface SHALL support bulk file selection  

##### 3.3.1.2 Administrative Dashboard

**UI-006:** The dashboard SHALL display system health metrics  
**UI-007:** The dashboard SHALL show processing queue status  
**UI-008:** The dashboard SHALL provide error logs and alerts  
**UI-009:** The dashboard SHALL enable manual retry of failed jobs  
**UI-010:** The dashboard SHALL export reports in multiple formats  

##### 3.3.1.3 Chat Interface

**UI-011:** The interface SHALL provide conversational chat widget  
**UI-012:** The interface SHALL display agent type indicator  
**UI-013:** The interface SHALL show typing indicators  
**UI-014:** The interface SHALL support markdown rendering  
**UI-015:** The interface SHALL maintain conversation history  

#### 3.3.2 Hardware Interfaces

The system operates in a cloud environment with no direct hardware interfaces. All hardware interaction occurs through cloud provider APIs.

#### 3.3.3 Software Interfaces

##### 3.3.3.1 MarkItDown MCP Interface

```python
Interface: MarkItDown MCP Server
Protocol: HTTP/REST
Endpoint: http://markitdown-mcp:8080/convert
Method: POST
Request: {
  "content": "base64_encoded_file",
  "filename": "document.docx",
  "options": {
    "preserve_formatting": true,
    "extract_images": true,
    "include_metadata": true
  }
}
Response: {
  "markdown": "# Converted Document...",
  "metadata": {},
  "images": [],
  "status": "success"
}
```

##### 3.3.3.2 Cohere Reranking Interface

```python
Interface: Cohere Rerank API
Protocol: HTTPS/REST
Endpoint: https://api.cohere.com/v2/rerank
Authentication: Bearer Token
Method: POST
Request: {
  "model": "rerank-v3.5",
  "query": "user query",
  "documents": ["array of documents"],
  "top_n": 10
}
```

##### 3.3.3.4 Mistral Pixtral Interface

```python
Interface: Mistral Pixtral Vision API
Protocol: HTTPS/REST
Endpoint: https://api.mistral.ai/v1/vision
Authentication: Bearer Token
Method: POST
Request: {
  "model": "pixtral-12b",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "What is shown in this image?"},
      {"type": "image", "source": {"data": "base64_encoded_image"}}
    ]
  }],
  "max_tokens": 300
}
Response: {
  "choices": [{
    "message": {
      "content": "Description of image content..."
    }
  }]
}
```

#### 3.3.4 Communications Interfaces

**CI-001:** The system SHALL use HTTPS for all external communications  
**CI-002:** The system SHALL implement WebSocket for real-time updates  
**CI-003:** The system SHALL support REST API with JSON payloads  
**CI-004:** The system SHALL implement gRPC for high-performance operations  
**CI-005:** The system SHALL use message queues for async processing  

### 3.4 System Features

#### 3.4.1 Feature: Intelligent Document Router

**Description:** Automatically routes documents to appropriate processors based on format and complexity

**Priority:** Essential

**Stimulus/Response Sequences:**
1. User uploads document
2. System determines file format
3. System assesses document complexity
4. System routes to appropriate processor
5. System returns processed Markdown

**Functional Requirements:**
- FR-001 through FR-015

#### 3.4.2 Feature: Hybrid RAG Search with Reranking

**Description:** Combines vector similarity with keyword search and applies Cohere reranking for optimal retrieval

**Priority:** Essential

**Stimulus/Response Sequences:**
1. User submits search query
2. System generates query embedding
3. System performs hybrid search (vector + keyword)
4. System retrieves top-30 results
5. System applies Cohere reranking
6. System returns top-10 reranked results

**Functional Requirements:**
- FR-045 through FR-050

#### 3.4.3 Feature: User-Specific Long-term Memory

**Description:** Maintains personalized memory for each user via Zep integration

**Priority:** High

**Stimulus/Response Sequences:**
1. User interacts with system
2. System identifies user ID
3. System retrieves relevant memories from Zep
4. System incorporates memories into response
5. System updates memories asynchronously

**Functional Requirements:**
- FR-085 through FR-091

#### 3.4.4 Feature: SQL-Queryable Tabular Data

**Description:** Enables SQL queries against extracted tabular data

**Priority:** High

**Stimulus/Response Sequences:**
1. System extracts tables from documents
2. System stores tables in PostgreSQL
3. User queries require tabular analysis
4. System generates SQL query
5. System executes query and returns results

**Functional Requirements:**
- FR-075 through FR-081

### 3.5 Performance Requirements

#### 3.5.1 Static Numerical Requirements

| Metric | Requirement | Measurement Method |
|--------|------------|-------------------|
| Maximum file size | 300MB | System validation |
| Concurrent processing | 5 files | Load testing |
| Vector batch size | 100 vectors | Configuration |
| Hash computation time | <500ms | Performance monitoring |
| Conversion timeout | 60 seconds | Timeout configuration |
| API rate limits | Various per service | Rate limiting |
| Database connections | 60 concurrent | Connection pooling |
| Rerank batch size | 30 documents | API configuration |

#### 3.5.2 Dynamic Numerical Requirements

| Metric | Requirement | Conditions |
|--------|------------|------------|
| Processing throughput | 100+ docs/day | Normal load |
| Vector search latency | <100ms | <100K vectors |
| Vector search latency | <500ms | 100K-1M vectors |
| Reranking latency | <2 seconds | 30 documents |
| Memory retrieval | <500ms | Any user |
| System uptime | 99% | Monthly average |
| Error recovery time | <5 minutes | Automatic recovery |
| Backup frequency | Every 6 hours | Incremental backups |

### 3.6 Design Constraints

#### 3.6.1 Standards Compliance

**DC-001:** The system SHALL comply with IEEE 830-1998 for documentation  
**DC-002:** The system SHALL follow OpenAPI 3.1 for API specification  
**DC-003:** The system SHALL implement OAuth 2.0 for authentication  
**DC-004:** The system SHALL use ISO 8601 for datetime formats  
**DC-005:** The system SHALL follow REST architectural principles  

#### 3.6.2 Language and Tool Requirements

**DC-006:** Backend services SHALL be implemented in Node.js/Python  
**DC-007:** Workflow orchestration SHALL use n8n platform  
**DC-008:** Database queries SHALL use parameterized SQL  
**DC-009:** Vector operations SHALL use Pinecone SDK  
**DC-010:** Testing SHALL use Jest/Pytest frameworks  

### 3.7 Software System Attributes

#### 3.7.1 Availability

The system shall maintain 99% uptime measured monthly, with planned maintenance windows excluded from calculations.

#### 3.7.2 Security

The system shall implement defense-in-depth security strategy with multiple layers of protection including authentication, authorization, encryption, and monitoring.

#### 3.7.3 Maintainability

The system shall be designed for easy maintenance with modular architecture, comprehensive logging, and automated deployment procedures.

#### 3.7.4 Portability

The system shall be containerized using Docker for deployment across different cloud environments with minimal configuration changes.

#### 3.7.5 Flexibility

The system shall support configuration-driven behavior allowing adjustments without code changes for parameters like chunk sizes, processing timeouts, and retry policies.

---

## 4. Supporting Information

### 4.1 Appendix A: Business Rules

**BR-001:** Files must be processed in order of upload/detection  
**BR-002:** Vector storage must complete before analysis begins  
**BR-003:** Documents with matching hash SHALL skip reprocessing  
**BR-004:** MarkItDown SHALL be primary processor for all supported formats  
**BR-005:** Mistral OCR SHALL only process complex PDFs  
**BR-006:** Metadata enrichment SHALL occur before vector storage  
**BR-007:** Contextual embeddings SHALL be optional and configurable  
**BR-008:** SQL database SHALL be source of truth for record state  
**BR-009:** Audit trail SHALL be immutable once written  
**BR-010:** Processing SHALL respect data retention policies  
**BR-011:** Hybrid search SHALL combine vector and keyword results  
**BR-012:** Reranking SHALL be applied to all search results  
**BR-013:** Long-term memories SHALL be user-specific  
**BR-014:** Tabular data SHALL be queryable via SQL  
**BR-015:** Web scraping SHALL respect robots.txt  
**BR-016:** Multimodal content SHALL maintain relationships  
**BR-017:** Graph updates SHALL be incremental  
**BR-018:** Agent selection SHALL be explicit  

### 4.2 Appendix B: Technical Stack Summary

#### Core Processing Infrastructure
- **Workflow Orchestration:** n8n (https://jb-n8n.onrender.com)
- **Primary Document Processor:** MarkItDown MCP Server
- **Complex PDF Processor:** Mistral OCR API (fallback)
- **Visual Content Analysis:** Mistral Pixtral-12B
- **Audio/Video Transcription:** Soniox API with diarization
- **Web Scraping:** Firecrawl API
- **Contextual Embeddings:** Mistral API

#### Storage and Databases
- **Object Storage:** Backblaze B2
- **Vector Database:** Pinecone (with metadata filtering)
- **Graph Database:** LightRAG API (knowledge graph service)
- **SQL Database:** PostgreSQL/Supabase (records, sessions, tabular data)
- **Audit Trail:** Airtable (human-readable logs)
- **Long-term Memory:** Zep (user memories)

#### Intelligence and Analysis
- **Chunking/Processing:** LlamaIndex
- **Structured Extraction:** LangExtract
- **Embeddings:** OpenAI text-embedding-3-small
- **Reranking:** Cohere API v3.5
- **Multi-Agent Framework:** CrewAI
- **Query Processing:** Dual agent architecture

#### Security and Monitoring
- **Security Monitoring:** Lakera Guard
- **Metrics Collection:** Prometheus
- **ML Observability:** Arize Phoenix
- **Testing Framework:** DeepEval
- **API Authentication:** JWT tokens with RBAC

### 4.3 Appendix C: Migration Plan from v2.8 to v2.9

#### Phase 1: Service Integration (Week 1-2)
1. Deploy Cohere reranking integration
2. Configure Zep memory service
3. Setup Firecrawl web scraping
4. Integrate LightRAG API endpoints
5. Prepare rollback procedures

#### Phase 2: Feature Implementation (Week 3-4)
1. Implement hybrid search with reranking
2. Deploy dual agent architecture
3. Enable SQL querying for tabular data
4. Configure contextual embeddings with Mistral
5. Implement advanced metadata filtering

#### Phase 3: Testing and Validation (Week 5-6)
1. Test hybrid search accuracy
2. Verify memory persistence and retrieval
3. Validate SQL query functionality
4. Test web scraping capabilities
5. Load test enhanced system

#### Phase 4: Gradual Rollout (Week 7-8)
1. Enable for 10% of users (monitoring)
2. Increase to 50% of users
3. Full production deployment
4. Performance optimization
5. Document lessons learned

### 4.4 Appendix D: Glossary of Terms

| Term | Definition |
|------|------------|
| **Agent** | Autonomous AI entity in CrewAI framework or dual architecture |
| **Chunk** | Segment of document for processing |
| **Contextual Embedding** | Embedding with added context for improved retrieval |
| **Diarization** | Speaker identification in audio |
| **Embedding** | Vector representation of text |
| **Hash** | Unique fingerprint of content (SHA-256) |
| **Hybrid RAG** | Combined retrieval methods (vector + keyword) |
| **Knowledge Graph** | Graph-based knowledge representation via LightRAG |
| **Long-term Memory** | User-specific persistent memory via Zep |
| **Namespace** | Logical grouping in vector database |
| **OCR** | Optical Character Recognition |
| **Pipeline** | Sequential processing workflow |
| **Reranking** | Re-ordering search results for relevance |
| **Session** | Correlated processing instance |
| **Vector** | Numerical representation for similarity |

### 4.5 Appendix E: API Specifications

#### 4.5.1 Core Processing Endpoints

```yaml
openapi: 3.1.0
info:
  title: AI Empire File Processing System API
  version: 2.9.0

paths:
  /api/v1/process/document:
    post:
      summary: Process a document
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [file_content, filename]
              properties:
                file_content: 
                  type: string
                  format: base64
                filename: 
                  type: string
                course: 
                  type: string
                module: 
                  type: string
                enable_contextual_embeddings:
                  type: boolean
                  default: false
                enable_multimodal:
                  type: boolean
                  default: false
      responses:
        200:
          description: Processing successful

  /api/v1/process/youtube:
    post:
      summary: Process YouTube video
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [url]
              properties:
                url:
                  type: string
                extract_frames:
                  type: boolean
                  default: false
                frame_interval:
                  type: integer
                  default: 30

  /api/v1/process/web:
    post:
      summary: Process web content via Firecrawl
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [url]
              properties:
                url:
                  type: string
                limit:
                  type: integer
                  default: 20
                webhook_url:
                  type: string

  /api/v1/hybrid/search:
    post:
      summary: Hybrid RAG search with reranking
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [query]
              properties:
                query:
                  type: string
                top_k:
                  type: integer
                  default: 30
                rerank_top_n:
                  type: integer
                  default: 10
                filters:
                  type: object
                include_graph:
                  type: boolean
                  default: false
                enable_cohere_rerank:
                  type: boolean
                  default: true

  /api/v1/tabular/query:
    post:
      summary: SQL query against tabular data
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [document_id, sql_query]
              properties:
                document_id:
                  type: string
                sql_query:
                  type: string
                timeout:
                  type: integer
                  default: 30

  /api/v1/memory/user:
    post:
      summary: Manage user long-term memory
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [user_id, action]
              properties:
                user_id:
                  type: string
                action:
                  type: string
                  enum: [create, update, search, delete]
                query:
                  type: string
                facts:
                  type: array
                min_relevance:
                  type: number
                  default: 0.7

  /api/v1/agent/route:
    post:
      summary: Route to appropriate agent
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [session_id, query]
              properties:
                session_id:
                  type: string
                user_id:
                  type: string
                query:
                  type: string
                use_long_term_memory:
                  type: boolean
                  default: false
```

#### 4.5.2 Hybrid RAG Endpoints

```yaml
  /api/v1/hybrid/record/check:
    post:
      summary: Check if record exists and needs update
      
  /api/v1/hybrid/record/create:
    post:
      summary: Create new record
      
  /api/v1/hybrid/record/update:
    post:
      summary: Update existing record
      
  /api/v1/hybrid/session/create:
    post:
      summary: Create new processing session
      
  /api/v1/hybrid/session/validate:
    post:
      summary: Validate session completion
      
  /api/v1/hybrid/embeddings/contextual:
    post:
      summary: Generate contextual embeddings with Mistral
      
  /api/v1/hybrid/metadata/enrich:
    post:
      summary: Enrich document with AI-generated metadata
      
  /api/v1/hybrid/graph/update:
    post:
      summary: Update knowledge graph with new entities
      
  /api/v1/hybrid/graph/query:
    post:
      summary: Query knowledge graph via LightRAG API
```

### 4.6 Appendix F: Testing Requirements

#### 4.6.1 Unit Testing Requirements

**TR-001:** Each module SHALL have minimum 80% code coverage  
**TR-002:** All API endpoints SHALL have unit tests  
**TR-003:** Error handling paths SHALL be tested  
**TR-004:** Mock external services for isolation  

#### 4.6.2 Integration Testing Requirements

**TR-005:** Test all document format conversions  
**TR-006:** Validate PDF routing logic  
**TR-007:** Test external API integrations (Cohere, Zep, Firecrawl, LightRAG)  
**TR-008:** Verify database operations  
**TR-009:** Test hybrid search with reranking  
**TR-010:** Validate memory persistence and retrieval  

#### 4.6.3 Performance Testing Requirements

**TR-011:** Load test with 100 concurrent documents  
**TR-012:** Stress test with maximum file sizes  
**TR-013:** Measure and validate response times  
**TR-014:** Test system recovery under failure  
**TR-015:** Test reranking performance with 30+ documents  
**TR-016:** Test SQL query performance on large tables  

#### 4.6.4 Security Testing Requirements

**TR-017:** Penetration testing annually  
**TR-018:** Vulnerability scanning monthly  
**TR-019:** Authentication/authorization testing  
**TR-020:** Data encryption validation  
**TR-021:** User memory isolation testing  

### 4.7 Appendix G: Monitoring and Observability

#### 4.7.1 Metrics to Monitor

| Metric | Threshold | Alert Level |
|--------|-----------|-------------|
| CPU Usage | >80% | Warning |
| Memory Usage | >90% | Critical |
| Processing Queue | >100 | Warning |
| Error Rate | >5% | Critical |
| API Latency | >1000ms | Warning |
| Database Connections | >50 | Warning |
| Reranking Time | >3s | Warning |
| Memory Retrieval Time | >1s | Warning |

#### 4.7.2 Logging Requirements

**OR-001:** Log all API requests with correlation IDs  
**OR-002:** Log processing milestones with timestamps  
**OR-003:** Log all errors with stack traces  
**OR-004:** Log security events separately  
**OR-005:** Implement log rotation and retention  
**OR-006:** Log reranking decisions and scores  
**OR-007:** Log memory operations per user  

#### 4.7.3 Dashboards

1. **Operations Dashboard**
   - Processing throughput
   - Queue status
   - Error rates
   - Service health

2. **Performance Dashboard**
   - Response times
   - Resource utilization
   - Database performance
   - Cache hit rates
   - Reranking performance

3. **Business Dashboard**
   - Documents processed
   - User activity
   - Content analytics
   - System usage trends
   - Memory utilization per user

### 4.8 Appendix H: Acceptance Criteria

#### 4.8.1 Functional Acceptance
- ✅ MarkItDown successfully processes 40+ formats
- ✅ Complex PDFs route correctly to Mistral OCR
- ✅ YouTube processing maintains three-tier transcript hierarchy
- ✅ Audio/video transcription includes speaker diarization
- ✅ Hash-based skip detection prevents redundant processing
- ✅ Hybrid search combines vector and keyword results
- ✅ Cohere reranking improves relevance
- ✅ Zep maintains user-specific memories
- ✅ Firecrawl successfully scrapes web content
- ✅ SQL queries work on tabular data
- ✅ Contextual embeddings improve retrieval
- ✅ Dual agent architecture functions correctly
- ✅ All content converts to clean Markdown

#### 4.8.2 Performance Acceptance
- ✅ 30% reduction in average processing time
- ✅ System handles 100+ documents daily
- ✅ Vector search latency under 100ms (95th percentile)
- ✅ Reranking completes within 2 seconds
- ✅ Memory retrieval under 500ms
- ✅ 99% uptime achieved monthly
- ✅ Concurrent processing of 5 files stable

#### 4.8.3 Integration Acceptance
- ✅ Backward compatibility with v2.8 maintained
- ✅ All external APIs integrated successfully
- ✅ SQL and Airtable remain synchronized
- ✅ Monitoring and alerting operational
- ✅ Security controls validated
- ✅ User memories properly isolated

9 has been reviewed and approved by:

| Name | Role | Signature | Date |
|------|------|-----------|------|
| | Project Manager | | |
| | Technical Lead | | |
| | QA Manager | | |
| | Product Owner | | |
| | Security Officer | | |

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 2.9 | 2025-09-26 | Complete IEEE 830 standardization with enhanced RAG features: Hybrid search with Cohere reranking, Zep long-term memory, Firecrawl web scraping, tabular data SQL queries, multimodal RAG, contextual embeddings via Mistral, advanced metadata filtering, dual agent architecture, LightRAG API integration | Engineering Team |
| 2.8 | 2025-08-15 | Streamlined architecture with MarkItDown MCP as primary processor, smart PDF routing with Mistral OCR fallback | Development Team |
| 2.7 | 2025-07-01 | Added hybrid RAG capabilities, hash-based change detection | Development Team |

---

**END OF DOCUMENT**

*This document contains comprehensive requirements and specifications for the AI Empire File Processing System v2.9 - an advanced Retrieval-Augmented Generation platform with hybrid search, long-term memory, and multi-agent capabilities*

**Version 2.9 Key Features:**
- Hybrid search with Cohere reranking for improved relevance
- Zep integration for user-specific long-term memory
- Firecrawl for automated web content ingestion
- SQL querying for tabular data analysis
- Multimodal RAG for mixed content types
- **Visual content querying using Mistral Pixtral-12B**
- Contextual embeddings using Mistral for better retrieval
- Advanced metadata filtering with complex queries
- Dual agent architecture (with/without memory)
- LightRAG API integration for knowledge graph capabilities
- Complete backward compatibility with v2.8 architecture

**Document Statistics:**
- Total Functional Requirements: 121 (updated with visual querying)
- Total Non-Functional Requirements: 30
- Total Security Requirements: 9
- Total Business Rules: 18
- Total Technical Constraints: 21
- Supported File Formats: 40+
- External Service Integrations: 12
- API Endpoints Defined: 20+

**Cost Optimization:**
- Visual querying via Mistral Pixtral: ~$0.0002 per image (50x cheaper than GPT-4V)
- Unified Mistral ecosystem reduces vendor complexity
- Efficient caching prevents redundant visual analysis

**Compliance:**
- IEEE Std 830-1998 compliant
- GDPR compliant
- SOC 2 Type II ready
- ISO/IEC 25010:2011 aligned

---