# Quickstart: Empire Desktop v7.5 Validation

**Purpose**: Step-by-step guide to validate Empire Desktop functionality
**Date**: 2025-01-02

---

## Prerequisites

Before starting validation, ensure:

- [ ] macOS 12.0+ (Monterey or later)
- [ ] Empire API is running: `curl https://jb-empire-api.onrender.com/health`
- [ ] Valid Clerk authentication credentials
- [ ] (For MCP) MCP server configs in `~/.empire/mcp_settings.json`

---

## Phase 1: MVP Validation (Phases 1-4)

### Test 1.1: App Launch

**Steps**:
1. Double-click Empire Desktop.app
2. Wait for app to fully load

**Expected**:
- App window appears within 2 seconds
- Dark theme UI with sidebar visible
- "New Chat" button is clickable
- No error dialogs

**Pass Criteria**: App launches cleanly, UI renders correctly

---

### Test 1.2: First Chat Message

**Steps**:
1. Click "New Chat" or press Cmd+N
2. Type: "What is Empire?"
3. Press Enter or click Send

**Expected**:
- Message appears in chat area (right-aligned)
- Typing indicator shows
- Response streams in real-time (word by word)
- Response contains source citations [1], [2], etc.
- Response is left-aligned with markdown formatting

**Pass Criteria**: Message sent, streaming response received with citations

---

### Test 1.3: Source Citation Popup

**Steps**:
1. Complete Test 1.2
2. Click on a citation number [1] in the response

**Expected**:
- Popup appears near the citation
- Shows: document title, page number (if available), excerpt
- Clicking outside closes popup

**Pass Criteria**: Citations are clickable and show source details

---

### Test 1.4: Stop Generation

**Steps**:
1. Start a new chat with a complex query: "Explain all features of Empire v7.3 in detail"
2. While streaming, click the Stop button

**Expected**:
- Response stops immediately (within 500ms)
- Partial response is preserved
- Can send new message after stopping

**Pass Criteria**: Generation stops cleanly, partial response saved

---

### Test 1.5: Chat History Sidebar

**Steps**:
1. Create 3 different chats with distinct topics:
   - "What is Empire?"
   - "How does RAG work?"
   - "Explain vector search"
2. Check sidebar after each

**Expected**:
- Each chat appears in sidebar
- Most recent chat at top
- Chat titles are auto-generated from first message
- Clicking chat switches to that conversation

**Pass Criteria**: All chats visible, navigation works

---

### Test 1.6: Chat Persistence (App Restart)

**Steps**:
1. Note the chats and messages from previous tests
2. Quit app completely (Cmd+Q)
3. Relaunch app

**Expected**:
- All previous chats appear in sidebar
- Clicking a chat shows full message history
- No data loss

**Pass Criteria**: Data persists across restart

---

### Test 1.7: Create Project

**Steps**:
1. Click "Projects" in sidebar
2. Click "New Project"
3. Enter:
   - Name: "Test Project"
   - Description: "For testing"
   - Department: "IT & Engineering"
4. Click Create

**Expected**:
- Project appears in project list
- Project card shows name and department
- Can click to open project detail view

**Pass Criteria**: Project created, visible in list

---

### Test 1.8: Chat Within Project

**Steps**:
1. Open "Test Project" from Test 1.7
2. Click "New Chat" within project
3. Send message: "Hello from project"
4. Go back to Projects, open project again

**Expected**:
- Chat is associated with project
- Chat appears under project's conversation list
- Chat NOT visible in main "Chats" list (only in project)

**Pass Criteria**: Project-scoped conversations work

---

### Test 1.9: Delete Chat

**Steps**:
1. Right-click a chat in sidebar
2. Select "Delete"
3. Confirm deletion

**Expected**:
- Confirmation dialog appears
- After confirm, chat removed from sidebar
- Chat data deleted from database

**Pass Criteria**: Chat deletion works with confirmation

---

### Test 1.10: Rename Chat

**Steps**:
1. Right-click a chat in sidebar
2. Select "Rename"
3. Enter new title: "Custom Title"
4. Press Enter

**Expected**:
- Edit field appears inline
- New title saved after Enter
- Title persists after app restart

**Pass Criteria**: Chat rename works

---

## Phase 2: Projects & MCP Validation (Phases 5-8)

### Test 2.1: Project Instructions

**Steps**:
1. Open a project
2. Click "Instructions" tab
3. Enter: "Always respond in bullet points. Be concise."
4. Save
5. Start new chat in project: "Explain vector databases"

**Expected**:
- Instructions saved
- AI response follows instructions (uses bullet points)
- Instructions apply to all chats in project

**Pass Criteria**: Project instructions modify AI behavior

---

### Test 2.2: Project Memory

**Steps**:
1. In project chat: "Remember that I prefer Python examples"
2. Check Memory tab
3. In new chat: "Show me how to connect to a database"

**Expected**:
- Memory tab shows extracted context
- New chat incorporates memory (shows Python examples)
- Memory persists across sessions

**Pass Criteria**: Memory auto-extracts and influences responses

---

### Test 2.3: MCP Server Connection (Supabase)

**Prerequisites**:
- `~/.empire/mcp_settings.json` configured with Supabase MCP
- Valid Supabase credentials

**Steps**:
1. Open Settings → MCP Servers
2. Verify Supabase server shows "Connected" status
3. In chat: "List all tables in my Supabase database"

**Expected**:
- MCP status indicator shows green
- AI uses Supabase MCP tool
- Response includes actual table names

**Pass Criteria**: MCP tool invocation works

---

### Test 2.4: MCP Server Connection (Neo4j)

**Prerequisites**:
- `~/.empire/mcp_settings.json` configured with Neo4j MCP
- Neo4j running on Mac Studio

**Steps**:
1. Open Settings → MCP Servers
2. Verify Neo4j server shows "Connected" status
3. In chat: "What nodes exist in my knowledge graph?"

**Expected**:
- Neo4j MCP connected
- AI uses Neo4j MCP tool
- Response includes graph data

**Pass Criteria**: Neo4j MCP works

---

### Test 2.5: Global Search

**Steps**:
1. Press Cmd+K (or click search icon)
2. Type: "vector"
3. Review results

**Expected**:
- Command palette opens
- Search results show matching messages
- Results include conversation title and snippet
- Clicking result navigates to message

**Pass Criteria**: Search finds messages across all chats

---

## Phase 3: Polish Validation (Phases 9-10)

### Test 3.1: Keyboard Shortcuts

**Test each shortcut**:

| Shortcut | Expected Action |
|----------|-----------------|
| Cmd+N | New chat |
| Cmd+Shift+N | New project |
| Cmd+K | Open search |
| Cmd+, | Open settings |
| Cmd+Enter | Send message |
| Cmd+W | Close current chat/view |
| Esc | Close dialogs/popups |

**Pass Criteria**: All shortcuts work as expected

---

### Test 3.2: Theme Toggle

**Steps**:
1. Open Settings
2. Change theme to Light
3. Observe UI
4. Change back to Dark

**Expected**:
- Theme changes immediately
- All UI elements update (not just main area)
- Setting persists after restart

**Pass Criteria**: Theme toggle works

---

### Test 3.3: Offline Mode (View Only)

**Steps**:
1. Disconnect from internet
2. Open app
3. Browse chat history
4. Try to send a message

**Expected**:
- App opens normally
- Can view all past chats
- Can search history
- Send shows error: "No internet connection"

**Pass Criteria**: Offline viewing works, send fails gracefully

---

### Test 3.4: App Auto-Update Check

**Steps**:
1. Check Help → Check for Updates
2. Or observe automatic check on launch

**Expected**:
- Update check runs
- Shows current version
- If update available, shows download option

**Pass Criteria**: Update mechanism works

---

## Performance Validation

### Perf 1: App Launch Time

**Measurement**:
1. Time from double-click to UI ready
2. Run 5 times, take average

**Target**: < 2 seconds

---

### Perf 2: Chat Response Start

**Measurement**:
1. Time from Send click to first token
2. Exclude API processing time (measure from API response start)

**Target**: < 1 second

---

### Perf 3: Sidebar Load

**Setup**: 500+ conversations in database

**Measurement**:
1. Time to render conversation list

**Target**: < 500ms

---

### Perf 4: Search Speed

**Setup**: 100k+ messages

**Measurement**:
1. Time from query to results displayed

**Target**: < 500ms

---

### Perf 5: Memory Usage

**Measurement**:
1. Activity Monitor → Memory column
2. Idle: just app open
3. Active: during streaming response

**Target**:
- Idle: < 150MB
- Active: < 300MB

---

## Security Validation

### Sec 1: Token Storage

**Steps**:
1. Login to app
2. Open Keychain Access
3. Search for "empire"

**Expected**:
- JWT token stored in Keychain
- Not visible in plain text files
- Protected by system security

**Pass Criteria**: Tokens in Keychain only

---

### Sec 2: Database Encryption

**Steps**:
1. Locate database: `~/Library/Application Support/Empire Desktop/`
2. Try to open with sqlite3 command

**Expected**:
- Database file exists
- Cannot read contents without decryption
- App can still read/write normally

**Pass Criteria**: Database encrypted at rest

---

## Validation Checklist Summary

### MVP (Must Pass)
- [ ] App Launch (1.1)
- [ ] Chat Message (1.2)
- [ ] Source Citations (1.3)
- [ ] Stop Generation (1.4)
- [ ] Chat History (1.5)
- [ ] Persistence (1.6)
- [ ] Create Project (1.7)
- [ ] Project Chat (1.8)
- [ ] Delete Chat (1.9)
- [ ] Rename Chat (1.10)

### Phase 2 (Should Pass)
- [ ] Project Instructions (2.1)
- [ ] Project Memory (2.2)
- [ ] MCP Supabase (2.3)
- [ ] MCP Neo4j (2.4)
- [ ] Global Search (2.5)

### Phase 3 (Nice to Have)
- [ ] Keyboard Shortcuts (3.1)
- [ ] Theme Toggle (3.2)
- [ ] Offline Mode (3.3)
- [ ] Auto-Update (3.4)

### Performance
- [ ] Launch < 2s
- [ ] Response < 1s
- [ ] Sidebar < 500ms
- [ ] Search < 500ms
- [ ] Memory < 300MB

### Security
- [ ] Keychain tokens
- [ ] Encrypted database

---

**Validation Complete When**: All MVP tests pass, performance targets met
