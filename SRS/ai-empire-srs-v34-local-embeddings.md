# Software Requirements Specification for AI Empire File Processing System
## Version 3.4
### Complete RAG Platform with Local BGE-M3 Embeddings via Ollama

**Document Status:** Final Draft
**Date:** November 2, 2025
**Classification:** Confidential - Internal Use
**IEEE Std 830-1998 Compliant**

---

## Document Control

### Revision History

| Version | Date | Author | Description | Approval |
|---------|------|--------|-------------|----------|
| 3.4 | 2025-11-02 | Engineering Team | Local BGE-M3 embeddings via Ollama integration - ZERO API costs for embeddings | Pending |
| 3.3 | 2025-09-27 | Engineering Team | Complete unified specification with v3.2 features | Approved |
| 3.2 | 2025-09-27 | Engineering Team | Complete unified specification incorporating all v2.9 features plus v3.0 parallel processing and v3.1 solopreneur optimizations | Approved |
| 3.1 | 2025-09-27 | Engineering Team | Solopreneur optimizations with cost tracking and fast track processing | Approved |
| 3.0 | 2025-09-27 | Engineering Team | Parallel processing and performance enhancements | Approved |
| 2.9 | 2025-09-26 | Engineering Team | IEEE 830 standardization with enhanced RAG capabilities, hybrid search, long-term memory | Approved |

### Document Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Project Manager | | | |
| Technical Lead | | | |
| QA Lead | | | |
| Product Owner | | | |
| Security Officer | | | |
| Performance Engineer | | | |

### Distribution List

- Development Team
- Product Management
- Quality Assurance Team
- System Administrators
- Security Team
- DevOps Engineers
- Performance Engineering Team
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

4. [Version 3.0 Enhancements](#4-version-30-enhancements)
   4.1 [Parallel Processing Engine](#41-parallel-processing-engine)
   4.2 [Semantic Chunking System](#42-semantic-chunking-system)
   4.3 [Quality Monitoring Framework](#43-quality-monitoring-framework)
   4.4 [Advanced Caching Architecture](#44-advanced-caching-architecture)

5. [Version 3.1 Solopreneur Optimizations](#5-version-31-solopreneur-optimizations)
   5.1 [Fast Track Processing](#51-fast-track-processing)
   5.2 [Cost Management System](#52-cost-management-system)
   5.3 [Intelligent Error Recovery](#53-intelligent-error-recovery)
   5.4 [Adaptive Optimization](#54-adaptive-optimization)

6. [Version 3.4 Local Embeddings Integration](#6-version-34-local-embeddings)
   6.1 [Ollama BGE-M3 Embeddings](#61-ollama-bge-m3-embeddings)
   6.2 [Zero-Cost Architecture](#62-zero-cost-architecture)
   6.3 [Performance Improvements](#63-performance-improvements)
   6.4 [Migration Strategy](#64-migration-strategy)

7. [Supporting Information](#7-supporting-information)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) document provides a complete description of all functions and specifications for the AI Empire File Processing System, version 3.4. This document is intended for all project stakeholders including developers, system architects, quality assurance teams, project managers, and business stakeholders involved in the development, deployment, and maintenance of the AI Empire intelligent document processing and retrieval-augmented generation platform.

**Version 3.4 Key Update:** Integration of local BGE-M3 embeddings via Ollama, eliminating ALL embedding API costs while improving performance by 5-10x. This update maintains complete backward compatibility while providing immediate cost savings of $50-100/month for active usage.

### 1.2 Scope

**Product Name:** AI Empire File Processing System
**Product Version:** 3.4
**Product Description:**

The AI Empire File Processing System is an enterprise-grade automated workflow system that processes diverse document formats, multimedia content, and web resources to generate organizational intelligence through retrieval-augmented generation. Version 3.4 introduces local BGE-M3 embeddings via Ollama, providing zero-cost embeddings with improved performance.

**New Capabilities in v3.4:**
- **Local BGE-M3 Embeddings**: 1024-dimensional embeddings via Ollama (FREE)
- **Zero Embedding API Costs**: Saves $50-100/month in active usage
- **5-10x Performance Improvement**: <10ms local vs 50-100ms API
- **Complete Data Privacy**: All embeddings processed locally
- **Seamless Graphiti MCP Integration**: Drop-in replacement for OpenAI/Mistral embeddings
- **Personal Memory Import**: 322 ChatGPT conversations imported with local embeddings

**Core Capabilities (All Maintained from v3.3):**
- All v2.9, v3.0, and v3.1 features remain fully functional
- Unified document processing supporting 40+ file formats
- Parallel processing of up to 5 documents simultaneously
- Temporal knowledge graphs via Graphiti
- Personal vs work memory separation via group_id
- Fast track processing for simple documents
- Real-time cost tracking and optimization

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|------|------------|
| **BGE-M3** | BAAI General Embedding Model - Multilingual, Multifunctionality, Multi-granularity |
| **Ollama** | Local LLM/embedding server for running AI models on-device |
| **MCP** | Model Context Protocol - Claude Desktop integration standard |
| **Graphiti** | Temporal knowledge graph system for memory management |
| **RAG** | Retrieval-Augmented Generation - AI technique combining retrieval with generation |
| **Embeddings** | Vector representations of text for similarity search |
| **group_id** | Memory isolation identifier (personal, project_empire, etc.) |
| **TTL** | Time To Live - Cache expiration duration |
| **OOM** | Out Of Memory - System resource exhaustion |
| **UV** | Modern Python package management tool |
| **Neo4j** | Graph database for storing temporal knowledge graphs |
| **Pinecone** | Cloud-native vector database for similarity search |
| **Zep** | Long-term memory service for user-specific information storage |

### 1.4 References

1. IEEE Std 830-1998 - IEEE Recommended Practice for Software Requirements Specifications
2. Ollama Documentation - https://ollama.ai/docs
3. BGE-M3 Model Card - https://huggingface.co/BAAI/bge-m3
4. Graphiti MCP Documentation - Internal
5. Neo4j Graph Database Documentation - https://neo4j.com/docs
6. Claude Desktop MCP Integration Guide - https://claude.ai/docs/mcp
7. Original mem-agent Documentation - https://github.com/dria/mem-agent
8. Empire Architecture Document v7.3 - Internal

### 1.5 Overview

This document is structured according to IEEE 830-1998 standard. Section 2 provides an overall description of the system including architecture and constraints. Section 3 details specific functional and non-functional requirements. Sections 4-6 describe version-specific enhancements, with Section 6 focusing on the new local embeddings integration in v3.4.

---

## 2. Overall Description

### 2.1 Product Perspective

#### 2.1.1 System Context

The AI Empire File Processing System v3.4 operates as a comprehensive document intelligence platform with local embedding generation:

```
Local Infrastructure:
├── Mac Studio (Primary)
│   ├── Ollama Server
│   │   ├── BGE-M3 Model (1024-dim)
│   │   └── BGE-Reranker-v2 (future)
│   └── Neo4j Database
│       ├── Personal Memories (322 ChatGPT)
│       └── Project Memories (isolated)
│
Cloud Infrastructure (Existing):
├── Render.com (n8n workflows)
├── Pinecone (vector storage)
├── LightRAG API (knowledge graphs)
└── External APIs (non-embedding)
```

#### 2.1.2 System Architecture with Local Embeddings

```
Input Layer (Unchanged):
├── HTML Upload Interface
├── Backblaze B2 Monitoring
├── YouTube URL Processing
├── Web Scraping (Firecrawl)
├── SFTP/Local File Monitoring
└── Direct API Calls

Processing Layer (Updated for v3.4):
├── Document Router
│   ├── Hash Check (Skip if unchanged)
│   ├── Format Detection
│   └── Cost-Aware Selection
├── Primary Processors (Unchanged)
│   ├── MarkItDown MCP (40+ formats)
│   ├── Mistral OCR (Complex PDFs only)
│   ├── Mistral Pixtral (Visual content)
│   ├── YouTube API (Transcripts/Frames)
│   ├── Soniox (Audio/Video)
│   └── Firecrawl (Web Content)
└── Unified Markdown Output

Embedding Layer (NEW in v3.4):
├── Ollama BGE-M3 Service
│   ├── Local Processing (<10ms)
│   ├── 1024-Dimensional Vectors
│   ├── Zero API Costs
│   └── Complete Privacy
├── Fallback Options
│   ├── OpenAI API (backup only)
│   └── Mistral API (contextual, optional)
└── Batch Processing Support

Memory Layer (Enhanced in v3.4):
├── Graphiti MCP Server
│   ├── Temporal Knowledge Graphs
│   ├── OllamaEmbedder Integration
│   └── Group-based Isolation
├── Personal Memories
│   ├── 322 ChatGPT Conversations
│   └── group_id='personal'
└── Project Memories
    ├── project_empire
    └── project_{name} pattern
```

### 2.2 Product Functions

#### 2.2.1 Core Functions (Maintained from v3.3)

1. **Document Processing** - All 40+ formats via MarkItDown
2. **Multimedia Processing** - Audio/video/visual content
3. **Web Ingestion** - Firecrawl scraping
4. **Hash-based Deduplication** - Skip unchanged content
5. **Parallel Processing** - Up to 5 concurrent documents
6. **Fast Track Processing** - 70% faster for simple documents
7. **Hybrid Search** - Vector + keyword + graph
8. **Long-term Memory** - Via Zep integration
9. **Multi-agent Intelligence** - CrewAI collaboration

#### 2.2.2 New Functions in v3.4

1. **Local Embedding Generation**
   - BGE-M3 via Ollama server
   - 1024-dimensional vectors
   - <10ms generation time
   - Batch processing support

2. **Zero-Cost Memory Import**
   - Import ChatGPT conversations
   - Process with local embeddings
   - Save $0.64+ per import

3. **Enhanced Memory Management**
   - Graphiti temporal graphs
   - Project-based isolation
   - Personal vs work separation

4. **Cost Elimination**
   - $0 embedding costs
   - $50-100/month savings
   - Reduced API dependencies

### 2.3 User Characteristics

#### 2.3.1 Updated User Personas for v3.4

**Primary Persona - Cost-Conscious Solopreneur:**
- Name: Jay (Primary System Owner)
- Technical Expertise: Medium to High
- Daily Document Volume: 50-200 documents
- Budget Constraint: Reduced from $500 to $400/month with v3.4
- Embedding Costs: $0 (was $50-100/month)
- Primary Concerns: Cost efficiency, data privacy, performance
- Infrastructure: Mac Studio with Ollama

### 2.4 Constraints

#### 2.4.1 Technical Constraints (Updated for v3.4)

**TC-034:** Ollama server must be running locally for embedding generation
**TC-035:** BGE-M3 model requires 2GB RAM when loaded
**TC-036:** Neo4j database required for Graphiti temporal graphs
**TC-037:** Mac Studio or equivalent for optimal local performance
**TC-038:** Embedding dimensions fixed at 1024 for BGE-M3

#### 2.4.2 Resource Constraints (Updated)

**TC-039:** Local storage for Ollama models (~2GB per model)
**TC-040:** Network bandwidth not required for embeddings (local only)
**TC-041:** CPU/GPU resources for local embedding generation

### 2.5 Assumptions and Dependencies

#### 2.5.1 New Assumptions for v3.4

1. **Infrastructure Assumptions**
   - Ollama server remains available on localhost:11434
   - Local hardware sufficient for embedding workload
   - BGE-M3 model provides comparable quality to OpenAI
   - Network latency eliminated for embeddings

2. **Cost Assumptions**
   - Embedding API costs will continue rising
   - Local compute costs negligible vs API costs
   - One-time hardware investment justified by savings

#### 2.5.2 Updated Dependencies

1. **Local Service Dependencies**
   - Ollama Server v0.1.31+
   - BGE-M3 model (BAAI/bge-m3)
   - Neo4j Community Edition
   - Python 3.11+ with httpx

2. **Reduced External Dependencies**
   - OpenAI API (backup only, not for embeddings)
   - Mistral API (optional contextual embeddings only)

---

## 3. Specific Requirements

### 3.1 Functional Requirements

#### 3.1.1 Local Embedding Requirements (NEW in v3.4)

**FR-200:** The system SHALL generate embeddings using local BGE-M3 model via Ollama
*Priority: Essential*

**FR-201:** The system SHALL maintain <10ms embedding generation time for text up to 3000 characters
*Priority: Essential*

**FR-202:** The system SHALL produce 1024-dimensional embedding vectors
*Priority: Essential*

**FR-203:** The system SHALL support batch embedding generation for multiple texts
*Priority: High*

**FR-204:** The system SHALL fallback to OpenAI embeddings if Ollama is unavailable
*Priority: Medium*

**FR-205:** The system SHALL integrate seamlessly with Graphiti MCP server
*Priority: Essential*

#### 3.1.2 Memory Management Requirements (Enhanced in v3.4)

**FR-206:** The system SHALL use group_id for memory isolation
*Priority: Essential*

**FR-207:** The system SHALL support unlimited project-based memories with pattern project_{name}
*Priority: Essential*

**FR-208:** The system SHALL import ChatGPT conversations with local embeddings
*Priority: High*

**FR-209:** The system SHALL maintain temporal knowledge graphs via Graphiti
*Priority: Essential*

### 3.2 Non-Functional Requirements

#### 3.2.1 Performance Requirements (Updated for v3.4)

**NFR-100:** The system SHALL achieve 5-10x faster embedding generation vs API calls
*Measurement: <10ms local vs 50-100ms API*

**NFR-101:** The system SHALL process 322 ChatGPT conversations in <60 seconds
*Measurement: Total import time with local embeddings*

**NFR-102:** The system SHALL handle 1000+ embeddings per minute locally
*Measurement: Throughput testing*

#### 3.2.2 Cost Requirements (NEW in v3.4)

**NFR-103:** The system SHALL operate with $0 embedding API costs
*Measurement: Monthly API billing*

**NFR-104:** The system SHALL save $50-100/month on embeddings
*Measurement: Cost comparison vs OpenAI/Mistral*

### 3.3 External Interface Requirements

#### 3.3.1 Ollama API Interface (NEW)

```python
Interface: Ollama Embeddings API
Protocol: HTTP/REST
Endpoint: http://localhost:11434/api/embeddings
Method: POST
Request:
{
  "model": "bge-m3",
  "prompt": "text to embed"
}
Response:
{
  "embedding": [0.1, 0.2, ..., 0.n]  # 1024 dimensions
}
```

### 3.4 System Features

#### 3.4.1 Feature: Zero-Cost Embedding Generation

**Description:** Generate embeddings locally using BGE-M3 via Ollama with zero API costs

**Priority:** Essential

**Stimulus/Response Sequences:**
1. Text content requires embedding
2. System sends request to local Ollama server
3. Ollama generates BGE-M3 embedding
4. System receives 1024-dim vector
5. Vector stored in Neo4j/Pinecone
6. No API charges incurred

**Functional Requirements:**
- FR-200 through FR-205

### 3.5 Performance Requirements

#### 3.5.1 Embedding Performance (NEW)

| Metric | Requirement | Condition |
|--------|-------------|-----------|
| Embedding latency | <10ms | Text <3000 chars |
| Embedding throughput | 1000/min | Batch processing |
| Memory usage | <2GB | BGE-M3 loaded |
| CPU usage | <50% | During generation |

---

## 4. Version 3.0 Enhancements

(Maintained as-is from v3.3)

---

## 5. Version 3.1 Solopreneur Optimizations

(Maintained as-is from v3.3)

---

## 6. Version 3.4 Local Embeddings Integration

### 6.1 Ollama BGE-M3 Embeddings

#### 6.1.1 Architecture

```python
class OllamaEmbedder(EmbedderClient):
    """
    Graphiti-compatible embedder using local Ollama server.
    Implements EmbedderClient interface for seamless integration.
    """
    def __init__(self, model="bge-m3", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.dimensions = 1024

    async def create(self, input_data: str) -> List[float]:
        """Generate embedding with zero API cost."""
        response = await self.client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": input_data}
        )
        return response.json()["embedding"]
```

#### 6.1.2 Integration Points

1. **Graphiti MCP Server**
   - Updated factories.py to create OllamaEmbedder
   - Modified config.yaml to use ollama provider
   - Maintains full Graphiti functionality

2. **Direct Neo4j Import**
   - SimpleOllamaEmbedder for standalone use
   - Batch processing for ChatGPT import
   - Group-based memory isolation

### 6.2 Zero-Cost Architecture

#### 6.2.1 Cost Comparison

| Component | Before (API) | After (Local) | Monthly Savings |
|-----------|-------------|---------------|-----------------|
| Embeddings | $0.0002/1K tokens | $0 | $50-100 |
| Import 322 chats | $0.64 | $0 | $0.64 |
| Daily usage (200 docs) | $2-3 | $0 | $60-90 |
| Annual savings | - | - | $600-1200 |

#### 6.2.2 Infrastructure Investment

- **One-time**: Mac Studio or equivalent
- **ROI**: 6-12 months based on usage
- **Additional benefits**: Privacy, performance, reliability

### 6.3 Performance Improvements

#### 6.3.1 Latency Reduction

```
API Embeddings:
- Network round trip: 20-50ms
- API processing: 20-30ms
- Error handling/retry: 0-500ms
- Total: 50-100ms average

Local Embeddings:
- Local processing: 5-10ms
- No network latency: 0ms
- No retry needed: 0ms
- Total: <10ms consistent
```

#### 6.3.2 Throughput Improvements

- **API**: Limited by rate limits (100-1000/min)
- **Local**: Limited only by CPU/GPU (1000+/min)
- **Batch processing**: Full parallelization possible

### 6.4 Migration Strategy

#### 6.4.1 Zero-Downtime Migration

1. **Install Ollama and BGE-M3**
   ```bash
   brew install ollama
   ollama pull bge-m3
   ```

2. **Update Configuration**
   ```yaml
   embedder:
     provider: "ollama"
     model: "bge-m3"
     dimensions: 1024
   ```

3. **Import Existing Data**
   ```bash
   python import_chatgpt_ollama_direct.py
   ```

#### 6.4.2 Rollback Strategy

- Keep OpenAI API keys as backup
- Config switch for instant rollback
- Dual-mode operation during transition

---

## 7. Supporting Information

### 7.1 Implementation Checklist

- [x] Ollama server installation
- [x] BGE-M3 model deployment
- [x] OllamaEmbedder class implementation
- [x] Graphiti MCP integration
- [x] ChatGPT import with local embeddings
- [x] Cost tracking validation
- [x] Performance benchmarking
- [x] Documentation updates

### 7.2 Performance Metrics

**Actual Results from Production:**
- 322 ChatGPT conversations imported
- Total embeddings generated: 322
- Total time: <60 seconds
- Cost savings: $0.64 immediate, $50-100/month ongoing
- Latency improvement: 5-10x
- Privacy: 100% local processing

### 7.3 Future Enhancements

1. **BGE-Reranker-v2 Integration**
   - Local reranking capabilities
   - Further API cost reduction

2. **GPU Acceleration**
   - Metal Performance Shaders on Mac
   - 10x+ throughput improvement

3. **Multi-model Support**
   - Alternative embedding models
   - Model A/B testing

---

**Document Version:** 3.4
**Last Updated:** November 2, 2025
**Status:** Implementation Complete
**Next Review:** December 2025

---

## Appendix A: Configuration Examples

### A.1 Graphiti MCP Server Configuration

```yaml
# config.yaml
llm:
  provider: "anthropic"
  model: "claude-sonnet-4-5-latest"

embedder:
  provider: "ollama"
  model: "bge-m3"
  dimensions: 1024

database:
  provider: "neo4j"
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "${NEO4J_PASSWORD}"
```

### A.2 Environment Variables

```env
# .env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=***REMOVED***
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3
GROUP_ID=personal
```

### A.3 Import Script Usage

```bash
# Import all ChatGPT conversations with local embeddings
python import_chatgpt_ollama_direct.py

# Switch memory context
./mem switch project_empire

# Query memories in Neo4j
MATCH (n:Episodic) WHERE n.group_id = 'personal' RETURN n LIMIT 25
```

---

**END OF DOCUMENT**