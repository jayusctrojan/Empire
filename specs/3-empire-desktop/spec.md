# Feature Specification: Empire Desktop v7.5

**Feature Branch**: `3-empire-desktop`
**Created**: 2025-01-02
**Updated**: 2025-01-02
**Status**: Draft
**Platform**: macOS only
**Input**: User description: "Native macOS desktop app for chatting with Empire knowledge base, featuring chat history, projects organization, and MCP server support - inspired by Claude Desktop"

---

## Overview

Empire Desktop is a native macOS application that provides a dedicated interface for interacting with the Empire v7.3 knowledge base. It brings the power of Empire's 15 AI agents, hybrid database architecture, and document processing to a desktop experience with persistent chat history, project organization, and MCP integration.

| # | Feature | Short Name | Priority | Phase |
|---|---------|------------|----------|-------|
| 1 | Core Chat Interface | `chat-interface` | P0 | 1 |
| 2 | Chat History & Sidebar | `chat-history` | P0 | 1 |
| 3 | Project Management | `projects` | P0 | 1-2 |
| 4 | Local SQLite Storage | `local-storage` | P0 | 1 |
| 5 | Empire API Integration | `api-integration` | P0 | 1 |
| 6 | Streaming Responses | `streaming` | P0 | 1 |
| 7 | Source Citations | `citations` | P0 | 1 |
| 8 | Project Instructions & Memory | `project-memory` | P1 | 2 |
| 9 | Project Files | `project-files` | P1 | 2 |
| 10 | Cloud Sync | `cloud-sync` | P1 | 2 |
| 11 | Global Search | `search` | P1 | 2 |
| 12 | MCP Client Foundation | `mcp-foundation` | P1 | 2 |
| 13 | MCP Server Integration | `mcp-servers` | P1 | 2 |
| 14 | Keyboard Shortcuts | `shortcuts` | P2 | 3 |
| 15 | Offline Mode | `offline` | P2 | 3 |
| 16 | Settings & Preferences | `settings` | P2 | 3 |
| 17 | Auto-Updates | `auto-updates` | P2 | 3 |

> **Note**: Features 8-11 (P1 Priority) will be fully specified after MVP validation. Current scope focuses on Features 1-7 and 12-13.

---

## Target User

**Primary User**: Jay Bajaj (single user, personal knowledge management)

**User Context**:
- Heavy user of Claude Desktop for AI conversations
- Has built Empire v7.3 with 47 completed tasks, 15 AI agents, and extensive knowledge base
- Wants organized access to personal knowledge base with project separation
- Uses MCP servers (Supabase, Neo4j, Chrome DevTools, etc.) extensively
- macOS user (Mac Studio)

---

## Feature 1: Core Chat Interface

### User Scenarios & Testing

#### User Story 1.1 - Send Message and Receive Response (Priority: P0)

As a user, I want to type a message and receive an AI response based on my knowledge base so that I can quickly find information in my documents.

**Why this priority**: Core functionality - app is unusable without this.

**Acceptance Scenarios**:

1. **Given** the app is open with an active chat, **When** I type a message and press Enter/Cmd+Enter, **Then** the message appears in the chat and a response begins streaming
2. **Given** I've sent a message, **When** the AI responds, **Then** the response streams word-by-word with a typing indicator
3. **Given** a response is streaming, **When** I want to stop it, **Then** I can click a stop button to halt generation
4. **Given** a response completes, **When** I view it, **Then** source citations are displayed inline [1], [2], etc.

#### User Story 1.2 - Attach Files to Message (Priority: P1)

As a user, I want to attach files to my message so that I can ask questions about specific documents.

**Acceptance Scenarios**:

1. **Given** I'm composing a message, **When** I click the "+" button or drag a file, **Then** the file is attached and shown as a preview
2. **Given** I've attached a file, **When** I send the message, **Then** the file is uploaded to Empire and included in context
3. **Given** I've attached an image, **When** I send the message, **Then** Claude Vision analyzes the image

#### Edge Cases

- Large file upload handling (show progress, handle timeout)
- Unsupported file type messaging
- Network disconnection during message send

### Requirements

#### Functional Requirements

- **FR-1.1**: System MUST provide a text input area that supports multi-line input
- **FR-1.2**: System MUST send messages to Empire API `/api/query/auto` endpoint
- **FR-1.3**: System MUST display user messages aligned right, AI messages aligned left
- **FR-1.4**: System MUST support Cmd+Enter to send messages
- **FR-1.5**: System MUST show a "stop" button during response streaming
- **FR-1.6**: System MUST support file attachment via click or drag-drop
- **FR-1.7**: System MUST display attachment previews before sending

### Success Criteria

- **SC-1.1**: User can send a message and receive a response within 5 seconds (excluding AI processing time)
- **SC-1.2**: Messages persist across app restarts
- **SC-1.3**: File attachments up to 50MB are supported

---

## Feature 2: Chat History & Sidebar

### User Scenarios & Testing

#### User Story 2.1 - View Recent Chats (Priority: P0)

As a user, I want to see my recent conversations in a sidebar so that I can quickly return to previous discussions.

**Acceptance Scenarios**:

1. **Given** I open the app, **When** the sidebar loads, **Then** I see my recent chats sorted by last message time
2. **Given** I have multiple chats, **When** I click a chat in the sidebar, **Then** that conversation loads in the main area
3. **Given** I'm in a chat, **When** I send a new message, **Then** that chat moves to the top of the recents list

#### User Story 2.2 - Start New Chat (Priority: P0)

As a user, I want to start a new conversation so that I can ask about a different topic.

**Acceptance Scenarios**:

1. **Given** I'm in any view, **When** I click "New Chat" or press Cmd+N, **Then** a new empty chat opens
2. **Given** I start a new chat, **When** I send the first message, **Then** the chat title is auto-generated from the message content

#### User Story 2.3 - Delete Chat (Priority: P1)

As a user, I want to delete old conversations so that I can keep my history clean.

**Acceptance Scenarios**:

1. **Given** I right-click a chat in the sidebar, **When** I select "Delete", **Then** I'm asked to confirm
2. **Given** I confirm deletion, **When** the action completes, **Then** the chat is removed from sidebar and storage

### Requirements

#### Functional Requirements

- **FR-2.1**: System MUST display a sidebar with recent conversations
- **FR-2.2**: System MUST allow creating new chats via button and Cmd+N
- **FR-2.3**: System MUST auto-generate chat titles from first message
- **FR-2.4**: System MUST allow renaming chats
- **FR-2.5**: System MUST allow deleting chats with confirmation
- **FR-2.6**: System MUST sort chats by most recent activity
- **FR-2.7**: System MUST show chat preview (first line of last message)

### Success Criteria

- **SC-2.1**: Sidebar loads within 500ms of app launch
- **SC-2.2**: User can access any chat from the last 12 months
- **SC-2.3**: Chat list supports 1000+ conversations without performance degradation

---

## Feature 3: Project Management

### User Scenarios & Testing

#### User Story 3.1 - Create Project (Priority: P0)

As a user, I want to create projects to organize my conversations by topic so that I can keep work and personal knowledge separate.

**Acceptance Scenarios**:

1. **Given** I click "Projects" in sidebar, **When** I click "New Project", **Then** a project creation dialog appears
2. **Given** the dialog is open, **When** I enter a name and description, **Then** the project is created and appears in my project list
3. **Given** I create a project, **When** I select a department (optional), **Then** the project is tagged with that Empire department

#### User Story 3.2 - View Project (Priority: P0)

As a user, I want to view a project to see its conversations, files, and settings.

**Acceptance Scenarios**:

1. **Given** I click a project, **When** it opens, **Then** I see: conversations list, memory summary, instructions, and files
2. **Given** I'm in a project, **When** I start a new chat, **Then** that chat is associated with this project
3. **Given** a project has instructions, **When** I chat within the project, **Then** those instructions are included as system context

#### User Story 3.3 - Edit Project Settings (Priority: P1)

As a user, I want to edit project instructions and memory so that I can customize AI behavior per project.

**Acceptance Scenarios**:

1. **Given** I'm viewing a project, **When** I click "Instructions", **Then** I can edit the custom system prompt
2. **Given** I'm viewing a project, **When** I click "Memory", **Then** I see auto-captured context and can edit it
3. **Given** I update instructions, **When** I start a new chat, **Then** the new instructions are used

### Requirements

#### Functional Requirements

- **FR-3.1**: System MUST allow creating projects with name, description, and optional department
- **FR-3.2**: System MUST display projects in a grid or list view
- **FR-3.3**: System MUST associate conversations with projects
- **FR-3.4**: System MUST support project-level custom instructions (system prompt)
- **FR-3.5**: System MUST support project-level memory (persistent context)
- **FR-3.6**: System MUST support project-level file attachments (max 50MB per file)
- **FR-3.7**: System MUST allow editing and deleting projects
- **FR-3.8**: System MUST support the 12 Empire departments as project tags

#### Key Entities

- **Project**: id, name, description, department, instructions, memory, created_at, updated_at
- **Conversation**: id, project_id (nullable), title, created_at, updated_at
- **ProjectFile**: id, project_id, filename, file_type, document_id (Empire), created_at

### Success Criteria

- **SC-3.1**: User can create a project in under 30 seconds
- **SC-3.2**: Projects support 100+ conversations each
- **SC-3.3**: Project instructions are applied to 100% of chats within that project

---

## Feature 4: Local SQLite Storage

### User Scenarios & Testing

#### User Story 4.1 - Persist Data Locally (Priority: P0)

As a user, I want my chats and projects stored locally so that I can access them offline and app launches quickly.

**Acceptance Scenarios**:

1. **Given** I close the app, **When** I reopen it, **Then** all my chats and projects are preserved
2. **Given** I'm offline, **When** I open the app, **Then** I can view all my chat history
3. **Given** the app crashes, **When** I restart, **Then** no data is lost (auto-save)

### Requirements

#### Functional Requirements

- **FR-4.1**: System MUST store all data in local SQLite database
- **FR-4.2**: System MUST auto-save after each message
- **FR-4.3**: System MUST encrypt database at rest
- **FR-4.4**: System MUST support database location: `~/Library/Application Support/Empire Desktop/`
- **FR-4.5**: System MUST handle database migrations for schema changes

#### Key Entities (SQLite Schema)

```sql
-- Projects
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    department TEXT,
    instructions TEXT,
    memory TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

-- Conversations
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

-- Messages
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    attachments TEXT,
    created_at TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

-- Settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### Success Criteria

- **SC-4.1**: App launches with data loaded in under 2 seconds
- **SC-4.2**: Database handles 100,000+ messages without degradation
- **SC-4.3**: Zero data loss across normal app lifecycle

---

## Feature 5: Empire API Integration

### User Scenarios & Testing

#### User Story 5.1 - Connect to Empire Backend (Priority: P0)

As a user, I want the app to connect to my Empire API so that I can query my knowledge base.

**Acceptance Scenarios**:

1. **Given** I launch the app, **When** I'm authenticated, **Then** the app connects to Empire API
2. **Given** I send a message, **When** the API responds, **Then** I see the response with sources
3. **Given** the API is unreachable, **When** I try to send, **Then** I see a clear error message

### Requirements

#### Functional Requirements

- **FR-5.1**: System MUST connect to `https://jb-empire-api.onrender.com`
- **FR-5.2**: System MUST use `/api/query/auto` for intelligent query routing
- **FR-5.3**: System MUST use `/api/query/adaptive` for complex queries
- **FR-5.4**: System MUST use WebSocket `/ws/chat` for streaming
- **FR-5.5**: System MUST handle authentication via Clerk JWT tokens
- **FR-5.6**: System MUST store tokens securely in macOS Keychain
- **FR-5.7**: System MUST handle token refresh automatically

### Success Criteria

- **SC-5.1**: API calls complete within 5 seconds (excluding AI processing)
- **SC-5.2**: Token refresh is seamless (no user intervention)
- **SC-5.3**: Network errors show user-friendly messages

---

## Feature 6: Streaming Responses

### User Scenarios & Testing

#### User Story 6.1 - See Response as It Generates (Priority: P0)

As a user, I want to see the AI response stream in real-time so that I don't wait for the full response.

**Acceptance Scenarios**:

1. **Given** I send a message, **When** the AI starts responding, **Then** I see text appear word-by-word
2. **Given** a response is streaming, **When** I want to stop it, **Then** I can click stop
3. **Given** streaming completes, **When** I view the response, **Then** it shows full formatting (markdown, code blocks)

### Requirements

#### Functional Requirements

- **FR-6.1**: System MUST support WebSocket streaming from Empire API
- **FR-6.2**: System MUST render markdown in real-time during streaming
- **FR-6.3**: System MUST show typing indicator during streaming
- **FR-6.4**: System MUST allow stopping generation mid-stream
- **FR-6.5**: System MUST handle stream interruption gracefully

### Success Criteria

- **SC-6.1**: First token appears within 1 second of request
- **SC-6.2**: Streaming is smooth with no visible lag between tokens
- **SC-6.3**: Stop button halts generation within 500ms

---

## Feature 7: Source Citations

### User Scenarios & Testing

#### User Story 7.1 - View Source Citations (Priority: P0)

As a user, I want to see which documents informed the AI response so that I can verify and explore further.

**Acceptance Scenarios**:

1. **Given** a response contains sources, **When** I view it, **Then** I see inline citations [1], [2], etc.
2. **Given** I click a citation, **When** the popup opens, **Then** I see: document title, page number, relevant excerpt
3. **Given** I want to see all sources, **When** I expand the sources section, **Then** I see full list with metadata

### Requirements

#### Functional Requirements

- **FR-7.1**: System MUST display inline citation numbers in responses
- **FR-7.2**: System MUST show citation popup on click
- **FR-7.3**: System MUST display: document title, page/section, excerpt, confidence score
- **FR-7.4**: System MUST support collapsible sources section at response end
- **FR-7.5**: System MUST link to original document when available

### Success Criteria

- **SC-7.1**: 100% of sourced responses show citations
- **SC-7.2**: Citation popup loads within 200ms
- **SC-7.3**: Source excerpts are accurate (95%+ of citations link to correct document) and relevant (excerpt contains query keywords or semantic match)

---

## Feature 12: MCP Client Foundation

### User Scenarios & Testing

#### User Story 12.1 - Connect to MCP Servers (Priority: P1)

As a user, I want Empire Desktop to connect to my MCP servers so that I can use tools like Supabase and Neo4j directly.

**Acceptance Scenarios**:

1. **Given** I configure an MCP server in settings, **When** the app starts, **Then** it connects to the server
2. **Given** an MCP server is connected, **When** I chat, **Then** the AI can use tools from that server
3. **Given** a tool is used, **When** I view the response, **Then** I see which tool was invoked

### Requirements

#### Functional Requirements

- **FR-12.1**: System MUST support MCP server configuration via `~/.empire/mcp_settings.json`
- **FR-12.2**: System MUST manage MCP server lifecycle (start, stop, restart)
- **FR-12.3**: System MUST implement MCP JSON-RPC protocol
- **FR-12.4**: System MUST discover and list available tools from servers
- **FR-12.5**: System MUST invoke tools and return results to AI context

#### MCP Configuration Format

```json
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
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
      }
    }
  }
}
```

### Success Criteria

- **SC-12.1**: MCP servers connect within 5 seconds of app launch
- **SC-12.2**: Tool invocations complete within 10 seconds
- **SC-12.3**: Server disconnection is handled gracefully with reconnection

---

## Feature 13: MCP Server Integration

### User Scenarios & Testing

#### User Story 13.1 - Use Supabase MCP (Priority: P1)

As a user, I want to query my Supabase database directly so that I can analyze data alongside my documents.

**Acceptance Scenarios**:

1. **Given** Supabase MCP is configured, **When** I ask about database data, **Then** the AI queries Supabase and includes results
2. **Given** I ask to "list my documents", **When** processed, **Then** the AI uses Supabase MCP to fetch the list

#### User Story 13.2 - Use Neo4j MCP (Priority: P1)

As a user, I want to query my knowledge graph so that I can explore entity relationships.

**Acceptance Scenarios**:

1. **Given** Neo4j MCP is configured, **When** I ask about entity relationships, **Then** the AI queries the graph
2. **Given** I ask "what entities are related to X", **When** processed, **Then** Neo4j MCP traverses the graph

### Requirements

#### Functional Requirements

- **FR-13.1**: System MUST support Supabase MCP server
- **FR-13.2**: System MUST support Neo4j MCP server
- **FR-13.3**: System MUST support Chrome DevTools MCP (Phase 3)
- **FR-13.4**: System MUST support Ref MCP (Phase 3)
- **FR-13.5**: System MUST support TaskMaster MCP (Phase 3)
- **FR-13.6**: System MUST allow enabling/disabling servers per project

### Success Criteria

- **SC-13.1**: Supabase queries return results within 5 seconds
- **SC-13.2**: Neo4j queries return results within 5 seconds
- **SC-13.3**: Tool usage is visible in response metadata

---

## Technical Architecture

### Framework Selection

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Desktop Framework | Tauri 2.0 | Lightweight, Rust backend, native macOS |
| Frontend | React 18 + TypeScript | Modern, component-based, strong typing |
| Styling | TailwindCSS + shadcn/ui | Dark theme components, rapid development |
| Local Database | SQLite via Tauri | Built-in, performant, encrypted |
| State Management | Zustand | Simple, performant, TypeScript-native |
| MCP Client | Rust (native) | Performance, direct system access |

### Application Structure

```
empire-desktop/
├── src-tauri/           # Rust backend
│   ├── src/
│   │   ├── main.rs      # App entry point
│   │   ├── db/          # SQLite operations
│   │   ├── api/         # Empire API client
│   │   ├── mcp/         # MCP client implementation
│   │   └── commands/    # Tauri commands
│   └── Cargo.toml
├── src/                 # React frontend
│   ├── components/      # UI components
│   ├── pages/           # Route pages
│   ├── hooks/           # React hooks
│   ├── stores/          # Zustand stores
│   ├── lib/             # Utilities
│   └── App.tsx
├── public/              # Static assets
└── package.json
```

---

## Assumptions

1. User has macOS 12.0 (Monterey) or later
2. User has valid Empire API credentials (Clerk authentication)
3. User has internet connectivity for API calls (offline mode is view-only)
4. MCP servers are pre-configured with correct credentials in environment
5. User is comfortable with direct DMG installation (no App Store)

---

## Dependencies

### External Dependencies

- Empire API v7.3 (https://jb-empire-api.onrender.com)
- Clerk authentication service
- Supabase (for cloud sync in Phase 2)
- MCP server binaries (npm packages, Docker images)

### Development Dependencies

- Rust toolchain (for Tauri)
- Node.js 18+ (for React frontend)
- Xcode Command Line Tools (for macOS builds)

---

## Out of Scope

1. Windows/Linux support (macOS only)
2. Mobile apps (iOS/Android)
3. App Store distribution
4. Multi-user/team features
5. Voice input (future consideration)
6. Custom MCP server creation UI

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tauri learning curve | Medium | Medium | Start with MVP, iterate |
| MCP protocol complexity | Medium | High | Use existing Claude Desktop as reference |
| Empire API changes | Low | Medium | Version API calls, handle gracefully |
| macOS code signing | Medium | Low | Apple Developer account required |

---

## Success Criteria Summary

| Phase | Key Metrics |
|-------|-------------|
| Phase 1 MVP | Chat works, history persists, basic projects |
| Phase 2 Projects & MCP | Full projects, cloud sync, MCP connected |
| Phase 3 Polish | Shortcuts working, offline mode, auto-updates |

**Overall Success**: User prefers Empire Desktop over web interface for daily knowledge base queries.
