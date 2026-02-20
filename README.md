# Empire v7.5 - AI-Powered Knowledge Management Platform

**Version:** v7.5.0
**Last Updated:** 2026-02-19
**Status:** Production Deployed

---

## Overview

Empire is a production-ready AI-powered knowledge management platform featuring a **multi-model quality pipeline**, **multi-tenant organization layer**, **Tauri desktop application**, **document generation**, and **multimodal RAG processing**.

### Key Capabilities

- **Multi-Model AI Pipeline**: Sonnet 4.5 bookend processing + Kimi K2.5 Thinking reasoning engine
- **Document Generation**: DOCX, XLSX, PPTX, PDF artifacts from AI responses
- **Multimodal RAG**: Local vision (Qwen2.5-VL-32B), audio STT (Whisper), video frame analysis
- **Multi-Tenant Organizations**: Role-based membership and data isolation
- **Tauri Desktop App**: TypeScript/React with artifact preview, org picker, unified search
- **Unified Search**: Cmd+K search across chats, projects, KB, and artifacts
- **15+ Specialized AI Agents**: Document processing, analysis, and orchestration
- **57 API Route Modules**: 300+ endpoints
- **Hybrid Database**: PostgreSQL (Supabase) + Neo4j + Redis

---

## Architecture

### Multi-Model Quality Pipeline

Every query flows through a 3-stage pipeline:

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

### AI Models

| Purpose | Model | Provider |
|---------|-------|----------|
| Prompt Engineering | Claude Sonnet 4.5 | Anthropic |
| Output Formatting | Claude Sonnet 4.5 | Anthropic |
| Reasoning Engine | Kimi K2.5 Thinking | Together AI |
| Query Expansion | Kimi K2.5 | Together AI |
| Image Analysis | Kimi K2.5 / Gemini 3 Flash | Together AI / Google |
| Local Vision | Qwen2.5-VL-32B | Ollama (Mac Studio) |
| Audio STT | distil-whisper/distil-large-v3.5 | faster-whisper (local) |
| Video Frames | Gemini 3 Flash | Google AI |
| Embeddings | BGE-M3 | Local (1024-dim) |
| Reranking | BGE-Reranker-v2 | Local |

### Technology Stack

| Layer | Technology |
|-------|------------|
| AI Reasoning | Kimi K2.5 Thinking (Together AI) |
| AI Prompt/Output | Claude Sonnet 4.5 (Anthropic) |
| Backend | FastAPI (Python 3.11+) |
| Desktop App | Tauri 2.x + React + TypeScript |
| State Management | Zustand |
| Task Queue | Celery |
| Vector DB | PostgreSQL + pgvector (Supabase) |
| Graph DB | Neo4j (Mac Studio Docker) |
| Cache/Broker | Redis (Upstash) |
| Storage | Backblaze B2 |
| Monitoring | Prometheus + Grafana + Alertmanager |
| Testing | pytest (backend) + vitest (frontend) |
| Deployment | Render.com |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Rust (for Tauri desktop app)
- Docker (for Neo4j)

### Backend

```bash
git clone https://github.com/jayusctrojan/Empire.git
cd Empire
cp .env.example .env  # Configure API keys
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
docker-compose up -d neo4j
uvicorn app.main:app --reload --port 8000
```

### Desktop App

```bash
cd empire-desktop
npm install
npm run tauri dev
```

### Verify

```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "7.5.0"}
```

---

## Project Structure

```
Empire/
├── app/                          # FastAPI backend
│   ├── routes/                   # 57 API route modules
│   ├── services/                 # 139 service files
│   ├── core/                     # Database, config
│   ├── middleware/                # Auth, rate limiting, org context
│   └── main.py                   # FastAPI entry point
├── empire-desktop/               # Tauri desktop application
│   ├── src/components/           # 31 React components
│   ├── src/stores/               # Zustand state management
│   ├── src/lib/api/              # Backend API client
│   └── src-tauri/                # Rust backend
├── tests/                        # 170+ backend test files
├── migrations/                   # SQL migrations
├── docs/                         # Documentation
├── notebooklm/                   # NotebookLM source docs
└── config/monitoring/            # Prometheus/Grafana
```

---

## Cloud Services (Production)

| Service | Platform | Cost |
|---------|----------|------|
| FastAPI Backend | Render | $7/month |
| Celery Workers | Render | $7/month |
| Gradio Chat UI | Render | $7/month |
| CrewAI Service | Render | $7/month |
| PostgreSQL | Supabase | $25/month |
| Redis | Upstash | Free |
| File Storage | Backblaze B2 | ~$5/month |
| **Infrastructure Total** | | **~$60/month** |
| Anthropic API | Anthropic | Usage-based |
| Together AI | Together | Usage-based |
| Google AI | Google | Usage-based |

---

## Documentation

| Document | Location |
|----------|----------|
| Architecture | `notebooklm/ARCHITECTURE.md` |
| Features | `notebooklm/FEATURES.md` |
| AI Models & Agents | `notebooklm/AI_AGENTS.md` |
| Developer Guide | `docs/onboarding/DEVELOPER_GUIDE.md` |
| End User Guide | `docs/onboarding/END_USER_GUIDE.md` |
| API Reference | `docs/API_REFERENCE.md` |

---

## Testing

```bash
# Backend
pytest                           # All tests
pytest tests/test_unified_search.py -v  # Specific file

# Frontend
cd empire-desktop
npx vitest run                   # All frontend tests
npx tsc --noEmit                 # Type checking
```

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and add tests
3. Run tests: `pytest` and `npx vitest run`
4. Push and create PR: `gh pr create`
5. Address CodeRabbit review feedback
6. Get approval from Jay before merging to main

---

*Empire v7.5 - Multi-model AI pipeline with organization tenancy, desktop app, artifact generation, and unified search.*
