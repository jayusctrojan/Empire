# Feature Specification: Empire v7.3 Feature Batch

**Feature Branch**: `2-empire-v73-features`
**Created**: 2025-11-23
**Updated**: 2025-11-23 (Added Feature 9)
**Status**: Draft
**Input**: User description: "9 new features for Empire v7.3 including R&D department, loading status, URL support, source attribution, agent chat, course additions, file uploads, book processing, and intelligent agent routing"

---

## Overview

This specification covers 9 new features for Empire v7.3, organized by priority and implementation complexity.

| # | Feature | Short Name | Priority |
|---|---------|------------|----------|
| 1 | R&D Department Addition | `rnd-department` | P1 |
| 2 | Loading Process Status UI | `loading-status` | P1 |
| 3 | URL/Link Support on Upload | `url-upload` | P2 |
| 4 | Source Attribution in Chat UI | `source-attribution` | P1 |
| 5 | Agent Chat & Improvement | `agent-chat` | P3 |
| 6 | Course Content Addition | `course-append` | P3 |
| 7 | Chat File/Image Upload | `chat-upload` | P2 |
| 8 | Book Processing | `book-processing` | P2 |
| 9 | Intelligent Agent Router | `agent-router` | P1 |

---

## Feature 1: R&D Department Addition

### User Scenarios & Testing

#### User Story 1.1 - Add R&D as 11th Department (Priority: P1)

As a system administrator, I want to add R&D as a new department so that research and development content can be properly classified and routed.

**Why this priority**: Foundation feature - all other department-related features depend on this being in place.

**Independent Test**: Can be fully tested by uploading a document tagged with "R&D" department and verifying it appears in department filters and follows R&D-specific workflows.

**Acceptance Scenarios**:

1. **Given** the current 10-department taxonomy exists, **When** R&D department is added, **Then** it appears in all department dropdowns and filters
2. **Given** a document is uploaded with R&D classification, **When** processed, **Then** it is stored in the correct B2 path (`crewai/assets/rnd/...`)
3. **Given** the AI classifier receives R&D-related content, **When** auto-classification runs, **Then** it correctly identifies R&D content

#### Edge Cases

- What happens when existing content should be reclassified to R&D?
- How does the system handle documents that span R&D and other departments?

### Requirements

#### Functional Requirements

- **FR-1.1**: System MUST add "R&D" as the 11th department in the department taxonomy
- **FR-1.2**: System MUST update Supabase schemas to include R&D department identifier
- **FR-1.3**: System MUST update B2 asset storage paths to include `rnd/` folder structure
- **FR-1.4**: System MUST update AI classification models to recognize R&D content
- **FR-1.5**: System MUST update all department dropdowns, filters, and selection UI components

#### Key Entities

- **Department**: Extended to include R&D (id: 11, slug: "rnd", name: "Research & Development")
- **DepartmentWorkflow**: New R&D-specific workflow configuration

### Success Criteria

- **SC-1.1**: R&D department appears in all 100% of department selection interfaces
- **SC-1.2**: Documents classified as R&D are correctly stored and retrievable
- **SC-1.3**: AI classification achieves >90% accuracy for R&D content

---

## Feature 2: Loading Process Status UI

### User Scenarios & Testing

#### User Story 2.1 - Real-time Processing Status (Priority: P1)

As a user uploading documents, I want to see exactly where my document is in the processing pipeline so that I know the system is working and can estimate completion time.

**Why this priority**: Critical UX improvement - users currently have no visibility into processing state.

**Independent Test**: Upload a document and verify the status indicator shows each stage: uploading → parsing → embedding → indexing → complete.

**Acceptance Scenarios**:

1. **Given** a user uploads a document, **When** upload begins, **Then** a progress indicator shows "Uploading..." with percentage
2. **Given** a document is being processed, **When** parsing begins, **Then** status updates to "Parsing document..."
3. **Given** embeddings are being generated, **When** embedding stage starts, **Then** status shows "Generating embeddings..."
4. **Given** indexing is in progress, **When** vectors are stored, **Then** status shows "Indexing to knowledge base..."
5. **Given** processing completes, **When** all stages finish, **Then** user sees "Complete" with success confirmation

#### User Story 2.2 - Query Processing Status (Priority: P2)

As a user running a complex query, I want to see which workflow stage is executing so that I understand why longer queries take time.

**Why this priority**: Improves user confidence for LangGraph adaptive queries that may take 10-30 seconds.

**Independent Test**: Run an adaptive query and verify status shows: analyzing → searching → refining → synthesizing.

**Acceptance Scenarios**:

1. **Given** a user submits a complex query, **When** LangGraph processes it, **Then** each node transition is reflected in the UI
2. **Given** a query requires multiple iterations, **When** refinement happens, **Then** iteration count is displayed

#### Edge Cases

- What happens when a processing stage fails mid-pipeline?
- How does the system show status for batch uploads (multiple files)?

### Requirements

#### Functional Requirements

- **FR-2.1**: System MUST display real-time processing status for document uploads
- **FR-2.2**: System MUST show distinct stages: upload, parse, embed, index, complete
- **FR-2.3**: System MUST display query processing status for LangGraph workflows
- **FR-2.4**: System MUST support WebSocket-based status updates (no polling)
- **FR-2.5**: System MUST show error state with descriptive message if any stage fails

#### Key Entities

- **ProcessingJob**: Tracks job_id, current_stage, progress_percentage, error_state
- **ProcessingStage**: Enum of stages (UPLOADING, PARSING, EMBEDDING, INDEXING, COMPLETE, ERROR)

### Success Criteria

- **SC-2.1**: Users see status updates within 500ms of stage transitions
- **SC-2.2**: 95% of users report understanding processing progress (survey)
- **SC-2.3**: Support ticket volume for "is it working?" questions reduced by 70%

---

## Feature 3: URL/Link Support on Upload

### User Scenarios & Testing

#### User Story 3.1 - YouTube Video Processing (Priority: P2)

As a user, I want to paste a YouTube URL and have the system extract and index the transcript so that I can query video content.

**Why this priority**: High user demand for video content integration.

**Independent Test**: Paste a YouTube URL, verify transcript is extracted, and confirm the content is searchable via chat.

**Acceptance Scenarios**:

1. **Given** a user pastes a valid YouTube URL, **When** submitted, **Then** system fetches video metadata and transcript
2. **Given** a YouTube video has captions, **When** processed, **Then** transcript is chunked and embedded
3. **Given** a YouTube video has no captions, **When** processed, **Then** audio is transcribed via Soniox

#### User Story 3.2 - Article/Webpage Processing (Priority: P2)

As a user, I want to paste article URLs and have the content extracted and indexed.

**Why this priority**: Enables users to quickly add web research to their knowledge base.

**Independent Test**: Paste an article URL, verify content extraction, and confirm searchability.

**Acceptance Scenarios**:

1. **Given** a user pastes a valid article URL, **When** submitted, **Then** system fetches and parses article content
2. **Given** an article has paywalled content, **When** accessible portion is extracted, **Then** user is notified of partial extraction
3. **Given** multiple URLs are pasted, **When** submitted as batch, **Then** all URLs are processed in parallel

#### Edge Cases

- What happens when a URL is invalid or returns 404?
- How does the system handle rate limiting from YouTube/websites?
- What about private/unlisted YouTube videos?

### Requirements

#### Functional Requirements

- **FR-3.1**: System MUST accept YouTube URLs and extract video transcripts
- **FR-3.2**: System MUST accept general web URLs and extract article content
- **FR-3.3**: System MUST use MarkItDown or similar for HTML-to-markdown conversion
- **FR-3.4**: System MUST store original URL as source metadata
- **FR-3.5**: System MUST support batch URL processing (up to 10 URLs at once)
- **FR-3.6**: System MUST handle videos without captions via audio transcription

#### Key Entities

- **URLSource**: Tracks url, source_type (youtube, article), extraction_status, content_hash
- **VideoMetadata**: title, channel, duration, thumbnail_url, transcript_source (captions/transcribed)

### Success Criteria

- **SC-3.1**: YouTube transcript extraction succeeds for 95%+ of public videos with captions
- **SC-3.2**: Article content extraction succeeds for 90%+ of standard web articles
- **SC-3.3**: URL-to-searchable-content pipeline completes within 60 seconds for typical content

---

## Feature 4: Source Attribution in Chat UI

### User Scenarios & Testing

#### User Story 4.1 - View Answer Sources (Priority: P1)

As a user chatting with the knowledge base, I want to see which documents/sources were used to generate the answer so that I can verify accuracy.

**Why this priority**: Critical for trust and verification - users need to know where information comes from.

**Independent Test**: Ask a question, verify sources are displayed below the answer with document names.

**Acceptance Scenarios**:

1. **Given** a user asks a question, **When** answer is generated, **Then** sources are listed below with document name and relevance score
2. **Given** sources are displayed, **When** user clicks a source, **Then** the relevant passage is highlighted or shown
3. **Given** an answer uses multiple sources, **When** displayed, **Then** sources are ordered by relevance/contribution

#### User Story 4.2 - Expandable Source Details (Priority: P2)

As a user, I want to optionally expand sources to see the exact passage used without leaving the chat.

**Why this priority**: Enhances verification workflow without disrupting chat flow.

**Independent Test**: Click "expand" on a source and verify the passage appears inline.

**Acceptance Scenarios**:

1. **Given** a source is listed, **When** user clicks expand, **Then** the relevant text passage appears
2. **Given** a source is from a PDF, **When** expanded, **Then** page number is shown

#### Edge Cases

- What happens when no sources are found (purely generative answer)?
- How are sources displayed for multi-turn conversations?

### Requirements

#### Functional Requirements

- **FR-4.1**: System MUST display source documents for each answer using LangExtract metadata
- **FR-4.2**: System MUST show document name, section/page, and relevance indicator
- **FR-4.3**: System MUST support expandable source details showing relevant passages
- **FR-4.4**: System MUST hyperlink sources when original document URL is available
- **FR-4.5**: System MUST clearly indicate when an answer is generated without sources

#### Key Entities

- **SourceCitation**: document_id, document_name, passage_text, relevance_score, page/section, url (optional)

### Success Criteria

- **SC-4.1**: 100% of RAG-based answers display at least one source citation
- **SC-4.2**: Users can view source passage within 1 click
- **SC-4.3**: 85%+ of users report increased confidence in answers (survey)

---

## Feature 5: Agent Chat & Improvement

### User Scenarios & Testing

#### User Story 5.1 - Select and Chat with Agents (Priority: P3)

As a user, I want to select a specific CrewAI agent and chat with it directly so that I can get specialized assistance.

**Why this priority**: Advanced feature building on existing CrewAI infrastructure.

**Independent Test**: Select an agent from list, start conversation, verify agent-specific responses.

**Acceptance Scenarios**:

1. **Given** available agents are listed, **When** user selects an agent, **Then** chat session starts with that agent
2. **Given** an agent has specialized knowledge, **When** user asks domain questions, **Then** agent responds with expertise
3. **Given** a chat session is active, **When** user switches agents, **Then** context is optionally preserved

#### User Story 5.2 - Agent Feedback and Improvement (Priority: P3)

As a user, I want to provide feedback on agent responses so that agents improve over time.

**Why this priority**: Enables continuous agent improvement based on real usage.

**Independent Test**: Rate a response, verify feedback is stored, check if future responses incorporate learning.

**Acceptance Scenarios**:

1. **Given** an agent response, **When** user provides thumbs up/down, **Then** feedback is logged
2. **Given** user provides detailed feedback, **When** submitted, **Then** feedback is associated with agent and query

#### Edge Cases

- What happens when an agent is under training/unavailable?
- How do permissions work for agent access?

### Requirements

#### Functional Requirements

- **FR-5.1**: System MUST display list of available CrewAI agents with descriptions
- **FR-5.2**: System MUST allow direct chat sessions with selected agents
- **FR-5.3**: System MUST collect feedback (rating, comments) on agent responses
- **FR-5.4**: System MUST store feedback for agent improvement analysis
- **FR-5.5**: System MUST support context preservation when switching agents

#### Key Entities

- **Agent**: agent_id, name, description, capabilities, status (available/training/offline)
- **AgentFeedback**: session_id, agent_id, rating, comment, query, response

### Success Criteria

- **SC-5.1**: Users can initiate agent chat within 2 clicks
- **SC-5.2**: 80%+ of agent interactions receive feedback
- **SC-5.3**: Agent response quality improves measurably over 30-day periods

---

## Feature 6: Course Content Addition

### User Scenarios & Testing

#### User Story 6.1 - Append Content to Existing Course (Priority: P3)

As a user, I want to add supplementary materials to an existing course in my knowledge base with explicit confirmation.

**Why this priority**: Rare operation that requires careful UX to prevent accidental additions.

**Independent Test**: Select existing course, upload new content, confirm checkbox, verify content is appended.

**Acceptance Scenarios**:

1. **Given** a course exists, **When** user selects "Add to Course", **Then** course selection dropdown appears
2. **Given** new content is uploaded, **When** user checks confirmation box, **Then** content is appended to course
3. **Given** content is appended, **When** course is queried, **Then** new content is included in results

#### Edge Cases

- What if appended content contradicts existing course material?
- How is version history maintained for courses?

### Requirements

#### Functional Requirements

- **FR-6.1**: System MUST provide "Add to Existing Course" option on upload page
- **FR-6.2**: System MUST require checkbox confirmation before appending
- **FR-6.3**: System MUST display course summary before confirmation
- **FR-6.4**: System MUST maintain relationship between original and appended content
- **FR-6.5**: System MUST log course modification history

#### Key Entities

- **CourseAppendLog**: course_id, appended_document_id, appended_at, appended_by

### Success Criteria

- **SC-6.1**: Zero accidental course modifications (confirmation prevents errors)
- **SC-6.2**: Appended content is searchable within 30 seconds of confirmation
- **SC-6.3**: Course history is fully auditable

---

## Feature 7: Chat File/Image Upload

### User Scenarios & Testing

#### User Story 7.1 - Upload Files During Chat (Priority: P2)

As a user chatting with the knowledge base, I want to upload a file mid-conversation and discuss its contents.

**Why this priority**: Matches expected ChatGPT-like experience users are familiar with.

**Independent Test**: During chat, upload a PDF, ask a question about it, verify answer references uploaded content.

**Acceptance Scenarios**:

1. **Given** user is in a chat session, **When** they click upload button, **Then** file picker opens
2. **Given** a file is uploaded mid-chat, **When** processed, **Then** file content is added to conversation context
3. **Given** file is in context, **When** user asks about it, **Then** answer references uploaded content

#### User Story 7.2 - Image Upload and Analysis (Priority: P2)

As a user, I want to upload images and have them analyzed using Claude Vision.

**Why this priority**: Enables multimodal conversations.

**Independent Test**: Upload an image, ask what's in it, verify vision analysis response.

**Acceptance Scenarios**:

1. **Given** user uploads an image, **When** processed, **Then** image is analyzed via Claude Vision API
2. **Given** image contains text, **When** analyzed, **Then** OCR content is extracted and searchable
3. **Given** image contains diagrams, **When** analyzed, **Then** description is generated

#### Edge Cases

- What are file size limits?
- How long do uploaded files persist in conversation context?
- What file types are supported?

### Requirements

#### Functional Requirements

- **FR-7.1**: System MUST support inline file upload during chat (drag-drop or button)
- **FR-7.2**: System MUST process uploaded files through the document pipeline
- **FR-7.3**: System MUST support image analysis via Claude Vision API
- **FR-7.4**: System MUST add uploaded content to conversation context
- **FR-7.5**: System MUST support file types: PDF, DOCX, TXT, PNG, JPG, WEBP

#### Key Entities

- **ChatAttachment**: chat_session_id, file_id, uploaded_at, processed_status, context_expiry

### Success Criteria

- **SC-7.1**: File upload to queryable in context takes <30 seconds for typical documents
- **SC-7.2**: Image analysis returns description within 5 seconds
- **SC-7.3**: 95%+ of supported file types process successfully

---

## Feature 8: Book Processing

### User Scenarios & Testing

#### User Story 8.1 - Process Long-Form PDF Books (Priority: P2)

As a user, I want to upload PDF books (100+ pages) and have them intelligently processed with chapter awareness.

**Why this priority**: Enables knowledge base to include comprehensive reference materials.

**Independent Test**: Upload a 200-page PDF book, verify chapter detection, confirm chapter-based queries work.

**Acceptance Scenarios**:

1. **Given** a book PDF is uploaded, **When** processed, **Then** chapters are detected and used as chunk boundaries
2. **Given** a book has table of contents, **When** parsed, **Then** TOC is extracted and used for navigation
3. **Given** book processing completes, **When** user queries, **Then** answers cite chapter and page numbers

#### User Story 8.2 - Book Metadata and Navigation (Priority: P3)

As a user, I want to see book structure and navigate to specific chapters.

**Why this priority**: Improves usability for long-form content.

**Independent Test**: View processed book, see chapter list, click chapter to filter search.

**Acceptance Scenarios**:

1. **Given** a book is processed, **When** viewed in library, **Then** chapter structure is displayed
2. **Given** chapters are displayed, **When** user clicks chapter, **Then** search is filtered to that chapter

#### Edge Cases

- What happens with scanned PDFs without OCR text?
- How are footnotes and references handled?
- What's the maximum book size supported?

### Requirements

#### Functional Requirements

- **FR-8.1**: System MUST detect and parse chapter structure from PDFs
- **FR-8.2**: System MUST extract table of contents when available
- **FR-8.3**: System MUST chunk content respecting chapter boundaries
- **FR-8.4**: System MUST store book metadata (title, author, chapters)
- **FR-8.5**: System MUST support scanned PDFs via OCR (LlamaParse/Mistral OCR)
- **FR-8.6**: System MUST handle books up to 500 pages (larger via async processing)

#### Key Entities

- **Book**: book_id, title, author, total_pages, chapter_count, processing_status
- **BookChapter**: book_id, chapter_number, title, start_page, end_page, content_hash

### Success Criteria

- **SC-8.1**: Books up to 300 pages process within 5 minutes
- **SC-8.2**: Chapter detection accuracy >85% for books with clear chapter markers
- **SC-8.3**: Book citations include chapter and page numbers

---

## Feature 9: Intelligent Agent Router

### User Scenarios & Testing

#### User Story 9.1 - Automatic Execution Pattern Selection (Priority: P1)

As a developer using the system, I want an intelligent router that automatically chooses the optimal execution pattern (skill, sub-agent, slash command, MCP) based on the task characteristics so that I get the most efficient and appropriate solution.

**Why this priority**: Foundation for intelligent agent orchestration - prevents over-complication and ensures right-tool-for-right-job.

**Independent Test**: Submit various task types and verify the router selects the appropriate pattern: one-off tasks → prompts/commands, repeat workflows → skills, parallel work → sub-agents, external data → MCP.

**Acceptance Scenarios**:

1. **Given** a one-off task request, **When** analyzed by router, **Then** it routes to a custom slash command
2. **Given** a reusable workflow pattern, **When** analyzed, **Then** it routes to an agent skill
3. **Given** a parallelizable task with isolated context, **When** analyzed, **Then** it routes to sub-agents
4. **Given** a task requiring external integration, **When** analyzed, **Then** it routes to appropriate MCP server

#### User Story 9.2 - CrewAI vs Claude Code Agent Selection (Priority: P1)

As a system, I want to intelligently route between CrewAI multi-agent workflows and Claude Code skills/sub-agents based on task complexity and characteristics.

**Why this priority**: Enables hybrid agent orchestration - leverage CrewAI for complex multi-step workflows, Claude Code for direct execution.

**Independent Test**: Submit a complex multi-document analysis task, verify routing to CrewAI; submit a simple file operation, verify routing to Claude Code skill.

**Acceptance Scenarios**:

1. **Given** a multi-agent coordination task, **When** router analyzes, **Then** it routes to CrewAI service with appropriate agents
2. **Given** a simple repeatable task, **When** router analyzes, **Then** it routes to Claude Code skill
3. **Given** a task requiring domain expertise, **When** router analyzes, **Then** it selects specialized CrewAI agent or Claude skill based on specialization match

#### User Story 9.3 - Composition and Fallback Strategy (Priority: P2)

As a system, I want to compose multiple patterns when needed and fall back gracefully when the primary pattern fails.

**Why this priority**: Enables robust execution - complex tasks may require hybrid approaches.

**Independent Test**: Submit a task that requires both MCP integration and sub-agent parallelization, verify composition works correctly.

**Acceptance Scenarios**:

1. **Given** a task requires both external data and parallel execution, **When** router analyzes, **Then** it composes MCP + sub-agents
2. **Given** a primary execution pattern fails, **When** error detected, **Then** router falls back to alternative pattern
3. **Given** a skill needs to use sub-agents, **When** executing, **Then** circular composition is handled correctly

#### Edge Cases

- What happens when task characteristics match multiple patterns equally?
- How does the system handle tasks that span Claude Code and CrewAI boundaries?
- What if both CrewAI and Claude Code agents are unavailable?

### Requirements

#### Functional Requirements

- **FR-9.1**: System MUST analyze task characteristics to determine optimal execution pattern
- **FR-9.2**: System MUST route between CrewAI agents and Claude Code skills/sub-agents
- **FR-9.3**: System MUST consider these decision factors:
  - Task repeatability (one-off vs reusable)
  - Context isolation requirements (shared vs isolated)
  - Parallelization needs (sequential vs concurrent)
  - External integration requirements
  - Domain specialization needs
  - Task complexity level
- **FR-9.4**: System MUST support composition of multiple patterns (e.g., skill + MCP + sub-agent)
- **FR-9.5**: System MUST handle circular composition safely (skill → sub-agent → skill)
- **FR-9.6**: System MUST provide fallback mechanisms when primary pattern fails
- **FR-9.7**: System MUST log routing decisions for debugging and improvement
- **FR-9.8**: System MUST respect user-specified pattern overrides when provided

#### Key Entities

- **ExecutionPattern**: Enum (PROMPT, SKILL, SUB_AGENT, MCP, CREWAI_AGENT)
- **TaskCharacteristics**: repeatability, parallelizable, requires_external_data, complexity_score, domain
- **RoutingDecision**: chosen_pattern, confidence_score, reasoning, fallback_patterns
- **AgentCapability**: agent_type (crewai/claude), specialization, availability_status

### Success Criteria

- **SC-9.1**: Router achieves >90% correct pattern selection on test suite of 100 diverse tasks
- **SC-9.2**: CrewAI vs Claude routing achieves >85% accuracy based on task complexity scoring
- **SC-9.3**: Composition of patterns succeeds without circular dependency issues
- **SC-9.4**: Fallback mechanisms activate within 2 seconds of primary pattern failure
- **SC-9.5**: Routing decision time adds <100ms overhead to task execution

---

## Router Decision Matrix (Reference)

This matrix guides the intelligent routing decisions:

### Task Type → Pattern Mapping

| Task Characteristics | Primary Pattern | Alternative | Rationale |
|---------------------|-----------------|-------------|-----------|
| One-off, simple | Slash Command | Skill (if frequent) | Primitives for simple tasks |
| Reusable workflow | Skill | Slash Command | Modularity for repeat solutions |
| Parallel execution needed | Sub-agent | CrewAI (if complex) | Context isolation for concurrent work |
| External API/DB integration | MCP Server | Skill + MCP | External data source access |
| Multi-agent coordination | CrewAI | Skill + Sub-agents | Complex multi-step workflows |
| Document analysis | CrewAI | Skill | Domain expertise required |
| Git operations | Skill | Slash Command | Repeat workflow management |
| Security audit | Sub-agent | CrewAI | Isolated, scalable analysis |
| Database query | MCP | Skill + MCP | Direct integration |

### CrewAI vs Claude Code Decision Criteria

Route to **CrewAI** when:
- Task requires multi-agent coordination (3+ specialized agents)
- Long-running async workflow (>30 seconds)
- Complex document processing with multiple analysis stages
- Domain expertise from specialized agents (legal, financial, technical)
- Task stored in CrewAI asset storage structure

Route to **Claude Code** when:
- Simple one-off or repeatable task
- Direct file system operations
- Git/version control operations
- Quick context-aware operations (<10 seconds)
- User wants to see execution steps in real-time

### Composition Rules

**Valid Compositions**:
- Skill → MCP (skills can use external data)
- Skill → Sub-agent (skills can parallelize work)
- Skill → Slash Command (skills can invoke prompts)
- Sub-agent → MCP (sub-agents can access external data)
- Sub-agent → Slash Command (sub-agents can use prompts)

**Invalid Compositions** (circular or redundant):
- Sub-agent → Sub-agent (not supported)
- Skill → Skill (use modular design instead)
- MCP → Sub-agent (MCP shouldn't orchestrate)

---

## Dependencies & Assumptions

### Cross-Feature Dependencies

- Feature 2 (Loading Status) enhances UX for Features 3, 7, 8 (all involve processing)
- Feature 4 (Source Attribution) builds on existing RAG infrastructure
- Feature 7 (Chat Upload) leverages Feature 8 (Book Processing) for PDF handling
- Feature 9 (Agent Router) orchestrates Feature 5 (Agent Chat) by routing between CrewAI and Claude Code agents

### Assumptions

- Existing Supabase and Neo4j infrastructure can handle additional department and entity types
- WebSocket connections are stable for real-time status updates
- YouTube API/transcript services remain accessible
- Claude Vision API is available for image analysis
- Book chapter detection can leverage existing LlamaParse capabilities

### Technical Considerations

- All features should integrate with existing Celery task queue
- Status updates should use WebSocket (not polling) for efficiency
- File uploads should go through existing B2 storage pipeline
- All new entities need corresponding Supabase migrations

---

## Implementation Priority Matrix

| Priority | Features | Rationale |
|----------|----------|-----------|
| P1 (Sprint 1) | 1, 2, 4, 9 | Foundation (R&D), UX critical (Loading), Trust (Sources), Orchestration (Router) |
| P2 (Sprint 2) | 3, 7, 8 | Content expansion (URLs, Files, Books) |
| P3 (Sprint 3) | 5, 6 | Advanced features (Agents, Courses) |

---

**Next Steps**:
1. Run `/speckit.plan` to generate technical implementation plan
2. Run `/speckit.tasks` to break down into actionable development tasks
3. Create GitHub issues from generated tasks
