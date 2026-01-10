# Research: Empire Desktop v7.5

**Feature**: Empire Desktop
**Date**: 2025-01-02
**Purpose**: Document technical decisions and research findings

---

## Decision 1: Desktop Framework

### Decision
**Tauri 2.0** (Rust + WKWebView)

### Rationale
- Native macOS performance with WKWebView
- Small binary size (~15MB vs 150MB+ Electron)
- Low memory footprint (~100MB vs 300MB+ Electron)
- Rust backend provides security and speed
- Built-in auto-updater support
- Strong TypeScript/React support for frontend

### Alternatives Considered

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Electron | Large ecosystem, mature | Heavy, memory-hungry, large binary | 10x larger binary, 3x memory |
| Swift/SwiftUI | Native macOS, best perf | macOS only, new UI paradigm | Limited web tech reuse |
| Flutter Desktop | Cross-platform, Dart | Less native feel, larger binary | Not truly native macOS |

### References
- [Tauri 2.0 Documentation](https://tauri.app/v2/)
- [Tauri vs Electron Comparison](https://tauri.app/v1/guides/getting-started/prerequisites)

---

## Decision 2: State Management

### Decision
**Zustand** for React state management

### Rationale
- Minimal boilerplate compared to Redux
- TypeScript-first design
- Smaller bundle size (~1KB)
- Simple API: create store, use hook
- Works seamlessly with React 18 concurrent features
- Easy persistence with middleware

### Alternatives Considered

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Redux Toolkit | Industry standard, devtools | Boilerplate, larger | Overkill for single-user app |
| Jotai | Atomic, React-like | Different mental model | Less familiar pattern |
| React Context | Built-in, no deps | Re-render issues, verbose | Performance concerns at scale |

### Example Usage
```typescript
// stores/chatStore.ts
import { create } from 'zustand'

interface ChatStore {
  messages: Message[]
  isStreaming: boolean
  addMessage: (msg: Message) => void
  setStreaming: (val: boolean) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isStreaming: false,
  addMessage: (msg) => set((state) => ({
    messages: [...state.messages, msg]
  })),
  setStreaming: (val) => set({ isStreaming: val })
}))
```

---

## Decision 3: Local Database

### Decision
**SQLite** via rusqlite with custom encryption

### Rationale
- Zero configuration, single file database
- Proven reliability at scale (billions of deployments)
- Full-text search via FTS5 extension
- ACID compliance for data integrity
- Easy backup (copy single file)
- Native Rust bindings (rusqlite)

### Alternatives Considered

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| IndexedDB | Browser native | Limited query power | No full-text search |
| LevelDB | Fast key-value | No SQL, no FTS | Need relational queries |
| Realm | Mobile-focused | Heavier, sync complexity | Overkill for local-only |

### Encryption Approach
```rust
// Use SQLCipher or custom encryption
// Option 1: SQLCipher (recommended)
let conn = Connection::open_with_flags_and_key(
    path,
    OpenFlags::SQLITE_OPEN_READ_WRITE,
    Some("encryption_key")
)?;

// Option 2: Encrypt file at rest
// Decrypt on open, re-encrypt on close
```

---

## Decision 4: UI Component Library

### Decision
**shadcn/ui** with TailwindCSS

### Rationale
- Copy-paste components (not a dependency)
- Full customization control
- Dark theme built-in
- Matches Claude Desktop aesthetic
- TailwindCSS for rapid styling
- TypeScript support

### Alternatives Considered

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| MUI | Feature-rich, mature | Heavy, opinionated | Too heavy for desktop app |
| Chakra UI | Good DX, accessible | Bundle size | shadcn lighter |
| Radix + custom | Maximum control | More work | shadcn is Radix + styling |

### Theme Configuration
```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#1a1a1a',
        foreground: '#ffffff',
        accent: '#e07850', // Empire orange
        muted: '#a0a0a0',
        border: '#404040',
      }
    }
  }
}
```

---

## Decision 5: MCP Client Implementation

### Decision
**Rust-native MCP client** in Tauri backend

### Rationale
- Direct process spawning from Rust
- Better lifecycle management
- Security: tool execution sandboxing
- Consistent error handling
- No JavaScript process management complexity

### Protocol Implementation

```rust
// MCP JSON-RPC message format
#[derive(Serialize, Deserialize)]
struct McpRequest {
    jsonrpc: String,  // "2.0"
    id: u64,
    method: String,
    params: serde_json::Value,
}

#[derive(Serialize, Deserialize)]
struct McpResponse {
    jsonrpc: String,
    id: u64,
    result: Option<serde_json::Value>,
    error: Option<McpError>,
}

// Lifecycle
// 1. spawn process with stdio pipes
// 2. send "initialize" request
// 3. receive "initialized" notification
// 4. list tools via "tools/list"
// 5. invoke tools via "tools/call"
// 6. send "shutdown" on app close
```

### References
- [MCP Specification](https://modelcontextprotocol.io/)
- [Claude Desktop MCP Config](https://docs.anthropic.com/en/docs/mcp)

---

## Decision 6: Streaming Architecture

### Decision
**WebSocket** for Empire API streaming + **Tauri Events** to React

### Rationale
- Empire API already supports WebSocket streaming
- Tauri events provide clean React integration
- No polling, true real-time updates
- Backpressure handling via Rust

### Implementation Flow

```rust
// Rust: WebSocket to Empire API
async fn stream_response(query: &str) -> Result<()> {
    let (ws, _) = connect_async("wss://jb-empire-api.onrender.com/ws/chat").await?;

    ws.send(Message::Text(query.to_string())).await?;

    while let Some(msg) = ws.next().await {
        match msg? {
            Message::Text(chunk) => {
                // Emit to React
                app_handle.emit_all("chat-chunk", chunk)?;
            }
            Message::Close(_) => break,
        }
    }
    Ok(())
}
```

```typescript
// React: Listen for events
useEffect(() => {
  const unlisten = listen('chat-chunk', (event) => {
    appendToMessage(event.payload as string)
  })
  return () => { unlisten.then(f => f()) }
}, [])
```

---

## Decision 7: Authentication Storage

### Decision
**macOS Keychain** via security-framework crate

### Rationale
- Native macOS secure storage
- Hardware-backed on Apple Silicon
- Standard practice for desktop apps
- Survives app reinstalls
- User can manage via Keychain Access

### Implementation

```rust
use security_framework::passwords::{
    set_generic_password,
    get_generic_password,
    delete_generic_password,
};

const SERVICE: &str = "com.empire.desktop";
const ACCOUNT: &str = "jwt_token";

pub fn store_token(token: &str) -> Result<()> {
    set_generic_password(SERVICE, ACCOUNT, token.as_bytes())
}

pub fn get_token() -> Result<String> {
    let bytes = get_generic_password(SERVICE, ACCOUNT)?;
    Ok(String::from_utf8(bytes)?)
}

pub fn clear_token() -> Result<()> {
    delete_generic_password(SERVICE, ACCOUNT)
}
```

---

## Decision 8: Full-Text Search

### Decision
**SQLite FTS5** for conversation search

### Rationale
- Built into SQLite, no extra dependencies
- Supports phrase search, boolean operators
- Ranked results with BM25
- Triggers keep index in sync
- Fast even with 100k+ messages

### Implementation

```sql
-- Create FTS virtual table
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id'
);

-- Triggers for sync
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

-- Search query
SELECT m.*, highlight(messages_fts, 0, '<mark>', '</mark>') as snippet
FROM messages_fts
JOIN messages m ON m.id = messages_fts.rowid
WHERE messages_fts MATCH ?
ORDER BY rank;
```

---

## Performance Benchmarks (Targets)

| Operation | Target | Measurement Method |
|-----------|--------|-------------------|
| App cold start | <2s | Time from launch to UI ready |
| Chat first token | <1s | Time from send to first chunk |
| Sidebar load | <500ms | Time to render conversation list |
| Search results | <500ms | Time to show search results |
| Project switch | <300ms | Time to load project context |
| Memory idle | <150MB | Activity Monitor |
| Memory active | <300MB | During chat streaming |

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Token storage | macOS Keychain (hardware-backed) |
| Local data | SQLite encryption at rest |
| Network | TLS 1.2+ for all API calls |
| MCP tools | Sandboxed process execution |
| Code signing | Apple Developer ID for distribution |

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Cross-platform? | No - macOS only |
| App Store? | No - direct DMG download |
| Multi-user? | No - single user |
| Offline AI? | No - view-only offline, AI requires API |

---

## References

- [Tauri 2.0 Documentation](https://tauri.app/v2/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Empire API Docs](https://jb-empire-api.onrender.com/docs)
- [shadcn/ui](https://ui.shadcn.com/)
- [Zustand](https://zustand-demo.pmnd.rs/)
