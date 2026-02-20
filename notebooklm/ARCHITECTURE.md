# Empire v7.5 - Production Architecture

**Version:** v7.5.0
**Last Updated:** 2026-02-19
**Status:** Production Ready

---

## AI Processing Architecture

### Multi-Model Quality Pipeline

Empire v7.5 uses a **3-stage multi-model pipeline** for every query. Two different AI providers work together:

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

### AI Models Used

| Purpose | Model | Provider | Type | Cost |
|---------|-------|----------|------|------|
| **Prompt Engineering** | Claude Sonnet 4.5 | Anthropic | Cloud API | ~$0.002/query |
| **Output Formatting** | Claude Sonnet 4.5 | Anthropic | Cloud API | ~$0.002/query |
| **Reasoning Engine** | Kimi K2.5 Thinking | Together AI | Cloud API | Usage-based |
| **Query Expansion** | Kimi K2.5 | Together AI | Cloud API | Usage-based |
| **Image Analysis (primary)** | Kimi K2.5 Thinking | Together AI | Cloud API | Usage-based |
| **Image Fallback** | Gemini 3 Flash | Google AI | Cloud API | Usage-based |
| **Local Vision** | Qwen2.5-VL-32B | Ollama | Local (Mac Studio) | $0 |
| **Audio STT** | distil-whisper/distil-large-v3.5 | faster-whisper | Local (Mac Studio) | $0 |
| **Video Frames** | Gemini 3 Flash | Google AI | Cloud API | Usage-based |
| **Embeddings** | BGE-M3 | Local/Render | 1024-dim vectors | $0 |
| **Reranking** | BGE-Reranker-v2 | Local | Search optimization | $0 |

### LLM Client Abstraction Layer

All AI providers implement a unified interface (`app/services/llm_client.py`):

```
LLMClient (abstract base)
  |-- TogetherAILLMClient    (Kimi K2.5 Thinking)
  |-- AnthropicLLMClient     (Claude Sonnet 4.5)
  |-- GeminiLLMClient        (Gemini 3 Flash)
  |-- OpenAICompatibleClient (Ollama/Qwen2.5-VL, any OpenAI-compatible API)
```

Features: `generate()`, `generate_with_images()`, `is_retryable()`, automatic retry with backoff.

### 15+ AI Agents (Legacy + Pipeline)

| Agent | Purpose |
|-------|---------|
| AGENT-002 | Content Summarizer - PDF summaries |
| AGENT-008 | Department Classifier - 12 business departments |
| AGENT-009 | Senior Research Analyst - Topic/entity extraction |
| AGENT-010 | Content Strategist - Executive summaries |
| AGENT-011 | Fact Checker - Claim verification |
| AGENT-012 | Research Agent - Web/academic search |
| AGENT-013 | Analysis Agent - Pattern detection |
| AGENT-014 | Writing Agent - Report generation |
| AGENT-015 | Review Agent - Quality assurance |
| Prompt Engineer | Query enrichment and intent detection (Sonnet 4.5) |
| Output Architect | Response formatting and artifact detection (Sonnet 4.5) |

---

## Application Architecture

### Two Frontend Interfaces

| Interface | Technology | Purpose |
|-----------|------------|---------|
| **Empire Desktop** | Tauri 2.x + React + TypeScript | Primary desktop app with full features |
| **Gradio Chat** | Gradio (Python) | Web-based chat interface |

### Desktop App Architecture

```
empire-desktop/
  src/
    components/         # React components (31 files)
      auth/             # Authentication (Clerk)
      chat/             # Chat UI, artifacts, phase indicators
      projects/         # Project management
    stores/             # Zustand state management
      chat.ts           # Conversations, messages, artifacts, phases
      app.ts            # View state, sidebar
      org.ts            # Organization selection, switching
      projects.ts       # Project list
    lib/
      api/              # Backend API client
        client.ts       # Fetch wrapper with X-Org-Id header
        search.ts       # Unified search API
        artifacts.ts    # Artifact download/metadata
        index.ts        # Core API functions
      database.ts       # Local IndexedDB for offline data
    test/
      setup.ts          # vitest + jsdom + localStorage mock
```

### Backend Architecture

```
app/
  routes/              # 57 API route modules (300+ endpoints)
    unified_search.py  # Cross-type search with asyncio.gather
    organizations.py   # Multi-tenant org management
    artifacts.py       # Artifact CRUD + download
    studio_cko.py      # CKO chat with multi-model pipeline
    kb_submissions.py  # Knowledge base submissions
    ...
  services/            # 139 service files
    llm_client.py      # Unified LLM provider abstraction
    prompt_engineer_service.py    # Sonnet 4.5 prompt enrichment
    output_architect_service.py   # Sonnet 4.5 output formatting
    document_generator_service.py # DOCX/XLSX/PPTX/PDF generation
    organization_service.py       # Org CRUD + membership
    vision_service.py             # Multi-provider image analysis
    whisper_stt_service.py        # Local audio transcription
    audio_video_processor.py      # Video frame extraction + analysis
    studio_cko_conversation_service.py  # CKO chat orchestration
    ...
  core/
    database.py        # Supabase client initialization
    config.py          # Environment configuration
  middleware/          # Auth, rate limiting, org context
```

---

## Database Architecture

### Hybrid Database System

| Database | Provider | Purpose | Cost |
|----------|----------|---------|------|
| **PostgreSQL** | Supabase | Vectors, user data, sessions, orgs, artifacts, audit logs | $25/month |
| **Neo4j** | Mac Studio Docker | Knowledge graphs, entity relationships | $0 |
| **Redis** | Upstash | Caching, Celery broker, rate limiting | Free tier |

### Key PostgreSQL Tables

**Core Tables:**
- `documents_v2` - Document metadata and content
- `record_manager_v2` - Vector embeddings (pgvector)
- `knowledge_entities` - Extracted entities
- `chat_sessions` - Chat history
- `audit_logs` - Security audit trail

**v7.5 Additions:**
- `organizations` - Company/org entities (slug, logo, settings)
- `org_memberships` - User-org relationships (owner/admin/member/viewer roles)
- `studio_cko_sessions` - CKO chat sessions (with org_id)
- `studio_cko_messages` - CKO chat messages
- `studio_cko_artifacts` - Generated document artifacts (DOCX/XLSX/PPTX/PDF)
- `projects` - Projects (with org_id)

### Row-Level Security

All org-scoped tables enforce RLS policies. Users can only access data within organizations they belong to.

---

## Storage Architecture

### Backblaze B2 (File Storage)

```
b2://empire-documents/
  {department}/           # 12 departments
    {document_id}/
      original.pdf
      processed.txt
      metadata.json
  artifacts/documents/    # NEW: Generated artifacts (v7.5)
    {artifact_id}.docx
    {artifact_id}.xlsx
    {artifact_id}.pptx
  crewai/assets/          # CrewAI outputs
    reports/
    analysis/
    visualizations/
```

---

## Cloud Services (Render.com)

| Service | Purpose | Cost |
|---------|---------|------|
| **jb-empire-api** | FastAPI backend, 57 route modules | $7/month |
| **empire-celery-worker** | Background task processing | $7/month |
| **jb-empire-chat** | Gradio chat interface | $7/month |
| **jb-crewai** | Multi-agent orchestration | $7/month |

---

## Security Architecture

### Multi-Layer Security

| Layer | Implementation |
|-------|---------------|
| **Transport** | TLS 1.2+ on all services |
| **Authentication** | Clerk auth + JWT tokens |
| **Authorization** | Row-Level Security (RLS) on org-scoped tables |
| **Multi-Tenancy** | Organization-level data isolation |
| **API Auth** | X-API-Key for Telegram bots and integrations |
| **Rate Limiting** | Redis-backed, tiered by endpoint |
| **Encryption** | AES-256 at rest (Supabase, B2) |
| **Audit** | Comprehensive event logging |
| **Input Sanitization** | PostgREST ilike injection protection |

### HTTP Security Headers

- HSTS (Strict-Transport-Security)
- CSP (Content-Security-Policy)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff

---

## Monitoring Stack

| Component | Purpose | Port |
|-----------|---------|------|
| **Prometheus** | Metrics collection | 9090 |
| **Grafana** | Visualization | 3001 |
| **Alertmanager** | Email notifications | 9093 |

### 39 Alert Rules

- **Critical**: Service down, high error rate, extreme latency
- **Warning**: Elevated errors, slow processing, resource usage
- **Info**: System health summaries

---

## Cost Summary

| Category | Monthly Cost |
|----------|--------------|
| Render Services (4) | $28 |
| Supabase PostgreSQL | $25 |
| Backblaze B2 | ~$5 |
| Upstash Redis | Free |
| Neo4j (self-hosted) | $0 |
| **Infrastructure Total** | **~$60** |
| Anthropic API (Sonnet 4.5) | Usage-based (~$0.004/query) |
| Together AI (Kimi K2.5) | Usage-based |
| Google AI (Gemini 3 Flash) | Usage-based |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| AI Reasoning | Kimi K2.5 Thinking (Together AI) |
| AI Prompt/Output | Claude Sonnet 4.5 (Anthropic API) |
| Local Vision | Qwen2.5-VL-32B (Ollama) |
| Local Audio | distil-whisper (faster-whisper) |
| Video Analysis | Gemini 3 Flash (Google AI) |
| Backend | FastAPI (Python 3.11+) |
| Desktop App | Tauri 2.x + React + TypeScript |
| State Management | Zustand |
| Task Queue | Celery |
| Vector DB | PostgreSQL + pgvector |
| Graph DB | Neo4j |
| Cache | Redis (Upstash) |
| Storage | Backblaze B2 |
| Frontend (Web) | Gradio |
| Monitoring | Prometheus + Grafana |
| Testing | pytest + vitest |
| Deployment | Render.com |

---

**Empire v7.5** - Cloud-first architecture with multi-model AI pipeline, desktop app, and multi-tenant data isolation.
