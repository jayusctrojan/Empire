# Architecture Plan: AI Studio v7.4
# Chief Knowledge Officer & Asset Management

## Document Information
- **Version**: 1.0
- **Created**: 2025-01-05
- **PRD Reference**: prd_ai_studio.txt v2.0
- **Status**: Ready for Review

---

## 1. Architecture Overview

### 1.1 System Context

AI Studio introduces a conversational knowledge management layer on top of Empire's existing RAG infrastructure. The **Chief Knowledge Officer (CKO)** serves as the intelligent interface between users and the knowledge base.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EMPIRE v7.4                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Chats     │  │  Projects   │  │ File Upload │  │     AI STUDIO       │ │
│  │             │  │             │  │             │  │  ┌───────────────┐  │ │
│  │  Standard   │  │  Project    │  │  Global KB  │  │  │     CKO       │  │ │
│  │  Chat UI    │  │  RAG Chat   │  │  Upload     │  │  │  Conversation │  │ │
│  │             │  │             │  │             │  │  └───────────────┘  │ │
│  │             │  │             │  │             │  │  ┌───────────────┐  │ │
│  │             │  │             │  │             │  │  │  Sidebar:     │  │ │
│  │             │  │             │  │             │  │  │  - Assets     │  │ │
│  │             │  │             │  │             │  │  │  - Classes    │  │ │
│  │             │  │             │  │             │  │  │  - Weights    │  │ │
│  │             │  │             │  │             │  │  │  - Feedback   │  │ │
│  │             │  │             │  │             │  │  └───────────────┘  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                          SHARED SERVICES LAYER                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  CKO Service  │  RAG Service  │  Agent Router  │  Asset Service      │   │
│  │  (NEW)        │  (Extended)   │  (Extended)    │  (NEW)              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│                             AI AGENTS (15)                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  AGENT-001: Master Orchestrator (CKO Brain)                          │   │
│  │  AGENT-002: Summarizer  │  AGENT-008: Classifier  │  AGENT-009-015   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│                           DATA LAYER                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌───────────┐  │
│  │   PostgreSQL   │  │     Neo4j      │  │     Redis      │  │    B2     │  │
│  │   (Supabase)   │  │  (Knowledge    │  │   (Cache/      │  │ (Storage) │  │
│  │   + pgvector   │  │    Graph)      │  │    Broker)     │  │           │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CKO Backend | Extended AGENT-001 | Leverage existing orchestrator, add persona layer |
| Conversation Storage | PostgreSQL (studio_cko_sessions) | Consistent with existing chat pattern |
| Clarification Flow | In-conversation (not queue) | More natural UX, reduces friction |
| Data Weights | User-level config (JSON column) | Flexible, no schema changes per weight type |
| Notification System | WebSocket + badge count | Real-time, non-intrusive |
| Search Backend | PostgreSQL FTS + pgvector | Unified search, no new dependencies |

### 1.3 Integration with Existing Systems

**Reused Components:**
- `project_rag_service.py` patterns for KB queries (weight global=1.0)
- `agent_router.py` for workflow selection
- WebSocket manager for streaming responses
- `agent_feedback` table for feedback collection
- B2 storage for asset files

**Extended Components:**
- `orchestrator_agent_service.py` → Add CKO persona methods
- Navigation sidebar → Add AI Studio item with notification badge
- `chat_sessions` pattern → New `studio_cko_sessions` table

---

## 2. Component Architecture

### 2.1 Backend Components

```
app/
├── services/
│   ├── cko_service.py                 # CKO conversation & persona (NEW)
│   ├── cko_weights_service.py         # Data weights management (NEW)
│   ├── cko_clarification_service.py   # Clarification tracking (NEW)
│   ├── asset_management_service.py    # 5-type asset CRUD (NEW)
│   ├── studio_search_service.py       # Global search (NEW)
│   ├── classification_service.py      # Extends AGENT-008 (NEW)
│   └── orchestrator_agent_service.py  # (EXTENDED - add CKO methods)
├── routes/
│   ├── studio/
│   │   ├── __init__.py
│   │   ├── cko.py                     # CKO conversation endpoints
│   │   ├── assets.py                  # Asset management endpoints
│   │   ├── classifications.py         # Classification endpoints
│   │   ├── weights.py                 # Data weights endpoints
│   │   ├── search.py                  # Global search endpoints
│   │   └── feedback.py                # Feedback endpoints
│   └── studio.py                      # Main studio router (mounts sub-routers)
├── models/
│   ├── studio.py                      # Pydantic models for Studio (NEW)
│   └── cko.py                         # CKO-specific models (NEW)
└── websockets/
    └── cko_streaming.py               # CKO response streaming (NEW)
```

### 2.2 Frontend Components (Desktop App)

```
empire-desktop/src/
├── views/
│   └── AIStudioView.tsx               # Main AI Studio container
├── components/
│   └── studio/
│       ├── CKOConversation.tsx        # Main CKO chat interface
│       ├── CKOMessage.tsx             # Message bubble (user/CKO)
│       ├── CKOClarification.tsx       # Yellow highlighted clarification
│       ├── CKOQuickActions.tsx        # Inline action buttons
│       ├── StudioSidebar.tsx          # Collapsible sidebar panels
│       ├── AssetPanel.tsx             # Assets list panel
│       ├── AssetCard.tsx              # Individual asset card
│       ├── AssetDetailModal.tsx       # Asset view/edit modal
│       ├── ClassificationPanel.tsx    # Classifications panel
│       ├── ClassificationCard.tsx     # Classification item
│       ├── WeightsPanel.tsx           # Data weights configuration
│       ├── WeightSlider.tsx           # Individual weight control
│       ├── FeedbackPanel.tsx          # Feedback history panel
│       ├── StudioSearch.tsx           # Global search bar (Cmd+K)
│       ├── SearchResults.tsx          # Search result list
│       └── NotificationBadge.tsx      # Yellow dot / count badge
├── stores/
│   └── studio/
│       ├── ckoStore.ts                # CKO conversation state
│       ├── assetsStore.ts             # Assets state
│       ├── classificationsStore.ts    # Classifications state
│       ├── weightsStore.ts            # Data weights state
│       └── searchStore.ts             # Search state
├── hooks/
│   └── studio/
│       ├── useCKOWebSocket.ts         # WebSocket connection hook
│       ├── useCKOPending.ts           # Pending clarifications polling
│       └── useStudioSearch.ts         # Search with debounce
└── api/
    └── studio/
        ├── cko.ts                     # CKO API client
        ├── assets.ts                  # Assets API client
        ├── classifications.ts         # Classifications API client
        ├── weights.ts                 # Weights API client
        └── search.ts                  # Search API client
```

### 2.3 Component Interaction Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DESKTOP APP (Electron + React)                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        AIStudioView.tsx                          │    │
│  │  ┌─────────────────────────────┐  ┌──────────────────────────┐  │    │
│  │  │   CKOConversation.tsx       │  │   StudioSidebar.tsx      │  │    │
│  │  │   ┌─────────────────────┐   │  │   ┌──────────────────┐   │  │    │
│  │  │   │ CKOMessage (user)   │   │  │   │ AssetPanel       │   │  │    │
│  │  │   │ CKOMessage (cko)    │   │  │   │ ClassifyPanel    │   │  │    │
│  │  │   │ CKOClarification    │◄──┼──┼───│ WeightsPanel     │   │  │    │
│  │  │   │ CKOQuickActions     │   │  │   │ FeedbackPanel    │   │  │    │
│  │  │   └─────────────────────┘   │  │   └──────────────────┘   │  │    │
│  │  │   ┌─────────────────────┐   │  │                          │  │    │
│  │  │   │ Message Input       │   │  │                          │  │    │
│  │  │   └─────────────────────┘   │  │                          │  │    │
│  │  └─────────────────────────────┘  └──────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                   ┌──────────┴──────────┐                               │
│                   │   ckoStore.ts       │                               │
│                   │   (Zustand)         │                               │
│                   └──────────┬──────────┘                               │
└──────────────────────────────┼───────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │      WebSocket + REST       │
                └──────────────┬──────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────────────┐
│                         FASTAPI BACKEND                                   │
├──────────────────────────────┼───────────────────────────────────────────┤
│                              │                                           │
│  ┌───────────────────────────▼───────────────────────────────────────┐  │
│  │                    CKO Service Layer                               │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐   │  │
│  │  │ cko_service.py │  │ cko_weights    │  │ cko_clarification  │   │  │
│  │  │                │  │ _service.py    │  │ _service.py        │   │  │
│  │  │ • process_msg  │  │ • get_weights  │  │ • track_pending    │   │  │
│  │  │ • stream_resp  │  │ • set_weights  │  │ • mark_resolved    │   │  │
│  │  │ • get_context  │  │ • apply_to_qry │  │ • get_count        │   │  │
│  │  └───────┬────────┘  └────────────────┘  └────────────────────┘   │  │
│  └──────────┼────────────────────────────────────────────────────────┘  │
│             │                                                            │
│  ┌──────────▼────────────────────────────────────────────────────────┐  │
│  │                    Agent Orchestration Layer                       │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  orchestrator_agent_service.py (AGENT-001)                  │  │  │
│  │  │  • CKO persona methods (NEW)                                │  │  │
│  │  │  • classify_content() (existing)                            │  │  │
│  │  │  • generate_asset() (existing)                              │  │  │
│  │  │  • delegate_to_agent() (existing)                           │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  AGENT-002 to AGENT-015 (specialized agents)                │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                           │
│  ┌───────────────────────────▼───────────────────────────────────────┐  │
│  │                    Data Access Layer                               │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐   │  │
│  │  │ Supabase       │  │ Neo4j          │  │ Redis              │   │  │
│  │  │ (PostgreSQL)   │  │ (Graph)        │  │ (Cache)            │   │  │
│  │  └────────────────┘  └────────────────┘  └────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Architecture

### 3.1 New Database Tables

```sql
-- =============================================================================
-- CKO SESSIONS (Conversations with Chief Knowledge Officer)
-- =============================================================================
CREATE TABLE studio_cko_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,

    -- Session metadata
    title TEXT,  -- Auto-generated from first message or user-defined

    -- Counters
    message_count INTEGER DEFAULT 0,
    pending_clarifications INTEGER DEFAULT 0,  -- For badge count

    -- Memory
    context_summary TEXT,  -- CKO's memory of this conversation

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

CREATE INDEX idx_cko_sessions_user ON studio_cko_sessions(user_id);
CREATE INDEX idx_cko_sessions_updated ON studio_cko_sessions(updated_at DESC);
CREATE INDEX idx_cko_sessions_pending ON studio_cko_sessions(pending_clarifications)
    WHERE pending_clarifications > 0;

-- =============================================================================
-- CKO MESSAGES
-- =============================================================================
CREATE TABLE studio_cko_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES studio_cko_sessions(id) ON DELETE CASCADE NOT NULL,

    -- Message content
    role TEXT NOT NULL CHECK (role IN ('user', 'cko')),
    content TEXT NOT NULL,

    -- Clarification tracking
    is_clarification BOOLEAN DEFAULT false,  -- Yellow highlight
    clarification_type TEXT,  -- classification, asset_type, conflict, sensitive, department
    clarification_status TEXT DEFAULT 'pending',  -- pending, answered, skipped
    clarification_answer TEXT,  -- User's response

    -- Sources and citations
    sources JSONB DEFAULT '[]',  -- [{doc_id, title, snippet, relevance_score}]

    -- Actions taken
    actions_performed JSONB DEFAULT '[]',  -- [{action: "reclassify", params: {...}, result: {...}}]

    -- Feedback
    rating INTEGER CHECK (rating BETWEEN -1 AND 1),  -- -1 = down, 0 = none, 1 = up

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_cko_messages_session ON studio_cko_messages(session_id);
CREATE INDEX idx_cko_messages_clarification ON studio_cko_messages(clarification_status)
    WHERE is_clarification = true;

-- =============================================================================
-- USER DATA WEIGHTS
-- =============================================================================
CREATE TABLE studio_user_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) UNIQUE NOT NULL,

    -- Weight configuration (JSON for flexibility)
    weights JSONB DEFAULT '{
        "preset": "balanced",
        "departments": {},
        "recency": {
            "enabled": true,
            "last_30_days": 1.5,
            "last_year": 1.0,
            "older": 0.7
        },
        "source_types": {
            "enabled": true,
            "pdf": 1.0,
            "video": 0.9,
            "audio": 0.85,
            "web": 0.8,
            "notes": 0.7
        },
        "confidence": {
            "enabled": true,
            "high": 1.2,
            "medium": 1.0,
            "low": 0.8
        },
        "verified": {
            "enabled": true,
            "weight": 1.5
        }
    }',

    -- Pinned and muted documents
    pinned_document_ids UUID[] DEFAULT '{}',
    muted_document_ids UUID[] DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_weights_user ON studio_user_weights(user_id);

-- =============================================================================
-- GENERATED ASSETS (5 Types)
-- =============================================================================
CREATE TABLE studio_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,

    -- Asset identification
    asset_type TEXT NOT NULL CHECK (asset_type IN ('skill', 'command', 'agent', 'prompt', 'workflow')),
    department TEXT NOT NULL,  -- One of 12 departments
    name TEXT NOT NULL,
    title TEXT NOT NULL,  -- Human-readable title

    -- Content
    content TEXT NOT NULL,  -- YAML, MD, or JSON depending on type
    format TEXT NOT NULL CHECK (format IN ('yaml', 'md', 'json')),

    -- Status
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),

    -- Source tracking
    source_document_id UUID,
    source_document_title TEXT,

    -- Classification metadata (from AGENT-001)
    classification_confidence NUMERIC(3,2),
    classification_reasoning TEXT,
    keywords_matched JSONB DEFAULT '[]',
    secondary_department TEXT,
    secondary_confidence NUMERIC(3,2),

    -- Asset decision metadata
    asset_decision_reasoning TEXT,

    -- Storage path (B2)
    storage_path TEXT,  -- crewai-suggestions/{type}/drafts/{name}.{format}

    -- Versioning
    version INTEGER DEFAULT 1,
    parent_version_id UUID REFERENCES studio_assets(id),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    published_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_assets_user ON studio_assets(user_id);
CREATE INDEX idx_assets_type ON studio_assets(asset_type);
CREATE INDEX idx_assets_department ON studio_assets(department);
CREATE INDEX idx_assets_status ON studio_assets(status);
CREATE INDEX idx_assets_created ON studio_assets(created_at DESC);

-- Full-text search index for assets
CREATE INDEX idx_assets_search ON studio_assets USING gin(
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
);

-- =============================================================================
-- CONTENT CLASSIFICATIONS
-- =============================================================================
CREATE TABLE studio_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,

    -- Source content
    document_id UUID,  -- Reference to documents_v2
    content_hash TEXT,  -- For deduplication
    filename TEXT,
    content_preview TEXT,  -- First 500 chars

    -- Primary classification
    department TEXT NOT NULL,
    confidence NUMERIC(3,2) NOT NULL,
    reasoning TEXT,
    keywords_matched JSONB DEFAULT '[]',

    -- Secondary classification
    secondary_department TEXT,
    secondary_confidence NUMERIC(3,2),

    -- User corrections
    user_corrected_department TEXT,
    correction_reason TEXT,
    corrected_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_classifications_user ON studio_classifications(user_id);
CREATE INDEX idx_classifications_department ON studio_classifications(department);
CREATE INDEX idx_classifications_confidence ON studio_classifications(confidence);
CREATE INDEX idx_classifications_corrected ON studio_classifications(user_corrected_department)
    WHERE user_corrected_department IS NOT NULL;

-- =============================================================================
-- RLS POLICIES
-- =============================================================================
ALTER TABLE studio_cko_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_cko_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_user_weights ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE studio_classifications ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users can access own CKO sessions" ON studio_cko_sessions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can access own CKO messages" ON studio_cko_messages
    FOR ALL USING (session_id IN (
        SELECT id FROM studio_cko_sessions WHERE user_id = auth.uid()
    ));

CREATE POLICY "Users can access own weights" ON studio_user_weights
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can access own assets" ON studio_assets
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can access own classifications" ON studio_classifications
    FOR ALL USING (auth.uid() = user_id);
```

### 3.2 Data Flow Diagrams

#### CKO Conversation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CKO CONVERSATION FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

User Message                    CKO Processing                      Response
    │                               │                                   │
    ▼                               │                                   │
┌─────────┐                         │                                   │
│ "What   │                         │                                   │
│ are you │────────────────────────▶│                                   │
│ unsure  │                         ▼                                   │
│ about?" │                   ┌───────────┐                             │
└─────────┘                   │ CKO       │                             │
                              │ Service   │                             │
                              └─────┬─────┘                             │
                                    │                                   │
                    ┌───────────────┼───────────────┐                   │
                    ▼               ▼               ▼                   │
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │
            │ Query       │ │ Check       │ │ Get User    │             │
            │ Pending     │ │ Low         │ │ Weights     │             │
            │ Clarify     │ │ Confidence  │ │             │             │
            └──────┬──────┘ └──────┬──────┘ └──────┬──────┘             │
                   │               │               │                    │
                   └───────────────┼───────────────┘                    │
                                   ▼                                    │
                           ┌─────────────┐                              │
                           │ AGENT-001   │                              │
                           │ Orchestrate │                              │
                           └──────┬──────┘                              │
                                  │                                     │
                                  ▼                                     │
                           ┌─────────────┐                              │
                           │ Generate    │                              │
                           │ CKO         │──────────────────────────────▶
                           │ Response    │                              │
                           └─────────────┘                        ┌─────────┐
                                                                  │ "I have │
                                                                  │ 2 items │
                                                                  │ that    │
                                                                  │ need    │
                                                                  │ input:" │
                                                                  │ [yellow]│
                                                                  └─────────┘
```

#### Data Weights Application Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA WEIGHTS APPLICATION                             │
└─────────────────────────────────────────────────────────────────────────────┘

User Query                Weights Service                RAG Service
    │                           │                            │
    ▼                           │                            │
┌─────────┐                     │                            │
│ "What's │                     │                            │
│ our     │─────────────────────▶                            │
│ sales   │                     │                            │
│ process │                     ▼                            │
│ ?"      │              ┌─────────────┐                     │
└─────────┘              │ Get User    │                     │
                         │ Weights     │                     │
                         └──────┬──────┘                     │
                                │                            │
                         ┌──────▼──────┐                     │
                         │ Weights:    │                     │
                         │ • Sales: 2x │                     │
                         │ • Recent:1.5│                     │
                         │ • Pin: doc1 │                     │
                         └──────┬──────┘                     │
                                │                            │
                                └────────────────────────────▶
                                                             │
                                                      ┌──────▼──────┐
                                                      │ Vector      │
                                                      │ Search +    │
                                                      │ Weighted    │
                                                      │ Reranking   │
                                                      └──────┬──────┘
                                                             │
                                Results weighted by:         │
                                • Department boost (Sales 2x)│
                                • Recency (newer = 1.5x)     │
                                • Pinned (always include)    │
                                • Muted (excluded)           │
                                                             ▼
                                                      ┌─────────────┐
                                                      │ Weighted    │
                                                      │ Context for │
                                                      │ LLM         │
                                                      └─────────────┘
```

#### Clarification Resolution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLARIFICATION RESOLUTION FLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

Document Upload                AGENT-001                    CKO Interface
      │                            │                             │
      ▼                            │                             │
 ┌─────────┐                       │                             │
 │ Upload  │───────────────────────▶                             │
 │ PDF     │                       ▼                             │
 └─────────┘                ┌─────────────┐                      │
                            │ Classify    │                      │
                            │ Content     │                      │
                            └──────┬──────┘                      │
                                   │                             │
                            ┌──────▼──────┐                      │
                            │ Confidence  │                      │
                            │ = 68%       │                      │
                            │ (Low)       │                      │
                            └──────┬──────┘                      │
                                   │                             │
                                   │ Create clarification        │
                                   │ record                      │
                                   │                             │
                                   └─────────────────────────────▶
                                                                 │
                                                          ┌──────▼──────┐
                                                          │ [Yellow]    │
                                                          │ "Is this IT │
                                                          │ or Ops?"    │
                                                          │             │
                                                          │ [IT] [Ops]  │
                                                          └──────┬──────┘
                                                                 │
User Response: "IT"                                              │
      │                                                          │
      └──────────────────────────────────────────────────────────┘
                                   │
                            ┌──────▼──────┐
                            │ Update      │
                            │ Classification│
                            │ to IT       │
                            └──────┬──────┘
                                   │
                            ┌──────▼──────┐
                            │ Mark        │
                            │ clarification│
                            │ resolved    │
                            └──────┬──────┘
                                   │
                                   ▼
                            ┌─────────────┐
                            │ Update      │
                            │ CKO memory  │
                            │ (prefer IT) │
                            └─────────────┘
```

---

## 4. API Design

### 4.1 CKO Endpoints

```yaml
/api/studio/cko:
  /message:
    POST:
      summary: Send message to CKO
      request:
        session_id: UUID (optional, creates new if omitted)
        content: string
        attachments: [UUID] (optional document IDs)
      response:
        session_id: UUID
        message_id: UUID
        content: string (streamed via WebSocket)
        is_clarification: boolean
        clarification_type: string (if clarification)
        sources: [{doc_id, title, snippet}]
        actions_available: [{action, params}]

  /sessions:
    GET:
      summary: List CKO sessions
      params:
        limit: int (default 20)
        offset: int (default 0)
      response:
        sessions: [{id, title, message_count, pending_clarifications, updated_at}]
        total: int

    POST:
      summary: Create new CKO session
      response:
        session: {id, title, created_at}

  /sessions/{session_id}:
    GET:
      summary: Get session with messages
      response:
        session: {id, title, message_count, pending_clarifications}
        messages: [{id, role, content, is_clarification, sources, created_at}]

    DELETE:
      summary: Delete session

  /sessions/{session_id}/messages/{message_id}/rate:
    POST:
      summary: Rate a CKO response
      request:
        rating: int (-1, 0, 1)
        feedback_text: string (optional)

  /pending:
    GET:
      summary: Get pending clarifications count
      response:
        count: int
        clarifications: [{session_id, message_id, type, preview}]

  /respond:
    POST:
      summary: Respond to clarification
      request:
        message_id: UUID
        response: string
        skip: boolean (use CKO's best guess)
      response:
        cko_reply: string
        action_taken: string

  /actions:
    POST:
      summary: Execute CKO action
      request:
        action: string (reclassify, update_weight, pin_doc, etc.)
        params: object
      response:
        success: boolean
        result: object
        cko_confirmation: string

WebSocket:
  /ws/studio/cko:
    description: Real-time CKO response streaming
    events:
      - message_start: {message_id}
      - content_delta: {delta}
      - message_end: {message_id, full_content}
      - clarification: {type, options}
      - action_result: {action, result}
```

### 4.2 Data Weights Endpoints

```yaml
/api/studio/weights:
  GET:
    summary: Get current weight configuration
    response:
      preset: string
      departments: {dept: weight}
      recency: {enabled, last_30_days, last_year, older}
      source_types: {enabled, pdf, video, audio, web, notes}
      confidence: {enabled, high, medium, low}
      verified: {enabled, weight}
      pinned_documents: [UUID]
      muted_documents: [UUID]

  PATCH:
    summary: Update weights
    request:
      preset: string (optional)
      departments: {dept: weight} (optional)
      recency: {...} (optional)
      source_types: {...} (optional)
    response:
      weights: {...}
      cko_acknowledgment: string

  /presets:
    GET:
      summary: List available presets
      response:
        presets: [{name, description, config}]

  /preview:
    POST:
      summary: Preview how weights affect a query
      request:
        query: string
        proposed_weights: object
      response:
        current_results: [{doc_id, score}]
        proposed_results: [{doc_id, score}]
        differences: [{doc_id, current_rank, proposed_rank}]

/api/studio/documents/{doc_id}:
  /pin:
    POST:
      summary: Pin a document
      response:
        pinned: true
        cko_confirmation: string

    DELETE:
      summary: Unpin a document

  /mute:
    POST:
      summary: Mute a document
      response:
        muted: true

    DELETE:
      summary: Unmute a document
```

### 4.3 Assets Endpoints

```yaml
/api/studio/assets:
  GET:
    summary: List assets
    params:
      type: string (skill, command, agent, prompt, workflow)
      department: string
      status: string (draft, published, archived)
      search: string
      limit: int
      offset: int
    response:
      assets: [{id, type, department, title, status, created_at}]
      total: int

  POST:
    summary: Create asset manually
    request:
      type: string
      department: string
      title: string
      content: string
    response:
      asset: {...}

  /{asset_id}:
    GET:
      summary: Get asset details
      response:
        asset: {id, type, department, title, content, format, status,
                source_document, classification_confidence, reasoning,
                version, created_at, updated_at}
        versions: [{version, created_at}]

    PATCH:
      summary: Update asset
      request:
        title: string (optional)
        content: string (optional)
        department: string (optional)
      response:
        asset: {...}
        version: int (incremented)

    DELETE:
      summary: Delete asset

  /{asset_id}/publish:
    POST:
      summary: Publish draft asset
      response:
        asset: {...}
        storage_path: string

  /{asset_id}/archive:
    POST:
      summary: Archive asset

  /{asset_id}/reclassify:
    POST:
      summary: Change asset type
      request:
        new_type: string
      response:
        asset: {...}
        old_type: string
        new_type: string
```

### 4.4 Classifications Endpoints

```yaml
/api/studio/classifications:
  GET:
    summary: List classifications
    params:
      department: string
      confidence_min: float
      confidence_max: float
      corrected: boolean
      limit: int
      offset: int
    response:
      classifications: [{id, filename, department, confidence,
                         secondary_department, corrected, created_at}]
      total: int

  /{classification_id}:
    GET:
      summary: Get classification details
      response:
        classification: {id, document_id, filename, content_preview,
                         department, confidence, reasoning, keywords_matched,
                         secondary_department, secondary_confidence,
                         user_corrected_department, correction_reason}

    PATCH:
      summary: Correct classification
      request:
        new_department: string
        reason: string (optional)
      response:
        classification: {...}
        cko_acknowledgment: string

  /stats:
    GET:
      summary: Classification statistics
      response:
        total: int
        by_department: {dept: count}
        avg_confidence: float
        correction_rate: float
        accuracy_trend: [{date, accuracy}]
```

### 4.5 Search Endpoints

```yaml
/api/studio/search:
  GET:
    summary: Global search
    params:
      q: string
      type: string (conversation, asset, document, classification)
      department: string
      date_from: datetime
      date_to: datetime
      limit: int
    response:
      results: [{type, id, title, snippet, score, created_at}]
      total: int
      facets: {type: count, department: count}

  /suggestions:
    GET:
      summary: Search suggestions
      params:
        q: string (partial query)
      response:
        suggestions: [string]

  /recent:
    GET:
      summary: Recent searches
      response:
        searches: [{query, timestamp}]
```

---

## 5. CKO Implementation Details

### 5.1 CKO Persona Layer

The CKO is implemented as a persona layer on top of AGENT-001 (Master Orchestrator).

```python
# app/services/cko_service.py

class CKOService:
    """
    Chief Knowledge Officer - Intelligent KB Persona

    The CKO is the face of AGENT-001, providing:
    - Conversational interface
    - Proactive insights
    - Natural clarifications
    - Weight-aware responses
    """

    CKO_SYSTEM_PROMPT = """
    You are the Chief Knowledge Officer (CKO) for this user's knowledge base.

    Your role:
    - You MANAGE the knowledge base, you don't just query it
    - You KNOW the content - reference specific documents by name
    - You PROACTIVELY share insights, conflicts, and recommendations
    - You ASK for clarification when confidence is low (<70%)
    - You EXPLAIN your reasoning when asked
    - You RESPECT the user's data weights and priorities
    - You REMEMBER past conversations and corrections

    Your tone:
    - Professional but approachable
    - Confident about what you know
    - Honest about uncertainty
    - Proactive, not just reactive

    Current KB Stats:
    - {doc_count} documents across {dept_count} departments
    - {asset_count} generated assets
    - {pending_count} items needing user input

    User's Data Weights:
    {weights_summary}

    Recent Corrections (learn from these):
    {recent_corrections}
    """

    async def process_message(
        self,
        user_id: UUID,
        session_id: Optional[UUID],
        content: str
    ) -> AsyncGenerator[CKOResponseChunk, None]:
        """Process user message and stream CKO response."""

        # Get or create session
        session = await self._get_or_create_session(user_id, session_id)

        # Get user context
        weights = await self.weights_service.get_user_weights(user_id)
        kb_stats = await self._get_kb_stats(user_id)
        recent_corrections = await self._get_recent_corrections(user_id)
        pending = await self.clarification_service.get_pending(user_id)

        # Build CKO system prompt with context
        system_prompt = self._build_system_prompt(
            kb_stats, weights, recent_corrections, pending
        )

        # Check if this is a clarification response
        if await self._is_clarification_response(session_id, content):
            async for chunk in self._handle_clarification_response(
                session_id, content
            ):
                yield chunk
            return

        # Determine query intent
        intent = await self._analyze_intent(content)

        # Process based on intent
        if intent.type == "question":
            async for chunk in self._answer_question(
                user_id, content, weights, system_prompt
            ):
                yield chunk

        elif intent.type == "action":
            async for chunk in self._execute_action(
                user_id, content, intent.action, intent.params
            ):
                yield chunk

        elif intent.type == "meta":  # Questions about CKO itself
            async for chunk in self._answer_meta_question(
                user_id, content, kb_stats, pending
            ):
                yield chunk

    async def _answer_question(
        self,
        user_id: UUID,
        question: str,
        weights: UserWeights,
        system_prompt: str
    ) -> AsyncGenerator[CKOResponseChunk, None]:
        """Answer a knowledge base question with weight awareness."""

        # Apply weights to retrieval
        weighted_context = await self._get_weighted_context(
            user_id, question, weights
        )

        # Check if we need clarification
        if weighted_context.needs_clarification:
            yield CKOResponseChunk(
                type="clarification",
                content=weighted_context.clarification_question,
                clarification_type=weighted_context.clarification_type,
                options=weighted_context.clarification_options
            )
            return

        # Generate response via AGENT-001 with CKO persona
        async for chunk in self.orchestrator.generate_response(
            question=question,
            context=weighted_context.documents,
            system_prompt=system_prompt,
            stream=True
        ):
            yield CKOResponseChunk(
                type="content",
                content=chunk.content,
                sources=chunk.sources
            )
```

### 5.2 Clarification Detection

```python
# app/services/cko_clarification_service.py

class CKOClarificationService:
    """Manages CKO clarification requests and responses."""

    CLARIFICATION_TRIGGERS = {
        "classification": {
            "confidence_threshold": 0.70,
            "template": "I classified '{filename}' as {dept} ({confidence}% confidence), "
                       "but it also matches {secondary_dept} ({secondary_conf}%). "
                       "Which fits better?",
            "options_generator": lambda c: [c.department, c.secondary_department]
        },
        "asset_type": {
            "confidence_threshold": 0.75,
            "template": "This content could become a {type1} or a {type2}. "
                       "Which would be more useful to you?",
            "options_generator": lambda c: [c.type1, c.type2]
        },
        "conflict": {
            "template": "I found conflicting information. {doc1} says '{claim1}', "
                       "but {doc2} says '{claim2}'. Which is correct?",
            "options_generator": lambda c: [c.doc1, c.doc2, "Both valid"]
        },
        "sensitive": {
            "template": "This document appears to contain {sensitive_type}. "
                       "Should I process it with extra privacy protections?",
            "options_generator": lambda c: ["Yes, protect", "No, process normally", "Skip entirely"]
        },
        "department": {
            "confidence_threshold": 0.60,
            "template": "This content spans {dept1} and {dept2} equally. "
                       "Should I classify it as one, or keep it in Global?",
            "options_generator": lambda c: [c.dept1, c.dept2, "Global"]
        }
    }

    async def check_for_clarification_need(
        self,
        classification_result: ClassificationResult
    ) -> Optional[Clarification]:
        """Check if classification result needs user clarification."""

        # Check confidence threshold
        if classification_result.confidence < 0.70:
            return Clarification(
                type="classification",
                message=self._format_clarification_message(
                    "classification", classification_result
                ),
                options=self.CLARIFICATION_TRIGGERS["classification"]["options_generator"](
                    classification_result
                ),
                metadata={
                    "document_id": classification_result.document_id,
                    "current_classification": classification_result.department
                }
            )

        # Check for close secondary match
        if (classification_result.secondary_confidence and
            classification_result.confidence - classification_result.secondary_confidence < 0.20):
            return Clarification(
                type="department",
                message=self._format_clarification_message(
                    "department", classification_result
                ),
                options=self.CLARIFICATION_TRIGGERS["department"]["options_generator"](
                    classification_result
                ),
                metadata={...}
            )

        return None

    async def get_pending_count(self, user_id: UUID) -> int:
        """Get count of pending clarifications for badge."""
        result = await self.db.execute(
            """
            SELECT COUNT(*) FROM studio_cko_messages
            WHERE session_id IN (
                SELECT id FROM studio_cko_sessions WHERE user_id = $1
            )
            AND is_clarification = true
            AND clarification_status = 'pending'
            """,
            [user_id]
        )
        return result.scalar()
```

### 5.3 Weight Application

```python
# app/services/cko_weights_service.py

class CKOWeightsService:
    """Manages and applies user data weights to queries."""

    DEFAULT_WEIGHTS = {
        "preset": "balanced",
        "departments": {},  # Empty = all equal at 1.0
        "recency": {
            "enabled": True,
            "last_30_days": 1.5,
            "last_year": 1.0,
            "older": 0.7
        },
        "source_types": {
            "enabled": True,
            "pdf": 1.0,
            "video": 0.9,
            "audio": 0.85,
            "web": 0.8,
            "notes": 0.7
        },
        "confidence": {
            "enabled": True,
            "high": 1.2,  # >90%
            "medium": 1.0,  # 70-90%
            "low": 0.8  # <70%
        },
        "verified": {
            "enabled": True,
            "weight": 1.5
        }
    }

    PRESETS = {
        "balanced": DEFAULT_WEIGHTS,
        "recent_focus": {
            **DEFAULT_WEIGHTS,
            "recency": {
                "enabled": True,
                "last_30_days": 2.0,
                "last_year": 1.0,
                "older": 0.5
            }
        },
        "verified_only": {
            **DEFAULT_WEIGHTS,
            "confidence": {
                "enabled": True,
                "high": 2.0,
                "medium": 1.0,
                "low": 0.3
            },
            "verified": {
                "enabled": True,
                "weight": 3.0
            }
        }
    }

    async def apply_weights_to_retrieval(
        self,
        user_id: UUID,
        base_results: List[RetrievalResult],
    ) -> List[WeightedResult]:
        """Apply user weights to rerank retrieval results."""

        weights = await self.get_user_weights(user_id)
        pinned = await self._get_pinned_documents(user_id)
        muted = await self._get_muted_documents(user_id)

        weighted_results = []

        for result in base_results:
            # Skip muted documents
            if result.document_id in muted:
                continue

            # Calculate weight multiplier
            multiplier = 1.0

            # Department weight
            dept_weight = weights.departments.get(result.department, 1.0)
            multiplier *= dept_weight

            # Recency weight
            if weights.recency["enabled"]:
                age_days = (datetime.now() - result.created_at).days
                if age_days <= 30:
                    multiplier *= weights.recency["last_30_days"]
                elif age_days <= 365:
                    multiplier *= weights.recency["last_year"]
                else:
                    multiplier *= weights.recency["older"]

            # Source type weight
            if weights.source_types["enabled"]:
                source_weight = weights.source_types.get(result.source_type, 1.0)
                multiplier *= source_weight

            # Confidence weight
            if weights.confidence["enabled"]:
                if result.classification_confidence > 0.9:
                    multiplier *= weights.confidence["high"]
                elif result.classification_confidence > 0.7:
                    multiplier *= weights.confidence["medium"]
                else:
                    multiplier *= weights.confidence["low"]

            # Verified weight
            if weights.verified["enabled"] and result.is_verified:
                multiplier *= weights.verified["weight"]

            # Pinned document bonus
            if result.document_id in pinned:
                multiplier *= 2.0  # Always boost pinned

            weighted_results.append(WeightedResult(
                **result.dict(),
                weight_multiplier=multiplier,
                weighted_score=result.similarity_score * multiplier
            ))

        # Sort by weighted score
        weighted_results.sort(key=lambda x: x.weighted_score, reverse=True)

        return weighted_results
```

---

## 6. Notification System

### 6.1 Badge Count Implementation

```typescript
// empire-desktop/src/components/studio/NotificationBadge.tsx

interface NotificationBadgeProps {
  count: number;
  isOverdue?: boolean;  // >24 hours pending
}

export const NotificationBadge: React.FC<NotificationBadgeProps> = ({
  count,
  isOverdue
}) => {
  if (count === 0) return null;

  return (
    <div className={cn(
      "absolute -top-1 -right-1 flex items-center justify-center",
      "min-w-[18px] h-[18px] rounded-full text-xs font-medium",
      isOverdue
        ? "bg-red-500 text-white"  // Red for overdue
        : "bg-yellow-400 text-gray-900"  // Yellow for pending
    )}>
      {count > 9 ? "9+" : count}
    </div>
  );
};

// Navigation item with badge
export const AIStudioNavItem: React.FC = () => {
  const { pendingCount, hasOverdue } = useCKOPending();

  return (
    <NavLink to="/studio" className="relative">
      <BrainIcon className="w-5 h-5" />
      <span>AI Studio</span>
      <NotificationBadge count={pendingCount} isOverdue={hasOverdue} />
    </NavLink>
  );
};
```

### 6.2 Polling Hook

```typescript
// empire-desktop/src/hooks/studio/useCKOPending.ts

export const useCKOPending = () => {
  const [pendingCount, setPendingCount] = useState(0);
  const [hasOverdue, setHasOverdue] = useState(false);

  useEffect(() => {
    const fetchPending = async () => {
      try {
        const response = await studioApi.cko.getPending();
        setPendingCount(response.count);

        // Check if any are overdue (>24 hours)
        const now = new Date();
        const overdue = response.clarifications.some(c => {
          const age = now.getTime() - new Date(c.created_at).getTime();
          return age > 24 * 60 * 60 * 1000;  // 24 hours
        });
        setHasOverdue(overdue);
      } catch (error) {
        console.error('Failed to fetch pending count:', error);
      }
    };

    // Initial fetch
    fetchPending();

    // Poll every 30 seconds
    const interval = setInterval(fetchPending, 30000);

    return () => clearInterval(interval);
  }, []);

  return { pendingCount, hasOverdue };
};
```

---

## 7. Search Architecture

### 7.1 Search Service

```python
# app/services/studio_search_service.py

class StudioSearchService:
    """Global search across AI Studio content."""

    async def search(
        self,
        user_id: UUID,
        query: str,
        types: Optional[List[str]] = None,  # conversation, asset, document, classification
        department: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 20
    ) -> SearchResults:
        """
        Unified search across all AI Studio content.

        Uses PostgreSQL full-text search + pgvector similarity.
        """

        results = []

        # Search CKO conversations
        if not types or "conversation" in types:
            conversations = await self._search_conversations(
                user_id, query, date_from, date_to, limit
            )
            results.extend(conversations)

        # Search assets
        if not types or "asset" in types:
            assets = await self._search_assets(
                user_id, query, department, date_from, date_to, limit
            )
            results.extend(assets)

        # Search documents
        if not types or "document" in types:
            documents = await self._search_documents(
                user_id, query, department, date_from, date_to, limit
            )
            results.extend(documents)

        # Search classifications
        if not types or "classification" in types:
            classifications = await self._search_classifications(
                user_id, query, department, date_from, date_to, limit
            )
            results.extend(classifications)

        # Sort by relevance score
        results.sort(key=lambda x: x.score, reverse=True)

        # Build facets
        facets = self._build_facets(results)

        return SearchResults(
            results=results[:limit],
            total=len(results),
            facets=facets
        )

    async def _search_conversations(
        self,
        user_id: UUID,
        query: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int
    ) -> List[SearchResult]:
        """Search CKO conversation messages."""

        sql = """
            SELECT
                m.id,
                s.id as session_id,
                s.title as session_title,
                m.content,
                m.created_at,
                ts_rank(to_tsvector('english', m.content), plainto_tsquery('english', $2)) as score
            FROM studio_cko_messages m
            JOIN studio_cko_sessions s ON m.session_id = s.id
            WHERE s.user_id = $1
            AND to_tsvector('english', m.content) @@ plainto_tsquery('english', $2)
            AND ($3::timestamptz IS NULL OR m.created_at >= $3)
            AND ($4::timestamptz IS NULL OR m.created_at <= $4)
            ORDER BY score DESC
            LIMIT $5
        """

        rows = await self.db.fetch(sql, user_id, query, date_from, date_to, limit)

        return [
            SearchResult(
                type="conversation",
                id=row["id"],
                title=row["session_title"] or "CKO Conversation",
                snippet=self._extract_snippet(row["content"], query),
                score=row["score"],
                created_at=row["created_at"],
                metadata={"session_id": row["session_id"]}
            )
            for row in rows
        ]

    async def _search_assets(
        self,
        user_id: UUID,
        query: str,
        department: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int
    ) -> List[SearchResult]:
        """Search generated assets."""

        sql = """
            SELECT
                id,
                asset_type,
                department,
                title,
                content,
                created_at,
                ts_rank(
                    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')),
                    plainto_tsquery('english', $2)
                ) as score
            FROM studio_assets
            WHERE user_id = $1
            AND to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
                @@ plainto_tsquery('english', $2)
            AND ($3::text IS NULL OR department = $3)
            AND ($4::timestamptz IS NULL OR created_at >= $4)
            AND ($5::timestamptz IS NULL OR created_at <= $5)
            ORDER BY score DESC
            LIMIT $6
        """

        rows = await self.db.fetch(
            sql, user_id, query, department, date_from, date_to, limit
        )

        return [
            SearchResult(
                type="asset",
                id=row["id"],
                title=row["title"],
                snippet=self._extract_snippet(row["content"], query),
                score=row["score"],
                created_at=row["created_at"],
                metadata={
                    "asset_type": row["asset_type"],
                    "department": row["department"]
                }
            )
            for row in rows
        ]
```

---

## 8. Frontend State Management

### 8.1 CKO Store

```typescript
// empire-desktop/src/stores/studio/ckoStore.ts

interface CKOState {
  // Session state
  currentSession: CKOSession | null;
  sessions: CKOSession[];

  // Messages
  messages: CKOMessage[];
  isStreaming: boolean;

  // Clarifications
  pendingClarifications: Clarification[];
  pendingCount: number;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  respondToClarification: (messageId: string, response: string) => Promise<void>;
  skipClarification: (messageId: string) => Promise<void>;
  createSession: () => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  rateMessage: (messageId: string, rating: number) => Promise<void>;
}

export const useCKOStore = create<CKOState>((set, get) => ({
  currentSession: null,
  sessions: [],
  messages: [],
  isStreaming: false,
  pendingClarifications: [],
  pendingCount: 0,

  sendMessage: async (content: string) => {
    const { currentSession } = get();

    // Add user message immediately
    const userMessage: CKOMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      createdAt: new Date().toISOString()
    };

    set(state => ({
      messages: [...state.messages, userMessage],
      isStreaming: true
    }));

    try {
      // Stream CKO response via WebSocket
      const ws = new WebSocket(`${WS_URL}/ws/studio/cko`);

      ws.onopen = () => {
        ws.send(JSON.stringify({
          session_id: currentSession?.id,
          content
        }));
      };

      let ckoMessage: Partial<CKOMessage> = {
        id: crypto.randomUUID(),
        role: 'cko',
        content: '',
        createdAt: new Date().toISOString()
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'content_delta') {
          ckoMessage.content += data.delta;
          set(state => ({
            messages: state.messages.map(m =>
              m.id === ckoMessage.id ? { ...m, content: ckoMessage.content } : m
            )
          }));
        }

        if (data.type === 'message_end') {
          ckoMessage = {
            ...ckoMessage,
            sources: data.sources,
            isClarification: data.is_clarification,
            clarificationType: data.clarification_type
          };

          set(state => ({
            messages: state.messages.map(m =>
              m.id === ckoMessage.id ? ckoMessage as CKOMessage : m
            ),
            isStreaming: false
          }));

          ws.close();
        }

        if (data.type === 'clarification') {
          // Add clarification message
          const clarificationMessage: CKOMessage = {
            id: crypto.randomUUID(),
            role: 'cko',
            content: data.content,
            isClarification: true,
            clarificationType: data.type,
            clarificationOptions: data.options,
            createdAt: new Date().toISOString()
          };

          set(state => ({
            messages: [...state.messages, clarificationMessage],
            pendingCount: state.pendingCount + 1
          }));
        }
      };

      // Add empty CKO message to show streaming
      set(state => ({
        messages: [...state.messages, ckoMessage as CKOMessage]
      }));

    } catch (error) {
      console.error('Failed to send message:', error);
      set({ isStreaming: false });
    }
  },

  respondToClarification: async (messageId: string, response: string) => {
    await studioApi.cko.respond(messageId, response);

    set(state => ({
      messages: state.messages.map(m =>
        m.id === messageId
          ? { ...m, clarificationStatus: 'answered', clarificationAnswer: response }
          : m
      ),
      pendingCount: state.pendingCount - 1
    }));
  },

  skipClarification: async (messageId: string) => {
    await studioApi.cko.respond(messageId, '', true);

    set(state => ({
      messages: state.messages.map(m =>
        m.id === messageId
          ? { ...m, clarificationStatus: 'skipped' }
          : m
      ),
      pendingCount: state.pendingCount - 1
    }));
  },

  // ... other actions
}));
```

---

## 9. Migration Strategy

### 9.1 Database Migrations

Migrations will be created in this order:

1. `001_create_studio_cko_sessions.sql`
2. `002_create_studio_cko_messages.sql`
3. `003_create_studio_user_weights.sql`
4. `004_create_studio_assets.sql`
5. `005_create_studio_classifications.sql`
6. `006_create_studio_indexes.sql`
7. `007_create_studio_rls_policies.sql`

### 9.2 Feature Flags

```python
# app/config.py

class FeatureFlags:
    AI_STUDIO_ENABLED = os.getenv("FEATURE_AI_STUDIO", "false").lower() == "true"
    CKO_CLARIFICATIONS_ENABLED = os.getenv("FEATURE_CKO_CLARIFICATIONS", "false").lower() == "true"
    DATA_WEIGHTS_ENABLED = os.getenv("FEATURE_DATA_WEIGHTS", "false").lower() == "true"
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

- `test_cko_service.py` - CKO response generation, intent detection
- `test_cko_weights_service.py` - Weight application, presets
- `test_cko_clarification_service.py` - Clarification detection, resolution
- `test_asset_management_service.py` - Asset CRUD, versioning
- `test_studio_search_service.py` - Search across types

### 10.2 Integration Tests

- `test_cko_conversation_flow.py` - Full conversation flow with clarifications
- `test_weighted_retrieval.py` - RAG with weights applied
- `test_studio_api.py` - All API endpoints

### 10.3 E2E Tests

- `test_ai_studio_e2e.py` - Full user journey in desktop app

---

## 11. Implementation Phases

### Phase 1: Foundation (Tasks 70-75)
1. Database migrations for all new tables
2. AI Studio navigation and routing
3. CKO service with basic conversation
4. WebSocket streaming setup
5. Basic feedback collection

### Phase 2: CKO Core (Tasks 76-80)
1. CKO persona implementation
2. Clarification detection and flow
3. Data weights service
4. Weight application to retrieval
5. Notification badge system

### Phase 3: Asset Management (Tasks 81-84)
1. Asset service implementation
2. Asset API endpoints
3. Asset frontend (list, detail, edit)
4. Asset versioning

### Phase 4: Classifications & Search (Tasks 85-88)
1. Classification service
2. Classification correction flow
3. Global search service
4. Search frontend (Cmd+K)

### Phase 5: Polish (Tasks 89-92)
1. Main chat CKO integration
2. Email notifications (optional)
3. Performance optimization
4. E2E testing

---

## 12. Dependencies

### New Python Packages
```
# No new packages required - uses existing:
# - anthropic (Claude API)
# - asyncpg (PostgreSQL)
# - redis (caching)
# - structlog (logging)
```

### Frontend Packages
```json
{
  "dependencies": {
    // No new packages - uses existing:
    // "zustand" (state)
    // "@tanstack/react-query" (data fetching)
    // "tailwindcss" (styling)
  }
}
```

---

## 13. Open Items

1. **CKO Name Customization**: Should users be able to rename CKO? (e.g., "Atlas", "Sage")
2. **Email Notifications**: Implement optional daily digest for pending clarifications?
3. **Multi-User**: How should CKO behave in team scenarios? Shared KB vs. personal views?
4. **CKO Memory Persistence**: How long to retain CKO conversation context?
5. **Weight Inheritance**: Should project-level weights override global weights?

---

**End of Architecture Plan**
