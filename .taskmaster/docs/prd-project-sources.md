# PRD: Empire Project Sources (NotebookLM-Style Enhancement)

**Version:** 1.0
**Date:** January 4, 2026
**Author:** Claude Code
**Status:** Draft

---

## 1. Executive Summary

Enhance Empire's existing Projects feature to function like Google's NotebookLM, where users can attach multiple sources (files, URLs, YouTube videos) to a project and have AI-powered conversations grounded exclusively in those sources. This transforms Projects from simple conversation organizers into intelligent, source-aware knowledge containers.

---

## 2. Problem Statement

### Current State
- Projects in Empire Desktop serve as conversation organizers with basic file attachment
- Files uploaded to projects go into the global knowledge base
- Chat queries search across ALL documents, not project-specific sources
- No support for adding URLs or YouTube links as project sources
- No visibility into document processing status

### Pain Points
1. Users cannot create focused knowledge bases for specific topics/projects
2. Chat responses may include irrelevant information from unrelated documents
3. No way to add web articles or YouTube content to a project
4. Users don't know when uploaded files are ready for querying
5. Cannot trace AI responses back to specific sources

### Desired State
- Projects become self-contained knowledge containers
- Users add sources (files, URLs, YouTube) with processing status visibility
- Chat within a project queries ONLY that project's sources
- AI responses include citations linking back to specific sources

---

## 3. Goals & Success Metrics

### Goals
1. Enable project-scoped source management (files, URLs, YouTube)
2. Provide real-time processing status for each source
3. Implement project-scoped RAG queries
4. Display source citations in chat responses

### Success Metrics
| Metric | Target |
|--------|--------|
| Source upload success rate | >95% |
| Processing completion rate | >90% |
| Average processing time (PDF <10 pages) | <30 seconds |
| Average processing time (YouTube <30 min) | <60 seconds |
| User satisfaction (scoped responses) | >4.5/5 |

---

## 4. User Stories

### 4.1 Source Management

**US-1: Add File Sources**
> As a user, I want to upload documents (PDF, DOCX, etc.) to my project so that I can query them in conversations.

**Acceptance Criteria:**
- [ ] Drag & drop file upload in Project Detail view
- [ ] Support for 40+ file types (PDF, DOCX, XLSX, PPTX, TXT, images, audio, video, archives)
- [ ] File size limit of 100MB per file
- [ ] Multiple file upload support
- [ ] Visual feedback during upload

**US-2: Add URL Sources**
> As a user, I want to add web article URLs to my project so that I can include online content in my knowledge base.

**Acceptance Criteria:**
- [ ] URL input field in Project Detail view
- [ ] Support for multiple URLs (space or newline separated)
- [ ] Auto-detection of URL type (article vs YouTube)
- [ ] Content extraction from web pages
- [ ] Metadata capture (title, author, publish date)

**US-3: Add YouTube Sources**
> As a user, I want to add YouTube video URLs to my project so that I can query video transcripts.

**Acceptance Criteria:**
- [ ] YouTube URL detection and validation
- [ ] Automatic transcript extraction
- [ ] Video metadata capture (title, channel, duration)
- [ ] Chapter detection when available
- [ ] Thumbnail display in sources list

**US-4: View Processing Status**
> As a user, I want to see the processing status of each source so that I know when it's ready for querying.

**Acceptance Criteria:**
- [ ] Status indicators: pending, processing, ready, failed
- [ ] Progress percentage for long-running processes
- [ ] Error messages for failed sources
- [ ] Retry option for failed sources
- [ ] Estimated time remaining (optional)

**US-5: Remove Sources**
> As a user, I want to remove sources from my project so that I can manage my knowledge base.

**Acceptance Criteria:**
- [ ] Delete button on each source
- [ ] Confirmation dialog before deletion
- [ ] Cascade delete of associated embeddings
- [ ] Immediate UI update after deletion

### 4.2 Project-Scoped Chat

**US-6: Chat with Project Sources**
> As a user, I want my chat conversations within a project to only use that project's sources so that responses are relevant and focused.

**Acceptance Criteria:**
- [ ] RAG queries filter by project_id
- [ ] Only sources with status "ready" are queried
- [ ] Clear indication that chat is project-scoped
- [ ] Option to include/exclude specific sources (future)

**US-7: View Source Citations**
> As a user, I want to see which sources were used to generate a response so that I can verify the information.

**Acceptance Criteria:**
- [ ] Citations displayed below AI responses
- [ ] Source name and type indicator
- [ ] Click to view source details
- [ ] Relevant excerpt from source (optional)

### 4.3 Source Overview

**US-8: View All Project Sources**
> As a user, I want to see all sources in my project with their status and metadata so that I can manage my knowledge base.

**Acceptance Criteria:**
- [ ] Grid/list view of all sources
- [ ] Source type icons (PDF, YouTube, URL, etc.)
- [ ] Status badges (ready, processing, failed)
- [ ] File size / content length display
- [ ] Sort by date added, name, type, status
- [ ] Search/filter sources

---

## 5. Feature Specifications

### 5.1 Sources Section (Project Detail View)

**Location:** Right panel of Project Detail View, replacing/enhancing current "Files" section

**Components:**
```
┌─────────────────────────────────────────────────┐
│ Sources                                    [+]  │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐ │
│ │ ▾ Add Sources                               │ │
│ │ ┌─────────────────────────────────────────┐ │ │
│ │ │ Drop files or paste URLs here...        │ │ │
│ │ │                                         │ │ │
│ │ │ Supports: PDF, DOCX, YouTube, URLs...   │ │ │
│ │ └─────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│ │ PDF  │ │  YT  │ │ DOCX │ │ URL  │          │
│ │ ●    │ │ ◐    │ │ ●    │ │ ●    │          │
│ │doc1  │ │vid1  │ │doc2  │ │art1  │          │
│ └──────┘ └──────┘ └──────┘ └──────┘          │
│                                                 │
│ 4 sources • 3 ready • 1 processing             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 75%        │
└─────────────────────────────────────────────────┘
```

**Status Indicators:**
- ● Ready (green) - Source processed and queryable
- ◐ Processing (blue, animated) - Currently being processed
- ○ Pending (gray) - Queued for processing
- ✕ Failed (red) - Processing failed, retry available

### 5.2 Source Types & Processing

| Source Type | File Extensions / Patterns | Processing Method |
|-------------|---------------------------|-------------------|
| PDF | .pdf | LlamaParse / PyPDF |
| Word | .doc, .docx | python-docx |
| Excel | .xls, .xlsx | pandas / openpyxl |
| PowerPoint | .ppt, .pptx | python-pptx |
| Text | .txt, .md, .rtf | Direct read |
| CSV | .csv | pandas |
| Images | .jpg, .png, .gif, .webp | Claude Vision |
| Audio | .mp3, .wav, .m4a | Soniox transcription |
| Video | .mp4, .mov, .avi | Soniox transcription |
| YouTube | youtube.com, youtu.be | yt-dlp transcript |
| Web Article | http://, https:// | BeautifulSoup scraping |
| Archive | .zip, .tar, .gz | Extract & process contents |

### 5.3 Processing Pipeline

```
Source Added
    │
    ▼
┌─────────────┐
│   PENDING   │ ← Queued in Celery
└─────────────┘
    │
    ▼
┌─────────────┐
│ PROCESSING  │ ← Celery worker picks up task
└─────────────┘
    │
    ├──► Extract Content (type-specific)
    │
    ├──► Generate Summary (Claude)
    │
    ├──► Create Embeddings (BGE-M3)
    │
    ├──► Store in Supabase (with project_id)
    │
    ▼
┌─────────────┐
│    READY    │ ← Available for RAG queries
└─────────────┘
    │
    ▼ (on error)
┌─────────────┐
│   FAILED    │ ← Error logged, retry available
└─────────────┘
```

### 5.4 Hybrid RAG Query Flow (Project Sources + Global Knowledge Base)

The system uses a **hybrid approach** that combines:
- **Project Sources (Primary)**: Specific files, URLs, and content attached to the project
- **Global Knowledge Base (Secondary)**: Empire's existing document repository with domain expertise

This enables the AI to apply expert knowledge frameworks while grounding responses in project-specific context.

```
User Query (in Project Chat)
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Generate Query Embedding (BGE-M3)│
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. PARALLEL Vector Search                                    │
│                                                              │
│   ┌─────────────────────────┐  ┌─────────────────────────┐  │
│   │  PROJECT SOURCES        │  │  GLOBAL KNOWLEDGE BASE  │  │
│   │  (Primary - Weight 1.0) │  │  (Secondary - Wt 0.7)   │  │
│   │                         │  │                         │  │
│   │  WHERE project_id = X   │  │  All user documents     │  │
│   │  AND status = 'ready'   │  │  (existing Empire KB)   │  │
│   │  LIMIT 8                │  │  LIMIT 5                │  │
│   └─────────────────────────┘  └─────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. Merge & Rerank Results           │
│    - Project sources prioritized    │
│    - Global KB supplements context  │
│    - Deduplicate overlapping info   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 4. Generate Response (Claude)       │
│    - Use project sources for        │
│      specific examples/context      │
│    - Use global KB for frameworks   │
│      and expert methodology         │
│    - Cite both source types         │
└─────────────────────────────────────┘
    │
    ▼
Response with Citations (Project + Global Sources)
```

**Example Use Case:**
- **Global KB**: Contains marketing expertise, social media frameworks, content strategy best practices
- **Project Sources**: Competitor brand guidelines, specific product info, target audience research
- **Query**: "Create a social media content strategy for our cosmetics launch"
- **Response**: Uses marketing frameworks from global KB + specific brand examples from project sources

---

## 6. UI/UX Specifications

### 6.1 Add Sources Interaction

**Unified Input Area:**
- Combined drag & drop zone for files
- Textarea for URLs (multiple, newline-separated)
- Auto-detect input type
- "Add Sources" button to process input

**Feedback:**
- Immediate visual feedback on valid input
- Invalid URL/file type warning
- Duplicate source detection

### 6.2 Source Card Design

```
┌────────────────────────────────┐
│ [PDF]          [●] Ready   [×] │
│                                │
│ Company Policy Manual.pdf      │
│ 2.4 MB • 45 pages • PDF        │
│ Added Jan 4, 2026              │
└────────────────────────────────┘

┌────────────────────────────────┐
│ [YT]           [◐] 45%     [×] │
│ ┌────────────────────────────┐ │
│ │     [Thumbnail Image]      │ │
│ └────────────────────────────┘ │
│ How to Build RAG Systems       │
│ 15:32 • TechChannel            │
│ Added Jan 4, 2026              │
└────────────────────────────────┘

┌────────────────────────────────┐
│ [URL]          [✕] Failed  [↻] │
│                                │
│ Best Practices for AI          │
│ example.com/article            │
│ Error: Could not fetch content │
└────────────────────────────────┘
```

### 6.3 Chat with Citations

```
┌────────────────────────────────────────────────┐
│ User: What does the policy say about PTO?      │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ AI: According to the Company Policy Manual,    │
│ employees are entitled to 15 days of PTO per   │
│ year, accruing at 1.25 days per month...       │
│                                                │
│ ─────────────────────────────────────────────  │
│ Sources:                                       │
│ [PDF] Company Policy Manual.pdf (p. 23-24)     │
│ [PDF] Employee Handbook.pdf (p. 8)             │
└────────────────────────────────────────────────┘
```

---

## 7. Non-Functional Requirements

### 7.1 Performance
- Source upload: <2 seconds for files under 10MB
- Processing queue pickup: <5 seconds
- PDF processing (<50 pages): <60 seconds
- YouTube transcript (<30 min): <30 seconds
- Web article scraping: <10 seconds
- RAG query response: <3 seconds

### 7.2 Scalability
- Support up to 100 sources per project
- Support up to 500MB total content per project
- Handle concurrent processing of 10 sources

### 7.3 Reliability
- Automatic retry for transient failures (max 3 attempts)
- Graceful degradation if processing service unavailable
- Source content cached after successful processing

### 7.4 Security
- File type validation (magic bytes, not just extension)
- URL validation and sanitization
- Content scanning for malicious payloads
- RLS policies for source access (user can only see own project sources)

---

## 8. Out of Scope (v1)

- Audio overview generation (podcast-style summaries)
- Source sharing between projects
- Collaborative projects (multi-user)
- Source version history
- Selective source inclusion/exclusion in queries
- Source annotations/highlights
- Export project knowledge base

---

## 9. Dependencies

### Existing Empire Components (No Changes Needed)
- Document processing pipeline (LlamaParse, PyPDF, etc.)
- YouTube transcript extraction (yt-dlp)
- Web scraping (BeautifulSoup)
- Embedding generation (BGE-M3)
- Vector storage (Supabase pgvector)
- Task queue (Celery + Redis)
- LLM integration (Claude API)

### New Components Required
- `project_sources` database table
- Celery tasks for source processing
- Project-scoped RAG query endpoint
- Frontend Sources UI component

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Long processing times frustrate users | Medium | Show progress %, estimated time, allow background processing |
| YouTube blocks transcript access | Medium | Fallback to audio transcription, show clear error |
| Web scraping blocked by sites | Low | Respect robots.txt, show clear error, allow manual paste |
| Large files overwhelm processing | Medium | File size limits, queue prioritization |
| Embedding storage costs | Low | Chunking strategy, deduplication |

---

## 11. Success Criteria

### MVP (v1) Complete When:
- [ ] Users can add files, URLs, and YouTube to projects
- [ ] Processing status visible for each source
- [ ] Chat queries only return results from project sources
- [ ] Citations shown in chat responses
- [ ] Failed sources can be retried or removed

### Future Enhancements (v2+)
- Audio overview generation
- Source annotations
- Selective source querying
- Cross-project source linking
- Collaborative knowledge bases

---

## 12. Timeline Estimate

| Phase | Duration | Description |
|-------|----------|-------------|
| Database & API | 2-3 days | Sources table, CRUD endpoints |
| Celery Tasks | 2-3 days | Processing pipeline with status updates |
| Project-Scoped RAG | 1-2 days | Filter queries by project_id |
| Frontend UI | 3-4 days | Sources section, status indicators, citations |
| Testing & Polish | 2-3 days | E2E testing, error handling, UX refinement |
| **Total** | **10-15 days** | |

---

## Appendix A: Glossary

- **Source**: Any content added to a project (file, URL, YouTube video)
- **Processing**: Extracting text, generating embeddings, storing in vector DB
- **Project-Scoped**: Limited to sources within a specific project
- **RAG**: Retrieval-Augmented Generation
- **Citation**: Reference to source used in AI response

---

## Clarifications

### Session 2026-01-04

- Q: Should users be able to adjust the Project/Global KB weighting ratio? → A: Fixed weights only. Project sources provide context/input (branding, specific references) that guides the Global KB experts (domain masters/frameworks) to produce tailored output. They don't compete - project sources inform, global KB provides intelligence.

- Q: After max retries (3) are exhausted, what should happen to failed sources? → A: Keep visible with "Failed" badge until user manually deletes. No auto-archiving or forced prompts.

- Q: How should the system handle users approaching storage/source limits? → A: Warning at 80% capacity, soft block at 100% with cleanup suggestions or upgrade prompt. No surprise hard blocks.

- Q: When WebSocket reconnects after a disconnect, how should the UI sync source states? → A: Full refresh of all project sources on reconnect. Backend is source of truth.

- Q: What should "View Source" do when clicking a citation? → A: Context-aware viewing - PDF opens at relevant page, YouTube jumps to timestamp, URL opens in browser.
