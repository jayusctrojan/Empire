## 10.1 Overview

This section provides a complete, production-ready implementation guide for the AI Empire v7.1 workflow orchestration using n8n. Each milestone represents a testable, independent component that builds upon the previous one, with all v7.1 enhancements for state-of-the-art RAG performance.

### 10.1.1 Implementation Philosophy

**Core Principles (v7.1):**
- **Incremental Development:** Build and test one component at a time
- **Milestone-Based:** Each milestone is independently functional
- **Test-First:** Validate each component before integration
- **API-First:** Prioritize Claude Sonnet 4.5 API for synthesis + Claude Haiku for expansion
- **Advanced RAG:** BGE-M3 embeddings, Query expansion, BGE-Reranker-v2, Adaptive chunking
- **Cost-Optimized:** Use batch processing, prompt caching, and BGE-Reranker-v2 for 70-85% savings
- **Fail-Safe:** Include error handling and fallbacks from the beginning
- **Observable:** Add logging, monitoring, and cost tracking at each step
- **Native First:** Use native n8n nodes where available, HTTP wrappers for external services
- **Performance First:** Target 40-60% better retrieval quality, <1s query latency

### 10.1.2 Complete n8n Architecture for v7.1

```
n8n Instance (Render - $15-30/month)
├── Webhook Endpoints (Entry Points)
│   ├── /webhook/document-upload (Document Intake)
│   ├── /webhook/chat (Chat Interface)
│   ├── /webhook/query (Direct RAG Queries)
│   ├── /webhook/admin (Administrative Tasks)
│   └── /webhook/monitoring (Health Checks)
│
├── Workflow Engine (Core Orchestration)
│   ├── Document Processing Pipeline
│   ├── RAG Query Pipeline
│   ├── Chat Memory Management
│   ├── External Service Integration
│   └── Error Handling & Recovery
│
├── Native Node Types Available:
│   ├── n8n-nodes-base.webhook (HTTP Triggers) - v2.1
│   ├── @n8n/n8n-nodes-langchain.lmChatAnthropic (Claude Sonnet + Haiku) - v1.0
│   ├── @n8n/n8n-nodes-langchain.anthropic (Claude Messages) - v1.0
│   ├── @n8n/n8n-nodes-langchain.embeddingsBGEm3 (BGE-M3 1024-dim) - v1.0 [NEW v7.1]
│   ├── @n8n/n8n-nodes-langchain.vectorStoreSupabase (Vector Operations) - v1.0
│   ├── n8n-nodes-base.postgres (Database Queries) - v2.6
│   ├── n8n-nodes-base.supabase (Supabase Operations) - v1.0
│   ├── n8n-nodes-base.s3 (Backblaze B2 Storage) - v1.0
│   ├── n8n-nodes-base.code (Custom JavaScript/Python) - v2.0
│   ├── n8n-nodes-base.if (Conditional Logic) - v2.0
│   ├── n8n-nodes-base.switch (Multi-Route Logic) - v3.3
│   ├── n8n-nodes-base.merge (Data Merging) - v3.0
│   ├── n8n-nodes-base.splitInBatches (Batch Processing) - v3.0
│   ├── @n8n/n8n-nodes-langchain.chatTrigger (Native Chat Interface) - v1.0
│   ├── n8n-nodes-base.httpRequest (External APIs) - v4.2
│   └── n8n-nodes-base.redis (Caching) - v2.0
│
├── External Services via HTTP Request:
│   ├── BGE-Reranker-v2 (Mac Studio - $0 local) [REPLACES Cohere v7.1]
│   ├── Claude Haiku (Query Expansion - $1.50-9/month) [NEW v7.1]
│   ├── LightRAG API (Knowledge Graph - $15/month)
│   ├── CrewAI API (Multi-Agent - $20/month)
│   ├── LlamaCloud/LlamaParse (Free Tier OCR - 10K pages/month) [NEW v7.1]
│   ├── Soniox API (Audio Transcription - $0-20/month)
│   └── Custom APIs (Any additional services)
│
└── Infrastructure Components:
    ├── Supabase (Vector DB + PostgreSQL - $25/month)
    ├── Backblaze B2 (Object Storage - $10-20/month)
    ├── Redis (Caching Layer - $7/month)
    └── Monitoring (Prometheus/Grafana - Self-hosted)
```

### 10.1.3 Key Technical Corrections Applied

**Expression Syntax Corrections:**
- ❌ OLD: `{{field}}` or `{{$node.NodeName.field}}`
- ✅ NEW: `{{ $json.field }}` or `{{ $node['Node Name'].json.field }}`

**Node Type Corrections:**
- ❌ OLD: `n8n-nodes-base.function`
- ✅ NEW: `n8n-nodes-base.code`

**Webhook Configuration Corrections:**
- ❌ OLD: `bodyContentType: 'multipart'`
- ✅ NEW: `options.rawBody: true, options.binaryPropertyName: 'file'`

**Switch Node Corrections:**
- ❌ OLD: Direct conditions in switch
- ✅ NEW: `rules.values` collection with proper structure

**Database Query Corrections:**
- ❌ OLD: Direct parameter interpolation
- ✅ NEW: `options.queryParams` with proper array format
