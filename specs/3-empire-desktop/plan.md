# Implementation Plan: Empire Desktop v7.5

**Branch**: `3-empire-desktop` | **Date**: 2025-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/3-empire-desktop/spec.md`

## Summary

Empire Desktop is a native macOS application built with Tauri 2.0 (Rust + React) that provides a desktop interface for chatting with the Empire v7.3 knowledge base. Key features include streaming chat responses with source citations, project-based organization, persistent local storage via SQLite, and MCP server integration.

---

## Technical Context

**Language/Version**: Rust 1.75+ (Tauri backend), TypeScript 5.x (React frontend)
**Primary Dependencies**:
- Backend: Tauri 2.0, rusqlite, reqwest, tokio, serde
- Frontend: React 18, TailwindCSS, shadcn/ui, Zustand
**Storage**: SQLite (local), macOS Keychain (credentials)
**Testing**: Vitest (frontend), cargo test (Rust)
**Target Platform**: macOS 12.0+ (Monterey and later)
**Project Type**: Desktop application (Tauri = Rust backend + Web frontend)
**Performance Goals**:
- App launch: <2 seconds
- First chat token: <1 second after API response starts
- Sidebar load: <500ms
- Search results: <500ms
**Constraints**:
- Binary size: <20MB
- Memory usage: <150MB idle, <300MB active
- Offline: View-only for chat history
**Scale/Scope**: Single user, 100k+ messages, 1000+ conversations

---

## Constitution Check

*No constitution.md defined - using sensible defaults*

| Gate | Status | Notes |
|------|--------|-------|
| Single platform focus | ✅ Pass | macOS only - no cross-platform complexity |
| Established framework | ✅ Pass | Tauri 2.0 is stable, well-documented |
| Local-first architecture | ✅ Pass | SQLite for persistence, API for AI |
| Minimal dependencies | ✅ Pass | Using standard Rust/React ecosystem |
| No custom protocols | ✅ Pass | MCP is standard JSON-RPC |

---

## Project Structure

### Documentation (this feature)

```text
specs/3-empire-desktop/
├── plan.md              # This file
├── research.md          # Technical decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Validation guide
├── contracts/           # Internal API contracts
├── checklists/          # Quality checklists
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
empire-desktop/
├── src-tauri/                    # Rust backend
│   ├── Cargo.toml
│   ├── tauri.conf.json           # App configuration
│   ├── icons/                    # App icons
│   └── src/
│       ├── main.rs               # Entry point
│       ├── lib.rs                # Library exports
│       ├── error.rs              # Error types
│       ├── db/                   # SQLite operations
│       │   ├── mod.rs
│       │   ├── init.rs           # DB initialization
│       │   ├── migrations.rs     # Schema migrations
│       │   ├── encryption.rs     # At-rest encryption
│       │   ├── projects.rs       # Project CRUD
│       │   ├── conversations.rs  # Conversation CRUD
│       │   ├── messages.rs       # Message CRUD
│       │   ├── settings.rs       # Settings storage
│       │   ├── search.rs         # Full-text search
│       │   └── schema/           # SQL schemas
│       │       ├── projects.sql
│       │       ├── conversations.sql
│       │       ├── messages.sql
│       │       └── settings.sql
│       ├── api/                  # Empire API client
│       │   ├── mod.rs
│       │   ├── http.rs           # HTTP client (reqwest)
│       │   ├── websocket.rs      # WebSocket streaming
│       │   ├── stream.rs         # Stream handler
│       │   ├── query.rs          # Query building
│       │   ├── auth.rs           # JWT management
│       │   └── keychain.rs       # macOS Keychain
│       ├── mcp/                  # MCP client
│       │   ├── mod.rs
│       │   ├── client.rs         # MCP client core
│       │   ├── jsonrpc.rs        # JSON-RPC protocol
│       │   ├── lifecycle.rs      # Server management
│       │   ├── config.rs         # Config parser
│       │   ├── tools.rs          # Tool discovery
│       │   └── invoke.rs         # Tool invocation
│       └── commands/             # Tauri commands
│           ├── mod.rs
│           ├── init.rs           # App init
│           ├── chat.rs           # Chat commands
│           ├── conversation.rs   # Conversation commands
│           ├── project.rs        # Project commands
│           ├── messages.rs       # Message commands
│           ├── search.rs         # Search commands
│           ├── settings.rs       # Settings commands
│           ├── export.rs         # Export commands
│           ├── title.rs          # Title generation
│           └── memory.rs         # Memory extraction
├── src/                          # React frontend
│   ├── App.tsx                   # Root component
│   ├── routes.tsx                # React Router
│   ├── main.tsx                  # Entry point
│   ├── index.css                 # Global styles
│   ├── types/                    # TypeScript types
│   │   ├── index.ts
│   │   ├── chat.ts
│   │   ├── conversation.ts
│   │   ├── project.ts
│   │   └── mcp.ts
│   ├── stores/                   # Zustand stores
│   │   ├── index.ts
│   │   ├── chatStore.ts
│   │   ├── conversationStore.ts
│   │   └── projectStore.ts
│   ├── hooks/                    # React hooks
│   │   ├── useApi.ts
│   │   ├── useChat.ts
│   │   ├── useNavigation.ts
│   │   └── useKeyboardShortcuts.ts
│   ├── lib/                      # Utilities
│   │   ├── utils.ts
│   │   ├── shortcuts.ts
│   │   └── tauri.ts              # Tauri invoke wrapper
│   ├── components/               # UI components
│   │   ├── ui/                   # shadcn/ui components
│   │   ├── layout/
│   │   │   └── Sidebar.tsx
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── TypingIndicator.tsx
│   │   │   ├── StopButton.tsx
│   │   │   ├── MarkdownRenderer.tsx
│   │   │   ├── SourceCitation.tsx
│   │   │   └── CitationPopup.tsx
│   │   ├── sidebar/
│   │   │   ├── ConversationList.tsx
│   │   │   ├── ConversationItem.tsx
│   │   │   ├── NewChatButton.tsx
│   │   │   └── ChatContextMenu.tsx
│   │   ├── projects/
│   │   │   ├── ProjectCard.tsx
│   │   │   ├── ProjectSearch.tsx
│   │   │   ├── DepartmentSelect.tsx
│   │   │   ├── InstructionsEditor.tsx
│   │   │   ├── MemoryEditor.tsx
│   │   │   └── ProjectContextPanel.tsx
│   │   ├── search/
│   │   │   └── SearchResults.tsx
│   │   ├── mcp/
│   │   │   └── McpStatusIndicator.tsx
│   │   ├── settings/
│   │   │   ├── ThemeToggle.tsx
│   │   │   ├── ApiSettings.tsx
│   │   │   └── McpServerSettings.tsx
│   │   ├── dialogs/
│   │   │   ├── CreateProjectDialog.tsx
│   │   │   ├── DeleteChatDialog.tsx
│   │   │   ├── RenameChatDialog.tsx
│   │   │   └── ShortcutsDialog.tsx
│   │   └── CommandPalette.tsx
│   └── pages/                    # Route pages
│       ├── ChatPage.tsx
│       ├── ProjectsPage.tsx
│       ├── ProjectDetailPage.tsx
│       └── SettingsPage.tsx
├── public/                       # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
└── README.md
```

**Structure Decision**: Tauri standard structure with `src-tauri/` for Rust backend and `src/` for React frontend. This follows Tauri 2.0 conventions and keeps backend/frontend cleanly separated.

---

## Technology Stack Details

### Backend (Rust)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | Tauri 2.0 | Native macOS, small binary, secure |
| HTTP Client | reqwest | Async, well-maintained, TLS support |
| WebSocket | tokio-tungstenite | Async WebSocket for streaming |
| Database | rusqlite | SQLite bindings, zero-config |
| Serialization | serde | Standard Rust serialization |
| Keychain | security-framework | Native macOS Keychain access |
| Async Runtime | tokio | Industry standard async runtime |

### Frontend (React)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | React 18 | Stable, hooks, concurrent features |
| Language | TypeScript 5 | Type safety, IDE support |
| Styling | TailwindCSS | Utility-first, dark theme easy |
| Components | shadcn/ui | Copy-paste components, customizable |
| State | Zustand | Simple, performant, TypeScript-first |
| Router | React Router 6 | Standard routing solution |
| Build | Vite | Fast HMR, native ESM |
| Markdown | react-markdown | Render AI responses |

### External Integrations

| Service | Purpose | Protocol |
|---------|---------|----------|
| Empire API | Knowledge base queries | REST + WebSocket |
| Clerk | Authentication | JWT |
| Supabase | Cloud sync (Phase 2) | REST |
| MCP Servers | Tool integrations | JSON-RPC over stdio |

---

## Key Technical Decisions

### 1. Tauri over Electron

**Decision**: Use Tauri 2.0
**Rationale**:
- Binary size: ~15MB vs ~150MB (Electron)
- Memory: ~100MB vs ~300MB
- Native macOS WebView (WKWebView)
- Rust backend for security and performance
- Built-in auto-updater

### 2. SQLite for Local Storage

**Decision**: SQLite with rusqlite
**Rationale**:
- Zero configuration database
- Single file, easy backup
- Full-text search built-in (FTS5)
- Encryption at rest via SQLCipher or custom
- Proven reliability

### 3. Zustand for State Management

**Decision**: Zustand over Redux
**Rationale**:
- Simpler API, less boilerplate
- TypeScript-first design
- Smaller bundle size
- Works well with React 18

### 4. MCP Client in Rust

**Decision**: Implement MCP client in Rust backend
**Rationale**:
- Process spawning from Rust is straightforward
- Direct stdio communication
- Better error handling and lifecycle management
- Security: sandbox tool execution

---

## API Integration

### Empire API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/query/auto` | POST | Auto-routed queries |
| `/api/query/adaptive` | POST | Complex LangGraph queries |
| `/ws/chat` | WebSocket | Streaming responses |
| `/api/documents` | GET | List documents |
| `/api/documents/upload` | POST | Upload files |
| `/health` | GET | Service health check |

### Authentication Flow

```
1. User opens app
2. Check Keychain for stored JWT
3. If no JWT or expired:
   a. Open browser to Clerk login
   b. Receive callback with JWT
   c. Store JWT in Keychain
4. Use JWT for all API calls
5. Auto-refresh before expiry
```

---

## MCP Integration Architecture

### Configuration Format

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
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
      }
    }
  }
}
```

### MCP Client Flow

```
1. App startup: Read mcp_settings.json
2. For each enabled server:
   a. Spawn process with command/args
   b. Set up stdio communication
   c. Send initialize request
   d. Receive capabilities and tools
3. Store available tools in memory
4. On chat: Include tools in context
5. On tool use: Invoke via JSON-RPC
6. On shutdown: Send shutdown to all servers
```

---

## Data Flow

### Chat Message Flow

```
User Input
    ↓
React ChatInput → Tauri Command (invoke)
    ↓
Rust: Build query with project context
    ↓
Rust: POST to Empire API /api/query/auto
    ↓
Rust: Open WebSocket for streaming
    ↓
Rust: Emit events to React (stream chunks)
    ↓
React: Update ChatMessage in real-time
    ↓
Rust: Save complete message to SQLite
    ↓
React: Display with source citations
```

### Project Context Flow

```
User selects Project
    ↓
Load project.instructions from SQLite
    ↓
Prepend to system prompt in API call
    ↓
Empire API receives enhanced context
    ↓
Response reflects project-specific behavior
```

---

## Complexity Tracking

No constitution violations to justify.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Tauri learning curve | Start with official templates, MVP first |
| MCP protocol complexity | Reference Claude Desktop implementation |
| WebSocket reliability | Reconnection logic, queue pending messages |
| macOS code signing | Set up Apple Developer account early |
| SQLite performance | Use indices, batch writes, FTS5 |

---

## Development Environment

### Prerequisites

```bash
# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add aarch64-apple-darwin  # Apple Silicon

# Node.js
brew install node@18

# Xcode Command Line Tools
xcode-select --install

# Tauri CLI
cargo install tauri-cli
```

### Project Initialization

```bash
# Create Tauri app
npm create tauri-app@latest empire-desktop -- --template react-ts

# Install dependencies
cd empire-desktop
npm install
cargo build
```

---

## Next Steps

1. **Phase 0 Complete**: research.md generated
2. **Phase 1 Complete**: data-model.md, quickstart.md generated
3. **Ready for**: /speckit.tasks (already done), /speckit.implement
