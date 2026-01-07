# Feature Specification: AI Studio - Chief Knowledge Officer

**Feature Branch**: `001-studio`
**Created**: 2025-01-05
**Status**: Draft
**PRD Reference**: `.taskmaster/docs/prd_ai_studio.txt` v2.0
**Architecture Reference**: `.taskmaster/docs/architecture_ai_studio.md` v1.0

## Overview

AI Studio introduces the **Chief Knowledge Officer (CKO)** - an intelligent AI persona that serves as the user's personal knowledge manager. Unlike traditional RAG chat that simply retrieves and answers, the CKO is an active, conversational entity that manages, understands, and proactively surfaces insights from the knowledge base.

**Key Concept**: The CKO is not a search engine - it's a knowledgeable colleague who happens to have perfect recall.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversational KB Interaction (Priority: P0)

As a knowledge worker, I want to have a conversation with my knowledge base through the CKO persona, so that I can get intelligent, contextual answers with explanations of reasoning.

**Why this priority**: This is the core feature - without CKO conversation, there is no AI Studio value proposition.

**Independent Test**: Can be fully tested by sending messages to CKO and receiving contextual responses with source citations. Delivers immediate value as an intelligent KB interface.

**Acceptance Scenarios**:

1. **Given** I am in AI Studio, **When** I ask "What do you know about our sales process?", **Then** CKO responds with synthesized information citing specific documents and offers to elaborate.
2. **Given** CKO has responded, **When** I ask "Why did you classify that as Finance?", **Then** CKO explains its reasoning with confidence scores and keywords matched.
3. **Given** I am chatting with CKO, **When** the response is streaming, **Then** I see real-time token streaming via WebSocket.

---

### User Story 2 - CKO Clarification Flow (Priority: P0)

As a user, I want CKO to ask me clarifying questions naturally in conversation when it's uncertain, so that classifications and decisions are more accurate.

**Why this priority**: This is the human-in-the-loop mechanism that differentiates CKO from basic RAG. Critical for accuracy.

**Independent Test**: Can be tested by uploading ambiguous content and verifying CKO asks for clarification with options, then processes the answer correctly.

**Acceptance Scenarios**:

1. **Given** a document with 68% classification confidence (below 70% threshold), **When** processed, **Then** CKO asks "Is this IT-Engineering or Operations?" with inline buttons.
2. **Given** CKO has asked a clarification, **When** I respond "IT", **Then** CKO acknowledges, updates classification, and remembers preference.
3. **Given** CKO has pending clarifications, **When** I'm not in AI Studio, **Then** yellow dot appears on AI Studio nav item with badge count.
4. **Given** a clarification is pending >24 hours, **When** viewing nav, **Then** dot changes to red indicating overdue.

---

### User Story 3 - Data Weights Configuration (Priority: P0)

As a user, I want to configure how CKO weighs different content sources (by department, recency, source type), so that responses prioritize what matters most to me.

**Why this priority**: Data weights are how users personalize CKO behavior - essential for trust and relevance.

**Independent Test**: Can be tested by setting department weight to 2.0 for Sales, querying, and verifying Sales documents rank higher.

**Acceptance Scenarios**:

1. **Given** I set Sales department weight to 2.0, **When** I ask a question, **Then** Sales documents are weighted 2x higher in retrieval.
2. **Given** recency weight is enabled (last 30 days: 1.5x), **When** querying, **Then** recent documents score 50% higher.
3. **Given** I pin a document, **When** querying related topics, **Then** pinned document is always included with 2.0x weight.
4. **Given** I mute a document, **When** querying, **Then** muted document is excluded from results.
5. **Given** I ask CKO "prioritize recent documents", **When** processed, **Then** CKO updates recency weights and confirms the change.

---

### User Story 4 - AI Studio Navigation (Priority: P1)

As a user, I want AI Studio as a navigation item between File Uploads and Settings, so that I can access CKO and KB management features easily.

**Why this priority**: Navigation is required for users to access the feature, but is infrastructure not core value.

**Independent Test**: Can be tested by clicking AI Studio nav and verifying the view loads with CKO conversation as primary interface.

**Acceptance Scenarios**:

1. **Given** I am in the app, **When** I look at sidebar, **Then** I see "AI Studio" between "File Uploads" and "Settings".
2. **Given** AI Studio nav item, **When** CKO has pending clarifications, **Then** yellow notification dot appears.
3. **Given** I click AI Studio, **When** view loads, **Then** CKO Conversation is the primary/default view with collapsible sidebar panels.

---

### User Story 5 - Asset Management (Priority: P1)

As a user, I want to view and manage the 5 types of generated assets (Skill, Command, Agent, Prompt, Workflow), so that I can review, edit, publish, or archive AI-generated content.

**Why this priority**: Assets are the output of AGENT-001 processing - users need visibility and control.

**Independent Test**: Can be tested by viewing asset list, filtering by type, opening detail modal, editing content, and publishing.

**Acceptance Scenarios**:

1. **Given** I am in AI Studio, **When** I expand Assets panel, **Then** I see list of generated assets with type icons and department badges.
2. **Given** asset list, **When** I filter by "Skill" type, **Then** only YAML skill assets are shown.
3. **Given** I click an asset, **When** modal opens, **Then** I see content, source document, classification confidence, and reasoning.
4. **Given** I edit asset content, **When** I save, **Then** version is incremented and change is persisted.
5. **Given** a draft asset, **When** I click "Publish", **Then** status changes to published and file is stored in B2.

---

### User Story 6 - Classification Management (Priority: P1)

As a user, I want to view and correct how my content was classified into 12 departments, so that I can improve classification accuracy.

**Why this priority**: Classification corrections feed back into CKO learning - important for long-term accuracy.

**Independent Test**: Can be tested by viewing classification, correcting department, and verifying CKO learns the preference.

**Acceptance Scenarios**:

1. **Given** I expand Classifications panel, **When** viewing list, **Then** I see documents with department, confidence score (color-coded), and correction indicator.
2. **Given** a misclassified document, **When** I select new department, **Then** classification is updated and CKO acknowledges learning.
3. **Given** multiple corrections to similar content, **When** new similar content arrives, **Then** CKO applies learned preference.

---

### User Story 7 - Global Search (Priority: P1)

As a user, I want to search across all AI Studio content (conversations, assets, documents, classifications) from one search bar, so that I can quickly find anything.

**Why this priority**: Search is a core productivity feature but not the primary value proposition.

**Independent Test**: Can be tested by pressing Cmd+K, typing query, and verifying results span multiple content types with facets.

**Acceptance Scenarios**:

1. **Given** I am in AI Studio, **When** I press Cmd+K, **Then** search bar focuses.
2. **Given** I search "sales", **When** results load, **Then** I see conversations, assets, and documents matching "sales" with type icons.
3. **Given** search results, **When** I filter by "asset", **Then** only asset results are shown.
4. **Given** I click a conversation result, **When** navigating, **Then** I'm taken to that CKO conversation at the matching message.

---

### User Story 8 - Feedback & Learning (Priority: P2)

As a user, I want to rate CKO responses and see how my feedback improves future responses, so that I trust the system is learning.

**Why this priority**: Feedback loop is important for long-term quality but not required for initial value.

**Independent Test**: Can be tested by rating responses thumbs up/down and viewing feedback dashboard showing impact.

**Acceptance Scenarios**:

1. **Given** CKO response, **When** I click thumbs down, **Then** feedback is recorded with option to add text.
2. **Given** I expand Feedback panel, **When** viewing, **Then** I see history of my feedback with CKO acknowledgments.
3. **Given** multiple negative ratings on similar responses, **When** asking similar question later, **Then** CKO adjusts approach.

---

### Edge Cases

- What happens when CKO has no relevant documents for a query? → CKO explains gap and suggests what to upload.
- How does system handle conflicting information in KB? → CKO surfaces conflict and asks user to resolve.
- What happens when user ignores clarifications indefinitely? → System proceeds with best guess after 24h, marks as skipped.
- How does system handle very large documents (>5MB)? → Document is chunked; CKO explains it processed in parts.
- What happens when Redis/cache is unavailable? → Weights still apply via DB lookup (slower); CKO functions degraded.
- How does system handle concurrent edits to same asset? → Last-write-wins with version conflict warning.

## Requirements *(mandatory)*

### Functional Requirements

**CKO Conversation (P0)**
- **FR-001**: System MUST provide conversational interface with CKO persona (not generic RAG)
- **FR-002**: System MUST stream CKO responses in real-time via WebSocket
- **FR-003**: CKO MUST cite source documents with expandable citations in responses
- **FR-004**: CKO MUST explain reasoning when asked "why" questions
- **FR-005**: CKO MUST persist conversation history across sessions
- **FR-006**: System MUST support creating new conversations and switching between them

**Clarification System (P0)**
- **FR-007**: CKO MUST ask clarifying questions when classification confidence < 70%
- **FR-008**: Clarification messages MUST be highlighted in yellow (#FEF3C7 background)
- **FR-009**: System MUST show yellow dot on AI Studio nav when clarifications pending
- **FR-010**: System MUST show red dot when clarifications pending > 24 hours
- **FR-011**: Users MUST be able to respond to clarifications inline or skip with "best guess"
- **FR-012**: CKO MUST remember user preferences from clarification responses
- **FR-012a**: System MUST auto-skip pending clarifications after 7 days, proceeding with CKO's best guess and logging the decision

**Data Weights (P0)**
- **FR-013**: System MUST allow configuring weight multipliers (0.0-2.0) per department
- **FR-014**: System MUST support recency weighting (last 30 days, last year, older)
- **FR-015**: System MUST support source type weighting (PDF, video, audio, web, notes)
- **FR-016**: System MUST support pinning documents (always included, 2.0x weight)
- **FR-017**: System MUST support muting documents (excluded from retrieval)
- **FR-018**: CKO MUST be able to adjust weights via conversation ("prioritize recent docs")
- **FR-019**: System MUST provide weight presets (Balanced, Recent Focus, Verified Only)

**Navigation & Layout (P1)**
- **FR-020**: AI Studio MUST appear in sidebar between File Uploads and Settings
- **FR-021**: AI Studio MUST show notification badge with pending clarification count
- **FR-022**: CKO Conversation MUST be the primary/default view
- **FR-023**: Sidebar panels (Assets, Classifications, Weights, Feedback) MUST be collapsible

**Asset Management (P1)**
- **FR-024**: System MUST display all 5 asset types: Skill (YAML), Command (MD), Agent (YAML), Prompt (MD), Workflow (JSON)
- **FR-025**: System MUST allow filtering assets by type, department, status
- **FR-026**: System MUST allow viewing and editing asset content
- **FR-027**: System MUST track asset versions with history
- **FR-028**: System MUST support publishing drafts to B2 storage
- **FR-029**: System MUST support archiving unwanted assets

**Classification Management (P1)**
- **FR-030**: System MUST display all 12 department classifications with confidence scores
- **FR-031**: System MUST allow correcting misclassified content
- **FR-032**: System MUST show classification reasoning and matched keywords
- **FR-033**: System MUST track correction rate for accuracy metrics

**Search (P1)**
- **FR-034**: System MUST provide global search across conversations, assets, documents, classifications
- **FR-035**: System MUST support keyboard shortcut Cmd+K for search
- **FR-036**: System MUST show search results with type icons and snippets
- **FR-037**: System MUST support filtering results by type

**Feedback (P2)**
- **FR-038**: System MUST allow thumbs up/down rating on CKO responses
- **FR-039**: System MUST persist feedback for learning analysis
- **FR-040**: System MUST show feedback history in dashboard

### Key Entities

- **CKO Session**: Conversation thread with CKO (id, user_id, title, message_count, pending_clarifications)
- **CKO Message**: Individual message in conversation (id, session_id, role, content, is_clarification, sources, rating)
- **User Weights**: Per-user weight configuration (id, user_id, weights JSON, pinned_ids, muted_ids)
- **Asset**: Generated content artifact (id, user_id, asset_type, department, content, format, status, version)
- **Classification**: Department classification record (id, user_id, document_id, department, confidence, user_corrected)

### 12 Departments (Classification Taxonomy)

1. IT & Engineering (`it-engineering`)
2. Sales & Marketing (`sales-marketing`)
3. Customer Support (`customer-support`)
4. Operations/HR/Supply (`operations-hr-supply`)
5. Finance & Accounting (`finance-accounting`)
6. Project Management (`project-management`)
7. Real Estate (`real-estate`)
8. Private Equity & M&A (`private-equity-ma`)
9. Consulting (`consulting`)
10. Personal & Continuing Ed (`personal-continuing-ed`)
11. Research & Development (`research-development`)
12. Global (`_global`) - cross-department catch-all

### 5 Asset Types

| Type | Format | Description |
|------|--------|-------------|
| SKILL | YAML | Complex reusable automation |
| COMMAND | MD | Quick one-liner actions |
| AGENT | YAML | Multi-step role-based tasks |
| PROMPT | MD | Reusable templates (default) |
| WORKFLOW | JSON | Multi-system automation |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: CKO first-token response time < 3 seconds for 95% of queries
- **SC-002**: CKO provides relevant source citations in > 90% of factual responses
- **SC-003**: Users can complete clarification response in < 10 seconds (inline buttons)
- **SC-004**: Classification accuracy improves by > 10% after 50 user corrections
- **SC-005**: 80% of users who access AI Studio return within 7 days
- **SC-006**: Average CKO conversation length > 5 messages (engagement metric)
- **SC-007**: Feedback submission rate > 10% of CKO responses
- **SC-008**: User satisfaction (thumbs up rate) > 80%
- **SC-009**: Search returns relevant results in < 500ms
- **SC-010**: Asset management operations (view, edit, publish) complete in < 2 seconds

### Non-Functional Requirements

- **NFR-001**: All API endpoints require authentication (JWT)
- **NFR-002**: RLS policies enforce user-level data isolation
- **NFR-003**: WebSocket connections support 1000+ concurrent sessions
- **NFR-004**: Data weights stored in JSON column for flexibility
- **NFR-005**: All new tables have appropriate indexes for query patterns
- **NFR-006**: WCAG 2.1 AA accessibility compliance
- **NFR-007**: CKO service MUST maintain 99.5% monthly availability with graceful degradation to basic RAG when CKO persona/agents unavailable
- **NFR-008**: System MUST queue failed external operations (AGENT-001, B2, Redis) and retry automatically (max 3 attempts), notifying user of processing delay
- **NFR-009**: AI Studio/CKO access restricted to admin user only; teammates (if added) do not have CKO access
- **NFR-010**: Empty states MUST show simple explanation text (no onboarding flows required for admin user)
- **NFR-011**: CKO MUST retain last 50 conversations with summarized context in active memory; older conversations remain searchable but not loaded into context window

### Constraints & Tradeoffs

- **Memory vs. Context**: CKO uses summarized context from recent 50 conversations (not full history) to balance memory continuity with LLM context window limits
- **Graceful Degradation**: When CKO agents unavailable, system falls back to basic RAG rather than failing completely
- **Admin-Only Access**: CKO is admin-only feature; team collaboration features deferred to future version

## Clarifications

### Session 2025-01-05

- Q: What availability and recovery expectations for CKO service? → A: 99.5% availability with graceful degradation to basic RAG when CKO unavailable
- Q: How should system handle external dependency failures (AGENT-001, B2, Redis)? → A: Queue failed operations and retry automatically (3 attempts), notify user of delay
- Q: What should UI show for empty states? → A: Simple empty state with brief explanation (admin-only user, no onboarding needed). Teammates if added would not have CKO access.
- Q: What triggers auto-skip for pending clarifications? → A: Auto-skip after 7 days, CKO proceeds with best guess and logs decision
- Q: How much CKO memory/conversation history to retain? → A: Last 50 conversations with summarized context; older ones searchable but not in active memory
