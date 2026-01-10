# Tasks: Empire Desktop v7.5

**Input**: Design documents from `/specs/3-empire-desktop/`
**Prerequisites**: spec.md (user stories), docs/EMPIRE_V75_PRD.md (technical details)
**Created**: 2025-01-02
**Total Tasks**: 115 tasks across 10 phases

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## User Story to Feature Mapping

| User Story | Primary Features | Spec Section |
|------------|-----------------|--------------|
| US1 | F1 (Chat Interface), F6 (Streaming), F7 (Citations) | Feature 1, 6, 7 |
| US2 | F2 (Chat History & Sidebar) | Feature 2 |
| US3 | F3 (Project Management) | Feature 3 |
| US4 | F4 (Local SQLite Storage) | Feature 4 |
| US5 | F8 (Project Instructions & Memory) | Feature 8 |
| US6 | F12 (MCP Foundation), F13 (MCP Servers) | Feature 12, 13 |
| US7 | F11 (Global Search), F14 (Shortcuts) | Feature 11, 14 |

## Path Conventions

```
empire-desktop/
├── src-tauri/           # Rust backend
│   ├── src/
│   │   ├── main.rs
│   │   ├── db/          # SQLite operations
│   │   ├── api/         # Empire API client
│   │   ├── mcp/         # MCP client
│   │   └── commands/    # Tauri commands
│   └── Cargo.toml
├── src/                 # React frontend
│   ├── components/
│   ├── pages/
│   ├── hooks/
│   ├── stores/
│   └── lib/
└── package.json
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, Tauri + React setup, basic tooling

- [ ] T001 Create `empire-desktop/` directory in project root
- [ ] T002 Initialize Tauri 2.0 project with `npm create tauri-app@latest`
- [ ] T003 [P] Configure TypeScript in `tsconfig.json`
- [ ] T004 [P] Configure TailwindCSS in `tailwind.config.js`
- [ ] T005 [P] Install shadcn/ui components with dark theme in `src/components/ui/`
- [ ] T006 [P] Configure ESLint and Prettier in `.eslintrc.js` and `.prettierrc`
- [ ] T007 Setup Zustand state management in `src/stores/index.ts`
- [ ] T008 Create base app layout in `src/App.tsx`
- [ ] T009 Configure Tauri app metadata in `src-tauri/tauri.conf.json`
- [ ] T010 [P] Create app icons for macOS in `src-tauri/icons/`

**Checkpoint**: Tauri app builds and runs with empty shell

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database Foundation

- [ ] T011 Add SQLite dependencies to `src-tauri/Cargo.toml` (rusqlite, serde)
- [ ] T012 Create database module structure in `src-tauri/src/db/mod.rs`
- [ ] T013 Implement database initialization in `src-tauri/src/db/init.rs`
- [ ] T014 Create migration system in `src-tauri/src/db/migrations.rs`
- [ ] T015 Implement projects table schema in `src-tauri/src/db/schema/projects.sql`
- [ ] T016 Implement conversations table schema in `src-tauri/src/db/schema/conversations.sql`
- [ ] T017 Implement messages table schema in `src-tauri/src/db/schema/messages.sql`
- [ ] T018 Implement settings table schema in `src-tauri/src/db/schema/settings.sql`

### API Foundation

- [ ] T019 Create API client module in `src-tauri/src/api/mod.rs`
- [ ] T020 Implement HTTP client with reqwest in `src-tauri/src/api/http.rs`
- [ ] T021 [P] Implement WebSocket client for streaming in `src-tauri/src/api/websocket.rs`
- [ ] T022 Create authentication token management in `src-tauri/src/api/auth.rs`
- [ ] T023 Implement macOS Keychain integration in `src-tauri/src/api/keychain.rs`
- [ ] T023a Implement Clerk browser callback handler for OAuth flow in `src-tauri/src/api/auth.rs` (FR-5.5)
- [ ] T023b Implement JWT token exchange and validation in `src-tauri/src/api/auth.rs` (FR-5.5, FR-5.7)

### Tauri Commands Foundation

- [ ] T024 Create Tauri commands module in `src-tauri/src/commands/mod.rs`
- [ ] T025 Implement app initialization command in `src-tauri/src/commands/init.rs`
- [ ] T026 Create error types and handling in `src-tauri/src/error.rs`

### Frontend Foundation

- [ ] T027 Create API hooks structure in `src/hooks/useApi.ts`
- [ ] T028 [P] Create TypeScript types in `src/types/index.ts`
- [ ] T029 [P] Create utility functions in `src/lib/utils.ts`
- [ ] T030 Setup React Router in `src/routes.tsx`

**Checkpoint**: Foundation ready - SQLite works, API client configured, Tauri commands callable from React

---

## Phase 3: User Story 1 - Core Chat Interface (Priority: P0) 🎯 MVP

**Goal**: User can send messages and receive streaming AI responses with source citations

**Independent Test**: Send "What is Empire?" and receive a response with sources displayed

### Implementation for User Story 1

- [ ] T031 [US1] Create chat message types in `src/types/chat.ts`
- [ ] T032 [US1] Create chat store with Zustand in `src/stores/chatStore.ts`
- [ ] T033 [P] [US1] Implement ChatMessage component in `src/components/chat/ChatMessage.tsx`
- [ ] T034 [P] [US1] Implement ChatInput component in `src/components/chat/ChatInput.tsx`
- [ ] T035 [P] [US1] Implement TypingIndicator component in `src/components/chat/TypingIndicator.tsx`
- [ ] T036 [US1] Create ChatContainer component in `src/components/chat/ChatContainer.tsx`
- [ ] T037 [US1] Implement send message Tauri command in `src-tauri/src/commands/chat.rs`
- [ ] T038 [US1] Implement streaming response handler in `src-tauri/src/api/stream.rs`
- [ ] T039 [US1] Connect React to Tauri streaming events in `src/hooks/useChat.ts`
- [ ] T040 [US1] Implement stop generation functionality in `src/components/chat/StopButton.tsx`
- [ ] T041 [US1] Add markdown rendering to messages in `src/components/chat/MarkdownRenderer.tsx`
- [ ] T042 [US1] Implement source citation display in `src/components/chat/SourceCitation.tsx`
- [ ] T043 [US1] Create citation popup component in `src/components/chat/CitationPopup.tsx`
- [ ] T044 [US1] Integrate chat with main App layout in `src/pages/ChatPage.tsx`

**Checkpoint**: User can chat with Empire API, see streaming responses and source citations

---

## Phase 4: User Story 2 - Chat History & Sidebar (Priority: P0)

**Goal**: User can view, create, and manage conversations in a sidebar

**Independent Test**: Create multiple chats, switch between them, verify history persists after restart

### Implementation for User Story 2

- [ ] T045 [US2] Create conversation types in `src/types/conversation.ts`
- [ ] T046 [US2] Add conversation store in `src/stores/conversationStore.ts`
- [ ] T047 [US2] Implement conversation CRUD commands in `src-tauri/src/commands/conversation.rs`
- [ ] T048 [US2] Implement conversation DB operations in `src-tauri/src/db/conversations.rs`
- [ ] T049 [P] [US2] Create Sidebar component in `src/components/layout/Sidebar.tsx`
- [ ] T050 [P] [US2] Create ConversationList component in `src/components/sidebar/ConversationList.tsx`
- [ ] T051 [P] [US2] Create ConversationItem component in `src/components/sidebar/ConversationItem.tsx`
- [ ] T052 [US2] Implement NewChat button in `src/components/sidebar/NewChatButton.tsx`
- [ ] T053 [US2] Implement chat title auto-generation in `src-tauri/src/commands/title.rs`
- [ ] T054 [US2] Add context menu for chat actions in `src/components/sidebar/ChatContextMenu.tsx`
- [ ] T055 [US2] Implement delete chat with confirmation in `src/components/dialogs/DeleteChatDialog.tsx`
- [ ] T056 [US2] Implement rename chat in `src/components/dialogs/RenameChatDialog.tsx`
- [ ] T057 [US2] Connect sidebar to chat navigation in `src/hooks/useNavigation.ts`

**Checkpoint**: Sidebar shows chats, new chat works, switching preserves history

---

## Phase 5: User Story 3 - Project Management (Priority: P0)

**Goal**: User can create and manage projects to organize conversations

**Independent Test**: Create project, add conversations to it, verify project-level organization

### Implementation for User Story 3

- [ ] T058 [US3] Create project types in `src/types/project.ts`
- [ ] T059 [US3] Add project store in `src/stores/projectStore.ts`
- [ ] T060 [US3] Implement project CRUD commands in `src-tauri/src/commands/project.rs`
- [ ] T061 [US3] Implement project DB operations in `src-tauri/src/db/projects.rs`
- [ ] T062 [P] [US3] Create ProjectList page in `src/pages/ProjectsPage.tsx`
- [ ] T063 [P] [US3] Create ProjectCard component in `src/components/projects/ProjectCard.tsx`
- [ ] T064 [P] [US3] Create ProjectDetail page in `src/pages/ProjectDetailPage.tsx`
- [ ] T065 [US3] Implement CreateProject dialog in `src/components/dialogs/CreateProjectDialog.tsx`
- [ ] T066 [US3] Add department selector (12 Empire departments) in `src/components/projects/DepartmentSelect.tsx`
- [ ] T067 [US3] Implement project search in `src/components/projects/ProjectSearch.tsx`
- [ ] T068 [US3] Add project to sidebar navigation in `src/components/layout/Sidebar.tsx`
- [ ] T069 [US3] Connect conversations to projects in `src/stores/conversationStore.ts`

**Checkpoint**: Projects CRUD works, conversations can be organized by project

---

## Phase 6: User Story 4 - Local Storage & Persistence (Priority: P0)

**Goal**: All data persists locally in SQLite, survives app restarts

**Independent Test**: Create chats/projects, quit app, reopen, verify all data intact

### Implementation for User Story 4

- [ ] T070 [US4] Implement auto-save on message send in `src-tauri/src/db/messages.rs`
- [ ] T071 [US4] Implement message retrieval for conversation in `src-tauri/src/commands/messages.rs`
- [ ] T072 [US4] Add database encryption at rest in `src-tauri/src/db/encryption.rs` (FR-4.3)
- [ ] T073 [US4] Implement settings persistence in `src-tauri/src/db/settings.rs`
- [ ] T074 [US4] Create data export functionality in `src-tauri/src/commands/export.rs`
- [ ] T075 [US4] Handle database migration on app update in `src-tauri/src/db/migrate.rs`

**Checkpoint**: Data persists across restarts, database is encrypted

---

## Phase 7: User Story 5 - Project Instructions & Memory (Priority: P1)

**Goal**: User can set custom instructions per project that affect AI behavior

**Independent Test**: Set project instructions "Always respond in bullet points", verify AI follows them

### Implementation for User Story 5

- [ ] T076 [US5] Add instructions field to project schema in `src-tauri/src/db/schema/projects.sql`
- [ ] T077 [US5] Create InstructionsEditor component in `src/components/projects/InstructionsEditor.tsx`
- [ ] T078 [US5] Create MemoryEditor component in `src/components/projects/MemoryEditor.tsx`
- [ ] T079 [US5] Implement instructions injection into API calls in `src-tauri/src/api/query.rs`
- [ ] T080 [US5] Add project context panel in `src/components/projects/ProjectContextPanel.tsx`
- [ ] T081 [US5] Implement auto-memory extraction from conversations in `src-tauri/src/commands/memory.rs`

**Checkpoint**: Project instructions modify AI behavior, memory persists

---

## Phase 8: User Story 6 - MCP Client Foundation (Priority: P1)

**Goal**: App can connect to MCP servers and discover available tools

**Independent Test**: Configure Supabase MCP, verify connection and tool discovery

### Implementation for User Story 6

- [ ] T082 [US6] Create MCP types in `src/types/mcp.ts`
- [ ] T083 [US6] Implement MCP client core in `src-tauri/src/mcp/client.rs`
- [ ] T084 [US6] Implement JSON-RPC protocol handler in `src-tauri/src/mcp/jsonrpc.rs`
- [ ] T085 [US6] Implement server lifecycle management in `src-tauri/src/mcp/lifecycle.rs`
- [ ] T086 [US6] Create MCP config file parser for `~/.empire/mcp_settings.json` in `src-tauri/src/mcp/config.rs`
- [ ] T087 [US6] Implement tool discovery in `src-tauri/src/mcp/tools.rs`
- [ ] T088 [US6] Implement tool invocation in `src-tauri/src/mcp/invoke.rs`
- [ ] T089 [US6] Create MCP status indicator in `src/components/mcp/McpStatusIndicator.tsx`
- [ ] T090 [US6] Implement MCP server management UI in `src/components/settings/McpServerSettings.tsx`

**Checkpoint**: MCP servers connect, tools discovered and can be invoked

---

## Phase 9: User Story 7 - Search & Keyboard Shortcuts (Priority: P1)

**Goal**: User can search all conversations and use keyboard shortcuts

**Independent Test**: Cmd+K opens search, find message from weeks ago, Cmd+N creates new chat

### Implementation for User Story 7

- [ ] T091 [US7] Implement full-text search in SQLite in `src-tauri/src/db/search.rs`
- [ ] T092 [US7] Create search command in `src-tauri/src/commands/search.rs`
- [ ] T093 [US7] Create CommandPalette component (Cmd+K) in `src/components/CommandPalette.tsx`
- [ ] T094 [US7] Implement search results display in `src/components/search/SearchResults.tsx`
- [ ] T095 [US7] Implement jump-to-message navigation in `src/hooks/useNavigation.ts`
- [ ] T096 [US7] Setup keyboard shortcut system in `src/hooks/useKeyboardShortcuts.ts`
- [ ] T097 [US7] Implement all shortcuts: Cmd+N, Cmd+K, Cmd+Enter, etc. in `src/lib/shortcuts.ts`
- [ ] T098 [US7] Create keyboard shortcuts help panel in `src/components/dialogs/ShortcutsDialog.tsx`

**Checkpoint**: Search works across all chats, keyboard shortcuts functional

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final polish, packaging, and release preparation

### Settings & Preferences

- [ ] T099 [P] Create Settings page in `src/pages/SettingsPage.tsx`
- [ ] T100 [P] Implement theme toggle (dark/light) in `src/components/settings/ThemeToggle.tsx`
- [ ] T101 [P] Implement API endpoint configuration in `src/components/settings/ApiSettings.tsx`
- [ ] T102 Implement settings persistence in `src-tauri/src/commands/settings.rs`

### App Packaging

- [ ] T103 Configure DMG packaging in `src-tauri/tauri.conf.json`
- [ ] T104 Setup code signing for macOS in build scripts
- [ ] T105 [P] Create app icon set for all required sizes in `src-tauri/icons/`
- [ ] T106 Configure auto-update with Sparkle in `src-tauri/Cargo.toml`
- [ ] T107 Create release build script in `scripts/build-release.sh`

### Documentation & Cleanup

- [ ] T108 [P] Create README.md for empire-desktop
- [ ] T109 [P] Document keyboard shortcuts in `docs/SHORTCUTS.md`
- [ ] T110 [P] Document MCP configuration in `docs/MCP_SETUP.md`
- [ ] T111 Code review and cleanup across all files
- [ ] T112 Performance optimization pass
- [ ] T113 Security audit of token storage and data handling

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1-4 (Phases 3-6)**: Depend on Foundational, can be done sequentially
- **US5-7 (Phases 7-9)**: Depend on US1-4 completion
- **Polish (Phase 10)**: Depends on all core features complete

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational
    ↓
┌───────────────────────────────────────┐
│  Phase 3: US1 - Chat Interface (MVP)  │
│              ↓                        │
│  Phase 4: US2 - History & Sidebar     │
│              ↓                        │
│  Phase 5: US3 - Projects              │
│              ↓                        │
│  Phase 6: US4 - Persistence           │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│  Phase 7: US5 - Instructions/Memory   │
│  Phase 8: US6 - MCP Foundation        │ (can run in parallel)
│  Phase 9: US7 - Search & Shortcuts    │
└───────────────────────────────────────┘
    ↓
Phase 10: Polish
```

### Within Each User Story

- Models/types before components
- Rust backend before React frontend
- Core functionality before polish
- Commit after each task

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- Within each US: parallel tasks can be done simultaneously
- US5, US6, US7 can potentially run in parallel after US1-4 complete

---

## Parallel Example: User Story 1

```bash
# Launch in parallel - different files, no dependencies:
T033: ChatMessage component
T034: ChatInput component
T035: TypingIndicator component

# Then sequentially:
T036: ChatContainer (depends on above components)
T037-T039: Backend streaming (sequential)
T044: Integration (depends on all above)
```

---

## Implementation Strategy

### MVP First (User Stories 1-2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 - Chat works
4. Complete Phase 4: User Story 2 - History sidebar
5. **STOP and VALIDATE**: Can chat and see history
6. Package DMG and test

### Incremental Delivery

| Milestone | Stories Complete | Deliverable |
|-----------|-----------------|-------------|
| MVP | US1 + US2 | Chat with history sidebar |
| Alpha | US1-4 | Projects, persistence |
| Beta | US1-7 | MCP, search, shortcuts |
| v1.0 | All | Polished release |

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1: Setup | 10 | Project initialization |
| Phase 2: Foundational | 20 | Database, API, commands |
| Phase 3: US1 Chat | 14 | Core chat interface |
| Phase 4: US2 History | 13 | Sidebar and history |
| Phase 5: US3 Projects | 12 | Project management |
| Phase 6: US4 Storage | 6 | Persistence |
| Phase 7: US5 Memory | 6 | Instructions/memory |
| Phase 8: US6 MCP | 9 | MCP client |
| Phase 9: US7 Search | 8 | Search & shortcuts |
| Phase 10: Polish | 15 | Packaging & docs |
| **Total** | **113** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- MVP = Phases 1-4 (Setup + Foundation + US1 + US2)
- Each checkpoint validates independent functionality
- Commit after each task or logical group
