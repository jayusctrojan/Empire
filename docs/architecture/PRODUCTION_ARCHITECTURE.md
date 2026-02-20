# Empire v7.5 Production Architecture - Hybrid Database + Multi-Model Pipeline

## Overview

Empire v7.5 uses a **hybrid database production architecture** where PostgreSQL, Neo4j, and Redis work together as complementary systems, combined with a **multi-model AI pipeline** for every query.

---

## The Multi-Model Quality Pipeline

Every CKO query flows through a 3-stage pipeline using multiple AI providers:

```
User Query
     |
     v
[Sonnet 4.5 - Prompt Engineer]     ~1-2s
  Intent detection, format detection, enriched query
     |
     v
[Kimi K2.5 - Query Expansion] -> [RAG Search] -> [BGE-Reranker-v2]
     |
     v
[Kimi K2.5 Thinking - Reasoning]   ~3-8s
  Deep reasoning with citations
     |
     v
[Sonnet 4.5 - Output Architect]    ~2-3s
  Formatting, structuring, artifact detection, streaming
     |
     v (if artifact detected)
[Document Generator] -> [B2 Storage] -> [Artifact card in chat]
```

### LLM Client Abstraction

All providers implement a unified interface (`app/services/llm_client.py`):

```
LLMClient (abstract base)
  |-- TogetherAILLMClient    (Kimi K2.5 Thinking)
  |-- AnthropicLLMClient     (Claude Sonnet 4.5)
  |-- GeminiLLMClient        (Gemini 3 Flash)
  |-- OpenAICompatibleClient (Ollama/Qwen2.5-VL)
```

---

## The Hybrid Database Strategy

### 1. PostgreSQL (Supabase) - $25/month
**Purpose**: Traditional data, vectors, and multi-tenant storage
- User accounts and authentication
- Document content and metadata
- Vector embeddings (pgvector, 1024-dim BGE-M3)
- CKO chat sessions and messages
- Organizations and org memberships
- Generated artifacts (studio_cko_artifacts)
- Projects (org-scoped)
- Audit logs and system data
- Row-Level Security on org-scoped tables

### 2. Neo4j (Mac Studio Docker) - FREE
**Purpose**: Knowledge graphs and relationships
- Entity nodes (people, organizations, concepts)
- Document-entity relationships
- Multi-hop graph traversal
- Community detection
- Centrality analysis
- Path finding between entities

### 3. Redis (Upstash) - Free
**Purpose**: Caching and message brokering
- Response caching
- Celery task broker
- Rate limiting counters

### Both PostgreSQL and Neo4j Work Together in Production

```python
# Example: Processing a new document
async def process_document(document):
    # 1. Store in PostgreSQL
    doc_id = await supabase.table('documents').insert({
        'content': document.text,
        'metadata': document.metadata,
        'org_id': current_org_id  # v7.5: org-scoped
    })

    # 2. Generate embeddings -> PostgreSQL
    embeddings = await generate_embeddings(document.text)  # BGE-M3, 1024-dim
    await supabase.table('record_manager_v2').insert({
        'document_id': doc_id,
        'embedding': embeddings
    })

    # 3. Extract entities -> Neo4j
    entities = await extract_entities(document.text)
    for entity in entities:
        await neo4j.run("""
            MERGE (e:Entity {name: $name, type: $type})
            MERGE (d:Document {id: $doc_id})
            MERGE (d)-[:MENTIONS]->(e)
        """, name=entity.name, type=entity.type, doc_id=doc_id)
```

---

## Multi-Tenant Organization Layer (v7.5)

All data is scoped to organizations:

```
Organization (company)
  |-- org_memberships (user <-> org, roles: owner/admin/member/viewer)
  |-- projects (org-scoped)
  |-- studio_cko_sessions (chats, org-scoped)
  |-- documents (KB, org-scoped)
  |-- studio_cko_artifacts (org-scoped)
```

- **X-Org-Id header**: Sent with every API request from the desktop app
- **Middleware**: Extracts org_id, sets request.state.org_id
- **RLS**: PostgreSQL Row-Level Security enforces tenant isolation

---

## Key PostgreSQL Tables (v7.5)

### Core Tables
- `documents_v2` - Document metadata and content
- `record_manager_v2` - Vector embeddings (pgvector)
- `knowledge_entities` - Extracted entities
- `chat_sessions` - Legacy chat history
- `audit_logs` - Security audit trail

### v7.5 Additions
- `organizations` - Company/org entities (slug, logo, settings)
- `org_memberships` - User-org relationships (owner/admin/member/viewer roles)
- `studio_cko_sessions` - CKO chat sessions (with org_id)
- `studio_cko_messages` - CKO chat messages
- `studio_cko_artifacts` - Generated document artifacts (DOCX/XLSX/PPTX/PDF)
- `projects` - Projects (with org_id)

---

## Unified Search Architecture

`GET /api/search/unified` searches across all content types within the user's organization:

```python
# Parallel search with asyncio.gather
tasks = []
if "chat" in search_types:
    tasks.append(_safe(_search_chats(supabase, q, org_id, user_id, limit), "Chat"))
if "project" in search_types:
    tasks.append(_safe(_search_projects(supabase, q, org_id, user_id, limit), "Project"))
if "kb" in search_types:
    tasks.append(_safe(_search_kb_documents(supabase, q, org_id, limit), "KB"))
if "artifact" in search_types:
    tasks.append(_safe(_search_artifacts(supabase, q, org_id, user_id, limit), "Artifact"))

for type_results in await asyncio.gather(*tasks):
    results.extend(type_results)
```

- PostgREST ilike injection protection
- Relevance scoring (title matches > description matches)
- Results sorted by relevance then date

---

## Storage Architecture

### Backblaze B2 (File Storage)

```
b2://empire-documents/
  {department}/           # 12 business departments
    {document_id}/
      original.pdf
      processed.txt
      metadata.json
  artifacts/documents/    # Generated artifacts (v7.5)
    {artifact_id}.docx
    {artifact_id}.xlsx
    {artifact_id}.pptx
  crewai/assets/          # CrewAI outputs
```

---

## Document Generation & Artifacts (v7.5)

| Format | Library | Use Case |
|--------|---------|----------|
| DOCX | python-docx | Reports, memos, analysis |
| XLSX | openpyxl | Spreadsheets, data tables |
| PPTX | python-pptx | Presentations, slide decks |
| PDF | PDFReportGenerator | Formal reports |

Artifact lifecycle:
1. Output Architect detects artifact-worthy content
2. Document Generator creates file from content blocks
3. File uploaded to B2 (`artifacts/documents/`)
4. Metadata saved to `studio_cko_artifacts` table
5. SSE event sent to desktop app
6. Desktop shows inline ArtifactCard with preview/download

---

## Multimodal Processing

### Image Analysis (3-tier fallback)
```
Image -> Qwen2.5-VL-32B (local, Ollama)
           |  (fallback)
         Kimi K2.5 Thinking (Together AI)
           |  (fallback)
         Gemini 3 Flash (Google AI)
```

### Audio Processing
```
Audio -> distil-whisper/distil-large-v3.5 (local, faster-whisper, 2x realtime)
           -> Transcript -> RAG pipeline
```

### Video Processing
```
Video -> ffmpeg frame extraction -> Gemini 3 Flash analysis -> Summary
```

---

## Security Architecture

| Layer | Implementation |
|-------|---------------|
| Transport | TLS 1.2+ on all services |
| Authentication | Clerk auth + JWT tokens |
| Authorization | Row-Level Security on org-scoped tables |
| Multi-Tenancy | Organization-level data isolation |
| API Auth | X-API-Key for Telegram bots |
| Rate Limiting | Redis-backed, tiered by endpoint |
| Encryption | AES-256 at rest (Supabase, B2) |
| Audit | Comprehensive event logging |
| Input Sanitization | PostgREST ilike injection protection |
| HTTP Headers | HSTS, CSP, X-Frame-Options, X-Content-Type-Options |

---

## Infrastructure & Monitoring

### Cloud Services (Render.com)

| Service | Purpose | Cost |
|---------|---------|------|
| jb-empire-api | FastAPI backend | $7/month |
| empire-celery-worker | Background tasks | $7/month |
| jb-empire-chat | Gradio chat UI | $7/month |
| jb-crewai | Multi-agent workflows | $7/month |

### Monitoring Stack

| Component | Purpose | Port |
|-----------|---------|------|
| Prometheus | Metrics collection | 9090 |
| Grafana | Visualization | 3001 |
| Alertmanager | Email notifications | 9093 |

39 alert rules: Critical (service down), Warning (performance), Info (health summaries)

---

## Cost Summary

| Category | Monthly Cost |
|----------|-------------|
| Render Services (4) | $28 |
| Supabase PostgreSQL | $25 |
| Backblaze B2 | ~$5 |
| Upstash Redis | Free |
| Neo4j (self-hosted) | $0 |
| **Infrastructure Total** | **~$60** |
| Anthropic API | ~$0.004/query |
| Together AI | Usage-based |
| Google AI | Usage-based |

---

## Why This Architecture

- **PostgreSQL + Neo4j**: Each excels at different queries - vectors/relational vs. graphs/relationships
- **Multi-model pipeline**: Sonnet 4.5 for formatting quality, Kimi K2.5 for deep reasoning
- **Local models**: Zero-cost vision and audio processing on Mac Studio
- **Multi-tenant**: Organization isolation with RLS for SaaS readiness
- **Cost efficient**: ~$60/month infrastructure + usage-based AI costs
