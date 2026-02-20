# Empire v7.5 - AI Agent & Model System

**Version:** v7.5.0
**Last Updated:** 2026-02-19
**AI Models:** Multi-model pipeline (Sonnet 4.5, Kimi K2.5, Gemini 3 Flash, Qwen2.5-VL, Whisper)

---

## Overview

Empire v7.5 features a **multi-model AI system** that combines multiple providers for different tasks. The core innovation is a **3-stage quality pipeline** that bookends every query with Claude Sonnet 4.5 for prompt engineering and output formatting, while using Kimi K2.5 Thinking for deep reasoning.

---

## Multi-Model Quality Pipeline

### The Pipeline

```
User Query
     |
     v
[STAGE 1: PROMPT ENGINEER - Sonnet 4.5]
  - Intent detection (factual/analytical/creative/document)
  - Output format detection (text/table/report/spreadsheet)
  - Enriched, structured query with instructions
     |
     v
[Query Expansion - Kimi K2.5] -> [RAG Search] -> [Reranking]
     |
     v
[STAGE 2: REASONING ENGINE - Kimi K2.5 Thinking]
  - Deep reasoning with think tokens
  - Citations [1], [2] from retrieved sources
  - Raw response (NOT streamed to user)
     |
     v
[STAGE 3: OUTPUT ARCHITECT - Sonnet 4.5]
  - Formats and structures the response
  - Detects if artifact is needed (DOCX/XLSX/PPTX/PDF)
  - Streams formatted output to user
     |
     v (if artifact detected)
[Document Generator -> B2 Storage -> Artifact card in chat]
```

### Pipeline Services

| Service | File | Model | Purpose |
|---------|------|-------|---------|
| Prompt Engineer | `prompt_engineer_service.py` | Sonnet 4.5 | Query enrichment, intent/format detection |
| Output Architect | `output_architect_service.py` | Sonnet 4.5 | Response formatting, artifact detection |
| CKO Conversation | `studio_cko_conversation_service.py` | Kimi K2.5 Thinking | Reasoning engine orchestration |
| Document Generator | `document_generator_service.py` | N/A (libraries) | DOCX/XLSX/PPTX/PDF file creation |

### Streaming UX

Users see phase indicators during processing:
1. "Analyzing..." (Prompt Engineer running)
2. "Searching..." (Query expansion + RAG search)
3. "Thinking..." (Kimi K2.5 reasoning)
4. "Formatting..." (Output Architect formatting)
5. Token-by-token streaming of formatted response

---

## LLM Client Abstraction

All model providers implement a unified interface (`app/services/llm_client.py`):

```python
class LLMClient(ABC):
    async def generate(prompt, system_prompt, ...) -> str
    async def generate_with_images(prompt, images, ...) -> str
    def is_retryable(error) -> bool
```

### Provider Implementations

| Client Class | Provider | Models | Features |
|-------------|----------|--------|----------|
| `TogetherAILLMClient` | Together AI | Kimi K2.5 Thinking | Reasoning, query expansion |
| `AnthropicLLMClient` | Anthropic | Claude Sonnet 4.5 | Prompt/output, JSON mode |
| `GeminiLLMClient` | Google AI | Gemini 3 Flash | Vision fallback, video frames |
| `OpenAICompatibleClient` | Ollama (local) | Qwen2.5-VL-32B | Local vision processing |

### Key Design Decisions

- **DRY base class**: `OpenAICompatibleClient` provides shared logic for any OpenAI-compatible API
- **Automatic retry**: `is_retryable()` method on each client for transient error handling
- **Fallback chains**: Vision uses Qwen -> Kimi -> Gemini cascade

---

## Multimodal Processing

### Image Analysis Pipeline

```
Image uploaded
     |
     v
[Qwen2.5-VL-32B via Ollama]  (local, zero cost)
     |  (fallback if Ollama unavailable)
     v
[Kimi K2.5 Thinking via Together AI]  (primary cloud)
     |  (fallback)
     v
[Gemini 3 Flash via Google AI]  (secondary cloud)
```

Service: `app/services/vision_service.py`

### Audio Processing

```
Audio file (mp3/wav/m4a/etc.)
     |
     v
[distil-whisper/distil-large-v3.5 via faster-whisper]  (local, 2x realtime)
     |
     v
Transcript text -> RAG pipeline
```

Service: `app/services/whisper_stt_service.py`

### Video Processing

```
Video file
     |
     v
[ffmpeg frame extraction at key intervals]
     |
     v
[Gemini 3 Flash - frame-by-frame analysis]
     |
     v
Summary + key findings
```

Service: `app/services/audio_video_processor.py`

---

## Legacy Agent Registry

### Content Processing Agents

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-002** | Content Summarizer | Generates PDF summaries with key points |
| **AGENT-008** | Department Classifier | Classifies content into 12 business departments |

### Document Analysis Agents

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-009** | Senior Research Analyst | Extracts topics, entities, facts |
| **AGENT-010** | Content Strategist | Generates executive summaries |
| **AGENT-011** | Fact Checker | Verifies claims with citations |

### Multi-Agent Orchestration

| Agent ID | Name | Purpose |
|----------|------|---------|
| **AGENT-012** | Research Agent | Web/academic search, query expansion |
| **AGENT-013** | Analysis Agent | Pattern detection, statistical analysis |
| **AGENT-014** | Writing Agent | Report generation, multi-format output |
| **AGENT-015** | Review Agent | Quality assurance, revision loops |

### Agent Workflows

**Document Analysis Pipeline:**
```
Document -> AGENT-009 (Research) -> AGENT-010 (Strategy) -> AGENT-011 (Fact-Check) -> Result
```

**Multi-Agent Orchestration:**
```
Task -> AGENT-012 (Research) -> AGENT-013 (Analysis) -> AGENT-014 (Writing) -> AGENT-015 (Review)
                                                                                 |
                                                                          [Revision Loop]
```

---

## Document Generation

### Format Support

| Format | Library | Generated From |
|--------|---------|---------------|
| DOCX | python-docx | Headings, paragraphs, tables, code blocks, lists |
| XLSX | openpyxl | Table blocks, header formatting, auto-column-width |
| PPTX | python-pptx | Title slide, heading slides, content bullets, tables |
| PDF | PDFReportGenerator | Full formatted reports |

Service: `app/services/document_generator_service.py`

### Artifact Lifecycle

1. Output Architect identifies artifact-worthy content and format
2. Document Generator creates the file from structured content blocks
3. File uploaded to B2 (`artifacts/documents/` folder)
4. Metadata saved to `studio_cko_artifacts` table
5. SSE event `{"type": "artifact", ...}` sent to desktop app
6. Desktop shows inline ArtifactCard with preview/download

---

## CKO Weights System

Three quality presets for the reasoning engine:

| Preset | Thinking Tokens | Use Case |
|--------|----------------|----------|
| **Speed** | 1,024 | Quick answers, simple lookups |
| **Balanced** | 4,096 | General queries (default) |
| **Quality** | 16,384 | Deep analysis, complex reasoning |

Service: `app/services/weights_service.py`
Endpoint: `GET /api/studio/cko/weights`

---

## 12 Business Departments

AGENT-008 classifies content into these departments:

| # | Department | Examples |
|---|------------|----------|
| 1 | IT & Engineering | Software, infrastructure, APIs, DevOps |
| 2 | Sales & Marketing | Campaigns, leads, CRM, revenue |
| 3 | Customer Support | Tickets, help desk, SLA |
| 4 | Operations & HR & Supply Chain | Hiring, logistics, procurement |
| 5 | Finance & Accounting | Budgets, auditing, tax, compliance |
| 6 | Project Management | Agile/Scrum, milestones, planning |
| 7 | Real Estate | Property, leases, mortgages |
| 8 | Private Equity & M&A | Investments, acquisitions, due diligence |
| 9 | Consulting | Strategy, advisory, frameworks |
| 10 | Personal & Continuing Education | Training, courses, certifications |
| 11 | Research & Development (R&D) | Innovation, prototyping, patents |
| 12 | Global (_global) | Cross-department content |

---

## Service Files

### Pipeline Services (v7.5)

| File | Purpose |
|------|---------|
| `llm_client.py` | Unified LLM provider abstraction (4 implementations) |
| `prompt_engineer_service.py` | Sonnet 4.5 query enrichment |
| `output_architect_service.py` | Sonnet 4.5 output formatting |
| `document_generator_service.py` | DOCX/XLSX/PPTX/PDF generation |
| `vision_service.py` | Multi-provider image analysis |
| `whisper_stt_service.py` | Local audio transcription |
| `audio_video_processor.py` | Video frame extraction + analysis |
| `studio_cko_conversation_service.py` | CKO chat orchestration |
| `weights_service.py` | Quality preset management |
| `organization_service.py` | Multi-tenant org management |
| `cost_tracking_service.py` | Per-query cost tracking across models |

### Legacy Agent Services

| File | Agents |
|------|--------|
| `content_summarizer_agent.py` | AGENT-002 |
| `department_classifier_agent.py` | AGENT-008 |
| `document_analysis_agents.py` | AGENT-009, 010, 011 |
| `multi_agent_orchestration.py` | AGENT-012, 013, 014, 015 |

---

## Test Coverage

| Test File | Tests |
|-----------|-------|
| `test_llm_client.py` | LLM client abstraction |
| `test_vision_service.py` | Multi-provider vision |
| `test_whisper_stt_service.py` | Local audio STT |
| `test_audio_video_processor.py` | Video processing |
| `test_prompt_engineer_service.py` | Prompt engineering |
| `test_unified_search.py` | Unified search (12 tests) |
| `test_organization_service.py` | Org management |
| `test_artifact_system.py` | Artifact CRUD |
| `test_document_generator_service.py` | Document generation |
| `test_content_summarizer.py` | 15 tests |
| `test_department_classifier.py` | 18 tests |
| `test_document_analysis_agents.py` | 45 tests |
| `test_multi_agent_orchestration.py` | 62 tests |

---

**Empire v7.5** - Multi-model AI system with quality pipeline, multimodal processing, and document generation.
