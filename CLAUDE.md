# DO NOT MERGE TO MAIN WITHOUT ASKING JAY FIRST!

**CRITICAL: All PRs must go through CodeRabbit review. NEVER merge PRs to main or push directly to main without explicit approval from Jay. When asking for permission, always say "Can I merge PR #X to main?"**

---

# Empire v7.5

## Overview

Empire is an AI-powered knowledge management platform with:
- **Multi-Model Quality Pipeline**: Sonnet 4.6 (prompt engineer + output architect) → Kimi K2.5 Thinking (reasoning engine)
- **Multi-Tenant Organizations**: Role-based membership (owner/admin/member/viewer), RLS data isolation
- **Tauri Desktop App**: React 18 + TypeScript + Zustand, 32 components
- **Document Generation**: DOCX, XLSX, PPTX, PDF artifacts from AI responses
- **Multimodal RAG**: Local vision (Qwen2.5-VL-32B), audio STT (Whisper), video frames (Gemini 3 Flash)
- **Hybrid Database**: PostgreSQL (Supabase) + Neo4j + Redis
- **58 API Route Modules** (300+ endpoints), **139 service files**

## AI Models

| Purpose | Model | Provider |
|---------|-------|----------|
| Prompt Engineering | Claude Sonnet 4.6 | Anthropic |
| Output Formatting | Claude Sonnet 4.6 | Anthropic |
| Reasoning Engine | Kimi K2.5 Thinking | Together AI |
| Image Analysis | Kimi K2.5 / Gemini 3 Flash | Together AI / Google |
| Audio STT | distil-whisper/distil-large-v3.5 | Local (faster-whisper) |
| Video Frames | Gemini 3 Flash | Google AI |
| Embeddings | BGE-M3 (1024-dim) | Local |

## Development Guidelines

- All database migrations go in `migrations/` directory
- Use idempotent SQL with `IF NOT EXISTS` / `CREATE OR REPLACE`
- Run CI/CD checks before merging
- Follow CodeRabbit review feedback
- Backend tests: `pytest` (170+ test files)
- Frontend tests: `npx vitest run` in `empire-desktop/` (44 tests)
- Type checking: `npx tsc --noEmit` in `empire-desktop/`

## Key Directories

- `app/` - FastAPI backend (Python 3.11+)
- `app/routes/` - 58 API route modules (300+ endpoints)
- `app/services/` - 139 service files (business logic, LLM clients, pipeline)
- `app/core/` - Database clients, config
- `app/middleware/` - Auth, rate limiting, org context
- `empire-desktop/` - Tauri 2.x desktop app (React + TypeScript)
- `empire-desktop/src/components/` - 32 React components
- `empire-desktop/src/stores/` - Zustand state management
- `empire-desktop/src/lib/api/` - Backend API client (with X-Org-Id header)
- `migrations/` - SQL migration files
- `tests/` - Backend test files (pytest)
- `docs/` - Architecture docs, onboarding guides
- `notebooklm/` - NotebookLM source documentation

## Key Services

- `app/services/llm_client.py` - Unified LLM provider abstraction (TogetherAI, Anthropic, Gemini, OpenAI-compatible)
- `app/services/prompt_engineer_service.py` - Sonnet 4.6 prompt enrichment (Stage 1)
- `app/services/output_architect_service.py` - Sonnet 4.6 output formatting (Stage 3)
- `app/services/studio_cko_conversation_service.py` - CKO pipeline orchestration
- `app/services/document_generator_service.py` - DOCX/XLSX/PPTX/PDF generation
- `app/services/vision_service.py` - Multi-provider image analysis
- `app/services/whisper_stt_service.py` - Local audio transcription
- `app/services/organization_service.py` - Multi-tenant org management
- `app/services/cost_tracking_service.py` - Per-query cost tracking

## Key Routes

- `app/routes/studio_cko.py` - CKO chat with multi-model pipeline + SSE streaming
- `app/routes/organizations.py` - Org CRUD + membership management
- `app/routes/unified_search.py` - Cross-type search (chats, projects, KB, artifacts)
- `app/routes/artifacts.py` - Artifact download/metadata
- `app/routes/studio_assets.py` - Asset CRUD, publish/archive lifecycle, test sandbox SSE

## Infrastructure

| Service | Platform | Cost |
|---------|----------|------|
| FastAPI Backend | Render | $7/month |
| Celery Workers | Render | $7/month |
| Gradio Chat UI | Render | $7/month |
| CrewAI Service | Render | $7/month |
| PostgreSQL | Supabase | $25/month |
| Redis | Upstash | Free |
| File Storage | Backblaze B2 | ~$5/month |
