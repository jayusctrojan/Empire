# Empire v7.3 - Production Architecture

**Version:** v7.3.0
**Last Updated:** 2025-12-30
**Status:** ✅ Production Ready

---

## AI Processing Architecture

### Primary AI: Claude Sonnet 4.5 (Anthropic Cloud API)

**All AI reasoning, summarization, classification, and chat responses use Claude Sonnet 4.5 via Anthropic's cloud API.**

```
User Query → FastAPI → Claude Sonnet 4.5 API → Response with Citations
```

### AI Models Used

| Purpose | Model | Provider | Type |
|---------|-------|----------|------|
| **All AI Processing** | Claude Sonnet 4.5 | Anthropic | Cloud API |
| Query Expansion | Claude Haiku | Anthropic | Cloud API |
| Image Analysis | Claude Vision | Anthropic | Cloud API |
| Embeddings | BGE-M3 | Local/Render | 1024-dim vectors |
| Reranking | BGE-Reranker-v2 | Local | Search optimization |

### 15 AI Agents (All Claude Sonnet 4.5)

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

---

## Database Architecture

### Hybrid Database System

Empire uses a hybrid database approach with PostgreSQL for vectors/data and Neo4j for graphs:

| Database | Provider | Purpose | Cost |
|----------|----------|---------|------|
| **PostgreSQL** | Supabase | Vectors, user data, sessions, audit logs | $25/month |
| **Neo4j** | Mac Studio Docker | Knowledge graphs, entity relationships | $0 |
| **Redis** | Upstash | Caching, Celery broker, rate limiting | Free tier |

### Why Both Databases?

- **PostgreSQL (pgvector)**: Fast vector similarity search, ACID transactions, row-level security
- **Neo4j**: Graph traversal, relationship queries, entity connections, graph algorithms

### Data Flow

```
Document Upload
     ↓
[PostgreSQL] Store content, metadata, embeddings
     ↓
[Neo4j] Store entities, relationships, graph connections
     ↓
Query Time: Hybrid search combines both
```

---

## Cloud Services (Render.com)

| Service | Purpose | Cost |
|---------|---------|------|
| **jb-empire-api** | FastAPI backend, 29 route modules (293+ endpoints) | $7/month |
| **empire-celery-worker** | Background task processing | $7/month |
| **jb-empire-chat** | Gradio chat interface | $7/month |
| **jb-crewai** | Multi-agent orchestration | $7/month |

### API Endpoints (29 Route Modules, 293+ Endpoints)

**Document Processing:**
- `POST /api/v1/upload` - Document upload with validation
- `GET /api/status/*` - Processing status

**Chat & Query:**
- `POST /api/query/auto` - Intelligent query routing
- `POST /api/query/adaptive` - LangGraph adaptive workflow
- `POST /api/chat/*` - Chat with file upload
- `WS /ws/*` - WebSocket real-time updates

**AI Agents:**
- `POST /api/summarizer/summarize` - Content summarization
- `POST /api/classifier/classify` - Department classification
- `POST /api/document-analysis/analyze` - Full document analysis
- `POST /api/orchestration/workflow` - Multi-agent orchestration

**Management:**
- `/api/documents/*` - Document management
- `/api/users/*` - User management
- `/api/rbac/*` - Role-based access control
- `/api/monitoring/*` - Analytics dashboard

---

## Storage Architecture

### Backblaze B2 (File Storage)

```
b2://empire-documents/
├── {department}/          # 12 departments
│   ├── {document_id}/
│   │   ├── original.pdf
│   │   ├── processed.txt
│   │   └── metadata.json
├── crewai/assets/         # CrewAI outputs
│   ├── reports/
│   ├── analysis/
│   └── visualizations/
```

### Supabase (Data Storage)

Key tables:
- `documents_v2` - Document metadata and content
- `record_manager_v2` - Vector embeddings (pgvector)
- `knowledge_entities` - Extracted entities
- `chat_sessions` - Chat history
- `audit_logs` - Security audit trail

---

## Security Architecture

### Multi-Layer Security

| Layer | Implementation |
|-------|---------------|
| **Transport** | TLS 1.2+ on all services |
| **Authentication** | Clerk auth + JWT tokens |
| **Authorization** | Row-Level Security (RLS) on 14 tables |
| **Rate Limiting** | Redis-backed, tiered by endpoint |
| **Encryption** | AES-256 at rest (Supabase, B2) |
| **Audit** | Comprehensive event logging |

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
| Anthropic API | Usage-based |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| AI | Claude Sonnet 4.5 (Anthropic API) |
| Backend | FastAPI (Python 3.11+) |
| Task Queue | Celery |
| Vector DB | PostgreSQL + pgvector |
| Graph DB | Neo4j |
| Cache | Redis (Upstash) |
| Storage | Backblaze B2 |
| Frontend | Gradio |
| Monitoring | Prometheus + Grafana |
| Deployment | Render.com |

---

**Empire v7.3** - Cloud-first architecture with Claude Sonnet 4.5 powering all AI capabilities.
