# Empire v7.5 - Features & Capabilities

**Version:** v7.5.0
**Last Updated:** 2026-02-19
**Status:** Production Deployed & Verified

---

## Core Features

### 1. Multi-Model Quality Pipeline

Every query flows through a **3-stage AI pipeline** that bookends reasoning with formatting:

```
User Query
     |
     v
[PROMPT ENGINEER - Sonnet 4.5]     ~1-2s
  Intent detection, format detection, enriched query
     |
     v
[Query Expansion - Kimi K2.5] -> [RAG Search] -> [BGE-Reranker-v2]
     |
     v
[REASONING ENGINE - Kimi K2.5 Thinking]   ~3-8s
  Deep reasoning with citations [1], [2]
     |
     v
[OUTPUT ARCHITECT - Sonnet 4.5]    ~2-3s
  Formatting, artifact detection, streaming
     |
     v (if artifact detected)
[Document Generator -> B2 Storage -> Artifact card in chat]
```

**Streaming UX**: Users see phase indicators ("Analyzing...", "Searching...", "Thinking...", "Formatting..."), then the formatted response streams token-by-token.

**Graceful degradation**: If either Sonnet 4.5 call fails, falls back to raw query -> Kimi -> raw response.

**Per-query pipeline cost**: ~$0.0045 for both Sonnet 4.5 calls combined.

### 2. Multi-Tenant Organization Layer

- **Organization model**: Multi-tenant SaaS with proper tenant isolation
- **Org Picker**: First screen after login for multi-org users
- **Org Switcher**: Dropdown in sidebar header for quick org changes
- **Role-based membership**: Owner, Admin, Member, Viewer
- **Row-Level Security**: All data scoped to user's current organization
- **Org-scoped data**: Projects, chats, KB documents, artifacts all isolated per org

### 3. Intelligent Chat Interface (CKO)

- Natural language queries with multi-model pipeline
- Real-time streaming with phase indicators
- Source attribution with inline citations [1], [2]
- File/image/audio/video upload in chat
- Conversation memory and context
- Quality weight presets (Speed / Balanced / Quality)

### 4. Document Generation & Artifacts

AI-generated documents from chat responses:

| Format | Library | Use Case |
|--------|---------|----------|
| **DOCX** | python-docx | Reports, memos, analysis documents |
| **XLSX** | openpyxl | Spreadsheets, data tables, budgets |
| **PPTX** | python-pptx | Presentations, slide decks |
| **PDF** | PDFReportGenerator | Formal reports with formatting |

- **ArtifactCard**: Inline card in chat with file type icon, title, format badge, size
- **ArtifactPanel**: Slide-out side panel with rendered markdown preview
- **Download**: Save to disk via Tauri save dialog
- **Storage**: Uploaded to Backblaze B2 (`artifacts/documents/` folder)

### 5. Unified Search

Search across all content types within the user's organization:

| Type | Table | Fields Searched |
|------|-------|----------------|
| **Chats** | studio_cko_sessions | title, context_summary |
| **Projects** | projects | name, description |
| **Knowledge Base** | documents | filename, department |
| **Artifacts** | studio_cko_artifacts | title, summary |

- **Cmd+K** keyboard shortcut opens search modal
- **Parallel search**: `asyncio.gather()` across all types simultaneously
- **Filter tabs**: All, Chats, Projects, Knowledge Base, Artifacts
- **Relevance scoring**: Title matches score higher than description/summary matches
- **Endpoint**: `GET /api/search/unified?q=...&types=chat,project,kb,artifact`

### 6. Multimodal Processing

**Image Analysis** (3-tier fallback):
```
Image -> Qwen2.5-VL-32B (local, Ollama, zero cost)
           |  (fallback)
         Kimi K2.5 Thinking (Together AI)
           |  (fallback)
         Gemini 3 Flash (Google AI)
```

**Audio Processing**:
```
Audio file (mp3/wav/m4a/etc.)
     |
     v
distil-whisper/distil-large-v3.5 (local, faster-whisper, 2x realtime)
     |
     v
Transcript text -> RAG pipeline
```

**Video Processing**:
```
Video file -> ffmpeg frame extraction -> Gemini 3 Flash analysis -> Summary
```

### 7. Source Attribution

Every AI response includes:
- Inline citations [1], [2], [3]
- Source document and page numbers
- Citation popovers in desktop app
- Confidence scores

### 8. Multi-Agent Orchestration

15+ specialized AI agents coordinate for complex tasks:
- Research -> Analysis -> Writing -> Review pipeline
- Automatic revision loops for quality
- Parallel processing for efficiency
- Document analysis pipeline (AGENT-009 -> 010 -> 011)

### 9. Tauri Desktop Application

| Layer | Technology |
|-------|------------|
| **Framework** | Tauri 2.x (Rust backend) |
| **UI** | React 18 + TypeScript |
| **State** | Zustand (with persist middleware) |
| **Styling** | Tailwind CSS (Empire dark theme) |
| **Testing** | Vitest + @testing-library/react (22 tests) |
| **Build** | Vite |

Key components: ChatView, GlobalSearch, OrgPicker, OrgSwitcher, Sidebar, MessageBubble, ArtifactCard, ArtifactPanel, PhaseIndicator

---

## Document Processing Features

### Supported File Types

| Category | Formats |
|----------|---------|
| Documents | PDF, DOCX, DOC, TXT, MD, RTF |
| Spreadsheets | XLSX, XLS, CSV |
| Presentations | PPTX, PPT |
| Images | PNG, JPG, JPEG, GIF, WEBP |
| Audio | MP3, WAV, M4A, OGG, FLAC |
| Video | MP4, MOV, AVI, MKV |
| Web | HTML, XML, JSON |
| Code | PY, JS, TS, JAVA, CPP, etc. |

### Book Processing

- Automatic chapter detection (>90% accuracy)
- Per-chapter knowledge base entries
- Book-wide OR chapter-specific queries
- Table of contents extraction

### URL/Link Support

- YouTube video transcription (via yt-dlp)
- Web article extraction (via BeautifulSoup)
- Automatic content type detection
- Metadata extraction

---

## Search & Retrieval

### Hybrid Search System

Combines multiple search methods:

1. **Vector Similarity** - Semantic understanding via BGE-M3 embeddings (1024-dim)
2. **Full-Text Search** - Keyword matching with ranking
3. **Graph Traversal** - Entity relationship discovery (Neo4j)
4. **Reranking** - BGE-Reranker-v2 for precision

### Query Expansion

Kimi K2.5 generates query variations:
- Original: "insurance requirements"
- Expanded: "insurance policy requirements", "coverage mandates", "regulatory compliance insurance"
- Result: 15-30% better recall

### CKO Weights System

Three quality presets for the reasoning engine:

| Preset | Thinking Tokens | Use Case |
|--------|----------------|----------|
| **Speed** | 1,024 | Quick answers, simple lookups |
| **Balanced** | 4,096 | General queries (default) |
| **Quality** | 16,384 | Deep analysis, complex reasoning |

---

## Security Features

### Authentication & Authorization

- Clerk authentication integration
- JWT token validation
- Role-Based Access Control (RBAC)
- Multi-tenant organization isolation
- Row-Level Security on org-scoped tables

### Rate Limiting

Tiered limits by endpoint:
- `/api/query/*`: 100 requests/minute
- `/api/documents/upload`: 20 requests/minute
- `/api/crewai/*`: 50 requests/minute
- Default: 200 requests/minute

### Encryption

- TLS 1.2+ in transit (all services)
- AES-256 at rest (Supabase, B2)
- Application-level encryption for sensitive fields

### Input Sanitization

- PostgREST ilike injection protection
- SQL wildcard escaping (`%`, `_`)
- Comma and quote stripping for OR-condition safety

### HTTP Security Headers

- HSTS (Strict-Transport-Security)
- CSP (Content-Security-Policy)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff

---

## Monitoring & Observability

### Metrics Collection

- Prometheus metrics on all services
- Custom business metrics
- Per-query cost tracking across models

### Visualization

- Grafana dashboards
- Real-time charts
- Historical analysis

### Alerting

39 alert rules across:
- **Critical**: Service down, high errors
- **Warning**: Performance degradation
- **Info**: System health summaries

Email notifications via Alertmanager.

---

## 12 Business Departments

Content is automatically classified into one of 12 departments:

1. **IT & Engineering** - Software, APIs, DevOps, cloud infrastructure
2. **Sales & Marketing** - CRM, campaigns, leads, revenue growth
3. **Customer Support** - Help desk, tickets, SLA, satisfaction
4. **Operations & HR & Supply Chain** - Logistics, hiring, procurement
5. **Finance & Accounting** - Budgets, auditing, tax, compliance
6. **Project Management** - Agile/Scrum, milestones, resource allocation
7. **Real Estate** - Property, leases, mortgages, tenant relations
8. **Private Equity & M&A** - Investments, acquisitions, due diligence
9. **Consulting** - Strategy, advisory, frameworks, transformation
10. **Personal & Continuing Education** - Training, courses, certifications
11. **Research & Development (R&D)** - Innovation, prototyping, patents
12. **Global** - Cross-department content applicable to multiple areas

---

## API Capabilities

### 57 Route Modules (300+ Endpoints)

**Core Pipeline:**
- CKO chat with multi-model pipeline
- Unified search across all content types
- Artifact CRUD and download

**Document Management:**
- Upload, retrieve, update, delete documents
- Bulk operations
- Status tracking

**Organizations:**
- Create, list, update organizations
- Add/remove members with roles
- Org-scoped data isolation

**AI Agents:**
- Summarization
- Classification
- Analysis
- Orchestration

**Administration:**
- User management
- RBAC configuration
- Audit logs
- Feature flags

### Streaming (SSE)

- Server-Sent Events for real-time chat streaming
- Phase indicators during pipeline processing
- Artifact events when documents are generated
- Token-by-token Output Architect streaming

---

## Performance Metrics

| Metric | Target | Achieved |
|--------|--------|----------|
| Pipeline Response (end-to-end) | <15 seconds | ~6-13s |
| Prompt Engineer Stage | <2 seconds | ~1-2s |
| Reasoning Stage | <8 seconds | ~3-8s |
| Output Architect Stage | <3 seconds | ~2-3s |
| Source Attribution Accuracy | >95% | Yes |
| Agent Routing Accuracy | >90% | Yes |
| Uptime | >99.5% | Yes |

---

## What Changed: v7.3 to v7.5

| Feature | v7.3 | v7.5 |
|---------|------|------|
| **Primary AI** | Claude Sonnet 4.5 only | Multi-model pipeline: Sonnet 4.5 (prompt/output) + Kimi K2.5 Thinking (reasoning) |
| **Frontend** | Gradio chat UI | Tauri Desktop App (React/TypeScript) + Gradio |
| **Vision** | Claude Vision (cloud) | Qwen2.5-VL-32B (local) + Kimi K2.5 + Gemini 3 Flash fallback |
| **Audio** | None | Local distil-whisper via faster-whisper |
| **Tenancy** | Single-user | Multi-tenant with organizations, memberships, roles |
| **Document Gen** | None | DOCX, XLSX, PPTX, PDF generation from AI responses |
| **Artifacts** | None | Inline preview cards, side panel, download in desktop app |
| **Search** | Per-type only | Unified search across chats, projects, KB, artifacts |
| **Testing** | Backend only | Backend (170+ tests) + Frontend vitest (22 tests) |
| **Route Modules** | 29 | 57 |

---

**Empire v7.5** - Multi-model AI pipeline with organization tenancy, desktop app, artifact generation, multimodal processing, and unified search.
