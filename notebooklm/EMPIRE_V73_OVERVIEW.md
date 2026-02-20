# Empire v7.5 - AI-Powered Knowledge Management Platform

**Version:** v7.5.0
**Last Updated:** 2026-02-19
**Status:** Production Deployed & Verified

---

## Executive Summary

Empire v7.5 is a production-ready AI-powered knowledge management platform featuring:

- **Multi-Model Quality Pipeline** with Sonnet 4.5 bookend processing + Kimi K2.5 Thinking reasoning engine
- **Multi-Tenant Organization Layer** with role-based membership and data isolation
- **Tauri Desktop Application** (TypeScript/React) with artifact preview, org picker, and unified search
- **Document Generation** producing DOCX, XLSX, PPTX, and PDF artifacts from AI responses
- **Multimodal RAG** with local vision (Qwen2.5-VL-32B), audio STT (Whisper), and video frame analysis
- **Unified Search** across chats, projects, knowledge base, and artifacts with filter tabs
- **15+ Specialized AI Agents** for document processing, analysis, and orchestration
- **Hybrid Database Architecture** (PostgreSQL + Neo4j)
- **57 API Route Modules** with 300+ endpoints

---

## What Changed: v7.3 to v7.5

| Feature | v7.3 | v7.5 |
|---------|------|------|
| **Primary AI** | Claude Sonnet 4.5 only | Multi-model pipeline: Sonnet 4.5 (prompt/output) + Kimi K2.5 Thinking (reasoning) |
| **Frontend** | Gradio chat UI | Tauri Desktop App (React/TypeScript) + Gradio |
| **Vision** | Claude Vision (cloud) | Qwen2.5-VL-32B (local via Ollama) + Kimi K2.5 + Gemini 3 Flash fallback |
| **Audio** | None | Local distil-whisper/distil-large-v3.5 via faster-whisper |
| **Tenancy** | Single-user | Multi-tenant with organizations, memberships, roles |
| **Document Gen** | None | DOCX, XLSX, PPTX, PDF generation from AI responses |
| **Artifacts** | None | Inline preview cards, side panel, download in desktop app |
| **Search** | Per-type only | Unified search across chats, projects, KB, artifacts |
| **Testing** | Backend only | Backend (170+ tests) + Frontend vitest (22 tests) |
| **Route Modules** | 29 | 57 |

---

## Core AI Architecture

### Multi-Model Quality Pipeline

Every query flows through a 3-stage pipeline:

```
User Query
  |
  v
[PROMPT ENGINEER - Sonnet 4.5]  ~1-2s
  Intent detection, output format detection, enriched query
  |
  v
[Query Expansion - Kimi K2.5] -> RAG Search -> Reranking
  |
  v
[REASONING ENGINE - Kimi K2.5 Thinking]  ~3-8s
  Deep reasoning with citations [1], [2]
  |
  v
[OUTPUT ARCHITECT - Sonnet 4.5]  ~2-3s
  Formats, structures, detects artifacts, streams to user
  |
  v (if artifact detected)
Document Generator -> B2 Storage -> Artifact card in chat
```

**Streaming UX**: User sees phase indicators ("Analyzing...", "Searching...", "Thinking...", "Formatting..."), then the Output Architect's formatted response streams token-by-token.

**Graceful degradation**: If either Sonnet call fails, falls back to raw query -> Kimi -> raw response.

### AI Models Used

| Purpose | Model | Provider | Type |
|---------|-------|----------|------|
| **Prompt Engineering** | Claude Sonnet 4.5 | Anthropic | Cloud API |
| **Output Formatting** | Claude Sonnet 4.5 | Anthropic | Cloud API |
| **Reasoning Engine** | Kimi K2.5 Thinking | Together AI | Cloud API |
| **Query Expansion** | Kimi K2.5 | Together AI | Cloud API |
| **Image Analysis** | Kimi K2.5 Thinking (primary) | Together AI | Cloud API |
| **Image Fallback** | Gemini 3 Flash | Google AI | Cloud API |
| **Local Vision** | Qwen2.5-VL-32B | Ollama (local) | Local inference |
| **Audio STT** | distil-whisper/distil-large-v3.5 | faster-whisper (local) | Local inference |
| **Video Frames** | Gemini 3 Flash | Google AI | Cloud API |
| **Embeddings** | BGE-M3 | Local/Render | 1024-dim vectors |
| **Reranking** | BGE-Reranker-v2 | Local | Search optimization |

### LLM Client Abstraction

All model providers use a unified `LLMClient` interface (`app/services/llm_client.py`):

```python
class LLMClient(ABC):
    async def generate(prompt, system_prompt, ...) -> str
    async def generate_with_images(prompt, images, ...) -> str
    def is_retryable(error) -> bool

# Implementations:
class TogetherAILLMClient(LLMClient)     # Kimi K2.5 Thinking
class AnthropicLLMClient(LLMClient)       # Claude Sonnet 4.5
class GeminiLLMClient(LLMClient)          # Gemini 3 Flash
class OpenAICompatibleClient(LLMClient)   # Ollama/Qwen2.5-VL
```

---

## Organization Layer (Multi-Tenant)

### Data Model

```
Organization (company)
  |-- org_memberships (user <-> org, with roles: owner/admin/member/viewer)
  |-- projects (scoped to org)
  |-- studio_cko_sessions (chats, scoped to org)
  |-- documents (KB, scoped to org)
  |-- studio_cko_artifacts (scoped to org)
```

### Features

- **Org Picker**: First screen after login for multi-org users
- **Org Switcher**: Dropdown in sidebar header to switch between orgs
- **Row-Level Security**: All data scoped to user's current organization
- **Role-Based Membership**: Owner, Admin, Member, Viewer roles

---

## Unified Search

### `GET /api/search/unified`

Searches across all content types within the user's organization:

| Type | Table | Fields Searched |
|------|-------|----------------|
| **chat** | studio_cko_sessions | title, context_summary |
| **project** | projects | name, description |
| **kb** | documents | filename, department |
| **artifact** | studio_cko_artifacts | title, summary |

- **Parallel search**: `asyncio.gather()` across all types simultaneously
- **Relevance scoring**: Title matches score higher than description/summary matches
- **Filter tabs**: All, Chats, Projects, Knowledge Base, Artifacts
- **Cmd+K** keyboard shortcut in desktop app

---

## Document Generation & Artifact System

### Supported Formats

| Format | Library | Use Case |
|--------|---------|----------|
| **DOCX** | python-docx | Reports, memos, analysis documents |
| **XLSX** | openpyxl | Spreadsheets, data tables, budgets |
| **PPTX** | python-pptx | Presentations, slide decks |
| **PDF** | PDFReportGenerator (custom) | Formal reports with formatting |

### Desktop UI

- **ArtifactCard**: Inline card in chat with file type icon, title, format badge, size
- **ArtifactPanel**: Slide-out right panel with rendered markdown preview
- **PhaseIndicator**: Animated pulsing dot showing pipeline phase during processing
- **Download**: Save to disk via Tauri save dialog

---

## Tauri Desktop Application

### Stack

| Layer | Technology |
|-------|------------|
| **Framework** | Tauri 2.x (Rust backend) |
| **UI** | React 18 + TypeScript |
| **State** | Zustand (with persist middleware) |
| **Styling** | Tailwind CSS (Empire dark theme) |
| **Testing** | Vitest + @testing-library/react (22 tests) |
| **Build** | Vite |

### Key Components

| Component | Purpose |
|-----------|---------|
| `ChatView.tsx` | Main chat interface with streaming + artifact panel |
| `GlobalSearch.tsx` | Cmd+K unified search modal with filter tabs |
| `OrgPicker.tsx` | Organization selection on launch |
| `OrgSwitcher.tsx` | Org switching dropdown in sidebar |
| `Sidebar.tsx` | Conversation list, navigation |
| `MessageBubble.tsx` | Chat messages with citation popovers |
| `ArtifactCard.tsx` | Inline artifact preview in chat |
| `ArtifactPanel.tsx` | Side panel artifact viewer |
| `PhaseIndicator.tsx` | Pipeline phase indicator |

---

## Multimodal Capabilities

### Image Analysis

```
Image -> Qwen2.5-VL-32B (local, via Ollama)
           |  (fallback if Ollama unavailable)
         Kimi K2.5 Thinking (Together AI)
           |  (fallback)
         Gemini 3 Flash (Google AI)
```

### Audio/Video Processing

```
Audio file -> distil-whisper (local, faster-whisper) -> Transcript -> RAG pipeline
Video file -> ffmpeg frame extraction -> Gemini 3 Flash analysis -> Summary
```

---

## Database Architecture

### Hybrid Database System

| Database | Provider | Purpose | Cost |
|----------|----------|---------|------|
| **PostgreSQL** | Supabase | Vectors, user data, sessions, orgs, artifacts | $25/month |
| **Neo4j** | Mac Studio Docker | Knowledge graphs, entity relationships | $0 |
| **Redis** | Upstash | Caching, Celery broker, rate limiting | Free tier |

### Key Tables (v7.5 additions)

| Table | Purpose |
|-------|---------|
| `organizations` | Company/org entities with slug, logo, settings |
| `org_memberships` | User-org relationships with roles |
| `studio_cko_artifacts` | Generated document artifacts |

---

## Cloud Services (Production)

| Service | Platform | Purpose | Cost |
|---------|----------|---------|------|
| FastAPI Backend | Render | Main API service | $7/month |
| Celery Workers | Render | Background task processing | $7/month |
| Chat UI | Render | Gradio-based interface | $7/month |
| CrewAI Service | Render | Multi-agent workflows | $7/month |
| PostgreSQL | Supabase | Primary database | $25/month |
| Redis | Upstash | Caching & message broker | Free |
| File Storage | Backblaze B2 | Document + artifact storage | ~$5/month |
| Anthropic API | Anthropic | Sonnet 4.5 (prompt/output) | Usage-based |
| Together AI | Together | Kimi K2.5 Thinking (reasoning) | Usage-based |
| Google AI | Google | Gemini 3 Flash (vision fallback) | Usage-based |

**Infrastructure: ~$60/month** (excluding AI API usage)
**Per-query pipeline cost: ~$0.0045** (both Sonnet calls combined)

---

## Testing

| Layer | Framework | Count |
|-------|-----------|-------|
| Backend | pytest | 170+ test files |
| Frontend | vitest + testing-library | 22 tests across 3 files |
| Code Review | CodeRabbit | Automated on every PR |

---

## Technology Stack Summary

| Layer | Technology |
|-------|------------|
| **AI Reasoning** | Kimi K2.5 Thinking (Together AI) |
| **AI Prompt/Output** | Claude Sonnet 4.5 (Anthropic API) |
| **Local Vision** | Qwen2.5-VL-32B (Ollama) |
| **Local Audio** | distil-whisper (faster-whisper) |
| **Video Analysis** | Gemini 3 Flash (Google AI) |
| **Backend** | FastAPI (Python 3.11+) |
| **Desktop App** | Tauri 2.x + React + TypeScript |
| **State Management** | Zustand |
| **Task Queue** | Celery |
| **Vector DB** | PostgreSQL + pgvector (Supabase) |
| **Graph DB** | Neo4j |
| **Cache/Broker** | Redis (Upstash) |
| **Storage** | Backblaze B2 |
| **Monitoring** | Prometheus + Grafana + Alertmanager |
| **Testing** | pytest (backend) + vitest (frontend) |
| **Deployment** | Render.com |

---

**Empire v7.5** - Multi-model AI pipeline with organization tenancy, desktop app, artifact generation, and unified search.
