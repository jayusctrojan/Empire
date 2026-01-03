# Empire v7.5 - Desktop App Product Requirements Document

**Version:** v7.5.0
**Created:** 2025-01-02
**Author:** Jay Bajaj
**Status:** Draft - Requirements Gathering

---

## Executive Summary

Empire v7.5 introduces **Empire Desktop** - a native macOS/Windows desktop application for interacting with your personal knowledge base. Inspired by Claude Desktop's UI/UX, Empire Desktop provides organized chat history, project-based knowledge organization, and seamless integration with the existing Empire v7.3 backend infrastructure.

### Vision
Transform Empire from a web-based document processing system into a **personal AI knowledge companion** with persistent memory, organized projects, and intuitive desktop experience.

---

## Goals & Objectives

### Primary Goals
1. **Organized Knowledge Access** - Chat with your knowledge base through organized projects
2. **Persistent Chat History** - Never lose a conversation; searchable history across all chats
3. **Project-Based Organization** - Group related documents, conversations, and context by project
4. **Native Desktop Experience** - Fast, always-available app (not browser-dependent)
5. **Offline Capability** - View history and cached content offline

### Success Metrics
| Metric | Target |
|--------|--------|
| Daily Active Usage | 5+ sessions/day |
| Chat Response Time | <3 seconds |
| History Search Speed | <500ms |
| App Launch Time | <2 seconds |
| Offline History Access | 100% of past chats |

---

## User Stories

### As a knowledge worker, I want to...
1. **Chat with my documents** - Ask questions about uploaded PDFs, notes, and web content
2. **Organize by project** - Keep work projects separate from personal learning
3. **Search past conversations** - Find that answer I got 3 weeks ago
4. **Continue conversations** - Pick up where I left off
5. **Attach files mid-chat** - Add context during a conversation
6. **See sources** - Know which documents informed each answer

### As a power user, I want to...
1. **Create project templates** - Reuse project structures
2. **Set project instructions** - Customize AI behavior per project
3. **Upload project files** - Maintain reference documents per project
4. **Export conversations** - Share or backup important chats
5. **Keyboard shortcuts** - Navigate without mouse

---

## Feature Requirements

### 1. Chat Interface (Core)

#### 1.1 Main Chat View
**Priority:** P0 (Must Have)

| Feature | Description | Claude Desktop Reference |
|---------|-------------|-------------------------|
| Chat Input | Multi-line text input with attachment button | Bottom input bar |
| Message Display | User/AI messages with timestamps | Main chat area |
| Streaming Responses | Real-time token streaming | Live response rendering |
| Source Citations | Inline [1], [2] citations with expandable sources | Empire v7.3 existing feature |
| File Attachments | Drag-drop or click to attach files | "+" button in input |
| Model Indicator | Show which AI model is responding | "Opus 4.5" selector |

#### 1.2 Chat Features
**Priority:** P0

- **New Chat** - Start fresh conversation
- **Continue Chat** - Resume previous conversation with full context
- **Regenerate Response** - Re-run last query
- **Copy Response** - Copy AI response to clipboard
- **Edit Message** - Edit and re-submit user message
- **Delete Message** - Remove message from history

#### 1.3 Quick Actions
**Priority:** P1 (Should Have)

Customizable quick action buttons (like Claude's "Code", "Learn", "Strategize", "Write"):
- **Summarize** - Summarize selected text or document
- **Analyze** - Deep analysis with multi-agent workflow
- **Research** - Web + knowledge base search
- **Write** - Generate content based on knowledge base
- **Compare** - Compare multiple documents

---

### 2. Projects System

#### 2.1 Project Management
**Priority:** P0

| Feature | Description |
|---------|-------------|
| Create Project | Name, description, optional template |
| Project List | Grid/list view of all projects with search |
| Project Settings | Instructions, model preferences, file management |
| Delete/Archive Project | Soft delete with recovery option |
| Project Templates | Save and reuse project configurations |

#### 2.2 Project Components (Per Claude Desktop)

**Memory** (Priority: P1)
- Project-specific context that persists across conversations
- Auto-generated from conversations or manually edited
- "Purpose & context" summary
- Key facts and preferences learned

**Instructions** (Priority: P0)
- Custom system prompts per project
- Define AI behavior, tone, focus areas
- Example: "You are an expert in n8n automation software..."

**Files** (Priority: P0)
- Upload reference documents to project
- Supported: PDF, DOCX, TXT, MD, images
- Files automatically indexed into project's knowledge scope
- Synced with Empire backend (Supabase + Neo4j)

**Conversations** (Priority: P0)
- List of all chats within project
- Last message preview and timestamp
- Search within project conversations

#### 2.3 Project Types (Empire-Specific)

Map to Empire's 12 departments for auto-organization:
1. IT & Engineering
2. Sales & Marketing
3. Customer Support
4. Operations & HR & Supply Chain
5. Finance & Accounting
6. Project Management
7. Real Estate
8. Private Equity & M&A
9. Consulting
10. Personal & Continuing Education
11. Research & Development
12. Global (Cross-department)

---

### 3. Chat History & Search

#### 3.1 Sidebar Navigation
**Priority:** P0

| Section | Description |
|---------|-------------|
| New Chat | Start new conversation |
| Chats | Recent conversations (all projects) |
| Projects | Project list with drill-down |
| Artifacts | Generated content (reports, code, etc.) |

#### 3.2 Search Functionality
**Priority:** P0

- **Global Search** - Search across all chats and projects
- **Project Search** - Search within specific project
- **Filters** - By date, project, has-attachments, has-code
- **Search Results** - Show matching messages with context
- **Jump to Message** - Navigate directly to search result

#### 3.3 History Management
**Priority:** P1

- **Export Chat** - Markdown, PDF, or JSON
- **Delete Chat** - With confirmation
- **Archive Chat** - Move to archive (not in main view)
- **Bulk Operations** - Select multiple chats for delete/archive

---

### 4. Integration with Empire Backend

#### 4.1 API Integration
**Priority:** P0

Connect to existing Empire v7.3 endpoints:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/query/auto` | Main chat queries (auto-routed) |
| `POST /api/query/adaptive` | Complex queries with LangGraph |
| `WS /ws/chat` | Real-time streaming responses |
| `POST /api/documents/upload` | File uploads |
| `GET /api/documents` | List user's documents |
| `POST /api/summarizer/summarize` | Quick summarization |
| `POST /api/classifier/classify` | Auto-classify content |

#### 4.2 Authentication
**Priority:** P0

- **Clerk Integration** - Use existing Clerk auth
- **Token Management** - Secure JWT storage in system keychain
- **Auto-refresh** - Seamless token refresh
- **Multi-device** - Sync across devices via Empire backend

#### 4.3 Data Sync
**Priority:** P1

| Data | Storage | Sync Strategy |
|------|---------|---------------|
| Chat History | Local SQLite + Supabase | Real-time sync |
| Projects | Local SQLite + Supabase | Real-time sync |
| Files | Local cache + B2 | On-demand download |
| Settings | Local + Supabase | Sync on change |

---

### 5. Desktop-Specific Features

#### 5.1 Native Experience
**Priority:** P0

- **Menu Bar** - File, Edit, View, Window, Help menus
- **Keyboard Shortcuts**:
  - `Cmd+N` - New chat
  - `Cmd+Shift+N` - New project
  - `Cmd+K` - Quick search
  - `Cmd+,` - Settings
  - `Cmd+Enter` - Send message
  - `Cmd+Shift+C` - Copy last response
- **System Tray** - Quick access icon
- **Notifications** - Background task completion alerts

#### 5.2 Window Management
**Priority:** P1

- **Multiple Windows** - Open multiple chats side-by-side
- **Tabs** - Tab-based chat navigation (optional)
- **Window Restore** - Remember window position and size
- **Dark/Light Mode** - System preference or manual toggle

#### 5.3 Offline Mode
**Priority:** P2 (Nice to Have)

- **View History** - Read past conversations offline
- **Queue Messages** - Queue queries for when back online
- **Local Search** - Search cached content offline
- **Sync Indicator** - Show sync status

---

### 6. Settings & Preferences

#### 6.1 General Settings
**Priority:** P0

| Setting | Options |
|---------|---------|
| Theme | Light, Dark, System |
| Default Model | Claude Sonnet 4.5 (current), Haiku (fast) |
| Startup | Launch at login, start minimized |
| Notifications | Enable/disable, sound |

#### 6.2 Chat Settings
**Priority:** P1

| Setting | Options |
|---------|---------|
| Response Style | Concise, Detailed, Technical |
| Source Display | Inline, Expandable, Hidden |
| Auto-save | Every message, on close |
| History Retention | Forever, 1 year, 6 months, 30 days |

#### 6.3 Advanced Settings
**Priority:** P2

| Setting | Options |
|---------|---------|
| API Endpoint | Production, Local dev |
| Cache Size | Limit local storage |
| Debug Mode | Show API calls, timing |
| Export All Data | Full data export |

---

## Technical Architecture

### Desktop Framework

**Selected:** Tauri 2.0 (Rust + WebView)

| Aspect | Details |
|--------|---------|
| **Framework** | Tauri 2.0 |
| **Backend** | Rust (native macOS APIs) |
| **Frontend** | React 18 + TypeScript |
| **WebView** | WKWebView (native macOS) |
| **Binary Size** | ~10-15 MB (vs 150MB+ Electron) |
| **Memory** | ~50-100 MB (vs 300MB+ Electron) |

**Why Tauri over Electron:**
- Native macOS WebView (WKWebView) - no bundled Chromium
- Rust backend for performance-critical operations
- Smaller, faster, more native-feeling
- Built-in auto-updater support
- Strong security model

### Tech Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Empire Desktop                        │
├─────────────────────────────────────────────────────────┤
│  Frontend: React + TypeScript + TailwindCSS             │
│  Desktop: Tauri (Rust)                                  │
│  Local DB: SQLite (via Tauri)                          │
│  State: Zustand or Redux                               │
│  UI Components: shadcn/ui (matches dark theme)         │
├─────────────────────────────────────────────────────────┤
│                    Empire Backend (v7.3)                │
├─────────────────────────────────────────────────────────┤
│  API: FastAPI (https://jb-empire-api.onrender.com)     │
│  Auth: Clerk                                           │
│  Database: Supabase (PostgreSQL + pgvector)            │
│  Storage: Backblaze B2                                 │
│  Graph: Neo4j                                          │
└─────────────────────────────────────────────────────────┘
```

### Data Models

#### Local SQLite Schema

```sql
-- Projects
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    department TEXT,
    memory TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT  -- Supabase ID
);

-- Conversations
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

-- Messages
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    sources TEXT,  -- JSON array of source citations
    attachments TEXT,  -- JSON array of attachment metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

-- Project Files (metadata only, actual files in B2)
CREATE TABLE project_files (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    filename TEXT NOT NULL,
    file_type TEXT,
    size_bytes INTEGER,
    b2_path TEXT,
    document_id TEXT,  -- Empire document ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### API Integration Layer

```typescript
// services/empire-api.ts
interface EmpireAPI {
  // Chat
  query(message: string, context: ChatContext): AsyncGenerator<string>;

  // Projects
  createProject(project: ProjectCreate): Promise<Project>;
  getProjects(): Promise<Project[]>;
  updateProject(id: string, updates: ProjectUpdate): Promise<Project>;
  deleteProject(id: string): Promise<void>;

  // Documents
  uploadFile(file: File, projectId: string): Promise<Document>;
  getDocuments(projectId?: string): Promise<Document[]>;

  // History
  getConversations(projectId?: string): Promise<Conversation[]>;
  getMessages(conversationId: string): Promise<Message[]>;

  // Sync
  syncAll(): Promise<SyncResult>;
}
```

---

## UI/UX Design

### Color Scheme (Match Claude Desktop Dark Theme)

```css
:root {
  --bg-primary: #1a1a1a;
  --bg-secondary: #2d2d2d;
  --bg-tertiary: #3d3d3d;
  --text-primary: #ffffff;
  --text-secondary: #a0a0a0;
  --accent: #e07850;  /* Empire orange (like Claude's coral) */
  --border: #404040;
  --success: #4ade80;
  --warning: #fbbf24;
  --error: #f87171;
}
```

### Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│  [≡]  Empire                                    [─] [□] [×]  │
├──────────┬───────────────────────────────────────────────────┤
│          │                                                   │
│ + New    │     🌸 Afternoon, Jay                             │
│          │                                                   │
│ ─────────│     ┌─────────────────────────────────────────┐   │
│ Chats    │     │ How can I help you today?               │   │
│ Projects │     │                                    [↑]  │   │
│ Artifacts│     └─────────────────────────────────────────┘   │
│          │                                                   │
│ ─────────│     [Summarize] [Analyze] [Research] [Write]      │
│ Recents  │                                                   │
│ • Chat 1 │                                                   │
│ • Chat 2 │                                                   │
│ • Chat 3 │                                                   │
│          │                                                   │
└──────────┴───────────────────────────────────────────────────┘
```

### Key Screens

1. **Home/New Chat** - Greeting, quick actions, recent chats
2. **Chat View** - Message thread with input
3. **Projects List** - Grid of projects with search
4. **Project Detail** - Conversations, files, settings
5. **Settings** - App preferences
6. **Search Results** - Global search results

---

## Security Considerations

### Authentication
- JWT tokens stored in system keychain (not localStorage)
- Biometric unlock option (Touch ID / Windows Hello)
- Session timeout with re-authentication

### Data Protection
- Local SQLite encrypted at rest
- TLS 1.2+ for all API communication
- No sensitive data in logs

### Privacy
- Local-first: Chat history stored locally by default
- Optional cloud sync (user choice)
- Data export and deletion capabilities (GDPR compliance)

---

## Implementation Phases

### Phase 1: MVP (4-6 weeks)
- [ ] Tauri + React + TypeScript setup (macOS)
- [ ] Chat interface with Empire API integration
- [ ] Streaming responses with source citations
- [ ] Local SQLite storage
- [ ] Basic project creation
- [ ] Chat history sidebar
- [ ] DMG packaging for distribution

### Phase 2: Projects & MCP (4-6 weeks)
- [ ] Full project management (CRUD)
- [ ] Project instructions and memory
- [ ] File attachments to projects
- [ ] Cloud sync with Supabase
- [ ] Search functionality (global + project)
- [ ] MCP client foundation
- [ ] Supabase + Neo4j MCP integration

### Phase 3: Polish & Features (4-6 weeks)
- [ ] Full MCP server management UI
- [ ] Keyboard shortcuts
- [ ] Multiple windows/tabs
- [ ] Offline mode (view history)
- [ ] Export/import conversations
- [ ] Settings and preferences
- [ ] Auto-updates (Sparkle framework)

### Phase 4: Advanced (Future)
- [ ] Additional MCP servers (Chrome DevTools, Ref, TaskMaster)
- [ ] Custom MCP server support
- [ ] Advanced memory/context management
- [ ] Voice input (Whisper integration)

---

## Decisions Made

| Question | Decision |
|----------|----------|
| **Platform** | macOS only |
| **MCP Support** | Yes - full MCP server support |
| **Distribution** | Direct download (DMG) |
| **Branding** | Empire Desktop |
| **User Base** | Single user (personal use) |

---

## MCP (Model Context Protocol) Integration

### Overview
Empire Desktop will support MCP servers similar to Claude Desktop, allowing integration with external tools and services.

### Supported MCP Servers (Initial)

| MCP Server | Purpose | Priority |
|------------|---------|----------|
| **Supabase MCP** | Direct database queries | P0 |
| **Neo4j MCP** | Knowledge graph queries | P0 |
| **Chrome DevTools MCP** | Browser automation/debugging | P1 |
| **Ref MCP** | Documentation lookups | P1 |
| **TaskMaster MCP** | Task management | P2 |
| **Render MCP** | Deployment management | P2 |

### MCP Configuration

```json
// ~/.empire/mcp_settings.json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server"],
      "env": {
        "SUPABASE_URL": "${SUPABASE_URL}",
        "SUPABASE_SERVICE_KEY": "${SUPABASE_SERVICE_KEY}"
      }
    },
    "neo4j": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "neo4j/mcp-server-neo4j:latest"],
      "env": {
        "NEO4J_URI": "${NEO4J_URI}",
        "NEO4J_USERNAME": "${NEO4J_USERNAME}",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
      }
    }
  }
}
```

### MCP Features

1. **Server Management**
   - Add/remove MCP servers via settings UI
   - Enable/disable servers per project
   - View server connection status

2. **Tool Discovery**
   - Auto-discover available tools from connected servers
   - Display tool descriptions in chat context
   - Tool usage indicators in responses

3. **Resource Access**
   - Read resources exposed by MCP servers
   - Display resource content inline
   - Cache frequently accessed resources

### MCP Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Empire Desktop                        │
├─────────────────────────────────────────────────────────┤
│  MCP Client Layer (Rust/TypeScript)                     │
│  ├── Server lifecycle management                        │
│  ├── JSON-RPC communication                             │
│  ├── Tool invocation                                    │
│  └── Resource fetching                                  │
├─────────────────────────────────────────────────────────┤
│  MCP Servers (External Processes)                       │
│  ├── supabase-mcp (PostgreSQL + pgvector)              │
│  ├── neo4j-mcp (Knowledge graphs)                      │
│  ├── chrome-devtools-mcp (Browser)                     │
│  └── [Custom servers...]                               │
└─────────────────────────────────────────────────────────┘
```

---

## Appendix

### A. Claude Desktop Features Reference

Based on Claude Desktop Version 1.0.2339:
- Chat/Code toggle
- New chat button
- Chats, Projects, Artifacts navigation
- Recent chats sidebar
- Project memory, instructions, files
- Model selector (Opus 4.5, Sonnet, etc.)
- Quick action buttons
- File attachment via "+" button
- Dark theme UI

### B. Existing Empire Endpoints

Full list at: https://jb-empire-api.onrender.com/docs

Key endpoints for Desktop:
- `/api/query/auto` - Auto-routed queries
- `/api/query/adaptive` - LangGraph workflow
- `/api/documents/*` - Document management
- `/api/chat/*` - Chat functionality
- `/ws/*` - WebSocket streaming

### C. Related Documentation

- `docs/empire_v73_overview.md` - Current system overview
- `notebooklm/FEATURES.md` - Feature documentation
- `CLAUDE.md` - Development guide
- `empire-arch.txt` - Architecture specification

---

**Document Status:** Draft
**Next Steps:** Review with stakeholders, finalize Phase 1 scope, begin technical design
