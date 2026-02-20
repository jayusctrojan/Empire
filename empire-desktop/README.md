# Empire Desktop

Tauri 2.x desktop application for Empire v7.5 — the primary interface for the AI-powered knowledge management platform.

## Stack

| Layer | Technology |
|-------|------------|
| Framework | Tauri 2.x (Rust backend) |
| UI | React 18 + TypeScript |
| State | Zustand (with persist middleware) |
| Styling | Tailwind CSS (Empire dark theme) |
| Testing | Vitest + @testing-library/react |
| Build | Vite |

## Features

- **CKO Chat**: Multi-model AI pipeline with phase indicators and streaming
- **Organization Picker/Switcher**: Multi-tenant organization support
- **Unified Search**: Cmd+K search across chats, projects, KB, artifacts
- **Artifact System**: Inline preview cards, side panel viewer, file download
- **Document Generation**: DOCX, XLSX, PPTX, PDF from AI responses

## Development

```bash
# Install dependencies
npm install

# Start in development mode (hot-reload)
npm run tauri dev

# Run tests
npx vitest run

# Type checking
npx tsc --noEmit

# Build for production
npm run tauri build
```

## Project Structure

```
empire-desktop/
├── src/
│   ├── components/           # 31 React components
│   │   ├── auth/             # Authentication (Clerk)
│   │   ├── chat/             # ChatView, MessageBubble, ArtifactCard, etc.
│   │   ├── projects/         # Project management
│   │   ├── GlobalSearch.tsx   # Cmd+K unified search modal
│   │   ├── OrgPicker.tsx      # Organization selection on launch
│   │   ├── OrgSwitcher.tsx    # Org switching dropdown
│   │   └── Sidebar.tsx        # Navigation sidebar
│   ├── stores/               # Zustand state management
│   │   ├── chat.ts           # Conversations, messages, artifacts, phases
│   │   ├── app.ts            # View state, sidebar
│   │   ├── org.ts            # Organization selection, switching
│   │   └── projects.ts       # Project list
│   ├── lib/
│   │   ├── api/              # Backend API client
│   │   │   ├── client.ts     # Fetch wrapper with X-Org-Id header
│   │   │   ├── search.ts     # Unified search API
│   │   │   ├── artifacts.ts  # Artifact download/metadata
│   │   │   └── index.ts      # Core API functions
│   │   ├── database.ts       # Local IndexedDB for offline data
│   │   └── utils.ts          # Utility functions (cn, etc.)
│   ├── test/                 # Test setup and test files
│   ├── types/                # TypeScript type definitions
│   └── App.tsx               # Root component
├── src-tauri/                # Rust backend for Tauri
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.ts
```

## Key Components

| Component | Purpose |
|-----------|---------|
| `ChatView` | Main chat interface with streaming + artifact panel |
| `GlobalSearch` | Cmd+K unified search modal with filter tabs |
| `OrgPicker` | Organization selection on launch |
| `OrgSwitcher` | Org switching dropdown in sidebar |
| `Sidebar` | Conversation list, navigation |
| `MessageBubble` | Chat messages with citation popovers |
| `ArtifactCard` | Inline artifact preview in chat |
| `ArtifactPanel` | Side panel artifact viewer |
| `PhaseIndicator` | Pipeline phase indicator (Analyzing/Searching/Thinking/Formatting) |

## Testing

22 tests across 3 test files:

```bash
npx vitest run                              # All tests
npx vitest run src/test/stores/chat.test.ts  # Specific file
npx vitest                                   # Watch mode
```
